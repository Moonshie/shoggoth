"""Bundled Midnight modules and persistent, app-wide activation state.

Descriptors stay lightweight; implementations are imported by their hooks.
Rendering reads an in-memory snapshot, never QSettings from a worker thread.
"""
from dataclasses import dataclass
from collections.abc import Callable

from PySide6.QtCore import QObject, QSettings, Signal


@dataclass(frozen=True)
class CardImageNaming:
    """Name a card's front and any card-specific back."""

    key: str
    label: str
    filename: Callable[[str, bool, str], str]


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    description: str
    default_enabled: bool = True
    card_widget: Callable | None = None
    project_widget: Callable | None = None
    install_browser: Callable | None = None
    annotate_tree: Callable | None = None
    update_tree: Callable | None = None
    tree_data_keys: tuple[str, ...] = ()
    transfer_card: Callable | None = None
    text_layers: Callable | None = None
    card_image_naming: CardImageNaming | None = None
    player_tree: Callable | None = None


class ModuleManager(QObject):
    changed = Signal(str, bool)

    def __init__(self, settings=None, modules=None):
        super().__init__()
        if modules is None:
            from shoggoth.midnight.modules import MODULES
            modules = MODULES
        self.modules = tuple(modules)
        if len({module.id for module in self.modules}) != len(self.modules):
            raise ValueError('Module IDs must be unique.')
        self.settings = settings if settings is not None else QSettings('Shoggoth', 'Shoggoth')
        self._enabled = {}
        for module in self.modules:
            value = self.settings.value(self.setting_key(module.id), module.default_enabled)
            self._enabled[module.id] = (value.lower() in ('true', '1', 'yes')
                                        if isinstance(value, str) else bool(value))

    @staticmethod
    def setting_key(module_id):
        return f'midnight/modules/{module_id}/enabled'

    def is_enabled(self, module_id):
        return self._enabled[module_id]

    def set_enabled(self, module_id, enabled):
        enabled = bool(enabled)
        if self.is_enabled(module_id) == enabled:
            return
        self.settings.setValue(self.setting_key(module_id), enabled)
        self.settings.sync()
        self._enabled[module_id] = enabled
        self.changed.emit(module_id, enabled)


_manager = None


def module_manager():
    global _manager
    if _manager is None:
        _manager = ModuleManager()
    return _manager
