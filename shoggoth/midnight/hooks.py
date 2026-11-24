"""Small, generic integration points shared by every Midnight module."""
from .registry import module_manager


def annotate_tree(spec, project):
    manager = module_manager()
    for module in manager.modules:
        if module.annotate_tree and manager.is_enabled(module.id):
            spec = module.annotate_tree(spec, project)
    return spec


def update_tree(item):
    manager = module_manager()
    for module in manager.modules:
        if module.update_tree and manager.is_enabled(module.id):
            module.update_tree(item)


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
