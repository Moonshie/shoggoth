"""Designer credits stored independently of official template assets."""
from shoggoth.midnight.registry import Module


def _card_widget(card):
    from .widget import DesignerWidget
    return DesignerWidget(card)


def _text_layers(side):
    from .rendering import designer_layers
    return designer_layers(side)


MODULE = Module(
    id='designer', name='Designer',
    description='A card designer credit, printed as “Des. Name” before its collection icon and number.',
    card_widget=_card_widget, text_layers=_text_layers,
)
