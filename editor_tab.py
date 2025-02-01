from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTextEdit, QListWidget, QInputDialog, QMenu, QFileDialog, QDialog,
                            QToolBar, QAction, QCompleter, QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel)
from PyQt5.QtCore import Qt, QUrl, QTimer, QStringListModel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QTextCharFormat, QSyntaxHighlighter, QIcon, QFont, QKeySequence
import enchant
from urllib.parse import quote
from snippet_editor_dialog import SnippetEditorDialog
import os
from rss_reader import RSSReader
import json
import time
from theme_manager import ThemeManager

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, snippet_manager=None):
        super().__init__(parent)
        self.dict = enchant.Dict("en_US")
        self.snippet_manager = snippet_manager
        
    def highlightBlock(self, text):
        format = QTextCharFormat()
        format.setUnderlineColor(Qt.red)
        format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        
        # Split text into words
        for word_start, word_length in self.get_words(text):
            word = text[word_start:word_start + word_length]
            
            # Skip spell check for snippets
            if self.snippet_manager and self.is_snippet_word(word):
                continue
            
            # Skip URLs and email addresses
            if self.is_url_or_email(word):
                continue
                
            # Skip words with numbers
            if any(c.isdigit() for c in word):
                continue
                
            # Skip all-caps words (likely acronyms)
            if word.isupper():
                continue
                
            # Check if the word is misspelled
            if not self.dict.check(word):
                # Skip proper nouns only at start of sentence
                if word[0].isupper() and word_start > 0:
                    prev_char = text[word_start - 1]
                    # If it's not the start of a sentence, mark as misspelled
                    if prev_char not in '.!?\n':
                        self.setFormat(word_start, word_length, format)
                else:
                    # Mark as misspelled
                    self.setFormat(word_start, word_length, format)
        
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
        if not self.dict.check(word):
            # Get base suggestions
            suggestions = self.dict.suggest(word)
            
            # Filter and sort suggestions
            filtered_suggestions = []
            for suggestion in suggestions:
                # Keep original case for first letter if word starts with capital
                if word and word[0].isupper() and suggestion:
                    suggestion = suggestion[0].upper() + suggestion[1:]
                # Don't suggest all caps unless original was all caps
                elif not word.isupper():
                    suggestion = suggestion.lower()
                filtered_suggestions.append(suggestion)
            
            # Limit to top 5 suggestions
            return filtered_suggestions[:5]
        return []

class CustomTextEdit(QTextEdit):
    def __init__(self, editor_tab, parent=None):
        super().__init__(parent)
        self.completer = None
        self.editor_tab = editor_tab
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.editor_tab.show_context_menu)
        self.setAcceptRichText(False)  # Disable rich text acceptance
        
    def insertFromMimeData(self, source):
        """Override to handle pasted content"""
        if source.hasText():
            # Get plain text and normalize line endings
            text = source.text()
            text = text.replace('\r\n', '\n')  # Convert Windows line endings
            text = text.replace('\r', '\n')    # Convert Mac line endings
            
            # Remove any excess blank lines (more than two consecutive)
            text = '\n'.join([line for line in 
                            [l.rstrip() for l in text.split('\n')] 
                            if line or not text.split('\n')[max(0, text.split('\n').index(line)-1):text.split('\n').index(line)+1].count('')>2])
            
            # Insert the cleaned text
            cursor = self.textCursor()
            cursor.insertText(text)
        else:
            super().insertFromMimeData(source)
            
    def setCompleter(self, completer):
        self.completer = completer
        
    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            # Handle Tab and Enter keys for completion
            if event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                # Get the currently selected item from popup
                popup = self.completer.popup()
                index = popup.currentIndex()
                if index.isValid():
                    completion = self.completer.completionModel().data(index, Qt.DisplayRole)
                    # Use the editor_tab's insert_completion method
                    self.editor_tab.insert_completion(completion)
                    popup.hide()
                    event.accept()
                    return
            
        super().keyPressEvent(event)

