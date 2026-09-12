"""Compatibility shim: the dialog now lives in jottr.settings (one module per tab)."""
from jottr.settings import SettingsDialog, SearchSiteDialog

__all__ = ["SettingsDialog", "SearchSiteDialog"]
