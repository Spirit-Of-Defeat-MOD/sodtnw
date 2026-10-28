"""📖 Guides (top left of the menu bar): short tours that point at the real thing on screen, step by step.

Each step switches to the right place, then an overlay over the window draws a glowing, pulsing frame around the
part being explained, an arrow bobbing at it and a ghost cursor that glides over and clicks it. The overlay lets
clicks through (you can try it as you go); a card next to it says what it is, with Back / Next.

A guide = {"title", "intro", "window" (app -> the window it's in, optional: the app's own), "steps": [{"title",
"text", "where" (app -> the widget, or None), "go" (app -> switch to it, optional), "click" (True: the ghost cursor
clicks it)}]}. GUIDES is Organisation Master's book; the other masters have their own (master_guides.py), put in their
menu bar with attach()."""
import json
import math
import os
import time
import tkinter as tk
from tkinter import ttk

import ui

KEY = "#ff00fe"  # (the overlay's see-through colour)


# ---------- finding the parts on screen ----------
def todo(app):
	return app.todo_page()


def find(root, text):
	"""The first widget under root whose text contains text (buttons, labels, radio buttons)."""
	stack = [root]
	while stack:
		w = stack.pop(0)
		try:
			if text in str(w.cget("text")):
				return w
		except (tk.TclError, AttributeError):
			pass
		stack += w.winfo_children()
	return None


def bar_item(app, text):
	return next((b for b in app.menubar.items if text in str(b.cget("text"))), None)


def mode(m):
	def go(app):
		app.show_page("To Do Master")
		todo(app).mode.set(m)
		todo(app).mode_changed()
	return go


def page(name):
	return lambda app: app.show_page(name)


def elm(app):
	"""The Error Log Master window (opened if it isn't)."""
	import error_log_master
	return error_log_master.show(app)


def elm_tab(i):
	return lambda app: elm(app).tabs.select(i)


def step(title, text, where=None, go=None, click=False):
	return dict(title=title, text=text, where=where, go=go, click=click)


