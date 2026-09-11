"""Focus mode UI for EditorTab."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QShortcut, QKeySequence

from jottr.translation_manager import _


class FocusModeMixin:
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
                border-radius: 0px;
                padding: 36px 48px;
                font-size: 15pt;
            }
        """)
        
        # Add exit button
        self.exit_focus_btn = QPushButton(_("Exit Focus Mode"), self)
        self.exit_focus_btn.clicked.connect(self.disable_focus_mode)
        self.exit_focus_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
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
                        if (
                            action.property("text_key") == "Focus Mode"
                            or action.text() == _("Focus Mode")
                        ):
                            action.setChecked(False)
                            break

