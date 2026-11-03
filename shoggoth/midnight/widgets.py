"""Qt entry points for the Midnight design-tag extension."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea,
    QToolButton, QVBoxLayout, QWidget,
)

import shoggoth
from shoggoth.midnight.flow_layout import TagFlowLayout
from shoggoth.midnight.presentation import TagChip, tag_details, tag_icon, tag_label
from shoggoth.midnight.tags import (
    PIP_CLASSES, card_tag_ids, card_tags, delete_tag, is_secondary, matching_project_tags, project_tags, reorder_tags, save_tag,
    set_card_tags, tag_usage,
)
from shoggoth.ui.compact_widgets import CLASS_CHIP_COLORS, class_label


# Keep the picker preference when navigating between cards during this session.
_session_match_classes = False


def _refresh_sidebar():
    if shoggoth.app is not None:
        shoggoth.app.refresh_tree()


def _clear_row(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()


def _scrolling_row():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFixedHeight(44)
    content = QWidget()
    row = QHBoxLayout(content)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(5)
    scroll.setWidget(content)
    return scroll, row


class TagEditDialog(QDialog):
    def __init__(self, project, tag=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.tag_id = tag['id'] if tag else None
        self.pips = list(tag['pips']) if tag else []
        self.setWindowTitle('Edit design tag' if tag else 'New design tag')
        self.resize(560, 300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(tag['name'] if tag else '')
        self.name_input.setPlaceholderText('e.g. Draw, Economy, Needs testing')
        form.addRow('Name', self.name_input)
        self.display_combo = QComboBox()
        self.display_combo.addItem('Main', False)
        self.display_combo.addItem('Secondary', True)
        self.display_combo.setCurrentIndex(1 if tag and is_secondary(tag) else 0)
        self.display_combo.setToolTip('Secondary tags have their own card row and a sidebar hover icon.')
        form.addRow('Display', self.display_combo)
        layout.addLayout(form)
        help_label = QLabel('Add any number of class pips. Repeated colors are allowed.\n'
                            'Click a pip below to remove it; leave empty for a text-only tag.')
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        classes = QHBoxLayout()
        for value in PIP_CLASSES:
            button = QPushButton('+ ' + class_label(value))
            background, foreground = CLASS_CHIP_COLORS[value]
            button.setStyleSheet(f'color: {foreground}; background-color: {background}; padding: 5px;')
            button.clicked.connect(lambda checked=False, pip=value: self.add_pip(pip))
            classes.addWidget(button)
        layout.addLayout(classes)
        scroll, self.pip_row = _scrolling_row()
        layout.addWidget(scroll)
        self.preview = QWidget()
        self.preview_row = QHBoxLayout(self.preview)
        self.preview_row.setContentsMargins(0, 0, 0, 0)
        preview_scroll, preview_container = _scrolling_row()
        preview_container.addWidget(self.preview)
        layout.addWidget(preview_scroll)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name_input.textChanged.connect(self._refresh_preview)
        self.display_combo.currentIndexChanged.connect(self._refresh_preview)
        self._refresh_pips()

    def add_pip(self, pip):
        self.pips.append(pip)
        self._refresh_pips()

    def remove_pip(self, index):
        self.pips.pop(index)
        self._refresh_pips()

    def _refresh_pips(self):
        _clear_row(self.pip_row)
        for index, pip in enumerate(self.pips):
            button = QPushButton(class_label(pip) + ' ×')
            background, foreground = CLASS_CHIP_COLORS[pip]
            button.setStyleSheet(f'color: {foreground}; background-color: {background}; padding: 4px;')
            button.setToolTip('Remove this pip')
            button.clicked.connect(lambda checked=False, i=index: self.remove_pip(i))
            self.pip_row.addWidget(button)
        if not self.pips:
            self.pip_row.addWidget(QLabel('No color pips'))
        self.pip_row.addStretch()
        self._refresh_preview()

    def _refresh_preview(self):
        _clear_row(self.preview_row)
        chip = TagChip({'name': self.name_input.text().strip() or 'Tag', 'pips': self.pips,
                        'secondary': self.display_combo.currentData()})
        chip.setFixedSize(chip.sizeHint())
        self.preview_row.addWidget(chip)
        self.preview_row.addStretch()

    def accept(self):
        try:
            self.tag_id = save_tag(self.project, self.name_input.text(), self.pips, self.tag_id,
                                   secondary=self.display_combo.currentData())
        except ValueError as error:
            self.error_label.setText(str(error))
            return
        super().accept()


class ProjectTagsWidget(QWidget):
    changed = Signal()

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        layout = QVBoxLayout(self)
        help_label = QLabel('Define tags for organizing and developing the cards in this project. '
                            'Assign them below a card’s name. They do not affect card rules, '
                            'artwork, or gameplay exports. Drag tags or use Move up / Move down '
                            'to set their display order on every card.')
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.tag_list = QListWidget()
        self.tag_list.setAccessibleName('Project design tags')
        self.tag_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.tag_list.setDefaultDropAction(Qt.MoveAction)
        self.tag_list.model().rowsMoved.connect(self._order_changed)
        self.tag_list.itemDoubleClicked.connect(self.edit_tag)
        self.tag_list.currentRowChanged.connect(self._selection_changed)
        layout.addWidget(self.tag_list, 1)
        self.details_label = QLabel()
        self.details_label.setTextFormat(Qt.PlainText)
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        buttons = QHBoxLayout()
        new_button = QPushButton('New tag…')
        new_button.clicked.connect(self.new_tag)
        buttons.addWidget(new_button)
        self.edit_button = QPushButton('Edit…')
        self.edit_button.clicked.connect(self.edit_tag)
        buttons.addWidget(self.edit_button)
        self.delete_button = QPushButton('Delete')
        self.delete_button.clicked.connect(self.remove_tag)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        self.move_up_button = QPushButton('Move up')
        self.move_up_button.clicked.connect(self.move_up)
        buttons.addWidget(self.move_up_button)
        self.move_down_button = QPushButton('Move down')
        self.move_down_button.clicked.connect(self.move_down)
        buttons.addWidget(self.move_down_button)
        layout.addLayout(buttons)
        self.refresh()

    def selected_tag(self):
        item = self.tag_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def refresh(self, selected_id=None):
        self.tag_list.clear()
        for tag in project_tags(self.project):
            item = QListWidgetItem(tag_icon(tag), tag_label(tag))
            item.setData(Qt.UserRole, tag)
            item.setToolTip(tag_details(tag))
            self.tag_list.addItem(item)
            if tag['id'] == selected_id:
                self.tag_list.setCurrentItem(item)
        if self.tag_list.currentRow() < 0 and self.tag_list.count():
            self.tag_list.setCurrentRow(0)
        self._selection_changed()

    def _selection_changed(self, *_args):
        tag = self.selected_tag()
        self.edit_button.setEnabled(tag is not None)
        self.delete_button.setEnabled(tag is not None)
        row = self.tag_list.currentRow()
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(0 <= row < self.tag_list.count() - 1)
        text = (f"{tag_details(tag)}\nAssigned to {tag_usage(self.project, tag['id'])} card(s)."
                if tag else 'No design tags yet. Use New tag… to create one.')
        self.details_label.setText(text)

    def move_up(self):
        self.move_tag(-1)

    def move_down(self):
        self.move_tag(1)

    def move_tag(self, offset):
        row = self.tag_list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self.tag_list.count() or target == row:
            return
        item = self.tag_list.takeItem(row)
        self.tag_list.insertItem(target, item)
        self.tag_list.setCurrentItem(item)
        self._order_changed()

    def _order_changed(self, *_args):
        reorder_tags(self.project, [self.tag_list.item(row).data(Qt.UserRole)['id']
                                    for row in range(self.tag_list.count())])
        self._selection_changed()
        self.changed.emit()
        _refresh_sidebar()

    def _edit(self, tag=None):
        dialog = TagEditDialog(self.project, tag, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh(dialog.tag_id)
            self.changed.emit()
            _refresh_sidebar()

    def new_tag(self):
        self._edit()

    def edit_tag(self, *_args):
        if tag := self.selected_tag():
            self._edit(tag)

    def remove_tag(self):
        tag = self.selected_tag()
        if tag is None:
            return
        count = tag_usage(self.project, tag['id'])
        if count and QMessageBox.question(
            self, 'Delete design tag',
            f'Delete “{tag["name"]}” and remove it from {count} card(s)?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        delete_tag(self.project, tag['id'])
        self.refresh()
        self.changed.emit()
        _refresh_sidebar()


class CardTagsWidget(QWidget):
    changed = Signal()

    def __init__(self, card, parent=None):
        super().__init__(parent)
        self.card = card
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        header = QHBoxLayout()
        header.addWidget(QLabel('Design tags'))
        self.choose_button = QToolButton()
        self.choose_button.setText('Choose…')
        self.choose_button.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self.choose_button)
        self.menu.aboutToShow.connect(self._build_menu)
        self.choose_button.setMenu(self.menu)
        header.addWidget(self.choose_button)
        manage_button = QPushButton('Manage…')
        manage_button.setToolTip('Manage this project’s design tags')
        manage_button.clicked.connect(self.manage_tags)
        header.addWidget(manage_button)
        self.match_classes_checkbox = QCheckBox('Match classes')
        self.match_classes_checkbox.setToolTip(
            'Only offer tags with a pip matching any of this card’s classes. '
            'Tags without pips are hidden while filtering.')
        self.match_classes_checkbox.setChecked(_session_match_classes)
        self.match_classes_checkbox.toggled.connect(self._on_match_classes_changed)
        header.addWidget(self.match_classes_checkbox)
        header.addStretch()
        layout.addLayout(header)
        self.main_label = QLabel('Main')
        self.main_label.setProperty('role', 'field-label')
        layout.addWidget(self.main_label)
        self.chip_container = QWidget()
        self.chip_row = TagFlowLayout(self.chip_container)
        layout.addWidget(self.chip_container)
        self.secondary_label = QLabel('Secondary')
        self.secondary_label.setProperty('role', 'field-label')
        layout.addWidget(self.secondary_label)
        self.secondary_container = QWidget()
        self.secondary_row = TagFlowLayout(self.secondary_container)
        layout.addWidget(self.secondary_container)
        self.refresh()

    def refresh(self):
        tags = card_tags(self.card)
        for secondary, row, container, label in (
            (False, self.chip_row, self.chip_container, self.main_label),
            (True, self.secondary_row, self.secondary_container, self.secondary_label),
        ):
            _clear_row(row)
            assigned = [tag for tag in tags if is_secondary(tag) == secondary]
            for tag in assigned:
                row.addWidget(TagChip(tag))
            container.setVisible(bool(assigned))
            label.setVisible(bool(assigned))
            container.updateGeometry()
        self.updateGeometry()
        self.choose_button.setToolTip('\n'.join(tag_details(tag) for tag in tags) or 'No tags selected')

    def _build_menu(self):
        self.menu.clear()
        chosen = card_tag_ids(self.card)
        tags = project_tags(self.card.project)
        offered = matching_project_tags(self.card) if self.match_classes_checkbox.isChecked() else tags
        for tag in offered:
            action = QAction(tag_icon(tag), tag_label(tag), self.menu)
            action.setCheckable(True)
            action.setChecked(tag['id'] in chosen)
            action.setToolTip(tag_details(tag))
            action.triggered.connect(lambda checked, tag_id=tag['id']: self.toggle_tag(tag_id, checked))
            self.menu.addAction(action)
        if not self.menu.actions():
            message = ('No tags match this card’s classes' if tags
                       else 'No tags defined — use Manage…')
            self.menu.addAction(message).setEnabled(False)

    def _on_match_classes_changed(self, checked):
        global _session_match_classes
        _session_match_classes = checked
        self._build_menu()

    def toggle_tag(self, tag_id, checked):
        ids = card_tag_ids(self.card)
        ids = list(dict.fromkeys([*ids, tag_id])) if checked else [value for value in ids if value != tag_id]
        set_card_tags(self.card, ids)
        self.refresh()
        self.changed.emit()
        _refresh_sidebar()

    def manage_tags(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Project design tags')
        dialog.resize(550, 400)
        layout = QVBoxLayout(dialog)
        manager = ProjectTagsWidget(self.card.project)
        manager.changed.connect(self.refresh)
        layout.addWidget(manager)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        self.refresh()
