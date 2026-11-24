"""Design annotations, independent of card rendering and gameplay exports."""
from shoggoth.midnight.registry import Module


def _card_widget(card):
    from .widgets import CardTagsWidget
    return CardTagsWidget(card)


def _project_widget(project):
    from .widgets import ProjectTagsWidget
    return ProjectTagsWidget(project)


def _install_browser(browser, manager):
    from .browser import DesignTagsBrowser
    return DesignTagsBrowser(browser, manager)


def _annotate_tree(spec, project):
    from .tallies import annotate_tree_tallies
    return annotate_tree_tallies(spec, project)


def _update_tree(item):
    from .tallies import update_tree_tallies
    update_tree_tallies(item)


def _transfer(card, destination, data):
    from .tags import transfer_card_tags
    transfer_card_tags(card, destination, data)


MODULE = Module(
    id='design_tags', name='Design tags',
    description='Project and card design tags, sidebar badges, and tag tallies.',
    card_widget=_card_widget, project_widget=_project_widget,
    install_browser=_install_browser, annotate_tree=_annotate_tree, update_tree=_update_tree,
    tree_data_keys=('midnight_tag_tallies',), transfer_card=_transfer,
)
