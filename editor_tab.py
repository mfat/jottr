from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTextEdit, QListWidget, QInputDialog, QMenu, QFileDialog, QDialog,
                            QToolBar, QAction, QCompleter, QListWidgetItem, QLineEdit, QPushButton, QMessageBox, QLabel, QShortcut, QToolTip)
from PyQt5.QtCore import Qt, QUrl, QTimer, QStringListModel, QRegExp
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QTextCharFormat, QSyntaxHighlighter, QIcon, QFont, QKeySequence, QPainter, QPen, QColor, QFontMetrics
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
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        try:
            # Initialize Hunspell with both US and GB dictionaries
            self.dict = Hunspell('en_US')
            self.gb_dict = Hunspell('en_GB')
            self.spell_check_enabled = True
            print("Spell checking enabled")
            
        except Exception as e:
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
                    # If not in user dictionary, check against Hunspell dictionaries
                    try:
                        if not self.dict.spell(word) and not self.gb_dict.spell(word):
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
        
        # Only get Hunspell suggestions for Latin words
        if self.is_latin_word(word):
            try:
                suggestions.extend(self.dict.suggest(word))
                suggestions.extend(self.gb_dict.suggest(word))
            except UnicodeEncodeError:
                pass
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(suggestions))

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
        self.completion_text = ""
        
    def insertFromMimeData(self, source):
        """Override paste to always use plain text"""
        if source.hasText():
            # Insert as plain text, using the editor's current formatting
            cursor = self.textCursor()
            cursor.insertText(source.text())
        
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.completion_text:
            # Get the cursor rectangle for positioning
            cursor = self.textCursor()
            rect = self.cursorRect(cursor)
            
            # Create painter
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(128, 128, 128)))  # Grey color
            
            # Calculate position for completion text
            font_metrics = QFontMetrics(self.font())
            x = rect.x()
            y = rect.y() + font_metrics.ascent()
            
            # Draw the completion text
            painter.drawText(x, y, self.completion_text)

