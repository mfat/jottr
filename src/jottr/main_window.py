from __future__ import annotations
import os
from typing import Optional, Iterator

from PyQt5.QtCore import QUrl, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import (
    QMainWindow,
    QAction,
    QFileDialog,
    QTabWidget,
    QWidget,
    QMessageBox,
    QStyle,
    QVBoxLayout,
)

from editor_tab import EditorTab
from rss_tab import RSSTab
from snippet_manager import SnippetManager
from settings_dialog import SettingsDialog
from settings_manager import SettingsManager
from ui_theme_manager import UIThemeManager


class MainWindow(QMainWindow):
    """Modern, cross-platform window using a QML toolbar and tabbed editor."""

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.snippet_manager = SnippetManager(settings_manager)

        self.setWindowTitle("Jottr")
        self.resize(1024, 768)

        self._create_actions()

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar_qml = os.path.join(os.path.dirname(__file__), "toolbar.qml")
        self.toolbar = QQuickWidget()
        self.toolbar.setResizeMode(QQuickWidget.SizeRootObjectToView)
        ctx = self.toolbar.rootContext()
        ctx.setContextProperty("mainWindow", self)
        self.toolbar.setSource(QUrl.fromLocalFile(toolbar_qml))

        layout.addWidget(self.toolbar)
        layout.addWidget(self.tab_widget)
        self.setCentralWidget(central)

        self._init_menu()
        self.statusBar().showMessage("Ready")

        self.new_editor_tab()

    # ------------------------------------------------------------------
    # setup helpers
    def _create_actions(self) -> None:
        style = self.style()
        self.new_action = QAction(style.standardIcon(QStyle.SP_FileIcon), "New", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_editor_tab)

        self.open_action = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Open", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_file_dialog)

        self.save_action = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_file)

        self.rss_action = QAction("RSS", self)
        self.rss_action.triggered.connect(self.new_rss_tab)

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.show_settings)

    def _init_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([self.new_action, self.open_action, self.save_action])
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit", self.close)
        exit_action.setShortcut(QKeySequence.Quit)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.rss_action)
        theme_menu = view_menu.addMenu("Theme")
        current_theme = self.settings_manager.get_ui_theme()
        for name in UIThemeManager.available_themes():
            act = theme_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name.lower() == current_theme)
            act.triggered.connect(
                lambda checked, n=name.lower(): self.settings_manager.apply_ui_theme(n)
            )

        tools_menu = self.menuBar().addMenu("&Tools")
        tools_menu.addAction(self.settings_action)

    # ------------------------------------------------------------------
    # helpers
    def current_editor_tab(self) -> Optional[EditorTab]:
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, EditorTab) else None

    def iter_editor_tabs(self) -> Iterator[EditorTab]:
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, EditorTab):
                yield widget

    # ------------------------------------------------------------------
    # tab management
    @pyqtSlot()
    def new_editor_tab(self) -> EditorTab:
        tab = EditorTab(self.snippet_manager, self.settings_manager)
        tab.set_main_window(self)
        index = self.tab_widget.addTab(tab, "Untitled")
        self.tab_widget.setCurrentIndex(index)
        tab.editor.setFocus()
        return tab

    @pyqtSlot()
    def new_rss_tab(self) -> None:
        tab = RSSTab()
        index = self.tab_widget.addTab(tab, "RSS Reader")
        self.tab_widget.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # file operations
    @pyqtSlot()
    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.open_file_path(path)

    def open_file_path(self, path: str) -> None:
        # Do not open same file twice
        for tab in self.iter_editor_tabs():
            if tab.current_file == path:
                QMessageBox.information(self, "Already Open", f"{os.path.basename(path)} is already open")
                return

        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except Exception as exc:  # pragma: no cover - GUI warning
            QMessageBox.warning(self, "Open failed", str(exc))
            return

        tab = self.new_editor_tab()
        tab.editor.setPlainText(content)
        tab.current_file = path
        self.tab_widget.setTabText(self.tab_widget.indexOf(tab), os.path.basename(path))

    @pyqtSlot()
    def save_file(self) -> None:
        tab = self.current_editor_tab()
        if not tab:
            return
        if tab.current_file:
            tab.save_file()
            self.statusBar().showMessage("Saved", 2000)
        else:
            self.save_file_as()

    def save_file_as(self) -> None:
        tab = self.current_editor_tab()
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "Text Files (*.txt);;All Files (*)")
        if path:
            tab.current_file = path
            tab.save_file()
            self.tab_widget.setTabText(self.tab_widget.indexOf(tab), os.path.basename(path))
            self.statusBar().showMessage("Saved", 2000)

    # ------------------------------------------------------------------
    @pyqtSlot()
    def show_settings(self) -> None:
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec_():
            # persist theme choice
            theme = dialog.theme_combo.currentText().lower()
            self.settings_manager.apply_ui_theme(theme)

            # homepage, search sites, etc.
            self.settings_manager.save_setting("homepage", dialog.homepage_edit.text())
            sites = {}
            for i in range(dialog.search_list.count()):
                name, site = dialog.search_list.item(i).text().split(": ", 1)
                sites[name] = site
            self.settings_manager.save_setting("search_sites", sites)

            words = [dialog.dict_list.item(i).text() for i in range(dialog.dict_list.count())]
            self.settings_manager.save_setting("user_dictionary", words)

            self.statusBar().showMessage("Settings saved", 2000)

    # ------------------------------------------------------------------
    # slots exposed to QML
    @pyqtSlot(str)
    def set_theme(self, name: str) -> None:
        """Switch the UI theme."""
        self.settings_manager.apply_ui_theme(name.lower())
