from collections.abc import Iterable
from pathlib import Path

from PIL import Image

from shoggoth.arkham_build.cards import ImageTarget
from shoggoth.arkham_build.thumbnails import extract_thumbnail
from shoggoth.arkham_build.upload_adapters import UploadAdapter
from shoggoth.card import Card
from shoggoth.midnight.modules.release_sync.exports import require_image
from shoggoth.renderer.card_renderer import CardRenderer, renderer_for_card


def export_card_images(
    card: Card,
    targets: Iterable[ImageTarget],
    adapter: UploadAdapter,
    renderer: CardRenderer,
    *,
    image_faces=None,
) -> None:
    if image_faces is None:
        renderer = renderer_for_card(renderer, card)

    for target in targets:
        stem = f"{card.id}{target.file_suffix}"
        thumbnail_filename = f"{stem}_thumbnail.webp"
        if image_faces is None:
            source = None
            filename = f"{stem}.webp"
            image_context = renderer.render_card_side(card, target.face, include_bleed=False)
        else:
            source = require_image(card, "back" if target.file_suffix else "front", image_faces)
            filename = f"{stem}{source.suffix}"
            image_context = Image.open(source)

        with image_context as image:
            if source is None:
                _save_webp(image, adapter.export_file(filename))

            with extract_thumbnail(image, target.face, target.card_type) as thumbnail:
                _save_webp(thumbnail, adapter.export_file(thumbnail_filename))

        prefix = target.field_prefix
        record = target.record

        record[f"{prefix}image_url"] = (adapter.image_url(filename) if source is None
                                        else adapter.image_url(filename, source=source))
        record[f"{prefix}thumbnail_url"] = adapter.image_url(thumbnail_filename)


def _save_webp(image: Image.Image, path: Path) -> None:
    image.save(path, format="WEBP", quality=80, method=6)
