# Midnight

Midnight is a personal branch of Shoggoth. Its optional modules live in
`shoggoth/midnight/modules/`, with shared integration points for the native UI,
renderer, and card transfer. Official asset updates do not touch these packages
or require changes to template JSON. Application updates are integrated with
Git merges, as described below.

## Modules menu

The top-row **Modules** menu lists **Design tags**, **Designer**, **Release sync**,
and **Tree Ordering** as independent checkable actions. They start enabled and are
remembered between app launches. These are app-wide preferences, including
command-line rendering on the same installation; they are not project settings.

Turning a module off hides its editor controls and presentation. Disabling
Design tags restores the native sidebar and closes pinned tag popups. Disabling
Designer removes its credit from subsequent previews and rendered exports.
Open editors retain their contents. Saved credits, tag definitions, and card
assignments remain in project files, and reappear when their module is enabled.
Storage operations still preserve module data, including tag definitions when
cards are transferred while the module is off.

The menu and editor hosts use a shared registry. Future bundled modules register
there to receive their own toggle without adding another native menu integration.

## Tree Ordering

**Modules → Tree Ordering** sorts player cards in the grouped **Tree** view.
Investigators come first in Guardian, Seeker, Rogue, Mystic, Survivor, and Neutral
order. Each investigator group lists the investigator, signatures alphabetically,
then signature weaknesses.

The class folders follow the same class order. Each level is kept together in
ascending order, with assets, events, then skills at that level. The existing
Other folder includes multiclass cards and appears before Neutral. Basic Weakness
comes after the class folders, followed by unlinked non-basic weaknesses.
Toggling the module switches the sidebar order immediately. Collection numbers
are assigned separately by the project's renumber command.

## Release sync

With **Modules → Release sync** enabled, select **Card ID only ({id}, {id}_back)**
under **File name format** in an **Images** export entry. The preset writes
`<id>.<ext>` for the front and `<id>_back.<ext>` for a card-specific back. It
skips standard player and encounter backs. Cards with multiple copies use the
combined version.

Add **Images** and **arkham.build** to a single export setup to use the Images
entry's size, format, bleed, and corner settings for full card art on arkham.build.
Release sync runs Images before arkham.build, which crops its thumbnails from
the exported files. Set the Images scope to cover the cards in arkham.build.
**Tabletop Simulator** uses its dedicated 1500 × 2100 WebP renders. Each
**Submit to cloud** entry marks the end of an export group within the setup.

With Release sync enabled, new TTS bags contain one copy of each exported card.
In **All cards** and **Campaign cards** exports, shared encounter cards appear
in their own set's bag. When updating a TTS save, Shoggoth updates every card
already in the save and exports one of each new card in the unused-cards bag.

Turning Release sync off hides the preset for new selections. Saved setups
keep their selection. To run an Images entry that uses it, enable Release sync
or select another filename format for that entry.

## Designer

With **Modules → Designer** enabled, open a card and enter a name in **Designer**
below the card name and design tags. Enter `Mint Tea Fan` to print:

```text
Des. Mint Tea Fan
```

Save with **Ctrl+S**, as with other card changes. Leave the field empty to omit
the credit. The credit belongs to the card and appears on each face with a usable
collection icon or number region. Faces without either region, such as standard
card backs, omit it.

The module derives placement and typography from each face's fully resolved
collection footer, including inherited layouts and card overrides. It prints
on the same row as the collection number, right-aligned just before the icon
and number, with a small gap. The icon's space is reserved even when no icon
is selected. Long names fit within a bounded text region using the native text
renderer. Illustrator and copyright text keep their original positions. No
official asset files or stored face regions change.

Designer is included in native rendered card images (and the print/PDF, TTS,
and arkham.build image paths that use them). It does not add gameplay/export
metadata or replace the illustrator's attribution. The editor also works in
modification and translation projects; original-card controls stay locked.

The source value is `card.meta.midnight.designer`, alongside design tags.
Native save/load, cloud sync, copies, and card transfer preserve it.

## Design tags

1. Select your project in the sidebar and open **Design tags**.
2. Choose **New tag…**, enter a name, and add class-colored pips. You can add
   zero, one, or many pips, including repeated colors. Their order is kept.
   Click a pip to remove it. Save the tag.
