"""Tag persistence and native UI/export boundaries; no asset pack needed."""
from copy import deepcopy
import json

import pytest
from PySide6.QtCore import Qt, QElapsedTimer, QEvent, QModelIndex, QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QMainWindow, QScrollArea, QStatusBar, QVBoxLayout, QWidget,
)

from conftest import card_data, project_data
from shoggoth.arkham_build import export_project
from shoggoth.cloud.merge import from_wire, to_wire
from shoggoth.export_helpers import build_gm_notes
from shoggoth.midnight.presentation import TagChip, paint_badge
from shoggoth.midnight.tallies import TALLY_KEY
from shoggoth.midnight.tags import (
    card_tag_ids, card_tags, delete_tag, is_secondary, matching_project_tags, project_tags, reorder_tags, save_tag, set_card_tags,
    transfer_card_tags,
)
from shoggoth.midnight.widgets import CardTagsWidget, ProjectTagsWidget, TagEditDialog
from shoggoth.modification import ModificationProject
from shoggoth.project import Project
from shoggoth.ui.compact_widgets import CLASS_CHIP_COLORS


@pytest.fixture(scope='module')
def _qt_application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def qt_app(_qt_application):
    yield _qt_application
    # Closing hides Qt windows; destroy the test widgets while their app is alive.
    for widget in _qt_application.topLevelWidgets():
        widget.deleteLater()
    _qt_application.sendPostedEvents(None, QEvent.DeferredDelete)


