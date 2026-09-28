"""Settings controls: a segmented choice, color dots, and a grid of editor theme swatches."""
from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QButtonGroup, QGridLayout, QHBoxLayout, QPushButton,
    QSizePolicy, QWidget,
)


class SegmentedControl(QWidget):
    """One choice from a few options, shown side by side as a pill track.

    Options are checkable buttons named "segmentedOption"; the Organic look
    styles the track and its checked option by object name.
    """

    currentDataChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Never squeezed: a clipped option label is unreadable.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idToggled.connect(self._on_toggled)
        self._data = []

    def addOption(self, label, data):
        button = QPushButton(label)
        button.setObjectName("segmentedOption")
        button.setCheckable(True)
        button.setAutoDefault(False)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._group.addButton(button, len(self._data))
        self._data.append(data)
        self._layout.addWidget(button)
        if len(self._data) == 1:
            button.setChecked(True)
        return button

    def clear(self):
        for button in self.buttons():
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.hide()
            button.deleteLater()
        self._data = []

    def count(self):
        return len(self._data)

    def itemData(self, index):
        return self._data[index]

    def itemText(self, index):
        return self._group.button(index).text()

    def findData(self, data):
        return self._data.index(data) if data in self._data else -1

    def currentIndex(self):
        return self._group.checkedId()

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._data):
            self._group.button(index).setChecked(True)

    def buttons(self):
        return [self._group.button(index) for index in range(len(self._data))]

    def currentData(self):
        index = self._group.checkedId()
        return self._data[index] if index >= 0 else None

    def setCurrentData(self, data):
        """Check the option holding *data*; return False when there is none."""
        if data not in self._data:
            return False
        self._group.button(self._data.index(data)).setChecked(True)
        return True

    def _on_toggled(self, index, checked):
        if checked:
            self.currentDataChanged.emit(self._data[index])


class ThemeSwatch(QAbstractButton):
    """A checkable miniature page in an editor theme's colors, with its name below.

    *accents* are the Markdown heading, link and code colors; themes that
    share a page color still look different by them.
    """

    SWATCH_HEIGHT = 50
    RADIUS = 14

    def __init__(self, name, background, foreground, accents=(), parent=None):
        super().__init__(parent)
        self.setObjectName("themeSwatch")
        self.setCheckable(True)
        self.setText(name)
        self.setToolTip(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.background = QColor(background)
        self.foreground = QColor(foreground)
        self.accents = [QColor(color) for color in accents]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _label_height(self):
        return self.fontMetrics().height() + 6

    def sizeHint(self):
        # Wide enough for the whole name; eliding is a last resort.
        label = self.fontMetrics().horizontalAdvance(self.text()) + 8
        return QSize(max(96, label), self.SWATCH_HEIGHT + self._label_height())

    def minimumSizeHint(self):
        return QSize(64, self.SWATCH_HEIGHT + self._label_height())

    def paintEvent(self, event):
        palette = self.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # The ring sits inside the widget, so the page is inset by its width.
        ring = 2.0
        page = QRectF(ring, ring, self.width() - 2 * ring, self.SWATCH_HEIGHT - 2 * ring)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background)
        painter.drawRoundedRect(page, self.RADIUS - ring, self.RADIUS - ring)

        # A heading, then two body lines each ending in a link or code span.
        # Without accents every segment falls back to the text color.
        heading, link, code = (self.accents + [self.foreground] * 3)[:3]
        body = QColor(self.foreground)
        body.setAlphaF(0.5)
        lines = (
            ((0.6, heading),),
            ((0.5, body), (0.35, link)),
            ((0.3, body), (0.3, code)),
        )
        bar = 5.0
        gap = 4.0
        top = page.top() + 10
        span = page.width() - 20
        for segments in lines:
            left = page.left() + 10
            for fraction, color in segments:
                painter.setBrush(color)
                width = span * fraction
                painter.drawRoundedRect(QRectF(left, top, width, bar), bar / 2, bar / 2)
                left += width + gap
            top += bar + 5

        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.isChecked():
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight), ring))
            outline = page.adjusted(-ring / 2, -ring / 2, ring / 2, ring / 2)
            painter.drawRoundedRect(outline, self.RADIUS - ring / 2, self.RADIUS - ring / 2)
        else:
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid), 1))
            painter.drawRoundedRect(page.adjusted(0.5, 0.5, -0.5, -0.5),
                                    self.RADIUS - ring, self.RADIUS - ring)
        if self.hasFocus():
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight), 1,
                                Qt.PenStyle.DotLine))
            painter.drawRoundedRect(page.adjusted(3, 3, -3, -3),
                                    self.RADIUS - 4, self.RADIUS - 4)

        painter.setPen(palette.color(
            QPalette.ColorRole.WindowText if self.isChecked()
            else QPalette.ColorRole.PlaceholderText
        ))
        label = QRectF(page.left() + 2, self.SWATCH_HEIGHT, page.width() - 2,
                       self._label_height())
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, int(label.width())
        )
        painter.drawText(label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, text)
        painter.end()


