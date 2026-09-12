"""Markdown preview rendering and scroll sync for EditorTab."""
import base64
import html
import json
import mimetypes
import os
import re
import tempfile
import time

from PyQt6.QtCore import QTimer, QUrl, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWebEngineCore import QWebEnginePage

try:
    import markdown as markdown_lib
    MARKDOWN_LIB_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    markdown_lib = None
    MARKDOWN_LIB_AVAILABLE = False


class MarkdownPreviewPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(f"Markdown preview JS: {message} ({source_id}:{line_number})")


class MarkdownPreviewMixin:
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
            tab_mod.MarkdownPreviewPage = MarkdownPreviewPage
            PageCls = MarkdownPreviewPage

        placeholder = getattr(self, "markdown_preview", None)
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
        view.installEventFilter(self)
        if hasattr(view, "loadFinished"):
            view.loadFinished.connect(self.render_markdown_preview_scripts)

        if hasattr(self, "markdown_splitter") and placeholder is not None:
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
        view.setVisible(was_visible)
        if hasattr(self, "apply_language_direction"):
            self.apply_language_direction()
        return view

    def is_markdown_file(self, file_path=None):
        """Return True when a path should be treated as markdown."""
        path = file_path or self.current_file or ""
        return os.path.splitext(path.lower())[1] in ('.md', '.markdown', '.mdown', '.mkd')

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
        self.animate_widget_visibility(self.markdown_preview, visible, fade=False)
        self.markdown_preview.setMinimumWidth(240 if visible else 0)
        if visible:
            if self.preview_scroll_timer:
                self.preview_scroll_timer.start()
            if hasattr(self, 'markdown_splitter') and self.markdown_splitter.sizes()[1] < 100:
                self.markdown_splitter.setSizes([600, 600])
            self.update_markdown_preview()
        else:
            if self.preview_scroll_timer:
                self.preview_scroll_timer.stop()
        if save_state:
            self.save_pane_states()

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

    def update_markdown_preview(self):
        """Render editor markdown into the preview pane."""
        if not self.markdown_preview_visible:
            return
        if not getattr(self, "_markdown_preview_ready", False):
            self.ensure_markdown_preview()

        if self.current_file:
            content_base_url = QUrl.fromLocalFile(os.path.dirname(self.current_file) + os.sep).toString()
        else:
            content_base_url = QUrl.fromLocalFile(os.getcwd() + os.sep).toString()

        def render_preview(scroll_ratio):
            try:
                scroll_ratio = max(0.0, min(1.0, float(scroll_ratio)))
            except (TypeError, ValueError):
                scroll_ratio = self.get_editor_scroll_ratio()

            self.write_markdown_preview_file(
                self.render_markdown_html(
                    self.editor.toPlainText(),
                    content_base_url,
                    initial_scroll_ratio=scroll_ratio
                )
            )
            self.markdown_preview_loading = True
            self.markdown_preview.load(QUrl.fromLocalFile(self.markdown_preview_file))

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

    def write_markdown_preview_file(self, preview_html):
        """Write the rendered preview to a normal local HTML file for WebEngine."""
        with open(self.markdown_preview_file, 'w', encoding='utf-8') as preview_file:
            preview_file.write(preview_html)

    def render_markdown_preview_scripts(self, *args):
        """Run preview scripts that need the WebEngine page to finish loading."""
        if not getattr(self, "_markdown_preview_ready", False) or not self.markdown_preview_visible:
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

    def render_markdown_html(self, text, content_base_url="", initial_scroll_ratio=None):
        """Render a practical markdown subset with stable heading and code styling."""
        if MARKDOWN_LIB_AVAILABLE:
            return self.render_markdown_html_with_library(text, content_base_url, initial_scroll_ratio)

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
            cells = EditorTab.split_table_row(value)
            if len(cells) < 2:
                return False
            return all(re.match(r'^:?-{3,}:?$', cell.strip()) for cell in cells)

        def table_alignments(separator):
            alignments = []
            for cell in EditorTab.split_table_row(separator):
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
                source = os.path.join(os.path.dirname(current_file), source)
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
            value = EditorTab.apply_typographer_replacements(value)
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
                table_rows = [EditorTab.split_table_row(stripped), EditorTab.split_table_row(lines[line_index + 1].strip())]
                alignments = table_alignments(lines[line_index + 1].strip())
                line_index += 2
                while line_index < len(lines) and "|" in lines[line_index].strip():
                    table_rows.append(EditorTab.split_table_row(lines[line_index].strip()))
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

        return f"""
        <html>
        <head>
            <style>
                body {{
                    color: #202124;
                    font-family: "DejaVu Sans", "Segoe UI", sans-serif;
                    font-size: 14px;
                    line-height: 1.55;
                    margin: 18px;
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
                    font-family: "DejaVu Sans Mono", "Consolas", monospace;
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
                    border-left: 4px solid #d0d7de;
                    color: #57606a;
                    margin: 0.8em 0;
                    padding-left: 12px;
                }}
                ul, ol {{ margin: 0.4em 0 0.8em 1.4em; }}
                li {{ margin: 0.2em 0; }}
                .task-list-item-checkbox {{
                    margin-right: 0.45em;
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
            </style>
            <script>
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
            <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        </head>
        <body>
            {''.join(body)}
        </body>
        </html>
        """

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

    def render_markdown_html_with_library(self, text, content_base_url="", initial_scroll_ratio=None):
        """Render markdown using Python-Markdown with local preview enhancements."""
        prepared_text = self.preprocess_markdown_extensions(text)
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
        body_html = self.apply_markdown_extensions(body_html)
        body_html = self.add_source_line_anchors(body_html, text)
        body_html = self.add_code_line_anchors(body_html)

        return self.wrap_markdown_preview_html(body_html, content_base_url, initial_scroll_ratio)

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
        """Preprocess syntax that Python-Markdown does not handle by default."""
        text, fenced_blocks = self.stash_fenced_code_blocks(text)
        text = self.preprocess_task_lists(text)
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text, flags=re.DOTALL)
        text = self.apply_typographer_replacements(text)
        text = self.apply_emoji_shortcodes(text)
        text = self.preprocess_math_blocks(text)
        text = re.sub(
            r'(?<!\\)\$(?!\$)(.+?)(?<!\\)\$',
            lambda match: f'<span class="math-inline">\\({html.escape(match.group(1).strip())}\\)</span>',
            text
        )
        text = self.restore_fenced_code_blocks(text, fenced_blocks)
        return text

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

    def wrap_markdown_preview_html(self, body_html, content_base_url="", initial_scroll_ratio=None):
        """Wrap rendered body HTML in Jottr preview CSS and scripts."""
        extension_head_html = self.render_markdown_extension_head_html()
        extension_style_html = self.render_markdown_extension_style_html()
        extension_body_html = self.render_markdown_extension_body_html()
        base_tag = f'<base href="{html.escape(content_base_url, quote=True)}">' if content_base_url else ''
        preview_font = QFont(getattr(self, "current_font", self.settings_manager.get_font("editor")))
        preview_family = html.escape(preview_font.family().replace("\\", "\\\\").replace('"', '\\"'), quote=True)
        preview_size = max(8, preview_font.pointSize() if preview_font.pointSize() > 0 else 14)
        dir_attr = "auto"
        try:
            restore_scroll_ratio = max(0.0, min(1.0, float(initial_scroll_ratio or 0)))
        except (TypeError, ValueError):
            restore_scroll_ratio = 0.0
        restore_scroll_ratio_json = json.dumps(restore_scroll_ratio)
        return f"""
        <html dir="{dir_attr}">
        <head>
            {base_tag}
            <script>
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
            </script>
            <style>
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
                body {{
                    color: #202124;
                    font-family: "{preview_family}", "Segoe UI", sans-serif;
                    font-size: {preview_size}pt;
                    line-height: 1.55;
                    margin: 18px;
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
            <script>
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
            <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
            {extension_head_html}
        </head>
        <body dir="{dir_attr}">
            {body_html}
            {extension_body_html}
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