def test_old_projects_are_not_modified_by_reading_tags(load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    original = deepcopy(project.data)
    assert project_tags(project) == []
    assert card_tags(project.get_card('a')) == []
    assert project.data == original
    assert not project.dirty


def test_tags_survive_native_save_reload_and_individual_card_save(load_project):
    project = load_project(project_data(cards=[card_data('a'), card_data('b')]))
    tag_id = save_tag(project, 'Économie', ['seeker', 'seeker', 'rogue'] * 5)
    plain_id = save_tag(project, 'Needs review')
    set_card_tags(project.get_card('a'), [tag_id, tag_id, plain_id])
    project.save_all()
    project = Project.load(project.file_path)
    assert [tag['name'] for tag in card_tags(project.get_card('a'))] == ['Économie', 'Needs review']
    assert card_tags(project.get_card('a'))[0]['pips'] == ['seeker', 'seeker', 'rogue'] * 5
    assert not project.dirty
    set_card_tags(project.get_card('b'), [plain_id])
    project.get_card('b').save()
    reloaded = Project.load(project.file_path)
    assert card_tag_ids(reloaded.get_card('b')) == [plain_id]
    assert project_tags(reloaded) == project_tags(project)


def test_secondary_designation_preserves_legacy_tags_and_roundtrips(load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    main = save_tag(project, 'Draw', ['seeker'])
    secondary = save_tag(project, 'Review', secondary=True)
    set_card_tags(project.get_card('a'), [secondary, main])
    assert not is_secondary(project_tags(project)[0])
    assert 'secondary' not in project_tags(project)[0]
    project.save_all()
    project = Project.load(project.file_path)
    assert [is_secondary(tag) for tag in card_tags(project.get_card('a'))] == [False, True]
    save_tag(project, 'Needs review', [], secondary)
    assert is_secondary(project_tags(project)[1])
    save_tag(project, 'Needs review', [], secondary, secondary=False)
    assert not is_secondary(project_tags(project)[1])
    assert 'secondary' not in project_tags(project)[1]
    assert card_tag_ids(project.get_card('a')) == [secondary, main]
    project.save_all()
    with pytest.raises(ValueError):
        save_tag(project, 'Invalid', secondary='secondary')
    assert not project.dirty


def test_transferred_secondary_definition_does_not_merge_with_main_tag(load_project):
    source = load_project(project_data(cards=[card_data('a')]), 'source.shoggoth')
    dest = load_project(project_data(), 'dest.shoggoth')
    secondary = save_tag(source, 'Review', ['seeker'], secondary=True)
    main = save_tag(dest, 'Review', ['seeker'])
    set_card_tags(source.get_card('a'), [secondary])
    data = deepcopy(source.get_card('a').data)
    transfer_card_tags(source.get_card('a'), dest, data)
    dest.add_card(data)
    tag = card_tags(dest.get_card('a'))[0]
    assert tag['name'] == 'Review (2)' and is_secondary(tag)
    assert tag['id'] != main
    assert not is_secondary(project_tags(dest)[0])
    repeated = deepcopy(source.get_card('a').data)
    repeated['id'] = 'b'
    transfer_card_tags(source.get_card('a'), dest, repeated)
    dest.add_card(repeated)
    assert len(project_tags(dest)) == 2
    assert card_tag_ids(dest.get_card('a')) == card_tag_ids(dest.get_card('b'))
    assert card_tag_ids(source.get_card('a')) == [secondary]


def test_rename_and_delete_keep_assignments_consistent_and_preserve_metadata(load_project):
    project = load_project(project_data(cards=[card_data('a', meta={'tags': ['public'],
        'midnight': {'other_feature': 'keep'}})], meta={'midnight': {'other_feature': 42}}))
    tag_id = save_tag(project, 'Draft', ['guardian'])
    card = project.get_card('a')
    set_card_tags(card, [tag_id])
    save_tag(project, 'Final', [], tag_id)
    assert card_tags(card) == [{'id': tag_id, 'name': 'Final', 'pips': []}]
    delete_tag(project, tag_id)
    assert card_tags(card) == []
    assert project.get_meta('midnight') == {'other_feature': 42}
    assert card.get_meta('midnight') == {'other_feature': 'keep'}
    assert card.get_meta('tags') == ['public']
    project.save_all()
    assert card_tag_ids(Project.load(project.file_path).get_card('a')) == []


def test_validation_and_noop_do_not_mutate_projects(load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    tag_id = save_tag(project, 'Draft')
    project.save_all()
    for name, pips in [('', []), (' draft ', []), ('Other', ['blue'])]:
        with pytest.raises(ValueError):
            save_tag(project, name, pips)
    with pytest.raises(ValueError):
        set_card_tags(project.get_card('a'), ['foreign-project-tag'])
    save_tag(project, 'Draft', [], tag_id)
    set_card_tags(project.get_card('a'), [])
    assert not project.dirty


def test_card_display_uses_project_order_and_reorder_survives_reload(load_project):
    project = load_project(project_data(cards=[card_data('a'), card_data('b')]))
    first, second, third = [save_tag(project, name) for name in ['Draw', 'Economy', 'Testing']]
    set_card_tags(project.get_card('a'), [third, first, second])
    set_card_tags(project.get_card('b'), [third, first])
    project.save_all()
    assignments = [card_tag_ids(project.get_card(card_id)) for card_id in ['a', 'b']]
    assert [tag['id'] for tag in card_tags(project.get_card('a'))] == [first, second, third]
    reorder_tags(project, [third, second, first])
    assert [tag['id'] for tag in card_tags(project.get_card('a'))] == [third, second, first]
    assert [tag['id'] for tag in card_tags(project.get_card('b'))] == [third, first]
    assert [card_tag_ids(project.get_card(card_id)) for card_id in ['a', 'b']] == assignments
    assert all(not project.get_card(card_id).dirty for card_id in ['a', 'b'])
    project.save_all()
    reloaded = Project.load(project.file_path)
    assert [tag['id'] for tag in card_tags(reloaded.get_card('a'))] == [third, second, first]
    assert [tag['id'] for tag in card_tags(reloaded.get_card('b'))] == [third, first]
    reorder_tags(reloaded, [third, second, first])
    assert not reloaded.dirty
    for invalid_order in [[first, second], [first, first, third], [first, second, 'unknown']]:
        with pytest.raises(ValueError):
            reorder_tags(reloaded, invalid_order)
    assert not reloaded.dirty


@pytest.mark.parametrize(('classes', 'expected'), [
    (['seeker'], ['Seeker', 'Mixed']),
    (['seeker', 'mystic'], ['Seeker', 'Mystic', 'Mixed']),
    (['guardian'], ['Guardian', 'Mixed']),
    (['neutral'], ['Neutral']),
    ([], []),
    (' Seeker, Mystic ', ['Seeker', 'Mystic', 'Mixed']),
])
def test_matching_tags_use_any_class_and_preserve_project_order(load_project, defaults, classes, expected):
    defaults('asset', {})
    defaults('player', {})
    project = load_project(project_data(cards=[card_data('a', front={'type': 'asset', 'classes': classes})]))
    for name, pips in [('Seeker', ['seeker']), ('Guardian', ['guardian']),
                       ('Mystic', ['mystic']), ('Mixed', ['guardian', 'seeker', 'seeker']),
                       ('Neutral', ['neutral']), ('No pips', [])]:
        save_tag(project, name, pips)
    assert [tag['name'] for tag in matching_project_tags(project.get_card('a'))] == expected


def test_matching_tags_resolve_inherited_classes_and_back_fallback(load_project, defaults):
    defaults('asset', {})
    project = load_project(project_data(cards=[
        card_data('parent', front={'type': 'asset', 'classes': ['mystic']}),
        card_data('child', front={'type': 'asset', 'inherit': {'card': 'parent', 'face': 'front'}}),
        card_data('back', front={'type': 'asset', 'classes': []},
                  back={'type': 'player', 'classes': ['guardian']}),
    ]))
    save_tag(project, 'Mystic', ['mystic'])
    save_tag(project, 'Guardian', ['guardian'])
    assert [tag['name'] for tag in matching_project_tags(project.get_card('child'))] == ['Mystic']
    assert [tag['name'] for tag in matching_project_tags(project.get_card('back'))] == ['Guardian']


def test_native_change_listeners_see_the_new_content(load_project):
    project = load_project(project_data(cards=[card_data('a')], meta={'celaeno_id': 'cloud'}))
    events = []
    Project.add_change_listener(lambda p, kind, element_id, changed:
                               events.append((kind, deepcopy(p._locate(element_id)[1]))))
    tag_id = save_tag(project, 'Draw', ['seeker'], secondary=True)
    set_card_tags(project.get_card('a'), [tag_id])
    assert events[0][1]['meta']['midnight']['design_tags'][0]['id'] == tag_id
    assert events[-1][1]['meta']['midnight']['design_tags'] == [tag_id]
    assert events[-1][1]['meta']['modified'] > 0
    wire_project = Project('cloud.shoggoth', from_wire(to_wire(project.data)))
    assert card_tags(wire_project.get_card('a')) == card_tags(project.get_card('a'))
    assert is_secondary(card_tags(wire_project.get_card('a'))[0])


def test_tags_are_independent_of_faces_and_gameplay_exports(load_project):
    project = load_project(project_data(cards=[card_data('a',
        front={'type': 'asset', 'classes': ['guardian'], 'text': 'Draw 1 card.'})],
        meta={'tags': ['public-project-tag']}))
    card = project.get_card('a')
    original_front = deepcopy(card.front.data)
    original_face_tags = card.front.tags
    original_build = export_project(project)
    original_tts = build_gm_notes(card)
    tag_id = save_tag(project, 'Private design tag', ['mystic', 'rogue'])
    secondary_id = save_tag(project, 'Secondary design tag', ['guardian'], secondary=True)
    set_card_tags(card, [tag_id, secondary_id])
    assert card.front.data == original_front
    assert card.front.tags == original_face_tags
    assert export_project(project) == original_build
    assert build_gm_notes(card) == original_tts
    assert tag_id not in json.dumps(original_build)


def test_modification_roundtrip_leaves_parent_untouched(write_project, tmp_path):
    parent_path = write_project(project_data(cards=[card_data('a')]))
    parent_text = parent_path.read_text()
    mod_path = tmp_path / 'translation.shoggoth'
    project = ModificationProject.create(mod_path, parent_path)
    tag_id = save_tag(project, 'Check translation', ['neutral'], secondary=True)
    set_card_tags(project.get_card('a'), [tag_id])
    project.save_all()
    reloaded = Project.load(mod_path)
    assert card_tag_ids(reloaded.get_card('a')) == [tag_id]
    assert project_tags(reloaded)[0]['name'] == 'Check translation'
    assert is_secondary(project_tags(reloaded)[0])
    assert parent_path.read_text() == parent_text


@pytest.mark.parametrize('copy_mode', [False, True])
def test_cross_project_transfer_reuses_matching_definitions_and_resolves_names(load_project, copy_mode):
    source = load_project(project_data(cards=[card_data('a'), card_data('b')]), 'source.shoggoth')
    dest = load_project(project_data(), 'dest.shoggoth')
    source_id = save_tag(source, 'Draw', ['seeker'])
    unassigned = save_tag(source, 'Do not transfer')
    dest_id = save_tag(dest, 'Draw', ['guardian'])
    set_card_tags(source.get_card('a'), [source_id])
    set_card_tags(source.get_card('b'), [source_id])
    card = source.get_card('a')
    data = deepcopy(card.data) if copy_mode else card.data
    transfer_card_tags(card, dest, data)
    if not copy_mode:
        source.data['cards'].remove(data)
    data['id'] = 'transferred'
    dest.add_card(data)
    tags = card_tags(dest.get_card('transferred'))
    assert tags[0]['name'] == 'Draw (2)'
    assert tags[0]['pips'] == ['seeker']
    assert tags[0]['id'] != dest_id
    assert unassigned not in [tag['id'] for tag in project_tags(dest)]
    if copy_mode:
        assert card_tag_ids(card) == [source_id]
    second = source.get_card('b')
    data2 = deepcopy(second.data)
    transfer_card_tags(second, dest, data2)
    dest.add_card(data2)
    assert len(project_tags(dest)) == 2
    assert card_tag_ids(dest.get_card('b')) == card_tag_ids(dest.get_card('transferred'))


def test_real_tag_dialog_and_card_picker(qt_app, load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    dialog = TagEditDialog(project)
    dialog.show()
    QTest.keyClicks(dialog.name_input, 'Draw')
    for pip in ['seeker', 'mystic', 'seeker']:
        dialog.add_pip(pip)
    dialog.remove_pip(2)
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
    assert dialog.result() == QDialog.Accepted
    picker = CardTagsWidget(project.get_card('a'))
    picker._build_menu()
    picker.menu.actions()[0].trigger()
    assert card_tag_ids(picker.card) == [dialog.tag_id]
    picker.refresh()
    assert len([chip for chip in picker.findChildren(TagChip) if not chip.isHidden()]) == 1
    picker.menu.actions()[0].trigger()
    assert card_tag_ids(picker.card) == []
    picker.close()
    dialog.close()


def test_secondary_editor_and_card_rows_keep_order_and_update_designation(qt_app, load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    dialog = TagEditDialog(project)
    dialog.name_input.setText('Review')
    dialog.display_combo.setCurrentIndex(1)
    dialog.add_pip('seeker')
    dialog.accept()
    secondary = dialog.tag_id
    main = save_tag(project, 'Draw', ['seeker'])
    second_secondary = save_tag(project, 'Balance', secondary=True)
    second_main = save_tag(project, 'Economy', ['rogue'])
    card = project.get_card('a')
    set_card_tags(card, [second_main, second_secondary, main, secondary])
    project.save_all()
    picker = CardTagsWidget(card)
    picker.resize(450, 250)
    picker.show()
    qt_app.processEvents()

    def names(row):
        return [row.itemAt(index).widget().tag['name'] for index in range(row.count())]

    assert names(picker.chip_row) == ['Draw', 'Economy']
    assert names(picker.secondary_row) == ['Review', 'Balance']
    assert picker.secondary_container.y() > picker.chip_container.geometry().bottom()
    assert picker.main_label.isVisible() and picker.secondary_label.isVisible()
    assert all(is_secondary(picker.secondary_row.itemAt(index).widget().tag) for index in range(2))
    picker._build_menu()
    assert [action.text() for action in picker.menu.actions()] == [
        'Review (Secondary)', 'Draw', 'Balance (Secondary)', 'Economy',
    ]
    tag = next(tag for tag in project_tags(project) if tag['id'] == secondary)
    editor = TagEditDialog(project, tag)
    assert editor.display_combo.currentData() is True
    editor.display_combo.setCurrentIndex(0)
    editor.accept()
    picker.refresh()
    assert names(picker.chip_row) == ['Review', 'Draw', 'Economy']
    assert names(picker.secondary_row) == ['Balance']
    assert not card.dirty
    assert card_tag_ids(card) == [second_main, second_secondary, main, secondary]
    picker.close()
    dialog.close()
    editor.close()


def test_choose_class_filter_follows_cards_and_keeps_existing_assignments(qt_app, load_project, monkeypatch):
    import shoggoth.midnight.widgets as widgets
    monkeypatch.setattr(widgets, '_session_match_classes', False)
    project = load_project(project_data(cards=[
        card_data('a', front={'type': 'asset', 'classes': ['seeker', 'mystic']}),
        card_data('b', front={'type': 'asset', 'classes': ['rogue']}),
    ]))
    ids = [save_tag(project, name, pips) for name, pips in [
        ('Draw', ['seeker']), ('Economy', ['rogue']), ('Spells', ['mystic']), ('Review', []),
    ]]
    card = project.get_card('a')
    set_card_tags(card, ids)
    project.save_all()
    picker = CardTagsWidget(card)
    picker._build_menu()
    assert [action.text() for action in picker.menu.actions()] == ['Draw', 'Economy', 'Spells', 'Review']
    picker.match_classes_checkbox.click()
    assert [action.text() for action in picker.menu.actions()] == ['Draw', 'Spells']
    assert all(action.isChecked() for action in picker.menu.actions())
    assert not project.dirty
    assert card_tag_ids(card) == ids
    assert [tag['name'] for tag in card_tags(card)] == ['Draw', 'Economy', 'Spells', 'Review']
    # The open-menu hook reads fresh classes after editing the card.
    card.front.set('classes', ['guardian'])
    picker.menu.aboutToShow.emit()
    assert len(picker.menu.actions()) == 1
    assert not picker.menu.actions()[0].isEnabled()
    assert 'No tags match' in picker.menu.actions()[0].text()
    next_picker = CardTagsWidget(project.get_card('b'))
    assert next_picker.match_classes_checkbox.isChecked()
    next_picker.menu.aboutToShow.emit()
    assert [action.text() for action in next_picker.menu.actions()] == ['Economy']
    next_picker.match_classes_checkbox.click()
    assert [action.text() for action in next_picker.menu.actions()] == ['Draw', 'Economy', 'Spells', 'Review']
    assert card_tag_ids(card) == ids
    picker.close()
    next_picker.close()


def test_manage_reordering_updates_card_immediately(qt_app, load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    ids = [save_tag(project, name) for name in ['Draw', 'Economy', 'Testing']]
    set_card_tags(project.get_card('a'), reversed(ids))
    picker = CardTagsWidget(project.get_card('a'))
    manager = ProjectTagsWidget(project)
    manager.changed.connect(picker.refresh)

    def displayed_names():
        return [picker.chip_row.itemAt(row).widget().tag['name']
                for row in range(picker.chip_row.count())]

    assert displayed_names() == ['Draw', 'Economy', 'Testing']
    assert not manager.move_up_button.isEnabled()
    manager.tag_list.setCurrentRow(1)
    manager.move_up_button.click()
    assert manager.selected_tag()['id'] == ids[1]
    assert manager.tag_list.currentRow() == 0
    assert not manager.move_up_button.isEnabled()
    assert displayed_names() == ['Economy', 'Draw', 'Testing']
    manager.move_down_button.click()
    assert displayed_names() == ['Draw', 'Economy', 'Testing']
    # Exercise the same native model move and rowsMoved signal as an internal drag.
    assert manager.tag_list.model().moveRow(QModelIndex(), 2, QModelIndex(), 0)
    assert displayed_names() == ['Testing', 'Draw', 'Economy']
    assert manager.tag_list.currentRow() == 2
    assert not manager.move_down_button.isEnabled()
    assert [tag['id'] for tag in project_tags(project)] == [ids[2], ids[0], ids[1]]
    picker._build_menu()
    assert [action.text() for action in picker.menu.actions()] == displayed_names()
    manager.close()
    picker.close()


def test_card_tags_wrap_on_resize_and_keep_long_tags_inside_the_editor(qt_app, load_project):
    project = load_project(project_data(cards=[card_data('a')]))
    names = ['Draw', 'Economy', 'Needs review', 'Test resource balance', 'Consistency', 'Keep an eye on this']
    ids = [save_tag(project, name, ['seeker', 'mystic']) for name in names]
    card = project.get_card('a')
    set_card_tags(card, ids)
    container = QWidget()
    layout = QVBoxLayout(container)
    picker = CardTagsWidget(card)
    layout.addWidget(picker)
    layout.addStretch()
    container.resize(1000, 700)
    container.show()
    qt_app.processEvents()
    wide_height = picker.chip_container.height()
    for width in [450, 700, 450]:
        container.resize(width, 700)
        qt_app.processEvents()
        assert picker.chip_container.height() > wide_height
        chips = [picker.chip_row.itemAt(row).widget() for row in range(picker.chip_row.count())]
        assert [chip.tag['name'] for chip in chips] == names
        assert len({chip.y() for chip in chips}) > 1
        for previous, chip in zip(chips, chips[1:]):
            assert not previous.geometry().intersects(chip.geometry())
        assert all(picker.chip_container.rect().contains(chip.geometry()) for chip in chips)
        assert picker.findChildren(QScrollArea) == []
    long_id = save_tag(project, 'An extended tag name that must remain readable. ' * 5,
                       ['seeker', 'mystic'] * 30)
    set_card_tags(card, [long_id])
    picker.refresh()
    qt_app.processEvents()
    chip = picker.chip_row.itemAt(0).widget()
    assert picker.chip_container.rect().contains(chip.geometry())
    assert chip.height() > chip.sizeHint().height()
    assert not chip.grab().isNull()
    set_card_tags(card, [])
    picker.refresh()
    assert picker.chip_container.isHidden()

    # The native card form can be wider than its viewport because of other fields.
    wide_field = QWidget()
    wide_field.setMinimumWidth(1000)
    layout.addWidget(wide_field)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(container)
    scroll.resize(550, 700)
    scroll.show()
    set_card_tags(card, ids)
    picker.refresh()
    for width in [550, 900, 550]:
        scroll.resize(width, 700)
        qt_app.processEvents()
        qt_app.processEvents()
        assert container.width() > scroll.viewport().width()
        for row in range(picker.chip_row.count()):
            chip = picker.chip_row.itemAt(row).widget()
            right = chip.mapTo(scroll.viewport(), QPoint(chip.width(), 0)).x()
            assert right <= scroll.viewport().width()
    scroll.close()


def test_project_and_modification_editors_mount_tags_and_lock_originals(qt_app, write_project, tmp_path, defaults):
    from shoggoth.ui.card_editor import CardEditor
    from shoggoth.ui.modification_editors import ModificationCompareEditor, TranslationEditor
    from shoggoth.ui.project_editor import ProjectEditor
    defaults('asset', {})
    defaults('player', {})
    path = write_project(project_data(cards=[card_data('a')]))
    project = Project.load(path)
    editor = ProjectEditor(project)
    assert editor.tabs.tabText(2) == 'Design tags'
    tag_id = save_tag(project, 'Draw', ['seeker'])
    card_editor = CardEditor(project.get_card('a'))
    card_editor.design_tags.toggle_tag(tag_id, True)
    project.save_all()
    modification = ModificationProject.create(tmp_path / 'mod.shoggoth', path)
    translation = TranslationEditor(modification.get_card('a'))
    translation.design_tags.toggle_tag(tag_id, False)
    assert card_tag_ids(modification.get_card('a')) == []
    assert card_tag_ids(project.get_card('a')) == [tag_id]
    comparison = ModificationCompareEditor(modification.get_card('a'))
    assert comparison.editor.design_tags.isEnabled()
    assert not comparison.original_editor.design_tags.isEnabled()
    for widget in [editor, card_editor, translation, comparison]:
        widget.close()


@pytest.mark.parametrize('move', [False, True])
def test_native_transfer_dialog_carries_tag_definitions(qt_app, load_project, move):
    from shoggoth.ui.transfer_dialog import TransferCardsDialog
    source = load_project(project_data(cards=[card_data('a')]), 'source.shoggoth')
    dest = load_project(project_data(), 'dest.shoggoth')
    tag_id = save_tag(source, 'Draw', ['seeker', 'mystic'])
    set_card_tags(source.get_card('a'), [tag_id])
    window = QMainWindow()
    window.open_projects = [source, dest]
    window.active_project = source
    window.refresh_tree = lambda: None
    window.status_bar = QStatusBar(window)
    dialog = TransferCardsDialog(window, source_project=source,
                                 selected_cards=[source.get_card('a')], destination_project=dest, move=move)
    dialog.button_box.button(QDialogButtonBox.Ok).click()
    assert dialog.result() == QDialog.Accepted
    assert len(list(dest.cards)) == 1
    assert card_tags(list(dest.cards)[0]) == project_tags(source)
    assert len(list(source.cards)) == (0 if move else 1)
    source.save_all()
    dest.save_all()
    assert card_tags(list(Project.load(dest.file_path).cards)[0])[0]['id'] == tag_id
    dialog.close()
    window.close()


@pytest.mark.parametrize('mode', ['tree', 'folders', 'list'])
def test_badges_in_all_sidebar_views_preserve_names(qt_app, load_project, mode):
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[card_data('a', 'Moonlight Research',
        front={'type': 'asset', 'classes': ['seeker']})]))
    tag_id = save_tag(project, 'Draw', ['seeker', 'mystic'])
    set_card_tags(project.get_card('a'), [tag_id])
    browser = FileBrowser()
    browser.resize(450, 350)
    browser.set_project(project)
    browser.switch_view(mode)
    tree = browser.list_tree if mode == 'list' else browser.tree
    tree.expandAll()
    browser.show()
    qt_app.processEvents()
    items = list(browser._iterate_items(tree.invisibleRootItem()))
    item = next(item for item in items if (item.data(0, Qt.UserRole) or {}).get('type') == 'card')
    assert 'Moonlight Research' in item.text(0)
    assert 'DRA' not in item.text(0)
    image = tree.viewport().grab().toImage()
    rect = tree.visualItemRect(item)
    colors = {image.pixelColor(x, y).name() for x in range(max(0, rect.left()), min(image.width(), rect.right()))
              for y in range(max(0, rect.top()), min(image.height(), rect.bottom()))}
    assert CLASS_CHIP_COLORS['seeker'][0] in colors
    assert CLASS_CHIP_COLORS['mystic'][0] in colors
    tree.setCurrentItem(item)
    browser.resize(160, 350)
    qt_app.processEvents()
    assert not tree.viewport().grab().isNull()
    browser.close()


@pytest.mark.parametrize('mode', ['tree', 'folders', 'list'])
def test_secondary_sidebar_tags_use_hover_icon_and_reclassify_live(qt_app, load_project, monkeypatch, mode):
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QStyleOptionViewItem, QToolTip
    import shoggoth.midnight.sidebar as sidebar
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[
        card_data('a', 'Mixed card', front={'type': 'asset', 'classes': ['guardian']}),
        card_data('b', 'Secondary only', front={'type': 'asset', 'classes': ['guardian']}),
    ]))
    main = save_tag(project, 'Draw', ['guardian'])
    review = save_tag(project, 'Review', ['guardian'], secondary=True)
    balance = save_tag(project, 'Balance', secondary=True)
    set_card_tags(project.get_card('a'), [main, review, balance])
    set_card_tags(project.get_card('b'), [review])
    browser = FileBrowser()
    browser.switch_view(mode)
    browser.set_project(project)
    browser.resize(450, 300)
    tree = browser.list_tree if mode == 'list' else browser.tree
    tree.expandAll()
    drawn = []
    paint = sidebar.paint_badge

    def record_badge(painter, rect, tag, label):
        drawn.append(tag['name'])
        paint(painter, rect, tag, label)

    monkeypatch.setattr(sidebar, 'paint_badge', record_badge)
    browser.show()
    qt_app.processEvents()
    tree.viewport().grab()
    assert drawn and set(drawn) == {'Draw'}
    item = next(item for item in browser._iterate_items(tree.invisibleRootItem())
                if (item.data(0, Qt.UserRole) or {}).get('type') == 'card'
                and item.data(0, Qt.UserRole)['data'].id == 'a')
    option = QStyleOptionViewItem()
    index = tree.indexFromItem(item)
    option.rect = tree.visualRect(index)
    position = QPoint(tree.viewport().width() - 10, option.rect.center().y())
    event = QHelpEvent(QEvent.ToolTip, position, tree.viewport().mapToGlobal(position))
    assert tree.itemDelegate().helpEvent(event, tree, option, index)
    assert 'secondary tags' in QToolTip.text()
    assert 'Review' in QToolTip.text() and 'Balance' in QToolTip.text()
    assert 'Draw' not in QToolTip.text()
    assert QToolTip.text().count('●') == 1
    QToolTip.hideText()
    QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, position)
    controller = tree.itemDelegate().tally_popup
    assert controller.is_pinned and 'secondary tags' in controller.popup.label.text()
    save_tag(project, 'Review', ['guardian'], review, secondary=False)
    save_tag(project, 'Balance', [], balance, secondary=False)
    browser.refresh()
    assert not controller.is_pinned
    drawn.clear()
    tree.expandAll()
    qt_app.processEvents()
    tree.viewport().grab()
    assert set(drawn) == {'Draw', 'Review', 'Balance'}
    browser.close()


@pytest.mark.parametrize('mode', ['tree', 'folders'])
def test_tree_header_tallies_follow_descendants_and_incremental_edits(qt_app, load_project, mode):
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[
        card_data('a', front={'type': 'asset', 'classes': ['guardian']}, amount=4),
        card_data('b', front={'type': 'asset', 'classes': ['guardian']}),
        card_data('c', front={'type': 'asset', 'classes': ['seeker']}),
        card_data('d', front={'type': 'location'}, encounter_set='enc'),
        card_data('e', front={'type': 'enemy'}, encounter_set='enc'),
        card_data('f', front={'type': 'asset', 'classes': ['guardian']}, investigator='Doctor A'),
    ], encounter_sets=[{'id': 'enc', 'name': 'Scenario', 'icon': ''}]))
    draw = save_tag(project, 'Draw', ['seeker', 'seeker'])
    review = save_tag(project, 'Review')
    unused = save_tag(project, 'Unused', ['guardian'])
    for card_id, ids in [('a', [draw, review]), ('b', [draw]), ('c', [review]),
                         ('d', [draw]), ('e', [draw]), ('f', [review])]:
        set_card_tags(project.get_card(card_id), ids)
    # Duplicate/stale IDs in an imported card still count each known tag once.
    project.get_card('a').data['meta']['midnight']['design_tags'] += [draw, 'unknown-tag']
    browser = FileBrowser()
    browser.switch_view(mode)
    browser.set_project(project)

    def items():
        return list(browser._iterate_items(browser.tree.invisibleRootItem()))

    def group(**fields):
        return next(item for item in items()
                    if all((item.data(0, Qt.UserRole) or {}).get(key) == value for key, value in fields.items()))

    def counts(item):
        return {tag['id']: tag['count'] for tag in item.data(0, Qt.UserRole)[TALLY_KEY]}

    root = browser.tree.topLevelItem(0)
    guardian = group(**{'class': 'guardian'})
    assert counts(root) == {draw: 4, review: 3}
    assert counts(guardian) == {draw: 2, review: 1, unused: 0}
    assert counts(group(**{'class': 'seeker'})) == {draw: 0, review: 1}
    assert counts(group(type='encounter')) == {draw: 2}
    assert counts(group(investigator='Doctor A')) == {review: 1}
    assert all(unused not in counts(item) for item in items()
               if item.data(0, Qt.UserRole).get('class') != 'guardian')
    guardian.setExpanded(False)
    set_card_tags(project.get_card('b'), [review])
    assert browser.update_card_node('b', project)
    assert group(**{'class': 'guardian'}) is guardian
    assert counts(guardian) == {draw: 1, review: 2, unused: 0}
    assert counts(root) == {draw: 3, review: 4}
    reorder_tags(project, [review, unused, draw])
    browser.refresh()
    assert [tag['id'] for tag in guardian.data(0, Qt.UserRole)[TALLY_KEY]] == [review, unused, draw]
    project.get_card('a').front.set('classes', ['seeker'])
    browser.refresh()
    assert counts(group(**{'class': 'guardian'})) == {review: 1, unused: 0}
    assert counts(group(**{'class': 'seeker'})) == {review: 2, draw: 1}
    set_card_tags(project.get_card('b'), [])
    browser.update_card_node('b', project)
    guardian = group(**{'class': 'guardian'})
    assert counts(guardian) == {unused: 0}
    shown = browser.tree.itemDelegate()._tags(browser.tree.indexFromItem(guardian))
    assert len(shown) == 1 and shown[0]['count'] == 0
    assert TALLY_KEY not in json.dumps(project.data)
    browser.close()


