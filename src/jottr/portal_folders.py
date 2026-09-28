"""Reach a sandboxed document's folder through a document-portal folder grant.

Inside Flatpak a file opened through the portal file chooser appears as
/run/user/<uid>/doc/<id>/<name>. The sandbox sees that one file only, so
nothing can be created beside it (an images folder, a pasted image). A folder
chosen through the portal is exported whole and writable, and the portal keeps
that grant across sessions. Jottr remembers the folders it was granted and
reaches a document's folder through the one that contains it on the host.
"""
import os
import re

from PyQt6.QtWidgets import QMessageBox

from jottr.file_dialogs import get_existing_directory
from jottr.translation_manager import _

GRANTS_SETTING = "portal_folder_grants"
HOME_ACCESS_ASKED_SETTING = "portal_home_access_asked"
HOST_PATH_XATTR = "user.document-portal.host-path"
_DOC_ID_DIR_RE = re.compile(r"^/run/user/\d+/doc/[^/]+$")
_DOC_ENTRY_RE = re.compile(r"^(/run/user/\d+/doc/([^/]+))/[^/]+")


def is_within(path, directory):
    """True when *path* is *directory* or lies somewhere under it."""
    path = os.path.normcase(os.path.abspath(path))
    directory = os.path.normcase(os.path.abspath(directory))
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:  # different drives on Windows
        return False


def is_single_file_folder(directory):
    """True for the portal folder that holds just one exported file."""
    return bool(_DOC_ID_DIR_RE.match(os.path.normpath(directory)))


def _decode_host_path(raw):
    return bytes(raw).split(b"\x00", 1)[0].decode("utf-8", "surrogateescape") or None


def _host_path_from_xattr(entry):
    getxattr = getattr(os, "getxattr", None)
    if getxattr is None:
        return None
    try:
        return _decode_host_path(getxattr(entry, HOST_PATH_XATTR))
    except OSError:
        return None


def _host_path_from_portal(doc_id):
    """The Documents portal's GetHostPaths, for portals without the xattr."""
    try:
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusMessage
    except ImportError:
        return None
    message = QDBusMessage.createMethodCall(
        "org.freedesktop.portal.Documents",
        "/org/freedesktop/portal/documents",
        "org.freedesktop.portal.Documents",
        "GetHostPaths",
    )
    # PyQt sends a plain list as "av"; the portal wants "as".
    doc_ids = QDBusArgument()
    doc_ids.beginArray(QMetaType(QMetaType.Type.QString.value))
    doc_ids.add(doc_id)
    doc_ids.endArray()
    message.setArguments([doc_ids])
    reply = QDBusConnection.sessionBus().call(message)
    if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
        return None
    paths = reply.arguments()[0]
    raw = paths.get(doc_id) if isinstance(paths, dict) else None
    return _decode_host_path(raw) if raw is not None else None


def host_path(path):
    """Where *path* lives on the host; itself outside the document portal.

    None when the portal cannot say.
    """
    path = os.path.abspath(path)
    match = _DOC_ENTRY_RE.match(path)
    if match is None:
        return path
    entry = match.group(0)
    host = _host_path_from_xattr(entry) or _host_path_from_portal(match.group(2))
    if not host:
        return None
    tail = os.path.relpath(path, entry)
    return host if tail == "." else os.path.join(host, tail)


def granted_folders(settings_manager):
    """Portal folders Jottr may write in: its grants, then workspace folders."""
    candidates = list(settings_manager.get_setting(GRANTS_SETTING, []) or [])
    workspace = settings_manager.get_setting("workspace_path", "")
    candidates.extend([workspace] if workspace else [])
    candidates.extend(settings_manager.get_setting("recent_workspaces", []) or [])
    folders = []
    for folder in candidates:
        if (
            isinstance(folder, str)
            and _DOC_ENTRY_RE.match(folder)
            and folder not in folders
            and os.path.isdir(folder)
        ):
            folders.append(folder)
    return folders


