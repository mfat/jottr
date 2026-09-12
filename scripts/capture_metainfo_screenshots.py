#!/usr/bin/env python3
"""Capture AppStream/Flathub screenshots for Jottr metainfo."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="jottr-screenshots-"))
os.environ["XDG_CONFIG_HOME"] = str(_tmp / "config")
os.environ["XDG_DATA_HOME"] = str(_tmp / "data")
os.environ["XDG_CACHE_HOME"] = str(_tmp / "cache")
for name in ("config", "data", "cache"):
    (_tmp / name).mkdir()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtCore import QEventLoop, QTimer, QUrl, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from jottr.main import warmup_opengl
from jottr.qt_style import capture_platform_qt_style, register_bundled_qt_plugins
from jottr.window import TextEditorApp

OUT = ROOT / "screenshots"
WIDTH, HEIGHT = 1280, 800

SAMPLE_MD = """# Harbor Draft

The ferry horn cut through the fog just after dawn. Notebook open,
coffee cooling, and a list of questions that still needed answers.

## Notes from the pier

- Interview the harbor master before noon
- Check tide charts against last week's log
- Fact-check the ferry schedule quote

> Write first. Edit later.

When the mist lifted, the city returned in pieces — roofs, then
windows, then the low chatter of people starting their day.
"""

FOCUS_SAMPLE = """Focus Mode

A clean column for drafting without chrome.
Keep typing. The rest can wait.
"""

BROWSER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Research</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1.5rem;
           background: #f7f3ea; color: #3b2f2f; }
    h1 { font-size: 1.35rem; margin-top: 0; }
    p, li { line-height: 1.55; max-width: 34rem; }
  </style>
</head>
<body>
  <h1>Research</h1>
  <p>Look up selected text without leaving your draft. Use
     site-specific search from the context menu.</p>
  <ul>
    <li>Wire services</li>
    <li>Dictionaries</li>
    <li>Your own sites</li>
  </ul>
</body>
</html>
"""


def wait(app: QApplication, ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def grab(window: TextEditorApp, name: str, max_width: int | None = None) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    window.repaint()
    QApplication.processEvents()
    pix = window.grab()
    if max_width and pix.width() > max_width:
        pix = pix.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    if not pix.save(str(path), "PNG"):
        raise RuntimeError(f"Failed to save {path}")
    print(f"wrote {path} ({pix.width()}x{pix.height()})")
    return path


def current_tab(window: TextEditorApp):
    return window.tab_widget.currentWidget()


def set_editor_text(window: TextEditorApp, text: str) -> None:
    editor = window.get_current_editor()
    editor.setPlainText(text)
    tab = current_tab(window)
    if hasattr(tab, "document_modified"):
        tab.document_modified = False
    idx = window.tab_widget.currentIndex()
    title = window.tab_widget.tabText(idx).rstrip("*")
    window.tab_widget.setTabText(idx, title)


def ensure_snippets(tab) -> None:
    mgr = getattr(tab, "snippet_manager", None)
    if mgr is None:
        return
    samples = {
        "lede": "LEDE: ",
        "sb": "SOUNDBITE: ",
        "graf": "### ",
        "quote": "> ",
    }
    existing = set(mgr.get_snippets())
    for title, body in samples.items():
        if title not in existing:
            mgr.add_snippet(title, body)
    if hasattr(tab, "update_snippet_list"):
        tab.update_snippet_list()


def wait_animation(widget_host, widget, app: QApplication, timeout_ms: int = 800) -> None:
    anim = getattr(widget_host, "ui_animations", {}).get(widget)
    if anim is None:
        wait(app, 50)
        return
    loop = QEventLoop()
    anim.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    app.processEvents()


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    register_bundled_qt_plugins()
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    capture_platform_qt_style(app)
    app.setApplicationName("Jottr")
    app.setApplicationDisplayName("Jottr")

    window = TextEditorApp()
    # Instant pane show/hide for reliable grabs.
    window.settings_manager.save_setting("enable_animations", False)
    warmup_opengl(window)
    window.resize(WIDTH, HEIGHT)
    window.show()
    wait(app, 250)

    window.set_editor_theme("Sepia")
    editor = window.get_current_editor()
    if editor is not None:
        editor.setFont(QFont("DejaVu Sans Mono", 12))
    wait(app, 100)

    set_editor_text(window, SAMPLE_MD)
    wait(app, 150)
    grab(window, "main.png")

    tab = current_tab(window)

    # --- snippets ---
    ensure_snippets(tab)
    if not tab.snippet_widget.isVisible():
        tab.toggle_pane("snippets")
    wait_animation(tab, tab.snippet_widget, app)
    # Force a readable splitter layout: editor | snippets | browser
    sizes = tab.splitter.sizes()
    total = sum(sizes) or WIDTH
    tab.splitter.setSizes([int(total * 0.62), int(total * 0.38), 0])
    wait(app, 100)
    grab(window, "snippets.png")
    if tab.snippet_widget.isVisible():
        tab.toggle_pane("snippets")
    wait_animation(tab, tab.snippet_widget, app)

    # --- markdown preview ---
    tab.set_markdown_preview_visible(True)
    wait_animation(tab, tab.markdown_preview, app)
    if hasattr(tab, "markdown_splitter"):
        tab.markdown_splitter.setSizes([640, 640])
    # Wait for Chromium preview paint.
    wait(app, 1500)
    tab.update_markdown_preview()
    wait(app, 1200)
    grab(window, "markdown.png")
    tab.set_markdown_preview_visible(False)
    wait_animation(tab, tab.markdown_preview, app)

    # --- browser ---
    if tab.browser_panel_enabled():
        # Avoid a file:// URL in the chrome; load HTML directly after the pane opens.
        tab._pending_url = "about:blank"
        if not tab.browser_widget.isVisible():
            tab.toggle_pane("browser")
        wait_animation(tab, tab.browser_widget, app)
        sizes = tab.splitter.sizes()
        total = sum(sizes) or WIDTH
        tab.splitter.setSizes([int(total * 0.55), 0, int(total * 0.45)])
        wait(app, 800)
        if tab.web_view is not None:
            loop = QEventLoop()

            def on_load(_ok: bool) -> None:
                tab.url_bar.setText("https://www.apnews.com/")
                QTimer.singleShot(350, loop.quit)

            tab.web_view.loadFinished.connect(on_load)
            tab.web_view.setHtml(BROWSER_HTML, QUrl("https://www.apnews.com/"))
            QTimer.singleShot(3000, loop.quit)
            loop.exec()
        wait(app, 300)
        tab.url_bar.setText("https://www.apnews.com/")
        wait(app, 50)
        grab(window, "browser.png")
        if tab.browser_widget.isVisible():
            tab.toggle_pane("browser")
        wait_animation(tab, tab.browser_widget, app)

    # --- focus mode (fullscreen by design) ---
    set_editor_text(window, FOCUS_SAMPLE)
    wait(app, 100)
    window.toggle_focus_mode()
    wait(app, 500)
    # Focus Mode goes fullscreen; downscale for store-friendly dimensions.
    grab(window, "focus.png", max_width=WIDTH)
    window.toggle_focus_mode()
    wait(app, 300)

    window.close()
    app.quit()
    print(f"temp config at {_tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
