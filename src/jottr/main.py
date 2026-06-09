import sys
if sys.version_info < (3, 10):
    print("Error: Python 3.10 or higher is required")
    sys.exit(1)

import os
import json
import hashlib
import signal
from PyQt6.QtWidgets import (
                            QApplication, QMainWindow, QTabWidget, QWidget,
                            QVBoxLayout, QHBoxLayout, QSplitter, QMenu, QToolBar,
                            QMessageBox, QLabel, QDialog, QSizePolicy,
                            QDialogButtonBox, QTabBar, QFileDialog, QToolButton,
                            QTreeView, QInputDialog, QPushButton, QGraphicsOpacityEffect,
                            QStyle, QStyleOptionTab, QStylePainter, QLineEdit,
                            QGraphicsDropShadowEffect, QStyleFactory)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QEvent, QDir, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QRect, QPoint, QVariantAnimation,
    QAbstractAnimation
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QAction, QShortcut, QFileSystemModel
from editor_tab import EditorTab
from snippet_manager import SnippetManager
from rss_tab import RSSTab
import feedparser
from PyQt6.QtGui import QIcon, QDesktopServices, QKeySequence, QColor, QCursor, QPen
from theme_manager import ThemeManager
from settings_manager import SettingsManager
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QByteArray
from settings_dialog import SettingsDialog
from translation_manager import _, is_rtl_language, set_language
from PyQt6.QtGui import QFont
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import QSize
from font_dialog import FontSelectionDialog
from plugin_manager import PluginManager
# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

# Application constants
APP_NAME = "Jottr"
APP_VERSION = "2.2.0"  # x-release-please-version
APP_HOMEPAGE = "https://github.com/mfat/jottr"
WORKSPACE_SIDEBAR_WIDTH = 210
WORKSPACE_SIDEBAR_MIN_WIDTH = 180
WORKSPACE_SIDEBAR_MAX_WIDTH = 480