def test_tree_header_uses_one_icon_with_vertical_tallies_on_hover(qt_app, load_project, monkeypatch):
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QStyleOptionViewItem, QToolTip
    import shoggoth.midnight.sidebar as sidebar
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[
        card_data('a', front={'type': 'asset', 'classes': ['guardian']}),
        card_data('b', front={'type': 'asset', 'classes': ['guardian']}),
    ]))
    draw = save_tag(project, 'Draw <cards>', ['seeker', 'mystic'])
    review = save_tag(project, 'Review')
    save_tag(project, 'Uncovered', ['guardian'])
    set_card_tags(project.get_card('a'), [draw, review])
    set_card_tags(project.get_card('b'), [draw])
    browser = FileBrowser()
    browser.resize(450, 250)
    browser.set_project(project)
    root = browser.tree.topLevelItem(0)
    guardian = root.child(0)
    guardian.setExpanded(False)
    labels = []
    icons = []
    paint = sidebar.paint_badge
    paint_icon = sidebar.DesignTagDelegate._paint_tally_icon

    def record_badge(painter, rect, tag, label):
        labels.append(label)
        paint(painter, rect, tag, label)

    def record_icon(painter, rect, option):
        icons.append(rect)
        paint_icon(painter, rect, option)

    monkeypatch.setattr(sidebar, 'paint_badge', record_badge)
    monkeypatch.setattr(sidebar.DesignTagDelegate, '_paint_tally_icon', staticmethod(record_icon))
    browser.show()
    qt_app.processEvents()
    assert not browser.grab().isNull()
    assert len(icons) >= 2 and all(10 <= rect.width() <= 14 for rect in icons)
    assert labels == []  # Collapsed headers paint icons, with no tally badges.
    assert 'DRA' not in guardian.text(0)
    index = browser.tree.indexFromItem(guardian)
    option = QStyleOptionViewItem()
    option.rect = browser.tree.visualRect(index)
    position = QPoint(browser.tree.viewport().width() - 10, option.rect.center().y())
    event = QHelpEvent(QEvent.ToolTip, position, browser.tree.viewport().mapToGlobal(position))
    assert browser.tree.itemDelegate().helpEvent(event, browser.tree, option, index)
    assert 'Draw &lt;cards&gt;' in QToolTip.text()
    assert QToolTip.text().count('<tr>') == 3
    assert '<b>2</b>' in QToolTip.text() and '<b>1</b>' in QToolTip.text() and '<b>0</b>' in QToolTip.text()
    assert QToolTip.text().index('Draw') < QToolTip.text().index('Review') < QToolTip.text().index('Uncovered')
    QToolTip.hideText()
    position.setX(option.rect.left() + 30)
    event = QHelpEvent(QEvent.ToolTip, position, browser.tree.viewport().mapToGlobal(position))
    assert not browser.tree.itemDelegate().helpEvent(event, browser.tree, option, index)
    guardian.setExpanded(True)
    qt_app.processEvents()
    browser.grab()
    assert 'DRA' in labels and 'REV' in labels
    browser.close()


