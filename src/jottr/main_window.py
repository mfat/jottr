from __future__ import annotations
import os
from typing import Optional, Iterator

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow,
    QAction,
    QFileDialog,
    QTabWidget,
    QToolBar,
    QMessageBox,
    QStyle,
)

from editor_tab import EditorTab
from rss_tab import RSSTab
from snippet_manager import SnippetManager
from settings_dialog import SettingsDialog
from settings_manager import SettingsManager


class MainWindow(QMainWindow):
    """Modernised application window with toolbar and tabbed editor."""

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.snippet_manager = SnippetManager(settings_manager)

        self.setWindowTitle("Jottr")
        self.resize(1024, 768)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)
        self.setCentralWidget(self.tab_widget)

        self._init_toolbar()
        self.statusBar().showMessage("Ready")

        self.new_editor_tab()

    # ------------------------------------------------------------------
    # toolbar
    def _init_toolbar(self) -> None:
        style = self.style()
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        new_action = QAction(style.standardIcon(QStyle.SP_FileIcon), "New", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_editor_tab)
        open_action = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_file_dialog)
        save_action = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_file)
        rss_action = QAction("RSS", self)
        rss_action.triggered.connect(self.new_rss_tab)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)

        toolbar.addActions([new_action, open_action, save_action, rss_action, settings_action])

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([new_action, open_action, save_action])
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit", self.close)
        exit_action.setShortcut(QKeySequence.Quit)

        tools_menu = self.menuBar().addMenu("&Tools")
        tools_menu.addAction(settings_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(rss_action)

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
    def new_editor_tab(self) -> EditorTab:
        tab = EditorTab(self.snippet_manager, self.settings_manager)
        tab.set_main_window(self)
        index = self.tab_widget.addTab(tab, "Untitled")
        self.tab_widget.setCurrentIndex(index)
        tab.editor.setFocus()
        return tab

    def new_rss_tab(self) -> None:
        tab = RSSTab()
        index = self.tab_widget.addTab(tab, "RSS Reader")
        self.tab_widget.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # file operations
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