3. Open a card. Below its name, use **Design tags → Choose…** to assign or
   remove tags. **Manage…** opens the same project tag manager from the card.
4. Save the project with **Ctrl+S** to persist definitions and assignments.

In the tag editor, set **Display** to **Main** or **Secondary**. This applies
to that tag throughout the project. Existing tags default to Main. Main tags
appear as sidebar badges. Every card reserves a small icon at the right edge
for Secondary tags, keeping badges aligned. The icon is muted when empty;
hover it to see the tags' names and pips, or click to pin a populated list.
This works in all three sidebar views.

The card editor shows separate **Main** and **Secondary** rows. Secondary
chips have dashed borders. Both rows wrap to fit the visible editor and keep
their relative project order. Category tally popups include both kinds.

Enable **Match classes** beside **Choose…** to offer only tags with at least
one pip matching any of the card's classes. For example, a Seeker/Mystic card
can choose tags containing either a Seeker or a Mystic pip. Tags without pips
are hidden while filtering. The preference follows you between cards for the
current app session. Existing assignments stay intact, and the menu uses the
card's current classes each time it opens.

In **Manage…** or the project's **Design tags** tab, drag tags into order or
select a tag and use **Move up** / **Move down**. That project order always
controls the card's tag display, sidebar badges, and Choose… menu, regardless
of the order in which tags were assigned. Save the project to keep the order.

Assigned tags display their full name and pips in the card editor, wrapping
onto additional lines as needed. The grouped tree, folder tree, and flat card
list align three-letter badges to the right edge, with one equal-width
background stripe per pip. A tag without pips has
a plain gray badge. Narrow sidebars collect excess badges into **+N**; hover
the card row to read every tag's full name and pip colors.

Tree and folder headers have a small list icon at the right edge. Hover the
icon to see a vertical list of full tag names, colored pips, and counts, with
extra space between columns. The tally tooltip opens after a short hover
(about 120 ms). Click the icon to pin the panel while editing cards; its
counts continue to update. Click the same icon again, press **Esc**, or use
the panel's **×** button to close it. Class headers
include every tag with a matching class pip, including **0** for tags not yet
assigned there, alongside tags already in use. This includes cards in nested groups and
counts each card once per tag, regardless of its number of copies or pips.
Tallies follow the project tag order and update when assignments change,
including while a group is collapsed. Individual cards keep their compact
tag badges.

Tag names are unique within a project, ignoring case and surrounding spaces.
Names and colors can be edited without breaking assignments. Deleting a tag
also removes it from the project's cards; a confirmation shows how many cards
are affected. Copying or moving cards between projects carries their assigned
tag definitions, reuses matching tags, and numbers conflicting names instead
of replacing an existing definition. Tags also work in modification projects.

These are design annotations. They do not change card faces, template tags,
classes, card sorting, printed artwork, PDF content, arkham.build output, or
TTS gameplay metadata. Shoggoth's existing **Meta → Tags** field is separate
and keeps its existing export behavior.

Definitions and assignments are saved inside the editable project file, so
project backups, copies of that file, and native cloud project sync carry
them. A project file is the source document, not a gameplay export. Normal
project saves are needed after changing definitions; the existing individual
card-save API still saves only that card.

## Keeping the fork current

Run this checkout with:

```bash
uv sync
uv run shoggoth
```

The existing updater recognizes an editable development install and disables
application self-updates. The official asset updater continues to work.
Installing an official release over a standalone Midnight build would replace
the custom application code: update this branch and rebuild instead.

This repository already has both remotes configured:

- `origin`: `https://github.com/Moonshie/shoggoth.git`
- `upstream`: `https://github.com/tokeeto/shoggoth.git`

Commit your current changes before updating. Then, from the repository root:

```bash
git switch midnight
git fetch upstream
git merge upstream/main
uv sync
uv run ruff check
QT_QPA_PLATFORM=offscreen uv run pytest
```

If Git reports conflicts, resolve them and complete the merge before running
the checks. Review the integration files below if upstream changes their
UI contracts. Open the app and check project tag editing, card assignment,
sidebar badges in all three views, and save/reload. Once satisfied, push the
updated branch with `git push origin midnight`.

