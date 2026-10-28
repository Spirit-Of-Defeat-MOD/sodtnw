"""To Do Master: the RR dev team's task list (part of Organisation Master).

Tasks live in tools/organisation_master/todo_tasks.json (in the RR repository, so every dev sees them). Each task has a
reference (RR-0001...) to use in discussions, commits and bug reports. A task belongs to one or more devs (shared), to
nobody (the General To Do: anyone can claim it), or Needs Planning first. Every save also writes the in-game list,
localisation/english/rr_todo_l_english.yml, shown by the To Do window (interface/rr_todo.gui,
common/scripted_guis/rr_todo_mechanics.txt) when you start playing a country.
"""
import collections
import copy
import datetime
import json
import os
import random
import re
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser, filedialog, font as tkfont

import dev_vc
import icons
import auto_flags
import ideas
import gfx_checks
import gfx_master
import music_master as mm
import todo_sync
import ui
import portrait_links
import portrait_preview
import state_review
import country_review
import achievements
import master_activity
import master_links
import developer_activity
import milestone_celebration

APP_NAME = "Organisation Master"
TOOL_DIR = None  # set by Organisation Master: where todo_tasks.json lives
TASKS_FILE = "todo_tasks.json"
# The in-game To Do list: the fixed lines (title, tooltips, a placeholder) are in localisation/english/rr_todo_l_english.yml
# (in git, never rewritten); the live list goes in replace/ (git-ignored: every dev's own, so nothing to pull over).
LOC_REL = "localisation/english/replace/rr_todo_live_l_english.yml"

TODO = "To do"
FLESHING = "Needs Fleshing"  # (the task waits on an idea in Ideas mode being thought through)
STATUSES = (TODO, FLESHING, "Started", "Partially Complete", "Final touches", "Ready for Review", "Completed", "Not Possible",
			"Passed to Another Dev")
CLOSED = ("Completed", "Not Possible")  # these go to the archive
PRIORITIES = ("Low", "Normal", "High", "Critical")
CATEGORIES = ["Bug", "Mechanic", "Content", "Focus tree", "Events", "Map", "Art", "Music", "Localisation", "Balance", "Tools"]
AI_DEVS = ("Chat Jipity", "Claude")
GREEN_DAYS, YELLOW_DAYS = 14, 91  # the timer: up to 2 weeks green, up to 3 months yellow, then red
AGE_COLOURS = {"green": "#2e7d32", "yellow": "#b58900", "red": "#c62828"}
AGE_DOTS = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
# text colour per layer of the list: task, sub-task, sub-sub-task... (projects and groupings have their own)
LAYER_COLOURS = ("#1c3d6e", "#17695c", "#7a4a1d", "#5b5b5b")
PRIORITY_WEIGHT = {"Low": 1, "Normal": 2, "High": 4, "Critical": 8}
TEMPLATES = {  # (indented lines: sub-tasks of the line above)
	"New country": ["History file (start date, owned states)", "Leaders and portraits", "Ideas / national spirits", "Focus tree",
					"Events", "Decisions", "Localisation", "OOB (army, navy, air)", "Flags", "Cosmetic names and colours", "Test in game"],
	"Focus tree": ["Plan the branches", "Write the focuses", "Focus icons", "Localisation", "Balance the rewards", "AI weights", "Test in game"],
	"Mechanic": ["Design notes", "Scripted effects and triggers", "GUI", "Localisation", "AI", "Cheat sheet / docs", "Test in game"],
	"Radio station": ["Research Music", "Upload Tracks", "Create Radio Icon", "Station name and faceplate", "Test in game"],
}
# default icons (tools/organisation_master/icons): a task's comes from its category unless it has its own
CATEGORY_ICONS = {"Bug": "bug", "Mechanic": "gear", "Content": "document", "Focus tree": "branches", "Events": "bell", "Map": "map",
				  "Art": "paintbrush", "Music": "music", "Localisation": "speech", "Balance": "scales", "Tools": "tools", "Formables": "flag"}
PROJECT_ICON, GROUP_ICON, TASK_ICON = "flag", "bookmark_book", "clipboard"
PROJECT_COLOURS = ("#1f5fa8", "#b0361f", "#2e7d32", "#7b3fa0", "#b06f00", "#00838f", "#8d2a5c", "#5d4037", "#37474f", "#c2185b")
PLANNING_COLOUR = "#6a3fa0"
ALL = "(all)"
GENERAL, PLANNING = "General To Do", "Needs Planning"
# the list's views (tabs): key, label
MUSIC_TODO = "Music Mod To Do"
VIEWS = (("open", "All open"), ("next", "⭐ My next task"), ("mine", "My tasks"), ("general", GENERAL), ("music", MUSIC_TODO), ("planning", PLANNING), ("archive", "Archive"))
FIELD_NAMES = {"needs_ai": "requires AI", "devs": "devs", "needs_planning": "needs planning", "depends_on": "blocked by", "parent": "sub-task of", "group": "grouping", "review_reasons": "review reasons", "review_snapshot": "state composition", "review_states": "review states", "review_map": "regional map", "review_approvals": "state approvals"}
NO_PROJECT = "No Project"
# Music Master keeps this project in step with its planned stations: music mod > station > the three steps
MUSIC_PROJECT = "RR Music Mods"
LOC = "Location"  # (the 📍 Has location descriptor)
ART = "Needs Icon/Art"  # (the 🎨 descriptor: an Icon / Art area for the pictures instead of a text field)
ART_PROJECT = "Art Reviews"  # (portraits marked for rework in Country Master go here)
ART_GROUP = "Country Master checks"
ART_REVIEWS = (("generic", "Generic Review"), ("portrait", "Portrait Review"))
ART_PRIORITY = {"Needs Severe Recorrection": "High"}
PORTRAIT_LINK = "portrait_review:"
MUSIC_STEPS = (("research", "Research Music"), ("upload", "Upload Tracks"), ("icon", "Create Radio Icon"))
NO_MUSIC_MOD = "Music mod not decided yet"


def now():
	return datetime.datetime.now().replace(microsecond=0)


def stamp(d=None):
	return (d or now()).isoformat(timespec="seconds")


def parse_time(s):
	try:
		return datetime.datetime.fromisoformat(s)
	except (TypeError, ValueError):
		return now()


ARCHIVE_REASONS = ("Completed", "Impossible", "Deprecated", "Cancelled", "Duplicate", "Other")


def is_closed(t):
	"""Done with: Completed / Not Possible, or archived (with a reason)."""
	return t.get("status") in CLOSED or bool(t.get("archived"))


def done_on(t):
	"""When a task was done (Completed, or archived as Completed): its "closed" time, else when it was set Completed."""
	if t.get("status") != "Completed" and t.get("archived") != "Completed":
		return None
	if t.get("closed"):
		return parse_time(t["closed"])
	h = next((h for h in reversed(t.get("history", [])) if h.get("field") in ("status", "archived") and h.get("new") == "Completed"), None)
	return parse_time(h["when"]) if h else None


def month_name(key):
	return datetime.date(int(key[:4]), int(key[5:7]), 1).strftime("%B %Y")


def age_of(t):
	"""How long the task has been there (to now, or to when it was closed / archived)."""
	end = parse_time(t["closed"]) if is_closed(t) and t.get("closed") else now()
	return end - parse_time(t.get("created"))


def age_band(delta):
	days = delta.total_seconds() / 86400
	return "green" if days <= GREEN_DAYS else "yellow" if days <= YELLOW_DAYS else "red"


def fmt_age(delta):
	s = int(delta.total_seconds())
	d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
	if d >= GREEN_DAYS:
		return f"{d}d"
	if d:
		return f"{d}d {h}h"
	return f"{h}h {m:02d}m" if h else f"{m}m"


def ago(s):
	return fmt_age(now() - parse_time(s)) + " ago" if s else ""


def short_date(s):
	return parse_time(s).strftime("%Y-%m-%d %H:%M") if s else ""


def loc_text(s):
	"""Text that is safe inside a HOI4 localisation string."""
	s = re.sub(r"\s*\n\s*", " / ", (s or "").strip())
	return s.replace('"', "''").replace("§", "").replace("$", "S").replace("[", "(").replace("]", ")").replace("\\", "/")


def devs_of(t):
	return list(t.get("devs") or [])


def monthly_leaders(tasks, dev_names, month):
	"""Credit each assigned dev once per completed task, matching the monthly archive report."""
	counts = dict.fromkeys(dev_names, 0)
	for task in tasks:
		completed = done_on(task)
		if completed and completed.strftime("%Y-%m") == month:
			for dev in set(devs_of(task)) & counts.keys():
				counts[dev] += 1
	most = max(counts.values(), default=0)
	return {dev for dev, count in counts.items() if count == most and most > 0}


def portrait_sprite(task):
	link = str(task.get("link") or "")
	for prefix in (PORTRAIT_LINK, "art_mark:"):
		if link.startswith(prefix):
			return link[len(prefix):]
	return None


VC_DATA = {"vcs", "vc_future_agenda", "vc_next_agenda"}
GFX_DATA = {"gfx"}
IDEA_DATA = {"ideas", "idea_categories", "idea_headings", "idea_header_details", "idea_cat_colours", "deleted_ideas"}


def keep_unchanged(old, new):
	"""The merged data with every part that didn't change still the same object as on screen (whole sections, and single
	tasks / projects / ideas / VCs): open editors keep pointing at live data, and only what changed is drawn again."""
	out = {}
	for k, v in new.items():
		was = old.get(k)
		if was == v:
			out[k] = was
		elif isinstance(v, list) and isinstance(was, list):
			key = next((i for i in ("ref", "id", "name") if v and all(isinstance(x, dict) and i in x for x in v + was)), None)
			olds = {x[key]: x for x in was} if key else {}
			out[k] = [olds[x[key]] if key and olds.get(x[key]) == x else x for x in v]
		else:
			out[k] = v
	return out


def repair_legacy_portraits(data):
	"""Older clients inferred completion from their own incomplete marks file; never accept that inference."""
	changed = False
	for task in data.get("tasks", []):
		sprite = portrait_sprite(task)
		if not sprite:
			continue
		if task["link"] != PORTRAIT_LINK + sprite:
			old = task["link"]
			task["link"] = PORTRAIT_LINK + sprite
			task["updated"] = stamp()
			task.setdefault("history", []).append(dict(when=task["updated"], who="Organisation Master", field="link", old=old,
				new=task["link"], note="Migrated portrait connection so older clients cannot infer completion from local mark files."))
			changed = True
		if task.get("status") != "Completed" or task.get("portrait_completion_confirmed"):
			continue
		last = next((h for h in reversed(task.get("history", [])) if h.get("field") == "status"), {})
		if last.get("new") == "Completed" and last.get("note") == "no longer marked for rework in Country Master":
			task["status"] = TODO
			task.pop("closed", None)
			task["updated"] = stamp()
			task.setdefault("history", []).append(dict(when=task["updated"], who="Organisation Master", field="status", old="Completed",
				new=TODO, note="Restored: legacy client inferred completion from an absent local portrait mark; explicit confirmation is required."))
			changed = True
	return changed


def is_music(t):
	return t.get("project") == "RR Music Mods" or str(t.get("link", "")).startswith("music_")


def lane(t):
	"""Where a task sits: archive, planning (Needs Planning), general / music (nobody's yet: claim it) or dev."""
	if is_closed(t):
		return "archive"
	if t.get("needs_planning"):
		return "planning"
	if devs_of(t):
		return "dev"
	return "music" if is_music(t) else "general"


REVIEW_LINKS = ("art_review:", "portrait_review:")  # (only art: one task covers many pictures; state / idea / country reviews are claimed as usual)


def shared_review(t):
	"""An art review: anyone can claim it, and it stays in the General To Do for everyone."""
	return not is_closed(t) and str(t.get("link") or "").startswith(REVIEW_LINKS)


def in_general(t):
	return lane(t) == "general" or (lane(t) == "dev" and shared_review(t))


REWORK_LINK = "art_review:rework"


def rework_group(mark):
	"""Which 🔁 Rework task a marked picture counts in: generic / leader portraits apart, otherwise its GFX section."""
	if mark.get("section", "portrait") == "portrait":
		return "generics" if mark.get("portrait_kind") == "generic" else "portraits"
	return mark.get("section") or "pictures"


def rework_group_name(group):
	"""generics -> Generics, flag -> Flags (the GFX section's name without its icon), anything new -> its own name."""
	if group in ("generics", "portraits", "pictures"):
		return group.capitalize()
	name = gfx_master.SECTION_NAME.get(group, group.replace("_", " ").title())
	return name.split(" ", 1)[1] if " " in name and not name[0].isalnum() else name


def show_value(v):
	if isinstance(v, dict) and v and all(isinstance(row, dict) and "approved" in row for row in v.values()):
		return f"{sum(bool(row['approved']) for row in v.values())} states approved"
	if isinstance(v, dict) and v.get("kind") == "state-map":
		return f"Map snapshot: {len(v.get('ids', []))} states"
	if isinstance(v, dict) and {"id", "cultures", "religions"} <= v.keys():
		return f"State {v['id']}: {len(v['cultures'])} cultures, {len(v['religions'])} religions"
	if isinstance(v, list):
		if v and all(isinstance(row, dict) and "id" in row for row in v):
			return "; ".join(f"{row['id']}: {row.get('name', 'State')}" for row in v)
		return ", ".join(str(item) for item in v) or "-"
	if isinstance(v, bool):
		return "yes" if v else "no"
	return v if v not in (None, "") else "-"


