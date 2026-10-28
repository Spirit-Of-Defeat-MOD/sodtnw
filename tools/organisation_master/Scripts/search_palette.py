"""🔎 Search everything (Ctrl+K): type, pick, and you're there - a task, project, idea, Dev VC, GFX picture, country (opens
in Country Master), guide, or one of Organisation Master's pages and actions."""
import tkinter as tk
from tkinter import ttk

import ui

KIND_ICON = {"task": "📋", "project": "📁", "idea": "💡", "vc": "🎙", "gfx": "🖼", "country": "🏳", "action": "⚙", "guide": "📖"}
LIMIT = 60


def entries(app):
	"""[(kind, label, words to match, go)] for everything there is to find."""
	todo = app.todo_page()
	out = []

	def mode(m, then=None):
		def go():
			app.show_page("To Do Master")
			todo.mode.set(m)
			todo.mode_changed()
			if then:
				todo.after(50, then)
		return go
	# ---- pages and actions ----
	for label, fn in (("To Do: 👤 Dev mode", mode("dev")), ("To Do: 📁 Project mode", mode("project")), ("🖼 GFX", mode("gfx")),
					  ("🔎 GFX: Review swiper", mode("gfx", lambda: (todo.gfx_pane.view.set("review"), todo.gfx_pane.view_changed()))),
					  ("💡 Ideas", mode("idea")), ("🎙 Dev VCs", mode("vc")), ("🏆 Achievements", mode("achievements")),
					  ("🎮 RR Games", app.show_games), ("🎉 Complete milestone / special thanks", todo.complete_milestone), ("📰 Recent Changes", app.recent_changes.show),
					  ("🎵 Music Master", lambda: app.show_page("Music Master")), ("🗑 Trash", todo.open_trash),
					  ("⏰ Stale tasks", todo.open_nudges), ("🙋 Ask for a task", mode("dev", todo.ask_for_task)),
					  ("📬 Since you were last here", lambda: app.since_last.show(quiet=False)),
					  ("🐞 Error Log Master", lambda: __import__("error_log_master").show(app)),
					  ("🚨 Error alerts can pop up for me (on / off)", lambda: (app.alerts_var.set(not app.alerts_var.get()),
																			   __import__("error_alerts").set_enabled(app, app.alerts_var.get()))),
					  ("🔀 GFX: Before / after", mode("gfx", lambda: __import__("gfx_compare").Compare(todo.gfx_pane))), ("🔄 Set up Live Sync", todo.sync_setup),
					  ("🩺 Check the To Do data", lambda: __import__("data_check").show(app.root, todo)),
					  ("🌍 Open Culture Master", lambda: app.open_master("Culture Master")),
					  ("🏳 Open Country Master", lambda: app.open_master("Country Master"))):
		out.append(("action", label, label.lower(), fn))
	# HASHED OUT 2026-10-25 at Mike's request: the Celebration tester is removed (see AGENTS.md); don't bring it back unasked.
	# from milestone_celebration import TEST_SCENES, test_animation
	# for title, animation in TEST_SCENES:
	# 	label = "Test celebration: " + title
	# 	out.append(("action", label, label.lower() + " milestone preview tester", lambda t=title,a=animation: test_animation(app,t,a)))
	try:
		import guides
		for key, g in guides.GUIDES.items():
			out.append(("guide", f"Guide: {g['title']}", f"guide help how {g['title']}".lower(), lambda k=key: guides.start(app, k)))
	except Exception:
		pass
	# ---- the To Do ----
	task_mode = app.config.get("todo_last_mode") if app.config.get("todo_last_mode") in ("dev", "project") else "dev"
	for t in todo.tasks:
		words = f"{t['ref']} {t.get('title', '')} {t.get('project', '')} {' '.join(t.get('devs') or [])}".lower()
		out.append(("task", f"{t['ref']}  {t.get('title', '')}" + (f"  ·  {t['project']}" if t.get("project") else ""), words,
					mode(task_mode, lambda r=t["ref"]: todo.go_to(r))))

	def show_project(name):
		iid = "proj:" + name
		if todo.tree.exists(iid):
			todo.tree.selection_set(iid)
			todo.tree.see(iid)
	for p in todo.data.get("projects", []):
		out.append(("project", p["name"], f"project {p['name']}".lower(), mode("project", lambda n=p["name"]: show_project(n))))
	for i in todo.data.get("ideas", []):
		out.append(("idea", i.get("title", ""), f"{i.get('title', '')} {i.get('category', '')} {i.get('by', '')}".lower(),
					lambda iid=i["id"]: (app.show_page("To Do Master"), todo.idea_pane.open_idea(iid))))
	for v in todo.data.get("vcs", []):
		label = f"Dev VC {v.get('date', '')}  {v.get('title', '')}"

		def open_vc(vid=v["id"]):
			mode("vc")()
			todo.after(80, lambda: todo.vc_pane.list.exists(vid) and (todo.vc_pane.list.selection_set(vid), todo.vc_pane.list.see(vid)))
		out.append(("vc", label, f"vc meeting {label}".lower(), open_vc))
	gfx = getattr(todo, "gfx_pane", None)
	for x in getattr(gfx, "items", []) or []:
		out.append(("gfx", f"{x['name']}  ·  {x.get('detail', '')[:60]}", f"gfx picture {x['name']} {x.get('token', '')}".lower(),
					lambda i=x["id"]: (mode("gfx")(), todo.after(120, lambda: gfx.go_item(i)))))
	# ---- countries (Country Master) ----
	af = getattr(todo, "auto_flags", None)
	if af is not None and af.ready:
		import master_links
		seen = {}
		for name, (tag, ideology) in af.names.items():
			if not ideology and tag not in seen:
				seen[tag] = name
		for tag, name in sorted(seen.items()):
			out.append(("country", f"{name.title()} ({tag})", f"{name} {tag}".lower(),
						lambda tg=tag: app.navigate_master(master_links.make("country", "country", tg))))
	return out


