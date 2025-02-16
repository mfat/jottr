import os
import sys

# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTextEdit, QListWidget, QInputDialog, QMenu, QFileDialog, QDialog,
                            QToolBar, QAction, QCompleter, QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel, QShortcut, QToolTip)
from PyQt5.QtCore import Qt, QUrl, QTimer, QStringListModel, QRegExp, QEvent
from PyQt5.QtGui import (QTextCharFormat, QSyntaxHighlighter, QIcon, QFont, QKeySequence, 
                        QPainter, QPen, QColor, QFontMetrics, QTextDocument, QTextCursor)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from enchant import Dict, DictNotFoundError
from urllib.parse import quote
from snippet_editor_dialog import SnippetEditorDialog
import os
from rss_reader import RSSReader
import json
import time
from theme_manager import ThemeManager
import hashlib

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        try:
            # Initialize enchant with English dictionary
            self.spell = Dict("en_US")
            self.spell_check_enabled = True
            print("Spell checking enabled")
            
        except DictNotFoundError as e:
            print(f"Warning: Spell checking disabled - {str(e)}")
            self.spell_check_enabled = False

    def is_latin_word(self, word):
        """Check if word contains only Latin characters"""
        try:
            word.encode('latin-1')
            return True
        except UnicodeEncodeError:
            return False

    def highlightBlock(self, text):
        if not self.spell_check_enabled:
            return

        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        format = QTextCharFormat()
        format.setUnderlineColor(Qt.red)
        format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)

        # For each word in the text
        expression = QRegExp("\\b\\w+\\b")
        index = expression.indexIn(text)
        while index >= 0:
            word = expression.cap()
            length = len(word)
            
            # Only spell check Latin words
            if self.is_latin_word(word):
                # Check if word is in user dictionary first
                if word not in user_dict:
                    # If not in user dictionary, check against enchant
                    try:
                        if not self.spell.check(word):
                            self.setFormat(index, length, format)
                    except UnicodeEncodeError:
                        pass  # Skip words that can't be encoded
            
            index = expression.indexIn(text, index + length)

    def suggest(self, word):
        """Get suggestions for a word, including user dictionary matches"""
        suggestions = []
        
        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        # Add matching words from user dictionary first
        for dict_word in user_dict:
            if dict_word.lower().startswith(word.lower()):
                suggestions.append(dict_word)
        
        # Only get enchant suggestions for Latin words
        if self.is_latin_word(word):
            try:
                # Get suggestions from enchant
                spell_suggestions = self.spell.suggest(word)
                if spell_suggestions:
                    # Remove the word itself from suggestions
                    spell_suggestions = [s for s in spell_suggestions if s.lower() != word.lower()]
                    suggestions.extend(spell_suggestions)
            except UnicodeEncodeError:
                pass
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(suggestions))

    def add_to_dictionary(self, word):
        """Add word to user dictionary"""
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)
            # Add to enchant personal word list
            self.spell.add(word)
            # Refresh spell checking
            self.rehighlight()

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.completer = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)
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
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                # Get the current completion
                current = self.completer.currentCompletion()
                if current:
                    # Insert the completion
                    self.insertCompletion(current)
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() == Qt.Key_Escape:
                self.completer.popup().hide()
                event.accept()
                return
                
        super().keyPressEvent(event)

class CompletingTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.completion_text = ""
        self.completion_start = None
        self.suppress_completion = False
        
    def keyPressEvent(self, event):
        """Handle key events"""
        # Handle suggestion navigation if parent has suggestions
        if (self.parent_tab and 
            self.parent_tab.suggestion_tooltip and 
            self.parent_tab.current_suggestions):
            
            if event.key() == Qt.Key_Down:
                self.parent_tab.select_next_suggestion()
                event.accept()
                return
            elif event.key() == Qt.Key_Up:
                self.parent_tab.select_previous_suggestion()
                event.accept()
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.parent_tab.selected_suggestion_index >= 0:
                    suggestion_type, text = self.parent_tab.current_suggestions[self.parent_tab.selected_suggestion_index]
                    self.parent_tab.apply_suggestion(text)
                event.accept()
                return
            elif event.key() == Qt.Key_Tab:
                # If there's only one suggestion, apply it
                if len(self.parent_tab.current_suggestions) == 1:
                    suggestion_type, text = self.parent_tab.current_suggestions[0]
                    self.parent_tab.apply_suggestion(text)
                # If there are multiple suggestions, cycle through them
                else:
                    # Always select next suggestion, wrapping around to first if at end
                    if self.parent_tab.selected_suggestion_index < 0:
                        self.parent_tab.selected_suggestion_index = 0
                    else:
                        self.parent_tab.select_next_suggestion()
                    # Update the highlighting
                    self.parent_tab.update_suggestion_highlighting()
                event.accept()
                return
            elif event.key() == Qt.Key_Escape:
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