GUIDES = {
	"general": dict(title="Getting started", intro="A quick look around Organisation Master.", steps=[
		step("Welcome to Organisation Master", "This is RR's central tool: the team's tasks, ideas, Dev VCs, missing pictures and music all live here, "
			 "and it opens the other masters. Use Next (or →) to look around; you can click the real thing at any point."),
		step("Who you are", "You're recognised by your git name. Everything you do (claims, votes, notes) is signed with it.",
			 lambda a: todo(a).identity, page("To Do Master")),
		step("The tools", "To Do Master and Music Master are pages of this window; pick one here.",
			 lambda a: a.nav_buttons.get("To Do Master"), click=True),
		step("The other masters", "Culture Master, Country Master and Model Master open as their own windows from here (or the Masters menu). Each has its own 📖 Guides, top left.",
			 lambda a: find(a.nav, "Culture Master")),
		step("Country characters", "In Country Master, Country page selects Characters without squeezing the page names. Pick a counted Role, scroll the list sideways for columns, and drag its lower divider to resize the editor. The Edit dropdown selects Character, Dual leaders or Script. Ideology and dual-leader choices autocomplete as you type; scrolling over them never changes a value.",
			 lambda a: find(a.nav, "Country Master")),
		step("Modes", "To Do Master has modes: your tasks by dev or by project, 🖼 GFX (missing pictures), 💡 Ideas and 🎙 Dev VCs.",
			 lambda a: todo(a).mode_frame),
		step("Live Sync", "Everyone's To Do is kept in step automatically. This says when it last synced; click it if something looks wrong.",
			 lambda a: todo(a).sync_label),
		step("Search everything", "Ctrl+K (or this) finds any task, idea, VC, picture, country or page, and takes you straight there.",
			 lambda a: bar_item(a, "Search"), click=True),
		step("Guides", "Every part has its own guide in this menu. Recent Changes (also in the bar) shows what's new in the tools.",
			 lambda a: bar_item(a, "Guides")),
	]),
	"todo": dict(title="To Do: tasks", intro="Finding, claiming and finishing tasks.", steps=[
		step("Dev mode", "Tasks grouped by who's on them. Project mode groups them by project instead.",
			 lambda a: todo(a).mode_buttons["dev"], mode("dev"), click=True),
		step("Views", "Everything open, ⭐ your next task, your tasks, the General To Do (nobody's yet: claim one!), music, planning, the archive.",
			 lambda a: todo(a).views_row),
		step("The list", "Double-click a task to edit it; right-click for everything else (claim, status, project, sub-tasks, linked ideas...).",
			 lambda a: todo(a).tree),
		step("A new task", "Add one here (or from a template / several at once in the row below).",
			 lambda a: find(todo(a).task_tools, "New task"), click=True),
		step("The selected task", "What it is, who's on it, its notes, links, art and history.",
			 lambda a: todo(a).d_title),
		step("🙋 Ask for a task", "Out of work? Press it under the Dev list: you light up for the leads until someone gives you a task.",
			 lambda a: todo(a).ask_btn, mode("dev")),
		step("🐞 Error Log Master", "In the side bar: the game's error logs grouped and made readable (🆕 new since the last run), plus a check of the mod's files for errors the log never shows. ➕ turns one into a task for whoever last changed the file; 🚨 Alert a dev flashes one at a teammate (it pops up on their screen until they answer); 🤔 Potential Unintentional Outcomes lists script that works but probably isn't what was meant.",
			 lambda a: find(a.nav, "Error Log Master")),
		step("Themed error alerts", "Error Log Master and incoming error alerts follow your theme, including their tabs and code highlights. Each theme has its own compact animated illustration; Soviet Terminal has a falling wireframe nuke and mushroom cloud. The message and response buttons remain accessible throughout. Timed sound effects follow Sound feedback and volume in Settings.",
			 lambda a: find(a.nav, "Error Log Master")),
		step("Handy buttons", "🎲 a random task to pick up, 🩺 the To Do's health, ↶ Undo (Ctrl+Z), 🗑 Trash for anything deleted, ⏰ stale tasks.",
			 lambda a: todo(a).tools_row),
		# HASHED OUT 2026-10-25 at Mike's request: the Celebration tester is removed (see AGENTS.md); don't bring it back unasked.
		# step("Celebration tester", "Settings > Celebration tester lets you try Culture Map, Mechanics or Technology immediately. These previews are local and do not complete or broadcast any milestone. Ctrl+K also finds each tester.",
		# 	 lambda a: bar_item(a, "Settings")),
		step("Celebrate milestones", "Right-click a milestone and choose Complete milestone / special thanks. Choose developers to thank and an animation (Automatic, Culture map duck, Mechanics duck, Technology duck or Confetti), preview locally, then Complete & celebrate. Everyone receives it through Live Sync, including offline devs on their next launch.",
			 lambda a: todo(a).ms_tree),
		step("Search the list", "Filters the list as you type (Ctrl+K searches everything).",
			 lambda a: todo(a).search_box),
	]),
	"ideas": dict(title="💡 Ideas", intro="Posting, voting on and approving ideas.", steps=[
		step("Ideas mode", "Ideas for the mod, before they're tasks.", lambda a: todo(a).mode_buttons["idea"], mode("idea"), click=True),
		step("Categories and projects", "Pick a category (or a project) to see its ideas; drag categories to reorder them.",
			 lambda a: todo(a).idea_pane.cats),
		step("Post an idea", "Type a title and Post. It goes in the category picked on the left.",
			 lambda a: find(todo(a).idea_pane, "Post an idea")),
		step("The ideas", "Pick one to read it, vote and comment. Headings group them; drag ideas onto them.",
			 lambda a: todo(a).idea_pane.list),
		step("✨ Only new", "Only what others posted or commented on since you last looked.",
			 lambda a: todo(a).idea_pane.new_btn, click=True),
		step("Votes", "👍 Good, 🔥 Super Want or 👎 Dislike: as many ideas as you like.",
			 lambda a: next(iter(todo(a).idea_pane.vote_btns.values()), None)),
		step("What happens to it", "Approve it into a task (or a sub-task), send it to the next Dev VC's agenda, or 🗄 shelve it with a reason.",
			 lambda a: todo(a).idea_pane.btn_approve),
		step("🗄 Shelved Ideas", "Shelved ideas wait here, grouped by why.", lambda a: todo(a).idea_pane.shelf_sec),
	]),
	"vc": dict(title="🎙 Dev VCs", intro="Running a Dev VC: agenda, notes, tasks.", steps=[
		step("Dev VCs mode", "One entry per voice call.", lambda a: todo(a).mode_buttons["vc"], mode("vc"), click=True),
		step("The VCs", "Pick a VC; + New VC makes the next one (and carries over what's unfinished).", lambda a: todo(a).vc_pane.list),
		step("Agenda", "Tick items off as you go. Right-click to edit, move, park in the Future Agenda or delete; it shows who put each forward.",
			 lambda a: todo(a).vc_pane.movable.get("vc_agenda")),
		step("Future Agenda", "Items for the next VC (from Ideas or tasks) and ones parked for later.",
			 lambda a: todo(a).vc_pane.future_sec),
		step("Notes", "Write as you talk: everyone sees them live; the note taker's lines come first if two people type in the same place. "
			 "Drag a section's ⠿ to reorder them.", lambda a: todo(a).vc_pane.movable.get("vc_notes")),
		step("Tasks from this VC", "Extract the Action items (or have an AI tidy the notes), tick the proposals and Commit: they're tasks.",
			 lambda a: todo(a).vc_pane.tasks_sec),
	]),
	"gfx": dict(title="🖼 GFX", intro="Finding and making the pictures the mod is missing.", steps=[
		step("GFX mode", "Every picture the mod asks for that isn't there, plus broken, unused and to-rework ones.",
			 lambda a: todo(a).mode_buttons["gfx"], mode("gfx"), click=True),
		step("Missing, Broken, Unused, Needs Rework", "Pick which list.", lambda a: next(iter(todo(a).gfx_pane.problem_buttons.values()), None)),
		step("Sections", "Cultures, religions, flags, portraits, ideologies, national focus and national ideas.",
			 lambda a: next(iter(todo(a).gfx_pane.section_buttons.values()), None)),
		step("The list", "Cultures hold their subcultures (expand them to do a family together; green = its own picture is done). "
			 "🤖 / 📝 = an AI's / a person's suggestion.", lambda a: todo(a).gfx_pane.tree),
		step("The picked one", "Its suggestion (rate the AI's), your own suggestion, related pictures, image links, ✋ I'll make it. "
			 "Right-click a picture for 🔁 Needs rework; the mouse's back / forward buttons go back and forth.",
			 lambda a: todo(a).gfx_pane.detail),
		step("🤖 Ask AI", "Copies a request for Claude / ChatGPT, with the team's ratings so it does better each time.",
			 lambda a: find(todo(a).gfx_pane, "Ask AI for suggestions")),
		step("✨ Remini", "Restores and upscales the picked portrait on your PC (GFPGAN by TencentARC). The first time it sets itself up (asks first, ~2 GB).",
			 lambda a: find(todo(a).gfx_pane, "Remini")),
		step("🔀 Before / after", "A picture as it was when it was marked for rework next to how it is now - or ⧉ overlaid: Space flips, the slider blends.",
			 lambda a: find(todo(a).gfx_pane, "Before / after")),
		step("🔎 Review swiper", "Goes through the pictures the mod already has, one card at a time: → looks fine, ← needs review "
			 "(pick the level and say what's wrong: it goes into 🔁 Needs Rework for everyone), ↓ not sure.",
			 lambda a: find(todo(a).gfx_pane, "Review swiper")),
	]),
	"errors": dict(title="🐞 Error Log Master", intro="The game's errors, readable, and fixing them.",
				   window=lambda a: elm(a), steps=[
		step("Error Log Master", "The game's error logs grouped and in plain words, plus checks the log never makes. It opens "
			 "from the side bar of Organisation Master; 🐞 n there is how many problems are in files you've just changed."),
		step("Read the logs", "↻ reads the game's error.log again (after a run of the game); 📂 opens someone else's log - "
			 "one from another mod can be read, but nothing in it can be fixed from here.",
			 lambda a: find(elm(a), "Read the logs again")),
		step("▶ Check the mod's files", "Reads the mod itself for errors the game never logs (and fills 🔎 Not in the log and "
			 "🤔 Potential Unintentional Outcomes). Takes a little while; it runs in the background.",
			 lambda a: elm(a).lint_btn),
		step("Narrowing it down", "Search, 🆕 Only new (since the last run), 👤 Only mine (in files you last changed), "
			 "the severity and how picky the spelling check is.", lambda a: find(elm(a), "Only new")),
		step("📜 From the game's logs", "Each kind of error once, with how many times it happened. Pick one to read it below.",
			 lambda a: elm(a).tabs, elm_tab(0)),
		step("🌐 Localisation", "Missing and broken localisation, and spelling.", lambda a: elm(a).tabs, elm_tab(1)),
		step("🔎 Not in the log", "What ▶ Check the mod's files found: script the game reads without a word but gets wrong.",
			 lambda a: elm(a).tabs, elm_tab(2)),
		step("🤔 Potential Unintentional Outcomes", "Script that works but probably isn't what was meant - a value set twice, "
			 "a trigger that can never be true... Worth a look, not always wrong.", lambda a: elm(a).tabs, elm_tab(3)),
		step("The picked error", "What it is, the help (💡 what it means and how to fix it), the lines in the log and who "
			 "last changed the file - click a heading to fold it. On the right, the code around it (◀ ▶ or ← → for an "
			 "error with several parts).", lambda a: elm(a).detail, elm_tab(0)),
		step("What to do with it", "🔧 Fix it (when there's a sure fix), 📄 open the file at the line, ➕ make it a To Do task "
			 "for whoever last changed the file, 🙈 hide it, ✋ claim it.", lambda a: elm(a).fix_btn),
		step("🚨 Alert a dev", "Flashes the error on a teammate's screen (live, even with Organisation Master already open) "
			 "until they answer. For the urgent ones.", lambda a: elm(a).alert_btn),
		step("✅ Recently fixed and 📈 Trend", "What's been fixed since you last looked and by whom, and how the error count "
			 "goes over time, one panel per source (the game, the localisation, the file checks).", lambda a: elm(a).tabs, elm_tab(4)),
	]),
	"music": dict(title="🎵 Music Master", intro="The RR music mods.", steps=[
		step("Music Master", "The RR radio stations and their songs, new music mods and planned stations.",
			 lambda a: a.nav_buttons.get("Music Master"), page("Music Master"), click=True),
		step("The radio", "Listen to the stations while you work.", lambda a: a.radio),
	]),
	"sync": dict(title="🔄 Live Sync", intro="How the shared To Do stays in step.", steps=[
		step("Live", "The To Do, ideas and VCs sync through their own repository every few seconds: no pushing, no Discord noise.",
			 lambda a: todo(a).sync_label, page("To Do Master")),
		step("If it isn't working", "Live Sync... checks git, your access and the repository, and walks you through any fix.",
			 lambda a: todo(a).sync_btn, click=True),
		step("Pulling the mod", "The masters run from a copy, so you can git pull with them open. When a new build arrives, "
			 "⚠ Update (top right) offers a restart.", lambda a: a.menubar),
	]),
	"fun": dict(title="🏆 Games & Achievements", intro="The fun side.", steps=[
		step("RR Games", "Quizzes on the mod's own data (flags, cultures, leaders, borders...), RRdle and Pinpoint, with leaderboards.",
			 lambda a: bar_item(a, "RR Games"), click=True),
		step("Achievements", "Badges for your work, plus 🎲 Fun & Games: the themes' hidden secrets and the games.",
			 lambda a: bar_item(a, "Achievements")),
		step("Themes", "Every theme has a secret or two. Good luck.", lambda a: bar_item(a, "Theme")),
	]),
}


