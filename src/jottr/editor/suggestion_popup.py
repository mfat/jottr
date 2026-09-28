"""Completion popup: snippet triggers and dictionary words under the cursor."""
from PyQt6.QtCore import QEvent, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _


class SuggestionPopup(QWidget):
    """A rounded card of suggestion rows, painted in the chrome colors.

    Each row is a snippet (its trigger as a monospace chip, then the start of
    its text) or a plain word. The row Tab or Enter would insert is filled
    and carries that key as a hint. Rows are painted, not widgets, so the
    app stylesheet never reaches them.

    It never takes focus, so nothing closes it for free: while shown it
    calls *on_dismiss* on a click anywhere outside it, when the editor loses
    focus, or when the app goes inactive.
    """

    SHADOW = 10          # transparent margin the drop shadow is drawn in
    PADDING = 5          # card edge to rows
    ROW_HEIGHT = 34
    MIN_WIDTH = 250
    MAX_WIDTH = 460

    def __init__(self, parent, rows, theme, font, on_activate, on_dismiss):
        """*rows* is a list of (kind, trigger, text); kind is "snippet" or "word"."""
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("suggestionPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.rows = list(rows)
        self.on_activate = on_activate
        self.on_dismiss = on_dismiss
        self.selected = -1
        self.hint_row = -1
        self.hint_key = ""
        self._hover = -1
        self._set_colors(theme)
        self.title_font = QFont(font)
        self.title_font.setWeight(QFont.Weight.DemiBold)
        self.word_font = QFont(font)
        self.chip_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.chip_font.setPointSizeF(max(7.0, font.pointSizeF() * 0.86))
        self.key_font = QFont(font)
        self.key_font.setPointSizeF(max(7.0, font.pointSizeF() * 0.78))
        self.resize(self.sizeHint())

    def _set_colors(self, theme):
        tokens = theme.get("organic") if isinstance(theme, dict) else None
        app = theme["app"]
        organic = bool(tokens)
        # Native has no pill tokens; take the nearest plain chrome colors.
        source = tokens or {
            "pane": app["surface"],
            "paper": app["background"],
            "line": app["border"],
            "ink": app["text"],
            "act_soft": app["surface_active"],
            "act_ink": app["text"],
        }
        self.pane = ThemeManager.css_color(source["pane"])
        self.paper = ThemeManager.css_color(source["paper"])
        self.line = ThemeManager.css_color(source["line"])
        self.ink = ThemeManager.css_color(source["ink"])
        self.act_soft = ThemeManager.css_color(source["act_soft"])
        self.act_ink = ThemeManager.css_color(source["act_ink"])
        self.card_radius = 16 if organic else 6
        self.row_radius = 11 if organic else 4
        self.chip_radius = 9 if organic else 3
        self.shadow_alpha = 34 if ThemeManager.theme_is_dark(theme) else 22

    # Geometry.

    def _chip_width(self, trigger):
        return QFontMetrics(self.chip_font).horizontalAdvance(trigger) + 16

    def _key_width(self):
        return QFontMetrics(self.key_font).horizontalAdvance(_("Enter")) + 12

    def sizeHint(self):
        title = QFontMetrics(self.title_font)
        content = 0
        for kind, trigger, text in self.rows:
            width = 20 + title.horizontalAdvance(text) + 10 + self._key_width()
            if kind == "snippet":
                width += self._chip_width(trigger) + 10
            content = max(content, width)
        width = min(self.MAX_WIDTH, max(self.MIN_WIDTH, content))
        height = len(self.rows) * self.ROW_HEIGHT + 2 * self.PADDING
        return QSize(width + 2 * self.SHADOW, height + 2 * self.SHADOW)

    def card_rect(self):
        return QRectF(self.rect()).adjusted(
            self.SHADOW, self.SHADOW - 3, -self.SHADOW, -self.SHADOW - 3
        )

    def row_rect(self, index):
        card = self.card_rect()
        return QRectF(
            card.left() + self.PADDING,
            card.top() + self.PADDING + index * self.ROW_HEIGHT,
            card.width() - 2 * self.PADDING,
            self.ROW_HEIGHT,
        )

    def row_at(self, pos):
        for index in range(len(self.rows)):
            if self.row_rect(index).contains(pos.toPointF()):
                return index
        return -1

    # State.

    def set_selected(self, index, key=""):
        """Fill row *index* (-1 for none) and show *key* on it as a hint."""
        self.selected = index
        self.hint_row = index
        self.hint_key = key
        self.update()

    # Dismissal.

    def showEvent(self, event):
        super().showEvent(event)
        app = QApplication.instance()
        app.installEventFilter(self)
        app.applicationStateChanged.connect(self._on_app_state_changed)

    def hideEvent(self, event):
        app = QApplication.instance()
        app.removeEventFilter(self)
        try:
            app.applicationStateChanged.disconnect(self._on_app_state_changed)
        except TypeError:
            pass
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and isinstance(obj, QWidget):
            if obj is not self and not self.isAncestorOf(obj):
                self.on_dismiss()
        elif kind == QEvent.Type.FocusOut and obj is self.parent():
            self.on_dismiss()
        return False

    def _on_app_state_changed(self, state):
        if state != Qt.ApplicationState.ApplicationActive:
            self.on_dismiss()

    # Painting.

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = self.card_rect()

        # A soft shadow below the card: stacked, widening translucent fills.
        painter.setPen(Qt.PenStyle.NoPen)
        for step in range(1, self.SHADOW):
            shade = QColor(0, 0, 0, max(1, self.shadow_alpha // (step + 1)))
            painter.setBrush(shade)
            spread = step * 0.8
            painter.drawRoundedRect(
                card.adjusted(-spread, -spread + 3, spread, spread + 3),
                self.card_radius + spread, self.card_radius + spread,
            )

        painter.setBrush(self.pane)
        painter.setPen(self.line)
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5),
                                self.card_radius, self.card_radius)

        for index, row in enumerate(self.rows):
            self._paint_row(painter, index, row)
        painter.end()

    def _paint_row(self, painter, index, row):
        kind, trigger, text = row
        rect = self.row_rect(index)
        filled = index == self.selected
        if filled or index == self._hover:
            fill = QColor(self.act_soft)
            if not filled:
                fill.setAlphaF(fill.alphaF() * 0.55)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, self.row_radius, self.row_radius)
        ink = self.act_ink if filled else self.ink
        x = rect.left() + 10
        right = rect.right() - 10

        if index == self.hint_row and self.hint_key:
            painter.setFont(self.key_font)
            key_height = QFontMetrics(self.key_font).height() + 2
            key_width = QFontMetrics(self.key_font).horizontalAdvance(self.hint_key) + 12
            key = QRectF(right - key_width, rect.center().y() - key_height / 2,
                         key_width, key_height)
            faded = QColor(ink)
            faded.setAlphaF(0.8)
            painter.setPen(faded)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(key.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
            painter.drawText(key, Qt.AlignmentFlag.AlignCenter, self.hint_key)
            right = key.left() - 10

        if kind == "snippet":
            painter.setFont(self.chip_font)
            chip_height = QFontMetrics(self.chip_font).height() + 4
            chip = QRectF(x, rect.center().y() - chip_height / 2,
                          self._chip_width(trigger), chip_height)
            # Paper on the filled row, as in the design; elsewhere the card
            # is often paper-colored itself, so tint the chip with ink.
            chip_fill = QColor(self.paper)
            if not filled:
                chip_fill = QColor(self.ink)
                chip_fill.setAlphaF(0.08)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(chip_fill)
            painter.drawRoundedRect(chip, self.chip_radius, self.chip_radius)
            painter.setPen(ink)
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, trigger)
            x = chip.right() + 10

        font = self.title_font if kind == "snippet" else self.word_font
        painter.setFont(font)
        painter.setPen(ink)
        label = QRectF(x, rect.top(), max(0.0, right - x), rect.height())
        elided = QFontMetrics(font).elidedText(
            text, Qt.TextElideMode.ElideRight, int(label.width())
        )
        painter.drawText(label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         elided)

    # Mouse.

    def mouseMoveEvent(self, event):
        hover = self.row_at(event.position().toPoint())
        if hover != self._hover:
            self._hover = hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        index = self.row_at(event.position().toPoint())
        if index >= 0:
            self.on_activate(self.rows[index][1])
            event.accept()
            return
        super().mousePressEvent(event)
