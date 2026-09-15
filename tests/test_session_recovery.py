"""Swap files, untitled document stashes, and reopening the last session."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtCore import QLockFile
from PyQt6.QtGui import QCloseEvent, QTextCursor
from PyQt6.QtWidgets import QApplication, QMessageBox

import jottr.editor.tab as editor_tab_module
import jottr.window as window_module
from jottr.editor.tab import EditorTab
from jottr.main import TextEditorApp
from jottr.session_recovery import (
    STASH_NEW_FILES_SETTING,
    SWAP_FILE_SETTING,
    read_session,
    read_stash_file,
    read_swap_file,
    release_session,
    session_lock_path,
    stash_directory,
    stash_file_path,
    swap_file_path,
    text_checksum,
    write_stash_file,
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


def process_events_for(milliseconds):
    """Run the event loop, so real timers fire."""
    deadline = time.monotonic() + milliseconds / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def wait_until(predicate, timeout_ms):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


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
        self.addCleanup(release_session, self.settings)
        self.snippets = SnippetManager(self.settings)

    def write_note(self, text="one\n", name="note.txt", folder=None):
        folder = Path(folder or self.temp_dir.name)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def make_tab(self):
        tab = EditorTab(self.snippets, self.settings)
        self.addCleanup(tab.deleteLater)
        self.addCleanup(tab.backup_timer.stop)
        self.addCleanup(tab.swap_timer.stop)
        return tab

    def load_tab(self, path):
        """Open *path* in a new tab the way the window does."""
        text = path.read_text(encoding="utf-8")
        tab = self.make_tab()
        tab.editor.setPlainText(text)
        tab.current_file = str(path)
        tab.editor.document().setModified(False)
        return tab, tab.load_swap_file(text)

    def make_window(self):
        window = TextEditorApp()
        self.addCleanup(window.deleteLater)
        return window

    @staticmethod
    def close_window(window):
        event = QCloseEvent()
        window.closeEvent(event)
        return event.isAccepted()

    @staticmethod
    def tab_summary(window):
        summary = []
        for index in range(window.tab_widget.count()):
            tab = window.tab_widget.widget(index)
            summary.append((
                window.tab_widget.tabText(index),
                tab.current_file,
                tab.editor.toPlainText(),
            ))
        return summary


class SwapFileTests(SessionRecoveryTestCase):
    def test_swap_file_follows_unsaved_changes_and_is_removed_on_save(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, shown = self.load_tab(path)
        self.assertFalse(shown)
        self.assertFalse(tab.write_swap_file())

        type_text(tab, "two\n")
        self.assertTrue(tab.swap_timer.isActive())
        self.assertTrue(tab.write_backup())
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
        tab.apply_backup_settings()
        self.assertFalse(os.path.exists(swap))
        type_text(tab, "three\n")
        self.assertFalse(tab.swap_timer.isActive())
        self.assertFalse(tab.write_swap_file())
        self.assertFalse(os.path.exists(swap))

    def test_backups_follow_the_configured_sync_interval(self):
        tab = self.make_tab()
        type_text(tab, "draft")
        # Kate's default "Save swap files every: 15s".
        self.assertEqual(tab.swap_timer.interval(), 15000)
        self.assertTrue(tab.write_backup())

        self.settings.save_setting("swap_sync_interval_seconds", 42)
        type_text(tab, " more")
        self.assertEqual(tab.swap_timer.interval(), 42000)
        tab.swap_timer.stop()

        self.settings.save_setting("swap_sync_interval_seconds", 0)
        self.assertEqual(tab.backup_interval_ms(), 1000)
        self.settings.save_setting("swap_sync_interval_seconds", "bad")
        self.assertEqual(tab.backup_interval_ms(), 15000)

    def test_untitled_document_is_stashed_while_typing(self):
        tab = self.make_tab()
        stash = stash_file_path(self.settings, tab.stash_id)
        type_text(tab, "draft")
        self.assertTrue(tab.swap_timer.isActive())
        self.assertTrue(tab.write_backup())
        self.assertEqual(read_stash_file(stash)["text"], "draft")

        # Emptied documents have nothing to keep.
        tab.editor.clear()
        self.assertFalse(tab.write_backup())
        self.assertFalse(os.path.exists(stash))

        type_text(tab, "draft again")
        self.assertTrue(tab.write_backup())
        self.settings.save_setting(STASH_NEW_FILES_SETTING, False)
        tab.apply_backup_settings()
        self.assertFalse(os.path.exists(stash))
        self.assertFalse(tab.write_backup())

    def test_saving_an_untitled_document_removes_its_stash(self):
        tab = self.make_tab()
        stash = stash_file_path(self.settings, tab.stash_id)
        type_text(tab, "draft")
        self.assertTrue(tab.write_stash_file())
        tab.current_file = str(Path(self.temp_dir.name) / "draft.txt")
        self.assertTrue(tab.save_file())
        self.assertFalse(os.path.exists(stash))


class SessionTests(SessionRecoveryTestCase):
    def test_open_files_and_untitled_documents_survive_a_crash(self):
        first = self.write_note("first\n", "first.txt")
        second = self.write_note("second\n", "second.txt", Path(self.temp_dir.name) / "elsewhere")
        crashed = self.make_window()
        self.assertEqual(crashed.workspace_path, "")
        crashed.open_file(str(first))
        type_text(crashed.new_editor_tab(), "untitled draft")
        crashed.open_file(str(second))
        type_text(crashed.tab_widget.currentWidget(), "unsaved line\n")
        crashed.tab_widget.setCurrentIndex(1)
        for index in range(crashed.tab_widget.count()):
            crashed.tab_widget.widget(index).write_backup()
        # No closeEvent: the process dies here.

        window = self.make_window()
        self.assertEqual(self.tab_summary(window), [
            ("first.txt", str(first), "first\n"),
            ("untitled*", None, "untitled draft"),
            ("second.txt", str(second), "second\n"),
        ])
        self.assertEqual(window.tab_widget.currentIndex(), 1)
        self.assertTrue(window.tab_widget.widget(1).editor.document().isModified())
        recovering = window.tab_widget.widget(2)
        self.assertIsNotNone(recovering.swap_recovery)
        self.assertTrue(recovering.recover_swap_file())
        self.assertEqual(recovering.editor.toPlainText(), "second\nunsaved line\n")

    def test_session_follows_closed_and_moved_tabs(self):
        first = self.write_note("first\n", "first.txt")
        second = self.write_note("second\n", "second.txt")
        window = self.make_window()
        window.settings_manager.save_setting("session_restore_mode", "always")
        window.open_file(str(first))
        window.open_file(str(second))
        draft = window.new_editor_tab()
        type_text(draft, "gone")
        self.assertTrue(draft.write_backup())
        window.tab_widget.tabBar().moveTab(0, 1)
        self.assertEqual(
            [entry.get("file") for entry in read_session(window.settings_manager)["tabs"]],
            [str(second), str(first), None],
        )

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ):
            window.close_tab(window.tab_widget.indexOf(draft))
        window.close_tab(window.tab_widget.indexOf(window.tab_widget.widget(0)))
        self.assertEqual(stash_names(window.settings_manager), [])

        reopened = self.make_window()
        self.assertEqual(
            [tab[1] for tab in self.tab_summary(reopened)], [str(first)]
        )

    def test_closing_prompts_for_new_unsaved_files_and_discard_drops_them(self):
        window = self.make_window()
        window.settings_manager.save_setting("session_restore_mode", "always")
        tab = window.tab_widget.widget(0)
        type_text(tab, "draft notes")
        window.tab_widget.setTabText(0, "Ideas*")

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ) as ask:
            self.assertTrue(self.close_window(window))
            # A repeated close must not ask again or change the session.
            self.assertTrue(self.close_window(window))
        ask.assert_called_once()
        self.assertEqual(stash_names(window.settings_manager), [])

        restored = self.make_window()
        self.assertEqual(self.tab_summary(restored), [("Document 1", None, "")])

    def test_new_unsaved_files_prompt_when_restoring_is_disabled(self):
        window = self.make_window()
        window.settings_manager.save_setting(STASH_NEW_FILES_SETTING, False)
        type_text(window.tab_widget.widget(0), "draft notes")
        window.tab_widget.widget(0).write_backup()

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ) as ask:
            self.assertTrue(self.close_window(window))
        ask.assert_called_once()
        self.assertEqual(stash_names(window.settings_manager), [])

        restored = self.make_window()
        self.assertEqual(self.tab_summary(restored), [("Document 1", None, "")])

    def test_cancelled_close_keeps_everything_open_and_backed_up(self):
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
        self.assertEqual(len(stash_names(window.settings_manager)), 1)
        self.assertEqual(len(read_session(window.settings_manager)["tabs"]), 2)

    def test_discarded_file_changes_reopen_the_file_without_them(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        window = self.make_window()
        window.settings_manager.save_setting("session_restore_mode", "always")
        window.open_file(str(path))
        type_text(window.tab_widget.currentWidget(), "two\n")
        self.assertTrue(window.tab_widget.currentWidget().write_swap_file())

        with patch.object(
            window_module, "ask_themed_question",
            return_value=QMessageBox.StandardButton.Discard,
        ):
            self.assertTrue(self.close_window(window))
        self.assertFalse(os.path.exists(swap))

        reopened = self.make_window()
        self.assertEqual(self.tab_summary(reopened), [("note.txt", str(path), "one\n")])
        self.assertIsNone(reopened.tab_widget.widget(0).swap_recovery)

    def test_restore_on_unsaved_changes_starts_empty_without_them(self):
        note = self.write_note()
        window = self.make_window()
        window.settings_manager.save_setting("session_restore_mode", "unsaved_changes")
        window.open_file(str(note))
        self.assertTrue(self.close_window(window))

        reopened = self.make_window()
        self.assertEqual(self.tab_summary(reopened), [("Document 1", None, "")])

    def test_restore_on_unsaved_changes_reopens_whole_session_for_file_changes(self):
        first = self.write_note("first\n", "first.txt")
        second = self.write_note("second\n", "second.txt")
        crashed = self.make_window()
        crashed.settings_manager.save_setting("session_restore_mode", "unsaved_changes")
        crashed.open_file(str(first))
        crashed.open_file(str(second))
        type_text(crashed.tab_widget.currentWidget(), "unsaved\n")
        self.assertTrue(crashed.tab_widget.currentWidget().write_swap_file())
        crashed.tab_widget.setCurrentIndex(0)
        # No closeEvent: the process dies here.

        window = self.make_window()
        self.assertEqual(
            [tab[1] for tab in self.tab_summary(window)], [str(first), str(second)]
        )
        self.assertEqual(window.tab_widget.currentIndex(), 0)
        self.assertIsNotNone(window.tab_widget.widget(1).swap_recovery)

    def test_restore_on_unsaved_changes_counts_untitled_drafts(self):
        note = self.write_note()
        crashed = self.make_window()
        crashed.settings_manager.save_setting("session_restore_mode", "unsaved_changes")
        crashed.open_file(str(note))
        draft = crashed.new_editor_tab()
        type_text(draft, "draft")
        self.assertTrue(draft.write_backup())
        # No closeEvent: the process dies here.

        reopened = self.make_window()
        self.assertEqual(self.tab_summary(reopened), [
            ("note.txt", str(note), "one\n"),
            ("draft*", None, "draft"),
        ])

    def make_workspace(self, folder, *names):
        workspace = Path(self.temp_dir.name) / folder
        notes = [self.write_note(f"{name}\n", f"{name}.txt", workspace) for name in names]
        return workspace, notes

    def test_workspace_tabs_restore_even_when_the_session_does_not(self):
        workspace, (first, second) = self.make_workspace("workspace", "first", "second")
        outside = self.write_note("outside\n", "outside.txt")
        window = self.make_window()
        window.settings_manager.save_setting("session_restore_mode", "unsaved_changes")
        self.assertTrue(window.switch_workspace(str(workspace)))
        window.open_file(str(first))
        window.open_file(str(second))
        window.open_file(str(outside))
        self.assertTrue(self.close_window(window))

        # Nothing unsaved, so the session stays closed, but the workspace does not.
        reopened = self.make_window()
        self.assertEqual(reopened.workspace_path, str(workspace))
        self.assertEqual(
            [tab[1] for tab in self.tab_summary(reopened)], [str(first), str(second)]
        )

    def test_restored_session_keeps_its_order_and_current_tab_in_a_workspace(self):
        workspace, (first, second) = self.make_workspace("workspace", "first", "second")
        outside = self.write_note("outside\n", "outside.txt")
        crashed = self.make_window()
        crashed.settings_manager.save_setting("session_restore_mode", "always")
        self.assertTrue(crashed.switch_workspace(str(workspace)))
        crashed.open_file(str(second))
        crashed.open_file(str(outside))
        crashed.open_file(str(first))
        crashed.tab_widget.setCurrentIndex(1)
        # No closeEvent: the process dies here.

        window = self.make_window()
        self.assertEqual(
            [tab[1] for tab in self.tab_summary(window)],
            [str(second), str(outside), str(first)],
        )
        self.assertEqual(window.tab_widget.currentIndex(), 1)

    def test_reopening_a_workspace_restores_its_tabs(self):
        first_workspace, (first,) = self.make_workspace("first-workspace", "first")
        second_workspace, (second,) = self.make_workspace("second-workspace", "second")
        window = self.make_window()
        self.assertTrue(window.switch_workspace(str(first_workspace)))
        window.open_file(str(first))
        self.assertTrue(window.switch_workspace(str(second_workspace)))
        window.open_file(str(second))
        self.assertEqual([tab[1] for tab in self.tab_summary(window)], [str(second)])

        self.assertTrue(window.switch_workspace(str(first_workspace)))
        self.assertEqual([tab[1] for tab in self.tab_summary(window)], [str(first)])

        self.assertTrue(window.close_workspace())
        self.assertEqual([tab[1] for tab in self.tab_summary(window)], [None])
        self.assertTrue(window.switch_workspace(str(first_workspace)))
        self.assertEqual([tab[1] for tab in self.tab_summary(window)], [str(first)])

    def test_startup_workspace_opens_with_its_tabs_and_unsaved_documents(self):
        chosen, (planned,) = self.make_workspace("chosen", "planned")
        last, (recent,) = self.make_workspace("last", "recent")
        outside = self.write_note("outside\n", "outside.txt")
        crashed = self.make_window()
        self.assertTrue(crashed.switch_workspace(str(chosen)))
        crashed.open_file(str(planned))
        self.assertTrue(crashed.switch_workspace(str(last)))
        crashed.open_file(str(recent))
        crashed.open_file(str(outside))
        type_text(crashed.tab_widget.currentWidget(), "unsaved\n")
        self.assertTrue(crashed.tab_widget.currentWidget().write_swap_file())
        draft = crashed.new_editor_tab()
        type_text(draft, "draft")
        self.assertTrue(draft.write_backup())
        crashed.settings_manager.save_setting("session_restore_mode", "workspace")
        crashed.settings_manager.save_setting("startup_workspace", str(chosen))
        # No closeEvent: the process dies here.

        # The chosen workspace replaces the last one; only unsaved work comes along.
        window = self.make_window()
        self.assertEqual(window.workspace_path, str(chosen))
        self.assertEqual(
            [tab[1] for tab in self.tab_summary(window)],
            [str(outside), None, str(planned)],
        )
        self.assertIsNotNone(window.tab_widget.widget(0).swap_recovery)
        self.assertEqual(window.tab_widget.widget(1).editor.toPlainText(), "draft")

    def test_missing_startup_workspace_restores_the_previous_session(self):
        last, (recent,) = self.make_workspace("last", "recent")
        window = self.make_window()
        self.assertTrue(window.switch_workspace(str(last)))
        window.open_file(str(recent))
        window.settings_manager.save_setting("session_restore_mode", "workspace")
        window.settings_manager.save_setting(
            "startup_workspace", str(Path(self.temp_dir.name) / "gone")
        )
        self.assertTrue(self.close_window(window))

        reopened = self.make_window()
        self.assertEqual(reopened.workspace_path, str(last))
        self.assertEqual([tab[1] for tab in self.tab_summary(reopened)], [str(recent)])

    def test_instance_started_while_another_runs_opens_empty(self):
        workspace, (note,) = self.make_workspace("workspace", "note")
        other = self.write_note("other\n", "other.txt")
        running = self.make_window()
        running.settings_manager.save_setting("session_restore_mode", "always")
        self.assertTrue(running.switch_workspace(str(workspace)))
        running.open_file(str(note))
        draft = running.new_editor_tab()
        type_text(draft, "draft")
        self.assertTrue(draft.write_backup())
        session = read_session(self.settings)

        # The running instance's lock, as if held by another process.
        release_session(self.settings)
        owner = QLockFile(session_lock_path(self.settings))
        self.assertTrue(owner.tryLock(0))
        self.addCleanup(owner.unlock)

        second = self.make_window()
        self.assertEqual(second.workspace_path, "")
        self.assertEqual(self.tab_summary(second), [("Document 1", None, "")])
        self.assertTrue(second.open_file(str(other)))
        self.assertEqual(read_session(self.settings), session)

        # Once the owner exits, the remaining instance saves its own tabs.
        owner.unlock()
        second.save_session()
        self.assertEqual(read_session(self.settings)["tabs"], [{"file": str(other)}])

    def test_stash_files_missing_from_the_session_are_reopened(self):
        # Written by a Jottr that only stashed on quit, or before the session was saved.
        write_stash_file(stash_file_path(self.settings, "1700000000-0000"), "Old draft", "kept")

        window = self.make_window()
        # Restored untitled documents are named after their first line.
        self.assertEqual(self.tab_summary(window), [("kept*", None, "kept")])
        self.assertEqual(window.tab_widget.widget(0).stash_id, "1700000000-0000")

    def test_untitled_tabs_are_named_after_their_first_line(self):
        window = self.make_window()
        tab = window.tab_widget.widget(0)

        def title(of=tab):
            return window.tab_widget.tabText(window.tab_widget.indexOf(of))

        def replace_text(text):
            cursor = tab.editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(text)

        self.assertEqual(title(), "Document 1")
        type_text(tab, "\n   Shopping   list  \nmilk\n")
        self.assertEqual(title(), "Shopping*")
        # Save dialogs suggest the title as the file name.
        self.assertTrue(tab.suggested_save_path("txt").endswith("Shopping.txt"))

        replace_text("# Weekly plan\n")
        self.assertEqual(title(), "Weekly*")
        replace_text("#hashtag")
        self.assertEqual(title(), "#hashtag*")
        replace_text("Tea and cakes")
        self.assertEqual(title(), "Tea and*")
        replace_text("x" * 60)
        self.assertEqual(title(), "x" * 10 + "*")
        replace_text("  \n\n")
        self.assertEqual(title(), "Document 1*")

        # Files keep their name, also when opened into an empty untitled tab.
        note = self.write_note("first line\n")
        window.new_editor_tab()
        self.assertTrue(window.open_file(str(note)))
        opened = window.tab_widget.currentWidget()
        self.assertEqual(title(opened), "note.txt")
        type_text(opened, "more\n")
        self.assertEqual(title(opened), "note.txt*")

    def test_first_start_without_a_session_reopens_workspace_files(self):
        workspace = Path(self.temp_dir.name) / "workspace"
        note = self.write_note("in workspace\n", "note.txt", workspace)
        self.settings.save_setting("workspace_path", str(workspace))
        self.settings.save_setting("workspace_sessions", {
            str(workspace): {"open_files": ["note.txt"], "markdown_files": []},
        })

        window = self.make_window()
        self.assertEqual(
            self.tab_summary(window), [("note.txt", str(note), "in workspace\n")]
        )
        self.assertEqual(
            read_session(window.settings_manager)["tabs"], [{"file": str(note)}]
        )


class AutosaveTests(SessionRecoveryTestCase):
    """Settings > Editor autosave works on its own, next to the backups."""

    def enable_autosave(self, seconds=30):
        self.settings.save_setting("autosave_enabled", True)
        self.settings.save_setting("autosave_interval_seconds", seconds)

    def test_autosave_and_backup_timers_run_on_their_own_intervals(self):
        self.enable_autosave(3)
        self.settings.save_setting("swap_sync_interval_seconds", 1)
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, _shown = self.load_tab(path)
        type_text(tab, "two\n")
        self.assertEqual(tab.backup_timer.interval(), 3000)
        self.assertEqual(tab.swap_timer.interval(), 1000)

        # The swap file is written first, and autosave has not saved yet.
        self.assertTrue(wait_until(lambda: os.path.exists(swap), 2500))
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")

        # Autosave then saves the file, which makes the swap file unnecessary.
        self.assertTrue(wait_until(lambda: not tab.editor.document().isModified(), 4000))
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo\n")
        self.assertFalse(os.path.exists(swap))
        process_events_for(1500)
        self.assertFalse(os.path.exists(swap))
        self.assertTrue(tab.backup_timer.isActive())

    def test_backups_do_not_depend_on_autosave(self):
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, _shown = self.load_tab(path)
        type_text(tab, "two\n")
        self.assertFalse(tab.backup_timer.isActive())
        self.assertFalse(tab.changes_pending)
        self.assertTrue(tab.swap_timer.isActive())

        self.assertTrue(tab.write_backup())
        tab.force_save()
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")
        self.assertEqual(read_swap_file(swap)["text"], "one\ntwo\n")

    def test_autosave_does_not_depend_on_backups(self):
        self.enable_autosave()
        self.settings.save_setting(SWAP_FILE_SETTING, False)
        self.settings.save_setting(STASH_NEW_FILES_SETTING, False)
        path = self.write_note()
        tab, _shown = self.load_tab(path)
        type_text(tab, "two\n")
        self.assertFalse(tab.swap_timer.isActive())
        self.assertTrue(tab.changes_pending)

        tab.force_save()
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo\n")
        self.assertFalse(tab.editor.document().isModified())
        self.assertFalse(os.path.exists(swap_file_path(self.settings, path)))
        self.assertEqual(stash_names(self.settings), [])

    def test_autosave_waits_for_a_recovery_choice(self):
        self.enable_autosave()
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        write_swap_file(swap, path, text_checksum("one\n"), "one\ntwo\n")
        tab, shown = self.load_tab(path)
        self.assertTrue(shown)

        tab.force_save()
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")
        self.assertTrue(os.path.exists(swap))
        self.assertIsNotNone(tab.swap_recovery)

        self.assertTrue(tab.recover_swap_file())
        self.assertTrue(tab.changes_pending)
        tab.force_save()
        self.assertEqual(path.read_text(encoding="utf-8"), "one\ntwo\n")
        self.assertFalse(os.path.exists(swap))
        self.assertFalse(tab.editor.document().isModified())

    def test_failed_autosave_keeps_the_swap_file(self):
        self.enable_autosave()
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        tab, _shown = self.load_tab(path)
        type_text(tab, "two\n")
        self.assertTrue(tab.write_swap_file())

        with patch.object(editor_tab_module.os, "replace", side_effect=OSError("denied")):
            tab.force_save()
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")
        self.assertFalse(os.path.exists(str(path) + ".tmp"))
        self.assertTrue(tab.changes_pending)
        self.assertTrue(tab.editor.document().isModified())
        self.assertEqual(read_swap_file(swap)["text"], "one\ntwo\n")

    def test_autosave_leaves_untitled_documents_to_the_stash(self):
        self.enable_autosave()
        tab = self.make_tab()
        type_text(tab, "draft")
        self.assertFalse(tab.changes_pending)

        tab.force_save()
        self.assertIsNone(tab.current_file)
        self.assertTrue(tab.editor.document().isModified())
        self.assertTrue(tab.write_backup())
        self.assertEqual(
            read_stash_file(stash_file_path(self.settings, tab.stash_id))["text"], "draft"
        )

    def test_autosaved_file_reopens_after_a_crash_without_recovery(self):
        self.enable_autosave()
        path = self.write_note()
        swap = swap_file_path(self.settings, path)
        crashed = self.make_window()
        crashed.settings_manager.save_setting("session_restore_mode", "always")
        crashed.open_file(str(path))
        tab = crashed.tab_widget.currentWidget()
        type_text(tab, "two\n")
        self.assertTrue(tab.write_swap_file())

        # Applying either settings page leaves the other feature alone.
        crashed.settings_manager.save_setting("swap_sync_interval_seconds", 60)
        crashed.apply_settings_domain("sessions")
        self.assertTrue(tab.changes_pending)
        self.assertTrue(tab.backup_timer.isActive())
        crashed.settings_manager.save_setting("autosave_interval_seconds", 45)
        crashed.apply_settings_domain("autosave")
        self.assertEqual(tab.backup_timer.interval(), 45000)
        self.assertTrue(tab.swap_timer.isActive())
        self.assertEqual(tab.swap_timer.interval(), 60000)
        self.assertTrue(os.path.exists(swap))

        tab.force_save()
        self.assertFalse(os.path.exists(swap))
        # No closeEvent: the process dies here.

        window = self.make_window()
        self.assertEqual(self.tab_summary(window), [("note.txt", str(path), "one\ntwo\n")])
        self.assertIsNone(window.tab_widget.widget(0).swap_recovery)


if __name__ == "__main__":
    unittest.main()
