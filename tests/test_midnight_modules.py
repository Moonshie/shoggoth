"""Activation, data preservation, rendering, and export through native paths."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image, ImageChops
from PySide6.QtCore import QEvent, QSettings, Qt
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
    assert list(menu.actions) == ['design_tags', 'designer', 'release_sync', 'tree_ordering']
    assert menu.actions['release_sync'].text() == 'Release sync'
    assert menu.actions['release_sync'].isChecked()
    assert menu.actions['tree_ordering'].text() == 'Tree Ordering'
    assert menu.actions['tree_ordering'].isChecked()
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


def test_tree_ordering_groups_investigators_class_levels_and_weaknesses(
        qt_app, midnight_modules, load_project, defaults):
    from shoggoth.ui.browser.file_browser import FileBrowser

    for card_type in ('asset', 'event', 'skill', 'investigator', 'treachery'):
        defaults(card_type, {'card_type': card_type})
    defaults('player', {})

    def make_card(card_id, name, card_type, card_class, level=0, **data):
        classes = card_class if isinstance(card_class, list) else [card_class]
        return card_data(card_id, name, front={'type': card_type, 'classes': classes, 'level': level}, **data)

    class_names = ('guardian', 'seeker', 'rogue', 'mystic', 'survivor', 'neutral')
    investigators = [make_card(f'{cls}-investigator', name, 'investigator', cls)
                     for cls, name in zip(class_names, ('Zed', 'Yan', 'Xin', 'Wren', 'Vale', 'Ada'))]
    class_cards = [make_card(f'{cls}-asset', 'Z Asset', 'asset', cls) for cls in class_names]
    project = load_project(project_data(cards=[
        *reversed(investigators), *reversed(class_cards),
        make_card('sig-z', 'Zulu Signature', 'asset', 'neutral', meta={'investigator': 'Zed'}),
        make_card('sig-a', 'alpha signature', 'skill', 'neutral', investigator='Zed'),
        make_card('sig-weakness', 'A Fault', 'treachery', 'weakness', investigator='Zed'),
        make_card('guardian-event', 'A Event', 'event', 'guardian'),
        make_card('guardian-skill', 'A Skill', 'skill', 'guardian'),
        make_card('guardian-level-10', 'A Level Ten', 'asset', 'guardian', '10'),
        make_card('guardian-level-2', 'Z Level Two', 'asset', 'guardian', '2'),
        make_card('multi', 'Multiclass Card', 'asset', ['guardian', 'seeker']),
        make_card('basic', 'Z Basic', 'treachery', 'basic weakness'),
        make_card('weakness', 'A Weakness', 'treachery', 'weakness'),
    ]))
    original = deepcopy(project.data)
    browser = FileBrowser()
    browser.set_project(project)
    root = browser.tree.topLevelItem(0)

    def children(item):
        return [item.child(i).data(0, Qt.UserRole) for i in range(item.childCount())]

    def card_ids(item):
        return [child['data'].id for child in children(item)]

    expected_classes = ['investigators', *class_names[:-1], 'other', 'neutral', 'basic weakness', 'weakness']
    assert [child['class'] for child in children(root)] == expected_classes
    investigator_header = root.child(0)
    assert [child['investigator'] for child in children(investigator_header)] == ['Zed', 'Yan', 'Xin', 'Wren', 'Vale', 'Ada']
    assert card_ids(investigator_header.child(0)) == ['guardian-investigator', 'sig-a', 'sig-z', 'sig-weakness']
    guardian = root.child(1)
    assert card_ids(guardian) == ['guardian-asset', 'guardian-event', 'guardian-skill', 'guardian-level-2', 'guardian-level-10']
    assert card_ids(root.child(root.childCount() - 2)) == ['basic']
    assert card_ids(root.child(root.childCount() - 1)) == ['weakness']
    assert project.data == original

    assert browser.select_item_in_tree('guardian-skill')
    current = browser.tree.currentItem()
    midnight_modules.set_enabled('tree_ordering', False)
    assert [child['class'] for child in children(root)] == [
        'investigators', 'seeker', 'rogue', 'guardian', 'mystic', 'survivor', 'neutral', 'other',
    ]
    assert browser.tree.currentItem() is current
    midnight_modules.set_enabled('tree_ordering', True)
    assert [child['class'] for child in children(root)] == expected_classes
    assert browser.tree.currentItem() is current
    assert project.data == original

    card = project.get_card('guardian-skill')
    card.front.set('level', 3)
    browser.update_card_node(card.id, project)
    qt_app.processEvents()
    assert card_ids(guardian) == ['guardian-asset', 'guardian-event', 'guardian-level-2', 'guardian-skill', 'guardian-level-10']
    assert browser.tree.currentItem() is current


def test_release_sync_exports_fronts_and_card_specific_backs(qt_app, load_project, tmp_path, monkeypatch):
    from shoggoth.ui.export_entry_widgets import ImagesEntryWidget
    from shoggoth.ui.export_runner import run_profile

    project = load_project(project_data(cards=[
        card_data('Player-ID', 'Player Card'),
        card_data('encounter-id', 'Encounter Card', back={'type': 'encounter'}, encounter_set='set'),
        card_data('location-id', 'Location', front={'type': 'location'},
                  back={'type': 'location', 'name': 'Reverse'},
                  encounter_set='set', encounter_number='1-3', amount=3),
    ], encounter_sets=[{'id': 'set', 'name': 'Set', 'icon': ''}]))
    card = project.get_card('location-id')
    assert len(card.versions) == 3
    fmt = 'midnight_release_sync_id'
    entry = {'type': 'images', 'settings': {'folder': 'release', 'separate_versions': True, 'include_backs': True}}
    widget = ImagesEntryWidget(project)
    widget.apply(entry)
    combo = widget._filename_combo
    index = combo.findData(fmt)
    assert index >= 0
    combo.setCurrentIndex(index)
    assert widget._separate.isHidden() and widget._backs.isHidden()
    entry.update(widget.read())
    assert entry['settings']['filename_format'] == fmt
    assert entry['settings']['separate_versions'] and entry['settings']['include_backs']

    renderer = CardRenderer.__new__(CardRenderer)

    def render_side(variant, side, **kwargs):
        assert variant is side.card
        color = 'blue' if side.data.get('name') == 'Reverse' else 'red'
        return Image.new('RGB', (1, 1), color)

    monkeypatch.setattr(renderer, 'render_card_side', render_side)
    results, errors = run_profile(widget, project, renderer, {'entries': [entry]})
    assert results and not errors
    folder = tmp_path / 'release'
    assert {path.name for path in folder.iterdir()} == {
        'Player-ID.png', 'encounter-id.png', 'location-id.png', 'location-id_back.png',
    }
    for card_id in ['Player-ID', 'encounter-id']:
        paths = renderer.expected_export_paths(project.get_card(card_id), folder, filename_format=fmt)
        assert paths == [str(folder / f'{card_id}.png')]
    expected = [folder / 'location-id.png', folder / 'location-id_back.png']
    assert renderer.expected_export_paths(card, folder, filename_format=fmt) == list(map(str, expected))
    for path, color in zip(expected, [(255, 0, 0), (0, 0, 255)]):
        with Image.open(path) as image:
            assert image.getpixel((0, 0)) == color
    combo.setCurrentIndex(combo.findData('id'))
    assert not widget._separate.isHidden() and widget._separate.isChecked()
    assert not widget._backs.isHidden() and widget._backs.isChecked()


def test_disabled_release_sync_preserves_saved_preset(qt_app, midnight_modules, load_project, tmp_path, monkeypatch):
    from shoggoth import i18n
    from shoggoth.ui.export_entry_widgets import ImagesEntryWidget
    from shoggoth.ui.export_runner import run_profile

    monkeypatch.setattr(i18n, '_fallback_translations', i18n.load_catalog('en'))
    fmt = 'midnight_release_sync_id'
    project = load_project(project_data(cards=[card_data('card-id')], export_profiles=[{
        'id': 'release', 'entries': [{
            'id': 'images', 'type': 'images', 'settings': {'folder': 'release', 'filename_format': fmt},
        }],
    }]))
    midnight_modules.set_enabled('release_sync', False)
    widget = ImagesEntryWidget(project)
    assert widget._filename_combo.findData(fmt) == -1
    profile = project.export_profiles[0]
    entry = profile.entries[0].data
    widget.apply(entry)
    combo = widget._filename_combo
    assert combo.currentData() == fmt
    assert not combo.model().item(combo.currentIndex()).isEnabled()
    entry.update(widget.read())
    assert entry['settings']['filename_format'] == fmt
    results, errors = run_profile(widget, project, None, profile.data)
    assert not results and len(errors) == 1
    assert 'Enable Release sync' in errors[0]
    assert not (tmp_path / 'release').exists()

    midnight_modules.set_enabled('release_sync', True)
    widget.apply(entry)
    assert combo.currentData() == fmt
    assert combo.model().item(combo.currentIndex()).isEnabled()


@pytest.mark.parametrize('upload_adapter', ['manual', 'cloudinary'])
def test_release_sync_reuses_images_for_arkham_build_and_renders_tts_separately(
        qt_app, load_project, tmp_path, monkeypatch, upload_adapter):
    import shoggoth
    from shoggoth import files, tts_lib, tts_sync
    from shoggoth.arkham_build import upload_adapters
    from shoggoth.ui.export_entry_widgets import ArkhamBuildEntryWidget
    from shoggoth.ui.export_runner import run_profile

    Image.new('RGB', (16, 16), 'green').save(tmp_path / 'icon.png')
    project = load_project(project_data(cards=[
        card_data('player-card', 'Player Card'),
        card_data('location-card', 'Location', front={'type': 'location'},
                  back={'type': 'location_back', 'name': 'Reverse'}),
    ], icon='icon.png'))
    monkeypatch.setattr(shoggoth, 'app', SimpleNamespace(current_project=project))
    monkeypatch.setattr(files, 'tts_dir', None)
    monkeypatch.setenv('CLOUDINARY_URL', 'cloudinary://test-key:test-secret@demo')
    uploads = {}

    def fake_upload(url, *, auth, files, data, timeout, allow_redirects):
        assert auth == ('test-key', 'test-secret')
        assert url.startswith('https://api.cloudinary.com/v1_1/demo/')
        assert data['overwrite'] == data['invalidate'] == 'true'
        assert timeout and not allow_redirects
        resource_type = url.split('/')[-2]
        public_id = data['public_id']
        filename, content, mime = files['file']
        uploads[(resource_type, public_id)] = (content.read(), mime)
        suffix = Path(filename).suffix if resource_type == 'image' else ''
        secure_url = f'https://res.cloudinary.com/demo/{resource_type}/upload/v2/{public_id}{suffix}'
        return SimpleNamespace(status_code=200, json=lambda: {'secure_url': secure_url})

    monkeypatch.setattr(upload_adapters.requests, 'post', fake_upload)
    build_widget = ArkhamBuildEntryWidget(project)
    build_widget.apply({'settings': {'upload_adapter': upload_adapter, 'url_prefix': 'https://example.com/cards'}})
    build_entry = {'type': 'arkham_build', **build_widget.read()}
    assert build_entry['settings']['upload_adapter'] == upload_adapter

    renderer = CardRenderer.__new__(CardRenderer)
    def render_side(card, side, **options):
        size = (options['width'], options['height']) if options['rotation'] == 'tts' else (300, 420)
        return Image.new('RGBA', size, (200, 20, 40, 100))

    rendered = Mock(side_effect=render_side)
    monkeypatch.setattr(renderer, 'render_card_side', rendered)
    images = {'type': 'images', 'settings': {
        'folder': 'release', 'filename_format': 'midnight_release_sync_id', 'format': 'png',
        'rounded': True, 'bleed': False,
    }}
    tts = {'type': 'tts', 'settings': {'folder': 'tts', 'export_images': True}}
    results, errors = run_profile(build_widget, project, renderer, {'entries': [tts, build_entry, images]})
    assert len(results) == 3 and not errors, errors
    assert all(call.kwargs['rounded'] and not call.kwargs['include_bleed'] for call in rendered.call_args_list)
    image_calls = [call for call in rendered.call_args_list if call.kwargs['rotation'] != 'tts']
    tts_calls = [call for call in rendered.call_args_list if call.kwargs['rotation'] == 'tts']
    assert len(image_calls) == 3
    assert len(tts_calls) == 4
    assert all({key: call.kwargs[key] for key in tts_lib.TTS_IMAGE_SIZE} == tts_lib.TTS_IMAGE_SIZE
               for call in tts_calls)

    release = tmp_path / 'release'
    tts_data = json.loads((tmp_path / f'{project.name} combined.json').read_text())
    tts_cards = {}
    tts_sync._extract_cards(tts_data['ObjectStates'], tts_cards)
    tts_folder = tmp_path / 'tts'
    tts_player_front = tts_folder / 'player-card_player_card_front_0.webp'
    tts_location_front = tts_folder / 'location-card_location_front_0.webp'
    tts_location_back = tts_folder / 'location-card_location_back_0.webp'
    assert tts_cards['player-card']['face'] == f'file:///{tts_player_front}'
    assert tts_cards['player-card']['back'] == tts_lib.DEFAULT_IMAGES['player']
    assert tts_cards['location-card']['face'] == f'file:///{tts_location_front}'
    assert tts_cards['location-card']['back'] == f'file:///{tts_location_back}'
    for path in (tts_player_front, tts_location_front, tts_location_back):
        with Image.open(path) as image:
            assert image.format == 'WEBP' and image.size == (1500, 2100)

    output_folder = upload_adapters.export_folder(project)
    data_path = output_folder / f'{project.id}.json'
    data = json.loads(data_path.read_text())
    records = {record['code']: record for record in data['data']['cards']}
    assert records['player-card']['image_url'].endswith('/player-card.png')
    assert 'back_image_url' not in records['player-card']
    assert records['location-card']['back_image_url'].endswith('/location-card_back.png')
    assert records['location-card']['back_thumbnail_url'].endswith('/location-card_back_thumbnail.webp')
    for stem in ('player-card', 'location-card', 'location-card_back'):
        source = release / f'{stem}.png'
        if upload_adapter == 'manual':
            local_copy = output_folder / project.id / source.name
            assert local_copy.read_bytes() == source.read_bytes()
        else:
            assert uploads[('image', f'shoggoth/arkham-build/{project.id}/{stem}')] == (source.read_bytes(), 'image/png')
    if upload_adapter == 'cloudinary':
        project_json_id = f'shoggoth/arkham-build/{project.id}/{data_path.name}'
        assert list(uploads)[-1] == ('raw', project_json_id)
        assert uploads[('raw', project_json_id)] == (data_path.read_bytes(), 'application/json')
        assert data['meta']['url'] == f'https://res.cloudinary.com/demo/raw/upload/v1/{project_json_id}'
        assert data['data']['packs'][0]['icon_url'].startswith('https://res.cloudinary.com/demo/image/upload/')
    else:
        assert not uploads


@pytest.mark.parametrize(('scope', 'suffix', 'single_cards', 'all_copies'), [
    ('all', 'combined', ['scenario', 'shared', 'player'], ['scenario'] * 2 + ['shared'] * 6 + ['player'] * 3),
    ('campaign', 'campaign', ['scenario', 'shared'], ['scenario'] * 2 + ['shared'] * 6),
    ('cards', 'player cards', ['player', 'scenario'], ['player'] * 3 + ['scenario'] * 2),
])
def test_release_sync_tts_exports_one_copy_per_card(
        qt_app, midnight_modules, load_project, tmp_path, monkeypatch, scope, suffix, single_cards, all_copies):
    import shoggoth
    from shoggoth import files, tts_sync
    from shoggoth.ui.export_runner import run_profile

    project = load_project(project_data(cards=[
        card_data('player', 'Player', amount=3, project_number=1),
        card_data('scenario', 'Scenario Card', amount=2, project_number=2, encounter_set='scenario-set'),
        card_data('shared', 'Shared Card', amount=3, project_number=3, encounter_set='shared-set'),
    ], encounter_sets=[
        {'id': 'scenario-set', 'name': 'Scenario', 'icon': '', 'order': 1,
         'meta': {'tts': {'included_sets': ['shared-set']}}},
        {'id': 'shared-set', 'name': 'Shared', 'icon': '', 'order': 2},
    ]))
    monkeypatch.setattr(shoggoth, 'app', SimpleNamespace(current_project=project))
    monkeypatch.setattr(files, 'tts_dir', None)
    send_to_tts = Mock()
    monkeypatch.setattr(tts_sync, 'push_to_tts', send_to_tts)
    profile = {'entries': [{
        'type': 'tts', 'scope': {'type': scope, 'card_ids': ['player', 'scenario']},
        'settings': {'export_images': False, 'sync': True},
    }]}

    def card_ids(bag):
        for obj in bag['ContainedObjects']:
            if obj['Name'] == 'Card':
                yield json.loads(obj['GMNotes'])['id']
            else:
                assert len(obj['DeckIDs']) == len(obj['ContainedObjects'])
                yield from card_ids(obj)

    for enabled, expected in [(True, single_cards), (False, all_copies)]:
        midnight_modules.set_enabled('release_sync', enabled)
        results, errors = run_profile(None, project, None, profile)
        assert len(results) == 1 and not errors, errors
        data = json.loads((tmp_path / f'{project.name} {suffix}.json').read_text())
        bag = data['ObjectStates'][0]
        assert list(card_ids(bag)) == expected
        assert list(card_ids(send_to_tts.call_args.args[0]['ObjectStates'][0])) == expected
        if enabled and scope in ('all', 'campaign'):
            scenario, shared = bag['ContainedObjects'][:2]
            assert list(card_ids(scenario)) == ['scenario']
            assert list(card_ids(shared)) == ['shared']


def test_release_sync_tts_update_exports_one_unused_copy(
        qt_app, load_project, tmp_path, monkeypatch):
    import shoggoth
    from shoggoth import files, tts_lib
    from shoggoth.ui.export_runner import run_profile

    project = load_project(project_data(cards=[
        card_data('placed', 'Placed Card', amount=3),
        card_data('unused', 'Unused Card', amount=4),
    ]))
    monkeypatch.setattr(shoggoth, 'app', SimpleNamespace(current_project=project))
    monkeypatch.setattr(files, 'tts_dir', None)
    saved_objects = [tts_lib.card_to_tts(project.get_card('placed'), index, tmp_path) for index in (1, 2)]
    for guid, obj in zip(('first', 'second'), saved_objects):
        obj['GUID'] = guid
    save_path = tmp_path / 'playtest.json'
    save_path.write_text(json.dumps({'ObjectStates': saved_objects}), encoding='utf-8')
    results, errors = run_profile(None, project, None, {'entries': [{
        'type': 'tts', 'settings': {'export_images': False, 'update_file': str(save_path)},
    }]})
    assert len(results) == 1 and not errors, errors
    updated = json.loads(save_path.read_text())['ObjectStates']
    assert [obj['GUID'] for obj in updated] == ['first', 'second']
    unused = json.loads((tmp_path / f'{project.name} unused cards.json').read_text())
    assert [json.loads(obj['GMNotes'])['id'] for obj in unused['ObjectStates'][0]['ContainedObjects']] == ['unused']


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
