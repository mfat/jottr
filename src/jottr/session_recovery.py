"""Swap files and the stash of new unsaved documents.

Swap files follow KTextEditor's Kate::SwapFile: while a file on disk has
unsaved edits, a copy of the buffer is kept in the swap directory together
with the checksum of the disk text it was based on. Saving, discarding or
closing the document removes it again, so finding one when the file is opened
means the previous run did not close properly.

The stash follows Kate's KateStashManager: when Jottr quits, untitled
documents with text are written to the stash directory instead of asking to
save them, and are popped back into tabs on the next start.
"""
import hashlib
import json
import os
import time

SWAP_FILE_SETTING = "swap_file_enabled"
STASH_NEW_FILES_SETTING = "restore_unsaved_new_files"

SWAP_FILE_VERSION = "Jottr Swap File 1"
SWAP_FILE_SUFFIX = ".jottr-swp"
STASH_FILE_VERSION = "Jottr Stash 1"
STASH_FILE_SUFFIX = ".json"


def text_checksum(text):
    return hashlib.sha1(text.encode("utf-8", "surrogatepass")).hexdigest()


def swap_directory(settings_manager):
    return os.path.join(settings_manager.config_dir, "swap")


def stash_directory(settings_manager):
    return os.path.join(settings_manager.config_dir, "stash")


def swap_file_path(settings_manager, file_path):
    """Swap file for *file_path*, named like Kate's preset swap directory."""
    full_path = os.path.abspath(file_path)
    # The hash of the full path keeps names unique without deep, long paths.
    digest = hashlib.sha1(full_path.encode("utf-8", "surrogatepass")).hexdigest()
    name = f"{digest}-{os.path.basename(full_path)}{SWAP_FILE_SUFFIX}"
    return os.path.join(swap_directory(settings_manager), name)


def _write_json_atomically(path, data):
    """Write owner-only JSON and sync it to disk before replacing *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        remove_file(temp_path)
        raise


def _read_json(path, version):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != version:
        return None
    if not isinstance(data.get("text"), str):
        return None
    return data


def remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        print(f"Could not remove {path}: {error}")


def write_swap_file(path, file_path, checksum, text):
    """Store *text* as the unsaved state of *file_path* (raises OSError)."""
    _write_json_atomically(path, {
        "version": SWAP_FILE_VERSION,
        "file": os.path.abspath(file_path),
        "checksum": checksum,
        "text": text,
    })


def read_swap_file(path):
    """Return the swap data at *path*, or None when missing or invalid."""
    return _read_json(path, SWAP_FILE_VERSION)


def stash_documents(settings_manager, documents):
    """Stash (title, text) pairs; return one path per document.

    The path is None where writing failed. Stashes left by another Jottr
    window that quit earlier are kept, so each stash gets its own file
    instead of one shared list.
    """
    directory = stash_directory(settings_manager)
    batch = time.time_ns()
    written = []
    for index, (title, text) in enumerate(documents):
        path = os.path.join(directory, f"{batch}-{index:04d}{STASH_FILE_SUFFIX}")
        try:
            _write_json_atomically(path, {
                "version": STASH_FILE_VERSION,
                "title": title,
                "text": text,
            })
        except OSError as error:
            print(f"Could not write to stash file {path}: {error}")
            path = None
        written.append(path)
    return written


def pop_stashed_documents(settings_manager):
    """Return stashed (title, text) pairs in stash order and remove them."""
    directory = stash_directory(settings_manager)
    try:
        names = sorted(
            name for name in os.listdir(directory)
            if name.endswith(STASH_FILE_SUFFIX)
        )
    except OSError:
        return []
    documents = []
    for name in names:
        path = os.path.join(directory, name)
        data = _read_json(path, STASH_FILE_VERSION)
        if data is None:
            # Leave unreadable stashes on disk rather than losing their text.
            continue
        title = data.get("title")
        documents.append((title if isinstance(title, str) else "", data["text"]))
        remove_file(path)
    return documents
