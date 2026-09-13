"""Embedded browser pane helpers for EditorTab."""
from urllib.parse import quote

from PyQt6.QtCore import QUrl, Qt, QSize
from PyQt6.QtGui import QAction, QShortcut, QKeySequence, QIcon, QFont, QDesktopServices
from PyQt6.QtWidgets import QToolBar, QLineEdit, QLabel, QWidget, QHBoxLayout, QPushButton, QMessageBox

from jottr.translation_manager import _


class BrowserPaneMixin:
    def search_in_browser(self, url):
        """Open a search URL in the browser pane, or the default browser if set."""
        if self.settings_manager.get_setting("search_open_in", "builtin") == "default":
            self.open_url_in_default_browser(QUrl(url))
            return
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
        
    def navigate_to_url(self):
        """Navigate to URL entered in URL bar"""
        url = self.url_bar.text().strip()
        if not url:
            return
            
        url = self.address_to_url(url)
        
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
        from PyQt6.QtWebEngineWidgets import QWebEngineView

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

    def toggle_pane(self, pane_type):
        """Toggle visibility of side panes"""
        if pane_type == "snippets":
            self.animate_widget_visibility(self.snippet_widget, not self.snippet_widget.isVisible())
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
                # Tear down WebEngine before animating — opacity/effects on a live
                # QWebEngineView briefly blank the whole window on Qt6.
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
                self.animate_widget_visibility(self.browser_widget, False, fade=False)
            else:
                # If showing browser, make sure it has reasonable size first
                current_sizes = self.splitter.sizes()
                if current_sizes[2] < 100:
                    editor_size = current_sizes[0]
                    new_browser_size = int(editor_size * 0.3)
                    new_editor_size = editor_size - new_browser_size
                    self.splitter.setSizes([new_editor_size, current_sizes[1], new_browser_size])
        
                # Width-only animation: fade effects are incompatible with WebEngine.
                animation = self.animate_widget_visibility(
                    self.browser_widget, True, fade=False
                )

                def attach_web_view():
                    if not self.intended_widget_visibility(self.browser_widget):
                        return
                    if not self.web_view:
                        self.create_web_view()
                    if hasattr(self, '_pending_url'):
                        self.web_view.setUrl(QUrl(self._pending_url))
                        del self._pending_url
                    else:
                        homepage = self.settings_manager.get_setting(
                            'homepage', 'https://www.google.com/'
                        )
                        self.web_view.setUrl(QUrl(homepage))

                if animation is not None:
                    animation.finished.connect(attach_web_view)
                else:
                    attach_web_view()
        
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

        from PyQt6.QtWebEngineCore import QWebEnginePage
            
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
        
    def address_to_url(self, address):
        """Turn address bar text into a URL; bare words become a Google search."""
        if address.startswith(('http://', 'https://')):
            return address
        if ' ' in address or '.' not in address:
            return f"https://www.google.com/search?q={quote(address)}"
        return 'http://' + address

    def open_in_default_browser(self):
        """Open the address bar URL in the system's default browser.

        QDesktopServices uses the OpenURI portal inside Flatpak and Snap, and
        xdg-open, ShellExecute or NSWorkspace outside a sandbox.
        """
        address = self.url_bar.text().strip()
        if address:
            url = QUrl(self.address_to_url(address))
        elif self.web_view:
            url = self.web_view.url()
        else:
            return
        if url.isEmpty():
            return
        self.open_url_in_default_browser(url)

    def open_url_in_default_browser(self, url):
        """Open a QUrl in the default browser, warning if the system cannot."""
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                _("Browser"),
                _("Could not open {url} in the default browser.").format(url=url.toString()),
            )

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
        self.url_bar.setPlaceholderText(_("Search or enter address"))
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        toolbar_layout.addWidget(self.url_bar)
        
        # Open the address in the system browser
        self.open_external_btn = QPushButton("↗")
        self.open_external_btn.setFixedSize(28, 28)
        self.open_external_btn.setToolTip(_("Open in Default Browser"))
        self.open_external_btn.setAccessibleName(_("Open in Default Browser"))
        self.open_external_btn.clicked.connect(self.open_in_default_browser)
        toolbar_layout.addWidget(self.open_external_btn)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(QFont("Arial", 14))
        close_btn.clicked.connect(lambda: self.toggle_pane("browser"))
        toolbar_layout.addWidget(close_btn)
        
        # Add toolbar to browser layout
        self.browser_widget.layout().addWidget(toolbar)

    def update_nav_buttons(self):
        """Update navigation button states"""
        if self.web_view:
            from PyQt6.QtWebEngineCore import QWebEnginePage
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