# ---------- the overlay: frame, arrow, ghost cursor ----------
class Overlay(tk.Toplevel):
	def __init__(self, app, win=None):
		super().__init__(app.root)
		self.app, self.win = app, win or app.root
		self._om_nonmodal = self._om_bar = self._om_effect_layer = True
		self.overrideredirect(True)
		self.transient(self.win)
		self.configure(background=KEY)
		self.attributes("-transparentcolor", KEY)
		try:
			self.attributes("-disabled", True)  # (clicks go through to the window under it)
		except tk.TclError:
			pass
		self.c = tk.Canvas(self, background=KEY, highlightthickness=0, borderwidth=0)
		self.c._om_effect_layer = True
		self.c.pack(fill="both", expand=True)
		self.target = None
		self.above = None  # (the tour's card: kept on top of the overlay)
		self.click = False
		self.cursor = None
		self.started = time.monotonic()
		self.job = None
		self.tick()

	def point_at(self, widget, click):
		self.target, self.click, self.started = widget, click, time.monotonic()
		self.from_xy = self.cursor

	def box(self):
		"""The target's box in the overlay's coordinates, or None."""
		w = self.target
		try:
			if w is None or not w.winfo_exists() or not w.winfo_ismapped():
				return None
			x, y = w.winfo_rootx() - self.winfo_rootx(), w.winfo_rooty() - self.winfo_rooty()
			return x, y, x + w.winfo_width(), y + w.winfo_height()
		except tk.TclError:
			return None

	def tick(self):
		if not self.winfo_exists():
			return
		r = self.win
		try:
			self.geometry(f"{r.winfo_width()}x{r.winfo_height()}+{r.winfo_rootx()}+{r.winfo_rooty()}")
			order = [str(w) for w in r.tk.call("wm", "stackorder", ".")]
			if str(self) in order and str(r) in order and order.index(str(self)) < order.index(str(r)):  # (Windows put it under the window)
				self.lift()
				if self.above is not None and self.above.winfo_exists():
					self.above.lift()
		except tk.TclError:
			return
		c, t = self.c, time.monotonic() - self.started
		c.delete("all")
		b = self.box()
		accent = ui.P.get("copper", "#e08a00")
		if b:
			x0, y0, x1, y1 = b
			pulse = (math.sin(t * 4) + 1) / 2
			pad = 4 + pulse * 5
			for i, width in ((0, 6), (1, 3)):  # (a glow: a wide frame, a sharp one inside)
				c.create_rectangle(x0 - pad - i * 3, y0 - pad - i * 3, x1 + pad + i * 3, y1 + pad + i * 3,
								   outline=accent if i else "#ffd27a", width=width)
			# the arrow, bobbing at it from above (or below when there's no room)
			cx = (x0 + x1) / 2
			up = y0 > 70
			bob = math.sin(t * 5) * 6
			tip = (y0 - pad - 8 + bob) if up else (y1 + pad + 8 - bob)
			back = -1 if up else 1  # (the arrow's head is at tip; its shaft goes away from the target)
			c.create_polygon(cx, tip, cx - 14, tip + back * 22, cx + 14, tip + back * 22, fill=accent, outline="#3a2a00")
			c.create_rectangle(cx - 5, tip + back * 22, cx + 5, tip + back * 44, fill=accent, outline="#3a2a00")
			if self.click:  # the ghost cursor: glides over, clicks (a ripple), again every few seconds
				goal = (cx + (x1 - x0) * 0.15, (y0 + y1) / 2)
				start = self.from_xy or (goal[0] + 160, goal[1] + 120)
				k = min(1, (t % 3.2) / 0.9)
				k = 1 - (1 - k) ** 3
				px, py = start[0] + (goal[0] - start[0]) * k, start[1] + (goal[1] - start[1]) * k
				self.cursor = (px, py)
				phase = (t % 3.2) - 0.9
				if 0 <= phase <= 0.7:
					for n in range(2):
						rad = 6 + (phase + n * 0.2) * 40
						if rad > 6:
							c.create_oval(goal[0] - rad, goal[1] - rad, goal[0] + rad, goal[1] + rad, outline=accent, width=2)
				arrow = [(0, 0), (0, 22), (6, 17), (10, 26), (14, 24), (10, 15), (17, 15)]
				c.create_polygon([(px + ax, py + ay) for ax, ay in arrow], fill="white", outline="black", width=1.5)
		self.job = self.after(33, self.tick)

	def close(self):
		if self.job:
			self.after_cancel(self.job)
		self.destroy()