class WorkspaceFileSystemModel(QFileSystemModel):
    """File model that exposes full paths as tooltips."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_file_icon = QIcon()
        self.workspace_folder_icon = QIcon()

    def set_workspace_icons(self, file_icon, folder_icon):
        self.workspace_file_icon = file_icon
        self.workspace_folder_icon = folder_icon
        self.layoutChanged.emit()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            return self.filePath(index)
        if (
            role == Qt.ItemDataRole.DecorationRole
            and index.isValid()
            and index.column() == 0
        ):
            icon = self.workspace_folder_icon if self.isDir(index) else self.workspace_file_icon
            if not icon.isNull():
                return icon
        return super().data(index, role)


class WorkspaceTreeView(QTreeView):
    """Tree view with deterministic connector lines and styled disclosure arrows."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connector_color = QColor("#4C8DFF")

    def set_connector_color(self, color):
        self.connector_color = QColor(color)
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        self.draw_connector_lines()

    def draw_connector_lines(self):
        model = self.model()
        if model is None:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(self.connector_color)
        pen.setWidth(1)
        painter.setPen(pen)

        index = self.indexAt(self.viewport().rect().topLeft())
        if not index.isValid():
            index = self.indexAt(QPoint(0, 1))

        while index.isValid():
            rect = self.visualRect(index)
            if rect.top() > self.viewport().height():
                break
            if rect.bottom() >= 0:
                self.draw_index_connectors(painter, index, rect)
            index = self.indexBelow(index)

        painter.end()

    def draw_index_connectors(self, painter, index, rect):
        root = self.rootIndex()
        indent = max(self.indentation(), 10)
        item_left = rect.left()
        current_x = max(6, item_left - (indent // 2))
        row_mid_y = rect.center().y()
        branch_bottom = row_mid_y if self.is_last_child(index) else rect.bottom()
        connector_end_x = item_left + 7

        painter.drawLine(current_x, rect.top(), current_x, branch_bottom)
        painter.drawLine(current_x, row_mid_y, max(current_x, connector_end_x), row_mid_y)

        parent = index.parent()
        ancestor_x = current_x - indent
        while parent.isValid() and parent != root and ancestor_x >= 0:
            if not self.is_last_child(parent):
                painter.drawLine(ancestor_x, rect.top(), ancestor_x, rect.bottom())
            parent = parent.parent()
            ancestor_x -= indent

    def is_last_child(self, index):
        parent = index.parent()
        model = self.model()
        return index.row() >= model.rowCount(parent) - 1


class CustomTitleBar(QWidget):
    """Frameless title bar with classic menus and window controls."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.drag_position = None
        self.search_expanded = False
        self.search_collapsed_min = 220
        self.search_collapsed_max = 380
        self.setObjectName("customTitleBar")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.app_icon = QLabel()
        self.app_icon.setObjectName("titleBarAppIcon")
        self.app_icon.setFixedSize(22, 22)
        self.app_icon.hide()
        layout.addWidget(self.app_icon)

        self.app_title = QLabel(APP_NAME)
        self.app_title.setObjectName("titleBarAppName")
        self.app_title.hide()
        layout.addWidget(self.app_title)

        self.menu_container = QWidget()
        self.menu_container.setObjectName("titleBarMenuSlot")
        self.menu_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        menu_layout = QHBoxLayout(self.menu_container)
        menu_layout.setContentsMargins(0, 0, 10, 0)
        menu_layout.setSpacing(0)
        self.menu_layout = menu_layout
        layout.addWidget(self.menu_container)

        self.left_balance_area = QWidget()
        self.left_balance_area.setObjectName("titleBarDragArea")
        self.left_balance_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.left_balance_area.setFixedWidth(10)
        layout.addWidget(self.left_balance_area)

        self.command_center = QLineEdit()
        self.command_center.setObjectName("titleBarCommandCenter")
        self.command_center.setPlaceholderText(_("Search, files, commands"))
        self.command_center.setToolTip(_("Use keyboard shortcuts or the classic menus for commands"))
        self.command_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.command_center.setClearButtonEnabled(False)
        self.command_center.setFrame(False)
        self.command_center.setFixedHeight(2)
        self.command_center.setFixedWidth(self.search_collapsed_width())
        self.command_center.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        search_shadow = QGraphicsDropShadowEffect(self.command_center)
        search_shadow.setBlurRadius(5)
        search_shadow.setOffset(0, 1)
        search_shadow.setColor(QColor(0, 0, 0, 55))
        self.command_center.setGraphicsEffect(search_shadow)
        self.command_center.installEventFilter(self)
        layout.addWidget(self.command_center)

        self.right_balance_area = QWidget()
        self.right_balance_area.setObjectName("titleBarDragArea")
        self.right_balance_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.right_balance_area, 1)

        self.search_width_animation = QVariantAnimation(self)
        self.search_width_animation.setDuration(170)
        self.search_width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.search_width_animation.valueChanged.connect(lambda value: self.command_center.setFixedWidth(int(value)))

        self.minimize_button = self.create_window_button("−", _("Minimize"))
        self.maximize_button = self.create_window_button("□", _("Maximize"))
        self.close_button = self.create_window_button("×", _("Close"))
        self.close_button.setProperty("role", "close")

        self.window_controls = QWidget()
        self.window_controls.setObjectName("titleBarWindowControls")
        self.window_controls.setFixedWidth(120)
        controls_layout = QHBoxLayout(self.window_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)
        controls_layout.addWidget(self.minimize_button)
        controls_layout.addWidget(self.maximize_button)
        controls_layout.addWidget(self.close_button)
        layout.addWidget(self.window_controls)

        self.minimize_button.clicked.connect(self.window.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(self.window.close)
        self.update_title_icon()
        self.update_maximize_button()
        self.sync_search_balance()
        self.draggable_title_widgets = {
            self.app_icon,
            self.app_title,
            self.left_balance_area,
            self.right_balance_area,
        }
        for widget in self.draggable_title_widgets:
            widget.installEventFilter(self)

    def create_window_button(self, text, tooltip):
        button = QToolButton()
        button.setObjectName("titleBarWindowButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(40, 30)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        return button

    def set_menu_bar(self, menubar):
        while self.menu_layout.count():
            item = self.menu_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        total_width = self.menu_layout.contentsMargins().left() + self.menu_layout.contentsMargins().right()
        self.title_menu_buttons = []
        for action in menubar.actions():
            button = QPushButton(action.text(), self.menu_container)
            button.setObjectName("titleBarMenuButton")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setMinimumWidth(0)
            button.setFlat(True)
            if action.menu():
                menu = action.menu()
                button.clicked.connect(
                    lambda checked=False, button=button, menu=menu: self.show_title_menu(button, menu)
                )
            else:
                button.clicked.connect(action.trigger)
            width = max(button.fontMetrics().horizontalAdvance(action.text()) + 24, 44)
            button.setFixedSize(width, 30)
            self.menu_layout.addWidget(button)
            self.title_menu_buttons.append(button)
            total_width += width

        self.menu_container.setFixedWidth(total_width)
        menubar.hide()
        self.sync_search_balance()

    def show_title_menu(self, button, menu):
        button.setDown(True)
        try:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        finally:
            button.setDown(False)
            button.clearFocus()

    def refresh_title_menu_buttons(self, menubar):
        if not hasattr(self, "title_menu_buttons"):
            self.set_menu_bar(menubar)
            return
        actions = menubar.actions()
        if len(actions) != len(self.title_menu_buttons):
            self.set_menu_bar(menubar)
            return
        total_width = self.menu_layout.contentsMargins().left() + self.menu_layout.contentsMargins().right()
        for button, action in zip(self.title_menu_buttons, actions):
            button.setText(action.text())
            width = max(button.fontMetrics().horizontalAdvance(action.text()) + 24, 44)
            button.setFixedSize(width, 30)
            total_width += width
        self.menu_container.setFixedWidth(total_width)
        self.sync_search_balance()

    def search_available_width(self):
        title_width = max(self.width(), self.window.width() if self.window else 0)
        controls_width = self.window_controls.width() if hasattr(self, "window_controls") else 120
        used_width = self.menu_container.width() + controls_width + 16
        return max(self.search_collapsed_min, title_width - used_width)

    def search_collapsed_width(self):
        return max(
            self.search_collapsed_min,
            min(self.search_collapsed_max, self.search_available_width() // 5)
        )

    def search_expanded_width(self):
        return max(self.search_collapsed_width(), self.search_available_width())

    def animate_search_width(self, expanded):
        self.search_expanded = expanded
        target = self.search_expanded_width() if expanded else self.search_collapsed_width()
        self.search_width_animation.stop()
        self.search_width_animation.setStartValue(self.command_center.width())
        self.search_width_animation.setEndValue(target)
        self.search_width_animation.start()

    def collapse_search_if_empty_from_global_pos(self, global_pos):
        if not self.search_expanded or self.command_center.text():
            return
        if hasattr(global_pos, "toPoint"):
            global_pos = global_pos.toPoint()
        command_pos = self.command_center.mapFromGlobal(global_pos)
        if self.command_center.rect().contains(command_pos):
            return
        self.command_center.clearFocus()
        self.animate_search_width(False)

    def resizeEvent(self, event):
        target = self.search_expanded_width() if self.search_expanded else self.search_collapsed_width()
        if self.search_width_animation.state() != QAbstractAnimation.State.Running:
            self.command_center.setFixedWidth(target)
        super().resizeEvent(event)

    def sync_search_balance(self):
        if not hasattr(self, "left_balance_area") or not hasattr(self, "window_controls"):
            return
        self.left_balance_area.setMinimumWidth(8)
        self.left_balance_area.setFixedWidth(10)
        self.right_balance_area.setMinimumWidth(8)
        target = self.search_expanded_width() if self.search_expanded else self.search_collapsed_width()
        self.command_center.setFixedWidth(target)

    def update_title_icon(self):
        if hasattr(self.window, "build_themed_icon"):
            self.app_icon.setPixmap(self.window.build_themed_icon("theme").pixmap(18, 18))

    def toggle_maximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()
        self.update_maximize_button()

    def update_maximize_button(self):
        if self.window.isMaximized():
            self.maximize_button.setText("❐")
            self.maximize_button.setToolTip(_("Restore"))
        else:
            self.maximize_button.setText("□")
            self.maximize_button.setToolTip(_("Maximize"))

    def begin_window_drag(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        handle = self.window.windowHandle()
        if handle and handle.startSystemMove():
            event.accept()
            return True
        self.drag_position = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
        event.accept()
        return True

    def continue_window_drag(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self.drag_position is None:
            return False
        if self.window.isMaximized():
            self.window.showNormal()
            self.update_maximize_button()
            self.drag_position = QPoint(self.window.width() // 2, self.height() // 2)
        self.window.move(event.globalPosition().toPoint() - self.drag_position)
        event.accept()
        return True

    def eventFilter(self, watched, event):
        if watched is getattr(self, "command_center", None):
            if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
                self.animate_search_width(True)
            elif event.type() == QEvent.Type.FocusOut and not self.command_center.text():
                self.animate_search_width(False)
            return super().eventFilter(watched, event)

        if watched in getattr(self, "draggable_title_widgets", set()):
            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                self.toggle_maximized()
                event.accept()
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                return self.begin_window_drag(event)
            if event.type() == QEvent.Type.MouseMove:
                return self.continue_window_drag(event)
            if event.type() == QEvent.Type.MouseButtonRelease:
                self.drag_position = None
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if self.begin_window_drag(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.continue_window_drag(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_maximize_button()
        super().changeEvent(event)


class LeftAlignedDocumentTabBar(QTabBar):
    """Document tab bar that keeps labels centered in the tab area."""

    label_left_padding = 8
    label_right_padding = 30
    icon_text_gap = 5
    icon_vertical_offset = -1
    underline_height = 2

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            self.draw_left_aligned_label(painter, option, index)

    def tab_text_color(self, selected=False):
        window = self.window()
        settings_manager = getattr(window, "settings_manager", None)
        if settings_manager is None:
            return self.palette().windowText().color()
        theme = ThemeManager.get_theme(
            settings_manager.get_ui_theme(),
            settings_manager.get_custom_themes()
        )
        return QColor(theme["app"]["text" if selected else "muted"])

    def label_contents_rect(self, tab_rect):
        return tab_rect.adjusted(
            self.label_left_padding,
            0,
            -self.label_right_padding,
            -self.underline_height
        )

    def draw_left_aligned_label(self, painter, option, index):
        label_rect = self.label_contents_rect(option.rect)
        icon = self.tabIcon(index)
        icon_size = self.iconSize() if not icon.isNull() else QSize(0, 0)
        icon_width = icon_size.width() if not icon.isNull() else 0
        gap = self.icon_text_gap if icon_width else 0
        available_text_width = max(0, label_rect.width() - icon_width - gap)
        text = painter.fontMetrics().elidedText(
            self.tabText(index),
            Qt.TextElideMode.ElideRight,
            available_text_width
        )
        text_width = painter.fontMetrics().horizontalAdvance(text)
        content_width = min(label_rect.width(), icon_width + gap + text_width)
        start_x = label_rect.left() + max(0, (label_rect.width() - content_width) // 2)

        if icon_width:
            icon_rect = QRect(
                start_x,
                label_rect.top() + (label_rect.height() - icon_size.height()) // 2 + self.icon_vertical_offset,
                icon_size.width(),
                icon_size.height()
            )
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            start_x = icon_rect.right() + 1 + gap

        text_rect = QRect(
            start_x,
            label_rect.top(),
            max(0, label_rect.right() - start_x + 1),
            label_rect.height()
        )
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(self.tab_text_color(selected))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
            text
        )


class TextEditorApp(QMainWindow):
    def __init__(self, file_path=None): 
        super().__init__()
        self.setObjectName("appWindow")
        self.setProperty("chromeMaximized", False)
        self.resize_margin = 6
        self.resize_edges = None
        self.resize_start_geometry = None
        self.resize_start_pos = None
        self.resize_cursor_active = False
        
        # Create settings manager first
        self.settings_manager = SettingsManager()
        language = self.settings_manager.get_setting("language", "en_US")
        set_language(language)
        self.apply_layout_direction(language)
        
        # Create snippet manager with settings manager
        self.snippet_manager = SnippetManager(self.settings_manager)
        
        # Load icons from Base64-encoded SVG data
        self.icons = {
            "about": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAxMSAzIEMgNi41NjggMyAzIDYuNTY4IDMgMTEgQyAzIDE1LjQzMiA2LjU2OCAxOSAxMSAxOSBDIDE1LjQzMiAxOSAxOSAxNS40MzIgMTkgMTEgQyAxOSA2LjU2OCAxNS40MzIgMyAxMSAzIHogTSAxMSA0IEMgMTQuODc4IDQgMTggNy4xMjIgMTggMTEgQyAxOCAxNC44NzggMTQuODc4IDE4IDExIDE4IEMgNy4xMjIgMTggNCAxNC44NzggNCAxMSBDIDQgNy4xMjIgNy4xMjIgNCAxMSA0IHogTSAxMCA2IEwgMTAgOCBMIDEyIDggTCAxMiA2IEwgMTAgNiB6IE0gMTAgOSBMIDEwIDE2IEwgMTIgMTYgTCAxMiA5IEwgMTAgOSB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "applications-system": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iYyIgeDE9IjEwLjIiIHgyPSIxNi4wNjkiIHkxPSIzIiB5Mj0iOC44MTciIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iI0NFRDlEQyIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNDRUQ5REMiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZCIgeDE9IjEwLjIiIHgyPSIxNi4wNjkiIHkxPSIzIiB5Mj0iOC44MTciIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iI0NFRDlEQyIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNDRUQ5REMiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZSIgeDE9IjEwLjIiIHgyPSIxNi4wNjkiIHkxPSIzIiB5Mj0iOC44MTciIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iI0NFRDlEQyIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNDRUQ5REMiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZiIgeDE9IjEwLjIiIHgyPSIxNi4wNjkiIHkxPSIzIiB5Mj0iOC44MTciIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iI0NFRDlEQyIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNDRUQ5REMiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZyIgeDE9IjEwLjIiIHgyPSIxNi4wNjkiIHkxPSIzIiB5Mj0iOC44MTciIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iI0NFRDlEQyIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNDRUQ5REMiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iaCIgeDE9IjEwLjkyIiB4Mj0iMTkuMDAyIiB5MT0iMTAuOTE4IiB5Mj0iMTguOTk4IiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIHN0b3AtY29sb3I9IiM0QzVCNjQiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjNUE2Qjc1Ii8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogICAgPGxpbmVhckdyYWRpZW50IGlkPSJpIiB4MT0iMTAuOTIiIHgyPSIxOS4wMDIiIHkxPSIxMC45MTgiIHkyPSIxOC45OTgiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iIzRDNUI2NCIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiM1QTZCNzUiLz4KICAgIDwvbGluZWFyR3JhZGllbnQ+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImoiIHgxPSIxMC45MiIgeDI9IjE5LjAwMiIgeTE9IjEwLjkxOCIgeTI9IjE4Ljk5OCIgZ3JhZGllbnRVbml0cz0idXNlclNwYWNlT25Vc2UiPgogICAgICA8c3RvcCBzdG9wLWNvbG9yPSIjNEM1QjY0Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iMSIgc3RvcC1jb2xvcj0iIzVBNkI3NSIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iayIgeDE9IjEwLjkyIiB4Mj0iMTkuMDAyIiB5MT0iMTAuOTE4IiB5Mj0iMTguOTk4IiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIHN0b3AtY29sb3I9IiM0QzVCNjQiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjNUE2Qjc1Ii8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogICAgPGxpbmVhckdyYWRpZW50IGlkPSJsIiB4MT0iMTAuOTIiIHgyPSIxOS4wMDIiIHkxPSIxMC45MTgiIHkyPSIxOC45OTgiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj4KICAgICAgPHN0b3Agc3RvcC1jb2xvcj0iIzRDNUI2NCIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiM1QTZCNzUiLz4KICAgIDwvbGluZWFyR3JhZGllbnQ+CiAgICA8cmFkaWFsR3JhZGllbnQgaWQ9ImEiIGN4PSIwIiBjeT0iMCIgcj0iMSIgZ3JhZGllbnRUcmFuc2Zvcm09InJvdGF0ZSgtMTM1IDE1LjMyIDYuMzQ2KXNjYWxlKDI0LjUxMjk5IDE4Ljg3MDIpIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIHN0b3AtY29sb3I9IiM1QzY3NzIiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSIuNTg0IiBzdG9wLWNvbG9yPSIjNkE3QTg0Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iLjc1NiIgc3RvcC1jb2xvcj0iIzkwOURBNiIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNCMkJGQkYiLz4KICAgIDwvcmFkaWFsR3JhZGllbnQ+CiAgICA8cmFkaWFsR3JhZGllbnQgaWQ9ImIiIGN4PSIwIiBjeT0iMCIgcj0iMSIgZ3JhZGllbnRUcmFuc2Zvcm09InJvdGF0ZSgtMTM1IDE1LjMyIDYuMzQ2KXNjYWxlKDI0LjUxMjk5IDE4Ljg3MDIpIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIHN0b3AtY29sb3I9IiM1QzY3NzIiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSIuNTg0IiBzdG9wLWNvbG9yPSIjNkE3QTg0Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iLjc1NiIgc3RvcC1jb2xvcj0iIzkwOURBNiIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3AtY29sb3I9IiNCMkJGQkYiLz4KICAgIDwvcmFkaWFsR3JhZGllbnQ+CiAgICA8cmFkaWFsR3JhZGllbnQgaWQ9Im0iIGN4PSIwIiBjeT0iMCIgcj0iMSIgZ3JhZGllbnRUcmFuc2Zvcm09Im1hdHJpeCgtMTcuMTg3NSAtMTcuMTg3NSAxMy4yMzA5NiAtMTMuMjMwOTYgMjIgMjIpIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wIG9mZnNldD0iLjQ0IiBzdG9wLWNvbG9yPSIjNjQ3NjgxIi8+CiAgICAgIDxzdG9wIG9mZnNldD0iLjUiIHN0b3AtY29sb3I9IiM2ODc3ODEiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSIuNjA2IiBzdG9wLWNvbG9yPSIjOTA5REE2Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iLjkwOCIgc3RvcC1jb2xvcj0iI0Q5RTdFOCIvPgogICAgPC9yYWRpYWxHcmFkaWVudD4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBmaWxsPSJ1cmwoI2EpIiBkPSJNOC41NDYgMTUuOTI0YTUuNTI0IDUuNTI0IDAgMCAxLTIuNDctMi40N2wtMS40MzYgMi4yMmEuMjUuMjUgMCAwIDAgLjAzMy4zMTNsMS4zNCAxLjM0YS4yNS4yNSAwIDAgMCAuMzEzLjAzM3oiLz4KICAgIDxwYXRoIGZpbGw9InVybCgjYikiIGZpbGwtcnVsZT0iZXZlbm9kZCIgZD0ibTkuMjU0IDE2LjIxNy41NTQgMi41ODVhLjI1LjI1IDAgMCAwIC4yNDQuMTk4aDEuODk2YS4yNS4yNSAwIDAgMCAuMjQ0LS4xOThsLjU1NC0yLjU4NS43MDgtLjI5MyAyLjIyIDEuNDM2YS4yNS4yNSAwIDAgMCAuMzEzLS4wMzNsMS4zNC0xLjM0YS4yNS4yNSAwIDAgMCAuMDMzLS4zMTNsLTEuNDM2LTIuMjIuMjkzLS43MDggMi41ODUtLjU1NGEuMjUuMjUgMCAwIDAgLjE5OC0uMjQ0di0xLjg5NmEuMjUuMjUgMCAwIDAtLjE5OC0uMjQ0bC0yLjU4NS0uNTU0LS4yOTMtLjcwOCAxLjQzNi0yLjIyYS4yNS4yNSAwIDAgMC0uMDMzLS4zMTNsLTEuMzQtMS4zNGEuMjUuMjUgMCAwIDAtLjMxMy0uMDMzbC0yLjIyIDEuNDM2LS43MDgtLjI5My0uNTU0LTIuNTg1QS4yNS4yNSAwIDAgMCAxMS45NDggM2gtMS44OTZhLjI1LjI1IDAgMCAwLS4yNDQuMTk4bC0uNTU0IDIuNTg1LS43MDguMjkzLTIuMjItMS40MzZhLjI1LjI1IDAgMCAwLS4zMTMuMDMzbC0xLjM0IDEuMzRhLjI1LjI1IDAgMCAwLS4wMzMuMzEzbDEuNDM2IDIuMjItLjI5My43MDgtMi41ODUuNTU0YS4yNS4yNSAwIDAgMC0uMTk4LjI0NHYxLjg5NmMwIC4xMTguMDgyLjIyLjE5OC4yNDRsMi41ODUuNTU0LjI5My43MDhhNS41MjQgNS41MjQgMCAwIDAgMi40NyAyLjQ3ek04IDExbDMgMyAzLTMtMy0zeiIgY2xpcC1ydWxlPSJldmVub2RkIi8+CiAgICA8ZyBvcGFjaXR5PSIuNCI+CiAgICAgIDxwYXRoIGZpbGw9InVybCgjYykiIGQ9Im0xMi41MTcgNS43MTItLjMyNS0xLjUxNEEuMjUuMjUgMCAwIDAgMTEuOTQ4IDRoLTEuODk2YS4yNS4yNSAwIDAgMC0uMjQ0LjE5OGwtLjMyNSAxLjUxNGE1LjQ1NCA1LjQ1NCAwIDAgMC0uMjMuMDcxbC41NTUtMi41ODVBLjI1LjI1IDAgMCAxIDEwLjA1MiAzaDEuODk2YS4yNS4yNSAwIDAgMSAuMjQ0LjE5OGwuNTU0IDIuNTg1YTUuNDU2IDUuNDU2IDAgMCAwLS4yMy0uMDcxIi8+CiAgICAgIDxwYXRoIGZpbGw9InVybCgjZCkiIGQ9Ik03Ljc1MSA2LjU2MmMuMjUtLjE4My41MTYtLjM0Ni43OTUtLjQ4Nkw2LjMyNiA0LjY0YS4yNS4yNSAwIDAgMC0uMzEzLjAzM2wtMS4zNCAxLjM0YS4yNS4yNSAwIDAgMC0uMDMzLjMxM2wuMjgzLjQzNyAxLjA5LTEuMDlhLjI1LjI1IDAgMCAxIC4zMTMtLjAzM3oiLz4KICAgICAgPHBhdGggZmlsbD0idXJsKCNlKSIgZD0iTTMgMTEuMDUyYS4yNS4yNSAwIDAgMSAuMTk4LS4yNDRsMi4zNDUtLjUwM2MuMDQ2LS4zNjMuMTI3LS43MTQuMjQtMS4wNTFsLTIuNTg1LjU1NGEuMjUuMjUgMCAwIDAtLjE5OC4yNDR6Ii8+CiAgICAgIDxwYXRoIGZpbGw9InVybCgjZikiIGZpbGwtcnVsZT0iZXZlbm9kZCIgZD0ibTQuNjQgMTUuNjc0IDEuMTcxLTEuODEuMjY1LjU5LTEuMTUzIDEuNzgzLS4yNS0uMjVhLjI1LjI1IDAgMCAxLS4wMzMtLjMxMyIgY2xpcC1ydWxlPSJldmVub2RkIi8+CiAgICAgIDxwYXRoIGZpbGw9InVybCgjZykiIGZpbGwtcnVsZT0iZXZlbm9kZCIgZD0ibTE1LjA0MyA2LjA0OC42MzEtLjQwOGEuMjUuMjUgMCAwIDEgLjMxMy4wMzNsMS4wOSAxLjA5LjI4My0uNDM3YS4yNS4yNSAwIDAgMC0uMDMzLS4zMTNsLTEuMzQtMS4zNGEuMjUuMjUgMCAwIDAtLjMxMy0uMDMzbC0xLjIzOC44MDF6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiLz4KICAgIDwvZz4KICAgIDxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik0xNi40NzcgMTEuNWE1LjUgNS41IDAgMSAwLTEwLjk1NSAwIDUuNSA1LjUgMCAwIDEgMTAuOTU1IDAiIG9wYWNpdHk9Ii4yIi8+CiAgICA8cGF0aCBmaWxsPSJ1cmwoI2gpIiBkPSJNOC41NDYgMTUuOTI0YTUuNDkyIDUuNDkyIDAgMCAxLTEuNDM1LTEuMDM1bDEuMTkyIDEuMTkyeiIvPgogICAgPHBhdGggZmlsbD0idXJsKCNpKSIgZD0ibTExLjIyMiAxOS0xLjc0Ni0xLjc0Ni0uMjIyLTEuMDM3YTUuNDg0IDUuNDg0IDAgMCAwIDEuOTQ5LjI4IDUuNDgzIDUuNDgzIDAgMCAwIDEuNTQzLS4yOGwtLjU1NCAyLjU4NWEuMjUuMjUgMCAwIDEtLjI0NC4xOTh6Ii8+CiAgICA8cGF0aCBmaWxsPSJ1cmwoI2opIiBkPSJNMTcuMjU0IDkuNDc2IDE5IDExLjIyMnYuNzI2YS4yNS4yNSAwIDAgMS0uMTk4LjI0NGwtMi41ODUuNTU0QTUuNDk0IDUuNDk0IDAgMCAwIDE2LjUgMTFjMC0uNjEtLjEtMS4xOTgtLjI4My0xLjc0NnoiLz4KICAgIDxwYXRoIGZpbGw9InVybCgjaykiIGQ9Im0xNC45MDUgNy4xMjYgMS4xNzYgMS4xNzctLjE1Ny4yNDNhNS40ODYgNS40ODYgMCAwIDAtMS4wMi0xLjQyIi8+CiAgICA8cGF0aCBmaWxsPSJ1cmwoI2wpIiBkPSJNMTMuNDU0IDE1LjkyNGE1LjQ5OCA1LjQ5OCAwIDAgMCAxLjQzNS0xLjAzNSA1LjQ5MyA1LjQ5MyAwIDAgMCAxLjAzNS0xLjQzNWwxLjQzNiAyLjIyYS4yNS4yNSAwIDAgMS0uMDMzLjMxM2wtMS4zNCAxLjM0YS4yNS4yNSAwIDAgMS0uMzEzLjAzM3oiLz4KICAgIDxwYXRoIGZpbGw9InVybCgjbSkiIGZpbGwtcnVsZT0iZXZlbm9kZCIgZD0iTTE0Ljg5IDE0Ljg5YTUuNSA1LjUgMCAxIDAtNy43OC03Ljc4IDUuNSA1LjUgMCAwIDAgNy43NzggNy43OE0xMSAxNGEzIDMgMCAxIDAgMC02IDMgMyAwIDAgMCAwIDYiIGNsaXAtcnVsZT0iZXZlbm9kZCIvPgogICAgPHBhdGggZmlsbD0iIzgxOTA5OCIgZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTEgMTNhMiAyIDAgMSAwIDAtNCAyIDIgMCAwIDAgMCA0bTAgMWEzIDMgMCAxIDAgMC02IDMgMyAwIDAgMCAwIDYiIGNsaXAtcnVsZT0iZXZlbm9kZCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "browser": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAgICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgICAgICAgICBjb2xvcjojMjMyNjI5OwogICAgICAgICAgICB9CiAgICAgICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBzdHlsZT0iZmlsbDpjdXJyZW50Q29sb3I7ZmlsbC1vcGFjaXR5OjE7c3Ryb2tlOm5vbmUiIGQ9Ik0gMTEgMTEgbSAtOSAwIGEgOCA4IDAgMSAwIDE4IDAgYSA4IDggMCAxIDAgLTE4IDAgeiBNIDExIDExIG0gLTggMCBhIDcgNyAwIDEgMSAxNiAwIGEgNyA3IDAgMSAxIC0xNiAwIHogTSAxNi40IDUuNiBMIDkuNCA5LjQgTCA1LjYgMTYuNCBMIDEyLjYgMTIuNiB6IE0gMTEgMTEgbSAtMSAwIGEgMC41IDAuNSAwIDEgMSAyIDAgYSAwLjUgMC41IDAgMSAxIC0yIDAgeiBNIDIuNSAxMSBMIDIuNSAxMiBMIDUgMTEgeiBNIDExIDIuNSBMIDEwIDIuNSBMIDExIDUgeiBNIDE5LjUgMTEgTCAxOS41IDEwIEwgMTcgMTEgeiBNIDExIDE5LjUgTCAxMiAxOS41IEwgMTEgMTcgeiIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "color-mode-invert-text": "data:image/svg+xml;base64,PCFET0NUWVBFIHN2Zz4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZlcnNpb249IjEuMSIgdmlld0JveD0iMCAwIDI0IDI0IiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiPgogIDxkZWZzPgogICAgPHN0eWxlIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSIgdHlwZT0idGV4dC9jc3MiPgogICAgICAgICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgICAgICAgICBjb2xvcjojMjMyNjI5OwogICAgICAgICAgICB9CiAgICAgICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgc3R5bGU9ImZpbGw6Y3VycmVudENvbG9yOyBmaWxsLW9wYWNpdHk6MTsgc3Ryb2tlOm5vbmUiIGQ9Ik0gMTEgMyBMIDExIDQgTCAxMi4xNzk3IDQgQyAxMy4yOTU0IDcuMjM5NDIgMTQuNDIzNCAxMC40NzQ4IDE1LjUzMTMgMTMuNzE2OCBDIDE2LjAxODQgMTUuMTU1NCAxNi41NzU0IDE2LjU3MDYgMTcuMDg5OCAxOCBMIDE1LjM0MTggMTggQyAxNC44MDAxIDE2LjUyMDggMTQuMjU4NSAxNS4wNDE3IDEzLjcxNjggMTMuNTYyNSBMIDExIDEzLjU2MjUgTCAxMSAxOSBMIDE5IDE5IEwgMTkgMyBMIDExIDMgWiBNIDExIDEzLjU2MjUgTCAxMSAxMi4yODEzIEwgOC44OTQ1MyAxMi4yODEzIEMgOS41OTYzNiAxMC4yNjc2IDEwLjI5ODIgOC4yNTM5MSAxMSA2LjI0MDIzIEwgMTEgNCBMIDkuOTEwMTYgNCBDIDguNzg2NTkgNy4yNjk2IDcuNjQxMjUgMTAuNTMyNiA2LjUzMTI1IDEzLjgwNjYgQyA2LjA0MzE0IDE1LjIxMjEgNS41MDY4MyAxNi42MDA5IDUgMTggTCA2Ljc0ODA1IDE4IEMgNy4yODk3MiAxNi41MjA4IDcuODMxMzggMTUuMDQxNyA4LjM3MzA1IDEzLjU2MjUgTCAxMSAxMy41NjI1IFogTSAxMSA2LjI0MDIzIEwgMTEgMTIuMjgxMyBMIDEzLjE5NTMgMTIuMjgxMyBDIDEyLjQ3ODUgMTAuMjI0NiAxMS43NjE3IDguMTY3OTcgMTEuMDQ0OSA2LjExMTMzIEMgMTEuMDI5OSA2LjE1NDMgMTEuMDE1IDYuMTk3MjcgMTEgNi4yNDAyMyBMIDExIDYuMjQwMjMgWiIvPgogIDwvZz4KPC9zdmc+Cg==",
            "document-open": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA0IDMgTCA0IDE5IEwgOSAxOSBMIDkgMTggTCA1IDE4IEwgNSA0IEwgMTMgNCBMIDEzIDggTCAxNyA4IEwgMTcgMTEgTCAxOCAxMSBMIDE4IDcgTCAxNCAzIEwgMTQgMyBMIDE0IDMgTCA1IDMgTCA0IDMgeiBNIDEwIDEyIEwgMTAgMTkgTCAxOCAxOSBMIDE4IDEzIEwgMTUgMTMgTCAxNCAxMiBMIDE0IDEyIEwgMTQgMTIgTCAxMCAxMiB6IE0gMTMuMSAxNCBMIDE3IDE0IEwgMTcgMTggTCAxMSAxOCBMIDExIDE1IEwgMTIgMTUgTCAxMy4xIDE0IHogIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "find": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA5IDMgQyA1LjY3NTk5NTIgMyAzIDUuNjc1OTk1MiAzIDkgQyAzIDEyLjMyNDAwNSA1LjY3NTk5NTIgMTUgOSAxNSBDIDEwLjQ4MTIwNSAxNSAxMS44MzA1ODQgMTQuNDY1MzE4IDEyLjg3NSAxMy41ODIwMzEgTCAxOC4yOTI5NjkgMTkgTCAxOSAxOC4yOTI5NjkgTCAxMy41ODIwMzEgMTIuODc1IEMgMTQuNDY1MzE4IDExLjgzMDU4NCAxNSAxMC40ODEyMDUgMTUgOSBDIDE1IDUuNjc1OTk1MiAxMi4zMjQwMDUgMyA5IDMgeiBNIDkgNCBDIDExLjc3MDAwNSA0IDE0IDYuMjI5OTk1MiAxNCA5IEMgMTQgMTEuNzcwMDA1IDExLjc3MDAwNSAxNCA5IDE0IEMgNi4yMjk5OTUyIDE0IDQgMTEuNzcwMDA1IDQgOSBDIDQgNi4yMjk5OTUyIDYuMjI5OTk1MiA0IDkgNCB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "focus-mode": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmVyc2lvbj0iMS4xIj4KIDxkZWZzPgogIDxzdHlsZSBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiIHR5cGU9InRleHQvY3NzIj4KICAgLkNvbG9yU2NoZW1lLVRleHQgeyBjb2xvcjojNDQ0NDQ0OyB9IC5Db2xvclNjaGVtZS1IaWdobGlnaHQgeyBjb2xvcjojNDI4NWY0OyB9IC5Db2xvclNjaGVtZS1OZXV0cmFsVGV4dCB7IGNvbG9yOiNmZjk4MDA7IH0gLkNvbG9yU2NoZW1lLVBvc2l0aXZlVGV4dCB7IGNvbG9yOiM0Y2FmNTA7IH0gLkNvbG9yU2NoZW1lLU5lZ2F0aXZlVGV4dCB7IGNvbG9yOiNmNDQzMzY7IH0KICA8L3N0eWxlPgogPC9kZWZzPgogPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoNCw0KSI+CiAgPHBhdGggc3R5bGU9ImZpbGw6Y3VycmVudENvbG9yIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgZD0iTSAyLDIgQyAxLDIgMSwzIDEsMyBWIDcgSCAzIFYgNCBIIDYgViAyIFogTSAxMCwyIFYgNCBIIDEzIFYgNyBIIDE1IFYgMyBDIDE1LDIgMTQsMiAxNCwyIFogTSAxLDkgViAxMyBDIDEsMTQgMiwxNCAyLDE0IEggNiBWIDEyIEggMyBWIDkgWiBNIDEzLDkgViAxMiBIIDEwIFYgMTQgSCAxNCBDIDE0LDE0IDE1LDE0IDE1LDEzIFYgOSBaIi8+CiA8L2c+Cjwvc3ZnPgo=",
            "font": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAzIDMgTCAzIDQgTCAzIDYgTCA0IDYgTCA0IDQgTCAxMCA0IEwgMTAgMTggTCA4IDE4IEwgNyAxOCBMIDcgMTkgTCAxNSAxOSBMIDE1IDE4IEwgMTQgMTggTCAxMiAxOCBMIDEyIDQgTCAxOCA0IEwgMTggNiBMIDE5IDYgTCAxOSA0IEwgMTkgMyBMIDMgMyB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "format-text-color": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAxNy41IDQgQyAxNy4wMTM1NDUgNS43MDI1IDE1LjgyMTggNy4xNjYwOTA2IDE1LjI5Njg3NSA4LjMzNzg5MDYgQyAxNS4xMTMxNzUgOC42ODYyOTA2IDE1IDkuMDc3MyAxNSA5LjUgQyAxNSAxMC44ODUgMTYuMTE1IDEyIDE3LjUgMTIgQyAxOC44ODUgMTIgMjAgMTAuODg1IDIwIDkuNSBDIDIwIDkuMDc3MyAxOS44ODY4MjUgOC42ODYyOTA2IDE5LjcwMzEyNSA4LjMzNzg5MDYgQyAxOS4xNzgyIDcuMTY2MDkwNiAxNy45ODY0NSA1LjcwMjUgMTcuNSA0IHogTSA0IDggTCA0IDEwIEwgOCAxMCBMIDggMjAgTCAxMCAyMCBMIDEwIDEwIEwgMTQgMTAgTCAxNCA4IEwgNCA4IHogIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "gtk-select-font": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA5LjkxMDE1NjIgNCBMIDYuNTk1NzAzMSAxMy41OTM3NSBMIDYuNDcyNjU2MiAxNCBMIDUgMTggTCA2LjY1ODIwMzEgMTggTCA4LjI4MzIwMzEgMTMuNTYyNSBMIDEzLjcxNjc5NyAxMy41NjI1IEwgMTUuMzQxNzk3IDE4IEwgMTcgMTggTCAxNS41MjczNDQgMTQgTCAxNS40MDQyOTcgMTMuNTkzNzUgTCAxMi4wODk4NDQgNCBMIDExLjg3NSA0IEwgMTAuMTI1IDQgTCA5LjkxMDE1NjIgNCB6IE0gMTEuMDE1NjI1IDUuOTM3NSBMIDEzLjE5NTMxMiAxMi4yODEyNSBMIDguODA0Njg3NSAxMi4yODEyNSBMIDExLjAxNTYyNSA1LjkzNzUgeiAiIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0Ii8+CiAgICA8cGF0aCBzdHlsZT0iZmlsbDpjdXJyZW50Q29sb3I7ZmlsbC1vcGFjaXR5OjE7c3Ryb2tlOm5vbmUiIGQ9Ik0gMTggMyBDIDE3LjQ0NzcxIDMgMTcgMy40NDc3IDE3IDQgQyAxNyA0LjU1MjMgMTcuNDQ3NzEgNSAxOCA1IEMgMTguNTUyMjggNSAxOSA0LjU1MjMgMTkgNCBDIDE5IDMuNDQ3NyAxOC41NTIyOCAzIDE4IDMgeiBNIDE4IDcgQyAxNy40NDc3MSA3IDE3IDcuNDQ3NyAxNyA4IEMgMTcgOC41NTIzIDE3LjQ0NzcxIDkgMTggOSBDIDE4LjU1MjI4IDkgMTkgOC41NTIzIDE5IDggQyAxOSA3LjQ0NzcgMTguNTUyMjggNyAxOCA3IHogTSAxOCAxMSBDIDE3LjQ0NzcxIDExIDE3IDExLjQ0NzcgMTcgMTIgQyAxNyAxMi41NTIzIDE3LjQ0NzcxIDEzIDE4IDEzIEMgMTguNTUyMjggMTMgMTkgMTIuNTUyMyAxOSAxMiBDIDE5IDExLjQ0NzcgMTguNTUyMjggMTEgMTggMTEgeiAiIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0Ii8+CiAgPC9nPgo8L3N2Zz4K",
            "help": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAxMSAzIEMgOS4xMjE4OTcxIDMgNy40MDMwNTU1IDMuNjQ1MDM3NCA2LjA0MTAxNTYgNC43MjA3MDMxIEMgNi4wMzU5MDU2IDQuNzI0NzMzMSA2LjAzMDQ4NTYgNC43MjgzNzI5IDYuMDI1MzkwNiA0LjczMjQyMTkgQyA1Ljk3MjM0MzYgNC43NzQ1MjU5IDUuOTE5MTIwNiA0LjgxNTk1OTkgNS44NjcxODc1IDQuODU5Mzc1IEwgNS4wMDc4MTI1IDQgTCAzIDQgTCAzIDYuMDA3ODEyNSBMIDQuMDQyOTY4OCA3LjA1MDc4MTIgQyAzLjM4Mjc2NzggOC4yMTUzNzM3IDMgOS41NjA0MzkyIDMgMTEgQyAzIDEyLjQzOTU2MSAzLjM4Mjc2NzggMTMuNzg0NjI2IDQuMDQyOTY4OCAxNC45NDkyMTkgTCAzIDE1Ljk5MjE4OCBMIDMgMTggTCA1LjAwNzgxMjUgMTggTCA1Ljg2NzE4NzUgMTcuMTQwNjI1IEMgNS45MTkxMjA1IDE3LjE4NDAzNSA1Ljk3MjM0MzcgMTcuMjI1NDc1IDYuMDI1MzkwNiAxNy4yNjc1NzggQyA2LjAzMDQ5MDYgMTcuMjcxNTc4IDYuMDM1OTA4NiAxNy4yNzUyNzcgNi4wNDEwMTU2IDE3LjI3OTI5NyBDIDcuNDAzMDU1NSAxOC4zNTQ5NjIgOS4xMjE4OTcxIDE5IDExIDE5IEMgMTIuOTU4NDQzIDE5IDE0Ljc0NTA5OSAxOC4zMDA3MTYgMTYuMTMyODEyIDE3LjE0MDYyNSBMIDE2Ljk5MjE4OCAxOCBMIDE5IDE4IEwgMTkgMTUuOTkyMTg4IEwgMTcuOTU3MDMxIDE0Ljk0OTIxOSBDIDE4LjYxNzIzMiAxMy43ODQ2MjYgMTkgMTIuNDM5NTYxIDE5IDExIEMgMTkgOS41NjA0MzkyIDE4LjYxNzIzMiA4LjIxNTM3MzYgMTcuOTU3MDMxIDcuMDUwNzgxMiBMIDE5IDYuMDA3ODEyNSBMIDE5IDQgTCAxNi45OTIxODggNCBMIDE2LjEzMjgxMiA0Ljg1OTM3NSBDIDE2LjA4MDg4MyA0LjgxNTk2IDE2LjAyNzY1NiA0Ljc3NDUyNiAxNS45NzQ2MDkgNC43MzI0MjE5IEMgMTUuOTY5NTA5IDQuNzI4MzgxOSAxNS45NjQwOTQgNC43MjQ3MzIxIDE1Ljk1ODk4NCA0LjcyMDcwMzEgQyAxNC41OTY5NDkgMy42NDUwMzc2IDEyLjg3ODEwMyAzIDExIDMgeiBNIDExIDQgQyAxMi4yNDA0NzUgNCAxMy40MDE4MjggNC4zMjEzNjU3IDE0LjQxMDE1NiA0Ljg4MjgxMjUgTCAxMi4xMTcxODggNy4xNzU3ODEyIEMgMTEuNzYwNzQ0IDcuMDcyMjc0OSAxMS4zOTA3MTEgNyAxMSA3IEMgMTAuNjA5Mjg5IDcgMTAuMjM5MjU1IDcuMDcyMjc1IDkuODgyODEyNSA3LjE3NTc4MTIgTCA4LjcwNzAzMTIgNiBMIDcuNTg5ODQzOCA0Ljg4MjgxMjUgQyA4LjU5ODE3MjMgNC4zMjEzNjU3IDkuNzU5NTI1MyA0IDExIDQgeiBNIDQuMzAwNzgxMiA0LjcwNzAzMTIgTCA1LjE0NDUzMTIgNS41NTA3ODEyIEMgNS4wMDE3NzYxIDUuNzA0MTcyMyA0Ljg2Mjg1MDYgNS44NjEwNjUgNC43MzI0MjE5IDYuMDI1MzkwNiBDIDQuNzI4MzgxOSA2LjAzMDQ5MDYgNC43MjQ3MzIxIDYuMDM1OTA4NiA0LjcyMDcwMzEgNi4wNDEwMTU2IEMgNC42ODAzMzUxIDYuMDkyMTMwNiA0LjY0MjY0ODEgNi4xNDUxNDQ0IDQuNjAzNTE1NiA2LjE5NzI2NTYgTCAzLjcwNzAzMTIgNS4zMDA3ODEyIEwgNC4zMDA3ODEyIDQuNzA3MDMxMiB6IE0gMTcuNjk5MjE5IDQuNzA3MDMxMiBMIDE4LjI5Mjk2OSA1LjMwMDc4MTIgTCAxNy4zOTY0ODQgNi4xOTcyNjU2IEMgMTcuMjI3Mzg2IDUuOTcyMDM5MSAxNy4wNDY5NzMgNS43NTY1NTM0IDE2Ljg1NTQ2OSA1LjU1MDc4MTIgTCAxNy42OTkyMTkgNC43MDcwMzEyIHogTSA0Ljg4MjgxMjUgNy41ODk4NDM4IEwgNy4xNzU3ODEyIDkuODgyODEyNSBDIDcuMDcyMjc0OSAxMC4yMzkyNTUgNyAxMC42MDkyODkgNyAxMSBDIDcgMTEuMzkwNzExIDcuMDcyMjc1MSAxMS43NjA3NDUgNy4xNzU3ODEyIDEyLjExNzE4OCBMIDYgMTMuMjkyOTY5IEwgNC44ODI4MTI1IDE0LjQxMDE1NiBDIDQuMzIxMzY1NyAxMy40MDE4MjggNCAxMi4yNDA0NzUgNCAxMSBDIDQgOS43NTk1MjUzIDQuMzIxMzY1NyA4LjU5ODE3MjMgNC44ODI4MTI1IDcuNTg5ODQzOCB6IE0gMTcuMTE3MTg4IDcuNTg5ODQzOCBDIDE3LjY3ODYzNCA4LjU5ODE3MjMgMTggOS43NTk1MjUzIDE4IDExIEMgMTggMTIuMjQwNDc1IDE3LjY3ODYzNCAxMy40MDE4MjggMTcuMTE3MTg4IDE0LjQxMDE1NiBMIDE2IDEzLjI5Mjk2OSBMIDE0LjgyNDIxOSAxMi4xMTcxODggQyAxNC45Mjc3MjUgMTEuNzYwNzQ0IDE1IDExLjM5MDcxMSAxNSAxMSBDIDE1IDEwLjYwOTI4OSAxNC45Mjc3MjUgMTAuMjM5MjU1IDE0LjgyNDIxOSA5Ljg4MjgxMjUgTCAxNy4xMTcxODggNy41ODk4NDM4IHogTSAxMSA4IEMgMTEuMDkxMTcgOCAxMS4xNzY1NzQgOC4wMTk0NTg4IDExLjI2NTYyNSA4LjAyNzM0MzggQyAxMS42NjAzNjggOC4wNjIyOTQ3IDEyLjAyOTk2MSA4LjE2OTc4MSAxMi4zNjUyMzQgOC4zNDE3OTY5IEMgMTIuOTIyMjUgOC42Mjc1Nzk3IDEzLjM3MjQyIDkuMDc3NzUwMyAxMy42NTgyMDMgOS42MzQ3NjU2IEMgMTMuODMwMjE5IDkuOTcwMDM5MyAxMy45Mzc3MDUgMTAuMzM5NjMyIDEzLjk3MjY1NiAxMC43MzQzNzUgQyAxMy45ODA1NDEgMTAuODIzNDI2IDE0IDEwLjkwODgzMSAxNCAxMSBDIDE0IDExLjA5MTE3IDEzLjk4MDUzNiAxMS4xNzY1NzQgMTMuOTcyNjU2IDExLjI2NTYyNSBDIDEzLjkzNzcwNiAxMS42NjAzNjggMTMuODMwMjE5IDEyLjAyOTk2MSAxMy42NTgyMDMgMTIuMzY1MjM0IEMgMTMuMzcyNDIgMTIuOTIyMjUgMTIuOTIyMjUgMTMuMzcyNDIgMTIuMzY1MjM0IDEzLjY1ODIwMyBDIDEyLjAyOTk2MSAxMy44MzAyMTkgMTEuNjYwMzY4IDEzLjkzNzcwNSAxMS4yNjU2MjUgMTMuOTcyNjU2IEMgMTEuMTc2NTcgMTMuOTgwNTQxIDExLjA5MTE2OSAxNCAxMSAxNCBDIDEwLjkwODgzMSAxNCAxMC44MjM0MjYgMTMuOTgwNTQxIDEwLjczNDM3NSAxMy45NzI2NTYgQyAxMC4zMzk2MzIgMTMuOTM3NzA1IDkuOTcwMDM5MyAxMy44MzAyMTkgOS42MzQ3NjU2IDEzLjY1ODIwMyBDIDkuMDc3NzUwMyAxMy4zNzI0MiA4LjYyNzU3OTcgMTIuOTIyMjUgOC4zNDE3OTY5IDEyLjM2NTIzNCBDIDguMTY5NzgxIDEyLjAyOTk2MSA4LjA2MjI5NTIgMTEuNjYwMzY4IDguMDI3MzQzOCAxMS4yNjU2MjUgQyA4LjAxOTQ1ODggMTEuMTc2NTc0IDggMTEuMDkxMTY5IDggMTEgQyA4IDEwLjkwODgzMSA4LjAxOTQ1ODggMTAuODIzNDI2IDguMDI3MzQzOCAxMC43MzQzNzUgQyA4LjA2MjI5NSAxMC4zMzk2MzIgOC4xNjk3ODEgOS45NzAwMzkzIDguMzQxNzk2OSA5LjYzNDc2NTYgQyA4LjYyNzU3OTcgOS4wNzc3NTAzIDkuMDc3NzUwMyA4LjYyNzU3OTcgOS42MzQ3NjU2IDguMzQxNzk2OSBDIDkuOTcwMDM5MyA4LjE2OTc4MSAxMC4zMzk2MzIgOC4wNjIyOTUyIDEwLjczNDM3NSA4LjAyNzM0MzggQyAxMC44MjM0MjYgOC4wMTk0NTg4IDEwLjkwODgzMSA4IDExIDggeiBNIDkuODgyODEyNSAxNC44MjQyMTkgQyAxMC4yMzkyNTUgMTQuOTI3NzI1IDEwLjYwOTI4OSAxNSAxMSAxNSBDIDExLjM5MDcxMSAxNSAxMS43NjA3NDUgMTQuOTI3NzMgMTIuMTE3MTg4IDE0LjgyNDIxOSBMIDE0LjQxMDE1NiAxNy4xMTcxODggQyAxMy40MDE4MjggMTcuNjc4NjM0IDEyLjI0MDQ3NSAxOCAxMSAxOCBDIDkuNzU5NTI1MyAxOCA4LjU5ODE3MjMgMTcuNjc4NjM0IDcuNTg5ODQzOCAxNy4xMTcxODggTCA4LjcwNzAzMTIgMTYgTCA5Ljg4MjgxMjUgMTQuODI0MjE5IHogTSA0LjYwMzUxNTYgMTUuODAyNzM0IEMgNC43NzI2MTM5IDE2LjAyNzk2MSA0Ljk1MzAyNzEgMTYuMjQzNDQ3IDUuMTQ0NTMxMiAxNi40NDkyMTkgTCA0LjMwMDc4MTIgMTcuMjkyOTY5IEwgMy43MDcwMzEyIDE2LjY5OTIxOSBMIDQuNjAzNTE1NiAxNS44MDI3MzQgeiBNIDE3LjM5NjQ4NCAxNS44MDI3MzQgTCAxOC4yOTI5NjkgMTYuNjk5MjE5IEwgMTcuNjk5MjE5IDE3LjI5Mjk2OSBMIDE2Ljg1NTQ2OSAxNi40NDkyMTkgQyAxNy4wNDY5NzMgMTYuMjQzNDQ3IDE3LjIyNzM4NiAxNi4wMjc5NjEgMTcuMzk2NDg0IDE1LjgwMjczNCB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "im-google": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxnIGlkPSJzdXJmYWNlMSI+CiAgICAgIDxwYXRoIHN0eWxlPSIgc3Ryb2tlOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm87ZmlsbDpyZ2IoMjUuODgyMzUzJSw1Mi4xNTY4NjMlLDk1LjY4NjI3NSUpO2ZpbGwtb3BhY2l0eToxOyIgZD0iTSAyMC42Nzk2ODggMTEuMjMwNDY5IEMgMjAuNjc5Njg4IDEwLjUxNTYyNSAyMC42MTcxODggOS44MjgxMjUgMjAuNDk2MDk0IDkuMTY3OTY5IEwgMTEgOS4xNjc5NjkgTCAxMSAxMy4wNzAzMTIgTCAxNi40MjU3ODEgMTMuMDcwMzEyIEMgMTYuMTg3NSAxNC4zMjgxMjUgMTUuNDcyNjU2IDE1LjM5MDYyNSAxNC40MDIzNDQgMTYuMTA1NDY5IEwgMTQuNDAyMzQ0IDE4LjY0NDUzMSBMIDE3LjY3MTg3NSAxOC42NDQ1MzEgQyAxOS41NzgxMjUgMTYuODg2NzE5IDIwLjY3OTY4OCAxNC4zMDA3ODEgMjAuNjc5Njg4IDExLjIzMDQ2OSBaIE0gMjAuNjc5Njg4IDExLjIzMDQ2OSAiLz4KICAgICAgPHBhdGggc3R5bGU9IiBzdHJva2U6bm9uZTtmaWxsLXJ1bGU6bm9uemVybztmaWxsOnJnYigyMC4zOTIxNTclLDY1Ljg4MjM1MyUsMzIuNTQ5MDIlKTtmaWxsLW9wYWNpdHk6MTsiIGQ9Ik0gMTEgMjEuMDgyMDMxIEMgMTMuNzIyNjU2IDIxLjA4MjAzMSAxNi4wMDM5MDYgMjAuMTgzNTk0IDE3LjY3MTg3NSAxOC42NDQ1MzEgTCAxNC40MDIzNDQgMTYuMTA1NDY5IEMgMTMuNTAzOTA2IDE2LjcxMDkzOCAxMi4zNTU0NjkgMTcuMDc4MTI1IDExIDE3LjA3ODEyNSBDIDguMzc4OTA2IDE3LjA3ODEyNSA2LjE1MjM0NCAxNS4zMDg1OTQgNS4zNTE1NjIgMTIuOTI1NzgxIEwgMiAxMi45MjU3ODEgTCAyIDE1LjUyNzM0NCBDIDMuNjU2MjUgMTguODIwMzEyIDcuMDU4NTk0IDIxLjA4MjAzMSAxMSAyMS4wODIwMzEgWiBNIDExIDIxLjA4MjAzMSAiLz4KICAgICAgPHBhdGggc3R5bGU9IiBzdHJva2U6bm9uZTtmaWxsLXJ1bGU6bm9uemVybztmaWxsOnJnYig5OC40MzEzNzMlLDczLjcyNTQ5JSwxLjk2MDc4NCUpO2ZpbGwtb3BhY2l0eToxOyIgZD0iTSA1LjM1MTU2MiAxMi45MTQwNjIgQyA1LjE1MjM0NCAxMi4zMTI1IDUuMDMxMjUgMTEuNjY3OTY5IDUuMDMxMjUgMTEgQyA1LjAzMTI1IDEwLjMzMjAzMSA1LjE1MjM0NCA5LjY4NzUgNS4zNTE1NjIgOS4wODU5MzggTCA1LjM1MTU2MiA2LjQ4MDQ2OSBMIDIgNi40ODA0NjkgQyAxLjMxMjUgNy44MzU5MzggMC45MTc5NjkgOS4zNjcxODggMC45MTc5NjkgMTEgQyAwLjkxNzk2OSAxMi42MzI4MTIgMS4zMTI1IDE0LjE2NDA2MiAyIDE1LjUxOTUzMSBMIDQuNjA5Mzc1IDEzLjQ4NDM3NSBaIE0gNS4zNTE1NjIgMTIuOTE0MDYyICIvPgogICAgICA8cGF0aCBzdHlsZT0iIHN0cm9rZTpub25lO2ZpbGwtcnVsZTpub256ZXJvO2ZpbGw6cmdiKDkxLjc2NDcwNiUsMjYuMjc0NTElLDIwLjc4NDMxNCUpO2ZpbGwtb3BhY2l0eToxOyIgZD0iTSAxMSA0LjkzMzU5NCBDIDEyLjQ4NDM3NSA0LjkzMzU5NCAxMy44MDQ2ODggNS40NDUzMTIgMTQuODU5Mzc1IDYuNDMzNTk0IEwgMTcuNzQ2MDk0IDMuNTQ2ODc1IEMgMTUuOTk2MDk0IDEuOTE0MDYyIDEzLjcyMjY1NiAwLjkxNzk2OSAxMSAwLjkxNzk2OSBDIDcuMDU4NTk0IDAuOTE3OTY5IDMuNjU2MjUgMy4xNzk2ODggMiA2LjQ4MDQ2OSBMIDUuMzUxNTYyIDkuMDg1OTM4IEMgNi4xNTIzNDQgNi42OTkyMTkgOC4zNzg5MDYgNC45MzM1OTQgMTEgNC45MzM1OTQgWiBNIDExIDQuOTMzNTk0ICIvPgogICAgPC9nPgogIDwvZz4KPC9zdmc+Cg==",
            "insert-text-frame": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAzIDIgTCAzIDMgTCAyIDMgTCAyIDQgTCAzIDQgTCAzIDE4IEwgMiAxOCBMIDIgMTkgTCAzIDE5IEwgMyAyMCBMIDQgMjAgTCA0IDE5IEwgMTQgMTkgTCAxNCAxOCBMIDQgMTggTCA0IDQgTCAxOCA0IEwgMTggMTQgTCAxOSAxNCBMIDE5IDQgTCAyMCA0IEwgMjAgMyBMIDE5IDMgTCAxOSAyIEwgMTggMiBMIDE4IDMgTCA0IDMgTCA0IDIgTCAzIDIgeiBNIDYgNiBMIDYgOCBMIDEwIDggTCAxMCAxNiBMIDEyIDE2IEwgMTIgOCBMIDE2IDggTCAxNiA2IEwgNiA2IHogTSAxNyAxNSBMIDE3IDE3IEwgMTUgMTcgTCAxNSAxOCBMIDE3IDE4IEwgMTcgMjAgTCAxOCAyMCBMIDE4IDE4IEwgMjAgMTggTCAyMCAxNyBMIDE4IDE3IEwgMTggMTUgTCAxNyAxNSB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "insert-text": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAzIDMgTCAzIDQgTCAzIDYgTCA0IDYgTCA0IDQgTCA4IDQgTCA4IDEzIEwgNyAxMyBMIDcgMTQgTCAxMCAxNCBMIDEwIDEzIEwgOSAxMyBMIDkgNCBMIDEzIDQgTCAxMyA2IEwgMTQgNiBMIDE0IDMgTCA0IDMgTCAzIDMgeiBNIDE2IDE0IEwgMTYgMTYgTCAxNCAxNiBMIDE0IDE3IEwgMTYgMTcgTCAxNiAxOSBMIDE3IDE5IEwgMTcgMTcgTCAxOSAxNyBMIDE5IDE2IEwgMTcgMTYgTCAxNyAxNCBMIDE2IDE0IHogIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "larger": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA4LjIxNjc5NjkgMyBMIDMgMTcgTCA0LjY4NzUgMTcgTCA2LjM1NTQ2ODggMTIuNTcwMzEyIEwgMTEuOTE3OTY5IDEyLjU3MDMxMiBMIDEyLjA2NjQwNiAxMyBMIDEzLjczMjQyMiAxMyBMIDEwLjIxMDkzOCAzIEwgOC4yMTY3OTY5IDMgeiBNIDkuMjMyNDIxOSA0LjYxMTMyODEgTCAxMS4zNjEzMjggMTEuMjg1MTU2IEwgNi44NzMwNDY5IDExLjI4NTE1NiBMIDkuMjMyNDIxOSA0LjYxMTMyODEgeiBNIDE1LjUgMTIuNzkyOTY5IEwgMTUuMjkyOTY5IDEzIEwgMTIgMTYuMjkyOTY5IEwgMTIuNzA3MDMxIDE3IEwgMTUgMTQuNzA3MDMxIEwgMTUgMTkgTCAxNiAxOSBMIDE2IDE0LjcwNzAzMSBMIDE4LjI5Mjk2OSAxNyBMIDE5IDE2LjI5Mjk2OSBMIDE1LjcwNzAzMSAxMyBMIDE1LjUgMTIuNzkyOTY5IHogIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "menu": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0ibTMgNXYyaDE2di0yaC0xNm0wIDV2MmgxNnYtMmgtMTZtMCA1djJoMTZ2LTJoLTE2IiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "new": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA0IDMgTCA0IDE5IEwgNSAxOSBMIDEzIDE5IEwgMTMgMTggTCA1IDE4IEwgNSA0IEwgMTMgNCBMIDEzIDcgTCAxMyA4IEwgMTcgOCBMIDE3IDE0IEwgMTggMTQgTCAxOCA4LjQwNjI1IEwgMTggNyBMIDE4IDYuOTkyMTg3NSBMIDE0LjAwNzgxMiAzIEwgMTQgMy4wMDk3NjU2IEwgMTQgMyBMIDEzIDMgTCA1IDMgTCA0IDMgeiBNIDE1IDE0IEwgMTUgMTYgTCAxMyAxNiBMIDEzIDE3IEwgMTUgMTcgTCAxNSAxOSBMIDE2IDE5IEwgMTYgMTcgTCAxOCAxNyBMIDE4IDE2IEwgMTYgMTYgTCAxNiAxNCBMIDE1IDE0IHogIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "file": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZGVmcz48c3R5bGUgdHlwZT0idGV4dC9jc3MiIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSI+LkNvbG9yU2NoZW1lLVRleHR7Y29sb3I6IzIzMjYyOTt9PC9zdHlsZT48L2RlZnM+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+PHBhdGggY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTTUgM2g5bDQgNHYxNEg1VjN6bTEgMXYxNmgxMVY4aC00VjRINnptOCAuN1Y3aDIuM0wxNCA0Ljd6TTggMTBoN3YxSDh2LTF6bTAgM2g3djFIOHYtMXptMCAzaDV2MUg4di0xeiIvPjwvZz48L3N2Zz4=",
            "folder": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZGVmcz48c3R5bGUgdHlwZT0idGV4dC9jc3MiIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSI+LkNvbG9yU2NoZW1lLVRleHR7Y29sb3I6IzIzMjYyOTt9PC9zdHlsZT48L2RlZnM+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+PHBhdGggY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTTMgNWg2bDIgMmg4djJINHY4aDE0LjJsLjktNkg0LjRsLjE1LTFIMjBsLTEuMiA4SDNWNXoiLz48L2c+PC9zdmc+",
            "folder-new": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZGVmcz48c3R5bGUgdHlwZT0idGV4dC9jc3MiIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSI+LkNvbG9yU2NoZW1lLVRleHR7Y29sb3I6IzIzMjYyOTt9PC9zdHlsZT48L2RlZnM+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+PHBhdGggY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTTMgNWg2bDIgMmg4djJINHY4aDd2MUgzVjV6bTEgNWgxNWwtMS40IDhIMTR2LTFoMi43NWwxLjA1LTZINS4yTDQuMTUgMTdIMTF2MUgzbDEtOHptMTAgM2gxLjV2MkgxOHYxLjVoLTIuNVYxOUgxNHYtMi41aC0yLjVWMTVIMTR2LTJ6Ii8+PC9nPjwvc3ZnPg==",
            "open": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0ibTMgM3YxIDE1aDEgMTV2LTEtMTNoLTYuOTkyMTg4bC0yLTItLjAwNzgxMi4wMDc4MTN2LS4wMDc4MTNoLTYtMW02LjAwNzgxIDVoOC45OTIxODh2MTBoLTE0di04aDN2LS4wMDc4MTNsLjAwNzgxMy4wMDc4MTMgMi0yIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "preferences-desktop-display-randr": "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB4bWxuczpjYz0iaHR0cDovL2NyZWF0aXZlY29tbW9ucy5vcmcvbnMjIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyIgeG1sbnM6aW5rc2NhcGU9Imh0dHA6Ly93d3cuaW5rc2NhcGUub3JnL25hbWVzcGFjZXMvaW5rc2NhcGUiIHhtbG5zOnNvZGlwb2RpPSJodHRwOi8vc29kaXBvZGkuc291cmNlZm9yZ2UubmV0L0RURC9zb2RpcG9kaS0wLmR0ZCIgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIj4KICAgIDxzdHlsZSB0eXBlPSJ0ZXh0L2NzcyIgaWQ9ImN1cnJlbnQtY29sb3Itc2NoZW1lIj4uQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgICAgIGNvbG9yOiMyMzI2Mjk7CiAgICAgICAgfQogICAgICAgIC5Db2xvclNjaGVtZS1CYWNrZ3JvdW5kIHsKICAgICAgICAgICAgY29sb3I6I2VmZjBmMTsKICAgICAgICB9CiAgICAgICAgLkNvbG9yU2NoZW1lLVBvc2l0aXZlVGV4dCB7CiAgICAgICAgICAgIGNvbG9yOiMyN2FlNjA7CiAgICAgICAgfQogICAgICAgIC5Db2xvclNjaGVtZS1OZXV0cmFsVGV4dCB7CiAgICAgICAgICAgIGNvbG9yOiNmNjc0MDA7CiAgICAgICAgfQogICAgICAgIC5Db2xvclNjaGVtZS1OZWdhdGl2ZVRleHQgewogICAgICAgICAgICBjb2xvcjojZGE0NDUzOwogICAgICAgIH08L3N0eWxlPgogICAgPGcgaWQ9InByZWZlcmVuY2VzLWRlc2t0b3AtZGlzcGxheS1yYW5kciIgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTI2LDEwKSI+CiAgICAgICAgPHJlY3QgaWQ9InJlY3QzODMyLTYiIHg9IjI2IiB5PSItMTAiIHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIgZmlsbC1vcGFjaXR5PSIwIi8+CiAgICAgICAgPHBhdGggaWQ9InJlY3Q3MjM1LTciIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0IiBkPSJtMzUuMDExMjQ5IDE1aDExLjk3NzUwMmwwLjAxMTI0OSAyaC0xMS45Nzc1MDJ6bTMuOTg4NzUxLTJoNHYyaC00em0tOS0xOHYxOGgyMnYtMTh6bTEgMWgyMHYxNGgtMjB6IiBmaWxsPSJjdXJyZW50Q29sb3IiLz4KICAgICAgICA8cGF0aCBpZD0icmVjdDMwMTgtNSIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiIGQ9Im0zMiA0IDUgNWgtNXoiIGZpbGw9ImN1cnJlbnRDb2xvciIvPgogICAgICAgIDxwYXRoIGlkPSJwYXRoMzAyOC0zIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgZD0ibTUwIDItNS01aDV6IiBmaWxsPSJjdXJyZW50Q29sb3IiLz4KICAgIDwvZz4KPC9zdmc+Cg==",
            "preferences-desktop-font": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiBoZWlnaHQ9IjI0IiB3aWR0aD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCI+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJhIiBncmFkaWVudFRyYW5zZm9ybT0ibWF0cml4KC42NDI4NTc3NiAwIDAgLjY0Mjg1Nzc2IC0yNDYuNTEwNDUgLTMzMC44NzA0NCkiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIiB4Mj0iMCIgeTE9IjU0NS43OTc5NyIgeTI9IjUxNy43OTc5NyI+CiAgICA8c3RvcCBvZmZzZXQ9IjAiIHN0b3AtY29sb3I9IiMyYTJjMmYiLz4KICAgIDxzdG9wIG9mZnNldD0iMSIgc3RvcC1jb2xvcj0iIzQyNDY0OSIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJiIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjYuNDk5OTk4IiB4Mj0iMTUuNTAwMDA2IiB5MT0iNi41MDAwMjciIHkyPSIxNS41MDAwMzUiPgogICAgPHN0b3Agb2Zmc2V0PSIwIiBzdG9wLWNvbG9yPSIjMjkyYzJmIi8+CiAgICA8c3RvcCBvZmZzZXQ9IjEiIHN0b3Atb3BhY2l0eT0iMCIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJjIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjUiIHgyPSI1IiB5MT0iMjAiIHkyPSI3Ij4KICAgIDxzdG9wIG9mZnNldD0iMCIgc3RvcC1jb2xvcj0iIzk5OWE5YyIvPgogICAgPHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjZjRmNWY1Ii8+CiAgPC9saW5lYXJHcmFkaWVudD4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxyZWN0IGZpbGw9InVybCgjYSkiIGhlaWdodD0iMTgiIHJ4PSI5IiBzdHJva2Utd2lkdGg9Ii42NDI4NTgiIHdpZHRoPSIxOCIgeD0iMi4wMDAwMDEiIHk9IjIuMDAwMDA1Ii8+CiAgICA8cGF0aCBkPSJtOS4yNTIyMzI3IDcuMTI0MDUwOC0zLjkyODcxNDcgNy42MjY0MDIyIDUuMjI4MjQxIDUuMjI2OTg2Yy4xNDk0ODUuMDA3My4yOTY4ODIuMDIyNi40NDgyNDMuMDIyNiA0LjI5NDc0MSAwIDcuODYwNjUtMi45ODEzNjQgOC43Njg5ODItNi45OTM1ODlsLTMuNDQwMjk0LTMuNDQwMjkzMy0yLjEzOTUxLS4xODQ1NzAyLTEuMjIyOTM3LjY5OTM1ODUuMDUxNDguMDMzOS0uMDQxNDMtLjAwNzUgMS42ODYyNDYgMS42ODYyNDYtLjM0NTI4NS4zOTY3NjR6IiBmaWxsPSJ1cmwoI2IpIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiIG9wYWNpdHk9Ii4yIiBzdHJva2Utd2lkdGg9Ii42NDI4NTgiLz4KICAgIDxwYXRoIGQ9Im03LjQyNTc4MTIgNi44Mzc4OTA2LTIuNTIxNDg0MyA3LjE2OTkyMTRoMS42MzA4NTkzbC41MTk1MzEzLTEuNzAxMTcxaDIuNTk5NjA5NGwuNTIxNDg0MSAxLjcwMTE3MWgxLjYyODkwN2wtMi41MjkyOTc0LTcuMTY5OTIxNHptLjkyOTY4NzYgMS4xMDkzNzVjLjAzMzMzMy4xMzMzMzM0LjA3NTU3My4yOTA3MDMyLjEyODkwNjIuNDcwNzAzMi4wNTMzMzMuMTc5OTk5OS4xMDY4MjI5LjM1NTk2MzUuMTYwMTU2Mi41MjkyOTY4LjA1MzMzMy4xNzMzMzM0LjA5NzUyNi4zMTYzNTQyLjEzMDg1OTQuNDI5Njg3NWwuNTE5NTMxMyAxLjY2MDE1NTloLTEuODU5Mzc1bC41MDk3NjU2LTEuNjYwMTU1OWMuMDI2NjY3LS4wNzMzMzMuMDYyNzA4LS4xOTU4MDczLjEwOTM3NS0uMzY5MTQwNi4wNTMzMzMtLjE4LjEwNjgyMjktLjM2NzIxMzUuMTYwMTU2My0uNTYwNTQ2OS4wNi0uMi4xMDcyOTE2LS4zNjY2NjY2LjE0MDYyNS0uNXptNi40Njg3MDkyLjA0ODgyN2MtLjM4NjY2NyAwLS43NTkxNDEuMDQ3MjkyLTEuMTE5MTQxLjE0MDYyNS0uMzYuMDg2NjY3LS42ODQwMzYuMjAyOTQyNy0uOTcwNzAzLjM0OTYwOTRsLjQ5MDIzNCAxLjAwOTc2NTZjLjI1MzMzNC0uMTEzMzMzMy41MDY0MzMtLjIwNTk2MzUuNzU5NzY2LS4yNzkyOTY5LjI1MzMzMy0uMDguNTE0NTgzLS4xMjEwOTM3Ljc4MTI1LS4xMjEwOTM3cy40NzI0NzQuMDY3ODM5LjYxOTE0MS4yMDExNzE4Yy4xNTMzMzMuMTMzMzMzNC4yMzA0NTEuMzQyMjM5OC4yMzA0NjguNjI4OTA2OGwuMDAwMDQxLjY4MTY0MTktLjk1MTE3Mi4wMjkzYy0uODEzMzMzLjAzMzMzLTEuNDIxNDU4LjE4NzYwNC0xLjgyODEyNC40NjA5MzctLjQwNjY2Ny4yNzMzMzQtLjYxMTMyOS42OTkyOTctLjYxMTMyOSAxLjI3OTI5NyAwIC41OTMzMzMuMTYwNDY5IDEuMDMwNTQ3LjQ4MDQ2OSAxLjMxMDU0N3MuNzIyMzE4LjQxOTkyMiAxLjIwODk4NC40MTk5MjJjLjQ1MzMzNCAwIC44MTAzMTMtLjA2NTg5IDEuMDcwMzEzLS4xOTkyMTkuMjYtLjEzMzMzMy41MDY5MDEtLjM0NzI5Mi43NDAyMzQtLjY0MDYyNWguMDQxMDJsLjI4OTA2My43NDAyMzRoMS4wNDEwMTVsLS4wMDAwNDEtNC4wODIwMzE5Yy0uMDAwMDA3LS42NTMzMzQtLjE5NjUxLTEuMTM1ODg1OS0uNTg5ODQ0LTEuNDQ5MjE5Mi0uMzg2NjctLjMyMDAwMzEtLjk0ODMxMS0uNDgwNDcxOC0xLjY4MTY0NC0uNDgwNDcxOHptLjc5MTA1NiAzLjQ4MDQ2OTl2LjQ1MTE3MmMwIC4zNDY2NjctLjExMDA3OC42MTcyMTQtLjMzMDA3OC44MTA1NDctLjIyLjE4NjY2Ny0uNDkwNTQ3LjI3OTI5Ny0uODEwNTQ3LjI3OTI5Ny0uMjEzMzMzIDAtLjM4NjE5OC0uMDQ3MjktLjUxOTUzMS0uMTQwNjI1LS4xMzMzMzMtLjEtLjE5OTIxOS0uMjYzNTY4LS4xOTkyMTktLjQ5MDIzNCAwLS4yNi4wOTI2My0uNDY4OTA2LjI3OTI5Ny0uNjI4OTA3LjE4NjY2Ny0uMTYuNTItLjI0NjQzMiAxLS4yNTk3NjV6IiBmaWxsPSJ1cmwoI2MpIi8+CiAgPC9nPgo8L3N2Zz4K",
            "preferences-desktop-theme-applications": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiBoZWlnaHQ9IjI0IiB3aWR0aD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCI+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJhIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjYuMzc1MDAzIiB4Mj0iMTUuNzUwMDIiIHhsaW5rOmhyZWY9IiNjIiB5MT0iMTAuMDAwMDEyIiB5Mj0iMTkuMzc1MDA5Ii8+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJiIiBncmFkaWVudFRyYW5zZm9ybT0ibWF0cml4KC40MTY2NjY5MiAwIDAgLjQwODMzMjY5IC0xNTkuMjM4MjcgLTIwMy4yNTA5NCkiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIiB4Mj0iMCIgeTE9IjU0My43OTc5NyIgeTI9IjUwMi42NTUwOSI+CiAgICA8c3RvcCBvZmZzZXQ9IjAiIHN0b3AtY29sb3I9IiNjNmNkZDEiLz4KICAgIDxzdG9wIG9mZnNldD0iMSIgc3RvcC1jb2xvcj0iI2UwZTVlNyIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJjIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjUuMzc1MDAzIiB4Mj0iMTQuNzUwMDIiIHkxPSI3LjAwMDAxMiIgeTI9IjE2LjM3NTAwOSI+CiAgICA8c3RvcCBvZmZzZXQ9IjAiLz4KICAgIDxzdG9wIG9mZnNldD0iMSIgc3RvcC1vcGFjaXR5PSIwIi8+CiAgPC9saW5lYXJHcmFkaWVudD4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIGQ9Im0xLjAwMDAwNiAyaDE5Ljk5OTk5NHYxOGgtMTkuOTk5OTk0eiIgZmlsbD0idXJsKCNiKSIgc3Ryb2tlLXdpZHRoPSIuNjMzODY2Ii8+CiAgICA8cGF0aCBkPSJtMiAxOCAxOC0xMSAxIDF2MTJoLTE3eiIgZmlsbD0idXJsKCNjKSIgZmlsbC1ydWxlPSJldmVub2RkIiBvcGFjaXR5PSIuMiIgc3Ryb2tlLXdpZHRoPSIuNjI1Ii8+CiAgICA8cGF0aCBkPSJtMSAyaDIwLjAwMDAwMnYzaC0yMC4wMDAwMDJ6IiBmaWxsPSIjNTY2MDY5IiBzdHJva2Utd2lkdGg9Ii42ODQ2NTMiLz4KICAgIDxwYXRoIGQ9Im0xLjAwMDAyNyA1aDE5Ljk5OTk3M3YxaC0xOS45OTk5NzN6IiBmaWxsPSIjM2RhZWU5IiBzdHJva2Utd2lkdGg9Ii43OTA1NjkiLz4KICAgIDxwYXRoIGQ9Im0yIDdoMTh2MTAuOTk5OTk5aC0xOHoiIGZpbGw9IiNmZmYiIHN0cm9rZS13aWR0aD0iLjU3NDQ1NiIvPgogICAgPHJlY3QgZmlsbD0iI2VmZjBmMSIgaGVpZ2h0PSIxLjUiIHJ4PSIuNzUiIHN0cm9rZS13aWR0aD0iLjc1IiB3aWR0aD0iMS41IiB4PSIxOC43NSIgeT0iMi43NSIvPgogICAgPHBhdGggZD0ibTE1LjE2OCA4LjA4Mi01LjMxMDU3ODEgMy45NTEyMDMgNS45NjY3OTcxIDUuOTY2Nzk3aDQuMTc1Nzgxdi01LjA4NnptLTQuOTYwOTY5IDUuMjEwOTY5LTMuMjA3MDMxIDIuNzA3MDMxIDIgMmg1LjkxNDA2MnoiIGZpbGw9InVybCgjYSkiIG9wYWNpdHk9Ii4yIi8+CiAgICA8ZyBmaWxsPSIjMzUzYjNlIj4KICAgICAgPGNpcmNsZSBjeD0iLTIzLjU1NTQ5NCIgY3k9Ii0zLjkzMzI4MSIgcj0iLjA0NDQ5NyIgc3Ryb2tlPSIjMDAwIi8+CiAgICAgIDxjaXJjbGUgY3g9Ii0yMy41NTU0OTQiIGN5PSItMy45MzMyODEiIHI9Ii4wNDQ0OTciIHN0cm9rZT0iIzAwMCIvPgogICAgICA8cGF0aCBkPSJtMTQuOTMxNjQxIDhjLS42NzA1NTktLjAwNDU3LTIuMjYxNDI5IDEuMTAxMTY2NS0zLjgzMDA3OSAyLjY2OTkyMi0uNDUxMzM2LjQ1MTQ5NC0uODczMDE3LjkxNDI2My0xLjI0NDE0MDEgMS4zNjMyODEuNjgxNTg3MS4xMjM4NDIgMS4yNTA1NTAxLjU5MTU3NCAxLjUwMzkwNjEgMS4yMzYzMjguNDAzMzc0LS4zNDEwMTguODE1Nzg0LS43MTgyMTggMS4yMTg3NS0xLjEyMTA5MyAxLjgzNzEyLTEuODM3MzExIDIuOTk1OTQyLTMuNjU3OTA3OSAyLjU4NzkyMi00LjA2NjQzOC0uMDQyLS4wNDIyLS4xMDAzMTktLjA2ODY5MzgtLjE3Mzg1OS0uMDc4MDkzOC0uMDE5NjgtLjAwMjQ4LS4wNDA4Ny0uMDAzNzYtLjA2MjUtLjAwMzkxem0tNS40MzE2NDEgNWMtLjgyODQyNzEgMC0xLjUuNjcxNTczLTEuNSAxLjUuMDAxMy4xNzA1NjMuMDMxNjg2LjMzOTY1NC4wODk4NDQuNWgtLjA4OTg0NGwtMSAxaDEuNWMxLjA2MDc0NzEgMCAxLjkyNDQzMy0uODE3NDQzIDEuOTk2MDk0LTEuODU5Mzc1LS4wMDA5OTctLjAxMTY1LS4wMDI2LS4wMjM2LS4wMDM5LS4wMzUxNi4wMDQ1LS4wMzQ5OS4wMDcxLS4wNzAyLjAwNzgtLjEwNTQ2OSAwLS41MTc3NjctLjM5NDE4MS0uOTQyOTMxLS44OTg0Mzc1LS45OTQxNDEtLjAxNjkwNC0uMDAxNi0uMDMzODMzLS4wMDI5LS4wNTA3ODEtLjAwMzktLjAxNzAzMjYtLjAwMDg2OC0uMDMzNTE2Ni0uMDAxOTU1LS4wNTA3NzU1LS4wMDE5NTV6IiBzdHJva2Utd2lkdGg9Ii41OTc1MDMiLz4KICAgIDwvZz4KICA8L2c+Cjwvc3ZnPgo=",
            "redo": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0ibTEzLjY5OTIxOSAzbC0uNzA3MDMxLjcwNzAzMSAyLjI5Mjk2OCAyLjI5Mjk2OWgtMi4yODUxNTYtMS4wMDc4MS0uNDkyMTg4Yy0zLjYwMSAwLTYuNSAyLjg5OS02LjUgNi41IDAgMy42MDEgMi44OTkgNi41IDYuNSA2LjVoMS41di0xaC0xLjVjLTMuMDQ3IDAtNS41LTIuNDUzLTUuNS01LjUgMC0zLjA0NyAyLjQ1My01LjUgNS41LTUuNWguNDkyMTg4IDEuMDA3ODEgMi4yODUxNTZsLTIuMjkyOTY4IDIuMjkyOTY5LjcwNzAzMS43MDcwMzEgMy4yOTI5NjktMy4yOTI5NjkuMjA3MDMxLS4yMDcwMzEtLjIwNzAzMS0uMjA3MDMxLTMuMjkyOTY5LTMuMjkyOTY5IiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "save-as": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAyIDIuOTk4MDQ2OSBMIDIgMyBMIDIgNCBMIDIgMTkgTCAzIDE5IEwgMTEgMTkgTCAxMSAxOCBMIDYgMTggTCA2IDEyIEwgMTEgMTIgTCAxMSAxMSBMIDYgMTEgTCA1IDExIEwgNSAxOCBMIDMgMTggTCAzIDQgTCA2IDQgTCA2IDggTCA2IDkgTCAxNCA5IEwgMTQgOCBMIDE0IDQgTCAxNC4yOTI5NjkgNCBMIDE3IDYuNzA3MDMxMiBMIDE3IDcgTCAxNyAxMCBMIDE4IDEwIEwgMTggNyBMIDE4IDYuMzAwNzgxMiBMIDE3Ljk5MjE4OCA2LjMwMDc4MTIgTCAxOCA2LjI5MTAxNTYgTCAxNC43MDcwMzEgMi45OTgwNDY5IEwgMTQuNjk5MjE5IDMuMDA3ODEyNSBMIDE0LjY5OTIxOSAyLjk5ODA0NjkgTCAxNCAyLjk5ODA0NjkgTCAyIDIuOTk4MDQ2OSB6IE0gNyA0IEwgMTAuOTAwMzkxIDQgTCAxMC45MDAzOTEgOCBMIDcgOCBMIDcgNCB6IE0gMTggMTEgTCAxNy4wMDM5MDYgMTEuOTk0MTQxIEwgMTcgMTEuOTk0MTQxIEwgMTIgMTYuOTkyMTg4IEwgMTIuMDA3ODEyIDE3LjAwMTk1MyBMIDEyLjAwMzkwNiAxOC4wMDU4NTkgTCAxMiAxOC4wMDU4NTkgTCAxMiAxOC45OTYwOTQgTCAxMiAxOS4wMDU4NTkgTCAxNCAxOS4wMDU4NTkgTCAxNC4wMDU4NTkgMTguOTk2MDk0IEwgMTQuMDA5NzY2IDE4Ljk5NjA5NCBMIDE0LjAxOTUzMSAxOC45OTYwOTQgTCAxNC4wMTM2NzIgMTguOTg2MzI4IEwgMTUgMTggTCAxOSAxNC4wMDM5MDYgTCAxOC4yOTQ5MjIgMTMuMjk0OTIyIEwgMTMuMzA0Njg4IDE4LjI4MTI1IEwgMTIuNzEwOTM4IDE3LjY4OTQ1MyBMIDE3LjcwMzEyNSAxMi43MDExNzIgTCAxOC4yOTQ5MjIgMTMuMjk0OTIyIEwgMTkgMTMuOTk4MDQ3IEwgMjAgMTIuOTk4MDQ3IEwgMTggMTEgeiAiIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0Ii8+CiAgPC9nPgo8L3N2Zz4K",
            "save": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAzIDIuOTk4MDQ2OSBMIDMgMyBMIDMgNCBMIDMgMTkgTCA0IDE5IEwgMTkgMTkgTCAxOSAxOCBMIDE5IDcgTCAxOSA2LjMwMDc4MTIgTCAxOC45OTIxODggNi4zMDA3ODEyIEwgMTkgNi4yOTEwMTU2IEwgMTUuNzA3MDMxIDIuOTk4MDQ2OSBMIDE1LjY5OTIxOSAzLjAwNzgxMjUgTCAxNS42OTkyMTkgMi45OTgwNDY5IEwgMTUgMi45OTgwNDY5IEwgMyAyLjk5ODA0NjkgeiBNIDQgNCBMIDcgNCBMIDcgOCBMIDcgOSBMIDE1IDkgTCAxNSA4IEwgMTUgNCBMIDE1LjI5Mjk2OSA0IEwgMTggNi43MDcwMzEyIEwgMTggNyBMIDE4IDE4IEwgMTYgMTggTCAxNiAxMSBMIDE1IDExIEwgNyAxMSBMIDYgMTEgTCA2IDE4IEwgNCAxOCBMIDQgNCB6IE0gOCA0IEwgMTEuOTAwMzkxIDQgTCAxMS45MDAzOTEgOCBMIDggOCBMIDggNCB6IE0gNyAxMiBMIDE1IDEyIEwgMTUgMTggTCA3IDE4IEwgNyAxMiB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "settings": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSAxNC41NTA3ODEgMyBDIDEzLjMzNjkyMSAzIDEyLjMzMTc2MiAzLjg1NTkzIDEyLjEwMTU2MiA1IEwgMy4wNTA3ODEyIDUgTCAzLjA1MDc4MTIgNiBMIDEyLjEwMTU2MiA2IEMgMTIuMzMxNzYyIDcuMTQ0MDcgMTMuMzM2OTIxIDggMTQuNTUwNzgxIDggQyAxNS43NjQ2NDEgOCAxNi43Njk4IDcuMTQ0MDcgMTcgNiBMIDE5LjA1MDc4MSA2IEwgMTkuMDUwNzgxIDUgTCAxNyA1IEMgMTYuNzY5OCAzLjg1NTkzIDE1Ljc2NDY0MSAzIDE0LjU1MDc4MSAzIHogTSAxNC41NTA3ODEgNCBDIDE1LjM4MTc4MSA0IDE2LjA1MDc4MSA0LjY2OSAxNi4wNTA3ODEgNS41IEMgMTYuMDUwNzgxIDYuMzMxIDE1LjM4MTc4MSA3IDE0LjU1MDc4MSA3IEMgMTMuNzE5NzgxIDcgMTMuMDUwNzgxIDYuMzMxIDEzLjA1MDc4MSA1LjUgQyAxMy4wNTA3ODEgNC42NjkgMTMuNzE5NzgxIDQgMTQuNTUwNzgxIDQgeiBNIDExLjU1MDc4MSA5IEMgMTAuMzM2OTIxIDkgOS4zMzE3NjI1IDkuODU1OTMgOS4xMDE1NjI1IDExIEwgMy4wNTA3ODEyIDExIEwgMy4wNTA3ODEyIDEyIEwgOS4xMDE1NjI1IDEyIEMgOS4zMzE3NjI1IDEzLjE0NDA3IDEwLjMzNjkyMSAxNCAxMS41NTA3ODEgMTQgQyAxMi43NjQ2NDEgMTQgMTMuNzY5OCAxMy4xNDQwNyAxNCAxMiBMIDE5LjA1MDc4MSAxMiBMIDE5LjA1MDc4MSAxMSBMIDE0IDExIEMgMTMuNzY5OCA5Ljg1NTkzIDEyLjc2NDY0MSA5IDExLjU1MDc4MSA5IHogTSA1LjU1MDc4MTIgMTQgQyA0LjE2NTc4MTMgMTQgMy4wNTA3ODEyIDE1LjExNSAzLjA1MDc4MTIgMTYuNSBDIDMuMDUwNzgxMiAxNy44ODUgNC4xNjU3ODEzIDE5IDUuNTUwNzgxMiAxOSBDIDYuNzY0NjQxMyAxOSA3Ljc2OTggMTguMTQ0MDcgOCAxNyBMIDE5LjA1MDc4MSAxNyBMIDE5LjA1MDc4MSAxNiBMIDggMTYgQyA3Ljc2OTggMTQuODU1OTMgNi43NjQ2NDEzIDE0IDUuNTUwNzgxMiAxNCB6IE0gNS41NTA3ODEyIDE1IEMgNi4zODE3ODEyIDE1IDcuMDUwNzgxMiAxNS42NjkgNy4wNTA3ODEyIDE2LjUgQyA3LjA1MDc4MTIgMTcuMzMxIDYuMzgxNzgxMiAxOCA1LjU1MDc4MTIgMTggQyA0LjcxOTc4MTMgMTggNC4wNTA3ODEyIDE3LjMzMSA0LjA1MDc4MTIgMTYuNSBDIDQuMDUwNzgxMiAxNS42NjkgNC43MTk3ODEzIDE1IDUuNTUwNzgxMiAxNSB6ICIgY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "smaller": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTSA4LjIxNjc5NjkgMyBMIDMgMTcgTCA0LjY4NzUgMTcgTCA2LjM1NTQ2ODggMTIuNTcwMzEyIEwgMTEuOTE3OTY5IDEyLjU3MDMxMiBMIDEyLjA2NjQwNiAxMyBMIDEzLjczMjQyMiAxMyBMIDEwLjIxMDkzOCAzIEwgOC4yMTY3OTY5IDMgeiBNIDkuMjMyNDIxOSA0LjYxMTMyODEgTCAxMS4zNjEzMjggMTEuMjg1MTU2IEwgNi44NzMwNDY5IDExLjI4NTE1NiBMIDkuMjMyNDIxOSA0LjYxMTMyODEgeiBNIDE1IDEyLjc5Mjk2OSBMIDE1IDE3LjA4NTkzOCBMIDEyLjcwNzAzMSAxNC43OTI5NjkgTCAxMiAxNS41IEwgMTUuMjkyOTY5IDE4Ljc5Mjk2OSBMIDE1LjUgMTkgTCAxNS43MDcwMzEgMTguNzkyOTY5IEwgMTkgMTUuNSBMIDE4LjI5Mjk2OSAxNC43OTI5NjkgTCAxNiAxNy4wODU5MzggTCAxNiAxMi43OTI5NjkgTCAxNSAxMi43OTI5NjkgeiAiIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0Ii8+CiAgPC9nPgo8L3N2Zz4K",
            "snippets": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZGVmcz48c3R5bGUgdHlwZT0idGV4dC9jc3MiIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSI+LkNvbG9yU2NoZW1lLVRleHR7Y29sb3I6IzIzMjYyOTt9PC9zdHlsZT48L2RlZnM+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+PHBhdGggY2xhc3M9IkNvbG9yU2NoZW1lLVRleHQiIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0iTTUgM2g5bDQgNHYxMkg1VjN6bTEgMXYxNGgxMVY4aC00VjRINnptOCAuN1Y3aDIuM0wxNCA0Ljd6TTggOGg2djFIOFY4em0wIDNoN3YxSDh2LTF6bTAgM2g1djFIOHYtMXpNMyA2aDF2MTRoMTF2MUgzVjZ6Ii8+PC9nPjwvc3ZnPg==",
            "theme": "data:image/svg+xml;base64,PCFET0NUWVBFIHN2Zz4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZlcnNpb249IjEuMSIgdmlld0JveD0iMCAwIDI0IDI0IiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiPgogIDxkZWZzPgogICAgPHN0eWxlIGlkPSJjdXJyZW50LWNvbG9yLXNjaGVtZSIgdHlwZT0idGV4dC9jc3MiPgogICAgICAgICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgICAgICAgICBjb2xvcjojMjMyNjI5OwogICAgICAgICAgICB9CiAgICAgICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgc3R5bGU9ImZpbGw6Y3VycmVudENvbG9yOyBmaWxsLW9wYWNpdHk6MTsgc3Ryb2tlOm5vbmUiIGQ9Ik0gNyAzIEMgNi4wMjcwOSA2LjQwNTAzIDMuNjQ1NTUgOS4zMzIyOCAyLjU5NTcgMTEuNjc1OCBDIDIuMjI4MyAxMi4zNzI2IDIgMTMuMTU0NiAyIDE0IEMgMiAxNi43NyA0LjIzIDE5IDcgMTkgQyA5Ljc3IDE5IDEyIDE2Ljc3IDEyIDE0IEMgMTIgMTMuMTU0NiAxMS43NzE3IDEyLjM3MjYgMTEuNDA0MyAxMS42NzU4IEMgMTAuMzU0NCA5LjMzMjI4IDcuOTcyOSA2LjQwNTAzIDcgMyBaIE0gOS4yODMyIDEwLjcxNjggQyAxMC4zMjA5IDExLjQzOCAxMSAxMi42MzUxIDExIDE0IEMgMTEgMTYuMjE2IDkuMjE2IDE4IDcgMTggQyA1LjYzNTA0IDE4IDQuNDM4IDE3LjMyMSAzLjcxNjggMTYuMjgzMiBDIDQuMzYzODUgMTYuNzMyOSA1LjE0ODkyIDE3IDYgMTcgQyA4LjIxNiAxNyAxMCAxNS4yMTYgMTAgMTMgQyAxMCAxMi4xNDg5IDkuNzMyOTEgMTEuMzYzOCA5LjI4MzIgMTAuNzE2OCBaIi8+CiAgICA8cGF0aCBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgc3R5bGU9ImZpbGw6Y3VycmVudENvbG9yOyBmaWxsLW9wYWNpdHk6MTsgc3Ryb2tlOm5vbmUiIGQ9Ik0gMTQgMiBDIDEzLjE4NTcgNC44NSAxMS4zOTQgNy4zNjAwOCAxMC4yMTI5IDkuNDc4NTIgQyAxMC40MTk5IDkuODI2MTggMTAuNjE4IDEwLjE3MzIgMTAuODAwOCAxMC41MDIgQyAxMS42MDg1IDguODg2MzcgMTIuOTMyNSA2Ljc3NzkgMTQgNC4zOTI1OCBDIDE1LjE5NDEgNy4wNjA2MyAxNi43NDY3IDkuNDE5OSAxNy40OTIyIDExLjA4NCBMIDE3LjUwMzkgMTEuMTEzMyBMIDE3LjUxOTUgMTEuMTQyNiBDIDE3LjgyMjcgMTEuNzE3NSAxOCAxMi4zMzQ2IDE4IDEzIEMgMTggMTUuMjMzMyAxNi4yMzMzIDE3IDE0IDE3IEMgMTMuMDQ4NSAxNyAxMi4xOTMzIDE2LjY2NTggMTEuNTExNyAxNi4xMjUgQyAxMS4zNjg3IDE2LjQyOTMgMTEuMTk2OSAxNi43MTM4IDEwLjk5OCAxNi45ODA1IEMgMTEuODM1MSAxNy42MTE5IDEyLjg2NjEgMTggMTQgMTggQyAxNi43NyAxOCAxOSAxNS43NyAxOSAxMyBDIDE5IDEyLjE1NDYgMTguNzcxNyAxMS4zNzI2IDE4LjQwNDMgMTAuNjc1OCBDIDE3LjM1NDQgOC4zMzIyOCAxNC45NzI5IDUuNDA1MDMgMTQgMiBaIi8+CiAgPC9nPgo8L3N2Zz4K",
            "undo": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAuQ29sb3JTY2hlbWUtVGV4dCB7CiAgICAgICAgY29sb3I6IzIzMjYyOTsKICAgICAgfQogICAgICA8L3N0eWxlPgogIDwvZGVmcz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgxLDEpIj4KICAgIDxwYXRoIHN0eWxlPSJmaWxsOmN1cnJlbnRDb2xvcjtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIgZD0ibTguMzAwNzgxIDNsLTMuMjkyOTY5IDMuMjkyOTY5LS4yMDcwMzEuMjA3MDMxLjIwNzAzMS4yMDcwMzEgMy4yOTI5NjkgMy4yOTI5NjkuNzA3MDMxLS43MDcwMzEtMi4yOTI5NjktMi4yOTI5NjhoMi4yODUxNTYgMS4wMDc4MS40OTIxODhjMy4wNDcgMCA1LjUgMi40NTMgNS41IDUuNSAwIDMuMDQ3LTIuNDUzIDUuNS01LjUgNS41aC0xLjV2MWgxLjVjMy42MDEgMCA2LjUtMi44OTkgNi41LTYuNSAwLTMuNjAxLTIuODk5LTYuNS02LjUtNi41aC0uNDkyMTg4LTEuMDA3ODEtMi4yODUxNTZsMi4yOTI5NjktMi4yOTI5NjktLjcwNzAzMS0uNzA3MDMxIiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIvPgogIDwvZz4KPC9zdmc+Cg==",
            "view-fullscreen-symbolic": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+CiA8cGF0aCBkPSJtIDIgMSA1IDAgMCAyIC0zIDAgYyAtMC41NDEgMCAtMSAwLjQxNiAtMSAxIGwgMCAzIC0yIDAgMCAtNSBjIDAgLTAuNTIzIDAuNDU5IC0xIDEgLTEgeiIgc3R5bGU9ImZpbGw6IzM1MzUzNTtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIvPgogPHBhdGggZD0ibSAxIDE0IDAgLTUgMiAwIDAgMyBjIDAgMC41NDEgMC40MTYgMSAxIDEgbCAzIDAgMCAyIC01IDAgYyAtMC41MjMgMCAtMSAtMC40NTkgLTEgLTEgeiIgc3R5bGU9ImZpbGw6IzM1MzUzNTtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIvPgogPHBhdGggZD0ibSAxNCAxIC01IDAgMCAyIDMgMCBjIDAuNTQxIDAgMSAwLjQxNiAxIDEgbCAwIDMgMiAwIDAgLTUgYyAwIC0wLjUyMyAtMC40NTkgLTEgLTEgLTEgeiIgc3R5bGU9ImZpbGw6IzM1MzUzNTtmaWxsLW9wYWNpdHk6MTtzdHJva2U6bm9uZSIvPgogPHBhdGggZD0ibSAxNSAxNCAwIC01IC0yIDAgMCAzIGMgMCAwLjU0MSAtMC40MTYgMSAtMSAxIGwgLTMgMCAwIDIgNSAwIGMgMC41MjMgMCAxIC0wLjQ1OSAxIC0xIHoiIHN0eWxlPSJmaWxsOiMzNTM1MzU7ZmlsbC1vcGFjaXR5OjE7c3Ryb2tlOm5vbmUiLz4KPC9zdmc+Cg==",
            "zoom-in": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGlkPSJzdmc2IiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAgIC5Db2xvclNjaGVtZS1UZXh0IHsgICAgICAgICAgICBjb2xvcjojMjMyNjI5OyAgICAgICAgfQogICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBpZD0icGF0aDM0NyIgZD0ibTExIDNhOCA4IDAgMCAwLTggOCA4IDggMCAwIDAgOCA4IDggOCAwIDAgMCA0Ljg5MjU3OC0xLjY5MzM1OWwzLjQwMDM5MSAzLjQwMDM5YTEgMSAwIDAgMCAxLjQxNDA2MiAwIDEgMSAwIDAgMCAwLTEuNDE0MDYybC0zLjQwMDM5LTMuNDAwMzkxYTggOCAwIDAgMCAxLjY5MzM1OS00Ljg5MjU3OCA4IDggMCAwIDAtOC04em0wIDFhNyA3IDAgMCAxIDcgNyA3IDcgMCAwIDEtNyA3IDcgNyAwIDAgMS03LTcgNyA3IDAgMCAxIDctN3ptLTEgM3YzaC0zdjJoM3YzaDJ2LTNoM3YtMmgtM3YtM2gtMnoiIGNsYXNzPSJDb2xvclNjaGVtZS1UZXh0IiBmaWxsPSJjdXJyZW50Q29sb3IiIHN0cm9rZS1saW5lY2FwPSJzcXVhcmUiIHN0cm9rZS13aWR0aD0iMiIgc3R5bGU9InBhaW50LW9yZGVyOm1hcmtlcnMgc3Ryb2tlIGZpbGwiLz4KICA8L2c+Cjwvc3ZnPgo=",
            "zoom-out": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGlkPSJzdmc2IiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAgIC5Db2xvclNjaGVtZS1UZXh0IHsgICAgICAgICAgICBjb2xvcjojMjMyNjI5OyAgICAgICAgfQogICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBpZD0icGF0aDM0NyIgZD0ibTExIDNhOCA4IDAgMCAwLTggOCA4IDggMCAwIDAgOCA4IDggOCAwIDAgMCA0Ljg5MjU3OC0xLjY5MzM1OWwzLjQwMDM5MSAzLjQwMDM5YTEgMSAwIDAgMCAxLjQxNDA2MiAwIDEgMSAwIDAgMCAwLTEuNDE0MDYybC0zLjQwMDM5LTMuNDAwMzkxYTggOCAwIDAgMCAxLjY5MzM1OS00Ljg5MjU3OCA4IDggMCAwIDAtOC04em0wIDFhNyA3IDAgMCAxIDcgNyA3IDcgMCAwIDEtNyA3IDcgNyAwIDAgMS03LTcgNyA3IDAgMCAxIDctN3ptLTQgNnYyaDh2LTJoLTh6IiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgZmlsbD0iY3VycmVudENvbG9yIiBzdHJva2UtbGluZWNhcD0ic3F1YXJlIiBzdHJva2Utd2lkdGg9IjIiIHN0eWxlPSJwYWludC1vcmRlcjptYXJrZXJzIHN0cm9rZSBmaWxsIi8+CiAgPC9nPgo8L3N2Zz4K",
            "zoom-reset": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGlkPSJzdmc2IiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij4KICA8ZGVmcyBpZD0iZGVmczMwNTEiPgogICAgPHN0eWxlIHR5cGU9InRleHQvY3NzIiBpZD0iY3VycmVudC1jb2xvci1zY2hlbWUiPgogICAgICAgIC5Db2xvclNjaGVtZS1UZXh0IHsgICAgICAgICAgICBjb2xvcjojMjMyNjI5OyAgICAgICAgfQogICAgPC9zdHlsZT4KICA8L2RlZnM+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMSwxKSI+CiAgICA8cGF0aCBpZD0icGF0aDM0NyIgZD0ibTMgM3Y2aDAuMjY5NTMxMiAxLjAzMzIwMzIgNC42OTcyNjU2bC0yLjkzOTQ1MzEtMi45Mzk0NTMxYTcgNyAwIDAgMSA0LjkzOTQ1MzEtMi4wNjA1NDY5IDcgNyAwIDAgMSA3IDcgNyA3IDAgMCAxLTcgNyA3IDcgMCAwIDEtNy03aC0xYTggOCAwIDAgMCA4IDggOCA4IDAgMCAwIDQuODkyNTc4LTEuNjkzMzU5bDMuNDAwMzkxIDMuNDAwMzlhMSAxIDAgMCAwIDEuNDE0MDYyIDAgMSAxIDAgMCAwIDAtMS40MTQwNjJsLTMuNDAwMzktMy40MDAzOTFhOCA4IDAgMCAwIDEuNjkzMzU5LTQuODkyNTc4IDggOCAwIDAgMC04LTggOCA4IDAgMCAwLTUuNjM0NzY1NiAyLjM2NTIzNDRsLTIuMzY1MjM0NC0yLjM2NTIzNDR6IiBjbGFzcz0iQ29sb3JTY2hlbWUtVGV4dCIgZmlsbD0iY3VycmVudENvbG9yIiBzdHJva2UtbGluZWNhcD0ic3F1YXJlIiBzdHJva2Utd2lkdGg9IjIiIHN0eWxlPSJwYWludC1vcmRlcjptYXJrZXJzIHN0cm9rZSBmaWxsIi8+CiAgPC9nPgo8L3N2Zz4K",
        }
        
        
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(760, 420)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager(self.settings_manager)
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        self.plugin_manager.activate_enabled_plugins()
        self.app_menu_bar = None
        
        # Setup toolbar contents
        self.setup_toolbar()
        self.create_menu_bar()
        self.setup_custom_title_bar()
        
        # Create status bar (simplified)
        self.statusBar = self.statusBar()
        self.statusBar.setObjectName("statusBar")
        self.statusBar.setSizeGripEnabled(True)
        self.document_status_label = QLabel(_("Saved · 0 words · 0 characters · Plain text · UTF-8"))
        self.document_status_label.setObjectName("bottomDocumentStatus")
        self.document_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusBar.addPermanentWidget(self.document_status_label, 1)
        QApplication.instance().installEventFilter(self)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_widget.setObjectName("mainSurface")
        main_widget.setProperty("chromeMaximized", False)
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 1, 0)
        layout.setSpacing(0)
        self.main_layout = layout
        layout.addWidget(self.custom_title_bar)
        layout.addWidget(self.toolbar)
        
        # Create tab widget
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.workspace_path = ""
        self.setup_workspace_explorer()
        self.setup_activity_ribbon()

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(LeftAlignedDocumentTabBar())
        self.tab_widget.setObjectName("documentTabs")
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setIconSize(QSize(16, 16))
        self.tab_widget.tabBar().setExpanding(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.update_topbar_context)
        
        # Install event filters on both the tab bar and its containing tab strip.
        self.tab_widget.tabBar().installEventFilter(self)
        self.tab_widget.installEventFilter(self)
        
        self.main_splitter.addWidget(self.activity_ribbon)
        self.main_splitter.addWidget(self.workspace_widget)
        self.main_splitter.addWidget(self.tab_widget)
        self.apply_workspace_sidebar_position(save=False)
        self.main_splitter.splitterMoved.connect(self.save_main_splitter_sizes)
        layout.addWidget(self.main_splitter)
        self.restore_workspace()
        
        # Create new tab if no tabs were restored
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        
        # Open file if specified
        if file_path:
            self.open_file_path(file_path)
        
        self.apply_app_style()
        self.setup_shortcuts()  # Add this line after setup_toolbar()

    def apply_app_style(self, font=None):
        """Apply the quiet writing-focused application chrome."""
        theme = ThemeManager.get_theme(
            self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app_font = QFont(font) if font is not None else self.settings_manager.get_font("ui")
        application = QApplication.instance()
        if application:
            application.setFont(app_font)
        self.setFont(app_font)
        stylesheet = ThemeManager.build_app_stylesheet(theme, app_font)
        if application:
            application.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)
        if hasattr(self, "workspace_tree"):
            self.workspace_tree.set_connector_color(theme["app"]["accent"])
        self.update_action_icons()
        self.refresh_tab_icons()

    def get_icon_color(self):
        """Return the configured icon color for the active app theme."""
        mode = self.settings_manager.get_setting("icon_contrast", "auto")
        theme = ThemeManager.get_theme(
            self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app = theme["app"]

        if mode == "light":
            return "#FFFFFF"
        if mode == "dark":
            return "#111111"
        if mode == "accent":
            return app["accent"]
        return self.high_contrast_color_for(app["surface_alt"])

    def high_contrast_color_for(self, background_color):
        """Choose a crisp icon color for the current chrome background."""
        color = QColor(background_color)
        luminance = (
            0.2126 * color.redF() +
            0.7152 * color.greenF() +
            0.0722 * color.blueF()
        )
        return "#FFFFFF" if luminance < 0.45 else "#111111"

    def build_themed_icon(self, icon_name):
        icon_data = self.icons.get(icon_name)
        if not icon_data or not icon_data.startswith('data:image/svg+xml;base64,'):
            return QIcon()

        base64_data = icon_data.split(',')[1]
        svg_data = QByteArray.fromBase64(base64_data.encode())
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(self.get_icon_color()))
        painter.end()

        icon = QIcon()
        icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(
            pixmap.scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ),
            QIcon.Mode.Normal,
            QIcon.State.Off
        )
        return icon

    def update_action_icons(self):
        if not hasattr(self, "icon_actions"):
            return
        for action, icon_name in self.icon_actions:
            action.setIcon(self.build_themed_icon(icon_name))
        for button, icon_name in getattr(self, "icon_buttons", []):
            button.setIcon(self.build_themed_icon(icon_name))
        self.update_workspace_model_icons()
        if hasattr(self, "custom_title_bar"):
            self.custom_title_bar.update_title_icon()

    def update_workspace_model_icons(self):
        if hasattr(self, "workspace_model"):
            self.workspace_model.set_workspace_icons(
                self.build_themed_icon("file"),
                self.build_themed_icon("folder"),
            )

    def setup_custom_title_bar(self):
        """Create the title bar with classic menus, search, and window controls."""
        if not hasattr(self, "custom_title_bar"):
            self.custom_title_bar = CustomTitleBar(self)
        self.custom_title_bar.show()
        menubar = self.menuBar()
        self.custom_title_bar.set_menu_bar(menubar)
        menubar.hide()

    def menuBar(self):
        if getattr(self, "app_menu_bar", None) is not None:
            return self.app_menu_bar
        return super().menuBar()

    def tab_icon_name_for_widget(self, tab):
        if getattr(tab, "is_settings_tab", False):
            return "settings"
        if isinstance(tab, EditorTab) or hasattr(tab, "current_file"):
            return "snippets"
        return ""

    def update_tab_icon(self, index):
        if index < 0 or not hasattr(self, "tab_widget"):
            return
        icon_name = self.tab_icon_name_for_widget(self.tab_widget.widget(index))
        icon = self.build_themed_icon(icon_name) if icon_name else QIcon()
        self.tab_widget.setTabIcon(index, icon)

    def refresh_tab_icons(self):
        if not hasattr(self, "tab_widget"):
            return
        for index in range(self.tab_widget.count()):
            self.update_tab_icon(index)

    def update_topbar_context(self):
        """Refresh workspace and document labels in the top bar."""
        if hasattr(self, "workspace_breadcrumb"):
            if self.workspace_path:
                self.workspace_breadcrumb.setText(os.path.basename(self.workspace_path) or self.workspace_path)
                self.workspace_breadcrumb.setToolTip(self.workspace_path)
            else:
                self.workspace_breadcrumb.setText(_("No workspace"))
                self.workspace_breadcrumb.setToolTip("")

        if not hasattr(self, "document_breadcrumb") or not hasattr(self, "tab_widget"):
            return
        current = self.tab_widget.currentWidget()
        current_index = self.tab_widget.currentIndex()
        if isinstance(current, EditorTab):
            title = self.tab_widget.tabText(current_index) if current_index >= 0 else _("Untitled")
            title = title.replace("*", " •")
            if getattr(current, "current_file", None):
                label = os.path.basename(current.current_file)
                if current.editor.document().isModified():
                    label = f"{label} •"
                self.document_breadcrumb.setToolTip(current.current_file)
            else:
                label = title or _("Untitled")
                self.document_breadcrumb.setToolTip("")
            self.document_breadcrumb.setText(label)
        elif current_index >= 0:
            self.document_breadcrumb.setText(self.tab_widget.tabText(current_index))
            self.document_breadcrumb.setToolTip("")
        else:
            self.document_breadcrumb.setText(_("Untitled"))
            self.document_breadcrumb.setToolTip("")

    def set_document_status(self, text):
        """Update the bottom ribbon without using QAction hover hints."""
        if hasattr(self, "document_status_label"):
            self.document_status_label.setText(text)

    def resolved_workspace_sidebar_position(self):
        """Return the actual sidebar side, honoring auto language direction."""
        configured = self.settings_manager.get_setting("workspace_sidebar_position", "auto")
        if configured not in ("auto", "left", "right"):
            configured = "auto"
        if configured != "auto":
            return configured
        language = self.settings_manager.get_setting("language", "en_US")
        return "right" if is_rtl_language(language) else "left"

    def apply_workspace_sidebar_position(self, save=True):
        """Move the workspace explorer to the chosen side of the editor."""
        if (
            not hasattr(self, "main_splitter")
            or not hasattr(self, "activity_ribbon")
            or not hasattr(self, "workspace_widget")
            or not hasattr(self, "tab_widget")
        ):
            return

        side = self.resolved_workspace_sidebar_position()
        splitter_sizes = self.main_splitter_sizes_for_side(side)

        if side == "right":
            if self.main_splitter.indexOf(self.tab_widget) != 0:
                self.main_splitter.insertWidget(0, self.tab_widget)
            if self.main_splitter.indexOf(self.workspace_widget) != 1:
                self.main_splitter.insertWidget(1, self.workspace_widget)
            if self.main_splitter.indexOf(self.activity_ribbon) != 2:
                self.main_splitter.insertWidget(2, self.activity_ribbon)
            self.main_splitter.setStretchFactor(0, 1)
            self.main_splitter.setStretchFactor(1, 0)
            self.main_splitter.setStretchFactor(2, 0)
            self._applying_main_splitter_sizes = True
            try:
                self.main_splitter.setSizes(splitter_sizes)
            finally:
                self._applying_main_splitter_sizes = False
        else:
            if self.main_splitter.indexOf(self.activity_ribbon) != 0:
                self.main_splitter.insertWidget(0, self.activity_ribbon)
            if self.main_splitter.indexOf(self.workspace_widget) != 1:
                self.main_splitter.insertWidget(1, self.workspace_widget)
            if self.main_splitter.indexOf(self.tab_widget) != 2:
                self.main_splitter.insertWidget(2, self.tab_widget)
            self.main_splitter.setStretchFactor(0, 0)
            self.main_splitter.setStretchFactor(1, 0)
            self.main_splitter.setStretchFactor(2, 1)
            self._applying_main_splitter_sizes = True
            try:
                self.main_splitter.setSizes(splitter_sizes)
            finally:
                self._applying_main_splitter_sizes = False

        self.workspace_widget.setProperty("side", side)
        self.activity_ribbon.setProperty("side", side)
        self.workspace_widget.style().unpolish(self.workspace_widget)
        self.workspace_widget.style().polish(self.workspace_widget)
        self.workspace_widget.update()
        self.activity_ribbon.style().unpolish(self.activity_ribbon)
        self.activity_ribbon.style().polish(self.activity_ribbon)
        self.activity_ribbon.update()

        if save:
            self.settings_manager.save_setting("workspace_sidebar_position", side)

    def default_main_splitter_sizes(self, side):
        activity_size = 48
        workspace_size = WORKSPACE_SIDEBAR_WIDTH
        editor_size = max(self.tab_widget.width(), 940) if hasattr(self, "tab_widget") else 940
        if side == "right":
            return [editor_size, workspace_size, activity_size]
        return [activity_size, workspace_size, editor_size]

    def valid_main_splitter_sizes(self, sizes):
        if not isinstance(sizes, list) or len(sizes) != 3:
            return False
        try:
            sizes = [int(size) for size in sizes]
        except (TypeError, ValueError):
            return False
        return all(size >= 0 for size in sizes) and sum(sizes) > 0

    def main_splitter_sizes_for_side(self, side):
        saved_sizes = self.settings_manager.get_setting("main_splitter_sizes", {})
        if isinstance(saved_sizes, dict) and self.valid_main_splitter_sizes(saved_sizes.get(side)):
            return [int(size) for size in saved_sizes[side]]
        return self.default_main_splitter_sizes(side)

    def save_main_splitter_sizes(self, *_args):
        if getattr(self, "_applying_main_splitter_sizes", False):
            return
        if not hasattr(self, "main_splitter"):
            return
        side = self.resolved_workspace_sidebar_position()
        sizes = [int(size) for size in self.main_splitter.sizes()]
        if not self.valid_main_splitter_sizes(sizes):
            return
        saved_sizes = self.settings_manager.get_setting("main_splitter_sizes", {})
        if not isinstance(saved_sizes, dict):
            saved_sizes = {}
        if saved_sizes.get(side) == sizes:
            return
        saved_sizes[side] = sizes
        self.settings_manager.save_setting("main_splitter_sizes", saved_sizes)

    def toggle_workspace_sidebar_position(self):
        """Toggle the file browser between left and right, like modern editors."""
        self.save_main_splitter_sizes()
        current = self.resolved_workspace_sidebar_position()
        self.settings_manager.save_setting(
            "workspace_sidebar_position",
            "right" if current == "left" else "left"
        )
        self.apply_workspace_sidebar_position(save=False)

    def toggle_workspace_sidebar_visibility(self):
        """Show or hide the workspace explorer while keeping the activity ribbon available."""
        if not hasattr(self, "workspace_widget"):
            return
        self.animate_widget_visibility(self.workspace_widget, not self.workspace_widget.isVisible())

    def setup_workspace_explorer(self):
        """Create the persisted workspace file explorer."""
        self.workspace_widget = QWidget()
        self.workspace_widget.setObjectName("workspaceExplorer")
        self.workspace_widget.setProperty("side", "left")
        self.workspace_widget.setMinimumWidth(WORKSPACE_SIDEBAR_MIN_WIDTH)
        self.workspace_widget.setMaximumWidth(WORKSPACE_SIDEBAR_MAX_WIDTH)
        workspace_layout = QVBoxLayout(self.workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 6, 6, 6)
        header_layout.setSpacing(5)

        self.workspace_title = QPushButton(_("Workspace"))
        self.workspace_title.setObjectName("workspaceTitle")
        self.workspace_title.setFlat(True)
        self.workspace_title.setToolTip(_("Switch workspace"))
        self.workspace_title.clicked.connect(self.show_workspace_navigator)
        self.workspace_path_label = QLabel(_("No folder open"))
        self.workspace_path_label.setObjectName("workspacePath")

        title_stack = QWidget()
        title_stack.setObjectName("workspaceIdentity")
        title_stack_layout = QVBoxLayout(title_stack)
        title_stack_layout.setContentsMargins(0, 0, 0, 0)
        title_stack_layout.setSpacing(1)
        title_stack_layout.addWidget(self.workspace_title)
        title_stack_layout.addWidget(self.workspace_path_label)
        header_layout.addWidget(title_stack, 1)

        self.icon_buttons = getattr(self, "icon_buttons", [])

        self.new_workspace_file_button = QPushButton()
        self.new_workspace_file_button.setObjectName("workspaceToolButton")
        self.new_workspace_file_button.setFixedSize(22, 22)
        self.new_workspace_file_button.setIcon(self.build_themed_icon("file"))
        self.new_workspace_file_button.setIconSize(QSize(16, 16))
        self.new_workspace_file_button.setToolTip(_("New file in workspace"))
        self.new_workspace_file_button.clicked.connect(self.create_workspace_file)
        self.icon_buttons.append((self.new_workspace_file_button, "file"))
        header_layout.addWidget(self.new_workspace_file_button)

        self.new_workspace_folder_button = QPushButton()
        self.new_workspace_folder_button.setObjectName("workspaceToolButton")
        self.new_workspace_folder_button.setFixedSize(22, 22)
        self.new_workspace_folder_button.setIcon(self.build_themed_icon("folder"))
        self.new_workspace_folder_button.setIconSize(QSize(16, 16))
        self.new_workspace_folder_button.setToolTip(_("New folder in workspace"))
        self.new_workspace_folder_button.clicked.connect(self.create_workspace_folder)
        self.icon_buttons.append((self.new_workspace_folder_button, "folder"))
        header_layout.addWidget(self.new_workspace_folder_button)

        workspace_layout.addWidget(header)

        self.workspace_model = WorkspaceFileSystemModel(self)
        self.update_workspace_model_icons()
        self.workspace_model.setFilter(
            QDir.Filter.AllDirs |
            QDir.Filter.Files |
            QDir.Filter.NoDotAndDotDot
        )
        self.workspace_model.setNameFilterDisables(False)

        self.workspace_tree = WorkspaceTreeView()
        self.workspace_tree.setObjectName("workspaceTree")
        self.workspace_tree.setModel(self.workspace_model)
        self.workspace_tree.setHeaderHidden(True)
        self.workspace_tree.setAnimated(True)
        self.workspace_tree.setAlternatingRowColors(False)
        self.workspace_tree.setAllColumnsShowFocus(False)
        self.workspace_tree.setExpandsOnDoubleClick(True)
        self.workspace_tree.setIndentation(12)
        self.workspace_tree.setRootIsDecorated(True)
        self.workspace_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workspace_tree.doubleClicked.connect(self.open_workspace_index)
        self.workspace_tree.customContextMenuRequested.connect(self.show_workspace_context_menu)
        for column in range(1, 4):
            self.workspace_tree.hideColumn(column)
        workspace_layout.addWidget(self.workspace_tree)
        self.workspace_widget.hide()
        self.ui_animations = {}

    def setup_activity_ribbon(self):
        """Create a VS Code-style vertical activity bar for workspace and plugin surfaces."""
        self.activity_ribbon = QWidget()
        self.activity_ribbon.setObjectName("activityRibbon")
        self.activity_ribbon.setProperty("side", "left")
        self.activity_ribbon.setFixedWidth(48)
        self.icon_buttons = getattr(self, "icon_buttons", [])

        layout = QVBoxLayout(self.activity_ribbon)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(4)

        def add_button(title, icon_name, handler, checkable=False):
            button = QToolButton()
            button.setObjectName("activityButton")
            button.setIcon(self.build_themed_icon(icon_name))
            button.setIconSize(QSize(20, 20))
            button.setFixedSize(40, 38)
            button.setToolTip(_(title))
            button.setCheckable(checkable)
            button.clicked.connect(handler)
            layout.addWidget(button)
            self.icon_buttons.append((button, icon_name))
            return button

        self.workspace_activity_button = add_button(
            "Files",
            "document-open",
            self.toggle_workspace_sidebar_visibility,
            checkable=True
        )
        self.workspace_activity_button.setChecked(True)
        add_button("Snippets", "snippets", self.toggle_snippets)
        if self.settings_manager.is_plugin_enabled("browser-panel"):
            add_button("Browser", "browser", self.toggle_browser)
        add_button("RSS", "globe", self.new_rss_tab)

        plugin_items = (
            self.plugin_manager.registry.panels
            + self.plugin_manager.registry.sidebar_items
            + self.plugin_manager.registry.toolbar_actions
        )
        if plugin_items:
            layout.addSpacing(8)
        seen_plugin_targets = set()
        for plugin_item in plugin_items:
            target_key = (
                plugin_item.get("panel")
                or plugin_item.get("panelId")
                or plugin_item.get("id")
                or plugin_item.get("title")
            )
            if not target_key or target_key in seen_plugin_targets:
                continue
            seen_plugin_targets.add(target_key)
            title = plugin_item.get("title") or target_key
            icon_name = plugin_item.get("icon") or "applications-system"
            add_button(
                title,
                icon_name,
                lambda checked=False, item=plugin_item: self.trigger_plugin_action(item)
            )

        layout.addStretch(1)
        self.settings_activity_button = add_button(
            "Settings",
            "applications-system",
            self.show_settings
        )

    def animations_enabled(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return False
        return bool(self.settings_manager.get_setting("enable_animations", True))

    def animate_widget_visibility(self, widget, visible, duration=260):
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

        default_target_width = WORKSPACE_SIDEBAR_WIDTH if widget is getattr(self, "workspace_widget", None) else 260
        target_width = max(widget.width(), widget.sizeHint().width(), default_target_width)
        if not visible and widget.width() > 0:
            target_width = widget.width()

        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        group = QParallelAnimationGroup(self)
        opacity_animation = QPropertyAnimation(effect, b"opacity", group)
        opacity_animation.setDuration(duration)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity_animation.setStartValue(0.0 if visible else 1.0)
        opacity_animation.setEndValue(1.0 if visible else 0.0)

        width_animation = QPropertyAnimation(widget, b"maximumWidth", group)
        width_animation.setDuration(duration)
        width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        width_animation.setStartValue(0 if visible else target_width)
        width_animation.setEndValue(target_width if visible else 0)

        group.addAnimation(opacity_animation)
        group.addAnimation(width_animation)
        self.ui_animations[widget] = group

        if visible:
            widget.setMaximumWidth(0)
            effect.setOpacity(0.0)
            widget.setVisible(True)
        else:
            widget.setMaximumWidth(target_width)
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

    def restore_workspace(self):
        """Restore the last workspace and open workspace files."""
        path = self.settings_manager.get_setting("workspace_path", "")
        if path and os.path.isdir(path):
            self.set_workspace_path(path, save=False)
            self.restore_workspace_session(path)

    def set_workspace_path(self, path, save=True):
        """Set and display the active workspace directory."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return False

        self.workspace_path = path
        root_index = self.workspace_model.setRootPath(path)
        self.workspace_tree.setRootIndex(root_index)
        self.workspace_title.setText(os.path.basename(path) or path)
        self.workspace_title.setToolTip(_("Switch workspace\n{path}").format(path=path))
        self.workspace_path_label.setText(os.path.dirname(path) or path)
        self.workspace_path_label.setToolTip(path)
        self.animate_widget_visibility(self.workspace_widget, True)
        self.workspace_tree.expand(root_index)
        if save:
            self.settings_manager.save_setting("workspace_path", path)
            self.add_recent_workspace(path)
            self.save_workspace_markdown_files()
        self.statusBar.showMessage(_("Workspace: {path}").format(path=path))
        self.update_topbar_context()
        return True

    def open_workspace_dialog(self):
        """Choose a directory to use as the current workspace."""
        start_dir = self.workspace_path or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, _("Open Workspace"), start_dir)
        if directory:
            self.switch_workspace(directory)

    def show_workspace_navigator(self):
        """Show recent workspace switcher under the workspace title."""
        menu = QMenu(self)
        recent_workspaces = self.get_recent_workspaces()
        if self.workspace_path:
            current_action = menu.addAction(os.path.basename(self.workspace_path) or self.workspace_path)
            current_action.setEnabled(False)
            menu.addSeparator()

        for workspace in recent_workspaces:
            if workspace == self.workspace_path:
                continue
            label = os.path.basename(workspace) or workspace
            action = menu.addAction(label)
            action.setToolTip(workspace)
            action.setEnabled(os.path.isdir(workspace))
            action.triggered.connect(lambda checked=False, path=workspace: self.switch_workspace(path))

        if recent_workspaces:
            menu.addSeparator()
        menu.addAction(_("Open Workspace..."), self.open_workspace_dialog)
        menu.addAction(_("Clear Missing Workspaces"), self.clear_missing_workspaces)
        menu.exec(self.workspace_title.mapToGlobal(self.workspace_title.rect().bottomLeft()))

    def get_recent_workspaces(self):
        """Return existing recent workspaces, preserving order."""
        workspaces = self.settings_manager.get_setting("recent_workspaces", [])
        if not isinstance(workspaces, list):
            return []
        clean = []
        for workspace in workspaces:
            path = os.path.abspath(str(workspace))
            if path not in clean:
                clean.append(path)
        return clean

    def add_recent_workspace(self, path):
        """Put a workspace at the top of the recent list."""
        path = os.path.abspath(path)
        recent = [item for item in self.get_recent_workspaces() if item != path]
        recent.insert(0, path)
        self.settings_manager.save_setting("recent_workspaces", recent[:12])

    def clear_missing_workspaces(self):
        """Remove recent workspaces that no longer exist."""
        self.settings_manager.save_setting(
            "recent_workspaces",
            [path for path in self.get_recent_workspaces() if os.path.isdir(path)]
        )

    def get_workspace_sessions(self):
        """Return stored per-workspace sessions."""
        sessions = self.settings_manager.get_setting("workspace_sessions", {})
        return sessions if isinstance(sessions, dict) else {}

    def save_workspace_sessions(self, sessions):
        self.settings_manager.save_setting("workspace_sessions", sessions)

    def workspace_relative_path(self, path, workspace=None):
        """Store workspace files relative to their workspace root."""
        workspace = workspace or self.workspace_path
        try:
            return os.path.relpath(os.path.abspath(path), workspace)
        except ValueError:
            return os.path.abspath(path)

    def workspace_absolute_path(self, path, workspace=None):
        """Resolve session paths, accepting older absolute paths too."""
        workspace = workspace or self.workspace_path
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(workspace, path))

    def save_current_workspace_session(self):
        """Save the current workspace's open files and Markdown inventory."""
        if not self.workspace_path:
            return
        sessions = self.get_workspace_sessions()
        workspace = self.workspace_path
        open_files = [
            self.workspace_relative_path(path, workspace)
            for path in self.get_open_files()
            if self.is_path_in_workspace(path)
        ]
        markdown_files = [
            self.workspace_relative_path(path, workspace)
            for path in self.get_workspace_markdown_files()
        ]
        sessions[workspace] = {
            "open_files": open_files,
            "markdown_files": markdown_files
        }
        self.save_workspace_sessions(sessions)
        self.settings_manager.save_setting("workspace_open_files", [
            self.workspace_absolute_path(path, workspace)
            for path in open_files
        ])
        self.settings_manager.save_setting("workspace_markdown_files", [
            self.workspace_absolute_path(path, workspace)
            for path in markdown_files
        ])

    def restore_workspace_session(self, workspace):
        """Open files remembered for a workspace."""
        sessions = self.get_workspace_sessions()
        session = sessions.get(os.path.abspath(workspace), {})
        open_files = session.get("open_files")
        if not open_files:
            open_files = self.settings_manager.get_setting("workspace_open_files", [])

        for file_path in open_files:
            absolute_path = self.workspace_absolute_path(file_path, workspace)
            if self.is_path_in_workspace(absolute_path) and os.path.isfile(absolute_path):
                self.open_file(absolute_path)

    def switch_workspace(self, path):
        """Switch to a workspace and restore its session."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, _("Workspace"), _("Workspace directory does not exist."))
            return False
        if path == self.workspace_path:
            return True
        self.save_current_workspace_session()
        if not self.close_current_workspace_tabs():
            return False
        self.set_workspace_path(path, save=True)
        self.restore_workspace_session(path)
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        return True

    def close_current_workspace_tabs(self):
        """Close tabs owned by the current workspace before switching."""
        if not self.workspace_path:
            return True
        index = self.tab_widget.count() - 1
        while index >= 0:
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab) and self.is_path_in_workspace(tab.current_file):
                if tab.editor.document().isModified():
                    reply = QMessageBox.question(
                        self,
                        _("Unsaved Changes"),
                        _("{filename} has unsaved changes. Save before switching workspaces?").format(
                            filename=os.path.basename(tab.current_file)
                        ),
                        QMessageBox.StandardButton.Save |
                        QMessageBox.StandardButton.Discard |
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Save and not tab.save_file():
                        return False
                    if reply == QMessageBox.StandardButton.Cancel:
                        return False
                self.tab_widget.removeTab(index)
                tab.deleteLater()
            index -= 1
        return True

    def is_path_in_workspace(self, path):
        """Return True when a file belongs to the active workspace."""
        if not self.workspace_path or not path:
            return False
        try:
            return os.path.commonpath([
                os.path.abspath(path),
                self.workspace_path
            ]) == self.workspace_path
        except ValueError:
            return False

    def save_workspace_open_files(self):
        """Persist open files that are inside the active workspace."""
        if not self.workspace_path:
            self.settings_manager.save_setting("workspace_open_files", [])
            return
        workspace = self.workspace_path
        files = [
            path for path in self.get_open_files()
            if self.is_path_in_workspace(path)
        ]
        self.settings_manager.save_setting("workspace_open_files", files)
        sessions = self.get_workspace_sessions()
        session = sessions.get(workspace, {})
        session["open_files"] = [
            self.workspace_relative_path(path, workspace)
            for path in files
        ]
        sessions[workspace] = session
        self.save_workspace_sessions(sessions)

    def get_workspace_markdown_files(self):
        """Return all Markdown files under the active workspace."""
        if not self.workspace_path:
            return []
        markdown_files = []
        markdown_extensions = (".md", ".markdown", ".mdown", ".mkd")
        for root, _dirs, files in os.walk(self.workspace_path):
            for filename in files:
                if filename.lower().endswith(markdown_extensions):
                    markdown_files.append(os.path.join(root, filename))
        return sorted(markdown_files)

    def save_workspace_markdown_files(self):
        """Persist the current workspace Markdown inventory."""
        markdown_files = self.get_workspace_markdown_files()
        self.settings_manager.save_setting("workspace_markdown_files", markdown_files)
        if self.workspace_path:
            workspace = self.workspace_path
            sessions = self.get_workspace_sessions()
            session = sessions.get(workspace, {})
            session["markdown_files"] = [
                self.workspace_relative_path(path, workspace)
                for path in markdown_files
            ]
            sessions[workspace] = session
            self.save_workspace_sessions(sessions)

    def selected_workspace_directory(self):
        """Return the selected folder, or containing folder for a selected file."""
        if not self.workspace_path:
            return ""
        index = self.workspace_tree.currentIndex()
        if index.isValid():
            path = self.workspace_model.filePath(index)
            if os.path.isdir(path):
                return path
            if os.path.isfile(path):
                return os.path.dirname(path)
        return self.workspace_path

    def open_workspace_index(self, index):
        """Open a file from the workspace tree."""
        path = self.workspace_model.filePath(index)
        if os.path.isfile(path):
            self.open_file(path)

    def show_workspace_context_menu(self, position):
        """Show workspace file operations."""
        if not self.workspace_path:
            return
        menu = QMenu(self)
        menu.addAction(self.build_themed_icon("file"), _("New File"), self.create_workspace_file)
        menu.addAction(self.build_themed_icon("folder"), _("New Folder"), self.create_workspace_folder)
        menu.addSeparator()
        index = self.workspace_tree.indexAt(position)
        if index.isValid() and os.path.isfile(self.workspace_model.filePath(index)):
            menu.addAction(_("Open"), lambda: self.open_workspace_index(index))
        menu.exec(self.workspace_tree.mapToGlobal(position))

    def create_workspace_file(self):
        """Create any file inside the active workspace."""
        if not self.workspace_path:
            self.open_workspace_dialog()
            if not self.workspace_path:
                return
        directory = self.selected_workspace_directory()
        name, ok = QInputDialog.getText(self, _("New File"), _("File name:"))
        if not ok or not name.strip():
            return
        target = os.path.abspath(os.path.join(directory, name.strip()))
        if not self.is_path_in_workspace(target):
            QMessageBox.warning(self, _("Workspace"), _("File must be inside the workspace."))
            return
        if os.path.exists(target):
            QMessageBox.warning(self, _("Workspace"), _("A file or folder with that name already exists."))
            return
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            with open(target, "w", encoding="utf-8"):
                pass
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not create file: {error}").format(error=exc))
            return
        self.save_workspace_markdown_files()
        self.open_file(target)

    def create_workspace_folder(self):
        """Create a folder inside the active workspace."""
        if not self.workspace_path:
            return
        directory = self.selected_workspace_directory()
        name, ok = QInputDialog.getText(self, _("New Folder"), _("Folder name:"))
        if not ok or not name.strip():
            return
        target = os.path.abspath(os.path.join(directory, name.strip()))
        if not self.is_path_in_workspace(target):
            QMessageBox.warning(self, _("Workspace"), _("Folder must be inside the workspace."))
            return
        try:
            os.makedirs(target, exist_ok=False)
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not create folder: {error}").format(error=exc))
            return
        self.save_workspace_markdown_files()
        
    def setup_toolbar(self):
        """Setup the main toolbar"""
        self.toolbar = QToolBar(_("Main Toolbar"))
        self.toolbar.setObjectName("mainToolBar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFixedHeight(40)
        
        # Prevent toolbar from being hidden
        self.toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        
        # Set toolbar properties for better icon rendering
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.icon_actions = []
        self.translatable_actions = []

        # Helper function to create themed action
        def create_action(icon_name, text, handler=None):
            icon_data = self.icons.get(icon_name)
            translated_text = _(text)
            if icon_data:
                # Convert base64 data URL to QIcon
                if icon_data.startswith('data:image/svg+xml;base64,'):
                    action = QAction(self.build_themed_icon(icon_name), translated_text, self)
                    self.icon_actions.append((action, icon_name))
                else:
                    action = QAction(translated_text, self)
            else:
                action = QAction(translated_text, self)
            action.setProperty("text_key", text)
            action.setProperty("tooltip_key", text)
            self.translatable_actions.append(action)
            action.setToolTip(translated_text)
            action.setStatusTip("")
            if handler:
                action.triggered.connect(handler)
            return action

        def set_action_tooltip(action, text):
            action.setProperty("tooltip_key", text)
            action.setToolTip(_(text))
            action.setStatusTip("")
            action.setWhatsThis(_(text))

        # Add the calm primary top-bar actions. Complete command groups live in the classic menus.
        new_action = create_action("new", "New", self.new_editor_tab)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        set_action_tooltip(new_action, "New (Ctrl+N)")
        
        open_action = create_action("open", "Open", self.open_file_dialog)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        set_action_tooltip(open_action, "Open (Ctrl+O)")

        workspace_toolbar_action = create_action("document-open", "Workspace", self.open_workspace_dialog)
        set_action_tooltip(workspace_toolbar_action, "Open Workspace")
        
        save_action = create_action("save", "Save", self.save_file)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        set_action_tooltip(save_action, "Save (Ctrl+S)")
        
        save_as_action = create_action("save-as", "Save As", self.save_file_as)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        set_action_tooltip(save_as_action, "Save As (Ctrl+Shift+S)")
        export_pdf_action = create_action("save-as", "Export PDF", self.export_pdf)
        set_action_tooltip(export_pdf_action, "Export current file as PDF")
        
        # Undo/Redo
        undo_action = create_action("undo", "Undo", self.undo)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        set_action_tooltip(undo_action, "Undo (Ctrl+Z)")

        redo_action = create_action("redo", "Redo", self.redo)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        set_action_tooltip(redo_action, "Redo (Ctrl+Shift+Z)")
        
        # Find/Replace and Focus Mode
        find_action = create_action("find", "Find/Replace", self.toggle_find)
        set_action_tooltip(find_action, "Find/Replace (Ctrl+F)")
        self.toolbar.addAction(find_action)
        
        focus_action = create_action("focus-mode", "Focus Mode", self.toggle_focus_mode)
        focus_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        set_action_tooltip(focus_action, "Focus Mode (Ctrl+Shift+D)")
        focus_action.setCheckable(True)
        self.toolbar.addAction(focus_action)
        self.focus_mode_action = focus_action
        
        # Fonts
        editor_font_action = create_action("font", "Editor Font", self.show_editor_font_dialog)
        set_action_tooltip(editor_font_action, "Choose Editor Font")
        self.toolbar.addAction(editor_font_action)
        
        # View toggles
        snippets_action = create_action("snippets", "Snippets", lambda: self.toggle_snippets())
        snippets_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        set_action_tooltip(snippets_action, "Toggle Snippets (Ctrl+Shift+N)")
        self.toolbar.addAction(snippets_action)

        markdown_action = create_action("insert-text", "Markdown", self.toggle_markdown_preview)
        markdown_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        set_action_tooltip(markdown_action, "Toggle Markdown Preview (Ctrl+Shift+M)")

        for toolbar_action in self.plugin_manager.registry.toolbar_actions:
            title = toolbar_action.get("title") or toolbar_action.get("id") or _("Plugin")
            action = create_action(
                toolbar_action.get("icon", ""),
                title,
                lambda checked=False, item=toolbar_action: self.trigger_plugin_action(item)
            )
            if toolbar_action.get("shortcut"):
                action.setShortcut(QKeySequence(toolbar_action["shortcut"]))
            set_action_tooltip(action, toolbar_action.get("tooltip", title))
            self.toolbar.addAction(action)

        # Zoom controls
        zoom_in_action = create_action("zoom-in", "Zoom In", self.zoom_in)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        set_action_tooltip(zoom_in_action, "Zoom In (Ctrl+=)")
        self.toolbar.addAction(zoom_in_action)

        zoom_out_action = create_action("zoom-out", "Zoom Out", self.zoom_out)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        set_action_tooltip(zoom_out_action, "Zoom Out (Ctrl+-)")
        self.toolbar.addAction(zoom_out_action)

        zoom_reset_action = create_action("zoom-reset", "Reset Zoom", self.zoom_reset)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        set_action_tooltip(zoom_reset_action, "Reset Zoom (Ctrl+0)")
        self.toolbar.addAction(zoom_reset_action)

        # Now set the overflow button text after all items are added
        def update_overflow_button():
            overflow_button = self.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            if overflow_button:
                overflow_button.setText(">>")
                overflow_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        
        # Use a single-shot timer to ensure the overflow button exists
        QTimer.singleShot(0, update_overflow_button)

    def retranslate_actions(self):
        """Refresh toolbar and classic menu labels after the active language changes."""
        if not hasattr(self, "translatable_actions"):
            return
        for action in self.translatable_actions:
            text_key = action.property("text_key")
            tooltip_key = action.property("tooltip_key")
            if text_key:
                action.setText(_(text_key))
            if tooltip_key:
                translated_tooltip = _(tooltip_key)
                action.setToolTip(translated_tooltip)
                action.setStatusTip("")
                action.setWhatsThis(translated_tooltip)
        if hasattr(self, "translatable_menus"):
            self.menuBar().setAccessibleName(_("Application menu"))
            for menu, title in self.translatable_menus:
                menu.setAccessibleName(_("{title} menu").format(title=_(title)))
        if hasattr(self, "custom_title_bar"):
            self.custom_title_bar.refresh_title_menu_buttons(self.menuBar())

    def apply_layout_direction(self, language):
        direction = (
            Qt.LayoutDirection.RightToLeft
            if is_rtl_language(language)
            else Qt.LayoutDirection.LeftToRight
        )
        app = QApplication.instance()
        if app:
            app.setLayoutDirection(direction)
        self.setLayoutDirection(direction)
        if (
            hasattr(self, "main_splitter")
            and self.settings_manager.get_setting("workspace_sidebar_position", "auto") == "auto"
        ):
            self.apply_workspace_sidebar_position(save=False)

    def apply_language_direction_to_tabs(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, "apply_language_direction"):
                tab.apply_language_direction()

    def get_current_editor(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            return current_tab.editor
        return None
        
    def undo(self):
        editor = self.get_current_editor()
        if editor:
            editor.undo()
            
    def redo(self):
        editor = self.get_current_editor()
        if editor:
            editor.redo()
            
    def cut(self):
        editor = self.get_current_editor()
        if editor:
            editor.cut()
            
    def copy(self):
        editor = self.get_current_editor()
        if editor:
            editor.copy()
            
    def paste(self):
        editor = self.get_current_editor()
        if editor:
            editor.paste()
        
    def new_tab(self):
        editor_tab = EditorTab(self.snippet_manager)
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("snippets"),
            _("Document {number}").format(number=self.tab_widget.count() + 1)
        )
        self.tab_widget.setCurrentWidget(editor_tab)

    def is_editor_tab_modified(self, tab):
        """Return True only for editor tabs with unsaved document changes."""
        return (
            isinstance(tab, EditorTab) and
            hasattr(tab, "editor") and
            tab.editor.document().isModified()
        )
        
    def close_tab(self, index):
        """Handle tab close"""
        tab = self.tab_widget.widget(index)
        
        if self.is_editor_tab_modified(tab):
            reply = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("This document has unsaved changes. Do you want to save them?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.tab_widget.setCurrentIndex(index)
                if not tab.save_file():  # If save is cancelled
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.tab_widget.removeTab(index)
        self.save_workspace_open_files()
        
        # Create new tab if last tab was closed
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
            
    def create_menu_bar(self):
        menubar = self.menuBar()
        self.app_menu_bar = menubar
        menubar.clear()
        menubar.setObjectName("appMenuBar")
        menubar.setAccessibleName(_("Application menu"))
        menubar.setNativeMenuBar(False)
        menubar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.translatable_menus = []

        def add_menu(title):
            menu = menubar.addMenu(_(title))
            menu.setAccessibleName(_("{title} menu").format(title=_(title)))
            menu.menuAction().setProperty("text_key", title)
            self.translatable_actions.append(menu.menuAction())
            self.translatable_menus.append((menu, title))
            return menu

        def add_action(menu, text, handler, icon_name=None, shortcut=None, tooltip=None, checkable=False):
            action = QAction(self.build_themed_icon(icon_name) if icon_name else QIcon(), _(text), self)
            action.setProperty("text_key", text)
            action.setProperty("tooltip_key", tooltip or text)
            action.setProperty("accessibility_label", tooltip or text)
            action.setToolTip(_(tooltip or text))
            action.setStatusTip("")
            action.setWhatsThis(_(tooltip or text))
            action.setCheckable(checkable)
            if shortcut is not None:
                action.setShortcut(shortcut)
            if handler:
                action.triggered.connect(handler)
            menu.addAction(action)
            self.translatable_actions.append(action)
            if icon_name:
                self.icon_actions.append((action, icon_name))
            return action

        # File menu
        file_menu = add_menu("File")

        add_action(
            file_menu,
            "New Editor Tab",
            self.new_editor_tab,
            "new",
            QKeySequence.StandardKey.New,
            "Create a new editor tab"
        )
        file_menu.addSeparator()
        add_action(file_menu, "Open...", self.open_file_dialog, "open", QKeySequence.StandardKey.Open, "Open a file")
        add_action(file_menu, "Save", self.save_file, "save", QKeySequence.StandardKey.Save, "Save current file")
        add_action(
            file_menu,
            "Save As...",
            self.save_file_as,
            "save-as",
            QKeySequence.StandardKey.SaveAs,
            "Save current file with a new name"
        )
        add_action(file_menu, "Export as PDF...", self.export_pdf, "save-as", tooltip="Export current file as PDF")
        file_menu.addSeparator()
        add_action(file_menu, "Settings", self.show_settings, "settings", tooltip="Open Settings")
        file_menu.addSeparator()
        add_action(file_menu, "Close Tab", self.close_current_tab, shortcut=QKeySequence.StandardKey.Close, tooltip="Close current tab")
        add_action(file_menu, "Exit", self.close, shortcut=QKeySequence.StandardKey.Quit, tooltip="Exit Jottr")

        # Edit menu
        edit_menu = add_menu("Edit")
        add_action(edit_menu, "Undo", self.undo, "undo", QKeySequence.StandardKey.Undo, "Undo")
        add_action(edit_menu, "Redo", self.redo, "redo", QKeySequence.StandardKey.Redo, "Redo")
        edit_menu.addSeparator()
        add_action(edit_menu, "Cut", self.cut, shortcut=QKeySequence.StandardKey.Cut, tooltip="Cut")
        add_action(edit_menu, "Copy", self.copy, shortcut=QKeySequence.StandardKey.Copy, tooltip="Copy")
        add_action(edit_menu, "Paste", self.paste, shortcut=QKeySequence.StandardKey.Paste, tooltip="Paste")
        edit_menu.addSeparator()
        add_action(edit_menu, "Find/Replace", self.toggle_find, "find", QKeySequence.StandardKey.Find, "Find/Replace")
        add_action(edit_menu, "Editor Font", self.show_editor_font_dialog, "font", tooltip="Choose Editor Font")

        # View menu
        view_menu = add_menu("View")

        add_action(view_menu, "Toggle Snippets", self.toggle_snippets, "snippets", QKeySequence("Ctrl+Shift+N"), "Toggle Snippets")
        add_action(
            view_menu,
            "Toggle Markdown Preview",
            self.toggle_markdown_preview,
            "insert-text",
            QKeySequence("Ctrl+Shift+M"),
            "Toggle Markdown Preview"
        )
        add_action(
            view_menu,
            "Focus Mode",
            self.toggle_focus_mode,
            "focus-mode",
            QKeySequence("Ctrl+Shift+D"),
            "Focus Mode",
            True
        )
        view_menu.addSeparator()

        add_action(view_menu, "Zoom In", self.zoom_in, "zoom-in", QKeySequence("Ctrl+="), "Zoom In")
        add_action(view_menu, "Zoom Out", self.zoom_out, "zoom-out", QKeySequence("Ctrl+-"), "Zoom Out")
        add_action(view_menu, "Reset Zoom", self.zoom_reset, "zoom-reset", QKeySequence("Ctrl+0"), "Reset Zoom")

        # Workspace menu
        workspace_menu = add_menu("Workspace")
        add_action(workspace_menu, "Open Workspace...", self.open_workspace_dialog, "document-open", tooltip="Open Workspace")
        add_action(workspace_menu, "Move Workspace Sidebar", self.toggle_workspace_sidebar_position, "document-open", tooltip="Move Workspace Sidebar")
        add_action(workspace_menu, "New Workspace File...", self.create_workspace_file, "file", tooltip="New File in Workspace")
        add_action(workspace_menu, "New Workspace Folder...", self.create_workspace_folder, "folder", tooltip="New Folder in Workspace")

        # Plugins menu
        if (
            self.plugin_manager.registry.commands
            or self.plugin_manager.registry.panels
            or self.plugin_manager.registry.sidebar_items
        ):
            plugins_menu = add_menu("Plugins")
            seen_plugin_targets = set()
            for panel in self.plugin_manager.registry.panels + self.plugin_manager.registry.sidebar_items:
                title = panel.get("title") or panel.get("id") or "Plugin Panel"
                target_key = panel.get("panel") or panel.get("panelId") or panel.get("id") or title
                if target_key in seen_plugin_targets:
                    continue
                seen_plugin_targets.add(target_key)
                handler = (
                    (lambda checked=False, item=panel: self.trigger_plugin_action(item))
                    if panel.get("builtin")
                    else (lambda checked=False, item=panel: self.open_plugin_panel(item))
                )
                add_action(
                    plugins_menu,
                    title,
                    handler,
                    tooltip=title
                )
            if self.plugin_manager.registry.commands and plugins_menu.actions():
                plugins_menu.addSeparator()
            for command in self.plugin_manager.registry.commands:
                title = command.get("title") or command.get("id") or "Plugin Command"
                shortcut = QKeySequence(command["shortcut"]) if command.get("shortcut") else None
                add_action(
                    plugins_menu,
                    title,
                    lambda checked=False, item=command: self.trigger_plugin_action(item),
                    shortcut=shortcut,
                    tooltip=title
                )

        # Help menu
        help_menu = add_menu("Help")
        add_action(help_menu, "Help", self.show_help, "help", QKeySequence.StandardKey.HelpContents, "Open Help")
        add_action(help_menu, "About", self.show_about, "about", tooltip="About Jottr")
        if hasattr(self, "custom_title_bar"):
            self.setup_custom_title_bar()
        else:
            menubar.hide()

    def close_current_tab(self):
        """Close the active document tab from the menubar or shortcut."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def save_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.save_file()
            
    def open_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.open_file()

    def new_editor_tab(self):
        """Create a new empty editor tab"""
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)  # Set reference to main window
        
        # Add tab with default title
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("snippets"),
            _("Document {number}").format(number=self.tab_widget.count() + 1)
        )
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        self.update_topbar_context()
        return editor_tab
        
    def new_rss_tab(self):
        rss_tab = RSSTab()
        self.tab_widget.addTab(rss_tab, _("RSS Reader"))
        self.tab_widget.setCurrentWidget(rss_tab)

    def apply_editor_font_to_tabs(self, font):
        """Apply the selected editor font to all open editor tabs."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.update_font(font)

    def show_editor_font_dialog(self):
        dialog = FontSelectionDialog(
            self.settings_manager.get_font("editor"),
            self,
            title=_("Choose Editor Font")
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            font = dialog.selectedFont()
            self.settings_manager.save_font(font, "editor")
            self.apply_editor_font_to_tabs(font)

    def apply_editor_theme_to_tabs(self, theme_name):
        """Apply an editor color theme to all open editor tabs."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.apply_theme(theme_name)

    def toggle_snippets(self):
        """Toggle snippets pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("snippets")

    def open_file_path(self, file_path):
        """Open a file by its path"""
        return self.open_file(file_path)

    def check_crash_recovery(self):
        """Check for and recover unsaved files from crash"""
        recovery_dir = self.settings_manager.get_recovery_dir()
        recovery_files = []
        
        # Find all recovery files with their metadata
        for filename in os.listdir(recovery_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(recovery_dir, filename)
                meta_path = file_path + '.json'
                
                try:
                    # Only recover if metadata exists and shows no clean exit
                    if os.path.exists(meta_path):
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                            
                        if not metadata.get('clean_exit', False):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if content.strip():  # Only recover non-empty files
                                    recovery_files.append((file_path, content, metadata))
                except:
                    continue
        
        # Automatically recover files that weren't cleanly exited
        for file_path, content, metadata in recovery_files:
            tab = self.new_editor_tab()
            tab.editor.setPlainText(content)
            
            # Restore cursor and scroll position
            cursor = tab.editor.textCursor()
            cursor.setPosition(metadata.get('cursor_position', 0))
            tab.editor.setTextCursor(cursor)
            tab.editor.verticalScrollBar().setValue(
                metadata.get('scroll_position', 0)
            )
            
            # Set tab title
            original_file = metadata.get('original_file')
            title = os.path.basename(original_file) if original_file else "Recovered File"
            current_index = self.tab_widget.indexOf(tab)
            self.tab_widget.setTabText(current_index, title + " (Recovered)")
            
            # Store original file path if it existed
            if original_file:
                tab.current_file = original_file

    def get_open_files(self):
        """Get list of currently open files"""
        open_files = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab) and tab.current_file:
                open_files.append(tab.current_file)
        return open_files

    def closeEvent(self, event):
        """Handle application close event"""
        if self.handle_unsaved_changes():
            self.save_main_splitter_sizes()
            self.save_workspace_markdown_files()
            self.save_workspace_open_files()
            # Save window state
            self.settings_manager.save_setting('window_state', {
                'geometry': self.saveGeometry().toBase64().data().decode(),
                'state': self.saveState().toBase64().data().decode()
            })
            event.accept()
        else:
            event.ignore()

    def open_external_url(self, url):
        """Open URL in system's default browser"""
        QDesktopServices.openUrl(QUrl(url))

    def show_help(self):
        """Show help documentation"""
        help_tab = self.new_editor_tab()
        
        # Load help content
        try:
            with open('help/help.md', 'r', encoding='utf-8') as f:
                help_content = f.read()
        except:
            help_content = _("Help documentation not found.")
        
        # Set content and make read-only
        help_tab.editor.setPlainText(help_content)
        help_tab.editor.setReadOnly(True)
        help_tab.set_markdown_preview_visible(True)
        
        # Set tab title
        current_index = self.tab_widget.indexOf(help_tab)
        self.tab_widget.setTabText(current_index, _("Help"))

    def show_about(self):
        """Show about dialog"""
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle(_("About {APP_NAME}").format(APP_NAME=APP_NAME))
        about_dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(about_dialog)
        layout.setSpacing(10)
        
        # App name
        title_label = QLabel(APP_NAME)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel(_("Version {APP_VERSION}").format(APP_VERSION=APP_VERSION))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel(_("A simple text editor for writers, journalists and researchers"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Developer
        dev_label = QLabel(_("Developed by mFat"))
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dev_label)
        
        # License
        license_label = QLabel(_("Licensed under GNU GPL v3.0"))
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)
        
        # Homepage link
        link_label = QLabel(_('<a href="{APP_HOMEPAGE}">Project Homepage</a>').format(APP_HOMEPAGE=APP_HOMEPAGE))
        link_label.setOpenExternalLinks(True)
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link_label)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(about_dialog.accept)
        button_box.setCenterButtons(True)  # Center the OK button
        layout.addWidget(button_box)
        
        about_dialog.exec()

    def toggle_focus_mode(self):
        """Toggle focus mode for current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_focus_mode()

    def update_focus_mode_action(self, checked):
        """Keep the focus toolbar action in sync with the active editor."""
        if hasattr(self, 'focus_mode_action'):
            self.focus_mode_action.setChecked(checked)

    def zoom_in(self):
        """Increase editor font size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_font = current_tab.current_font  # Use stored font
            new_font = QFont(current_font)  # Create new font based on current
            new_font.setPointSize(current_font.pointSize() + 1)
            current_tab.update_font(new_font)

    def zoom_out(self):
        """Decrease editor font size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_font = current_tab.current_font  # Use stored font
            size = current_font.pointSize()
            if size > 1:  # Prevent font from becoming too small
                new_font = QFont(current_font)  # Create new font based on current
                new_font.setPointSize(size - 1)
                current_tab.update_font(new_font)

    def zoom_reset(self):
        """Reset editor font to default size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            default_font = self.settings_manager.get_font("editor")
            # Preserve current font properties except size
            new_font = QFont(current_tab.current_font)
            new_font.setPointSize(default_font.pointSize())
            current_tab.update_font(new_font)

    

    def apply_settings_from_view(self, settings_view):
        settings = settings_view.get_data()
        plugin_settings_changed = bool(getattr(settings_view, "_plugin_settings_dirty", False))
        self.settings_manager.save_setting('homepage', settings['homepage'])
        self.settings_manager.save_setting('search_sites', settings['search_sites'])
        self.settings_manager.save_setting('user_dictionary', settings['user_dictionary'])
        self.settings_manager.save_custom_themes(settings['custom_themes'])
        self.settings_manager.save_ui_theme(settings['ui_theme'])
        self.settings_manager.save_theme(settings['theme'])
        self.settings_manager.save_setting('language', settings['language'])
        set_language(settings['language'])
        self.apply_layout_direction(settings['language'])
        self.apply_language_direction_to_tabs()
        self.retranslate_actions()
        self.settings_manager.save_setting('icon_contrast', settings['icon_contrast'])
        self.settings_manager.save_setting('enable_animations', settings['enable_animations'])
        self.settings_manager.save_font(settings['ui_font'], "ui")
        self.settings_manager.save_setting('markdown_scroll_sync', settings['markdown_scroll_sync'])
        self.settings_manager.save_setting('editor_line_numbers', settings['editor_line_numbers'])
        self.settings_manager.save_setting(
            'double_click_empty_tab_bar_new_tab',
            settings['double_click_empty_tab_bar_new_tab']
        )
        self.settings_manager.save_setting(
            'double_click_tab_closes_tab',
            settings['double_click_tab_closes_tab']
        )
        self.settings_manager.save_setting('autosave_enabled', settings['autosave_enabled'])
        self.settings_manager.save_setting('autosave_interval_seconds', settings['autosave_interval_seconds'])
        self.settings_manager.save_setting('plugins_directory', settings['plugins_directory'])
        self.settings_manager.save_setting('plugin_registry_url', settings['plugin_registry_url'])
        self.settings_manager.save_setting('plugin_registry_checksum_url', settings['plugin_registry_checksum_url'])
        self.settings_manager.save_setting('plugin_channels', settings.get('plugin_channels', []))
        self.settings_manager.save_setting('plugin_channel_filter', settings.get('plugin_channel_filter', 'all'))
        self.settings_manager.save_setting('plugin_state', settings['plugin_state'])
        self.apply_app_style()
        if plugin_settings_changed:
            self.plugin_manager = PluginManager(self.settings_manager)
            self.plugin_manager.refresh()
            self.plugin_manager.activate_enabled_plugins()
            old_toolbar = self.toolbar
            if hasattr(self, "main_layout"):
                self.main_layout.removeWidget(old_toolbar)
            self.removeToolBar(old_toolbar)
            old_toolbar.deleteLater()
            self.setup_toolbar()
            if hasattr(self, "main_layout"):
                self.main_layout.insertWidget(1, self.toolbar)
            self.create_menu_bar()
            self.setup_custom_title_bar()
            if hasattr(settings_view, "_plugin_settings_dirty"):
                settings_view._plugin_settings_dirty = False
        else:
            self.update_action_icons()
            self.retranslate_actions()
        self.apply_editor_theme_to_tabs(settings['theme'])
        self.apply_editor_line_numbers(settings['editor_line_numbers'])
        self.apply_autosave_settings()
        self.statusBar.showMessage(_("Settings applied"), 3000)

    def close_settings_tab(self, settings_view):
        index = self.tab_widget.indexOf(settings_view)
        if index >= 0:
            self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.new_editor_tab()

    def show_settings(self):
        """Open settings as a workspace tab."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if getattr(tab, "is_settings_tab", False):
                self.tab_widget.setCurrentIndex(index)
                return tab
        settings_tab = SettingsDialog(
            self.settings_manager,
            self,
            embedded=True,
            apply_callback=self.apply_settings_from_view,
            close_callback=self.close_settings_tab,
        )
        settings_tab.is_settings_tab = True
        self.tab_widget.addTab(settings_tab, self.build_themed_icon("settings"), _("Settings"))
        self.tab_widget.setCurrentWidget(settings_tab)
        return settings_tab

    def trigger_plugin_action(self, action):
        builtin = action.get("builtin")
        if builtin and self.run_builtin_plugin_action(builtin):
            return
        command_id = action.get("command") or action.get("commandId") or action.get("id")
        if command_id in self.plugin_manager.registry.command_callbacks:
            self.plugin_manager.registry.command_callbacks[command_id]()
            return
        panel_id = action.get("panel") or action.get("panelId")
        if panel_id:
            panel = self.find_plugin_panel(panel_id)
            if panel:
                self.open_plugin_panel(panel)
                return
        message = action.get("message")
        if message:
            QMessageBox.information(self, _("Plugin"), message)

    def run_builtin_plugin_action(self, action_id):
        actions = {
            "toggle_browser": self.toggle_browser,
            "toggle_markdown_preview": self.toggle_markdown_preview,
            "new_rss_tab": self.new_rss_tab,
        }
        handler = actions.get(action_id)
        if not handler:
            return False
        handler()
        return True

    def find_plugin_panel(self, panel_id):
        for panel in self.plugin_manager.registry.panels + self.plugin_manager.registry.sidebar_items:
            if panel.get("id") == panel_id:
                return panel
        return None

    def open_plugin_panel(self, panel):
        panel_id = panel.get("id")
        title = panel.get("title") or panel_id or _("Plugin")
        if panel_id not in self.plugin_manager.registry.panel_factories and panel.get("type") == "python":
            plugin_name = panel.get("plugin")
            if plugin_name:
                try:
                    self.plugin_manager.install_plugin_from_registry(plugin_name)
                    self.plugin_manager.activate_enabled_plugins()
                except Exception as exc:
                    QMessageBox.warning(
                        self,
                        _("Plugin"),
                        _("Could not install plugin: {error}").format(error=exc)
                    )
        if panel_id in self.plugin_manager.registry.panel_factories:
            widget = self.plugin_manager.registry.panel_factories[panel_id]()
        else:
            widget = self.create_manifest_plugin_panel(panel)
        self.tab_widget.addTab(widget, title)
        self.tab_widget.setCurrentWidget(widget)

    def create_manifest_plugin_panel(self, panel):
        panel_type = panel.get("type", "text")
        if panel_type in {"browser", "web"}:
            view = QWebEngineView()
            url = panel.get("url") or panel.get("homepage") or "about:blank"
            view.load(QUrl(url))
            return view
        if panel_type == "rss":
            return RSSTab()
        label = QLabel(panel.get("content") or panel.get("description") or _("Plugin panel"))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return label

    def toggle_browser(self):
        """Toggle browser pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("browser")

    def apply_editor_line_numbers(self, visible):
        """Apply line number visibility to all open editor tabs."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.set_line_numbers_visible(visible)

    def apply_autosave_settings(self):
        """Apply autosave settings to all open editor tabs."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.configure_autosave_timer()

    def toggle_markdown_preview(self):
        """Toggle markdown preview in current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_markdown_preview()

    def toggle_find(self):
        """Toggle find/replace in current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_find()

    def save_file_as(self):
        """Save current file with a new name"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.save_file(force_dialog=True)

    def export_pdf(self):
        """Export the current editor tab as a PDF."""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and hasattr(current_tab, "export_pdf"):
            current_tab.export_pdf()

    def update_window_state_properties(self):
        """Refresh stylesheet state for frameless window chrome."""
        self.setProperty("chromeMaximized", self.isMaximized())
        central = self.centralWidget()
        if central:
            central.setProperty("chromeMaximized", self.isMaximized())
            central.style().unpolish(central)
            central.style().polish(central)
            central.update()
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_window_state_properties()
            if hasattr(self, "custom_title_bar"):
                self.custom_title_bar.update_maximize_button()
        super().changeEvent(event)

    def showEvent(self, event):
        self.update_window_state_properties()
        super().showEvent(event)

    def resize_hit_test(self, global_pos):
        """Return native resize edges and cursor for a global pointer position."""
        if self.isMaximized() or self.isFullScreen():
            return None, None
        if hasattr(global_pos, "toPoint"):
            global_pos = global_pos.toPoint()

        geometry = self.frameGeometry()
        x = global_pos.x()
        y = global_pos.y()
        margin = self.resize_margin
        left = geometry.left() <= x <= geometry.left() + margin
        right = geometry.right() - margin <= x <= geometry.right()
        top = geometry.top() <= y <= geometry.top() + margin
        bottom = geometry.bottom() - margin <= y <= geometry.bottom()

        edges = None
        for enabled, edge in (
            (left, Qt.Edge.LeftEdge),
            (right, Qt.Edge.RightEdge),
            (top, Qt.Edge.TopEdge),
            (bottom, Qt.Edge.BottomEdge),
        ):
            if enabled:
                edges = edge if edges is None else edges | edge

        if edges is None:
            return None, None
        if (left and top) or (right and bottom):
            return edges, Qt.CursorShape.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return edges, Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return edges, Qt.CursorShape.SizeHorCursor
        return edges, Qt.CursorShape.SizeVerCursor

    def object_belongs_to_window(self, obj):
        return isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj))

    def set_resize_cursor(self, cursor):
        app = QApplication.instance()
        if not app:
            return
        if cursor and not self.resize_cursor_active:
            app.setOverrideCursor(QCursor(cursor))
            self.resize_cursor_active = True
        elif not cursor and self.resize_cursor_active:
            app.restoreOverrideCursor()
            self.resize_cursor_active = False

    def start_window_resize(self, edges, global_pos):
        handle = self.windowHandle()
        if handle and handle.startSystemResize(edges):
            return True
        if hasattr(global_pos, "toPoint"):
            global_pos = global_pos.toPoint()
        self.resize_edges = edges
        self.resize_start_pos = global_pos
        self.resize_start_geometry = QRect(self.geometry())
        return True

    def continue_window_resize(self, global_pos):
        if self.resize_edges is None or self.resize_start_geometry is None:
            return False
        if hasattr(global_pos, "toPoint"):
            global_pos = global_pos.toPoint()
        delta = global_pos - self.resize_start_pos
        geometry = QRect(self.resize_start_geometry)
        minimum = self.minimumSize()

        if self.resize_edges & Qt.Edge.LeftEdge:
            new_left = geometry.left() + delta.x()
            if geometry.right() - new_left + 1 >= minimum.width():
                geometry.setLeft(new_left)
        if self.resize_edges & Qt.Edge.RightEdge:
            geometry.setWidth(max(minimum.width(), geometry.width() + delta.x()))
        if self.resize_edges & Qt.Edge.TopEdge:
            new_top = geometry.top() + delta.y()
            if geometry.bottom() - new_top + 1 >= minimum.height():
                geometry.setTop(new_top)
        if self.resize_edges & Qt.Edge.BottomEdge:
            geometry.setHeight(max(minimum.height(), geometry.height() + delta.y()))

        self.setGeometry(geometry)
        return True

    def eventFilter(self, obj, event):
        """Handle frameless resize edges and double-click on the tab bar."""
        if self.object_belongs_to_window(obj):
            if event.type() == QEvent.Type.MouseMove:
                if self.continue_window_resize(event.globalPosition()):
                    return True
                _edges, cursor = self.resize_hit_test(event.globalPosition())
                self.set_resize_cursor(cursor)
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if hasattr(self, "custom_title_bar"):
                    self.custom_title_bar.collapse_search_if_empty_from_global_pos(event.globalPosition())
                edges, _cursor = self.resize_hit_test(event.globalPosition())
                if edges is not None:
                    self.start_window_resize(edges, event.globalPosition())
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self.resize_edges = None
                self.resize_start_geometry = None
                self.resize_start_pos = None
            elif event.type() == QEvent.Type.Leave and self.resize_edges is None:
                self.set_resize_cursor(None)

        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj == self.tab_widget.tabBar():
                tab_index = self.tab_widget.tabBar().tabAt(event.pos())
                if tab_index >= 0 and self.settings_manager.get_setting("double_click_tab_closes_tab", True):
                    self.close_tab(tab_index)
                    return True
                if tab_index == -1 and self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True):
                    self.new_editor_tab()
                    return True
                return False
            if (
                obj == self.tab_widget
                and self.is_tab_strip_position(event.pos())
            ):
                if self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True):
                    self.new_editor_tab()
                    return True
                return False
        return super().eventFilter(obj, event)  # Let other events pass through

    def is_tab_strip_position(self, pos):
        """Return whether a QTabWidget-local position is in the top tab strip."""
        if hasattr(pos, "toPoint"):
            pos = pos.toPoint()
        tab_bar = self.tab_widget.tabBar()
        tab_bar_top = tab_bar.mapTo(self.tab_widget, tab_bar.rect().topLeft()).y()
        tab_bar_bottom = tab_bar_top + max(tab_bar.height(), 1)
        return tab_bar_top <= pos.y() <= tab_bar_bottom

    def open_file_dialog(self):
        """Open file from dialog"""
        self.open_file()

    def open_file(self, file_path=None):
        """Open a file immediately, reusing an empty untitled tab when possible."""
        if file_path is None:
            # Show file dialog if no path provided
            file_path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                _("Open File"),
                "",
                _("Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*.*)")
            )
            if not file_path:  # User cancelled
                return

        file_path = os.path.abspath(file_path)

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if getattr(tab, "current_file", None) and os.path.abspath(tab.current_file) == file_path:
                self.tab_widget.setCurrentIndex(index)
                tab.editor.setFocus()
                self.update_topbar_context()
                return True
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Could not open file: {error}").format(error=str(e)))
            return False

        editor_tab = self.reusable_empty_editor_tab()
        if editor_tab is None:
            editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
            editor_tab.set_main_window(self)
            self.tab_widget.addTab(editor_tab, self.build_themed_icon("snippets"), os.path.basename(file_path))
        else:
            current_index = self.tab_widget.indexOf(editor_tab)
            self.tab_widget.setTabText(current_index, os.path.basename(file_path))
            self.update_tab_icon(current_index)

        editor_tab.editor.setPlainText(content)
        editor_tab.current_file = file_path
        editor_tab.editor.document().setModified(False)
        if editor_tab.is_markdown_file(file_path):
            editor_tab.set_markdown_preview_visible(True)
        else:
            editor_tab.set_markdown_preview_visible(False)
        
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        self.update_topbar_context()
        return True

    def reusable_empty_editor_tab(self):
        """Return an untouched untitled editor tab that can be replaced by an opened file."""
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, EditorTab):
            return None
        if getattr(current_tab, "current_file", None):
            return None
        if current_tab.editor.toPlainText():
            return None
        if current_tab.editor.document().isModified():
            return None
        return current_tab

    # Add a new method to set up the find shortcut
    def setup_shortcuts(self):
        """Set up additional keyboard shortcuts"""
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)  # Typically Ctrl+F
        find_shortcut.activated.connect(self.toggle_find)
        markdown_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
        markdown_shortcut.activated.connect(self.toggle_markdown_preview)

    def handle_unsaved_changes(self):
        """Handle unsaved changes before closing"""
        unsaved_tabs = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if self.is_editor_tab_modified(tab):
                unsaved_tabs.append(i)
        
        if unsaved_tabs:
            reply = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("You have unsaved changes. Do you want to save them before closing?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                for i in unsaved_tabs:
                    self.tab_widget.setCurrentIndex(i)
                    if not self.tab_widget.widget(i).save_file():  # If save is cancelled
                        return False
                return True
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
            # If Discard, continue with close
        
        return True

def install_terminal_interrupt_handler(app):
    """Let Ctrl+C in a launching terminal stop the Qt event loop promptly."""
    def handle_sigint(_signum, _frame):
        app.quit()

    signal.signal(signal.SIGINT, handle_sigint)
    timer = QTimer(app)
    timer.timeout.connect(lambda: None)
    timer.start(100)
    app._sigint_timer = timer
    return timer


def main():
    # Enable high DPI scaling
    # Qt 6 enables high-DPI scaling by default.
    
    # Create application instance
    app = QApplication(sys.argv)
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    
    # Set application metadata
    app.setApplicationName("Jottr")
    app.setApplicationDisplayName("Jottr")
    app.setDesktopFileName("jottr")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationDomain("github.com/mfat/jottr")
    install_terminal_interrupt_handler(app)
    
    # Get file paths from command-line arguments
    file_paths = []
    if len(sys.argv) > 1:
        file_paths = [arg for arg in sys.argv[1:] if os.path.isfile(arg)]
    
    # Create main window
    window = TextEditorApp()
    window.show()
    
    # Open files from command line
    for file_path in file_paths:
        window.open_file(file_path)
    
    return app.exec()

if __name__ == "__main__":
    main() 
