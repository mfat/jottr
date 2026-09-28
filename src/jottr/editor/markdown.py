"""Markdown preview rendering and scroll sync for EditorTab."""
import base64
import html
import importlib.util
import json
import mimetypes
import os
import re
import secrets
import tempfile
import time

from PyQt6.QtCore import QTimer, QUrl, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont

from jottr.bundled_fonts import bundled_font_face_css

# Qt WebEngine and python-markdown are slow to import and only needed once a
# preview renders, so both load on first use instead of at startup.
MARKDOWN_LIB_AVAILABLE = importlib.util.find_spec("markdown") is not None
_markdown_preview_page_class = None


def markdown_preview_page_class():
    """Return the preview page class, importing Qt WebEngine on first use."""
    global _markdown_preview_page_class
    if _markdown_preview_page_class is None:
        from PyQt6.QtWebEngineCore import QWebEnginePage

        class MarkdownPreviewPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line_number, source_id):
                print(f"Markdown preview JS: {message} ({source_id}:{line_number})")

            def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
                if not is_main_frame:
                    return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
                action = markdown_preview_navigation(url, self.url(), navigation_type)
                if action == "open":
                    from PyQt6.QtGui import QDesktopServices

                    QDesktopServices.openUrl(url)
                return action == "load"

        _markdown_preview_page_class = MarkdownPreviewPage
    return _markdown_preview_page_class


def markdown_preview_navigation(url, current_url, navigation_type):
    """What the preview does with a navigation: "load", "open", or "block".

    Like the page in Qt's Markdown Editor example, the preview only shows
    what Jottr loads into it; followed links open outside. History and
    reloads are blocked too, because the page on disk is only as new as the
    last full load, not the render swapped into it since.
    """
    from PyQt6.QtWebEngineCore import QWebEnginePage

    NavigationType = QWebEnginePage.NavigationType
    if navigation_type == NavigationType.NavigationTypeTyped:
        return "load"
    if navigation_type != NavigationType.NavigationTypeLinkClicked:
        return "block"
    remove_fragment = QUrl.UrlFormattingOption.RemoveFragment
    if url.hasFragment() and url.adjusted(remove_fragment) == current_url.adjusted(remove_fragment):
        return "load"
    return "open"


# Context menu entries worth keeping: the rest navigate, reload, or save a
# page that is not the document.
MARKDOWN_PREVIEW_MENU_ACTIONS = (
    "Copy",
    "SelectAll",
    "CopyLinkToClipboard",
    "CopyImageToClipboard",
    "CopyImageUrlToClipboard",
)


