import os
import signal
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

from PyQt6.QtCore import QPoint, QRect, Qt, QEvent
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QTextCursor, QTextDocument
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QTextEdit, QWidget

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

    def test_workspace_model_uses_themed_decoration_icons(self):
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir()
        note = workspace / "note.md"
        note.write_text("# Note", encoding="utf-8")

        file_icon = QIcon(QPixmap(8, 8))
        folder_icon = QIcon(QPixmap(10, 10))
        model = WorkspaceFileSystemModel()
        self.addCleanup(model.deleteLater)
        model.set_workspace_icons(file_icon, folder_icon)
        model.setRootPath(str(workspace))
        app().processEvents()

        file_index = model.index(str(note))
        folder_index = model.index(str(workspace))

        self.assertEqual(
            model.data(file_index, Qt.ItemDataRole.DecorationRole).cacheKey(),
            file_icon.cacheKey()
        )
        self.assertEqual(
            model.data(folder_index, Qt.ItemDataRole.DecorationRole).cacheKey(),
            folder_icon.cacheKey()
        )

    def test_terminal_interrupt_handler_installs_sigint_timer(self):
        qt_app = app()

        with patch.object(main_module.signal, "signal") as signal_mock:
            timer = main_module.install_terminal_interrupt_handler(qt_app)

        self.addCleanup(timer.stop)
        self.assertIs(qt_app._sigint_timer, timer)
        self.assertTrue(timer.isActive())
        self.assertEqual(timer.interval(), 100)
        signal_mock.assert_called_once()
        self.assertEqual(signal_mock.call_args.args[0], signal.SIGINT)

    def test_workspace_tree_uses_visible_hierarchy_settings(self):
        tree = WorkspaceTreeView()
        self.addCleanup(tree.deleteLater)

        tree.setIndentation(18)
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(False)
        tree.setAllColumnsShowFocus(False)
        tree.set_connector_color("#2F6FED")

        self.assertEqual(tree.indentation(), 18)
        self.assertTrue(tree.rootIsDecorated())
        self.assertFalse(tree.alternatingRowColors())
        self.assertFalse(tree.allColumnsShowFocus())
        self.assertEqual(tree.connector_color, QColor("#2F6FED"))

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

    def test_editor_uses_full_width_when_markdown_preview_is_hidden(self):
        editor = self.make_editor()

        self.assertFalse(editor.markdown_preview_visible)
        self.assertGreater(editor.editor.maximumWidth(), 1000000)

        editor.set_markdown_preview_visible(True, save_state=False)
        self.assertEqual(editor.editor.maximumWidth(), editor_tab_module.EDITOR_PREVIEW_MAX_WIDTH)

        editor.set_markdown_preview_visible(False, save_state=False)
        self.assertGreater(editor.editor.maximumWidth(), 1000000)

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
        self.assertEqual(exported_pages[0].page_layout.margins().top(), 10.0)
        info.assert_called_once()

    def test_markdown_preview_uses_registered_markdown_extensions(self):
        editor = self.make_editor()

        class Registry:
            markdown_extensions = [
                {
                    "process_html": lambda body, context: body.replace("<p>plugin</p>", "<section>plugin</section>"),
                    "head_html": lambda context: "<script>window.pluginHead = true;</script>",
                    "style_html": lambda context: ".plugin-extension { color: red; }",
                    "body_html": lambda context: "<script>window.pluginBody = true;</script>",
                }
            ]

        class PluginManager:
            registry = Registry()

        class MainWindow:
            plugin_manager = PluginManager()

        editor.set_main_window(MainWindow())

        html = editor.render_markdown_html("plugin")

        self.assertIn("<section>plugin</section>", html)
        self.assertIn("window.pluginHead", html)
        self.assertIn(".plugin-extension", html)
        self.assertIn("window.pluginBody", html)

    def test_markdown_preview_does_not_handle_plugin_syntax_without_extension(self):
        editor = self.make_editor()

        html = editor.render_markdown_html("```plugin-diagram\nA-->B\n```")

        self.assertIn("language-plugin-diagram", html)
        self.assertNotIn("window.pluginDiagram", html)

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

    def test_markdown_preview_splitter_size_survives_hide_and_show(self):
        self.settings.save_setting("pane_states", {
            "snippets_visible": False,
            "browser_visible": False,
            "markdown_preview_visible": False,
            "markdown_sizes": [720, 360],
            "sizes": [700, 300, 300],
        })
        editor = self.make_editor()

        self.assertEqual(editor.saved_markdown_sizes, [720, 360])

        editor.set_markdown_preview_visible(True)
        with patch.object(editor.markdown_splitter, "sizes", return_value=[800, 320]):
            editor.save_pane_states()
        self.assertEqual(self.settings.get_setting("pane_states")["markdown_sizes"], [800, 320])

        editor.set_markdown_preview_visible(False)
        with patch.object(editor.markdown_splitter, "sizes", return_value=[1120, 0]):
            editor.save_pane_states()
        self.assertEqual(self.settings.get_setting("pane_states")["markdown_sizes"], [800, 320])

        editor.set_markdown_preview_visible(True)
        self.assertEqual(editor.saved_markdown_sizes, [800, 320])

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
            self.assertIsInstance(window.tab_widget.tabBar(), main_module.LeftAlignedDocumentTabBar)
            window.settings_manager.save_ui_theme("Dracula")
            dark_app = main_module.ThemeManager.get_theme("Dracula", window.settings_manager.get_custom_themes())["app"]
            tab_bar = window.tab_widget.tabBar()
            self.assertEqual(tab_bar.tab_text_color(True).name(), QColor(dark_app["text"]).name())
            self.assertEqual(tab_bar.tab_text_color(False).name(), QColor(dark_app["muted"]).name())
            label_rect = tab_bar.label_contents_rect(QRect(0, 0, 160, 38))
            self.assertEqual(label_rect.top(), 0)
            self.assertEqual(label_rect.bottom(), 35)
            self.assertEqual(tab_bar.icon_vertical_offset, -1)
            self.assertFalse(window.tab_widget.tabIcon(0).isNull())
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
            self.assertEqual(toolbar_tooltips["Zoom In"], "Zoom In (Ctrl+=)")
            self.assertEqual(toolbar_tooltips["Zoom Out"], "Zoom Out (Ctrl+-)")
            self.assertEqual(toolbar_tooltips["Reset Zoom"], "Reset Zoom (Ctrl+0)")
            self.assertNotIn("Preview Font", toolbar_tooltips)
            self.assertNotIn("Theme", toolbar_tooltips)
            self.assertNotIn("Menu", toolbar_tooltips)
            self.assertTrue(all(toolbar_tooltips.values()))
            toolbar_actions = {
                action.text(): action
                for action in window.toolbar.actions()
                if not action.isSeparator() and action.text()
            }
            self.assertFalse(toolbar_actions["Zoom In"].icon().isNull())
            self.assertFalse(toolbar_actions["Zoom Out"].icon().isNull())
            self.assertFalse(toolbar_actions["Reset Zoom"].icon().isNull())
            self.assertEqual(toolbar_actions["Reset Zoom"].shortcut().toString(), "Ctrl+0")
            toolbar_actions["Zoom In"].trigger()
            self.assertEqual(first_tab.current_font.pointSize(), original_size + 1)
            toolbar_actions["Reset Zoom"].trigger()
            self.assertEqual(first_tab.current_font.pointSize(), original_size)
            self.assertIn("QToolBar#mainToolBar QToolButton:focus", QApplication.instance().styleSheet())
            self.assertIn("QToolBar#mainToolBar QToolButton:disabled", QApplication.instance().styleSheet())
            self.assertIn("padding: 0px", QApplication.instance().styleSheet())
            self.assertIn("spacing: 0px", QApplication.instance().styleSheet())
            self.assertIn("margin: 0px 0px", QApplication.instance().styleSheet())
            self.assertIn("max-height: 34px", QApplication.instance().styleSheet())
            self.assertIn("QTabWidget#documentTabs QTabBar::close-button", QApplication.instance().styleSheet())
            self.assertIn("subcontrol-position: center right", QApplication.instance().styleSheet())
            self.assertIn("margin-bottom: 2px", QApplication.instance().styleSheet())
            self.assertIn("text-align: center", QApplication.instance().styleSheet())
            self.assertIn("height: 38px", QApplication.instance().styleSheet())
            self.assertIn("QTabWidget#documentTabs::pane", QApplication.instance().styleSheet())
            self.assertIn("QSplitter#mainSplitter::handle", QApplication.instance().styleSheet())
            file_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "File")
            file_tooltips = {
                action.text(): action.toolTip()
                for action in file_menu.actions()
                if not action.isSeparator() and action.text()
            }
            self.assertEqual(file_tooltips["Export as PDF..."], "Export current file as PDF")
            self.assertNotEqual(window.icons["snippets"], window.icons["menu"])

    def test_settings_opens_as_reusable_workspace_tab(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

            def apply_theme(self, theme_name):
                self.theme_name = theme_name

            def update_line_numbers_visibility(self, visible):
                self.line_numbers_visible = visible

            def set_line_numbers_visible(self, visible):
                self.line_numbers_visible = visible

            def configure_autosave_timer(self):
                self.autosave_configured = True

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            initial_count = window.tab_widget.count()
            self.assertTrue(hasattr(window, "settings_activity_button"))
            self.assertFalse(window.settings_activity_button.icon().isNull())
            window.settings_activity_button.click()
            settings_tab = window.tab_widget.currentWidget()
            self.assertEqual(window.tab_widget.count(), initial_count + 1)
            self.assertIs(window.tab_widget.currentWidget(), settings_tab)
            self.assertFalse(window.tab_widget.tabIcon(window.tab_widget.currentIndex()).isNull())
            self.assertTrue(getattr(settings_tab, "is_settings_tab", False))
            self.assertGreaterEqual(settings_tab.settings_nav.count(), 3)
            self.assertEqual(settings_tab.settings_nav.item(0).text(), "Appearance")

            settings_tab.keyPressEvent(QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier
            ))
            self.assertEqual(window.tab_widget.count(), initial_count + 1)
            self.assertIs(window.tab_widget.currentWidget(), settings_tab)
            self.assertFalse(settings_tab.isHidden())

            self.assertIs(window.show_settings(), settings_tab)
            self.assertEqual(window.tab_widget.count(), initial_count + 1)

    def test_settings_autosave_does_not_recreate_chrome_for_regular_changes(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

            def apply_theme(self, theme_name):
                self.theme_name = theme_name

            def update_line_numbers_visibility(self, visible):
                self.line_numbers_visible = visible

            def set_line_numbers_visible(self, visible):
                self.line_numbers_visible = visible

            def configure_autosave_timer(self):
                self.autosave_configured = True

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            settings_tab = window.show_settings()
            toolbar = window.toolbar
            title_buttons = list(window.custom_title_bar.title_menu_buttons)

            settings_tab.autosave_enabled_check.setChecked(
                not settings_tab.autosave_enabled_check.isChecked()
            )
            settings_tab.commit_auto_save()

            self.assertIs(window.toolbar, toolbar)
            self.assertEqual(window.custom_title_bar.title_menu_buttons, title_buttons)

    def test_main_window_builds_accessible_themed_menubar(self):
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
            self.addCleanup(lambda: QApplication.instance().setStyleSheet(""))

            menubar = window.menuBar()
            self.assertEqual(window.objectName(), "appWindow")
            self.assertEqual(window.minimumSize().width(), 760)
            self.assertEqual(window.minimumSize().height(), 420)
            self.assertTrue(window.statusBar.isSizeGripEnabled())
            self.assertIs(window.main_layout.itemAt(0).widget(), window.custom_title_bar)
            self.assertIs(window.main_layout.itemAt(1).widget(), window.toolbar)
            self.assertFalse(window.custom_title_bar.isHidden())
            self.assertTrue(window.custom_title_bar.app_title.isHidden())
            self.assertTrue(hasattr(window.custom_title_bar, "show_title_menu"))
            self.assertEqual(window.custom_title_bar.command_center.objectName(), "titleBarCommandCenter")
            self.assertLessEqual(window.custom_title_bar.command_center.minimumHeight(), 30)
            self.assertLessEqual(window.custom_title_bar.command_center.maximumHeight(), 30)
            self.assertLessEqual(window.custom_title_bar.command_center.width(), 380)
            self.assertIsNotNone(window.custom_title_bar.command_center.graphicsEffect())
            self.assertTrue(window.statusBar.isSizeGripEnabled())
            self.assertEqual(window.main_layout.contentsMargins().right(), 1)
            self.assertEqual(window.custom_title_bar.left_balance_area.width(), 10)
            self.assertGreaterEqual(window.custom_title_bar.right_balance_area.width(), 8)
            collapsed_width = window.custom_title_bar.command_center.width()
            expanded_width = window.custom_title_bar.search_expanded_width()
            self.assertGreaterEqual(expanded_width, collapsed_width * 4)
            self.assertFalse(window.custom_title_bar.menu_container.isHidden())
            self.assertTrue(hasattr(window.custom_title_bar, "title_menu_buttons"))
            self.assertEqual(
                [button.text() for button in window.custom_title_bar.title_menu_buttons],
                ["File", "Edit", "View", "Workspace", "Help"]
            )
            self.assertTrue(all(isinstance(button, QPushButton) for button in window.custom_title_bar.title_menu_buttons))
            self.assertTrue(all(button.height() <= 32 for button in window.custom_title_bar.title_menu_buttons))
            self.assertTrue(
                all(
                    button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 14
                    for button in window.custom_title_bar.title_menu_buttons
                )
            )
            window.show()
            QApplication.processEvents()
            self.assertEqual(window.custom_title_bar.title_menu_buttons[0].geometry().x(), 0)
            menu_right = window.custom_title_bar.menu_container.geometry().right()
            search_left = window.custom_title_bar.command_center.geometry().left()
            self.assertEqual(search_left - menu_right - 1, 10)
            window.custom_title_bar.animate_search_width(True)
            QApplication.processEvents()
            self.assertTrue(window.custom_title_bar.search_expanded)
            window.custom_title_bar.command_center.clear()
            outside_search = window.tab_widget.mapToGlobal(window.tab_widget.rect().center())
            window.custom_title_bar.collapse_search_if_empty_from_global_pos(outside_search)
            self.assertFalse(window.custom_title_bar.search_expanded)
            window.custom_title_bar.animate_search_width(True)
            window.custom_title_bar.command_center.setText("find me")
            window.custom_title_bar.collapse_search_if_empty_from_global_pos(outside_search)
            self.assertTrue(window.custom_title_bar.search_expanded)
            window.custom_title_bar.command_center.clear()
            window.custom_title_bar.animate_search_width(False)
            controls_right = window.custom_title_bar.window_controls.mapTo(
                window.custom_title_bar,
                window.custom_title_bar.window_controls.rect().topRight()
            ).x()
            self.assertEqual(controls_right, window.custom_title_bar.width() - 1)
            self.assertIn(window.custom_title_bar.left_balance_area, window.custom_title_bar.draggable_title_widgets)
            self.assertIn(window.custom_title_bar.right_balance_area, window.custom_title_bar.draggable_title_widgets)
            self.assertFalse(hasattr(window, "toolbar_menu_container"))
            self.assertTrue(bool(window.windowFlags() & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(menubar.isHidden())
            self.assertFalse(window.custom_title_bar.close_button.isHidden())
            self.assertFalse(window.custom_title_bar.maximize_button.isHidden())
            self.assertFalse(window.custom_title_bar.minimize_button.isHidden())
            self.assertEqual(window.custom_title_bar.close_button.text(), "×")
            self.assertEqual(window.custom_title_bar.maximize_button.text(), "□")
            self.assertEqual(window.custom_title_bar.minimize_button.text(), "−")
            self.assertEqual(window.new_workspace_file_button.text(), "")
            self.assertEqual(window.new_workspace_folder_button.text(), "")
            self.assertFalse(window.new_workspace_file_button.icon().isNull())
            self.assertFalse(window.new_workspace_folder_button.icon().isNull())
            self.assertIn((window.new_workspace_file_button, "file"), window.icon_buttons)
            self.assertIn((window.new_workspace_folder_button, "folder"), window.icon_buttons)
            window.settings_manager.save_setting("icon_contrast", "auto")
            self.assertEqual(window.get_icon_color(), "#111111")
            window.settings_manager.save_setting("ui_theme", "Dark")
            self.assertEqual(window.get_icon_color(), "#FFFFFF")
            window.settings_manager.save_setting("ui_theme", "Light")
            original_workspace_file_icon = window.workspace_model.workspace_file_icon.cacheKey()
            window.settings_manager.save_setting("icon_contrast", "accent")
            window.update_action_icons()
            self.assertNotEqual(window.workspace_model.workspace_file_icon.cacheKey(), original_workspace_file_icon)
            self.assertFalse(hasattr(window, "toolbar_window_controls"))
            self.assertEqual(menubar.objectName(), "appMenuBar")
            self.assertFalse(menubar.isNativeMenuBar())
            self.assertEqual(menubar.focusPolicy(), Qt.FocusPolicy.StrongFocus)
            self.assertEqual(menubar.accessibleName(), "Application menu")

            menu_titles = [action.text() for action in menubar.actions()]
            self.assertEqual(menu_titles, ["File", "Edit", "View", "Workspace", "Help"])

            file_actions = [
                action for action in menubar.actions()[0].menu().actions()
                if not action.isSeparator()
            ]
            self.assertEqual(file_actions[0].text(), "New Editor Tab")
            self.assertEqual(file_actions[0].toolTip(), "Create a new editor tab")
            self.assertFalse(file_actions[0].icon().isNull())
            self.assertIn("Settings", [action.text() for action in file_actions])

            edit_actions = [
                action.text() for action in menubar.actions()[1].menu().actions()
                if not action.isSeparator()
            ]
            self.assertEqual(edit_actions[:3], ["Undo", "Redo", "Cut"])
            self.assertIn("Find/Replace", edit_actions)
            self.assertNotIn("Settings", edit_actions)
            workspace_actions = [
                action for action in menubar.actions()[3].menu().actions()
                if not action.isSeparator()
            ]
            self.assertIn("New Workspace File...", [action.text() for action in workspace_actions])
            self.assertIn("New Workspace Folder...", [action.text() for action in workspace_actions])
            self.assertTrue(
                all(
                    not action.icon().isNull()
                    for action in workspace_actions
                    if action.text() in {"New Workspace File...", "New Workspace Folder..."}
                )
            )
            self.assertIn("QWidget#customTitleBar", QApplication.instance().styleSheet())
            self.assertIn("QWidget#titleBarWindowControls", QApplication.instance().styleSheet())
            self.assertIn("QLineEdit#titleBarCommandCenter", QApplication.instance().styleSheet())
            self.assertIn("QMenuBar#appMenuBar", QApplication.instance().styleSheet())
            self.assertIn("QTreeView#workspaceTree::branch", QApplication.instance().styleSheet())
            self.assertIn("data:image/svg+xml;utf8", QApplication.instance().styleSheet())
            self.assertIn("QTreeView#workspaceTree::branch:has-children:closed", QApplication.instance().styleSheet())
            self.assertIn("QTreeView#workspaceTree::branch:has-children:open", QApplication.instance().styleSheet())
            self.assertEqual(window.workspace_tree.connector_color, QColor("#2F6FED"))
            self.assertIn("QTabWidget#documentTabs {\n                border-right: 1px solid", QApplication.instance().styleSheet())
            self.assertIn("QMainWindow#appWindow", QApplication.instance().styleSheet())
            self.assertIn('QMainWindow#appWindow[chromeMaximized="true"]', QApplication.instance().styleSheet())
            self.assertIn("QWidget#mainSurface", QApplication.instance().styleSheet())
            self.assertIn('QWidget#mainSurface[chromeMaximized="true"]', QApplication.instance().styleSheet())
            self.assertIn('QMainWindow#appWindow[chromeMaximized="true"] QWidget#customTitleBar', QApplication.instance().styleSheet())
            self.assertIn('QMainWindow#appWindow[chromeMaximized="true"] QStatusBar#statusBar', QApplication.instance().styleSheet())
            self.assertIn("QWidget#activityRibbon", QApplication.instance().styleSheet())
            self.assertIn('QMainWindow#appWindow[chromeMaximized="true"] QWidget#activityRibbon', QApplication.instance().styleSheet())
            maximized_styles = [
                block
                for block in QApplication.instance().styleSheet().split("}")
                if 'chromeMaximized="true"' in block
            ]
            self.assertTrue(maximized_styles)
            self.assertFalse(any("border-left: 0px" in block for block in maximized_styles))
            self.assertFalse(any("border-right: 0px" in block for block in maximized_styles))
            self.assertFalse(any("border-top: 0px" in block for block in maximized_styles))
            self.assertFalse(any("border-bottom: 0px" in block for block in maximized_styles))

            window.show()
            QApplication.processEvents()
            self.assertFalse(window.property("chromeMaximized"))
            self.assertFalse(window.centralWidget().property("chromeMaximized"))
            window.showMaximized()
            QApplication.processEvents()
            window.update_window_state_properties()
            self.assertTrue(window.property("chromeMaximized"))
            self.assertTrue(window.centralWidget().property("chromeMaximized"))
            window.showNormal()
            QApplication.processEvents()
            window.update_window_state_properties()
            self.assertFalse(window.property("chromeMaximized"))
            self.assertFalse(window.centralWidget().property("chromeMaximized"))
            top_left_edges, top_left_cursor = window.resize_hit_test(window.frameGeometry().topLeft())
            self.assertTrue(top_left_edges & Qt.Edge.LeftEdge)
            self.assertTrue(top_left_edges & Qt.Edge.TopEdge)
            self.assertEqual(top_left_cursor, Qt.CursorShape.SizeFDiagCursor)
            right_edges, right_cursor = window.resize_hit_test(window.frameGeometry().topRight() - QPoint(1, -20))
            self.assertTrue(right_edges & Qt.Edge.RightEdge)
            self.assertEqual(right_cursor, Qt.CursorShape.SizeHorCursor)

    def test_plugin_menu_deduplicates_sidebar_items_that_open_existing_panels(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        class FakeRegistry:
            def __init__(self):
                self.commands = []
                self.panels = [
                    {"id": "browser-panel.panel", "title": "Browser", "type": "python"},
                ]
                self.sidebar_items = [
                    {"id": "browser-panel.sidebar", "title": "Browser", "panel": "browser-panel.panel"},
                ]
                self.toolbar_actions = []
                self.panel_factories = {}
                self.command_callbacks = {}

        class FakePluginManager:
            def __init__(self, settings_manager):
                self.registry = FakeRegistry()

            def refresh(self):
                return []

            def activate_enabled_plugins(self):
                return self.registry

        with patch.object(main_module, "EditorTab", FakeEditorTab), patch.object(main_module, "PluginManager", FakePluginManager):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            plugins_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "Plugins")
            plugin_actions = [action.text() for action in plugins_menu.actions() if not action.isSeparator()]
            self.assertEqual(plugin_actions, ["Browser"])

    def test_main_window_closes_rss_tabs_without_editor_assumption(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

            def save_file(self, force_dialog=False):
                return True

        class FakeRSSTab(QWidget):
            pass

        with (
            patch.object(main_module, "EditorTab", FakeEditorTab),
            patch.object(main_module, "RSSTab", FakeRSSTab),
        ):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            window.new_rss_tab()
            self.assertIsInstance(window.tab_widget.currentWidget(), FakeRSSTab)

            window.close_current_tab()

            self.assertNotIsInstance(window.tab_widget.currentWidget(), FakeRSSTab)
            self.assertTrue(window.handle_unsaved_changes())

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

    def test_double_click_tab_bar_uses_configured_tab_actions(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        class FakeMouseDoubleClickEvent:
            def __init__(self, pos):
                self._pos = pos

            def type(self):
                return QEvent.Type.MouseButtonDblClick

            def pos(self):
                return self._pos

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            tab_bar = window.tab_widget.tabBar()
            tab_pos = tab_bar.tabRect(0).center()
            empty_pos = QPoint(10000, max(1, tab_bar.height() // 2))
            widget_empty_pos = QPoint(
                window.tab_widget.width() - 4,
                tab_bar.mapTo(window.tab_widget, tab_bar.rect().center()).y()
            )
            initial_count = window.tab_widget.count()

            self.assertTrue(window.eventFilter(tab_bar, FakeMouseDoubleClickEvent(tab_pos)))
            self.assertEqual(window.tab_widget.count(), initial_count)
            self.assertTrue(window.eventFilter(tab_bar, FakeMouseDoubleClickEvent(empty_pos)))
            self.assertEqual(window.tab_widget.count(), initial_count + 1)
            self.assertTrue(window.eventFilter(window.tab_widget, FakeMouseDoubleClickEvent(widget_empty_pos)))
            self.assertEqual(window.tab_widget.count(), initial_count + 2)

            window.settings_manager.save_setting("double_click_tab_closes_tab", False)
            current_count = window.tab_widget.count()
            current_tab_pos = tab_bar.tabRect(0).center()
            self.assertFalse(window.eventFilter(tab_bar, FakeMouseDoubleClickEvent(current_tab_pos)))
            self.assertEqual(window.tab_widget.count(), current_count)

            window.settings_manager.save_setting("double_click_empty_tab_bar_new_tab", False)
            self.assertFalse(window.eventFilter(tab_bar, FakeMouseDoubleClickEvent(empty_pos)))
            self.assertFalse(window.eventFilter(window.tab_widget, FakeMouseDoubleClickEvent(widget_empty_pos)))
            self.assertEqual(window.tab_widget.count(), current_count)

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
            file_menu = next(
                action.menu()
                for action in window.menuBar().actions()
                if action.property("text_key") == "File"
            )
            menu_actions = {
                action.text(): action.toolTip()
                for action in file_menu.actions()
                if not action.isSeparator() and action.text()
            }

            self.assertNotIn("Translated Menu", toolbar_tooltips)
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

    def test_workspace_sidebar_position_follows_language_and_can_toggle(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_font = settings_manager.get_font()
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        self.settings.save_setting("language", "fa_IR")
        self.settings.save_setting("workspace_sidebar_position", "auto")
        self.addCleanup(lambda: QApplication.instance().setLayoutDirection(Qt.LayoutDirection.LeftToRight))
        self.addCleanup(lambda: translation_manager.set_language("en_US"))

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.resolved_workspace_sidebar_position(), "right")
            self.assertEqual(window.main_splitter.indexOf(window.activity_ribbon), 2)
            self.assertEqual(window.main_splitter.indexOf(window.workspace_widget), 1)
            self.assertEqual(window.main_splitter.indexOf(window.tab_widget), 0)
            self.assertEqual(window.activity_ribbon.property("side"), "right")
            self.assertEqual(window.workspace_widget.property("side"), "right")
            self.assertEqual(window.workspace_widget.maximumWidth(), main_module.WORKSPACE_SIDEBAR_MAX_WIDTH)
            self.assertGreaterEqual(main_module.WORKSPACE_SIDEBAR_MAX_WIDTH, main_module.WORKSPACE_SIDEBAR_WIDTH * 2)

            window.toggle_workspace_sidebar_position()

            self.assertEqual(window.settings_manager.get_setting("workspace_sidebar_position"), "left")
            self.assertEqual(window.main_splitter.indexOf(window.activity_ribbon), 0)
            self.assertEqual(window.main_splitter.indexOf(window.workspace_widget), 1)
            self.assertEqual(window.main_splitter.indexOf(window.tab_widget), 2)
            self.assertEqual(window.activity_ribbon.property("side"), "left")
            self.assertEqual(window.workspace_widget.property("side"), "left")

    def test_main_splitter_sizes_are_saved_and_restored_by_sidebar_side(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_font = settings_manager.get_font()
                self.current_file = None

            def set_main_window(self, main_window):
                self.main_window = main_window

        self.settings.save_setting("language", "en_US")
        self.settings.save_setting("workspace_sidebar_position", "left")
        self.settings.save_setting("main_splitter_sizes", {"left": [48, 360, 840]})

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.main_splitter_sizes_for_side("left"), [48, 360, 840])

            with patch.object(window.main_splitter, "sizes", return_value=[48, 420, 780]):
                window.save_main_splitter_sizes()

            self.assertEqual(
                window.settings_manager.get_setting("main_splitter_sizes")["left"],
                [48, 420, 780]
            )

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