class EditorTab(QWidget):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.current_font = self.settings_manager.get_font()
        self.web_view = None  # Initialize to None
        self.main_window = None  # Initialize main_window to None
        
        # Initialize recovery ID and paths first
        self.recovery_id = str(int(time.time() * 1000))
        self.session_path = os.path.join(
            self.settings_manager.get_recovery_dir(),
            f"session_{self.recovery_id}.txt"
        )
        self.meta_path = self.session_path + '.json'
        
        # Setup UI components
        self.setup_ui()
        
        # Setup autosave after UI is ready
        self.last_save_time = time.time()
        self.changes_pending = False
        
        # Start periodic backup timer
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.force_save)
        self.backup_timer.start(5000)  # Backup every 5 seconds
        
        # Apply theme
        ThemeManager.apply_theme(self.editor, self.settings_manager.get_theme())
        
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
        
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for editor and side panes
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create text editor with default font
        self.editor = CompletingTextEdit(self)  # Pass self as parent
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.update_font(self.current_font)
        
        # Connect text changed signal to update status
        self.editor.textChanged.connect(self.update_status)
        
        # Create spell checker
        self.highlighter = SpellCheckHighlighter(self.editor.document(), self.settings_manager)
        
        # Add editor to splitter
        self.splitter.addWidget(self.editor)
        
        # Create snippet widget
        self.snippet_widget = QWidget()
        snippet_layout = QVBoxLayout(self.snippet_widget)
        snippet_layout.setContentsMargins(0, 0, 0, 0)
        
        # Snippet header
        snippet_header = QWidget()
        snippet_header.setFixedHeight(28)  # Match browser toolbar height
        snippet_header.setStyleSheet("""
            QWidget {
                background-color: palette(window);
                padding: 0px;
                margin: 0px;
            }
            QPushButton {
                border: none;
                padding: 0px;
                margin: 0px;
                color: palette(text);
            }
            QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        header_layout = QHBoxLayout(snippet_header)
        header_layout.setContentsMargins(4, 2, 4, 2)  # Tight margins to match browser toolbar
        header_layout.setSpacing(4)  # Reduce spacing between widgets
        
        snippet_title = QLabel("Snippets")
        snippet_title.setStyleSheet("font-weight: bold; padding: 0px; margin: 0px;")
        header_layout.addWidget(snippet_title)
        
        snippet_close = QPushButton("×")
        snippet_close.setFixedSize(20, 20)
        snippet_close.clicked.connect(lambda: self.toggle_pane("snippets"))
        header_layout.addWidget(snippet_close)
        
        snippet_layout.addWidget(snippet_header)
        
        # Snippet list
        self.snippet_list = QListWidget()
        self.snippet_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: palette(base);
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:hover {
                background-color: palette(alternate-base);
            }
        """)
        self.snippet_list.itemDoubleClicked.connect(self.insert_snippet)
        self.snippet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_list.customContextMenuRequested.connect(self.show_snippet_context_menu)
        self.update_snippet_list()  # Populate the list
        snippet_layout.addWidget(self.snippet_list)
        
        # Create browser widget without web view
        self.browser_widget = QWidget()
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
        
        # Hide side panes by default
        self.snippet_widget.hide()
        self.browser_widget.hide()
        
        # Restore pane states
        states = self.settings_manager.get_setting('pane_states', {
            'snippets_visible': False,
            'browser_visible': False,
            'sizes': [700, 300, 300]
        })
        
        # Apply visibility
        self.snippet_widget.setVisible(states.get('snippets_visible', False))
        self.browser_widget.setVisible(states.get('browser_visible', False))
        
        # Apply sizes
        if 'sizes' in states:
            self.splitter.setSizes(states['sizes'])
        
        # Connect splitter moved signal to save states
        self.splitter.splitterMoved.connect(self.save_pane_states)
        
        # Set focus to editor
        self.editor.setFocus()
        
        # Create find/replace toolbar (initially hidden)
        self.find_toolbar = QWidget(self)
        self.find_toolbar.setVisible(False)
        self.find_toolbar.setFixedHeight(32)  # Set fixed compact height
        find_layout = QHBoxLayout(self.find_toolbar)
        find_layout.setContentsMargins(4, 2, 4, 2)  # Reduce vertical margins
        find_layout.setSpacing(4)  # Reduce spacing between elements
        
        # Find input
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.textChanged.connect(self.find_text)
        self.find_input.setFixedHeight(24)  # Set fixed height for input
        find_layout.addWidget(self.find_input)
        
        # Replace input
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.setFixedHeight(24)  # Set fixed height for input
        find_layout.addWidget(self.replace_input)
        
        # Find next/previous buttons
        self.find_prev_btn = QPushButton("↑")
        self.find_next_btn = QPushButton("↓")
        self.find_prev_btn.setFixedSize(24, 24)  # Make buttons square and compact
        self.find_next_btn.setFixedSize(24, 24)
        self.find_prev_btn.clicked.connect(lambda: self.find_text(direction='up'))
        self.find_next_btn.clicked.connect(lambda: self.find_text(direction='down'))
        find_layout.addWidget(self.find_prev_btn)
        find_layout.addWidget(self.find_next_btn)
        
        # Replace buttons
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("All")  # Shortened text
        self.replace_btn.setFixedHeight(24)
        self.replace_all_btn.setFixedHeight(24)
        self.replace_btn.clicked.connect(self.replace_text)
        self.replace_all_btn.clicked.connect(self.replace_all)
        find_layout.addWidget(self.replace_btn)
        find_layout.addWidget(self.replace_all_btn)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.toggle_find)
        find_layout.addWidget(close_btn)
        
        # Add styling
        self.find_toolbar.setStyleSheet("""
            QWidget {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QLineEdit {
                border: 1px solid palette(mid);
                border-radius: 2px;
                padding: 2px 4px;
                background: palette(base);
            }
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 2px;
                padding: 2px 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: palette(light);
            }
        """)
        
        layout.addWidget(self.find_toolbar)
        
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
                "Text Files (*.txt);;All Files (*.*)"
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
                                                 "Text Files (*.txt);;All Files (*)")
        if file_name:
            self.current_file = file_name
            with open(file_name, 'r') as file:
                self.editor.setPlainText(file.read())
            
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
        
        menu = QMenu(self)
        
        # Cut/Copy/Paste actions
        menu.addAction("Cut", self.editor.cut)
        menu.addAction("Copy", self.editor.copy)
        menu.addAction("Paste", self.editor.paste)
        menu.addSeparator()
        
        # Get selected text
        selected_text = cursor.selectedText()
        
        if selected_text:
            # Add "Save as Snippet" option
            menu.addAction("Save as Snippet", lambda: self.save_snippet(selected_text))
            menu.addSeparator()
            
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
        
        # Show menu
        menu.exec_(self.editor.mapToGlobal(pos))

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
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)
            # Add to enchant personal word list
            self.highlighter.spell.add(word)
            # Refresh spell checking
            self.highlighter.rehighlight()

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
        if dialog.exec_() == QDialog.Accepted:
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
            menu.exec_(self.snippet_list.mapToGlobal(position))

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
        self.current_font.setWeight(QFont.Normal)  # Force Regular weight
        
        # Update font for the editor
        self.editor.setFont(self.current_font)
        
        # Store font properties in the editor's stylesheet
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                font-family: {self.current_font.family()};
                font-size: {self.current_font.pointSize()}pt;
                font-weight: normal;  /* Force Regular weight in stylesheet too */
                font-style: {('italic' if self.current_font.italic() else 'normal')};
                background-color: {self.editor.palette().base().color().name()};
                color: {self.editor.palette().text().color().name()};
                selection-background-color: {self.editor.palette().highlight().color().name()};
            }}
        """)

    def apply_theme(self, theme_name):
        """Apply theme while preserving font properties"""
        self.settings_manager.save_theme(theme_name)
        ThemeManager.apply_theme(self.editor, theme_name)
        
        # After applying theme, reapply font to ensure properties are preserved
        if hasattr(self, 'current_font'):
            self.update_font(self.current_font)

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
        copy_action.setShortcutContext(Qt.WidgetShortcut)
        copy_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Copy))
        self.web_view.addAction(copy_action)
        
        # Cut
        cut_action = QAction(self.web_view)
        cut_action.setShortcut(QKeySequence("Ctrl+X"))
        cut_action.setShortcutContext(Qt.WidgetShortcut)
        cut_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Cut))
        self.web_view.addAction(cut_action)
        
        # Paste
        paste_action = QAction(self.web_view)
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.setShortcutContext(Qt.WidgetShortcut)
        paste_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Paste))
        self.web_view.addAction(paste_action)
        
    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def setup_browser_toolbar(self):
        """Setup browser toolbar with navigation controls"""
        # Browser toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet("""
            QWidget {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QLineEdit {
                border: 1px solid palette(mid);
                border-radius: 3px;
                padding: 2px 8px;
                background: palette(base);
                selection-background-color: palette(highlight);
                margin: 4px;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
                color: palette(text);
            }
            QPushButton:hover {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 0, 4, 0)
        toolbar_layout.setSpacing(2)
        
        # Navigation buttons
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedSize(24, 24)
        self.back_btn.setEnabled(False)  # Initially disabled
        toolbar_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedSize(24, 24)
        self.forward_btn.setEnabled(False)  # Initially disabled
        toolbar_layout.addWidget(self.forward_btn)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        toolbar_layout.addWidget(self.url_bar)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
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
        
        # Add exit button
        self.exit_focus_btn = QPushButton("Exit Focus Mode", self)
        self.exit_focus_btn.clicked.connect(self.disable_focus_mode)
        self.exit_focus_btn.setStyleSheet("""
            QPushButton {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        self.update_exit_button_position()
        self.exit_focus_btn.show()
        
        # Set fullscreen
        window.setWindowState(window.windowState() | Qt.WindowFullScreen)

    def disable_focus_mode(self):
        """Disable focus mode"""
        self.focus_mode = False
        
        window = self.window()
        
        # Remove fullscreen flag while preserving other states
        new_state = window.windowState() & ~Qt.WindowFullScreen
        if self.pre_focus_state & Qt.WindowMaximized:
            new_state |= Qt.WindowMaximized
            
        # Apply the state change
        window.setWindowState(new_state)
        
        # Show UI elements
        window.toolbar.show()
        window.tab_widget.tabBar().show()
        
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
        flags = QTextDocument.FindFlags()
        if direction == 'up':
            flags |= QTextDocument.FindBackward
            
        # Remove case sensitivity flag to make search case-insensitive
        # flags |= QTextDocument.FindCaseSensitively  # Commented out to make case-insensitive
            
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
        cursor.movePosition(QTextCursor.Start)
        self.editor.setTextCursor(cursor)
        
        # Create find flags for case-insensitive search
        flags = QTextDocument.FindFlags()
        # flags |= QTextDocument.FindCaseSensitively  # Commented out to make case-insensitive
        
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
        cursor.movePosition(QTextCursor.Start)
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
        menu.exec_(self.editor.mapToGlobal(position))

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
            'sizes': self.splitter.sizes()
        }
        self.settings_manager.save_setting('pane_states', states)

    def set_main_window(self, main_window):
        """Set reference to main window and initialize session state"""
        self.main_window = main_window
        # Update session state to include this tab
        current_tabs = self.main_window.get_open_tab_ids()
        if self.recovery_id not in current_tabs:
            current_tabs.append(self.recovery_id)
            self.settings_manager.save_session_state(current_tabs)

    def cleanup_session_files(self):
        """Clean up session files for this tab"""
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
        except Exception as e:
            print(f"Failed to cleanup session files: {str(e)}")

    def keyPressEvent(self, event):
        """Handle key events"""
        super().keyPressEvent(event)  # Just pass through to parent

    def show_suggestion_tooltip(self, suggestions, cursor):
        """Show suggestions in a tooltip-like widget"""
        self.hide_suggestions()
        self.current_suggestions = suggestions
        self.selected_suggestion_index = -1
        
        # Create tooltip widget
        self.suggestion_tooltip = QWidget(self.editor, Qt.ToolTip)
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
            container.setCursor(Qt.PointingHandCursor)
            
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
        if obj == self.editor and event.type() == QEvent.KeyPress:
            # Handle Escape key
            if event.key() == Qt.Key_Escape and hasattr(self, 'focus_mode') and self.focus_mode:
                self.disable_focus_mode()
                event.accept()
                return True
            # Handle Ctrl+Shift+D (or Cmd+Shift+D on Mac)
            elif (event.key() == Qt.Key_D and 
                  event.modifiers() & Qt.ShiftModifier and 
                  event.modifiers() & (Qt.ControlModifier if sys.platform != 'darwin' else Qt.MetaModifier)):
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
            self.back_btn.setEnabled(self.web_view.page().action(QWebEnginePage.Back).isEnabled())
            self.forward_btn.setEnabled(self.web_view.page().action(QWebEnginePage.Forward).isEnabled())

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