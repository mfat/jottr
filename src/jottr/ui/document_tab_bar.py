"""Document tab bar with in-place title editing, drawn by the widget style."""
from PyQt6.QtWidgets import QLineEdit, QTabBar, QTabWidget, QToolTip
from PyQt6.QtCore import Qt, QEvent, QPoint, QSize, pyqtSignal


class TabTitleEditor(QLineEdit):
    """Line edit shown over a tab label while the tab is renamed."""

    cancelled = pyqtSignal()

    def event(self, event):
        # Take Escape before window shortcuts (such as leaving focus mode) do.
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and event.key() == Qt.Key.Key_Escape
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.cancelled.emit()


class LeftAlignedDocumentTabBar(QTabBar):
    """Document tab bar whose tab titles can be edited in place."""

    tabs_changed = pyqtSignal()

    label_left_padding = 8
    label_right_padding = 30
    title_editor_min_width = 120
    # Extra vertical room without QSS colors — style still paints the tab.
    tab_height_extra = 6
    min_tab_height = 36

    title_editor = None
    _committing_title = False

    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        if hint.isValid():
            return QSize(
                hint.width(),
                max(hint.height() + self.tab_height_extra, self.min_tab_height),
            )
        return hint

    def minimumTabSizeHint(self, index):
        hint = super().minimumTabSizeHint(index)
        if hint.isValid():
            return QSize(
                hint.width(),
                max(hint.height() + self.tab_height_extra, self.min_tab_height),
            )
        return hint

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tab positions change under an open title editor.
        self.tabMoved.connect(self.finish_title_edit)
        self.tabs_changed.connect(self.finish_title_edit)

    def edit_tab_title(self, index, text, commit, select_length=None):
        """Edit the title of tab *index* in place, starting from *text*.

        Enter passes the text to *commit*, which returns an error message to
        keep editing, or None when done. Escape, clicking elsewhere, and tabs
        being added, closed or moved cancel the edit.
        """
        self.finish_title_edit()
        rect = self.label_contents_rect(self.tabRect(index))
        rect.setWidth(max(rect.width(), self.title_editor_min_width))
        editor = TabTitleEditor(text, self)
        editor.setGeometry(rect)
        editor.setSelection(0, len(text) if select_length is None else select_length)
        editor.returnPressed.connect(lambda: self._commit_title_edit(editor, commit))
        editor.cancelled.connect(self.finish_title_edit)
        self.title_editor = editor
        editor.show()
        editor.setFocus()
        return editor

    def _commit_title_edit(self, editor, commit):
        if editor is not self.title_editor:
            return
        self._committing_title = True
        try:
            error = commit(editor.text())
        finally:
            self._committing_title = False
        if editor is not self.title_editor:
            return
        if error:
            editor.setFocus()
            QToolTip.showText(editor.mapToGlobal(QPoint(0, editor.height())), error, editor)
            return
        self.finish_title_edit()

    def finish_title_edit(self, *_args):
        """Close the title editor without renaming, if one is open."""
        editor = self.title_editor
        if editor is None or self._committing_title:
            return
        self.title_editor = None
        QToolTip.hideText()
        editor.hide()
        editor.deleteLater()

    def tabInserted(self, index):
        super().tabInserted(index)
        self.tabs_changed.emit()

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self.tabs_changed.emit()

    def label_contents_rect(self, tab_rect):
        """Where a tab's title sits, clear of its icon and close button."""
        return tab_rect.adjusted(self.label_left_padding, 0, -self.label_right_padding, 0)


class DocumentTabWidget(QTabWidget):
    """QTabWidget for documents, with in-place tab renaming."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(LeftAlignedDocumentTabBar())
        self.setDocumentMode(True)