class EditorTab(QWidget):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.completer = None
        self.main_window = None  # Will store reference to main window
        
        # Load settings
        self.current_font = settings_manager.get_font()
        self.current_theme = settings_manager.get_theme()
        
        self.setup_ui()
        self.setup_autocomplete()
        self.setup_autosave()
        
        # Apply theme
        ThemeManager.apply_theme(self.editor, self.current_theme)
        
        # Track if content has been modified
        self.editor.document().modificationChanged.connect(self.handle_modification)
        self.editor.document().setModified(False)
        
    def set_main_window(self, window):
        """Set reference to main window"""
        self.main_window = window

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create main splitter (horizontal)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Create left side splitter (horizontal) for editor and snippets
        left_splitter = QSplitter(Qt.Horizontal)
        
        # Create text editor with default font
        self.editor = CustomTextEdit(self)
        self.editor.setFont(self.current_font)
        self.spell_checker = SpellCheckHighlighter(self.editor.document(), self.snippet_manager)
        
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
        
    def setup_autosave(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000)  # 30 seconds
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()
        
        # Try to recover autosaved content on startup
        self.check_for_recovery()
        
    def autosave(self):
        content = self.editor.toPlainText()
        if not content.strip():  # Don't save empty content
            return
        
        autosave_dir = os.path.join(os.path.expanduser("~"), ".editor_autosave")
        os.makedirs(autosave_dir, exist_ok=True)
        
        # Save both content and metadata
        autosave_data = {
            'content': content,
            'timestamp': time.time(),
            'original_file': self.current_file
        }
        
        autosave_file = os.path.join(autosave_dir, f"autosave_{id(self)}.json")
        try:
            with open(autosave_file, 'w') as f:
                json.dump(autosave_data, f)
        except Exception as e:
            print(f"Autosave failed: {e}")

    def check_for_recovery(self):
        # Only check for recovery if this is a new instance (not a new tab)
        if not hasattr(self, '_recovery_checked'):
            self._recovery_checked = True
            autosave_dir = os.path.join(os.path.expanduser("~"), ".editor_autosave")
            if not os.path.exists(autosave_dir):
                return
            
            recovery_files = []
            for filename in os.listdir(autosave_dir):
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(autosave_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        recovery_files.append({
                            'path': filepath,
                            'timestamp': data['timestamp'],
                            'content': data['content'],
                            'original_file': data.get('original_file')
                        })
                except:
                    continue
            
            if not recovery_files:
                return
            
            # Sort by timestamp, newest first
            recovery_files.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Ask user about recovery
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Unsaved changes from a previous session were found.")
            msg.setInformativeText("Would you like to recover them?")
            msg.setWindowTitle("Recovery Available")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            
            if msg.exec_() == QMessageBox.Yes:
                # Create new tabs for each recovery file
                for recovery in recovery_files:
                    self.recover_content(recovery)
            
            # Clean up recovery files
            for recovery in recovery_files:
                try:
                    os.remove(recovery['path'])
                except:
                    pass

    def recover_content(self, recovery):
        self.editor.setPlainText(recovery['content'])
        if recovery['original_file']:
            self.current_file = recovery['original_file']
    
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
            
            # Clean up autosave file after successful save
            self.cleanup_autosave()
            
            # Update tab title to show file name
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
        self.snippet_list.clear()
        for title in self.snippet_manager.get_snippets():
            self.snippet_list.addItem(title)
        # Only update completer if it exists
        if self.completer:
            self.update_completer_model()
            
    def insert_snippet(self, item):
        text = self.snippet_manager.get_snippet(item.text())
        if text:
            self.editor.insertPlainText(text)
            
    def show_context_menu(self, position):
        menu = self.editor.createStandardContextMenu()
        
        # Get cursor at click position
        click_cursor = self.editor.cursorForPosition(position)
        
        # If no text is selected, select word under cursor
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            click_cursor.select(click_cursor.WordUnderCursor)
            self.editor.setTextCursor(click_cursor)  # Update the editor's cursor
            cursor = click_cursor
        
        word = cursor.selectedText()
        if word:
            # Check if word is misspelled
            if not self.spell_checker.dict.check(word):
                suggestions = self.spell_checker.get_suggestions(word)
                if suggestions:
                    spell_menu = menu.addMenu("Spelling Suggestions")
                    for suggestion in suggestions:
                        action = spell_menu.addAction(suggestion)
                        action.triggered.connect(
                            lambda checked, word=suggestion: self.replace_word(cursor, word))
        
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            
            # Add custom actions
            menu.addSeparator()
            menu.addAction("Search in Google", 
                          lambda: self.search_google(selected_text))
            menu.addAction("Search in AP News", 
                          lambda: self.search_apnews(selected_text))
            menu.addAction("Google Search AP News Only", 
                          lambda: self.search_google_site_apnews(selected_text))
            menu.addAction("Save as Snippet", 
                          lambda: self.save_snippet(selected_text))
        
        menu.exec_(self.editor.mapToGlobal(position))
        
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
            
    def replace_word(self, cursor, new_word):
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(new_word)
        cursor.endEditBlock()
    
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

    def setup_autocomplete(self):
        # Create completer
        self.completer = QCompleter(self)
        self.completer.setWidget(self.editor)
        self.completer.activated.connect(self.insert_completion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        
        # Set completer for custom editor
        self.editor.setCompleter(self.completer)
        
        # Update completer's model with snippet titles
        self.update_completer_model()
        
        # Connect editor's textChanged signal to handle autocomplete
        self.editor.textChanged.connect(self.handle_text_changed)
    
    def update_completer_model(self):
        # Get all snippet titles
        titles = self.snippet_manager.get_snippets()
        # Create and set the model
        model = QStringListModel(titles, self.completer)
        self.completer.setModel(model)
    
    def handle_text_changed(self):
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
    
    def insert_completion(self, completion):
        cursor = self.editor.textCursor()
        
        # Delete the partially typed word
        chars_to_delete = len(self.completer.completionPrefix())
        cursor.movePosition(cursor.Left, cursor.KeepAnchor, chars_to_delete)
        cursor.removeSelectedText()
        
        # Insert the snippet content instead of just the title
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
        self.editor.setFont(font)
        # Store font settings in theme-aware stylesheet
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                font-family: {font.family()};
                font-size: {font.pointSize()}pt;
                font-weight: {font.weight()};
                font-style: {('italic' if font.italic() else 'normal')};
            }}
        """)

    def apply_theme(self, theme_name):
        self.current_theme = theme_name  # Store current theme
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

    def cleanup_autosave(self):
        """Clean up autosave file for this tab"""
        if not hasattr(self, 'autosave_path'):
            return
        
        try:
            if os.path.exists(self.autosave_path):
                os.remove(self.autosave_path)
        except:
            pass