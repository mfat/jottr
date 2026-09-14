"""Main editor tab widget."""
import json
import os
import sys
import tempfile
import time
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextEdit, QListWidget,
    QInputDialog, QMenu, QDialog, QToolBar, QCompleter,
    QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel, QToolTip,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QStringListModel, QEvent, QSize, QRect,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QMarginsF,
)
from PyQt6.QtGui import (
    QAction, QShortcut, QTextCharFormat, QIcon, QFont, QKeySequence,
    QPainter, QPen, QColor, QFontMetrics, QTextDocument, QTextCursor, QTextOption,
    QPageLayout, QPageSize,
)

from jottr.snippet_editor_dialog import SnippetEditorDialog
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _, is_rtl_language, localize_digits
from jottr.file_dialogs import get_open_file_name, get_save_file_name

from jottr.editor.spellcheck import (
    SpellCheckHighlighter,
    find_word_bounds,
)
from jottr.editor.case_transform import (
    apply_capitalize,
    apply_lowercase,
    apply_uppercase,
)
from jottr.editor.text_edit import CompletingTextEdit
from jottr.editor.text_format import (
    apply_code_block,
    apply_heading,
    apply_line_prefix,
    apply_link,
    apply_numbered_list,
    apply_wrap,
    apply_wrap_in_quotes,
)
from jottr.editor.markdown import MarkdownPreviewMixin
from jottr.editor.browser import BrowserPaneMixin
from jottr.editor.focus_mode import FocusModeMixin
from jottr.editor.find_replace import FindReplaceMixin
from jottr.editor.swap_file import SwapFileMixin

# Lazily bound / test-patched WebEngine symbols used by markdown preview.
QWebEngineView = None
MarkdownPreviewPage = None
# Lazily bound / test-patched page used for PDF export.
QWebEnginePage = None


