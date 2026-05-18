import os
import sys

# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTextEdit, QListWidget, QInputDialog, QMenu, QFileDialog, QDialog,
                            QToolBar, QCompleter, QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel, QToolTip)
from PyQt6.QtCore import Qt, QUrl, QTimer, QStringListModel, QEvent, QSize, QRect, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (QAction, QShortcut, QTextCharFormat, QSyntaxHighlighter, QIcon, QFont, QKeySequence,
                        QPainter, QPen, QColor, QFontMetrics, QTextDocument, QTextCursor)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from urllib.parse import quote
from snippet_editor_dialog import SnippetEditorDialog
from rss_reader import RSSReader
import json
import time
from theme_manager import ThemeManager
import hashlib
import html
import re
import base64
import mimetypes
import tempfile

try:
    import markdown as markdown_lib
    MARKDOWN_LIB_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    markdown_lib = None
    MARKDOWN_LIB_AVAILABLE = False

# Try enchant first, fallback to pyspellchecker
try:
    from spellchecker import SpellChecker
except (ImportError, ModuleNotFoundError):
    SpellChecker = None

try:
    from enchant import Dict, DictNotFoundError
    USE_ENCHANT = True
except (ImportError, ModuleNotFoundError) as e:
    print("Enchant not available, falling back to pyspellchecker:", str(e))
    USE_ENCHANT = False

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.spell_check_enabled = True
        self.USE_ENCHANT = USE_ENCHANT  # Store the global flag
        self.markdown_formats = {}
        self.set_theme(
            self.settings_manager.get_theme(),
            self.settings_manager.get_custom_themes(),
            rehighlight=False
        )
        
        try:
            if self.USE_ENCHANT:
                self.spell = Dict("en_US")
                print("Using Enchant for spell checking")
            else:
                self.spell = SpellChecker()
                print("Using pyspellchecker for spell checking")
        except Exception as e:
            print(f"Spell checker initialization error: {str(e)}, falling back to pyspellchecker")
            self.spell = SpellChecker()
            self.USE_ENCHANT = False

    def set_theme(self, theme_name=None, custom_themes=None, rehighlight=True):
        """Refresh Markdown syntax colors from the active editor theme."""
        theme = ThemeManager.get_theme(
            theme_name or self.settings_manager.get_theme(),
            custom_themes if custom_themes is not None else self.settings_manager.get_custom_themes()
        )
        self.markdown_formats = self.build_markdown_formats(theme)
        if rehighlight:
            self.rehighlight()

    def build_markdown_formats(self, theme):
        syntax = theme["syntax"]
        editor = theme["editor"]

        def make_format(color, bold=False, italic=False, monospace=False, background=None):
            text_format = QTextCharFormat()
            text_format.setForeground(QColor(color))
            if background:
                text_format.setBackground(QColor(background))
            if bold:
                text_format.setFontWeight(QFont.Weight.Bold)
            if italic:
                text_format.setFontItalic(True)
            if monospace:
                text_format.setFontFamily("Monospace")
            return text_format

        return {
            "heading": make_format(syntax["keyword"], bold=True),
            "marker": make_format(syntax["comment"], bold=True),
            "emphasis": make_format(syntax["type"], italic=True),
            "strong": make_format(syntax["function"], bold=True),
            "code": make_format(syntax.get("constant", syntax["number"]), monospace=True, background=editor["current_line"]),
            "link": make_format(syntax["function"]),
            "url": make_format(syntax["string"]),
            "quote": make_format(syntax["comment"], italic=True),
            "list": make_format(syntax["keyword"], bold=True),
            "table": make_format(syntax["type"]),
            "html": make_format(syntax["type"]),
            "rule": make_format(syntax["comment"])
        }

    def check_word(self, word):
        """Check if a word is spelled correctly"""
        if not self.spell_check_enabled:
            return True
            
        if self.USE_ENCHANT:
            return self.spell.check(word)
        else:
            # pyspellchecker considers unknown words misspelled
            return word.lower() in self.spell

    def suggest(self, word):
        """Get suggestions for a word"""
        if not self.spell_check_enabled:
            return []
            
        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        # Add matching words from user dictionary first
        suggestions = [dict_word for dict_word in user_dict 
                      if dict_word.lower().startswith(word.lower())]
        
        # Only get spell checker suggestions for Latin words
        if self.is_latin_word(word):
            try:
                if self.USE_ENCHANT:
                    spell_suggestions = self.spell.suggest(word)
                else:
                    spell_suggestions = self.spell.candidates(word)
                
                if spell_suggestions:
                    # Remove the word itself from suggestions
                    spell_suggestions = [s for s in spell_suggestions 
                                      if s.lower() != word.lower()]
                    suggestions.extend(spell_suggestions)
            except UnicodeEncodeError:
                pass
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(suggestions))

    def add_to_dictionary(self, word):
        """Add word to user dictionary"""
        if self.USE_ENCHANT:
            # Enchant spell checker implementation
            self.spell.add(word)
        else:
            # PySpellChecker implementation
            self.spell.word_frequency.add(word)
            # Force a recheck of the document
            self.highlighter.rehighlight()
        
        # Add to user dictionary in settings
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)

    def highlight_markdown(self, text):
        skip_ranges = []
        self.setCurrentBlockState(0)

        fence_match = re.match(r'^\s*(`{3,}|~{3,})', text)
        if self.previousBlockState() == 1:
            self.setFormat(0, len(text), self.markdown_formats["code"])
            skip_ranges.append((0, len(text)))
            if not fence_match:
                self.setCurrentBlockState(1)
            return skip_ranges

        if fence_match:
            self.setFormat(0, len(text), self.markdown_formats["code"])
            self.setCurrentBlockState(1)
            skip_ranges.append((0, len(text)))
            return skip_ranges

        heading_match = re.match(r'^(#{1,6})(\s+.*)$', text)
        if heading_match:
            self.setFormat(heading_match.start(1), len(heading_match.group(1)), self.markdown_formats["marker"])
            self.setFormat(heading_match.start(2), len(heading_match.group(2)), self.markdown_formats["heading"])

        quote_match = re.match(r'^(\s*>+)(.*)$', text)
        if quote_match:
            self.setFormat(quote_match.start(1), len(quote_match.group(1)), self.markdown_formats["marker"])
            self.setFormat(quote_match.start(2), len(quote_match.group(2)), self.markdown_formats["quote"])

        list_match = re.match(r'^(\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?)', text)
        if list_match:
            self.setFormat(list_match.start(1), len(list_match.group(1)), self.markdown_formats["list"])

        if re.match(r'^\s*[-*_](?:\s*[-*_]){2,}\s*$', text):
            self.setFormat(0, len(text), self.markdown_formats["rule"])

        if "|" in text and re.search(r'\S\s*\|\s*\S', text):
            for match in re.finditer(r'\|', text):
                self.setFormat(match.start(), 1, self.markdown_formats["table"])

        for match in re.finditer(r'(`+)([^`]+)(\1)', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["code"])
            skip_ranges.append((match.start(), match.end()))

        for match in re.finditer(r'(!?\[)([^\]]+)(\]\()([^)]+)(\))', text):
            self.setFormat(match.start(1), len(match.group(1)), self.markdown_formats["marker"])
            self.setFormat(match.start(2), len(match.group(2)), self.markdown_formats["link"])
            self.setFormat(match.start(3), len(match.group(3)), self.markdown_formats["marker"])
            self.setFormat(match.start(4), len(match.group(4)), self.markdown_formats["url"])
            self.setFormat(match.start(5), len(match.group(5)), self.markdown_formats["marker"])
            skip_ranges.append((match.start(4), match.end(4)))

        for match in re.finditer(r'(\*\*|__)(.+?)\1', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["strong"])

        for match in re.finditer(r'(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["emphasis"])

        for match in re.finditer(r'</?[A-Za-z][^>]*>', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["html"])

        return skip_ranges

    def is_in_ranges(self, index, ranges):
        return any(start <= index < end for start, end in ranges)

    def highlightBlock(self, text):
        skip_ranges = self.highlight_markdown(text)
        if not self.spell_check_enabled:
            return

        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        format = QTextCharFormat()
        format.setUnderlineColor(Qt.GlobalColor.red)
        format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

        # For each word in the text
        for match in re.finditer(r'\b\w+\b', text):
            index = match.start()
            word = match.group(0)
            length = len(word)
            
            # Only spell check Latin words
            if self.is_latin_word(word) and not self.is_in_ranges(index, skip_ranges):
                # Check if word is in user dictionary first
                if word not in user_dict:
                    try:
                        if not self.check_word(word):
                            self.setFormat(index, length, format)
                    except UnicodeEncodeError:
                        pass  # Skip words that can't be encoded

    def is_latin_word(self, word):
        """Check if word contains only Latin characters"""
        try:
            word.encode('latin-1')
            return True
        except UnicodeEncodeError:
            return False

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.completer = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        if parent:
            self.customContextMenuRequested.connect(parent.show_context_menu)

    def setCompleter(self, completer):
        if self.completer:
            self.completer.activated.disconnect()
        
        self.completer = completer
        if self.completer:
            self.completer.setWidget(self)
            self.completer.activated[str].connect(self.insertCompletion)

    def insertCompletion(self, completion):
        """Insert the selected snippet"""
        if not self.completer:
            return
            
        # Get the current cursor
        tc = self.textCursor()
        
        # Delete the partially typed word
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(tc.Left)
        tc.movePosition(tc.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
        
        # Get and insert the full snippet content
        if self.parent_tab:
            snippet_content = self.parent_tab.snippet_manager.get_snippet(completion)
            if snippet_content:
                tc = self.textCursor()
                tc.movePosition(tc.Left, tc.KeepAnchor, len(completion))
                tc.insertText(snippet_content)

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            # Handle keys for autocompletion
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                # Get the current completion
                current = self.completer.currentCompletion()
                if current:
                    # Insert the completion
                    self.insertCompletion(current)
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.completer.popup().hide()
                event.accept()
                return
                
        super().keyPressEvent(event)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CompletingTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.completion_text = ""
        self.completion_start = None
        self.suppress_completion = False
        self.line_numbers_visible = False
        self.line_number_area = LineNumberArea(self)
        self.line_number_area.hide()
        self.document().blockCountChanged.connect(self.update_line_number_area_width)
        self.verticalScrollBar().valueChanged.connect(self.update_line_number_area)
        self.textChanged.connect(self.update_line_number_area)
        
        # Initialize spell checker
        if USE_ENCHANT:
            try:
                self.spell_checker = Dict("en_US")
            except:
                self.spell_checker = SpellChecker()
                print("Fallback to pyspellchecker in CompletingTextEdit")
        else:
            self.spell_checker = SpellChecker()

    def line_number_area_width(self):
        digits = max(2, len(str(max(1, self.document().blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def set_line_numbers_visible(self, visible):
        self.line_numbers_visible = visible
        self.line_number_area.setVisible(visible)
        self.update_line_number_area_width()
        self.update_line_number_area()

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width() if self.line_numbers_visible else 0, 0, 0, 0)

    def update_line_number_area(self):
        if self.line_numbers_visible:
            self.line_number_area.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(245, 245, 245))
        painter.setPen(QColor(120, 120, 120))

        block = self.document().firstBlock()
        layout = self.document().documentLayout()
        viewport_top = self.viewport().rect().top()
        viewport_bottom = self.viewport().rect().bottom()
        scroll_offset = self.verticalScrollBar().value()

        while block.isValid():
            block_rect = layout.blockBoundingRect(block)
            top = int(block_rect.top() - scroll_offset)
            bottom = int(block_rect.bottom() - scroll_offset)

            if bottom >= viewport_top and top <= viewport_bottom:
                number = str(block.blockNumber() + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number
                )

            if top > viewport_bottom:
                break
            block = block.next()

    def keyPressEvent(self, event):
        """Handle key events"""
        # Handle suggestion navigation if parent has suggestions
        if (self.parent_tab and 
            self.parent_tab.suggestion_tooltip and 
            self.parent_tab.current_suggestions):
            
            if event.key() == Qt.Key.Key_Down:
                self.parent_tab.select_next_suggestion()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Up:
                self.parent_tab.select_previous_suggestion()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_tab.selected_suggestion_index >= 0:
                    suggestion_type, text = self.parent_tab.current_suggestions[self.parent_tab.selected_suggestion_index]
                    self.parent_tab.apply_suggestion(text)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Tab:
                # If there's only one suggestion, apply it
                if len(self.parent_tab.current_suggestions) == 1:
                    suggestion_type, text = self.parent_tab.current_suggestions[0]
                    self.parent_tab.apply_suggestion(text)
                # If there are multiple suggestions, cycle through them
                else:
                    self.parent_tab.select_next_suggestion()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.parent_tab.hide_suggestions()
                event.accept()
                return

        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Override paste to always use plain text"""
        if source.hasText():
            cursor = self.textCursor()
            cursor.insertText(source.text())
        
    def paintEvent(self, event):
        super().paintEvent(event)
        # Remove old completion painting code

    def check_for_completion(self):
        """Check current word against both user dictionary and snippets"""
        # This method is now handled by EditorTab's handle_text_changed
        pass

    def show_suggestions_menu(self, suggestions, start_pos):
        """Show popup menu with suggestions"""
        # This method is now replaced by EditorTab's show_suggestion_tooltip
        pass

    def apply_suggestion(self, suggestion):
        """Apply the clicked suggestion"""
        if not self.suggestion_tooltip:
            return
            
        cursor = self.editor.textCursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.positionInBlock()
        
        # Find start of current word
        start = pos
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '_'):
            start -= 1
        
        # Find if this is a snippet or word suggestion
        is_snippet = False
        for suggestion_type, title in self.current_suggestions:
            if title == suggestion:
                is_snippet = (suggestion_type == 'snippet')
                break
        
        # Replace the current word
        cursor.movePosition(cursor.StartOfBlock)
        cursor.movePosition(cursor.Right, cursor.MoveAnchor, start)
        cursor.movePosition(cursor.Right, cursor.KeepAnchor, pos - start)
        
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

class MarkdownPreviewPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(f"Markdown preview JS: {message} ({source_id}:{line_number})")

class EditorTab(QWidget):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.current_font = self.settings_manager.get_font()
        self.current_theme = self.settings_manager.get_theme()
        self.web_view = None  # Initialize to None
        self.main_window = None  # Initialize main_window to None
        self.markdown_preview_visible = False
        self.preview_scroll_pending = False
        self.editor_scroll_pending = False
        self.syncing_markdown_scroll = False
        self.preview_scroll_timer = None
        self.markdown_render_timer = None
        self.editor_scroll_animation = None
        self.pending_preview_source_line = None
        self.ignore_preview_scroll_until = 0
        self.preview_user_scroll_until = 0
        self.markdown_preview_file = os.path.join(
            tempfile.gettempdir(),
            f'jottr_markdown_preview_{id(self)}.html'
        )
        self._mermaid_script_content = None
        
        # Add USE_ENCHANT as instance attribute
        self.USE_ENCHANT = USE_ENCHANT  # Use the module-level variable
        
        # Initialize spell checker
        if self.USE_ENCHANT:
            try:
                self.spell_checker = Dict("en_US")
            except:
                self.USE_ENCHANT = False  # Fall back if enchant fails
                self.spell_checker = SpellChecker()
                print("Fallback to pyspellchecker in EditorTab")
        else:
            self.spell_checker = SpellChecker()
        
        # Setup UI components
        self.setup_ui()
        
        # Setup autosave after UI is ready
        self.last_save_time = time.time()
        self.changes_pending = False
        
        # Start periodic backup timer
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.force_save)
        self.backup_timer.start(5000)  # Backup every 5 seconds

        self.preview_scroll_timer = QTimer(self)
        self.preview_scroll_timer.timeout.connect(self.schedule_editor_scroll_sync)
        self.preview_scroll_timer.setInterval(250)

        self.markdown_render_timer = QTimer(self)
        self.markdown_render_timer.setSingleShot(True)
        self.markdown_render_timer.setInterval(180)
        self.markdown_render_timer.timeout.connect(self.update_markdown_preview)
        
        # Apply theme
        ThemeManager.apply_theme(
            self.editor,
            self.current_theme,
            self.settings_manager.get_custom_themes()
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
        self.editor.textChanged.connect(self.schedule_markdown_preview_update)
        self.editor.cursorPositionChanged.connect(self.schedule_markdown_cursor_sync)
        self.editor.verticalScrollBar().valueChanged.connect(self.schedule_markdown_scroll_sync)

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
        editor_pane_layout.setContentsMargins(12, 0, 12, 10)
        editor_pane_layout.setSpacing(0)

        self.markdown_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.markdown_splitter.setObjectName("markdownSplitter")
        self.markdown_splitter.addWidget(self.editor)

        self.markdown_preview = QWebEngineView()
        self.markdown_preview.setObjectName("markdownPreview")
        self.markdown_preview.setPage(MarkdownPreviewPage(self.markdown_preview))
        preview_settings = self.markdown_preview.settings()
        preview_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        preview_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        preview_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.markdown_preview.setVisible(False)
        self.markdown_preview.installEventFilter(self)
        self.markdown_preview.loadFinished.connect(self.render_markdown_preview_scripts)
        self.markdown_splitter.addWidget(self.markdown_preview)
        self.markdown_splitter.setSizes([600, 600])
        self.markdown_splitter.splitterMoved.connect(self.save_pane_states)
        editor_pane_layout.addWidget(self.markdown_splitter)
        
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
        
        snippet_title = QLabel("Snippets")
        snippet_title.setObjectName("panelTitle")
        header_layout.addWidget(snippet_title)
        header_layout.addStretch()
        
        snippet_close = QPushButton("×")
        snippet_close.setObjectName("panelCloseButton")
        snippet_close.setFixedSize(24, 24)
        snippet_close.setToolTip("Close snippets")
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
            'browser_visible': False,
            'markdown_preview_visible': False,
            'markdown_sizes': [600, 600],
            'sizes': [700, 300, 300]
        })
        
        # Apply visibility
        self.snippet_widget.setVisible(states.get('snippets_visible', False))
        self.browser_widget.setVisible(states.get('browser_visible', False))
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
        self.find_input.setPlaceholderText("Find")
        self.find_input.textChanged.connect(self.find_text)
        self.find_input.setFixedHeight(28)
        find_layout.addWidget(self.find_input)
        
        # Replace input
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
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
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("All")  # Shortened text
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
        theme = ThemeManager.get_theme(
            self.current_theme,
            self.settings_manager.get_custom_themes()
        )
        self.setStyleSheet(ThemeManager.build_workspace_stylesheet(theme))
        
    def on_text_changed(self):
        """Handle text changes"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return  # Don't autosave if not properly initialized
            
        self.changes_pending = True
        current_time = time.time()
        
        # Save if it's been more than 1 second since last save
        if current_time - self.last_save_time > 1.0:
            self.autosave()
            self.last_save_time = current_time

    def force_save(self):
        """Force save if there are pending changes"""
        if self.changes_pending:
            self.autosave()
            self.last_save_time = time.time()
            self.changes_pending = False

    def autosave(self):
        """Perform autosave with integrity checks"""
        content = self.editor.toPlainText()
        
        try:
            # Create temporary files first
            temp_content = self.session_path + '.tmp'
            temp_meta = self.meta_path + '.tmp'
            
            # Save content with integrity check
            with open(temp_content, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            
            # Verify content was written correctly
            with open(temp_content, 'r', encoding='utf-8') as f:
                saved_content = f.read()
                if saved_content != content:
                    raise ValueError("Content verification failed")
            
            # Save metadata
            metadata = {
                'timestamp': time.time(),
                'original_file': self.current_file,
                'cursor_position': self.editor.textCursor().position(),
                'scroll_position': self.editor.verticalScrollBar().value(),
                'modified': self.editor.document().isModified(),
                'tab_index': self.main_window.tab_widget.indexOf(self) if self.main_window else 0,
                'active': self.main_window.tab_widget.currentWidget() == self if self.main_window else False,
                'checksum': hashlib.md5(content.encode()).hexdigest()
            }
            
            with open(temp_meta, 'w') as f:
                json.dump(metadata, f)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace old files with new ones
            os.replace(temp_content, self.session_path)
            os.replace(temp_meta, self.meta_path)
            
            # Update session state
            if self.main_window:
                current_tabs = self.main_window.get_open_tab_ids()
                self.settings_manager.save_session_state(current_tabs)
            
            self.changes_pending = False
                
        except Exception as e:
            print(f"Autosave failed: {str(e)}")

    def save_file(self, force_dialog=False):
        """Save file, optionally forcing Save As dialog"""
        if not self.current_file or force_dialog:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save File",
                os.path.expanduser("~"),
                "Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*.*)"
            )
            if file_name:
                self.current_file = file_name
            else:
                return False
                
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            
            # Update tab title
            if self.main_window:
                current_index = self.main_window.tab_widget.indexOf(self)
                self.main_window.tab_widget.setTabText(current_index, os.path.basename(self.current_file))
            
            # Mark document as unmodified
            self.editor.document().setModified(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file: {str(e)}")
            return False

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", 
                                                 "Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*)")
        if file_name:
            self.current_file = file_name
            with open(file_name, 'r', encoding='utf-8') as file:
                self.editor.setPlainText(file.read())
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
        """Show context menu"""
        # Get current selection
        cursor = self.editor.textCursor()
        had_selection = cursor.hasSelection()
        
        if not had_selection:
            # Only select word under cursor if there was no existing selection
            cursor = self.editor.cursorForPosition(pos)
            cursor.select(cursor.WordUnderCursor)
            self.editor.setTextCursor(cursor)
        
        # Create menu with a slight delay to prevent accidental triggers
        QTimer.singleShot(100, lambda: self._show_context_menu_impl(pos))

    def _show_context_menu_impl(self, pos):
        """Implementation of context menu display"""
        menu = QMenu(self)
        
        # # Cut/Copy/Paste actions
        # menu.addAction("Cut", self.editor.cut)
        # menu.addAction("Copy", self.editor.copy)
        # menu.addAction("Paste", self.editor.paste)
        # menu.addSeparator()
        
        # Get selected text
        selected_text = self.editor.textCursor().selectedText()
        
        if selected_text:
            
            
            # Add search submenu
            search_menu = menu.addMenu("Search in...")
            
            # Get site-specific searches from settings
            search_sites = self.settings_manager.get_setting('search_sites', {
                'AP News': 'site:apnews.com',
                'Reuters': 'site:reuters.com',
                'BBC News': 'site:bbc.com/news'
            })
            
            # Add search actions for each site
            for name, site_query in search_sites.items():
                action = search_menu.addAction(name)
                search_url = f"https://www.google.com/search?q={quote(selected_text)}+{site_query}"
                action.triggered.connect(lambda checked, url=search_url: 
                    self.search_in_browser(url))
            
            # Add separator and regular Google search
            search_menu.addSeparator()
            google_action = search_menu.addAction("Google")
            google_url = f"https://www.google.com/search?q={quote(selected_text)}"
            google_action.triggered.connect(lambda checked, url=google_url: 
                self.search_in_browser(url))
            # Add Wikipedia search
            wiki_action = search_menu.addAction("Wikipedia")
            wiki_url = f"https://en.wikipedia.org/w/index.php?search={quote(selected_text)}"
            wiki_action.triggered.connect(lambda checked, url=wiki_url: 
                self.search_in_browser(url))
            
            # Add Google Scholar search
            scholar_action = search_menu.addAction("Google Scholar")
            scholar_url = f"https://scholar.google.com/scholar?q={quote(selected_text)}"
            scholar_action.triggered.connect(lambda checked, url=scholar_url: 
                self.search_in_browser(url))
            
            # Add Google Maps search
            maps_action = search_menu.addAction("Google Maps")
            maps_url = f"https://www.google.com/maps/search/{quote(selected_text)}"
            maps_action.triggered.connect(lambda checked, url=maps_url: 
                self.search_in_browser(url))
            
            # Add Google News search
            news_action = search_menu.addAction("Google News")
            news_url = f"https://news.google.com/search?q={quote(selected_text)}"
            news_action.triggered.connect(lambda checked, url=news_url: 
                self.search_in_browser(url))
            
            # add google translate search
            translate_action = search_menu.addAction("Google Translate")
            translate_url = f"https://translate.google.com/?sl=auto&tl=en&text={quote(selected_text)}"
            translate_action.triggered.connect(lambda checked, url=translate_url: 
                self.search_in_browser(url))
            
            # Add Google define search
            dictionary_action = search_menu.addAction("Google Define")
            dictionary_url = f"https://www.google.com/search?q=define+{quote(selected_text)}"
            dictionary_action.triggered.connect(lambda checked, url=dictionary_url: 
                self.search_in_browser(url))
            
            menu.addSeparator()
            
            # Only show spell check options for single words
            if not ' ' in selected_text:
                # Add spell check suggestions if word is misspelled
                if self.highlighter.spell_check_enabled:
                    suggestions = self.highlighter.suggest(selected_text)[:7]  # Limit to 7 suggestions
                    if suggestions:
                        menu.addAction("Spelling Suggestions:").setEnabled(False)
                        for suggestion in suggestions:
                            action = menu.addAction(suggestion)
                            action.triggered.connect(lambda checked, word=suggestion: 
                                self.replace_word(word))
                        menu.addSeparator()
                
                # Add to dictionary option if not already in it
                if selected_text not in self.settings_manager.get_setting('user_dictionary', []):
                    add_action = menu.addAction("Add to Dictionary")
                    add_action.triggered.connect(lambda: self.add_to_dictionary(selected_text))
                    menu.addSeparator()
            # Add "Save as Snippet" option
            menu.addAction("Save as Snippet", lambda: self.save_snippet(selected_text))
            menu.addSeparator()
        # Cut/Copy/Paste actions
        menu.addAction("Cut", self.editor.cut)
        menu.addAction("Copy", self.editor.copy)
        menu.addAction("Paste", self.editor.paste)
        menu.addSeparator()            
        
        # Show menu
        menu.exec(self.editor.mapToGlobal(pos))

    def search_in_browser(self, url):
        """Search the given URL in the browser pane"""
        # Store URL to load
        self._pending_url = url
        
        # Check if browser is visible but too narrow
        if self.browser_widget.isVisible():
            current_sizes = self.splitter.sizes()
            if current_sizes[2] < 300:  # If browser pane is too narrow
                editor_size = current_sizes[0]
                new_browser_size = int(editor_size * 0.3)  # 30% of editor width
                new_editor_size = editor_size - (new_browser_size - current_sizes[2])
                self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
        # Make sure browser is visible and web view exists
        if not self.browser_widget.isVisible():
            # Mark browser as opened during focus mode BEFORE toggling
            if self.focus_mode:
                self.panes_opened_in_focus['browser'] = True
            self.toggle_pane("browser")
            return
        
        # If browser is visible but no web view exists, create it
        if not self.web_view:
            self.create_web_view()
        
        # Stop any current loading and load new URL
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))

    def add_to_dictionary(self, word):
        """Add word to user dictionary"""
        if self.USE_ENCHANT:
            # Enchant spell checker implementation
            self.spell_checker.add(word)
        else:
            # PySpellChecker implementation
            self.spell_checker.word_frequency.add(word)
            # Force a recheck of the document
            self.highlighter.rehighlight()
        
        # Add to user dictionary in settings
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)

    def ensure_browser_visible(self):
        """Ensure browser pane is visible"""
        if not self.browser_widget.isVisible():
            self.browser_widget.setVisible(True)
            self.settings_manager.save_pane_visibility(
                self.snippet_widget.isVisible(),
                True
            )

    def search_google(self, text):
        """Search Google in browser pane"""
        url = f"https://www.google.com/search?q={quote(text)}"
        
        # Store URL and ensure browser is visible
        self._pending_url = url
        
        # Check if browser is visible but too narrow
        if self.browser_widget.isVisible():
            current_sizes = self.splitter.sizes()
            if current_sizes[2] < 300:  # If browser pane is too narrow
                editor_size = current_sizes[0]
                new_browser_size = int(editor_size * 0.3)  # 30% of editor width
                new_editor_size = editor_size - (new_browser_size - current_sizes[2])
                self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
        # If browser is not visible, show it first
        if not self.browser_widget.isVisible():
            self.toggle_pane("browser")
            return
        
        # If browser is visible but no web view exists, create it
        if not self.web_view:
            self.create_web_view()
        
        # Use existing web view
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))
        self.url_bar.setText(url)

    def search_apnews(self, text):
        """Search AP News in browser pane"""
        url = f"https://apnews.com/search?q={quote(text)}"
        
        # Store URL and ensure browser is visible
        self._pending_url = url
        
        # If browser is not visible, show it first
        if not self.browser_widget.isVisible():
            self.toggle_pane("browser")
            return
            
        # If browser is visible but no web view exists, create it
        if not self.web_view:
            self.create_web_view()
            
        # Use existing web view
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))
        self.url_bar.setText(url)
        
    def search_google_site_apnews(self, text):
        """Search AP News via Google in browser pane"""
        url = f"https://www.google.com/search?q=site:apnews.com {quote(text)}"
        
        # Store URL and ensure browser is visible
        self._pending_url = url
        
        # If browser is not visible, show it first
        if not self.browser_widget.isVisible():
            self.toggle_pane("browser")
            return
            
        # If browser is visible but no web view exists, create it
        if not self.web_view:
            self.create_web_view()
            
        # Use existing web view
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))
        self.url_bar.setText(url)
        
    def save_snippet(self, text):
        """Save selected text as a snippet"""
        title, ok = QInputDialog.getText(self, "Save Snippet", "Enter snippet title:")
        if ok and title:
            self.snippet_manager.add_snippet(title, text)
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
        current_item = self.snippet_list.currentItem()
        
        if current_item:
            menu.addAction("Edit Snippet", self.edit_current_snippet)
            menu.addAction("Delete Snippet", self.delete_current_snippet)
            menu.exec(self.snippet_list.mapToGlobal(position))

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
        cursor.movePosition(cursor.Left, cursor.KeepAnchor, chars_to_delete)
        cursor.removeSelectedText()
        
        # Insert the snippet content
        snippet_content = self.snippet_manager.get_snippet(completion)
        if snippet_content:
            cursor.insertText(snippet_content)
    
    def navigate_to_url(self):
        """Navigate to URL entered in URL bar"""
        url = self.url_bar.text().strip()
        if not url:
            return
            
        # Add http:// if no protocol specified
        if not url.startswith(('http://', 'https://')):
            # Check if it's a search query
            if ' ' in url or not '.' in url:
                url = f"https://www.google.com/search?q={quote(url)}"
            else:
                url = 'http://' + url
        
        # Check if browser is visible but too narrow
        if self.browser_widget.isVisible():
            current_sizes = self.splitter.sizes()
            if current_sizes[2] < 300:  # If browser pane is too narrow
                editor_size = current_sizes[0]
                new_browser_size = int(editor_size * 0.3)  # 30% of editor width
                new_editor_size = editor_size - (new_browser_size - current_sizes[2])
                self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
        # If browser is not visible, show it first
        if not self.browser_widget.isVisible():
            self._pending_url = url
            self.toggle_pane("browser")
            return
        
        # If browser is visible but no web view exists, create it
        if not self.web_view:
            self.create_web_view()
        
        # Stop any current loading and load new URL
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))

    def create_web_view(self):
        """Create and set up web view"""
        self.web_view = QWebEngineView()
        
        # Connect all web view signals
        self.web_view.urlChanged.connect(self.update_url)
        self.web_view.loadStarted.connect(lambda: self.url_bar.setEnabled(False))
        self.web_view.loadFinished.connect(lambda: self.url_bar.setEnabled(True))
        self.web_view.loadFinished.connect(self.update_nav_buttons)
        
        # Connect navigation buttons
        self.back_btn.clicked.connect(self.web_view.back)
        self.forward_btn.clicked.connect(self.web_view.forward)
        
        # Add to layout
        self.web_container.layout().addWidget(self.web_view)

    def update_font(self, font):
        """Update editor font"""
        self.current_font = QFont(font)  # Store a copy of the font
        self.current_font.setWeight(QFont.Weight.Normal)  # Force Regular weight
        
        # Update font for the editor
        self.editor.setFont(self.current_font)
        
        ThemeManager.apply_theme(
            self.editor,
            self.current_theme,
            self.settings_manager.get_custom_themes()
        )
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(
                self.current_theme,
                self.settings_manager.get_custom_themes()
            )
        self.editor.update_line_number_area_width()
        self.editor.update_line_number_area()
        self.update_markdown_preview()

    def apply_theme(self, theme_name):
        """Apply theme while preserving font properties"""
        self.current_theme = theme_name
        self.settings_manager.save_theme(theme_name)
        ThemeManager.apply_theme(
            self.editor,
            theme_name,
            self.settings_manager.get_custom_themes()
        )
        
        # After applying theme, reapply font to ensure properties are preserved
        if hasattr(self, 'current_font'):
            self.update_font(self.current_font)
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(
                theme_name,
                self.settings_manager.get_custom_themes()
            )
        self.apply_workspace_style()
        self.update_markdown_preview()

    def set_line_numbers_visible(self, visible):
        """Show or hide editor line numbers."""
        self.editor.set_line_numbers_visible(visible)

    def is_markdown_file(self, file_path=None):
        """Return True when a path should be treated as markdown."""
        path = file_path or self.current_file or ""
        return os.path.splitext(path.lower())[1] in ('.md', '.markdown', '.mdown', '.mkd')

    def set_markdown_preview_visible(self, visible, save_state=True):
        """Show or hide the rendered markdown preview."""
        self.markdown_preview_visible = visible
        self.markdown_preview.setVisible(visible)
        self.markdown_preview.setMinimumWidth(240 if visible else 0)
        if visible:
            if self.preview_scroll_timer:
                self.preview_scroll_timer.start()
            if hasattr(self, 'markdown_splitter') and self.markdown_splitter.sizes()[1] < 100:
                self.markdown_splitter.setSizes([600, 600])
            self.update_markdown_preview()
        else:
            if self.preview_scroll_timer:
                self.preview_scroll_timer.stop()
        if save_state:
            self.save_pane_states()

    def toggle_markdown_preview(self):
        """Toggle the rendered markdown preview pane."""
        self.set_markdown_preview_visible(not self.markdown_preview_visible)

    def schedule_markdown_preview_update(self):
        """Render the preview after typing has settled briefly."""
        if not hasattr(self, 'markdown_preview') or not self.markdown_preview_visible:
            return
        if self.markdown_render_timer:
            self.markdown_render_timer.start()

    def update_markdown_preview(self):
        """Render editor markdown into the preview pane."""
        if not hasattr(self, 'markdown_preview') or not self.markdown_preview_visible:
            return

        if self.current_file:
            content_base_url = QUrl.fromLocalFile(os.path.dirname(self.current_file) + os.sep).toString()
        else:
            content_base_url = QUrl.fromLocalFile(os.getcwd() + os.sep).toString()

        self.write_markdown_preview_file(
            self.render_markdown_html(self.editor.toPlainText(), content_base_url)
        )
        self.markdown_preview.load(QUrl.fromLocalFile(self.markdown_preview_file))
        QTimer.singleShot(100, self.sync_markdown_preview_scroll)
        QTimer.singleShot(300, self.render_markdown_preview_scripts)

    def write_markdown_preview_file(self, preview_html):
        """Write the rendered preview to a normal local HTML file for WebEngine."""
        with open(self.markdown_preview_file, 'w', encoding='utf-8') as preview_file:
            preview_file.write(preview_html)

    def render_markdown_preview_scripts(self, *args):
        """Run preview scripts that need the WebEngine page to finish loading."""
        if not hasattr(self, 'markdown_preview') or not self.markdown_preview_visible:
            return

        self.markdown_preview.page().runJavaScript("""
            (async function () {
                let rendered = false;
                if (window.mermaid) {
                    try {
                    mermaid.initialize({
                        startOnLoad: false,
                        securityLevel: 'loose',
                        theme: 'default'
                    });

                    function renderDiagram(renderId, source, diagram) {
                        return new Promise(function (resolve, reject) {
                            try {
                                if (mermaid.render.length >= 3) {
                                    mermaid.render(renderId, source, function (svg, bindFunctions) {
                                        resolve({
                                            svg: svg,
                                            bindFunctions: bindFunctions
                                        });
                                    }, diagram);
                                    return;
                                }

                                Promise.resolve(mermaid.render(renderId, source)).then(function (result) {
                                    if (typeof result === 'string') {
                                        resolve({
                                            svg: result,
                                            bindFunctions: null
                                        });
                                    } else {
                                        resolve(result);
                                    }
                                }).catch(reject);
                            } catch (error) {
                                reject(error);
                            }
                        });
                    }

                    var diagrams = Array.prototype.slice.call(document.querySelectorAll('.mermaid'));
                    for (var index = 0; index < diagrams.length; index += 1) {
                        var diagram = diagrams[index];
                        if (diagram.dataset.rendered === 'true') {
                            continue;
                        }

                        var source = diagram.textContent;
                        var renderId = 'jottr-mermaid-' + Date.now() + '-' + index;
                        try {
                            var result = await renderDiagram(renderId, source, diagram);
                            diagram.innerHTML = result.svg;
                            diagram.dataset.rendered = 'true';
                            diagram.classList.remove('mermaid-error');
                            if (result.bindFunctions) {
                                result.bindFunctions(diagram);
                            }
                            rendered = true;
                        } catch (error) {
                            diagram.classList.add('mermaid-error');
                            diagram.textContent = 'Mermaid render error: ' + error.message + '\\n\\n' + source;
                            rendered = true;
                        }
                    }
                } catch (error) {
                    console.error('Mermaid render failed', error);
                }
                }

                if (window.MathJax && window.MathJax.typesetPromise) {
                    try {
                        await window.MathJax.typesetPromise();
                        rendered = true;
                    } catch (error) {
                        console.error('MathJax render failed', error);
                    }
                }

                return rendered;
            })();
        """, lambda _result: QTimer.singleShot(50, self.sync_markdown_preview_scroll))

    def get_editor_scroll_ratio(self):
        """Return editor vertical scroll progress as a 0..1 ratio."""
        scroll_bar = self.editor.verticalScrollBar()
        maximum = scroll_bar.maximum()
        if maximum <= 0:
            return 0.0
        return max(0.0, min(1.0, scroll_bar.value() / maximum))

    def get_editor_top_visible_line(self):
        """Return the 1-based source line nearest the top of the editor viewport."""
        cursor = self.editor.cursorForPosition(self.editor.viewport().rect().topLeft())
        return cursor.blockNumber() + 1

    def schedule_markdown_cursor_sync(self):
        """Sync preview to the line currently being edited."""
        if self.syncing_markdown_scroll:
            return

        self.pending_preview_source_line = self.editor.textCursor().blockNumber() + 1
        self.schedule_markdown_scroll_sync()

    def schedule_markdown_scroll_sync(self, *_args):
        """Debounce editor scroll events before updating preview scroll."""
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                self.syncing_markdown_scroll or
                self.preview_scroll_pending):
            return

        self.preview_scroll_pending = True
        QTimer.singleShot(16, self.sync_markdown_preview_scroll)

    def sync_markdown_preview_scroll(self):
        """Scroll the markdown preview to match the editor's relative position."""
        self.preview_scroll_pending = False
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                not hasattr(self, 'markdown_preview')):
            return

        source_line = self.pending_preview_source_line or self.get_editor_top_visible_line()
        editor_scroll_ratio = self.get_editor_scroll_ratio()
        self.pending_preview_source_line = None
        self.syncing_markdown_scroll = True
        self.ignore_preview_scroll_until = time.time() + 0.75
        self.markdown_preview.page().runJavaScript(
            """
            (function(targetLine, editorScrollRatio) {
                const nodes = Array.from(document.querySelectorAll('[data-source-line]'));
                if (!nodes.length) return;

                let target = nodes[0];
                for (const node of nodes) {
                    const line = Number(node.dataset.sourceLine);
                    if (line > targetLine) break;
                    target = node;
                }

                const doc = document.scrollingElement || document.documentElement;
                const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
                const anchorTop = Math.max(0, target.getBoundingClientRect().top + window.scrollY - 16);
                const ratioTop = maxScroll * Math.max(0, Math.min(1, Number(editorScrollRatio) || 0));
                let top = anchorTop;

                if (anchorTop >= maxScroll && editorScrollRatio < 0.98) {
                    top = ratioTop;
                }

                top = Math.max(0, Math.min(maxScroll, top));

                if (window.__jottrPreviewScrollFrame) {
                    cancelAnimationFrame(window.__jottrPreviewScrollFrame);
                }

                const start = window.scrollY;
                const delta = top - start;
                if (Math.abs(delta) < 2) {
                    window.scrollTo(0, top);
                    return;
                }

                const duration = 140;
                const startTime = performance.now();
                function ease(value) {
                    return value < 0.5 ? 2 * value * value : 1 - Math.pow(-2 * value + 2, 2) / 2;
                }
                function step(now) {
                    const progress = Math.min(1, (now - startTime) / duration);
                    window.scrollTo(0, start + delta * ease(progress));
                    if (progress < 1) {
                        window.__jottrPreviewScrollFrame = requestAnimationFrame(step);
                    }
                }
                window.__jottrPreviewScrollFrame = requestAnimationFrame(step);
            })(""" + str(source_line) + ", " + repr(editor_scroll_ratio) + """);
            """,
            lambda _result: setattr(self, 'syncing_markdown_scroll', False)
        )

    def animate_editor_scroll_to(self, value):
        """Smoothly move the editor scrollbar to the requested value."""
        scroll_bar = self.editor.verticalScrollBar()
        target = max(scroll_bar.minimum(), min(scroll_bar.maximum(), int(value)))
        if abs(scroll_bar.value() - target) < 2:
            scroll_bar.setValue(target)
            QTimer.singleShot(0, lambda: setattr(self, 'syncing_markdown_scroll', False))
            return

        if self.editor_scroll_animation:
            self.editor_scroll_animation.stop()

        self.editor_scroll_animation = QPropertyAnimation(scroll_bar, b"value", self)
        self.editor_scroll_animation.setDuration(130)
        self.editor_scroll_animation.setStartValue(scroll_bar.value())
        self.editor_scroll_animation.setEndValue(target)
        self.editor_scroll_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.editor_scroll_animation.finished.connect(
            lambda: setattr(self, 'syncing_markdown_scroll', False)
        )
        self.editor_scroll_animation.start()

    def schedule_editor_scroll_sync(self):
        """Debounce preview scroll events before updating editor scroll."""
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                self.syncing_markdown_scroll or
                time.time() < self.ignore_preview_scroll_until or
                time.time() > self.preview_user_scroll_until or
                self.editor_scroll_pending):
            return

        self.editor_scroll_pending = True
        QTimer.singleShot(80, self.sync_editor_scroll_from_preview)

    def sync_editor_scroll_from_preview(self):
        """Scroll the editor to match the preview's relative position."""
        self.editor_scroll_pending = False
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                not hasattr(self, 'markdown_preview')):
            return

        script = """
            (function() {
                const nodes = Array.from(document.querySelectorAll('[data-source-line]'));
                if (!nodes.length) return 1;

                let best = nodes[0];
                let bestDistance = Infinity;
                for (const node of nodes) {
                    const distance = Math.abs(node.getBoundingClientRect().top - 16);
                    if (distance < bestDistance) {
                        best = node;
                        bestDistance = distance;
                    }
                }
                return Number(best.dataset.sourceLine) || 1;
            })();
        """

        def apply_editor_scroll(source_line):
            try:
                source_line = max(1, int(float(source_line)))
            except (TypeError, ValueError):
                return

            block = self.editor.document().findBlockByNumber(source_line - 1)
            if not block.isValid():
                return

            scroll_bar = self.editor.verticalScrollBar()
            layout = self.editor.document().documentLayout()
            block_top = layout.blockBoundingRect(block).top() - scroll_bar.value()

            self.syncing_markdown_scroll = True
            self.animate_editor_scroll_to(round(scroll_bar.value() + block_top - 16))

        self.markdown_preview.page().runJavaScript(script, apply_editor_scroll)

    def render_markdown_html(self, text, content_base_url=""):
        """Render a practical markdown subset with stable heading and code styling."""
        if MARKDOWN_LIB_AVAILABLE:
            return self.render_markdown_html_with_library(text, content_base_url)

        body = []
        paragraph = []
        paragraph_lines = []
        in_code_block = False
        code_lines = []
        code_start_line = None
        in_math_block = False
        math_lines = []
        math_start_line = None
        list_stack = []

        emoji_map = {
            "smile": "😄", "grinning": "😀", "joy": "😂", "laughing": "😆",
            "wink": "😉", "blush": "😊", "heart": "❤️", "broken_heart": "💔",
            "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎",
            "clap": "👏", "pray": "🙏", "fire": "🔥", "star": "⭐",
            "sparkles": "✨", "rocket": "🚀", "tada": "🎉", "warning": "⚠️",
            "x": "❌", "white_check_mark": "✅", "check": "✅", "information_source": "ℹ️",
            "bulb": "💡", "eyes": "👀", "thinking": "🤔", "cry": "😢",
            "sob": "😭", "angry": "😠", "poop": "💩", "100": "💯",
            "memo": "📝", "book": "📖", "computer": "💻", "gear": "⚙️",
            "bug": "🐛", "lock": "🔒", "unlock": "🔓", "link": "🔗"
        }

        def is_table_separator(value):
            cells = EditorTab.split_table_row(value)
            if len(cells) < 2:
                return False
            return all(re.match(r'^:?-{3,}:?$', cell.strip()) for cell in cells)

        def table_alignments(separator):
            alignments = []
            for cell in EditorTab.split_table_row(separator):
                stripped = cell.strip()
                if stripped.startswith(":") and stripped.endswith(":"):
                    alignments.append("center")
                elif stripped.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")
            return alignments

        def split_image_target(target):
            target = target.strip()
            title = ""
            if target.startswith("<"):
                end = target.find(">")
                if end >= 0:
                    source = target[1:end].strip()
                    title = target[end + 1:].strip()
                else:
                    source = target.strip("<>").strip()
            else:
                match = re.match(r'^(.*?)\s+["\']([^"\']*)["\']\s*$', target)
                if match:
                    source = match.group(1).strip()
                    title = match.group(2)
                else:
                    source = target
            return source, title

        def resolve_local_image_path(source):
            if source.startswith("file://"):
                return QUrl(source).toLocalFile()

            current_file = getattr(self, 'current_file', None)
            if current_file and not os.path.isabs(source):
                source = os.path.join(os.path.dirname(current_file), source)
            return os.path.abspath(os.path.expanduser(source))

        def image_file_to_data_url(path):
            if not os.path.isfile(path):
                return None

            mime_type, _ = mimetypes.guess_type(path)
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            try:
                with open(path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode("ascii")
                return f"data:{mime_type};base64,{encoded}"
            except OSError:
                return None

        def resolve_image_source(source):
            source = source.strip()
            if source.startswith("<") and source.endswith(">"):
                source = source[1:-1].strip()
            if source.startswith(("http://", "https://", "data:")):
                return html.escape(source, quote=True)

            local_path = resolve_local_image_path(source)
            data_url = image_file_to_data_url(local_path)
            if data_url:
                return html.escape(data_url, quote=True)
            return html.escape(QUrl.fromLocalFile(local_path).toString(QUrl.FullyEncoded), quote=True)

        def render_inline(value):
            images = []
            inline_math = []

            def stash_image(match):
                alt_text = html.escape(match.group(1), quote=True)
                source_target, explicit_title = split_image_target(match.group(2))
                source = resolve_image_source(source_target)
                title = html.escape(explicit_title or match.group(1), quote=True)
                images.append(
                    f'<img src="{source}" alt="{alt_text}" title="{title}">'
                )
                return f"\u0000IMG{len(images) - 1}\u0000"

            def stash_inline_math(match):
                expression = html.escape(match.group(1).strip())
                inline_math.append(f'<span class="math-inline">\\({expression}\\)</span>')
                return f"\u0000MATH{len(inline_math) - 1}\u0000"

            value = re.sub(
                r'!\[([^\]]*)\]\(\s*([^)]+?)\s*\)',
                stash_image,
                value
            )
            value = re.sub(r'(?<!\\)\$(?!\$)(.+?)(?<!\\)\$', stash_inline_math, value)
            value = html.escape(value)
            value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
            value = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)
            value = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', value)
            value = re.sub(r'~~(.+?)~~', r'<del>\1</del>', value)
            value = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', value)
            value = re.sub(r'(?<!_)_([^_\n]+)_(?!_)', r'<em>\1</em>', value)
            value = EditorTab.apply_typographer_replacements(value)
            value = re.sub(
                r':([a-zA-Z0-9_+\-]+):',
                lambda match: emoji_map.get(match.group(1), match.group(0)),
                value
            )
            value = re.sub(
                r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
                r'<a href="\2">\1</a>',
                value
            )
            for index, image_markup in enumerate(images):
                value = value.replace(f"\u0000IMG{index}\u0000", image_markup)
            for index, math_markup in enumerate(inline_math):
                value = value.replace(f"\u0000MATH{index}\u0000", math_markup)
            return value

        def flush_paragraph():
            nonlocal paragraph_lines
            if paragraph:
                source_line = paragraph_lines[0] if paragraph_lines else 1
                body.append(f'<p data-source-line="{source_line}">{render_inline(" ".join(paragraph))}</p>')
                paragraph.clear()
                paragraph_lines.clear()

        def close_list():
            while list_stack:
                close_list_level()

        def close_list_level():
            list_state = list_stack.pop()
            if list_state.get('open_item'):
                body.append("</li>")
            body.append(f"</{list_state['type']}>")

        def list_level_from_indent(indent):
            return indent // 2

        def render_task_list_item_content(item_text):
            task = re.match(r'^\[([ xX])\]\s*(.*)$', item_text)
            if not task:
                return render_inline(item_text)

            checked = ' checked' if task.group(1).lower() == 'x' else ''
            return (
                f'<input class="task-list-item-checkbox" type="checkbox" disabled{checked}> '
                f'{render_inline(task.group(2))}'
            )

        def render_list_item(line_number, list_type, level, item_text, start_number=None):
            while list_stack and list_stack[-1]['level'] > level:
                close_list_level()

            if list_stack and list_stack[-1]['level'] == level and list_stack[-1]['type'] != list_type:
                close_list_level()

            if not list_stack or list_stack[-1]['level'] < level:
                start_attr = f' start="{start_number}"' if list_type == "ol" and start_number and start_number != 1 else ""
                body.append(f"<{list_type}{start_attr}>")
                list_stack.append({'type': list_type, 'level': level, 'open_item': False})

            if list_stack[-1]['open_item']:
                body.append("</li>")

            body.append(f'<li data-source-line="{line_number}">{render_task_list_item_content(item_text)}')
            list_stack[-1]['open_item'] = True

        def render_display_math(source_line, expression):
            escaped_expression = html.escape(expression.strip())
            return (
                f'<div class="math-block" data-source-line="{source_line}">'
                f'\\[{escaped_expression}\\]</div>'
            )

        def render_code_block(source_line, values, span_start_line=None):
            span_start_line = span_start_line or source_line
            code_markup = []
            for offset, value in enumerate(values):
                escaped_line = html.escape(value) or " "
                code_markup.append(
                    f'<span class="source-code-line" data-source-line="{span_start_line + offset}">'
                    f'{escaped_line}</span>'
                )
            return (
                f'<pre data-source-line="{source_line}">'
                f'<code>{"".join(code_markup)}</code></pre>'
            )

        def is_indented_code_line(value):
            return value.startswith("    ") or value.startswith("\t")

        def strip_code_indent(value):
            if value.startswith("\t"):
                return value[1:]
            if value.startswith("    "):
                return value[4:]
            return value

        def collect_indented_code(start_index):
            code_block_lines = []
            current_index = start_index
            while current_index < len(lines):
                current_line = lines[current_index]
                if is_indented_code_line(current_line) and not is_list_line(current_line):
                    code_block_lines.append(strip_code_indent(current_line.rstrip()))
                    current_index += 1
                elif not current_line.strip() and code_block_lines:
                    code_block_lines.append("")
                    current_index += 1
                else:
                    break

            while code_block_lines and code_block_lines[-1] == "":
                code_block_lines.pop()
            return code_block_lines, current_index

        def is_list_line(value):
            return bool(
                re.match(r'^(\s*)[-*+](?:\s+(.*))?$', value) or
                re.match(r'^(\s*)(\d+)[.)](?:\s+(.*))?$', value)
            )

        def render_table(source_line, rows, alignments):
            header = rows[0]
            body_rows = rows[2:]
            html_rows = [f'<table data-source-line="{source_line}">', '<thead><tr>']
            for index, cell in enumerate(header):
                alignment = alignments[index] if index < len(alignments) else "left"
                html_rows.append(f'<th style="text-align: {alignment};">{render_inline(cell.strip())}</th>')
            html_rows.append('</tr></thead>')

            if body_rows:
                html_rows.append('<tbody>')
                for row in body_rows:
                    html_rows.append('<tr>')
                    for index, cell in enumerate(row):
                        alignment = alignments[index] if index < len(alignments) else "left"
                        html_rows.append(f'<td style="text-align: {alignment};">{render_inline(cell.strip())}</td>')
                    html_rows.append('</tr>')
                html_rows.append('</tbody>')

            html_rows.append('</table>')
            return ''.join(html_rows)

        lines = text.splitlines()
        line_index = 0

        while line_index < len(lines):
            line_number = line_index + 1
            raw_line = lines[line_index]
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    block_line = code_start_line or line_number
                    body.append(render_code_block(block_line, code_lines, block_line + 1))
                    code_lines = []
                    code_start_line = None
                    in_code_block = False
                else:
                    flush_paragraph()
                    close_list()
                    in_code_block = True
                    code_start_line = line_number
                line_index += 1
                continue

            if in_code_block:
                code_lines.append(raw_line)
                line_index += 1
                continue

            if stripped.startswith("$$"):
                if in_math_block:
                    content = stripped[2:].strip()
                    if content:
                        math_lines.append(content)
                    body.append(render_display_math(math_start_line or line_number, chr(10).join(math_lines)))
                    math_lines = []
                    math_start_line = None
                    in_math_block = False
                else:
                    flush_paragraph()
                    close_list()
                    after_open = stripped[2:].strip()
                    if after_open.endswith("$$") and len(after_open) > 2:
                        body.append(render_display_math(line_number, after_open[:-2]))
                    else:
                        in_math_block = True
                        math_start_line = line_number
                        if after_open:
                            math_lines.append(after_open)
                line_index += 1
                continue

            if in_math_block:
                if stripped.endswith("$$"):
                    before_close = raw_line.rstrip()[:-2].strip()
                    if before_close:
                        math_lines.append(before_close)
                    body.append(render_display_math(math_start_line or line_number, chr(10).join(math_lines)))
                    math_lines = []
                    math_start_line = None
                    in_math_block = False
                else:
                    math_lines.append(raw_line)
                line_index += 1
                continue

            if not stripped:
                flush_paragraph()
                close_list()
                line_index += 1
                continue

            unordered = re.match(r'^(\s*)[-*+](?:\s+(.*))?$', line)
            ordered = re.match(r'^(\s*)(\d+)[.)](?:\s+(.*))?$', line)
            if unordered or ordered:
                flush_paragraph()
                desired_list = "ul" if unordered else "ol"
                indent = len(unordered.group(1) if unordered else ordered.group(1))
                item_text = (unordered.group(2) if unordered else ordered.group(3)) or ""
                start_number = None if unordered else int(ordered.group(2))
                render_list_item(line_number, desired_list, list_level_from_indent(indent), item_text, start_number)
                line_index += 1
                continue

            if is_indented_code_line(raw_line):
                flush_paragraph()
                close_list()
                indented_code_lines, line_index = collect_indented_code(line_index)
                body.append(render_code_block(line_number, indented_code_lines))
                continue

            if ("|" in stripped and
                    line_index + 1 < len(lines) and
                    is_table_separator(lines[line_index + 1].strip())):
                flush_paragraph()
                close_list()
                table_rows = [EditorTab.split_table_row(stripped), EditorTab.split_table_row(lines[line_index + 1].strip())]
                alignments = table_alignments(lines[line_index + 1].strip())
                line_index += 2
                while line_index < len(lines) and "|" in lines[line_index].strip():
                    table_rows.append(EditorTab.split_table_row(lines[line_index].strip()))
                    line_index += 1
                body.append(render_table(line_number, table_rows, alignments))
                continue

            heading = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading:
                flush_paragraph()
                close_list()
                level = len(heading.group(1))
                body.append(f'<h{level} data-source-line="{line_number}">{render_inline(heading.group(2))}</h{level}>')
                line_index += 1
                continue

            if re.match(r'^([-*_])(?:\s*\1){2,}\s*$', stripped):
                flush_paragraph()
                close_list()
                body.append(f'<hr data-source-line="{line_number}">')
                line_index += 1
                continue

            quote = re.match(r'^(>+\s*)+(.*)$', stripped)
            if quote:
                flush_paragraph()
                close_list()
                quote_text = quote.group(2).strip()
                body.append(f'<blockquote data-source-line="{line_number}">{render_inline(quote_text)}</blockquote>')
                line_index += 1
                continue

            close_list()
            paragraph.append(stripped)
            paragraph_lines.append(line_number)
            line_index += 1

        if in_code_block:
            block_line = code_start_line or 1
            body.append(render_code_block(block_line, code_lines, block_line + 1))
        if in_math_block:
            body.append(render_display_math(math_start_line or 1, chr(10).join(math_lines)))
        flush_paragraph()
        close_list()

        return f"""
        <html>
        <head>
            <style>
                body {{
                    color: #202124;
                    font-family: "DejaVu Sans", "Segoe UI", sans-serif;
                    font-size: 14px;
                    line-height: 1.55;
                    margin: 18px;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #111827;
                    font-weight: 700;
                    margin: 1.1em 0 0.45em;
                }}
                h1 {{ font-size: 30px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
                h2 {{ font-size: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 4px; }}
                h3 {{ font-size: 20px; }}
                h4 {{ font-size: 17px; }}
                h5 {{ font-size: 15px; }}
                h6 {{ font-size: 14px; color: #57606a; }}
                p {{ margin: 0 0 0.8em; }}
                pre {{
                    background: #f6f8fa;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    padding: 12px;
                    white-space: pre-wrap;
                    margin: 0.9em 0;
                }}
                code {{
                    font-family: "DejaVu Sans Mono", "Consolas", monospace;
                    background: #f6f8fa;
                    border-radius: 4px;
                    padding: 2px 4px;
                }}
                pre code {{ background: transparent; padding: 0; }}
                .source-code-line {{
                    display: block;
                    min-height: 1.55em;
                }}
                blockquote {{
                    border-left: 4px solid #d0d7de;
                    color: #57606a;
                    margin: 0.8em 0;
                    padding-left: 12px;
                }}
                ul, ol {{ margin: 0.4em 0 0.8em 1.4em; }}
                li {{ margin: 0.2em 0; }}
                .task-list-item-checkbox {{
                    margin-right: 0.45em;
                    vertical-align: -0.1em;
                }}
                a {{ color: #0969da; }}
                table {{
                    border-collapse: collapse;
                    margin: 1em 0;
                    width: 100%;
                    overflow: hidden;
                }}
                th, td {{
                    border: 1px solid #d0d7de;
                    padding: 6px 10px;
                    vertical-align: top;
                }}
                th {{
                    background: #f6f8fa;
                    font-weight: 700;
                }}
                tr:nth-child(even) td {{
                    background: #fbfbfc;
                }}
                img {{
                    display: block;
                    max-width: 100%;
                    height: auto;
                    margin: 0.8em 0;
                }}
                .math-inline {{
                    white-space: nowrap;
                }}
                .math-block {{
                    margin: 1em 0;
                    overflow-x: auto;
                }}
            </style>
            <script>
                window.MathJax = {{
                    tex: {{
                        inlineMath: [['\\\\(', '\\\\)']],
                        displayMath: [['\\\\[', '\\\\]']],
                        processEscapes: true
                    }},
                    svg: {{
                        fontCache: 'global'
                    }}
                }};
            </script>
            <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        </head>
        <body>
            {''.join(body)}
        </body>
        </html>
        """

    @staticmethod
    def split_table_row(row):
        """Split a markdown table row, respecting escaped pipe characters."""
        stripped = row.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|") and not stripped.endswith("\\|"):
            stripped = stripped[:-1]

        cells = []
        current = []
        escaped = False
        for char in stripped:
            if escaped:
                current.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "|":
                cells.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        if escaped:
            current.append("\\")
        cells.append(''.join(current).strip())
        return cells

    def render_markdown_html_with_library(self, text, content_base_url=""):
        """Render markdown using Python-Markdown with local preview enhancements."""
        prepared_text = self.preprocess_markdown_extensions(text)
        extensions = [
            'extra',
            'sane_lists',
            'smarty',
            'toc',
            'nl2br',
            'admonition',
            'meta',
        ]

        body_html = markdown_lib.markdown(
            prepared_text,
            extensions=extensions,
            output_format='html5'
        )
        body_html = self.render_mermaid_blocks(body_html)
        body_html = self.add_source_line_anchors(body_html, text)
        body_html = self.add_code_line_anchors(body_html)

        return self.wrap_markdown_preview_html(body_html, content_base_url)

    def render_mermaid_blocks(self, body_html):
        """Convert mermaid fenced code blocks into Mermaid render targets."""
        def replace_mermaid(match):
            attributes = match.group(1) or ""
            diagram_source = html.unescape(match.group(2)).strip()
            if "language-mermaid" not in attributes and "mermaid" not in attributes:
                return match.group(0)
            return self.render_mermaid_block(diagram_source)

        return re.sub(
            r'<pre><code([^>]*)>(.*?)</code></pre>',
            replace_mermaid,
            body_html,
            flags=re.DOTALL
        )

    def render_mermaid_block(self, diagram_source):
        """Render a Mermaid block with the bundled official Mermaid runtime."""
        escaped_source = html.escape(diagram_source)

        return (
            '<div class="mermaid-block">'
            f'<div class="mermaid">{escaped_source}</div>'
            '</div>'
        )

    def get_mermaid_script_content(self):
        """Return the bundled Mermaid renderer source for the preview page."""
        cached_script = getattr(self, '_mermaid_script_content', None)
        if cached_script is not None:
            return cached_script

        mermaid_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'vendor',
            'mermaid.min.js'
        )
        try:
            with open(mermaid_path, 'r', encoding='utf-8') as mermaid_file:
                script_content = mermaid_file.read()
        except OSError:
            script_content = ""

        # Keep the inline script from accidentally closing its own script tag.
        script_content = script_content.replace("</script", "<\\/script")
        self._mermaid_script_content = script_content
        return script_content

    def preprocess_markdown_extensions(self, text):
        """Preprocess syntax that Python-Markdown does not handle by default."""
        text, fenced_blocks = self.stash_fenced_code_blocks(text)
        text = self.preprocess_task_lists(text)
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text, flags=re.DOTALL)
        text = self.apply_typographer_replacements(text)
        text = self.apply_emoji_shortcodes(text)
        text = self.preprocess_math_blocks(text)
        text = re.sub(
            r'(?<!\\)\$(?!\$)(.+?)(?<!\\)\$',
            lambda match: f'<span class="math-inline">\\({html.escape(match.group(1).strip())}\\)</span>',
            text
        )
        text = self.restore_fenced_code_blocks(text, fenced_blocks)
        return text

    @staticmethod
    def stash_fenced_code_blocks(text):
        """Temporarily remove fenced code blocks from markdown preprocessing."""
        lines = text.splitlines(keepends=True)
        processed_lines = []
        fenced_blocks = []
        index = 0

        while index < len(lines):
            line = lines[index]
            match = re.match(r'^([ \t]*)(`{3,}|~{3,})', line)
            if not match:
                processed_lines.append(line)
                index += 1
                continue

            fence_marker = match.group(2)
            fence_char = fence_marker[0]
            fence_length = len(fence_marker)
            block_lines = [line]
            index += 1

            while index < len(lines):
                block_lines.append(lines[index])
                closing = re.match(r'^[ \t]*(%s{%d,})[ \t]*$' % (re.escape(fence_char), fence_length), lines[index])
                index += 1
                if closing:
                    break

            placeholder = f'\u0000JOTTR_FENCED_CODE_{len(fenced_blocks)}\u0000'
            fenced_blocks.append(''.join(block_lines))
            processed_lines.append(placeholder + '\n')

        return ''.join(processed_lines), fenced_blocks

    @staticmethod
    def restore_fenced_code_blocks(text, fenced_blocks):
        """Restore fenced code blocks after markdown preprocessing."""
        for index, block in enumerate(fenced_blocks):
            text = text.replace(f'\u0000JOTTR_FENCED_CODE_{index}\u0000\n', block)
            text = text.replace(f'\u0000JOTTR_FENCED_CODE_{index}\u0000', block)
        return text

    def preprocess_task_lists(self, text):
        """Convert GitHub-style task list markers to disabled checkboxes."""
        processed_lines = []
        task_pattern = re.compile(r'^(\s*(?:[-*+]|\d+[.)])\s+)\[([ xX])\]\s*(.*)$')
        previous_task_indent = None
        previous_task_type = None

        for line in text.splitlines():
            match = task_pattern.match(line)
            if not match:
                processed_lines.append(line)
                if line.strip():
                    previous_task_indent = None
                    previous_task_type = None
                continue

            checked = ' checked' if match.group(2).lower() == 'x' else ''
            checkbox = f'<input class="task-list-item-checkbox" type="checkbox" disabled{checked}>'
            prefix = self.normalize_markdown_list_indent(match.group(1))
            indent = len(re.match(r'^(\s*)', prefix).group(1))
            task_type = "ol" if re.search(r'\d+[.)]\s+$', prefix) else "ul"
            if (processed_lines and previous_task_indent is not None and
                    indent <= previous_task_indent and task_type != previous_task_type):
                processed_lines.append("")
            processed_lines.append(f'{prefix}{checkbox} {match.group(3)}')
            previous_task_indent = indent
            previous_task_type = task_type

        return "\n".join(processed_lines)

    @staticmethod
    def normalize_markdown_list_indent(prefix):
        """Normalize two-space nested list indentation for Python-Markdown."""
        match = re.match(r'^(\s*)((?:[-*+]|\d+[.)])\s+)$', prefix)
        if not match:
            return prefix

        indent = match.group(1)
        marker = match.group(2)
        spaces = len(indent.replace("\t", "    "))
        normalized_indent = " " * ((spaces // 2) * 4)
        return normalized_indent + marker

    def preprocess_math_blocks(self, text):
        """Convert $$ display math blocks to MathJax-friendly HTML."""
        lines = text.splitlines()
        output = []
        math_lines = []
        math_start_line = None
        in_math = False

        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("$$"):
                if in_math:
                    tail = stripped[2:].strip()
                    if tail:
                        math_lines.append(tail)
                    output.append(
                        f'<div class="math-block" data-source-line="{math_start_line or index}">'
                        f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
                    )
                    math_lines = []
                    math_start_line = None
                    in_math = False
                else:
                    after_open = stripped[2:].strip()
                    if after_open.endswith("$$") and len(after_open) > 2:
                        output.append(
                            f'<div class="math-block" data-source-line="{index}">'
                            f'\\[{html.escape(after_open[:-2].strip())}\\]</div>'
                        )
                    else:
                        in_math = True
                        math_start_line = index
                        if after_open:
                            math_lines.append(after_open)
                continue

            if in_math:
                if stripped.endswith("$$"):
                    before_close = line.rstrip()[:-2].strip()
                    if before_close:
                        math_lines.append(before_close)
                    output.append(
                        f'<div class="math-block" data-source-line="{math_start_line or index}">'
                        f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
                    )
                    math_lines = []
                    math_start_line = None
                    in_math = False
                else:
                    math_lines.append(line)
                continue

            output.append(line)

        if in_math:
            output.append(
                f'<div class="math-block" data-source-line="{math_start_line or 1}">'
                f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
            )

        return "\n".join(output)

    @staticmethod
    def apply_emoji_shortcodes(value):
        emoji_map = {
            "smile": "😄", "grinning": "😀", "joy": "😂", "laughing": "😆",
            "wink": "😉", "blush": "😊", "heart": "❤️", "broken_heart": "💔",
            "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎",
            "clap": "👏", "pray": "🙏", "fire": "🔥", "star": "⭐",
            "sparkles": "✨", "rocket": "🚀", "tada": "🎉", "warning": "⚠️",
            "x": "❌", "white_check_mark": "✅", "check": "✅", "information_source": "ℹ️",
            "bulb": "💡", "eyes": "👀", "thinking": "🤔", "cry": "😢",
            "sob": "😭", "angry": "😠", "poop": "💩", "100": "💯",
            "memo": "📝", "book": "📖", "computer": "💻", "gear": "⚙️",
            "bug": "🐛", "lock": "🔒", "unlock": "🔓", "link": "🔗"
        }
        return re.sub(
            r':([a-zA-Z0-9_+\-]+):',
            lambda match: emoji_map.get(match.group(1), match.group(0)),
            value
        )

    def collect_source_anchor_lines(self, text):
        """Collect approximate source lines for rendered block elements."""
        anchors = []
        in_fence = False
        fence_start = None
        in_math = False
        math_start = None

        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("```"):
                if in_fence:
                    in_fence = False
                    fence_start = None
                else:
                    anchors.append(index)
                    in_fence = True
                    fence_start = index
                continue
            if in_fence:
                continue

            if stripped.startswith("$$"):
                if in_math:
                    in_math = False
                    math_start = None
                else:
                    anchors.append(index)
                    in_math = True
                    math_start = index
                continue
            if in_math:
                continue

            if re.match(r'^\|?.+\|.+$', stripped):
                if index == 1 or not re.match(r'^:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?$', stripped):
                    anchors.append(index)
                continue

            anchors.append(index)

        return anchors or [1]

    def add_source_line_anchors(self, body_html, source_text):
        """Attach source-line attributes to block elements for scroll sync."""
        source_lines = iter(self.collect_source_anchor_lines(source_text))

        def add_anchor(match):
            tag = match.group(1)
            attrs = match.group(2) or ""
            if "data-source-line=" in attrs:
                return match.group(0)
            line = next(source_lines, None)
            if line is None:
                return match.group(0)
            return f'<{tag}{attrs} data-source-line="{line}">'

        return re.sub(
            r'<(h[1-6]|p|pre|blockquote|li|table|hr|div)(\s[^>]*)?>',
            add_anchor,
            body_html
        )

    def add_code_line_anchors(self, body_html):
        """Attach source-line attributes to individual rendered code lines."""
        def replace_pre(match):
            pre_attrs = match.group(1) or ""
            code_attrs = match.group(2) or ""
            code_text = match.group(3)
            line_match = re.search(r'data-source-line="(\d+)"', pre_attrs)
            if not line_match or 'class="source-code-line"' in code_text:
                return match.group(0)

            source_line = int(line_match.group(1))
            span_start_line = source_line + 1 if "language-" in code_attrs else source_line
            lines = code_text.splitlines()
            if not lines:
                return match.group(0)

            spans = []
            for offset, value in enumerate(lines):
                spans.append(
                    f'<span class="source-code-line" data-source-line="{span_start_line + offset}">'
                    f'{value or " "}</span>'
                )
            return f'<pre{pre_attrs}><code{code_attrs}>{"".join(spans)}</code></pre>'

        return re.sub(
            r'<pre([^>]*)><code([^>]*)>(.*?)</code></pre>',
            replace_pre,
            body_html,
            flags=re.DOTALL
        )

    def wrap_markdown_preview_html(self, body_html, content_base_url=""):
        """Wrap rendered body HTML in Jottr preview CSS and scripts."""
        mermaid_script_content = self.get_mermaid_script_content()
        base_tag = f'<base href="{html.escape(content_base_url, quote=True)}">' if content_base_url else ''
        preview_font = QFont(getattr(self, "current_font", self.editor.font()))
        preview_family = html.escape(preview_font.family().replace("\\", "\\\\").replace('"', '\\"'), quote=True)
        preview_size = max(8, preview_font.pointSize() if preview_font.pointSize() > 0 else 14)
        return f"""
        <html>
        <head>
            {base_tag}
            <style>
                body {{
                    color: #202124;
                    font-family: "{preview_family}", "Segoe UI", sans-serif;
                    font-size: {preview_size}pt;
                    line-height: 1.55;
                    margin: 18px;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #111827;
                    font-weight: 700;
                    margin: 1.1em 0 0.45em;
                }}
                h1 {{ font-size: 30px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
                h2 {{ font-size: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 4px; }}
                h3 {{ font-size: 20px; }}
                h4 {{ font-size: 17px; }}
                h5 {{ font-size: 15px; }}
                h6 {{ font-size: 14px; color: #57606a; }}
                p {{ margin: 0 0 0.8em; }}
                pre {{
                    background: #f6f8fa;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    padding: 12px;
                    white-space: pre-wrap;
                    margin: 0.9em 0;
                }}
                code {{
                    font-family: "{preview_family}", "Consolas", monospace;
                    background: #f6f8fa;
                    border-radius: 4px;
                    padding: 2px 4px;
                }}
                pre code {{ background: transparent; padding: 0; }}
                blockquote {{
                    border-left: 4px solid #d0d7de;
                    color: #57606a;
                    margin: 0.8em 0;
                    padding-left: 12px;
                }}
                ul, ol {{ margin: 0.4em 0 0.8em 1.4em; }}
                li {{ margin: 0.2em 0; }}
                .task-list-item-checkbox {{
                    margin-right: 0.45em;
                    vertical-align: -0.1em;
                }}
                a {{ color: #0969da; }}
                table {{
                    border-collapse: collapse;
                    margin: 1em 0;
                    width: 100%;
                    overflow: hidden;
                }}
                th, td {{
                    border: 1px solid #d0d7de;
                    padding: 6px 10px;
                    vertical-align: top;
                }}
                th {{
                    background: #f6f8fa;
                    font-weight: 700;
                }}
                tr:nth-child(even) td {{
                    background: #fbfbfc;
                }}
                img {{
                    display: block;
                    max-width: 100%;
                    height: auto;
                    margin: 0.8em 0;
                }}
                .math-inline {{
                    white-space: nowrap;
                }}
                .math-block {{
                    margin: 1em 0;
                    overflow-x: auto;
                }}
                .admonition {{
                    border-left: 4px solid #0969da;
                    background: #f6f8fa;
                    padding: 10px 14px;
                    margin: 1em 0;
                }}
                .admonition-title {{
                    font-weight: 700;
                    margin-top: 0;
                }}
                .mermaid {{
                    background: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    margin: 1em 0;
                    padding: 12px;
                    overflow-x: auto;
                    text-align: center;
                }}
                .mermaid-svg {{
                    display: block;
                    height: auto;
                    max-width: 100%;
                    min-width: 220px;
                }}
                .mermaid svg {{
                    display: inline-block;
                    max-width: 100%;
                }}
                .mermaid-error {{
                    color: #b42318;
                    font-family: "DejaVu Sans Mono", "Consolas", monospace;
                    text-align: left;
                    white-space: pre-wrap;
                }}
            </style>
            <script>
                window.MathJax = {{
                    tex: {{
                        inlineMath: [['\\\\(', '\\\\)']],
                        displayMath: [['\\\\[', '\\\\]']],
                        processEscapes: true
                    }},
                    svg: {{
                        fontCache: 'global'
                    }}
                }};
            </script>
            <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
            <script>
                {mermaid_script_content}
            </script>
            <script>
                async function renderMermaidDiagrams() {{
                    if (!window.mermaid) {{
                        document.querySelectorAll('.mermaid').forEach(function (diagram) {{
                            diagram.classList.add('mermaid-error');
                            diagram.textContent = 'Mermaid runtime could not be loaded.\\n\\n' + diagram.textContent;
                        }});
                        return;
                    }}

                    try {{
                        mermaid.initialize({{
                            startOnLoad: false,
                            securityLevel: 'loose',
                            theme: 'default'
                        }});

                        function renderDiagram(renderId, source, diagram) {{
                            return new Promise(function (resolve, reject) {{
                                try {{
                                    if (mermaid.render.length >= 3) {{
                                        mermaid.render(renderId, source, function (svg, bindFunctions) {{
                                            resolve({{
                                                svg: svg,
                                                bindFunctions: bindFunctions
                                            }});
                                        }}, diagram);
                                        return;
                                    }}

                                    Promise.resolve(mermaid.render(renderId, source)).then(function (result) {{
                                        if (typeof result === 'string') {{
                                            resolve({{
                                                svg: result,
                                                bindFunctions: null
                                            }});
                                        }} else {{
                                            resolve(result);
                                        }}
                                    }}).catch(reject);
                                }} catch (error) {{
                                    reject(error);
                                }}
                            }});
                        }}

                        var diagrams = Array.prototype.slice.call(document.querySelectorAll('.mermaid'));
                        for (var index = 0; index < diagrams.length; index += 1) {{
                            var diagram = diagrams[index];
                            if (diagram.dataset.rendered === 'true') {{
                                continue;
                            }}

                            var source = diagram.textContent;
                            var renderId = 'jottr-mermaid-' + Date.now() + '-' + index;
                            try {{
                                var result = await renderDiagram(renderId, source, diagram);
                                diagram.innerHTML = result.svg;
                                diagram.dataset.rendered = 'true';
                                diagram.classList.remove('mermaid-error');
                                if (result.bindFunctions) {{
                                    result.bindFunctions(diagram);
                                }}
                            }} catch (error) {{
                                diagram.classList.add('mermaid-error');
                                diagram.textContent = 'Mermaid render error: ' + error.message + '\\n\\n' + source;
                            }}
                        }}
                    }} catch (error) {{
                        console.error('Mermaid render failed', error);
                    }}
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', renderMermaidDiagrams);
                }} else {{
                    renderMermaidDiagrams();
                }}

                window.addEventListener('load', renderMermaidDiagrams);
            </script>
        </head>
        <body>
            {body_html}
        </body>
        </html>
        """

    @staticmethod
    def apply_typographer_replacements(value):
        """Apply common markdown typographer replacements."""
        replacements = {
            "(c)": "©",
            "(C)": "©",
            "(r)": "®",
            "(R)": "®",
            "(tm)": "™",
            "(TM)": "™",
            "+-": "±",
        }
        for source, replacement in replacements.items():
            value = value.replace(source, replacement)
        return value

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

    def toggle_pane(self, pane_type):
        """Toggle visibility of side panes"""
        if pane_type == "snippets":
            self.snippet_widget.setVisible(not self.snippet_widget.isVisible())
            # If showing snippets, make sure it has reasonable size
            if self.snippet_widget.isVisible():
                current_sizes = self.splitter.sizes()
                if current_sizes[1] < 100:  # If snippet pane is too small
                    editor_size = current_sizes[0]
                    new_snippet_size = int(editor_size * 0.2)  # 20% for snippets
                    new_editor_size = editor_size - new_snippet_size
                    self.splitter.setSizes([new_editor_size, new_snippet_size, current_sizes[2]])
                    
        elif pane_type == "browser":
            is_visible = self.browser_widget.isVisible()
            
            if is_visible:
                # If currently visible, hide it and destroy web view
                self.browser_widget.setVisible(False)
                if self.web_view:
                    self.web_view.stop()
                    self.web_view.setParent(None)
                    self.web_view.deleteLater()
                    self.web_view = None
                    
                    # Clear the container layout
                    while self.web_container.layout().count():
                        item = self.web_container.layout().takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
            else:
                # If showing browser, make sure it has reasonable size first
                current_sizes = self.splitter.sizes()
                if current_sizes[2] < 100:
                    editor_size = current_sizes[0]
                    new_browser_size = int(editor_size * 0.3)
                    new_editor_size = editor_size - new_browser_size
                    self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
                self.browser_widget.setVisible(True)
                
                # Create web view and load URL
                self.create_web_view()
                if hasattr(self, '_pending_url'):
                    self.web_view.setUrl(QUrl(self._pending_url))
                    del self._pending_url
                else:
                    homepage = self.settings_manager.get_setting('homepage', 'https://www.apnews.com/')
                    self.web_view.setUrl(QUrl(homepage))
        
        # Track if pane was opened during focus mode
        if self.focus_mode:
            if pane_type == "browser":
                # Only track as opened if we're showing it
                self.panes_opened_in_focus['browser'] = self.browser_widget.isVisible()
            elif pane_type == "snippets":
                self.panes_opened_in_focus['snippets'] = self.snippet_widget.isVisible()
        
        # Save states after toggle
        self.save_pane_states()

    def setup_browser_shortcuts(self):
        """Setup standard shortcuts for the web browser"""
        if not self.web_view:
            return
            
        # Copy
        copy_action = QAction(self.web_view)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        copy_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.WebAction.Copy))
        self.web_view.addAction(copy_action)
        
        # Cut
        cut_action = QAction(self.web_view)
        cut_action.setShortcut(QKeySequence("Ctrl+X"))
        cut_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        cut_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.WebAction.Cut))
        self.web_view.addAction(cut_action)
        
        # Paste
        paste_action = QAction(self.web_view)
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        paste_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.WebAction.Paste))
        self.web_view.addAction(paste_action)
        
    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def setup_browser_toolbar(self):
        """Setup browser toolbar with navigation controls"""
        # Browser toolbar
        toolbar = QWidget()
        toolbar.setObjectName("browserToolbar")
        toolbar.setFixedHeight(40)
        
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(5)
        
        # Navigation buttons
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedSize(28, 28)
        self.back_btn.setEnabled(False)  # Initially disabled
        toolbar_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedSize(28, 28)
        self.forward_btn.setEnabled(False)  # Initially disabled
        toolbar_layout.addWidget(self.forward_btn)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        toolbar_layout.addWidget(self.url_bar)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(QFont("Arial", 14))
        close_btn.clicked.connect(lambda: self.toggle_pane("browser"))
        toolbar_layout.addWidget(close_btn)
        
        # Add toolbar to browser layout
        self.browser_widget.layout().addWidget(toolbar)

    def update_status(self):
        """Update word and character count"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return
        
        text = self.editor.toPlainText()
        
        # Update word count (split by whitespace and filter empty strings)
        words = len([word for word in text.split() if word.strip()])
        chars = len(text)
        
        # Update status bar
        self.main_window.statusBar.showMessage(f"Words: {words} | Characters: {chars}")

    def toggle_focus_mode(self):
        """Toggle focus mode"""
        if not hasattr(self, 'focus_mode'):
            self.focus_mode = False
            
        self.focus_mode = not self.focus_mode
        
        if self.focus_mode:
            self.enable_focus_mode()
        else:
            self.disable_focus_mode()

    def enable_focus_mode(self):
        """Enable focus mode"""
        self.focus_mode = True
        if self.main_window and hasattr(self.main_window, 'update_focus_mode_action'):
            self.main_window.update_focus_mode_action(True)
        
        # Store current window state
        window = self.window()
        self.pre_focus_state = window.windowState()
        
        # Store current pane states
        self.pre_focus_states = {
            'snippets_visible': self.snippet_widget.isVisible(),
            'browser_visible': self.browser_widget.isVisible(),
            'sizes': self.splitter.sizes()
        }
        
        # Hide UI elements
        window.toolbar.hide()
        window.tab_widget.tabBar().hide()
        
        # Hide panes
        self.snippet_widget.hide()
        self.browser_widget.hide()
        self.editor_pane.setMaximumWidth(900)
        self.editor_pane.setStyleSheet("""
            QWidget#editorPane {
                background: #eef3f8;
            }
            QTextEdit#writingEditor {
                background: #ffffff;
                border: 1px solid #d7e0ea;
                border-radius: 3px;
                padding: 36px 48px;
                font-size: 15pt;
            }
        """)
        
        # Add exit button
        self.exit_focus_btn = QPushButton("Exit Focus Mode", self)
        self.exit_focus_btn.clicked.connect(self.disable_focus_mode)
        self.exit_focus_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 9px 16px;
                min-width: 120px;
                min-height: 32px;
                color: #17202a;
            }
            QPushButton:hover {
                background: #eaf3ff;
                border-color: #9fc8f7;
            }
        """)
        self.update_exit_button_position()
        self.exit_focus_btn.show()
        
        # Set fullscreen
        window.setWindowState(window.windowState() | Qt.WindowState.WindowFullScreen)

    def disable_focus_mode(self):
        """Disable focus mode"""
        self.focus_mode = False
        if self.main_window and hasattr(self.main_window, 'update_focus_mode_action'):
            self.main_window.update_focus_mode_action(False)
        
        window = self.window()
        
        # Remove fullscreen flag while preserving other states
        new_state = window.windowState() & ~Qt.WindowState.WindowFullScreen
        if self.pre_focus_state & Qt.WindowState.WindowMaximized:
            new_state |= Qt.WindowState.WindowMaximized
            
        # Apply the state change
        window.setWindowState(new_state)
        
        # Show UI elements
        window.toolbar.show()
        window.tab_widget.tabBar().show()
        self.editor_pane.setMaximumWidth(16777215)
        self.editor_pane.setStyleSheet("")
        self.apply_workspace_style()
        
        # Remove exit button
        if hasattr(self, 'exit_focus_btn'):
            self.exit_focus_btn.deleteLater()
            del self.exit_focus_btn
        
        # Restore pane states
        if hasattr(self, 'pre_focus_states'):
            browser_should_be_visible = (self.pre_focus_states['browser_visible'] or
                                       self.browser_widget.isVisible() or
                                       self.panes_opened_in_focus['browser'])
            
            self.snippet_widget.setVisible(self.pre_focus_states['snippets_visible'])
            self.browser_widget.setVisible(browser_should_be_visible)
            
            # Calculate proper sizes
            total_width = sum(self.pre_focus_states['sizes'])
            if browser_should_be_visible:
                editor_ratio = 0.7
                browser_ratio = 0.3
                snippet_width = self.pre_focus_states['sizes'][1] if self.pre_focus_states['snippets_visible'] else 0
                
                editor_width = int(total_width * editor_ratio) - (snippet_width // 2)
                browser_width = int(total_width * browser_ratio)
                
                self.splitter.setSizes([editor_width, snippet_width, browser_width])
            else:
                self.splitter.setSizes(self.pre_focus_states['sizes'])

    def update_exit_button_position(self):
        """Update exit button position based on current window size"""
        if hasattr(self, 'exit_focus_btn'):
            margin = 20
            self.exit_focus_btn.move(
                self.width() - self.exit_focus_btn.width() - margin,
                self.height() - self.exit_focus_btn.height() - margin
            )

    def resizeEvent(self, event):
        """Handle resize events to keep exit button positioned correctly"""
        super().resizeEvent(event)
        if hasattr(self, 'focus_mode') and self.focus_mode:
            self.update_exit_button_position()

    def handle_escape(self):
        """Handle ESC key press"""
        if self.suggestion_tooltip:
            self.suggestion_tooltip.hide()
            self.suggestion_tooltip.deleteLater()
            self.suggestion_tooltip = None
            return
            
        if self.focus_mode:
            self.disable_focus_mode()
            # Update menu if possible
            if hasattr(self, 'main_window'):
                # Try to update focus mode action if method exists
                if hasattr(self.main_window, 'update_focus_mode_action'):
                    self.main_window.update_focus_mode_action(False)
                # Otherwise just update the View menu if it exists
                elif hasattr(self.main_window, 'view_menu'):
                    for action in self.main_window.view_menu.actions():
                        if action.text() == "Focus Mode":
                            action.setChecked(False)
                            break

    def toggle_find(self):
        """Toggle find/replace toolbar visibility"""
        visible = not self.find_toolbar.isVisible()
        self.find_toolbar.setVisible(visible)
        if visible:
            self.find_input.setFocus()
            # Select text if any is selected
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                self.find_input.setText(cursor.selectedText())
                self.find_input.selectAll()
        else:
            # Clear highlighting when closing
            self.clear_highlights()
            self.editor.setFocus()

        # Update the search action state in the main toolbar if it exists
        if hasattr(self, 'main_window'):
            for action in self.main_window.toolbar.actions():
                if action.text() == "Find/Replace":
                    action.setChecked(visible)
                    break

    def find_text(self, direction='down'):
        """Find text in editor"""
        text = self.find_input.text()
        if not text:
            return
            
        cursor = self.editor.textCursor()
        document = self.editor.document()
        
        # Create find flags
        flags = QTextDocument.FindFlag(0)
        if direction == 'up':
            flags |= QTextDocument.FindFlag.FindBackward
            
        # Remove case sensitivity flag to make search case-insensitive
        # flags |= QTextDocument.FindFlag.FindCaseSensitively  # Commented out to make case-insensitive
            
        # Find next occurrence
        if not self.editor.find(text, flags):
            # If not found, wrap around
            cursor = QTextCursor(document)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, flags)

    def replace_text(self):
        """Replace current occurrence"""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        
        if not find_text:
            return
        
        cursor = self.editor.textCursor()
        
        # If no text is selected, find next occurrence first
        if not cursor.hasSelection():
            self.find_text()
            cursor = self.editor.textCursor()
        
        # Check if we have a valid selection that matches the search text (case-insensitive)
        if cursor.hasSelection() and cursor.selectedText().lower() == find_text.lower():
            cursor.beginEditBlock()
            cursor.insertText(replace_text)
            cursor.endEditBlock()
            # Find next occurrence
            self.find_text()

    def replace_all(self):
        """Replace all occurrences"""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        
        if not find_text:
            return
        
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        
        # Move to start
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        
        # Create find flags for case-insensitive search
        flags = QTextDocument.FindFlag(0)
        # flags |= QTextDocument.FindFlag.FindCaseSensitively  # Commented out to make case-insensitive
        
        # Replace all occurrences
        count = 0
        while self.editor.find(find_text, flags):
            cursor = self.editor.textCursor()
            cursor.insertText(replace_text)
            count += 1
        
        cursor.endEditBlock()
        
        # Show message with count
        QMessageBox.information(self, "Replace All", f"Replaced {count} occurrence{'s' if count != 1 else ''}")
        
        # Move cursor back to start
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)

    def clear_highlights(self):
        """Clear any search highlighting"""
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)

    def create_context_menu(self, position):
        """Create context menu for editor"""
        menu = QMenu(self)
        
        # Cut/Copy/Paste actions
        cut_action = menu.addAction("Cut")
        cut_action.triggered.connect(self.editor.cut)
        cut_action.setShortcut("Ctrl+X")
        
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.editor.copy)
        copy_action.setShortcut("Ctrl+C")
        
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self.editor.paste)
        paste_action.setShortcut("Ctrl+V")
        
        # Add separator before Select All
        menu.addSeparator()
        
        # Add Select All action
        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.editor.selectAll)
        select_all_action.setShortcut("Ctrl+A")
        
        # Show menu at cursor position
        menu.exec(self.editor.mapToGlobal(position))

    def handle_text_changed(self):
        """Handle text changes for autocompletion"""
        if self.suggestion_tooltip:
            self.suggestion_tooltip.hide()
            self.suggestion_tooltip.deleteLater()
            self.suggestion_tooltip = None
            
        cursor = self.editor.textCursor()
        current_line = cursor.block().text()
        current_position = cursor.positionInBlock()
        
        # Find the word being typed
        word_start = current_position
        while word_start > 0 and (current_line[word_start - 1].isalnum() or 
                                 current_line[word_start - 1] in '_-'):
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
            'snippets_visible': self.snippet_widget.isVisible(),
            'browser_visible': self.browser_widget.isVisible(),
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
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
            QLabel {
                padding: 2px 8px;
                color: palette(text);
                border-radius: 2px;
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
        
        # Position tooltip below the cursor
        rect = self.editor.cursorRect(cursor)
        pos = self.editor.mapToGlobal(rect.bottomLeft())
        pos.setY(pos.y() + 5)  # Add a small offset
        self.suggestion_tooltip.move(pos)
        
        # Calculate and set fixed size
        self.suggestion_tooltip.adjustSize()
        
        # Show tooltip
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
                    border-radius: 2px;
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
        
        # Find start of current word
        start = pos
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '_'):
            start -= 1
            
        # Find if this is a snippet or word suggestion
        is_snippet = False
        for suggestion_type, title in self.current_suggestions:
            if title == suggestion:
                is_snippet = (suggestion_type == 'snippet')
                break
        
        # Replace the current word
        cursor.movePosition(cursor.StartOfBlock)
        cursor.movePosition(cursor.Right, cursor.MoveAnchor, start)
        cursor.movePosition(cursor.Right, cursor.KeepAnchor, pos - start)
        
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

        # Find start of word (including alphanumeric and underscores)
        start = pos
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '_'):
            start -= 1

        # Find end of word (including alphanumeric and underscores)
        end = pos
        while end < len(text) and (text[end].isalnum() or text[end] == '_'):
            end += 1

        # Select and replace the word
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, cursor.KeepAnchor)
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

    def update_nav_buttons(self):
        """Update navigation button states"""
        if self.web_view:
            self.back_btn.setEnabled(self.web_view.page().action(QWebEnginePage.WebAction.Back).isEnabled())
            self.forward_btn.setEnabled(self.web_view.page().action(QWebEnginePage.WebAction.Forward).isEnabled())

    def handle_navigation(self, navigation_type, url):
        """Handle navigation requests"""
        # Update navigation buttons
        self.update_nav_buttons()
        return True  # Allow navigation

    def navigate_url(self):
        """Navigate to URL in browser"""
        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.web_view.setUrl(QUrl(url))
