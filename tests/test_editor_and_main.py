import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "jottr"
sys.path.insert(0, str(SRC_DIR))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextDocument
from PyQt6.QtWidgets import QApplication, QTextEdit, QWidget

from editor_tab import EditorTab, SpellCheckHighlighter
import editor_tab as editor_tab_module
import main as main_module
from main import APP_NAME, TextEditorApp, WorkspaceFileSystemModel, WorkspaceTreeView
from settings_manager import SettingsManager
from snippet_manager import SnippetManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class _Signal:
    def connect(self, callback):
        self.callback = callback


class _FakeWebEngineSettings:
    def setAttribute(self, *_args):
        pass


class _FakeWebEngineView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loadFinished = _Signal()
        self.html = ""
        self.base_url = None

    def setPage(self, page):
        self._page = page

    def settings(self):
        return _FakeWebEngineSettings()

    def setHtml(self, html, base_url=None):
        self.html = html
        self.base_url = base_url

    def page(self):
        return self

    def runJavaScript(self, _script, callback=None):
        if callback:
            callback(None)


class EditorAndMainTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.snippets = SnippetManager(self.settings)

    def test_workspace_model_tooltip_is_full_path(self):
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir()
        note = workspace / "note.md"
        note.write_text("# Note", encoding="utf-8")

        model = WorkspaceFileSystemModel()
        self.addCleanup(model.deleteLater)
        model.setRootPath(str(workspace))
        app().processEvents()
        index = model.index(str(note))

        self.assertEqual(model.data(index, Qt.ItemDataRole.ToolTipRole), str(note))

<<<<<<< HEAD
    def test_workspace_tree_uses_visible_hierarchy_settings(self):
        tree = WorkspaceTreeView()
        self.addCleanup(tree.deleteLater)

        tree.setIndentation(18)
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(True)
        tree.setAllColumnsShowFocus(True)

        self.assertEqual(tree.indentation(), 18)
        self.assertTrue(tree.rootIsDecorated())
        self.assertTrue(tree.alternatingRowColors())
        self.assertTrue(tree.allColumnsShowFocus())

