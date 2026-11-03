"""Paint compact tag badges without changing card names, sorting, or tree data."""
from html import escape

from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QToolTip

from shoggoth.midnight.presentation import badge_font, paint_badge, tag_details, tag_label, tag_pips_html
from shoggoth.midnight.tags import card_tags, is_secondary
from shoggoth.midnight.tallies import TALLY_KEY
from shoggoth.midnight.tally_popup import TallyPopupController
from shoggoth.ui.browser.drag_drop import CompactLeafDelegate


class DesignTagDelegate(CompactLeafDelegate):
    def __init__(self, tree, compact=True):
        super().__init__(tree)
        self.compact = compact
        self.tally_popup = TallyPopupController(self)

    def _tags(self, index):
        data = index.data(Qt.UserRole) or {}
        card = data.get('data') if data.get('type') == 'card' else None
        if card:
            return card_tags(card)
        return data.get(TALLY_KEY, []) if self.compact else []

    def _popup_tags(self, index):
        tags = self._tags(index)
        data = index.data(Qt.UserRole) or {}
        return [tag for tag in tags if is_secondary(tag)] if data.get('type') == 'card' else tags

    def _has_popup(self, index):
        data = index.data(Qt.UserRole) or {}
        return data.get('type') == 'card' or bool(self._popup_tags(index))

    def _tally_icon_rect(self, option):
        size = min(14, max(10, option.fontMetrics.height() - 2))
        right = min(option.rect.right(), self._tree.viewport().width() - 1) - 4
        return QRect(right - size + 1, option.rect.center().y() - size // 2, size, size)

    def _tally_html(self, index, *, hint=False):
        data = index.data(Qt.UserRole) or {}
        is_card = data.get('type') == 'card'
        title = escape(data['data'].name if is_card else str(index.data(Qt.DisplayRole)))
        rows = []
        for tag in self._popup_tags(index):
            name = tag['name'] if is_card else tag_label(tag)
            count = (f'<td width="12"></td><td align="right"><b>{tag["count"]}</b></td>'
                     if 'count' in tag else '')
            rows.append(f'<tr><td>{escape(name)}</td><td width="12"></td>'
                        f'<td>{tag_pips_html(tag)}</td>{count}</tr>')
        footer = '<br><small>Click the icon to pin</small>' if hint and rows else ''
        heading = 'secondary tags' if is_card else 'tag counts'
        content = f'<table cellspacing="4">{"".join(rows)}</table>' if rows else '<p>No secondary tags</p>'
        return f'<qt><b>{title} — {heading}</b>{content}{footer}</qt>'

    @staticmethod
    def _paint_tally_icon(painter, rect, option):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        role = QPalette.HighlightedText if option.state & QStyle.State_Selected else QPalette.Text
        color = option.palette.color(role)
        color.setAlpha(180 if option.state & QStyle.State_Enabled else 85)
        painter.setPen(QPen(color, 1.2, Qt.SolidLine, Qt.RoundCap))
        for y in (rect.top() + 3, rect.center().y(), rect.bottom() - 2):
            painter.drawPoint(rect.left() + 2, y)
            painter.drawLine(rect.left() + 5, y, rect.right() - 1, y)
        painter.restore()

    def paint(self, painter, option, index):
        tags = self._tags(index)
        data = index.data(Qt.UserRole) or {}
        if not tags and data.get('type') != 'card':
            if self.compact:
                super().paint(painter, option, index)
            else:
                # The list has ordinary native indentation, including untagged cards.
                from PySide6.QtWidgets import QStyledItemDelegate
                QStyledItemDelegate.paint(self, painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        if self.compact and data.get('type') in self._ALWAYS_LEAF_TYPES \
                and not index.model().hasChildren(index):
            opt.rect = opt.rect.adjusted(-self._tree.indentation(), 0, 0, 0)
        style = opt.widget.style() if opt.widget else QApplication.style()
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget)
        text_rect.setRight(min(opt.rect.right(), self._tree.viewport().width() - 1) - 4)
        text = opt.text
        opt.text = ''
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        painter.save()
        painter.setFont(opt.font)
        metrics = painter.fontMetrics()
        is_header = data.get('type') != 'card'
        icon_rect = self._tally_icon_rect(opt)
        icon_option = QStyleOptionViewItem(opt)
        if not is_header and not any(is_secondary(tag) for tag in tags):
            icon_option.state &= ~QStyle.State_Enabled
        if is_header:
            reserved = text_rect.right() - icon_rect.left() + 5
            name_rect = QRect(text_rect)
        else:
            tags = [tag for tag in tags if not is_secondary(tag)]
            badge_area = QRect(text_rect)
            badge_area.setRight(icon_rect.left() - 5)
            name_rect = QRect(badge_area)
            badge_height = max(10, int(min(text_rect.height(), metrics.height()) * 0.75))
            badge_metrics = QFontMetrics(badge_font(opt.font, badge_height))
            labels = [tag['name'][:3].upper() for tag in tags]
            badge_width = max([24, badge_metrics.horizontalAdvance('WWW') + 4]
                              + [badge_metrics.horizontalAdvance(label) + 6 for label in labels])
            gap = 3
            # Leave room for the name in narrow sidebars; +N stands for hidden badges.
            budget = max(0, min(badge_area.width() * 0.6, badge_area.width() - 48))
            slots = min(len(tags), int(budget // (badge_width + gap)))
            visible = tags[:slots]
            labels = labels[:slots]
            if slots and slots < len(tags):
                visible[-1] = {'pips': []}
                labels[-1] = f'+{len(tags) - slots + 1}'
            reserved = slots * (badge_width + gap) + (4 if slots else 0)
        name_rect.setWidth(max(0, name_rect.width() - reserved))
        palette_role = (QPalette.HighlightedText if opt.state & QStyle.State_Selected
                        else QPalette.Text)
        style.drawItemText(painter, name_rect, Qt.AlignVCenter | Qt.AlignLeft,
                           opt.palette, bool(opt.state & QStyle.State_Enabled),
                           metrics.elidedText(text, Qt.ElideRight, name_rect.width()), palette_role)
        self._paint_tally_icon(painter, icon_rect, icon_option)
        if not is_header:
            x = badge_area.right() + 1 - slots * (badge_width + gap) + gap
            for tag, label in zip(visible, labels):
                paint_badge(painter, QRectF(x, text_rect.center().y() - badge_height / 2,
                                           badge_width, badge_height), tag, label)
                x += badge_width + gap
        painter.restore()

    def helpEvent(self, event, view, option, index):
        tags = self._tags(index)
        data = index.data(Qt.UserRole) or {}
        if tags or data.get('type') == 'card':
            title = escape(str(index.data(Qt.DisplayRole)))
            icon_rect = self._tally_icon_rect(option)
            if self._has_popup(index) and icon_rect.contains(event.pos()):
                if not self.tally_popup.is_pinned:
                    QToolTip.showText(event.globalPos(), self._tally_html(index, hint=True),
                                      view.viewport(), icon_rect)
                return True
            main = [tag for tag in tags if not is_secondary(tag)]
            if data.get('type') == 'card' and main:
                details = '<br>'.join(escape(tag_details(tag)) for tag in main)
                QToolTip.showText(event.globalPos(), f'<qt>{title}<br>{details}</qt>', view)
                return True
        return super().helpEvent(event, view, option, index)
