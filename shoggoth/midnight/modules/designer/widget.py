from PySide6.QtCore import QSignalBlocker, Signal

from shoggoth.ui.field_widgets import LabeledLineEdit
from .model import designer, set_designer


class DesignerWidget(LabeledLineEdit):
    changed = Signal()

    def __init__(self, card):
        super().__init__('Designer')
        self.card = card
        self.input.setPlaceholderText('e.g. Mint Tea Fan')
        self.setToolTip('Printed as “Des. Name” on the right of the footer, before '
                        'the collection icon and number. Leave empty to omit the credit.')
        self.refresh()
        self.input.textChanged.connect(self._edited)

    def refresh(self):
        with QSignalBlocker(self.input):
            self.input.setText(designer(self.card))

    def _edited(self, text):
        before = designer(self.card)
        set_designer(self.card, text)
        if designer(self.card) != before:
            self.changed.emit()
