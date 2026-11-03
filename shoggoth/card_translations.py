import json
import logging

from shoggoth.files import translation_dir


logger = logging.getLogger(__name__)

CARD_KEYWORD_DEFAULTS = {
    "<for>": "<b>Forced –</b>",
    "<prey>": "<b>Prey –</b>",
    "<rev>": "<b>Revelation –</b>",
    "<spawn>": "<b>Spawn –</b>",
    "<obj>": "<b>Objective –</b>",
    "<objective>": "<b>Objective –</b>",
}


def load_card_translations(language):
    """Load card translations. Use English keyword defaults if the file is invalid."""
    path = translation_dir / f"{language or 'en'}.json"
    try:
        with path.open(encoding="utf-8") as file:
            translations = json.load(file)
        if not isinstance(translations, dict) or not all(
            isinstance(value, str) for value in translations.values()
        ):
            raise ValueError("Card translations must be a string map")
        return translations
    except (OSError, UnicodeError, ValueError):
        logger.warning(
            "Card translations unavailable; using English keyword defaults",
            extra={"language": language or "en", "translation_path": str(path)},
        )
        return {}
