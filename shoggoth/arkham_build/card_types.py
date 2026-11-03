from enum import Enum, auto
from pathlib import Path
from typing import NamedTuple

from shoggoth.card import Face


class CardType(NamedTuple):
    code: str
    is_backside: bool


class NoCardType(Enum):
    """Faces that are not exported as an arkham.build card."""

    UNSUPPORTED = auto()
    # A generic player or encounter card back.
    CARD_BACK = auto()


type ResolvedCardType = CardType | NoCardType


UNSUPPORTED_TYPE = NoCardType.UNSUPPORTED
CARD_BACK_TYPE = NoCardType.CARD_BACK
ACT_AGENDA_FULL_TEMPLATE = "act_agenda_full"
_INDETERMINATE_TYPE = "indeterminate"


_TYPE_MAP = {
    # Legacy types without a card_type use their template name as role.
    ACT_AGENDA_FULL_TEMPLATE: _INDETERMINATE_TYPE,
    "chaos": "scenario",
}


_SUPPORTED_TYPES = {
    "act",
    "agenda",
    "asset",
    "enemy",
    "enemy_location",
    "event",
    "investigator",
    "key",
    "location",
    "scenario",
    "skill",
    "story",
    "treachery",
    _INDETERMINATE_TYPE,
}


_UNSUPPORTED_TEMPLATES = {
    "enemy_deck",
    "scanning",
    "fullart_scanning",
    "fullart_encounter_with_connections",
}


def resolve_card_types(
    front: Face, back: Face
) -> tuple[ResolvedCardType, ResolvedCardType]:
    mapped_front_type = _card_type(front)
    mapped_back_type = _card_type(back)
    return (
        _resolve_indeterminate_type(mapped_front_type, mapped_back_type),
        _resolve_indeterminate_type(mapped_back_type, mapped_front_type),
    )


def is_double_sided(front_type: CardType, back_type: CardType) -> bool:
    if front_type == back_type == CardType("scenario", False):
        return True

    return (
        front_type.code in {"act", "agenda", "investigator", "location"}
        and front_type.code == back_type.code
        and not front_type.is_backside
        and back_type.is_backside
    )


def face_template(face: Face) -> tuple[str, bool]:
    template = Path(face.get("type") or "").stem
    return template.removesuffix("_back"), template.endswith("_back")


def _card_type(card_face: Face) -> ResolvedCardType:
    template, is_backside = face_template(card_face)
    if template in _UNSUPPORTED_TEMPLATES:
        return UNSUPPORTED_TYPE

    roles = card_face.card_types
    if not roles:
        return UNSUPPORTED_TYPE

    if {"act", "agenda"}.issubset(roles):
        return CardType(_INDETERMINATE_TYPE, is_backside)

    if {"enemy", "location"}.issubset(roles):
        return CardType("enemy_location", is_backside)

    if roles[0] in {"player", "encounter"}:
        return CARD_BACK_TYPE

    type_code = _TYPE_MAP.get(roles[0], roles[0])
    if type_code not in _SUPPORTED_TYPES:
        return UNSUPPORTED_TYPE

    return CardType(type_code, is_backside)


def _resolve_indeterminate_type(
    card_type: ResolvedCardType, other_type: ResolvedCardType
) -> ResolvedCardType:
    """Some card types can only be resolved via the other card side."""
    if isinstance(card_type, NoCardType) or card_type.code != _INDETERMINATE_TYPE:
        return card_type

    if isinstance(other_type, NoCardType) or other_type.code not in {"act", "agenda"}:
        return UNSUPPORTED_TYPE

    return CardType(other_type.code, card_type.is_backside)
