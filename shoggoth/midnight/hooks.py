"""Small, generic integration points shared by every Midnight module."""
from .registry import module_manager


def player_tree(project, cards):
    manager = module_manager()
    for module in manager.modules:
        if module.player_tree and manager.is_enabled(module.id):
            return module.player_tree(project, cards)
    return None


def annotate_tree(spec, project):
    manager = module_manager()
    for module in manager.modules:
        if module.annotate_tree and manager.is_enabled(module.id):
            spec = module.annotate_tree(spec, project)
    return spec


def update_tree(item):
    """Update module data for one item and report whether its tree spec needs syncing."""
    manager = module_manager()
    refresh = False
    for module in manager.modules:
        if module.update_tree and manager.is_enabled(module.id):
            if module.update_tree(item):
                refresh = True
    return refresh


def tree_data(spec):
    return {key: spec[key] for module in module_manager().modules
            for key in module.tree_data_keys if key in spec}


def transfer_card(card, destination, data):
    # Storage hooks always run: disabling presentation must not break copied data.
    for module in module_manager().modules:
        if module.transfer_card:
            module.transfer_card(card, destination, data)


def text_layers(side):
    manager = module_manager()
    for module in manager.modules:
        if module.text_layers and manager.is_enabled(module.id):
            yield from module.text_layers(side)


def card_image_naming_options():
    manager = module_manager()
    for module in manager.modules:
        if module.card_image_naming is not None:
            yield module.card_image_naming, module.name, manager.is_enabled(module.id)


def resolve_card_image_naming(key):
    for naming, module_name, enabled in card_image_naming_options():
        if naming.key == key:
            if not enabled:
                raise ValueError(f'Enable {module_name} in the Modules menu to use {naming.label}.')
            return naming
    return None
