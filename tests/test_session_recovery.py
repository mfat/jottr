"""Swap file backup and restoring newly-created unsaved files."""
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

from PyQt6.QtGui import QCloseEvent, QTextCursor
from PyQt6.QtWidgets import QApplication, QMessageBox

import jottr.window as window_module
from jottr.editor.tab import EditorTab
from jottr.main import TextEditorApp
from jottr.session_recovery import (
    STASH_NEW_FILES_SETTING,
    SWAP_FILE_SETTING,
    pop_stashed_documents,
    read_swap_file,
    stash_directory,
    stash_documents,
    swap_file_path,
    text_checksum,
    write_swap_file,
)
from jottr.settings_manager import SettingsManager
from jottr.snippet_manager import SnippetManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


def type_text(tab, text):
    cursor = tab.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(text)
    tab.editor.setTextCursor(cursor)


def stash_names(settings_manager):
    directory = stash_directory(settings_manager)
    return os.listdir(directory) if os.path.isdir(directory) else []


class SessionRecoveryTestCase(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.snippets = SnippetManager(self.settings)

    def write_note(self, text="one\n"):
        path = Path(self.temp_dir.name) / "note.txt"
        path.write_text(text, encoding="utf-8")
        return path


class SwapFileTests(SessionRecoveryTestCase):
    def load_tab(self, path):
        """Open *path* in a new tab the way the window does."""
        text = path.read_text(encoding="utf-8")
        tab = EditorTab(self.snippets, self.settings)
        self.addCleanup(tab.deleteLater)
        self.addCleanup(tab.backup_timer.stop)
        self.addCleanup(tab.swap_timer.stop)
        tab.editor.setPlainText(text)
        tab.current_file = str(path)
        tab.editor.document().setModified(False)
        return tab, tab.load_swap_file(text)

    def test_swap_file_follows_unsaved_changes_and_is_removed_on_save(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, shown = self.load_tab(path)
        self.assertFalse(shown)
        self.assertFalse(tab.write_swap_file())

        type_text(tab, "two\n")
        self.assertTrue(tab.swap_timer.isActive())
        self.assertTrue(tab.write_swap_file())
        data = read_swap_file(swap)
        self.assertEqual(data["text"], "one\ntwo\n")
        self.assertEqual(data["checksum"], text_checksum("one\n"))
        self.assertEqual(data["file"], str(path))

        self.assertTrue(tab.save_file())
        self.assertFalse(os.path.exists(swap))
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo\n")

        # The saved text is the new base for the next swap file.
        type_text(tab, "three\n")
        self.assertTrue(tab.write_swap_file())
        self.assertEqual(read_swap_file(swap)["checksum"], text_checksum("one\ntwo\n"))

    def test_left_over_swap_file_offers_recovery(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        write_swap_file(swap, path, text_checksum("one\n"), "one\ntwo\n")

        tab, shown = self.load_tab(path)
        self.assertTrue(shown)
        self.assertTrue(tab.editor.isReadOnly())
        self.assertFalse(tab.swap_file_bar.isHidden())
        self.assertIn("+two", tab.swap_file_diff())

        self.assertTrue(tab.recover_swap_file())
        self.assertEqual(tab.editor.toPlainText(), "one\ntwo\n")
        self.assertTrue(tab.editor.document().isModified())
        self.assertFalse(tab.editor.isReadOnly())
        self.assertTrue(tab.swap_file_bar.isHidden())
        # Still unsaved, so the swap file stays until the file is saved.
        self.assertTrue(os.path.exists(swap))

        tab.editor.undo()
        self.assertEqual(tab.editor.toPlainText(), "one\n")

    def test_swap_file_for_other_disk_contents_is_removed(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        write_swap_file(swap, path, text_checksum("changed elsewhere\n"), "stale\n")

        tab, shown = self.load_tab(path)
        self.assertFalse(shown)
        self.assertFalse(os.path.exists(swap))
        self.assertFalse(tab.editor.isReadOnly())

    def test_closing_keeps_pending_swap_file_and_discard_removes_it(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        write_swap_file(swap, path, text_checksum("one\n"), "one\ntwo\n")

        tab, shown = self.load_tab(path)
        self.assertTrue(shown)
        tab.release_swap_file()
        self.assertTrue(os.path.exists(swap))

        tab.discard_swap_file()
        self.assertFalse(os.path.exists(swap))
        self.assertEqual(tab.editor.toPlainText(), "one\n")
        self.assertFalse(tab.editor.document().isModified())
        self.assertFalse(tab.editor.isReadOnly())

        type_text(tab, "two\n")
        self.assertTrue(tab.write_swap_file())
        tab.release_swap_file()
        self.assertFalse(os.path.exists(swap))

    def test_disabling_swap_files_stops_and_removes_backups(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, _shown = self.load_tab(path)
        type_text(tab, "two\n")
        self.assertTrue(tab.write_swap_file())

        self.settings.save_setting(SWAP_FILE_SETTING, False)
        tab.apply_swap_file_setting()
        self.assertFalse(os.path.exists(swap))
        type_text(tab, "three\n")
        self.assertFalse(tab.swap_timer.isActive())
        self.assertFalse(tab.write_swap_file())
        self.assertFalse(os.path.exists(swap))


class StashTests(SessionRecoveryTestCase):
    def make_window(self):
        window = TextEditorApp()
        self.addCleanup(window.deleteLater)
        return window

    @staticmethod
    def close_window(window):
        event = QCloseEvent()
        window.closeEvent(event)
        return event.isAccepted()

    def test_stash_round_trip_keeps_order_and_empties_stash(self):
        stash_documents(self.settings, [("First", "a"), ("Second", "b")])
        stash_documents(self.settings, [("Third", "c")])
        self.assertEqual(
            pop_stashed_documents(self.settings),
            [("First", "a"), ("Second", "b"), ("Third", "c")],
        )
        self.assertEqual(stash_names(self.settings), [])

    def test_new_unsaved_files_are_stashed_on_close_and_restored_on_startup(self):
        window = self.make_window()
        tab = window.tab_widget.widget(0)
        type_text(tab, "draft notes")
        window.tab_widget.setTabText(0, "Ideas*")

        with patch.object(
            window_module, "ask_themed_question",
            side_effect=AssertionError("stashed documents must not prompt"),
        ):
            self.assertTrue(self.close_window(window))
            # A repeated close must not stash the documents twice.
            self.assertTrue(self.close_window(window))
        self.assertEqual(len(stash_names(window.settings_manager)), 1)

        restored = self.make_window()
        self.assertEqual(restored.tab_widget.count(), 1)
        restored_tab = restored.tab_widget.widget(0)
        self.assertEqual(restored_tab.editor.toPlainText(), "draft notes")
        self.assertTrue(restored_tab.editor.document().isModified())
        self.assertEqual(restored.tab_widget.tabText(0), "Ideas*")
        self.assertEqual(stash_names(restored.settings_manager), [])

    def test_new_unsaved_files_prompt_when_restoring_is_disabled(self):
        window = self.make_window()
        window.settings_manager.save_setting(STASH_NEW_FILES_SETTING, False)
        type_text(window.tab_widget.widget(0), "draft notes")

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ) as ask:
            self.assertTrue(self.close_window(window))
        ask.assert_called_once()
        self.assertEqual(stash_names(window.settings_manager), [])

    def test_cancelled_close_drops_the_stash(self):
        path = self.write_note()
        window = self.make_window()
        type_text(window.tab_widget.widget(0), "draft notes")
        self.assertTrue(window.open_file(str(path)))
        type_text(window.tab_widget.currentWidget(), "two\n")

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Cancel,
        ) as ask:
            self.assertFalse(self.close_window(window))
        ask.assert_called_once()
        self.assertEqual(stash_names(window.settings_manager), [])

    def test_reopening_a_file_after_a_crash_offers_recovery(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        crashed = self.make_window()
        crashed.open_file(str(path))
        type_text(crashed.tab_widget.currentWidget(), "two\n")
        self.assertTrue(crashed.tab_widget.currentWidget().write_swap_file())

        window = self.make_window()
        window.open_file(str(path))
        tab = window.tab_widget.currentWidget()
        self.assertIsNotNone(tab.swap_recovery)
        self.assertTrue(tab.recover_swap_file())
        self.assertEqual(tab.editor.toPlainText(), "one\ntwo\n")

        # Closing with Discard removes the swap file along with the changes.
        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ):
            self.assertTrue(self.close_window(window))
        self.assertFalse(os.path.exists(swap))


if __name__ == "__main__":
    unittest.main()