=======
>>>>>>> parent of 429d996 (Revert "Implementing the workspaces.")
    def make_editor(self):
        web_view_patch = patch.object(editor_tab_module, "QWebEngineView", _FakeWebEngineView)
        preview_page_patch = patch.object(editor_tab_module, "MarkdownPreviewPage", lambda parent=None: object())
        web_view_patch.start()
        preview_page_patch.start()
        self.addCleanup(web_view_patch.stop)
        self.addCleanup(preview_page_patch.stop)
        editor = EditorTab(self.snippets, self.settings)
        self.addCleanup(editor.deleteLater)
        self.addCleanup(editor.backup_timer.stop)
        self.addCleanup(editor.preview_scroll_timer.stop)
        self.addCleanup(editor.markdown_render_timer.stop)
        return editor

    def test_markdown_helpers_cover_tables_tasks_math_and_shortcodes(self):
        editor = self.make_editor()

        self.assertEqual(EditorTab.split_table_row(r"| a \| b | c |"), ["a | b", "c"])
        self.assertEqual(EditorTab.apply_emoji_shortcodes("Ship it :rocket:"), "Ship it 🚀")
        html = editor.render_markdown_html(
            "# Title\n\n- [x] done\n\n| A | B |\n| --- | ---: |\n| one | two |\n\n$$x^2$$"
        )

        self.assertIn("Title", html)
        self.assertIn("task-list-item-checkbox", html)
        self.assertIn("<table", html)
        self.assertIn("math-block", html)

    def test_markdown_preview_anchors_fenced_code_lines(self):
        editor = self.make_editor()

        html = editor.render_markdown_html("```css\nbody { color: red; }\na { color: blue; }\n```")

        self.assertIn("source-code-line", html)
        self.assertIn('data-source-line="2"', html)
        self.assertIn('data-source-line="3"', html)

    def test_markdown_preview_uses_editor_font(self):
        editor = self.make_editor()
        font = QFont("Liberation Serif", 16)
        editor.update_font(font)

        html = editor.render_markdown_html("# Title")

        self.assertIn('font-family: "Liberation Serif"', html)
        self.assertIn("font-size: 16pt", html)

    def test_editor_file_and_line_number_state(self):
        editor = self.make_editor()

        self.assertTrue(editor.is_markdown_file("notes.md"))
        self.assertTrue(editor.is_markdown_file("notes.markdown"))
        self.assertFalse(editor.is_markdown_file("notes.txt"))

        editor.set_line_numbers_visible(False)
        self.assertFalse(editor.editor.line_numbers_visible)
        editor.set_line_numbers_visible(True)
        self.assertTrue(editor.editor.line_numbers_visible)

    def test_editor_scroll_ratio_tracks_scrollbar_progress(self):
        editor = self.make_editor()
        scroll_bar = editor.editor.verticalScrollBar()
        scroll_bar.setRange(0, 100)
        scroll_bar.setValue(45)
        self.assertAlmostEqual(
            editor.get_editor_scroll_ratio(),
            0.45,
            places=2
        )

    def test_markdown_highlighter_uses_theme_syntax_colors(self):
        self.settings.save_theme("Dracula")
        document = QTextDocument()
        highlighter = SpellCheckHighlighter(document, self.settings)
        highlighter.spell_check_enabled = False

        document.setPlainText("# Title\n\n`code`\n\n[link](https://example.test)")
        highlighter.rehighlight()

        heading_colors = {
            item.format.foreground().color().name()
            for item in document.findBlockByNumber(0).layout().formats()
        }
        code_colors = {
            item.format.foreground().color().name()
            for item in document.findBlockByNumber(2).layout().formats()
        }
        link_colors = {
            item.format.foreground().color().name()
            for item in document.findBlockByNumber(4).layout().formats()
        }

        self.assertIn("#ff79c6", heading_colors)
        self.assertIn("#bd93f9", code_colors)
        self.assertIn("#50fa7b", link_colors)
        self.assertIn("#f1fa8c", link_colors)

    def test_editor_snippet_insert_find_replace_and_save(self):
        editor = self.make_editor()
        self.snippets.add_snippet("sig", "Regards")
        editor.update_snippet_list()

        self.assertEqual(editor.snippet_list.count(), 1)
        editor.insert_snippet(editor.snippet_list.item(0))
        self.assertEqual(editor.editor.toPlainText(), "Regards")

        editor.editor.setPlainText("alpha beta alpha")
        editor.find_input.setText("alpha")
        editor.replace_input.setText("omega")
        with patch("editor_tab.QMessageBox.information"):
            editor.replace_all()
        self.assertEqual(editor.editor.toPlainText(), "omega beta omega")

        target = Path(self.temp_dir.name) / "saved.txt"
        editor.current_file = str(target)
        editor.editor.setPlainText("saved content")
        self.assertTrue(editor.save_file())
        self.assertEqual(target.read_text(encoding="utf-8"), "saved content")

    def test_editor_autosaves_existing_file_when_enabled(self):
        self.settings.save_setting("autosave_enabled", True)
        self.settings.save_setting("autosave_interval_seconds", 1)
        editor = self.make_editor()
        target = Path(self.temp_dir.name) / "autosave.md"
        target.write_text("old", encoding="utf-8")
        editor.current_file = str(target)

        editor.editor.setPlainText("new content")
        self.assertTrue(editor.changes_pending)
        self.assertTrue(editor.backup_timer.isActive())

        editor.force_save()

        self.assertEqual(target.read_text(encoding="utf-8"), "new content")
        self.assertFalse(editor.changes_pending)
        self.assertFalse(editor.editor.document().isModified())

    def test_editor_does_not_autosave_when_disabled(self):
        self.settings.save_setting("autosave_enabled", False)
        editor = self.make_editor()
        target = Path(self.temp_dir.name) / "manual.md"
        target.write_text("old", encoding="utf-8")
        editor.current_file = str(target)

        editor.editor.setPlainText("new content")
        editor.force_save()

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertFalse(editor.backup_timer.isActive())

    def test_editor_pane_state_is_saved(self):
        editor = self.make_editor()
        editor.show()
        app().processEvents()

        editor.toggle_pane("snippets")
        states = self.settings.get_setting("pane_states")

        self.assertTrue(states["snippets_visible"])
        self.assertIn("sizes", states)

    def test_main_window_smoke_actions(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.settings_manager = settings_manager
                self.editor = QTextEdit(self)
                self.editor.line_numbers_visible = True
                self.current_font = settings_manager.get_font()
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def update_font(self, font):
                self.current_font = QFont(font)

            def toggle_markdown_preview(self):
                self.markdown_preview_visible = not self.markdown_preview_visible

            def set_line_numbers_visible(self, visible):
                self.editor.line_numbers_visible = visible

            def save_file(self, force_dialog=False):
                return True

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.windowTitle(), APP_NAME)
            self.assertGreaterEqual(window.tab_widget.count(), 1)
            first_tab = window.tab_widget.currentWidget()
            original_size = first_tab.current_font.pointSize()

            window.zoom_in()
            self.assertEqual(first_tab.current_font.pointSize(), original_size + 1)
            window.zoom_out()
            self.assertEqual(first_tab.current_font.pointSize(), original_size)
            window.toggle_markdown_preview()
            self.assertTrue(first_tab.markdown_preview_visible)
            window.apply_editor_line_numbers(False)
            self.assertFalse(first_tab.editor.line_numbers_visible)
            toolbar_tooltips = {
                action.text(): action.toolTip()
                for action in window.toolbar.actions()
                if not action.isSeparator() and action.text()
            }
            self.assertEqual(toolbar_tooltips["Font"], "Choose Editor Font")
            self.assertEqual(toolbar_tooltips["Theme"], "Choose Editor Theme")
            self.assertEqual(toolbar_tooltips["Menu"], "More Actions")
            self.assertTrue(all(toolbar_tooltips.values()))

    def test_main_window_opens_file_in_new_tab(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith((".md", ".markdown"))

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        target = Path(self.temp_dir.name) / "story.md"
        target.write_text("# Story", encoding="utf-8")
        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            window.open_file(str(target))
            current = window.tab_widget.currentWidget()

            self.assertEqual(current.current_file, str(target))
            self.assertEqual(current.editor.toPlainText(), "# Story")
            self.assertTrue(current.markdown_preview_visible)

    def test_main_window_reuses_blank_tab_and_focuses_existing_file(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith(".md")

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        first = Path(self.temp_dir.name) / "first.md"
        second = Path(self.temp_dir.name) / "second.md"
        first.write_text("# First", encoding="utf-8")
        second.write_text("# Second", encoding="utf-8")

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.tab_widget.count(), 1)
            window.open_file(str(first))
            self.assertEqual(window.tab_widget.count(), 1)
            self.assertEqual(window.tab_widget.currentWidget().current_file, str(first))

            window.open_file(str(second))
            self.assertEqual(window.tab_widget.count(), 2)
            window.open_file(str(first))
            self.assertEqual(window.tab_widget.count(), 2)
            self.assertEqual(window.tab_widget.currentWidget().current_file, str(first))

    def test_workspace_path_and_open_files_are_persisted(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith(".md")

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir()
        note = workspace / "note.md"
        note.write_text("# Note", encoding="utf-8")
        outside = Path(self.temp_dir.name) / "outside.md"
        outside.write_text("# Outside", encoding="utf-8")
        text_file = workspace / "notes.txt"
        text_file.write_text("plain", encoding="utf-8")

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertTrue(window.set_workspace_path(str(workspace)))
            window.open_file(str(note))
            window.open_file(str(outside))
            window.save_workspace_open_files()

            reloaded = SettingsManager()
            self.assertEqual(reloaded.get_setting("workspace_path"), str(workspace))
            self.assertEqual(reloaded.get_setting("workspace_open_files"), [str(note)])
            self.assertEqual(reloaded.get_setting("workspace_markdown_files"), [str(note)])

    def test_workspace_restore_reopens_workspace_files(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith(".md")

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir()
        note = workspace / "note.md"
        note.write_text("# Note", encoding="utf-8")
        self.settings.save_setting("workspace_path", str(workspace))
        self.settings.save_setting("workspace_open_files", [str(note)])

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            open_files = [
                window.tab_widget.widget(index).current_file
                for index in range(window.tab_widget.count())
                if getattr(window.tab_widget.widget(index), "current_file", None)
            ]
            self.assertEqual(open_files, [str(note)])
            self.assertFalse(window.workspace_widget.isHidden())

    def test_switch_workspace_restores_recent_workspace_session(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith(".md")

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

            def save_file(self):
                self.editor.document().setModified(False)
                return True

        first_workspace = Path(self.temp_dir.name) / "first"
        second_workspace = Path(self.temp_dir.name) / "second"
        first_workspace.mkdir()
        second_workspace.mkdir()
        first_note = first_workspace / "first.md"
        second_note = second_workspace / "second.md"
        first_note.write_text("# First", encoding="utf-8")
        second_note.write_text("# Second", encoding="utf-8")

        self.settings.save_setting("workspace_sessions", {
            str(second_workspace): {
                "open_files": ["second.md"],
                "markdown_files": ["second.md"],
            }
        })

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertTrue(window.set_workspace_path(str(first_workspace)))
            self.assertTrue(window.open_file(str(first_note)))
            self.assertTrue(window.switch_workspace(str(second_workspace)))

            open_files = [
                window.tab_widget.widget(index).current_file
                for index in range(window.tab_widget.count())
                if getattr(window.tab_widget.widget(index), "current_file", None)
            ]
            self.assertEqual(open_files, [str(second_note)])
            self.assertEqual(window.workspace_path, str(second_workspace))

            reloaded = SettingsManager()
            sessions = reloaded.get_setting("workspace_sessions")
            self.assertEqual(sessions[str(first_workspace)]["open_files"], ["first.md"])
            self.assertIn(str(second_workspace), reloaded.get_setting("recent_workspaces"))

    def test_workspace_file_creation_opens_new_file(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith(".md")

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir()

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)
            window.set_workspace_path(str(workspace))

            with patch("main.QInputDialog.getText", return_value=("draft.txt", True)):
                window.create_workspace_file()

            target = workspace / "draft.txt"
            self.assertTrue(target.is_file())
            self.assertEqual(window.tab_widget.currentWidget().current_file, str(target))


if __name__ == "__main__":
    unittest.main()
