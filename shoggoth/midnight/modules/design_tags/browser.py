"""Activate tag presentation without replacing native browser state."""
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QStyledItemDelegate

from shoggoth.ui.browser.drag_drop import CompactLeafDelegate
from .sidebar import DesignTagDelegate


class DesignTagsBrowser(QObject):
    def __init__(self, browser, manager):
        super().__init__(browser)
        self.browser = browser
        self.manager = manager
        self.delegates = []
        for tree, compact in ((browser.tree, True), (browser.list_tree, False)):
            native = CompactLeafDelegate(tree) if compact else QStyledItemDelegate(tree)
            tags = DesignTagDelegate(tree, compact=compact)
            self.delegates.append((tree, native, tags))
        manager.changed.connect(self._changed)
        self._apply(manager.is_enabled('design_tags'))

    def _apply(self, enabled):
        for tree, native, tags in self.delegates:
            tags.tally_popup.set_active(enabled)
            tree.setItemDelegate(tags if enabled else native)
            tree.viewport().update()

    def _changed(self, module_id, enabled):
        if module_id == 'design_tags':
            self._apply(enabled)
            if self.browser._view_mode != 'list':
                self.browser.refresh()
