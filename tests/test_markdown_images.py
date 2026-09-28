"""Pasting, dropping and inserting images into Markdown documents."""
import os
import re
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

from jottr import portal_folders
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
        self.assertEqual(images.image_folder("/notes", "images"), "/notes/images")
        self.assertEqual(images.image_folder("/notes", " assets/ "), "/notes/assets")
        self.assertEqual(images.image_folder("/notes", ""), "/notes")

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



class PortalFolderTests(unittest.TestCase):
    """Flatpak: a portal document has no folder until one is granted.

    A temp folder stands in for /run/user/<uid>/doc. note.md is exported alone
    under doc id "file"; the user's home folder is exported under "home".
    """

    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": os.path.join(self.temp_dir.name, "config")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.snippets = SnippetManager(self.settings)

        mount = Path(self.temp_dir.name, "doc")
        self.document = mount / "file" / "note.md"
        self.document.parent.mkdir(parents=True)
        self.document.write_text("", encoding="utf-8")
        self.home_grant = mount / "home" / "me"
        (self.home_grant / "notes").mkdir(parents=True)
        (self.home_grant / "pictures").mkdir()
        red_image().save(str(self.home_grant / "pictures" / "cat.png"), "PNG")
        self.picked = mount / "picked" / "cat.png"
        self.picked.parent.mkdir()
        red_image().save(str(self.picked), "PNG")
        host_paths = {
            str(self.document): "/home/me/notes/note.md",
            str(self.home_grant): "/home/me",
            str(self.picked): "/home/me/pictures/cat.png",
        }
        root = re.escape(str(mount))
        for name, value in (
            ("_DOC_ID_DIR_RE", re.compile(rf"^{root}/[^/]+$")),
            ("_DOC_ENTRY_RE", re.compile(rf"^({root}/([^/]+))/[^/]+")),
            ("_host_path_from_xattr", host_paths.get),
            ("_host_path_from_portal", lambda _doc_id: None),
        ):
            patcher = patch.object(portal_folders, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_tab(self):
        tab = EditorTab(self.snippets, self.settings)
        self.addCleanup(tab.deleteLater)
        self.addCleanup(tab.backup_timer.stop)
        self.addCleanup(tab.swap_timer.stop)
        tab.current_file = str(self.document)
        return tab

    def grant_on_request(self, chosen):
        question = patch.object(
            portal_folders.QMessageBox, "question",
            return_value=portal_folders.QMessageBox.StandardButton.Ok,
        )
        chooser = patch.object(portal_folders, "get_existing_directory", return_value=chosen)
        return question, chooser

    def test_host_paths_follow_the_exported_entry(self):
        self.assertEqual(
            portal_folders.host_path(str(self.home_grant / "notes" / "images" / "a.png")),
            "/home/me/notes/images/a.png",
        )
        self.assertEqual(portal_folders.host_path("/elsewhere/a.png"), "/elsewhere/a.png")

    def test_document_folder_is_reached_through_a_granted_folder(self):
        self.assertIsNone(portal_folders.accessible_folder(self.settings, str(self.document)))
        portal_folders.remember_grant(self.settings, str(self.home_grant))
        self.assertEqual(
            portal_folders.accessible_folder(self.settings, str(self.document)),
            str(self.home_grant / "notes"),
        )

    def test_workspace_folders_count_as_grants(self):
        self.settings.save_setting("recent_workspaces", [str(self.home_grant)])
        self.assertEqual(
            portal_folders.accessible_folder(self.settings, str(self.document)),
            str(self.home_grant / "notes"),
        )

    def test_paste_asks_for_the_folder_once_and_saves_there(self):
        tab = self.make_tab()
        question, chooser = self.grant_on_request(str(self.home_grant))
        with question as asked, chooser, patch.object(
            images, "pasted_image_name", return_value="pasted-1.png"
        ):
            tab.editor.insertFromMimeData(image_mime())
            tab.editor.insertPlainText("\n")
            tab.editor.insertFromMimeData(image_mime())

        self.assertEqual(asked.call_count, 1)
        self.assertEqual(
            tab.editor.toPlainText(), "![](images/pasted-1.png)\n![](images/pasted-1-1.png)"
        )
        self.assertTrue((self.home_grant / "notes" / "images" / "pasted-1.png").is_file())
        self.assertEqual(
            self.settings.get_setting(portal_folders.GRANTS_SETTING), [str(self.home_grant)]
        )
        self.assertEqual(tab.preview_base_folder(), str(self.home_grant / "notes"))

    def test_declining_folder_access_inserts_nothing(self):
        tab = self.make_tab()
        with patch.object(
            portal_folders.QMessageBox, "question",
            return_value=portal_folders.QMessageBox.StandardButton.Cancel,
        ), patch.object(portal_folders, "get_existing_directory") as chooser:
            tab.editor.insertFromMimeData(image_mime())

        chooser.assert_not_called()
        self.assertEqual(tab.editor.toPlainText(), "")
        self.assertEqual(tab.preview_base_folder(), str(self.document.parent))

    def test_a_folder_that_does_not_hold_the_document_is_refused(self):
        tab = self.make_tab()
        question, chooser = self.grant_on_request(str(self.picked.parent))
        with question, chooser, patch.object(portal_folders.QMessageBox, "warning") as warned:
            tab.editor.insertFromMimeData(image_mime())

        warned.assert_called_once()
        self.assertEqual(tab.editor.toPlainText(), "")
        self.assertEqual(self.settings.get_setting(portal_folders.GRANTS_SETTING, []), [])

    def test_links_are_worked_out_between_host_paths(self):
        portal_folders.remember_grant(self.settings, str(self.home_grant))
        self.settings.save_setting(images.COPY_IMAGES_SETTING, False)
        tab = self.make_tab()
        # A file picked through the portal sits in its own portal folder.
        tab.editor.insertFromMimeData(url_mime(str(self.picked)))
        self.assertEqual(tab.editor.toPlainText(), "![cat](../pictures/cat.png)")

    def test_untitled_images_move_through_the_grant_on_first_save(self):
        portal_folders.remember_grant(self.settings, str(self.home_grant))
        tab = self.make_tab()
        tab.current_file = None
        with patch.object(images, "pasted_image_name", return_value="pasted-1.png"):
            tab.editor.insertFromMimeData(image_mime())
        with patch("jottr.editor.tab.get_save_file_name", return_value=(str(self.document), "")):
            self.assertTrue(tab.save_file())

        self.assertEqual(tab.editor.toPlainText(), "![](images/pasted-1.png)")
        self.assertTrue((self.home_grant / "notes" / "images" / "pasted-1.png").is_file())

    def test_startup_home_grant_gives_the_preview_the_document_folder(self):
        tab = self.make_tab()
        self.assertEqual(tab.preview_base_folder(), str(self.document.parent))
        question, chooser = self.grant_on_request(str(self.home_grant))
        with patch.dict(os.environ, {"HOME": "/home/me"}), question, chooser:
            self.assertTrue(portal_folders.request_home_access(None, self.settings))

        self.assertEqual(tab.preview_base_folder(), str(self.home_grant / "notes"))

    def test_startup_home_request_is_asked_once(self):
        with patch.dict(os.environ, {"HOME": "/home/me"}), patch.object(
            portal_folders.QMessageBox, "question",
            return_value=portal_folders.QMessageBox.StandardButton.Cancel,
        ) as asked:
            self.assertFalse(portal_folders.request_home_access(None, self.settings))
            self.assertFalse(portal_folders.request_home_access(None, self.settings))

        self.assertEqual(asked.call_count, 1)

    def test_startup_home_request_skips_an_existing_home_grant(self):
        portal_folders.remember_grant(self.settings, str(self.home_grant))
        with patch.dict(os.environ, {"HOME": "/home/me"}), patch.object(
            portal_folders.QMessageBox, "question"
        ) as asked:
            self.assertFalse(portal_folders.request_home_access(None, self.settings))

        asked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
