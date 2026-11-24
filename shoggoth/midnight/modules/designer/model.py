"""Namespaced card credit, preserved by native save, cloud, and transfer."""


def designer(card):
    namespace = card.get_meta('midnight', {})
    value = namespace.get('designer', '') if isinstance(namespace, dict) else ''
    return value.strip() if isinstance(value, str) else ''


def set_designer(card, name):
    name = name.strip()
    if name == designer(card):
        return
    stored = card.get_meta('midnight', {})
    namespace = dict(stored) if isinstance(stored, dict) else {}
    if name:
        namespace['designer'] = name
    else:
        namespace.pop('designer', None)
    meta = card.data.setdefault('meta', {})
    if namespace:
        meta['midnight'] = namespace
    else:
        meta.pop('midnight', None)
    card.dirty = True
