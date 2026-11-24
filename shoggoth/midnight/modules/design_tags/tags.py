"""Project-local design tags. No renderer, exporter, Qt, or file-format hooks.

Definitions live in project.meta.midnight.design_tags; cards store their IDs
in card.meta.midnight.design_tags. Unknown namespace fields are preserved.
"""
from copy import deepcopy
from uuid import uuid4

PIP_CLASSES = ('guardian', 'seeker', 'rogue', 'mystic', 'survivor', 'neutral')


def is_secondary(tag):
    """Older definitions without a display designation are main tags."""
    return tag.get('secondary', False) is True


def _namespace(owner):
    value = owner.get_meta('midnight', {})
    return value if isinstance(value, dict) else {}


def _write(owner, value):
    namespace = dict(_namespace(owner))
    if value:
        namespace['design_tags'] = value
    else:
        namespace.pop('design_tags', None)
    meta = owner.data.setdefault('meta', {})
    if namespace:
        meta['midnight'] = namespace
    else:
        meta.pop('midnight', None)
    # Notify native dirty/cloud listeners only AFTER storing the new content.
    owner.dirty = True


def project_tags(project):
    """Return independent definitions; reading old projects never adds fields."""
    return deepcopy(_namespace(project).get('design_tags', []))


def card_tag_ids(card):
    return list(_namespace(card).get('design_tags', []))


def card_tags(card):
    """Resolve assignments in the project's display order, regardless of click order."""
    assigned = set(card_tag_ids(card))
    return [tag for tag in project_tags(card.project) if tag['id'] in assigned]


def matching_project_tags(card):
    """Offer tags sharing any pip color with the card's resolved classes."""
    classes = card.front.get('classes', []) or card.back.get('classes', [])
    if isinstance(classes, str):
        classes = classes.split(',')
    classes = {str(value).strip().casefold() for value in classes}
    return [tag for tag in project_tags(card.project) if classes.intersection(tag['pips'])]


def reorder_tags(project, tag_ids):
    """Change display order without rewriting any card's assignments."""
    tags = project_tags(project)
    tag_ids = list(tag_ids)
    definitions = {tag['id']: tag for tag in tags}
    if len(tag_ids) != len(tags) or set(tag_ids) != set(definitions):
        raise ValueError('The order must contain every project design tag exactly once.')
    reordered = [definitions[tag_id] for tag_id in tag_ids]
    if reordered != tags:
        _write(project, reordered)


def save_tag(project, name, pips=(), tag_id=None, *, secondary=None):
    """Create/edit a tag, keeping its ID and all card assignments on rename."""
    name = name.strip()
    if not name:
        raise ValueError('Enter a tag name.')
    pips = list(pips)
    if any(pip not in PIP_CLASSES for pip in pips):
        raise ValueError('Choose a class color for each pip.')
    if secondary is not None and not isinstance(secondary, bool):
        raise ValueError('Choose Main or Secondary for the tag display.')
    tags = project_tags(project)
    if any(tag['id'] != tag_id and tag['name'].casefold() == name.casefold() for tag in tags):
        raise ValueError('A design tag with this name already exists in this project.')
    if tag_id is not None and not any(tag['id'] == tag_id for tag in tags):
        raise ValueError('This design tag no longer exists.')
    tag_id = tag_id or str(uuid4())
    tag = {'id': tag_id, 'name': name, 'pips': pips}
    for index, existing in enumerate(tags):
        if existing['id'] == tag_id:
            tag = {**existing, **tag}
            display_secondary = is_secondary(existing) if secondary is None else secondary
            if display_secondary:
                tag['secondary'] = True
            else:
                tag.pop('secondary', None)
            if existing == tag:
                return tag_id
            tags[index] = tag
            break
    else:
        if secondary:
            tag['secondary'] = True
        tags.append(tag)
    _write(project, tags)
    return tag_id


def set_card_tags(card, tag_ids):
    known = {tag['id'] for tag in project_tags(card.project)}
    tag_ids = list(dict.fromkeys(tag_ids))
    if any(tag_id not in known for tag_id in tag_ids):
        raise ValueError('Choose tags defined in this project.')
    if card_tag_ids(card) != tag_ids:
        _write(card, tag_ids)


def tag_usage(project, tag_id):
    return sum(tag_id in card_tag_ids(card) for card in project.cards)


def delete_tag(project, tag_id):
    tags = project_tags(project)
    remaining = [tag for tag in tags if tag['id'] != tag_id]
    if remaining == tags:
        return
    # Clean assignments while the definition still exists, notifying each card.
    for card in project.cards:
        ids = card_tag_ids(card)
        if tag_id in ids:
            set_card_tags(card, [value for value in ids if value != tag_id])
    _write(project, remaining)


def _same_display(first, second):
    return first['pips'] == second['pips'] and is_secondary(first) == is_secondary(second)


def transfer_card_tags(card, destination, data):
    """Carry only assigned definitions when the native transfer copies/moves a card.

    Reuse identical tags; give differing same-named tags a numbered suffix.
    Never edit the source card's data (a copy can still belong to that project).
    """
    if destination is card.project:
        return
    ids = []
    for tag in card_tags(card):
        tags = project_tags(destination)
        same = next((other for other in tags if _same_display(other, tag)
                     and (other['id'] == tag['id'] or other['name'].casefold() == tag['name'].casefold())), None)
        if same:
            ids.append(same['id'])
            continue
        name = tag['name']
        suffix = 2
        names = {other['name'].casefold(): other for other in tags}
        while name.casefold() in names and not _same_display(names[name.casefold()], tag):
            name = f"{tag['name']} ({suffix})"
            suffix += 1
        if name.casefold() in names:
            ids.append(names[name.casefold()]['id'])
        else:
            tag_id = tag['id'] if all(other['id'] != tag['id'] for other in tags) else str(uuid4())
            _write(destination, [*tags, {**tag, 'id': tag_id, 'name': name}])
            ids.append(tag_id)
    namespace = dict((data.get('meta') or {}).get('midnight') or {})
    if ids:
        namespace['design_tags'] = ids
    else:
        namespace.pop('design_tags', None)
    if namespace:
        data.setdefault('meta', {})['midnight'] = namespace
    elif 'meta' in data:
        data['meta'].pop('midnight', None)
