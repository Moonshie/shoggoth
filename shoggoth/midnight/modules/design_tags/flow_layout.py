"""A native height-for-width layout for the card's wrapping tag chips."""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, QSize
from PySide6.QtWidgets import QLayout, QScrollArea


class TagFlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._scroll_area = None
        self._viewport = None
        self._viewport_width = None
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(5)
        if parent is not None:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Show:
            ancestor = watched.parentWidget()
            while ancestor is not None:
                if isinstance(ancestor, QScrollArea):
                    self._scroll_area = ancestor
                    self._viewport = ancestor.viewport()
                    self._viewport.installEventFilter(self)
                    self._fit_viewport()
                    break
                ancestor = ancestor.parentWidget()
        elif watched is self._viewport and event.type() == QEvent.Resize:
            self._fit_viewport()
        return super().eventFilter(watched, event)

    def _fit_viewport(self):
        # Other card fields can force the form wider than its scroll viewport.
        # Wrap tags within what is visible, using native resize notifications.
        viewport = self._viewport
        left = self.parentWidget().mapTo(viewport, QPoint()).x()
        left += self._scroll_area.horizontalScrollBar().value()
        width = max(1, viewport.width() - max(0, left) - 8)
        if self._viewport_width != width:
            self._viewport_width = width
            self.invalidate()
            self.parentWidget().updateGeometry()

    def addItem(self, item):
        self._items.append(item)
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), place=False)

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, place=True)

    def _arrange(self, rect, *, place):
        margins = self.contentsMargins()
        area = rect.marginsRemoved(margins)
        if self._viewport_width is not None:
            area.setWidth(min(area.width(), self._viewport_width))
        x, y, row_height = area.left(), area.top(), 0
        spacing = self.spacing()
        for item in self._items:
            width = min(item.sizeHint().width(), max(1, area.width()))
            if row_height and x + width > area.left() + area.width():
                x = area.left()
                y += row_height + spacing
                row_height = 0
            height = item.heightForWidth(width) if item.hasHeightForWidth() else item.sizeHint().height()
            if place:
                item.setGeometry(QRect(x, y, width, height))
            x += width + spacing
            row_height = max(row_height, height)
        return y + row_height + margins.bottom() - rect.top()
