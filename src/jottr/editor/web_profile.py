"""Shared Qt WebEngine profiles for the browser pane and plugin web panels.

Browsing is off-the-record unless the user opts in to remembering cookies,
which Jottr then keeps in a disk-backed profile under its config directory.
Qt WebEngine never encrypts that cookie database (it disables Chromium's
os_crypt), so remembering stays opt-in.

Qt can clear cookies, the HTTP cache, and visited links at runtime, but not
local storage, IndexedDB, or other site data. A full wipe therefore removes
the profile's folders while no profile has them open: at exit, after the
profiles are released, and again at startup in case Jottr did not exit cleanly.
"""
import os
import shutil
import threading
import time
import uuid

REMEMBER_DATA_SETTING = "browser_remember_data"
WIPE_PENDING_SETTING = "browser_wipe_pending"

# Folders being deleted are renamed to "<name>.deleting-<id>" beside the original.
_DELETING_MARK = ".deleting-"
# Startup deletes in the background after this delay, so it never competes
# with loading the window. Exit waits at most this long for deletion.
_STARTUP_DELETE_DELAY_SECONDS = 5.0
_EXIT_DELETE_WAIT_SECONDS = 2.0

# Storage path (None for off-the-record) -> QWebEngineProfile. A storage path
# may back only one profile per process, so profiles are created once.
_profiles = {}
# Held while this process has the disk-backed profile, so another running
# Jottr does not wipe folders out from under it.
_profile_lock = None


def _profile(storage_path, cache_path=None):
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    from PyQt6.QtWidgets import QApplication

    profile = _profiles.get(storage_path)
    if profile is None:
        app = QApplication.instance()
        if storage_path is None:
            profile = QWebEngineProfile(app)
        else:
            # The constructor leaves an empty default storage directory behind.
            # QWebEngineProfileBuilder would avoid that, but PyQt6 cannot
            # instantiate it.
            profile = QWebEngineProfile("jottr", app)
            profile.setPersistentStoragePath(storage_path)
            profile.setCachePath(cache_path)
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
            )
        _profiles[storage_path] = profile
    return profile


def storage_path(settings_manager):
    return os.path.join(settings_manager.config_dir, "browser")


def cache_path():
    from PyQt6.QtCore import QStandardPaths

    cache_root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation
    )
    return os.path.join(cache_root, "browser")


def _lock_file(settings_manager):
    from PyQt6.QtCore import QLockFile

    lock = QLockFile(storage_path(settings_manager) + ".lock")
    # Held for a whole session: detect crashed holders by process, not age.
    lock.setStaleLockTime(0)
    return lock


def _persistent_profile(settings_manager):
    global _profile_lock

    path = storage_path(settings_manager)
    if path not in _profiles and _profile_lock is None:
        lock = _lock_file(settings_manager)
        if lock.tryLock(0):
            _profile_lock = lock
    return _profile(path, cache_path())


def browser_profile(settings_manager):
    """Profile new browser pages should use under the current settings."""
    if settings_manager.get_setting(REMEMBER_DATA_SETTING, False):
        return _persistent_profile(settings_manager)
    return _profile(None)


def new_browser_page(settings_manager, view):
    """A page on the current browser profile, owned by ``view``."""
    from PyQt6.QtWebEngineCore import QWebEnginePage

    return QWebEnginePage(browser_profile(settings_manager), view)


def clear_browsing_data(settings_manager, finished=None):
    """Delete cookies, cache, and visited links from every browser profile.

    Clearing is asynchronous; ``finished`` runs once every HTTP cache clear
    has completed (immediately on Qt before 6.7, which cannot report it).
    """
    from PyQt6.QtCore import Qt

    _persistent_profile(settings_manager)
    profiles = list(_profiles.values())
    remaining = [len(profiles)]

    def cache_cleared():
        remaining[0] -= 1
        if remaining[0] == 0 and finished is not None:
            finished()

    for profile in profiles:
        profile.cookieStore().deleteAllCookies()
        profile.clearAllVisitedLinks()
        completed = getattr(profile, "clearHttpCacheCompleted", None)
        if completed is not None:
            completed.connect(cache_cleared, Qt.ConnectionType.SingleShotConnection)
        profile.clearHttpCache()
        if completed is None:
            cache_cleared()


def request_wipe(settings_manager):
    """Delete all saved browsing data once no profile has it open."""
    settings_manager.save_setting(WIPE_PENDING_SETTING, True)


def _move_aside(path):
    """Rename ``path`` for deletion; True when nothing is left at ``path``."""
    try:
        os.rename(path, f"{path}{_DELETING_MARK}{uuid.uuid4().hex}")
    except FileNotFoundError:
        pass
    except OSError:
        return False
    return True


def _delete_moved_folders(folders, delay_seconds):
    """Delete folders moved aside by this or any earlier, interrupted wipe."""
    if delay_seconds:
        time.sleep(delay_seconds)
    for folder in folders:
        parent, name = os.path.split(folder)
        try:
            entries = os.listdir(parent)
        except OSError:
            continue
        for entry in entries:
            if entry.startswith(name + _DELETING_MARK):
                shutil.rmtree(os.path.join(parent, entry), ignore_errors=True)


def wipe_pending_data(settings_manager, at_exit=False):
    """Remove the saved browsing data folders if a wipe was requested.

    Never blocks on deletion: the folders are only renamed here, which is a
    single metadata update and frees their paths for a new profile. Their
    contents, and folders left by earlier interrupted wipes, are deleted in a
    background thread; at startup after a delay, at exit waiting a bounded
    time. Whatever remains is swept on the next launch.

    Keeps the wipe pending while this or another running Jottr has the
    disk-backed profile open. Returns whether the folders were moved aside.
    """
    folders = (storage_path(settings_manager), cache_path())
    moved = False
    if (settings_manager.get_setting(WIPE_PENDING_SETTING, False)
            and folders[0] not in _profiles):
        lock = _lock_file(settings_manager)
        if lock.tryLock(0):
            try:
                moved = all([_move_aside(folder) for folder in folders])
            finally:
                lock.unlock()
            if moved:
                settings_manager.save_setting(WIPE_PENDING_SETTING, False)

    delay = 0.0 if at_exit else _STARTUP_DELETE_DELAY_SECONDS
    deleter = threading.Thread(
        target=_delete_moved_folders, args=(folders, delay),
        name="jottr-browser-data-wipe", daemon=True,
    )
    deleter.start()
    if at_exit:
        deleter.join(_EXIT_DELETE_WAIT_SECONDS)
    return moved


def release_browser_profiles():
    """Delete the profiles so disk-backed data is flushed before exit.

    Call only after every page using them is gone.
    """
    from PyQt6 import sip

    global _profile_lock

    while _profiles:
        _path, profile = _profiles.popitem()
        if not sip.isdeleted(profile):
            sip.delete(profile)
    if _profile_lock is not None:
        _profile_lock.unlock()
        _profile_lock = None
