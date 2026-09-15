"""File > Open Recent."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox

import jottr.editor.tab as editor_tab_module
from jottr.main import TextEditorApp
from jottr.window import MAX_RECENT_FILES


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class RecentFilesTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_note(self, name="note.txt", text="one\n"):
        path = Path(self.temp_dir.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def make_window(self):
        window = TextEditorApp()
        self.addCleanup(window.deleteLater)
        return window

    @staticmethod
    def menu_entries(window):
        window.open_recent_menu.aboutToShow.emit()
        return [
            action.data() if action.data() else action.text()
            for action in window.open_recent_menu.actions()
            if not action.isSeparator()
        ]

    def test_opened_files_are_listed_newest_first_then_clear_list(self):
        window = self.make_window()
        self.assertFalse(window.open_recent_menu.menuAction().isEnabled())
        first = self.write_note("first.txt")
        second = self.write_note("second.txt")

        window.open_file(first)
        window.open_file(second)
        window.open_file(first)

        self.assertTrue(window.open_recent_menu.menuAction().isEnabled())
        self.assertEqual(self.menu_entries(window), [first, second, "Clear List"])

        clear = window.open_recent_menu.actions()[-1]
        clear.trigger()
        self.assertEqual(window.get_recent_files(), [])
        self.assertFalse(window.open_recent_menu.menuAction().isEnabled())

    def test_list_keeps_the_newest_entries_and_survives_restart(self):
        window = self.make_window()
        paths = [self.write_note(f"note{number}.txt") for number in range(MAX_RECENT_FILES + 2)]
        for path in paths:
            window.add_recent_file(path)

        expected = list(reversed(paths))[:MAX_RECENT_FILES]
        self.assertEqual(window.get_recent_files(), expected)
        self.assertEqual(self.make_window().get_recent_files(), expected)

    def test_label_names_the_file_and_its_folder(self):
        home = os.path.expanduser("~")
        self.assertEqual(
            TextEditorApp.recent_file_label(os.path.join(home, "notes", "a&b.md")),
            f"a&&b.md [~{os.sep}notes]",
        )
        self.assertEqual(
            TextEditorApp.recent_file_label(os.path.join(os.sep, "srv", "todo.txt")),
            f"todo.txt [{os.sep}srv]",
        )

    def test_choosing_an_entry_opens_it_and_a_missing_one_is_dropped(self):
        window = self.make_window()
        kept = self.write_note("kept.txt", "kept\n")
        gone = self.write_note("gone.txt")
        window.add_recent_file(kept)
        window.add_recent_file(gone)
        os.remove(gone)

        with patch.object(QMessageBox, "critical") as critical:
            self.assertFalse(window.open_recent_file(gone))
        critical.assert_called_once()
        self.assertEqual(window.get_recent_files(), [kept])

        self.assertEqual(self.menu_entries(window), [kept, "Clear List"])
        window.open_recent_menu.actions()[0].trigger()
        tab = window.tab_widget.currentWidget()
        self.assertEqual(tab.current_file, kept)
        self.assertEqual(tab.editor.toPlainText(), "kept\n")

    def test_restoring_a_session_leaves_the_list_alone(self):
        window = self.make_window()
        path = self.write_note()

        window.restore_session_tab({"file": path})

        self.assertEqual(window.tab_widget.currentWidget().current_file, path)
        self.assertEqual(window.get_recent_files(), [])

    def test_save_as_adds_the_file_and_rename_follows_it(self):
        window = self.make_window()
        saved = os.path.join(self.temp_dir.name, "saved.txt")
        tab = window.tab_widget.currentWidget()
        tab.editor.setPlainText("text\n")

        with patch.object(
            editor_tab_module, "get_save_file_name", return_value=(saved, "")
        ):
            self.assertTrue(tab.save_file())
        self.assertEqual(window.get_recent_files(), [saved])

        # A plain save of an already named file does not reorder the list.
        other = self.write_note("other.txt")
        window.add_recent_file(other)
        self.assertTrue(tab.save_file())
        self.assertEqual(window.get_recent_files(), [other, saved])

        self.assertIsNone(window.apply_tab_title(tab, "renamed.txt"))
        renamed = os.path.join(self.temp_dir.name, "renamed.txt")
        self.assertEqual(window.get_recent_files(), [other, renamed])


if __name__ == "__main__":
    unittest.main()
