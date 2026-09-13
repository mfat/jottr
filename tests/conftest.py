"""Shared pytest setup for the Qt test suite."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _delete_windows_left_by_test():
    """Destroy the windows and dialogs a test created.

    Nothing runs an event loop between tests, so windows released with
    deleteLater() (or not released at all) pile up across the suite. Every
    later restyle then repolishes all of them, each test runs slower than the
    last, and stale windows react to other tests' theme changes.
    """
    yield
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow

    app = QApplication.instance()
    if app is None:
        return
    # Deleting whole main windows under a live chrome stylesheet (after a
    # widget style swap) leaves the stylesheet style with dangling entries,
    # and the next setStyleSheet crashes. Tests re-apply their own chrome.
    app.setStyleSheet("")
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, (QMainWindow, QDialog)):
            widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
