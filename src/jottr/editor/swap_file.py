"""Swap file backup and crash recovery for an editor tab (Kate::SwapFile)."""
import difflib
import os

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QFontDatabase, QTextCursor
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from jottr.session_recovery import (
    SWAP_FILE_SETTING,
    read_swap_file,
    remove_file,
    swap_file_path,
    text_checksum,
    write_swap_file,
)
from jottr.translation_manager import _

# Kate appends every edit to its swap file right away; a full copy is written
# instead, at most this often while typing.
SWAP_SYNC_INTERVAL_MS = 3000


class SwapFileMixin:
    """Keeps a swap file for the tab's file while it has unsaved changes.

    Expects EditorTab: editor, current_file, settings_manager.
    """

    def setup_swap_file(self):
        # Swap file this tab owns on disk, if any.
        self.swap_file = None
        # Checksum of the text last loaded from or saved to current_file.
        self.disk_checksum = None
        # Swap data found on load, while the recovery bar waits for a choice.
        self.swap_recovery = None

        self.swap_timer = QTimer(self)
        self.swap_timer.setSingleShot(True)
        self.swap_timer.setInterval(SWAP_SYNC_INTERVAL_MS)
        self.swap_timer.timeout.connect(self.write_swap_file)
        self.editor.textChanged.connect(self.schedule_swap_write)
        self.editor.document().modificationChanged.connect(
            self._on_swap_modification_changed
        )
        self.setup_swap_file_bar()

    def setup_swap_file_bar(self):
        self.swap_file_bar = QWidget(self)
        self.swap_file_bar.setObjectName("swapFileBar")
        self.swap_file_bar.setVisible(False)
        self.swap_file_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        bar_layout = QHBoxLayout(self.swap_file_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.setSpacing(6)
        self.swap_file_label = QLabel(_("The file was not closed properly."))
        self.swap_file_label.setObjectName("swapFileLabel")
        self.swap_file_label.setWordWrap(True)
        bar_layout.addWidget(self.swap_file_label, 1)
        self.swap_diff_button = QPushButton(_("View Changes"))
        self.swap_diff_button.clicked.connect(self.show_swap_diff)
        bar_layout.addWidget(self.swap_diff_button)
        self.swap_recover_button = QPushButton(_("Recover Data"))
        self.swap_recover_button.clicked.connect(self.recover_swap_file)
        bar_layout.addWidget(self.swap_recover_button)
        self.swap_discard_button = QPushButton(_("Discard"))
        self.swap_discard_button.clicked.connect(self.discard_swap_file)
        bar_layout.addWidget(self.swap_discard_button)
        self.layout().insertWidget(0, self.swap_file_bar)

    def swap_file_enabled(self):
        return bool(self.settings_manager.get_setting(SWAP_FILE_SETTING, True))

    def schedule_swap_write(self):
        if self.swap_recovery is not None or not self.current_file:
            return
        if not self.swap_file_enabled() or not self.editor.document().isModified():
            return
        # Not restarted on each edit, so continuous typing still gets backed up.
        if not self.swap_timer.isActive():
            self.swap_timer.start()

    def write_swap_file(self):
        """Write the unsaved text of current_file to its swap file now."""
        self.swap_timer.stop()
        if self.swap_recovery is not None or not self.current_file:
            return False
        if not self.swap_file_enabled() or not self.editor.document().isModified():
            return False
        path = swap_file_path(self.settings_manager, self.current_file)
        if self.swap_file and self.swap_file != path:
            # The file was renamed or saved under another name.
            self.remove_swap_file()
        if self.disk_checksum is None:
            self.disk_checksum = self._checksum_on_disk()
        try:
            write_swap_file(
                path, self.current_file, self.disk_checksum, self.editor.toPlainText()
            )
        except OSError as error:
            print(f"Could not write swap file {path}: {error}")
            return False
        self.swap_file = path
        return True

    def _checksum_on_disk(self):
        try:
            with open(self.current_file, "r", encoding="utf-8") as handle:
                return text_checksum(handle.read())
        except (OSError, ValueError):
            return None

    def remove_swap_file(self):
        self.swap_timer.stop()
        if self.swap_file:
            remove_file(self.swap_file)
            self.swap_file = None

    def release_swap_file(self):
        """The document is closing: drop its swap file.

        A swap file still waiting for Recover or Discard is kept, so the offer
        comes back the next time the file is opened.
        """
        self.swap_timer.stop()
        if self.swap_recovery is None:
            self.remove_swap_file()

    def apply_swap_file_setting(self):
        if self.swap_recovery is not None:
            return
        if self.swap_file_enabled():
            self.schedule_swap_write()
        else:
            self.remove_swap_file()

    def mark_swap_file_saved(self, text):
        """current_file now holds *text* on disk."""
        self.disk_checksum = text_checksum(text)

    def _on_swap_modification_changed(self, modified):
        if not modified and self.swap_recovery is None:
            self.remove_swap_file()

    def load_swap_file(self, text):
        """current_file was just loaded with *text*: offer a left-over swap file.

        Returns True when the recovery bar is shown. A swap file based on other
        disk contents than *text* cannot be applied and is removed, like Kate.
        """
        self.swap_timer.stop()
        self._close_swap_recovery()
        self.swap_file = None
        self.mark_swap_file_saved(text)
        if not self.current_file:
            return False
        path = swap_file_path(self.settings_manager, self.current_file)
        if not os.path.exists(path):
            return False
        data = read_swap_file(path)
        if (
            data is None
            or data.get("checksum") != self.disk_checksum
            or data["text"] == text
        ):
            remove_file(path)
            return False
        self.swap_file = path
        self.swap_recovery = data
        # Edits before a choice would be overwritten by recovery; Kate does the same.
        self.editor.setReadOnly(True)
        self.swap_file_bar.setVisible(True)
        return True

    def _close_swap_recovery(self):
        self.swap_recovery = None
        self.editor.setReadOnly(False)
        self.swap_file_bar.setVisible(False)

    def recover_swap_file(self):
        """Replace the loaded text with the swap file's unsaved text."""
        data = self.swap_recovery
        if data is None:
            return False
        self._close_swap_recovery()
        # One undoable edit, so the recovered changes can be undone.
        cursor = QTextCursor(self.editor.document())
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(data["text"])
        cursor.endEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        return True

    def discard_swap_file(self):
        if self.swap_recovery is None:
            return
        self._close_swap_recovery()
        self.remove_swap_file()
        self.editor.setFocus()

    def swap_file_diff(self):
        """Unified diff from the file on disk to the swap file's text."""
        data = self.swap_recovery
        if data is None:
            return ""
        name = os.path.basename(self.current_file or "")
        return "".join(difflib.unified_diff(
            self.editor.toPlainText().splitlines(keepends=True),
            data["text"].splitlines(keepends=True),
            fromfile=name,
            tofile=_("{name} (recovered)").format(name=name),
        ))

    def show_swap_diff(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("View Changes"))
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setFont(QFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)))
        view.setPlainText(self.swap_file_diff())
        layout.addWidget(view)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close_button = QPushButton(_("Close"))
        close_button.clicked.connect(dialog.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        dialog.exec()
        dialog.deleteLater()