Merging retains upstream history and this branch's changes. Keeping each
feature in its own commit and package reduces conflict exposure, but changes
to upstream APIs or storage still need review. No automatic Git merges or
updater changes are installed by this feature.

## Extension boundary

Each module owns its model helpers, widgets, and presentation in
`shoggoth/midnight/modules/<module_id>/`. The shared `registry.py`, `hooks.py`,
and `ui.py` provide activation, hook dispatch, and editor/menu hosts. Modules
use the native project writer, dirty notifications,
cloud timestamps, modification diffs, and existing class color palette.
There are no monkey patches, background watchers, or alternate project files.

The connections to upstream code are:

| File | Connection |
| --- | --- |
| `shoggoth/ui/main_window/menus.py` | Mount the Modules menu. |
| `shoggoth/ui/project_editor.py` | Mount project module controls. |
| `shoggoth/ui/card_editor.py` | Mount card module controls and refresh them after JSON edits. |
| `shoggoth/ui/modification_editors.py` | Mount translation module controls and lock originals. |
| `shoggoth/ui/browser/file_browser.py` | Install module browser bindings and dispatch tree hooks. |
| `shoggoth/ui/browser/tree_spec.py` | Build native player-card nodes in the order supplied by the active module. |
| `shoggoth/ui/browser/tree_sync.py` | Preserve registered module data during native synchronization. |
| `shoggoth/ui/transfer_dialog.py` | Dispatch data-preservation hooks during native card transfer. |
| `shoggoth/ui/export_entry_widgets.py` | Offer naming presets from enabled modules. |
| `shoggoth/ui/export_runner.py` | Run Images before arkham.build and pass along the exported paths. |
| `shoggoth/renderer/card_renderer.py` | Dispatch module naming presets and render module text layers. |
| `shoggoth/arkham_build/images.py` | Use exported Images files for uploads and thumbnail crops. |

`modules/design_tags/` owns the existing tag system; `modules/designer/` owns
designer credit storage, its editor field, and its temporary render layer.
`modules/release_sync/` owns the ID-only naming preset and shared export planning.
`modules/tree_ordering/` owns the grouped player-card tree order.

To add a bundled module, create its package, export a `Module` descriptor, and
add that descriptor to `MODULES` in `shoggoth/midnight/modules/__init__.py`.
`registry.Module` documents the available hooks. Widget factories receive the
native card/project and return a widget with a `changed` signal; an optional
`refresh()` resynchronizes controls after JSON edits and reactivation. Browser
bindings receive the browser and manager, listen to activation changes, and
restore native presentation when disabled. Bind QObject signal handlers to
QObject methods so deleting an editor/browser also disconnects its listeners.
Text-layer hooks return temporary views for the native text renderer; they
must never change source face/default data. Transfer hooks run even while a
module is disabled so switching presentation off cannot lose stored data.

Activation uses `midnight/modules/<module_id>/enabled` in Shoggoth's existing
application preferences. Rendering reads an in-memory snapshot, including from
background threads, rather than querying Qt settings per card.

Project definitions use `project.meta.midnight.design_tags`:

```json
[
  {"id": "a-stable-uuid", "name": "Draw", "pips": ["seeker", "mystic"]}
]
```

Secondary definitions additionally have `"secondary": true`. An absent
designation means Main. Changing it preserves the tag's ID and assignments.

Card assignments use `card.meta.midnight.design_tags`:

```json
["a-stable-uuid"]
```

The namespace is separate from native `meta.tags` and from the face's
mechanical/template `tags`. Other Midnight namespace fields are preserved.
Existing projects gain no fields merely by being opened. Stable IDs let
renames propagate without rewriting every assigned card. Native save/load and
cloud wire conversion preserve this metadata without changes to either path.

`tests/test_midnight_tags.py` covers persistence, modification projects, native
change notifications, cloud wire conversion, transfer behavior, unchanged
gameplay exports, real Qt controls, and rendered badges in all sidebar views.
`tests/test_midnight_modules.py` covers independent persistent toggles, live
editor/sidebar changes, closed tag popups, preserved unsaved editor content,
disabled-module transfer, future registry entries, designer persistence, native
credit geometry, and actual image rendering/export against the asset pack.
