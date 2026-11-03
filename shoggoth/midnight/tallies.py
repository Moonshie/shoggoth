"""Tag totals for the native tree's actual descendant cards.

Build totals with the tree spec, then propagate assignment changes as deltas.
Painting never traverses the tree or scans the project's cards.
"""
from collections import Counter

from PySide6.QtCore import Qt

from shoggoth.midnight.tags import card_tag_ids, project_tags

TALLY_KEY = 'midnight_tag_tallies'


def _card_counts(card, known):
    return Counter({tag_id: 1 for tag_id in set(card_tag_ids(card)) if tag_id in known})


def _entries(definitions, counts, group_class=None):
    return [{**tag, 'count': counts[tag['id']]} for tag in definitions
            if counts[tag['id']] > 0 or group_class in tag['pips']]


def annotate_tree_tallies(spec, project):
    """Add ordered totals, including unused class tags, in one bottom-up pass."""
    definitions = project_tags(project)
    known = {tag['id'] for tag in definitions}

    def visit(node):
        counts = Counter()
        if node['type'] == 'card':
            counts = _card_counts(node['data'], known)
        for child in node.get('children', []):
            counts.update(visit(child))
        node[TALLY_KEY] = _entries(definitions, counts, node.get('class'))
        return counts

    visit(spec)
    return spec


def _stored_counts(data):
    return Counter({tag['id']: tag['count'] for tag in data.get(TALLY_KEY, [])})


def _set_entries(item, data, entries):
    if data.get(TALLY_KEY) != entries:
        item.setData(0, Qt.UserRole, {**data, TALLY_KEY: entries})


def update_tree_tallies(item):
    """Refresh one card and its ancestors through the native card-update path."""
    data = item.data(0, Qt.UserRole) or {}
    card = data.get('data') if data.get('type') == 'card' else None
    if card is None:
        return
    definitions = project_tags(card.project)
    counts = _card_counts(card, {tag['id'] for tag in definitions})
    delta = counts.copy()
    delta.subtract(_stored_counts(data))
    if not any(delta.values()):
        return
    _set_entries(item, data, _entries(definitions, counts))
    parent = item.parent()
    while parent is not None:
        data = parent.data(0, Qt.UserRole) or {}
        counts = _stored_counts(data)
        counts.update(delta)
        _set_entries(parent, data, _entries(definitions, counts, data.get('class')))
        parent = parent.parent()
