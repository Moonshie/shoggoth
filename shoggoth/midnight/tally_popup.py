"""Fast local hover and a pinned, live tally panel for tree header icons."""
import weakref

from PySide6.QtCore import Qt, QEvent, QModelIndex, QObject, QPoint, QPersistentModelIndex, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QHelpEvent, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QStyleOptionViewItem, QToolButton,
    QToolTip, QVBoxLayout,
)

HOVER_DELAY_MS = 120


class PinnedTallyPopup(QFrame):
    closed = Signal()

    def __init__(self, tree):
        super().__init__(tree, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFrameShape(QFrame.StyledPanel)
        self.setWindowTitle('Pinned design tags')
        palette = self.palette()
        palette.setColor(QPalette.Window, palette.color(QPalette.ToolTipBase))
        palette.setColor(QPalette.Base, palette.color(QPalette.ToolTipBase))
        palette.setColor(QPalette.WindowText, palette.color(QPalette.ToolTipText))
        palette.setColor(QPalette.Text, palette.color(QPalette.ToolTipText))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        header = QHBoxLayout()
        header.addWidget(QLabel('Pinned'))
        header.addStretch()
        self.close_button = QToolButton()
        self.close_button.setText('×')
        self.close_button.setAutoRaise(True)
        self.close_button.setToolTip('Close pinned tags (Esc)')
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        self.label = QLabel()
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)
        self.escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.escape.setContext(Qt.ApplicationShortcut)
        self.escape.setEnabled(False)
        self.escape.activated.connect(self.close)

    def show_at(self, text, anchor):
        self.label.setText(text)
        hint = self.label.sizeHint()
        screen = (QGuiApplication.screenAt(anchor) or self.screen()).availableGeometry()
        self.resize(min(max(180, hint.width() + 28), screen.width() - 16),
                    min(hint.height() + self.close_button.sizeHint().height() + 36, screen.height() - 16))
        self.move(max(screen.left() + 8, min(anchor.x(), screen.right() - self.width() - 8)),
                  max(screen.top() + 8, min(anchor.y(), screen.bottom() - self.height() - 8)))
        self.escape.setEnabled(True)
        self.show()

    def closeEvent(self, event):
        self.escape.setEnabled(False)
        self.closed.emit()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)


class TallyPopupController(QObject):
    def __init__(self, delegate):
        super().__init__(delegate)
        # QObject parents own this controller; avoid Python references back to them.
        self._delegate_ref = weakref.ref(delegate)
        self._tree_ref = weakref.ref(delegate._tree)
        self._viewport_ref = weakref.ref(delegate._tree.viewport())
        self.popup = None
        self._hover = QPersistentModelIndex()
        self._pinned = QPersistentModelIndex()
        self._pressed = QPersistentModelIndex()
        self._position = QPoint()
        self._hover_visible = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(HOVER_DELAY_MS)
        self._timer.timeout.connect(self._show_hover)
        self.viewport.setMouseTracking(True)
        self.viewport.installEventFilter(self)
        self.tree.installEventFilter(self)
        model = self.tree.model()
        model.dataChanged.connect(self._model_changed)
        model.modelAboutToBeReset.connect(self.dismiss)
        model.rowsRemoved.connect(self._rows_removed)

    @property
    def delegate(self):
        return self._delegate_ref()

    @property
    def tree(self):
        return self._tree_ref()

    @property
    def viewport(self):
        return self._viewport_ref()

    @property
    def is_pinned(self):
        return self.popup is not None and self.popup.isVisible()

    def _target_at(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid():
            return None
        option = QStyleOptionViewItem()
        option.initFrom(self.tree)
        self.delegate.initStyleOption(option, index)
        option.rect = self.tree.visualRect(index)
        if self.delegate._tally_icon_rect(option).contains(position) and self.delegate._has_popup(index):
            return index, option
        return None

    def eventFilter(self, watched, event):
        if watched is self.tree and event.type() == QEvent.Hide:
            self.dismiss()
        if watched is not self.viewport:
            return False
        kind = event.type()
        if kind in (QEvent.Leave, QEvent.Hide, QEvent.Wheel):
            self._clear_hover()
        elif kind == QEvent.MouseMove:
            target = self._target_at(event.position().toPoint())
            if target is None or self.is_pinned:
                self._clear_hover()
            else:
                self._position = event.position().toPoint()
                if self._hover != target[0]:
                    self._clear_hover()
                    self._hover = QPersistentModelIndex(target[0])
                    self._timer.start()
        elif kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) and event.button() == Qt.LeftButton:
            target = self._target_at(event.position().toPoint())
            if target is not None:
                self._clear_hover()
                self._pressed = QPersistentModelIndex(target[0])
                return True
        elif kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self._pressed.isValid():
            target = self._target_at(event.position().toPoint())
            pressed = self._pressed
            self._pressed = QPersistentModelIndex()
            if target is not None and target[0] == pressed:
                self._toggle_pin(*target)
            return True
        elif kind == QEvent.KeyPress and event.key() == Qt.Key_Escape and self.is_pinned:
            self.popup.close()
            return True
        return False

    def _clear_hover(self):
        self._timer.stop()
        self._hover = QPersistentModelIndex()
        if self._hover_visible:
            QToolTip.hideText()
            self._hover_visible = False

    def _show_hover(self):
        target = self._target_at(self._position)
        if target is None or target[0] != self._hover or self.is_pinned:
            return
        event = QHelpEvent(QEvent.ToolTip, self._position, self.tree.viewport().mapToGlobal(self._position))
        self._hover_visible = self.delegate.helpEvent(event, self.tree, target[1], target[0])

    def _toggle_pin(self, index, option):
        if not self.delegate._popup_tags(index):
            return
        if self.is_pinned and self._pinned == index:
            self.popup.close()
            return
        self._clear_hover()
        QToolTip.hideText()
        if self.popup is None:
            self.popup = PinnedTallyPopup(self.tree)
            self.popup.closed.connect(self._unpin)
        self._pinned = QPersistentModelIndex(index)
        anchor = self.tree.viewport().mapToGlobal(self.delegate._tally_icon_rect(option).bottomRight())
        self.popup.show_at(self.delegate._tally_html(index), anchor + QPoint(8, 8))

    def _unpin(self):
        self._pinned = QPersistentModelIndex()

    def _model_changed(self, first, last, roles=None):
        if not self.is_pinned or not self._pinned.isValid():
            return
        if roles and Qt.UserRole not in roles and Qt.DisplayRole not in roles:
            return
        if first.parent() == self._pinned.parent() and first.row() <= self._pinned.row() <= last.row():
            index = QModelIndex(self._pinned)
            if self.delegate._popup_tags(index):
                self.popup.label.setText(self.delegate._tally_html(index))
            else:
                self.popup.close()

    def _rows_removed(self, *_args):
        if not self._hover.isValid():
            self._clear_hover()
        if self.is_pinned and not self._pinned.isValid():
            self.popup.close()

    def dismiss(self):
        self._clear_hover()
        self._pressed = QPersistentModelIndex()
        if self.popup is not None:
            self.popup.close()
