import os
import sys
import tempfile
import time
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
from PyQt6.QtGui import QFont, QTextCursor, QTextDocument
from PyQt6.QtWidgets import QApplication, QDialog, QTextEdit, QWidget

from editor_tab import EditorTab, SpellCheckHighlighter
import editor_tab as editor_tab_module
import main as main_module
import translation_manager
from main import APP_NAME, FontSelectionDialog, TextEditorApp, WorkspaceFileSystemModel, WorkspaceTreeView
from settings_manager import SettingsManager
from snippet_manager import SnippetManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class _Signal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback

    def emit(self, *args):
        if self.callback:
            self.callback(*args)


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

    def load(self, url):
        self.url = url

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
        editor.update_font(QFont("Liberation Serif", 16))

        html = editor.render_markdown_html("# Title")

        self.assertIn('font-family: "Liberation Serif"', html)
        self.assertIn("font-size: 16pt", html)

    def test_editor_exports_pdf_with_preview_styles(self):
        editor = self.make_editor()
        editor.current_file = str(Path(self.temp_dir.name) / "note.md")
        editor.editor.setPlainText("# Title\n\nBody text")
        exported_pages = []

        class FakePdfPage:
            def __init__(self, parent=None):
                self.parent = parent
                self.loadFinished = _Signal()
                self.pdfPrintingFinished = _Signal()
                self.html = ""
                self.base_url = None
                self.printed_path = None
                self.page_layout = None
                exported_pages.append(self)

            def load(self, url):
                self.url = url
                self.html = Path(url.toLocalFile()).read_text(encoding="utf-8")
                self.loadFinished.emit(True)

            def runJavaScript(self, _script, callback=None):
                if callback:
                    callback(True)

            def printToPdf(self, path, page_layout=None):
                self.printed_path = path
                self.page_layout = page_layout
                self.pdfPrintingFinished.emit(path, True)

        output_path = str(Path(self.temp_dir.name) / "exported")
        with patch.object(editor_tab_module, "QWebEnginePage", FakePdfPage):
            with patch.object(editor_tab_module.QMessageBox, "information") as info:
                self.assertTrue(editor.export_pdf(output_path))

        self.assertEqual(len(exported_pages), 1)
        self.assertTrue(exported_pages[0].printed_path.endswith(".pdf"))
        self.assertIn("font-family", exported_pages[0].html)
        self.assertIn("<h1", exported_pages[0].html)
        self.assertIn("@page", exported_pages[0].html)
        self.assertIn("padding-inline-start: 2.2em", exported_pages[0].html)
        self.assertEqual(exported_pages[0].page_layout.margins().top(), 14.0)
        info.assert_called_once()

    def test_markdown_preview_can_use_latest_mermaid_runtime(self):
        self.settings.save_setting("mermaid_runtime", "latest")
        editor = self.make_editor()

        html = editor.render_markdown_html("```mermaid\ngraph TD\nA-->B\n```")

        self.assertIn(EditorTab.MERMAID_LATEST_CDN_URL, html)
        self.assertIn("if (!window.mermaid)", html)
        self.assertIn('<div class="mermaid">graph TD', html)
        self.assertIn("mermaid.run", html)
        self.assertIn("startup:", html)
        self.assertIn("typeset: false", html)

    def test_markdown_preview_uses_bundled_mermaid_by_default(self):
        editor = self.make_editor()

        html = editor.render_markdown_html("```mermaid\ngraph TD\nA-->B\n```")

        self.assertNotIn(EditorTab.MERMAID_LATEST_CDN_URL, html)
        self.assertIn('<div class="mermaid">graph TD', html)

    def test_editor_context_menu_selects_word_with_qt6_enum(self):
        editor = self.make_editor()
        editor.editor.setPlainText("hello world")
        editor.editor.moveCursor(QTextCursor.MoveOperation.Start)

        with patch.object(editor_tab_module.QTimer, "singleShot") as single_shot:
            editor.show_context_menu(editor.editor.cursorRect().center())

        self.assertEqual(editor.editor.textCursor().selectedText(), "hello")
        single_shot.assert_called_once()

    def test_editor_font_updates_visible_editor_style_and_document(self):
        editor = self.make_editor()
        font = QFont("Liberation Serif", 16)

        editor.update_font(font)

        self.assertEqual(editor.editor.font().family(), "Liberation Serif")
        self.assertEqual(editor.editor.font().pointSize(), 16)
        self.assertEqual(editor.editor.document().defaultFont().family(), "Liberation Serif")
        self.assertEqual(editor.editor.document().defaultFont().pointSize(), 16)
        self.assertIn("QTextEdit#writingEditor", editor.editor.styleSheet())
        self.assertIn('font-family: "Liberation Serif"', editor.editor.styleSheet())
        self.assertIn("font-size: 16pt", editor.editor.styleSheet())

    def test_editor_and_markdown_preview_use_auto_text_direction_for_rtl_content(self):
        self.settings.save_setting("language", "fa_IR")
        editor = self.make_editor()

        editor.editor.setPlainText("یک متن فارسی")
        html = editor.render_markdown_html("# عنوان\n\nیک متن فارسی")

        self.assertEqual(editor.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        self.assertEqual(editor.editor.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        self.assertEqual(editor.markdown_preview.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        self.assertEqual(
            editor.editor.document().defaultTextOption().textDirection(),
            Qt.LayoutDirection.LayoutDirectionAuto
        )
        self.assertIn('<html dir="auto">', html)
        self.assertIn('<body dir="auto">', html)
        self.assertIn('dir="auto" data-source-line="1"', html)
        self.assertIn("text-align: start;", html)

    def test_rtl_editor_places_line_numbers_on_right(self):
        self.settings.save_setting("language", "fa_IR")
        editor = self.make_editor()
        code_editor = editor.editor

        code_editor.resize(420, 280)
        app().processEvents()

        self.assertTrue(code_editor.line_numbers_visible)
        self.assertTrue(code_editor.line_number_area_on_right())
        self.assertEqual(
            code_editor.line_number_alignment(),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self.assertEqual(
            code_editor.line_number_area.geometry().left(),
            code_editor.viewport().geometry().right() + 1
        )

        self.settings.save_setting("language", "en_US")
        editor.apply_language_direction()
        code_editor.resize(420, 280)
        app().processEvents()

        self.assertFalse(code_editor.line_number_area_on_right())
        self.assertEqual(
            code_editor.line_number_area.geometry().right(),
            code_editor.viewport().geometry().left() - 1
        )

    def test_line_numbers_use_language_digit_shape(self):
        self.settings.save_setting("language", "en_US")
        editor = self.make_editor()

        self.assertEqual(editor.editor.format_line_number(123), "123")

        self.settings.save_setting("language", "de_DE")
        self.assertEqual(editor.editor.format_line_number(123), "123")

        self.settings.save_setting("language", "fa_IR")
        self.assertEqual(editor.editor.format_line_number(123), "۱۲۳")

        self.settings.save_setting("language", "ar_SA")
        self.assertEqual(editor.editor.format_line_number(123), "١٢٣")

    def test_line_number_background_matches_editor_theme(self):
        self.settings.save_theme("Dracula")
        editor = self.make_editor()

        self.assertEqual(
            editor.editor.line_number_background_color().name(),
            "#282a36"
        )

    def test_editor_and_markdown_preview_use_auto_text_direction_for_ltr_content(self):
        self.settings.save_setting("language", "en_US")
        editor = self.make_editor()

        editor.editor.setPlainText("Plain English text")
        html = editor.render_markdown_html("# Title\n\nPlain English text")

        self.assertEqual(editor.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertEqual(editor.editor.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertEqual(editor.markdown_preview.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertEqual(
            editor.editor.document().defaultTextOption().textDirection(),
            Qt.LayoutDirection.LayoutDirectionAuto
        )
        self.assertIn('<html dir="auto">', html)
        self.assertIn('<body dir="auto">', html)
        self.assertIn('dir="auto" data-source-line="1"', html)

    def test_editor_and_preview_direction_does_not_follow_ui_language(self):
        self.settings.save_setting("language", "en_US")
        editor = self.make_editor()
        rtl_html = editor.render_markdown_html("# عنوان\n\nیک متن فارسی")

        self.assertEqual(editor.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertEqual(
            editor.editor.document().defaultTextOption().textDirection(),
            Qt.LayoutDirection.LayoutDirectionAuto
        )
        self.assertIn('<html dir="auto">', rtl_html)
        self.assertNotIn("direction: ltr;", rtl_html)
        self.assertNotIn("text-align: left;", rtl_html)

        self.settings.save_setting("language", "fa_IR")
        editor.apply_language_direction()
        ltr_html = editor.render_markdown_html("# Title\n\nPlain English text")

        self.assertEqual(editor.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        self.assertEqual(
            editor.editor.document().defaultTextOption().textDirection(),
            Qt.LayoutDirection.LayoutDirectionAuto
        )
        self.assertIn('<html dir="auto">', ltr_html)
        self.assertNotIn("direction: rtl;", ltr_html)
        self.assertNotIn("text-align: right;", ltr_html)

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

    def test_markdown_scroll_sync_waits_for_pending_preview_render(self):
        editor = self.make_editor()
        editor.markdown_preview_visible = True
        editor.markdown_typing_active_until = 0
        editor.markdown_render_timer.start()

        with patch.object(editor_tab_module.QTimer, "singleShot") as single_shot:
            editor.schedule_markdown_scroll_sync()

        self.assertTrue(editor.preview_sync_after_load)
        single_shot.assert_not_called()

    def test_markdown_scroll_sync_waits_while_typing_is_active(self):
        editor = self.make_editor()
        editor.markdown_preview_visible = True
        editor.markdown_typing_active_until = time.time() + 1.0

        with patch.object(editor_tab_module.QTimer, "singleShot") as single_shot:
            editor.schedule_markdown_scroll_sync()

        self.assertFalse(editor.preview_sync_after_load)
        single_shot.assert_not_called()

    def test_markdown_preview_restores_scroll_before_reveal(self):
        editor = self.make_editor()

        html = editor.render_markdown_html("# Title", initial_scroll_ratio=0.4)

        self.assertIn("jottr-restoring-preview-scroll", html)
        self.assertIn("window.__jottrInitialPreviewScrollRatio = 0.4", html)
        self.assertIn("visibility: hidden", html)

    def test_markdown_preview_load_finishes_before_deferred_scroll_sync(self):
        editor = self.make_editor()
        editor.markdown_preview_visible = True
        editor.markdown_preview_loading = True
        editor.preview_sync_after_load = True

        with patch.object(editor_tab_module.QTimer, "singleShot") as single_shot:
            editor.render_markdown_preview_scripts()

        self.assertFalse(editor.markdown_preview_loading)
        self.assertFalse(editor.preview_sync_after_load)
        single_shot.assert_called_once()

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

    def test_editor_save_dialog_uses_translation_without_shadowing(self):
        editor = self.make_editor()
        target = Path(self.temp_dir.name) / "save-dialog.md"
        editor.editor.setPlainText("dialog save")

        with patch.object(editor_tab_module.QFileDialog, "getSaveFileName", return_value=(str(target), "")):
            self.assertTrue(editor.save_file(force_dialog=True))

        self.assertEqual(editor.current_file, str(target))
        self.assertEqual(target.read_text(encoding="utf-8"), "dialog save")

    def test_pdf_export_dialog_uses_app_translations(self):
        self.settings.save_setting("language", "fa_IR")
        translation_manager.set_language("fa_IR")
        self.addCleanup(lambda: translation_manager.set_language("en_US"))
        editor = self.make_editor()
        target = str(Path(self.temp_dir.name) / "translated-export.pdf")
        dialogs = []

        class FakeFileDialog:
            class AcceptMode:
                AcceptSave = object()

            class FileMode:
                AnyFile = object()

            class Option:
                DontUseNativeDialog = object()
                DontConfirmOverwrite = object()

            class DialogLabel:
                LookIn = "look_in"
                FileName = "file_name"
                FileType = "file_type"
                Accept = "accept"
                Reject = "reject"

            def __init__(self, parent, title, directory):
                self.parent = parent
                self.title = title
                self.directory = directory
                self.labels = {}
                self.name_filters = []
                self.selected_name_filter = ""
                self.layout_direction = None
                self.options = []
                dialogs.append(self)

            def setAcceptMode(self, value):
                self.accept_mode = value

            def setFileMode(self, value):
                self.file_mode = value

            def setOption(self, option, enabled):
                self.options.append((option, enabled))

            def setDefaultSuffix(self, suffix):
                self.default_suffix = suffix

            def setNameFilters(self, filters):
                self.name_filters = filters

            def selectNameFilter(self, name_filter):
                self.selected_name_filter = name_filter

            def setLabelText(self, label, text):
                self.labels[label] = text

            def setLayoutDirection(self, direction):
                self.layout_direction = direction

            def exec(self):
                return QDialog.DialogCode.Accepted

            def selectedFiles(self):
                return [target]

        with patch.object(editor_tab_module, "QFileDialog", FakeFileDialog):
            self.assertEqual(editor.prompt_pdf_export_path(), target)

        dialog = dialogs[0]
        self.assertEqual(dialog.title, "برون‌بری به PDF")
        self.assertEqual(dialog.name_filters, ["فایل‌های PDF (*.pdf)", "همهٔ فایل‌ها (*.*)"])
        self.assertIn((FakeFileDialog.Option.DontConfirmOverwrite, True), dialog.options)
        self.assertEqual(dialog.labels[FakeFileDialog.DialogLabel.LookIn], "نگاه در:")
        self.assertEqual(dialog.labels[FakeFileDialog.DialogLabel.FileName], "نام فایل:")
        self.assertEqual(dialog.labels[FakeFileDialog.DialogLabel.FileType], "نوع فایل:")
        self.assertEqual(dialog.labels[FakeFileDialog.DialogLabel.Accept], "ذخیره")
        self.assertEqual(dialog.labels[FakeFileDialog.DialogLabel.Reject], "لغو")
        self.assertEqual(dialog.layout_direction, Qt.LayoutDirection.RightToLeft)

    def test_pdf_export_replace_confirmation_uses_app_translations(self):
        self.settings.save_setting("language", "fa_IR")
        translation_manager.set_language("fa_IR")
        self.addCleanup(lambda: translation_manager.set_language("en_US"))
        editor = self.make_editor()
        target = Path(self.temp_dir.name) / "existing.pdf"
        target.write_text("old", encoding="utf-8")
        dialogs = []

        class FakeMessageBox:
            class Icon:
                Warning = object()

            class ButtonRole:
                AcceptRole = object()
                RejectRole = object()

            def __init__(self, parent):
                self.parent = parent
                self.buttons = []
                dialogs.append(self)

            def setIcon(self, icon):
                self.icon = icon

            def setWindowTitle(self, title):
                self.title = title

            def setText(self, text):
                self.text = text

            def addButton(self, text, role):
                button = {"text": text, "role": role}
                self.buttons.append(button)
                return button

            def setDefaultButton(self, button):
                self.default_button = button

            def exec(self):
                return 0

            def clickedButton(self):
                return self.default_button

        with patch.object(editor_tab_module, "QMessageBox", FakeMessageBox):
            self.assertTrue(editor.confirm_pdf_export_replace(str(target)))

        dialog = dialogs[0]
        self.assertEqual(dialog.title, "تأیید ذخیره به‌عنوان")
        self.assertIn("existing.pdf", dialog.text)
        self.assertEqual(dialog.buttons[0]["text"], "جایگزینی")
        self.assertEqual(dialog.buttons[1]["text"], "لغو")

    def test_editor_open_dialog_uses_translation_without_shadowing(self):
        editor = self.make_editor()
        target = Path(self.temp_dir.name) / "open-dialog.txt"
        target.write_text("# Dialog Open", encoding="utf-8")

        with patch.object(editor_tab_module.QFileDialog, "getOpenFileName", return_value=(str(target), "")):
            editor.open_file()

        self.assertEqual(editor.current_file, str(target))
        self.assertEqual(editor.editor.toPlainText(), "# Dialog Open")

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

    def test_editor_disables_animated_visibility_when_requested(self):
        self.settings.save_setting("enable_animations", False)
        editor = self.make_editor()
        editor.show()
        app().processEvents()

        animation = editor.animate_widget_visibility(editor.snippet_widget, True)

        self.assertIsNone(animation)
        self.assertTrue(editor.snippet_widget.isVisible())
        self.assertIsNone(editor.snippet_widget.graphicsEffect())

    def test_editor_animated_visibility_slides_and_fades_panes(self):
        editor = self.make_editor()
        editor.animations_enabled = lambda: True
        editor.show()
        app().processEvents()

        animation = editor.animate_widget_visibility(editor.snippet_widget, True)

        self.assertIsNotNone(animation)
        self.assertEqual(animation.animationCount(), 2)
        self.assertTrue(editor.snippet_widget.isVisible())
        self.assertEqual(editor.snippet_widget.maximumWidth(), 0)
        self.assertIsNotNone(editor.snippet_widget.graphicsEffect())
        animation.stop()

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
                self.pdf_exported = False

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

            def export_pdf(self):
                self.pdf_exported = True

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
            window.export_pdf()
            self.assertTrue(first_tab.pdf_exported)
            toolbar_tooltips = {
                action.text(): action.toolTip()
                for action in window.toolbar.actions()
                if not action.isSeparator() and action.text()
            }
            self.assertEqual(toolbar_tooltips["Editor Font"], "Choose Editor Font")
            self.assertNotIn("Preview Font", toolbar_tooltips)
            self.assertNotIn("Theme", toolbar_tooltips)
            self.assertEqual(toolbar_tooltips["Menu"], "More Actions")
            self.assertTrue(all(toolbar_tooltips.values()))
            dropdown_tooltips = {
                action.text(): action.toolTip()
                for action in window.menu_dropdown.actions()
                if not action.isSeparator() and action.text()
            }
            self.assertEqual(dropdown_tooltips["Export PDF"], "Export current file as PDF")
            self.assertNotEqual(window.icons["snippets"], window.icons["menu"])

    def test_main_window_left_aligns_document_tabs(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertFalse(window.tab_widget.tabBar().expanding())
            stylesheet = QApplication.instance().styleSheet()
            self.assertIn("QTabWidget#documentTabs::tab-bar", stylesheet)
            self.assertIn("alignment: left", stylesheet)

    def test_main_window_applies_separate_ui_and_editor_fonts(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_font = settings_manager.get_font("editor")
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

            def update_font(self, font):
                self.current_font = QFont(font)
                self.editor.setFont(self.current_font)

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)
            self.addCleanup(lambda: QApplication.instance().setStyleSheet(""))

            first_tab = window.tab_widget.widget(0)
            second_tab = window.new_editor_tab()
            ui_font = QFont("Liberation Sans", 13)
            editor_font = QFont("Liberation Mono", 16)

            window.apply_app_style(ui_font)
            window.apply_editor_font_to_tabs(editor_font)

            self.assertEqual(QApplication.instance().font().family(), "Liberation Sans")
            self.assertEqual(QApplication.instance().font().pointSize(), 13)
            self.assertIn('font-family: "Liberation Sans"', QApplication.instance().styleSheet())
            self.assertIn("QToolTip", QApplication.instance().styleSheet())
            self.assertEqual(first_tab.current_font.family(), "Liberation Mono")
            self.assertEqual(first_tab.current_font.pointSize(), 16)
            self.assertEqual(second_tab.current_font.family(), "Liberation Mono")
            self.assertEqual(second_tab.current_font.pointSize(), 16)

    def test_font_dialog_uses_translated_text(self):
        translations_dir = Path(self.temp_dir.name) / "translations"
        translations_dir.mkdir()
        (translations_dir / "zz_ZZ.po").write_text(
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: zz_ZZ\\n"\n'
            '\n'
            'msgid "Choose Editor Font"\n'
            'msgstr "Translated Font Picker"\n'
            '\n'
            'msgid "Font:"\n'
            'msgstr "Translated Font:"\n'
            '\n'
            'msgid "Size:"\n'
            'msgstr "Translated Size:"\n'
            '\n'
            'msgid "Style:"\n'
            'msgstr "Translated Style:"\n'
            '\n'
            'msgid "Preview:"\n'
            'msgstr "Translated Preview:"\n'
            '\n'
            'msgid "Regular"\n'
            'msgstr "Translated Regular"\n'
            '\n'
            'msgid "Bold Italic"\n'
            'msgstr "Translated Bold Italic"\n'
            '\n'
            'msgid "The quick brown fox jumps over the lazy dog."\n'
            'msgstr "Translated preview text."\n',
            encoding="utf-8"
        )

        with patch.object(translation_manager, "get_translations_dir", return_value=translations_dir):
            translation_manager.set_language("zz_ZZ")
            dialog = FontSelectionDialog(QFont("Serif", 12))
            self.addCleanup(dialog.deleteLater)

            self.assertEqual(dialog.windowTitle(), "Translated Font Picker")
            self.assertEqual(dialog.font_label.text(), "Translated Font:")
            self.assertEqual(dialog.size_label.text(), "Translated Size:")
            self.assertEqual(dialog.style_label.text(), "Translated Style:")
            self.assertEqual(dialog.preview_label.text(), "Translated Preview:")
            self.assertEqual(dialog.size_combo.currentText(), "12")
            self.assertEqual(dialog.style_combo.itemText(0), "Translated Regular")
            self.assertEqual(dialog.style_combo.itemText(3), "Translated Bold Italic")
            self.assertEqual(dialog.preview_text.text(), "Translated preview text.")
            self.assertIn("QFontComboBox", dialog.styleSheet())
            self.assertIn("QFontComboBox::down-arrow", dialog.styleSheet())
            self.assertIn("QComboBox::down-arrow", dialog.styleSheet())
            self.assertIn("QAbstractItemView", dialog.styleSheet())

        translation_manager.set_language("en_US")

    def test_main_window_retranslates_toolbar_menu_actions(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_font = settings_manager.get_font()
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        translations_dir = Path(self.temp_dir.name) / "translations"
        translations_dir.mkdir()
        (translations_dir / "zz_ZZ.po").write_text(
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: zz_ZZ\\n"\n'
            '\n'
            'msgid "Menu"\n'
            'msgstr "Translated Menu"\n'
            '\n'
            'msgid "More Actions"\n'
            'msgstr "Translated More Actions"\n'
            '\n'
            'msgid "Settings"\n'
            'msgstr "Translated Settings"\n'
            '\n'
            'msgid "Open Settings"\n'
            'msgstr "Translated Open Settings"\n',
            encoding="utf-8"
        )

        with (
            patch.object(main_module, "EditorTab", FakeEditorTab),
            patch.object(translation_manager, "get_translations_dir", return_value=translations_dir),
        ):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            translation_manager.set_language("zz_ZZ")
            window.retranslate_actions()

            toolbar_tooltips = {
                action.text(): action.toolTip()
                for action in window.toolbar.actions()
                if not action.isSeparator() and action.text()
            }
            menu_actions = {
                action.text(): action.toolTip()
                for action in window.menu_dropdown.actions()
                if not action.isSeparator() and action.text()
            }

            self.assertEqual(toolbar_tooltips["Translated Menu"], "Translated More Actions")
            self.assertEqual(menu_actions["Translated Settings"], "Translated Open Settings")

        translation_manager.set_language("en_US")

    def test_main_window_applies_rtl_layout_for_rtl_language(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_font = settings_manager.get_font()
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        self.settings.save_setting("language", "fa_IR")
        self.addCleanup(lambda: QApplication.instance().setLayoutDirection(Qt.LayoutDirection.LeftToRight))
        self.addCleanup(lambda: translation_manager.set_language("en_US"))

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.layoutDirection(), Qt.LayoutDirection.RightToLeft)
            self.assertEqual(QApplication.instance().layoutDirection(), Qt.LayoutDirection.RightToLeft)

            window.apply_layout_direction("en_US")

            self.assertEqual(window.layoutDirection(), Qt.LayoutDirection.LeftToRight)
            self.assertEqual(QApplication.instance().layoutDirection(), Qt.LayoutDirection.LeftToRight)

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

    def test_main_window_open_file_dialog_uses_translation_without_shadowing(self):
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

        target = Path(self.temp_dir.name) / "dialog.md"
        target.write_text("# Dialog", encoding="utf-8")

        with patch.object(main_module, "EditorTab", FakeEditorTab), \
             patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(target), "")):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertTrue(window.open_file())
            self.assertEqual(window.tab_widget.currentWidget().current_file, str(target))

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
