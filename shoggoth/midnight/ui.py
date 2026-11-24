"""Module menu and editor hosts; activation never rebuilds native editors."""
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .registry import module_manager


class ModuleWidgets(QWidget):
    def __init__(self, owner, parent=None):
        super().__init__(owner if parent is None else parent)
        self.manager = module_manager()
        self.widgets = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for module in self.manager.modules:
            if module.card_widget:
                widget = module.card_widget(owner.card)
                widget.changed.connect(owner.data_changed.emit)
                layout.addWidget(widget)
                self.widgets[module.id] = widget
        self.manager.changed.connect(self._changed)
        self._update_visibility()

    def _update_visibility(self):
        for module_id, widget in self.widgets.items():
            widget.setVisible(self.manager.is_enabled(module_id))
        self.setVisible(any(self.manager.is_enabled(key) for key in self.widgets))

    def _changed(self, module_id, enabled):
        if module_id in self.widgets:
            if enabled:
                refresh = getattr(self.widgets[module_id], 'refresh', None)
                if refresh:
                    refresh()
            self._update_visibility()

    def refresh(self):
        for widget in self.widgets.values():
            refresh = getattr(widget, 'refresh', None)
            if refresh:
                refresh()


class ProjectModules(QObject):
    def __init__(self, editor, *, tabs=None, layout=None):
        super().__init__(editor)
        self.manager = module_manager()
        self.tabs = tabs
        self.widgets = {}
        for module in self.manager.modules:
            if module.project_widget:
                widget = module.project_widget(editor.project)
                widget.changed.connect(editor.data_changed.emit)
                if tabs is not None:
                    tabs.addTab(widget, module.name)
                else:
                    layout.addWidget(widget)
                self.widgets[module.id] = widget
        self.manager.changed.connect(self._changed)
        self._update_visibility()

    def _update_visibility(self):
        for module_id, widget in self.widgets.items():
            enabled = self.manager.is_enabled(module_id)
            if self.tabs is not None:
                self.tabs.setTabVisible(self.tabs.indexOf(widget), enabled)
            else:
                widget.setVisible(enabled)

    def _changed(self, module_id, enabled):
        if module_id in self.widgets:
            if enabled:
                refresh = getattr(self.widgets[module_id], 'refresh', None)
                if refresh:
                    refresh()
            self._update_visibility()


def install_browser(browser):
    manager = module_manager()
    return [module.install_browser(browser, manager) for module in manager.modules
            if module.install_browser]


class ModulesMenu(QObject):
    def __init__(self, window, menubar):
        super().__init__(window)
        self.window = window
        self.manager = module_manager()
        self.menu = menubar.addMenu('Modules')
        self.actions = {}
        self.menu.setToolTipsVisible(True)
        for module in self.manager.modules:
            action = QAction(module.name, self.menu)
            action.setToolTip(module.description)
            action.setCheckable(True)
            action.setChecked(self.manager.is_enabled(module.id))
            action.triggered.connect(
                lambda enabled, key=module.id: self.manager.set_enabled(key, enabled))
            self.menu.addAction(action)
            self.actions[module.id] = action
        self.manager.changed.connect(self._changed)

    def _changed(self, module_id, enabled):
        self.actions[module_id].setChecked(enabled)
        # The renderer is also used by export jobs. All render paths consult the
        # same manager; invalidate in-flight preview results and refresh pins.
        self.window.card_renderer.card_wo_illus_cache.clear()
        self.window.preview.rerender_now()