class TodoMaster(ttk.Frame):
	def __init__(self, parent, app):
		super().__init__(parent, padding=8)
		self.app = app
		self.data = {}
		self.sync = todo_sync.Sync(self, TOOL_DIR)  # (live: the To Do's own git repository, see todo_sync.py)
		self._applying = False
		self.load()
		self.cur = None  # the task in the details
		self._note_job = None
		self._undo = []  # (state before, state after) of your recent changes (Undo; survives live sync, see undo)
		self._undo_buttons = []
		self.last_open = self.app.config.get("todo_last_open")  # (tasks unblocked since then are highlighted)
		self._dev_sel = ()  # the dev list row last acted on
		self.sort = ("age", True)

		self._build_toolbar()

		# ---- the views (tabs) ----
		vf = self.views_row = ttk.Frame(self)
		vf.pack(fill="x", pady=(10, 4))
		self.view = tk.StringVar(value=self.app.config.get("todo_view", "open"))
		self.view_buttons = {}
		for key, text in VIEWS:
			b = ttk.Radiobutton(vf, text=text, variable=self.view, value=key, command=self.view_changed, style="View.TRadiobutton")
			b.sound_kind = "open"
			b.pack(side="left", padx=(0, 4))
			self.view_buttons[key] = b
		self.export_info = ttk.Label(vf, text="", style="Muted.TLabel")
		self.export_info.pack(side="right")

		# ---- filters ----
		sec = ui.Section(self, "Filters", "todo_filters", app, expand=False).place_in(fill="x", pady=(2, 6))
		ui.tool_button(sec.tools, "Clear filters", self.clear_filters).pack(side="left", padx=2)
		self.sec_filters = sec
		fr = sec.body
		self.f = {}
		for i, (key, text, width) in enumerate((("dev", "Dev", 16), ("category", "Category", 14), ("status", "Status", 20),
												("priority", "Priority", 10), ("age", "Age", 22), ("tag", "Country tag", 9),
												("project", "Project", 16), ("milestone", "Milestone", 16))):
			ttk.Label(fr, text=text, style="Muted.TLabel").grid(row=0, column=i, sticky="w", padx=(0, 10))
			v = self.f[key] = tk.StringVar(value=ALL)
			cb = ttk.Combobox(fr, textvariable=v, width=width, state="readonly", font="TkDefaultFont")
			cb.grid(row=1, column=i, sticky="w", padx=(0, 10))
			cb.bind("<<ComboboxSelected>>", lambda ev: self.fill())
			setattr(self, f"fbox_{key}", cb)
		self.show_ref = tk.BooleanVar(value=bool(self.app.config.get("todo_show_ref", False)))
		ttk.Checkbutton(fr, text="Show reference number", variable=self.show_ref,
						command=lambda: (self.app.config.update(todo_show_ref=self.show_ref.get()), self.app.save_config(), self.fill())).grid(
			row=1, column=8, sticky="w", padx=(6, 0))

		# ---- Monthly Report (Archive view) ----
		sec = self.report_sec = ui.Section(self, "📅 Monthly Report", "todo_report", app, expand=False)
		ui.tool_button(sec.tools, "📋 Copy report", self.copy_report).pack(side="left", padx=2)
		rb = sec.body
		row = ttk.Frame(rb)
		row.pack(fill="x")
		for text, d in (("◀", 1), ("▶", -1)):  # (older / newer: small arrows, not theme-sized buttons)
			a = ttk.Label(row, text=text, style="Head.TLabel", cursor="hand2")
			a.bind("<Button-1>", lambda ev, d=d: self.step_month(d))
			setattr(self, "report_older" if d == 1 else "report_newer", a)
		self.report_older.pack(side="left")
		self.report_month = tk.StringVar()
		self.report_box = ttk.Combobox(row, textvariable=self.report_month, state="readonly", width=16, font="TkDefaultFont")
		self.report_box.pack(side="left", padx=4)
		self.report_box.bind("<<ComboboxSelected>>", lambda ev: self.fill_report())
		self.report_newer.pack(side="left")
		self.report_sum = ttk.Label(row, text="", style="Head.TLabel")
		self.report_sum.pack(side="left", padx=12)
		cols = ttk.Frame(rb)
		cols.pack(fill="x", pady=(6, 4))
		self.report_cols = {}
		for key, title in (("dev", "By dev"), ("project", "By project"), ("category", "By category"), ("gfx", "🖼 GFX made")):
			f = ttk.Frame(cols)
			f.pack(side="left", anchor="n", padx=(0, 28))
			ttk.Label(f, text=title, style="Muted.TLabel").pack(anchor="w")
			self.report_cols[key] = ttk.Label(f, text="", font="om_mono", justify="left")
			self.report_cols[key].pack(anchor="w")
		self.report_text = tk.Text(rb, height=9, wrap="word", font="om_small", relief="flat", cursor="arrow")
		self.report_text.pack(fill="x")
		self.report_text.tag_configure("head", font="om_bold")
		self.report_text.tag_configure("task", lmargin1=ui.px(14), lmargin2=ui.px(28))
		self.report_text.tag_bind("task", "<Double-1>", self.report_go)
		ttk.Label(rb, text="Everything completed that month (double-click one to see it).", style="Muted.TLabel").pack(anchor="w")
		self._report_refs = {}

		pw = self.panes = self.main_pw = ttk.PanedWindow(self, orient="horizontal")
		pw.pack(fill="both", expand=True)

		# ---- left: dev list ----
		# (panes and tables don't ask for their full width: the sash decides, drag it to resize)
		left = ttk.Frame(pw, padding=(0, 0, 8, 0), width=ui.px(380))
		left.pack_propagate(False)
		self.dev_side = ttk.Frame(left)
		self.proj_side = ttk.Frame(left)
		pw.add(left, weight=1)
		sec = ui.Section(self.dev_side, "Dev list", "todo_devs", app, expand=False).place_in(fill="x")  # (no stretching)
		ui.tool_button(sec.tools, "+ Dev", self.add_dev).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "Show all", self.show_all).pack(side="left", padx=2)
		self.collapse_btn = ui.tool_button(sec.tools, "Collapse All", self.collapse_all)
		self.collapse_btn.sound_kind = "close"
		self.collapse_btn.pack(side="left", padx=2)
		dbox = ttk.Frame(sec.body, width=ui.px(300), height=ui.px(300))
		dbox.pack_propagate(False)
		dbox.pack(fill="x")
		d = self.dev_tree = ttk.Treeview(dbox, columns=("active", "blocked", "done"), height=12, selectmode="browse")
		for col, text, w in (("#0", "Dev", 130), ("active", "Active", 52), ("blocked", "Blocked", 60), ("done", "Done", 48)):
			d.heading(col, text=text)
			d.column(col, width=ui.px(w), anchor="w" if col == "#0" else "e", stretch=col == "#0", minwidth=ui.px(120 if col == "#0" else 40))
		d.heading("#0", command=self.trophy_secret)
		d.pack(fill="both", expand=True)
		d.tag_configure("me", font="om_bold")
		d.tag_configure("lane", foreground="#1f5fa8", font="om_bold")
		d.tag_configure("planning", foreground=PLANNING_COLOUR, font="om_bold")
		d.tag_configure("asking", background="#ffd54f", foreground="#3a2a00", font="om_bold")  # (🙋 asked for a task: leads see it)
		d.bind("<<TreeviewSelect>>", self.dev_picked)
		d.bind("<Button-3>", self.dev_menu)
		d.bind("<Double-1>", lambda ev: self.rename_dev(self.dev_at(ev)))
		self.ask_btn = ttk.Button(sec.body, text="🙋 Ask for a task", command=self.ask_for_task)
		self.ask_btn.pack(fill="x", pady=(6, 0))
		ttk.Label(sec.body, text="Click a dev to see their tasks; right-click to rename.\n🏆 Most completed this month (ties share the trophy).\n"
								 "🙋 Ask for a task: you light up for the leads until you're given a task.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
		sec = ui.Section(self.dev_side, "Last worked on", "todo_last", app, expand=False).place_in(fill="x", pady=(8, 0))
		self.last_worked = ttk.Label(sec.body, text="", wraplength=ui.px(320), justify="left")
		self.last_worked.pack(anchor="w", fill="x")
		# Projects (Project mode)
		sec = self.project_section = ui.Section(self.proj_side, "Projects", "todo_projects", app, expand=False).place_in(fill="x")  # (no stretching)
		ui.tool_button(sec.tools, "+ Project", self.add_project).pack(side="left", padx=2)
		pbox = ttk.Frame(sec.body, width=ui.px(300), height=ui.px(300))
		pbox.pack_propagate(False)
		pbox.pack(fill="x")
		pt = self.proj_tree = ttk.Treeview(pbox, columns=("lead", "open", "done"), selectmode="browse")
		for col, text, w in (("#0", "Project", 130), ("lead", "Lead", 100), ("open", "Open", 50), ("done", "Done", 50)):
			pt.heading(col, text=text)
			pt.column(col, width=ui.px(w), anchor="w" if col in ("#0", "lead") else "e", stretch=col == "#0", minwidth=ui.px(40))
		pt.pack(fill="both", expand=True)
		pt.tag_configure("none", foreground="#777")
		pt.bind("<<TreeviewSelect>>", self.project_picked)
		self._proj_drag = None
		pt.bind("<ButtonPress-1>", self.project_drag_press, add="+")
		pt.bind("<B1-Motion>", self.project_drag_motion, add="+")
		pt.bind("<ButtonRelease-1>", self.project_drag_release, add="+")
		pt.bind("<Escape>", self.project_drag_cancel, add="+")
		pt.bind("<Button-3>", self.project_menu)
		pt.bind("<Double-1>", lambda ev: self.edit_project(self.project_at(ev)))
		ttk.Label(sec.body, text="Click a project to see its tasks; drag to reorder. Right-click: lead, rename, new task in it.",
				  style="Muted.TLabel", wraplength=ui.px(340), justify="left").pack(anchor="w", pady=(4, 0))
		self._proj_sel = ()
		# Milestones (a release / development target, and what still blocks it)
		sec = self.ms_section = ui.Section(left, "Milestones", "todo_milestones", app, expand=False).place_in(fill="x", pady=(8, 0))
		ui.tool_button(sec.tools, "+ Milestone", lambda: self.edit_milestone(None)).pack(side="left", padx=2)
		self.show_hidden_ms = tk.BooleanVar(value=False)
		self.hidden_btn = ttk.Checkbutton(sec.tools, text="Show hidden", variable=self.show_hidden_ms, command=lambda: self.fill())
		self.hidden_btn.pack(side="left", padx=6)
		mt = self.ms_tree = ttk.Treeview(sec.body, columns=("target", "done", "open", "blocked"), height=5, selectmode="browse")
		for col, text, w in (("#0", "Milestone", 120), ("target", "Target", 85), ("done", "Done", 45), ("open", "Open", 45), ("blocked", "Blocked", 55)):
			mt.heading(col, text=text)
			mt.column(col, width=ui.px(w), anchor="w" if col in ("#0", "target") else "e", stretch=col == "#0")
		mt.pack(fill="x")
		mt.tag_configure("late", foreground="#c62828")
		mt.tag_configure("hl", background="#ece3fb", font="om_bold")
		mt.tag_configure("hidden", foreground="#999")
		mt.bind("<<TreeviewSelect>>", self.milestone_picked)
		mt.bind("<Double-1>", lambda ev: mt.identify_row(ev.y) and self.edit_milestone(mt.identify_row(ev.y)[3:]))
		mt.bind("<Button-3>", self.milestone_menu)
		self._ms_sel = ()
		self.activity = developer_activity.Activity(left, self)
		lg = self.legend_frame = ttk.Frame(left)
		lg.pack(anchor="w", pady=(10, 0))
		ttk.Label(lg, text="Age:", style="Muted.TLabel").pack(side="left")
		for band, text in (("green", "up to 2 weeks"), ("yellow", "up to 3 months"), ("red", "older")):
			tk.Label(lg, text=f"{AGE_DOTS[band]} {text}", fg=AGE_COLOURS[band], font="om_small_bold").pack(side="left", padx=4)

		# ---- right: the tasks, then the picked task ----
		right = ttk.Frame(pw, padding=(8, 0, 0, 0))
		pw.add(right, weight=4)
		sec = self.sec_tasks = ui.Section(right, "Tasks", "todo_tasks", app).place_in(fill="both")
		for header in (sec.head, sec.arrow, sec.title, sec.count, sec.tools):
			header.bind("<Button-3>", self.task_bar_menu)
		ui.tool_button(sec.tools, "+ New task", lambda: self.edit_task(new=True)).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "Show all", self.show_all).pack(side="left", padx=2)
		self.order_btns = [ui.tool_button(sec.tools, "↓ Later", lambda: self.move_mine(1)), ui.tool_button(sec.tools, "↑ Earlier", lambda: self.move_mine(-1))]
		self.winfo_toplevel().bind("<Alt-Up>", lambda ev: self.view.get() == "next" and self.move_mine(-1), add="+")
		self.winfo_toplevel().bind("<Alt-Down>", lambda ev: self.view.get() == "next" and self.move_mine(1), add="+")
		tf = ttk.Frame(sec.body, width=ui.px(600), height=ui.px(250))
		tf.pack_propagate(False)
		tf.pack(fill="both", expand=True)
		cols = (("ref", "Ref", 75, False), ("title", "Task", 300, True), ("project", "Project", 110, False), ("devs", "Dev(s)", 150, False), ("category", "Category", 100, False),
				("status", "Status", 165, False), ("priority", "Priority", 75, False), ("age", "Age", 75, False),
				("sweep", "Sweep", 60, False), ("tags", "Tags", 75, False), ("flags", "Flags", 170, False))
		t = self.tree = ttk.Treeview(tf, columns=[c[0] for c in cols], show="headings", selectmode="extended")
		self.cols = [c[0] for c in cols]
		self.col_titles = {c[0]: c[1] for c in cols}
		self.col_titles["#0"] = "Task  (project › task › sub-task)"
		t.heading("#0", text=self.col_titles["#0"], command=lambda: self.sort_by("title"))
		t.column("#0", width=ui.px(380), minwidth=ui.px(150), stretch=False)
		t.tag_configure("project", font="om_bold", foreground="#1f2d3d", background="#e9eef5")
		t.tag_configure("group", font="om_bold", foreground="#5b4a8a")
		for key, text, w, stretch in cols:
			t.heading(key, text=text, command=lambda k=key: self.sort_by(k))
			t.column(key, width=ui.px(w), anchor="w", stretch=False, minwidth=ui.px(40))
		ys = ttk.Scrollbar(tf, command=t.yview)
		xs = ttk.Scrollbar(tf, orient="horizontal", command=t.xview)
		t.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
		xs.pack(side="bottom", fill="x")
		self.no_group_drop = tk.Canvas(t, height=ui.px(28), highlightthickness=0, borderwidth=0, takefocus=False)
		t._drag_drop_overlay = self.no_group_drop
		self.no_group_drop.bind("<ButtonRelease-1>", self.dnd_release)
		t.bind("<Configure>", lambda _event: self.show_no_group() if self._dnd and self._dnd.get("on") else None, add="+")
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		# (the first configured tag wins: row highlights before colours before the stripes)
		t.tag_configure("blocked", background="#fbe3e3")
		t.tag_configure("mshl", background="#ece3fb")  # (a highlighted milestone's tasks: over ready / unblocked, under blocked)
		t.tag_configure("unblocked", background="#fff1c2")
		t.tag_configure("ready", background="#e4f4dc")
		t.tag_configure("closed", foreground="#888")
		for i, c in enumerate(LAYER_COLOURS):
			t.tag_configure(f"L{i}", foreground=c)
		t.tag_configure("critical", font="om_bold")
		t.bind("<<TreeviewSelect>>", lambda ev: self.show_task())
		t.bind("<<TreeviewOpen>>", self.task_branch_opened, add="+")
		t.bind("<<TreeviewClose>>", lambda ev: self.task_branch_opened(ev, closing=True), add="+")
		t.bind("<ButtonRelease-1>", self.task_clicked, add="+")
		t.bind("<ButtonRelease-1>", self.cell_click, add="+")
		# (no column stretches, so widening one by its title's edge sticks; your widths are kept just for you)
		for col, w in (self.app.config.get("todo_col_widths") or {}).items():
			try:
				t.column(col, width=int(w))
			except (tk.TclError, ValueError):
				pass
		t.bind("<ButtonPress-1>", lambda ev: setattr(self, "_drag_col", t.identify_region(ev.x, ev.y) == "separator"), add="+")
		t.bind("<ButtonRelease-1>", self.keep_widths, add="+")
		# drag and drop: a task onto a task (its sub-task), a grouping (into it) or a project (its top-level task)
		t.tag_configure("droptarget", background="#cfe3fb")
		self._dnd = None
		t.bind("<ButtonPress-1>", self.dnd_press, add="+")
		t.bind("<B1-Motion>", self.dnd_motion, add="+")
		t.bind("<ButtonRelease-1>", self.dnd_release, add="+")
		t.bind("<Escape>", self.dnd_cancel, add="+")
		t.bind("<Unmap>", self.dnd_cancel, add="+")
		t.bind("<FocusOut>", self.dnd_cancel, add="+")
		t.bind("<Double-1>", lambda ev: t.identify_row(ev.y) and self.edit_task())
		t.bind("<Button-3>", self.task_menu)
		ttk.Label(sec.body, text="Right-click a task: status, claim, share, priority, category, sweep, blocked, dependencies... "
								 "Click a column title to sort.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

		sec = ui.Section(right, "Selected task", "todo_detail", app, expand=False).place_in(fill="x", pady=(8, 0))
		det = sec.body
		self.d_title = tk.Label(det, text="Pick a task", font="om_title", anchor="w")
		self.d_title.pack(fill="x")
		self.d_info = ttk.Label(det, text="", justify="left")  # (milestones)
		self.d_grid = ttk.Frame(det)  # (tasks and projects: label / value pairs)
		self.d_grid.pack(anchor="w", fill="x", pady=(4, 0))
		self._dwidth = ui.px(800)

		def resized(ev):
			self._dwidth = max(ui.px(300), ev.width - 10)
			self.d_info.config(wraplength=self._dwidth)
		det.bind("<Configure>", resized)
		self.d_block = tk.Label(det, text="", fg="#c62828", anchor="w", justify="left", font="om_bold")
		db = self.d_buttons = ttk.Frame(det)
		db.pack(anchor="w", pady=6)
		ttk.Button(db, text="Edit...", command=self.edit_selected).pack(side="left")
		self.status_btn = ttk.Menubutton(db, text="Status")
		self.claim_btn = ttk.Button(db, text="✋ Claim", command=lambda: self.claim(self.picked() or [self.cur]))
		self.share_btn = ttk.Button(db, text="Share with...", command=lambda: self.share(self.picked() or [self.cur]))
		self.copy_btn = ttk.Button(db, text="Copy reference", command=lambda: self.copy_ref(False))
		self.commit_btn = ttk.Button(db, text="Copy for a commit", command=lambda: self.copy_ref(True))
		self.task_btns = (self.status_btn, self.claim_btn, self.share_btn)
		self.show_buttons(True)
		self.fields_frame = ttk.Frame(det)  # (Descriptors: the task's fields - its project's, its grouping's, its own)
		self._field_vars = {}
		self._field_task = None
		gd = self.group_desc_frame = ttk.Frame(det)
		ttk.Label(gd, text="Description of the grouping (everyone sees it)", style="Muted.TLabel").pack(anchor="w")
		self.group_desc = tk.Text(gd, height=5, wrap="word", font="om_body", relief="solid", borderwidth=1)
		self.group_desc.pack(fill="x")
		self.group_desc.bind("<KeyRelease>", lambda ev: self.note_changed())
		self.cur_group = None  # (holder key, grouping) shown in the panel
		nf = self.notes_frame = ttk.Frame(det)
		nf.pack(fill="both", expand=True)
		self.n_set_label = ttk.Label(nf, text="Note from the setter (shown in game)", style="Muted.TLabel")
		self.n_set_label.grid(row=0, column=0, sticky="w")
		self.n_dev_label = ttk.Label(nf, text="Note from the dev", style="Muted.TLabel")
		self.n_dev_label.grid(row=0, column=1, sticky="w", padx=(10, 0))
		self.n_set = tk.Text(nf, height=5, width=40, wrap="word", font="om_body", relief="solid", borderwidth=1)
		self.n_set.grid(row=1, column=0, sticky="nsew")
		self.n_dev = tk.Text(nf, height=5, width=40, wrap="word", font="om_body", relief="solid", borderwidth=1)
		self.n_dev.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
		nf.columnconfigure(0, weight=1)
		nf.columnconfigure(1, weight=1)
		self.portrait_preview = portrait_preview.PortraitPreview(nf, app.mod_root)
		self.state_review_panel = state_review.StateReviewPanel(det, app.mod_root, app.navigate_master, self.approve_review_state, app,
			invalidate=self.invalidate_review_states)
		self.country_review_panel = country_review.CountryReviewPanel(det, app.mod_root, app.navigate_master, self.approve_country_review)
		self.n_set.bind("<KeyRelease>", lambda ev: self.note_changed())
		self.n_dev.bind("<KeyRelease>", lambda ev: self.note_changed())
		sec = ui.Section(right, "Links", "todo_links", app, expand=False).place_in(fill="x", pady=(8, 0))
		self.master_link_btn = ui.tool_button(sec.tools, "Open in master", self.open_in_master)
		self.master_link_btn.pack(side="left", padx=2)
		ui.tool_button(sec.tools, "+ File", lambda: self.cur and self.add_link(self.cur, "file")).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "+ Folder", lambda: self.cur and self.add_link(self.cur, "folder")).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "+ URL / commit", lambda: self.cur and self.add_link(self.cur, "ask")).pack(side="left", padx=2)
		lf = ttk.Frame(sec.body)
		lf.pack(fill="x")
		self.links = tk.Listbox(lf, height=3, font="om_body", activestyle="none")
		self.links.pack(side="left", fill="x", expand=True)
		self.links.bind("<Double-1>", lambda ev: self.open_link())
		lb_ = ttk.Frame(lf)
		lb_.pack(side="left", padx=(6, 0))
		ttk.Button(lb_, text="Open", style="Tool.TButton", command=self.open_link).pack(fill="x")
		ttk.Button(lb_, text="Open file", style="Tool.TButton", command=lambda: self.open_link(as_file=True)).pack(fill="x", pady=2)
		ttk.Button(lb_, text="Remove", style="Tool.TButton", command=self.remove_link).pack(fill="x", pady=2)
		ttk.Label(sec.body, text="Double-click recognised links to open their item in its master. Open file opens the original file. Web and commit links open in your browser.",
				  style="Muted.TLabel").pack(anchor="w")
		sec = ui.Section(right, "History", "todo_history", app, collapsed=True, expand=False).place_in(fill="x", pady=(8, 0))
		self.hist = tk.Text(sec.body, height=6, wrap="word", font="om_small", state="disabled", background="#f6f6f6", relief="flat")
		self.hist.pack(fill="x")

		self.vc_pane = dev_vc.DevVC(self, self)  # (🎙 Dev VCs mode)
		self.idea_pane = ideas.Ideas(self, self)  # (💡 Ideas mode)
		self.gfx_pane = gfx_master.GFX(self, self)  # (🖼 GFX mode: missing pictures)
		self.achievement_pane = None
		if not self.git_match()[1]:  # (a git name nobody in the Dev list has: which dev are you?)
			self.after(2500, self.confirm_me)
		ui.THEME_HOOKS.append(self.redraw_icons)  # (each theme has its own icon sheet)
		if self.tidy_trash():  # (🗑 copies older than TRASH_DAYS)
			self._saved = json.dumps(self.data, ensure_ascii=False)
		self.sync.start(self._saved)  # (as loaded: what this PC had)
		self.auto_flags = auto_flags.AutoFlags(self.app.mod_root)  # (🏳 flags from project / grouping / heading names)
		self.auto_flags.start()
		self.after(1500, self.wait_auto_flags)
		self.after(6000, self.remind_stale)  # (⏰ your own stale tasks, quietly)
		self.after(9000, self.run_data_check)  # (🩺 after the first sync: links to things that are gone)
		self.after(2500, self.export)  # (the in-game list is there as soon as the tool opens)
		self.sync_art(quiet=True)
		if self.reconcile_idea_reviews():
			self.save(undoable=False, feedback=False)
		self.fill_filters()
		self.show_side()
		self.fill()
		self.layout_mode()
		self.tick()
		self.after(1000, self.watch_master_activity)

	def _build_toolbar(self):
		"""Keep the mode selector anchored while the mode-specific controls fold away."""
		top = self.top_row = ttk.Frame(self)
		top.pack(fill="x", padx=(ui.px(12), 0))
		top.columnconfigure(3, weight=1)
		self.mode = tk.StringVar(value=self.app.config.get("todo_mode", "dev"))
		mf = self.mode_frame = tk.Frame(top, background=ui.HEAD_BG, padx=4, pady=2)
		mf.grid(row=0, column=2, sticky="nw", padx=(ui.px(16), 0), pady=(2, 0))
		self.mode_buttons = {}
		for index, (key, text) in enumerate((("dev", "👤 Dev mode"), ("project", "📁 Project mode"), ("gfx", "🖼 GFX"), ("idea", "💡 Ideas"), ("vc", "🎙 Dev VCs"))):
			b = self.mode_buttons[key] = ttk.Radiobutton(mf, text=text, variable=self.mode, value=key, command=self.mode_changed, style="View.TRadiobutton")
			if key in ("dev", "project"):
				b.sound_kind = "open"
			b.grid(row=0, column=index, sticky="w")
		identity = self.identity = ttk.Frame(top)
		identity.grid(row=0, column=0, sticky="w")
		ttk.Label(identity, text="You are").pack(side="left")
		self.me = tk.StringVar(value=self.guess_me())
		ttk.Label(identity, textvariable=self.me, style="Head.TLabel").pack(side="left", padx=(4, 12))
		self.who_btn = ttk.Button(identity, text="Who am I?...", command=self.confirm_me)
		if not self.git_match()[1]:
			self.who_btn.pack(side="left", padx=(0, 8))
		tt = self.task_tools = ttk.Frame(top)
		tt.grid(row=0, column=1, sticky="w", padx=(0, ui.px(4)))
		tt.columnconfigure((0, 1, 2), weight=1, uniform="todo_top_actions")
		for col, (text, command) in enumerate((("+ New task", lambda: self.edit_task(new=True)),
				("Devs...", self.edit_devs), ("Categories...", self.edit_categories))):
			ttk.Button(tt, text=text, command=command, width=18).grid(row=0, column=col, sticky="ew", padx=(0, ui.px(4)))

		# Reserve the task-button column even when it is hidden in Ideas / Dev VCs.
		tt.bind("<Configure>", lambda ev: self._reserve_task_toolbar_width())
		self.after_idle(self._reserve_task_toolbar_width)
		# Mode selector stays left of sync; search sits underneath to keep the buttons visible.
		utility = self.utility_row = ttk.Frame(top)
		utility.grid(row=0, column=4, sticky="e", padx=(ui.px(16), 0))
		self.reload_btn = ttk.Button(utility, text="Reload", command=self.reload)
		self.reload_btn.pack(side="right")
		self.sync_btn = ttk.Button(utility, text="🔄 Live Sync...", style="Tool.TButton", command=self.sync_setup)
		self.sync_btn.pack(side="right", padx=(0, 4))
		sb = self.search_box = ttk.Frame(top)
		sb.grid(row=1, column=4, sticky="e", padx=(ui.px(16), 0), pady=(ui.px(4), 0))
		self.sync_label = ttk.Label(utility, text="", style="Muted.TLabel", cursor="hand2")
		self.sync_label.pack(side="right", padx=(0, 8))
		self.sync_label.bind("<Button-1>", lambda ev: self.sync_setup())

		tools = self.tools_row = ttk.Frame(self)
		tools.pack(fill="x", pady=(6, 0), after=top)
		groups = ((("+ From template...", self.from_template), ("Templates...", self.edit_templates), ("Bulk add...", self.bulk_add)),
				  (("🎲 Random task", self.random_task), ("🩺 Health", self.health), ("↶ Undo", self.undo)),
				  (("🗑 Trash", self.open_trash), ("⏰ Stale tasks", self.open_nudges)))
		for group_index, actions in enumerate(groups):
			group = ttk.Frame(tools)
			group.pack(side="left", padx=(ui.px(20) if group_index else 0, 0))
			group.columnconfigure((0, 1, 2), weight=1, uniform="todo_secondary_actions")
			for col, (text, command) in enumerate(actions):
				b = ttk.Button(group, text=text, command=command, width=18)
				b.grid(row=0, column=col, sticky="ew", padx=(0, ui.px(4)))
				if command == self.undo:
					self.undo_btn = b
				elif command == self.open_nudges:
					self.nudge_btn = b
				elif command == self.health:
					self.health_btn = b
		self.register_undo_button(self.undo_btn)
		self.unblocked_btn = ttk.Button(tools, text="", command=self.show_unblocked)
		self._setup_undo_shortcut()
		self.search = tk.StringVar()
		ttk.Entry(sb, textvariable=self.search, width=28, font="TkDefaultFont").pack(side="right", padx=(4, 12))
		ttk.Label(sb, text="🔍 Search").pack(side="right")
		self.search.trace_add("write", lambda *_: self.fill())

	def _reserve_task_toolbar_width(self):
		width = self.task_tools.winfo_reqwidth() + ui.px(4)
		if int(self.top_row.columnconfigure(1, "minsize")) != width:
			self.top_row.columnconfigure(1, minsize=width)

	# ---------- data ----------
	def path(self):
		return self.sync.path() or os.path.join(TOOL_DIR, TASKS_FILE)  # (the live copy, once it's there)

	def load(self):
		try:
			self.data = json.load(open(self.path(), encoding="utf-8"))
		except (OSError, ValueError):
			self.data = {}
		self.data.setdefault("devs", [])
		self.data.setdefault("categories", list(CATEGORIES))
		self.data.setdefault("tasks", [])
		self.data.setdefault("next_ref", 1)
		if not self.data.get("leads_set"):  # (the first leads: Mike and Globus)
			for d in self.data.get("devs", []):
				if d["name"] in ("Mike", "Globus"):
					d["lead"] = True
			self.data["leads_set"] = True
		named = {}
		for d in self.data["devs"]:
			if d.get("git") and d["name"] != d["git"]:
				named[d["git"].lower()] = d["name"]
		used = {n for t in self.data["tasks"] for n in devs_of(t) + [t.get("set_by"), t.get("reviewer")]}
		self.data["devs"] = [d for d in self.data["devs"] if not (d["name"] == d.get("git") and d["name"].lower() in named
																	and d["name"] not in used and not d.get("lead"))]
		self.data.setdefault("projects", [])  # [{name, lead, set_by, created, note}]
		self.data.setdefault("milestones", [])  # [{name, target, note}]: a release / development target
		moved = False
		for t in self.data["tasks"]:  # (My next task numbers are each dev's own too)
			for dev, n in (t.pop("order", None) or {}).items():
				self.app.config.setdefault("todo_order", {}).setdefault(dev, {}).setdefault(t["ref"], n)
				moved = True
		for m in self.data["milestones"]:  # (hide / highlight are each dev's own: kept in the settings, not this file)
			for key in ("hidden", "highlight"):
				if m.pop(key, None):
					lst = self.app.config.setdefault(f"todo_ms_{key}", [])
					if m["name"] not in lst:
						lst.append(m["name"])
					moved = True
		if moved:
			self.app.save_config()
			with open(self.path(), "w", encoding="utf-8") as f:
				json.dump(self.data, f, indent=1, ensure_ascii=False)
		self.data.setdefault("templates", copy.deepcopy(TEMPLATES))  # {name: [lines]}
		self._saved = json.dumps(self.data, ensure_ascii=False)  # (what Undo goes back to)
		for t in self.data["tasks"]:  # older files: one "dev" per task
			if "dev" in t:
				d = t.pop("dev")
				t.setdefault("devs", [d] if d else [])
				for h in t.get("history", []):
					if h.get("field") == "dev":
						h["field"] = "devs"
		if not self.data["devs"]:
			# start with the people who committed to RR in the last year
			out = mm.git(self.app.mod_root, "shortlog", "-sn", "--since=1.year", "HEAD")
			names = [l.split("\t", 1)[1].strip() for l in out.splitlines() if "\t" in l]
			self.data["devs"] = [{"name": n, "git": n} for n in names] or [{"name": mm.git_user(), "git": mm.git_user()}]
		for name in AI_DEVS:
			if name not in self.dev_names():
				self.data["devs"].append({"name": name, "git": ""})

	def save(self, undoable=True, feedback=True):
		if self._note_job:  # a note typed a moment ago goes in too
			self.flush_notes(save=False)
		self.reconcile_idea_reviews()
		self.unflag_askers()  # (🙋 given a task: not asking any more)
		milestone_celebration.restore_status(self.data)
		previous = getattr(self, "_saved", None)
		if previous is not None and undoable and not self._applying:
			self.data.setdefault("master_activity", []).extend(
				developer_activity.changes(json.loads(previous), self.data, self.me.get()))
		developer_activity.compact(self.data)  # (the activity log was most of the file: saved and synced on every change)
		achievements.award(self.data)
		now_text = json.dumps(self.data, ensure_ascii=False)
		previous = getattr(self, "_saved", None)
		if undoable and now_text != getattr(self, "_saved", now_text):
			self._undo.append((self._saved, now_text))
			del self._undo[:-20]
		self._saved = now_text
		self._refresh_undo_buttons()
		with open(self.path(), "w", encoding="utf-8") as f:
			f.write(now_text)  # (compact, already made: indenting it froze the window ~0.3 s on every save; live sync commits it indented)
		self.app.log(TASKS_FILE)
		self.export()
		toasts = getattr(self.app, "achievement_toasts", None)
		if toasts:
			toasts.observe(self.data, self.me.get(), quiet=self._applying)
		celebrations = getattr(self.app, "milestone_celebrations", None)
		if celebrations:
			celebrations.observe(self.data, self.me.get())
		presence = getattr(self.app, "presence_toasts", None)
		if presence:
			presence.observe(self.data, self.me.get())  # (👋 another dev opened a tool)
		if hasattr(self, "activity"):
			self.activity.refresh()
		if not self._applying:
			self.sync.soon()  # (sent to the others a few seconds later)
		if feedback and undoable and not self._applying and previous is not None and previous != now_text:
			old = {t["ref"]: t for t in json.loads(previous).get("tasks", [])}
			completed = any(t.get("status") == "Completed" and old.get(t["ref"], {}).get("status") != "Completed" for t in self.tasks)
			me = self.me.get()
			claimed = bool(me) and any(t["ref"] in old and me in devs_of(t) and me not in devs_of(old[t["ref"]]) for t in self.tasks)
			current = {t["ref"]: t for t in self.tasks}
			left = bool(me) and any(ref in current and me in devs_of(t) and me not in devs_of(current[ref]) for ref, t in old.items())
			deleted = bool(old.keys() - current.keys())
			created = bool(current.keys() - old.keys())
			ai = any(t.get("needs_ai") and not old.get(t["ref"], {}).get("needs_ai") for t in self.tasks)
			kind = "womp" if left or deleted else "new_task" if created else "claim" if claimed else "complete" if completed else "ai" if ai else "success"
			getattr(self.app, "feedback", lambda *_: None)(kind)

	def apply_remote(self, data, remap, first):
		"""The others' changes merged in (live sync). Undo starts again from here (it would take theirs out too)."""
		ref = self.cur and self.cur["ref"]
		ref = remap.get(ref, ref)
		old = self.data
		data = keep_unchanged(old, data)
		changed = {k for k in set(old) | set(data) if old.get(k) is not data.get(k)}
		self.data = data
		portraits_repaired = repair_legacy_portraits(self.data)
		portraits_repaired |= self.fold_portrait_tasks()  # (an older build elsewhere brought back per-portrait review tasks)
		reviews_completed = self.reconcile_review_approvals()
		self._saved = json.dumps(self.data, ensure_ascii=False)  # (your Undo steps stay: undo takes back only your change)
		self._applying = True
		try:
			self.save(undoable=False)
		finally:
			self._applying = False
		self._refresh_undo_buttons()
		if portraits_repaired or reviews_completed:
			self.sync.soon()
		# Only what changed is drawn again (redrawing everything made the whole window flash on every sync).
		everything = first or remap or portraits_repaired or reviews_completed
		quiet = VC_DATA | IDEA_DATA | GFX_DATA | {"master_activity", "music_plans", "music_station_catalog", "sleigh_scores", "rr_game_scores", "rr_daily", "presence", milestone_celebration.EVENTS, milestone_celebration.SEEN}
		task_side = everything or bool(changed - quiet)
		if task_side:
			self.fill_filters()
			self.fill()
		if everything or changed & (VC_DATA | {"devs", "categories"}):
			self.vc_pane.refresh_remote()
		if everything or changed & (IDEA_DATA | {"projects", "tasks", "devs", "categories"}):
			self.idea_pane.fill()  # (keeps the idea picked: found again by its id)
		if (everything or changed & (GFX_DATA | {"tasks"})) and self.gfx_pane.winfo_manager():
			self.gfx_pane.redraw()
		shown = self.task(ref) if ref else None
		if task_side and (shown is not self.cur or changed - quiet - {"tasks", "next_ref"} or not shown):
			self.show_task(ref if shown else None)
		music = getattr(self.app, "existing_music_page", lambda: None)()
		if music is not None:
			music.receive_music_live()
		if remap:
			self.app.set_status("To Do: someone else used the same RR number - yours is now " +
								", ".join(f"{a} -> {b}" for a, b in remap.items() if a != b))
		elif not first:
			self.app.set_status("To Do: the others' latest changes are in.")

	def sync_setup(self):
		import sync_setup
		sync_setup.SyncSetup(self)

	def sync_status(self, text):
		if self.winfo_exists():
			self.sync_label.config(text=text)

	def reload(self):
		self.sync.soon(200)
		self.flush_notes()
		ref = self.cur and self.cur["ref"]
		self.load()
		self.fill_filters()
		self.fill()
		if ref and self.tree.exists(ref):
			self.tree.selection_set(ref)

	@property
	def tasks(self):
		return self.data["tasks"]

	def task(self, ref):
		return next((t for t in self.tasks if t["ref"] == ref), None)

	def dev_names(self):
		return [d["name"] for d in self.data["devs"]]

	def guess_me(self):
		"""You are: the dev with your git name (until then, just your git name: Who am I? puts you in the Dev list)."""
		g, match = self.git_match()
		return match or g

	def git_match(self):
		"""(git name, the dev it is or None): the dev with that git name; a dev without one yet by name (any case)."""
		g = mm.git_user()
		low = g.lower()
		return g, (next((d["name"] for d in self.data["devs"] if (d.get("git") or "").lower() == low), None)
				   or next((d["name"] for d in self.data["devs"] if not d.get("git") and d["name"].lower() == low), None))

	def confirm_me(self):
		"""First start-up: from your git name, which dev you are (it signs your tasks and changes)."""
		if not self.winfo_exists():
			return
		g, match = self.git_match()
		if match:
			messagebox.showinfo(APP_NAME, f"You are {match} (your git name).", parent=self)
			return
		w = tk.Toplevel(self)
		w.title("Who are you?")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=14)
		f.pack()
		ttk.Label(f, text="Which dev are you?", style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text=f"Your git name is {g}: nobody in the Dev list has it yet.\nYour name goes on the tasks you set and every "
						  "change you make, and it's tied to your git name from now on (a lead can change that).",
				  style="Muted.TLabel", justify="left").pack(anchor="w", pady=(2, 10))
		new = "+ Add me as a new dev"
		free = [d["name"] for d in self.data["devs"] if not d.get("git")]  # (devs nobody has claimed yet)
		v = tk.StringVar(value=match or new)
		row = ttk.Frame(f)
		row.pack(anchor="w")
		ttk.Label(row, text="I am").pack(side="left")
		ttk.Combobox(row, textvariable=v, values=free + [new], state="readonly", width=26, font="TkDefaultFont").pack(side="left", padx=6)
		nv = tk.StringVar(value=g)
		nrow = ttk.Frame(f)
		ttk.Label(nrow, text="Name").pack(side="left")
		ttk.Entry(nrow, textvariable=nv, width=24, font="TkDefaultFont").pack(side="left", padx=6)
		v.trace_add("write", lambda *_: nrow.pack(anchor="w", pady=(6, 0)) if v.get() == new else nrow.pack_forget())
		if v.get() == new:
			nrow.pack(anchor="w", pady=(6, 0))

		def ok():
			name = v.get()
			if name == new:
				name = nv.get().strip()
				if not name or name in self.dev_names():
					messagebox.showerror(APP_NAME, "Give a new name (not one in the Dev list).", parent=w)
					return
				self.data["devs"].append({"name": name, "git": g})
				self.save()
				self.fill_filters()
			else:
				d = next(d for d in self.data["devs"] if d["name"] == name)
				if not d.get("git"):
					d["git"] = g
					self.save()
			self.me.set(name)
			self.app.config["todo_me_confirmed"] = True
			self.remember_me()
			self.who_btn.pack_forget()
			w.destroy()
			self.app.set_status(f"You are {name}.")
		ttk.Button(f, text="That's me", command=ok).pack(anchor="e", pady=(12, 0))
		w.protocol("WM_DELETE_WINDOW", lambda: (self.app.config.update(todo_me_confirmed=True), self.app.save_config(), w.destroy()))

	def remember_me(self):
		self.app.config["todo_me"] = self.me.get()
		self.app.save_config()
		self.app.record_access("To Do Master")
		self.fill()

	def change(self, t, field, new, note=None, who=None):
		"""Sets a field and records who changed it (status, category, devs, priority, blocked, reviewer, ...)."""
		old = t.get(field)
		if old == new or (old in (None, "", []) and new in (None, "", [], False)):
			return False
		t[field] = new
		h = {"when": stamp(), "who": who or self.me.get(), "field": field, "old": old, "new": new}
		if note:
			h["note"] = note
		t.setdefault("history", []).append(h)
		t["updated"] = h["when"]
		if field == "status":
			if new in CLOSED:
				t["closed"] = h["when"]
			else:
				t.pop("closed", None)
			if (new == FLESHING) != (old == FLESHING) and hasattr(self, "idea_pane"):  # (its idea: made / reopened, or done)
				self.after_idle(lambda: self.idea_pane.task_fleshing(t, new == FLESHING))
		return True

	# ---------- the list ----------
	# ---------- Monthly Report (Archive) ----------
	def show_report(self):
		want = (self.view.get() == "archive" and self.mode.get() not in ("vc", "idea", "gfx", "achievements")
			and self.sec_filters.winfo_manager() == "pack")
		if want and not self.report_sec.winfo_manager():
			self.report_sec.place_in(fill="x", pady=(0, 6), after=self.sec_filters)
		elif not want and self.report_sec.winfo_manager():
			self.report_sec.pack_forget()
		if want:
			self.fill_report()

	def gfx_month_text(self, key):
		"""(🖼 how many missing / broken pictures were left at the start of the month and at its end, from the GFX scans)"""
		got = gfx_checks.month_change(self.data, key)
		if not got:
			return ""
		a, b = got
		return f"   ·   🖼 GFX left: {a} → {b}" + ((f" (✓ {a - b} fewer)" if b < a else f" ({b - a} new)") if a != b else "")

	def error_month_text(self, key):
		"""(🐞 the mod check's problems at the start of the month and at its end, from Error Log Master's trend)"""
		points = [p for p in self.data.get("error_trend", []) if p.get("source") == "check"]
		before = [p for p in points if p["when"][:7] < key]
		during = [p for p in points if p["when"][:7] == key]
		if not during:
			return ""
		a, b = (before[-1] if before else during[0])["total"], during[-1]["total"]
		return f"   ·   🐞 Errors: {a} → {b}" + ((f" (✓ {a - b} fewer)" if b < a else f" ({b - a} more)") if a != b else "")

	def report_months(self):
		keys = {d.strftime("%Y-%m") for d in map(done_on, self.tasks) if d} | {now().strftime("%Y-%m")}
		return sorted(keys, reverse=True)

	def step_month(self, d):
		names = list(self.report_box.cget("values"))
		if self.report_month.get() in names:
			i = min(max(names.index(self.report_month.get()) + d, 0), len(names) - 1)
			self.report_month.set(names[i])
			self.fill_report()

	def report_data(self):
		"""(month key, the tasks done in it, oldest first)."""
		keys = self.report_months()
		names = [month_name(k) for k in keys]
		self.report_box.config(values=names)
		if self.report_month.get() not in names:
			self.report_month.set(names[0])
		key = keys[names.index(self.report_month.get())]
		done = sorted((t for t in self.tasks if (done_on(t) or now()).strftime("%Y-%m") == key and done_on(t)), key=done_on)
		return key, done

	def report_counts(self, done):
		out = {"dev": {}, "project": {}, "category": {}, "gfx": {}}
		for t in done:
			if (t.get("link") or "").startswith(gfx_master.LINK):  # (🖼 a missing picture made)
				for d in devs_of(t) or ["(nobody)"]:
					out["gfx"][d] = out["gfx"].get(d, 0) + 1
			for d in devs_of(t) or ["(nobody)"]:
				out["dev"][d] = out["dev"].get(d, 0) + 1
			p = t.get("project") or NO_PROJECT
			out["project"][p] = out["project"].get(p, 0) + 1
			c = t.get("category") or "-"
			out["category"][c] = out["category"].get(c, 0) + 1
		return {k: sorted(v.items(), key=lambda kv: (-kv[1], kv[0].lower())) for k, v in out.items()}

	def fill_report(self):
		key, done = self.report_data()
		counts = self.report_counts(done)
		prev = (datetime.date(int(key[:4]), int(key[5:7]), 1) - datetime.timedelta(days=1)).strftime("%Y-%m")
		before = sum(1 for t in self.tasks if done_on(t) and done_on(t).strftime("%Y-%m") == prev)
		made = sum(1 for t in self.tasks if (t.get("created") or "")[:7] == key)
		vcs = sum(1 for v in self.data.get("vcs", []) if (v.get("date") or "")[:7] == key)
		diff = len(done) - before
		plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")
		self.report_sum.config(text=f"✓ {len(done)} done" + (f" ({'+' if diff > 0 else ''}{diff} on {month_name(prev).split()[0]})" if before or done else "")
							   + f"   ·   {plural(len(counts['dev']), 'dev')}   ·   {plural(made, 'new task')} set"
							   + (f"   ·   {plural(vcs, 'Dev VC')}" if vcs else "")
							   + (f"   ·   🖼 {plural(sum(c for _, c in counts['gfx']), 'picture')} made" if counts["gfx"] else "")
							   + self.gfx_month_text(key) + self.error_month_text(key))
		for k, rows in counts.items():
			top = rows[:8]
			wide = max((len(n) for n, _ in top), default=0)
			most = max((c for _, c in top), default=1)
			self.report_cols[k].config(text="\n".join(f"{n:<{wide}}  {'█' * max(1, round(8 * c / most))} {c}" for n, c in top)
									   + (f"\n+ {len(rows) - 8} more" if len(rows) > 8 else "") or "-")
		tx = self.report_text
		tx.config(state="normal")
		tx.delete("1.0", "end")
		self._report_refs = {}
		by_project = {}
		for t in done:
			by_project.setdefault(t.get("project") or NO_PROJECT, []).append(t)
		if not done:
			tx.insert("end", f"Nothing completed in {month_name(key)} yet.")
		for p, rows in sorted(by_project.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
			tx.insert("end", f"{p}  ({len(rows)})\n", "head")
			for t in rows:
				tag = "ref_" + t["ref"]
				self._report_refs[tag] = t["ref"]
				who = ", ".join(devs_of(t))
				tx.insert("end", f"✓ {t.get('title', '')}" + (f"  -  {who}" if who else "") + f"  ·  {done_on(t).strftime('%d %b')}\n", ("task", tag))
		tx.config(state="disabled")

	def report_go(self, ev):
		for tag in self.report_text.tag_names(f"@{ev.x},{ev.y}"):
			if tag in self._report_refs:
				self.go_to(self._report_refs[tag])
				return

	def copy_report(self):
		"""The month's report as text (for Discord: bold heads, a line per task)."""
		key, done = self.report_data()
		counts = self.report_counts(done)
		lines = [f"**Monthly Report: {month_name(key)}**", f"{len(done)} tasks completed", ""]
		lines.append("**By dev:** " + ", ".join(f"{n} {c}" for n, c in counts["dev"]))
		if counts["gfx"]:
			lines.append("**🖼 GFX made:** " + ", ".join(f"{n} {c}" for n, c in counts["gfx"]))
		if self.gfx_month_text(key):
			lines.append("**🖼 GFX left:** " + self.gfx_month_text(key).split("GFX left: ", 1)[1])
		if self.error_month_text(key):
			lines.append("**🐞 Errors:** " + self.error_month_text(key).split("Errors: ", 1)[1])
		lines.append("")
		by_project = {}
		for t in done:
			by_project.setdefault(t.get("project") or NO_PROJECT, []).append(t)
		for p, rows in sorted(by_project.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
			lines.append(f"**{p}** ({len(rows)})")
			lines += [f"- {t.get('title', '')}" + (f" ({', '.join(devs_of(t))})" if devs_of(t) else "") for t in rows]
			lines.append("")
		self.clipboard_clear()
		self.clipboard_append("\n".join(lines).strip())
		self.app.set_status(f"Monthly Report for {month_name(key)} copied ({len(done)} tasks): paste it anywhere.")

	def view_changed(self):
		self.app.config["todo_view"] = self.view.get()
		self.app.save_config()
		self.fill()

	def fill_filters(self):
		tags = sorted({g for t in self.tasks for g in t.get("tags", [])})
		vals = {"milestone": [ALL] + self.ms_order(), "project": [ALL] + self.project_names() + [NO_PROJECT], "dev": [ALL] + self.dev_names(), "category": [ALL] + self.data["categories"],
				"status": [ALL] + list(STATUSES) + ["Blocked"], "priority": [ALL] + list(PRIORITIES),
				"age": [ALL, "Green (up to 2 weeks)", "Yellow (up to 3 months)", "Red (older)"], "tag": [ALL] + tags}
		for k, v in vals.items():
			getattr(self, f"fbox_{k}").config(values=v)
			if self.f[k].get() not in v:
				self.f[k].set(ALL)

	def clear_filters(self):
		for v in self.f.values():
			v.set(ALL)
		self.search.set("")
		self.dev_tree.selection_set(())
		self.fill()

	def planning_both(self, t):
		"""A Needs Planning task also shows in its own list (General To Do, a dev's...): by default when it has sub-tasks."""
		return t.get("needs_planning") and t.get("planning_both", bool(self.subtasks(t)))

	def set_planning_both(self, tasks, on):
		for t in tasks:
			t["planning_both"] = on  # (stored as it is: "not set" means on when it has sub-tasks)
		self.refresh()

	def in_view(self, t, view=None):
		view = view or self.view.get()
		ln = lane(t)
		if view != "planning" and ln == "planning" and self.planning_both(t):
			ln = lane(dict(t, needs_planning=False))  # (also in its own list)
		if view == "archive":
			return ln == "archive"
		if view == "open":
			return ln != "archive"
		if view == "next":
			return self.ready(t)
		if view == "mine":
			return ln != "archive" and self.me.get() in devs_of(t)
		if view == "general":
			return in_general(t)  # (claimed reviews too: they're everyone's)
		return ln == view

	def shown(self, t):
		if not self.in_view(t):
			return False
		f = {k: v.get() for k, v in self.f.items()}
		if f["dev"] != ALL and f["dev"] not in devs_of(t):
			return False
		if f["category"] != ALL and t.get("category") != f["category"]:
			return False
		if f["status"] == "Blocked":
			if not t.get("blocked"):
				return False
		elif f["status"] != ALL and t.get("status") != f["status"]:
			return False
		if f["priority"] != ALL and t.get("priority") != f["priority"]:
			return False
		if f["age"] != ALL and age_band(age_of(t)) != f["age"].split()[0].lower():
			return False
		if f["milestone"] != ALL and not self.in_ms(t, f["milestone"]):
			return False
		if f["milestone"] == ALL and not self.show_hidden_ms.get() and self.ms_flag(self.ms_of(t), "hidden"):
			return False  # (a hidden milestone hides its tasks too, until Show hidden or that milestone is picked)
		if f["project"] != ALL and (t.get("project") or NO_PROJECT) != f["project"]:
			return False
		if f["tag"] != ALL and f["tag"] not in t.get("tags", []):
			return False
		q = self.search.get().strip().lower()
		if q:
			text = " ".join(str(t.get(k, "")) for k in ("ref", "title", "set_by", "category", "status", "setter_note", "dev_note",
															"blocked", "reviewer")) + " " + " ".join(t.get("tags", []) + devs_of(t)) + (" ai requires-ai" if t.get("needs_ai") else "") \
					+ " " + " ".join(f"{k} {v}" for k, v in (t.get("fields") or {}).items())
			if not all(w in text.lower() for w in q.split()):
				return False
		return True

	def sort_key(self, t):
		k = self.sort[0]
		if k == "age":
			return age_of(t)
		if k == "priority":
			return PRIORITIES.index(t.get("priority", "Normal")) if t.get("priority") in PRIORITIES else 1
		if k == "status":
			return STATUSES.index(t["status"]) if t.get("status") in STATUSES else 0
		if k == "ref":
			return int(re.sub(r"\D", "", t["ref"]) or 0)
		if k == "tags":
			return " ".join(t.get("tags", []))
		if k == "devs":
			return " ".join(devs_of(t)).lower() or "~"
		if k == "sweep":
			return 0 if t.get("sweep") else 1
		if k == "flags":
			return (not t.get("blocked"), not t.get("needs_planning"), not t.get("needs_ai"), not t.get("depends_on"))
		return str(t.get(k, "")).lower()

	def sort_by(self, key):
		self.sort = (key, not self.sort[1] if self.sort[0] == key else key in ("age", "priority"))
		self.fill()

	def dnd_press(self, ev):
		self.dnd_cancel()
		t = self.tree
		row = t.identify_row(ev.y)
		self._dnd = None
		if row and self.task(row) and t.identify_region(ev.x, ev.y) in ("tree", "cell"):
			refs = [r for r in t.selection() if self.task(r)] if row in t.selection() else [row]
			self._dnd = {"refs": refs, "x": ev.x, "y": ev.y, "on": False, "target": None}

	def dnd_target(self, row):
		"""What a drop on this row does: (project, parent, group) or None (not allowed)."""
		moving = [self.task(r) for r in self._dnd["refs"]]
		if row == "__no_group__":
			return ("", "", "")
		if not row or row in self._dnd["refs"]:
			return None
		if row.startswith("proj:"):
			return (row[5:] if self.project(row[5:]) else "", "", "")
		if row.startswith("grp:"):
			key, g = row[4:].rsplit(":", 1)
			if key.startswith("proj:"):
				return (key[5:], "", g)
			par = self.task(key)
			if par is None or any(par is m or self.is_below(par, m) for m in moving):
				return None
			return (par.get("project", ""), key, g)
		par = self.task(row)
		if par is None or any(self.is_below(par, m) for m in moving):
			return None
		return (par.get("project", ""), row, "")

	def dnd_motion(self, ev):
		d = self._dnd
		if not d:
			return
		if not d["on"] and abs(ev.x - d["x"]) + abs(ev.y - d["y"]) < 8:
			return
		d["on"] = True
		t = self.tree
		t.config(cursor="fleur")
		self.show_no_group()
		ui.drag_wobble(t, ev, d["refs"], origin=(d["x"], d["y"]))
		d["at"] = (ev.x, ev.y)
		ui.drag_autoscroll(t, ev, after=self.dnd_hover)  # (near the top / bottom: scrolls by itself; the wheel works too)
		self.dnd_hover(ev)
		return "break"

	def dnd_hover(self, ev=None):
		"""The drop target under the pointer, highlighted (again after the list scrolled under a still pointer)."""
		d, t = self._dnd, self.tree
		if not d or not d["on"]:
			return
		x, y = (ev.x, ev.y) if ev is not None else d["at"]
		row = "__no_group__" if ev is not None and self.over_no_group(ev) else t.identify_row(y)
		self.show_no_group(active=row == "__no_group__")
		if d["target"] != row:
			if d["target"] and t.exists(d["target"]):
				t.item(d["target"], tags=[g for g in t.item(d["target"], "tags") if g != "droptarget"])
			d["target"] = row
			if row and t.exists(row) and self.dnd_target(row) is not None:
				t.item(row, tags=("droptarget",) + tuple(t.item(row, "tags")))

	def dnd_release(self, ev):
		d, self._dnd = self._dnd, None
		t = self.tree
		t.config(cursor="")
		ungroup = self.over_no_group(ev)
		ui.drag_autoscroll_stop(t)
		if hasattr(t, "_drag_wobble"):
			t._drag_wobble.stop()
		self.hide_no_group()
		if not d or not d["on"]:
			return
		if d["target"] and t.exists(d["target"]):
			t.item(d["target"], tags=[g for g in t.item(d["target"], "tags") if g != "droptarget"])
		row = "__no_group__" if ungroup else t.identify_row(ev.y) if 0 <= ev.x < t.winfo_width() and 0 <= ev.y < t.winfo_height() else ""
		self._dnd = d  # (for dnd_target; the cell click of this release already saw it was a drag)
		where = self.dnd_target(row) if row else None
		self._dnd = None
		if where is None:
			return
		project, parent, group = where
		moved = [self.task(r) for r in d["refs"] if self.task(r)]
		if not moved:
			return
		moved = [m for m in moved if not any(self.is_below(m, o) for o in moved if o is not m)]  # Sub-tasks go with their parent.
		for m in moved:
			if project != (m.get("project") or ""):
				for c in [m] + [c for c in self.tasks if self.is_below(c, m)]:
					self.change(c, "project", project, note="moved")
			self.change(m, "parent", parent, note="moved")
			self.change(m, "group", group, note="moved")
			if group:
				self.keep_group(parent or "proj:" + project, group)
		self.refresh()
		what = f"{moved[0].get('title', '')}" if len(moved) == 1 else f"{len(moved)} tasks"
		dest = "No Group / No Project" if ungroup else (self.title_of(parent) if parent else project or NO_PROJECT) + (f" › {group}" if group else "")
		self.app.set_status(f"Moved {what} into {dest} (Ctrl+Z to undo).")

	def over_no_group(self, event):
		x = getattr(event, "x_root", self.tree.winfo_rootx() + event.x) - self.tree.winfo_rootx()
		y = getattr(event, "y_root", self.tree.winfo_rooty() + event.y) - self.tree.winfo_rooty()
		if self.tree.exists("__no_group__") and 0 <= x < self.tree.winfo_width() and 0 <= y < self.tree.winfo_height() and self.tree.identify_row(y) == "__no_group__":
			return True
		label = self.no_group_drop
		if not label.winfo_ismapped():
			return False
		return label.winfo_x() <= x < label.winfo_x() + label.winfo_width() and label.winfo_y() <= y < label.winfo_y() + label.winfo_height()

	def show_no_group(self, active=False):
		if self.mode.get() not in ("dev", "project"):
			return
		t = self.tree
		bg = ui.P["selection_background"] if active else ui.P["header_background"]
		fg = ui.P["selection_foreground"] if active else ui.P["header_foreground"]
		t.tag_configure("no_group_drop", background=bg, foreground=fg, font="om_bold")
		if not t.exists("__no_group__"):
			t.insert("", "end", iid="__no_group__", text="↓ No Group — release from project / grouping", tags=("no_group_drop",))
		box = t.bbox("__no_group__")
		visible = bool(box and box[1] + box[3] <= t.winfo_height())
		if visible and not active:
			self.no_group_drop.place_forget()
		else:
			# Keep the same in-list drop row reachable when the native final row is below the scroll viewport.
			canvas = self.no_group_drop
			height = box[3] if visible else ui.px(28)
			canvas.configure(background=bg, height=height)
			canvas.delete("all")
			canvas.create_line(0, 0, t.winfo_width(), 0, fill=ui.P["copper"], width=2)
			canvas.create_text(10, height / 2, anchor="w", text="↓ No Group — release from project / grouping", font="om_bold", fill=fg)
			canvas.place(x=1, y=box[1] if visible else max(0, t.winfo_height()-height-1), width=max(1,t.winfo_width()-2), height=height)
			canvas.tk.call("raise", str(canvas))

	def hide_no_group(self):
		self.no_group_drop.place_forget()
		if self.tree.exists("__no_group__"):
			self.tree.delete("__no_group__")

	def dnd_cancel(self, event=None):
		if event is not None and event.type == tk.EventType.Unmap and event.widget is not self.tree:
			return
		d = self._dnd
		if d and d.get("target") and self.tree.exists(d["target"]):
			row = d["target"]
			self.tree.item(row, tags=[tag for tag in self.tree.item(row, "tags") if tag != "droptarget"])
		self._dnd = None
		ui.drag_autoscroll_stop(self.tree)
		self.hide_no_group()
		self.tree.configure(cursor="")
		if hasattr(self.tree, "_drag_wobble"):
			self.tree._drag_wobble.stop()

	def keep_widths(self, ev=None):
		if getattr(self, "_drag_col", False):
			self._drag_col = False
			self.app.config["todo_col_widths"] = {c: int(self.tree.column(c, "width")) for c in ("#0",) + tuple(self.cols)}
			self.app.save_config()

	def show_sort(self):
		"""▲ / ▼ on the column the list is sorted by."""
		key, rev = self.sort
		for col, title in self.col_titles.items():
			on = key == col or (col == "#0" and key == "title")
			self.tree.heading(col, text=title + ((" ▼" if rev else " ▲") if on else ""))

	QUICK = ("priority", "devs", "category", "status", "project")

	def cell_click(self, ev):
		"""A click on a task's Priority / Dev(s) / Category / Status / Project: change it there (✋ claim it: claim it)."""
		t = self.tree
		if self._dnd and self._dnd.get("on"):
			return  # (it was a drag)
		if t.identify_region(ev.x, ev.y) != "cell":
			return
		row = t.identify_row(ev.y)
		task = self.task(row)
		c = t.identify_column(ev.x)
		if row.startswith("proj:") and c != "#0":
			shown = list(t["displaycolumns"])
			if shown[int(c[1:]) - 1] == "priority":
				m = tk.Menu(self, tearoff=0)
				self.project_priority_menu(m, row[5:])
				m.tk_popup(ev.x_root, ev.y_root)
			return
		if not task or c == "#0":
			return
		shown = list(t["displaycolumns"])
		if shown == ["#all"]:
			shown = list(self.cols)
		col = shown[int(c[1:]) - 1]
		if col not in self.QUICK:
			return
		tasks = self.picked() if row in t.selection() else [task]
		if col == "devs" and not devs_of(task) and lane(task) in ("general", "music"):
			self.claim(tasks)
			return
		m = tk.Menu(self, tearoff=0)
		if col == "status":
			self.status_menu(m, tasks)
		elif col in ("priority", "category"):
			cur = {x.get(col) for x in tasks}
			for v in (PRIORITIES if col == "priority" else self.data["categories"]):
				m.add_command(label=("● " if cur == {v} else "    ") + v, command=lambda v=v: self.set_many(tasks, col, v))
			if col == "category":
				m.add_separator()
				m.add_command(label="New category...", command=lambda: self.new_category(tasks))
		elif col == "project":
			cur = {x.get("project") or "" for x in tasks}
			for name in self.project_names() + [""]:
				m.add_command(label=("● " if cur == {name} else "    ") + (name or NO_PROJECT), command=lambda n=name: self.set_project(tasks, n))
			m.add_separator()
			m.add_command(label="New project...", command=lambda: self.add_project(tasks))
		else:  # devs: tick who works on it
			me = self.me.get()
			if any(me not in devs_of(x) for x in tasks):
				m.add_command(label=f"✋ Claim (add {me})", command=lambda: self.claim(tasks))
			for d in self.dev_names():
				on = all(d in devs_of(x) for x in tasks)
				m.add_command(label=("☑ " if on else "☐ ") + d, command=lambda d=d, on=on: self.toggle_dev(tasks, d, not on))
			m.add_separator()
			m.add_command(label="Share with devs...", command=lambda: self.share(tasks))
		m.tk_popup(ev.x_root, ev.y_root)

	def toggle_dev(self, tasks, dev, on):
		n = 0
		for x in tasks:
			ds = devs_of(x)
			new = ds + [dev] if on and dev not in ds else [d for d in ds if d != dev] if not on else ds
			n += self.change(x, "devs", new, note=("added " if on else "took off ") + dev)
		if n:
			self.refresh()

	def devs_text(self, t):
		ds = devs_of(t)
		if ds:
			return " + ".join(ds)
		return "✋ claim it" if lane(t) in ("general", "music") else "-"

	def task_row(self, x, depth=0):
		"""(values, tags) of a task's row in the table."""
		flags = []
		if x.get("needs_planning"):
			flags.append("📝 Planning")
		if x.get("needs_ai"):
			flags.append("🤖 AI")
		if not x.get("art") and not is_closed(x) and ART in [f for f, _ in self.fields_of(x)]:
			flags.append("🎨 Needs art")
		if x.get("blocked"):
			flags.append("⛔ Blocked")
		subs = self.subtasks(x)
		if subs:
			flags.append(f"☑ {sum(1 for c in subs if c.get('status') in CLOSED)}/{len(subs)} sub-tasks")
		waiting = [r for r in x.get("depends_on", []) if self.task(r) and not is_closed(self.task(r))]
		if waiting:
			flags.append("⏳ blocked by " + ", ".join(self.title_of(r) for r in waiting))
		blocking = [o for o in self.tasks if x["ref"] in o.get("depends_on", []) and not is_closed(o)]
		if blocking and not is_closed(x):
			flags.append("⛓ blocking " + ", ".join(o.get("title", o["ref"]) for o in blocking))
		tags = ["closed" if is_closed(x) else f"L{min(depth, len(LAYER_COLOURS) - 1)}"]
		if x.get("blocked") or waiting:
			tags.insert(0, "blocked")
		elif self.unblocked_now(x):
			tags.insert(0, "unblocked")
			flags.insert(0, "🔓 unblocked")
		elif self.ready(x):
			tags.insert(0, "ready")
		ms = self.milestone(self.ms_of(x)) if self.ms_of(x) else None
		if ms and self.ms_flag(ms["name"], "highlight"):  # (its own, or a milestone it's inside)
			tags.append("mshl")
			flags.insert(0, f"🏁 {ms['name']}")
		if x.get("priority") == "Critical":
			tags.append("critical")
		status = x.get("status", TODO) + (f" ({x['reviewer']})" if x.get("status") == "Ready for Review" and x.get("reviewer") else "")
		if x.get("archived"):
			status = f"🗄 {x['archived']}"
		values = (x["ref"], x.get("title", ""), (x.get("project") or "") + (f" · {x['group']}" if x.get("group") else ""), self.devs_text(x),
				  x.get("category", ""), status,
				  x.get("priority", "Normal"), self.timer_text(x), "🧹" if x.get("sweep") else "", " ".join(x.get("tags", [])), "  ".join(flags))
		return values, tags

	def task_branch_opened(self, event=None, closing=False):
		if self.mode.get() in ("dev", "project"):
			row = self.tree.focus()
			if row and self.tree.exists(row) and self.tree.get_children(row):
				getattr(self.app, "feedback", lambda *_: None)("close" if closing else "open")

	def task_clicked(self, event):
		if self.mode.get() not in ("dev", "project") or (self._dnd and self._dnd.get("on")):
			return
		if self.tree.identify_region(event.x, event.y) not in ("tree", "cell") or "indicator" in self.tree.identify_element(event.x, event.y).lower():
			return
		task = self.task(self.tree.identify_row(event.y))
		if task:
			kind = "select_owned" if self.me.get() in devs_of(task) else "select"
			getattr(self.app, "feedback", lambda *_: None)(kind)

	def show_empty_groupings(self):
		"""Keep empty folders available for organising only in the unfiltered open list."""
		return self.view.get() == "open" and not self.search.get().strip() and all(v.get() == ALL for v in self.f.values())

	def insert_task(self, parent_iid, x, shown, opened, depth=0):
		"""A task's row, then its sub-tasks (in their groupings first); folders open as they were (else: opened)."""
		t = self.tree
		values, tags = self.task_row(x, depth)
		project_mode = self.mode.get() == "project"
		kids = sorted((c for c in self.subtasks(x) if c["ref"] in shown), key=self.sort_key, reverse=self.sort[1])
		label = f"{x['ref']}  {x.get('title', '')}" if project_mode and self.show_ref.get() else x.get("title", "")
		if kids and not project_mode:
			label += f"   ({sum(1 for c in self.subtasks(x) if c.get('status') in CLOSED)}/{len(self.subtasks(x))} sub-tasks done)"
		t.insert(parent_iid, "end", iid=x["ref"], text=label, image=self.icon(x), values=values, tags=tags, open=self._open.get(x["ref"], opened))
		groups = {g: [] for g in x.get("groupings", [])}  # (its groupings, empty ones too)
		for c in kids:
			if c.get("group"):
				groups.setdefault(c["group"], []).append(c)
		for g in sorted(groups, key=lambda g: (x.get("groupings", []) + [g]).index(g) if g in x.get("groupings", []) else 999):  # groupings first, in their order
			if not groups[g] and not self.show_empty_groupings():
				continue
			members = [c for c in self.subtasks(x) if c.get("group") == g]
			done = sum(1 for c in members if is_closed(c))
			gid = f"grp:{x['ref']}:{g}"
			t.insert(x["ref"], "end", iid=gid, text=f" {g}  ({len(groups[g])})", image=self.group_icon(x, g), tags=("group",), open=self._open.get(gid, opened),
					 values=("", g, x.get("project") or "", "", "", f"{done}/{len(members)} done", "", "", "", "", ""))
			for c in groups[g]:
				self.insert_task(gid, c, shown, opened, depth + 1)
		for c in kids:
			if not c.get("group"):
				self.insert_task(x["ref"], c, shown, opened, depth + 1)

	def insert_tops(self, pid, name, tops, shown, opened):
		"""A project's top-level tasks under its row: its groupings (folders) first, then the rest."""
		t = self.tree
		p = self.project(name) or {}
		groups = {g: [] for g in p.get("groupings", [])}
		for x in tops:
			if x.get("group"):
				groups.setdefault(x["group"], []).append(x)
		every = [c for c in self.tasks if self.container(c) == "proj:" + name]
		for g, members in groups.items():
			if not members and not self.show_empty_groupings():
				continue
			done = sum(1 for c in every if c.get("group") == g and is_closed(c))
			total = sum(1 for c in every if c.get("group") == g)
			gid = f"grp:proj:{name}:{g}"
			t.insert(pid, "end", iid=gid, text=f" {g}  ({len(members)})", image=self.group_icon(p, g),
					 tags=("group",), open=self._open.get(gid, opened),
					 values=("", g, name, "", "", f"{done}/{total} done", "", "", "", "", ""))
			for x in members:
				self.insert_task(gid, x, shown, opened)
		for x in tops:
			if not x.get("group") or x["group"] not in groups:
				self.insert_task(pid, x, shown, opened)

	def fill_projects_tree(self, rows):
		"""Project mode: each project (its lead, progress), its tasks, their sub-tasks."""
		t = self.tree
		shown = {x["ref"] for x in rows}
		names = self.project_names() + [NO_PROJECT]
		want = self.f["project"].get()
		for name in names:
			if want != ALL and name != want:
				continue
			mine = [x for x in rows if (x.get("project") or NO_PROJECT) == name]
			p = self.project(name)
			if not mine and (name == NO_PROJECT or self.search.get().strip()):
				continue
			everything = [x for x in self.tasks if (x.get("project") or NO_PROJECT) == name]
			done = sum(1 for x in everything if is_closed(x))
			iid = "proj:" + name
			if t.exists(iid):
				continue
			t.insert("", "end", iid=iid, text=f" {name}", image=self.project_icon(name), open=self._open.get(iid, True), tags=self.project_tags(name),
					 values=("", name, name, f"Lead: {p.get('lead') or '-'}" if p else "", "", f"{done}/{len(everything)} done", "", "", "", "", ""))

			t.set(iid, "priority", self.project_priority_text(name))
			add = lambda parent_iid, x: self.insert_task(parent_iid, x, shown, False)  # (groupings / sub-tasks start folded)
			tops = []
			for x in mine:
				par = x.get("parent")
				if par and par in shown and (self.task(par) or {}).get("project") == x.get("project"):
					continue  # it goes under its parent
				tops.append(x)
			if self.project(name):
				self.insert_tops(iid, name, tops, shown, False)
			else:
				for x in tops:
					add(iid, x)

	def fill(self):
		# Project creation/rename/colour changes also invalidate the Ideas sidebar and picker.
		catalog = tuple((p.get("name"), p.get("colour")) for p in self.data.get("projects", []))
		if hasattr(self, "idea_pane") and catalog != getattr(self, "_idea_project_catalog", None):
			self._idea_project_catalog = catalog
			self.idea_pane.fill()
		self.activity.refresh()
		self.show_report()
		t = self.tree
		keep = t.selection()
		self._open = {i: bool(t.item(i, "open")) for i in self.all_rows() if t.get_children(i)}  # (folders stay as they were)
		t.delete(*t.get_children())
		rows = sorted((x for x in self.tasks if self.shown(x)), key=self.sort_key, reverse=self.sort[1])
		project_mode = self.mode.get() == "project"
		t.config(show="tree headings",
				 displaycolumns=[c for c in self.cols if c not in ("ref", "title", "project")] if project_mode else
				 [c for c in self.cols if c != "title" and (c != "ref" or self.show_ref.get())])
		self.col_titles["#0"] = "Task  (project › task › sub-task)" if project_mode else "Task  (▸ opens its sub-tasks)"
		if self.view.get() == "next":
			for x in self.next_order(rows):
				values, tags = self.task_row(x)
				n = self.my_numbers().get(x["ref"])
				t.insert("", "end", iid=x["ref"], text=f"{n}.  {x.get('title', '')}" if n else f"·   {x.get('title', '')}", image=self.icon(x),
						 values=values, tags=tags)
		elif project_mode:
			self.fill_projects_tree(rows)
		else:
			shown = {x["ref"] for x in rows}
			tops = [x for x in rows if x.get("parent") not in shown]  # (sub-tasks go under their parent task)
			projects = self.project_names()
			for x in tops:
				if x.get("project") not in projects:
					self.insert_task("", x, shown, False)
			if self.sort[0] == "priority":
				projects = sorted(projects, key=lambda n: PRIORITIES.index(self.project_priority(n)[0]), reverse=self.sort[1])
			for name in projects:
				mine = [x for x in tops if x.get("project") == name]
				if not mine:
					continue
				p = self.project(name) or {}
				every = [x for x in self.tasks if x.get("project") == name]
				done = sum(1 for x in every if is_closed(x))
				pid = "proj:" + name
				t.insert("", "end", iid=pid, text=f" {name}   ({sum(1 for x in rows if x.get('project') == name)})", image=self.project_icon(name),
						 tags=self.project_tags(name),
						 open=self._open.get(pid, False),
						 values=("", name, name, f"Lead: {p.get('lead') or '-'}", "", f"{done}/{len(every)} done", self.project_priority_text(name), "", "", "", ""))
				self.insert_tops(pid, name, mine, shown, False)
		ui.stripe(t)
		f = tkfont.nametofont("TkDefaultFont")  # (Flags as wide as its longest text: the scrollbar reaches all of it)
		widest = max([f.measure(t.set(i, "flags")) for i in self.all_rows() if not i.startswith(("proj:", "grp:"))] + [0])
		t.column("flags", width=max(int(t.column("flags", "width")), ui.px(170), widest + ui.px(24)))
		for i in keep:
			if t.exists(i):
				t.selection_add(i)
		self.fill_devs()
		self.fill_projects()
		self.fill_milestones()
		for b in self.order_btns:  # (your own order: only in My next task)
			if self.view.get() == "next":
				b.pack(side="right", padx=2)
			else:
				b.pack_forget()
		self.update_unblocked()
		counts = {k: sum(1 for x in self.tasks if self.in_view(x, k)) for k, _ in VIEWS}
		for k, text in VIEWS:
			self.view_buttons[k].config(text=f"{text} ({counts[k]})")
		self.sec_tasks.title.config(text=dict(VIEWS)[self.view.get()] if self.view.get() != "open" else "Tasks")
		self.sec_tasks.set_count(f"{len(rows)} shown")
		self.show_sort()
		self.app.set_status(f"To Do: {len(rows)} shown, {counts['open']} open, {counts['archive']} in the archive.")
		if self.cur and not t.exists(self.cur["ref"]):
			self.show_task(None)

	@staticmethod
	def timer_text(x):
		"""The timer with its colour as a dot: 🟢 up to 2 weeks, 🟡 up to 3 months, 🔴 older."""
		delta = age_of(x)
		return fmt_age(delta) if is_closed(x) else f"{AGE_DOTS[age_band(delta)]} {fmt_age(delta)}"

	def tick(self):
		"""The timers move on (every half minute)."""
		if self.winfo_exists():
			self.activity.refresh()
			for x in self.tasks:
				if self.tree.exists(x["ref"]):
					self.tree.set(x["ref"], "age", self.timer_text(x))
			self.idea_pane.update_badge()  # (new ideas from the others: the Ideas button counts them)
			if getattr(self, "_dev_trophy_month", None) != now().strftime("%Y-%m"):
				self.fill_devs()
			self.after(30000, self.tick)

	def fill_devs(self):
		d = self.dev_tree
		keep = d.selection()
		d.delete(*d.get_children())
		self._dev_trophy_month = now().strftime("%Y-%m")
		leaders = monthly_leaders(self.tasks, self.dev_names(), self._dev_trophy_month)
		lead = self.is_lead()
		asking = {x["name"] for x in self.data["devs"] if x.get("asking_task")}
		for name in self.dev_names():
			mine = [x for x in self.tasks if name in devs_of(x)]
			act = sum(1 for x in mine if not is_closed(x) and not x.get("blocked"))
			blk = sum(1 for x in mine if not is_closed(x) and x.get("blocked"))
			done = sum(1 for x in mine if x.get("status") == "Completed")
			lit = name in asking and (lead or name == self.me.get())
			d.insert("", "end", iid="dev:" + name, text=("🙋 " if lit else "") + ("🏆 " if name in leaders else "") + ("★ " if name == self.me.get() else "") + name,
					 values=(act, blk, done), tags=(("me",) if name == self.me.get() else ()) + (("asking",) if lit and lead else ()))
		for key, text, tag in (("general", f"✋ {GENERAL}", "lane"), ("music", f"🎵 {MUSIC_TODO}", "lane"), ("planning", f"📝 {PLANNING}", "planning")):
			rows = [x for x in self.tasks if (in_general(x) if key == "general" else lane(x) == key)]
			d.insert("", "end", iid="view:" + key, text=text,
					 values=(sum(1 for x in rows if not x.get("blocked")), sum(1 for x in rows if x.get("blocked")), ""), tags=(tag,))
		ui.stripe(d)
		for i in keep:
			if d.exists(i):
				d.selection_set(i)
		self.show_last_worked()
		me = self.me.get() in asking
		self.ask_btn.config(text="🙋 Asked for a task (click to take it back)" if me else "🙋 Ask for a task")
		new = asking - getattr(self, "_seen_asking", asking) - {self.me.get()}
		self._seen_asking = asking
		if lead and new:  # (a lead hears about it when it comes in)
			self.app.set_status(f"🙋 {', '.join(sorted(new))} {'is' if len(new) == 1 else 'are'} asking for a task (lit up in the Dev list).")
			getattr(self.app, "feedback", lambda *_: None)("presence")

	def ask_for_task(self):
		"""🙋 You'd like a task: you light up in the leads' Dev list until someone gives you one (or you take it back)."""
		dev = next((x for x in self.data["devs"] if x["name"] == self.me.get()), None)
		if dev is None:
			return
		if dev.get("asking_task"):
			dev.pop("asking_task")
			self.app.set_status("🙋 You took back your ask for a task.")
		else:
			dev["asking_task"] = stamp()
			self.app.set_status("🙋 The leads can see you'd like a task. It goes away by itself when you're given one.")
		self.save()
		self.fill_devs()

	def task_ideas_for(self, name, n=8):
		"""🙋 Open tasks nobody has, best first for this dev: [(score, task, reasons)]. Their skills and what they want to
		learn (Skills...), the projects they've worked in, priority, and how long it's waited."""
		dev = next((x for x in self.data["devs"] if x["name"] == name), {})
		skills, learn = set(dev.get("skills") or []), set(dev.get("learn") or [])
		projects = collections.Counter(x.get("project") for x in self.tasks if name in devs_of(x) and x.get("project"))
		out = []
		for t in self.tasks:
			if is_closed(t) or t.get("blocked") or t.get("needs_planning") or devs_of(t) or t.get("status") == FLESHING:
				continue
			score, why = PRIORITY_WEIGHT.get(t.get("priority"), 2), []
			cat, proj = t.get("category") or "", t.get("project") or ""
			if cat and cat in skills:
				score += 6
				why.append(f"skilled at {cat}")
			elif cat and cat in learn:
				score += 4
				why.append(f"wants to learn {cat}")
			if proj and projects.get(proj):
				score += min(5, 1 + projects[proj] // 3)
				why.append(f"has done {projects[proj]} in {proj}")
			if t.get("priority") in ("High", "Critical"):
				why.append(f"{t['priority'].lower()} priority")
			days = (now() - datetime.datetime.fromisoformat(t["created"])).days if t.get("created") else 0
			score += min(3, days / 14)
			if days >= 14:
				why.append(f"waiting {days} days")
			out.append((score, t, why))
		out.sort(key=lambda r: -r[0])
		return out[:n]

	def suggest_task(self, name):
		"""🙋 For a lead: the tasks that would suit a dev who asked for one; Give hands it over (which ends their ask)."""
		ideas = self.task_ideas_for(name)
		w = tk.Toplevel(self)
		w.title(f"🙋 A task for {name}")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		dev = next((x for x in self.data["devs"] if x["name"] == name), {})
		asked = dev.get("asking_task")
		ttk.Label(f, text=f"🙋 {name} " + (f"asked for a task {ago(asked)}" if asked else "isn't asking right now") + ".", font="om_bold").pack(anchor="w")
		ttk.Label(f, text="Open tasks nobody has, best fit first (their skills, what they want to learn, projects they've worked in, "
						  "priority, how long it's waited).", style="Muted.TLabel", wraplength=ui.px(560)).pack(anchor="w", pady=(2, 8))
		t = ttk.Treeview(f, columns=("why",), height=min(8, max(3, len(ideas))), selectmode="browse")
		t.heading("#0", text="Task")
		t.heading("why", text="Why")
		t.column("#0", width=ui.px(300))
		t.column("why", width=ui.px(320))
		t.pack(fill="both", expand=True)
		for _, task, why in ideas:
			t.insert("", "end", iid=task["ref"], text=f"{task['ref']}  {task.get('title', '')}", values=(", ".join(why) or "open and unclaimed",))
		if ideas:
			t.selection_set(ideas[0][1]["ref"])
		else:
			ttk.Label(f, text="Nothing open and unclaimed right now.", style="Muted.TLabel").pack(anchor="w", pady=4)

		def give():
			sel = t.selection()
			task = self.task(sel[0]) if sel else None
			if task is None:
				return
			self.change(task, "devs", [name], note=f"Given to {name} (they asked for a task)")
			self.save()
			self.fill_filters()
			self.fill()
			self.fill_devs()
			self.app.set_status(f"🙋 {task['ref']} {task.get('title', '')} is {name}'s now.")
			w.destroy()

		def show():
			sel = t.selection()
			if sel:
				self.show_task(sel[0])
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(8, 0))
		ttk.Button(bf, text=f"Give it to {name}", command=give).pack(side="right")
		ttk.Button(bf, text="Show the task", command=show).pack(side="right", padx=6)
		ttk.Button(bf, text="Close", command=w.destroy).pack(side="left")
		t.bind("<Double-1>", lambda ev: give())

	def unflag_askers(self):
		"""Someone who asked for a task and has been given one since (added to a task's devs, or a new task set with them on
		it): not asking any more. True when it changed."""
		changed = False
		for dev in self.data["devs"]:
			since, name = dev.get("asking_task"), dev["name"]
			if not since:
				continue
			for t in self.tasks:
				if name not in devs_of(t):
					continue
				if (t.get("created") or "") >= since or any(
						h.get("field") == "devs" and (h.get("when") or "") >= since and name in (h.get("new") or [])
						and name not in (h.get("old") or []) for h in t.get("history", [])):
					dev.pop("asking_task")
					changed = True
					break
		return changed

	def trophy_secret(self):
		"""A small Easter egg for a particularly thorough inspector of the Dev column heading."""
		self._trophy_taps = getattr(self, "_trophy_taps", 0) + 1
		if self._trophy_taps < 7:
			return
		self._trophy_taps = 0
		dev = next((d for d in self.data["devs"] if d["name"] == self.me.get()), None)
		if dev is None or "rubber_duck" in (dev.get("secrets") or []):
			return
		dev.setdefault("secrets", []).append("rubber_duck")
		self.save()
		getattr(self.app, "feedback", lambda *_: None)("success")
		messagebox.showinfo(APP_NAME, "MINISTRY OF UNFINISHED BUSINESS\n\nA very small rubber duck stamps your paperwork.\nQUACK.\n\nRubber Duck Supreme unlocked.\nThe duck believes in you. Please finish a task.", parent=self)

	def last_worked_on(self, name):
		"""The newest thing this dev did on a task (a change they made, or a task they set). Worked out for everyone in one
		pass, once per save (it went through every task's history for each dev on every refresh)."""
		if getattr(self, "_lw_key", None) is not getattr(self, "_saved", None) or not hasattr(self, "_lw"):
			newest = {}
			for x in self.tasks:
				for h in x.get("history", []):
					who = h.get("who")
					if who and (who not in newest or h["when"] > newest[who][0]):
						newest[who] = (h["when"], x, h)
			self._lw = newest
			self._lw_key = getattr(self, "_saved", None)
		got = self._lw.get(name)
		if got is None:
			return None
		when, x, h = got
		return when, x, "set the task" if h["field"] == "created" else f"{FIELD_NAMES.get(h['field'], h['field'])}: {show_value(h.get('new'))}"

	def show_last_worked(self):
		sel = [i[4:] for i in self.dev_tree.selection() if i.startswith("dev:")]
		lines = []
		for n in sel or self.dev_names():
			b = self.last_worked_on(n)
			if b:
				lines.append(f"{n}: {b[1]['ref']} {b[1].get('title', '')}\n      {b[2]}, {ago(b[0])}")
			elif sel:
				lines.append(f"{n}: nothing yet")
		self.last_worked.config(text="\n".join(lines) or "Nothing yet.")

	def dev_at(self, ev):
		row = self.dev_tree.identify_row(ev.y)
		return row[4:] if row.startswith("dev:") else None

	def dev_picked(self, ev=None):
		sel = self.dev_tree.selection()
		# Refilling the dev list picks the same row again, which fires this again: only act on a new pick
		# (else every pick refilled the lists for ever and the window froze).
		if sel == self._dev_sel:
			return
		self._dev_sel = sel
		if sel and sel[0].startswith("dev:"):
			self.f["dev"].set(sel[0][4:])
			if self.view.get() not in ("open", "archive"):
				self.view.set("open")
			self.fill()
			name = sel[0][4:]
			if name != self.me.get() and self.is_lead() and next((x for x in self.data["devs"] if x["name"] == name), {}).get("asking_task"):
				self.after(100, lambda: self.suggest_task(name))  # (🙋 they asked for a task: what would suit them)
		elif sel and sel[0].startswith("view:"):
			self.f["dev"].set(ALL)
			self.view.set(sel[0][5:])
			self.view_changed()
		self.show_last_worked()

	def dev_menu(self, ev):
		name = self.dev_at(ev)
		m = tk.Menu(self, tearoff=0)
		if name:
			self.dev_tree.selection_set("dev:" + name)
			m.add_command(label=f"{name}'s tasks", command=lambda: (setattr(self, "_dev_sel", ()), self.dev_picked()))
			lead = self.is_lead()
			if lead:
				m.add_command(label=f"🙋 Suggest a task for {name}...", command=lambda: self.suggest_task(name))
			if lead:
				m.add_command(label="Rename...", command=lambda: self.rename_dev(name))
				m.add_command(label="Git name...", command=lambda: self.git_name(name))
			if lead or name == self.me.get():
				m.add_command(label="Skills / wants to learn...", command=lambda: self.skills(name))
			if lead:
				m.add_command(label="Remove...", command=lambda: self.remove_dev(name))
			m.add_separator()
		else:
			row = self.dev_tree.identify_row(ev.y)
			if row.startswith("view:"):
				view = row[5:]
				m.add_command(label="+ New task here...", command=lambda: (self.view.set(view), self.edit_task(new=True, project="")))
				m.add_separator()
		m.add_command(label="+ New task (no project)...", command=lambda: self.edit_task(new=True, project=""))
		if self.is_lead():
			m.add_command(label="Add a dev...", command=self.add_dev)
		m.tk_popup(ev.x_root, ev.y_root)

	# ---------- the picked task ----------
	def show_task(self, ref=""):
		self.flush_notes()
		if ref == "":
			sel = self.tree.selection()
			ref = sel[0] if sel else None
		t = self.cur = self.task(ref) if ref else None
		self.portrait_preview.show(portrait_sprite(t) if t else None, (t or {}).get("links") or [])
		self.state_review_panel.show(t)
		self.country_review_panel.show(t)
		for box in (self.n_set, self.n_dev):
			box.delete("1.0", "end")
		self.hist.config(state="normal")
		self.hist.delete("1.0", "end")
		self.sel_ref = ref
		if t is None and ref and ref.startswith("ms:"):
			self.show_buttons(False)
			self.d_grid.pack_forget()
			self.d_info.pack(anchor="w", pady=(2, 0), before=self.d_buttons)
			self.show_milestone(ref[3:])
			self.hist.config(state="disabled")
			return
		self.d_info.pack_forget()
		self.d_grid.pack(anchor="w", fill="x", pady=(4, 0), before=self.d_buttons)
		if t is None and ref and ref.startswith("proj:"):
			name = ref[5:]
			p = self.project(name) or {}
			mine = [x for x in self.tasks if (x.get("project") or NO_PROJECT) == name]
			opn = [x for x in mine if not is_closed(x)]
			blk = sum(1 for x in opn if x.get("blocked") or self.waiting_on(x))
			pr, own = self.project_priority(name) if p else ("", False)
			self.d_title.config(text=name, fg=p.get("colour") or "#1f2d3d")
			self.details([("Lead", p.get("lead") or "nobody yet", None), ("Priority", f"{pr} (set)" if own else f"{pr} (average)" if pr else "-", None),
						  ("Milestone", p.get("milestone") or "-", None),
						  ("Tasks", f"{len(opn)} open   ·   {len(mine) - len(opn)} done" + (f"   ·   {blk} blocked" if blk else ""), "#c62828" if blk else None)],
						 wide=[("Note", p["note"])] if p.get("note") else [],
						 foot=f"Set up by {p.get('set_by', '?')} on {short_date(p.get('created'))}" if p else "")
			self.d_block.pack_forget()
			self.show_buttons(False, edit=bool(p))
			self.hist.config(state="disabled")
			return
		if t is None and ref and ref.startswith("grp:"):
			key, g = ref[4:].rsplit(":", 1)
			holder = self.holder(key) or {}
			members = [c for c in self.tasks if self.container(c) == key and c.get("group") == g]
			opn = [c for c in members if not is_closed(c)]
			where = f"{key[5:]} (project)" if key.startswith("proj:") else self.title_of(key)
			self.d_title.config(text=g, fg="#5b4a8a")
			self.details([("In", where, None), ("Tasks", f"{len(opn)} open   ·   {len(members) - len(opn)} done", None)])
			self.d_block.pack_forget()
			self.show_buttons(False, edit=True)
			self.cur_group = (key, g)
			self.group_desc.delete("1.0", "end")
			self.group_desc.insert("1.0", (holder.get("group_notes") or {}).get(g, ""))
			self.group_desc_frame.pack(fill="x", after=self.d_buttons, pady=(4, 0))
			self.hist.config(state="disabled")
			return
		if t is None:
			self.d_title.config(text="Pick a task", fg="#333")
			self.details([])
			self.d_block.pack_forget()
			self.show_buttons(False, edit=False)
			self.hist.config(state="disabled")
			return
		self.show_buttons(True)
		delta = age_of(t)
		colour = ui.P["input_foreground"] if state_review.state_id(t) else "#777" if is_closed(t) else AGE_COLOURS[age_band(delta)]
		self.d_title.config(text=t.get("title", ""), fg=colour)
		where = {"general": f"{GENERAL} - nobody's yet: claim it", "music": f"{MUSIC_TODO} - nobody's yet: claim it", "planning": PLANNING,
				 "dev": "", "archive": "Archive"}[lane(t)]
		proj = t.get("project") or "-"
		if t.get("group"):
			proj += f"  ›  {t['group']}"
		status = t.get("status", TODO) + (f"  (reviewer {t['reviewer']})" if t.get("reviewer") else "")
		pairs = [("Status", status, None), ("Priority", t.get("priority", "Normal"), "#c62828" if t.get("priority") == "Critical" else None),
				 ("Dev(s)", ", ".join(devs_of(t)) or "nobody yet", None), ("Category", t.get("category", "") or "-", None),
				 ("Project", proj, None), ("Age", fmt_age(delta) + (f" (closed {short_date(t['closed'])})" if t.get("closed") else ""), None if is_closed(t) else AGE_COLOURS[age_band(delta)])]
		if self.ms_of(t):
			pairs.append(("Milestone", self.ms_of(t) + ("" if t.get("milestone") else " (its project's)"), None))
		if where:
			pairs.append(("List", where, None))
		idea = self.idea_pane.idea(t["idea"]) if t.get("idea") and hasattr(self, "idea_pane") else None
		if idea:
			pairs.append(("Idea", f"💡 {idea.get('title', '')} ({idea.get('state', 'open').replace('fleshing', 'needs fleshing')})", "#b06f00" if idea.get("state") == "fleshing" else None))
		if t.get("sweep") or t.get("tags") or t.get("needs_ai"):
			pairs.append(("Also", ", ".join((["🤖 requires AI"] if t.get("needs_ai") else []) + (["part of a sweep"] if t.get("sweep") else [])
											+ ([" ".join(t["tags"])] if t.get("tags") else [])), None))
		wide = []
		if t.get("archived"):
			h = next((h for h in reversed(t.get("history", [])) if h.get("field") == "archived" and h.get("new")), {})
			wide.append(("Archived", f"{t['archived']}" + (f" - {t['archive_note']}" if t.get("archive_note") else "")
						 + (f"  (by {h.get('who')} on {short_date(h.get('when'))})" if h else "")))
		if t.get("parent"):
			wide.append(("Sub-task of", self.title_of(t["parent"])))
		waits = [self.task(r) for r in t.get("depends_on", []) if self.task(r)]
		if waits:
			wide.append(("Blocked by", ";   ".join(f"{o.get('title', '')}" + (" ✔" if is_closed(o) else f" ({o.get('status')})") for o in waits)))
		blocking = [o for o in self.tasks if t["ref"] in o.get("depends_on", []) and not is_closed(o)]
		if blocking:
			wide.append(("Blocking", ";   ".join(f"{o.get('title', '')} ({', '.join(devs_of(o)) or 'nobody'})" for o in blocking)))
		subs = self.subtasks(t)
		if subs:
			left = [c for c in subs if not is_closed(c)]
			wide.append(("Sub-tasks", f"{len(subs) - len(left)} of {len(subs)} done" + ("   ·   still open: " + ", ".join(c.get("title", "") for c in left[:8])
																						  + (" ..." if len(left) > 8 else "") if left else "")))
		self.details(pairs, wide, foot=f"Set by {t.get('set_by', '?')} on {short_date(t.get('created'))}   ·   {t['ref']}")
		self.d_block.config(text=f"⛔ Blocked: {t['blocked']}" if t.get("blocked") else "")
		if t.get("blocked"):
			self.d_block.pack(fill="x", before=self.d_buttons)
		else:
			self.d_block.pack_forget()
		self.n_set_label.config(text=f"Note from the setter, {t.get('set_by', '?')} (shown in game)")
		self.n_dev_label.config(text=f"Note from the dev{'s' if len(devs_of(t)) > 1 else ''}, {', '.join(devs_of(t)) or 'nobody yet'}")
		self.n_set.insert("1.0", t.get("setter_note", ""))
		self.n_dev.insert("1.0", t.get("dev_note", ""))
		self.show_fields(t)
		for h in reversed(t.get("history", [])):
			if h["field"] == "created":
				line = f"{short_date(h['when'])}  {h['who']} set the task"
			else:
				line = (f"{short_date(h['when'])}  {h['who']}: {FIELD_NAMES.get(h['field'], h['field'])} "
						f"{show_value(h.get('old'))} -> {show_value(h.get('new'))}")
			self.hist.insert("end", line + (f"  ({h['note']})" if h.get("note") else "") + "\n")
		self.hist.config(state="disabled")
		m = tk.Menu(self.status_btn, tearoff=0)
		self.status_menu(m, [t])
		self.status_btn.config(menu=m, text=f"Status: {t.get('status')}")
		self.fill_links()
		self.claim_btn.config(text="Leave the task" if self.me.get() in devs_of(t) else "✋ Claim",
							  command=(lambda: self.leave([t])) if self.me.get() in devs_of(t) else (lambda: self.claim([t])))

	# ---------- descriptors: fields a project / grouping gives its tasks (Location, Upgrade 1...), or a task has itself ----------
	def fields_of(self, t):
		"""[(field, where it comes from)] for a task: its project's, its grouping's, then its own."""
		out = []
		p = self.project(t.get("project")) if t.get("project") else None
		for f in (p or {}).get("fields", []):
			out.append((f, f"📁 {p['name']}"))
		if t.get("group") and self.container(t):
			holder = self.holder(self.container(t)) or {}
			for f in (holder.get("group_fields") or {}).get(t["group"], []):
				out.append((f, f"🗂 {t['group']}"))
		for f in t.get("own_fields", []):
			out.append((f, "this task"))
		seen, uniq = set(), []
		for f, src in out:
			if f.lower() not in seen:
				seen.add(f.lower())
				uniq.append((f, src))
		return uniq

	def show_fields(self, t):
		"""The Descriptors box of the Selected task panel: one line per field, typed in place (saved a moment later)."""
		ff = self.fields_frame
		for w in ff.winfo_children():
			w.destroy()
		self._field_vars, self._field_task = {}, t
		fields = self.fields_of(t) if t else []
		if not fields:
			ff.pack_forget()
			return
		ff.pack(fill="x", after=self.d_buttons, pady=(2, 6))
		head = ttk.Frame(ff)
		head.grid(row=0, column=0, columnspan=3, sticky="we")
		ttk.Label(head, text="🏷 Descriptors", style="Head.TLabel").pack(side="left")
		ttk.Button(head, text="Edit this task's own...", style="Tool.TButton", command=lambda: self.edit_own_fields(t)).pack(side="right")
		vals = t.get("fields") or {}
		for r, (f, src) in enumerate(fields, start=1):
			if f == ART:
				self.art_row(ff, r, t, src)
				continue
			ttk.Label(ff, text=("📍 " if f == LOC else "") + f).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=1)
			if (self.data.get("field_types") or {}).get(f) == "yesno":
				v = self._field_vars[f] = tk.BooleanVar(value=vals.get(f) == "Yes")
				ttk.Checkbutton(ff, text="Yes", variable=v, command=self.flush_fields).grid(row=r, column=1, sticky="w", pady=1)
			else:
				v = self._field_vars[f] = tk.StringVar(value=vals.get(f, ""))
				e = ttk.Entry(ff, textvariable=v, font="TkDefaultFont")
				e.grid(row=r, column=1, sticky="we", pady=1)
				e.bind("<KeyRelease>", lambda ev: self.note_changed())
			ttk.Label(ff, text=src, style="Muted.TLabel").grid(row=r, column=2, sticky="w", padx=(8, 0))
		ff.columnconfigure(1, weight=1)

	def flush_fields(self, save=True):
		t = self._field_task
		if t is None or not self._field_vars or t is not self.cur:
			return False
		vals = dict(t.get("fields") or {})
		for f, v in self._field_vars.items():
			text = ("Yes" if v.get() else "") if isinstance(v, tk.BooleanVar) else v.get().strip()
			if text:
				vals[f] = text
			else:
				vals.pop(f, None)
		if vals != (t.get("fields") or {}):
			t["fields"] = vals
			if not vals:
				t.pop("fields")
			t["updated"] = stamp()
			if save:
				self.save()
			return True
		return False

	def edit_field_list(self, title, fields, done):
		"""A list of field names to edit (add, remove, move up / down); done(new list) on OK."""
		w = tk.Toplevel(self)
		w.title(title)
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=title, style="Head.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
		ttk.Label(f, text="Fields every task under it gets in its 🏷 Descriptors (e.g. Location, Culture/Requirements, Upgrade 1).",
				  style="Muted.TLabel", wraplength=ui.px(420), justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 8))
		lb = tk.Listbox(f, height=9, width=40, activestyle="none", font="TkDefaultFont")
		types = dict(self.data.get("field_types") or {})
		lb.grid(row=2, column=0, sticky="nsew")
		items = list(fields)

		def refill(sel=None):
			lb.delete(0, "end")
			for x in items:
				lb.insert("end", {LOC: "📍 ", ART: "🎨 "}.get(x, "") + x + ("   (Yes / No)" if types.get(x) == "yesno" else ""))
			if sel is not None and 0 <= sel < len(items):
				lb.selection_set(sel)
		refill()
		bf = ttk.Frame(f)
		bf.grid(row=2, column=1, sticky="n", padx=(8, 0))
		new = tk.StringVar()
		yesno = tk.BooleanVar(value=False)

		def add(name=None):
			n = (name or new.get()).strip()
			if n and n.lower() not in (x.lower() for x in items):
				items.append(n)
				if n not in (LOC, ART):
					if yesno.get():
						types[n] = "yesno"
					else:
						types.pop(n, None)
				refill(len(items) - 1)
			new.set("")

		def flip():
			i = cur()
			if i is not None and items[i] not in (LOC, ART):
				x = items[i]
				if types.get(x) == "yesno":
					types.pop(x)
				else:
					types[x] = "yesno"
				refill(i)

		def cur():
			return lb.curselection()[0] if lb.curselection() else None

		def move(d):
			i = cur()
			if i is not None and 0 <= i + d < len(items):
				items[i], items[i + d] = items[i + d], items[i]
				refill(i + d)

		def remove():
			i = cur()
			if i is not None:
				items.pop(i)
				refill(min(i, len(items) - 1))
		for text, fn in (("📍 + Location", lambda: add(LOC)), ("🎨 + Needs Icon/Art", lambda: add(ART)), ("⇄ Yes/No / Text", flip),
						 ("▲ Up", lambda: move(-1)), ("▼ Down", lambda: move(1)), ("Remove", remove)):
			ttk.Button(bf, text=text, command=fn).pack(fill="x", pady=(0, 3))
		row = ttk.Frame(f)
		row.grid(row=3, column=0, columnspan=2, sticky="we", pady=(8, 0))
		e = ttk.Entry(row, textvariable=new, width=30, font="TkDefaultFont")
		e.pack(side="left", fill="x", expand=True)
		e.bind("<Return>", lambda ev: add())
		ttk.Checkbutton(row, text="Yes / No", variable=yesno).pack(side="left", padx=(6, 0))
		ttk.Button(row, text="+ Add", command=add).pack(side="left", padx=(6, 0))
		e.focus_set()
		ttk.Label(f, text="(The values typed in stay with each task, even if a field is removed and added again.)", style="Muted.TLabel").grid(
			row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

		def ok():
			add()
			w.destroy()
			ft = self.data.setdefault("field_types", {})  # (a field's type goes with its name, for everyone)
			for x in items:
				if types.get(x) == "yesno":
					ft[x] = "yesno"
				else:
					ft.pop(x, None)
			done(items)
		ob = ttk.Frame(f)
		ob.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
		ttk.Button(ob, text="OK", command=ok).pack(side="left")
		ttk.Button(ob, text="Cancel", command=w.destroy).pack(side="left", padx=4)
		self._fields_dialog = (items, add, ok, yesno, flip, lb)  # (for tests)

	def edit_project_fields(self, name):
		p = self.project(name)
		if p is None:
			return

		def done(items):
			p["fields"] = items
			if not items:
				p.pop("fields")
			self.refresh()
		self.edit_field_list(f"Descriptors for 📁 {name}'s tasks", p.get("fields", []), done)

	def edit_group_fields(self, key, g):
		holder = self.holder(key)
		if holder is None:
			return

		def done(items):
			gf = holder.setdefault("group_fields", {})
			gf[g] = items
			if not items:
				gf.pop(g)
			self.refresh()
		self.edit_field_list(f"Descriptors for 🗂 {g}'s tasks", (holder.get("group_fields") or {}).get(g, []), done)

	def edit_own_fields(self, t):
		def done(items):
			t["own_fields"] = items
			if not items:
				t.pop("own_fields")
			t["updated"] = stamp()
			self.refresh()
		self.flush_fields()
		self.edit_field_list(f"This task's own descriptors ({t['ref']})", t.get("own_fields", []), done)

	def toggle_location(self, tasks, f=LOC):
		"""Right-click > 📍 Has location / 🎨 Needs Icon/Art: that descriptor on the task(s) (theirs, not their project's)."""
		self.flush_fields()
		on = not all(f in t.get("own_fields", []) for t in tasks)
		for t in tasks:
			own = t.setdefault("own_fields", [])
			if on and f not in own:
				own.insert(0, f)
			elif not on and f in own:
				own.remove(f)
			if not own:
				t.pop("own_fields")
			t["updated"] = stamp()
		self.refresh()
		if on and len(tasks) == 1 and f == LOC:
			self.after(50, lambda: self.focus_field(LOC))

	# ---------- 🎨 Needs Icon/Art: its pictures (PNG, kept with the live To Do so everyone sees them) ----------
	def art_dir(self):
		return os.path.join(os.path.dirname(self.path()), ideas.PICTURES)

	def art_row(self, ff, r, t, src):
		have = t.get("art", [])
		ttk.Label(ff, text="🎨 Icon / Art").grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=(3, 1))
		box = ttk.Frame(ff)
		box.grid(row=r, column=1, sticky="we", pady=1)
		bar = ttk.Frame(box)
		bar.pack(fill="x")
		ttk.Label(bar, text=f"{len(have)} added" if have else "needed - none added yet", foreground="#2e9d4a" if have else "#d08a1e").pack(side="left")
		for text, fn in (("+ Picture...", lambda: self.add_art(t)), ("📋 Paste", lambda: self.paste_art(t))):
			ttk.Button(bar, text=text, style="Tool.TButton", command=fn).pack(side="left", padx=(6, 0))
		pics = ttk.Frame(box)
		pics.pack(fill="x", pady=(2, 0))
		self._art_thumbs = []
		from PIL import Image, ImageTk
		for name in have:
			path = os.path.join(self.art_dir(), name)
			try:
				im = Image.open(path)
				im.thumbnail((ui.px(72), ui.px(72)))
				ph = ImageTk.PhotoImage(im)
			except OSError:
				ph = None
			self._art_thumbs.append(ph)
			lab = tk.Label(pics, image=ph, text="" if ph else "(not here yet)", cursor="hand2", relief="solid", borderwidth=1)
			lab.pack(side="left", padx=(0, 4))
			lab.bind("<Button-1>", lambda ev, p=path: os.path.exists(p) and os.startfile(p))
			lab.bind("<Button-3>", lambda ev, n=name: self.art_menu(ev, t, n))
		ttk.Label(ff, text=src, style="Muted.TLabel").grid(row=r, column=2, sticky="nw", padx=(8, 0), pady=(3, 0))

	def store_picture(self, im, stem):
		"""A picture kept with the live To Do (PNG, at most 1024 px); returns its file name (tasks' art, 🖼 GFX)."""
		import uuid
		from PIL import Image
		os.makedirs(self.art_dir(), exist_ok=True)
		name = f"{stem}-{uuid.uuid4().hex[:6]}.png"
		im = im.convert("RGBA")
		im.thumbnail((1024, 1024), Image.LANCZOS)  # (kept small: everyone downloads it)
		im.save(os.path.join(self.art_dir(), name), optimize=True)
		return name

	def picture_from_file(self, title):
		"""A picture picked from a file (a PIL image), or None."""
		from PIL import Image
		path = filedialog.askopenfilename(parent=self, title=title,
										  filetypes=[("Pictures", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.dds *.tga"), ("All files", "*.*")])
		if not path:
			return None
		try:
			return Image.open(path)
		except OSError as ex:
			messagebox.showerror(APP_NAME, f"Can't read that picture:\n{ex}", parent=self)
			return None

	def picture_from_clipboard(self):
		"""The picture on the clipboard (a PIL image), or None (and says so)."""
		from PIL import Image, ImageGrab
		im = ImageGrab.grabclipboard()
		if isinstance(im, list) and im:
			try:
				im = Image.open(im[0])
			except OSError:
				im = None
		if not isinstance(im, Image.Image):
			messagebox.showinfo(APP_NAME, "There's no picture on the clipboard (copy one, or take a screenshot with Win+Shift+S).", parent=self)
			return None
		return im

	def save_art(self, t, im):
		name = self.store_picture(im, f"art-{t['ref']}")
		self.flush_fields()
		t.setdefault("art", []).append(name)
		t["updated"] = stamp()
		self.refresh()
		self.app.set_status(f"Art added to {t['ref']} ({len(t['art'])}).")

	def add_art(self, t):
		im = self.picture_from_file(f"Icon / art for {t['ref']}")
		if im is not None:
			self.save_art(t, im)

	def paste_art(self, t):
		im = self.picture_from_clipboard()
		if im is not None:
			self.save_art(t, im)

	def art_menu(self, ev, t, name):
		path = os.path.join(self.art_dir(), name)
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="Open", command=lambda: os.path.exists(path) and os.startfile(path))
		m.add_command(label="Open the folder", command=lambda: os.startfile(self.art_dir()))
		m.add_command(label="Remove", command=lambda: self.remove_art(t, name))
		m.tk_popup(ev.x_root, ev.y_root)

	def remove_art(self, t, name):
		if name in t.get("art", []):
			t["art"].remove(name)
			if not t["art"]:
				t.pop("art")
			t["updated"] = stamp()
			self.refresh()

	def set_location(self, t):
		self.flush_fields()
		v = simpledialog.askstring("Location", f"Where is {t.get('title', '')}? (a state, province, city, coordinates...)",
								   initialvalue=(t.get("fields") or {}).get(LOC, ""), parent=self)
		if v is None:
			return
		if LOC not in [f for f, _ in self.fields_of(t)]:
			t.setdefault("own_fields", []).insert(0, LOC)
		vals = t.setdefault("fields", {})
		if v.strip():
			vals[LOC] = v.strip()
		else:
			vals.pop(LOC, None)
		t["updated"] = stamp()
		self.refresh()

	def focus_field(self, f):
		for w in self.fields_frame.grid_slaves():
			if isinstance(w, ttk.Entry) and str(w.cget("textvariable")) == str(self._field_vars.get(f)):
				w.focus_set()

	def note_changed(self):
		if self._note_job:
			self.after_cancel(self._note_job)
		self._note_job = self.after(1000, self.flush_notes)

	def flush_notes(self, save=True):
		if self._note_job:
			self.after_cancel(self._note_job)
			self._note_job = None
		if getattr(self, "cur_group", None):
			key, g = self.cur_group
			holder = self.holder(key)
			text = self.group_desc.get("1.0", "end").strip()
			if holder is not None and text != (holder.get("group_notes") or {}).get(g, ""):
				holder.setdefault("group_notes", {})[g] = text
				if not text:
					holder["group_notes"].pop(g, None)
				if save:
					self.save(feedback=False)
			return
		t = self.cur
		if t is None:
			return
		changed = self.flush_fields(save=False)
		a, b = self.n_set.get("1.0", "end").strip(), self.n_dev.get("1.0", "end").strip()
		if changed and save and (a, b) == (t.get("setter_note", ""), t.get("dev_note", "")):
			self.save(feedback=False)
		if a != t.get("setter_note", "") or b != t.get("dev_note", ""):
			t["setter_note"], t["dev_note"] = a, b
			if save:
				self.save(feedback=False)

	def close(self):
		self.flush_notes()
		self.vc_pane.close()
		self.idea_pane.close()
		self.gfx_pane.close()
		self.sync.final()  # (anything not sent yet)
		self.app.config["todo_last_open"] = stamp()
		self.app.save_config()

	def show_buttons(self, task, edit=True):
		"""The buttons of the Selected task panel: a task's, or a project's / milestone's (Edit, copy); notes only for a task."""
		if hasattr(self, "fields_frame") and not task:
			self.fields_frame.pack_forget()
			self._field_vars, self._field_task = {}, None
		if hasattr(self, "group_desc_frame"):
			self.group_desc_frame.pack_forget()
			self.cur_group = None
		if not hasattr(self, "notes_frame"):
			pass  # (still being built)
		elif task:
			self.notes_frame.pack(fill="both", expand=True, after=self.d_buttons)
		else:
			self.notes_frame.pack_forget()
		for b in self.task_btns + (self.copy_btn, self.commit_btn):
			b.pack_forget()
		if task:
			for b in self.task_btns:
				b.pack(side="left", padx=(4, 0))
		self.copy_btn.pack(side="left", padx=(12, 0))
		self.commit_btn.pack(side="left", padx=4)
		self.d_buttons.winfo_children()[0].state(["!disabled"] if edit or task else ["disabled"])

	def details(self, pairs, wide=(), foot=""):
		"""The Selected task panel: label / value pairs two to a line, then the long ones, then a small grey footer."""
		g = self.d_grid
		for w in g.winfo_children():
			w.destroy()
		for i, (k, v, colour) in enumerate(pairs):
			r, c = divmod(i, 2)
			ttk.Label(g, text=k, style="Muted.TLabel").grid(row=r, column=c * 2, sticky="nw", padx=(0 if c == 0 else ui.px(28), ui.px(10)), pady=1)
			lab = tk.Label(g, text=v, font="om_bold", anchor="w", justify="left")
			if colour:
				lab.config(fg=colour)
			lab.grid(row=r, column=c * 2 + 1, sticky="w", pady=1)
		row = (len(pairs) + 1) // 2
		for k, v in wide:
			ttk.Label(g, text=k, style="Muted.TLabel").grid(row=row, column=0, sticky="nw", pady=(3, 0), padx=(0, ui.px(10)))
			ttk.Label(g, text=v, wraplength=max(ui.px(300), self._dwidth - ui.px(130)), justify="left").grid(row=row, column=1, columnspan=3, sticky="w", pady=(3, 0))
			row += 1
		if foot:
			ttk.Label(g, text=foot, style="Muted.TLabel", font="om_small").grid(row=row, column=0, columnspan=4, sticky="w", pady=(4, 0))
		ui.theme_all(g)

	def edit_selected(self):
		ref = getattr(self, "sel_ref", None) or ""
		if ref.startswith("proj:") and self.project(ref[5:]):
			self.edit_project(ref[5:])
		elif ref.startswith("ms:"):
			self.edit_milestone(ref[3:])
		elif ref.startswith("grp:"):
			key, g = ref[4:].rsplit(":", 1)
			self.rename_group(key, [c for c in self.tasks if self.container(c) == key and c.get("group") == g], g)
		else:
			self.edit_task()

	def copy_ref(self, commit):
		ref = getattr(self, "sel_ref", None) or ""
		if ref.startswith(("proj:", "ms:", "grp:")):  # a project / milestone / grouping: its name
			name = ref.rsplit(":", 1)[1] if ref.startswith("grp:") else ref.split(":", 1)[1]
			text = f"{name}: " if commit else name
			self.clipboard_clear()
			self.clipboard_append(text)
			self.app.set_status(f"Copied: {text}")
			return
		sel = [self.task(r) for r in self.tree.selection() if self.task(r)] or ([self.cur] if self.cur else [])
		if not sel:
			return
		text = "\n".join(f"{t['ref']}: {t.get('title', '')}" if commit else t["ref"] for t in sel)
		self.clipboard_clear()
		self.clipboard_append(text)
		self.app.set_status(f"Copied: {text.splitlines()[0]}" + (" ..." if len(sel) > 1 else ""))

	# ---------- right-click ----------
	def picked(self):
		return [self.task(r) for r in self.tree.selection() if self.task(r)]

	def status_menu(self, m, tasks):
		cur = {t.get("status") for t in tasks}
		for s in STATUSES:
			mark = "● " if cur == {s} else "    "
			if s == "Ready for Review":
				m.add_command(label=mark + "Ready for Review...", command=lambda: self.set_review(tasks))
			elif s == "Passed to Another Dev":
				m.add_command(label=mark + "Passed to Another Dev...", command=lambda: self.pass_on(tasks))
			else:
				m.add_command(label=mark + s, command=lambda s=s: self.set_many(tasks, "status", s))

	def task_menu(self, ev):
		if self.tree.identify_region(ev.x, ev.y) == "heading" and self.tree.identify_column(ev.x) == "#0":
			return self.task_bar_menu(ev)
		row = self.tree.identify_row(ev.y)
		if not row:
			return
		if row.startswith("proj:"):
			self.tree.selection_set(row)
			return self.project_menu(ev, row[5:])
		if row.startswith("grp:"):
			self.tree.selection_set(row)
			return self.group_menu(ev, *row[4:].rsplit(":", 1))
		if row not in self.tree.selection():
			self.tree.selection_set(row)
		tasks = self.picked()
		me = self.me.get()
		m = tk.Menu(self, tearoff=0)
		head = f"{tasks[0]['ref']}  {tasks[0].get('title', '')[:40]}" if len(tasks) == 1 else f"{len(tasks)} tasks"
		m.add_command(label=head, state="disabled")
		if self.view.get() == "next" and len(tasks) == 1:
			m.add_command(label="Set my number...", command=lambda: self.set_my_number(tasks[0]))
			m.add_command(label="Clear my numbers (back to the blocks / priority order)", command=self.clear_my_numbers)
			m.add_separator()
		if any(me not in devs_of(t) for t in tasks):
			m.add_command(label=f"✋ Claim (add {me})", command=lambda: self.claim(tasks))
		if any(me in devs_of(t) for t in tasks):
			m.add_command(label=f"Leave the task (take {me} off)", command=lambda: self.leave(tasks))
		m.add_command(label="Share with devs...", command=lambda: self.share(tasks))
		m.add_separator()
		self.status_menu(m, tasks)
		m.add_separator()
		for field, values, text in (("priority", PRIORITIES, "Priority"), ("category", self.data["categories"], "Category")):
			sub = tk.Menu(m, tearoff=0)
			cur = {t.get(field) for t in tasks}
			for v in values:
				sub.add_command(label=("● " if cur == {v} else "    ") + v, command=lambda f=field, v=v: self.set_many(tasks, f, v))
			if field == "category":
				sub.add_separator()
				sub.add_command(label="New category...", command=lambda: self.new_category(tasks))
			m.add_cascade(label=text, menu=sub)
		plan = all(t.get("needs_planning") for t in tasks)
		m.add_command(label=("☑" if plan else "☐") + f" {PLANNING}", command=lambda: self.set_many(tasks, "needs_planning", not plan))
		if plan:
			both = all(self.planning_both(t) for t in tasks)
			m.add_command(label=("☑" if both else "☐") + "     Also show in its own list (General To Do / its devs)",
						  command=lambda: self.set_planning_both(tasks, not both))
		sweep = all(t.get("sweep") for t in tasks)
		m.add_command(label=("☑" if sweep else "☐") + " Part of a sweep", command=lambda: self.set_many(tasks, "sweep", not sweep))
		ai = all(t.get("needs_ai") for t in tasks)
		m.add_command(label=("☑" if ai else "☐") + " 🤖 Requires AI", command=lambda: self.set_many(tasks, "needs_ai", not ai))
		loc = all(LOC in t.get("own_fields", []) for t in tasks)
		inherited = all(LOC in [f for f, src in self.fields_of(t) if src != "this task"] for t in tasks)
		m.add_command(label=("☑" if loc or inherited else "☐") + " 📍 Has location" + ("  (from its project / grouping)" if inherited and not loc else ""),
					  command=lambda: self.toggle_location(tasks), state="disabled" if inherited and not loc else "normal")
		if len(tasks) == 1 and LOC in [f for f, _ in self.fields_of(tasks[0])]:
			where = (tasks[0].get("fields") or {}).get(LOC)
			m.add_command(label="📍 Set the location..." + (f"  (now: {where[:30]})" if where else ""), command=lambda: self.set_location(tasks[0]))
		art = all(ART in t.get("own_fields", []) for t in tasks)
		art_inh = all(ART in [f for f, src in self.fields_of(t) if src != "this task"] for t in tasks)
		m.add_command(label=("☑" if art or art_inh else "☐") + " 🎨 Needs Icon/Art" + ("  (from its project / grouping)" if art_inh and not art else ""),
					  command=lambda: self.toggle_location(tasks, ART), state="disabled" if art_inh and not art else "normal")
		if len(tasks) == 1:
			m.add_command(label="🏷 Its own descriptors...", command=lambda: self.edit_own_fields(tasks[0]))
		if any(t.get("blocked") for t in tasks):
			m.add_command(label="Unblock", command=lambda: self.set_many(tasks, "blocked", ""))
		m.add_command(label="Blocked (reason)...", command=lambda: self.block(tasks))
		m.add_command(label="Blocked by (task dependencies)...", command=lambda: self.set_deps(tasks))
		m.add_separator()
		sub = tk.Menu(m, tearoff=0)
		cur = {t.get("project") or "" for t in tasks}
		for name in self.project_names() + [""]:
			sub.add_command(label=("● " if cur == {name} else "    ") + (name or NO_PROJECT), command=lambda n=name: self.set_project(tasks, n))
		sub.add_separator()
		sub.add_command(label="New project...", command=lambda: self.add_project(tasks))
		m.add_cascade(label="Project", menu=sub)
		m.add_command(label="📋 Bring to Agenda (next Dev VC)", command=lambda: self.tasks_to_agenda(tasks))
		if len(tasks) == 1 and tasks[0].get("idea") and self.idea_pane.idea(tasks[0]["idea"]):
			m.add_command(label="💡 Go to its idea (being fleshed out)", command=lambda: self.idea_pane.open_idea(tasks[0]["idea"]))
		if len(tasks) == 1:
			n = len(self.idea_pane.linked_ideas(task=tasks[0]["ref"]))
			m.add_command(label="💡 Add a linked idea...", command=lambda: self.idea_pane.add_linked(task=tasks[0]["ref"]))
			if n:
				m.add_command(label=f"💡 See its ideas ({n})", command=lambda: self.idea_pane.show_linked(task=tasks[0]["ref"]))
			m.add_command(label="+ Add a sub-task...", command=lambda: self.edit_task(new=True, parent=tasks[0]))
			m.add_command(label="+ New grouping (for its sub-tasks)...", command=lambda: self.add_groupings(tasks[0]))
		m.add_command(label="Sub-task of...", command=lambda: self.set_parent(tasks))
		if all(self.container(x) for x in tasks):
			sub = tk.Menu(m, tearoff=0)
			cur = {x.get("group") or "" for x in tasks}
			for g in self.groups_of({self.container(x) for x in tasks}) + [""]:
				sub.add_command(label=("● " if cur == {g} else "    ") + (g or "(no grouping)"), command=lambda g=g: self.set_many(tasks, "group", g))
			sub.add_separator()
			sub.add_command(label="New grouping...", command=lambda: self.new_group(tasks))
			m.add_cascade(label="Grouping", menu=sub)
		m.add_separator()
		if any(x.get("archived") or x.get("status") in CLOSED for x in tasks):
			m.add_command(label="↩ Restore from archive", command=lambda: self.unarchive(tasks))
		if any(not is_closed(x) for x in tasks):
			m.add_command(label="🗄 Archive...", command=lambda: self.archive(tasks))
		m.add_separator()
		sub = tk.Menu(m, tearoff=0)
		cur = {x.get("milestone") or "" for x in tasks}
		for ms in self.ms_order() + [""]:
			sub.add_command(label=("● " if cur == {ms} else "    ") + (self.ms_label(ms) if ms else "(no milestone)"), command=lambda ms=ms: self.set_many(tasks, "milestone", ms))
		sub.add_separator()
		sub.add_command(label="New milestone...", command=lambda: self.edit_milestone(None, tasks))
		m.add_cascade(label="Milestone", menu=sub)
		m.add_command(label="🖼 Icon...", command=lambda: self.pick_icon(tasks))
		m.add_command(label="⧉ Duplicate (with its sub-tasks)", command=lambda: self.duplicate(tasks))
		if len(tasks) == 1 and self.subtasks(tasks[0]):
			m.add_command(label="Save as template...", command=lambda: self.save_template(tasks[0]))
		m.add_command(label="🔗 Add a link...", command=lambda: self.add_link(tasks[0], "ask"))
		m.add_separator()
		m.add_command(label="Copy reference", command=lambda: self.copy_ref(False))
		m.add_command(label="Copy for a commit (RR-0000: title)", command=lambda: self.copy_ref(True))
		m.add_command(label="Edit...", command=self.edit_task)
		m.add_command(label="Delete...", command=lambda: self.delete(tasks))
		m.tk_popup(ev.x_root, ev.y_root)

	def refresh(self):
		self.save()
		self.fill_filters()
		self.fill()
		self.show_task()

	def set_many(self, tasks, field, value, note=None):
		follow_ups = []
		if field == "status" and value == "Completed":
			r = self.completion_prompt([t for t in tasks if t.get("status") != "Completed"])
			if r is None:
				return
			tasks, review, follow_ups = r
			if review:
				self.set_review(tasks)
				return
		n = sum(self.change(t, field, value, note) for t in tasks)
		if n:
			for draft in follow_ups:
				self.create_follow_up(draft)
			self.refresh()
			self.app.set_status(f"{n} task{'s' if n != 1 else ''}: {FIELD_NAMES.get(field, field)} -> {show_value(value)}")

	def claim(self, tasks):
		me = self.me.get()
		n = sum(self.change(t, "devs", devs_of(t) + [me], note="claimed") for t in tasks if t and me not in devs_of(t))
		if n:
			self.refresh()
			self.app.set_status(f"{me} claimed {n} task{'s' if n != 1 else ''}.")

	def leave(self, tasks):
		me = self.me.get()
		n = sum(self.change(t, "devs", [d for d in devs_of(t) if d != me], note="left the task") for t in tasks if t and me in devs_of(t))
		if n:
			self.refresh()

	def pick_devs(self, title, text, chosen):
		"""A dialog with a tick per dev; the ticked names (None when cancelled)."""
		w = tk.Toplevel(self)
		w.title(title)
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=text).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
		v = {}
		for i, n in enumerate(self.dev_names()):
			v[n] = tk.BooleanVar(value=n in chosen)
			ttk.Checkbutton(f, text=n, variable=v[n]).grid(row=1 + i // 3, column=i % 3, sticky="w", padx=(0, 16), pady=2)
		out = {}

		def ok(ev=None):
			out["v"] = [n for n in self.dev_names() if v[n].get()]
			w.destroy()
		bf = ttk.Frame(f)
		bf.grid(row=99, column=0, columnspan=3, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="OK", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)
		w.bind("<Return>", ok)
		w.grab_set()
		self.wait_window(w)
		return out.get("v")

	def share(self, tasks):
		tasks = [t for t in tasks if t]
		if not tasks:
			return
		chosen = set(devs_of(tasks[0])) if len(tasks) == 1 else set.intersection(*(set(devs_of(t)) for t in tasks))
		ds = self.pick_devs("Share with devs", f"Who works on {tasks[0]['ref'] if len(tasks) == 1 else f'these {len(tasks)} tasks'}? "
											  "(none = back to the General To Do)", chosen)
		if ds is not None:
			self.set_many(tasks, "devs", ds, note="shared")

	def pick_from(self, title, text, values, initial=None, entry=False):
		"""A small dialog: pick one of values (or type, with entry=True). None when cancelled."""
		w = tk.Toplevel(self)
		w.title(title)
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=text).pack(anchor="w")
		v = tk.StringVar(value=initial if initial is not None else (values[0] if values else ""))
		box = (ttk.Entry(f, textvariable=v, width=50, font="TkDefaultFont") if entry and not values else
			   ttk.Combobox(f, textvariable=v, values=values, width=40, state="normal" if entry else "readonly", font="TkDefaultFont"))
		box.pack(pady=6, fill="x")
		box.focus_set()
		out = {}

		def ok(ev=None):
			out["v"] = v.get().strip()
			w.destroy()
		w.bind("<Return>", ok)
		w.bind("<Escape>", lambda ev: w.destroy())
		bf = ttk.Frame(f)
		bf.pack(anchor="e")
		ttk.Button(bf, text="OK", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)
		w.grab_set()
		self.wait_window(w)
		return out.get("v")

	def set_review(self, tasks):
		devs = [d for d in self.dev_names() if not any(d in devs_of(t) for t in tasks)] or self.dev_names()
		r = self.pick_from("Ready for Review", "Reviewer (who checks it):", ["(nobody yet)"] + devs,
						   tasks[0].get("reviewer") or "(nobody yet)")
		if r is None:
			return
		for t in tasks:
			self.change(t, "status", "Ready for Review")
			self.change(t, "reviewer", "" if r == "(nobody yet)" else r)
		self.refresh()

	def pass_on(self, tasks):
		"""Passed to Another Dev: the new dev takes your place (or everyone's, when you aren't on it)."""
		me = self.me.get()
		devs = [d for d in self.dev_names() if not all(d in devs_of(t) for t in tasks)]
		to = self.pick_from("Passed to Another Dev", "Pass to:", devs)
		if not to:
			return
		for t in tasks:
			was = devs_of(t)
			new = [to if d == me else d for d in was] if me in was else [to]
			self.change(t, "status", "Passed to Another Dev", note=f"from {', '.join(was) or 'nobody'} to {to}")
			self.change(t, "devs", list(dict.fromkeys(new)))
		self.refresh()

	def block(self, tasks):
		r = self.pick_from("Blocked", "Why is it blocked?", [], tasks[0].get("blocked", ""), entry=True)
		if r:
			self.set_many(tasks, "blocked", r)

	def task_list(self, parent, exclude, chosen, height=10):
		"""The tasks to pick "blocked by" from, by project (folded unless one of theirs is ticked), with tick boxes,
		a project filter, search and column sorting: (frame, a function giving the ticked refs)."""
		picked = set(chosen)
		box = ttk.Frame(parent)
		top = ttk.Frame(box)
		top.pack(fill="x", pady=(0, 4))
		ttk.Label(top, text="Project", style="Muted.TLabel").pack(side="left")
		pv = tk.StringVar(value=ALL)
		names = self.project_names() + [NO_PROJECT]
		ttk.Combobox(top, textvariable=pv, values=[ALL] + names, state="readonly", width=22, font="TkDefaultFont").pack(side="left", padx=(4, 12))
		ttk.Label(top, text="🔍").pack(side="left")
		q = tk.StringVar()
		ttk.Entry(top, textvariable=q, width=24, font="TkDefaultFont").pack(side="left", padx=4)
		only = tk.BooleanVar(value=False)
		ttk.Checkbutton(top, text="Only the ticked ones", variable=only).pack(side="left", padx=8)
		count = ttk.Label(top, text="", style="Muted.TLabel")
		count.pack(side="right")
		tf = ttk.Frame(box, width=ui.px(640), height=ui.px(22 * height + 30))
		tf.pack_propagate(False)
		tf.pack(fill="both", expand=True)
		t = ttk.Treeview(tf, columns=("pick", "ref", "devs", "status"), selectmode="browse")
		ys = ttk.Scrollbar(tf, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		sort = {"k": "ref", "rev": False}
		for col, text, w, stretch in (("#0", "Task", 300, True), ("pick", "✓", 34, False), ("ref", "Ref", 75, False),
									  ("devs", "Dev(s)", 130, False), ("status", "Status", 120, False)):
			t.heading(col, text=text, command=lambda c=col: by(c))
			t.column(col, width=ui.px(w), stretch=stretch, anchor="center" if col == "pick" else "w")
		t.tag_configure("project", font="om_bold")
		t.tag_configure("ticked", foreground="#1f5fa8", font="om_bold")
		t.tag_configure("closed", foreground="#888")
		cands = [o for o in self.tasks if o["ref"] not in exclude]

		def key(o):
			k = sort["k"]
			if k == "#0":
				return o.get("title", "").lower()
			if k == "pick":
				return o["ref"] not in picked
			if k == "devs":
				return ", ".join(devs_of(o)).lower() or "~"
			if k == "status":
				return STATUSES.index(o["status"]) if o.get("status") in STATUSES else 0
			return int(re.sub(r"\D", "", o["ref"]) or 0)

		def fill(*_):
			opened = {i for i in t.get_children() if t.item(i, "open")}
			t.delete(*t.get_children())
			words = q.get().lower().split()
			for name in names:
				if pv.get() != ALL and pv.get() != name:
					continue
				rows = [o for o in cands if (o.get("project") or NO_PROJECT) == name
						and (not only.get() or o["ref"] in picked)
						and all(w in f"{o['ref']} {o.get('title', '')} {' '.join(devs_of(o))}".lower() for w in words)]
				if not rows:
					continue
				n = sum(1 for o in rows if o["ref"] in picked)
				pid = "proj:" + name
				t.insert("", "end", iid=pid, text=f" {name}  ({len(rows)})", image=self.project_icon(name), values=(f"{n}" if n else "", "", "", ""),
						 tags=self.project_tags(name, tree=t),
						 open=bool(n) or bool(words) or pv.get() == name or pid in opened)
				for o in sorted(rows, key=key, reverse=sort["rev"]):
					on = o["ref"] in picked
					t.insert(pid, "end", iid=o["ref"], text=o.get("title", ""), values=("☑" if on else "☐", o["ref"], ", ".join(devs_of(o)) or "-", o.get("status", "")),
							 tags=("ticked",) if on else ("closed",) if is_closed(o) else ())
			count.config(text=f"{len(picked)} ticked")
			for col, text in (("#0", "Task"), ("pick", "✓"), ("ref", "Ref"), ("devs", "Dev(s)"), ("status", "Status")):
				t.heading(col, text=text + ((" ▼" if sort["rev"] else " ▲") if sort["k"] == col else ""))

		def by(col):
			sort["rev"] = not sort["rev"] if sort["k"] == col else False
			sort["k"] = col
			fill()

		def click(ev):
			row = t.identify_row(ev.y)
			if not row or row.startswith("proj:"):
				return
			picked.symmetric_difference_update({row})
			on = row in picked
			t.set(row, "pick", "☑" if on else "☐")
			t.item(row, tags=("ticked",) if on else ())
			par = t.parent(row)
			n = sum(1 for c in t.get_children(par) if c in picked)
			t.set(par, "pick", f"{n}" if n else "")
			count.config(text=f"{len(picked)} ticked")
		t.bind("<ButtonRelease-1>", click)
		pv.trace_add("write", fill)
		q.trace_add("write", fill)
		only.trace_add("write", fill)
		fill()
		ttk.Label(box, text="Click a task to tick / untick it. Click a column title to sort.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
		return box, lambda: sorted(picked, key=lambda r: int(re.sub(r"\D", "", r) or 0))

	def set_deps(self, tasks):
		refs = {t["ref"] for t in tasks}
		w = tk.Toplevel(self)
		w.title("Task dependencies")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text=f"{', '.join(sorted(refs))} is blocked by (can only be done after):").pack(anchor="w")
		lb, get = self.task_list(f, refs, set(tasks[0].get("depends_on", [])), 16)
		lb.pack(fill="both", expand=True, pady=6)

		def ok():
			deps = get()
			w.destroy()
			for t in tasks:
				self.change(t, "depends_on", deps)
			self.refresh()
		bf = ttk.Frame(f)
		bf.pack(anchor="e")
		ttk.Button(bf, text="OK", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	# ---------- projects / sub-tasks ----------
	def project_names(self):
		projects = self.data["projects"]
		last = max((p["list_order"] for p in projects if isinstance(p.get("list_order"), (int, float))), default=-1)
		return [p["name"] for _, p in sorted(enumerate(projects),
			key=lambda item: (item[1].get("list_order") if isinstance(item[1].get("list_order"), (int, float)) else last + 1 + item[0], item[0]))]

	def project(self, name):
		return next((p for p in self.data["projects"] if p["name"] == name), None)

	def container(self, t):
		"""Where a task sits directly: under its parent task (its ref), else in its project ("proj:<name>"), else nowhere."""
		if t.get("parent"):
			return t["parent"]
		return "proj:" + t["project"] if t.get("project") and self.project(t["project"]) else None

	def holder(self, key):
		"""The task or project a grouping belongs to (its "groupings", "group_icons")."""
		return self.project(key[5:]) if key and key.startswith("proj:") else self.task(key)

	def in_container(self, c, key):
		return self.container(c) == key

	def groups_of(self, keys):
		"""The groupings of these tasks / projects (kept on them, and used by what's in them)."""
		out = []
		for k in keys:
			out += (self.holder(k) or {}).get("groupings", [])
		out += sorted({c["group"] for c in self.tasks if self.container(c) in keys and c.get("group")}, key=str.lower)
		return list(dict.fromkeys(out))

	def keep_group(self, key, g):
		p = self.holder(key)
		if p is not None and g and g not in p.setdefault("groupings", []):
			p["groupings"].append(g)

	def new_group(self, tasks):
		g = (simpledialog.askstring("New grouping", "Grouping (e.g. Europe):", parent=self) or "").strip()
		if g:
			for x in tasks:
				self.keep_group(self.container(x), g)
			self.set_many(tasks, "group", g)

	def add_groupings(self, parent, key=None):
		"""+ New grouping on a task (for its sub-tasks) or a project (for its tasks): empty folders, one per line."""
		key = key or parent["ref"]
		w = tk.Toplevel(self)
		w.title("New grouping")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=f"Groupings in {parent.get('title') or parent.get('name', '')} (one per line):").pack(anchor="w")
		box = tk.Text(f, width=40, height=6, font="om_body")
		box.pack(pady=6)
		box.focus_set()

		def ok():
			names = [l.strip() for l in box.get("1.0", "end").splitlines() if l.strip()]
			w.destroy()
			for g in names:
				self.keep_group(key, g)
			if names:
				self.refresh()
		ttk.Button(f, text="Add", command=ok).pack(side="right")

	def group_menu(self, ev, parent_ref, group):
		members = [c for c in self.tasks if self.container(c) == parent_ref and c.get("group") == group]
		m = tk.Menu(self, tearoff=0)
		m.add_command(label=f"🗂 {group}  ({len(members)})", state="disabled")
		if parent_ref.startswith("proj:"):
			m.add_command(label="+ New task in it...", command=lambda: self.edit_task(new=True, project=parent_ref[5:], group=group))
		else:
			m.add_command(label="+ New sub-task in it...", command=lambda: self.edit_task(new=True, parent=self.task(parent_ref), group=group))
		m.add_command(label="Rename the grouping...", command=lambda: self.rename_group(parent_ref, members, group))
		m.add_command(label="🖼 Icon...", command=lambda: self.pick_group_icon(parent_ref, group))
		n = len(((self.holder(parent_ref) or {}).get("group_fields") or {}).get(group, []))
		m.add_command(label="🏷 Descriptors for its tasks..." + (f"  ({n})" if n else ""), command=lambda: self.edit_group_fields(parent_ref, group))
		m.add_command(label="Remove the grouping (its tasks stay)", command=lambda: self.remove_group(parent_ref, members, group))
		m.tk_popup(ev.x_root, ev.y_root)

	def remove_group(self, parent_ref, members, g):
		p = self.holder(parent_ref)
		if p is not None and g in p.get("groupings", []):
			p["groupings"].remove(g)
		for c in members:
			self.change(c, "group", "")
		self.refresh()

	def rename_group(self, parent_ref, members, old):
		g = (simpledialog.askstring("Rename grouping", "New name:", initialvalue=old, parent=self) or "").strip()
		if g and g != old:
			gid_old = f"grp:{parent_ref}:{old}"
			if gid_old in getattr(self, "_open", {}):
				self._open[f"grp:{parent_ref}:{g}"] = self._open[gid_old]
			p = self.holder(parent_ref)
			if p is not None and old in (p.get("group_notes") or {}):
				p["group_notes"][g] = p["group_notes"].pop(old)
			if p is not None and old in (p.get("group_fields") or {}):
				p["group_fields"][g] = p["group_fields"].pop(old)
			if p is not None:
				gs = p.setdefault("groupings", [])
				p["groupings"] = [g if x == old else x for x in gs] if old in gs else gs + [g]
			for c in members:
				self.change(c, "group", g)
			self.refresh()

	def archive(self, tasks):
		"""Into the archive, with a reason (Completed and Impossible also set the status); open sub-tasks can go too."""
		tasks = [x for x in tasks if x and not is_closed(x)]
		if not tasks:
			return
		subs = []
		for x in tasks:
			subs += [c for c in self.tasks if self.is_below(c, x) and not is_closed(c) and c not in tasks and c not in subs]
		w = tk.Toplevel(self)
		w.title("Archive")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		what = f"{tasks[0]['ref']}  {tasks[0].get('title', '')}" if len(tasks) == 1 else f"{len(tasks)} tasks"
		ttk.Label(f, text=f"Archive {what}", style="Head.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
		ttk.Label(f, text="Why?", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
		reason = tk.StringVar(value="Completed")
		other = tk.StringVar()
		oe = ttk.Entry(f, textvariable=other, width=34, font="TkDefaultFont", state="disabled")
		for i, r in enumerate(ARCHIVE_REASONS):
			ttk.Radiobutton(f, text=r, variable=reason, value=r,
							command=lambda: oe.config(state="normal" if reason.get() == "Other" else "disabled")).grid(row=2 + i, column=0, sticky="w")
		oe.grid(row=2 + len(ARCHIVE_REASONS) - 1, column=1, sticky="w", padx=(6, 0))
		r = 2 + len(ARCHIVE_REASONS)
		ttk.Label(f, text="Note (optional, e.g. which task it duplicates)", style="Muted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
		note = tk.StringVar()
		ttk.Entry(f, textvariable=note, width=50, font="TkDefaultFont").grid(row=r + 1, column=0, columnspan=2, sticky="we")
		with_subs = tk.BooleanVar(value=True)
		if subs:
			ttk.Checkbutton(f, text=f"Also archive its {len(subs)} open sub-task{'s' if len(subs) != 1 else ''}", variable=with_subs).grid(
				row=r + 2, column=0, columnspan=2, sticky="w", pady=(8, 0))

		def ok(ev=None):
			why = other.get().strip() if reason.get() == "Other" else reason.get()
			if not why:
				messagebox.showerror(APP_NAME, "Write the reason (Other).", parent=w)
				return
			w.destroy()
			todo = tasks + (subs if with_subs.get() else [])
			for x in todo:
				if reason.get() == "Completed":
					self.change(x, "status", "Completed")
				elif reason.get() == "Impossible":
					self.change(x, "status", "Not Possible")
				self.change(x, "archived", why, note=note.get().strip() or None)
				if note.get().strip():
					x["archive_note"] = note.get().strip()
				x.setdefault("closed", stamp())
			self.refresh()
			self.app.set_status(f"Archived {len(todo)} task{'s' if len(todo) != 1 else ''}: {why}.")
		w.bind("<Return>", ok)
		bf = ttk.Frame(f)
		bf.grid(row=r + 3, column=0, columnspan=2, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="Archive", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def unarchive(self, tasks):
		"""Back out of the archive (a Completed / Not Possible one goes back to To do)."""
		n = 0
		for x in tasks:
			if x.get("archived"):
				n += self.change(x, "archived", "", note="restored")
				x.pop("archive_note", None)
			if x.get("status") in CLOSED:
				n += self.change(x, "status", TODO, note="restored")
			if not is_closed(x):
				x.pop("closed", None)
		if n:
			self.refresh()

	# ---------- ready / unblocked ----------
	def waiting_on(self, t):
		return [r for r in t.get("depends_on", []) if self.task(r) and not is_closed(self.task(r))]

	def ready(self, t):
		"""Yours, open, not blocked, nothing it waits for, not still being planned."""
		return (self.me.get() in devs_of(t) and not is_closed(t) and not t.get("blocked") and not t.get("needs_planning")
				and not self.waiting_on(t))

	def unblocked_now(self, t):
		"""Its blockers were all finished since you last closed the tool."""
		if not self.last_open or is_closed(t) or not t.get("depends_on") or self.waiting_on(t):
			return False
		done = [self.task(r).get("closed", "") for r in t["depends_on"] if self.task(r)]
		return bool(done) and max(done) > self.last_open

	def update_unblocked(self):
		n = [t for t in self.tasks if self.unblocked_now(t)]
		if n:
			self.unblocked_btn.config(text=f"🔓 {len(n)} task{'s' if len(n) != 1 else ''} unblocked since you last looked")
			self.unblocked_btn.pack(side="right")
		else:
			self.unblocked_btn.pack_forget()

	def show_unblocked(self):
		m = tk.Menu(self, tearoff=0)
		for t in [t for t in self.tasks if self.unblocked_now(t)]:
			m.add_command(label=f"{t['ref']}  {t.get('title', '')}  ({', '.join(devs_of(t)) or 'nobody'})", command=lambda r=t["ref"]: self.go_to(r))
		m.tk_popup(self.unblocked_btn.winfo_rootx(), self.unblocked_btn.winfo_rooty() + self.unblocked_btn.winfo_height())

	# ---------- your own order (My next task) ----------
	def next_order(self, rows):
		"""My next task's order: your numbered tasks first (by number), then the rest so that whatever blocks a task
		(a blocker, or an unfinished sub-task) comes before it; ties by priority, then age."""
		mine = self.my_numbers()
		num = sorted((x for x in rows if mine.get(x["ref"])), key=lambda x: mine[x["ref"]])
		rest = [x for x in rows if x not in num]
		refs = {x["ref"] for x in rest}
		rank = lambda x: (-PRIORITY_WEIGHT.get(x.get("priority", "Normal"), 2), -age_of(x).total_seconds())
		before = {x["ref"]: {r for r in self.waiting_on(x) if r in refs} | {c["ref"] for c in self.tasks if c.get("parent") == x["ref"]
																			  and c["ref"] in refs and not is_closed(c)} for x in rest}
		out, left = [], sorted(rest, key=rank)
		while left:
			free = [x for x in left if not (before[x["ref"]] - {o["ref"] for o in out})]
			x = free[0] if free else left[0]  # (a loop of blocks: just the next one)
			out.append(x)
			left.remove(x)
		return num + out

	def my_numbers(self):
		"""Your own My next task numbers {ref: n}: in Organisation Master's settings on this PC (per dev), not the shared file."""
		return self.app.config.setdefault("todo_order", {}).setdefault(self.me.get(), {})

	def shown_mine(self):
		return [self.task(i) for i in self.tree.get_children() if self.task(i)]

	def number_mine(self, order):
		for i, x in enumerate(order, start=1):
			self.my_numbers()[x["ref"]] = i

	def move_mine(self, d):
		"""↑ Earlier / ↓ Later: the list as it is gets numbered, then the picked task moves."""
		sel = [r for r in self.tree.selection() if self.task(r)]
		order = self.shown_mine()
		if not sel or self.view.get() != "next":
			return
		x = self.task(sel[0])
		i = order.index(x)
		j = max(0, min(len(order) - 1, i + d))
		if i == j:
			return
		order.insert(j, order.pop(i))
		self.number_mine(order)
		self.app.save_config()
		self.fill()
		self.tree.selection_set(x["ref"])
		self.tree.see(x["ref"])

	def set_my_number(self, x):
		order = self.shown_mine()
		n = simpledialog.askinteger("My number", f"Where in your list does {x.get('title', '')} go? (1 = first)", parent=self,
									minvalue=1, maxvalue=len(order), initialvalue=order.index(x) + 1)
		if n:
			order.remove(x)
			order.insert(n - 1, x)
			self.number_mine(order)
			self.app.save_config()
			self.fill()
			self.tree.selection_set(x["ref"])

	def clear_my_numbers(self):
		for x in self.tasks:
			self.my_numbers().pop(x["ref"], None)
		self.app.save_config()
		self.fill()

	def go_to(self, ref):
		"""Show a task in the list (its folders opened) and pick it."""
		t = self.task(ref)
		if not t:
			return
		if not self.in_view(t):
			self.view.set("archive" if is_closed(t) else "open")
		if not self.shown(t):  # (only when the filters hide it: else they stay as they are)
			for v in self.f.values():
				v.set(ALL)
			self.search.set("")
		self.fill()
		if self.tree.exists(ref):
			p = self.tree.parent(ref)
			while p:
				self.tree.item(p, open=True)
				p = self.tree.parent(p)
			self.tree.selection_set(ref)
			self.tree.see(ref)

	# ---------- random task ----------
	def random_task(self):
		"""A random task to pick up: claimable or yours and ready, weighted by priority (and a little by age)."""
		pool = [t for t in self.tasks if not is_closed(t) and not t.get("blocked") and not self.waiting_on(t) and not self.subtasks(t)
				and (lane(t) in ("general", "music") or self.ready(t))]
		if not pool:
			messagebox.showinfo(APP_NAME, "Nothing to pick from: no open, unblocked task is free or yours.")
			return
		weights = [PRIORITY_WEIGHT.get(t.get("priority", "Normal"), 2) * (1 + min(age_of(t).days, 180) / 90) for t in pool]
		t = random.choices(pool, weights=weights)[0]
		w = tk.Toplevel(self)
		w.title("🎲 Random task")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=14)
		f.pack()
		ttk.Label(f, text=f"{t['ref']}   {t.get('title', '')}", style="Title.TLabel", wraplength=ui.px(520)).pack(anchor="w")
		ttk.Label(f, text=f"{t.get('project') or NO_PROJECT}{' · ' + t['group'] if t.get('group') else ''}   ·   {t.get('priority')} priority   ·   "
						  f"{t.get('category', '')}   ·   age {fmt_age(age_of(t))}   ·   {', '.join(devs_of(t)) or 'nobody yet'}",
				  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
		if t.get("setter_note"):
			ttk.Label(f, text=t["setter_note"], wraplength=ui.px(520), justify="left").pack(anchor="w", pady=(6, 0))
		bf = ttk.Frame(f)
		bf.pack(anchor="e", pady=(12, 0))
		if self.me.get() not in devs_of(t):
			ttk.Button(bf, text=f"✋ Claim it ({self.me.get()})", command=lambda: (w.destroy(), self.claim([t]), self.go_to(t["ref"]))).pack(side="left")
		ttk.Button(bf, text="🎲 Another one", command=lambda: (w.destroy(), self.random_task())).pack(side="left", padx=4)
		ttk.Button(bf, text="Show it", command=lambda: (w.destroy(), self.go_to(t["ref"]))).pack(side="left")

	# ---------- many tasks at once: lines, templates, bulk ----------
	def create_from_lines(self, lines, common, parent=None):
		"""Tasks from lines (an indented line is a sub-task of the line above it); common: project, category, devs..."""
		made, stack = [], []  # stack: (indent, task)
		for raw in lines:
			if not raw.strip():
				continue
			ind = len(raw.replace("\t", "    ")) - len(raw.replace("\t", "    ").lstrip())
			while stack and stack[-1][0] >= ind:
				stack.pop()
			par = stack[-1][1]["ref"] if stack else (parent["ref"] if parent else "")
			t = self.add_task(raw.strip().lstrip("-*• ").strip(), **dict(common, parent=par))
			made.append(t)
			stack.append((ind, t))
		return made

	def common_fields(self, f, row, project="", devs=(), category=None, priority="Normal"):
		"""Project / category / priority / devs fields for a dialog: (row after them, a function giving their values)."""
		pv = tk.StringVar(value=project or NO_PROJECT)
		cv = tk.StringVar(value=category if category in self.data["categories"] else (self.data["categories"][0] if self.data["categories"] else ""))
		prv = tk.StringVar(value=priority if priority in PRIORITIES else "Normal")
		for i, (text, var, vals) in enumerate((("Project", pv, self.project_names() + [NO_PROJECT]), ("Category", cv, self.data["categories"]),
											   ("Priority", prv, PRIORITIES))):
			ttk.Label(f, text=text, style="Muted.TLabel").grid(row=row + i, column=0, sticky="w", pady=2)
			ttk.Combobox(f, textvariable=var, values=vals, state="readonly", width=28, font="TkDefaultFont").grid(row=row + i, column=1, sticky="w")
		row += 3
		ttk.Label(f, text="Dev(s)", style="Muted.TLabel").grid(row=row, column=0, sticky="nw", pady=2)
		dvf = ttk.Frame(f)
		dvf.grid(row=row, column=1, sticky="w")
		dv = {}
		for i, n in enumerate(self.dev_names()):
			dv[n] = tk.BooleanVar(value=n in devs)
			ttk.Checkbutton(dvf, text=n, variable=dv[n]).grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 12))
		return row + 1, lambda: {"project": "" if pv.get() == NO_PROJECT else pv.get(), "category": cv.get(), "priority": prv.get(),
								 "devs": [n for n in self.dev_names() if dv[n].get()]}

	def from_template(self, project=""):
		names = list(self.data["templates"])
		if not names:
			self.edit_templates()
			return
		w = tk.Toplevel(self)
		w.title("New task from a template")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack()
		tv = tk.StringVar(value=names[0])
		nv = tk.StringVar()
		ttk.Label(f, text="Template", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=2)
		ttk.Combobox(f, textvariable=tv, values=names, state="readonly", width=28, font="TkDefaultFont").grid(row=0, column=1, sticky="w")
		ttk.Label(f, text="For (e.g. Liangshan)", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=2)
		e = ttk.Entry(f, textvariable=nv, width=40, font="TkDefaultFont")
		e.grid(row=1, column=1, sticky="w")
		e.focus_set()
		preview = ttk.Label(f, text="", style="Muted.TLabel", justify="left")
		row, get = self.common_fields(f, 2, project)
		preview.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
		tv.trace_add("write", lambda *_: preview.config(text="Sub-tasks: " + ", ".join(l.strip() for l in self.data["templates"].get(tv.get(), [])[:12])))
		tv.set(tv.get())

		def ok(ev=None):
			c = get()
			title = f"{tv.get()}: {nv.get().strip()}" if nv.get().strip() else tv.get()
			w.destroy()
			top = self.add_task(title, **c)
			self.create_from_lines(self.data["templates"][tv.get()], c, top)
			self.refresh()
			self.go_to(top["ref"])
			self.app.set_status(f"{top['ref']} {title} with {len(self.subtasks(top))} sub-tasks.")
		w.bind("<Return>", ok)
		ttk.Button(f, text="Create", command=ok).grid(row=row + 1, column=1, sticky="e", pady=(10, 0))

	def edit_templates(self):
		w = tk.Toplevel(self)
		w.title("Task templates")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		lb = tk.Listbox(f, width=24, height=14, exportselection=False, font="om_body")
		lb.grid(row=0, column=0, rowspan=3, sticky="ns")
		box = tk.Text(f, width=56, height=16, font="om_body", wrap="none")
		box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
		ttk.Label(f, text="One sub-task per line; indent a line (Tab) to make it a sub-task of the line above.", style="Muted.TLabel").grid(
			row=1, column=1, sticky="w", padx=(8, 0))
		cur = {"n": None}

		def keep():
			if cur["n"] in self.data["templates"]:
				self.data["templates"][cur["n"]] = [l.rstrip() for l in box.get("1.0", "end").splitlines() if l.strip()]

		def refill(pick=None):
			lb.delete(0, "end")
			for n in self.data["templates"]:
				lb.insert("end", n)
			names = list(self.data["templates"])
			if pick in names:
				lb.selection_set(names.index(pick))
				show()

		def show(ev=None):
			keep()
			sel = lb.curselection()
			cur["n"] = lb.get(sel[0]) if sel else None
			box.delete("1.0", "end")
			if cur["n"]:
				box.insert("1.0", "\n".join(self.data["templates"][cur["n"]]))
		lb.bind("<<ListboxSelect>>", show)

		def new():
			keep()
			n = (simpledialog.askstring("New template", "Name of the template:", parent=w) or "").strip()
			if n and n not in self.data["templates"]:
				self.data["templates"][n] = []
				cur["n"] = None
				refill(n)

		def delete():
			if cur["n"] and messagebox.askyesno(APP_NAME, f"Delete the template {cur['n']}?", parent=w):
				del self.data["templates"][cur["n"]]
				cur["n"] = None
				box.delete("1.0", "end")
				refill()

		def close():
			keep()
			self.save()
			w.destroy()
		bf = ttk.Frame(f)
		bf.grid(row=2, column=1, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="New...", command=new).pack(side="left")
		ttk.Button(bf, text="Delete", command=delete).pack(side="left", padx=4)
		ttk.Button(bf, text="Save and close", command=close).pack(side="left")
		w.protocol("WM_DELETE_WINDOW", close)
		refill(next(iter(self.data["templates"]), None))

	def save_template(self, t):
		"""A task's sub-tasks (and theirs, indented) as a template."""
		n = (simpledialog.askstring("Save as template", "Name of the template:", initialvalue=t.get("title", ""), parent=self) or "").strip()
		if not n:
			return
		lines = []

		def walk(x, depth):
			for c in sorted(self.subtasks(x), key=lambda c: int(re.sub(r"\D", "", c["ref"]) or 0)):
				lines.append("\t" * depth + c.get("title", ""))
				walk(c, depth + 1)
		walk(t, 0)
		self.data["templates"][n] = lines
		self.save()
		self.app.set_status(f"Template {n}: {len(lines)} lines.")

	def bulk_add(self):
		w = tk.Toplevel(self)
		w.title("Bulk add")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text="One task per line (indent a line to make it a sub-task of the line above):").grid(row=0, column=0, columnspan=2, sticky="w")
		box = tk.Text(f, width=70, height=12, font="om_body", wrap="none")
		box.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 8))
		box.focus_set()
		fp = self.f["project"].get() if self.mode.get() == "project" else ALL
		row, get = self.common_fields(f, 2, fp if fp not in (ALL, NO_PROJECT) else "")
		ttk.Label(f, text="Under task", style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=2)
		opts = ["(none: top-level tasks)"] + [f"{o['ref']}  {o.get('title', '')}" for o in self.tasks if not is_closed(o)]
		uv = tk.StringVar(value=opts[0])
		ttk.Combobox(f, textvariable=uv, values=opts, state="readonly", width=56, font="TkDefaultFont").grid(row=row, column=1, sticky="w")
		ttk.Label(f, text="Grouping", style="Muted.TLabel").grid(row=row + 1, column=0, sticky="w", pady=2)
		gv = tk.StringVar()
		ttk.Entry(f, textvariable=gv, width=28, font="TkDefaultFont").grid(row=row + 1, column=1, sticky="w")

		def ok():
			lines = box.get("1.0", "end").splitlines()
			if not any(l.strip() for l in lines):
				return
			c = get()
			parent = None if uv.get().startswith("(") else self.task(uv.get().split()[0])
			if parent is not None and not c["project"]:
				c["project"] = parent.get("project", "")
			w.destroy()
			made = self.create_from_lines(lines, c, parent)
			if gv.get().strip() and parent is not None:
				self.keep_group(parent["ref"], gv.get().strip())
				for t in made:
					if t.get("parent") == parent["ref"]:
						t["group"] = gv.get().strip()
			self.refresh()
			self.app.set_status(f"{len(made)} tasks added ({made[0]['ref']} - {made[-1]['ref']}).")
		ttk.Button(f, text="Add them", command=ok).grid(row=row + 2, column=1, sticky="e", pady=(10, 0))

	# ---------- duplicate ----------
	def copy_tree(self, roots, project=None, suffix=" (copy)"):
		"""Copies of tasks with all their sub-tasks; blockers inside the copied set point at the copies."""
		todo = []
		for r in roots:
			todo += [x for x in [r] + [c for c in self.tasks if self.is_below(c, r)] if x not in todo]
		new_ref = {x["ref"]: self.new_ref() for x in todo}
		now = stamp()
		made = []
		for x in todo:
			n = copy.deepcopy(x)
			for k in ("archived", "archive_note", "closed", "link", "reviewer"):
				n.pop(k, None)
			n.update(ref=new_ref[x["ref"]], status=TODO, created=now, updated=now, set_by=self.me.get(),
					 parent=new_ref.get(x.get("parent"), x.get("parent", "")),
					 depends_on=[new_ref.get(r, r) for r in x.get("depends_on", [])],
					 history=[{"when": now, "who": self.me.get(), "field": "created", "old": None, "new": None, "note": f"copy of {x['ref']}"}])
			if x in roots:
				n["title"] = x.get("title", "") + suffix
			if project is not None:
				n["project"] = project
			self.tasks.append(n)
			made.append(n)
		return made

	def duplicate(self, tasks):
		roots = [t for t in tasks if not any(self.is_below(t, o) for o in tasks)]
		made = self.copy_tree(roots)
		self.refresh()
		self.go_to(made[0]["ref"])
		self.app.set_status(f"Copied {len(made)} task{'s' if len(made) != 1 else ''}.")

	def duplicate_project(self, name):
		p = self.project(name)
		new = (simpledialog.askstring("Duplicate project", "Name of the copy:", initialvalue=f"{name} (copy)", parent=self) or "").strip()
		if not p or not new:
			return
		if new in self.project_names():
			messagebox.showerror(APP_NAME, f"There's already a project called {new}.")
			return
		q = copy.deepcopy(p)
		q.update(name=new, set_by=self.me.get(), created=stamp())
		self.data["projects"].append(q)
		mine = [t for t in self.tasks if t.get("project") == name]
		roots = [t for t in mine if (self.task(t.get("parent")) or {}).get("project") != name]
		made = self.copy_tree(roots, project=new, suffix="")
		self.refresh()
		self.app.set_status(f"Project {new}: {len(made)} tasks copied from {name}.")

	# ---------- finishing ----------
	def completion_prompt(self, tasks, assignments=None):
		"""Completing: unfinished sub-tasks are flagged, and it can go for review instead.
		-> (tasks to complete, review?, follow-up drafts) or None (cancelled)."""
		if not tasks:
			return tasks, False, []
		subs = []
		for x in tasks:
			subs += [c for c in self.tasks if self.is_below(c, x) and not is_closed(c) and c not in tasks and c not in subs]
		w = tk.Toplevel(self)
		w.title("Complete")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		tabs = ttk.Notebook(f)
		tabs.pack(fill="both", expand=True)
		summary = ttk.Frame(tabs, padding=8)
		tabs.add(summary, text="Completion")
		what = f"{tasks[0]['ref']}  {tasks[0].get('title', '')}" if len(tasks) == 1 else f"{len(tasks)} tasks"
		ttk.Label(summary, text=f"Complete {what}?", style="Head.TLabel").pack(anchor="w")
		credit = ttk.Frame(summary)
		credit.pack(fill="x", pady=(8, 0))
		ttk.Label(credit, text="Completed by").pack(side="left", padx=(0, 8))
		keep_credit = "Assigned devs (you if unassigned)"
		completed_by = tk.StringVar(value=keep_credit)
		ttk.Combobox(credit, textvariable=completed_by, values=[keep_credit] + self.dev_names(), state="readonly", width=34).pack(side="left")
		also = tk.BooleanVar(value=False)
		if subs:
			ttk.Label(summary, text=f"⚠ {len(subs)} sub-task{'s are' if len(subs) != 1 else ' is'} not finished:", foreground="#b06f00").pack(anchor="w", pady=(6, 0))
			ttk.Label(summary, text="\n".join(f"   {c['ref']}  {c.get('title', '')}  ({c.get('status')})" for c in subs[:10])
							  + ("\n   ..." if len(subs) > 10 else ""), justify="left").pack(anchor="w")
			ttk.Checkbutton(summary, text="Complete them too", variable=also).pack(anchor="w", pady=(4, 0))
		out = {}
		drafts = []
		serial = 0
		bar = ttk.Frame(f)
		bar.pack(fill="x", pady=(8, 0))

		def add_follow_up():
			nonlocal serial
			serial += 1
			options = ttk.Frame(tabs, padding=8)
			source = tk.StringVar(value=tasks[0]["ref"])
			row = 0
			if len(tasks) > 1:
				ttk.Label(options, text="Follow up to", style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8))
				choices = [f"{t['ref']}  {t.get('title', '')}" for t in tasks]
				source.set(choices[0])
				ttk.Combobox(options, textvariable=source, values=choices, state="readonly", width=50).grid(row=row, column=1, sticky="ew")
				row += 1
			title = tk.StringVar()
			ttk.Label(options, text="Follow-up task", style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
			entry = ttk.Entry(options, textvariable=title, width=52)
			entry.grid(row=row, column=1, sticky="ew")
			row, get_fields = self.common_fields(options, row + 1, tasks[0].get("project", ""), devs_of(tasks[0]),
												 category=tasks[0].get("category"), priority=tasks[0].get("priority", "Normal"))
			needs_ai = tk.BooleanVar(value=False)
			ttk.Checkbutton(options, text="🤖 Requires AI", variable=needs_ai).grid(row=row, column=1, sticky="w", pady=4)
			row += 1
			ttk.Label(options, text="Note", style="Muted.TLabel").grid(row=row, column=0, sticky="nw", pady=4)
			note = tk.Text(options, width=52, height=3, wrap="word", font="om_body", undo=True)
			note.grid(row=row, column=1, sticky="ew", pady=4)
			ttk.Label(options, text="Linked to the completed task in the archive.", style="Muted.TLabel").grid(row=row + 1, column=0, columnspan=2, sticky="w")
			drafts.append(dict(frame=options, title=title, entry=entry, fields=get_fields, source=source, note=note, needs_ai=needs_ai))
			tabs.add(options, text=f"Follow-up {serial}")
			tabs.select(options)
			entry.focus_set()

		def remove_follow_up():
			selected = tabs.select()
			for draft in drafts:
				if str(draft["frame"]) == selected:
					tabs.forget(draft["frame"])
					draft["frame"].destroy()
					drafts.remove(draft)
					break

		ttk.Button(bar, text="+ Add follow-up", command=add_follow_up).pack(side="left")
		remove = ttk.Button(bar, text="Remove follow-up", command=remove_follow_up, state="disabled")
		remove.pack(side="left", padx=4)
		tabs.bind("<<NotebookTabChanged>>", lambda ev: remove.config(state="disabled" if tabs.select() == str(summary) else "normal"))

		def done(review=False):
			results = []
			if not review:
				for draft in drafts:
					if not draft["title"].get().strip():
						tabs.select(draft["frame"])
						messagebox.showerror(APP_NAME, "Give each follow-up task a title, or remove its tab.", parent=w)
						draft["entry"].focus_set()
						return
					results.append(dict(draft["fields"](), title=draft["title"].get().strip(), source_ref=draft["source"].get().split()[0],
										note=draft["note"].get("1.0", "end").strip(), needs_ai=draft["needs_ai"].get()))
			completed = tasks + (subs if also.get() else [])
			if not review:
				for task in completed:
					assigned = (assignments or {}).get(task["ref"], devs_of(task))
					devs = (assigned or [self.me.get()]) if completed_by.get() == keep_credit else [completed_by.get()]
					self.change(task, "devs", devs, note="Completion credit")
			out["r"] = (completed, review, results)
			w.destroy()
		bf = ttk.Frame(f)
		bf.pack(anchor="e", pady=(12, 0))
		ttk.Button(bf, text="Complete", command=done).pack(side="left")
		ttk.Button(bf, text="Send for review instead...", command=lambda: done(True)).pack(side="left", padx=4)
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left")
		w.bind("<Return>", lambda ev: done())
		w.bind("<Escape>", lambda ev: w.destroy())
		w.grab_set()
		self.wait_window(w)
		return out.get("r")

	def create_follow_up(self, draft):
		"""Create both ends of the relationship before the completion's single save/undo step."""
		source = self.task(draft["source_ref"])
		if not source or source.get("status") != "Completed":
			return None
		follow_up = self.add_task(draft["title"], devs=list(draft["devs"]), project=draft["project"],
								  category=draft["category"], priority=draft["priority"], needs_ai=draft.get("needs_ai", False), follow_up_of=source["ref"],
								  links=["task:" + source["ref"]],
								  setter_note=f"Follow-up to {source['ref']}: {source.get('title', '')}." + ("\n\n" + draft["note"] if draft["note"] else ""))
		self.change(source, "links", list(dict.fromkeys(source.get("links", []) + ["task:" + follow_up["ref"]])),
					note=f"Follow-up task created: {follow_up['ref']}")
		return follow_up

	# ---------- milestones ----------
	def milestone(self, name):
		return next((m for m in self.data["milestones"] if m["name"] == name), None)

	def fill_milestones(self):
		mt = self.ms_tree
		keep = mt.selection()
		mt.delete(*mt.get_children())
		today = now().strftime("%Y-%m-%d")
		hidden = sum(1 for m in self.data["milestones"] if self.ms_flag(m["name"], "hidden"))
		self.hidden_btn.config(text=f"Show hidden ({hidden})")
		names = {m["name"] for m in self.data["milestones"]}

		def add(parent_iid, ms):
			hid, hl = self.ms_flag(ms["name"], "hidden"), self.ms_flag(ms["name"], "highlight")
			if hid and not self.show_hidden_ms.get():
				return
			mine = [t for t in self.tasks if self.in_ms(t, ms["name"])]
			opn = [t for t in mine if not is_closed(t)]
			blk = [t for t in opn if t.get("blocked") or self.waiting_on(t)]
			late = ms.get("target") and ms["target"] < today and opn
			tags = (("hl",) if hl else ()) + (("late",) if late else ()) + (("hidden",) if hid else ())
			iid = "ms:" + ms["name"]
			mt.insert(parent_iid, "end", iid=iid, text=("🏁 " if hl else "") + ("✓ " if ms.get("completed_event") else "") + ms["name"] + (" (hidden)" if hid else ""),
					  values=(ms.get("target", ""), len(mine) - len(opn), len(opn), len(blk)), tags=tags, open=True)
			for sub in sorted((m for m in self.data["milestones"] if m.get("parent") == ms["name"]), key=lambda m: m.get("target") or "9999"):
				add(iid, sub)
		for ms in sorted((m for m in self.data["milestones"] if m.get("parent", "") not in names), key=lambda m: m.get("target") or "9999"):
			add("", ms)
		for i in keep:
			if mt.exists(i):
				mt.selection_set(i)
		self.ms_section.set_count(str(len(self.data["milestones"])))

	def milestone_picked(self, ev=None):
		sel = self.ms_tree.selection()
		if sel == self._ms_sel:  # (refilling picks it again: act once)
			return
		self._ms_sel = sel
		if sel:
			self.f["milestone"].set(sel[0][3:])
			if self.view.get() not in ("open", "archive"):
				self.view.set("open")
			self.fill()
			self.show_task(sel[0])

	def show_milestone(self, name):
		ms = self.milestone(name) or {}
		mine = [t for t in self.tasks if self.in_ms(t, name)]
		opn = [t for t in mine if not is_closed(t)]
		path = " › ".join(reversed(self.ms_chain(name)))
		self.d_title.config(text=f"🏁 {path}" + (f"   (target {ms['target']})" if ms.get("target") else ""), fg="#1f2d3d")
		lines = [f"{len(mine) - len(opn)} of {len(mine)} tasks done" + (" (with its sub-milestones)" if self.ms_below(name) - {name} else "")
				 + (f"   ·   {ms['note']}" if ms.get("note") else "")]
		for sub in [m for m in self.data["milestones"] if m.get("parent") == name]:
			st = [t for t in self.tasks if self.in_ms(t, sub["name"])]
			lines.append(f"   🏁 {sub['name']}: {sum(1 for t in st if is_closed(t))} of {len(st)} done" + (f", target {sub['target']}" if sub.get("target") else ""))
		if ms.get("completed_event"):
			lines.insert(0, f"✓ Completed by {ms.get('completed_by', '')} · {ms.get('completed_at', '')[:10]}")
		if opn:
			lines.append("Still blocking it:")
			for t in sorted(opn, key=lambda t: -PRIORITY_WEIGHT.get(t.get("priority", "Normal"), 2)):
				why = ("⛔ " + t["blocked"]) if t.get("blocked") else ("⏳ waits for " + ", ".join(self.title_of(r) for r in self.waiting_on(t))) if self.waiting_on(t) else ""
				where = f"  [{self.ms_of(t)}]" if self.ms_of(t) != name else ""
				lines.append(f"   {t.get('title', '')}  ({', '.join(devs_of(t)) or 'nobody'}, {t.get('status')}, {t.get('priority')}){where}  {why}")
		self.d_info.config(text="\n".join(lines))
		self.d_block.pack_forget()

	def edit_milestone(self, name, tasks=None, project=None, parent=""):
		ms = self.milestone(name) if name else None
		w = tk.Toplevel(self)
		w.title("Milestone")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		nv = tk.StringVar(value=(ms or {}).get("name", ""))
		tv = tk.StringVar(value=(ms or {}).get("target", ""))
		ov = tk.StringVar(value=(ms or {}).get("note", ""))
		for r, (text, var, wd) in enumerate((("Milestone (e.g. 0.9 release)", nv, 30), ("Target date (YYYY-MM-DD)", tv, 14), ("Note", ov, 46))):
			ttk.Label(f, text=text, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=2)
			ttk.Entry(f, textvariable=var, width=wd, font="TkDefaultFont").grid(row=r, column=1, sticky="w")
		inside = ["(none: a top milestone)"] + [m["name"] for m in self.data["milestones"] if not ms or m["name"] not in self.ms_below(ms["name"])]
		pv = tk.StringVar(value=(ms or {}).get("parent") or parent or inside[0])
		ttk.Label(f, text="Inside milestone", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=2)
		ttk.Combobox(f, textvariable=pv, values=inside, state="readonly", width=28, font="TkDefaultFont").grid(row=3, column=1, sticky="w")

		def ok(ev=None):
			n = nv.get().strip()
			if not n or (n != (ms or {}).get("name") and self.milestone(n)):
				messagebox.showerror(APP_NAME, "Give it a (new) name.", parent=w)
				return
			if tv.get().strip() and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tv.get().strip()):
				messagebox.showerror(APP_NAME, "The target date is YYYY-MM-DD (or empty).", parent=w)
				return
			w.destroy()
			par = "" if pv.get().startswith("(") else pv.get()
			if ms is None:
				self.data["milestones"].append({"name": n, "target": tv.get().strip(), "note": ov.get().strip(), "parent": par})
			else:
				ms["parent"] = par
				if n != ms["name"]:
					for t in self.tasks:
						if t.get("milestone") == ms["name"]:
							t["milestone"] = n
					for p in self.data["projects"]:
						if p.get("milestone") == ms["name"]:
							p["milestone"] = n
					for m in self.data["milestones"]:  # (its sub-milestones stay in it)
						if m.get("parent") == ms["name"]:
							m["parent"] = n
					for key in ("hidden", "highlight"):
						lst = self.app.config.get(f"todo_ms_{key}", [])
						self.app.config[f"todo_ms_{key}"] = [n if x == ms["name"] else x for x in lst]
					self.app.save_config()
					if self.f["milestone"].get() == ms["name"]:
						self.f["milestone"].set(n)
				ms.update(name=n, target=tv.get().strip(), note=ov.get().strip())
			if tasks:
				self.set_many(tasks, "milestone", n)
			elif project:
				self.set_project_ms(project, n)
			else:
				self.refresh()
		w.bind("<Return>", ok)
		ttk.Button(f, text="Save", command=ok).grid(row=4, column=1, sticky="e", pady=(10, 0))

	def complete_milestone(self, name=None):
		milestone_celebration.complete_dialog(self, name)

	def milestone_menu(self, ev):
		row = self.ms_tree.identify_row(ev.y)
		m = tk.Menu(self, tearoff=0)
		if row:
			name = row[3:]
			hl, hid = self.ms_flag(name, "highlight"), self.ms_flag(name, "hidden")
			m.add_command(label="Remove the highlight" if hl else "🏁 Highlight (its tasks stand out)  - just for you",
						  command=lambda: self.set_ms(name, "highlight", not hl))
			m.add_command(label="Unhide" if hid else "Hide  - just for you", command=lambda: self.set_ms(name, "hidden", not hid))
			m.add_command(label="🎉 Complete milestone / special thanks...", command=lambda: self.complete_milestone(name))
			m.add_command(label="Edit...", command=lambda: self.edit_milestone(name))
			m.add_command(label="+ Sub-milestone...", command=lambda: self.edit_milestone(None, parent=name))
			sub = tk.Menu(m, tearoff=0)
			cur = (self.milestone(name) or {}).get("parent", "")
			for other in [x["name"] for x in self.data["milestones"] if x["name"] not in self.ms_below(name)] + [""]:
				sub.add_command(label=("● " if cur == other else "    ") + (other or "(none: a top milestone)"), command=lambda o=other: self.move_ms(name, o))
			m.add_cascade(label="Move into", menu=sub)
			m.add_command(label="Show all tasks", command=lambda: (self.f["milestone"].set(ALL), self.ms_tree.selection_set(()), self.fill()))
			m.add_command(label="Delete (its tasks stay)", command=lambda: self.delete_milestone(name))
			m.add_separator()
		m.add_command(label="+ New milestone...", command=lambda: self.edit_milestone(None))
		m.tk_popup(ev.x_root, ev.y_root)

	def ms_of(self, t):
		"""A task's milestone: its own, else its project's."""
		if t.get("milestone"):
			return t["milestone"]
		return (self.project(t.get("project")) or {}).get("milestone", "") if t.get("project") else ""

	def set_project_ms(self, name, ms):
		p = self.project(name)
		if p is None:
			return
		if ms:
			p["milestone"] = ms
		else:
			p.pop("milestone", None)
		self.refresh()
		self.app.set_status(f"{name} -> {ms or '(no milestone)'} (its tasks with no milestone of their own go with it).")

	def ms_flag(self, name, key):
		"""hidden / highlight of a milestone (or of a milestone it's inside): your own (Organisation Master's settings on
		this PC), not the shared task file."""
		mine = self.app.config.get(f"todo_ms_{key}", [])
		return any(n in mine for n in self.ms_chain(name))

	def ms_chain(self, name):
		"""A milestone and the milestones it's inside: [Tech Push, Stage 2, ...]."""
		out = []
		while name and name not in out:
			out.append(name)
			name = (self.milestone(name) or {}).get("parent", "")
		return out

	def ms_below(self, name):
		"""A milestone and every sub-milestone in it (any depth)."""
		return {m["name"] for m in self.data["milestones"] if name in self.ms_chain(m["name"])}

	def in_ms(self, t, name):
		return self.ms_of(t) in self.ms_below(name)

	def set_ms(self, name, key, on):
		if self.milestone(name) is None:
			return
		names = [n for n in self.app.config.get(f"todo_ms_{key}", []) if n != name] + ([name] if on else [])
		self.app.config[f"todo_ms_{key}"] = names
		self.app.save_config()
		if key == "hidden" and on and self.f["milestone"].get() == name:
			self.f["milestone"].set(ALL)
		self.refresh()

	def show_all(self):
		"""Back to every open task: no dev / project / milestone filter (the view, the dev list and the search too)."""
		for v in self.f.values():
			v.set(ALL)
		self.search.set("")
		self.view.set("open")
		self.app.config["todo_view"] = "open"
		for tree, attr in ((self.dev_tree, "_dev_sel"), (self.proj_tree, "_proj_sel"), (self.ms_tree, "_ms_sel")):
			tree.selection_set(())
			setattr(self, attr, ())
		self.fill()
		self.app.set_status("Showing all the open tasks.")

	def move_ms(self, name, parent):
		ms = self.milestone(name)
		if ms is not None and parent not in self.ms_below(name):
			ms["parent"] = parent
			self.refresh()

	def ms_label(self, name):
		"""A milestone for the menus: indented under the milestones it's inside."""
		return "      " * (len(self.ms_chain(name)) - 1) + name

	def ms_order(self):
		"""Milestone names, each followed by its sub-milestones."""
		out = []
		names = {m["name"] for m in self.data["milestones"]}

		def walk(parent):
			for m in sorted((m for m in self.data["milestones"] if (m.get("parent", "") if m.get("parent", "") in names else "") == parent),
							key=lambda m: m.get("target") or "9999"):
				out.append(m["name"])
				walk(m["name"])
		walk("")
		return out

	def delete_milestone(self, name):
		if not messagebox.askyesno(APP_NAME, f"Delete the milestone {name}? Its tasks stay."):
			return
		for t in self.tasks:
			if t.get("milestone") == name:
				self.change(t, "milestone", "")
		for p in self.data["projects"]:
			if p.get("milestone") == name:
				p.pop("milestone", None)
		up = (self.milestone(name) or {}).get("parent", "")
		for m in self.data["milestones"]:  # (its sub-milestones move up)
			if m.get("parent") == name:
				m["parent"] = up
		self.data["milestones"] = [m for m in self.data["milestones"] if m["name"] != name]
		if self.f["milestone"].get() == name:
			self.f["milestone"].set(ALL)
		self.refresh()

	# ---------- links ----------
	def fill_links(self):
		self.links.delete(0, "end")
		self.master_link_btn.configure(state="normal" if self.master_target() else "disabled")
		for l in (self.cur or {}).get("links", []):
			if l.startswith("rr://"):
				self.links.insert("end", "🔗 " + l)
				continue
			if l.startswith("game:"):
				self.links.insert("end", "🎮 Game portrait: " + l[5:])
				continue
			if l.startswith("task:"):
				ref = l[5:]
				task = self.task(ref)
				label = "↩ Follows" if self.cur.get("follow_up_of") == ref else "↪ Follow-up" if task and task.get("follow_up_of") == self.cur["ref"] else "🔗 Task"
				self.links.insert("end", f"{label}: {ref}" + (f"  {task.get('title', '')}" + (" (archive)" if is_closed(task) else "") if task else " (unavailable)"))
				continue
			self.links.insert("end", ("🌐 " if re.match(r"https?://", l) else "⎇ " if re.fullmatch(r"[0-9a-f]{7,40}", l) else "📄 ") + l)

	def add_link(self, t, kind):
		root = self.app.mod_root
		if kind == "file":
			p = filedialog.askopenfilename(parent=self, initialdir=root, title="A file for " + t.get("title", ""))
		elif kind == "folder":
			p = filedialog.askdirectory(parent=self, initialdir=root, title="A folder for " + t.get("title", ""))
		else:
			p = (simpledialog.askstring("Link", "A web address (https://...), a commit (its hash) or a mod path:", parent=self) or "").strip()
		if not p:
			return
		if os.path.isabs(p) and os.path.normcase(os.path.abspath(p)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep):
			p = os.path.relpath(p, root).replace("\\", "/")
		self.change(t, "links", t.get("links", []) + [p])
		self.save()
		if t is self.cur:
			self.fill_links()

	def master_target(self, selected=None):
		if not self.cur:
			return None
		try:
			source = master_links.from_task(self.cur)
			if self.cur.get("review_states") and self.state_review_panel.current_sid:
				source = master_links.make("culture", "state", self.state_review_panel.current_sid,
					system=self.cur.get("review_system") or "culture")
		except ValueError:
			source = None
		if selected is not None:
			try:
				target = master_links.from_file(selected, self.app.mod_root)
				if target:
					if source and not selected.startswith("rr://"):
						a, b = master_links.parse(source), master_links.parse(target)
						if a["kind"] == b["kind"] == "state" and a["value"] == b["value"]:
							return source
					return target
			except ValueError:
				pass
			return None
		if source:
			return source
		for link in self.cur.get("links", []):
			try:
				target = master_links.from_file(link, self.app.mod_root)
				if target:
					return target
			except ValueError:
				continue
		return None

	def open_in_master(self):
		sel = self.links.curselection()
		link = self.cur.get("links", [])[sel[0]] if sel and self.cur else None
		target = self.master_target(link) or self.master_target()
		if target:
			self.flush_notes()
			self.app.navigate_master(target)

	def open_link(self, as_file=False):
		sel = self.links.curselection()
		if not sel or not self.cur:
			return
		l = self.cur.get("links", [])[sel[0]]
		if not as_file:
			target = self.master_target(l)
			if target:
				self.flush_notes()
				self.app.navigate_master(target)
				return
		if l.startswith("rr://"):
			messagebox.showinfo(APP_NAME, "This is a link to an item in a master. Use Open in master.", parent=self)
			return
		if l.startswith("task:"):
			if self.task(l[5:]):
				self.go_to(l[5:])
			else:
				messagebox.showinfo(APP_NAME, "That linked task is no longer available.")
		elif l.startswith("game:"):
			path = portrait_links.game_link_path(self.app.mod_root, l)
			if path:
				os.startfile(path)
			else:
				messagebox.showinfo(APP_NAME, "That base-game portrait could not be found in your Hearts of Iron IV installation.")
		elif re.match(r"https?://", l):
			webbrowser.open(l)
		elif re.fullmatch(r"[0-9a-f]{7,40}", l):
			url = mm.git(self.app.mod_root, "config", "--get", "remote.origin.url").strip()
			url = re.sub(r"^git@([^:]+):", r"https://\1/", url).removesuffix(".git")
			if url:
				webbrowser.open(f"{url}/commit/{l}")
		else:
			p = l if os.path.isabs(l) else os.path.join(self.app.mod_root, l)
			if os.path.exists(p):
				os.startfile(p)
			else:
				messagebox.showerror(APP_NAME, f"{p} isn't there.")

	def remove_link(self):
		sel = self.links.curselection()
		if sel and self.cur:
			links = list(self.cur.get("links", []))
			del links[sel[0]]
			self.change(self.cur, "links", links)
			self.save()
			self.fill_links()

	# ---------- undo ----------
	def register_undo_button(self, button):
		self._undo_buttons.append(button)
		self._refresh_undo_buttons()

	def _refresh_undo_buttons(self):
		for button in self._undo_buttons:
			if button.winfo_exists():
				button.state(["!disabled"] if self._undo else ["disabled"])

	def _setup_undo_shortcut(self):
		root = self.winfo_toplevel()
		self._undo_root = root
		self._undo_tag = f"OrganisationUndo{id(self)}"
		for key in ("<Control-z>", "<Control-Z>"):
			root.bind_class(self._undo_tag, key, self.undo_key)
		self._undo_map_binding = root.bind("<Map>", self._tag_undo_widget, add="+")
		self.bindtags((self._undo_tag,) + self.bindtags())
		self.bind("<Destroy>", self._remove_undo_shortcut, add="+")

	def _tag_undo_widget(self, ev):
		widget = ev.widget
		# Dialogs keep their own editing shortcuts; the main page uses the Undo command.
		if widget.winfo_toplevel() is not self.winfo_toplevel():
			return
		parent = widget
		while parent is not None and parent is not self:
			parent = getattr(parent, "master", None)
		if parent is self and self._undo_tag not in widget.bindtags():
			widget.bindtags((self._undo_tag,) + widget.bindtags())

	def _remove_undo_shortcut(self, ev):
		if ev.widget is self:
			root = self._undo_root
			root.unbind("<Map>", self._undo_map_binding)
			for key in ("<Control-z>", "<Control-Z>"):
				root.unbind_class(self._undo_tag, key)

	def undo(self):
		"""Takes back your last change (status, reassignment, deletion, notes, a GFX mark...). When the others' changes came
		in since (live sync), only yours is taken back: a three-way merge of before / after your change with now, the same
		way live sync merges, so their work stays."""
		if self._note_job:
			self.flush_notes()
		for pane in (self.idea_pane, self.vc_pane):
			if pane._job:
				pane.flush()
		if not self._undo:
			return
		before, after = self._undo.pop()
		ref = self.cur and self.cur["ref"]
		vc_id = self.vc_pane.cur and self.vc_pane.cur["id"]
		# Discard old object references before refreshing editors from the restored data.
		self.cur = None
		self.cur_group = None
		self.vc_pane.cur = None
		self.idea_pane.cur = None
		self.idea_pane._dirty = False
		activity = list(self.data.get("master_activity", []))
		if after == self._saved:  # (nothing came in since: straight back)
			restored = json.loads(before)
		else:
			restored = todo_sync.merge(json.loads(after), json.loads(before), json.loads(self._saved))
		# Music planning and published celebrations have their own lifecycle; To Do Undo must retain them.
		for key in ("music_plans", "music_station_catalog", milestone_celebration.EVENTS, milestone_celebration.SEEN):
			if key in self.data:
				restored[key] = self.data[key]
		undo_events = developer_activity.changes(self.data, restored, self.me.get())
		for event in undo_events:
			event["title"] = "Undo · " + event["title"]
		try:  # (an undone ✓ Reworked / rework mark: this PC's Country Master list follows)
			gfx_master.follow_undo(self.app.mod_root, self.data, restored)
		except OSError:
			pass
		self.data = restored
		self.data["master_activity"] = activity + undo_events
		self._saved = before
		self.save(undoable=False)
		self.fill_filters()
		self.fill()
		self.vc_pane.fill()
		if vc_id and self.vc_pane.list.exists(vc_id):
			self.vc_pane.list.selection_set(vc_id)
		self.vc_pane.show()
		self.idea_pane.fill()  # (keeps the idea picked: found again by its id)
		self.idea_pane.show()
		if self.gfx_pane.winfo_manager():
			self.gfx_pane.redraw()  # (🖼 GFX showed the old list: the undo looked like it did nothing)
			self.gfx_pane.undone()  # (a swiper's last card comes back)
		self.show_task(ref if ref and self.task(ref) else None)
		self._refresh_undo_buttons()
		self.app.set_status(f"Undone ({len(self._undo)} more to undo).")
		getattr(self.app, "feedback", lambda *_: None)("undo")

	def undo_key(self, ev):
		if self.winfo_ismapped():
			self.undo()
			return "break"

	# ---------- health ----------
	def health(self):
		"""What needs looking at: unassigned work, blocked tasks, pending reviews, projects without a lead, red timers."""
		w = tk.Toplevel(self)
		w.title("🩺 Project health")
		w.geometry(f"{ui.px(900)}x{ui.px(480)}")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		opn = [t for t in self.tasks if not is_closed(t)]
		nolead = [p["name"] for p in self.data["projects"] if not p.get("lead")]
		ttk.Label(f, text=f"{len(opn)} open tasks   ·   {sum(1 for t in opn if not devs_of(t))} unassigned   ·   "
						  f"{sum(1 for t in opn if t.get('blocked') or self.waiting_on(t))} blocked   ·   "
						  f"{sum(1 for t in opn if t.get('status') == 'Ready for Review')} waiting for review   ·   "
						  f"{sum(1 for t in opn if age_band(age_of(t)) == 'red')} older than 3 months", style="Head.TLabel").pack(anchor="w")
		if nolead:
			ttk.Label(f, text="⚠ Projects without a lead: " + ", ".join(nolead), foreground="#b06f00").pack(anchor="w", pady=(2, 0))
		box = ttk.Frame(f)
		box.pack(fill="both", expand=True, pady=(8, 0))
		t = ttk.Treeview(box, columns=("open", "unassigned", "blocked", "review", "red", "lead"))
		for col, text, wd in (("#0", "Project / task", 330), ("open", "Open", 60), ("unassigned", "Unassigned", 85), ("blocked", "Blocked", 70),
							  ("review", "Reviews", 70), ("red", "🔴 Old", 60), ("lead", "Lead", 110)):
			t.heading(col, text=text)
			t.column(col, width=ui.px(wd), anchor="w" if col in ("#0", "lead") else "e", stretch=col == "#0")
		ys = ttk.Scrollbar(box, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		t.tag_configure("proj", font="om_bold")
		t.tag_configure("warn", foreground="#c62828")
		for name in self.project_names() + [NO_PROJECT]:
			mine = [x for x in opn if (x.get("project") or NO_PROJECT) == name]
			if not mine:
				continue
			un = [x for x in mine if not devs_of(x)]
			bl = [x for x in mine if x.get("blocked") or self.waiting_on(x)]
			rv = [x for x in mine if x.get("status") == "Ready for Review"]
			red = [x for x in mine if age_band(age_of(x)) == "red"]
			p = self.project(name) or {}
			pid = t.insert("", "end", iid="proj:" + name, text=f" {name}", image=self.project_icon(name), tags=("proj",),
						   values=(len(mine), len(un), len(bl), len(rv), len(red), p.get("lead") or ("⚠ none" if p else "")))
			for label, rows in (("⛔ Blocked", bl), ("👀 Waiting for review", rv), ("🔴 Older than 3 months", red)):
				if rows:
					g = t.insert(pid, "end", text=f"{label} ({len(rows)})", tags=("warn",))
					for x in rows:
						t.insert(g, "end", iid="t:" + x["ref"], text=f"{x['ref']}  {x.get('title', '')}", values=("", "", "", "", "", ", ".join(devs_of(x)) or "-"))

		def go(ev=None):
			sel = t.selection()
			if not sel:
				return
			if sel[0].startswith("t:"):
				self.go_to(sel[0][2:])
			elif sel[0].startswith("proj:"):
				self.f["project"].set(sel[0][5:])
				self.view.set("open")
				self.fill()
		t.bind("<Double-1>", go)
		ttk.Label(f, text="Double-click a project to show its tasks, a task to go to it.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

	# ---------- icons ----------
	def isize(self):
		return ui.px(20)

	def icon(self, x):
		"""A task's icon: its own, else its category's, else the clipboard."""
		cats = self.data.setdefault("category_icons", {})
		return icons.image(x.get("icon") or cats.get(x.get("category")) or CATEGORY_ICONS.get(x.get("category")) or TASK_ICON, self.isize())

	def auto_icon(self, name):
		"""A country's flag when a name says one ("United Kingdom", "Communist China", "ENG focus tree"), else None."""
		af = getattr(self, "auto_flags", None)
		return af.match(name) if af else None

	def flag_image(self, name):
		ic = self.auto_icon(name)
		return icons.image(ic, self.isize()) if ic else ""

	def wait_auto_flags(self):
		"""The flag index is built in the background: once it's there, the lists get their flags."""
		if not self.winfo_exists():
			return
		if not self.auto_flags.ready:
			self.after(1000, self.wait_auto_flags)
			return
		self.fill()
		if hasattr(self, "fill_projects"):
			self.fill_projects()
		self.idea_pane.fill()

	def project_icon(self, name):
		return icons.image((self.project(name) or {}).get("icon") or self.auto_icon(name) or PROJECT_ICON, self.isize())

	def group_icon(self, parent, g):
		return icons.image((parent.get("group_icons") or {}).get(g) or self.auto_icon(g) or GROUP_ICON, self.isize())

	def redraw_icons(self):
		if self.winfo_exists():
			self.fill()

	def pick_icon(self, tasks):
		cur = tasks[0].get("icon") if len(tasks) == 1 else None

		def chosen(i):
			for x in tasks:
				if i:
					x["icon"] = i
				else:
					x.pop("icon", None)
			self.refresh()
		icons.pick(self, f"Icon of {tasks[0].get('title', '') if len(tasks) == 1 else f'{len(tasks)} tasks'}", cur, chosen)

	def project_priority(self, name):
		"""(priority, overridden?): its own when set, else the average of its open tasks (Normal when it has none)."""
		p = self.project(name) or {}
		if p.get("priority") in PRIORITIES:
			return p["priority"], True
		opn = [x for x in self.tasks if x.get("project") == name and not is_closed(x)]
		if not opn:
			return "Normal", False
		avg = sum(PRIORITIES.index(x.get("priority", "Normal")) if x.get("priority") in PRIORITIES else 1 for x in opn) / len(opn)
		return PRIORITIES[int(avg + 0.5)], False

	def project_priority_text(self, name):
		pr, own = self.project_priority(name)
		return f"★ {pr}" if own else f"≈ {pr}"

	def project_priority_menu(self, m, name):
		"""Average (of its tasks) or an override; and setting all its open tasks."""
		p = self.project(name)
		if not p:
			return
		pr, own = self.project_priority(name)

		def set_(v):
			if v:
				p["priority"] = v
			else:
				p.pop("priority", None)
			self.refresh()
		m.add_command(label=("● " if not own else "    ") + f"Average of its tasks (≈ {self.project_priority(name)[0] if not own else '...'})",
					  command=lambda: set_(None))
		for v in PRIORITIES:
			m.add_command(label=("● " if own and pr == v else "    ") + f"{v} (override)", command=lambda v=v: set_(v))
		m.add_separator()
		opn = [x for x in self.tasks if x.get("project") == name and not is_closed(x)]
		sub = tk.Menu(m, tearoff=0)
		for v in PRIORITIES:
			sub.add_command(label=v, command=lambda v=v: self.set_many(opn, "priority", v, note=f"whole project {name}"))
		m.add_cascade(label=f"Set all its {len(opn)} open tasks to", menu=sub)

	def pick_project_icon(self, name):
		p = self.project(name)
		if p:
			icons.pick(self, f"Icon of {name}", p.get("icon"), lambda i: (p.update(icon=i) if i else p.pop("icon", None), self.refresh()))

	def pick_group_icon(self, parent_ref, g):
		p = self.holder(parent_ref)
		if p:
			gi = p.setdefault("group_icons", {})
			icons.pick(self, f"Icon of {g}", gi.get(g), lambda i: (gi.update({g: i}) if i else gi.pop(g, None), self.refresh()))

	def pick_category_icon(self, cat):
		cats = self.data.setdefault("category_icons", {})
		icons.pick(self, f"Default icon of {cat} tasks", cats.get(cat) or CATEGORY_ICONS.get(cat),
				   lambda i: (cats.update({cat: i}) if i else cats.pop(cat, None), self.refresh()))

	def title_of(self, ref):
		o = self.task(ref)
		return o.get("title", ref) if o else ref

	def subtasks(self, t):
		return [c for c in self.tasks if c.get("parent") == t["ref"]]

	def collapse_all(self):
		"""Fold projects and every nested branch, retaining their closed state on refresh."""
		changed = False
		for row in self.all_rows():
			if self.tree.get_children(row):
				changed = changed or bool(self.tree.item(row, "open"))
				self.tree.item(row, open=False)
				self._open[row] = False
		if changed:
			getattr(self.app, "feedback", lambda *_: None)("close")

	def task_bar_menu(self, event):
		menu = tk.Menu(self, tearoff=0)
		menu.add_command(label="Collapse All", command=self.collapse_all)
		try:
			menu.tk_popup(event.x_root, event.y_root)
		finally:
			menu.grab_release()
		return "break"

	def all_rows(self, parent=""):
		out = []
		for i in self.tree.get_children(parent):
			out.append(i)
			out += self.all_rows(i)
		return out

	def mode_changed(self):
		self.app.config["todo_mode"] = self.mode.get()
		if self.mode.get() not in ("vc", "idea", "gfx", "achievements"):
			self.app.config["todo_last_mode"] = self.mode.get()
		self.app.save_config()
		self.show_side()
		self.layout_mode()
		self.fill()
		if getattr(self.app, "_ready", False):
			self.app.record_access("To Do Master")

	def layout_mode(self):
		"""Dev VCs / Ideas mode: their page in place of the task tools, views, filters and task list."""
		if self.mode.get() == "achievements" and self.achievement_pane is None:
			self.achievement_pane = achievements.Achievements(self, self)
		pane = {"vc": self.vc_pane, "idea": self.idea_pane, "gfx": self.gfx_pane, "achievements": self.achievement_pane}.get(self.mode.get())
		if pane and self.tools_row.winfo_manager():  # (the task tools aren't for VCs / ideas)
			self._reserve_task_toolbar_width()
			self.task_tools.grid_remove()
			self.search_box.grid_remove()
			self.tools_row.pack_forget()
		elif not pane and not self.tools_row.winfo_manager():
			self.task_tools.grid()
			self.search_box.grid()
			self.tools_row.pack(fill="x", pady=(6, 0), after=self.top_row)
		for p in (self.vc_pane, self.idea_pane, self.gfx_pane, self.achievement_pane):
			if p is not None and p is not pane and p.winfo_manager():
				p.flush()
				if p is self.idea_pane:
					p.leave()  # (what's there now is "seen")
				p.pack_forget()
		if pane and not pane.winfo_manager():
			for w in (self.views_row, self.sec_filters, self.main_pw):
				w.pack_forget()
			if pane is self.idea_pane:
				pane.enter()
			pane.pack(fill="both", expand=True, after=self.top_row)
			pane.fill()
		elif not pane and not self.main_pw.winfo_manager():
			self.views_row.pack(fill="x", pady=(10, 4), after=self.tools_row)
			self.sec_filters.pack(fill="x", pady=(2, 6), after=self.views_row)
			self.main_pw.pack(fill="both", expand=True, after=self.sec_filters)
		self.show_report()

	def show_side(self):
		if self.mode.get() in ("vc", "idea", "gfx", "achievements"):
			return
		new, old = (self.proj_side, self.dev_side) if self.mode.get() == "project" else (self.dev_side, self.proj_side)
		old.pack_forget()
		new.pack(fill="x", before=self.ms_section)

	def fill_projects(self):
		pt = self.proj_tree
		self._proj_drag = None
		pt.configure(cursor="")
		keep = pt.selection()
		pt.delete(*pt.get_children())
		for name in self.project_names() + [NO_PROJECT]:
			mine = [x for x in self.tasks if (x.get("project") or NO_PROJECT) == name]
			if name == NO_PROJECT and not mine:
				continue
			p = self.project(name) or {}
			pt.insert("", "end", iid="proj:" + name, text=" " + name, image=self.project_icon(name) if p else "",
					  values=(p.get("lead", ""), sum(1 for x in mine if not is_closed(x)), sum(1 for x in mine if is_closed(x))),
					  tags=self.project_tags(name, bold=False) if p else ("none",))
		ui.stripe(pt)
		for i in keep:
			if pt.exists(i):
				pt.selection_set(i)

	def project_at(self, ev):
		row = self.proj_tree.identify_row(ev.y)
		return row[5:] if row.startswith("proj:") and row[5:] != NO_PROJECT else None

	def project_drag_press(self, event):
		t = self.proj_tree
		self._proj_drag = None
		row = t.identify_row(event.y)
		if t.identify_region(event.x, event.y) in ("tree", "cell") and row.startswith("proj:") and self.project(row[5:]):
			self._proj_drag = {"row": row, "x": event.x, "y": event.y, "on": False}
			t.focus_set()
			return "break"  # Select on release so a drag does not change the project filter.

	def project_drag_motion(self, event):
		d = self._proj_drag
		t = self.proj_tree
		if not d or not t.exists(d["row"]):
			return
		if not d["on"] and abs(event.x - d["x"]) + abs(event.y - d["y"]) < 8:
			return
		d["on"] = True
		t.configure(cursor="fleur")
		ui.drag_wobble(t, event, [d["row"]], origin=(d["x"], d["y"]))
		ui.drag_autoscroll(t, event)
		if not 0 <= event.x < t.winfo_width() or not ui.px(20) <= event.y < t.winfo_height():
			return "break"
		target = t.identify_row(event.y)
		if target == d["row"]:
			return "break"
		rows = [row for row in t.get_children() if row != d["row"]]
		end = rows.index("proj:" + NO_PROJECT) if "proj:" + NO_PROJECT in rows else len(rows)
		if target in rows and self.project(target[5:]):
			box = t.bbox(target)
			index = rows.index(target) + (event.y >= box[1] + box[3] / 2)
		else:
			index = end
		t.move(d["row"], "", min(index, end))
		return "break"

	def project_drag_release(self, event):
		d = self._proj_drag
		self._proj_drag = None
		t = self.proj_tree
		ui.drag_autoscroll_stop(t)
		t.configure(cursor="")
		if not d:
			return
		if not d["on"]:
			if t.identify_row(event.y) == d["row"]:
				t.focus(d["row"])
				t.selection_set(d["row"])
			return "break"
		if not (0 <= event.x < t.winfo_width() and ui.px(20) <= event.y < t.winfo_height()):
			self.fill_projects()
			return "break"
		order = [row[5:] for row in t.get_children() if row.startswith("proj:") and self.project(row[5:])]
		if order != self.project_names():
			for position, name in enumerate(order):
				self.project(name)["list_order"] = position
			self.refresh()
			self.app.set_status("Project order saved. Ctrl+Z undoes it.")
		return "break"

	def project_drag_cancel(self, event=None):
		if self._proj_drag:
			self._proj_drag = None
			ui.drag_autoscroll_stop(self.proj_tree)
			self.fill_projects()
			return "break"

	def project_picked(self, ev=None):
		sel = self.proj_tree.selection()
		if sel == self._proj_sel:  # (refilling picks the same row again: act once)
			return
		self._proj_sel = sel
		if sel:
			self.f["project"].set(sel[0][5:])
			self.fill()

	def project_menu(self, ev, name=None):
		name = name or self.project_at(ev)
		m = tk.Menu(self, tearoff=0)
		if name and name != NO_PROJECT:
			m.add_command(label=f"📁 {name}", state="disabled")
			m.add_command(label="+ New task in it...", command=lambda: self.edit_task(new=True, project=name))
			m.add_command(label="💡 Add a linked idea...", command=lambda: self.idea_pane.add_linked(project=name))
			n = len(self.idea_pane.linked_ideas(project=name))
			if n:
				m.add_command(label=f"💡 See its ideas ({n})", command=lambda: self.idea_pane.show_linked(project=name))
			m.add_command(label="+ New grouping (for its tasks)...", command=lambda: self.add_groupings(self.project(name), "proj:" + name))
			m.add_command(label="Lead / name / colour / note...", command=lambda: self.edit_project(name))
			n = len((self.project(name) or {}).get("fields", []))
			m.add_command(label="🏷 Descriptors for its tasks..." + (f"  ({n})" if n else ""), command=lambda: self.edit_project_fields(name))
			m.add_command(label="Colour...", command=lambda: self.pick_project_colour(name))
			m.add_command(label="🖼 Icon...", command=lambda: self.pick_project_icon(name))
			sub = tk.Menu(m, tearoff=0)
			self.project_priority_menu(sub, name)
			m.add_cascade(label="Priority", menu=sub)
			sub = tk.Menu(m, tearoff=0)
			cur = (self.project(name) or {}).get("milestone", "")
			for ms in self.ms_order() + [""]:
				sub.add_command(label=("● " if cur == ms else "    ") + (self.ms_label(ms) if ms else "(no milestone)"), command=lambda ms=ms: self.set_project_ms(name, ms))
			sub.add_separator()
			sub.add_command(label="New milestone...", command=lambda: self.edit_milestone(None, project=name))
			m.add_cascade(label="🏁 Milestone", menu=sub)
			m.add_command(label="Show only this project", command=lambda: (self.f["project"].set(name), self.fill()))
			m.add_command(label="⧉ Duplicate the project...", command=lambda: self.duplicate_project(name))
			m.add_command(label="+ From template, in it...", command=lambda: self.from_template(project=name))
			m.add_command(label="Delete the project...", command=lambda: self.delete_project(name))
			m.add_separator()
		m.add_command(label="+ New project...", command=self.add_project)
		m.add_command(label="Show every project", command=lambda: (self.f["project"].set(ALL), self.proj_tree.selection_set(()), self.fill()))
		m.tk_popup(ev.x_root, ev.y_root)

	def project_tags(self, name, bold=True, tree=None):
		"""Style the intended list without resetting the other lists' themed project rows."""
		c = (self.project(name) or {}).get("colour")
		if not c:
			return ("project",) if bold else ()
		tag = f"pc{c.lstrip('#')}{'b' if bold else ''}"
		for target in (tree,) if tree is not None else (self.tree, self.proj_tree):
			try:
				ui.project_row_tag(target, tag, c, bold)
			except tk.TclError:
				pass
		return (tag,)

	def pick_project_colour(self, name):
		p = self.project(name)
		if not p:
			return
		c = colorchooser.askcolor(p.get("colour") or PROJECT_COLOURS[0], parent=self, title=f"Colour of {name}")[1]
		if c:
			p["colour"] = c
			getattr(self.app, "feedback", lambda *_: None)("colour")
			self.refresh()

	def add_project(self, tasks=None):
		self.edit_project(None, tasks)

	def edit_project(self, name, tasks=None):
		"""A project's name, lead (Project Lead) and note; name None = a new one (tasks: put them in it)."""
		if name == NO_PROJECT:
			return
		p = self.project(name) if name else None
		w = tk.Toplevel(self)
		w.title("New project" if p is None else f"Project: {name}")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		nv = tk.StringVar(value=p["name"] if p else "")
		lv = tk.StringVar(value=(p or {}).get("lead", "") or "(nobody yet)")
		ttk.Label(f, text="Project", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=3)
		e = ttk.Entry(f, textvariable=nv, width=40, font="om_bold")
		e.grid(row=0, column=1, sticky="we")
		e.focus_set()
		ttk.Label(f, text="Project lead", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=3)
		ttk.Combobox(f, textvariable=lv, values=["(nobody yet)"] + self.dev_names(), state="readonly", width=24,
					 font="TkDefaultFont").grid(row=1, column=1, sticky="w")
		colour = {"c": (p or {}).get("colour") or PROJECT_COLOURS[len(self.data["projects"]) % len(PROJECT_COLOURS)]}
		ttk.Label(f, text="Colour", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=3)
		cf = ttk.Frame(f)
		cf.grid(row=3, column=1, sticky="w")
		sw = tk.Label(cf, text="  📁 " + (nv.get() or "Project") + "  ", fg=colour["c"], bg=ui._mix(colour["c"], "#ffffff", 0.86),
					  font="om_bold", relief="groove")
		sw.pack(side="left")

		def set_c(c):
			colour["c"] = c
			getattr(self.app, "feedback", lambda *_: None)("colour")
			sw.config(fg=c, bg=ui._mix(c, "#ffffff", 0.86))
		nv.trace_add("write", lambda *_: sw.config(text="  📁 " + (nv.get() or "Project") + "  "))
		for c in PROJECT_COLOURS:
			b = tk.Label(cf, text="■", fg=c, font="om_big", cursor="hand2")
			b.pack(side="left")
			b.bind("<Button-1>", lambda ev, c=c: set_c(c))
		ttk.Button(cf, text="Colour...", style="Tool.TButton",
				   command=lambda: (lambda c: c and set_c(c))(colorchooser.askcolor(colour["c"], parent=w)[1])).pack(side="left", padx=6)
		ttk.Label(f, text="Note", style="Muted.TLabel").grid(row=2, column=0, sticky="nw", pady=3)
		note = tk.Text(f, width=50, height=4, wrap="word", font="om_body", relief="solid", borderwidth=1)
		note.grid(row=2, column=1, sticky="we")
		note.insert("1.0", (p or {}).get("note", ""))

		def ok(ev=None):
			n = nv.get().strip()
			if not n:
				messagebox.showerror(APP_NAME, "Give the project a name.", parent=w)
				return
			if n != (p or {}).get("name") and n in self.project_names():
				messagebox.showerror(APP_NAME, f"There's already a project called {n}.", parent=w)
				return
			lead = "" if lv.get() == "(nobody yet)" else lv.get()
			if p is None:
				self.data["projects"].append({"name": n, "lead": lead, "colour": colour["c"], "set_by": self.me.get(), "created": stamp(),
											  "note": note.get("1.0", "end").strip()})
			else:
				if n != p["name"]:
					self.record_deletion("projects", p, "name", trash=False)  # (renamed, not deleted)
					for x in self.tasks + self.data.get("ideas", []) + self.data.get("idea_header_details", []):
						if x.get("project") == p["name"]:
							x["project"] = n
					if self.f["project"].get() == p["name"]:
						self.f["project"].set(n)
				p.update(name=n, lead=lead, colour=colour["c"], note=note.get("1.0", "end").strip())
			w.destroy()
			if tasks:
				self.set_project(tasks, n)
			else:
				self.refresh()
		bf = ttk.Frame(f)
		bf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def delete_project(self, name):
		mine = [x for x in self.tasks if x.get("project") == name]
		if not messagebox.askyesno(APP_NAME, f"Delete the project {name}?" + (f"\n\nIts {len(mine)} tasks stay, with no project." if mine else "")):
			return
		for x in mine:
			self.change(x, "project", "", note=f"project {name} deleted")
		if self.project(name):
			self.record_deletion("projects", self.project(name), "name", members=[x["ref"] for x in mine])
		self.data["projects"] = [p for p in self.data["projects"] if p["name"] != name]
		for i in self.data.get("ideas", []) + self.data.get("idea_header_details", []):  # Ideas and group defaults lose the deleted project.
			if i.get("project") == name:
				i["project"] = ""
		if self.f["project"].get() == name:
			self.f["project"].set(ALL)
		self.refresh()

	def set_project(self, tasks, name):
		"""Tasks (and their sub-tasks) go in a project; a sub-task whose parent is elsewhere stops being one."""
		todo = list(tasks)
		for t in tasks:
			todo += [c for c in self.tasks if self.is_below(c, t) and c not in todo]
		for t in todo:
			self.change(t, "project", name)
			if t.get("parent") and (self.task(t["parent"]) or {}).get("project", "") != name and t["parent"] not in {x["ref"] for x in todo}:
				self.change(t, "parent", "")
		self.refresh()

	def is_below(self, c, t):
		"""Is c a sub-task (or a sub-sub-task...) of t?"""
		seen = set()
		while c.get("parent") and c["parent"] not in seen:
			if c["parent"] == t["ref"]:
				return True
			seen.add(c["parent"])
			c = self.task(c["parent"]) or {}
		return False

	def set_parent(self, tasks):
		refs = {t["ref"] for t in tasks}
		project = tasks[0].get("project", "")
		cands = [o for o in sorted(self.tasks, key=lambda x: x["ref"]) if o["ref"] not in refs and o.get("project", "") == project
				 and not any(self.is_below(o, t) for t in tasks)]
		labels = ["(not a sub-task)"] + [f"{o['ref']}  {o.get('title', '')}" for o in cands]
		cur = tasks[0].get("parent")
		pick = self.pick_from("Sub-task of", f"{', '.join(sorted(refs))} is a sub-task of (tasks of {project or NO_PROJECT}):", labels,
							  next((l for l in labels if cur and l.startswith(cur + " ")), labels[0]))
		if pick is None:
			return
		self.set_many(tasks, "parent", "" if pick == labels[0] else pick.split()[0])

	# ---------- tasks kept by Music Master ----------
	def new_ref(self):
		ref = f"RR-{self.data['next_ref']:04d}"
		while self.task(ref):
			self.data["next_ref"] += 1
			ref = f"RR-{self.data['next_ref']:04d}"
		self.data["next_ref"] += 1
		return ref

	def add_task(self, title, **kw):
		"""A new task (nobody's yet: General To Do) set by you; kw: project, parent, category, link, setter_note..."""
		now = stamp()
		t = {"ref": self.new_ref(), "title": title, "devs": [], "category": "", "priority": "Normal", "status": TODO, "sweep": False,
			 "tags": [], "setter_note": "", "dev_note": "", "blocked": "", "reviewer": "", "needs_planning": False, "project": "",
			 "parent": "", "depends_on": [], "set_by": self.me.get(), "created": now, "updated": now,
			 "history": [{"when": now, "who": self.me.get(), "field": "created", "old": None, "new": None}]}
		t.update(kw)
		self.tasks.append(t)
		return t

	def tasks_to_agenda(self, tasks):
		"""📋 Bring to Agenda: the tasks onto the next Dev VC's agenda, put forward by you."""
		where = ""
		for t in tasks:
			where = dev_vc.bring_to_agenda(self.data, f"📌 {t['ref']}: {t.get('title', '')}", "To Do", self.me.get())
		self.save()
		self.vc_pane.fill_agenda()
		self.vc_pane.fill_future()
		self.app.set_status(f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} on the agenda of {where}.")

	def linked(self, link):
		return next((t for t in self.tasks if t.get("link") == link), None)

	def reconcile_idea_reviews(self):
		"""One review per project-linked idea; implementation tasks remain a separate lead decision."""
		changed = False
		pending = set()
		for idea in self.data.get("ideas", []):
			parent = self.task(idea.get("task")) if idea.get("task") else None
			project = (parent.get("project") if parent else idea.get("project")) or ""
			key = "idea_review:" + idea["id"]
			if not self.project(project) or idea.get("state", "open") not in ideas.ACTIVE:
				continue
			pending.add(key)
			task = self.linked(key)
			if task is None and idea.get("review_task"):
				continue  # An explicitly removed review must not be recreated on every save.
			category = ideas.TASK_CATEGORY.get((idea.get("category") or "").split(ideas.SEP)[0], idea.get("category") or "")
			if category not in self.data.get("categories", []):
				category = ""
			note = f"Review the project idea before deciding whether to implement it.\nIdea: {idea.get('title', '')}\nCategory: {idea.get('category') or '(none)'}\nPosted by {idea.get('by') or 'unknown'}."
			if idea.get("text"):
				note += "\n\n" + idea["text"]
			if idea.get("comments"):
				note += "\n\nComments:\n" + "\n".join(f"- {row.get('by', '?')}: {row.get('text', '')}" for row in idea["comments"][-10:])
			if task is None:
				task = self.add_task("Review idea: " + idea.get("title", ""), project=project, category=category,
					status="Ready for Review", reviewer=(self.project(project) or {}).get("lead", ""),
					link=key, idea=idea["id"], group="Idea Reviews", icon="clipboard", setter_note=note,
					idea_review_note=note, links=list(idea.get("links") or []))
				changed = True
			if idea.get("review_task") != task["ref"]:
				idea["review_task"] = task["ref"]
				changed = True
			moved = task.get("project") != project
			for field, value in (("title", "Review idea: " + idea.get("title", "")), ("project", project),
					("category", category), ("idea", idea["id"]), ("group", "Idea Reviews")):
				changed |= self.change(task, field, value, note="Linked idea updated")
			if task.get("setter_note") == task.get("idea_review_note"):
				changed |= self.change(task, "setter_note", note, note="Linked idea details updated")
			changed |= self.change(task, "idea_review_note", note)
			links = list(dict.fromkeys(list(task.get("links") or []) + list(idea.get("links") or [])))
			changed |= self.change(task, "links", links)
			if moved or task.get("idea_review_auto_closed"):
				changed |= self.change(task, "status", "Ready for Review", note="Idea needs review in this project")
				changed |= self.change(task, "archived", "")
				changed |= self.change(task, "idea_review_auto_closed", False)
			self.keep_group("proj:" + project, "Idea Reviews")
		for task in self.tasks:
			if str(task.get("link", "")).startswith("idea_review:") and task["link"] not in pending and not is_closed(task):
				changed |= self.change(task, "status", "Completed", note="Idea resolved, removed, or no longer linked to a project")
				changed |= self.change(task, "idea_review_auto_closed", True)
		return changed

	def sync_music(self, mods, stations, statuses=None, artwork=None):
		"""Music Master's planned stations -> the RR Music Mods project: a task per music mod, under it a task per planned
		station, under that Research Music / Upload Tracks / Create Radio Icon. mods: {key: name}; stations:
		[(plan id, title, music mod key)]. statuses: optional {plan id: Music Master status}; artwork: ids with attached art."""
		changed = False
		if not self.project(MUSIC_PROJECT):
			self.data["projects"].append({"name": MUSIC_PROJECT, "lead": "", "set_by": self.me.get(), "created": stamp(),
										  "note": "Kept by Music Master: a task per music mod, a sub-task per planned station."})
			changed = True
		if "Music" not in self.data["categories"]:
			self.data["categories"].append("Music")
			changed = True

		def mod_task(key):
			nonlocal changed
			title = mods.get(key) or NO_MUSIC_MOD
			t = self.linked("music_mod:" + key)
			if t is None:
				t = self.add_task(title, project=MUSIC_PROJECT, category="Music", link="music_mod:" + key)
				changed = True
			elif t.get("title") != title:
				t["title"] = title
				changed = True
			return t
		live = set()
		for pid, title, key in stations:
			live.add(pid)
			m = mod_task(key or "")
			st = self.linked("music_station:" + pid)
			if st is None:
				st = self.add_task(title, project=MUSIC_PROJECT, category="Music", parent=m["ref"], link="music_station:" + pid,
								   setter_note="Planned station in Music Master.")
				for step, name in MUSIC_STEPS:
					self.add_task(name, project=MUSIC_PROJECT, category="Music", parent=st["ref"], link=f"music_step:{pid}:{step}")
				changed = True
			else:
				if st.get("title") != title:
					st["title"] = title
					changed = True
				if st.get("parent") != m["ref"]:
					changed |= self.change(st, "parent", m["ref"], note=f"music mod -> {m['title']}")
				if st.get("project") != MUSIC_PROJECT:
					changed |= self.change(st, "project", MUSIC_PROJECT)
			status = (statuses or {}).get(pid)
			steps = {"Uploading Songs": ("research",), "Awaiting Art": ("research", "upload")}.get(status, ())
			for step in steps:
				task = self.linked(f"music_step:{pid}:{step}")
				if task:
					changed |= self.change(task, "status", "Completed", note=f"Music Master: {status}")
			if pid in (artwork or ()):
				task = self.linked(f"music_step:{pid}:icon")
				if task:
					changed |= self.change(task, "status", "Completed", note="Music Master: artwork attached to the planned station")
		for t in self.tasks:
			link = t.get("link", "")
			if link.startswith("music_station:") and link[14:] not in live and not is_closed(t):
				self.change(t, "status", "Not Possible", note="its planned station was deleted in Music Master")
				changed = True
		if changed:
			self.save()
			self.fill_filters()
			self.fill()
		return changed

	# ---------- portraits marked in Country Master -> Art Reviews ----------
	def import_master_activity(self):
		pending = master_activity.pending(self.app.mod_root)
		if not pending:
			return False
		known = {e["id"] for e in self.data.get("master_activity", [])}
		paths, changed = [], False
		for path, event in pending:
			if event["id"] in known:
				paths.append(path)
				continue
			dev = next((d for d in self.data["devs"] if event["who"].casefold() in
				{d["name"].casefold(), (d.get("git") or "").casefold()}), None)
			if not dev:
				continue  # Preserve the event until this identity is added/mapped in the Dev list.
			event = dict(event, who=dev["name"])
			if event["action"] == "state_review":
				if event.get("master") != "Culture Master" or not self.import_state_review(event):
					continue
			if event["action"] == "country_review":
				if event.get("master") != "Country Master" or not self.import_country_review(event):
					continue
			if event["action"] == "add_task":  # (an AI's task, from ai_tasks.py: added live, no restart)
				self.import_ai_task(event)
			if event["action"] in ("portrait_unmarked", "portrait_marked") and event.get("sprite"):
				sprite, st = str(event["sprite"]), event.get("state") or {}
				if event["action"] == "portrait_unmarked":
					gfx_master.unmark(self.data, gfx_master.portrait_key(sprite), dev["name"])
				else:  # (🔁 Needs Rework in GFX, for everyone)
					path = portrait_links.resolve_portraits(self.app.mod_root, [sprite]).get(sprite)
					gfx_master.mark_portrait(self.data, sprite, st.get("cat"), used=st.get("used", ""), when=(event.get("when") or "")[:10],
											 by=dev["name"], note=st.get("note", ""), kind=st.get("kind", "generic"), file=self.mod_rel(path))
				self.rework_task()
			self.data.setdefault("master_activity", []).append(event)
			known.add(event["id"])
			paths.append(path)
			changed = True
		if paths:
			self.save(undoable=False, feedback=False)  # Acknowledge only after the shared local copy is saved.
			master_activity.acknowledge(paths)
		if changed:
			self.fill()
		return changed

	def import_ai_task(self, event):
		"""A task Claude / ChatGPT asked for (ai_tasks.py). Skipped when one with the same key or title is already there
		(open or done), so sending a list twice is harmless."""
		st = event.get("state") if isinstance(event.get("state"), dict) else {}
		title = " ".join(str(st.get("title") or "").split())
		if not title:
			return False
		link = f"ai_task:{st['key']}" if st.get("key") else ""
		request = str(st.get("key") or "").startswith("request-")  # (💬 a master's Request: two can share a title)
		if (link and self.linked(link)) or (not request and any(t.get("title", "").casefold() == title.casefold() for t in self.tasks)):
			return False
		project = str(st.get("project") or "")
		if project and not self.project(project):
			self.data["projects"].append({"name": project, "lead": "", "set_by": event["who"], "created": event["when"], "note": "", "icon": ""})
		category = str(st.get("category") or "")
		if category and category not in self.data["categories"]:
			self.data["categories"].append(category)
		names = {d["name"] for d in self.data["devs"]}
		parent = st.get("parent") if self.task(st.get("parent") or "") else ""
		for step in st.get("under") or []:  # (Requests > Culture Master: found in the project, or made the first time)
			step = " ".join(str(step).split())
			if not step:
				continue
			found = next((t for t in self.tasks if t.get("title", "").casefold() == step.casefold()
						  and (t.get("parent") or "") == parent and (parent or t.get("project", "") == project)), None)
			if found is None:
				found = self.add_task(step, project=project, category=str(st.get("under_category") or category), parent=parent, set_by=event["who"],
									  setter_note="💬 Requests from the masters' Request button land here.")
			parent = found["ref"]
		t = self.add_task(title, project=project, category=category, setter_note=str(st.get("note") or ""), link=link, parent=parent,
						  devs=[d for d in st.get("devs") or [] if d in names], set_by=event["who"],
						  priority=st.get("priority") if st.get("priority") in PRIORITIES else "Normal")
		t["history"][0]["who"] = event["who"]
		self.app.set_status(f"To Do: {event['who']} added {t['ref']} {title}.")
		return True

	def import_state_review(self, event):
		"""One task for a named region, or one per individually flagged state; retries stay idempotent."""
		state = event.get("state")
		if not isinstance(state, dict):
			return False
		members = state.get("states")
		if members is not None:
			if not isinstance(members, list) or not members or not re.fullmatch(r"[a-f0-9]{32}", str(state.get("review_id", ""))):
				return False
			if any(not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0 for row in members):
				return False
			members = list({row["id"]: row for row in members}.values())
			title = str(state.get("title") or "Regional Cultures Review").strip()
			key = "culture_region_review:" + state["review_id"]
		else:
			if type(state.get("id")) is not int or state["id"] <= 0:
				return False
			members = [state]
			title = f"Review {state.get('name') or 'State ' + str(state['id'])} (state {state['id']})"
			key = f"culture_state_review:{state['id']}"
		project = state_review.PROJECT
		if not self.project(project):
			self.data["projects"].append({"name": project, "lead": "", "set_by": event["who"],
				"created": event["when"], "note": "", "icon": "globe"})
		if "Culture" not in self.data["categories"]:
			self.data["categories"].append("Culture")
		note = f"Flagged for Review in Culture Master by {event['who']} ({state.get('system') or 'culture'})."
		note += "\nStates: " + "; ".join(f"{row['id']}: {row.get('name') or 'State'}" for row in members)
		if state.get("note"):
			note += "\n" + str(state["note"])
		reasons = [reason for reason in state_review.REASONS if reason in (state.get("reasons") or [])]
		if reasons:
			note += "\nReview reasons: " + ", ".join(reasons)
		task = self.linked(key)
		if task is None:
			task = self.add_task(title, project=project, category="Culture", icon="magnifier",
				link=key, setter_note=note, set_by=event["who"])
			task["history"][0]["who"] = event["who"]
		else:
			self.change(task, "setter_note", (task.get("setter_note") or "") + "\n\n" + note, who=event["who"])
			if is_closed(task):
				self.change(task, "review_approvals", {}, who=event["who"])
				self.change(task, "status", TODO, who=event["who"], note="Explicitly flagged for review again in Culture Master")
				if task.get("archived"):
					self.change(task, "archived", "", who=event["who"])
		for field, value in (("project", project), ("group", state_review.GROUP), ("review_reasons", reasons)):
			self.change(task, field, value, who=event["who"])
		self.keep_group("proj:" + project, state_review.GROUP)
		if state.get("states") is not None:
			self.change(task, "review_states", members, who=event["who"])
			if isinstance(state.get("map"), dict):
				self.change(task, "review_map", state["map"], who=event["who"])
		else:
			composition = state.get("snapshot")
			if isinstance(composition, dict) and composition.get("id") == state["id"]:
				self.change(task, "review_snapshot", composition, who=event["who"])
		links = list(task.get("links") or [])
		for row in members:
			path = row.get("file")
			if isinstance(path, str):
				path = path.replace("\\", "/")
				if path.startswith("history/states/") and ".." not in path.split("/") and path.endswith(".txt") and path not in links:
					links.append(path)
		self.change(task, "links", links, who=event["who"])
		if state.get("system") in ("culture", "religion", "language"):
			self.change(task, "review_system", state["system"], who=event["who"])
		return True

	def import_country_review(self, event):
		"""Country Master > Flag for Review...: one task per country (flagging it again updates and reopens it)."""
		c = event.get("state")
		if not isinstance(c, dict) or not re.fullmatch(r"[A-Z0-9]{3}", str(c.get("tag", ""))):
			return False
		tag, who = c["tag"], event["who"]
		project = country_review.PROJECT
		if not self.project(project):
			self.data["projects"].append({"name": project, "lead": "", "set_by": who, "created": event["when"], "note": "", "icon": "flag"})
		if "Country" not in self.data["categories"]:
			self.data["categories"].append("Country")
		reasons = [r for r in country_review.REASONS if r in (c.get("reasons") or [])]
		note = f"Flagged for Review in Country Master by {who}." + (f"\nReview reasons: {', '.join(reasons)}" if reasons else "") \
			+ (f"\n{c['note']}" if c.get("note") else "")
		key = country_review.LINK + tag
		task = self.linked(key)
		if task is None:
			task = self.add_task(f"Review {c.get('name') or tag} ({tag})", project=project, category="Country", icon=f"flag:{tag}",
								 link=key, setter_note=note, set_by=who)
			task["history"][0]["who"] = who
		else:
			self.change(task, "setter_note", (task.get("setter_note") or "") + "\n\n" + note, who=who)
			if is_closed(task):
				self.change(task, "review_approvals", {}, who=who)
				self.change(task, "status", TODO, who=who, note="Flagged for review again in Country Master")
				if task.get("archived"):
					self.change(task, "archived", "", who=who)
		snap = {k: c.get(k) for k in ("tag", "name", "ruling", "leaders", "characters", "ideas", "states", "cores", "files", "fingerprint")}
		for field, value in (("project", project), ("group", country_review.GROUP), ("review_reasons", reasons), ("review_country", snap)):
			self.change(task, field, value, who=who)
		self.keep_group("proj:" + project, country_review.GROUP)
		links = list(task.get("links") or [])
		for rel in c.get("files") or []:
			rel = str(rel).replace("\\", "/")
			if ".." not in rel.split("/") and rel.endswith(".txt") and rel not in links:
				links.append(rel)
		self.change(task, "links", links, who=who)
		return True

	def approve_country_review(self, task, approve, fingerprint):
		task = self.task(task["ref"])
		if task is None:
			return
		self.flush_notes()
		values = dict(task.get("review_approvals") or {})
		values["country"] = dict(approved=bool(approve), by=self.me.get(), when=stamp(), fingerprint=fingerprint)
		self.change(task, "review_approvals", values, note="Country approved" if approve else "Country approval removed")
		if approve:
			if not devs_of(task):
				self.change(task, "devs", [self.me.get()], note="Country review approval")
			self.change(task, "status", "Completed", note="Country approved")
		elif task.get("status") == "Completed":
			self.change(task, "status", TODO, note="Country approval removed")
			if task.get("archived"):
				self.change(task, "archived", "")
		self.save()
		self.fill_filters()
		self.fill()
		self.show_task(task["ref"])

	def reconcile_review_approvals(self):
		changed = False
		for task in self.tasks:
			if not state_review.all_approved(task) or task.get("status") == "Completed":
				continue
			approvals = task.get("review_approvals") or {}
			people = list(dict.fromkeys(value.get("by") for value in approvals.values() if value.get("approved") and value.get("by")))
			if not devs_of(task) and people:
				self.change(task, "devs", people, note="State review approvals")
			if task.get("archived"):
				self.change(task, "archived", "")
			changed |= self.change(task, "status", "Completed", note="All states approved")
		return changed

	def invalidate_review_states(self, states):
		task = self.task((self.state_review_panel.task or {}).get("ref"))
		if task is None:
			return
		values = dict(task.get("review_approvals") or {})
		for sid in states:
			values[str(sid)] = dict(approved=False, by="Organisation Master", when=stamp(), reason="State changed after approval")
		self.change(task, "review_approvals", values, note="Saved state composition changed after approval", who="Organisation Master")
		if task.get("status") == "Completed":
			self.change(task, "status", TODO, note="State changes need approval", who="Organisation Master")
			if task.get("archived"):
				self.change(task, "archived", "")
		self.save(undoable=False, feedback=False)
		ref, sid = task["ref"], self.state_review_panel.current_sid
		def refresh_review():
			keep = (self.state_review_panel.task or {}).get("ref") == ref
			self.fill_filters()
			self.fill()
			if keep:
				self.show_task(ref)
				self.state_review_panel.show(self.task(ref), sid)
		self.after_idle(refresh_review)

	def approve_review_state(self, sid, approve, fingerprint=None):
		task = self.task((self.state_review_panel.task or {}).get("ref"))
		if task is None or sid not in state_review.review_ids(task):
			return
		self.flush_notes()
		values = dict(task.get("review_approvals") or {})
		changed = self.state_review_panel.status(sid) == "changed"
		values[str(sid)] = dict(approved=bool(approve), by=self.me.get(), when=stamp(), fingerprint=fingerprint)
		self.change(task, "review_approvals", values, note=f"State {sid}: " + ("changes approved" if approve and changed else "approved as is" if approve else "approval removed"))
		if not approve and task.get("status") == "Completed":
			self.change(task, "status", TODO, note="State approval removed")
			if task.get("archived"):
				self.change(task, "archived", "")
		self.reconcile_review_approvals()
		self.save()
		self.fill_filters()
		self.fill()
		self.show_task(task["ref"])

	def watch_master_activity(self):
		if not self.winfo_exists():
			return
		try:
			self.import_master_activity()
			if self.reconcile_review_approvals():
				self.save(undoable=False, feedback=False)
				self.fill()
			month = now().strftime("%Y-%m")
			if getattr(self, "_achievement_month", None) != month:
				self._achievement_month = month
				self.save(undoable=False, feedback=False)  # Finalize badges after the calendar month ends.
		except OSError:
			pass  # Keep inbox files to retry; never lose saved work because the live copy is temporarily unavailable.
		self.after(2000, self.watch_master_activity)

	def art_file(self):
		cm = os.path.join(os.path.dirname(TOOL_DIR), "country_master")
		new = os.path.join(cm, "portraits_to_rework.txt")
		return new if os.path.exists(new) else os.path.join(cm, "generics_to_rework.txt")

	def watch_art(self):
		"""Country Master writes the marks (another program): looked at every few seconds."""
		if not self.winfo_exists():
			return
		try:
			m = os.path.getmtime(self.art_file())
		except OSError:
			m = 0
		if m != getattr(self, "_art_mtime", None):
			self._art_mtime = m
			self.sync_art()
		self.after(3000, self.watch_art)

	def read_art(self):
		"""This mod's marks: {sprite: (category, used by, marked on, generic / portrait, note)} (Country Master's file)."""
		mod = os.path.basename(os.path.normpath(self.app.mod_root))
		out = {}
		try:
			lines = open(self.art_file(), encoding="utf-8").read().splitlines()
		except OSError:
			return None  # Missing/unreadable local marks are not evidence that shared work is finished.
		for line in lines:
			parts = [p.strip() for p in line.split(" | ")]
			if line.lstrip().startswith("#") or len(parts) < 3 or parts[0] != mod:
				continue
			cat, rest = (parts[2], parts[3:]) if len(parts) > 3 else ("Needs Touchup", parts[2:])
			used = rest[0] if rest else ""
			kind = rest[2] if len(rest) > 2 else ("portrait" if re.search(r"\(\w+ (large|small)\)$", used) else "generic")
			out[parts[1]] = (cat, used, rest[1] if len(rest) > 1 else "", kind, rest[3] if len(rest) > 3 else "")
		return out

	def sync_art(self, quiet=False):
		"""🔁 Portraits marked for rework in Country Master are in 🖼 GFX > Needs Rework, shared and live (not in the To Do):
		this PC's Country Master list adds any it has that aren't there yet (not ones reworked since it was marked), the old
		per-portrait To Do tasks move there once, and the To Do keeps one shared task while anything waits."""
		if not hasattr(self, "_art_watch"):
			self._art_watch = True
			self.after(3000, self.watch_art)
		changed = repair_legacy_portraits(self.data)
		marks = self.read_art() or {}
		store = gfx_master.rework_store(self.data)
		new = [sp for sp, m in marks.items() if gfx_master.portrait_key(sp) not in store
			   and not gfx_master.done_since(self.data, gfx_master.portrait_key(sp), m[2])]
		old = [t for t in self.tasks if portrait_sprite(t)]
		files = portrait_links.resolve_portraits(self.app.mod_root, new + [portrait_sprite(t) for t in old]) if new or old else {}
		for sprite in new:
			cat, used, when, kind, why = marks[sprite]
			changed |= gfx_master.mark_portrait(self.data, sprite, cat, used=used, when=when, by=self.me.get(), note=why,
												kind="leader" if kind == "portrait" else "generic", file=self.mod_rel(files.get(sprite)))
		changed |= self.move_portrait_tasks(old, files)
		changed |= self.rework_task()
		if changed:
			self.save()
			if not quiet:
				self.fill_filters()
				self.fill()
		return changed

	def fold_portrait_tasks(self):
		"""Per-portrait review tasks (and their Generic / Portrait Review parents) that came back from an older build: into the
		🔁 rework list, so the To Do keeps its one task. True when it changed."""
		old = [t for t in self.tasks if portrait_sprite(t)]
		if not old and not any(str(t.get("link") or "") in ("art_review:generic", "art_review:portrait", REWORK_LINK) for t in self.tasks):
			return False
		files = portrait_links.resolve_portraits(self.app.mod_root, [portrait_sprite(t) for t in old]) if old else {}
		changed = self.move_portrait_tasks(old, files)
		return self.rework_task() or changed

	def mod_rel(self, path):
		"""A file of the mod as mod-relative (forward slashes); others as they are; None -> "". (portrait_links gives
		mod-relative paths already, and "game:<path>" for the base game's: kept, every PC finds its own game.)"""
		if not path:
			return ""
		if path.startswith("game:") or not os.path.isabs(path):
			return path.replace("\\", "/")
		root = os.path.normcase(os.path.abspath(self.app.mod_root))
		return os.path.relpath(path, self.app.mod_root).replace("\\", "/") if os.path.normcase(os.path.abspath(path)).startswith(root + os.sep) else path

	def move_portrait_tasks(self, old, files):
		"""Once: the per-portrait Art Reviews tasks (and their Generic / Portrait Review parents) become 🔁 Needs Rework
		entries in GFX (category, who marked it and when, what's wrong, who claimed it); the tasks go to the 🗑 Trash."""
		parents = [t for t in self.tasks if str(t.get("link") or "") in ("art_review:generic", "art_review:portrait")]
		if not old and not parents:
			return False
		kinds = {t["ref"]: t["link"][len("art_review:"):] for t in parents}
		for t in old:
			sprite = portrait_sprite(t)
			if not is_closed(t) and not gfx_master.done_since(self.data, gfx_master.portrait_key(sprite), (t.get("created") or "")[:10]):
				note = t.get("setter_note") or ""
				used = re.search(r"Used by (.*?)(?: \(marked [^)]*\))?\.(?:\n|$)", note)
				why = re.search(r"What's wrong: (.*)", note)
				gfx_master.mark_portrait(self.data, sprite, t.get("group"), used=used.group(1) if used else "", when=(t.get("created") or "")[:10],
										 by=t.get("set_by", ""), note=" / ".join(x for x in ((why.group(1) if why else ""), t.get("dev_note", "")) if x),
										 kind="leader" if kinds.get(t.get("parent")) == "portrait" else "generic", claimed=devs_of(t),
										 file=self.mod_rel(files.get(sprite)))
			self.record_deletion("tasks", t, "ref")
			self.tasks.remove(t)
		claimed = sorted({d for t in parents for d in devs_of(t)})
		for t in parents:
			self.record_deletion("tasks", t, "ref")
			self.tasks.remove(t)
		if claimed:
			self._rework_claimed = claimed  # (the shared rework task starts with whoever had the old review tasks)
		gone = {t["ref"] for t in old + parents}
		for o in self.tasks:
			if o.get("parent") in gone:
				o["parent"] = ""
		self.app.set_status(f"🔁 {len(old)} portrait rework tasks moved to 🖼 GFX > Needs Rework (the old tasks are in the 🗑 Trash).")
		return True

	def rework_task(self):
		"""The To Do's tasks for the 🔁 rework list, one per kind of picture (🔁 Rework Generics, 🔁 Rework Portraits, and one
		for any other GFX section that gets marks, e.g. 🔁 Rework Flags): open while anything of that kind waits, completed
		when none do. Shared reviews: claimable, but in the General To Do for everyone. True when something changed."""
		changed = False
		old = self.linked(REWORK_LINK)  # (the one task for everything, before the split: its devs carry over)
		if old is not None:
			self._rework_claimed = sorted(set(getattr(self, "_rework_claimed", [])) | set(devs_of(old)))
			self.record_deletion("tasks", old, "ref")
			self.tasks.remove(old)
			changed = True
		groups = {}
		for m in gfx_master.rework_store(self.data).values():
			groups.setdefault(rework_group(m), []).append(m)
		for t in self.tasks:  # (kinds with nothing left: their task is completed)
			key = str(t.get("link") or "")
			if key.startswith(REWORK_LINK + ":") and key[len(REWORK_LINK) + 1:] not in groups and not is_closed(t):
				self.change(t, "status", "Completed", note="Nothing of this kind left in 🖼 GFX > 🔁 Needs Rework")
				changed = True
		if groups and not self.project(ART_PROJECT):
			self.data["projects"].append({"name": ART_PROJECT, "lead": "", "set_by": self.me.get(), "created": stamp(), "note": "", "icon": "picture"})
		for group, marks in sorted(groups.items()):
			n, name = len(marks), rework_group_name(group)
			by = collections.Counter(m.get("reason", "?") for m in marks)
			title = f"🔁 Rework {name} ({n} waiting in 🖼 GFX)"
			note = (f"{n} {name.lower()} marked for rework: " + ", ".join(f"{k} {v}" for k, v in by.most_common()) +
					".\nThey're in 🖼 GFX > 🔁 Needs Rework: claim one there, ✓ Reworked when done. Mark more in Country Master "
					"(right-click a portrait) or in GFX (right-click a picture).")
			link = f"{REWORK_LINK}:{group}"
			t = self.linked(link)
			if t is None:
				self.add_task(title, project=ART_PROJECT, category="Art", link=link, setter_note=note, icon="picture",
							  devs=getattr(self, "_rework_claimed", []))
				changed = True
				continue
			for field, value in (("title", title), ("setter_note", note), ("project", ART_PROJECT)):
				if t.get(field) != value:
					t[field] = value
					changed = True
			if is_closed(t):
				self.change(t, "status", TODO, note="Pictures of this kind marked for rework again")
				changed = True
		return changed

	def record_deletion(self, collection, item, key, trash=True, **extra):
		"""Only an explicit delete/rename may remove shared work during sync. trash: keep a copy for the 🗑 Trash."""
		entry = {"created": item.get("created"), "when": stamp(), "who": self.me.get()}
		if trash:
			entry["item"] = copy.deepcopy(item)
			entry.update(extra)
		self.data.setdefault("deleted_" + collection, {})[item[key]] = entry

	# ---------- ⏰ Stale tasks: claimed, open and untouched for a while (leads see everyone's, devs their own) ----------
	def last_touched(self, t):
		whens = [h.get("when") or "" for h in t.get("history", [])] + [t.get("updated") or "", t.get("created") or ""]
		return parse_time(max(whens)) if any(whens) else None

	def stale_tasks(self, everyone=None):
		"""[(task, idle days)] most idle first. everyone: a lead's view (default: leads see all, others their own)."""
		days = int(self.app.config.get("nudge_days", 21))
		everyone = self.is_lead() if everyone is None else everyone
		me, today = self.me.get(), now()
		out = []
		for t in self.tasks:
			if is_closed(t) or not devs_of(t) or t.get("status") in (FLESHING, "Ready for Review") or t.get("blocked") or self.waiting_on(t):
				continue
			if not everyone and me not in devs_of(t):
				continue
			if (t.get("snoozed_until") or "") > stamp():
				continue
			last = self.last_touched(t)
			idle = (today - last).days if last else 0
			if idle >= days:
				out.append((t, idle))
		return sorted(out, key=lambda x: -x[1])

	def update_nudge_button(self):
		b = getattr(self, "nudge_btn", None)
		if b is not None and b.winfo_exists():
			n = len(self.stale_tasks())
			b.config(text="⏰ Stale tasks" + (f" ({n})" if n else ""))

	def remind_stale(self):
		"""A quiet line at start-up about your own stale tasks."""
		mine = self.stale_tasks(everyone=False)
		if mine:
			self.app.set_status(f"⏰ {len(mine)} of your tasks haven't moved in {self.app.config.get('nudge_days', 21)}+ days: "
								f"⏰ Stale tasks (tool row) lists them.")
		self.update_nudge_button()

	def nudge_text(self, rows):
		by_dev = {}
		for t, idle in rows:
			for d in devs_of(t):
				by_dev.setdefault(d, []).append((t, idle))
		out = []
		for d, items in by_dev.items():
			out.append(f"**{d}**, a friendly nudge: these haven't moved in a while - still on them? (or Leave / Blocked if not)")
			out += [f"- {t['ref']} {t.get('title', '')} ({idle} days)" for t, idle in items]
			out.append("")
		return "\n".join(out).strip()

	def open_nudges(self):
		lead = self.is_lead()
		w = tk.Toplevel(self)
		w.title("⏰ Stale tasks")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="⏰ Stale tasks", style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text=("Claimed, open tasks nobody has touched in a while (blocked, waiting, in review and Needs Fleshing ones "
						   "aren't counted). " + ("As a lead you see everyone's." if lead else "Yours; leads see everyone's.")),
				  style="Muted.TLabel", wraplength=ui.px(640), justify="left").pack(anchor="w", pady=(2, 6))
		row = ttk.Frame(f)
		row.pack(fill="x", pady=(0, 6))
		ttk.Label(row, text="Untouched for at least").pack(side="left")
		days = tk.IntVar(value=int(self.app.config.get("nudge_days", 21)))
		ttk.Spinbox(row, from_=3, to=365, textvariable=days, width=5, command=lambda: changed_days()).pack(side="left", padx=4)
		ttk.Label(row, text="days (yours to set)").pack(side="left")
		box = ttk.Frame(f, height=ui.px(320), width=ui.px(680))
		box.pack_propagate(False)
		box.pack(fill="both", expand=True)
		t = ttk.Treeview(box, columns=("devs", "idle", "last"), show="tree headings", selectmode="extended")
		for col, text, width in (("#0", "Task", 340), ("devs", "Dev(s)", 140), ("idle", "Idle", 70), ("last", "Last change", 110)):
			t.heading(col, text=text)
			t.column(col, width=ui.px(width), stretch=col == "#0", anchor="e" if col == "idle" else "w")
		ys = ttk.Scrollbar(box, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		rows = {}
		note = ttk.Label(f, text="", style="Muted.TLabel")
		note.pack(anchor="w", pady=(4, 0))

		def fill():
			t.delete(*t.get_children())
			rows.clear()
			for task, idle in self.stale_tasks():
				iid = t.insert("", "end", text=f"{task['ref']}  {task.get('title', '')}",
							   values=(", ".join(devs_of(task)), f"{idle} days", short_date(stamp(self.last_touched(task))) if self.last_touched(task) else "-"))
				rows[iid] = (task, idle)
			ui.stripe(t)
			note.config(text=f"{len(rows)} stale" if rows else "Nothing stale. 🎉")
			self.update_nudge_button()

		def changed_days():
			try:
				self.app.config["nudge_days"] = max(1, int(days.get()))
			except (tk.TclError, ValueError):
				return
			self.app.save_config()
			fill()

		def picked():
			return [rows[i] for i in t.selection() if i in rows] or list(rows.values())

		def copy_nudge():
			text = self.nudge_text(picked())
			if text:
				self.clipboard_clear()
				self.clipboard_append(text)
				self.app.set_status("Nudge copied: paste it on Discord.")

		def snooze():
			for task, _ in [rows[i] for i in t.selection() if i in rows]:
				task["snoozed_until"] = stamp(now() + datetime.timedelta(days=14))
				task["updated"] = stamp()
			self.save()
			fill()

		def go():
			sel = [rows[i] for i in t.selection() if i in rows]
			if sel:
				w.destroy()
				self.go_to(sel[0][0]["ref"])
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(8, 0))
		ttk.Button(bf, text="Go to", command=go).pack(side="left")
		ttk.Button(bf, text="📋 Copy a nudge (selected, or all)", command=copy_nudge).pack(side="left", padx=6)
		ttk.Button(bf, text="💤 Snooze 2 weeks", command=snooze).pack(side="left")
		ttk.Button(bf, text="Close", command=w.destroy).pack(side="right")
		t.bind("<Double-1>", lambda ev: go())
		fill()
		self._nudges = (t, rows, fill, copy_nudge, snooze)  # (for tests)

	# ---------- 🗑 Trash: deleted tasks, projects and ideas, restorable ----------
	TRASH_DAYS = 90  # (copies older than this are let go when the To Do loads; the delete itself stays recorded)

	def trash_items(self):
		"""[(kind, key, entry)] newest first: what can still be restored."""
		out = []
		for kind, field in (("task", "deleted_tasks"), ("project", "deleted_projects"), ("idea", "deleted_ideas")):
			for key, entry in (self.data.get(field) or {}).items():
				if entry.get("item") and not entry.get("restored"):
					out.append((kind, key, entry))
		return sorted(out, key=lambda x: x[2].get("when", ""), reverse=True)

	def run_data_check(self, quiet=False):
		"""🩺 data_check: the safe fixes saved (and synced), a status line when it found anything."""
		import data_check
		fixed, problems = data_check.check(self.data)
		if fixed:
			self.save(undoable=False, feedback=False)
			self.fill()
			self.idea_pane.fill()
		if not quiet and (fixed or problems):
			self.app.set_status(f"🩺 Data check: {len(fixed)} fixed" + (f", {len(problems)} need a person" if problems else "")
								+ " (Settings > Check the To Do data...)")
		return fixed, problems

	def tidy_trash(self):
		cutoff = stamp(now() - datetime.timedelta(days=self.TRASH_DAYS))
		changed = False
		for field in ("deleted_tasks", "deleted_projects", "deleted_ideas"):
			for key, entry in list((self.data.get(field) or {}).items()):
				if entry.get("when", "") < cutoff and (entry.get("item") or field == "deleted_ideas"):
					if field == "deleted_ideas":
						self.data[field].pop(key)
					else:
						entry.pop("item", None)
					changed = True
		return changed

	def restore_from_trash(self, kind, key):
		field = {"task": "deleted_tasks", "project": "deleted_projects", "idea": "deleted_ideas"}[kind]
		entry = (self.data.get(field) or {}).get(key)
		if not entry or not entry.get("item"):
			return None
		item = copy.deepcopy(entry["item"])
		if kind == "task":
			if self.task(item["ref"]):
				item["ref"] = self.new_ref()  # (its number was given out again meanwhile)
			if item.get("parent") and not self.task(item["parent"]):
				item["parent"] = ""
			if item.get("project") and not self.project(item["project"]):
				item["project"] = ""
			item.setdefault("history", []).append({"when": stamp(), "who": self.me.get(), "field": "restored", "old": None, "new": None,
												   "note": "restored from the Trash"})
			item["updated"] = stamp()
			self.tasks.append(item)
			what = f"{item['ref']} {item.get('title', '')}"
		elif kind == "project":
			if self.project(item["name"]):
				messagebox.showerror(APP_NAME, f"There's already a project called {item['name']}: rename it first.", parent=self)
				return None
			self.data["projects"].append(item)
			for ref in entry.get("members", []):  # (its tasks that are still without a project go back in)
				t = self.task(ref)
				if t is not None and not t.get("project"):
					self.change(t, "project", item["name"], note="its project was restored")
			what = f"📁 {item['name']}"
		else:
			if self.idea_pane.idea(item["id"]) is None:
				self.data.setdefault("ideas", []).append(item)
			what = f"💡 {item.get('title', '')}"
		if kind == "idea":
			self.data[field].pop(key)
		else:
			entry.update(restored=stamp(), when=stamp(), restored_by=self.me.get())
			entry.pop("item", None)
		self.save()
		self.fill_filters()
		self.fill()
		self.idea_pane.fill()
		self.app.set_status(f"Restored {what} from the Trash.")
		return item

	def open_trash(self):
		w = tk.Toplevel(self)
		w.title("🗑 Trash")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="🗑 Trash", style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text=f"Deleted tasks, projects and ideas, for everyone (it syncs). Restore puts one back as it was; they're kept "
						  f"for {self.TRASH_DAYS} days.", style="Muted.TLabel", wraplength=ui.px(620), justify="left").pack(anchor="w", pady=(2, 8))
		box = ttk.Frame(f, height=ui.px(300), width=ui.px(640))
		box.pack_propagate(False)
		box.pack(fill="both", expand=True)
		t = ttk.Treeview(box, columns=("kind", "who", "when"), show="tree headings", selectmode="extended")
		for col, text, width in (("#0", "What", 330), ("kind", "Kind", 70), ("who", "Deleted by", 100), ("when", "When", 120)):
			t.heading(col, text=text)
			t.column(col, width=ui.px(width), stretch=col == "#0")
		ys = ttk.Scrollbar(box, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		rows = {}

		def fill():
			t.delete(*t.get_children())
			rows.clear()
			for kind, key, entry in self.trash_items():
				item = entry["item"]
				title = {"task": f"{item.get('ref', key)}  {item.get('title', '')}", "project": f"📁 {item.get('name', key)}",
						 "idea": f"💡 {item.get('title', '')}"}[kind]
				iid = t.insert("", "end", text=title, values=(kind, entry.get("who", "?"), short_date(entry.get("when"))))
				rows[iid] = (kind, key)
			ui.stripe(t)
			empty.config(text="" if rows else "The trash is empty.")

		def restore():
			picked = [rows[i] for i in t.selection() if i in rows]
			for kind, key in picked:
				self.restore_from_trash(kind, key)
			fill()
		empty = ttk.Label(f, text="", style="Muted.TLabel")
		empty.pack(anchor="w", pady=(4, 0))
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(8, 0))
		ttk.Button(bf, text="↩ Restore selected", command=restore).pack(side="left")
		ttk.Button(bf, text="Close", command=w.destroy).pack(side="right")
		t.bind("<Double-1>", lambda ev: restore())
		fill()
		self._trash = (t, rows, restore, fill)  # (for tests)

	def delete(self, tasks):
		if not messagebox.askyesno(APP_NAME, f"Delete {', '.join(t['ref'] for t in tasks)} for good?\n\n"
											 "(Completed tasks are better left in the archive: their reference stays findable.)"):
			return
		gone = {t["ref"] for t in tasks}
		for t in tasks:
			self.record_deletion("tasks", t, "ref")
			self.tasks.remove(t)
		for o in self.tasks:  # sub-tasks and blocked tasks of the deleted ones
			if o.get("parent") in gone:
				o["parent"] = ""
			if set(o.get("depends_on", [])) & gone:
				o["depends_on"] = [r for r in o["depends_on"] if r not in gone]
		self.cur = None
		self.save()
		self.fill()
		self.show_task(None)

	# ---------- new / edit ----------
	def edit_task(self, new=False, parent=None, project=None, group=""):
		if not new and not self.picked() and not self.cur:
			return
		view = self.view.get()
		fp = self.f["project"].get() if self.mode.get() == "project" else ALL  # (Dev mode: no project unless picked)
		project = parent.get("project", "") if parent else project if project is not None else (fp if fp not in (ALL, NO_PROJECT) else "")
		t = {"title": "", "devs": [self.me.get()] if view == "mine" else [], "needs_planning": view == "planning",
			 "category": self.data["categories"][0] if self.data["categories"] else "", "priority": "Normal",
			 "status": TODO, "sweep": False, "tags": [], "setter_note": "", "dev_note": "", "blocked": "", "reviewer": "",
			 "depends_on": [], "project": project, "parent": parent["ref"] if parent else "", "group": group} if new else (self.picked() or [self.cur])[0]
		self.flush_notes()
		w = tk.Toplevel(self)
		w.title("New task" if new else f"Edit {t['ref']}")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		v = {k: tk.StringVar(value=t.get(k) or "") for k in ("title", "category", "priority", "status", "blocked", "reviewer")}
		v["tags"] = tk.StringVar(value=" ".join(t.get("tags", [])))
		sweep = tk.BooleanVar(value=bool(t.get("sweep")))
		needs_ai = tk.BooleanVar(value=bool(t.get("needs_ai")))
		planning = tk.BooleanVar(value=bool(t.get("needs_planning")))
		r = 0
		ttk.Label(f, text="Task", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		e = ttk.Entry(f, textvariable=v["title"], width=80, font="om_bold")
		e.grid(row=r, column=1, columnspan=3, sticky="we")
		e.focus_set()
		r += 1
		# its icon: its own, else its category's (it follows the Category box)
		ic = {"id": t.get("icon")}
		ttk.Label(f, text="Icon", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		icf = ttk.Frame(f)
		icf.grid(row=r, column=1, columnspan=3, sticky="w")
		ib = tk.Label(icf, cursor="hand2", relief="groove", padx=4, pady=2)
		ib.pack(side="left")
		il = ttk.Label(icf, text="", style="Muted.TLabel")
		il.pack(side="left", padx=8)

		def show_icon(*_):
			own = ic["id"]
			cid = own or self.data.get("category_icons", {}).get(v["category"].get()) or CATEGORY_ICONS.get(v["category"].get()) or TASK_ICON
			ib.config(image=icons.image(cid, ui.px(28)))
			il.config(text=f"{icons.label(own)}  (click to change)" if own else f"{icons.label(cid)} - its category's  (click to choose one)")

		def choose(ev=None):
			getattr(self.app, "feedback", lambda *_: None)("icon")
			icons.pick(w, "Icon of the task", ic["id"], lambda i: (ic.update(id=i), show_icon()))
		for wd in (ib, il):
			wd.bind("<Button-1>", choose)
		v["category"].trace_add("write", show_icon)
		show_icon()
		r += 1
		ttk.Label(f, text="Dev(s)", style="Muted.TLabel").grid(row=r, column=0, sticky="nw", pady=3)
		dvf = ttk.Frame(f)
		dvf.grid(row=r, column=1, columnspan=3, sticky="w")
		dv = {}
		for i, n in enumerate(self.dev_names()):
			dv[n] = tk.BooleanVar(value=n in devs_of(t))
			ttk.Checkbutton(dvf, text=n, variable=dv[n]).grid(row=i // 5, column=i % 5, sticky="w", padx=(0, 14))
		ttk.Label(dvf, text=f"none ticked = {GENERAL} (anyone can claim it); several = shared", style="Muted.TLabel").grid(
			row=99, column=0, columnspan=5, sticky="w")
		r += 1
		for key, text in (("category", "Category"), ("priority", "Priority"), ("status", "Status"), ("reviewer", "Reviewer")):
			ttk.Label(f, text=text, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
			vals = {"category": self.data["categories"], "priority": PRIORITIES, "status": STATUSES, "reviewer": [""] + self.dev_names()}[key]
			cb = ttk.Combobox(f, textvariable=v[key], values=vals, state="readonly", width=30, font="TkDefaultFont")
			cb.sound_priority = key == "priority"
			cb.grid(row=r, column=1, sticky="w")
			if key == "category":
				ttk.Button(f, text="New category...", command=lambda cb=cb: self.new_category(None, cb, v["category"])).grid(row=r, column=2, sticky="w", padx=6)
			r += 1
		ttk.Label(f, text="Project", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		pv = tk.StringVar(value=t.get("project") or NO_PROJECT)
		pcb = ttk.Combobox(f, textvariable=pv, values=self.project_names() + [NO_PROJECT], state="readonly", width=30, font="TkDefaultFont")
		pcb.grid(row=r, column=1, sticky="w")
		r += 1
		ttk.Label(f, text="Sub-task of", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		parv = tk.StringVar()
		parcb = ttk.Combobox(f, textvariable=parv, state="readonly", width=60, font="TkDefaultFont")
		parcb.grid(row=r, column=1, columnspan=3, sticky="w")

		def parents(*_):
			proj = "" if pv.get() == NO_PROJECT else pv.get()
			opts = ["(not a sub-task)"] + [f"{o['ref']}  {o.get('title', '')}" for o in sorted(self.tasks, key=lambda x: x["ref"])
										  if o is not t and o.get("project", "") == proj and not (t.get("ref") and self.is_below(o, t))]
			parcb.config(values=opts)
			cur = t.get("parent")
			if parv.get() not in opts:
				parv.set(next((o for o in opts if cur and o.startswith(cur + " ")), opts[0]))
		r += 1
		ttk.Label(f, text="Grouping", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		gv = tk.StringVar(value=t.get("group", ""))
		gcb = ttk.Combobox(f, textvariable=gv, width=30, font="TkDefaultFont")
		gcb.grid(row=r, column=1, sticky="w")
		ttk.Label(f, text="a folder in its parent task (or its project), e.g. Europe (type a new one)", style="Muted.TLabel").grid(
			row=r, column=2, columnspan=2, sticky="w", padx=6)

		def groupings(*_):
			par = "" if parv.get().startswith("(") else parv.get().split()[0]
			proj = "" if pv.get() == NO_PROJECT else pv.get()
			gcb.config(values=self.groups_of({par}) if par else self.groups_of({"proj:" + proj}) if proj else [])
		parcb.bind("<<ComboboxSelected>>", groupings)

		def project_picked(*_):
			parents()
			groupings()
		pcb.bind("<<ComboboxSelected>>", project_picked)
		parents()
		groupings()
		r += 1
		ttk.Label(f, text="Country tags", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		ttk.Entry(f, textvariable=v["tags"], width=30, font="TkDefaultFont").grid(row=r, column=1, sticky="w")
		ttk.Label(f, text="e.g. GER FRA (empty = not for one country)", style="Muted.TLabel").grid(row=r, column=2, columnspan=2, sticky="w", padx=6)
		r += 1
		ttk.Label(f, text="Blocked (reason)", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
		ttk.Entry(f, textvariable=v["blocked"], width=80, font="TkDefaultFont").grid(row=r, column=1, columnspan=3, sticky="we")
		r += 1
		cf = ttk.Frame(f)
		cf.grid(row=r, column=1, columnspan=3, sticky="w", pady=4)
		ttk.Checkbutton(cf, text=PLANNING, variable=planning).pack(side="left")
		ttk.Checkbutton(cf, text="Part of a sweep", variable=sweep).pack(side="left", padx=16)
		ttk.Checkbutton(cf, text="🤖 Requires AI", variable=needs_ai).pack(side="left")
		r += 1
		ttk.Label(f, text="Note from the setter (shown in game)", style="Muted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
		ttk.Label(f, text="Note from the dev", style="Muted.TLabel").grid(row=r, column=2, columnspan=2, sticky="w", pady=(8, 0), padx=(10, 0))
		r += 1
		n1 = tk.Text(f, width=50, height=6, wrap="word", font="om_body", relief="solid", borderwidth=1)
		n1.grid(row=r, column=0, columnspan=2, sticky="nsew")
		n1.insert("1.0", t.get("setter_note", ""))
		n2 = tk.Text(f, width=50, height=6, wrap="word", font="om_body", relief="solid", borderwidth=1)
		n2.grid(row=r, column=2, columnspan=2, sticky="nsew", padx=(10, 0))
		n2.insert("1.0", t.get("dev_note", ""))
		r += 1
		ttk.Label(f, text="Blocked by (the tasks it waits for)", style="Muted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
		r += 1
		lb, get_deps = self.task_list(f, {t.get("ref")}, set(t.get("depends_on", [])), 7)
		lb.grid(row=r, column=0, columnspan=4, sticky="nsew")
		f.columnconfigure(1, weight=1)

		def ok():
			title = v["title"].get().strip()
			if not title:
				messagebox.showerror(APP_NAME, "What is the task?", parent=w)
				return
			follow_ups = []
			vals = {"title": title, "devs": [n for n in self.dev_names() if dv[n].get()], "category": v["category"].get(),
					"priority": v["priority"].get() or "Normal", "status": v["status"].get() or TODO, "blocked": v["blocked"].get().strip(),
					"reviewer": v["reviewer"].get(), "sweep": sweep.get(), "needs_planning": planning.get(), "needs_ai": needs_ai.get(),
					"tags": sorted({g.upper() for g in re.split(r"[\s,;]+", v["tags"].get()) if g}),
					"depends_on": get_deps(),
					"project": "" if pv.get() == NO_PROJECT else pv.get(),
					"parent": "" if parv.get().startswith("(") else parv.get().split()[0],
					"group": gv.get().strip() if not parv.get().startswith("(") or pv.get() != NO_PROJECT else ""}
			notes = {"setter_note": n1.get("1.0", "end").strip(), "dev_note": n2.get("1.0", "end").strip()}
			if vals.get("group") and (vals.get("parent") or vals.get("project")):
				self.keep_group(vals["parent"] or "proj:" + vals["project"], vals["group"])
			if new:
				ref = f"RR-{self.data['next_ref']:04d}"
				while self.task(ref):
					self.data["next_ref"] += 1
					ref = f"RR-{self.data['next_ref']:04d}"
				self.data["next_ref"] += 1
				t.update(vals, **notes, ref=ref, set_by=self.me.get(), created=stamp(), updated=stamp())
				if ic["id"]:
					t["icon"] = ic["id"]
				if t["status"] in CLOSED:
					t["closed"] = stamp()
					if t["status"] == "Completed" and not devs_of(t):
						t["devs"] = [self.me.get()]
				t["history"] = [{"when": t["created"], "who": self.me.get(), "field": "created", "old": None, "new": None}]
				self.tasks.append(t)
			else:
				if vals.get("status") == "Completed" and t.get("status") != "Completed":
					r = self.completion_prompt([t], assignments={t["ref"]: vals["devs"]})
					if r is None:
						return
					extra, review, follow_ups = r
					if review:
						follow_ups = []
						vals["status"] = "Ready for Review"
					else:
						vals["devs"] = devs_of(t)  # Keep the completion dialog's credit instead of stale edit fields.
						for c in extra:
							if c is not t:
								self.change(c, "status", "Completed", note=f"with {t['ref']}")
				for k, val in vals.items():
					if k in ("title", "tags"):
						t[k] = val  # (not recorded)
					else:
						self.change(t, k, val)
				t.update(notes)
				if ic["id"]:
					t["icon"] = ic["id"]
				else:
					t.pop("icon", None)
			for draft in follow_ups:
				self.create_follow_up(draft)
			w.destroy()
			self.save()
			self.fill_filters()
			if not self.in_view(t):
				self.view.set({"archive": "archive", "planning": "planning", "general": "general", "music": "music"}.get(lane(t), "open"))
			self.fill()
			if self.tree.exists(t["ref"]):
				self.tree.selection_set(t["ref"])
				self.tree.see(t["ref"])
			self.show_task(t["ref"])
		bf = ttk.Frame(f)
		bf.grid(row=r + 1, column=0, columnspan=4, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)
		getattr(self.app, "task_editor_sounds", lambda *_: None)(f)

	def new_category(self, tasks=None, box=None, var=None):
		name = simpledialog.askstring("New category", "Name of the category:", parent=self)
		name = (name or "").strip()
		if not name:
			return
		if name not in self.data["categories"]:
			self.data["categories"].append(name)
		if box is not None:
			box.config(values=self.data["categories"])
			var.set(name)
			self.save()
		elif tasks:
			self.set_many(tasks, "category", name)
		self.fill_filters()

	# ---------- devs / categories ----------
	def edit_list(self, title, items, add, rename, remove, extra=None):
		w = tk.Toplevel(self)
		w.title(title)
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		lb = tk.Listbox(f, width=36, height=14, exportselection=False, font="om_body")
		lb.pack(side="left", fill="both", expand=True)

		def refill():
			lb.delete(0, "end")
			for x in items():
				lb.insert("end", x)
		refill()
		bf = ttk.Frame(f)
		bf.pack(side="left", fill="y", padx=(10, 0))
		cur = lambda: lb.get(lb.curselection()[0]) if lb.curselection() else None
		ttk.Button(bf, text="Add...", command=lambda: (add(), refill())).pack(fill="x")
		ttk.Button(bf, text="Rename...", command=lambda: cur() and (rename(cur()), refill())).pack(fill="x", pady=3)
		for label_, fn in ([extra] if extra and isinstance(extra[0], str) else extra or []):
			ttk.Button(bf, text=label_, command=lambda fn=fn: cur() and (fn(cur()), refill())).pack(fill="x", pady=(0, 3))
		ttk.Button(bf, text="Remove", command=lambda: cur() and (remove(cur()), refill())).pack(fill="x", pady=3)
		ttk.Button(bf, text="Close", command=w.destroy).pack(side="bottom", fill="x")
		lb.bind("<Double-1>", lambda ev: cur() and (rename(cur()), refill()))

	def _renamed(self):
		self.save()
		self.fill_filters()
		self.fill()
		self.show_task()

	def lead_only(self, what="change the Dev list"):
		if self.is_lead():
			return True
		messagebox.showinfo(APP_NAME, f"Only leads can {what}.", parent=self)
		return False

	def add_dev(self):
		if not self.lead_only():
			return
		n = (simpledialog.askstring("New dev", "Dev's name:", parent=self) or "").strip()
		if n and n not in self.dev_names():
			g = (simpledialog.askstring("New dev", f"{n}'s git name (who they commit as; empty = the same):", parent=self) or "").strip()
			self.data["devs"].append({"name": n, "git": g or n})
			self._renamed()

	def rename_dev(self, old):
		if not old or not self.lead_only():
			return
		n = (simpledialog.askstring("Rename dev", f"New name for {old}:", initialvalue=old, parent=self) or "").strip()
		if not n or n == old:
			return
		if n in self.dev_names():
			messagebox.showerror(APP_NAME, f"There's already a dev called {n}.")
			return
		for d in self.data["devs"]:
			if d["name"] == old:
				d["name"] = n
		for t in self.tasks:
			if old in devs_of(t):
				t["devs"] = [n if d == old else d for d in devs_of(t)]
			for k in ("set_by", "reviewer"):
				if t.get(k) == old:
					t[k] = n
			for h in t.get("history", []):
				if h.get("who") == old:
					h["who"] = n
		if self.me.get() == old:
			self.me.set(n)
			self.remember_me()
		self._renamed()
		self.app.set_status(f"{old} is now {n}.")

	def git_name(self, name):
		if not self.lead_only("see or change git names"):
			return
		d = next(d for d in self.data["devs"] if d["name"] == name)
		g = simpledialog.askstring("Git name", f"Who {name} commits as (git user.name):", initialvalue=d.get("git", name), parent=self)
		if g is not None:
			d["git"] = g.strip() or name
			self.save()

	def remove_dev(self, n):
		if not self.lead_only():
			return
		open_ = [t["ref"] for t in self.tasks if n in devs_of(t) and not is_closed(t)]
		if open_ and not messagebox.askyesno(APP_NAME, f"{n} still has {len(open_)} open tasks ({', '.join(open_[:6])}). "
													   "Remove them from the list anyway? (Their tasks keep their name.)"):
			return
		self.data["devs"] = [d for d in self.data["devs"] if d["name"] != n]
		self._renamed()

	def is_lead(self, name=None):
		return bool(next((d for d in self.data["devs"] if d["name"] == (name or self.me.get())), {}).get("lead"))

	def skills(self, focus=None):
		"""Skills and Wants to learn per category. Leads see (and can change) everyone's and who's a lead; other devs
		only their own."""
		lead = self.is_lead()
		me = self.me.get()
		devs = [d for d in self.data["devs"] if lead or d["name"] == me]
		if not devs:
			messagebox.showinfo(APP_NAME, "Pick who you are first (You are, top left).")
			return
		if focus and focus != me and not lead:
			messagebox.showinfo(APP_NAME, "Only leads see other devs' skills. Here are yours.")
		cats = self.data["categories"]
		w = tk.Toplevel(self)
		w.title("Skills and wants to learn" + ("  (lead view)" if lead else ""))
		w.transient(self.winfo_toplevel())
		outer = ttk.Frame(w, padding=12)
		outer.pack(fill="both", expand=True)
		ttk.Label(outer, text="Skills and wants to learn", style="Title.TLabel").pack(anchor="w")
		ttk.Label(outer, text="Choose a developer, then mark their skills and learning interests. " + ("Leads can edit every profile."
																					  if lead else "Leads can see these."),
				  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
		# Edit one developer at a time, keeping every developer's draft until Save.
		v = {d["name"]: {"lead": tk.BooleanVar(value=bool(d.get("lead"))),
			"ai_tool": tk.BooleanVar(value=bool(d.get("ai_tool"))),
			**{key: {cat: tk.BooleanVar(value=cat in d.get(key, [])) for cat in cats}
			   for key in ("skills", "learn")}} for d in devs}
		body = ttk.Frame(outer)
		body.pack(fill="both", expand=True)
		body.rowconfigure(0, weight=1)
		body.columnconfigure(1, weight=1)
		people = ttk.LabelFrame(body, text="Developers" if lead else "Developer", padding=8)
		people.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
		people.rowconfigure(0, weight=1)
		people.columnconfigure(0, weight=1)
		people_tree = ttk.Treeview(people, show="tree", selectmode="browse", height=12)
		people_tree.column("#0", width=ui.px(185), minwidth=ui.px(130), stretch=True)
		people_tree.grid(row=0, column=0, sticky="nsew")
		ttk.Scrollbar(people, orient="vertical", command=people_tree.yview).grid(row=0, column=1, sticky="ns")
		people_tree.configure(yscrollcommand=people.grid_slaves(row=0, column=1)[0].set)
		detail = ttk.LabelFrame(body, text="Skills profile", padding=12)
		detail.grid(row=0, column=1, sticky="nsew")
		heading = ttk.Label(detail, style="Title.TLabel")
		heading.pack(anchor="w")
		counts = ttk.Label(detail, style="Muted.TLabel")
		counts.pack(anchor="w", pady=(3, 8))
		lead_box = ttk.Checkbutton(detail, text="Team lead") if lead else None
		if lead_box:
			lead_box.pack(anchor="w", pady=(0, 10))
		ai_box = ttk.Checkbutton(detail, text="AI Tool — skills are not required")
		ai_box.pack(anchor="w", pady=(0, 10))
		ttk.Separator(detail).pack(fill="x", pady=(0, 8))
		sf = ui.ScrollFrame(detail)
		sf.pack(fill="both", expand=True)
		g = sf.inner
		g.columnconfigure(0, weight=1, minsize=ui.px(140))
		g.columnconfigure(1, minsize=ui.px(100))
		g.columnconfigure(2, minsize=ui.px(150))
		for col, label in enumerate(("Category", "Good at this", "Interested in learning")):
			ttk.Label(g, text=label, style="Head.TLabel").grid(row=0, column=col, sticky="w", padx=8, pady=(4, 10))
		controls = []
		for i, cat in enumerate(cats):
			row = 1 + i * 2
			ttk.Label(g, text=cat, wraplength=ui.px(200)).grid(row=row, column=0, sticky="w", padx=8, pady=9)
			skill = ttk.Checkbutton(g, text="Skilled", padding=(6, 6))
			learn = ttk.Checkbutton(g, text="Want to learn", padding=(6, 6))
			skill.grid(row=row, column=1, sticky="w", padx=8, pady=3)
			learn.grid(row=row, column=2, sticky="w", padx=8, pady=3)
			ttk.Separator(g).grid(row=row + 1, column=0, columnspan=3, sticky="ew")
			controls.append((cat, skill, learn))
		if not cats:
			ttk.Label(g, text="Add categories from the Categories menu first.").grid(row=1, column=0, columnspan=3, pady=20)

		def refresh_counts():
			selected = people_tree.selection()
			if not selected:
				return
			x = v[selected[0]]
			nskills = sum(b.get() for b in x["skills"].values())
			nlearn = sum(b.get() for b in x["learn"].values())
			ai = x["ai_tool"].get()
			counts.configure(text="AI Tool · skills and learning interests are not required" if ai else
				f"{nskills} skilled categories  ·  {nlearn} learning interests")
			for _cat, skill, learn in controls:
				for control in (skill, learn):
					control.state(["disabled"] if ai else ["!disabled"])
			for name, values in v.items():
				people_tree.item(name, text=name + ("  ·  Lead" if values["lead"].get() else "") + ("  ·  AI" if values["ai_tool"].get() else ""))

		def select_person(_event=None):
			selected = people_tree.selection()
			if not selected:
				return
			if lead:
				overview.grid_remove()
			detail.grid()
			name = selected[0]
			x = v[name]
			ai_box.configure(variable=x["ai_tool"], command=refresh_counts)
			heading.configure(text=name)
			if lead_box:
				lead_box.configure(variable=x["lead"], command=refresh_counts)
			for cat, skill, learn in controls:
				skill.configure(variable=x["skills"][cat], command=refresh_counts)
				learn.configure(variable=x["learn"][cat], command=refresh_counts)
			refresh_counts()
			sf.canvas.yview_moveto(0)

		if lead:
			overview = ttk.LabelFrame(body, text="View All — team skills", padding=12)
			overview.grid(row=0, column=1, sticky="nsew")
			overview.grid_remove()
			overview_scroll = ui.ScrollFrame(overview)
			overview_scroll.pack(fill="both", expand=True)

			def view_all():
				for child in overview_scroll.inner.winfo_children():
					child.destroy()
				for name, values in v.items():
					card = ttk.LabelFrame(overview_scroll.inner, text=name + (" · Lead" if values["lead"].get() else ""), padding=12)
					card.pack(fill="x", pady=(0, 10))
					if values["ai_tool"].get():
						lines = ["AI Tool · skills and learning interests are not required."]
					else:
						lines = [label + (", ".join(cat for cat in cats if values[key][cat].get()) or "None listed")
							for key, label in (("skills", "Skilled: "), ("learn", "Wants to learn: "))]
					for line in lines:
						label = ttk.Label(card, text=line, wraplength=ui.px(420), justify="left")
						label.pack(fill="x", pady=3)
						label.bind("<Configure>", lambda event: event.widget.configure(wraplength=max(ui.px(150), event.width)))
				people_tree.selection_remove(*people_tree.selection())
				detail.grid_remove()
				overview.grid()
				overview_scroll.canvas.yview_moveto(0)

			ttk.Button(people, text="View All", command=view_all).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

		for d in devs:
			people_tree.insert("", "end", iid=d["name"], text=d["name"])
		people_tree.bind("<<TreeviewSelect>>", select_person)
		initial = focus if focus in v else me if me in v else devs[0]["name"]
		people_tree.selection_set(initial)
		people_tree.see(initial)
		select_person()
		w.geometry(f"{min(w.winfo_screenwidth() - 80, ui.px(960))}x{min(w.winfo_screenheight() - 120, ui.px(790))}")
		w.minsize(min(w.winfo_screenwidth() - 80, ui.px(760)), min(w.winfo_screenheight() - 120, ui.px(480)))

		def ok():
			for d in devs:
				x = v[d["name"]]
				d["skills"] = [c for c in cats if x["skills"][c].get()]
				d["learn"] = [c for c in cats if x["learn"][c].get()]
				d["ai_tool"] = x["ai_tool"].get()
				if lead:
					d["lead"] = x["lead"].get()
			w.destroy()
			self.save()
			self.app.set_status("Skills saved.")
		footer = ttk.Frame(outer)
		footer.pack(fill="x", pady=(12, 0))
		ttk.Label(footer, text="Changes are applied when you save.", style="Muted.TLabel").pack(side="left")
		ttk.Button(footer, text="Save", command=ok).pack(side="right")
		ttk.Button(footer, text="Cancel", command=w.destroy).pack(side="right", padx=(0, 8))
		w.bind("<Escape>", lambda _event: w.destroy())
		ui.theme_all(w)

	def edit_devs(self):
		if not self.is_lead():
			self.skills()  # (everyone else: their own skills)
			return
		self.edit_list("Devs", self.dev_names, self.add_dev, self.rename_dev, self.remove_dev,
					   extra=[("Git name...", self.git_name), ("Skills...", self.skills)])

	def edit_categories(self):
		def add():
			self.new_category()

		def rename(old):
			n = (simpledialog.askstring("Rename category", "New name:", initialvalue=old, parent=self) or "").strip()
			if not n or n == old:
				return
			self.data["categories"] = [n if c == old else c for c in self.data["categories"]]
			for t in self.tasks:
				if t.get("category") == old:
					self.change(t, "category", n, note="category renamed")
			self._renamed()

		def remove(c):
			used = [t["ref"] for t in self.tasks if t.get("category") == c]
			if used and not messagebox.askyesno(APP_NAME, f"{len(used)} tasks are in {c}. Remove it from the list anyway? (They keep it.)"):
				return
			self.data["categories"].remove(c)
			self._renamed()
		self.edit_list("Categories", lambda: self.data["categories"], add, rename, remove, extra=("Icon...", self.pick_category_icon))

	# ---------- the in-game list ----------
	def task_line(self, t, with_devs=None):
		col = {"green": "G", "yellow": "Y", "red": "R"}
		pcol = {"Low": "g", "Normal": "W", "High": "O", "Critical": "R"}
		delta = age_of(t)
		# (colour codes don't nest in HOI4: each part gets its own)
		bits = ([loc_text(t["project"])] if t.get("project") else []) + [loc_text(t.get("category", "")), loc_text(t.get("status", TODO))]
		if t.get("sweep"):
			bits.append("Sweep")
		if t.get("tags"):
			bits.append(" ".join(t["tags"]))
		line = (f"  §{col[age_band(delta)]}{fmt_age(delta)}§!  §H{t['ref']}§!  {loc_text(t.get('title', ''))}  "
				f"§{pcol.get(t.get('priority'), 'W')}{t.get('priority', 'Normal')}§!  §g({', '.join(b for b in bits if b)})§!")
		if with_devs:
			line += f"\\n      §gWith {loc_text(', '.join(with_devs))}§!"
		if t.get("blocked"):
			line += f"\\n      §RBlocked:§! {loc_text(t['blocked'])}"
		waiting = [r for r in t.get("depends_on", []) if self.task(r) and not is_closed(self.task(r))]
		if waiting:
			line += f"\\n      §gWaiting for {loc_text(', '.join(self.title_of(r) for r in waiting))}§!"
		if t.get("setter_note"):
			line += f"\\n      §g{loc_text(t.get('set_by', ''))}:§! {loc_text(t['setter_note'])}"
		return line

	def export(self):
		"""localisation/english/rr_todo_l_english.yml: the open tasks per dev, then the General To Do and Needs Planning."""
		when = now()
		open_ = [t for t in self.tasks if lane(t) != "archive"]
		order = lambda t: (-PRIORITIES.index(t.get("priority", "Normal")) if t.get("priority") in PRIORITIES else -1, -age_of(t).total_seconds())
		parts = []
		for name in self.dev_names():
			mine = sorted((t for t in open_ if lane(t) == "dev" and name in devs_of(t)), key=order)
			if not mine:
				continue
			blk = sum(1 for t in mine if t.get("blocked"))
			parts.append(f"§Y{loc_text(name)}§!  §g({len(mine)} open" + (f", {blk} blocked" if blk else "") + ")§!")
			parts += [self.task_line(t, [d for d in devs_of(t) if d != name]) for t in mine]
			parts.append("")
		music = [t for t in open_ if lane(t) == "music"]
		if music:
			parts.append(f"§B{MUSIC_TODO}§!  §g({len(music)} open, nobody's yet: claim them in To Do Master)§!")
			for mod in [t for t in self.tasks if str(t.get("link", "")).startswith("music_mod:")]:
				stations = [t for t in music if t.get("parent") == mod["ref"]]
				if stations:
					names = ", ".join(loc_text(t.get("title", "")) for t in stations[:8]) + (" ..." if len(stations) > 8 else "")
					parts.append(f"  §H{loc_text(mod.get('title', ''))}§!  §g({len(stations)} stations to make)§!  {names}")
			parts.append("")
		for key, head in (("general", f"§B{GENERAL}§!  §g(nobody's yet: claim one in To Do Master)§!"), ("planning", f"§B{PLANNING}§!")):
			rows = sorted((t for t in open_ if (in_general(t) if key == "general" else lane(t) == key)), key=order)
			if rows:
				parts.append(head)
				parts += [self.task_line(t, devs_of(t)) for t in rows]
				parts.append("")
		body = "\\n".join(parts).rstrip("\\n") or "Nothing to do. Enjoy it while it lasts."
		lines = ["l_english:",
				 " # Made by Organisation Master > To Do Master (the live To Do) on this PC: not in git, don't edit by hand.",
				 " # It replaces the placeholders in localisation/english/rr_todo_l_english.yml.",
				 f' rr_todo_updated:0 "{len(open_)} open tasks  -  timers as of {when.strftime("%Y-%m-%d %H:%M")}  -  §Gup to 2 weeks§!  §Yup to 3 months§!  §Rolder§!"',
				 f' rr_todo_list:0 "{body}"']
		text = "﻿" + "\r\n".join(lines) + "\r\n"
		p = os.path.join(self.app.mod_root, LOC_REL)
		if text != getattr(self, "_exported", None) or not os.path.exists(p):  # (unchanged: not written again, so OneDrive isn't kept busy)
			os.makedirs(os.path.dirname(p), exist_ok=True)
			with open(p, "w", encoding="utf-8", newline="") as f:
				f.write(text)
			self._exported = text
			self.app.log(LOC_REL)
		self.export_info.config(text=f"In game: {len(open_)} open tasks")
