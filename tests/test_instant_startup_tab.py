"""Bare instant editor tab: upgrade, keep/drop, and deferred-UI safety."""
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

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QMenu

from jottr.editor.tab import EditorTab
from jottr.session_recovery import release_session
from jottr.settings_manager import SettingsManager
from jottr.snippet_manager import SnippetManager
from jottr.window import TextEditorApp


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


class InstantEditorTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.addCleanup(release_session, self.settings)
        self.snippets = SnippetManager(self.settings)

    def test_spelling_actions_safe_before_upgrade(self):
        tab = EditorTab(self.snippets, self.settings, instant=True)
        self.addCleanup(tab.deleteLater)
        self.assertTrue(tab._instant_pending)
        self.assertFalse(hasattr(tab, "highlighter"))

        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        self.assertFalse(tab._add_spelling_actions(menu, "mispelled"))

    def test_markdown_splitter_persists_sizes_after_upgrade(self):
        tab = EditorTab(self.snippets, self.settings, instant=True)
        self.addCleanup(tab.deleteLater)
        signal = tab.markdown_splitter.splitterMoved
        self.assertEqual(tab.markdown_splitter.receivers(signal), 0)

        self.assertTrue(tab.finish_instant_upgrade())
        self.addCleanup(tab.backup_timer.stop)
        self.assertGreater(tab.markdown_splitter.receivers(signal), 0)
        self.assertTrue(hasattr(tab, "backup_timer"))
        self.assertTrue(hasattr(tab, "highlighter"))


class InstantTabDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        # Isolated config + production deferred startup (bare tab first).
        self.env = patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": self.temp_dir.name,
                "JOTTR_DEFER_STARTUP": "1",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.window = TextEditorApp()

        def cleanup_window():
            settings = self.window.settings_manager
            for index in range(self.window.tab_widget.count()):
                tab = self.window.tab_widget.widget(index)
                editor = getattr(tab, "editor", None)
                if editor is not None:
                    editor.document().setModified(False)
            self.window.close()
            release_session(settings)
            self.window.deleteLater()

        self.addCleanup(cleanup_window)

    def _upgrade_then_add_extra_tab(self):
        """Leave two tabs with `_instant_tab` still tracked for drop checks."""
        self.assertEqual(self.window._startup_stage, "tab")
        instant = self.window._instant_tab
        self.assertIsNotNone(instant)
        self.window._upgrade_startup_editor(schedule_next=False)
        # new_editor_tab drains remaining startup while count is still 1, so
        # drop is a no-op; then the extra tab makes count >= 2.
        self.window.new_editor_tab()
        self.window._instant_tab = instant
        return instant

    def test_typed_instant_tab_kept_when_other_tabs_exist(self):
        instant = self.window._instant_tab
        type_text(instant, "keep me")
        self._upgrade_then_add_extra_tab()

        self.window._drop_redundant_instant_tab()
        self.assertIs(self.window._instant_tab, instant)
        self.assertGreaterEqual(self.window.tab_widget.indexOf(instant), 0)
        self.assertIn("keep me", instant.editor.toPlainText())

    def test_pristine_instant_tab_dropped_when_other_tabs_exist(self):
        instant = self._upgrade_then_add_extra_tab()
        self.assertFalse(instant.editor.toPlainText())

        self.window._drop_redundant_instant_tab()
        self.assertIsNone(self.window._instant_tab)
        self.assertEqual(self.window.tab_widget.indexOf(instant), -1)


if __name__ == "__main__":
    unittest.main()
