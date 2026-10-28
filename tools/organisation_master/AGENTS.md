# Notes for AI agents (ChatGPT / Codex, Claude)

Read "Working on the tools" at the top of README.md in this folder before changing anything here. In short:

- **Adding To Do tasks** (yours or the user's): run `python Scripts/ai_tasks.py tasks.json` (`--who "Chat Jipity"` for
  ChatGPT; the file's top explains the fields). The open Organisation Master adds them live within seconds; never
  close / reopen it for that, never edit `todo_tasks.json` or the sync clone, never park To Dos in a text file.
- **Celebration tester: hashed out (2026-10-25, Mike asked).** Settings > Celebration tester, its Ctrl+K entries and its
  📖 guide step are commented out (organisation_master.py, Scripts/search_palette.py, Scripts/guides.py; the functions in
  Scripts/milestone_celebration.py are left for the tests). Don't bring it back or add other test menus unless asked;
  milestones still preview from Complete milestone / special thanks.
- **🟢 What you're doing** (`Scripts/now_doing.py`): each master calls `now_doing.report("<Master name>", "<a few words>")`
  every ~10 s and `now_doing.clear(...)` on closing; Organisation Master shares it (`presence` in the To Do data). A new
  master should do the same with something useful ("Editing <thing>"), not "Using the tool".
- Code goes in `Scripts/`; only `organisation_master.py` stays in this folder.
- Find the tool's files with `import paths` and `paths.TOOL` (never `dirname(__file__)` or `sys._MEIPASS`).
- Art and sounds live in `sounds/`, `secret_assets/` and `icons/` here and are NOT built into the exes; keep pictures
  near the size they're drawn at.
- Build only with `build.bat` (close the master first). The build.bats make a spec, run `Scripts/slim_spec.py` on it
  (leaves out Tcl's time zones / translations: ~750 fewer files to unpack, faster start), then build from the spec;
  keep that order when changing a build.bat. Culture / Country Master use some of these scripts: rebuild
  them too when those scripts change.
- 🖼 GFX suggestions: when asked to fill GFX suggestions, add them to `gfx_suggestions.json` here
  (`{"items": {<GFX id>: {"suggestion", "links", "by"}}}`), keeping what's there; only link images you know exist. Not sure what an entry is? Give it `"needs_clarification": "<your question>"`
  instead: the tab highlights it and asks the team in 💡 Ideas, filed under **Art & Visuals › GFX Clarification**
  automatically. Don't post GFX questions as ideas yourself; use `needs_clarification` so they land there. (If you
  ever must add one straight into the To Do data, give it `"category": "Art & Visuals"`, `"heading": "GFX
  Clarification"` and `"gfx": "<GFX id>"`.)
- Before writing GFX suggestions, read `gfx_suggestion_ratings.json` here: the team rates each AI suggestion 👍 / 👎 with
  reasons (Not fitting the theme, Nonsensical, Too basic, Wrong / inaccurate, Too detailed for its size, Doesn't match its
  family's style, Links broken / not useful, Copies another entry's suggestion, Other) and a comment. Avoid what was rated
  bad, keep doing what was liked, and replace the suggestion of any entry rated bad (🤖 Ask AI's request lists them).
  People's own ideas for an entry are in the To Do data (`gfx.items.<id>.human_suggestion`): don't contradict them.
- New features get an entry in `Scripts/release_notes.py`.
- **A new master**: start from `master_template/` (its README has the steps): a `master_base.MasterApp` subclass plus a
  `master.json`, which registers it everywhere (Organisation Master's Masters menu / side bar, activity, rr:// links, the
  update check). Don't hand-copy Culture / Country Master's start-up code.
- **New pages, buttons and features**: add a step to the matching guide in `Scripts/guides.py` (`GUIDES`: where = a
  function finding the real widget) and, for a new page or action, an entry in `Scripts/search_palette.py` (Ctrl+K).
- New links between records (a task's `parent`, an idea's `task`...) that can point at something deleted: teach
  `Scripts/data_check.py` to fix or report them.
- The exes run from a copy in `%LOCALAPPDATA%\OrganisationMaster\run` (`Scripts/run_copy.py`) so a git pull can replace
  them; in Task Manager they're `OrganisationMaster-<size>-<time>` etc. Keep the `run_copy.start(...)` call right after
  `import sys` in each master's start script, and use `sys.executable` (it's set back to the repository's exe) or
  `paths.TOOL` for locations.
