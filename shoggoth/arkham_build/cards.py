from typing import Any, NamedTuple

from shoggoth.arkham_build.card_fields import export_face_fields
from shoggoth.arkham_build.card_types import (
    CARD_BACK_TYPE,
    UNSUPPORTED_TYPE,
    ResolvedCardType,
    is_double_sided,
    resolve_card_types,
)
from shoggoth.card import Face

_BACK_FIELDS = {"name", "subname", "traits", "text", "flavor", "illustrator"}


class ImageTarget(NamedTuple):
    """A face to render and the record that receives its image URLs."""

    face: Face
    record: dict[str, Any]
    field_prefix: str
    file_suffix: str
    card_type: ResolvedCardType


def export_card(card, *, image_mapper=None):
    """Return the card's records and the image targets for its faces."""
    front = card.front
    back = card.back

    front_type, back_type = resolve_card_types(front, back)

    if front_type in {CARD_BACK_TYPE, UNSUPPORTED_TYPE}:
        return [], []

    front_face = _export_face(card.id, front, front_type, image_mapper)
    targets = [ImageTarget(front, front_face, "", "", front_type)]

    if back_type == CARD_BACK_TYPE:
        return [front_face], targets

    if back_type == UNSUPPORTED_TYPE:
        targets.append(ImageTarget(back, front_face, "back_", "_back", back_type))
        return [front_face], targets

    if is_double_sided(front_type, back_type):
        back_fields = export_face_fields(back, image_mapper=image_mapper)
        front_face.update(
            {
                f"back_{field}": value
                for field, value in back_fields.items()
                if field in _BACK_FIELDS
            }
        )
        front_face["double_sided"] = True
        targets.append(ImageTarget(back, front_face, "back_", "_back", back_type))
        return [front_face], targets

    back_face = _export_face(f"{card.id}_back", back, back_type, image_mapper)
    front_face["back_link"] = back_face["code"]
    back_face["hidden"] = True
    targets.append(ImageTarget(back, back_face, "", "_back", back_type))

    return [front_face, back_face], targets


def apply_card_metadata(card, records):
    """Apply explicit metadata after generated fields, without changing the source."""
    metadata = card.get_meta("arkham_build")
    if not records or not isinstance(metadata, dict):
        return

    records[0].update({key: value for key, value in metadata.items() if key != "back"})
    back_metadata = metadata.get("back")
    if len(records) == 2 and isinstance(back_metadata, dict):
        records[1].update(back_metadata)


def _export_face(code, face, card_type, image_mapper):
    record = {
        "code": code,
        "pack_code": face.card.project.id,
        "type_code": card_type.code,
        **export_face_fields(face, image_mapper=image_mapper),
    }

    # The full-art template defaults clues for acts, which agendas don't have.
    if card_type.code == "agenda" and "clues" not in face.data:
        record.pop("clues", None)

    return record
