"""Export features for keeping published card images in sync."""
from shoggoth.midnight.registry import CardImageNaming, Module


def _filename(card_id, is_back, extension):
    suffix = '_back' if is_back else ''
    return f'{card_id}{suffix}.{extension}'


MODULE = Module(
    id='release_sync', name='Release sync',
    description='Use card IDs in filenames, share Images with arkham.build, and export one copy per card to TTS.',
    card_image_naming=CardImageNaming('midnight_release_sync_id', 'Card ID only ({id}, {id}_back)', _filename),
)
