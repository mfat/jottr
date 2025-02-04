from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTextEdit, QListWidget, QInputDialog, QMenu, QFileDialog, QDialog,
                            QToolBar, QAction, QCompleter, QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel, QShortcut)
from PyQt5.QtCore import Qt, QUrl, QTimer, QStringListModel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QTextCharFormat, QSyntaxHighlighter, QIcon, QFont, QKeySequence
from hunspell import Hunspell  # Use hunspell package instead of cyhunspell
from urllib.parse import quote
from snippet_editor_dialog import SnippetEditorDialog
import os
from rss_reader import RSSReader
import json
import time
from theme_manager import ThemeManager
import hashlib

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, snippet_manager=None):
        super().__init__(parent)
        self.snippet_manager = snippet_manager
        try:
            # Initialize Hunspell with both US and GB dictionaries
            self.dict = Hunspell('en_US')
            self.gb_dict = Hunspell('en_GB')
            self.spell_check_enabled = True
            print("Spell checking enabled")
            
        except Exception as e:
            print(f"Warning: Spell checking disabled - {str(e)}")
            self.spell_check_enabled = False
        
    def highlightBlock(self, text):
        if not self.spell_check_enabled:
            return
            
        # Format for misspelled words
        format = QTextCharFormat()
        format.setUnderlineColor(Qt.red)
        format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        
        # Get word positions
        for start, length in self.get_words(text):
            word = text[start:start + length]
            
            # Skip if word contains non-Latin characters
            if any(ord(c) > 127 for c in word):
                continue
                
            # Skip URLs, emails, and snippet words
            if self.is_url_or_email(word) or self.is_snippet_word(word):
                continue
                
            try:
                # Check spelling in both dictionaries
                if not self.dict.spell(word) and not self.gb_dict.spell(word):
                    self.setFormat(start, length, format)
            except UnicodeEncodeError:
                # Skip words that can't be encoded in Latin-1
                continue
        
    def get_words(self, text):
        """Get word positions and lengths, handling contractions properly"""
        words = []
        start = 0
        in_word = False
        
        for i, char in enumerate(text):
            is_word_char = char.isalpha() or char == "'"
            
            if is_word_char and not in_word:
                start = i
                in_word = True
            elif not is_word_char and in_word:
                if i - start > 0:  # Only add if word has length
                    words.append((start, i - start))
                in_word = False
                
        # Handle word at end of text
        if in_word and len(text) - start > 0:
            words.append((start, len(text) - start))
            
        return words

    def is_snippet_word(self, word):
        """Check if word is part of a snippet"""
        if not self.snippet_manager:
            return False
            
        # Check snippet titles
        if word in self.snippet_manager.get_snippets():
            return True
            
        # Check snippet contents
        for content in self.snippet_manager.get_all_snippet_contents():
            if word in content.split():
                return True
        return False

    def is_url_or_email(self, word):
        """Check if word looks like a URL or email address"""
        return ('.' in word and '/' in word) or '@' in word

    def get_suggestions(self, word):
        """Get spelling suggestions for a word"""
        if self.spell_check_enabled:
            # Try US dictionary first
            if not self.dict.spell(word):
                suggestions = self.dict.suggest(word)
                if not suggestions and not self.gb_dict.spell(word):
                    # If no suggestions from US dict, try GB dict
                    suggestions.extend(self.gb_dict.suggest(word))
                return list(set(suggestions))[:5]  # Remove duplicates and limit to top 5
        return []

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

