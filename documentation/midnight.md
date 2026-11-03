# Midnight

Midnight is a personal branch of Shoggoth. Its additions live in
`shoggoth/midnight/`, with small, explicit connections to the existing Qt UI.
This is an extension package inside the fork, rather than an independently
installable plugin. Upstream updates are integrated with Git merges; they do
not automatically rewrite or port Midnight's features.

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
the checks. Review the six integration files below if upstream changes their
UI contracts. Open the app and check project tag editing, card assignment,
sidebar badges in all three views, and save/reload. Once satisfied, push the
updated branch with `git push origin midnight`.

Merging retains upstream history and this branch's changes. Keeping each
feature in its own commit and package reduces conflict exposure, but changes
to upstream APIs or storage still need review. No automatic Git merges or
updater changes are installed by this feature.

## Extension boundary

The feature owns its model helpers, widgets, and painting in
`shoggoth/midnight/`. It uses the native project writer, dirty notifications,
cloud timestamps, modification diffs, and existing class color palette.
There are no monkey patches, background watchers, or alternate project files.

The connections to upstream code are:

| File | Connection |
| --- | --- |
| `shoggoth/ui/project_editor.py` | Mount the project tag manager. |
| `shoggoth/ui/card_editor.py` | Mount the card picker and refresh it after JSON edits. |
| `shoggoth/ui/modification_editors.py` | Mount the translation picker and lock original-card controls. |
| `shoggoth/ui/browser/file_browser.py` | Install badges and update tree tag tallies. |
| `shoggoth/ui/browser/tree_sync.py` | Preserve tally data during native tree synchronization. |
| `shoggoth/ui/transfer_dialog.py` | Carry definitions when the native transfer copies or moves cards. |

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