def score(words, text, label):
	"""Higher is better; None when a word isn't in it."""
	if not all(w in text for w in words):
		return None
	first = label.lower()
	return (3 if first.startswith(words[0]) else 2 if f" {words[0]}" in first else 1 if words[0] in first else 0) * 10 - len(label) / 100


class Palette(tk.Toplevel):
	def __init__(self, app):
		super().__init__(app.root)
		self.app = app
		self._om_nonmodal = True
		self.overrideredirect(True)
		self.transient(app.root)
		self.all = entries(app)
		root = app.root
		w, h = ui.px(640), ui.px(420)
		x = root.winfo_rootx() + (root.winfo_width() - w) // 2
		y = root.winfo_rooty() + ui.px(70)
		self.geometry(f"{w}x{h}+{x}+{y}")
		f = tk.Frame(self, background=ui.P.get("copper", "#1f5fa8"), padx=2, pady=2)
		f.pack(fill="both", expand=True)
		inner = ttk.Frame(f, padding=8)
		inner.pack(fill="both", expand=True)
		self.q = tk.StringVar()
		e = ttk.Entry(inner, textvariable=self.q, font="om_head")
		e.pack(fill="x")
		ttk.Label(inner, text="Tasks, projects, ideas, Dev VCs, GFX, countries, pages, guides · ↑↓ Enter · Esc closes",
				  style="Muted.TLabel").pack(anchor="w", pady=(2, 4))
		self.list = tk.Listbox(inner, font="om_body", activestyle="none", relief="flat", highlightthickness=0)
		self.list.pack(fill="both", expand=True)
		self.q.trace_add("write", lambda *_: self.fill())
		for widget in (e, self.list):
			widget.bind("<Down>", lambda ev: self.move(1))
			widget.bind("<Up>", lambda ev: self.move(-1))
			widget.bind("<Return>", lambda ev: self.go())
			widget.bind("<Escape>", lambda ev: self.destroy())
		self.list.bind("<Double-1>", lambda ev: self.go())
		self.bind("<FocusOut>", lambda ev: self.after(150, self.close_if_away))
		self.fill()
		self.entry = e
		self.to_front()
		self.after(60, self.to_front)  # (Windows puts a borderless window under the main one: raised again once it's shown)

	def to_front(self):
		if self.winfo_exists():
			self.lift()
			self.entry.focus_force()

	def close_if_away(self):
		try:
			if self.winfo_exists() and self.focus_get() is None:
				self.destroy()
		except (tk.TclError, KeyError):
			pass

	def fill(self):
		words = self.q.get().lower().split()
		if words:
			hits = [(s, e) for e in self.all if (s := score(words, e[2], e[1])) is not None]
			hits.sort(key=lambda p: -p[0])
			self.shown = [e for _, e in hits[:LIMIT]]
		else:
			self.shown = [e for e in self.all if e[0] in ("action", "guide")][:LIMIT]
		self.list.delete(0, "end")
		for kind, label, _, _ in self.shown:
			self.list.insert("end", f"{KIND_ICON.get(kind, '•')}  {label}")
		if self.shown:
			self.list.selection_set(0)

	def move(self, d):
		if not self.shown:
			return "break"
		cur = (self.list.curselection() or (0,))[0]
		new = max(0, min(len(self.shown) - 1, cur + d))
		self.list.selection_clear(0, "end")
		self.list.selection_set(new)
		self.list.see(new)
		return "break"

	def go(self):
		sel = self.list.curselection()
		if not sel or not self.shown:
			return
		go = self.shown[sel[0]][3]
		self.destroy()
		go()


def open_palette(app):
	for w in app.root.winfo_children():
		if isinstance(w, Palette):
			w.destroy()
	return Palette(app)