class EditorTab(QWidget):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.current_font = self.settings_manager.get_font()
        
        # Initialize recovery ID and paths first
        self.recovery_id = str(int(time.time() * 1000))  # Unique ID for this tab
        self.session_path = os.path.join(
            self.settings_manager.get_recovery_dir(),
            f"session_{self.recovery_id}.txt"
        )
        self.meta_path = self.session_path + '.json'
        
        # Initialize completer first
        self.completer = QCompleter(self.snippet_manager.get_snippets())
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        
        # Initialize main window reference
        self.main_window = None
        
        # Setup UI components
        self.setup_ui()
        
        # Connect completer to editor after UI setup
        self.editor.setCompleter(self.completer)
        
        # Setup autosave after UI is ready
        self.last_save_time = time.time()
        self.changes_pending = False
        
        # Start periodic backup timer
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.force_save)
        self.backup_timer.start(5000)  # Backup every 5 seconds if needed
        
        # Apply theme
        ThemeManager.apply_theme(self.editor, self.settings_manager.get_theme())
        
        # Track if content has been modified
        self.editor.document().modificationChanged.connect(self.handle_modification)
        self.editor.document().setModified(False)
        
        self.focus_mode = False
        
        # Add focus mode shortcut
        focus_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        focus_shortcut.activated.connect(self.toggle_focus_mode)
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create main splitter (horizontal)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Create left side splitter (horizontal) for editor and snippets
        left_splitter = QSplitter(Qt.Horizontal)
        
        # Create text editor with default font
        self.editor = CustomTextEdit(self)
        self.editor.setCompleter(self.completer)  # Set completer for custom editor
        self.update_font(self.current_font)
        self.highlighter = SpellCheckHighlighter(self.editor.document(), self.snippet_manager)
        
        # Create snippet panel
        snippet_widget = QWidget()
        snippet_layout = QVBoxLayout(snippet_widget)
        snippet_layout.setContentsMargins(0, 0, 0, 0)
        
        # Snippet header
        snippet_header = QWidget()
        snippet_header.setStyleSheet("""
            QWidget {
                background-color: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QPushButton {
                border: none;
                padding: 0px;
                color: palette(text);
            }
            QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        header_layout = QHBoxLayout(snippet_header)
        header_layout.setContentsMargins(8, 4, 4, 4)
        
        snippet_title = QLabel("Snippets")
        snippet_title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(snippet_title)
        
        snippet_close = QPushButton("×")
        snippet_close.setFixedSize(20, 20)
        snippet_close.clicked.connect(lambda: self.toggle_pane("snippets"))
        header_layout.addWidget(snippet_close)
        
        snippet_layout.addWidget(snippet_header)
        
        # Snippet list
        self.snippet_list = QListWidget()
        self.snippet_list.itemDoubleClicked.connect(self.insert_snippet)
        self.snippet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_list.customContextMenuRequested.connect(self.show_snippet_context_menu)
        self.update_snippet_list()  # Populate the list
        snippet_layout.addWidget(self.snippet_list)
        
        # Create browser panel
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)
        
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
        back_btn = QPushButton("←")
        back_btn.setFixedSize(24, 24)
        back_btn.clicked.connect(lambda: self.web_view.back())
        toolbar_layout.addWidget(back_btn)
        
        forward_btn = QPushButton("→")
        forward_btn.setFixedSize(24, 24)
        forward_btn.clicked.connect(lambda: self.web_view.forward())
        toolbar_layout.addWidget(forward_btn)
        
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
        
        browser_layout.addWidget(toolbar)
        
        # Web view with shortcuts
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("https://www.google.com"))
        self.web_view.urlChanged.connect(self.update_url)
        
        # Add standard shortcuts for the web view
        self.setup_browser_shortcuts()
        
        browser_layout.addWidget(self.web_view)
        
        # Add to splitters
        left_splitter.addWidget(self.editor)
        left_splitter.addWidget(snippet_widget)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(browser_widget)
        
        # Set splitter sizes
        left_splitter.setStretchFactor(0, 2)  # Editor gets more space
        left_splitter.setStretchFactor(1, 1)  # Snippets get less space
        main_splitter.setStretchFactor(0, 2)   # Left side gets more space
        main_splitter.setStretchFactor(1, 1)   # Browser gets less space
        
        # Store widgets for visibility toggling
        self.snippet_widget = snippet_widget
        self.browser_widget = browser_widget
        
        # Set initial visibility from settings
        show_snippets, show_browser = self.settings_manager.get_pane_visibility()
        self.snippet_widget.setVisible(show_snippets)
        self.browser_widget.setVisible(show_browser)
        
        main_layout.addWidget(main_splitter)
        
        # Set focus to editor
        self.editor.setFocus()
        
        # Connect signals for status updates
        self.editor.textChanged.connect(self.update_status)
        self.editor.textChanged.connect(self.handle_text_changed)
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)
        self.editor.textChanged.connect(self.on_text_changed)
        
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

    def save_file(self):
        if not self.current_file:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save File", "", 
                                                     "Text Files (*.txt);;All Files (*)")
            if file_name:
                self.current_file = file_name
            else:
                return False
                
        try:
            with open(self.current_file, 'w') as file:
                file.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            
            # Mark as clean exit before cleanup
            self.autosave()
            self.cleanup_session_files()
            
            # Update tab title
            if self.main_window and hasattr(self.main_window, 'tab_widget'):
                current_index = self.main_window.tab_widget.indexOf(self)
                if current_index >= 0:
                    file_name = os.path.basename(self.current_file)
                    self.main_window.tab_widget.setTabText(current_index, file_name)
            
            return True
        except:
            QMessageBox.warning(self, "Save Error", "Failed to save file.")
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
            
    def show_context_menu(self, position):
        """Show custom context menu"""
        cursor = self.editor.cursorForPosition(position)
        current_cursor = self.editor.textCursor()
        
        # If we have a selection and clicked outside it, select the new word
        # Otherwise keep the existing selection
        if not current_cursor.hasSelection() or not self.is_position_in_selection(position):
            cursor.select(cursor.WordUnderCursor)
            self.editor.setTextCursor(cursor)
        
        menu = self.editor.createStandardContextMenu()
        
        # Add custom actions for selected text
        selected_text = self.editor.textCursor().selectedText()
        if selected_text:
            menu.addSeparator()
            
            # Add search actions
            menu.addAction("Search in Google", 
                          lambda: self.search_google(selected_text))
            menu.addAction("Search in AP News", 
                          lambda: self.search_apnews(selected_text))
            menu.addAction("Search in AP News with Google", 
                          lambda: self.search_google_site_apnews(selected_text))
            
            # Add snippet action
            menu.addAction("Save as Snippet", 
                          lambda: self.save_snippet(selected_text))
            
            # Only show spelling suggestions for single words
            if (hasattr(self, 'highlighter') and 
                self.highlighter.spell_check_enabled and 
                len(selected_text.split()) == 1):  # Check if it's a single word
                try:
                    if not self.highlighter.dict.spell(selected_text):
                        menu.addSeparator()
                        menu.addAction("Spelling Suggestions:").setEnabled(False)
                        suggestions = self.highlighter.dict.suggest(selected_text)[:5]
                        for suggestion in suggestions:
                            action = menu.addAction(suggestion)
                            action.triggered.connect(lambda _, word=suggestion: self.replace_selected_text(word))
                    # Check GB dictionary if not found in US
                    elif not self.highlighter.gb_dict.spell(selected_text):
                        menu.addSeparator()
                        menu.addAction("Spelling Suggestions:").setEnabled(False)
                        suggestions = self.highlighter.gb_dict.suggest(selected_text)[:5]
                        for suggestion in suggestions:
                            action = menu.addAction(suggestion)
                            action.triggered.connect(lambda _, word=suggestion: self.replace_selected_text(word))
                except:
                    pass  # Skip spell checking if there's an error
        
        menu.exec_(self.editor.viewport().mapToGlobal(position))
    
    def is_position_in_selection(self, position):
        """Check if the given position is within the current selection"""
        cursor = self.editor.textCursor()
        click_cursor = self.editor.cursorForPosition(position)
        
        if not cursor.hasSelection():
            return False
            
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        click_pos = click_cursor.position()
        
        return selection_start <= click_pos <= selection_end

    def replace_selected_text(self, new_text):
        """Replace the selected text with new_text"""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(new_text)
        cursor.endEditBlock()

    def ensure_browser_visible(self):
        """Ensure browser pane is visible"""
        if not self.browser_widget.isVisible():
            self.browser_widget.setVisible(True)
            self.settings_manager.save_pane_visibility(
                self.snippet_widget.isVisible(),
                True
            )

    def search_google(self, text):
        url = f"https://www.google.com/search?q={quote(text)}"
        self.url_bar.setText(url)
        self.web_view.setUrl(QUrl(url))
        self.ensure_browser_visible()
        
    def search_apnews(self, text):
        url = f"https://apnews.com/search?q={quote(text)}"
        self.url_bar.setText(url)
        self.web_view.setUrl(QUrl(url))
        self.ensure_browser_visible()
        
    def search_google_site_apnews(self, text):
        url = f"https://www.google.com/search?q=site:apnews.com {quote(text)}"
        self.url_bar.setText(url)
        self.web_view.setUrl(QUrl(url))
        self.ensure_browser_visible()
        
    def save_snippet(self, text):
        title, ok = QInputDialog.getText(self, 'Save Snippet', 
                                       'Enter snippet title:')
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
        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.web_view.setUrl(QUrl(url))

    def update_font(self, font):
        self.current_font = font
        # Update font for the editor
        self.editor.setFont(font)
        # Store font properties in the editor's stylesheet
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                font-family: {font.family()};
                font-size: {font.pointSize()}pt;
                font-weight: {font.weight()};
                font-style: {('italic' if font.italic() else 'normal')};
                background-color: {self.editor.palette().base().color().name()};
                color: {self.editor.palette().text().color().name()};
                selection-background-color: {self.editor.palette().highlight().color().name()};
            }}
        """)

    def apply_theme(self, theme_name):
        """Apply theme to editor"""
        self.settings_manager.save_theme(theme_name)
        ThemeManager.apply_theme(self.editor, theme_name)

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

    def toggle_pane(self, pane):
        if pane == "snippets":
            self.snippet_widget.setVisible(not self.snippet_widget.isVisible())
        else:
            self.browser_widget.setVisible(not self.browser_widget.isVisible())
        
        # Save visibility state
        self.settings_manager.save_pane_visibility(
            self.snippet_widget.isVisible(),
            self.browser_widget.isVisible()
        )

    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def setup_browser_shortcuts(self):
        """Setup standard shortcuts for the web browser"""
        # Copy
        copy_action = QAction(self.web_view)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.setShortcutContext(Qt.WidgetShortcut)  # Only active when web view has focus
        copy_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Copy))
        self.web_view.addAction(copy_action)
        
        # Cut
        cut_action = QAction(self.web_view)
        cut_action.setShortcut(QKeySequence("Ctrl+X"))
        cut_action.setShortcutContext(Qt.WidgetShortcut)  # Only active when web view has focus
        cut_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Cut))
        self.web_view.addAction(cut_action)
        
        # Paste
        paste_action = QAction(self.web_view)
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.setShortcutContext(Qt.WidgetShortcut)  # Only active when web view has focus
        paste_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.Paste))
        self.web_view.addAction(paste_action)
        
        # Select All
        select_all_action = QAction(self.web_view)
        select_all_action.setShortcut(QKeySequence("Ctrl+A"))
        select_all_action.setShortcutContext(Qt.WidgetShortcut)  # Only active when web view has focus
        select_all_action.triggered.connect(lambda: self.web_view.page().triggerAction(QWebEnginePage.SelectAll))
        self.web_view.addAction(select_all_action)

    def update_status(self):
        """Update word and character count"""
        text = self.editor.toPlainText()
        
        # Update word count
        words = len(text.split()) if text else 0
        chars = len(text)
        
        # Update status bar if main window exists
        if self.main_window:
            self.main_window.word_count_label.setText(f"Words: {words}")
            self.main_window.char_count_label.setText(f"Characters: {chars}")

    def update_cursor_position(self):
        """Update cursor position in status bar"""
        if not self.main_window:
            return
        
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        
        self.main_window.cursor_pos_label.setText(f"Line: {line}, Column: {column}")

    def toggle_focus_mode(self):
        """Toggle focus mode on/off"""
        self.focus_mode = not self.focus_mode
        
        if self.focus_mode:
            # Create and show exit button
            self.exit_focus_button = QPushButton("×", self)
            self.exit_focus_button.setFixedSize(30, 30)
            self.exit_focus_button.clicked.connect(self.toggle_focus_mode)
            self.exit_focus_button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #888;
                    font-size: 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #333;
                }
            """)
            
            # Create escape hint overlay
            self.escape_hint = QLabel(self)
            self.escape_hint.setText("⎋ ESC to exit")
            self.escape_hint.setStyleSheet("""
                QLabel {
                    color: #888;
                    background-color: transparent;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-size: 12px;
                }
            """)
            self.escape_hint.adjustSize()
            
            # Position and show UI elements
            self.exit_focus_button.show()
            self.escape_hint.show()
            self.exit_focus_button.raise_()
            self.escape_hint.raise_()
            
            # Hide distracting elements
            self.snippet_widget.hide()
            self.browser_widget.hide()
            if self.main_window:
                self.main_window.toolbar.hide()
                self.main_window.statusBar.hide()
                self.main_window.tab_widget.tabBar().hide()
                self.main_window.showFullScreen()
            
            # Add escape key shortcut
            self.escape_shortcut = QShortcut(QKeySequence("Escape"), self)
            self.escape_shortcut.activated.connect(self.toggle_focus_mode)
            
            # Update positions when window resizes
            self.main_window.resizeEvent = lambda e: self.update_focus_ui_positions()
            self.update_focus_ui_positions()
            
        else:
            # Remove focus mode UI elements
            if hasattr(self, 'exit_focus_button'):
                self.exit_focus_button.deleteLater()
                del self.exit_focus_button
            
            if hasattr(self, 'escape_hint'):
                self.escape_hint.deleteLater()
                del self.escape_hint
            
            if hasattr(self, 'escape_shortcut'):
                self.escape_shortcut.deleteLater()
                del self.escape_shortcut
            
            # Restore UI elements
            show_snippets, show_browser = self.settings_manager.get_pane_visibility()
            self.snippet_widget.setVisible(show_snippets)
            self.browser_widget.setVisible(show_browser)
            if self.main_window:
                self.main_window.toolbar.show()
                self.main_window.statusBar.show()
                self.main_window.tab_widget.tabBar().show()
                self.main_window.showNormal()
                
                # Restore original resize event
                self.main_window.resizeEvent = self.main_window.resizeEvent
    
    def update_focus_ui_positions(self):
        """Update the positions of focus mode UI elements"""
        if hasattr(self, 'exit_focus_button') and hasattr(self, 'escape_hint'):
            margin = 10
            
            # Position exit button in top-right
            self.exit_focus_button.move(
                self.main_window.width() - self.exit_focus_button.width() - margin,
                margin
            )
            
            # Position escape hint next to exit button
            self.escape_hint.move(
                self.main_window.width() - self.exit_focus_button.width() - self.escape_hint.width() - margin * 2,
                margin + (self.exit_focus_button.height() - self.escape_hint.height()) // 2
            )

    def cleanup_session_files(self):
        """Clean up session files for this tab"""
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
        except Exception as e:
            print(f"Failed to cleanup session files: {str(e)}")

    def set_main_window(self, main_window):
        """Set reference to main window and initialize session state"""
        self.main_window = main_window
        # Update session state to include this tab
        current_tabs = self.main_window.get_open_tab_ids()
        if self.recovery_id not in current_tabs:
            current_tabs.append(self.recovery_id)
            self.settings_manager.save_session_state(current_tabs)

    def handle_text_changed(self):
        """Handle text changes for autocompletion"""
        cursor = self.editor.textCursor()
        current_line = cursor.block().text()
        current_position = cursor.positionInBlock()
        
        # Find the word being typed (include numbers and letters)
        word_start = current_position
        while word_start > 0 and (current_line[word_start - 1].isalnum() or 
                                 current_line[word_start - 1] in '_-'):
            word_start -= 1
        
        if word_start <= len(current_line):
            current_word = current_line[word_start:current_position]
            
            if len(current_word) >= 2:  # Only show suggestions after 2 characters
                rect = self.editor.cursorRect()
                self.completer.setCompletionPrefix(current_word)
                
                if self.completer.completionCount() > 0:
                    popup = self.completer.popup()
                    # Always show popup but don't auto-complete
                    popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                    
                    # Calculate popup position
                    rect.setWidth(self.completer.popup().sizeHintForColumn(0) + 
                                self.completer.popup().verticalScrollBar().sizeHint().width())
                    self.completer.complete(rect)
                else:
                    self.completer.popup().hide()
            else:
                self.completer.popup().hide()