# ---------- the card: what it is, Back / Next ----------
class Tour:
	def __init__(self, app, key, book=None):
		self.app, self.key, self.g = app, key, (book or GUIDES)[key]
		self.at = 0
		self.on_close = None  # (called once when the tour ends - finished or closed)
		try:
			win = self.g["window"](app) if self.g.get("window") else app.root
		except Exception:
			win = app.root
		self.win = win
		self.overlay = Overlay(app, win)
		w = self.card = self.overlay.above = tk.Toplevel(win)
		w._om_nonmodal = True
		w.overrideredirect(True)
		w.transient(win)
		frame = tk.Frame(w, background=ui.P.get("copper", "#e08a00"), padx=2, pady=2)
		frame.pack(fill="both", expand=True)
		inner = ttk.Frame(frame, padding=12)
		inner.pack(fill="both", expand=True)
		top = ttk.Frame(inner)
		top.pack(fill="x")
		self.count = ttk.Label(top, text="", style="Muted.TLabel")
		self.count.pack(side="right")
		ttk.Label(top, text=f"📖 {self.g['title']}", style="Muted.TLabel").pack(side="left")
		self.title = ttk.Label(inner, text="", font="om_head", wraplength=ui.px(360), justify="left")
		self.title.pack(anchor="w", pady=(6, 2))
		self.text = ttk.Label(inner, text="", wraplength=ui.px(360), justify="left")
		self.text.pack(anchor="w")
		bf = ttk.Frame(inner)
		bf.pack(fill="x", pady=(10, 0))
		ttk.Button(bf, text="✕ Close", style="Tool.TButton", command=self.close).pack(side="left")
		self.next_btn = ttk.Button(bf, text="Next →", command=lambda: self.move(1))
		self.next_btn.pack(side="right")
		self.back_btn = ttk.Button(bf, text="← Back", command=lambda: self.move(-1))
		self.back_btn.pack(side="right", padx=4)
		for seq, fn in (("<Right>", lambda ev: self.move(1)), ("<Left>", lambda ev: self.move(-1)), ("<Escape>", lambda ev: self.close())):
			w.bind(seq, fn)  # (the card has the keyboard while the tour is on)
		self.show()

	def show(self):
		s = self.g["steps"][self.at]
		if s.get("go"):
			try:
				s["go"](self.app)
			except Exception:
				pass
		self.win.update_idletasks()
		try:
			target = s["where"](self.app) if s.get("where") else None
		except Exception:
			target = None
		self.overlay.point_at(target, s.get("click"))
		n = len(self.g["steps"])
		self.count.config(text=f"{self.at + 1} / {n}")
		self.title.config(text=s["title"])
		self.text.config(text=s["text"] + ("" if target is not None or not s.get("where") else "\n\n(It isn't on screen right now.)"))
		self.back_btn.state(["!disabled" if self.at else "disabled"])
		self.next_btn.config(text="Done ✓" if self.at == n - 1 else "Next →")
		self.place(target)

	def place(self, target):
		"""The card beside the part it's about (below, else above; the middle when there's none), on screen."""
		c, r = self.card, self.win
		c.update_idletasks()
		cw, ch = c.winfo_reqwidth(), c.winfo_reqheight()
		sw, sh = c.winfo_screenwidth(), c.winfo_screenheight()
		try:
			ok = target is not None and target.winfo_ismapped()
		except tk.TclError:
			ok = False
		if ok:
			x = target.winfo_rootx()
			y = target.winfo_rooty() + target.winfo_height() + ui.px(60)
			if y + ch > sh - 40:
				y = target.winfo_rooty() - ch - ui.px(60)
		else:
			x = r.winfo_rootx() + (r.winfo_width() - cw) // 2
			y = r.winfo_rooty() + (r.winfo_height() - ch) // 2
		x = max(8, min(sw - cw - 8, x))
		y = max(8, min(sh - ch - 40, y))
		c.geometry(f"+{int(x)}+{int(y)}")
		c.lift()
		c.focus_force()

	def move(self, d):
		if not self.card.winfo_exists():
			return
		at = self.at + d
		if at >= len(self.g["steps"]):
			config, save = store(self.app)
			done = config.setdefault("guides_done", [])
			if self.key not in done:
				done.append(self.key)
				save()
			return self.close()
		if at >= 0:
			self.at = at
			self.show()

	def close(self):
		for w in (self.overlay, self.card):
			try:
				w.close() if hasattr(w, "close") else w.destroy()
			except tk.TclError:
				pass
		if getattr(self.app, "tour", None) is self:
			self.app.tour = None
		then, self.on_close = self.on_close, None
		if then:
			self.app.root.after(300, then)


