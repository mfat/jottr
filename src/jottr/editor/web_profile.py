"""Shared Qt WebEngine profiles for the browser pane and plugin web panels.

Browsing is off-the-record unless the user opts in to remembering cookies,
which Jottr then keeps in a disk-backed profile under its config directory.
Qt WebEngine never encrypts that cookie database (it disables Chromium's
os_crypt), so remembering stays opt-in.
"""
import os

REMEMBER_DATA_SETTING = "browser_remember_data"

# Storage path (None for off-the-record) -> QWebEngineProfile. A storage path
# may back only one profile per process, so profiles are created once.
_profiles = {}


def _profile(storage_path):
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    from PyQt6.QtWidgets import QApplication

    profile = _profiles.get(storage_path)
    if profile is None:
        app = QApplication.instance()
        if storage_path is None:
            profile = QWebEngineProfile(app)
        else:
            profile = QWebEngineProfile("jottr", app)
            profile.setPersistentStoragePath(storage_path)
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
            )
        _profiles[storage_path] = profile
    return profile


def storage_path(settings_manager):
    return os.path.join(settings_manager.config_dir, "browser")


def browser_profile(settings_manager):
    """Profile new browser pages should use under the current settings."""
    if settings_manager.get_setting(REMEMBER_DATA_SETTING, False):
        return _profile(storage_path(settings_manager))
    return _profile(None)


def new_browser_page(settings_manager, view):
    """A page on the current browser profile, owned by ``view``."""
    from PyQt6.QtWebEngineCore import QWebEnginePage

    return QWebEnginePage(browser_profile(settings_manager), view)


def clear_browsing_data(settings_manager):
    """Delete cookies, cache, and visited links from every browser profile."""
    _profile(storage_path(settings_manager))
    for profile in _profiles.values():
        profile.cookieStore().deleteAllCookies()
        profile.clearHttpCache()
        profile.clearAllVisitedLinks()


def release_browser_profiles():
    """Delete the profiles so disk-backed data is flushed before exit.

    Call only after every page using them is gone.
    """
    from PyQt6 import sip

    while _profiles:
        _path, profile = _profiles.popitem()
        if not sip.isdeleted(profile):
            sip.delete(profile)
