# Organisation Master

The central tool for Revolution Realized development. `OrganisationMaster.exe` (build it with `build.bat`).

## Working on the tools (ChatGPT / Codex, Claude, anyone)

**Folder layout**
- `tools/organisation_master/` holds only the start script `organisation_master.py`, `OrganisationMaster.exe`,
  `build.bat`, this README and the tool's **files**: `sounds/`, `secret_assets/`, `icons/`, `themes/`, `sync.json`,
  `planned_music_stations.json`, `backups/`, `audio_tools/`, `audio_recovery/`.
- **All other code is in `tools/organisation_master/Scripts/`.** New modules go there, never next to
  `organisation_master.py`. `organisation_master.py` puts `Scripts/` on the import path, so `import ui` etc. work
  unchanged.
- Culture Master and Country Master use some of these scripts too (`ui`, `master_activity`, `master_links`,
  `sound_feedback`, `state_review`, `country_review`...). Their builds and theme code already look in `Scripts/`.

**Finding the tool's files: always `paths.py`**
- `import paths`, then `paths.TOOL` is `tools/organisation_master`, whether the code runs as `.py` or inside any of
  the three exes (Culture / Country Master find it next door). Example:
  `os.path.join(paths.TOOL, "secret_assets", "duck.png")`.
- Never use `os.path.dirname(__file__)` (that's `Scripts/` now) or `sys._MEIPASS` (nothing is unpacked there) to
  find art, sounds, icons or themes. (`paths.BUNDLE` still exists for older code; it is the same folder.)

**Art and sounds are not built into the exes**
- They're read from `tools/organisation_master` at run time, so the repository stores one copy. Adding a picture or a
  sound means adding the file to its folder; no build change.
- Keep art near the size it's drawn at (about twice the largest on-screen size; sprites drawn at 48 px don't need
  2000 px sources). Big sources make the repository grow on every commit.
- Don't add `--add-data` lines for `sounds/`, `secret_assets/` or `icons/` to any `build.bat`.

**The exes run from a copy** (`Scripts/run_copy.py`): started from the repository, a master copies its exe to
`%LOCALAPPDATA%\OrganisationMaster\run` (once per build), starts that and exits, so a git pull can always replace the
exe in the repository. The copy sets `sys.executable` back to the repository's exe (paths, shortcuts and the update
check still mean the repository). In Task Manager they show as `OrganisationMaster-<size>-<time>` etc. A new master's
start script calls `run_copy.start("Name")` straight after `import sys` (only as `__main__`, only when frozen).

**Shared pieces for every master and feature**
- **New masters**: `master_template/` (copy, rename, fill in `build()`); `Scripts/master_base.py` gives the theme, sounds,
  menu bar, File menu, ◂ Organisation Master, status line, activity, rr:// links and a graceful close; a `master.json` in
  the master's folder registers it (`Scripts/masters.py`: Organisation Master's Masters menu and side bar, activity inbox,
  links, update check).
- **🔎 Search everything** (Ctrl+K, or the menu bar; `Scripts/search_palette.py`): tasks, projects, ideas, Dev VCs, GFX
  items, countries (open in Country Master), pages, actions and guides. Ctrl+K also works inside text boxes.