def store(app):
	"""(settings dict, save()) where it's remembered which guides you've done: Organisation Master's own settings, else a
	small file per master (%APPDATA%/<Master>/guides.json)."""
	if callable(getattr(app, "save_config", None)) and isinstance(getattr(app, "config", None), dict):
		return app.config, app.save_config
	got = getattr(app, "_guide_store", None)
	if got is None:
		name = (getattr(app, "GUIDE_NAME", None) or getattr(app, "NAME", None) or "Master").replace(" ", "")
		path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), name, "guides.json")
		try:
			data = json.load(open(path, encoding="utf-8"))
		except (OSError, ValueError):
			data = {}

		def save():
			try:
				os.makedirs(os.path.dirname(path), exist_ok=True)
				with open(path, "w", encoding="utf-8") as f:
					json.dump(data, f, indent=1)
			except OSError:
				pass
		got = app._guide_store = (data, save)
	return got


def start(app, key, book=None):
	book = book or getattr(app, "guide_book", None) or GUIDES
	old = getattr(app, "tour", None)
	if old is not None:
		old.on_close = None  # (replaced by another guide: not "finished")
		old.close()
	app.tour = Tour(app, key, book)
	return app.tour


def menu(app, parent_menu, book=None):
	"""📖 Guides: the general one first, then one per part."""
	book = book or getattr(app, "guide_book", None) or GUIDES
	m = tk.Menu(parent_menu, tearoff=0)

	def fill():  # (each time it opens: ✓ the ones you've finished)
		m.delete(0, "end")
		done_keys = store(app)[0].get("guides_done", [])
		for n, (key, g) in enumerate(book.items()):
			done = key in done_keys
			m.add_command(label=("✓ " if done else "    ") + g["title"] + f"  -  {g['intro']}", command=lambda k=key: start(app, k, book))
			if n == 0 and len(book) > 1:
				m.add_separator()
	m.configure(postcommand=fill)
	fill()
	return m


