"""Register bundled modules here; the menu and hosts consume this registry."""
from .design_tags import MODULE as DESIGN_TAGS
from .designer import MODULE as DESIGNER

MODULES = (DESIGN_TAGS, DESIGNER)