def remember_grant(settings_manager, folder):
    grants = [
        grant for grant in settings_manager.get_setting(GRANTS_SETTING, []) or []
        if grant != folder
    ]
    settings_manager.save_setting(GRANTS_SETTING, [folder] + grants)


def _folder_through_grant(host_dir, grant):
    grant_host = host_path(grant)
    if grant_host and is_within(host_dir, grant_host):
        return os.path.normpath(os.path.join(grant, os.path.relpath(host_dir, grant_host)))
    return None


def accessible_folder(settings_manager, document_path):
    """A writable path to *document_path*'s folder, or None until one is granted."""
    directory = os.path.dirname(os.path.abspath(document_path))
    if not is_single_file_folder(directory):
        return directory
    document_host = host_path(document_path)
    if not document_host:
        return None
    host_dir = os.path.dirname(document_host)
    for grant in granted_folders(settings_manager):
        folder = _folder_through_grant(host_dir, grant)
        if folder and os.path.isdir(folder):
            return folder
    return None


def has_home_grant(settings_manager):
    """True when a remembered grant covers the home folder."""
    home = os.path.expanduser("~")
    for grant in granted_folders(settings_manager):
        grant_host = host_path(grant)
        if grant_host and is_within(home, grant_host):
            return True
    return False


def request_home_access(parent, settings_manager):
    """Ask once for the home folder through the portal and remember the grant.

    Documents opened later from anywhere in home then come with their folder,
    so the preview shows their images and pasted images land beside them.
    Returns True when a new folder was granted.
    """
    if settings_manager.get_setting(HOME_ACCESS_ASKED_SETTING, False):
        return False
    if has_home_grant(settings_manager):
        return False
    settings_manager.save_setting(HOME_ACCESS_ASKED_SETTING, True)
    home = os.path.expanduser("~")
    answer = QMessageBox.question(
        parent,
        _("Allow Folder Access"),
        _(
            "Jottr runs in a sandbox and can only see the documents you open, "
            "not the folders they are in. Images linked from a document, such "
            "as a README's screenshots, cannot be shown, and pasted images "
            "cannot be saved beside it.\n\n"
            "Choose your home folder {folder} to let Jottr see the folders of "
            "the documents you open. Jottr remembers the folder you choose."
        ).format(folder=home),
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Ok,
    )
    if answer != QMessageBox.StandardButton.Ok:
        return False
    chosen = get_existing_directory(parent, _("Choose Your Home Folder"), home)
    if not chosen or not _DOC_ENTRY_RE.match(os.path.abspath(chosen)):
        return False
    remember_grant(settings_manager, chosen)
    return True


def request_folder_access(parent, settings_manager, document_path):
    """Ask for the document's folder (or one above it) through the portal.

    Returns the writable folder, or None when the user declines or picks a
    folder that does not contain the document.
    """
    document_host = host_path(document_path)
    host_dir = os.path.dirname(document_host) if document_host else ""
    answer = QMessageBox.question(
        parent,
        _("Allow Folder Access"),
        _(
            "Jottr can only see this document, not the folder it is in, so it "
            "cannot save images beside it.\n\n"
            "Choose the folder {folder}, or a folder above it such as your home "
            "folder, to let Jottr save images there. Jottr remembers the folder "
            "you choose."
        ).format(folder=host_dir or _("that holds the document")),
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Ok,
    )
    if answer != QMessageBox.StandardButton.Ok:
        return None
    chosen = get_existing_directory(parent, _("Choose the Document's Folder"), host_dir)
    if not chosen:
        return None
    folder = _folder_through_grant(host_dir, chosen) if host_dir else None
    if folder is None or not os.path.isdir(folder):
        QMessageBox.warning(
            parent,
            _("Allow Folder Access"),
            _("The folder you chose does not contain the document."),
        )
        return None
    remember_grant(settings_manager, chosen)
    return folder