def test_tally_hover_opens_quickly_and_cancels_when_leaving_icon(qt_app, load_project, monkeypatch):
    from PySide6.QtWidgets import QToolTip
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[
        card_data('a', front={'type': 'asset', 'classes': ['guardian']}),
    ]))
    save_tag(project, 'Draw', ['guardian'])
    browser = FileBrowser()
    browser.set_project(project)
    browser.resize(450, 250)
    browser.show()
    qt_app.processEvents()
    tree = browser.tree
    viewport = tree.viewport()
    header = tree.topLevelItem(0).child(0)
    position = QPoint(viewport.width() - 10, tree.visualItemRect(header).center().y())
    outside = QPoint(10, viewport.height() - 10)
    shown = []
    show_text = QToolTip.showText

    def record_tooltip(*args):
        shown.append(args[1])
        show_text(*args)

    monkeypatch.setattr(QToolTip, 'showText', record_tooltip)
    QTest.mouseMove(viewport, outside)
    QTest.mouseMove(viewport, position)
    QTest.qWait(35)
    QTest.mouseMove(viewport, outside)
    QTest.qWait(180)
    assert shown == []
    elapsed = QElapsedTimer()
    elapsed.start()
    QTest.mouseMove(viewport, position)
    while not shown and elapsed.elapsed() < 500:
        QTest.qWait(10)
    assert shown and elapsed.elapsed() < 500
    assert 'Click the icon to pin' in shown[-1]
    QTest.mouseMove(viewport, outside)
    QToolTip.hideText()
    browser.close()


