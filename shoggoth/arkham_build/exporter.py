import datetime
from collections.abc import Callable, Mapping
from typing import Any, NotRequired, TypedDict

from shoggoth.arkham_build.assets import ImageAssetExporter
from shoggoth.arkham_build.card_fields import compact
from shoggoth.arkham_build.cards import ImageTarget, apply_card_metadata, export_card
from shoggoth.arkham_build.deckbuilding import add_deckbuilding_fields
from shoggoth.arkham_build.images import export_card_images
from shoggoth.card import Card
from shoggoth.project import Project
from shoggoth.renderer.card_renderer import CardRenderer
from shoggoth.updater import get_current_version as shoggoth_version

type CardExecutor = Callable[[list[Card], Callable[[Card], None]], None]


class _GroupData(TypedDict):
    id: str
    name: str
    icon: NotRequired[str]


class _ExportedGroup(TypedDict):
    code: str
    name: str
    icon_url: NotRequired[str]


_STATUSES = {"draft", "alpha", "beta", "complete", "final"}
_CONTENT_TYPES = {"campaign", "investigators", "player_cards", "rework", "scenario"}


# FIXME: `meta.url` could be derived for Celeano cloud projects
def export_project(
    project: Project,
    settings: Mapping[str, Any],
    renderer: CardRenderer,
    *,
    card_executor: CardExecutor,
) -> dict[str, object]:
    assert renderer is not None, "A configured renderer is required"
    assert callable(card_executor), "A card executor is required"

    data = project.data
    url_prefix = (settings.get("url_prefix") or "").strip().rstrip("/")
    assets = ImageAssetExporter(project, url_prefix)

    return {
        "meta": _project_meta(data),
        "data": {
            "cards": _export_cards(
                project, url_prefix, renderer, card_executor, assets
            ),
            "packs": [_export_group(data, assets)],
            "encounter_sets": [
                _export_group(encounter_set, assets)
                for encounter_set in data.get("encounter_sets", [])
            ],
        },
    }


def _export_group(data: _GroupData, assets: ImageAssetExporter) -> _ExportedGroup:
    group: _ExportedGroup = {"code": data["id"], "name": data["name"]}

    icon_url = assets.export(data.get("icon"))
    if icon_url is not None:
        group["icon_url"] = icon_url

    return group


def _export_cards(
    project: Project,
    url_prefix: str,
    renderer: CardRenderer,
    card_executor: CardExecutor,
    assets: ImageAssetExporter,
) -> list[dict[str, object]]:
    cards = [Card(data, project) for data in project.data["cards"]]
    records_by_id = {}
    targets_by_id: dict[str, list[ImageTarget]] = {}
    for card in cards:
        records_by_id[card.id], targets_by_id[card.id] = export_card(
            card, image_mapper=assets.map_tag
        )

    def export_images(card: Card) -> None:
        export_card_images(card, targets_by_id[card.id], url_prefix, renderer)

    image_cards = [card for card in cards if url_prefix and targets_by_id[card.id]]
    if image_cards:
        card_executor(image_cards, export_images)

    add_deckbuilding_fields(cards, records_by_id)
    for card in cards:
        apply_card_metadata(card, records_by_id[card.id])

    return [record for records in records_by_id.values() for record in records]


def _project_meta(data: Mapping[str, Any]) -> dict[str, object]:
    meta = data.get("meta", {})
    language = meta.get("language") or "en"
    status = meta.get("status")
    types = [t for t in meta.get("types") or [] if t in _CONTENT_TYPES]

    return {
        "author": meta.get("author", ""),
        "code": data["id"],
        "date_updated": datetime.datetime.now().isoformat(),
        "language": language,
        "generator": f"Shoggoth/{shoggoth_version()}",
        "name": data["name"],
        **compact(
            {
                "banner_url": meta.get("banner_url"),
                "banner_credit": meta.get("banner_credit"),
                "description": meta.get("description"),
                "external_link": meta.get("website_url"),
                "status": status if status in _STATUSES else "draft",
                "tags": meta.get("tags"),
                "types": types or None,
            }
        ),
    }