def __getattr__(name):
    if name == "MarkdownPreviewPage":
        return markdown_preview_page_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class MarkdownPreviewMixin:
    # How long the pane takes to slide open. A page rendered for an opening
    # pane holds its fade for this long, so text appears once the pane has
    # settled rather than sliding around while it moves.
    markdown_preview_reveal_duration_ms = 260
    # The page is loaded once and then updated in place, like Qt's Markdown
    # Editor example: only a change to its shell (styles, fonts, base folder,
    # plugin output) loads it again. These track the shell requested, the
    # shell actually showing, and the rendered document inside it.
    requested_preview_shell_signature = None
    loaded_preview_shell_signature = None
    rendered_preview_body_html = None

    def ensure_markdown_preview(self):
        """Create the Chromium markdown preview on first use."""
        if getattr(self, "_markdown_preview_ready", False):
            return self.markdown_preview

        import jottr.editor.tab as tab_mod
        from PyQt6.QtWebEngineCore import QWebEngineSettings

        # Prefer symbols on editor.tab so tests can patch without importing WebEngine.
        ViewCls = tab_mod.QWebEngineView
        if ViewCls is None:
            from PyQt6.QtWebEngineWidgets import QWebEngineView as ViewCls
            tab_mod.QWebEngineView = ViewCls
        PageCls = tab_mod.MarkdownPreviewPage
        if PageCls is None:
            PageCls = markdown_preview_page_class()
            tab_mod.MarkdownPreviewPage = PageCls

        placeholder = getattr(self, "markdown_preview", None)
        container = getattr(self, "markdown_preview_container", None)
        was_visible = bool(placeholder is not None and placeholder.isVisible())
        sizes = None
        if hasattr(self, "markdown_splitter"):
            sizes = self.markdown_splitter.sizes()

        view = ViewCls()
        view.setObjectName("markdownPreview")
        if hasattr(view, "setPage"):
            view.setPage(PageCls(view))
        if hasattr(view, "settings"):
            preview_settings = view.settings()
            preview_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            preview_settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
            )
            preview_settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
            )
        # Paint the page background before the first document arrives so the
        # pane never flashes an empty frame as it opens.
        page = view.page() if hasattr(view, "page") else None
        if page is not None and hasattr(page, "setBackgroundColor"):
            page.setBackgroundColor(QColor("#ffffff"))
        view.installEventFilter(self)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self.show_markdown_preview_context_menu)
        if hasattr(view, "loadFinished"):
            view.loadFinished.connect(self.markdown_preview_load_finished)

        if container is not None and placeholder is not None:
            container.layout().replaceWidget(placeholder, view)
            placeholder.setParent(None)
            placeholder.deleteLater()
            if sizes:
                self.markdown_splitter.setSizes(sizes)
        elif hasattr(self, "markdown_splitter") and placeholder is not None:
            index = self.markdown_splitter.indexOf(placeholder)
            if index < 0:
                index = self.markdown_splitter.count()
            self.markdown_splitter.insertWidget(index, view)
            placeholder.setParent(None)
            placeholder.deleteLater()
            if sizes:
                self.markdown_splitter.setSizes(sizes)
        self.markdown_preview = view
        self._markdown_preview_ready = True
        # Inside the clip container the container carries visibility, so the
        # view itself stays shown and simply gets clipped away.
        view.setVisible(True if container is not None else was_visible)
        if hasattr(self, "apply_language_direction"):
            self.apply_language_direction()
        return view

    def show_markdown_preview_context_menu(self, pos):
        """Chromium's context menu, without the entries that navigate."""
        from PyQt6.QtWebEngineCore import QWebEnginePage

        view = self.markdown_preview
        menu = view.createStandardContextMenu()
        kept = {
            view.pageAction(getattr(QWebEnginePage.WebAction, name))
            for name in MARKDOWN_PREVIEW_MENU_ACTIONS
        }
        for action in menu.actions():
            if not action.isSeparator() and action not in kept:
                menu.removeAction(action)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if any(not action.isSeparator() for action in menu.actions()):
            menu.popup(view.mapToGlobal(pos))
        else:
            menu.close()

    def is_markdown_file(self, file_path=None):
        """Return True when a path should be treated as markdown."""
        path = file_path or self.current_file or ""
        return os.path.splitext(path.lower())[1] in ('.md', '.markdown', '.mdown', '.mkd')

    def markdown_preview_pane(self):
        """Widget the splitter sizes: the clip container, or the view itself."""
        return getattr(self, "markdown_preview_container", None) or self.markdown_preview

    def markdown_preview_reveal_width(self):
        """Width the preview will end up with once the pane is fully open."""
        splitter = getattr(self, "markdown_splitter", None)
        if splitter is None:
            return 600
        sizes = splitter.sizes()
        width = sizes[1] if len(sizes) > 1 else 0
        # The splitter shares out its width minus the handles in proportion to
        # the stored sizes; matching that here keeps the page from reflowing
        # by a few pixels when the pane settles.
        usable = splitter.width() - splitter.handleWidth() * max(0, len(sizes) - 1)
        total = sum(sizes)
        if usable > 340:
            if width > 0 and total > 0:
                width = round(width * usable / total)
            else:
                # A hidden pane reports no size of its own; it opens to the
                # even split that set_markdown_preview_visible falls back to.
                width = usable // 2
            width = min(width, usable - 100)
        return max(240, width or 600)

    def freeze_markdown_preview_width(self, width):
        """Pin the page's layout width so it cannot reflow while the pane moves."""
        if getattr(self, "_markdown_preview_ready", False):
            container = getattr(self, "markdown_preview_container", None)
            if container is not None and width > 0:
                # The view sits inside the container's card inset.
                margins = container.layout().contentsMargins()
                width -= margins.left() + margins.right()
            self.markdown_preview.setMinimumWidth(max(0, int(width)))

    def set_markdown_preview_visible(self, visible, save_state=True):
        """Show or hide the rendered markdown preview."""
        if visible:
            self.ensure_markdown_preview()
        elif not getattr(self, "_markdown_preview_ready", False):
            self.markdown_preview_visible = False
            if save_state:
                self.save_pane_states()
            return
        self.markdown_preview_visible = visible
        pane = self.markdown_preview_pane()
        if visible:
            if hasattr(self, 'markdown_splitter') and self.markdown_splitter.sizes()[1] < 100:
                self.markdown_splitter.setSizes([600, 600])
            width = self.markdown_preview_reveal_width()
            # The page is laid out at its final width straight away, so it can
            # render behind the pane without reflowing as the pane opens.
            self.freeze_markdown_preview_width(width)
            self.clip_markdown_preview_pane(pane)
            if self.preview_scroll_timer:
                self.preview_scroll_timer.start()
            self.update_markdown_preview(preserve_preview_scroll=False, fade_in=True)
            self.animate_markdown_preview_pane(True, width)
        else:
            # A pane closed before it finished opening is already at zero width:
            # collapse it without letting the page reflow on the way out.
            width = pane.width()
            self.freeze_markdown_preview_width(max(width, 240))
            self.animate_markdown_preview_pane(False, max(width, 1))
            if self.preview_scroll_timer:
                self.preview_scroll_timer.stop()
        if save_state:
            self.save_pane_states()

    def clip_markdown_preview_pane(self, pane):
        """Show the pane clipped to zero width so Chromium can render off-screen."""
        original_width = pane.property("animation_original_max_width")
        if original_width is None or int(original_width) == 0:
            original_width = pane.maximumWidth()
            if original_width > 0:
                pane.setProperty("animation_original_max_width", original_width)
        if self.animations_enabled():
            pane.setMaximumWidth(0)
        pane.setVisible(True)

    def animate_markdown_preview_pane(self, visible, width):
        """Slide the pane open or shut without reflowing the rendered page."""
        pane = self.markdown_preview_pane()
        # The minimum width goes back on only once the pane has arrived, so the
        # reveal starts from zero instead of snapping open to 240px.
        pane.setMinimumWidth(0)
        animation = self.animate_widget_visibility(
            pane,
            visible,
            duration=self.markdown_preview_reveal_duration_ms,
            fade=False,
            target_width=width,
        )
        if animation is None:
            self.finish_markdown_preview_pane(visible)
        else:
            animation.finished.connect(lambda: self.finish_markdown_preview_pane(visible))

    def finish_markdown_preview_pane(self, visible):
        """Hand layout control back to the splitter once the pane has settled."""
        self.freeze_markdown_preview_width(240 if visible else 0)
        self.markdown_preview_pane().setMinimumWidth(240 if visible else 0)

    def toggle_markdown_preview(self):
        """Toggle the rendered markdown preview pane."""
        self.set_markdown_preview_visible(not self.markdown_preview_visible)

    def schedule_markdown_preview_update(self):
        """Render the preview after typing has settled briefly."""
        if not getattr(self, "_markdown_preview_ready", False) or not self.markdown_preview_visible:
            return
        self.markdown_typing_active_until = time.time() + 0.75
        self.pending_preview_source_line = self.editor.textCursor().blockNumber() + 1
        if self.markdown_render_timer:
            self.markdown_render_timer.start()

    def preview_base_folder(self):
        """Folder the preview resolves relative image links against.

        Inside Flatpak that is the document's folder through a granted portal
        folder when there is one; the bare portal folder shows only the file.
        """
        document_folder = getattr(self, "document_folder", None)
        folder = document_folder() if document_folder is not None else None
        return folder or os.path.dirname(self.current_file)

    def update_markdown_preview(self, preserve_preview_scroll=True, fade_in=False):
        """Render editor markdown into the preview pane."""
        if not self.markdown_preview_visible:
            return
        if not getattr(self, "_markdown_preview_ready", False):
            self.ensure_markdown_preview()

        if self.current_file:
            content_base_url = QUrl.fromLocalFile(self.preview_base_folder() + os.sep).toString()
        else:
            content_base_url = QUrl.fromLocalFile(os.getcwd() + os.sep).toString()

        body_html = self.render_markdown_body_html(self.editor.toPlainText())
        fade_hold_ms = (
            self.markdown_preview_reveal_duration_ms
            if fade_in and self.animations_enabled() else 0
        )
        shell_signature = self.markdown_preview_signature(
            self.wrap_markdown_preview_html("", content_base_url)
        )
        if self.markdown_preview_shows_shell(shell_signature):
            self.replace_markdown_preview_body(body_html, fade_in, fade_hold_ms)
            return

        def render_preview(scroll_ratio):
            try:
                scroll_ratio = max(0.0, min(1.0, float(scroll_ratio)))
            except (TypeError, ValueError):
                scroll_ratio = self.get_editor_scroll_ratio()

            preview_html = self.wrap_markdown_preview_html(
                body_html,
                content_base_url,
                initial_scroll_ratio=scroll_ratio,
                fade_in=fade_in,
                fade_hold_ms=fade_hold_ms,
            )

            if fade_in:
                # Blank the outgoing page so the pane opens empty rather than
                # flashing the stale render away once the new one arrives.
                self.markdown_preview.page().runJavaScript(
                    "document.documentElement.classList.add('jottr-preview-fade-in');"
                )

            self.write_markdown_preview_file(preview_html)
            self.requested_preview_shell_signature = shell_signature
            self.loaded_preview_shell_signature = None
            self.rendered_preview_body_html = body_html
            self.markdown_preview_loading = True
            self.markdown_preview.load(QUrl.fromLocalFile(self.markdown_preview_file))

        if not preserve_preview_scroll:
            # Opening the pane: skip the round trip to a page that is about to
            # be replaced and start the render in this event loop pass.
            render_preview(self.get_editor_scroll_ratio())
            return

        self.markdown_preview.page().runJavaScript(
            """
            (function() {
                const doc = document.scrollingElement || document.documentElement;
                const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
                if (!maxScroll) return 0;
                return Math.max(0, Math.min(1, window.scrollY / maxScroll));
            })();
            """,
            render_preview
        )

    # The per-render values that say nothing about what the page shows.
    preview_signature_noise = re.compile(
        r"window\.__jottr(?:InitialPreviewScrollRatio|PreviewFadeIn|PreviewFadeHoldMs)"
        r" = (?:[0-9.eE+-]+|true|false)"
    )

    def markdown_preview_signature(self, preview_html):
        """Preview HTML reduced to what actually changes on screen."""
        return self.preview_signature_noise.sub("", preview_html)

    def write_markdown_preview_file(self, preview_html):
        """Write the rendered preview to a normal local HTML file for WebEngine."""
        with open(self.markdown_preview_file, 'w', encoding='utf-8') as preview_file:
            preview_file.write(preview_html)

    def markdown_preview_shows_shell(self, shell_signature):
        """True when the page has loaded this shell and is still showing it."""
        if (shell_signature != self.loaded_preview_shell_signature or
                self.markdown_preview_loading):
            return False
        # A followed link leaves the page; the document is never handed to
        # whatever it shows instead.
        url = self.markdown_preview.url()
        return (url.adjusted(QUrl.UrlFormattingOption.RemoveFragment) ==
                QUrl.fromLocalFile(self.markdown_preview_file))

    def replace_markdown_preview_body(self, body_html, fade_in=False, fade_hold_ms=0):
        """Swap the rendered document into the loaded page without reloading it."""
        if fade_in:
            # Reopening the pane: the page kept the scroll position it was
            # closed at, so line it back up with the editor.
            self.pending_preview_source_line = self.get_editor_top_visible_line()
        if body_html == self.rendered_preview_body_html:
            if fade_in:
                QTimer.singleShot(0, self.sync_markdown_preview_scroll)
            return

        if fade_in:
            self.preview_sync_after_load = True
        self.rendered_preview_body_html = body_html
        self.markdown_preview_loading = True
        self.markdown_preview.page().runJavaScript(
            "window.__jottrReplacePreviewBody(%s, %s, %s);" % (
                json.dumps(body_html), json.dumps(bool(fade_in)), json.dumps(int(fade_hold_ms))
            ),
            lambda _result: self.render_markdown_preview_scripts()
        )

    def markdown_preview_load_finished(self, ok=True):
        """Note which shell the page now shows, then run its render scripts."""
        self.loaded_preview_shell_signature = (
            self.requested_preview_shell_signature if ok else None
        )
        self.render_markdown_preview_scripts()

    def render_markdown_preview_scripts(self, *args):
        """Run preview scripts that need the WebEngine page to finish loading."""
        if not getattr(self, "_markdown_preview_ready", False) or not self.markdown_preview_visible:
            self.markdown_preview_loading = False
            return

        script = """
            (async function () {
                let rendered = false;
                if (window.MathJax && window.MathJax.typesetPromise) {
                    try {
                        if (!window.jottrMathJaxRendering) {
                            window.jottrMathJaxRendering = true;
                            var mathNodes = Array.prototype.slice.call(document.querySelectorAll('.math-inline, .math-block'));
                            if (mathNodes.length) {
                                await window.MathJax.typesetPromise(mathNodes);
                                rendered = true;
                            }
                        }
                    } catch (error) {
                        console.error('MathJax render failed', error);
                    } finally {
                        window.jottrMathJaxRendering = false;
                    }
                }
                return rendered;
            })();
        """
        self.markdown_preview.page().runJavaScript(
            script,
            lambda _result: self.finish_markdown_preview_load()
        )

    def finish_markdown_preview_load(self):
        """Finish preview rendering and run one deferred scroll sync if needed."""
        self.markdown_preview_loading = False
        if self.preview_sync_after_load:
            self.preview_sync_after_load = False
            QTimer.singleShot(50, self.sync_markdown_preview_scroll)

    def get_editor_scroll_ratio(self):
        """Return editor vertical scroll progress as a 0..1 ratio."""
        scroll_bar = self.editor.verticalScrollBar()
        maximum = scroll_bar.maximum()
        if maximum <= 0:
            return 0.0
        return max(0.0, min(1.0, scroll_bar.value() / maximum))

    def get_editor_top_visible_line(self):
        """Return the 1-based source line nearest the top of the editor viewport."""
        cursor = self.editor.cursorForPosition(self.editor.viewport().rect().topLeft())
        return cursor.blockNumber() + 1

    def schedule_markdown_cursor_sync(self):
        """Sync preview to the line currently being edited."""
        if self.syncing_markdown_scroll:
            return

        self.pending_preview_source_line = self.editor.textCursor().blockNumber() + 1
        self.schedule_markdown_scroll_sync()

    def schedule_markdown_scroll_sync(self, *_args):
        """Debounce editor scroll events before updating preview scroll."""
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                self.syncing_markdown_scroll or
                self.preview_scroll_pending):
            return

        if time.time() < self.markdown_typing_active_until:
            return

        if ((self.markdown_render_timer and self.markdown_render_timer.isActive()) or
                self.markdown_preview_loading):
            self.preview_sync_after_load = True
            return

        self.preview_scroll_pending = True
        QTimer.singleShot(16, self.sync_markdown_preview_scroll)

    def sync_markdown_preview_scroll(self):
        """Scroll the markdown preview to match the editor's relative position."""
        self.preview_scroll_pending = False
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                not getattr(self, "_markdown_preview_ready", False)):
            return

        source_line = self.pending_preview_source_line or self.get_editor_top_visible_line()
        editor_scroll_ratio = self.get_editor_scroll_ratio()
        self.pending_preview_source_line = None
        self.syncing_markdown_scroll = True
        self.ignore_preview_scroll_until = time.time() + 0.75
        self.markdown_preview.page().runJavaScript(
            """
            (function(targetLine, editorScrollRatio) {
                const nodes = Array.from(document.querySelectorAll('[data-source-line]'));
                if (!nodes.length) return;

                let target = nodes[0];
                for (const node of nodes) {
                    const line = Number(node.dataset.sourceLine);
                    if (line > targetLine) break;
                    target = node;
                }

                const doc = document.scrollingElement || document.documentElement;
                const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
                const anchorTop = Math.max(0, target.getBoundingClientRect().top + window.scrollY - 16);
                const ratioTop = maxScroll * Math.max(0, Math.min(1, Number(editorScrollRatio) || 0));
                let top = anchorTop;

                if (anchorTop >= maxScroll && editorScrollRatio < 0.98) {
                    top = ratioTop;
                }

                top = Math.max(0, Math.min(maxScroll, top));

                if (window.__jottrPreviewScrollFrame) {
                    cancelAnimationFrame(window.__jottrPreviewScrollFrame);
                }

                const start = window.scrollY;
                const delta = top - start;
                if (Math.abs(delta) < 2) {
                    window.scrollTo(0, top);
                    return;
                }

                const duration = 140;
                const startTime = performance.now();
                function ease(value) {
                    return value < 0.5 ? 2 * value * value : 1 - Math.pow(-2 * value + 2, 2) / 2;
                }
                function step(now) {
                    const progress = Math.min(1, (now - startTime) / duration);
                    window.scrollTo(0, start + delta * ease(progress));
                    if (progress < 1) {
                        window.__jottrPreviewScrollFrame = requestAnimationFrame(step);
                    }
                }
                window.__jottrPreviewScrollFrame = requestAnimationFrame(step);
            })(""" + str(source_line) + ", " + repr(editor_scroll_ratio) + """);
            """,
            lambda _result: setattr(self, 'syncing_markdown_scroll', False)
        )

    def animate_editor_scroll_to(self, value):
        """Smoothly move the editor scrollbar to the requested value."""
        scroll_bar = self.editor.verticalScrollBar()
        target = max(scroll_bar.minimum(), min(scroll_bar.maximum(), int(value)))
        if abs(scroll_bar.value() - target) < 2:
            scroll_bar.setValue(target)
            QTimer.singleShot(0, lambda: setattr(self, 'syncing_markdown_scroll', False))
            return

        if self.editor_scroll_animation:
            self.editor_scroll_animation.stop()

        self.editor_scroll_animation = QPropertyAnimation(scroll_bar, b"value", self)
        self.editor_scroll_animation.setDuration(130)
        self.editor_scroll_animation.setStartValue(scroll_bar.value())
        self.editor_scroll_animation.setEndValue(target)
        self.editor_scroll_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.editor_scroll_animation.finished.connect(
            lambda: setattr(self, 'syncing_markdown_scroll', False)
        )
        self.editor_scroll_animation.start()

    def schedule_editor_scroll_sync(self):
        """Debounce preview scroll events before updating editor scroll."""
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                self.syncing_markdown_scroll or
                time.time() < self.ignore_preview_scroll_until or
                time.time() > self.preview_user_scroll_until or
                self.editor_scroll_pending):
            return

        self.editor_scroll_pending = True
        QTimer.singleShot(80, self.sync_editor_scroll_from_preview)

    def sync_editor_scroll_from_preview(self):
        """Scroll the editor to match the preview's relative position."""
        self.editor_scroll_pending = False
        if (not self.settings_manager.get_setting('markdown_scroll_sync', True) or
                not self.markdown_preview_visible or
                not getattr(self, "_markdown_preview_ready", False)):
            return

        script = """
            (function() {
                const nodes = Array.from(document.querySelectorAll('[data-source-line]'));
                if (!nodes.length) return 1;

                let best = nodes[0];
                let bestDistance = Infinity;
                for (const node of nodes) {
                    const distance = Math.abs(node.getBoundingClientRect().top - 16);
                    if (distance < bestDistance) {
                        best = node;
                        bestDistance = distance;
                    }
                }
                return Number(best.dataset.sourceLine) || 1;
            })();
        """

        def apply_editor_scroll(source_line):
            try:
                source_line = max(1, int(float(source_line)))
            except (TypeError, ValueError):
                return

            block = self.editor.document().findBlockByNumber(source_line - 1)
            if not block.isValid():
                return

            scroll_bar = self.editor.verticalScrollBar()
            layout = self.editor.document().documentLayout()
            block_top = layout.blockBoundingRect(block).top() - scroll_bar.value()

            self.syncing_markdown_scroll = True
            self.animate_editor_scroll_to(round(scroll_bar.value() + block_top - 16))

        self.markdown_preview.page().runJavaScript(script, apply_editor_scroll)

    def render_markdown_html(self, text, content_base_url="", initial_scroll_ratio=None,
                             fade_in=False, fade_hold_ms=0):
        """Render markdown as a complete preview page."""
        return self.wrap_markdown_preview_html(
            self.render_markdown_body_html(text),
            content_base_url, initial_scroll_ratio, fade_in, fade_hold_ms
        )

    def render_markdown_body_html(self, text):
        """Render markdown as the HTML that goes inside the preview page."""
        if MARKDOWN_LIB_AVAILABLE:
            return self.render_markdown_body_html_with_library(text)
        return self.render_markdown_body_html_builtin(text)

    def render_markdown_body_html_builtin(self, text):
        """Render a practical markdown subset with stable heading and code styling."""
        body = []
        paragraph = []
        paragraph_lines = []
        in_code_block = False
        code_lines = []
        code_start_line = None
        in_math_block = False
        math_lines = []
        math_start_line = None
        list_stack = []

        emoji_map = {
            "smile": "😄", "grinning": "😀", "joy": "😂", "laughing": "😆",
            "wink": "😉", "blush": "😊", "heart": "❤️", "broken_heart": "💔",
            "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎",
            "clap": "👏", "pray": "🙏", "fire": "🔥", "star": "⭐",
            "sparkles": "✨", "rocket": "🚀", "tada": "🎉", "warning": "⚠️",
            "x": "❌", "white_check_mark": "✅", "check": "✅", "information_source": "ℹ️",
            "bulb": "💡", "eyes": "👀", "thinking": "🤔", "cry": "😢",
            "sob": "😭", "angry": "😠", "poop": "💩", "100": "💯",
            "memo": "📝", "book": "📖", "computer": "💻", "gear": "⚙️",
            "bug": "🐛", "lock": "🔒", "unlock": "🔓", "link": "🔗"
        }

        def is_table_separator(value):
            cells = self.split_table_row(value)
            if len(cells) < 2:
                return False
            return all(re.match(r'^:?-{3,}:?$', cell.strip()) for cell in cells)

        def table_alignments(separator):
            alignments = []
            for cell in self.split_table_row(separator):
                stripped = cell.strip()
                if stripped.startswith(":") and stripped.endswith(":"):
                    alignments.append("center")
                elif stripped.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")
            return alignments

        def split_image_target(target):
            target = target.strip()
            title = ""
            if target.startswith("<"):
                end = target.find(">")
                if end >= 0:
                    source = target[1:end].strip()
                    title = target[end + 1:].strip()
                else:
                    source = target.strip("<>").strip()
            else:
                match = re.match(r'^(.*?)\s+["\']([^"\']*)["\']\s*$', target)
                if match:
                    source = match.group(1).strip()
                    title = match.group(2)
                else:
                    source = target
            return source, title

        def resolve_local_image_path(source):
            if source.startswith("file://"):
                return QUrl(source).toLocalFile()

            current_file = getattr(self, 'current_file', None)
            if current_file and not os.path.isabs(source):
                source = os.path.join(self.preview_base_folder(), source)
            return os.path.abspath(os.path.expanduser(source))

        def image_file_to_data_url(path):
            if not os.path.isfile(path):
                return None

            mime_type, _ = mimetypes.guess_type(path)
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            try:
                with open(path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode("ascii")
                return f"data:{mime_type};base64,{encoded}"
            except OSError:
                return None

        def resolve_image_source(source):
            source = source.strip()
            if source.startswith("<") and source.endswith(">"):
                source = source[1:-1].strip()
            if source.startswith(("http://", "https://", "data:")):
                return html.escape(source, quote=True)

            local_path = resolve_local_image_path(source)
            data_url = image_file_to_data_url(local_path)
            if data_url:
                return html.escape(data_url, quote=True)
            return html.escape(QUrl.fromLocalFile(local_path).toString(QUrl.FullyEncoded), quote=True)

        def render_inline(value):
            images = []
            inline_math = []

            def stash_image(match):
                alt_text = html.escape(match.group(1), quote=True)
                source_target, explicit_title = split_image_target(match.group(2))
                source = resolve_image_source(source_target)
                title = html.escape(explicit_title or match.group(1), quote=True)
                images.append(
                    f'<img src="{source}" alt="{alt_text}" title="{title}">'
                )
                return f"\u0000IMG{len(images) - 1}\u0000"

            def stash_inline_math(match):
                expression = html.escape(match.group(1).strip())
                inline_math.append(f'<span class="math-inline">\\({expression}\\)</span>')
                return f"\u0000MATH{len(inline_math) - 1}\u0000"

            value = re.sub(
                r'!\[([^\]]*)\]\(\s*([^)]+?)\s*\)',
                stash_image,
                value
            )
            value = re.sub(r'(?<!\\)\$(?!\$)(.+?)(?<!\\)\$', stash_inline_math, value)
            value = html.escape(value)
            value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
            value = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)
            value = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', value)
            value = re.sub(r'~~(.+?)~~', r'<del>\1</del>', value)
            value = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', value)
            value = re.sub(r'(?<!_)_([^_\n]+)_(?!_)', r'<em>\1</em>', value)
            value = self.apply_typographer_replacements(value)
            value = re.sub(
                r':([a-zA-Z0-9_+\-]+):',
                lambda match: emoji_map.get(match.group(1), match.group(0)),
                value
            )
            value = re.sub(
                r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
                r'<a href="\2">\1</a>',
                value
            )
            for index, image_markup in enumerate(images):
                value = value.replace(f"\u0000IMG{index}\u0000", image_markup)
            for index, math_markup in enumerate(inline_math):
                value = value.replace(f"\u0000MATH{index}\u0000", math_markup)
            return value

        def flush_paragraph():
            nonlocal paragraph_lines
            if paragraph:
                source_line = paragraph_lines[0] if paragraph_lines else 1
                body.append(f'<p data-source-line="{source_line}">{render_inline(" ".join(paragraph))}</p>')
                paragraph.clear()
                paragraph_lines.clear()

        def close_list():
            while list_stack:
                close_list_level()

        def close_list_level():
            list_state = list_stack.pop()
            if list_state.get('open_item'):
                body.append("</li>")
            body.append(f"</{list_state['type']}>")

        def list_level_from_indent(indent):
            return indent // 2

        def render_task_list_item_content(item_text):
            task = re.match(r'^\[([ xX])\]\s*(.*)$', item_text)
            if not task:
                return render_inline(item_text)

            checked = ' checked' if task.group(1).lower() == 'x' else ''
            return (
                f'<input class="task-list-item-checkbox" type="checkbox" disabled{checked}> '
                f'{render_inline(task.group(2))}'
            )

        def render_list_item(line_number, list_type, level, item_text, start_number=None):
            while list_stack and list_stack[-1]['level'] > level:
                close_list_level()

            if list_stack and list_stack[-1]['level'] == level and list_stack[-1]['type'] != list_type:
                close_list_level()

            if not list_stack or list_stack[-1]['level'] < level:
                start_attr = f' start="{start_number}"' if list_type == "ol" and start_number and start_number != 1 else ""
                body.append(f"<{list_type}{start_attr}>")
                list_stack.append({'type': list_type, 'level': level, 'open_item': False})

            if list_stack[-1]['open_item']:
                body.append("</li>")

            body.append(f'<li data-source-line="{line_number}">{render_task_list_item_content(item_text)}')
            list_stack[-1]['open_item'] = True

        def render_display_math(source_line, expression):
            escaped_expression = html.escape(expression.strip())
            return (
                f'<div class="math-block" data-source-line="{source_line}">'
                f'\\[{escaped_expression}\\]</div>'
            )

        def render_code_block(source_line, values, span_start_line=None):
            span_start_line = span_start_line or source_line
            code_markup = []
            for offset, value in enumerate(values):
                escaped_line = html.escape(value) or " "
                code_markup.append(
                    f'<span class="source-code-line" data-source-line="{span_start_line + offset}">'
                    f'{escaped_line}</span>'
                )
            return (
                f'<pre data-source-line="{source_line}">'
                f'<code>{"".join(code_markup)}</code></pre>'
            )

        def is_indented_code_line(value):
            return value.startswith("    ") or value.startswith("\t")

        def strip_code_indent(value):
            if value.startswith("\t"):
                return value[1:]
            if value.startswith("    "):
                return value[4:]
            return value

        def collect_indented_code(start_index):
            code_block_lines = []
            current_index = start_index
            while current_index < len(lines):
                current_line = lines[current_index]
                if is_indented_code_line(current_line) and not is_list_line(current_line):
                    code_block_lines.append(strip_code_indent(current_line.rstrip()))
                    current_index += 1
                elif not current_line.strip() and code_block_lines:
                    code_block_lines.append("")
                    current_index += 1
                else:
                    break

            while code_block_lines and code_block_lines[-1] == "":
                code_block_lines.pop()
            return code_block_lines, current_index

        def is_list_line(value):
            return bool(
                re.match(r'^(\s*)[-*+](?:\s+(.*))?$', value) or
                re.match(r'^(\s*)(\d+)[.)](?:\s+(.*))?$', value)
            )

        def render_table(source_line, rows, alignments):
            header = rows[0]
            body_rows = rows[2:]
            html_rows = [f'<table data-source-line="{source_line}">', '<thead><tr>']
            for index, cell in enumerate(header):
                alignment = alignments[index] if index < len(alignments) else "left"
                html_rows.append(f'<th style="text-align: {alignment};">{render_inline(cell.strip())}</th>')
            html_rows.append('</tr></thead>')

            if body_rows:
                html_rows.append('<tbody>')
                for row in body_rows:
                    html_rows.append('<tr>')
                    for index, cell in enumerate(row):
                        alignment = alignments[index] if index < len(alignments) else "left"
                        html_rows.append(f'<td style="text-align: {alignment};">{render_inline(cell.strip())}</td>')
                    html_rows.append('</tr>')
                html_rows.append('</tbody>')

            html_rows.append('</table>')
            return ''.join(html_rows)

        lines = text.splitlines()
        line_index = 0

        while line_index < len(lines):
            line_number = line_index + 1
            raw_line = lines[line_index]
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    block_line = code_start_line or line_number
                    body.append(render_code_block(block_line, code_lines, block_line + 1))
                    code_lines = []
                    code_start_line = None
                    in_code_block = False
                else:
                    flush_paragraph()
                    close_list()
                    in_code_block = True
                    code_start_line = line_number
                line_index += 1
                continue

            if in_code_block:
                code_lines.append(raw_line)
                line_index += 1
                continue

            if stripped.startswith("$$"):
                if in_math_block:
                    content = stripped[2:].strip()
                    if content:
                        math_lines.append(content)
                    body.append(render_display_math(math_start_line or line_number, chr(10).join(math_lines)))
                    math_lines = []
                    math_start_line = None
                    in_math_block = False
                else:
                    flush_paragraph()
                    close_list()
                    after_open = stripped[2:].strip()
                    if after_open.endswith("$$") and len(after_open) > 2:
                        body.append(render_display_math(line_number, after_open[:-2]))
                    else:
                        in_math_block = True
                        math_start_line = line_number
                        if after_open:
                            math_lines.append(after_open)
                line_index += 1
                continue

            if in_math_block:
                if stripped.endswith("$$"):
                    before_close = raw_line.rstrip()[:-2].strip()
                    if before_close:
                        math_lines.append(before_close)
                    body.append(render_display_math(math_start_line or line_number, chr(10).join(math_lines)))
                    math_lines = []
                    math_start_line = None
                    in_math_block = False
                else:
                    math_lines.append(raw_line)
                line_index += 1
                continue

            if not stripped:
                flush_paragraph()
                close_list()
                line_index += 1
                continue

            unordered = re.match(r'^(\s*)[-*+](?:\s+(.*))?$', line)
            ordered = re.match(r'^(\s*)(\d+)[.)](?:\s+(.*))?$', line)
            if unordered or ordered:
                flush_paragraph()
                desired_list = "ul" if unordered else "ol"
                indent = len(unordered.group(1) if unordered else ordered.group(1))
                item_text = (unordered.group(2) if unordered else ordered.group(3)) or ""
                start_number = None if unordered else int(ordered.group(2))
                render_list_item(line_number, desired_list, list_level_from_indent(indent), item_text, start_number)
                line_index += 1
                continue

            if is_indented_code_line(raw_line):
                flush_paragraph()
                close_list()
                indented_code_lines, line_index = collect_indented_code(line_index)
                body.append(render_code_block(line_number, indented_code_lines))
                continue

            if ("|" in stripped and
                    line_index + 1 < len(lines) and
                    is_table_separator(lines[line_index + 1].strip())):
                flush_paragraph()
                close_list()
                table_rows = [self.split_table_row(stripped), self.split_table_row(lines[line_index + 1].strip())]
                alignments = table_alignments(lines[line_index + 1].strip())
                line_index += 2
                while line_index < len(lines) and "|" in lines[line_index].strip():
                    table_rows.append(self.split_table_row(lines[line_index].strip()))
                    line_index += 1
                body.append(render_table(line_number, table_rows, alignments))
                continue

            heading = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading:
                flush_paragraph()
                close_list()
                level = len(heading.group(1))
                body.append(f'<h{level} data-source-line="{line_number}">{render_inline(heading.group(2))}</h{level}>')
                line_index += 1
                continue

            if re.match(r'^([-*_])(?:\s*\1){2,}\s*$', stripped):
                flush_paragraph()
                close_list()
                body.append(f'<hr data-source-line="{line_number}">')
                line_index += 1
                continue

            quote = re.match(r'^(>+\s*)+(.*)$', stripped)
            if quote:
                flush_paragraph()
                close_list()
                quote_text = quote.group(2).strip()
                body.append(f'<blockquote data-source-line="{line_number}">{render_inline(quote_text)}</blockquote>')
                line_index += 1
                continue

            close_list()
            paragraph.append(stripped)
            paragraph_lines.append(line_number)
            line_index += 1

        if in_code_block:
            block_line = code_start_line or 1
            body.append(render_code_block(block_line, code_lines, block_line + 1))
        if in_math_block:
            body.append(render_display_math(math_start_line or 1, chr(10).join(math_lines)))
        flush_paragraph()
        close_list()
        return "".join(body)

    @staticmethod
    def split_table_row(row):
        """Split a markdown table row, respecting escaped pipe characters."""
        stripped = row.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|") and not stripped.endswith("\\|"):
            stripped = stripped[:-1]

        cells = []
        current = []
        escaped = False
        for char in stripped:
            if escaped:
                current.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "|":
                cells.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        if escaped:
            current.append("\\")
        cells.append(''.join(current).strip())
        return cells

    def render_markdown_body_html_with_library(self, text):
        """Render markdown using Python-Markdown with local preview enhancements."""
        import markdown as markdown_lib

        prepared_text, inline_math = self.preprocess_markdown_extensions(text)
        extensions = [
            'extra',
            'sane_lists',
            'smarty',
            'toc',
            'nl2br',
            'admonition',
            'meta',
        ]

        body_html = markdown_lib.markdown(
            prepared_text,
            extensions=extensions,
            output_format='html5'
        )
        body_html = self.restore_inline_math(body_html, inline_math)
        body_html = self.apply_markdown_extensions(body_html)
        body_html = self.add_source_line_anchors(body_html, text)
        return self.add_code_line_anchors(body_html)

    def markdown_extensions(self):
        manager = getattr(getattr(self, "main_window", None), "plugin_manager", None)
        registry = getattr(manager, "registry", None)
        return list(getattr(registry, "markdown_extensions", []))

    def markdown_extension_context(self):
        return {
            "editor": self,
            "settings_manager": self.settings_manager,
            "main_window": self.main_window,
        }

    def call_markdown_extension(self, extension, key, *args):
        callback = extension.get(key)
        if not callable(callback):
            return "" if key.endswith("_html") else None
        try:
            return callback(*args, self.markdown_extension_context())
        except TypeError:
            return callback(*args)

    def apply_markdown_extensions(self, body_html):
        for extension in self.markdown_extensions():
            callback = extension.get("process_html")
            if not callable(callback):
                continue
            try:
                body_html = callback(body_html, self.markdown_extension_context())
            except TypeError:
                body_html = callback(body_html)
        return body_html

    def render_markdown_extension_head_html(self):
        parts = []
        for extension in self.markdown_extensions():
            value = self.call_markdown_extension(extension, "head_html")
            if value:
                parts.append(str(value))
        return "\n".join(parts)

    def render_markdown_extension_style_html(self):
        parts = []
        for extension in self.markdown_extensions():
            value = self.call_markdown_extension(extension, "style_html")
            if value:
                parts.append(str(value))
        return "\n".join(parts)

    def render_markdown_extension_body_html(self):
        parts = []
        for extension in self.markdown_extensions():
            value = self.call_markdown_extension(extension, "body_html")
            if value:
                parts.append(str(value))
        return "\n".join(parts)

    def preprocess_markdown_extensions(self, text):
        """Preprocess syntax that Python-Markdown does not handle by default.

        Returns the text with inline math still stashed, and the stash to
        restore it from once Python-Markdown has run.
        """
        text, fenced_blocks = self.stash_fenced_code_blocks(text)
        text = self.preprocess_task_lists(text)
        text = self.preprocess_math_blocks(text)
        text, inline_math = self.stash_inline_math(text)
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text, flags=re.DOTALL)
        text = self.apply_typographer_replacements(text)
        text = self.apply_emoji_shortcodes(text)
        text = self.restore_fenced_code_blocks(text, fenced_blocks)
        return text, inline_math

    # Inline code spans, which keep any dollar signs they hold, $$display$$
    # math within a line, or $math$.
    inline_math_pattern = re.compile(
        r'(`+).+?(?<!`)\1(?!`)'
        r'|(?<!\\)\$\$(.+?)(?<!\\)\$\$'
        r'|(?<!\\)\$(?!\$)(.+?)(?<!\\)\$'
    )

    def stash_inline_math(self, text):
        """Swap $math$ for plain tokens that markdown processing leaves alone.

        Python-Markdown would otherwise unescape the \\( \\) delimiters MathJax
        looks for, and emphasis, quotes, and emoji would rewrite the TeX.
        """
        stash = []

        def replace(match):
            if match.group(1):
                return match.group(0)
            if match.group(2) is not None:
                stash.append(
                    f'<span class="math-inline">\\[{html.escape(match.group(2).strip())}\\]</span>'
                )
            else:
                stash.append(
                    f'<span class="math-inline">\\({html.escape(match.group(3).strip())}\\)</span>'
                )
            return f"JOTTRINLINEMATH{len(stash) - 1}END"

        return self.inline_math_pattern.sub(replace, text), stash

    @staticmethod
    def restore_inline_math(text, stash):
        """Put stashed inline math back in place of its tokens."""
        if not stash:
            return text
        return re.sub(
            r'JOTTRINLINEMATH(\d+)END',
            lambda match: stash[int(match.group(1))],
            text
        )

    @staticmethod
    def stash_fenced_code_blocks(text):
        """Temporarily remove fenced code blocks from markdown preprocessing."""
        lines = text.splitlines(keepends=True)
        processed_lines = []
        fenced_blocks = []
        index = 0

        while index < len(lines):
            line = lines[index]
            match = re.match(r'^([ \t]*)(`{3,}|~{3,})', line)
            if not match:
                processed_lines.append(line)
                index += 1
                continue

            fence_marker = match.group(2)
            fence_char = fence_marker[0]
            fence_length = len(fence_marker)
            block_lines = [line]
            index += 1

            while index < len(lines):
                block_lines.append(lines[index])
                closing = re.match(r'^[ \t]*(%s{%d,})[ \t]*$' % (re.escape(fence_char), fence_length), lines[index])
                index += 1
                if closing:
                    break

            placeholder = f'\u0000JOTTR_FENCED_CODE_{len(fenced_blocks)}\u0000'
            fenced_blocks.append(''.join(block_lines))
            processed_lines.append(placeholder + '\n')

        return ''.join(processed_lines), fenced_blocks

    @staticmethod
    def restore_fenced_code_blocks(text, fenced_blocks):
        """Restore fenced code blocks after markdown preprocessing."""
        for index, block in enumerate(fenced_blocks):
            text = text.replace(f'\u0000JOTTR_FENCED_CODE_{index}\u0000\n', block)
            text = text.replace(f'\u0000JOTTR_FENCED_CODE_{index}\u0000', block)
        return text

    def preprocess_task_lists(self, text):
        """Convert GitHub-style task list markers to disabled checkboxes."""
        processed_lines = []
        task_pattern = re.compile(r'^(\s*(?:[-*+]|\d+[.)])\s+)\[([ xX])\]\s*(.*)$')
        previous_task_indent = None
        previous_task_type = None

        for line in text.splitlines():
            match = task_pattern.match(line)
            if not match:
                processed_lines.append(line)
                if line.strip():
                    previous_task_indent = None
                    previous_task_type = None
                continue

            checked = ' checked' if match.group(2).lower() == 'x' else ''
            checkbox = f'<input class="task-list-item-checkbox" type="checkbox" disabled{checked}>'
            prefix = self.normalize_markdown_list_indent(match.group(1))
            indent = len(re.match(r'^(\s*)', prefix).group(1))
            task_type = "ol" if re.search(r'\d+[.)]\s+$', prefix) else "ul"
            if (processed_lines and previous_task_indent is not None and
                    indent <= previous_task_indent and task_type != previous_task_type):
                processed_lines.append("")
            processed_lines.append(f'{prefix}{checkbox} {match.group(3)}')
            previous_task_indent = indent
            previous_task_type = task_type

        return "\n".join(processed_lines)

    @staticmethod
    def normalize_markdown_list_indent(prefix):
        """Normalize two-space nested list indentation for Python-Markdown."""
        match = re.match(r'^(\s*)((?:[-*+]|\d+[.)])\s+)$', prefix)
        if not match:
            return prefix

        indent = match.group(1)
        marker = match.group(2)
        spaces = len(indent.replace("\t", "    "))
        normalized_indent = " " * ((spaces // 2) * 4)
        return normalized_indent + marker

    def preprocess_math_blocks(self, text):
        """Convert $$ display math blocks to MathJax-friendly HTML."""
        lines = text.splitlines()
        output = []
        math_lines = []
        math_start_line = None
        in_math = False

        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("$$"):
                if in_math:
                    tail = stripped[2:].strip()
                    if tail:
                        math_lines.append(tail)
                    output.append(
                        f'<div class="math-block" data-source-line="{math_start_line or index}">'
                        f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
                    )
                    math_lines = []
                    math_start_line = None
                    in_math = False
                else:
                    after_open = stripped[2:].strip()
                    if after_open.endswith("$$") and len(after_open) > 2:
                        output.append(
                            f'<div class="math-block" data-source-line="{index}">'
                            f'\\[{html.escape(after_open[:-2].strip())}\\]</div>'
                        )
                    else:
                        in_math = True
                        math_start_line = index
                        if after_open:
                            math_lines.append(after_open)
                continue

            if in_math:
                if stripped.endswith("$$"):
                    before_close = line.rstrip()[:-2].strip()
                    if before_close:
                        math_lines.append(before_close)
                    output.append(
                        f'<div class="math-block" data-source-line="{math_start_line or index}">'
                        f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
                    )
                    math_lines = []
                    math_start_line = None
                    in_math = False
                else:
                    math_lines.append(line)
                continue

            output.append(line)

        if in_math:
            output.append(
                f'<div class="math-block" data-source-line="{math_start_line or 1}">'
                f'\\[{html.escape(chr(10).join(math_lines).strip())}\\]</div>'
            )

        return "\n".join(output)

    @staticmethod
    def apply_emoji_shortcodes(value):
        emoji_map = {
            "smile": "😄", "grinning": "😀", "joy": "😂", "laughing": "😆",
            "wink": "😉", "blush": "😊", "heart": "❤️", "broken_heart": "💔",
            "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎",
            "clap": "👏", "pray": "🙏", "fire": "🔥", "star": "⭐",
            "sparkles": "✨", "rocket": "🚀", "tada": "🎉", "warning": "⚠️",
            "x": "❌", "white_check_mark": "✅", "check": "✅", "information_source": "ℹ️",
            "bulb": "💡", "eyes": "👀", "thinking": "🤔", "cry": "😢",
            "sob": "😭", "angry": "😠", "poop": "💩", "100": "💯",
            "memo": "📝", "book": "📖", "computer": "💻", "gear": "⚙️",
            "bug": "🐛", "lock": "🔒", "unlock": "🔓", "link": "🔗"
        }
        return re.sub(
            r':([a-zA-Z0-9_+\-]+):',
            lambda match: emoji_map.get(match.group(1), match.group(0)),
            value
        )

    def collect_source_anchor_lines(self, text):
        """Collect approximate source lines for rendered block elements."""
        anchors = []
        in_fence = False
        fence_start = None
        in_math = False
        math_start = None

        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("```"):
                if in_fence:
                    in_fence = False
                    fence_start = None
                else:
                    anchors.append(index)
                    in_fence = True
                    fence_start = index
                continue
            if in_fence:
                continue

            if stripped.startswith("$$"):
                if in_math:
                    in_math = False
                    math_start = None
                else:
                    anchors.append(index)
                    in_math = True
                    math_start = index
                continue
            if in_math:
                continue

            if re.match(r'^\|?.+\|.+$', stripped):
                if index == 1 or not re.match(r'^:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?$', stripped):
                    anchors.append(index)
                continue

            anchors.append(index)

        return anchors or [1]

    def add_source_line_anchors(self, body_html, source_text):
        """Attach source-line attributes to block elements for scroll sync."""
        source_lines = iter(self.collect_source_anchor_lines(source_text))

        def add_anchor(match):
            tag = match.group(1)
            attrs = match.group(2) or ""
            if "data-source-line=" in attrs:
                return match.group(0)
            line = next(source_lines, None)
            if line is None:
                return match.group(0)
            if "dir=" not in attrs:
                attrs = f'{attrs} dir="auto"'
            return f'<{tag}{attrs} data-source-line="{line}">'

        return re.sub(
            r'<(h[1-6]|p|pre|blockquote|li|table|hr|div)(\s[^>]*)?>',
            add_anchor,
            body_html
        )

    def add_code_line_anchors(self, body_html):
        """Attach source-line attributes to individual rendered code lines."""
        def replace_pre(match):
            pre_attrs = match.group(1) or ""
            code_attrs = match.group(2) or ""
            code_text = match.group(3)
            line_match = re.search(r'data-source-line="(\d+)"', pre_attrs)
            if not line_match or 'class="source-code-line"' in code_text:
                return match.group(0)

            source_line = int(line_match.group(1))
            span_start_line = source_line + 1 if "language-" in code_attrs else source_line
            lines = code_text.splitlines()
            if not lines:
                return match.group(0)

            spans = []
            for offset, value in enumerate(lines):
                spans.append(
                    f'<span class="source-code-line" data-source-line="{span_start_line + offset}">'
                    f'{value or " "}</span>'
                )
            return f'<pre{pre_attrs}><code{code_attrs}>{"".join(spans)}</code></pre>'

        return re.sub(
            r'<pre([^>]*)><code([^>]*)>(.*?)</code></pre>',
            replace_pre,
            body_html,
            flags=re.DOTALL
        )

    def preview_font(self):
        """Editor face the preview renders with (never a hardcoded family)."""
        return QFont(getattr(self, "current_font", None) or self.settings_manager.get_font("editor"))

    @staticmethod
    def css_font_family(font):
        """*font*'s family, escaped for use inside a quoted CSS font-family."""
        return html.escape(
            font.family().replace("\\", "\\\\").replace('"', '\\"'), quote=True
        )

    def markdown_preview_script_nonce(self):
        """This tab's key for the scripts its preview page may run.

        It stays the same for the tab's life, so pages rendered for it keep
        the same shell and can be updated in place.
        """
        nonce = getattr(self, "_markdown_preview_script_nonce", None)
        if nonce is None:
            nonce = self._markdown_preview_script_nonce = secrets.token_urlsafe(18)
        return nonce

    @staticmethod
    def markdown_preview_content_security_policy(nonce):
        """Policy that runs only Jottr's and plugins' scripts in the preview.

        Documents may carry raw HTML, and the page is a local file that can
        read other local files, so a document's own scripts, event handlers,
        javascript: links, plugins, and local frames are all refused.
        Scripts Jottr's own scripts load, such as MathJax's components, run.
        """
        return (
            f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
            "object-src 'none'; "
            "frame-src https:"
        )

    @staticmethod
    def trust_markdown_extension_scripts(extension_html, nonce):
        """Let the scripts plugins add to the preview page run."""
        return re.sub(
            r'<script\b', f'<script nonce="{nonce}"', extension_html, flags=re.IGNORECASE
        )

    def wrap_markdown_preview_html(self, body_html, content_base_url="", initial_scroll_ratio=None,
                                   fade_in=False, fade_hold_ms=0):
        """Wrap rendered body HTML in Jottr preview CSS and scripts."""
        nonce = self.markdown_preview_script_nonce()
        extension_head_html = self.trust_markdown_extension_scripts(
            self.render_markdown_extension_head_html(), nonce
        )
        extension_style_html = self.render_markdown_extension_style_html()
        extension_body_html = self.trust_markdown_extension_scripts(
            self.render_markdown_extension_body_html(), nonce
        )
        base_tag = f'<base href="{html.escape(content_base_url, quote=True)}">' if content_base_url else ''
        preview_font = self.preview_font()
        preview_family = self.css_font_family(preview_font)
        font_face_css = bundled_font_face_css()
        preview_size = max(8, preview_font.pointSize() if preview_font.pointSize() > 0 else 14)
        dir_attr = "auto"
        try:
            restore_scroll_ratio = max(0.0, min(1.0, float(initial_scroll_ratio or 0)))
        except (TypeError, ValueError):
            restore_scroll_ratio = 0.0
        restore_scroll_ratio_json = json.dumps(restore_scroll_ratio)
        fade_in_json = json.dumps(bool(fade_in))
        try:
            fade_hold_json = json.dumps(max(0, int(fade_hold_ms)))
        except (TypeError, ValueError):
            fade_hold_json = "0"
        return f"""
        <html dir="{dir_attr}">
        <head>
            <meta http-equiv="Content-Security-Policy" content="{self.markdown_preview_content_security_policy(nonce)}">
            {base_tag}
            <script nonce="{nonce}">
                // A page rendered for an opening pane starts out invisible and
                // fades itself in once its own DOM is ready — but never before
                // the pane has finished sliding open.
                window.__jottrPreviewFadeIn = {fade_in_json};
                window.__jottrPreviewFadeHoldMs = {fade_hold_json};
                if (window.__jottrPreviewFadeIn) {{
                    document.documentElement.classList.add('jottr-preview-fade-in');
                }}
                window.__jottrRevealPreview = function () {{
                    var held = Math.max(0, window.__jottrPreviewFadeHoldMs - performance.now());
                    setTimeout(function () {{
                        document.documentElement.classList.remove('jottr-preview-fade-in');
                    }}, held);
                }};
                document.addEventListener('DOMContentLoaded', window.__jottrRevealPreview);
                // Backstop in case the page is handed to us already parsed.
                setTimeout(window.__jottrRevealPreview, 1200);
                window.__jottrInitialPreviewScrollRatio = {restore_scroll_ratio_json};
                if (window.__jottrInitialPreviewScrollRatio > 0) {{
                    document.documentElement.classList.add('jottr-restoring-preview-scroll');
                }}
                window.__jottrRestoreInitialPreviewScroll = function () {{
                    var ratio = Number(window.__jottrInitialPreviewScrollRatio) || 0;
                    function restore() {{
                        var doc = document.scrollingElement || document.documentElement;
                        var maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
                        if (maxScroll > 0 && ratio > 0) {{
                            window.scrollTo(0, maxScroll * Math.max(0, Math.min(1, ratio)));
                        }}
                        document.documentElement.classList.remove('jottr-restoring-preview-scroll');
                    }}
                    requestAnimationFrame(function () {{
                        requestAnimationFrame(restore);
                    }});
                }};
                document.addEventListener('DOMContentLoaded', window.__jottrRestoreInitialPreviewScroll);
                window.addEventListener('load', window.__jottrRestoreInitialPreviewScroll);
                setTimeout(window.__jottrRestoreInitialPreviewScroll, 450);
                // The <base> tag points relative links at the document's
                // folder, which takes #anchor links there too; scroll to
                // the target in this page instead.
                document.addEventListener('click', function (event) {{
                    var link = event.target.closest && event.target.closest('a[href^="#"]');
                    if (!link) {{
                        return;
                    }}
                    event.preventDefault();
                    var id = decodeURIComponent(link.getAttribute('href').slice(1));
                    var target = id ? document.getElementById(id) : document.body;
                    if (target) {{
                        target.scrollIntoView();
                    }}
                }});
                // Later renders swap the document in here instead of loading
                // the page again, which keeps its scroll position, scripts,
                // and fonts. Plugin body scripts run again over each new
                // render, as they would after a load, and can also listen
                // for the jottr-preview-updated event.
                window.__jottrReplacePreviewBody = function (bodyHtml, fadeIn, fadeHoldMs) {{
                    var root = document.documentElement;
                    var content = document.getElementById('jottr-preview-content');
                    if (fadeIn) {{
                        root.classList.add('jottr-preview-fade-in');
                    }}
                    if (window.MathJax && window.MathJax.typesetClear) {{
                        window.MathJax.typesetClear([content]);
                    }}
                    content.innerHTML = bodyHtml;
                    var extensions = document.getElementById('jottr-preview-extensions');
                    Array.prototype.forEach.call(extensions.querySelectorAll('script'), function (old) {{
                        var script = document.createElement('script');
                        Array.prototype.forEach.call(old.attributes, function (attribute) {{
                            script.setAttribute(attribute.name, attribute.value);
                        }});
                        // The nonce attribute reads back empty once parsed.
                        script.nonce = old.nonce;
                        script.textContent = old.textContent;
                        old.replaceWith(script);
                    }});
                    document.dispatchEvent(new Event('jottr-preview-updated'));
                    if (fadeIn) {{
                        setTimeout(function () {{
                            root.classList.remove('jottr-preview-fade-in');
                        }}, fadeHoldMs);
                    }}
                }};
            </script>
            <style>
                {font_face_css}
                @page {{
                    margin: 1mm;
                }}
                @media print {{
                    body {{
                        margin: 0;
                    }}
                }}
                html.jottr-restoring-preview-scroll body {{
                    visibility: hidden;
                }}
                html.jottr-preview-fade-in body {{
                    opacity: 0;
                    transition: none;
                }}
                body {{
                    color: #202124;
                    font-family: "{preview_family}", "Segoe UI", sans-serif;
                    font-size: {preview_size}pt;
                    line-height: 1.55;
                    margin: 18px;
                    opacity: 1;
                    transition: opacity 180ms ease-out;
                    text-align: start;
                    unicode-bidi: plaintext;
                }}
                h1, h2, h3, h4, h5, h6, p, li, blockquote, th, td, div {{
                    text-align: start;
                    unicode-bidi: plaintext;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #111827;
                    font-weight: 700;
                    margin: 1.1em 0 0.45em;
                }}
                h1 {{ font-size: 30px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
                h2 {{ font-size: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 4px; }}
                h3 {{ font-size: 20px; }}
                h4 {{ font-size: 17px; }}
                h5 {{ font-size: 15px; }}
                h6 {{ font-size: 14px; color: #57606a; }}
                p {{ margin: 0 0 0.8em; }}
                pre {{
                    background: #f6f8fa;
                    border: 1px solid #d0d7de;
                    border-radius: 0px;
                    padding: 12px;
                    white-space: pre-wrap;
                    margin: 0.9em 0;
                }}
                code {{
                    font-family: "{preview_family}", "Consolas", monospace;
                    background: #f6f8fa;
                    border-radius: 0px;
                    padding: 2px 4px;
                }}
                pre code {{ background: transparent; padding: 0; }}
                .source-code-line {{
                    display: block;
                    min-height: 1.55em;
                }}
                blockquote {{
                    border-inline-start: 4px solid #d0d7de;
                    color: #57606a;
                    margin: 0.8em 0;
                    padding-inline-start: 12px;
                }}
                ul, ol {{
                    margin: 0.4em 0 0.8em 0.35em;
                    padding-inline-start: 2.2em;
                }}
                li {{ margin: 0.2em 0; }}
                .task-list-item-checkbox {{
                    margin-inline-end: 0.45em;
                    vertical-align: -0.1em;
                }}
                a {{ color: #0969da; }}
                table {{
                    border-collapse: collapse;
                    margin: 1em 0;
                    width: 100%;
                    overflow: hidden;
                }}
                th, td {{
                    border: 1px solid #d0d7de;
                    padding: 6px 10px;
                    vertical-align: top;
                }}
                th {{
                    background: #f6f8fa;
                    font-weight: 700;
                }}
                tr:nth-child(even) td {{
                    background: #fbfbfc;
                }}
                img {{
                    display: block;
                    max-width: 100%;
                    height: auto;
                    margin: 0.8em 0;
                }}
                .math-inline {{
                    white-space: nowrap;
                }}
                .math-block {{
                    margin: 1em 0;
                    overflow-x: auto;
                }}
                .admonition {{
                    border-left: 4px solid #0969da;
                    background: #f6f8fa;
                    padding: 10px 14px;
                    margin: 1em 0;
                }}
                .admonition-title {{
                    font-weight: 700;
                    margin-top: 0;
                }}
                {extension_style_html}
            </style>
            <script nonce="{nonce}">
                window.MathJax = {{
                    tex: {{
                        inlineMath: [['\\\\(', '\\\\)']],
                        displayMath: [['\\\\[', '\\\\]']],
                        processEscapes: true
                    }},
                    svg: {{
                        fontCache: 'global'
                    }},
                    startup: {{
                        typeset: false
                    }}
                }};
            </script>
            <script nonce="{nonce}" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
            {extension_head_html}
        </head>
        <body dir="{dir_attr}">
            <div id="jottr-preview-content">{body_html}</div>
            <div id="jottr-preview-extensions">{extension_body_html}</div>
        </body>
        </html>
        """

    @staticmethod
    def apply_typographer_replacements(value):
        """Apply common markdown typographer replacements."""
        replacements = {
            "(c)": "©",
            "(C)": "©",
            "(r)": "®",
            "(R)": "®",
            "(tm)": "™",
            "(TM)": "™",
            "+-": "±",
        }
        for source, replacement in replacements.items():
            value = value.replace(source, replacement)
        return value

