"""Shared tag drawing; use the editor's existing semantic class colors."""
from PySide6.QtCore import Qt, QRect, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from shoggoth.ui.compact_widgets import CLASS_CHIP_COLORS, class_label
from shoggoth.midnight.tags import is_secondary


def tag_label(tag):
    return f"{tag['name']} (Secondary)" if is_secondary(tag) else tag['name']


def tag_details(tag):
    pips = ', '.join(class_label(pip) for pip in tag['pips'])
    label = tag_label(tag)
    return f"{label} — {pips}" if pips else label


def tag_pips_html(tag):
    return '&#8201;'.join(f'<span style="color:{CLASS_CHIP_COLORS[pip][0]}">●</span>'
                         for pip in tag['pips'])


def tag_icon(tag):
    """A fixed-size swatch can represent arbitrarily many ordered/repeated pips."""
    pixmap = QPixmap(36, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    paint_badge(painter, QRectF(0, 0, 36, 16), tag, '')
    painter.end()
    return QIcon(pixmap)


def badge_font(font, height):
    font = QFont(font)
    font.setBold(True)
    font.setPixelSize(max(8, int(height) - 3))
    return font


def paint_badge(painter, rect, tag, text):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    shape = QPainterPath()
    radius = min(4, rect.height() / 4)
    shape.addRoundedRect(rect, radius, radius)
    painter.setClipPath(shape, Qt.IntersectClip)
    colors = [CLASS_CHIP_COLORS[pip][0] for pip in tag['pips']] or ['#535861']
    width = rect.width() / len(colors)
    for index, color in enumerate(colors):
        painter.fillRect(QRectF(rect.left() + index * width, rect.top(), width + 0.5,
                                rect.height()), QColor(color))
    # A dark outline keeps the abbreviation legible across every class color.
    if text:
        font = badge_font(painter.font(), rect.height())
        painter.setFont(font)
        metrics = painter.fontMetrics()
        path = QPainterPath()
        path.addText(rect.center().x() - metrics.horizontalAdvance(text) / 2,
                     rect.center().y() + (metrics.ascent() - metrics.descent()) / 2,
                     font, text)
        painter.strokePath(path, QPen(QColor(0, 0, 0, 190), 1.5))
        painter.fillPath(path, Qt.white)
    painter.restore()


class TagChip(QWidget):
    """Full tag name followed by the actual pips, for the card editor/preview."""

    def __init__(self, tag, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.setToolTip(tag_details(tag))
        self.setAccessibleName(tag_details(tag))
        policy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.tag['name']) + 18 + 13 * len(self.tag['pips']),
                     max(26, metrics.height() + 8))

    def minimumSizeHint(self):
        return QSize(1, self.sizeHint().height())

    def _wrapped_name(self, width):
        area = QRect(0, 0, max(1, width - 16), 0)
        flags = Qt.TextWordWrap
        bounds = self.fontMetrics().boundingRect(area, flags, self.tag['name'])
        if bounds.width() > area.width():
            flags = Qt.TextWrapAnywhere
            bounds = self.fontMetrics().boundingRect(area, flags, self.tag['name'])
        return bounds, flags

    def heightForWidth(self, width):
        if width >= self.sizeHint().width():
            return self.sizeHint().height()
        columns = max(1, (width - 16) // 13)
        pip_rows = (len(self.tag['pips']) + columns - 1) // columns
        name_rect, _ = self._wrapped_name(width)
        return max(self.sizeHint().height(), name_rect.height() + 8 + pip_rows * 13)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.palette().mid().color(), 1)
        if is_secondary(self.tag):
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(self.palette().alternateBase())
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)
        painter.setPen(self.palette().text().color())
        wrapped = self.width() < self.sizeHint().width()
        if wrapped:
            name_rect, flags = self._wrapped_name(self.width())
            name_rect.translate(8, 4)
            painter.drawText(name_rect, flags, self.tag['name'])
            x, y = 8, name_rect.bottom() + 4
        else:
            painter.drawText(self.rect().adjusted(8, 0, -8, 0), Qt.AlignVCenter, self.tag['name'])
            x = self.fontMetrics().horizontalAdvance(self.tag['name']) + 13
            y = (self.height() - 9) / 2
        for pip in self.tag['pips']:
            if wrapped and x + 9 > self.width() - 8 and x > 8:
                x = 8
                y += 13
            painter.setPen(QPen(self.palette().mid().color(), 0.5))
            painter.setBrush(QColor(CLASS_CHIP_COLORS[pip][0]))
            painter.drawEllipse(QRectF(x, y, 9, 9))
            x += 13