- **🩺 Data check** (`Scripts/data_check.py`): 9 s after start-up, and Settings > Check the To Do data...: links to
  things that are gone (a sub-task's parent, dependencies, a missing project / idea category / heading, an idea's or a GFX
  item's task, the next task number) are fixed and synced; duplicate numbers / ids, unknown devs and VC proposals that
  point at deleted tasks are listed for a person.
- **📖 Guides** (top left of the menu bar; `Scripts/guides.py`): Getting started, then To Do, Ideas, Dev VCs, GFX, Music,
  Live Sync, Games & Achievements. Each step switches to the right place; a click-through overlay draws a pulsing glow
  around the real widget, a bobbing arrow and a ghost cursor that clicks it; a card says what it is (Back / Next, ← →,
  Esc). Finished guides get a ✓; the first start after they arrived offers the tour once.

**Building**
- Always build with `build.bat` (double-click, or `cmd /c build.bat`), never a hand-written PyInstaller command: it
  has the `--paths` for `Scripts/` and the exclusions (PIL AVIF, unittest, pydoc) that keep the exe small
  (Organisation Master ~32 MB, Culture / Country Master ~30 MB). If an exe is suddenly 8-10 MB bigger, it was built
  without them.
- Close the master first (a running exe can't be replaced). Culture / Country Master need rebuilding too when a
  script they use changes.
- Keep `build.bat` files with Windows (CRLF) line endings.
- Add an entry to `Scripts/release_notes.py` (newest first, unique `id`) for anything the team should see.

- **Other masters**: the left side (and the *Masters* menu) opens **Culture Master** and **Country Master** on RR.
  Both have **◂ Organisation Master** in their menu bar to come back here.
- **Tools** (left side): the parts of Organisation Master. **To Do Master** and **Music Master**. More will come.
- **RR Games** (top bar): ten games using the saved mod's religions, cultures, flags, country shapes and
  political leaders. Pick a game and difficulty, then **Start round**. Most rounds have ten questions;
  Flagrant Misidentification runs until the first mistake or timeout, speeding up to five seconds per flag.
  Hard Borderline Genius hides the map after four seconds. Typed country answers accept names or tags.
  Medium Borderline Genius uses multiple choice and includes breakaways and formables, using Country Master's
  scripted release borders, releasable cores and formable state footprints. Hard uses the same wider pool.
  Spot the Minority shows a square regional map with the target state highlighted in orange; Hard hides its
  state and country names. Culture Shock uses composition tables rather than icons.
  Countries sharing the same name show a tag qualifier, such as `France [FRA]`, consistently across the games.
  Type the full qualified name or the tag; an ambiguous bare name does not consume a guess.
  **Guess That Ideology!** shows a political leader's portrait. Easy asks for the main ideology, Normal draws
  sub-ideology choices from all groups, and Hard draws them only from the correct main ideology. Only explicit
  leader-role ideologies are used; multiple recorded roles are accepted. Rounds have ten questions and separate
  leaderboards per difficulty, shared through Live Sync.
  **Name That Station** uses the installed RR radio mods: Easy plays 12 seconds with up to three station
  choices, Normal plays seven seconds with up to four song choices, and Hard plays four seconds with station
  autocomplete. Shared tracks accept stations containing the same file or song name. Replay/Stop and volume controls are
  available; clips stop on answering, leaving the game, or losing window focus. Ads/jingles are skipped.
  Music uses the shared preview player, stopping the sidebar radio or another preview to avoid overlap.
  No song files are edited/downloaded. Missing local tracks are skipped; install the RR music mods to play.
  **Leaderboards** keeps each developer's best run separately for every game/difficulty, shared through Live Sync.
  Loading and question preparation run in the background. End/close retains answered questions; changing
  saved mod data is reflected after restarting Organisation Master. The ignored `.rr_games_cache/` is local only.
- **Game results**: each quiz answer stays visible until **Next question** (or **See round results**).
  Every round shows its own score, time and answer review, regardless of personal best; select a review row
  for its full answer. **Play Again** starts another round; completed RRdle offers **Play practice**, and a
  paused daily offers **Resume daily**. Pinpoint's **Review round / map** keeps the final map available.
  Easy/Normal countries and flags use their saved startup cosmetic and ruling-ideology presentation.
  Hard may alternate startup/base names; typing accepts either valid name or the real tag.
- **RRdle**: a daily country puzzle, with 8 guesses on Easy and 6 on Medium/Hard. Daily answers are chosen from
  a sorted pool with a stable `rrdle:<UTC date>:<difficulty>` seed, then retained in shared `rr_daily` data.
  Your guesses save after every turn; closing or ending pauses that attempt, and Start resumes it. Finished
  dailies reopen their results; **Practice** is unlimited and never records a score. Easy supplies name/alias
  suggestions and a blurred flag, Medium removes the flag, Hard also removes suggestions, size, population
  and direction arrows. Missing source data is omitted from hints; ideology-side yellow requires an explicit
  side in the ideology data. Countries with no usable Hard hint at all are excluded from daily selection.
  Distances use capital-state centres and 40,075 km per map width. Formable borders
  use their saved footprint; missing formable capitals/ideologies are not inferred. Daily numbering starts
  at #1 on 24 October 2026. **Share** copies an emoji grid. Leaderboards show consecutive UTC-day streaks,
  wins as a percentage of finished games, and average guesses on wins.
- **Pinpoint**: locate ten states with a click; drag to pan and use the wheel to zoom. Detailed map pixels load
  as you zoom, including tiny islands. Easy selects capitals/populous states and shows the owner's flag,
  continent and lightly highlighted territory. Medium gives the state/owner and 20 seconds; Hard gives only
  the state name, a plain map and 10 seconds. Clicks inside earn 1,000; outside earn `max(0, round(1000-km/2))`
  from the nearest boundary, with wrapped longitude. Timeout earns zero. Inspect the flashing answer/line,
  then **Next state**. After ten, the summary map shows all clicks; the best score per dev/difficulty wins,
  with time breaking ties. End retains a partial run. Timers pause when the games window loses focus.
- **Recent Changes** (top bar, beside Achievements): program update notes for all the tools. New entries appear
  once at launch per developer on this PC; the menu reopens the complete history. The last five updates are included.
  Future updates go in `release_notes.py` with a new unique ID, newest first, so only unseen entries are announced.
  Update bands identify the master: red To Do, purple Music, green Culture, black Country; general Organisation
  changes use grey. Badges use the current theme's clipboard/music/globe/flag/gear icons. Updates covering more
  than one master show a badge for each, and Ideas / Dev VCs use the To Do color.
- **Files changed** (bottom left): every file written this session.
- **Drag movement**: To Do tasks/projects, Ideas/categories/headings and Culture Master's file-order entries
  follow the pointer as full list rows, preserving the grab offset. Text and columns stay upright, with no separate popup card.
  Painting, sliders and resizing keep their existing behaviour. Releasing or leaving the control stops the motion.
  Dragging a task in Dev/Project mode reveals a **No Group** row inside the list. Drop there to release the task
  from its project, parent and grouping. Sub-tasks travel with their parent. The drop row stays reachable within
  long lists, disappears on release or cancellation and supports Undo.
- **Flag Icon** (inside every icon picker): enter `ENG`, `ENG_fascist`, `ENG_fascism` or a cosmetic flag tag,
  check the live preview and select **Use Flag Icon**. The actual game flag is shaped like the generic waving
  flag on a pole, with a bevelled metallic rim, embossed highlights and shadows.
  Lookup reuses Country Master's flag index: mod overrides first, then the installed base game and DLC folders;
  standard and mod ideology fallbacks are supported. `fascist` is accepted as an alias for `fascism`.
  Task/project/group/category icons store the portable `flag:<tag>` ID in shared data, so each PC renders the flag
  locally. Missing assets show a framed question mark; invalid or missing tags cannot be selected in the picker.
- **Browse ideas**: switch the left sidebar between **Categories** and **Projects**. Each project lists its ideas'
  categories; selecting either filters the idea list. Posting with a project selected keeps the chosen category
  and links the idea to that project. Existing category dropdowns and right-click actions still apply.
  Pending project-linked ideas automatically get one **Review idea** task in the project's **Idea Reviews** group,
  with its lead as reviewer. Existing pending ideas are included at launch. The review follows project/category
  changes; approval, shelving, deletion or unlinking closes a pending review. Manually completed or explicitly
  deleted reviews are preserved. Review tasks link back to their source through **See its ideas**; an idea's
  right-click menu also opens its review task. Implementation approval remains a separate action.
  Right-click a category or heading in either the sidebar or idea list and choose **Assign to Project** to move
  the group, its nested ideas and their review tasks together. In Projects view, only the source project's ideas
  move. Group assignments also supply defaults for future ideas; explicit project choices override them. Empty
  assigned groups remain visible under their project. Categories, headings, notes, comments and links are retained,
  and Undo restores the entire assignment. A lead or the poster of every affected idea can assign a group.
- **Ideas header details**: select a heading/category to edit its details, comments and links in **Selected idea**. The right-click
  **Details, comments & links…** shortcut focuses the same panel. Add shared context, attributed comments and links/files. A note marker and
  comment count identify headers with content. Details follow renames and moves; removing a heading merges
  its content into the parent. Header content is included in Undo, Live Sync and the lead activity log.
- **Portrait previews**: selecting a portrait task under **Portrait Review** or **Generic Review** shows its
  image beside the notes in **Selected task**. Click the preview to open the original file. Previews load in the
  background; missing portraits display a short message.
- **Open in master** (To Do > Links): jump from state reviews to the selected state/layer in Culture Master,
  country files to their country in Country Master, portrait reviews to their exact image, and music tasks to
  their planned station in Music Master. Recognised file links work too; **Open file** keeps normal file access.
  Culture / Country Master launch at the target after loading. Music navigation uses the current Organisation
  Master window and preserves staged music edits. Portable `rr://` master links can also be pasted into Links.
- **Developer activity · leads** (To Do, Dev / Project mode): lead developers see each dev's last recorded
  tool access and last change. **View log…** opens a filterable history of task changes, Ideas / VC edits,
  and saved work in Music, Culture and Country Master, with file paths and change details. Access recording
  starts with this update; existing attributed task history is included. Events are shared through Live Sync;
  access does not count as saved work for achievements.
- **Theme** menu: Classic (the Windows look), **Revolution Realised** (copper and parchment, from
  `themes/Revolution Realised`), Midnight, Field Grey, Sons of Sorel (wine red), Arctic Station (light, glacier blue),
  BurgSys (graphite and violet) and Soviet Terminal; each has its own icon sheet. A theme is a folder in `tools/organisation_master/themes/`
  with a `theme.json` (colours, font, an optional `assets.button` picture used for every button, and an optional
  `assets.logo` shown very faintly at the bottom of the side bar); add one and it
  shows in the menu next time. **One theme for all the masters** (Organisation, Culture and Country Master; kept in
  `%APPDATA%\OrganisationMaster\theme.json`): change it in one and the others follow. Tick *Just for <master>* in
  the Theme menu to give one master its own theme.
- **Launch settings** (top bar; asked on first launch): shortcuts on the desktop, in the Start menu (pin it to the
  taskbar from there), in the first-level RR folder (git-ignored) and launching on Windows start-up. Just for this PC.
  **Settings > Window mode** selects Windowed or Borderless full screen and remembers it for the next launch;
  **F11** switches between them any time.
  In borderless full screen the menu bar gets its own buttons, top right: **🗗 Exit full screen (Esc)** (Esc does it
  too), **—** (minimise) and **✕** (close).
- The title bar and menu bar follow the theme too.
- **Settings** menu: text size (Small to Huge; also **Ctrl +** / **Ctrl -**), open / fold every section. Every block with
  a grey title bar folds away when you click its title (remembered); the line between the left and right halves can
  be dragged.
- **Settings > Sound feedback**: soft clicks acknowledge button presses (including dialog buttons, checkboxes and
  mode selectors); gentle sounds confirm saved actions, task completion and Undo. Task view tabs and opening
  project / grouping / sub-task branches use their own soft opening sound. Enabled by default; the on/off choice
  is saved on this PC. Typing autosaves and background sync are silent.
  Closing a branch reverses its opening sound. Clicking a task gives a subtle sound, brighter for your assigned
  tasks; claiming one plays a short celebratory sound.
  Leaving or deleting a task plays a soft "womp womp"; creating a task and opening its icon picker have distinct
  sounds. Task-editor dropdowns have very light open/select sounds, with Priority becoming more urgent up to
  Critical. Ticking Requires AI gives a robotic chirp. Closing the tool plays its own brief exit sound.
  The sound setting is shared with Culture Master and Country Master through local `sounds.json` beside
  Organisation Master's config. Their Settings menus have the same toggle; they use the same controls, tree,
  save/create/delete and exit sounds, with Undo feedback in Culture Master. Background loading stays silent.
  Culture Master plays one brush sweep after a changed map stroke. Accepted colour choices give a droplet;
  Country Master previews and switches collapses / bombs with a mechanical click. Validation results use a
  gentle chime when clear and a muted knock when problems are found.
  Each master plays a brief playful startup jingle once loading finishes; reloading or switching mods in the
  same window does not repeat it. Startup audio follows the shared Sound feedback toggle too.
  Idea reactions use a ding for Like / Good, a voiced "YES!" for Super Want, and an original incorrect-answer
  buzzer for Dislike. Removing a reaction keeps the ordinary click. Each master's active theme selects its sound
  bank automatically, including per-master themes; see `sounds/README.md` for the styles.
- Backups of every file changed go to `tools/organisation_master/backups/<time>/<mod>/...`.
- Settings (the last page and music mod) are in `%APPDATA%\OrganisationMaster\config.json`.

## To Do Master

**Added 23 October 2026** (also in Recent Changes):
- **⚠ Update** (menu bar, orange): GitHub has a newer Organisation / Culture / Country Master exe than this PC (a quiet
  `git fetch` every 10 minutes, never touching your files: pull, then restart), or the exe on disk changed while the
  tool was open (Restart now). Live Sync setup shows the same check. `update_check.py`.
- **🗑 Trash** (tool row): deleted tasks, projects and ideas for 90 days; Restore puts one back (a project takes back its
  tasks still without a project). Deletions keep a copy in `deleted_tasks` / `deleted_projects` / `deleted_ideas`; a
  restore marks the record `restored` (newer `when`) so it wins in Live Sync over the older delete. Renames don't go in.
- **⏰ Stale tasks** (tool row): claimed, open tasks untouched for N days (default 21, set on this PC); leads see all,
  devs their own; blocked / waiting / in review / Needs Fleshing don't count. Copy a nudge (Discord text per dev),
  Snooze 2 weeks (`snoozed_until`, synced), a quiet start-up reminder about your own.
- **Country reviews**: Country Master > right-click a country > Flag for Review... (reasons, note, a snapshot and a
  fingerprint of its history / own character files) > inbox > task in Country System > Review Countries
  (`country_review.py`). Selected task: flag, snapshot, changed-since-flagged / approved check, Open in Country Master,
  Approve (completes it).
- **🕘 Idea picture history**: external edits keep the replaced version (`picture_history` on the idea); the viewer's
  History lists them, ↩ Restore this version makes one current (the newer one goes into its history).
- **Automatic flags** (`auto_flags.py`): projects, groupings and idea categories / headings without an icon of their own
  get a country's flag from their name (base game + mod localisation: names, adjectives, ideology names; explicit tags
  like ENG), with the ideology flag when the name says one ("Communist China", "Fascist Britain").
  Region / continent names (`REGION_NAMES` + each globe's label in `icons/regions/regions.json`) give `region:id`
  (the longer match wins over a country name); one-word names that are ordinary words (`GENERIC`) are never a country.
- **Settings > Sound volume...** (all three masters, `sounds.json`): scales the generated sounds and the theme
  secrets' sounds; the Radio and Music Master have their own volume.
- **Dev VC agenda control**: ✎ Edit, ⏭ To Future Agenda and 🗑 Delete (tool buttons and right-click, which also has
  tick and move up / down). **Future Agenda** (`vc_future_agenda`, team-wide, synced): parked items with where they came
  from; ⇧ Into this VC brings them back. Ideas brought to the agenda follow their item. Its **📅 Next Dev VC** group
  (`next: true`) is what 📋 Bring to Agenda (Ideas, task right-click) adds when no VC dated after today exists; + New VC
  takes it in (`dev_vc.bring_to_agenda`; the old `vc_next_agenda` list is moved into it). Agenda items keep `by` (put
  forward by) through carrying, parking and bringing back; right-click > Put forward by sets it.
- **Dev VC section order**: drag a section's ⠿ grip to move it (everything under the VC header); saved per VC as
  `section_order`, a new VC copies the last one's. (`ui.Section.head_extras`: title-bar labels that follow its colours.)
- **Sync fixes** (`todo_sync.py`): with nothing to send, the clone's HEAD moves to origin so the next merge's base is
  the version both sides had (before, a PC only watching kept an old base and its stale copy won clashes). Written
  text both sides changed merges line by line (`merge_text`); in Dev VC notes the note taker's lines go first
  (`note_taker_first`). A push beaten by someone else's is 'beaten' (merge and resend at once), and 'offline' shows
  only after 3 misses in a row. `apply_remote` keeps the open VC; `show()` keeps the cursor and scroll.
  Each VC text records `edited[key] = {by, when}`: when both sides have a stamp, the newer wins outright unless
  two different people both wrote since the shared version (then line by line, note taker first).
- **No flash on sync**: `apply_remote` runs the merged data through `keep_unchanged` (unchanged sections and
  tasks / projects / ideas / VCs stay the same objects) and redraws only the panes whose data changed
  (`VC_DATA`, `IDEA_DATA`); `DevVC.refresh_remote` re-shows the open VC in place (attendee ticks and section packing
  are only remade when they differ). The local To Do file is written compact (the sync repo's copy stays indented).

The dev team's tasks. Every change also writes `localisation/english/rr_todo_l_english.yml`, the list shown in game.

**Live sync** (`todo_sync.py`): with a repository set in `sync.json` (`"remote"`), the To Do (tasks, projects,
milestones, Dev VC notes) lives in that repository instead of the RR one, and nobody commits or pushes it: changes are
sent a few seconds after you make them and the others' come in every 20 seconds (top right of the toolbar: ● Live /
○ offline). It's a repository of its own, so the RR repository (and the Discord git tracker) never sees these commits.
Changes are merged per task and per field (the same field changed by two devs: the later change wins); an RR number
given out by two devs at once is renumbered on one side; offline changes are kept and sent when it's back. Each PC's
copy is a clone in `%LOCALAPPDATA%\OrganisationMaster\todo_sync`. The first PC to start with an empty repository fills it
from `tools/organisation_master/todo_tasks.json`. Undo starts again after the others' changes come in. Music Master,
Culture Master and Country Master files are not part of it (commit them as before). Without `sync.json` the To Do is
`tools/organisation_master/todo_tasks.json` in the RR repository, committed like any file.

**🔄 Live Sync...** (next to Reload; clicking the ● Live / ○ offline status opens it too) checks every step on your PC -
Git installed, sync.json, your git name, GitHub access to the repository (signed in? added to it?), the local copy,
syncing now - says what's wrong and offers the fix: Download Git, Sign in to GitHub (a small window plus GitHub's
sign-in), Sign out (signed in with the wrong account), Copy a request for Mike, Who am I?, Sync now, Repair (a fresh
local copy: the old one is kept beside it, what's on screen is merged in). **Copy a report** puts every check on the
clipboard to paste to whoever helps.

- **You are** (top): which dev you are (guessed from your git name, remembered). Your name goes on the tasks you set and
  on every change you make.
- **Views** (the row of tabs): All open, My tasks, **General To Do** (tasks nobody has yet - anyone can **✋ Claim**
  one), **Needs Planning** (tasks to think through before anyone starts) and the Archive.
- **Dev mode / Project mode** (top): Dev mode lists the tasks flat with the Dev list on the left. Project mode
  shows the **Projects** on the left (each with its **Project lead**, open and done tasks) and the tasks as a tree:
  project > task > sub-task (e.g. Antarctica > Antarctica map > Terrain Map, Siberia Heightmap, ...). **+ Project** /
  right-click a project: lead, name, note, new task in it. A task's **Project** and **Sub-task of** are in its edit
  window and its right-click menu (**+ Add a sub-task...**). A task with sub-tasks shows how many are done.
- **Art Reviews** (kept by Country Master): a grouping *Country Master checks* with **Generic Review** and
  **Portrait Review**. Every generic / leader portrait marked for rework in Country Master is a sub-task under the
  right one (grouped by its rework category; *Needs Severe Recorrection* = High priority). Explicitly choosing
  **Not marked** in the updated Country Master completes the task; explicitly marking it again reopens it.
  Missing or incomplete local marks files never change completion status. Legacy false completions are repaired
  when loading or syncing. The marks file is checked every few seconds. Each portrait task also gets its
  source image in **Links**, including existing tasks. Mod paths stay relative; base-game portraits resolve against
  each developer's local game installation. Existing links are preserved.
- **RR Music Mods** (a project kept by Music Master): every planned music station is a task under the task of its
  music mod ("Music mod not decided yet" until it's attached), with the sub-tasks **Research Music**, **Upload
  Tracks** and **Create Radio Icon**. Attaching a plan to another music mod moves its task (recorded in the
  history), renaming a plan renames it, deleting a plan marks its task Not Possible. They start in the General To Do:
  claim them.
- **Groupings** are folders in a task (for its sub-tasks) or in a project (for its top-level tasks): right-click >
  + New grouping. Click one to write its **description** (everyone sees it); right-click it to rename, set its icon
  or remove it.
  Filtered lists (including My tasks) hide groupings without visible tasks. The unfiltered All open list keeps empty
  groupings available for organising.
- **Drag and drop** a task (or several) onto a task (it becomes its sub-task), a grouping or a project; Ctrl+Z undoes.
- Right-click the task section bar or **Task** column heading > **Collapse All** (Dev / Project mode) folds projects, groupings and sub-task branches back to
  their top-level rows. They remain folded when the list refreshes.
- Drag projects in the **Projects** list to reorder them. The order is saved and synced; Ctrl+Z undoes it.
  **No Project** stays at the bottom. Escape or dropping outside the list cancels a drag.
- The task window has an **Icon** (click it to pick; its category's otherwise).
- **Blocked by**: a task waits for others (right-click > **Blocked by (task dependencies)...**); it is shown pink
  with "⏳ blocked by RR-0003", and the task it waits for shows "⛓ blocking RR-0004".
- **Devs**: a task can have several devs (**Share with devs...**: tick them; none = back to the General To Do).
  **Claim** adds you, **Leave the task** takes you off.
- **New task...**: task, dev, category (**New category...**), priority (Low / Normal / High / Critical), status,
  reviewer, country tags (e.g. `GER FRA`), *Part of a sweep*, *🤖 Requires AI*, blocked reason, the setter's note (shown in game), the
  dev's note, and the tasks it depends on. It gets a reference, **RR-0001**, RR-0002, ... - use it in discussions,
  commit messages and bug reports (**Copy reference** / **Copy for a commit** gives `RR-0007: title`).
- **Timer**: how long the task has been there - green up to 2 weeks, yellow up to 3 months, red after that (it stops
  when the task is closed).
- **⭐ My next task** (tab): your tasks with nothing unfinished blocking them, by priority then age. Your ready tasks
  are light green in every list; tasks whose blockers were finished since you last closed the tool are gold, and a
  🔓 button on the tools row lists them.
- **Tools row**: **+ From template...** (a task with a template's sub-tasks: New country, Focus tree, Mechanic, Radio
  station, ...; **Templates...** edits them, right-click a task > Save as template), **Bulk add...** (paste lines -
  indented = sub-task of the line above - with a shared project, category, priority, devs, parent task and grouping),
  **🎲 Random task** (a free or ready task, weighted Low 1 / Normal 2 / High 4 / Critical 8 and a little by age),
  **🩺 Health** (unassigned, blocked, waiting for review and old tasks per project; projects without a lead) and
  **↶ Undo** (Ctrl+Z: back through the last 30 changes). Ideas has Undo beside Post; Dev VCs has it in the VC header,
  sharing the same history. Ctrl+Z runs this command throughout the main page, including its note
  editors; separate editing dialogs keep their native text undo.
- **Milestones** (left): a release / development target with a date. Put tasks in one with right-click > Milestone;
  click it to see its tasks and what still blocks it (red when its date has passed with tasks open). A whole project
  can go in one too (right-click the project > 🏁 Milestone): its tasks follow unless they have their own. Right-click
  a milestone to **Highlight** it (its tasks turn lavender, 🏁 in Flags) or **Hide** it (Show hidden brings it back).
  **Show all** (Dev list / Tasks bars) clears the dev, project and milestone filters.
- **Completing** a task asks about its unfinished sub-tasks (complete them too) and offers **Send for review instead**.
  Use **+ Add follow-up** to create one or more follow-up tabs, each with its own title, optional note and
  **🤖 Requires AI** checkbox. Project, category, priority and developers default to the completed task's.
  **Remove follow-up** discards the selected draft. Every new task links to the completed task in the Archive,
  which links back to all its follow-ups in **Links**. Completion and all follow-ups share one Undo step.
- **⧉ Duplicate** (right-click): a task with all its sub-tasks, or a whole project (project's right-click); blockers
  between the copied tasks point at the copies.
- **Links** (under the selected task): mod files, folders, commits (open on GitHub) and web addresses.
- **Click a cell** of a task's Priority, Dev(s), Category, Status or Project to change it there (for every picked
  task when it's one of them); **✋ claim it** in the Dev(s) column claims it. Click any column title to sort (▲ / ▼),
  the Sweep column included. Blockers are shown by their tasks' titles.
- **Music Mod To Do**: the RR Music Mods tasks nobody has claimed yet (kept apart from the General To Do; in game one
  line per music mod).
- **Right-click a task** (or several): **Claim** / **Leave**, **Share with devs...**, To do / Started / Partially Complete / Final touches / Completed / Not Possible,
  **Ready for Review...** (pick the reviewer), **Passed to Another Dev...** (pick the dev), Priority, Category (and a
  new one), *Needs Planning*, *Part of a sweep*, *🤖 Requires AI*, **Blocked (reason)...** / Unblock, **Depends on...**, Copy reference, Edit,
  Delete. Changes of status, category, dev, priority, blocked, reviewer, sweep and dependencies are recorded (who,
  when, old -> new) in the task's **History**.
- **Filters**: dev, category, status (or Open / Blocked), priority, age (green / yellow / red), country tag, and
  **Search** (reference, text, notes, tags...).
- **Radio** (bottom-left sidebar): choose an installed RR music station, then play its entire playlist in order
  or enable **Shuffle**. Includes play/pause, previous/next, stop, volume and **No ads**. The **⋯** menu offers
  **Repeat station**, **Skip jingles** and **Reload stations**. Options and station choice are remembered; music
  starts only when you press Play. Missing tracks are skipped. Music Master previews and Radio share audio
  safely, stopping the other playback when taking over. Radio reads saved music-mod files and never edits them.
  Right-click anywhere on the player and choose **Pop out radio** for a separate movable window. Right-click
  it to **Dock radio in sidebar**, close the floating window, or use the sidebar's **Radio · Dock** button.
  Playback, station, queue and options stay shared when docking; the floating window's size and position are remembered.
- **Dev list** (left): each dev's active, blocked and completed tasks (shared tasks count for each of them), the
  General To Do and Needs Planning, and what each dev last worked on. The **🏆 trophy** marks the dev with the most
  completions in the current calendar month; tied leaders share it. Click a dev to filter; **right-click a dev** (or
  double-click) to rename them (their tasks, notes and history follow), set their git name or remove them.
  **🙋 Ask for a task** (under the list) sets `asking_task` (a stamp) on your dev entry: you light up (amber, 🙋) in the
  leads' Dev list and a lead hears about it when it comes in; `unflag_askers` (every save) clears it once you're on a
  task set or given to you since.
- **🐞 Error Log Master** (side bar, between To Do Master and Music Master; a pop-out, `Scripts/error_log_master.py`):
  logs/error.log + text.log grouped by kind and message pattern (the varying words become …), 🆕 since the run before
  (`%LOCALAPPDATA%\OrganisationMaster\error_log_seen.json`), read again by itself when the game writes them. *🔎 Not in
  the log*: `Scripts/mod_lint.py` (braces, events called but never written, undefined GFX_ sprites, loc files - BOM /
  header / malformed / duplicate keys, missing focus and event text; cached in mod_lint.json). 📄 open the file (VS Code
  when there), ➕ a Bug task given to the file's last git author (link `errorlog:<id>`, once), 🙈 hide a pattern for
  everyone (`error_noise`). All token complaints (and the "N errors." total they add up to) are one kind, *Tokens*.
  *🌐 Localisation* has everything about text: text.log's duplicate keys (with both texts), the check's loc-file problems,
  missing text and a spell check of the English text (`error_fixes.MISSPELLINGS`); 🙈 Dismiss hides one for everyone
  (`error_dismissed`). The picked error is shown in full at the bottom with 💡 what it means / how to fix it
  (`error_fixes.HELP`) and 🔧 Fix it for the easy ones: missing synchronized tokens (added to tokens.txt), a duplicate
  key with the same text (the extra mod copy commented out - or the mod's copy when the base game has the same text),
  a missing BOM, a misspelling. Files are copied to backups/error_fixes first. Pop-ups are drawn in the theme (`ask`).
  A duplicate key's 🔧 opens a chooser (`choose_copy`): every copy with its text, 🎮 base-game ones highlighted (the
  theme's age_yellow, also in the list: 🎮 rows clash with a game file); the base game is never edited - the mod's text
  over a game key goes to `localisation/english/replace/rr_replace_l_english.yml` (`use_copy`), the game's text comments
  out the mod's copies; a DLC file's copy (goe_, aat_, nsb_... `error_fixes.DLC`) can be switched off with an empty file
  of the same name (`make_empty`). Spelling: the team's English (`loc_spelling`: British / American / Typos only;
  `error_fixes.VARIANTS` - the British setting flags American spellings and the other way round). Duplicate ideas: 🔧
  shows every definition (`find_defs`, common/ideas), keep one, the others are commented out with a note
  (`remove_defs`). The bottom right shows the code around the error (`places` / `snapshot`: the named file and line,
  where a token is used - git grep -, each duplicate idea's definition, each copy of a loc key, 🎮 the game's from its
  folder), the line and the name highlighted. An error with several parts (each duplicate idea, each token, each file:
  `parts`) gets ◀ 2 of 4 ▶ above the code - ← / → too (in the lists only when there are parts) - and 🔧 works on the
  part shown (duplicate ideas: the ones still to do first); 📄 Open goes to the first mod file the code panel shows
  for that part. A fixed error leaves the lists (🔧, or found fixed in the files since the log: `find_fixed`) and goes in
  *✅ Recently fixed* (shared `error_fixed`, 30 days: what, by whom, when, files); ✓ Checked clears it for you only
  (config `error_fixed_seen`). Reading (`parse`): messages over several lines are kept whole; every way the game names a
  place (`in file: "x" near line: n` - the line inside the quotes first -, `x.txt:123`, `in x line : n`, paths with spaces)
  is `FILE_REFS`; grouping ignores file names and numbers, keeps an Error: "..." message's first words, and keeps symbol
  mistakes (// , =) apart. `error_fixes.HELP` explains ~30 common errors (wrong scope, unexpected token, two limits in an if,
  missing default focus icon, NOT as an effect, removed doctrines / tech categories, 3D entities...); 🔧 also turns //
  into #, takes out commas and stray backticks (`fix_lines`; quoted text and real comments left alone). 📂 Open a log reads
  any error.log - another mod's is read only (no 🔧 / tasks / code: its files aren't RR's). The game's own logs are
  read only too when the last launch didn't run RR (`last_run_mods`: the launcher's dlc_load.json). The mod check
  (`mod_lint.references`) also finds flags checked but never set (a flag set as X_@ROOT counts for X_GER...), ideas /
  country tags / characters (capitals ignored, like the game) / focuses (joint focuses too) used but never defined,
  things defined twice (focus ids, top-level events, ideas), undeclared event namespaces, undefined decision categories
  and missing texture files (the game's dlc zips count); the base game's definitions count unless the mod's
  descriptor.mod replaces that folder. Tried on the 28 installed mods (KR, TNO, Pax, DBK...) to weed out false alarms.
  🔧 also re-saves 24-bit flags as 32-bit (`fix_flag32`).
  Severity (`error_fixes.severity`): 🔴 breaks things / 🟠 wrong in game / 🟡 cosmetic, sorted worst first, with a
  filter. A group row's 🔧 Fix all fixes every fixable one in it (`fix_all`). Braces: 🔧 puts the missing } where the
  indentation steps back out (`brace_plan`, two parts: where it opens / where it goes). "Did you mean" for names used
  but never defined (`mod_lint.suggester`, 🔧 renames), base-game leftovers (the same file exists in the game: 🔧
  comments the line out), map checks (`mod_lint.map_checks`: provinces in no state / two states / sea in a state,
  victory points outside their state, strategic regions, supply nodes, railways), Culture Master's data checks
  (`culture_checks`) and performance hints (nested every_ loops, on_daily, 24-bit flags). 👤 Only mine: problems in
  files you changed last (`authors`: git log), also in 📬 Since you were last here. ✋ Claim an error (shared
  `error_claims`, shown on the row); ➕ task rows show their task and fixing the error completes it (`complete_links`;
  gone from the next log / check too: `complete_gone`). 🙈 Accept asks why (Intentional / Base-game leftover / Harmless
  / Will fix later + a note, kept in `error_dismissed`). 📈 Trend: 🔴🟠🟡 totals per log and per check (shared
  `error_trend`), and the Monthly Report's 🐞 Errors line. game.log / setup.log / graphics.log are read too (their
  errors and warnings only). Live watch (`start_watch`, every 20 s): files you've changed but not committed get a quick
  check (braces, //, BOM) and the side-bar button shows 🐞 n; they come first in *Not in the log*. 🚨 Alert a dev
  (`Scripts/error_alerts.py`, shared `error_alerts`): the error pops up on their Organisation Master, topmost and flashing,
  until they answer ✋ (claims it, opens Error Log Master at it: `go_to`) or ⏳ with why; the sender is told. Settings >
  🚨 Error alerts can pop up for me (config `error_alerts`, shared as the dev's `alerts_off`). Capital errors
  (`error_fixes.capital_problem`: the country's tag from its loc name, its history's capital = line, the states it owns)
  get 🔧 `fix_capital`. 🤔 *Potential Unintentional Outcomes* (`Scripts/outcome_checks.py`, run by `mod_lint.run`; problems with
  `tab = "outcome"`): focuses on one spot / one-sided mutually exclusive / no reward / never available, self-firing and
  repeating MTTH events, same-name options, tag decisions with no tag check, unlimited every_ loops doing big effects,
  empty limits, placeholder and copy-pasted text (not the base game's own: `game_text`). The detail's parts are foldable (`section`; config `error_detail_closed`). 📈 Trend: a panel per
  source, each on its own scale. Only RR's errors go in
  the live sync: another mod's log (its launch, or 📂) writes nothing shared - no trend, ✅ fixed, tasks or 🆕 baseline.
- **Type to find** (every list in every master, `ui.install_type_to_find`): a letter jumps to the first row starting with
  it, the same letter again to the next (U: United Kingdom, United States...), letters typed quickly narrow it ("uni").
- **🟢 Online now** (in *Developer activity · leads*: online devs are lit up green, and *What they're up to* under
  the list): who has a tool open and what they're up to - "Painting
  Aleutian (culture) (Culture Master)", "Editing Japan (JAP) · Characters", "Playing RRdle (Hard)", "Reviewing pictures".
  Each master writes its line to `%APPDATA%\OrganisationMaster\now` (`Scripts/now_doing.py`); Organisation Master
  publishes this PC's lines to `presence` in the To Do data (at most every 30 s, a heartbeat every 5 min, offline on
  closing; `Activity.refresh_online` every 10 s). Settings > 🟢 Share what I'm doing off: just online.
  **Devs...** / **Categories...** do the same in a list.
  **Skills / wants to learn...** shows a developer list beside a readable category profile, with separate
  **Skilled** and **Want to learn** controls. Leads can switch between developers and edit lead status;
  other developers see their own profile. Switching profiles retains draft edits until **Save**; **Cancel** discards them.
  **AI Tool** disables skill and learning entry without deleting previous selections. Leads also have **View All**
  for a readable team overview, including current draft edits.
- **Achievements** (top menu bar, beside **Launch settings**): 59 badges with icons from the active theme, including 5 funny badges and a hidden
  rubber-duck Easter egg. Badges are grouped into collapsible sections for Organisation Master, Music Master,
  Culture Master and Country Master, plus **🎲 Fun & Games** last (`FUN_KEYS`: the theme secrets, the hidden Funny ones
  and 15 RR-game badges, group "Games", counted by `game_metrics` from `rr_game_scores` / `sleigh_scores` - e.g. Wrong
  Hemisphere (a Pinpoint miss over 8,000 km), Did You Peek? (RRdle on the first guess), Participation Trophy (5+ answered,
  none right)). Use the arrows to fold or expand each section.
  Filter by developer or badge group, search requirements, or open the Developers tab to
  compare earned badges. Double-click a developer to inspect their progress. Existing recorded work counts; shared
  tasks credit every assigned dev. Badges are retained in each developer's shared record with their first recorded
  date, so they survive renames and sync. **Win Developer of the Month** requires the highest completion count in a
  finished calendar month (ties count); the live trophy still reflects the current month's leader.
  Each of Music, Culture and Country Master has 10 tool-specific badges: playlists, tracks, station art and research;
  cultures, religions, languages, migration and population; countries, leaders, flags, armies and portrait reviews.
  Specific save badges require recorded file paths; older receipts containing only a mod name still earn the basic save badge.
  Other masters queue local
  save receipts for Organisation Master to import and sync, even if it was closed when the work was saved.
  Credit follows the shared **You are** identity, falling back to the mod's Git identity. Unknown identities stay
  queued until mapped in the Dev list. Saved work does not inflate completed-task or monthly trophy totals.
  In **Culture Master**, right-click a map state and choose **Flag for Review...** to queue a Culture task in
  **Culture System → Review States**. Choose **Needs Minorities**, **Unsure Placement** and/or **Needs Lore Update**,
  with optional notes and a link to the state's history file. **Selected task** shows current saved cultures and
  religions (including available icons), their presence, migratory tribe/band and cult/order. If current files are
  unavailable, it labels and shows the composition snapshot captured when flagged. Reflagging the same state
  updates its existing task and reopens it if finished. Requests wait safely if Organisation Master is closed.
  **Regional reviews**: Shift-click multiple states in Culture Master, then right-click → **Flag selected states for
  Review...** and name the review. They arrive as one task in the same grouping. Use the state's dropdown in
  **Selected task** to browse each composition and **Open state in Culture Master** to jump to that map state.
  Review panels separate names, groups, presence and majority/minority roles, with larger icons and rows.
  Migratory tribes and cults/orders have separate cards when present; absent entries share one compact line.
  Previous/next buttons browse regional states.
  Tables stack in narrower windows and only display scrollbars when needed.
  Click the state-name heading to collapse the reviewer. **Approve as is**, below **Open in Culture Master**,
  marks that state green; approving every member completes the task and records the reviewers. Click again to
  remove an approval (and reopen a completed review). Approval changes support Undo and Live Sync.
  A small progress bar tracks the approved count. The dropdown highlights approved states green with **✓**,
  and changed states blue with **?**. Saved composition changes are compared with the original review snapshot;
  their button becomes **Approve Changes**. Open reviewers check saved files every five seconds in the background.
  Approvals remember the accepted composition, so further edits require approval again and reopen completed
  reviews when detected. Comparisons ignore changes to translated labels, artwork and display order. Older
  reviews without an original snapshot cannot show changes since creation; older approvals without a saved
  composition fingerprint keep their existing approval until it is explicitly changed.
  Regional reviews have a collapsible **Show on Map** below the data source. New requests carry a compact map
  snapshot in their synced task; older reviews can build one from local mod files when expanded. The selected
  state is highlighted, approved states are green, changed states are blue, and clicking a review state selects its composition.
  Live sync requires an explicit deletion record to remove shared tasks or projects, protecting against stale
  copies that omit newer work. Use updated Organisation Master builds on all developers' PCs for Delete/rename actions.
  Older snapshots with truncated task history also retain previously recorded completion and assignment changes;
  an explicit Restore from archive or reassignment remains a normal editable change.
- **💡 Ideas** (mode, between Project mode and Dev VCs; `ideas.py`): small ideas before they're tasks.
  - Drag categories in the left-hand list to reorder them; the order is saved with the shared Ideas data. **All ideas**
    stays first. Escape or dropping outside the list cancels a drag; existing category contents and headings stay together.
    Right-click anywhere in the category box and choose **Undo change** to reverse recent reorders in this session.
  - **Post** one line into a category (seeded: Focus Trees, Events & Decisions, Mechanics, Map & Countries, Art & Visuals,
    Music & Sound, Balance, Lore & Alt History, Tools & Workflow, Misc; + Category adds one, leads rename / remove).
  - **Headings** (in the idea list, like the task list's groupings): **📑 + Heading** on the Ideas bar (in the picked
    heading / category; with All ideas it asks which category), right-click empty space in the list or a category on
    the left (works for an empty category too), or right-click a category or 📑 heading row >
    **+ Heading...** / **+ Heading inside it...** - e.g. Focus Trees > United Kingdom > Dutchtown. Pick a heading row
    and Post puts the new idea in it (Post shows "→ Focus Trees › United Kingdom › Dutchtown"); right-click an idea >
    📑 Heading to move it, or the 📑 box in Selected idea. With *All ideas* picked each category gets a row of its own;
    with one category picked its headings show even when empty. **🎨 Colour...** on a category or heading (what's under
    it takes it unless it has its own). Rename / Remove heading (its ideas go up a level). Folds are your own.
    Right-click an idea or a heading / category row > **Category** to move it to another category. A heading moves
    with its nested headings and ideas; a category row moves all its contents. Existing editing permissions apply.
  - **Drag & drop**: drag an idea onto a 📑 heading, a 🗂 category row, a 📁 project row (links it to that project) or
    another idea (goes where that one is); drag a 📑 heading into another heading or category (its sub-headings and
    ideas go along).
  - **Votes**: 👍 Good, 🔥 Super Want and 👎 Dislike, on as many ideas as you like (click again to take it back; a
    dislike and a want cancel each other; *Most wanted* = 2 × Super Want + Good − Dislike). **Comments**
    under each idea, **Size guess** (Small / Medium / Large), **links** and **pictures** (+ Picture... or 📋 Paste a
    screenshot; kept small and synced in `idea_pictures/`). Anyone votes, comments and adds links / pictures; the poster
    or a lead edits, shelves, reopens or deletes.
  - **Statuses**: Open, 🧩 Needs Fleshing (a lead sends it back to be thought through), Approved, Shelved, ♊ Duplicate
    (needs a comment saying why; it goes in both ideas' comments and the votes move to the original).
  - **🗄 Shelve...** asks why (`SHELVE_REASONS` in `Scripts/ideas.py`: Already decided / known, Not for RR, Too big
    for now, After release, Nobody to do it, Covered by another idea or task, Changed our minds, Other) and an optional
    note (`shelve_reason`, `shelve_note` on the idea). **🗄 Shelved Ideas** (left side, like the To Do's Archive) lists
    them grouped by reason: click to open, right-click to change why or reopen. Show has Shelved and Duplicates apart.
  - **✨ Only new** (next to Show hidden, with a count): only ideas posted or commented on by others since you last
    looked (`is_new`).
  - **📋 Bring to Agenda**: onto the next Dev VC (the next one dated today or later; if there isn't one yet, it goes in
    when the next VC is made).
  - **✔ Approve into a task...** (leads): title, category, *Sub-task of* (an open task: it goes in that task's project),
    project, priority, Needs Planning (ticked by default). The idea's size, votes, details, links and comments go in the
    task's note; the idea shows its RR number.
  - **Search**, **Sort** (newest, most wanted, most comments, size) and Show (Open + Needs Fleshing, ..., All).
  - **Linked ideas**: right-click a task or a project (task list, Projects list) > **💡 Add a linked idea...** (and
    **💡 See its ideas (n)**). The list groups ideas **by project** (a task's ideas follow the task's project; ideas
    with no project sit at the top level, after the project folders; right-click an idea > **📁 Project** to assign one): fold / open each (⊟ Fold all / ⊞ Open all), sort the projects (A-Z, most ideas, most wanted) and
    right-click one to hide it (Show hidden brings them back); folds and hidden ones are your own. The selected idea's
    *Linked to* (project, task) can be changed; approving a task's idea starts as a sub-task of that task.
  - **New since you last looked** (your own): 🆕 / bold in the list, new comments highlighted, and the Ideas button
    counts them; from 10 new ideas it flashes until you look.
  - **📅 Monthly Ideas Report** (left): posted, approved, needing fleshing, shelved, comments, the most wanted, ideas by
    dev; 📋 Copy for Discord.
- **Status Needs Fleshing**: makes (or reopens) a linked idea in 💡 Ideas, marked 🧩 Needs Fleshing, with the task's note.
  Talk it through there (comments, links, pictures); a lead's **✔ Fleshed out → back to RR-0000** puts the task back to
  To do with what was added on the idea in its note. Moving the task off Needs Fleshing any other way closes the idea.
  The task shows its idea (Selected task) and right-click > 💡 Go to its idea.
- **🏷 Descriptors** (fields a task fills in, e.g. a landmark's Location, Culture/Requirements, Upgrade 1-3): right-click
  a project or a grouping > **🏷 Descriptors for its tasks...** (add / remove / reorder; 📍 + Location) - every task under
  it gets them in the **🏷 Descriptors** box of Selected task (typed in place, saved a moment later; the box says where
  each field comes from). A single task: right-click > **☐ 📍 Has location** / **📍 Set the location...** / **🏷 Its own
  descriptors...**. Add or remove fields whenever: the values stay with each task. Search finds them.
  **Yes / No** fields: tick *Yes / No* when adding one (or select it and press ⇄ Yes/No / Text): it shows as a tick
  box instead of a text field (saved as Yes; search finds e.g. "decision yes"). A field's type goes with its name.
  **🎨 Needs Icon/Art** (right-click a task, or 🎨 + Needs Icon/Art in a project's / grouping's list): the box gets an
  **Icon / Art** area - + Picture... / 📋 Paste (a screenshot), thumbnails (click to open, right-click to remove); kept as
  PNG (transparency kept) in `idea_pictures/` with the live To Do, so everyone sees them. Until art is added the task
  shows **🎨 Needs art** in the list.
- **Archive (completed)**: Completed and Not Possible tasks, searchable like the rest.
  The completion popup includes **Completed by**: keep the assigned devs (or yourself when unassigned), or choose
  a developer explicitly, including **Chat Jipity** and **Claude**. Credit is recorded in task history. Cancelling or
  sending for review leaves the credit unchanged. Missing Country Master marks files no longer complete portraits.
  **📅 Monthly Report** (on top of the Archive): pick a month (◀ ▶) and see everything completed in it, by project, with
  counts by dev / project / category, the month before, new tasks set and Dev VCs held. Double-click a task to go to it;
  **📋 Copy report** puts it on the clipboard as text ready for Discord.
- **The picked task** (bottom): who set it and when, its fields, dependencies (still waiting ones are flagged ⏳), the
  blocked reason, the setter's note and the dev's note (both editable there, saved as you type) and the history.

**In game**: `interface/rr_todo.gui` + `common/scripted_guis/rr_todo_mechanics.txt` show the open tasks per dev
(timer, reference, task, priority, category, status, who it's shared with, blocked reason, what it waits for, the
setter's note), then the General To Do and Needs Planning, when you start playing a country. The close button hides it, **Shift+T** opens / closes it again. Timers in game are as of the
last change made in To Do Master. `rr_todo_enabled` (common/scripted_triggers/rr_todo_triggers.txt) switches the
whole window off, e.g. for a public release.

- **Icons** (`tools/organisation_master/icons/`: one sprite sheet per theme, the same 80 icons; Classic uses the RR
  one): every project, grouping and task has one. Right-click > **🖼 Icon...** picks it (search, hover for its name,
  Default). Defaults: projects a flag, groupings a book, tasks their category's icon - **Categories... > Icon...**
  sets a category's.

### 🖼 GFX (missing pictures)

The GFX mode (between Project mode and Ideas) scans the mod for pictures it asks for that aren't there
(`Scripts/gfx_master.py`, scan cached in `%LOCALAPPDATA%\OrganisationMaster\gfx_scan.json`):

- **Culture Icons**: cultures and subcultures without their `gfx/interface/culture` icon (Culture Master's naming).
- **Religious Icons**: religions and religion groups without their `gfx/interface/religion` icon.
- **Flags**: countries with no flag at all, ideology flags with no plain flag to fall back on, and the mod's own
  flags missing their `small/` or `medium/` copies.
- **Portraits**: generic portraits (large, and small for army / navy) and leaders without a large portrait.
- **Ideologies**: main ideologies (`GFX_ideology_<main>_group`) and sub-ideologies (`GFX_ideology_<token>`) without an icon.
- **🎯 National Focus**: focus icons (`icon = GFX_...`, including the trigger / value form) in the mod's own focus trees
  whose spriteType or file isn't there; one item per sprite, families by tree (`focus_and_idea_icons`).
- **📜 National Ideas**: national spirits' pictures (`picture = x` -> `GFX_idea_x`, or `GFX_idea_<idea>` without one; also
  `GFX_x`). Laws (`law = yes` categories, economy / trade / mobilization), designers, advisors, `hidden_ideas` and the
  scripts' token ideas (nothing to show: no modifier, picture, research / equipment bonus, rule, on_add / on_remove)
  are left out. Families by country (`TAG_...`), else by file.
- **Pictures** (references, yours, and the picture itself for 🗑 unused / ⚠ broken) use Ideas' thumbnails:
  `idea_picture_viewer.picture_label` / `show_picture` - click pops it out in the zoomable viewer (DDS / TGA too;
  one PIL can't read opens in its own app).
- **First look on a new PC**: the scan takes ~5 minutes the first time (reading every country, checking ~30,000
  pictures). Until a PC has its own (`%LOCALAPPDATA%/OrganisationMaster/gfx_scan.json`) it shows `gfx_scan_seed.json.gz`
  (in git, paths stored as `<MOD>` / `<GAME>`; `write_seed` / `read_seed`). Refresh the seed now and then:
  `gfx_master.write_seed(items, when, mod_root, find_game(mod_root))` from a recent scan. While scanning, the tab shows
  the step and the time (`list_note`); a failed scan shows its error there.
- **Animated pictures** (`gfx_checks.animated`: a `frameAnimatedSpriteType`, or a `spriteType` with `noOfFrames` > 1, in the
  mod's interface/*.gfx) are measured by one frame (`frame_size`: the width split by the frame count that divides it), so
  frame strips aren't ⚠ Broken for being wide.
- **🔁 The rework list is shared** (`todo_tasks.json` `gfx.rework`, live): portraits marked in Country Master arrive
  through the activity inbox (`portrait_marked` / `portrait_unmarked`, with category, used by, kind and note) and from
  this PC's `portraits_to_rework.txt` (`sync_art`: any not on the list yet, unless reworked since - `gfx.rework_done`).
  The old per-portrait Art Reviews tasks were moved here once (`move_portrait_tasks`; the tasks are in the 🗑 Trash).
  ✋ claims on the list itself (`claimed`); ✓ Reworked unmarks for everyone (and this PC's Country Master file). The To
  Do keeps one task per kind (`rework_group`: generics, portraits, or the GFX section), `art_review:rework:<kind>`
  (*🔁 Rework Generics (N waiting)*...), open while that kind has anything (`rework_task`; the old single task is folded in).
- **Art review tasks are shared** (`REVIEW_LINKS`: art and portrait reviews only; one task covers many pictures): claimable,
  but still in the General To Do for everyone (`in_general`). State, idea and country reviews are claimed as usual.
- **🔁 Needs Rework** (beside Missing / Broken / Unused): right-click a picture under *Look at these* (or the picture
  itself) > 🔁 Needs rework... (Country Master's categories + a note) -> `todo_tasks.json` `gfx.rework` {key: {file, name,
  section, family, reason, note, by, when}} (synced; `refresh_items` adds them to the scan's items). Portraits marked in
  Country Master (`tools/country_master/portraits_to_rework.txt`, this mod's lines) come in with the scan (`cm_reworks`).
  ✋ makes a *Rework: ...* task; ✓ I made it / ✓ Reworked removes this tab's mark (Country Master's: unmark there).
- **🤖 AI suggestion / 📝 Human suggestion** are separate boxes (the human one: `gfx.items.<id>.human_suggestion`,
  `human_by`, `human_when`). **👍 Good / 👎 Not good...** rates the AI's (`ai_rating`: rating, reasons from `AI_RATE_REASONS`,
  comment, by, when, the suggestion rated); ratings are synced and exported to `gfx_suggestion_ratings.json`. **🤖 Ask AI**
  adds the feedback (`rating_feedback`) and re-asks for suggestions rated not good.
- **🔗 Related** (`related_box`): the item's parent and children from the scan (`related`: cultures <-> subcultures,
  religion groups <-> religions / sects, ideologies <-> sub-ideologies; {id, kind, name, role, path}). Pictures show as
  thumbnails (right-click: 🔁 Needs rework); relatives in the lists get a 🔍 button (`go_item` jumps to them).
- **Families in the list** (`fill_list`, `parent_id`, `CHILD_KINDS`): subcultures inside their culture, religions inside
  their group, sub-ideologies inside their ideology. A parent not in the list (its picture is done, or it's in another
  list) gets a group row, green when done (`show_group`: its picture, ✋ all / 🤖 Ask AI for the family). 🤖 Ask AI
  writes a `# Family:` line before each family.
- **◀ ▶ history** (`remember` / `step_history`): the items looked at; the mouse's back / forward buttons (Tk's Button-4 /
  Button-5 on Windows) step through it while GFX is on screen.
- **Image links**: links that are pictures (a direct image, or a Wikimedia Commons file page) show as thumbnails
  under the list at all times (`link_thumb`, loaded in the background; click -> `pop_link` -> the viewer); **Show pictures**
  hides them (`gfx_link_pictures` in config). **🔎 Find pictures** searches `search_words(item)` (cultures: "<name> culture
  -portrait", not people) with quick buttons from `search_options(item)`.
- **🤖 / 📝** beside Status (`marks`): an AI's suggestion in `gfx_suggestions.json` ("by" in `AI_NAMES`), and / or a
  person's (the item's Notes, or a suggestion there signed by a dev).

Each item shows a 🤖 suggestion, reference pictures (its siblings, the country's other flags), image links and your
own pictures and notes. Suggestions come from `gfx_suggestions.json` (Claude / ChatGPT fill it: 🤖 Ask AI copies a
request for up to 40 items without one), else one made from the mod's data. **🃏 Swipe for a task** deals random
missing pictures: left = not this one (personal, in your config), right = a task for you in project *Missing GFX*
(link `gfx:<id>`; ✋ claim any one from the list too). **✓ I made it** completes the task (counted per dev in the Archive's
Monthly Report, column 🖼 GFX made); a rescan also completes tasks whose picture is now in the mod. **🔎 Review swiper**
(`Scripts/gfx_review.py`) deals the mod's own pictures that are there (the scan lists them as `problem: "present"` items,
kept apart in `gfx_pane.present`) and aren't in 🔁 Needs Rework, a family at a time: → looks fine (personal,
`gfx_review_passed` in your config), ← needs review (`ask_rework`: level + what's wrong, into the shared rework list;
portraits by sprite like Country Master), ↓ not sure (comes round again). "Looks fine"s are shared
(`gfx.review_passed` {picture id: {dev: day}}: the card says who it looked fine to) and counted (`gfx.review_counts`:
the 🔎 Today counter and the Fresh Eyes / Eagle Eye badges). **🔀 Before / after** (`Scripts/gfx_compare.py`): the
picture as committed in git before it was marked vs now, side by side or overlaid (Space / click flips, a slider
blends); `unmark` keeps file / name / marked in `gfx.rework_done` so reworked ones can be compared too.
**✨ Remini** (`Scripts/remini.py`, tooltip: GFPGAN by TencentARC): restores and upscales the picked picture (2× / 4×)
on this PC. First use asks, then sets up its own venv in `%LOCALAPPDATA%\OrganisationMaster
emini` (a Python 3.10-3.13
on the PC; PyTorch CPU + gfpgan / basicsr / facexlib from PyPI, GFPGANv1.4.pth from GitHub, ~2 GB; basicsr's old
torchvision import is patched). `Scripts/remini_worker.py` runs in that venv. The result: side by side / overlaid,
💾 Save as PNG, or ⬇ Use it in the mod (the original's size and format; the original goes to backups/remini).
✏ Edit overlay: Remini's version over the original - Strength slider, 🧽 Eraser (at a % level) / 🖌 Restore brush on
a per-pixel mask, Ctrl+Z per stroke; 💾 Save overlay layer = Remini's version with that mask as alpha. Photoshop's
brush keys: Alt + right-drag (left / right size, up / down level, smooth), [ ] size, E eraser, B brush, X swap, 1-0 level.
**🎭 Self swap →** (in Remini's window; `Scripts/remini_swap.py`): "FaceApp it with itself" - the original portrait's
face put back onto the edited Remini picture with InsightFace's inswapper_128 + ArcFace w600k_r50 (VisoMaster's model
files, sha256-checked, onnxruntime on the CPU; RetinaFace from facexlib finds the faces), soft-mask paste back, GFPGAN
cleanup; opens as the next step with its own overlay / eraser. Its setup (~430 MB) is in Settings > ✨ Remini or asked
for on first use (`setup_swap`, `swap_ready`). Right-click either window (or Ctrl+C / Ctrl+V): 📋 copy the result /
the top layer / the original (clipboard PNG + bitmap: `copy_image`), 📥 paste on top - the pasted picture becomes the top
layer for the strength / eraser (`paste_image`; Ctrl+Z takes a paste back). Settings > ✨ Remini
(GFPGAN): detect / Set up / Repair / ⚡ NVIDIA GPU (CUDA PyTorch) / Uninstall (`remini.Settings`). Rework reasons:
"Looks too AI" (icons) and "Needs a Remini" (portraits; Country Master's categories too) - `reasons_for(section)`. "Not actually missing" hides an item for
everyone with a reason.

Besides 🔍 **Missing**, the scan (`Scripts/gfx_checks.py`) finds ⚠ **Broken** pictures (a DDS that isn't DXT1 / DXT5 /
uncompressed, RLE or non-32-bit flag TGAs, a size that isn't the rest of its family's - flags 82x52 / 41x26 / 10x7 -,
stretched portraits, icons without a spriteType) and 🗑 **Unused** ones (files nothing points at in gfx/interface/culture,
religion, ideologies and gfx/leaders; spriteTypes in RR_cultures / RR_religions / rr_ideologies.gfx for entries that
are gone; flags for no tag or cosmetic tag). Only file headers are read, cached in
`%LOCALAPPDATA%\OrganisationMaster\gfx_headers.json`. **🗑 Remove** deletes an unused file and its spriteType block after
copying both to `backups/gfx_removed/<time>/`. **✋ The whole family** makes a parent task (link `gfx_family:<key>`)
with a sub-task per open picture. **📈 Progress** reads `gfx.history` ({date: {section: left}}, written after each
scan); the Monthly Report shows "GFX left" from it. **👁 Preview in game** fits a draft to its family's size.
❓ **Needs clarification** (anyone, or an AI via `"needs_clarification"` in `gfx_suggestions.json`) highlights an
entry nobody is sure about and posts the question as an idea in 💡 Ideas under **Art & Visuals › GFX Clarification**
(`CLARIFY_CATEGORY` / `CLARIFY_HEADING` in `Scripts/gfx_master.py`; the heading is made when first needed, and GFX
questions still loose in Art & Visuals are filed there whenever the tab refreshes - one a dev moved elsewhere stays);
✓ Clarified, or closing the idea, clears it. Shared data: `todo_tasks.json` → `gfx.items`.

### 🎙 Dev VCs (the third mode)

The team's voice calls, like tabs on the left (newest first; ◀ ▶ or PgUp / PgDn to flick through them). Each has a
title, date, note taker and attendees, an **agenda** (tick items off; **+ New VC** offers to carry the unticked ones of
the last VC forward, marked with the date they came from), and separate **Discussion**, **Decisions**, **Action items**
and **Notes** - only Action items become tasks, so ideas that were just talked about don't become commitments. Every
RR-0123 written in them is a link to that task.

Tasks from a VC: **Extract from Action items** (lines like `Mike & Globus: fix the coast #Antarctica !high under
RR-0001`), or **📝 Note for Claude / ChatGPT** (writes the VC and instructions to `Templates/AI_Notes/Dev_VC/`, and copies
it to paste into ChatGPT) then **Load the AI's tasks** (the `_tasks.json` the AI writes next to the note, or its pasted
answer). They wait in **Proposed tasks**: double-click one to edit it, click ✓ to (un)tick it, **Commit ticked** adds
them to To Do Master (noting the VC). Committed ones show their RR number - click it to go to the task.
The proposed-task editor includes **Needs AI**; this flag is retained when the proposal becomes a task.

Right-click a proposal and choose **Deny** to record **Completed**, **Changed Opinion**, **Duplicate**, or **Not a Task**.
Denied proposals stay visible crossed out with their reason, are excluded from sending and pending counts, and can
be reopened with **right-click > Restore denied**. Right-clicking a selected row keeps the multi-selection, so these
actions can apply to several proposals together.

The **Proposed Tasks / Proposed Ideas** buttons switch the same panel between the two lists. **+ Propose idea**
adds an idea with its category, project and notes; **Move to Ideas / Move to Tasks** reclassifies selected unsent
proposals. In Ideas view, **Send ticked to Ideas** posts open ideas with the VC context and keeps a link to each
posted idea. Its AI note and loader use separate `_ideas.md` / `_ideas.json` files, capturing tentative suggestions
without creating tasks. Sent and denied proposals cannot be sent again.

Drag the handle beneath Agenda, Discussion, Decisions, Action items or Notes to resize its editor. Heights are
remembered on this PC; double-click a handle to reset it.

Drag the **⋮** handle beside the VC list to change its width (remembered on this PC). The list shows separate
**Sent**, **Pending** and **Denied** totals, including task and idea proposals. VCs with proposals all sent or denied
turn grey; restoring a denied proposal makes its VC pending again. Empty VCs remain unmarked.

## Music Master

Music mod discovery reads names first and loads full data only for the selected view. Track lengths are read
in the background, shown as **…** until ready, and cached for the session. Totals update without resetting song
selection, scroll or playback; unrelated installed music mods are loaded only when selected.

Radio stations and songs of RR's music mods (`Revolution_Realized_Musics`, `Revolution-Realised-Music-Crimson-Tunes`,
or any mod next to RR in the mod folder with a `music/` folder).

A station is:
- `music/<station>.txt`: `music_station = "<station>"`, then one `music = { song = "<name>" chance = { modifier = { factor = 1 } } }` per song
- `music/<station>/*.ogg`: the songs
- `music/*.asset`: one `music = { name = "<name>" file = "<station>/<file>.ogg" volume = 0.65 }` per song
- `<station>_TITLE` in the mod's localisation: its name
- `GFX_<station>_album_art` (interface/*.gfx): its picture, 304x120 in 2 frames (the station button and the picked one)
- `<station>_faceplate` and `<station>_stations_entry` (interface/*.gui): the player and the station button

**Music mod** (top): pick the mod to work on (remembered). **★ All RR music mods** shows the stations of every RR
music mod at once, each mod in its own colour (the legend under it); the tools on the right work on the picked
station's own mod. Other mods with music (Pax, DBK, ...) are listed after the RR ones as "Other:". **New music mod...**: name, folder, file prefix, supported
version (RR's), an optional main menu line and thumbnail; it makes the folder with `descriptor.mod`, the launcher's
`<folder>.mod` next to it, `music/<prefix>_music.asset`, `interface/<prefix>_musicplayer.gfx`,
`interface/<prefix>_music_stations.gui`, `localisation/<prefix>_music_l_english.yml` and (with a main menu line)
`localisation/english/replace/<prefix>_addons_l_english.yml`.

**Save to mod** (top right, like Culture Master): changes to the music mods wait until you press it (or Ctrl+S);
**Discard** throws them away, and closing with unsaved changes asks first. Songs added, album art and files to delete
are kept aside until then; every file written is backed up first.

**Gap Finder** (top): duplicates and missing music are looked for every time the mods load, and their count is on the
button. It lists: the same song name twice in the .asset files, the same song spelled differently, one file used by
two songs, a song twice in a station, **missing music** (no file / no .asset entry), stations without a name or album
art, songs in no station and unused .ogg files. Double-click one to go to it.

**Radio stations** (left): each with its number of songs and total length; red when something is missing (a song
file, its `.asset` entry, the name or the album art). **Check the mod** lists all of it, and songs of the `.asset`
files no station plays. **New station...**: name, token, album art - writes the station file and folder, its name,
its album art (the picture fills the button; the second frame gets the red "picked" frame) and its windows in the
`.gui` (a copy of another station's, of this mod or another music mod).

**The station** (right): album art, name (**Rename...**, **Album art...**), and its songs with length (read from
the .ogg), volume, chance and file.
- **Add songs...**: pick .ogg files (Ogg Vorbis only - HOI4 plays nothing else; convert others first, e.g. Audacity >
  Export > Ogg). Each gets a name (from its Title / Artist tags, else its file name; editable), volume (slider, ▶ / ■ to hear it)
  and chance factor (conditions afterwards with Edit song...).
  The file is copied into `music/<station>/`, its `music = { }` goes into the `.asset` file (after this station's
  songs) and into the station's file.
- The list shows **Song** and **Artist** apart (in game the name stays `Song - Artist`). **Sort by** (Order in the
  file, Song, Artist, Length, Volume, Chance; ▲/▼) or click a column title; it stays sorted.
- **The file**: double-click a song's File cell to point it at another .ogg straight away (one from outside the mod is
  copied into `music/<station>/` on Save).
- **Edit song...** (or double-click): song and artist (the game's name, also in the `.asset` and every station that
  plays it), its file (with ✓ / ✗ and Browse...), volume (a slider;
  double-click its number to type one; **▶ / ■ hear it** plays it at that volume, and moving the slider changes it as
  it plays) and its **chance**: the code inside `chance = { }`, like vanilla's - one or more
  `modifier = { factor = 0 NOT = { is_tag = USA } }` (each multiplies the chance when its triggers are true). The
  buttons under it add the usual ones (only / more for a country, only at peace / war, only for an ideology). The song
  list shows it in short, e.g. `×0 if not (is_tag = USA)`.
- **Move to station...**: to another station (or copied, keeping it here too); its file stays where it is.
- **Remove**: out of this station; a song no other station plays loses its `.asset` entry too, and you are asked
  whether to delete its file (a copy goes to the backups).
- **▶ in front of a song** (or **▶ / ■ Play**): plays it here, at its in-game volume; it turns into a red **■** - click
  it again (or **■ Stop** on the bar under the list) to stop. The bar also has **⏸ Pause / ▶ Resume**, the time and a
  slider to jump in the song. Picking another song's ▶ switches to it. **Open in player**: the default player.
  (Playing uses pygame; build.bat installs it.)

**Planned music stations** (bottom left): ideas for stations - name, the music mod it goes in, token, status (Idea /
Collecting songs / Ready to make / Uploading Songs / Awaiting Art / Made), theme, the songs wanted (`Title - Artist | link`, ✓ = already in game) and
notes. Kept in `tools/organisation_master/planned_music_stations.json` (in the RR repository, so everyone sees them).
**Awaiting Art** completes the linked **Research Music** and **Upload Tracks** To Dos, leaving **Create Radio Icon**
and the station's main task open. **Uploading Songs** completes only **Research Music**. Attaching a logo completes
**Create Radio Icon**, regardless of the station's status (existing attachments count too; missing files do not).
Changing back to another music status or removing artwork preserves those recorded completions.
The list shows the plans of the mod(s) in view plus the ones with no music mod yet (grey), coloured like the stations.
- **Clicking a plan** shows it on the right, laid out like a station being made: its logo (**Logo...**, saved as a png
  in `tools/organisation_master/planned_station_logos/`; it becomes the album art when the station is made), name,
  token, music mod, status and theme (edits are saved as you type), then its songs with artist, "in game" tick and
  YouTube link. The red ▶ in front, double-click or **▶ Watch on YouTube** opens the video; a song without a link searches YouTube for
  it. **Add song... / Edit song... / Remove / ▲ ▼ / In game ✓ / ✗** and the notes are there too.
- **Right-click a plan** (or several): pick its music mod, **New music mod (planned)...** (a short name and colour,
  for a music mod that has no folder yet), **Name / colour of ...** (the short name and colour of any music mod in the
  lists, e.g. "Crimson Tunes"), and **Make ... now** for a planned one (New music mod..., prefilled; its plans, name
  and colour then go to the new folder). The names and colours are kept in the plans file (`music_mods`).
- **Added by**: new plans and songs remember the git name (`user.name`) of whoever added them, shown above the songs
  and in the songs' *Added by* column; plans without it get it from `git blame` of the plans file. A station shows who
  added its file to the music mod's git (`git log`).
- **Attach to music mod...**: sets the music mod of the picked plans (Ctrl / Shift click for several), or "(not decided)".
- **Import from spreadsheet**: reads the Music tab of the RR spreadsheet; stations no RR music mod has yet (names
  compared loosely, so "The Voice of the Worker" = "Voice of the Worker") become plans with their songs, and plans
  already there get the songs they don't have yet. Safe to run again.
- **Make the station** turns a plan into a real station in its music mod (asked when it has none) and marks it Made.

**Milestone celebrations**: right-click a milestone > **Complete milestone / special thanks**, or find it with Ctrl+K. Choose any developers for special thanks, preview locally without completing anything, then **Complete & celebrate**. Completion keeps task statuses unchanged. Announcements and per-developer seen receipts use Live Sync; offline developers see pending announcements on launch. A celebration interrupted by a crash/shutdown is offered again. The sound toggle and volume apply. Updated executables and external art/audio assets must be installed on each PC; Live Sync carries the announcement, not program updates.

Mechanics celebrations use the Trotsky duck tightening a bolt with a spanner, then wiping sweat off his brow. Automatic chooses this for milestone names containing Mechanics/Mechanical; the completion dialog’s Animation dropdown can also select it for any milestone. Confetti and music begin at the final turn; the preview never publishes a completion.

Technology celebrations use the Trotsky duck picking up a raygun backwards, investigating the wrong end, then a harmless zap leaving soot and a continuous blink loop. Automatic selects this for Technology/Tech milestone names, or choose Technology duck explicitly. The zap sound plays once; the accident does not replay during the blink loop.

Error Log Master and its alert popups update with the active theme: navigation tabs, code/detail backgrounds, highlights, severity colours and alert borders. Soviet Terminal plays a short code-drawn 1980s flat WarGames-style vector nuke with impact arcs and an outlined mushroom-cloud header that settles after five seconds, above the readable message and response buttons. The other thirteen themes now use the chosen polished pixel animation scenes with supporting motion and particles, stored in `secret_assets/error_alerts/`. Each scene plays once and settles above the readable message and response controls. Original sound-effect sequences in `sounds/error_alerts/` follow the animation, respect Sound feedback and volume, and use a separate mixer channel from the Radio. Closing the popup stops its sound.