class ThemeSwatchGrid(QWidget):
    """Editor themes as a grid of swatches; exactly one is current."""

    themeChanged = pyqtSignal(str)
    # Every click, including on the current theme, so a popup can close.
    themeClicked = pyqtSignal(str)

    @classmethod
    def fromThemes(cls, themes, columns=5, parent=None):
        """A grid for a ThemeManager.get_themes() mapping, light pages first."""
        ordered = sorted(
            themes,
            key=lambda name: QColor(themes[name]["editor"]["background"]).lightnessF() < 0.5,
        )

        def entry(name):
            editor = themes[name]["editor"]
            syntax = themes[name].get("syntax") or {}
            # The colors Markdown headings, links and inline code are drawn in.
            accents = [
                syntax[key]
                for key in ("keyword", "function", "constant")
                if key in syntax
            ]
            return name, editor["background"], editor["foreground"], accents

        return cls((entry(name) for name in ordered), columns, parent)

    def __init__(self, themes, columns=5, parent=None):
        """*themes* is an iterable of (name, background, foreground[, accents])."""
        super().__init__(parent)
        self.setObjectName("themeSwatchGrid")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(16)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._names = []
        self._columns = columns
        for index, (name, background, foreground, *accents) in enumerate(themes):
            swatch = ThemeSwatch(name, background, foreground, *accents)
            self._group.addButton(swatch, index)
            self._names.append(name)
            layout.addWidget(swatch, index // columns, index % columns)
        for column in range(columns):
            layout.setColumnStretch(column, 1)
        self._group.idToggled.connect(self._on_toggled)
        self._group.idClicked.connect(lambda index: self.themeClicked.emit(self._names[index]))

    def sizeHint(self):
        # Columns share width equally, so each needs the widest swatch's.
        hint = super().sizeHint()
        swatches = self._group.buttons()
        if not swatches:
            return hint
        layout = self.layout()
        columns = min(self._columns, len(swatches))
        margins = layout.contentsMargins() + self.contentsMargins()
        width = (
            columns * max(swatch.sizeHint().width() for swatch in swatches)
            + (columns - 1) * layout.horizontalSpacing()
            + margins.left() + margins.right()
        )
        return QSize(max(hint.width(), width), hint.height())

    def themeNames(self):
        return list(self._names)

    def swatch(self, name):
        return self._group.button(self._names.index(name)) if name in self._names else None

    def currentTheme(self):
        index = self._group.checkedId()
        return self._names[index] if index >= 0 else ""

    def setCurrentTheme(self, name):
        """Check *name*'s swatch; return False when there is no such theme."""
        swatch = self.swatch(name)
        if swatch is None:
            return False
        swatch.setChecked(True)
        return True

    def _on_toggled(self, index, checked):
        if checked:
            self.themeChanged.emit(self._names[index])


class ColorSwatch(QAbstractButton):
    """A checkable round color dot; checked adds a ring around it."""

    DIAMETER = 18
    RING = 4

    def __init__(self, label, color, parent=None):
        """*color* is a QColor or a callable returning one (read when painting)."""
        super().__init__(parent)
        self.setObjectName("colorSwatch")
        self.setCheckable(True)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._color = color
        side = self.DIAMETER + 2 * self.RING
        self.setFixedSize(side, side)

    def color(self):
        return QColor(self._color() if callable(self._color) else self._color)

    def paintEvent(self, event):
        palette = self.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        dot = QRectF(self.rect()).adjusted(self.RING, self.RING, -self.RING, -self.RING)
        if self.isChecked() or self.hasFocus():
            painter.setPen(QPen(palette.color(QPalette.ColorRole.WindowText),
                                2 if self.isChecked() else 1,
                                Qt.PenStyle.SolidLine if self.isChecked() else Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(outer)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid), 1))
        painter.setBrush(self.color())
        painter.drawEllipse(dot)
        painter.end()


class ColorSwatchPicker(QWidget):
    """One choice from a row of color dots; the API mirrors SegmentedControl."""

    currentDataChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("colorSwatchPicker")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idToggled.connect(self._on_toggled)
        self._data = []

    def addOption(self, label, data, color):
        swatch = ColorSwatch(label, color)
        self._group.addButton(swatch, len(self._data))
        self._data.append(data)
        self._layout.addWidget(swatch)
        if len(self._data) == 1:
            swatch.setChecked(True)
        return swatch

    def count(self):
        return len(self._data)

    def itemData(self, index):
        return self._data[index]

    def buttons(self):
        return [self._group.button(index) for index in range(len(self._data))]

    def currentData(self):
        index = self._group.checkedId()
        return self._data[index] if index >= 0 else None

    def setCurrentData(self, data):
        if data not in self._data:
            return False
        self._group.button(self._data.index(data)).setChecked(True)
        return True

    def _on_toggled(self, index, checked):
        if checked:
            self.currentDataChanged.emit(self._data[index])