class EditorTab(QWidget):
    def __init__(self, snippet_manager, settings_manager):
        super().__init__()
        self.snippet_manager = snippet_manager
        self.settings_manager = settings_manager
        self.current_file = None
        self.current_font = self.settings_manager.get_font()
        
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
        
        # Set homepage for web view
        homepage = self.settings_manager.get_setting('homepage', 'https://www.apnews.com/')
        self.web_view.setUrl(QUrl(homepage))
        
        # Setup autocomplete
        self.current_word = ""
        self.current_suggestions = []
        self.suggestion_index = -1
        
        # Install event filter for key handling
        self.editor.installEventFilter(self)

    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for editor and side panes
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create text editor with default font
        self.editor = CompletingTextEdit()
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.update_font(self.current_font)
        
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
        
        # Create browser widget
        self.browser_widget = QWidget()
        browser_layout = QVBoxLayout(self.browser_widget)
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
        
        # Add widgets to splitter
        self.splitter.addWidget(self.snippet_widget)
        self.splitter.addWidget(self.browser_widget)
        
        # Add splitter to layout
        layout.addWidget(self.splitter)
        
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
            
    def show_context_menu(self, pos):
        """Show context menu"""
        # Get cursor at click position and select word under it
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
        
        # Add spell check suggestions if word is misspelled
        if self.highlighter.spell_check_enabled:
            word = selected_text  # Use the selected word
            if word:
                # Get suggestions including user dictionary matches
                self.current_suggestions = self.highlighter.suggest(word)[:5]
                if self.current_suggestions:
                    menu.addAction("Suggestions:").setEnabled(False)
                    self.suggestion_index = 0  # Reset suggestion index
                    for i, suggestion in enumerate(self.current_suggestions):
                        action = menu.addAction(suggestion)
                        action.triggered.connect(lambda checked, word=suggestion: self.apply_suggestion(word))
                    menu.addSeparator()
                    
                
                # Add to dictionary option if not already in it
                if word not in self.settings_manager.get_setting('user_dictionary', []):
                    add_action = menu.addAction("Add to Dictionary")
                    add_action.triggered.connect(lambda: self.add_to_dictionary(word))
                    menu.addSeparator()
        
        # Show menu
        menu.exec_(self.editor.mapToGlobal(pos))

    def search_in_browser(self, url):
        """Perform search in browser pane and ensure it's visible"""
        # Show browser pane if hidden
        if not self.browser_widget.isVisible():
            self.toggle_pane("browser")  # Use toggle_pane to handle visibility and sizing
        
        # Navigate to URL
        self.web_view.setUrl(QUrl(url))

    def add_to_dictionary(self, word):
        """Add word to user dictionary"""
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)
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
        """Toggle visibility of side panes"""
        if pane == "snippets":
            self.snippet_widget.setVisible(not self.snippet_widget.isVisible())
            # If showing snippets, make sure it has reasonable size
            if self.snippet_widget.isVisible():
                current_sizes = self.splitter.sizes()
                if current_sizes[1] < 100:  # If snippet pane is too small
                    editor_size = current_sizes[0]
                    new_snippet_size = int(editor_size * 0.2)  # 20% for snippets
                    new_editor_size = editor_size - new_snippet_size
                    self.splitter.setSizes([new_editor_size, new_snippet_size, current_sizes[2]])
        elif pane == "browser":
            self.browser_widget.setVisible(not self.browser_widget.isVisible())
            # If showing browser, make sure it has reasonable size
            if self.browser_widget.isVisible():
                current_sizes = self.splitter.sizes()
                if current_sizes[2] < 100:  # If browser pane is too small
                    editor_size = current_sizes[0]
                    new_browser_size = int(editor_size * 0.3)  # 30% for browser
                    new_editor_size = editor_size - new_browser_size
                    self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
        # Save states after toggling
        self.save_pane_states()

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

    def enable_focus_mode(self):
        """Enable focus mode"""
        self.focus_mode = True
        # Hide side panes
        if hasattr(self, 'snippet_widget'):
            self.snippet_widget.hide()
        if hasattr(self, 'browser_widget'):
            self.browser_widget.hide()
        # Set editor to full width
        if hasattr(self, 'splitter'):
            self.splitter.setSizes([self.width(), 0, 0])

    def disable_focus_mode(self):
        """Disable focus mode"""
        self.focus_mode = False
        # Restore pane states from settings
        states = self.settings_manager.get_setting('pane_states', {
            'snippets_visible': False,
            'browser_visible': False,
            'sizes': [700, 300, 300]
        })
        
        if hasattr(self, 'snippet_widget'):
            self.snippet_widget.setVisible(states.get('snippets_visible', False))
        if hasattr(self, 'browser_widget'):
            self.browser_widget.setVisible(states.get('browser_visible', False))
        if hasattr(self, 'splitter'):
            self.splitter.setSizes(states.get('sizes', [700, 300, 300]))

    def toggle_focus_mode(self):
        """Toggle focus mode"""
        if not hasattr(self, 'focus_mode'):
            self.focus_mode = False
            
        self.focus_mode = not self.focus_mode
        
        if self.focus_mode:
            # Save current state
            self.pre_focus_state = self.window().windowState()
            
            # Hide everything except editor
            self.snippet_widget.hide()
            self.browser_widget.hide()
            self.window().toolbar.hide()
            self.window().tab_widget.tabBar().hide()
            
            # Create exit button as overlay
            self.exit_focus_btn = QPushButton("Exit Focus Mode (Esc)", self)
            self.exit_focus_btn.clicked.connect(self.toggle_focus_mode)
            self.exit_focus_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 1px solid #999;
                    border-radius: 4px;
                    color: #999;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: rgba(153, 153, 153, 0.1);
                }
            """)
            
            # Position button at top right
            self.exit_focus_btn.setFixedSize(160, 30)
            self.exit_focus_btn.move(self.width() - 170, 10)
            self.exit_focus_btn.raise_()
            self.exit_focus_btn.show()
            
            # Go full screen
            self.window().showFullScreen()
            
        else:
            # Restore window state
            if hasattr(self, 'pre_focus_state'):
                self.window().setWindowState(self.pre_focus_state)
            
            # Show UI elements
            self.window().toolbar.show()
            self.window().tab_widget.tabBar().show()
            
            # Restore pane states
            states = self.settings_manager.get_setting('pane_states', {
                'snippets_visible': False,
                'browser_visible': False,
                'sizes': [700, 300, 300]
            })
            self.snippet_widget.setVisible(states.get('snippets_visible', False))
            self.browser_widget.setVisible(states.get('browser_visible', False))
            self.splitter.setSizes(states.get('sizes', [700, 300, 300]))
            
            # Remove exit button
            if hasattr(self, 'exit_focus_btn'):
                self.exit_focus_btn.deleteLater()
                del self.exit_focus_btn

    def resizeEvent(self, event):
        """Handle resize events to keep exit button positioned correctly"""
        super().resizeEvent(event)
        if hasattr(self, 'focus_mode') and self.focus_mode and hasattr(self, 'exit_focus_btn'):
            self.exit_focus_btn.move(self.width() - 170, 10)

    def keyPressEvent(self, event):
        """Handle escape key for focus mode"""
        if event.key() == Qt.Key_Escape and hasattr(self, 'focus_mode') and self.focus_mode:
            self.toggle_focus_mode()
            event.accept()
        else:
            super().keyPressEvent(event)

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

    def get_word_at_cursor(self):
        """Get the word under the cursor"""
        cursor = self.editor.textCursor()
        cursor.select(cursor.WordUnderCursor)
        return cursor.selectedText()

    def replace_word(self, new_word):
        """Replace the word under cursor with new word"""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(cursor.WordUnderCursor)
        cursor.removeSelectedText()
        cursor.insertText(new_word)
        cursor.endEditBlock()

    def save_pane_states(self):
        """Save pane visibility and sizes"""
        states = {
            'snippets_visible': self.snippet_widget.isVisible(),
            'browser_visible': self.browser_widget.isVisible(),
            'sizes': self.splitter.sizes()
        }
        self.settings_manager.save_setting('pane_states', states)

    def eventFilter(self, obj, event):
        """Handle key events for suggestions"""
        if obj == self.editor and event.type() == event.KeyPress:
            # Handle Tab and Enter for suggestions
            if event.key() in (Qt.Key_Tab, Qt.Key_Return):
                if self.current_suggestions:
                    if 0 <= self.suggestion_index < len(self.current_suggestions):
                        self.apply_suggestion(self.current_suggestions[self.suggestion_index])
                        return True
                    self.current_suggestions = []
                    return False
            
            # Clear suggestions on Escape
            elif event.key() == Qt.Key_Escape:
                self.current_suggestions = []
                self.suggestion_index = -1
                return False
            
            # Update suggestions as user types
            elif event.text().isalpha():
                QTimer.singleShot(0, self.check_for_completion)
        
        return super().eventFilter(obj, event)

    def check_for_completion(self):
        """Check if current word matches any user dictionary words"""
        cursor = self.editor.textCursor()
        cursor.select(cursor.WordUnderCursor)
        current_word = cursor.selectedText()
        
        if current_word and len(current_word) >= 2:  # Only suggest for words 2+ chars
            # Get user dictionary
            user_dict = self.settings_manager.get_setting('user_dictionary', [])
            
            # Find matching words
            self.current_suggestions = [
                word for word in user_dict 
                if word.lower().startswith(current_word.lower()) 
                and word.lower() != current_word.lower()
            ]
            
            if self.current_suggestions:
                self.suggestion_index = 0
                # Show inline completion
                completion = self.current_suggestions[0][len(current_word):]
                self.editor.completion_text = completion
                self.editor.viewport().update()
            else:
                self.suggestion_index = -1
                self.editor.completion_text = ""
                self.editor.viewport().update()
        else:
            self.current_suggestions = []
            self.suggestion_index = -1
            self.editor.completion_text = ""
            self.editor.viewport().update()

    def apply_suggestion(self, word):
        """Apply a word suggestion"""
        cursor = self.editor.textCursor()
        cursor.select(cursor.WordUnderCursor)
        cursor.insertText(word)
        self.current_suggestions = []
        self.suggestion_index = -1
        self.editor.completion_text = ""
        self.editor.viewport().update()