def busy(app):
	"""A dialog is up (Who are you?, a message box...): the first start's tour waits for it."""
	if app.root.grab_current() is not None:
		return True
	for w in app.root.winfo_children():
		if isinstance(w, tk.Toplevel) and w.wm_state() not in ("withdrawn", "iconic") and not getattr(w, "_om_nonmodal", False):
			return True
	return False


def first_run(app, then):
	"""A brand new PC: the general tour on its own (no What's new, no launch settings yet); then() when it ends."""
	if busy(app):
		app.root.after(1500, lambda: first_run(app, then))
		return
	if app.config.get("guides_offered"):  # (closed during the tour last time: on to the launch settings)
		return then()
	app.config["guides_offered"] = True
	app.save_config()
	start(app, "general").on_close = then


def attach(app, menubar, name, book, ready=lambda: True):
	"""A master's 📖 Guides menu (call it before the menu bar is themed, first for it to be top left) and, the first
	time that master opens on this PC, its first guide - once ready() (it's loaded), the window is up and nothing else
	is asking."""
	app.GUIDE_NAME, app.guide_book = name, book
	first_at = 1 if int(menubar.cget("tearoff")) else 0  # (after a tear-off line, which a menu bar never shows)
	menubar.insert_cascade(first_at, label="📖 Guides", menu=menu(app, menubar, book))

	def first():
		try:
			if not ready() or not app.root.winfo_viewable() or busy(app):
				return app.root.after(1500, first)
		except tk.TclError:
			return
		config, save = store(app)
		if config.get("guides_offered"):
			return
		config["guides_offered"] = True
		save()
		start(app, next(iter(book)), book)
	app.root.after(2500, first)


def offer_first_run(app):
	"""The first time Organisation Master starts on this PC (after the guides arrived): offer the tour, once."""
	if app.config.get("guides_offered") or getattr(app, "first_start", False):
		return
	if app.root.grab_current() is not None:  # (another dialog first, e.g. the first start's launch settings)
		app.root.after(4000, lambda: offer_first_run(app))
		return
	app.config["guides_offered"] = True
	app.save_config()
	from tkinter import messagebox
	if messagebox.askyesno("Organisation Master", "New: 📖 Guides (top left) show you around, pointing at the real thing.\n\n"
												   "Take the 2-minute tour now?", parent=app.root):
		start(app, "general")
