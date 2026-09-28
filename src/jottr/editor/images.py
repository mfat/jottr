"""Markdown images: store pasted, dropped and picked images, and link them.

Like Typora and VS Code, an image is copied into a folder beside the document
("images" by default, Settings > Editor > Markdown) and linked relatively, so
a note and its images move together. A never-saved document has no folder
yet: its images wait in the config directory under an absolute file:// link,
and the first save moves them beside the document and rewrites the links.

Inside Flatpak a document opened through the portal comes without its folder;
see jottr.portal_folders for how Jottr asks for it once and remembers it.
"""
import os
import re
import shutil
from datetime import datetime

from PyQt6.QtCore import QStandardPaths, QUrl
from PyQt6.QtGui import QImage, QPixmap, QTextCursor
from PyQt6.QtWidgets import QMessageBox

from jottr.file_dialogs import get_open_file_name
from jottr.portal_folders import (
    accessible_folder,
    host_path,
    is_within,
    request_folder_access,
)
from jottr.translation_manager import _

IMAGE_EXTENSIONS = frozenset({
    ".apng", ".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".jxl",
    ".png", ".svg", ".tif", ".tiff", ".webp",
})
IMAGE_FOLDER_SETTING = "markdown_image_folder"
IMAGE_FOLDER_DEFAULT = "images"
COPY_IMAGES_SETTING = "markdown_copy_images"
UNSAVED_IMAGES_DIRNAME = "unsaved-images"

# The target of a Markdown image, ![alt](target "title"), in either form.
_IMAGE_TARGET_RE = re.compile(r"!\[[^\]\n]*\]\(\s*(<[^>\n]*>|[^)\s]+)")


def is_image_path(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


class FolderAccessDeclined(Exception):
    """The user would not grant access to the document's folder."""


def image_folder(document_dir, folder_name):
    """Folder in *document_dir* that the document's images are copied into."""
    folder_name = (folder_name or "").strip().strip("/\\")
    return os.path.join(document_dir, folder_name) if folder_name else document_dir


def unique_path(directory, filename):
    """*filename* in *directory*, numbered (name-1.png, ...) if it is taken."""
    stem, extension = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    number = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem}-{number}{extension}")
        number += 1
    return candidate


def pasted_image_name(now=None):
    return f"pasted-{(now or datetime.now()):%Y%m%d-%H%M%S}.png"


def link_target(image_path, document_path):
    """How a document links to *image_path*: relative if saved, else file://.

    Worked out between host paths, since in Flatpak the two can sit in
    different portal folders.
    """
    image_path = host_path(image_path) or image_path
    if document_path:
        document_host = host_path(document_path)
        try:
            if document_host:
                relative = os.path.relpath(image_path, os.path.dirname(document_host))
                return relative.replace(os.sep, "/")
        except ValueError:  # different drives on Windows
            pass
    return QUrl.fromLocalFile(image_path).toString()


def format_target(target):
    """Wrap a target with spaces or parentheses in <...> so it stays one link."""
    if re.search(r"[\s()<>]", target):
        return f"<{target}>"
    return target


def markdown_image(alt, target):
    alt = alt.replace("[", "\\[").replace("]", "\\]")
    return f"![{alt}]({format_target(target)})"


def local_path_of_target(target):
    """Local file path an image target names, or None for relative/remote ones."""
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if target.startswith("file://"):
        return QUrl(target).toLocalFile() or None
    if os.path.isabs(target):
        return target
    return None


def utf16_position(text, index):
    """QTextDocument position of the Python string index *index* in *text*."""
    return len(text[:index].encode("utf-16-le")) // 2


def mime_image_data(mime):
    """The bitmap a clipboard or drop carries, or None."""
    if not mime.hasImage():
        return None
    data = mime.imageData()
    if isinstance(data, QPixmap):
        data = data.toImage()
    if isinstance(data, QImage) and not data.isNull():
        return data
    return None


def _text_is_only_a_url(text):
    text = text.strip()
    return bool(text) and not re.search(r"\s", text) and bool(re.match(r"https?://", text))


def mime_images(mime):
    """Classify what an image paste or drop carries.

    Returns ("files", [local image paths]), ("image", QImage) or
    ("urls", [remote image URLs]), or None when it is not an image.
    """
    urls = mime.urls() if mime.hasUrls() else []
    files = [
        url.toLocalFile() for url in urls
        if url.isLocalFile() and is_image_path(url.toLocalFile())
    ]
    if files:
        return "files", files
    image = mime_image_data(mime)
    # Apps such as spreadsheets put a picture of copied text beside the text,
    # so a bitmap only wins when the text is missing or just its web address
    # (a browser's Copy Image).
    text = mime.text() if mime.hasText() else ""
    if image is not None and (not text.strip() or _text_is_only_a_url(text)):
        return "image", image
    remote = [
        url.toString() for url in urls
        if url.scheme() in ("http", "https") and is_image_path(url.path())
    ]
    if remote:
        return "urls", remote
    return None


