"""Pasting, dropping and inserting images into Markdown documents."""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from jottr.editor import images
from jottr.editor.tab import EditorTab
from jottr.settings_manager import SettingsManager
from jottr.snippet_manager import SnippetManager

_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


def red_image():
    image = QImage(4, 3, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    return image


def image_mime(image=None, text=None):
    mime = QMimeData()
    mime.setImageData(image or red_image())
    if text is not None:
        mime.setText(text)
    return mime


def url_mime(*urls):
    mime = QMimeData()
    mime.setUrls([QUrl(url) if "://" in url else QUrl.fromLocalFile(url) for url in urls])
    return mime


class ImageHelperTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_link_target_is_relative_to_the_document(self):
        self.assertEqual(
            images.link_target("/notes/images/cat.png", "/notes/today.md"), "images/cat.png"
        )
        self.assertEqual(
            images.link_target("/pictures/cat.png", "/notes/today.md"), "../pictures/cat.png"
        )

    def test_untitled_documents_link_by_file_url(self):
        self.assertEqual(images.link_target("/tmp/a/cat.png", None), "file:///tmp/a/cat.png")

    def test_targets_with_spaces_or_parentheses_are_bracketed(self):
        self.assertEqual(images.markdown_image("cat", "images/cat.png"), "![cat](images/cat.png)")
        self.assertEqual(images.markdown_image("my cat", "images/my cat.png"),
                         "![my cat](<images/my cat.png>)")
        self.assertEqual(images.markdown_image("a", "a(1).png"), "![a](<a(1).png>)")
        self.assertEqual(images.markdown_image("[x]", "x.png"), "![\\[x\\]](x.png)")

    def test_unique_path_numbers_taken_names(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(images.unique_path(folder, "cat.png"), os.path.join(folder, "cat.png"))
            Path(folder, "cat.png").touch()
            Path(folder, "cat-1.png").touch()
            self.assertEqual(images.unique_path(folder, "cat.png"), os.path.join(folder, "cat-2.png"))

    def test_pasted_image_name_carries_the_time(self):
        self.assertEqual(
            images.pasted_image_name(datetime(2026, 9, 29, 14, 30, 12)),
            "pasted-20260929-143012.png",
        )

    def test_image_folder_setting(self):
        self.assertEqual(images.image_folder("/notes/a.md", "images"), "/notes/images")
        self.assertEqual(images.image_folder("/notes/a.md", " assets/ "), "/notes/assets")
        self.assertEqual(images.image_folder("/notes/a.md", ""), "/notes")

    def test_mime_classification(self):
        self.assertEqual(images.mime_images(url_mime("/pics/a.png", "/pics/b.txt")),
                         ("files", ["/pics/a.png"]))
        self.assertIsNone(images.mime_images(url_mime("/pics/b.txt")))
        self.assertEqual(images.mime_images(image_mime())[0], "image")
        # A browser's Copy Image carries the picture's address as text.
        self.assertEqual(images.mime_images(image_mime(text="https://x.org/a.png"))[0], "image")
        # A spreadsheet's copied cells carry a picture of the text beside it.
        self.assertIsNone(images.mime_images(image_mime(text="a\tb\n1\t2")))
        self.assertEqual(images.mime_images(url_mime("https://x.org/cat.jpg?s=2")),
                         ("urls", ["https://x.org/cat.jpg?s=2"]))
        plain = QMimeData()
        plain.setText("hello")
        self.assertIsNone(images.mime_images(plain))

    def test_local_path_of_target(self):
        self.assertEqual(images.local_path_of_target("file:///tmp/a%20b.png"), "/tmp/a b.png")
        self.assertEqual(images.local_path_of_target("<file:///tmp/a b.png>"), "/tmp/a b.png")
        self.assertEqual(images.local_path_of_target("/tmp/a.png"), "/tmp/a.png")
        self.assertIsNone(images.local_path_of_target("images/a.png"))
        self.assertIsNone(images.local_path_of_target("https://x.org/a.png"))


class EditorImageTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": os.path.join(self.temp_dir.name, "config")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.snippets = SnippetManager(self.settings)
        self.notes = Path(self.temp_dir.name, "notes")
        self.notes.mkdir()

    def make_tab(self, file_name=None):
        tab = EditorTab(self.snippets, self.settings)
        self.addCleanup(tab.deleteLater)
        self.addCleanup(tab.backup_timer.stop)
        self.addCleanup(tab.swap_timer.stop)
        if file_name:
            tab.current_file = str(self.notes / file_name)
        return tab

    def picture(self, name="cat.png", folder=None):
        folder = Path(folder or Path(self.temp_dir.name, "pictures"))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        red_image().save(str(path), "PNG")
        return path

    def test_pasting_an_image_saves_it_beside_the_document(self):
        tab = self.make_tab("today.md")
        with patch.object(images, "pasted_image_name", return_value="pasted-1.png"):
            tab.editor.insertFromMimeData(image_mime())

        self.assertEqual(tab.editor.toPlainText(), "![](images/pasted-1.png)")
        saved = QImage(str(self.notes / "images" / "pasted-1.png"))
        self.assertEqual((saved.width(), saved.height()), (4, 3))

    def test_dropping_image_files_copies_them_and_links_each(self):
        tab = self.make_tab("today.md")
        first = self.picture("cat.png")
        second = self.picture("my dog.png")
        mime = url_mime(str(first), str(second))
        self.assertTrue(tab.editor.canInsertFromMimeData(mime))

        tab.editor.insertFromMimeData(mime)

        self.assertEqual(
            tab.editor.toPlainText(),
            "![cat](images/cat.png)\n![my dog](<images/my dog.png>)",
        )
        self.assertTrue((self.notes / "images" / "cat.png").is_file())
        self.assertTrue((self.notes / "images" / "my dog.png").is_file())
        self.assertTrue(first.is_file())

    def test_images_already_beside_the_document_are_linked_in_place(self):
        tab = self.make_tab("today.md")
        picture = self.picture("cat.png", self.notes / "art")
        tab.editor.insertFromMimeData(url_mime(str(picture)))

        self.assertEqual(tab.editor.toPlainText(), "![cat](art/cat.png)")
        self.assertFalse((self.notes / "images").exists())

    def test_linking_originals_when_copying_is_off(self):
        self.settings.save_setting(images.COPY_IMAGES_SETTING, False)
        tab = self.make_tab("today.md")
        picture = self.picture("cat.png")
        tab.editor.insertFromMimeData(url_mime(str(picture)))

        self.assertEqual(tab.editor.toPlainText(), "![cat](../pictures/cat.png)")
        self.assertFalse((self.notes / "images").exists())

    def test_image_folder_setting_is_used(self):
        self.settings.save_setting(images.IMAGE_FOLDER_SETTING, "")
        tab = self.make_tab("today.md")
        tab.editor.insertFromMimeData(url_mime(str(self.picture("cat.png"))))

        self.assertEqual(tab.editor.toPlainText(), "![cat](cat.png)")
        self.assertTrue((self.notes / "cat.png").is_file())

    def test_plain_text_documents_paste_images_as_text(self):
        tab = self.make_tab("today.txt")
        picture = self.picture("cat.png")
        mime = url_mime(str(picture))
        mime.setText(str(picture))
        tab.editor.insertFromMimeData(mime)

        self.assertEqual(tab.editor.toPlainText(), str(picture))

    def test_insert_image_links_the_chosen_file(self):
        tab = self.make_tab("today.md")
        picture = self.picture("cat.png")
        with patch.object(images, "get_open_file_name", return_value=(str(picture), "")):
            self.assertTrue(tab.pick_and_insert_image())

        self.assertEqual(tab.editor.toPlainText(), "![cat](images/cat.png)")

    def test_untitled_images_move_beside_the_document_on_first_save(self):
        tab = self.make_tab()
        tab.editor.setPlainText("😀 note\n")
        cursor = tab.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        tab.editor.setTextCursor(cursor)
        with patch.object(images, "pasted_image_name", return_value="pasted-1.png"):
            tab.editor.insertFromMimeData(image_mime())
        tab.editor.insertPlainText("\n")
        tab.editor.insertFromMimeData(url_mime(str(self.picture("my cat.png"))))

        waiting = Path(tab.unsaved_images_dir())
        self.assertTrue((waiting / "pasted-1.png").is_file())
        self.assertIn(QUrl.fromLocalFile(str(waiting / "pasted-1.png")).toString(),
                      tab.editor.toPlainText())

        document = self.notes / "today.md"
        with patch("jottr.editor.tab.get_save_file_name", return_value=(str(document), "")):
            self.assertTrue(tab.save_file())

        expected = "😀 note\n![](images/pasted-1.png)\n![my cat](<images/my cat.png>)"
        self.assertEqual(tab.editor.toPlainText(), expected)
        self.assertEqual(document.read_text(encoding="utf-8"), expected)
        self.assertTrue((self.notes / "images" / "pasted-1.png").is_file())
        self.assertTrue((self.notes / "images" / "my cat.png").is_file())
        self.assertFalse((waiting / "pasted-1.png").exists())
        # The relinking is one undo step on top of the edits.
        tab.editor.undo()
        self.assertIn(images.UNSAVED_IMAGES_DIRNAME, tab.editor.toPlainText())


if __name__ == "__main__":
    unittest.main()
