"""Project a credit into the native text renderer without editing face data."""
from copy import deepcopy
from html import escape

from .model import designer


class DesignerLayer:
    """Only this temporary text field is visible to the native text pass."""
    def __init__(self, side, name, region, font):
        self.card = side.card
        self.other_side = side.other_side
        self.data = {
            'midnight_designer': f'Des. {escape(name)}',
            'midnight_designer_region': region,
            'midnight_designer_font': font,
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def visible_keys(self):
        return self.data.keys()


def _region(side, field):
    value = side.get(f'{field}_region')
    if (isinstance(value, dict) and not value.get('is_attached')
            and value.get('width', 0) > 0 and value.get('height', 0) > 0):
        return value
    return None


def designer_layers(side):
    name = designer(side.card)
    if not name:
        return
    icon = _region(side, 'collection_icon')
    number = _region(side, 'collection_number')
    if not icon and not number:
        return
    # The number supplies the footer baseline and text size. Reserve the icon's
    # box even if it is currently empty, so adding an icon cannot move the name.
    baseline = number or icon
    font = deepcopy(side.get('collection_number_font') or side.get('illustrator_font') or {})
    font['alignment'] = 'right'
    # Follow the footer, including a rotated illustrator's independent layout.
    font['rotation'] = (side.get('collection_number_font') or {}).get('rotation', 0)
    gap = max(8, round(font.get('size', 20) / 2))
    right = min(anchor.get('x', 0) for anchor in (icon, number) if anchor) - gap
    width = min(600, right)
    if width <= 0:
        return
    region = {'x': right - width, 'y': baseline.get('y', 0),
              'width': width, 'height': baseline['height']}
    yield DesignerLayer(side, name, region, font)
