"""Tests for portal-aware file dialog helpers."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from jottr import file_dialogs


class FileDialogTests(unittest.TestCase):
    def test_helpers_use_native_qfiledialog_statics(self):
        with patch.object(
            file_dialogs.QFileDialog, "getOpenFileName", return_value=("/tmp/a.md", "")
        ) as open_dialog, patch.object(
            file_dialogs.QFileDialog, "getSaveFileName", return_value=("/tmp/b.md", "")
        ) as save_dialog, patch.object(
            file_dialogs.QFileDialog, "getExistingDirectory", return_value="/tmp"
        ) as dir_dialog:
            self.assertEqual(
                file_dialogs.get_open_file_name(None, "Open", "/home", "Text (*.txt)", "Text (*.txt)"),
                ("/tmp/a.md", ""),
            )
            self.assertEqual(
                file_dialogs.get_save_file_name(None, "Save", "/home", "Text (*.txt)"),
                ("/tmp/b.md", ""),
            )
            self.assertEqual(
                file_dialogs.get_existing_directory(None, "Folder", "/home"),
                "/tmp",
            )

        open_dialog.assert_called_once()
        save_dialog.assert_called_once()
        dir_dialog.assert_called_once()
        for call in (open_dialog, save_dialog, dir_dialog):
            options = call.call_args.kwargs.get("options")
            self.assertIsNone(options)

    def test_source_never_forces_non_native_dialogs(self):
        src_root = PROJECT_ROOT / "src" / "jottr"
        offenders = []
        for path in src_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "DontUseNativeDialog" in text and path.name != "file_dialogs.py":
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual(offenders, [])

    def test_flatpak_relies_on_portal_not_host_filesystem(self):
        flatpak = (PROJECT_ROOT / "io.github.mfat.jottr.yml").read_text(encoding="utf-8")
        self.assertIn("org.freedesktop.portal.FileChooser", flatpak)
        self.assertNotIn("--filesystem=home", flatpak)
        self.assertNotIn("--filesystem=host", flatpak)


if __name__ == "__main__":
    unittest.main()
