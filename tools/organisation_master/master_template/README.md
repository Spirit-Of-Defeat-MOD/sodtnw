# Making a new master

Everything a master shares with the others (the theme and Theme menu, sounds, the themed menu bar, File menu,
**◂ Organisation Master**, a status line, activity for To Do Master and the achievements, rr:// links between masters,
running from a copy so a git pull can replace the exe, the update check) comes from
`tools/organisation_master/Scripts/master_base.py`. A new master only writes its own window.

1. **Copy this folder** to `tools/<your_master>` (e.g. `tools/focus_master`). It must sit next to `organisation_master`.
2. **Rename** `template_master.py` to `<your_master>.py`, and in it: the class name, `NAME = "Focus Master"`, the name
   in `run_copy.start("FocusMaster")` (the exe's name without .exe).
3. **master.json**: its `name` (the same as `NAME`), `exe` (`FocusMaster.exe`), `script` (`focus_master.py`), a one-line
   `description`, and for rr:// links `link` (`focus` -> `rr://focus/<kind>/<value>`) with its `link_kinds`.
   That's all it takes to be in Organisation Master's Masters menu and side bar, the activity inbox and the update
   check: nothing to add anywhere else.
4. **build.bat**: change `--name TemplateMaster` and `template_master.py` (and add `--icon` / `--add-data` for an .ico if
   it has one). Keep the `--paths` and `--exclude-module` lines.
5. Fill in `build()` (the window), `build_menu()` (its menus), `reload()` and `open_target()` as needed. Call
   `self.saved([files], "text")` after writing to the mod and `self.set_status(...)` for messages.
6. Run it as a .py (`python focus_master.py`) while working on it; build the exe with `build.bat` when it's ready.
   Add a release note in `tools/organisation_master/Scripts/release_notes.py`.

Find files of Organisation Master's (themes, sounds, art) with `import paths` / `paths.TOOL`; code shared between masters
goes in `tools/organisation_master/Scripts/`.
