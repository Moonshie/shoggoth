"""Share Images outputs with arkham.build within each export/publish group."""
from pathlib import Path

from shoggoth.midnight.registry import module_manager


def plan_entries(entries):
    if not module_manager().is_enabled('release_sync'):
        yield from ((entry, False) for entry in entries)
        return

    window = []
    for entry in entries:
        if entry.get('type') == 'publish':
            yield from _images_first(window)
            yield entry, False
            window.clear()
        else:
            window.append(entry)
    yield from _images_first(window)


def _images_first(entries):
    first_arkham_build = next((i for i, entry in enumerate(entries)
                               if entry.get('type') == 'arkham_build'), len(entries))
    tail = entries[first_arkham_build:]
    images = [entry for entry in tail if entry.get('type') == 'images']
    remaining = [entry for entry in tail if entry.get('type') != 'images']
    has_images = any(entry.get('type') == 'images' for entry in entries)
    for entry in [*entries[:first_arkham_build], *images, *remaining]:
        yield entry, has_images and entry.get('type') == 'arkham_build'


def require_image(card, face, image_faces):
    path = image_faces.get(card.id, {}).get(face)
    if not path or not Path(path).is_file():
        raise ValueError(f'Images did not export the {face} of "{card.name}" ({card.id}). '
                         'Check the Images scope and export result.')
    return Path(path)