@pytest.mark.parametrize('mode', ['tree', 'folders'])
def test_clicking_tally_icon_pins_live_counts_without_selecting_group(qt_app, load_project, mode):
    from shoggoth.ui.browser.file_browser import FileBrowser
    project = load_project(project_data(cards=[
        card_data('a', front={'type': 'asset', 'classes': ['guardian']}),
        card_data('b', front={'type': 'asset', 'classes': ['guardian']}),
        card_data('c', front={'type': 'asset', 'classes': ['seeker']}),
    ]))
    draw = save_tag(project, 'Draw', ['guardian', 'seeker'])
    save_tag(project, 'Healing', ['guardian'])
    set_card_tags(project.get_card('a'), [draw])
    browser = FileBrowser()
    browser.switch_view(mode)
    browser.set_project(project)
    browser.resize(450, 300)
    browser.tree.expandAll()
    browser.show()
    qt_app.processEvents()
    tree = browser.tree
    viewport = tree.viewport()
    guardian = next(item for item in browser._iterate_items(tree.invisibleRootItem())
                    if (item.data(0, Qt.UserRole) or {}).get('class') == 'guardian')
    position = QPoint(viewport.width() - 10, tree.visualItemRect(guardian).center().y())
    selected = browser.get_card_item('a', project)
    tree.setCurrentItem(selected)
    QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, position)
    controller = tree.itemDelegate().tally_popup
    assert controller.is_pinned
    assert tree.currentItem() is selected
    popup = controller.popup
    initial_position = popup.pos()
    QTest.mouseMove(viewport, QPoint(10, viewport.height() - 10))
    other_card = browser.get_card_item('b', project)
    QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, tree.visualItemRect(other_card).center())
    assert controller.is_pinned
    assert tree.currentItem() is other_card
    set_card_tags(project.get_card('b'), [draw])
    browser.update_card_node('b', project)
    assert '<b>2</b>' in popup.label.text() and '<b>0</b>' in popup.label.text()
    assert popup.pos() == initial_position
    popup.close_button.click()
    assert not controller.is_pinned
    for _ in range(2):
        QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, position)
        assert controller.is_pinned
        QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, position)
        assert not controller.is_pinned
    QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, position)
    QTest.keyClick(viewport, Qt.Key_Escape)
    assert not controller.is_pinned
    QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, position)
    assert controller.is_pinned
    browser.tree.clear()
    assert not controller.is_pinned
    browser.close()


def test_split_badge_preserves_repeated_pips_and_supports_no_color(qt_app):
    from PySide6.QtCore import QRectF
    image = QImage(90, 20, QImage.Format_ARGB32)
    painter = QPainter(image)
    paint_badge(painter, QRectF(0, 0, 90, 20), {'pips': ['seeker', 'seeker', 'mystic']}, '')
    painter.end()
    assert image.pixelColor(15, 10) == QColor(CLASS_CHIP_COLORS['seeker'][0])
    assert image.pixelColor(45, 10) == QColor(CLASS_CHIP_COLORS['seeker'][0])
    assert image.pixelColor(75, 10) == QColor(CLASS_CHIP_COLORS['mystic'][0])
    painter = QPainter(image)
    paint_badge(painter, QRectF(0, 0, 90, 20), {'pips': []}, 'NEW')
    painter.end()
    assert image.pixelColor(5, 10) == QColor('#535861')
