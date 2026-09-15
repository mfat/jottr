"""Tests for showing files in the desktop file manager."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PyQt6.QtCore import QUrl
from PyQt6.QtDBus import QDBusUnixFileDescriptor
from PyQt6.QtWidgets import QApplication

from jottr import file_manager


class ShowInFileManagerTests(unittest.TestCase):
    def setUp(self):
        QApplication.instance() or QApplication(["jottr-tests"])
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.pdf = Path(temp_dir.name) / "Shopping list.pdf"
        self.pdf.write_bytes(b"%PDF")
        self.calls = []

    def session_bus(self, *answers):
        """Record D-Bus calls, answering each with the next of *answers*."""
        answers = list(answers)

        def call(_service, _path, interface, method, arguments):
            self.calls.append((interface, method, arguments))
            return answers.pop(0)

        return patch.object(file_manager, "_call_session_bus", side_effect=call)

    def test_linux_asks_the_portal_to_show_the_file(self):
        with self.session_bus(True), patch.object(
            file_manager.QDesktopServices, "openUrl"
        ) as open_url:
            self.assertTrue(file_manager.show_in_file_manager(str(self.pdf), "linux"))

        ((interface, method, arguments),) = self.calls
        self.assertEqual((interface, method), ("org.freedesktop.portal.OpenURI", "OpenDirectory"))
        self.assertEqual(arguments[0], "")
        self.assertIsInstance(arguments[1], QDBusUnixFileDescriptor)
        self.assertEqual(arguments[2], {})
        open_url.assert_not_called()

    def test_linux_falls_back_to_the_file_manager_then_the_folder(self):
        with self.session_bus(False, True), patch.object(
            file_manager.QDesktopServices, "openUrl"
        ) as open_url:
            self.assertTrue(file_manager.show_in_file_manager(str(self.pdf), "linux"))
        self.assertEqual(
            self.calls[1],
            (
                "org.freedesktop.FileManager1",
                "ShowItems",
                [[QUrl.fromLocalFile(str(self.pdf)).toString()], ""],
            ),
        )
        open_url.assert_not_called()

        with self.session_bus(False, False), patch.object(
            file_manager.QDesktopServices, "openUrl", return_value=True
        ) as open_url:
            self.assertTrue(file_manager.show_in_file_manager(str(self.pdf), "linux"))
        open_url.assert_called_once_with(QUrl.fromLocalFile(str(self.pdf.parent)))

    def test_windows_and_macos_select_the_file(self):
        with self.session_bus(), patch.object(
            file_manager, "_start_detached", return_value=True
        ) as start:
            self.assertTrue(file_manager.show_in_file_manager(str(self.pdf), "win32"))
            self.assertTrue(file_manager.show_in_file_manager(str(self.pdf), "darwin"))
        self.assertEqual(
            [call.args for call in start.call_args_list],
            [
                ("explorer", ["/select,", os.path.normpath(str(self.pdf))]),
                ("open", ["-R", str(self.pdf)]),
            ],
        )
        self.assertEqual(self.calls, [])

    def test_missing_files_are_not_shown(self):
        with self.session_bus(), patch.object(
            file_manager.QDesktopServices, "openUrl"
        ) as open_url:
            self.assertFalse(
                file_manager.show_in_file_manager(str(self.pdf.with_name("gone.pdf")), "linux")
            )
        open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