class MarkdownImagesMixin:
    """Paste, drop and Insert Image for EditorTab."""

    def image_folder_name(self):
        return self.settings_manager.get_setting(IMAGE_FOLDER_SETTING, IMAGE_FOLDER_DEFAULT)

    def unsaved_images_dir(self):
        return os.path.join(self.settings_manager.config_dir, UNSAVED_IMAGES_DIRNAME)

    def document_folder(self, ask=False):
        """Writable folder of the saved document, None if the sandbox hides it.

        With *ask*, a hidden folder is requested through the portal.
        """
        folder = accessible_folder(self.settings_manager, self.current_file)
        if folder is None and ask:
            folder = request_folder_access(self, self.settings_manager, self.current_file)
        return folder

    def image_destination_dir(self):
        if not self.current_file:
            return self.unsaved_images_dir()
        folder = self.document_folder(ask=True)
        if folder is None:
            raise FolderAccessDeclined()
        return image_folder(folder, self.image_folder_name())

    def accepts_pasted_images(self):
        """Paste and drop turn images into links in Markdown and untitled documents."""
        return not self.current_file or self.is_markdown_file(self.current_file)

    def store_image_file(self, source):
        """Path the document should link to for the image file *source*."""
        source = os.path.abspath(source)
        copy = bool(self.settings_manager.get_setting(COPY_IMAGES_SETTING, True))
        if is_within(source, self.unsaved_images_dir()):
            return source
        if self.current_file:
            # An image already beside the note is linked where it is.
            source_host = host_path(source)
            document_host = host_path(self.current_file)
            if not copy or (
                source_host and document_host
                and is_within(source_host, os.path.dirname(document_host))
            ):
                return source
        elif not copy:
            return source
        directory = self.image_destination_dir()
        os.makedirs(directory, exist_ok=True)
        destination = unique_path(directory, os.path.basename(source))
        shutil.copy2(source, destination)
        return destination

    def store_image_data(self, image):
        """Save a pasted bitmap as PNG and return its path."""
        directory = self.image_destination_dir()
        os.makedirs(directory, exist_ok=True)
        destination = unique_path(directory, pasted_image_name())
        if not image.save(destination, "PNG"):
            raise OSError(_("Could not write {path}").format(path=destination))
        return destination

    def image_links_for_files(self, paths):
        links = []
        for path in paths:
            stored = self.store_image_file(path)
            alt = os.path.splitext(os.path.basename(path))[0]
            links.append(markdown_image(alt, link_target(stored, self.current_file)))
        return links

    def insert_image_links(self, links):
        if links:
            self.editor.textCursor().insertText("\n".join(links))

    def report_image_failure(self, error):
        QMessageBox.warning(
            self, _("Image"), _("Could not save the image: {error}").format(error=error)
        )

    def insert_images_from_mime(self, mime):
        """Link the images a paste or drop carries; False leaves it to plain text."""
        if not self.accepts_pasted_images():
            return False
        found = mime_images(mime)
        if found is None:
            return False
        kind, value = found
        try:
            if kind == "files":
                links = self.image_links_for_files(value)
            elif kind == "image":
                stored = self.store_image_data(value)
                links = [markdown_image("", link_target(stored, self.current_file))]
            else:
                links = [
                    markdown_image(os.path.splitext(os.path.basename(QUrl(url).path()))[0], url)
                    for url in value
                ]
        except FolderAccessDeclined:
            return True
        except OSError as error:
            self.report_image_failure(error)
            return True
        self.insert_image_links(links)
        return True

    def pick_and_insert_image(self):
        """Insert Image: choose an image file and link it at the caret."""
        if self.current_file:
            start_dir = os.path.dirname(self.current_file)
        else:
            start_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.PicturesLocation
            )
        patterns = " ".join(f"*{extension}" for extension in sorted(IMAGE_EXTENSIONS))
        path, _selected = get_open_file_name(
            self,
            _("Insert Image"),
            start_dir,
            f"{_('Images')} ({patterns});;{_('All Files (*.*)')}",
        )
        if not path:
            return False
        try:
            links = self.image_links_for_files([path])
        except FolderAccessDeclined:
            return False
        except OSError as error:
            self.report_image_failure(error)
            return False
        self.insert_image_links(links)
        self.editor.setFocus()
        return True

    def adopt_unsaved_images(self):
        """Move images waiting for this document beside it and relink them.

        Runs on save, once the document has a path. Each link into the unsaved
        images folder is rewritten in place, as one undo step.
        """
        if not self.current_file:
            return
        text = self.editor.toPlainText()
        unsaved_dir = self.unsaved_images_dir()
        moved = {}
        edits = []
        failures = []
        directory = None
        # Declining folder access once is not asked again on every save.
        declined = getattr(self, "_folder_access_declined_for", None) == self.current_file
        for match in _IMAGE_TARGET_RE.finditer(text):
            local = local_path_of_target(match.group(1))
            if not local or not is_within(local, unsaved_dir):
                continue
            key = os.path.normcase(os.path.abspath(local))
            if key not in moved:
                if not os.path.isfile(local):
                    continue
                if directory is None:
                    if declined:
                        break
                    try:
                        directory = self.image_destination_dir()
                    except FolderAccessDeclined:
                        # The links still work from the unsaved images folder.
                        self._folder_access_declined_for = self.current_file
                        break
                try:
                    os.makedirs(directory, exist_ok=True)
                    destination = unique_path(directory, os.path.basename(local))
                    shutil.move(local, destination)
                except OSError as error:
                    failures.append(error)
                    continue
                moved[key] = destination
            new_target = format_target(link_target(moved[key], self.current_file))
            edits.append((match.start(1), match.end(1), new_target))
        if edits:
            cursor = QTextCursor(self.editor.document())
            cursor.beginEditBlock()
            try:
                for start, end, new_target in reversed(edits):
                    cursor.setPosition(utf16_position(text, start))
                    cursor.setPosition(
                        utf16_position(text, end), QTextCursor.MoveMode.KeepAnchor
                    )
                    cursor.insertText(new_target)
            finally:
                cursor.endEditBlock()
        if failures:
            self.report_image_failure(failures[0])
