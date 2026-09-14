"""Swap files, the stash of untitled documents, and the open-tabs session.

Swap files follow KTextEditor's Kate::SwapFile: while a file on disk has
unsaved edits, a copy of the buffer is kept in the swap directory together
with the checksum of the disk text it was based on. Saving, discarding or
closing the document removes it again, so finding one when the file is opened
means the previous run did not close properly.

The stash follows Kate's KateStashManager, but is kept up to date while
typing instead of only on quit, so untitled documents also survive a crash.

The session lists the open tabs (files and stashed untitled documents) and is
rewritten whenever they change, so the next start reopens exactly those tabs
whether Jottr was closed or crashed.
"""
import hashlib
import json
import os
import re

SWAP_FILE_SETTING = "swap_file_enabled"
STASH_NEW_FILES_SETTING = "restore_unsaved_new_files"
# How often unsaved text is written to swap and stash files while typing.
# Default and maximum follow Kate's "Save swap files every" (0 there only
# skips the disk sync; backups are turned off with the checkboxes here).
SWAP_SYNC_INTERVAL_SETTING = "swap_sync_interval_seconds"
SWAP_SYNC_DEFAULT_SECONDS = 15
SWAP_SYNC_MIN_SECONDS = 1
SWAP_SYNC_MAX_SECONDS = 600
# Which previous session the next start reopens.
SESSION_RESTORE_SETTING = "session_restore_mode"
SESSION_RESTORE_ALWAYS = "always"
SESSION_RESTORE_UNSAVED = "unsaved_changes"

SWAP_FILE_VERSION = "Jottr Swap File 1"
SWAP_FILE_SUFFIX = ".jottr-swp"
STASH_FILE_VERSION = "Jottr Stash 1"
STASH_FILE_SUFFIX = ".json"
SESSION_FILE_VERSION = "Jottr Session 1"

_STASH_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")


def text_checksum(text):
    return hashlib.sha1(text.encode("utf-8", "surrogatepass")).hexdigest()


def swap_directory(settings_manager):
    return os.path.join(settings_manager.config_dir, "swap")


def stash_directory(settings_manager):
    return os.path.join(settings_manager.config_dir, "stash")


def session_file_path(settings_manager):
    return os.path.join(settings_manager.config_dir, "session.json")


def swap_file_path(settings_manager, file_path):
    """Swap file for *file_path*, named like Kate's preset swap directory."""
    full_path = os.path.abspath(file_path)
    # The hash of the full path keeps names unique without deep, long paths.
    digest = hashlib.sha1(full_path.encode("utf-8", "surrogatepass")).hexdigest()
    name = f"{digest}-{os.path.basename(full_path)}{SWAP_FILE_SUFFIX}"
    return os.path.join(swap_directory(settings_manager), name)


def is_valid_stash_id(stash_id):
    return isinstance(stash_id, str) and bool(_STASH_ID_PATTERN.fullmatch(stash_id))


def stash_file_path(settings_manager, stash_id):
    return os.path.join(stash_directory(settings_manager), f"{stash_id}{STASH_FILE_SUFFIX}")


def _write_json_atomically(path, data):
    """Write owner-only JSON and sync it to disk before replacing *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        remove_file(temp_path)
        raise


def _read_json(path, version):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != version:
        return None
    return data


def remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        print(f"Could not remove {path}: {error}")


def write_swap_file(path, file_path, checksum, text):
    """Store *text* as the unsaved state of *file_path* (raises OSError)."""
    _write_json_atomically(path, {
        "version": SWAP_FILE_VERSION,
        "file": os.path.abspath(file_path),
        "checksum": checksum,
        "text": text,
    })


def read_swap_file(path):
    """Return the swap data at *path*, or None when missing or invalid."""
    data = _read_json(path, SWAP_FILE_VERSION)
    if data is None or not isinstance(data.get("text"), str):
        return None
    return data


def swap_file_has_changes(settings_manager, file_path):
    """Whether opening *file_path* would restore unsaved changes from its swap file."""
    data = read_swap_file(swap_file_path(settings_manager, file_path))
    if data is None:
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, ValueError):
        return False
    return data.get("checksum") == text_checksum(text) and data["text"] != text


def write_stash_file(path, title, text):
    """Store an untitled document (raises OSError)."""
    _write_json_atomically(path, {
        "version": STASH_FILE_VERSION,
        "title": title,
        "text": text,
    })


def read_stash_file(path):
    """Return {"title", "text"} stashed at *path*, or None when missing or invalid."""
    data = _read_json(path, STASH_FILE_VERSION)
    if data is None or not isinstance(data.get("text"), str):
        return None
    title = data.get("title")
    return {"title": title if isinstance(title, str) else "", "text": data["text"]}


def stash_ids_on_disk(settings_manager):
    """Ids of all stash files, in name order."""
    try:
        names = sorted(os.listdir(stash_directory(settings_manager)))
    except OSError:
        return []
    ids = []
    for name in names:
        if name.endswith(STASH_FILE_SUFFIX):
            stash_id = name[:-len(STASH_FILE_SUFFIX)]
            if is_valid_stash_id(stash_id):
                ids.append(stash_id)
    return ids


def write_session(settings_manager, tabs, current):
    """Store the open tabs: {"file": path} or {"untitled": stash id, "title": title}."""
    _write_json_atomically(session_file_path(settings_manager), {
        "version": SESSION_FILE_VERSION,
        "tabs": tabs,
        "current": current,
    })


def read_session(settings_manager):
    """Return the saved session, or None when there is none yet."""
    data = _read_json(session_file_path(settings_manager), SESSION_FILE_VERSION)
    if data is None or not isinstance(data.get("tabs"), list):
        return None
    return data
