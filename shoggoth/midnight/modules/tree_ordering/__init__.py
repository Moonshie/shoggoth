"""Optional player-card ordering for the grouped tree."""
from shoggoth.midnight.registry import Module


def _player_tree(project, cards):
    from .tree import build_player_tree
    return build_player_tree(project, cards)


def _install_browser(browser, manager):
    from .tree import TreeOrderingBrowser
    return TreeOrderingBrowser(browser, manager)


def _update_tree(item):
    from .tree import ordering_changed
    return ordering_changed(item)


MODULE = Module(
    id='tree_ordering', name='Tree Ordering',
    description='Order the grouped player-card tree by investigator, class, level, and weakness type.',
    player_tree=_player_tree, install_browser=_install_browser, update_tree=_update_tree,
    tree_data_keys=('midnight_tree_order',),
)
