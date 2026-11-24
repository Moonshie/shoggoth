"""Register bundled modules here; the menu and hosts consume this registry."""
from .design_tags import MODULE as DESIGN_TAGS
from .designer import MODULE as DESIGNER
from .release_sync import MODULE as RELEASE_SYNC
from .tree_ordering import MODULE as TREE_ORDERING

MODULES = (DESIGN_TAGS, DESIGNER, RELEASE_SYNC, TREE_ORDERING)
