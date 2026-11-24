"""Apply collection-order priorities to the native player-card groups."""
from PySide6.QtCore import QObject, Qt

from shoggoth.card import natural_sort_key
from shoggoth.project import class_order, class_sort_key, player_type_order
from shoggoth.ui.browser.tree_spec import build_card_spec, build_investigator_spec, build_player_class_spec


_PLAYER_GROUPS = tuple('other' if cls == 'multi' else cls for cls in class_order) + ('weakness',)
_ORDER_KEY = 'midnight_tree_order'


class TreeOrderingBrowser(QObject):
    def __init__(self, browser, manager):
        super().__init__(browser)
        self.browser = browser
        manager.changed.connect(self._changed)

    def _changed(self, module_id, enabled):
        if module_id == 'tree_ordering' and self.browser._view_mode == 'tree':
            self.browser.refresh()


def _investigator_group(card):
    linked = card.get_meta('investigator', card.get('investigator'))
    if linked:
        return linked
    if card.card_type == 'investigator':
        return card.name or card.id
    return None


def _investigator_group_key(entry):
    group, cards = entry
    ranks = (class_order.get(card.get_class(), len(class_order))
             for card in cards if card.card_type == 'investigator')
    return min(ranks, default=len(class_order)), group.casefold()


def _signature_key(card):
    if card.card_type == 'investigator':
        rank = 0
    elif card.card_type == 'mini_investigator':
        rank = 3
    elif card.get_class() == 'weakness':
        rank = 2
    else:
        rank = 1
    return rank, card.name.casefold()


def _class_card_key(card):
    level = card.front.get('level', 0)
    return (
        not bool(card.get_meta('sorting', card.get('sorting', True))),
        class_order.get(card.get_class(), len(class_order)),
        class_sort_key(card),
        natural_sort_key(0 if level in ('', 'None') else level),
        player_type_order.get(card.card_type, len(player_type_order)),
    )


def _order_fields(card):
    """Ordering data saved on the existing card node to detect relevant edits."""
    return (
        card.name, card.card_type, card.get_class(), _investigator_group(card), card.get('encounter_set'),
        str(card.front.get('classes')), str(card.front.get('level')), str(card.front.get('index')),
        bool(card.get_meta('sorting', card.get('sorting', True))),
        str(card.get_meta('bonded', card.get('bonded'))),
    )


def ordering_changed(item):
    data = item.data(0, Qt.UserRole) or {}
    previous = data.get(_ORDER_KEY)
    return previous is not None and tuple(previous) != _order_fields(data['data'])


def _card_specs(cards):
    children = []
    for card in cards:
        spec = build_card_spec(card, include_level=True)
        spec[_ORDER_KEY] = _order_fields(card)
        children.append(spec)
    return children


def build_player_tree(project, cards):
    investigators = {}
    classes = {cls: [] for cls in _PLAYER_GROUPS}
    for card in cards:
        cls = card.get_class()
        group = _investigator_group(card)
        if group and cls != 'basic weakness':
            investigators.setdefault(group, []).append(card)
        else:
            classes.get(cls, classes['other']).append(card)

    sections = []
    if investigators:
        groups = [build_investigator_spec(project, group, _card_specs(sorted(linked, key=_signature_key)))
                  for group, linked in sorted(investigators.items(), key=_investigator_group_key)]
        sections.append(build_player_class_spec(project, 'investigators', groups))
    for cls, class_cards in classes.items():
        if class_cards:
            # Keep the numbering algorithm's existing order within each level and type.
            sections.append(build_player_class_spec(project, cls, _card_specs(sorted(class_cards, key=_class_card_key))))
    return sections
