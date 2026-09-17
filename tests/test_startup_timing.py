"""Startup timing regression guard (offscreen).

Runs in a subprocess so a deferred-startup QApplication cannot leave
stylesheet/widget state that later tests trip over.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Generous ceiling so CI load spikes do not flake; local cold starts are ~300–700ms.
_STARTUP_BUDGET_MS = 1500
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"

_WORKER = r"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["JOTTR_DEFER_STARTUP"] = "1"
os.environ.pop("JOTTR_SYNC_STARTUP", None)
sys.path.insert(0, {src!r})

t0 = time.perf_counter()
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from jottr.file_dialogs import use_portal_file_dialogs
from jottr.qt_style import capture_platform_qt_style, register_bundled_qt_plugins
from jottr.window import TextEditorApp

register_bundled_qt_plugins()
use_portal_file_dialogs()
app = QApplication([])
app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
capture_platform_qt_style(app)

window = TextEditorApp()
assert window._startup_content_pending
assert window.tab_widget.count() == 0
window.show()
app.processEvents()
elapsed_ms = (time.perf_counter() - t0) * 1000
assert not window._startup_content_pending
assert window.tab_widget.count() >= 1
assert any(not action.icon().isNull() for action, _ in window.icon_actions)
print(f"elapsed_ms={{elapsed_ms:.1f}}")
window.close()
app.quit()
""".format(src=str(_SRC_ROOT))


def test_cold_startup_under_budget():
    """Import + window shell + first paint stay under a hard ceiling."""
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(_SRC_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", _WORKER],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"startup worker failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    elapsed_line = [line for line in result.stdout.splitlines() if line.startswith("elapsed_ms=")]
    assert elapsed_line, result.stdout
    elapsed_ms = float(elapsed_line[-1].split("=", 1)[1])
    assert elapsed_ms < _STARTUP_BUDGET_MS, (
        f"startup to first paint took {elapsed_ms:.0f}ms "
        f"(budget {_STARTUP_BUDGET_MS}ms)"
    )
