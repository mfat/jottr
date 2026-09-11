"""Shared UI widgets for the main window."""

from jottr.ui.document_tab_bar import LeftAlignedDocumentTabBar
from jottr.ui.workspace import WorkspaceFileSystemModel, WorkspaceTreeView
from jottr.ui.workspace_controller import WorkspaceControllerMixin

__all__ = [
    "LeftAlignedDocumentTabBar",
    "WorkspaceControllerMixin",
    "WorkspaceFileSystemModel",
    "WorkspaceTreeView",
]
