"""📬 Since you were last here: on opening Organisation Master (once the live sync has brought the others' changes in),
a short summary of what happened since you last opened it - tasks given to you, your tasks the others changed, what got
completed, new tasks and ideas, pictures marked for rework, who's asking for a task. Double-click a task to go to it.
Personal (config.json): last_seen (when you last opened it), since_last_here (Settings: show it on opening)."""
import datetime
import tkinter as tk
from tkinter import ttk

import ui

QUIET = 30 * 60  # (opened again within half an hour: nothing to say)
FIELDS = {"status": "status", "setter_note": "note", "dev_note": "dev note", "priority": "priority", "blocked": "blocked",
		  "title": "title", "reviewer": "reviewer", "depends_on": "dependencies", "category": "category", "project": "project"}


def moment(s):
	try:
		d = datetime.datetime.fromisoformat(s)
		return d if d.tzinfo else d.astimezone()
	except (TypeError, ValueError):
		return None


def gather(data, me, since):
	"""[(section, [(text, task ref or None)])] of what happened after since (an ISO stamp), the others' doing."""
	after = moment(since)
	if after is None:
		return []

	def new(s):
		m = moment(s)
		return m is not None and m > after
	tasks = data.get("tasks", [])
	given, changed, done, made = [], [], [], []
	for t in tasks:
		ref, title = t.get("ref"), t.get("title", "")
		devs = t.get("devs") or []
		hist = t.get("history", [])
		if new(t.get("created")) and t.get("set_by") != me:
			if me in devs:
				given.append((f"{ref}  {title}  (set by {t.get('set_by', '?')})", ref))
			else:
				made.append((f"{ref}  {title}  (by {t.get('set_by', '?')})", ref))
		for h in hist:
			if not new(h.get("when")) or h.get("who") == me:
				continue
			if h.get("field") == "devs" and me in (h.get("new") or []) and me not in (h.get("old") or []):
				given.append((f"{ref}  {title}  (from {h.get('who', '?')})", ref))
			elif h.get("field") == "status" and h.get("new") in ("Completed", "Not Possible"):
				done.append((f"{ref}  {title}  ({h['new'].lower()}, {h.get('who', '?')})", ref))
			elif me in devs and h.get("field") in FIELDS:
				val = h.get("new")
				val = val if isinstance(val, str) and len(val) < 40 else "changed"
				changed.append((f"{ref}  {title}: {FIELDS[h['field']]} {val}  ({h.get('who', '?')})", ref))
	ideas = [(f"💡 {i.get('title', '?')}  (by {i.get('by', '?')})", None) for i in data.get("ideas", [])
			 if new(i.get("created")) and i.get("by") != me]
	gfx = data.get("gfx") or {}
	marks = [m for m in (gfx.get("rework") or {}).values() if new(m.get("when")) and m.get("by") != me]
	fixed = [k for k, m in (gfx.get("rework_done") or {}).items() if new(m.get("when")) and m.get("by") != me]
	art = []
	if marks:
		art.append((f"🔁 {len(marks)} picture{'s' if len(marks) != 1 else ''} marked for rework", None))
	if fixed:
		art.append((f"✓ {len(fixed)} picture{'s' if len(fixed) != 1 else ''} reworked", None))
	asking = [(f"🙋 {d['name']} is asking for a task", None) for d in data.get("devs", []) if d.get("asking_task") and d["name"] != me]
	errors = []
	try:  # (🐞 problems the mod check found new - not there the check before - since you were last here, in files you changed last)
		import error_log_master as elm
		root = getattr(gather, "mod_root", None)
		cache = elm.load(elm.LINT_CACHE, {})
		prev = set(cache.get("prev") or [])
		probs = [p for p in cache.get("problems", []) if p.get("key") not in prev] if prev and new(cache.get("when")) else []
		if root and probs:
			dev = next((d for d in data.get("devs", []) if d["name"] == me), {})
			names = {me.casefold(), (dev.get("git") or "").casefold()} - {""}
			mine = {f for f, a in elm.authors(root).items() if a.casefold() in names}
			n = sum(1 for p in probs if p["file"] in mine)
			if n:
				errors.append((f"🐞 {n} new problem{'s' if n != 1 else ''} in files you changed last (Error Log Master > 👤 Only mine)", None))
	except Exception:
		pass

	def uniq(rows):
		return list(dict.fromkeys(rows))
	return [(name, rows) for name, rows in (("📥 Given to you", uniq(given)), ("✏ Your tasks, changed by the others", uniq(changed)[:15]),
											 ("✓ Completed", uniq(done)[:15] + ([(f"... and {len(uniq(done)) - 15} more", None)] if len(uniq(done)) > 15 else [])),
											 ("🆕 New tasks", uniq(made)[:10] + ([(f"... and {len(made) - 10} more", None)] if len(made) > 10 else [])),
											 ("💡 New ideas", ideas[:8]), ("🖼 GFX", art), ("🙋 Asking for a task", asking),
											 ("🐞 Errors", errors)) if rows]


class SinceLastHere:
	def __init__(self, app):
		self.app = app
		self.previous = app.config.get("last_seen")  # (kept for the menu's "show it again")
		app.config["last_seen"] = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
		app.save_config()
		if self.previous and app.config.get("since_last_here", True):
			gap = (datetime.datetime.now().astimezone() - (moment(self.previous) or datetime.datetime.now().astimezone())).total_seconds()
			if gap > QUIET:
				app.root.after(6000, self.show)  # (after the first live sync: the others' changes are in)

	def show(self, quiet=True):
		todo = self.app.todo_page()
		since = self.previous or self.app.config["last_seen"]
		gather.mod_root = self.app.mod_root
		sections = gather(todo.data, todo.me.get(), since)
		if not sections:
			if not quiet:
				self.app.set_status("📬 Nothing new since you were last here.")
			return
		w = tk.Toplevel(self.app.root)
		w.title("📬 Since you were last here")
		w._om_nonmodal = True  # (just a summary: the live sync carries on while it's open)
		w.transient(self.app.root)
		w.geometry(f"{ui.px(620)}x{ui.px(520)}")
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		when = moment(since)
		ttk.Label(f, text=f"📬 Since you were last here ({when.strftime('%d %b, %H:%M') if when else since})", font="om_head").pack(anchor="w")
		ttk.Label(f, text="Double-click a task to go to it.", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
		t = ttk.Treeview(f, show="tree", selectmode="browse")
		ys = ttk.Scrollbar(f, command=t.yview)
		t.configure(yscrollcommand=ys.set)
		ys.pack(side="right", fill="y")
		t.pack(fill="both", expand=True)
		t.tag_configure("head", font="om_bold")
		refs = {}
		for name, rows in sections:
			g = t.insert("", "end", text=f"{name}  ({len(rows)})", open=True, tags=("head",))
			for text, ref in rows:
				iid = t.insert(g, "end", text=text)
				if ref:
					refs[iid] = ref
		ui.stripe(t)

		def go(ev=None):
			sel = t.selection()
			if sel and sel[0] in refs:
				self.app.show_page("To Do Master")
				todo.show_task(refs[sel[0]])
		t.bind("<Double-1>", go)
		ttk.Button(f, text="Close", command=w.destroy).pack(anchor="e", pady=(8, 0))
		self.app.feedback("presence") if hasattr(self.app, "feedback") else None
