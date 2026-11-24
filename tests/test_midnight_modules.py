"""Activation, data preservation, and credit rendering through native paths."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image, ImageChops
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication, QMainWindow, QStyleOptionViewItem

from conftest import card_data, project_data
from shoggoth.arkham_build.cards import export_card
from shoggoth.cloud.merge import from_wire, to_wire
from shoggoth.midnight.hooks import text_layers, transfer_card
from shoggoth.midnight.modules.designer.model import designer, set_designer
from shoggoth.midnight.modules.design_tags.tags import card_tags, save_tag, set_card_tags
from shoggoth.midnight.registry import Module, ModuleManager
from shoggoth.midnight.ui import ModulesMenu
from shoggoth.project import Project
from shoggoth.renderer import CardRenderer


@pytest.fixture(scope='module')
def _qt_application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def qt_app(_qt_application):
    yield _qt_application
    for widget in _qt_application.topLevelWidgets():
        widget.deleteLater()
    _qt_application.sendPostedEvents(None, QEvent.DeferredDelete)


def test_activation_is_persistent_independent_and_does_not_mutate_projects(
        midnight_modules, load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    original = deepcopy(project.data)
    assert designer(project.get_card('a')) == ''
    assert list(text_layers(project.get_card('a').front)) == []
    assert all(midnight_modules.is_enabled(m.id) for m in midnight_modules.modules)
    midnight_modules.set_enabled('designer', False)
    assert midnight_modules.is_enabled('design_tags')
    reloaded = ModuleManager(midnight_modules.settings)
    assert not reloaded.is_enabled('designer')
    assert reloaded.is_enabled('design_tags')
    assert project.data == original
    assert not project.dirty


def test_designer_roundtrip_cloud_and_disabled_transfer_preserve_both_modules(
        midnight_modules, load_project):
    project = load_project(project_data(cards=[card_data('a', meta={
        'tags': ['public'], 'midnight': {'other': 42}})]))
    card = project.get_card('a')
    tag_id = save_tag(project, 'Review', ['seeker'])
    set_card_tags(card, [tag_id])
    native_front = deepcopy(card.front.data)
    original_export = export_card(card)[0]
    notifications = []
    Project.add_change_listener(lambda p, kind, element_id, changed:
                               notifications.append(deepcopy(p._locate(element_id)[1])))
    set_designer(card, '  Mint Tea Fan  ')
    assert notifications[-1]['meta']['midnight']['designer'] == 'Mint Tea Fan'
    assert card.front.data == native_front
    assert export_card(card)[0] == original_export
    project.save_all()
    reloaded = Project.load(project.file_path)
    assert designer(reloaded.get_card('a')) == 'Mint Tea Fan'
    cloud = Project('cloud.shoggoth', from_wire(to_wire(project.data)))
    assert designer(cloud.get_card('a')) == 'Mint Tea Fan'
    midnight_modules.set_enabled('designer', False)
    midnight_modules.set_enabled('design_tags', False)
    destination = load_project(project_data(), 'destination.shoggoth')
    data = deepcopy(card.data)
    transfer_card(card, destination, data)
    destination.add_card(data)
    assert designer(destination.get_card('a')) == 'Mint Tea Fan'
    assert card_tags(destination.get_card('a')) == card_tags(card)
    set_designer(card, '')
    assert card.get_meta('midnight') == {'design_tags': [tag_id], 'other': 42}
    assert card.get_meta('tags') == ['public']
    project.save_all()
    set_designer(card, '  ')
    assert not project.dirty


def test_live_menu_toggles_editors_without_losing_unsaved_input(
        qt_app, midnight_modules, load_project, defaults):
    from shoggoth.ui.card_editor import CardEditor
    from shoggoth.ui.project_editor import ProjectEditor
    defaults('asset', {})
    defaults('player', {})
    project = load_project(project_data(cards=[card_data('a')]))
    card = project.get_card('a')
    editor = CardEditor(card)
    project_editor = ProjectEditor(project)
    credit = editor.modules.widgets['designer']
    credit.input.setText('Mint Tea Fan')
    editor._set_view('json')
    editor.json_editor.setPlainText('{"unsaved":')
    window = QMainWindow()
    window.card_renderer = SimpleNamespace(card_wo_illus_cache={})
    window.preview = SimpleNamespace(rerender_now=Mock())
    menu = ModulesMenu(window, window.menuBar())
    assert menu.menu.title() == 'Modules'
    assert list(menu.actions) == ['design_tags', 'designer']
    menu.actions['designer'].trigger()
    assert credit.isHidden()
    assert not editor.modules.widgets['design_tags'].isHidden()
    assert designer(card) == 'Mint Tea Fan'
    menu.actions['design_tags'].trigger()
    assert editor.modules.isHidden()
    assert not project_editor.tabs.isTabVisible(2)
    menu.actions['designer'].trigger()
    assert not editor.modules.isHidden() and not credit.isHidden()
    assert credit.input.text() == 'Mint Tea Fan'
    assert editor.json_editor.toPlainText() == '{"unsaved":'
    menu.actions['design_tags'].trigger()
    assert project_editor.tabs.isTabVisible(2)
    assert window.preview.rerender_now.call_count == 4


@pytest.mark.parametrize('mode', ['tree', 'folders', 'list'])
def test_disabled_tag_module_restores_native_sidebar_and_dismisses_pins(
        qt_app, midnight_modules, load_project, mode):
    from shoggoth.midnight.modules.design_tags.sidebar import DesignTagDelegate
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[card_data('a')]))
    card = project.get_card('a')
    tag_id = save_tag(project, 'Review', ['mystic'], secondary=True)
    set_card_tags(card, [tag_id])
    browser = FileBrowser()
    browser.set_project(project)
    browser.switch_view(mode)
    browser.resize(420, 500)
    browser.show()
    qt_app.processEvents()
    tree = browser.list_tree if mode == 'list' else browser.tree
    delegate = tree.itemDelegate()
    assert isinstance(delegate, DesignTagDelegate)
    item = (tree.topLevelItem(0).child(0) if mode == 'list' else browser.get_card_item(card.id, project))
    tree.setCurrentItem(item)
    index = tree.indexFromItem(item)
    option = QStyleOptionViewItem()
    option.rect = tree.visualRect(index)
    delegate.tally_popup._toggle_pin(index, option)
    assert delegate.tally_popup.is_pinned
    original = deepcopy(project.data)
    midnight_modules.set_enabled('design_tags', False)
    assert not isinstance(tree.itemDelegate(), DesignTagDelegate)
    assert not delegate.tally_popup.is_pinned
    assert not delegate.tally_popup._active
    assert tree.currentItem() is item
    midnight_modules.set_enabled('design_tags', True)
    assert tree.itemDelegate() is delegate
    assert delegate.tally_popup._active
    assert project.data == original


def test_future_registered_module_gets_menu_and_persistent_toggle(qt_app, monkeypatch, tmp_path):
    from shoggoth.midnight import registry
    manager = ModuleManager(QSettings(str(tmp_path / 'future.ini'), QSettings.IniFormat),
                            modules=[Module('future', 'Future module', 'A future extension.')])
    monkeypatch.setattr(registry, '_manager', manager)
    window = QMainWindow()
    window.card_renderer = SimpleNamespace(card_wo_illus_cache={})
    window.preview = SimpleNamespace(rerender_now=Mock())
    menu = ModulesMenu(window, window.menuBar())
    assert menu.actions['future'].text() == 'Future module'
    menu.actions['future'].trigger()
    assert not ModuleManager(manager.settings, modules=manager.modules).is_enabled('future')


def test_designer_modification_edits_leave_parent_locked_and_unchanged(
        qt_app, midnight_modules, write_project, tmp_path, defaults):
    from shoggoth.modification import ModificationProject
    from shoggoth.ui.modification_editors import ModificationCompareEditor, TranslationEditor
    defaults('asset', {})
    defaults('player', {})
    path = write_project(project_data(cards=[card_data('a', meta={
        'midnight': {'designer': 'Original Designer'}})]))
    original_text = path.read_text()
    modification = ModificationProject.create(tmp_path / 'modification.shoggoth', path)
    translation = TranslationEditor(modification.get_card('a'))
    translation.modules.widgets['designer'].input.setText('Mint Tea Fan')
    comparison = ModificationCompareEditor(modification.get_card('a'))
    assert comparison.editor.modules.widgets['designer'].isEnabled()
    assert not comparison.original_editor.modules.widgets['designer'].isEnabled()
    midnight_modules.set_enabled('designer', False)
    midnight_modules.set_enabled('designer', True)
    assert not comparison.original_editor.modules.widgets['designer'].isEnabled()
    modification.save_all()
    reloaded = Project.load(modification.file_path)
    assert designer(reloaded.get_card('a')) == 'Mint Tea Fan'
    assert designer(reloaded.original_card('a')) == 'Original Designer'
    assert path.read_text() == original_text


@pytest.mark.parametrize('rotation,anchor_x', [(0, 153), (90, 200), (90, 42)])
def test_credit_follows_resolved_collection_footer_without_changing_assets(
        midnight_modules, load_project, defaults, rotation, anchor_x):
    region = {'x': anchor_x, 'y': 2097, 'width': 1360, 'height': 40, 'attach_after': 'copyright'}
    font = {'font': 'bold', 'size': 38, 'color': 'white', 'rotation': rotation}
    footer = {
        'collection_icon_region': {'x': 1315, 'y': 2093, 'width': 80, 'height': 50},
        'collection_number_region': {'x': 1411, 'y': 2096, 'width': 180, 'height': 40},
        'collection_number_font': {'font': 'bold', 'size': 38, 'color': 'white', 'alignment': 'left'},
    }
    defaults('footer', footer)
    defaults('asset', {'parent': 'footer', 'illustrator_region': region, 'illustrator_font': font})
    project = load_project(project_data(cards=[card_data('a', front={
        'type': 'asset', 'illustrator': 'Native Artist', 'copyright': 'Native Copyright'})]))
    card = project.get_card('a')
    set_designer(card, 'Mint & <Tea> Fan')
    original = deepcopy(project.data)
    renderer = CardRenderer(locale=None)
    renderer.rich_text.render_text = Mock()
    renderer.render_text(Image.new('RGB', (1644, 2244)), card.front, 0.5)
    calls = renderer.rich_text.render_text.call_args_list
    designer_call = calls[-1]
    assert designer_call.args[1] == 'Des. Mint &amp; &lt;Tea&gt; Fan'
    credit_region = list(text_layers(card.front))[0].get('midnight_designer_region')
    assert credit_region == {'x': 696, 'y': 2096, 'width': 600, 'height': 40}
    assert designer_call.kwargs['font_size'] == 38
    assert designer_call.kwargs['scale'] == 0.5
    assert designer_call.kwargs['fill'] == 'white'
    assert designer_call.kwargs['alignment'] == 'right'
    assert project.data == original
    assert card.front['illustrator_region'] == region
    assert card.front['illustrator_font'] == font
    assert card.front['collection_icon_region'] == footer['collection_icon_region']
    assert card.front['collection_number_region'] == footer['collection_number_region']
    midnight_modules.set_enabled('designer', False)
    renderer.rich_text.render_text.reset_mock()
    renderer.render_text(Image.new('RGB', (1644, 2244)), card.front)
    assert not any('Des.' in call.args[1] for call in renderer.rich_text.render_text.call_args_list)


def test_empty_credits_and_faces_without_footer_anchors_have_no_layer(load_project, defaults):
    defaults('asset', {})
    project = load_project(project_data(cards=[card_data('a')]))
    card = project.get_card('a')
    set_designer(card, 'Mint Tea Fan')
    assert list(text_layers(card.front)) == []
    card.front.set('collection_icon_region', {'width': 0, 'height': 40})
    assert list(text_layers(card.front)) == []
    card.front.set('collection_icon_region', {'x': 1315, 'width': 80, 'height': 50})
    assert len(list(text_layers(card.front))) == 1  # Reserve the slot even without an icon.
    set_designer(card, '')
    assert list(text_layers(card.front)) == []


@pytest.mark.assets
@pytest.mark.parametrize('kind', ['asset', 'event', 'skill'])
def test_native_rendered_export_changes_only_before_collection_footer(
        midnight_modules, load_project, tmp_path, kind):
    icon_path = tmp_path / 'collection-icon.png'
    Image.new('RGBA', (64, 64), 'white').save(icon_path)
    project = load_project(project_data(cards=[card_data('a', front={
        'type': kind, 'name': 'Designer test', 'classes': ['seeker'],
        'illustrator': 'Native Artist'})], icon=str(icon_path)))
    card = project.get_card('a')
    set_designer(card, 'Mint Tea Fan')
    renderer = CardRenderer(locale='en')
    kwargs = dict(include_bleed=True, trim=None)
    enabled = renderer.render_card_side(card, card.front, **kwargs)
    midnight_modules.set_enabled('designer', False)
    disabled = renderer.render_card_side(card, card.front, **kwargs)
    difference = ImageChops.difference(enabled, disabled)
    box = difference.getbbox()
    assert box is not None
    midnight_modules.set_enabled('designer', True)
    region = list(text_layers(card.front))[0].get('midnight_designer_region')
    assert box[0] >= region['x']
    assert box[1] >= region['y']
    assert box[2] <= region['x'] + region['width'] < card.front['collection_icon_region']['x']
    assert box[3] <= region['y'] + region['height']
    # Every pixel outside the new credit remains the same, including the
    # illustrator, collection icon/number, and the event/skill rules box.
    difference.paste((0, 0, 0), (region['x'], region['y'],
                               region['x'] + region['width'], region['y'] + region['height']))
    assert difference.getbbox() is None
    midnight_modules.set_enabled('designer', True)
    folder = tmp_path / 'export'
    folder.mkdir()
    outputs = renderer.export_card_images(card, str(folder),
                                         {'width': 1500, 'height': 2100, 'bleed': 72, 'trim': None},
                                         bleed=True, format='png')
    with Image.open(outputs[0]) as exported:
        assert ImageChops.difference(exported.convert('RGB'), enabled).getbbox() is None
    renderer.export_card_images(card, str(folder),
                                {'width': 1500, 'height': 2100, 'bleed': 72, 'trim': None},
                                bleed=True, format='png', text_as_html=True)
    html = Path(outputs[0]).with_suffix('.html').read_text()
    assert 'Des. Mint Tea Fan' in html
    assert 'Native Artist' in html
    midnight_modules.set_enabled('designer', False)
    renderer.export_card_images(card, str(folder),
                                {'width': 1500, 'height': 2100, 'bleed': 72, 'trim': None},
                                bleed=True, format='png', text_as_html=True)
    html = Path(outputs[0]).with_suffix('.html').read_text()
    assert 'Des. Mint Tea Fan' not in html
    assert 'Native Artist' in html