class EditorTab(
    MarkdownPreviewMixin,
    BrowserPaneMixin,
    FocusModeMixin,
    FindReplaceMixin,
    SwapFileMixin,
    QWidget,
):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.current_font = self.settings_manager.get_font("editor")
        self.current_theme = self.settings_manager.get_theme()
        self.web_view = None  # Initialize to None
        self.main_window = None  # Initialize main_window to None
        self.markdown_preview_visible = False
        self.preview_scroll_pending = False
        self.editor_scroll_pending = False
        self.syncing_markdown_scroll = False
        self.preview_scroll_timer = None
        self.markdown_render_timer = None
        self.markdown_preview_loading = False
        self.preview_sync_after_load = False
        self.markdown_typing_active_until = 0
        self.ui_animations = {}
        self.editor_scroll_animation = None
        self.pending_preview_source_line = None
        self.ignore_preview_scroll_until = 0
        self.preview_user_scroll_until = 0
        self.markdown_preview_file = os.path.join(
            tempfile.gettempdir(),
            f'jottr_markdown_preview_{id(self)}.html'
        )
        
        # Setup UI components
        self.setup_ui()
        
        # Setup autosave after UI is ready
        self.changes_pending = False
        
        # Start configurable autosave timer
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.force_save)
        self.configure_autosave_timer()

        self.preview_scroll_timer = QTimer(self)
        self.preview_scroll_timer.timeout.connect(self.schedule_editor_scroll_sync)
        self.preview_scroll_timer.setInterval(250)

        self.markdown_render_timer = QTimer(self)
        self.markdown_render_timer.setSingleShot(True)
        self.markdown_render_timer.setInterval(650)
        self.markdown_render_timer.timeout.connect(self.update_markdown_preview)
        
        # Apply theme
        ThemeManager.apply_theme(
            self.editor,
            self.current_theme,
            self.current_font
        )

        # Track if content has been modified
        self.editor.document().modificationChanged.connect(self.handle_modification)
        self.editor.document().setModified(False)
        
        # Install event filter for key handling
        self.editor.installEventFilter(self)
        
        # Add ESC shortcut for exiting focus mode
        self.focus_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.focus_shortcut.activated.connect(self.handle_escape)
        
        self.focus_mode = False
        self.panes_opened_in_focus = {'browser': False, 'snippets': False}  # Track panes opened during focus mode
        self.suggestion_tooltip = None
        self.selected_suggestion_index = -1
        self.current_suggestions = []
        self.editor.textChanged.connect(self.handle_text_changed)
        self.editor.textChanged.connect(self.mark_autosave_pending)
        self.editor.textChanged.connect(self.schedule_markdown_preview_update)
        self.editor.textChanged.connect(self.schedule_document_language_refresh)
        self.editor.cursorPositionChanged.connect(self.schedule_markdown_cursor_sync)
        self.editor.verticalScrollBar().valueChanged.connect(self.schedule_markdown_scroll_sync)
        self.setup_swap_file()
        self._document_language_timer = QTimer(self)
        self._document_language_timer.setSingleShot(True)
        self._document_language_timer.setInterval(400)
        self._document_language_timer.timeout.connect(self.refresh_document_language_detection)

    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for editor and side panes
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("workspaceSplitter")
        
        # Create text editor with default font
        self.editor = CompletingTextEdit(self)  # Pass self as parent
        self.editor.setObjectName("writingEditor")
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.editor.set_line_numbers_visible(
            self.settings_manager.get_setting('editor_line_numbers', True)
        )
        self.update_font(self.current_font)

        self.editor_pane = QWidget()
        self.editor_pane.setObjectName("editorPane")
        editor_pane_layout = QHBoxLayout(self.editor_pane)
        editor_pane_layout.setContentsMargins(0, 0, 0, 0)
        editor_pane_layout.setSpacing(0)

        self.markdown_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.markdown_splitter.setObjectName("markdownSplitter")
        self.markdown_splitter.addWidget(self.editor)

        # Placeholder until markdown preview is first shown — avoids starting
        # Chromium on every blank editor tab at startup.
        self.markdown_preview = QWidget()
        self.markdown_preview.setObjectName("markdownPreview")
        self._markdown_preview_ready = False
        self.markdown_preview.setVisible(False)
        self.markdown_preview.installEventFilter(self)
        self.markdown_splitter.addWidget(self.markdown_preview)
        self.markdown_splitter.setSizes([600, 600])
        self.markdown_splitter.splitterMoved.connect(self.save_pane_states)
        editor_pane_layout.addWidget(self.markdown_splitter)
        self.apply_language_direction()
        
        # Connect text changed signal to update status
        self.editor.textChanged.connect(self.update_status)
        
        # Create spell checker
        self.highlighter = SpellCheckHighlighter(self.editor.document(), self.settings_manager)
        
        # Add editor to splitter
        self.splitter.addWidget(self.editor_pane)
        
        # Create snippet widget
        self.snippet_widget = QWidget()
        self.snippet_widget.setObjectName("sidePanel")
        snippet_layout = QVBoxLayout(self.snippet_widget)
        snippet_layout.setContentsMargins(0, 0, 0, 0)
        snippet_layout.setSpacing(0)
        
        # Snippet header
        snippet_header = QWidget()
        snippet_header.setObjectName("panelHeader")
        snippet_header.setFixedHeight(36)
        header_layout = QHBoxLayout(snippet_header)
        header_layout.setContentsMargins(10, 4, 8, 4)
        header_layout.setSpacing(6)
        
        snippet_title = QLabel(_("Snippets"))
        snippet_title.setObjectName("panelTitle")
        header_layout.addWidget(snippet_title)
        header_layout.addStretch()

        snippet_new = QPushButton("+")
        snippet_new.setObjectName("panelHeaderButton")
        snippet_new.setFixedSize(24, 24)
        snippet_new.setToolTip(_("New snippet"))
        snippet_new.clicked.connect(self.new_snippet)
        header_layout.addWidget(snippet_new)

        snippet_close = QPushButton("×")
        snippet_close.setObjectName("panelCloseButton")
        snippet_close.setFixedSize(24, 24)
        snippet_close.setToolTip(_("Close snippets"))
        snippet_close.clicked.connect(lambda: self.toggle_pane("snippets"))
        header_layout.addWidget(snippet_close)
        
        snippet_layout.addWidget(snippet_header)
        
        # Snippet list
        self.snippet_list = QListWidget()
        self.snippet_list.setObjectName("snippetList")
        self.snippet_list.itemDoubleClicked.connect(self.insert_snippet)
        self.snippet_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.snippet_list.customContextMenuRequested.connect(self.show_snippet_context_menu)
        self.update_snippet_list()  # Populate the list
        snippet_layout.addWidget(self.snippet_list)
        
        # Create browser widget without web view
        self.browser_widget = QWidget()
        self.browser_widget.setObjectName("sidePanel")
        browser_layout = QVBoxLayout(self.browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)
        
        # Create browser toolbar
        self.setup_browser_toolbar()
        
        # Create placeholder for web view
        self.web_container = QWidget()
        web_container_layout = QVBoxLayout(self.web_container)  # Add layout
        web_container_layout.setContentsMargins(0, 0, 0, 0)    # No margins
        web_container_layout.setSpacing(0)                     # No spacing
        browser_layout.addWidget(self.web_container)
        
        # Add widgets to splitter
        self.splitter.addWidget(self.snippet_widget)
        self.splitter.addWidget(self.browser_widget)
        
        # Add splitter to layout
        layout.addWidget(self.splitter)
        self.apply_workspace_style()
        
        # Hide side panes by default
        self.snippet_widget.hide()
        self.browser_widget.hide()
        
        # Restore pane states
        states = self.settings_manager.get_setting('pane_states', {
            'snippets_visible': False,
            'markdown_preview_visible': False,
            'markdown_sizes': [600, 600],
            'sizes': [700, 300, 300]
        })
        
        # Apply visibility
        self.snippet_widget.setVisible(states.get('snippets_visible', False))
        # The browser pane always starts closed (hidden above) and is not restored.
        self.set_markdown_preview_visible(False, save_state=False)
        
        # Apply sizes
        if 'sizes' in states:
            self.splitter.setSizes(states['sizes'])
        if 'markdown_sizes' in states:
            self.markdown_splitter.setSizes(states['markdown_sizes'])
        
        # Connect splitter moved signal to save states
        self.splitter.splitterMoved.connect(self.save_pane_states)
        
        # Set focus to editor
        self.editor.setFocus()
        
        # Create find/replace toolbar (initially hidden)
        self.find_toolbar = QWidget(self)
        self.find_toolbar.setObjectName("findToolbar")
        self.find_toolbar.setVisible(False)
        self.find_toolbar.setFixedHeight(40)
        find_layout = QHBoxLayout(self.find_toolbar)
        find_layout.setContentsMargins(8, 4, 8, 4)
        find_layout.setSpacing(6)
        
        # Find input
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(_("Find"))
        self.find_input.textChanged.connect(self.find_text)
        self.find_input.setFixedHeight(28)
        find_layout.addWidget(self.find_input)
        
        # Replace input
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText(_("Replace with"))
        self.replace_input.setFixedHeight(28)
        find_layout.addWidget(self.replace_input)
        
        # Find next/previous buttons
        self.find_prev_btn = QPushButton("↑")
        self.find_next_btn = QPushButton("↓")
        self.find_prev_btn.setFixedSize(28, 28)
        self.find_next_btn.setFixedSize(28, 28)
        self.find_prev_btn.clicked.connect(lambda: self.find_text(direction='up'))
        self.find_next_btn.clicked.connect(lambda: self.find_text(direction='down'))
        find_layout.addWidget(self.find_prev_btn)
        find_layout.addWidget(self.find_next_btn)
        
        # Replace buttons
        self.replace_btn = QPushButton(_("Replace"))
        self.replace_all_btn = QPushButton(_("All"))  # Shortened text
        self.replace_btn.setFixedHeight(28)
        self.replace_all_btn.setFixedHeight(28)
        self.replace_btn.clicked.connect(self.replace_text)
        self.replace_all_btn.clicked.connect(self.replace_all)
        find_layout.addWidget(self.replace_btn)
        find_layout.addWidget(self.replace_all_btn)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.toggle_find)
        find_layout.addWidget(close_btn)
        
        # Add styling
        layout.addWidget(self.find_toolbar)

    def apply_workspace_style(self):
        """Apply the editor workspace chrome."""
        theme = ThemeManager.get_theme(self.current_theme)
        self.setStyleSheet(ThemeManager.build_workspace_stylesheet(theme))

    def autosave_enabled(self):
        """Return whether autosave should write existing files."""
        return bool(self.settings_manager.get_setting('autosave_enabled', False))

    def autosave_interval_ms(self):
        """Return configured autosave interval in milliseconds."""
        try:
            seconds = int(self.settings_manager.get_setting('autosave_interval_seconds', 30))
        except (TypeError, ValueError):
            seconds = 30
        return max(1, seconds) * 1000

    def configure_autosave_timer(self):
        """Apply autosave settings to this tab."""
        self.backup_timer.setInterval(self.autosave_interval_ms())
        if self.autosave_enabled():
            if self.current_file and self.editor.document().isModified():
                self.changes_pending = True
            self.backup_timer.start()
        else:
            self.backup_timer.stop()

    def mark_autosave_pending(self):
        """Mark the current file as needing autosave."""
        if not self.autosave_enabled():
            return
        if not self.current_file:
            return
        self.changes_pending = True

    def force_save(self):
        """Force save if there are pending changes."""
        if self.autosave_enabled() and self.changes_pending:
            self.autosave()

    def report_autosave_failure(self, error):
        """Surface an autosave failure in the console and status bar."""
        message = _("Autosave failed: {error}").format(error=str(error))
        print(message)
        if self.main_window and hasattr(self.main_window, "statusBar"):
            self.main_window.statusBar.showMessage(message, 5000)

    def autosave(self):
        """Autosave the current file with an atomic replace."""
        if not self.current_file:
            self.changes_pending = False
            return False

        content = self.editor.toPlainText()
        temp_content = self.current_file + '.tmp'
        
        try:
            with open(temp_content, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            with open(temp_content, 'r', encoding='utf-8') as f:
                saved_content = f.read()
                if saved_content != content:
                    raise ValueError("Content verification failed")

            os.replace(temp_content, self.current_file)
        except Exception as e:
            try:
                if os.path.exists(temp_content):
                    os.remove(temp_content)
            except OSError:
                pass
            self.report_autosave_failure(e)
            return False

        self.changes_pending = False
        self.mark_swap_file_saved(content)
        self.editor.document().setModified(False)
        if self.main_window and hasattr(self.main_window, 'save_workspace_open_files'):
            self.main_window.save_workspace_open_files()
        if self.main_window and hasattr(self.main_window, 'save_workspace_markdown_files'):
            self.main_window.save_workspace_markdown_files()
        return True

    def preferred_save_kind(self):
        """Return 'markdown', 'text', or 'other' for Save dialog defaults."""
        if self.current_file:
            if self.is_markdown_file(self.current_file):
                return "markdown"
            extension = os.path.splitext(self.current_file)[1].lower()
            if extension == ".txt":
                return "text"
            if extension:
                return "other"
        if getattr(self, "markdown_preview_visible", False):
            return "markdown"
        return "text"

    def preferred_save_suffix(self):
        """Default extension (without dot) for the preferred save kind."""
        kind = self.preferred_save_kind()
        if kind == "markdown":
            return "md"
        if kind == "text":
            return "txt"
        return ""

    def save_dialog_filters(self):
        """Name filters and initial selection for the Save dialog."""
        markdown_filter = _("Markdown Files (*.md *.markdown)")
        text_filter = _("Text Files (*.txt)")
        all_files_filter = _("All Files (*.*)")
        kind = self.preferred_save_kind()
        if kind == "markdown":
            return (
                f"{markdown_filter};;{text_filter};;{all_files_filter}",
                markdown_filter,
            )
        if kind == "text":
            return (
                f"{text_filter};;{markdown_filter};;{all_files_filter}",
                text_filter,
            )
        return (
            f"{all_files_filter};;{markdown_filter};;{text_filter}",
            all_files_filter,
        )

    def suffix_for_save_filter(self, selected_filter, fallback_suffix=""):
        """Pick an extension from the chosen Save dialog filter."""
        selected = (selected_filter or "").lower()
        if "*.md" in selected or "*.markdown" in selected:
            return "md"
        if "*.txt" in selected:
            return "txt"
        return fallback_suffix

    def ensure_save_extension(self, file_path, selected_filter="", fallback_suffix=""):
        """Append a relevant extension when the chosen path has none."""
        if not file_path or os.path.splitext(file_path)[1]:
            return file_path
        suffix = self.suffix_for_save_filter(selected_filter, fallback_suffix)
        if not suffix:
            return file_path
        return f"{file_path}.{suffix}"

    def save_file(self, force_dialog=False):
        """Save file, optionally forcing Save As dialog"""
        if not self.current_file or force_dialog:
            filters, initial_filter = self.save_dialog_filters()
            start_path = self.current_file or os.path.expanduser("~")
            fallback_suffix = self.preferred_save_suffix()
            file_name, selected_filter = get_save_file_name(
                self,
                _("Save File"),
                start_path,
                filters,
                initial_filter,
            )
            if file_name:
                self.current_file = self.ensure_save_extension(
                    file_name, selected_filter, fallback_suffix
                )
            else:
                return False
                
        try:
            content = self.editor.toPlainText()
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.mark_swap_file_saved(content)

            # Update tab title
            if self.main_window:
                current_index = self.main_window.tab_widget.indexOf(self)
                self.main_window.tab_widget.setTabText(current_index, os.path.basename(self.current_file))
            
            # Mark document as unmodified
            self.editor.document().setModified(False)
            self.changes_pending = False
            if self.main_window and hasattr(self.main_window, 'save_workspace_open_files'):
                self.main_window.save_workspace_open_files()
            if self.main_window and hasattr(self.main_window, 'save_workspace_markdown_files'):
                self.main_window.save_workspace_markdown_files()
            return True
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Could not save file: {error}").format(error=str(e)))
            return False

    def suggested_pdf_export_path(self):
        """Return a sensible default path for exporting the current document."""
        if self.current_file:
            return os.path.splitext(self.current_file)[0] + ".pdf"
        return os.path.join(os.path.expanduser("~"), "document.pdf")

    def prompt_pdf_export_path(self):
        """Show a native/portal save dialog for PDF export."""
        pdf_filter = _("PDF Files (*.pdf)")
        all_files_filter = _("All Files (*.*)")
        selected_path, _selected_filter = get_save_file_name(
            self,
            _("Export as PDF"),
            self.suggested_pdf_export_path(),
            f"{pdf_filter};;{all_files_filter}",
            pdf_filter,
        )
        if not selected_path:
            return ""
        if not os.path.splitext(selected_path)[1]:
            selected_path = f"{selected_path}.pdf"
        # Overwrite confirmation is handled by the native/portal dialog.
        return selected_path

    def confirm_pdf_export_replace(self, file_path):
        """Confirm overwriting an existing PDF with translated buttons."""
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(_("Confirm Save As"))
        message_box.setText(
            _("A file named \"{name}\" already exists. Do you want to replace it?")
            .format(name=os.path.basename(file_path))
        )
        replace_button = message_box.addButton(_("Replace"), QMessageBox.ButtonRole.AcceptRole)
        message_box.addButton(_("Cancel"), QMessageBox.ButtonRole.RejectRole)
        message_box.setDefaultButton(replace_button)
        message_box.exec()
        return message_box.clickedButton() == replace_button

    def export_pdf(self, output_path=None):
        """Export the current document to PDF using the markdown preview styles."""
        if not output_path:
            output_path = self.prompt_pdf_export_path()
            if not output_path:
                return False

        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"

        base_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        base_url = QUrl.fromLocalFile(os.path.join(base_dir, ""))
        html_content = self.render_markdown_html(
            self.editor.toPlainText(),
            base_url.toString()
        )
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".html",
                prefix="jottr-pdf-export-",
                delete=False
            )
            temp_file.write(html_content)
            temp_file_path = temp_file.name
        except OSError as e:
            QMessageBox.critical(
                self,
                _("Error"),
                _("Could not export PDF: {error}").format(error=str(e))
            )
            return False
        finally:
            if temp_file:
                temp_file.close()

        global QWebEnginePage
        if QWebEnginePage is None:
            from PyQt6.QtWebEngineCore import QWebEnginePage as _QWebEnginePage
            QWebEnginePage = _QWebEnginePage
        page = QWebEnginePage(self)
        self._pdf_export_page = page
        self._pdf_export_html_path = temp_file_path

        def cleanup_export():
            html_path = getattr(self, "_pdf_export_html_path", None)
            self._pdf_export_page = None
            self._pdf_export_html_path = None
            if html_path:
                try:
                    os.remove(html_path)
                except OSError:
                    pass

        def finish_export(file_path, success):
            cleanup_export()
            if success:
                QMessageBox.information(
                    self,
                    _("Export Complete"),
                    _("PDF exported to {path}").format(path=file_path)
                )
            else:
                QMessageBox.critical(
                    self,
                    _("Error"),
                    _("Could not export PDF: {error}").format(error=file_path)
                )

        def print_when_ready(_result=True):
            page_layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(10.0, 10.0, 10.0, 10.0),
                QPageLayout.Unit.Millimeter
            )
            page.printToPdf(output_path, page_layout)

        def prepare_loaded_page(success):
            if not success:
                cleanup_export()
                QMessageBox.critical(self, _("Error"), _("Could not prepare PDF export."))
                return

            page.runJavaScript(
                """
                (async function () {
                    try {
                        if (window.MathJax && window.MathJax.typesetPromise) {
                            var mathNodes = Array.prototype.slice.call(
                                document.querySelectorAll('.math-inline, .math-block')
                            );
                            if (mathNodes.length) {
                                await window.MathJax.typesetPromise(mathNodes);
                            }
                        }
                        await new Promise(function (resolve) {
                            requestAnimationFrame(function () {
                                requestAnimationFrame(resolve);
                            });
                        });
                        return true;
                    } catch (error) {
                        console.error('PDF export render failed', error);
                        return false;
                    }
                })();
                """,
                print_when_ready
            )

        page.pdfPrintingFinished.connect(finish_export)
        page.loadFinished.connect(prepare_loaded_page)
        page.load(QUrl.fromLocalFile(temp_file_path))
        return True

    def open_file(self):
        file_name, _selected_filter = get_open_file_name(
            self,
            _("Open File"),
            "",
            _("Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*)")
        )
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as file:
                content = file.read()
            self.editor.setPlainText(content)
            self.current_file = file_name
            self.editor.document().setModified(False)
            self.changes_pending = False
            self.load_swap_file(content)
            if self.is_markdown_file(file_name):
                self.set_markdown_preview_visible(True)
            
            # Update tab title to show file name
            if self.main_window and hasattr(self.main_window, 'tab_widget'):
                current_index = self.main_window.tab_widget.indexOf(self)
                if current_index >= 0:
                    # Use base name of file for tab title
                    file_name = os.path.basename(file_name)
                    self.main_window.tab_widget.setTabText(current_index, file_name)
            
    def update_snippet_list(self):
        """Update snippet list and completer"""
        if hasattr(self, 'snippet_list'):
            self.snippet_list.clear()
            for title in self.snippet_manager.get_snippets():
                self.snippet_list.addItem(title)
            self.update_completer_model()
            
    def insert_snippet(self, item):
        text = self.snippet_manager.get_snippet(item.text())
        if text:
            self.editor.insertPlainText(text)
            
    def show_context_menu(self, pos):
        """Show context menu (Kate/KTextEditor-style placement).

        Mouse: keep an existing selection; otherwise only move the caret to the
        click. Do not auto-select the word under the cursor.

        customContextMenuRequested / cursorForPosition use viewport coordinates;
        map via the viewport so editor stylesheet padding does not shift the menu.
        """
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.editor.setTextCursor(self.editor.cursorForPosition(pos))

        global_pos = self.editor.viewport().mapToGlobal(pos)
        # Create menu with a slight delay to prevent accidental triggers
        QTimer.singleShot(100, lambda: self._show_context_menu_impl(global_pos))

    def _word_at_cursor(self):
        """Return the word under the caret without changing the selection."""
        cursor = self.editor.textCursor()
        block = cursor.block()
        start, end = find_word_bounds(block.text(), cursor.positionInBlock())
        return block.text()[start:end]

    def _add_search_menu(self, menu, text):
        """Add the "Search in..." submenu for the given text."""
        search_menu = menu.addMenu(_("Search in..."))

        # Add regular Google search
        google_action = search_menu.addAction(_("Google"))
        google_url = f"https://www.google.com/search?q={quote(text)}"
        google_action.triggered.connect(lambda checked, url=google_url:
            self.search_in_browser(url))

        # Add Google Scholar search
        scholar_action = search_menu.addAction(_("Google Scholar"))
        scholar_url = f"https://scholar.google.com/scholar?q={quote(text)}"
        scholar_action.triggered.connect(lambda checked, url=scholar_url:
            self.search_in_browser(url))

        # Add Google Maps search
        maps_action = search_menu.addAction(_("Google Maps"))
        maps_url = f"https://www.google.com/maps/search/{quote(text)}"
        maps_action.triggered.connect(lambda checked, url=maps_url:
            self.search_in_browser(url))

        # Add Google News search
        news_action = search_menu.addAction(_("Google News"))
        news_url = f"https://news.google.com/search?q={quote(text)}"
        news_action.triggered.connect(lambda checked, url=news_url:
            self.search_in_browser(url))

        # add google translate search
        translate_action = search_menu.addAction(_("Google Translate"))
        translate_url = f"https://translate.google.com/?sl=auto&tl=en&text={quote(text)}"
        translate_action.triggered.connect(lambda checked, url=translate_url:
            self.search_in_browser(url))

        # Add Google define search
        dictionary_action = search_menu.addAction(_("Google Define"))
        dictionary_url = f"https://www.google.com/search?q=define:{quote(text)}"
        dictionary_action.triggered.connect(lambda checked, url=dictionary_url:
            self.search_in_browser(url))

        # Add separator and Wikipedia search
        search_menu.addSeparator()
        wiki_action = search_menu.addAction(_("Wikipedia"))
        wiki_url = f"https://en.wikipedia.org/w/index.php?search={quote(text)}"
        wiki_action.triggered.connect(lambda checked, url=wiki_url:
            self.search_in_browser(url))

        # Add separator and site-specific (news) searches from settings
        search_sites = self.settings_manager.get_setting('search_sites', {
            'AP News': 'site:apnews.com',
            'Reuters': 'site:reuters.com',
            'BBC News': 'site:bbc.com/news'
        })
        if search_sites:
            search_menu.addSeparator()
        from jottr.settings.search_site import search_site_url
        for name, site in search_sites.items():
            action = search_menu.addAction(name)
            search_url = search_site_url(text, site)
            action.triggered.connect(lambda checked, url=search_url:
                self.search_in_browser(url))

    def _add_formatting_menu(self, menu, has_inline_target):
        """Add the Formatting submenu (quotes and common Markdown)."""
        formatting_menu = menu.addMenu(_("Formatting"))
        editor = self.editor

        # Inline formats need a selection or a word under the caret
        inline_actions = [
            (_("Bold"), lambda: apply_wrap(editor, "**")),
            (_("Italic"), lambda: apply_wrap(editor, "*")),
            (_("Strikethrough"), lambda: apply_wrap(editor, "~~")),
            (_("Inline Code"), lambda: apply_wrap(editor, "`")),
            (_("Link"), lambda: apply_link(editor)),
            (_("Wrap in Quotes"), lambda: apply_wrap_in_quotes(editor)),
        ]
        for label, callback in inline_actions:
            formatting_menu.addAction(label, callback).setEnabled(has_inline_target)
        formatting_menu.addSeparator()

        # Line formats act on the selected lines or the current line
        for level in (1, 2, 3):
            formatting_menu.addAction(
                _("Heading {level}").format(level=level),
                lambda level=level: apply_heading(editor, level),
            )
        formatting_menu.addSeparator()
        formatting_menu.addAction(_("Bulleted List"), lambda: apply_line_prefix(editor, "- "))
        formatting_menu.addAction(_("Numbered List"), lambda: apply_numbered_list(editor))
        formatting_menu.addAction(_("Task List"), lambda: apply_line_prefix(editor, "- [ ] "))
        formatting_menu.addAction(_("Blockquote"), lambda: apply_line_prefix(editor, "> "))
        formatting_menu.addAction(_("Code Block"), lambda: apply_code_block(editor))

    def _add_spelling_actions(self, menu, word):
        """Add spell-check actions for a single misspelled word."""
        if not word or ' ' in word or not self.highlighter.spell_check_enabled:
            return False
        if self.highlighter.check_word(word):
            return False

        added = False
        suggestions = self.highlighter.suggest(word)[:7]
        if suggestions:
            menu.addAction(_("Spelling Suggestions:")).setEnabled(False)
            for suggestion in suggestions:
                action = menu.addAction(suggestion)
                action.triggered.connect(lambda checked, replacement=suggestion:
                    self.replace_word(replacement))
            menu.addSeparator()
            added = True

        if not self.highlighter.word_in_user_dictionary(word):
            add_action = menu.addAction(_("Add to Dictionary"))
            add_action.triggered.connect(lambda: self.add_to_dictionary(word))
            menu.addSeparator()
            added = True
        return added

    def _show_context_menu_impl(self, global_pos):
        """Implementation of context menu display.

        global_pos is already in global screen coordinates (from the viewport).
        """
        menu = QMenu(self)

        # Get selected text (only real user selections; we never auto-select)
        selected_text = self.editor.textCursor().selectedText()
        # Like Kate: without a selection, act on the word under the caret
        target_text = selected_text or self._word_at_cursor()

        if target_text:
            self._add_search_menu(menu, target_text)
            menu.addSeparator()
        # Spell-check for a single word (skips multi-word selections)
        self._add_spelling_actions(menu, target_text)
        if target_text:
            menu.addAction(_("Save as Snippet"), lambda: self.save_snippet(target_text))
            menu.addSeparator()

        # Cut/Copy/Paste actions (Kate: cut/copy need selection; paste needs clipboard)
        has_selection = bool(selected_text)
        cut_action = menu.addAction(_("Cut"), self.editor.cut)
        cut_action.setEnabled(has_selection)
        copy_action = menu.addAction(_("Copy"), self.editor.copy)
        copy_action.setEnabled(has_selection)
        paste_action = menu.addAction(_("Paste"), self.editor.paste)
        paste_action.setEnabled(self.editor.canPaste())
        select_all_action = menu.addAction(_("Select All"), self.editor.selectAll)
        select_all_action.setEnabled(not self.editor.document().isEmpty())
        menu.addSeparator()

        # Kate Selection ▸ Capitalization (context menu: selection only, like Cut/Copy)
        capitalization_menu = menu.addMenu(_("Capitalization"))
        capitalization_menu.menuAction().setEnabled(has_selection)
        capitalization_menu.addAction(_("Uppercase"), lambda: apply_uppercase(self.editor))
        capitalization_menu.addAction(_("Lowercase"), lambda: apply_lowercase(self.editor))
        capitalization_menu.addAction(_("Capitalize"), lambda: apply_capitalize(self.editor))

        self._add_formatting_menu(menu, has_inline_target=bool(target_text))
        menu.addSeparator()

        # Top-left of the menu at the click (Kate: mapToGlobal(e->pos()))
        menu.exec(global_pos)

    def add_to_dictionary(self, word):
        """Add word to user dictionary via the shared highlighter."""
        self.highlighter.add_to_dictionary(word)

    def save_snippet(self, text):
        """Save selected text as a snippet"""
        title, ok = QInputDialog.getText(self, _("Save Snippet"), _("Enter snippet title:"))
        if ok and title:
            self.snippet_manager.add_snippet(title, text)
            self.update_snippet_list()
            
    def new_snippet(self):
        """Create a snippet from the Snippets panel, prefilled with any selection."""
        dialog = SnippetEditorDialog("", self.editor.textCursor().selectedText().replace(' ', '\n'), self)
        dialog.setWindowTitle(_("New Snippet"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        title = data['title'].strip()
        if not title:
            return
        if self.snippet_manager.get_snippet(title) is not None:
            reply = QMessageBox.question(
                self,
                _("New Snippet"),
                _("A snippet named \"{title}\" already exists. Replace it?").format(title=title),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.snippet_manager.add_snippet(title, data['content'])
        self.update_snippet_list()

    def edit_current_snippet(self):
        current_item = self.snippet_list.currentItem()
        if not current_item:
            return
            
        old_title = current_item.text()
        content = self.snippet_manager.get_snippet(old_title)
        
        dialog = SnippetEditorDialog(old_title, content, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            # Delete old snippet if title changed
            if data['title'] != old_title:
                self.snippet_manager.delete_snippet(old_title)
            self.snippet_manager.add_snippet(data['title'], data['content'])
            self.update_snippet_list()
    
    def delete_current_snippet(self):
        current_item = self.snippet_list.currentItem()
        if current_item:
            self.snippet_manager.delete_snippet(current_item.text())
            self.update_snippet_list()

    def show_snippet_context_menu(self, position):
        menu = QMenu()
        menu.addAction(_("New Snippet"), self.new_snippet)
        # Only offer edit/delete when the click landed on a snippet
        current_item = self.snippet_list.itemAt(position)

        if current_item:
            self.snippet_list.setCurrentItem(current_item)
            menu.addSeparator()
            menu.addAction(_("Edit Snippet"), self.edit_current_snippet)
            menu.addAction(_("Delete Snippet"), self.delete_current_snippet)
        # customContextMenuRequested is viewport-relative; list has stylesheet padding
        menu.exec(self.snippet_list.viewport().mapToGlobal(position))

    def update_completer_model(self):
        """Update completer with current snippets"""
        if hasattr(self, 'completer') and self.completer:
            model = QStringListModel()
            model.setStringList(self.snippet_manager.get_snippets())
            self.completer.setModel(model)

    def insert_completion(self, completion):
        """Insert the selected snippet"""
        if not isinstance(completion, str):
            return
            
        cursor = self.editor.textCursor()
        
        # Delete the partially typed word
        chars_to_delete = len(self.completer.completionPrefix())
        cursor.movePosition(
            QTextCursor.MoveOperation.Left,
            QTextCursor.MoveMode.KeepAnchor,
            chars_to_delete,
        )
        cursor.removeSelectedText()
        
        # Insert the snippet content
        snippet_content = self.snippet_manager.get_snippet(completion)
        if snippet_content:
            cursor.insertText(snippet_content)
    
    def update_font(self, font):
        """Update editor font"""
        self.current_font = QFont(font)  # Store a copy of the font
        self.current_font.setWeight(QFont.Weight.Normal)  # Force Regular weight
        
        # Update font for the editor
        self.editor.setFont(self.current_font)
        self.editor.document().setDefaultFont(self.current_font)
        
        ThemeManager.apply_theme(
            self.editor,
            self.current_theme,
            self.current_font
        )
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(self.current_theme)
        self.editor.update_line_number_area_width()
        self.editor.update_line_number_area()
        self.update_markdown_preview()

    def apply_ui_font(self, font):
        """Apply Main UI Font to snippets/browser chrome, not the writing surface."""
        ui_font = QFont(font)
        for attr in ("snippet_widget", "browser_widget", "find_toolbar"):
            root = getattr(self, attr, None)
            if root is None:
                continue
            root.setFont(ui_font)
            for child in root.findChildren(QWidget):
                child.setFont(ui_font)

    def get_language_direction(self):
        language = self.settings_manager.get_setting("language", "en_US")
        return (
            Qt.LayoutDirection.RightToLeft
            if is_rtl_language(language)
            else Qt.LayoutDirection.LeftToRight
        )

    def apply_language_direction(self):
        """Apply UI direction while letting document text choose direction per block."""
        direction = self.get_language_direction()
        self.setLayoutDirection(direction)
        if hasattr(self, "editor"):
            self.editor.setLayoutDirection(direction)
            text_option = QTextOption(self.editor.document().defaultTextOption())
            text_option.setTextDirection(Qt.LayoutDirection.LayoutDirectionAuto)
            self.editor.document().setDefaultTextOption(text_option)
            self.editor.update_line_number_area_width()
            self.editor.update_line_number_area()
        if hasattr(self, "markdown_preview"):
            self.markdown_preview.setLayoutDirection(direction)
        self.update_markdown_preview()

    def apply_theme(self, theme_name):
        """Apply theme while preserving font properties"""
        self.current_theme = theme_name
        ThemeManager.apply_theme(self.editor, theme_name)

        # After applying theme, reapply font to ensure properties are preserved.
        # update_font already rehighlights with the new theme, so the final
        # set_theme below only refreshes formats without a second full pass.
        if hasattr(self, 'current_font'):
            self.update_font(self.current_font)
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(
                theme_name,
                rehighlight=not hasattr(self, 'current_font'),
            )
        self.apply_workspace_style()
        self.update_markdown_preview()

    def set_line_numbers_visible(self, visible):
        """Show or hide editor line numbers."""
        self.editor.set_line_numbers_visible(visible)

    def animations_enabled(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return False
        return bool(self.settings_manager.get_setting("enable_animations", True))

    def animate_widget_visibility(self, widget, visible, duration=260, fade=True):
        widget.setProperty("target_visible", visible)
        if not self.animations_enabled():
            widget.setGraphicsEffect(None)
            original_width = widget.property("animation_original_max_width")
            if original_width is not None:
                widget.setMaximumWidth(int(original_width))
            widget.setVisible(visible)
            return None

        current_animation = self.ui_animations.pop(widget, None)
        if current_animation:
            current_animation.stop()

        original_width = widget.property("animation_original_max_width")
        if original_width is None or int(original_width) == 0:
            original_width = widget.maximumWidth()
            widget.setProperty("animation_original_max_width", original_width)

        target_width = max(widget.width(), widget.sizeHint().width(), 260)
        if not visible and widget.width() > 0:
            target_width = widget.width()

        group = QParallelAnimationGroup(self)

        # QWebEngineView (and parents that host it) must not use graphics opacity
        # effects — they force a paint proxy that blanks/flickers the window.
        effect = None
        if fade:
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)

            opacity_animation = QPropertyAnimation(effect, b"opacity", group)
            opacity_animation.setDuration(duration)
            opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            opacity_animation.setStartValue(0.0 if visible else 1.0)
            opacity_animation.setEndValue(1.0 if visible else 0.0)
            group.addAnimation(opacity_animation)
        else:
            widget.setGraphicsEffect(None)

        width_animation = QPropertyAnimation(widget, b"maximumWidth", group)
        width_animation.setDuration(duration)
        width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        width_animation.setStartValue(0 if visible else target_width)
        width_animation.setEndValue(target_width if visible else 0)
        group.addAnimation(width_animation)
        self.ui_animations[widget] = group

        if visible:
            widget.setMaximumWidth(0)
            if effect is not None:
                effect.setOpacity(0.0)
            widget.setVisible(True)
        else:
            widget.setMaximumWidth(target_width)
            if effect is not None:
                effect.setOpacity(1.0)

        def finish_animation():
            if not visible:
                widget.setVisible(False)
            widget.setMaximumWidth(int(original_width))
            widget.setGraphicsEffect(None)
            self.ui_animations.pop(widget, None)

        group.finished.connect(finish_animation)
        group.start()
        return group

    def intended_widget_visibility(self, widget):
        target = widget.property("target_visible")
        if target is None:
            return widget.isVisible()
        return bool(target)

    def handle_modification(self, modified):
        """Update tab title to show modification status"""
        if self.main_window and hasattr(self.main_window, 'tab_widget'):
            current_index = self.main_window.tab_widget.indexOf(self)
            if current_index >= 0:
                current_text = self.main_window.tab_widget.tabText(current_index)
                if modified and not current_text.endswith('*'):
                    self.main_window.tab_widget.setTabText(current_index, current_text + '*')
                elif not modified and current_text.endswith('*'):
                    self.main_window.tab_widget.setTabText(current_index, current_text[:-1])

    def update_status(self):
        """Update word and character count"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return
        
        text = self.editor.toPlainText()
        
        # Update word count (split by whitespace and filter empty strings)
        words = len([word for word in text.split() if word.strip()])
        chars = len(text)
        
        # Update status bar
        self.main_window.statusBar.showMessage(_("Words: {words} | Characters: {chars}").format(words=words, chars=chars))

    def schedule_document_language_refresh(self):
        """Debounce auto language detection while typing."""
        timer = getattr(self, "_document_language_timer", None)
        if timer is not None:
            timer.start()

    def refresh_document_language_detection(self):
        """Refresh Auto-detect dictionaries from the current document text."""
        highlighter = getattr(self, "highlighter", None)
        if highlighter is None:
            return
        highlighter.refresh_detected_language(rehighlight=True)
        if self.main_window and hasattr(self.main_window, "update_document_language_status"):
            self.main_window.update_document_language_status()

    def handle_text_changed(self):
        """Handle text changes for autocompletion"""
        if self.suggestion_tooltip:
            self.suggestion_tooltip.hide()
            self.suggestion_tooltip.deleteLater()
            self.suggestion_tooltip = None
            
        cursor = self.editor.textCursor()
        current_line = cursor.block().text()
        current_position = cursor.positionInBlock()
        
        # Find the word being typed (keep contractions intact)
        word_start = current_position
        while word_start > 0 and (
            current_line[word_start - 1].isalnum()
            or current_line[word_start - 1] in "_-'’"
        ):
            word_start -= 1

        current_word = current_line[word_start:current_position]
        
        if len(current_word) >= 2:  # Only show suggestions after 2 characters
            suggestions = []
            
            # Get snippet suggestions
            if hasattr(self, 'snippet_manager'):
                for title in self.snippet_manager.get_snippets():
                    if title.lower().startswith(current_word.lower()):
                        suggestions.append(('snippet', title))

            # Get dictionary suggestions
            user_dict = self.settings_manager.get_setting('user_dictionary', [])
            for word in user_dict:
                if word.lower().startswith(current_word.lower()) and word.lower() != current_word.lower():
                    suggestions.append(('word', word))
            
            if suggestions:
                self.show_suggestion_tooltip(suggestions, cursor)

    def save_pane_states(self):
        """Save pane visibility and sizes"""
        states = {
            'snippets_visible': self.intended_widget_visibility(self.snippet_widget),
            'markdown_preview_visible': self.markdown_preview_visible if hasattr(self, 'markdown_preview') else False,
            'markdown_sizes': self.markdown_splitter.sizes() if hasattr(self, 'markdown_splitter') else [600, 600],
            'sizes': self.splitter.sizes()
        }
        self.settings_manager.save_setting('pane_states', states)

    def set_main_window(self, main_window):
        """Set reference to main window and initialize session state"""
        self.main_window = main_window
        # # Update session state to include this tab
        # current_tabs = self.main_window.get_open_tab_ids()
        # # if self.recovery_id not in current_tabs:
        # #     current_tabs.append(self.recovery_id)
        # #     self.settings_manager.save_session_state(current_tabs)

    # def cleanup_session_files(self):
    #     """Clean up session files for this tab"""
    #     try:
    #         if os.path.exists(self.session_path):
    #             os.remove(self.session_path)
    #         if os.path.exists(self.meta_path):
    #             os.remove(self.meta_path)
    #     except Exception as e:
    #         print(f"Failed to cleanup session files: {str(e)}")

    def keyPressEvent(self, event):
        """Handle key events"""
        super().keyPressEvent(event)  # Just pass through to parent

    def show_suggestion_tooltip(self, suggestions, cursor):
        """Show suggestions in a tooltip-like widget"""
        self.hide_suggestions()
        self.current_suggestions = suggestions
        self.selected_suggestion_index = -1
        
        # Create tooltip widget
        self.suggestion_tooltip = QWidget(self.editor, Qt.WindowType.ToolTip)
        layout = QVBoxLayout(self.suggestion_tooltip)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Style the tooltip
        self.suggestion_tooltip.setStyleSheet("""
            QWidget {
                background-color: palette(window);
                border: 0.5px solid palette(mid);
                border-radius: 0px;
            }
            QLabel {
                padding: 2px 8px;
                color: palette(text);
                border-radius: 0px;
                margin: 1px;
                font-family: "Courier New", "DejaVu Sans Mono", monospace;
            }
        """)
        
        # Add suggestions (limited to 7)
        for i, (suggestion_type, text) in enumerate(suggestions[:7]):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(1)
            
            if suggestion_type == 'snippet':
                # For snippets, show content directly
                content = self.snippet_manager.get_snippet(text)
                if content:
                    # Limit preview to first line or 50 chars
                    preview = content.split('\n')[0][:50]
                    if len(preview) < len(content):
                        preview += "..."
                    label = QLabel(preview)
            else:
                # For words, just show the word
                label = QLabel(text)
            
            container_layout.addWidget(label)
            
            # Make container clickable
            container.mousePressEvent = lambda _, t=text: self.apply_suggestion(t)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            
            layout.addWidget(container)
        
        # Position below the cursor. cursorRect is in viewport coordinates, and
        # the editor stylesheet applies padding, so map via the viewport.
        self.suggestion_tooltip.adjustSize()
        rect = self.editor.cursorRect(cursor)
        pos = self.editor.viewport().mapToGlobal(rect.bottomLeft())
        pos.setY(pos.y() + 5)
        self.suggestion_tooltip.move(pos)
        self.suggestion_tooltip.show()
        self.suggestion_tooltip.raise_()

    def select_next_suggestion(self):
        """Select next suggestion in the list"""
        if not self.current_suggestions:
            return
            
        self.selected_suggestion_index = (self.selected_suggestion_index + 1) % len(self.current_suggestions)
        self.update_suggestion_highlighting()

    def select_previous_suggestion(self):
        """Select previous suggestion in the list"""
        if not self.current_suggestions:
            return
            
        self.selected_suggestion_index = (self.selected_suggestion_index - 1) % len(self.current_suggestions)
        self.update_suggestion_highlighting()

    def update_suggestion_highlighting(self):
        """Update the visual highlighting of selected suggestion"""
        if not self.suggestion_tooltip:
            return
            
        layout = self.suggestion_tooltip.layout()
        for i in range(layout.count()):
            container = layout.itemAt(i).widget()
            if i == self.selected_suggestion_index:
                container.setStyleSheet("""
                    background-color: palette(highlight);
                    border-radius: 0px;
                    QLabel { color: palette(highlighted-text); }
                """)
            else:
                container.setStyleSheet("")

    def hide_suggestions(self):
        """Hide suggestion tooltip"""
        if self.suggestion_tooltip:
            self.suggestion_tooltip.hide()
            self.suggestion_tooltip.deleteLater()
            self.suggestion_tooltip = None
        self.selected_suggestion_index = -1
        self.current_suggestions = []

    def apply_suggestion(self, suggestion):
        """Apply the clicked suggestion"""
        if not self.suggestion_tooltip:
            return
            
        cursor = self.editor.textCursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.positionInBlock()
        
        # Replace from start of current word (including contractions) to cursor
        if pos > 0 and (text[pos - 1].isalnum() or text[pos - 1] in "_'’"):
            start, _ = find_word_bounds(text, pos - 1)
        else:
            start = pos
            
        # Find if this is a snippet or word suggestion
        is_snippet = False
        for suggestion_type, title in self.current_suggestions:
            if title == suggestion:
                is_snippet = (suggestion_type == 'snippet')
                break
        
        # Replace the current word
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            start,
        )
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            pos - start,
        )
        
        if is_snippet:
            # Get and insert snippet content
            content = self.snippet_manager.get_snippet(suggestion)
            if content:
                cursor.insertText(content)
        else:
            # Insert the word suggestion directly
            cursor.insertText(suggestion)
        
        # Hide tooltip
        self.hide_suggestions()
        
        # Set focus back to editor
        self.editor.setFocus()

    def replace_word(self, new_word):
        """Replace the word under cursor with new word"""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()

        # Get the current position and text
        block = cursor.block()
        text = block.text()
        pos = cursor.positionInBlock()

        # Keep contractions like "shouldn't" intact when replacing
        start, end = find_word_bounds(text, pos)

        # Select and replace the word
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(new_word)

        cursor.endEditBlock()

    def eventFilter(self, obj, event):
        """Filter events for focus mode"""
        if hasattr(self, 'markdown_preview') and obj == self.markdown_preview:
            if event.type() in (QEvent.Type.Wheel, QEvent.Type.KeyRelease, QEvent.Type.MouseButtonRelease):
                self.preview_user_scroll_until = time.time() + 1.0
                self.schedule_editor_scroll_sync()

        if obj == self.editor and event.type() == QEvent.Type.KeyPress:
            self.markdown_typing_active_until = time.time() + 0.75
            # Handle Escape key
            if event.key() == Qt.Key.Key_Escape and hasattr(self, 'focus_mode') and self.focus_mode:
                self.disable_focus_mode()
                event.accept()
                return True
            # Handle Ctrl+Shift+D (or Cmd+Shift+D on Mac)
            elif (event.key() == Qt.Key.Key_D and 
                  event.modifiers() & Qt.KeyboardModifier.ShiftModifier and 
                  event.modifiers() & (Qt.KeyboardModifier.ControlModifier if sys.platform != 'darwin' else Qt.KeyboardModifier.MetaModifier)):
                if self.focus_mode:
                    self.disable_focus_mode()
                else:
                    self.toggle_focus_mode()
                event.accept()
                return True
        return super().eventFilter(obj, event)  # Let other events pass through

