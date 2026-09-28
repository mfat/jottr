"""Plugins page painting: the list's plugin cards and the round initial avatars."""
from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QWidget

from jottr.theme_manager import ThemeManager

# Item data: a dict with title, status, status_kind, description, meta, initial.
PLUGIN_CARD_ROLE = Qt.ItemDataRole.UserRole + 1

_PAD = 12
_AVATAR = 38
_GAP = 12
_LINE_GAP = 3


def plugin_initial(title):
    """The first letter or digit of *title*, uppercased, for its avatar."""
    for char in title or "":
        if char.isalnum():
            return char.upper()
    return "?"


def _scaled(font, factor, weight=None):
    scaled = QFont(font)
    size = font.pointSizeF() if font.pointSizeF() > 0 else 10.0
    scaled.setPointSizeF(max(6.0, size * factor))
    if weight is not None:
        scaled.setWeight(weight)
    return scaled


class PluginCardDelegate(QStyledItemDelegate):
    """Paints each plugin row as a card: avatar, name and status, description, meta.

    Organic fills the selected card with the accent; Native uses the palette
    highlight like any list row. Colors come from
    *tokens_for*, a callable returning ThemeManager.chrome_tokens.
    """

    def __init__(self, view, tokens_for):
        super().__init__(view)
        self.view = view
        self.tokens_for = tokens_for

    # Layout.

    def _fonts(self, base):
        return (
            _scaled(base, 1.0, QFont.Weight.Bold),      # title
            _scaled(base, 0.8, QFont.Weight.Bold),      # status badge
            _scaled(base, 0.9),                         # description
            _scaled(base, 0.82),                        # meta
            _scaled(base, 1.2, QFont.Weight.DemiBold),  # avatar initial
        )

    def _badge_size(self, font, text):
        metrics = QFontMetrics(font)
        return QSize(metrics.horizontalAdvance(text) + 16, metrics.height() + 4)

    def _text_width(self, width):
        return max(40, width - 2 * _PAD - _AVATAR - _GAP)

    def _badge_below(self, title_font, title, text_width, badge):
        """True when the name's longest word won't fit beside the badge."""
        words = (title or "").split() or [""]
        longest = max(QFontMetrics(title_font).horizontalAdvance(word) for word in words)
        return longest > text_width - badge.width() - 6

    def sizeHint(self, option, index):
        card = index.data(PLUGIN_CARD_ROLE) or {}
        width = self.view.viewport().width() - 2 * self.view.spacing()
        title_font, badge_font, desc_font, meta_font, _initial = self._fonts(option.font)
        text_width = self._text_width(width)
        badge = self._badge_size(badge_font, card.get("status", ""))
        below = self._badge_below(title_font, card.get("title", ""), text_width, badge)
        title_width = text_width if below else max(20, text_width - badge.width() - 6)
        title_only = QFontMetrics(title_font).boundingRect(
            QRect(0, 0, title_width, 10000), Qt.TextFlag.TextWordWrap, card.get("title", "")
        ).height()
        if below:
            title_height = title_only + _LINE_GAP + badge.height()
        else:
            title_height = max(title_only, badge.height())
        desc_height = QFontMetrics(desc_font).boundingRect(
            QRect(0, 0, text_width, 10000), Qt.TextFlag.TextWordWrap,
            card.get("description", "")
        ).height()
        meta_height = QFontMetrics(meta_font).height()
        height = _PAD + title_height + _LINE_GAP + desc_height + _LINE_GAP + meta_height + _PAD
        return QSize(max(0, width), max(height, 2 * _PAD + _AVATAR))

    # Painting.

    def paint(self, painter, option, index):
        card = index.data(PLUGIN_CARD_ROLE) or {}
        t = self.tokens_for()
        organic = ThemeManager.interface_look() == "organic"
        palette = option.palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        title_font, badge_font, desc_font, meta_font, initial_font = self._fonts(option.font)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(option.rect).adjusted(1, 1, -1, -1)
        radius = 16 if organic else 4

        # Colors for this row's state.
        ink, muted, faint = t["ink"], t["muted"], t["faint"]
        avatar_fill, avatar_ink = t["code"], t["muted"]
        if selected and organic:
            fill = t["act"]
            ink = t["on_act"]
            muted, faint = QColor(ink), QColor(ink)
            muted.setAlphaF(0.85)
            faint.setAlphaF(0.7)
            avatar_fill, avatar_ink = ink, fill
        elif selected:
            fill = palette.color(QPalette.ColorRole.Highlight)
            ink = muted = faint = palette.color(QPalette.ColorRole.HighlightedText)
            avatar_fill, avatar_ink = ink, fill
        elif hovered:
            fill = t["hover"]
        else:
            fill = None
        if fill is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, radius, radius)

        # Avatar.
        avatar = QRectF(rect.left() + _PAD - 1, rect.top() + _PAD - 1, _AVATAR, _AVATAR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(avatar_fill)
        painter.drawEllipse(avatar)
        painter.setPen(avatar_ink)
        painter.setFont(initial_font)
        painter.drawText(avatar, Qt.AlignmentFlag.AlignCenter, card.get("initial", "?"))

        # Name, with the status badge at its right.
        x = int(avatar.right()) + _GAP
        right = int(rect.right()) - _PAD
        y = int(rect.top()) + _PAD - 1
        status = card.get("status", "")
        badge = self._badge_size(badge_font, status)
        # The badge sits right of the name, or under it when a word of the
        # name would otherwise be cut.
        below = self._badge_below(title_font, card.get("title", ""), right - x, badge)
        painter.setFont(title_font)
        painter.setPen(ink)
        title_width = right - x if below else max(20, right - x - badge.width() - 6)
        title_rect = QRect(x, y, title_width, 10000)
        title_bounds = painter.boundingRect(title_rect, Qt.TextFlag.TextWordWrap,
                                            card.get("title", ""))
        painter.drawText(title_rect, Qt.TextFlag.TextWordWrap, card.get("title", ""))
        if below:
            badge_rect = QRectF(x, y + title_bounds.height() + _LINE_GAP,
                                badge.width(), badge.height())
            y += title_bounds.height() + _LINE_GAP + badge.height() + _LINE_GAP
        else:
            badge_rect = QRectF(right - badge.width(), y, badge.width(), badge.height())
            y += max(title_bounds.height(), badge.height()) + _LINE_GAP
        if status:
            self._paint_badge(painter, badge_rect, badge_font, status,
                              card.get("status_kind", ""), t, ink, selected)

        # Description, then version and channel.
        painter.setFont(desc_font)
        painter.setPen(muted)
        desc_rect = QRect(x, y, max(20, right - x), 10000)
        desc_bounds = painter.boundingRect(desc_rect, Qt.TextFlag.TextWordWrap,
                                           card.get("description", ""))
        painter.drawText(desc_rect, Qt.TextFlag.TextWordWrap, card.get("description", ""))
        y += desc_bounds.height() + _LINE_GAP
        painter.setFont(meta_font)
        painter.setPen(faint)
        meta = QFontMetrics(meta_font).elidedText(
            card.get("meta", ""), Qt.TextElideMode.ElideRight, max(20, right - x)
        )
        painter.drawText(QRect(x, y, max(20, right - x), QFontMetrics(meta_font).height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)
        painter.restore()

    def _paint_badge(self, painter, rect, font, text, kind, t, ink, on_highlight):
        painter.setFont(font)
        if on_highlight:
            painter.setPen(QPen(ink, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            color = ink
        elif kind == "enabled":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(t["act_soft"])
            color = t["act_ink"]
        elif kind == "error":
            painter.setPen(QPen(t["danger"], 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            color = t["danger"]
        else:
            painter.setPen(QPen(t["line"], 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            color = t["muted"]
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                rect.height() / 2, rect.height() / 2)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class PluginAvatar(QWidget):
    """A filled circle with a plugin's initial, in the accent colors."""

    def __init__(self, size, tokens_for, parent=None):
        super().__init__(parent)
        self.setObjectName("pluginAvatar")
        self.setFixedSize(size, size)
        self.tokens_for = tokens_for
        self.initial = ""

    def set_initial(self, initial):
        self.initial = initial
        self.setVisible(bool(initial))
        self.update()

    def paintEvent(self, event):
        t = self.tokens_for()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(t["act"])
        painter.drawEllipse(QRectF(self.rect()))
        painter.setPen(QColor(t["on_act"]))
        painter.setFont(_scaled(self.font(), 1.7, QFont.Weight.DemiBold))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self.initial)
        painter.end()
