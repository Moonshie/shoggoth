import re
from collections.abc import Mapping, Sequence
from html import unescape
from typing import Required, TypedDict

from shoggoth.arkham_build.text import card_labels, map_text
from shoggoth.card import Card, Face


class DeckbuildingRecord(TypedDict, total=False):
    type_code: Required[str]
    restrictions: str
    deck_requirements: str


def add_deckbuilding_fields(
    cards: Sequence[Card],
    records_by_id: Mapping[str, Sequence[DeckbuildingRecord]],
) -> None:
    investigators: dict[str, list[Card]] = {}
    signatures: dict[str, list[str]] = {}

    for card in cards:
        records = records_by_id[card.id]
        if not records or records[0]["type_code"] != "investigator":
            continue

        link = card.get("investigator") or card.name
        investigators.setdefault(link, []).append(card)

        signatures[card.id] = []

    for card in cards:
        records = records_by_id[card.id]
        if not records or records[0]["type_code"] == "investigator":
            continue

        owners = investigators.get(card.get("investigator"), [])
        if not owners:
            continue

        restriction = "investigator:" + ":".join(owner.id for owner in owners)
        for record in records:
            record["restrictions"] = restriction

        if not card.get_meta("bonded"):
            for owner in owners:
                signatures[owner.id].append(f"card:{card.id}")

    for group in investigators.values():
        for investigator in group:
            requirements = (
                _deck_size_requirements(investigator.back)
                + signatures[investigator.id]
                + ["random:subtype:basicweakness"]
            )
            records_by_id[investigator.id][0]["deck_requirements"] = ", ".join(
                requirements
            )


def _plain_text(face: Face, value: object) -> str:
    mapped = map_text(face, "entries", str(value or ""))
    return " ".join(unescape(re.sub(r"<[^>]*>", "", mapped)).split())


def _deck_size_requirements(face: Face) -> list[str]:
    """The size requirement from the last valid "Deck Size" entry, if any."""
    labels = {label.casefold() for label in card_labels(face, "CARD_LABEL_DECK_SIZE")}

    requirements = []
    for header, value in face.get("entries", []):
        if _plain_text(face, header).casefold().rstrip(":： ") not in labels:
            continue

        match = re.fullmatch(r"(\d+)\.?", _plain_text(face, value))
        if match:
            requirements = [f"size:{int(match[1])}"]
    return requirements
