"""Organisation Master: the central tool for Revolution Realized development.

It opens the other masters (Culture Master, Country Master) and holds the tools that work on RR's other mods and
files: To Do Master (the dev team's tasks, also shown in game) and Music Master (stations and songs of the RR
music mods, new music mods, planned stations).
"""
import json
import os
import re
import subprocess
import sys
if getattr(sys, "frozen", False):  # (the exe runs from a copy so a git pull can replace it: Scripts/run_copy.py)
	import run_copy
	run_copy.start("OrganisationMaster")
import time
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
sys.path.insert(0, os.path.join(HERE, "Scripts"))  # (the tool's code: Scripts/; the exe has it built in)
if not getattr(sys, "frozen", False):  # running the .py: the other masters' code is next door
	sys.path[:0] = [os.path.join(HERE, "..", "culture_master"), os.path.join(HERE, "..", "country_master")]

import music_master  # noqa: E402
import radio  # noqa: E402
import todo_master  # noqa: E402
import update_check  # noqa: E402
import ui  # noqa: E402
import master_links  # noqa: E402
import release_notes  # noqa: E402
from sound_feedback import SoundFeedback, SoundBindings, SharedSoundSettings, volume_window  # noqa: E402

APP_NAME = "Organisation Master"
VERSION = "1.0"
CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OrganisationMaster", "config.json")
import masters as master_registry  # noqa: E402
# (name, folder, exe, script, description): Culture / Country Master, and every master with a tools/<folder>/master.json
MASTERS = [(m["name"], m["folder"], m.get("exe", ""), m["script"], m.get("description", "")) for m in master_registry.every()]


# ---------------- shortcuts and start-up (Launch settings) ----------------
SHORTCUT = "Organisation Master.lnk"


def shell_folder(csidl):
	"""A Windows folder (desktop 0x10, Start menu programs 0x02, start-up 0x07), wherever it really is (OneDrive...)."""
	import ctypes
	buf = ctypes.create_unicode_buffer(260)
	ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
	return buf.value


def launch_places(mod_root):
	"""{key: (title, what it does, the shortcut's path)}."""
	return {"desktop": ("Desktop shortcut", "An Organisation Master shortcut on your desktop.", os.path.join(shell_folder(0x10), SHORTCUT)),
			"start": ("Start menu shortcut", "In the Start menu. To put it on the taskbar: right-click it there > Pin to taskbar.",
					  os.path.join(shell_folder(0x02), SHORTCUT)),
			"rr": ("Shortcut in the RR folder", f"A shortcut in the first-level RR folder (next to descriptor.mod):\n{mod_root}\n"
												"It's added to .gitignore, so it's never pushed.", os.path.join(mod_root, SHORTCUT)),
			"startup": ("Launch on start-up", "Organisation Master opens by itself when Windows starts.", os.path.join(shell_folder(0x07), SHORTCUT))}


def make_shortcut(path):
	"""A Windows shortcut to this tool (the exe, or the script with pythonw)."""
	if getattr(sys, "frozen", False):
		target, args, icon = sys.executable, "", sys.executable
	else:
		pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
		target, args, icon = (pyw if os.path.exists(pyw) else sys.executable), f'"{os.path.abspath(__file__)}"', os.path.join(HERE, "organisation_master.ico")
	env = dict(clean_env(), OM_LNK=path, OM_TARGET=target, OM_ARGS=args, OM_DIR=HERE, OM_ICON=icon)
	ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:OM_LNK); $s.TargetPath=$env:OM_TARGET; $s.Arguments=$env:OM_ARGS; "
		  "$s.WorkingDirectory=$env:OM_DIR; $s.IconLocation=$env:OM_ICON; $s.Description='Organisation Master - Revolution Realized'; $s.Save()")
	r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, capture_output=True, text=True, timeout=60,
					   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
	if r.returncode != 0 or not os.path.exists(path):
		raise OSError((r.stderr or "the shortcut wasn't made").strip()[:300])


def git_ignore(mod_root, line):
	"""A line in RR's .gitignore (kept with its line endings)."""
	p = os.path.join(mod_root, ".gitignore")
	try:
		raw = open(p, "rb").read()
	except OSError:
		raw = b""
	text = raw.decode("utf-8", "replace")
	if line in [l.strip() for l in text.splitlines()]:
		return
	end = "\r\n" if "\r\n" in text or not text else "\n"
	with open(p, "ab") as f:
		f.write(((end if text and not text.endswith(("\n", "\r")) else "") + line + end).encode("utf-8"))


def clean_env():
	"""Environment for starting another tool: a fresh one-file exe (not tied to this one's temp folder)."""
	env = dict(os.environ)
	env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
	for k in list(env):
		if k.startswith("_MEIPASS") or k.startswith("_PYI_"):
			del env[k]
	return env


def find_mod_root():
	"""Revolution Realized: the folder above tools/organisation_master (a descriptor.mod in it)."""
	d = HERE
	for _ in range(4):
		d = os.path.dirname(d)
		if os.path.isfile(os.path.join(d, "descriptor.mod")):
			return d
	return os.path.dirname(os.path.dirname(HERE))


class App(SoundBindings):
	def __init__(self, root):
		self.root = root
		self.tool_dir = HERE
		root._sound_feedback = self
		self.mod_root = find_mod_root()
		self.mod_dir = os.path.dirname(self.mod_root)  # the HOI4 mod folder: RR's music mods sit next to it
		self.config = self.load_config()
		self.recent_changes = release_notes.RecentChanges(self)
		self._ready = False
		self.sound_settings = SharedSoundSettings()
		self.sounds = SoundFeedback(self.sound_settings.enabled, theme=lambda: ui.theme_for("Organisation Master"),
									volume=self.sound_settings.volume)
		self.changes = []
		music_master.TOOL_DIR = HERE
		todo_master.icons.DIR = os.path.join(HERE, "icons")
		todo_master.icons.MOD_ROOT = self.mod_root
		todo_master.TOOL_DIR = HERE
		root.title(f"{APP_NAME} {VERSION} - {self.mod_root}")
		try:
			root.iconbitmap(os.path.join(getattr(sys, "_MEIPASS", HERE), "organisation_master.ico"))
		except Exception:
			pass
		self.build()
		self.install_button_sounds()
		self._ready = True
		from halloween_ghost import HalloweenGhost
		self.halloween_ghost = HalloweenGhost(self)
		from theme_secrets import ThemeSecrets
		self.theme_secrets = ThemeSecrets(self)
		from achievement_toast import AchievementToasts
		self.achievement_toasts = AchievementToasts(self)
		from presence_toast import PresenceToasts
		self.presence_toasts = PresenceToasts(self)  # (👋 another dev opened a tool)
		from milestone_celebration import Celebrations
		self.milestone_celebrations = Celebrations(self)
		from since_last import SinceLastHere
		self.since_last = SinceLastHere(self)  # (📬 what happened since you last opened it)
		self.record_access("Organisation Master")
		self.record_access(self.config.get("page", "To Do Master"))
		self.background = "--background" in sys.argv  # (started by another master: minimised, quietly - om_companion.py)
		if not self.background:
			self.play_startup()
		root.protocol("WM_DELETE_WINDOW", self.quit)
		root.after(3500, self.recent_changes.startup)
		import now_doing
		self.now_publisher = now_doing.Publisher(self.todo_page(), lambda: self.config.get("share_doing", True))
		root.after(4000, self.now_doing)  # (🟢 what you're up to, shared with the team)

	def now_doing(self):
		"""🟢 Every 10 s: this tool's line, then this PC's tools' lines into the shared data (throttled; see now_doing.py)."""
		if getattr(self, "_quitting", False):
			return
		import now_doing
		try:
			now_doing.report("Organisation Master", self.now_text())
			todo = self.todo_page()
			if self.now_publisher.tick():
				todo.save(undoable=False, feedback=False)
			todo.activity.refresh_online()  # (🟢 Developer activity: who's online, what they're up to)
		except Exception:
			pass
		self.root.after(10000, self.now_doing)

	def now_text(self):
		"""What you're doing in Organisation Master, in a few words."""
		games = getattr(self, "rr_games_window", None)
		if games is not None and games.winfo_exists():
			if getattr(games, "active", False):
				from rr_games_data import GAMES
				name = GAMES.get(getattr(games, "session_game", ""), ("an RR game",))[0]
				return f"Playing {name} ({str(getattr(games, 'session_level', '')).title()})"
			return "Picking an RR game"
		page = next((n for n, (make, frame) in self.pages.items() if frame is not None and frame.winfo_ismapped()), "")
		if page != "To Do Master":
			return f"In {page}" if page else "Around"
		todo = self.todo_page()
		mode = todo.mode.get()
		if mode == "gfx":
			view = todo.gfx_pane.view.get()
			return {"review": "Reviewing pictures (🔎 Review swiper)", "swipe": "Swiping for a GFX task"}.get(view, "Looking through 🖼 GFX")
		if mode in ("idea", "vc", "achievements"):
			return {"idea": "Reading 💡 Ideas", "vc": "In the 🎙 Dev VCs", "achievements": "Looking at 🏆 achievements"}[mode]
		t = getattr(todo, "cur", None)
		return f"On the To Do · {t['ref']} {t.get('title', '')[:50]}" if t else "On the To Do"

	def quit(self):
		"""Closing: anything still waiting to be written is saved first (plan edits), and the music stops."""
		if getattr(self, "_quitting", False):
			return
		self.save_config()  # (the window size)
		try:  # (🟢 offline for the team; this tool's line goes)
			import now_doing
			now_doing.clear("Organisation Master")
			self.now_publisher.offline()
			self.todo_page().save(undoable=False, feedback=False)
		except Exception:
			pass
		games = getattr(self, "rr_games_window", None)
		if games is not None and games.winfo_exists():
			games.close()
		for make, frame in self.pages.values():
			page = frame.inner.winfo_children()[0] if frame is not None and hasattr(frame, "inner") else frame
			if page is not None and hasattr(page, "close"):
				try:
					if page.close() is False:  # (unsaved changes, and the closing was cancelled)
						return
				except Exception:
					pass
		for w in [self.root] + [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]:
			try:  # (gone from the screen at once: the rest - the last sync, the exit sound - happens unseen)
				w.withdraw()
			except tk.TclError:
				pass
		self.radio.close()
		self._quitting = True
		if getattr(self, "rr_games_service", None):
			self.rr_games_service.close()
		self.halloween_ghost.close()
		self.theme_secrets.close()
		self.achievement_toasts.close()
		self.presence_toasts.close()
		self.milestone_celebrations.close()
		done = self.sounds.finish()
		deadline = time.monotonic() + 1.5
		def finish_close():
			if done.is_set() or time.monotonic() >= deadline:
				self.root.destroy()
			else:
				self.root.after(20, finish_close)
		finish_close()

	# ---------- config / log ----------
	def load_config(self):
		try:
			return json.load(open(CONFIG, encoding="utf-8"))
		except (OSError, ValueError):
			return {}

	def save_config(self):
		os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
		json.dump(self.config, open(CONFIG, "w", encoding="utf-8"), indent=1)

	def log(self, what):
		self.changes.append((time.strftime("%H:%M:%S"), what))
		self.changes_btn.config(text=f"Files changed ({len(self.changes)})")

	def set_status(self, text):
		self.status.config(text=text)

	def feedback(self, kind="success"):
		if self._ready and not getattr(self, "_quitting", False):
			self.sounds.play(kind)

	def toggle_sound(self):
		self.sound_settings.set(self.sound_var.get())
		self.config["sound_feedback"] = self.sound_var.get()
		self.save_config()
		self.feedback()
		self.set_status("Sound feedback " + ("on." if self.sound_var.get() else "off."))


	def game_version(self):
		try:
			m = re.search(r'supported_version\s*=\s*"([^"]+)"', open(os.path.join(self.mod_root, "descriptor.mod"), encoding="utf-8-sig").read())
			return m.group(1) if m else "1.13.*"
		except OSError:
			return "1.13.*"

	# ---------- window ----------
	def build(self):
		root = self.root
		root.geometry(self.config.get("geometry", "1500x900"))
		ui.init(root, self.config.get("text_scale", 1.0))
		ui.load_themes(os.path.join(HERE, "themes"))
		if not os.path.exists(ui.THEME_FILE) and self.config.get("theme"):  # (the theme used to be in this tool's settings)
			ui.choose_theme("Organisation Master", self.config["theme"], False)
		ui.apply_theme(root, ui.theme_for("Organisation Master"))
		root.bind("<Configure>", lambda ev: ev.widget is root and not self.is_fullscreen() and self.config.update(geometry=root.geometry()))
		menu = tk.Menu(root)
		import guides
		menu.add_cascade(label="📖 Guides", menu=guides.menu(self, menu))  # (top left: the general tour, then one per part)
		root.after(5000, lambda: guides.offer_first_run(self))
		fm = tk.Menu(menu, tearoff=0)
		fm.add_command(label="Open the RR folder", command=lambda: os.startfile(self.mod_root))
		fm.add_command(label="Open the mod folder", command=lambda: os.startfile(self.mod_dir))
		fm.add_separator()
		fm.add_command(label="Quit", command=self.quit)
		menu.add_cascade(label="File", menu=fm)
		mm = tk.Menu(menu, tearoff=0)
		for name, *_ in MASTERS:
			mm.add_command(label=name, command=lambda n=name: self.open_master(n))
		menu.add_cascade(label="Masters", menu=mm)
		vm = tk.Menu(menu, tearoff=0)
		self.settings_menu = vm
		self.scale_var = tk.DoubleVar(value=self.config.get("text_scale", 1.0))
		for name, sc in ui.SCALES:
			vm.add_radiobutton(label=f"Text size: {name} ({int(sc * 100)}%)", variable=self.scale_var, value=sc,
							   command=lambda: self.set_scale(self.scale_var.get()))
		vm.add_separator()
		vm.add_command(label="Bigger text", accelerator="Ctrl +", command=lambda: self.step_scale(1))
		vm.add_command(label="Smaller text", accelerator="Ctrl -", command=lambda: self.step_scale(-1))
		vm.add_separator()
		vm.add_command(label="Open every section", command=lambda: ui.all_sections(False))
		vm.add_command(label="Fold every section", command=lambda: ui.all_sections(True))
		vm.add_separator()
		window_menu = tk.Menu(vm, tearoff=0)
		self.window_mode_var = tk.StringVar(value=self.config.get("launch_mode", "window"))
		for value, label in (("window", "Windowed"), ("fullscreen", "Borderless full screen")):
			window_menu.add_radiobutton(label=label, variable=self.window_mode_var, value=value,
									   command=lambda: self.set_fullscreen(self.window_mode_var.get() == "fullscreen"))
		vm.add_cascade(label="Window mode", menu=window_menu)
		vm.add_separator()
		self.sound_var = tk.BooleanVar(value=self.sound_settings.enabled())
		vm.configure(postcommand=lambda: self.sound_var.set(self.sound_settings.enabled()))
		vm.add_checkbutton(label="Sound feedback", variable=self.sound_var, command=self.toggle_sound)
		vm.add_command(label="Sound volume...", command=lambda: volume_window(self.root, self.sound_settings, self.feedback))
		self.presence_var = tk.BooleanVar(value=self.config.get("presence_toasts", True))
		vm.add_checkbutton(label="👋 Show when other devs open a tool", variable=self.presence_var,
						   command=lambda: (self.config.update(presence_toasts=self.presence_var.get()), self.save_config()))
		self.since_var = tk.BooleanVar(value=self.config.get("since_last_here", True))
		vm.add_checkbutton(label="📬 Show “Since you were last here” on opening", variable=self.since_var,
						   command=lambda: (self.config.update(since_last_here=self.since_var.get()), self.save_config()))
		vm.add_command(label="📬 Since you were last here...", command=lambda: self.since_last.show(quiet=False))
		vm.add_command(label="✨ Remini (GFPGAN): set up / uninstall...", command=lambda: __import__("remini").Settings(self.root))
		self.share_var = tk.BooleanVar(value=self.config.get("share_doing", True))
		vm.add_checkbutton(label="🟢 Share what I'm doing (else just that I'm online)", variable=self.share_var,
						   command=lambda: (self.config.update(share_doing=self.share_var.get()), self.save_config()))
		self.companion_var = tk.BooleanVar(value=self.config.get("start_with_masters", True))
		vm.add_checkbutton(label="🟢 Start in the background with the other masters (so they're shared)", variable=self.companion_var,
						   command=lambda: (self.config.update(start_with_masters=self.companion_var.get()), self.save_config()))
		self.alerts_var = tk.BooleanVar(value=self.config.get("error_alerts", True))
		vm.add_checkbutton(label="🚨 Error alerts can pop up for me", variable=self.alerts_var,
						   command=lambda: __import__("error_alerts").set_enabled(self, self.alerts_var.get()))
		vm.add_separator()
		vm.add_command(label="🩺 Check the To Do data...", command=lambda: __import__("data_check").show(self.root, self.page("To Do Master")))
		# HASHED OUT 2026-10-25 at Mike's request: the Celebration tester is removed (see AGENTS.md); don't bring it back unasked.
		# from milestone_celebration import tester_menu
		# vm.add_cascade(label="Celebration tester", menu=tester_menu(self, vm))
		menu.add_cascade(label="Settings", menu=vm)
		tm = ui.theme_menu(root, menu, "Organisation Master")  # (one theme for all the masters; "Just for ..." keeps one apart)
		tm.add_command(label="Open the themes folder", command=lambda: os.startfile(os.path.join(HERE, "themes")))
		lm = tk.Menu(menu, tearoff=0)
		lm.add_command(label="Shortcuts and start-up...", command=self.launch_settings)
		menu.add_cascade(label="Launch settings", menu=lm)
		menu.add_command(label="Achievements", command=lambda: self.show_page("Achievements"))
		menu.add_command(label="RR Games", command=self.show_games)
		menu.add_command(label="Recent Changes", command=self.recent_changes.show)
		menu.add_command(label="🔎 Search (Ctrl+K)", command=self.open_search)
		self.menubar = ui.MenuBar(root, menu)  # (drawn by the tool, so it follows the theme)
		self.menubar.pack(side="top", fill="x")
		# borderless full screen has no window frame: its own close / minimise / back-to-a-window, top right
		self.fs_buttons = [self.menubar.add_right("✕", self.quit, hover="#c42b1c"),
						   self.menubar.add_right("—", self.root.iconify),
						   self.menubar.add_right("🗗 Exit full screen (Esc)", lambda: self.set_fullscreen(False))]
		root.bind("<Escape>", lambda ev: (self.set_fullscreen(False), "break")[1] if self.is_fullscreen() else None)
		self.update_check = update_check.UpdateCheck(self)  # (⚠ when a newer build is on this PC or on GitHub)
		self.update_check.start(self.menubar)
		root.after(300, lambda: ui.title_bar(root))  # (once the window is really there)
		root.bind_all("<F11>", lambda ev: self.set_fullscreen(not self.is_fullscreen()))
		if getattr(self, "background", False):
			root.after(150, root.iconify)
		elif self.config.get("launch_mode") == "fullscreen":
			root.after(100, lambda: self.set_fullscreen(True, remember=False))
		self.first_start = not self.config.get("launch_asked")
		if self.first_start:  # (the first time on this PC: only the 📖 tour, then shortcuts / start with Windows - no What's new)
			root.after(1500, lambda: guides.first_run(self, then=lambda: self.launch_settings(first=True)))
		for k in ("<Control-k>", "<Control-K>"):  # (🔎 search everything; also in text boxes, where Tk's Ctrl+K would delete the line)
			root.bind_all(k, lambda ev: (self.open_search(), "break")[1])
			for cls in ("Text", "Entry", "TEntry", "TCombobox"):
				root.bind_class(cls, k, lambda ev: (self.open_search(), "break")[1])
		for k in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
			root.bind_all(k, lambda ev: self.step_scale(1))
		for k in ("<Control-minus>", "<Control-KP_Subtract>"):
			root.bind_all(k, lambda ev: self.step_scale(-1))

		body = self.body = ttk.Frame(root)
		body.pack(fill="both", expand=True)
		nav = self.nav = ttk.Frame(body, padding=8, width=ui.px(240))
		nav.pack(side="left", fill="y")
		nav.pack_propagate(False)
		self.nav_title = ttk.Label(nav, text="Organisation Master", font="om_title")
		self.nav_title.pack(anchor="w")
		ttk.Label(nav, text="Revolution Realized", foreground="#666").pack(anchor="w", pady=(0, 10))
		ttk.Label(nav, text="TOOLS", foreground="#888", font="om_tiny").pack(anchor="w")
		self.pages = {}
		self.nav_buttons = {}
		self.content = ttk.Frame(body)
		self.content.pack(side="left", fill="both", expand=True)
		self.add_page("To Do Master", lambda parent: todo_master.TodoMaster(parent, self), nav)
		self.error_log_window = None
		self.error_btn = ttk.Button(nav, text="Error Log Master  ↗", style="Nav.TButton",
									command=lambda: __import__("error_log_master").show(self))  # (🐞 a pop-out, not a page)
		self.error_btn.pack(fill="x", pady=1)
		__import__("error_log_master").start_watch(self)  # (🐞 n: problems in the files you've just changed)
		__import__("error_alerts").start(self)  # (🚨 an error another dev flashed at you: pops up until answered)
		self.add_page("Music Master", lambda parent: music_master.MusicMaster(parent, self), nav)
		ttk.Label(nav, text="(more to come)", foreground="#aaa").pack(anchor="w", padx=10)
		ttk.Separator(nav).pack(fill="x", pady=10)
		ttk.Label(nav, text="OTHER MASTERS", foreground="#888", font="om_tiny").pack(anchor="w")
		for name, folder, exe, script, desc in MASTERS:
			b = ttk.Button(nav, text=f"▸ {name}", style="Nav.TButton", command=lambda n=name: self.open_master(n))
			b.pack(fill="x", pady=1)
			ttk.Label(nav, text=desc, foreground="#777", wraplength=ui.px(200), justify="left", font="om_tiny").pack(anchor="w", padx=6, pady=(0, 4))
		ttk.Separator(nav).pack(fill="x", pady=10)
		self.changes_btn = ttk.Button(nav, text="Files changed (0)", style="Small.TButton", command=self.show_changes)
		self.changes_btn.pack(fill="x")
		self.radio = radio.Radio(nav, self)
		self.radio.pack(side="bottom", fill="x", pady=(8, 0))
		# the theme's logo (assets.logo), very faint, in the empty space at the bottom of the side bar
		self.logo_label = tk.Label(nav, borderwidth=0, highlightthickness=0)
		self.logo_label.pack(side="bottom", pady=(0, 8))
		self._logo_job = None
		self.nav.bind("<Configure>", self.schedule_logo, add="+")
		ui.THEME_HOOKS.append(self.draw_logo)
		root.after(400, self.draw_logo)
		self.status = ttk.Label(root, text="", relief="sunken", anchor="w")
		self.status.pack(fill="x", side="bottom")
		self.show_page(self.config.get("page", "Music Master"))

	def draw_logo(self):
		self._logo_job = None
		if not self.logo_label.winfo_exists():
			return
		bg = ttk.Style(self.root).lookup("TFrame", "background") or "#f0f0f0"
		size = min(ui.px(300), self.nav.winfo_width() - ui.px(16)) if self.nav.winfo_width() > 1 else ui.px(220)
		# Decorative artwork yields to the radio and buttons on short windows.
		used = 16
		for child in self.nav.pack_slaves():
			if child is self.logo_label:
				continue
			padding = child.pack_info().get("pady", 0)
			padding = padding if isinstance(padding, (tuple, list)) else self.root.tk.splitlist(str(padding))
			margins = sum(child.winfo_pixels(value) for value in padding)
			if len(padding) == 1:
				margins *= 2
			used += child.winfo_reqheight() + margins
		size = min(size, max(0, self.nav.winfo_height() - used - 8))
		self._logo = ui.logo_watermark(size, bg)
		self.logo_label.config(image=self._logo or "", background=bg)
		if self._logo:
			self.logo_label.pack(side="bottom", pady=(0, 8))
		else:
			self.logo_label.pack_forget()

	def schedule_logo(self, event=None):
		if self._logo_job is not None:
			self.root.after_cancel(self._logo_job)
		self._logo_job = self.root.after(50, self.draw_logo)

	def set_scale(self, sc):
		ui.set_scale(self.root, sc)
		if hasattr(self, "theme_secrets"):
			self.theme_secrets.dismiss()
			self.theme_secrets.retheme()
		self.nav.config(width=ui.px(240))
		for child in self.nav.winfo_children():
			if isinstance(child,ttk.Label) and child.cget("wraplength"):
				child.configure(wraplength=ui.px(200))
		self.root.after(200, self.draw_logo)
		self.scale_var.set(sc)
		self.config["text_scale"] = sc
		self.save_config()
		self.set_status(f"Text size {int(sc * 100)}%")

	def is_fullscreen(self):
		try:
			return bool(self.root.attributes("-fullscreen"))
		except tk.TclError:
			return False

	def set_fullscreen(self, on, remember=True):
		"""Borderless full screen (the whole screen, no window frame) or the normal window."""
		self.root.attributes("-fullscreen", bool(on))
		for b in self.fs_buttons:
			if on:
				b.pack(side="right")
			else:
				b.pack_forget()
		if hasattr(self,"theme_secrets"):
			self.theme_secrets.place_pumpkin()
		if not on and self.config.get("geometry"):
			self.root.geometry(self.config["geometry"])
		self.root.after(200, lambda: ui.title_bar(self.root))
		self.window_mode_var.set("fullscreen" if on else "window")
		if remember:
			self.config["launch_mode"] = self.window_mode_var.get()
			self.save_config()
			self.feedback()

	def launch_settings(self, first=False):
		"""Where Organisation Master has shortcuts (desktop, Start menu, the RR folder) and whether it starts with Windows."""
		self.config["launch_asked"] = True
		self.save_config()
		try:
			places = launch_places(self.mod_root)
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't find the Windows folders: {ex}")
			return
		w = tk.Toplevel(self.root)
		w.title("Launch settings")
		w.transient(self.root)
		w.resizable(False, False)
		f = ttk.Frame(w, padding=14)
		f.pack()
		ttk.Label(f, text="Welcome to Organisation Master" if first else "Launch settings", style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text="Where would you like to open Organisation Master from? Tick the ones you want; unticking one removes "
						  "that shortcut.\nThese are just for this PC. You can change them any time: Launch settings, in the bar at the top.",
				  style="Muted.TLabel", justify="left").pack(anchor="w", pady=(2, 10))
		v = {}
		ttk.Style(w).configure("Bold.TCheckbutton", font="om_bold")
		for key, (title, what, path) in places.items():
			v[key] = tk.BooleanVar(value=os.path.exists(path))
			ttk.Checkbutton(f, text=title, variable=v[key], style="Bold.TCheckbutton").pack(anchor="w", pady=(6, 0))
			ttk.Label(f, text=what, style="Muted.TLabel", justify="left").pack(anchor="w", padx=(ui.px(24), 0))
		def ok():
			done, errors = [], []
			for key, (text, _, path) in places.items():
				try:
					if v[key].get() and not os.path.exists(path):
						make_shortcut(path)
						if key == "rr":
							git_ignore(self.mod_root, SHORTCUT)
						done.append(f"+ {text}")
					elif not v[key].get() and os.path.exists(path):
						os.remove(path)
						done.append(f"- {text}")
				except Exception as ex:
					errors.append(f"{text}: {ex}")
			w.destroy()
			if errors:
				messagebox.showerror(APP_NAME, "\n".join(errors))
			self.set_status("Launch settings: " + ("; ".join(done) if done else "nothing changed"))
		bf = ttk.Frame(f)
		bf.pack(anchor="e", pady=(12, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Not now" if first else "Cancel", command=w.destroy).pack(side="left", padx=4)

	def set_theme(self, name):
		ui.choose_theme("Organisation Master", name, False)
		ui.apply_theme(self.root, name)
		self.config["theme"] = name
		self.save_config()
		self.set_status(f"Theme: {name}")

	def step_scale(self, d):
		steps = [sc for _, sc in ui.SCALES]
		cur = min(range(len(steps)), key=lambda i: abs(steps[i] - ui.scale()))
		self.set_scale(steps[max(0, min(len(steps) - 1, cur + d))])

	def add_page(self, name, make, nav):
		self.pages[name] = (make, None)
		b = ttk.Button(nav, text=name, style="Nav.TButton", command=lambda: self.show_page(name))
		b.pack(fill="x", pady=1)
		self.nav_buttons[name] = b

	def show_page(self, name):
		if name == "Achievements":  # Previous versions remembered Achievements as a sidebar page.
			name = "To Do Master"
			self.todo_page().mode.set("achievements")
			self.todo_page().mode_changed()
		elif name == "To Do Master":
			page = self.todo_page()
			if page.mode.get() == "achievements":
				page.mode.set(self.config.get("todo_last_mode", "dev"))
				page.mode_changed()
		if name not in self.pages:
			name = next(iter(self.pages))
		for n, (make, frame) in self.pages.items():
			if frame is not None:
				frame.pack_forget()
		self.page(name)
		frame = self.pages[name][1]
		frame.pack(fill="both", expand=True)
		for n, b in self.nav_buttons.items():
			b.state(["pressed"] if n == name else ["!pressed"])
		self.config["page"] = name
		self.save_config()
		if self._ready:
			self.record_access(name)

	def record_access(self, name):
		from master_activity import record
		holder = self.pages.get("To Do Master", (None, None))[1]
		who = holder.inner.winfo_children()[0].me.get() if holder is not None else self.config.get("todo_me")
		if name == "To Do Master":
			mode = self.todo_page().mode.get()
			name = {"idea": "Ideas", "vc": "Dev VCs"}.get(mode, name)
		record(name, self.mod_root, action="opened", who=who)

	def open_search(self):
		import search_palette
		search_palette.open_palette(self)

	def page(self, name):
		"""A tool page (made the first time it's needed, shown or not)."""
		make, frame = self.pages[name]
		if frame is None:
			holder = ui.ScrollFrame(self.content)  # the page scrolls when it's taller than the window
			self.pages[name] = (make, holder)
			page = make(holder.inner)
			page.pack(fill="both", expand=True)
		return self.pages[name][1].inner.winfo_children()[0]

	def show_games(self):
		import rr_games
		rr_games.show(self)

	def todo_page(self):
		"""To Do Master (Music Master keeps its RR Music Mods project in step)."""
		return self.page("To Do Master")

	def existing_music_page(self):
		"""Sync updates an open Music Master without constructing it in the background."""
		_, holder = self.pages.get("Music Master", (None, None))
		children = holder.inner.winfo_children() if holder is not None else []
		return children[0] if children else None

	def navigate_master(self, link):
		try:
			target = master_links.parse(link)
		except ValueError as error:
			messagebox.showerror(APP_NAME, str(error), parent=self.root)
			return
		if target["master"] == "Music Master":
			self.show_page("Music Master")
			self.page("Music Master").open_target(target)
		else:
			self.open_master(target["master"], link)

	def open_master(self, name, target=None):
		folder, exe, script = next((f, e, s) for n, f, e, s, _ in MASTERS if n == name)
		base = os.path.dirname(HERE)
		exe_path, script_path = os.path.join(base, folder, exe), os.path.join(base, folder, script)
		args = [self.mod_root] + (["--open", target] if target else [])
		if exe and os.path.isfile(exe_path):
			subprocess.Popen([exe_path, *args], env=clean_env())
		elif os.path.isfile(script_path):
			subprocess.Popen([sys.executable, script_path, *args], env=clean_env())
		else:
			messagebox.showerror(APP_NAME, f"{name} isn't in tools/{folder}.")
			return
		self.set_status(f"Opening {name} (it takes a few seconds)...")

	def show_changes(self):
		w = tk.Toplevel(self.root)
		w.title("Files changed this session")
		w.geometry("700x400")
		if getattr(self,"theme_secrets",None):self.theme_secrets.attach_changes(w)
		t = tk.Text(w, wrap="word", font=("Consolas", 9))
		t.pack(fill="both", expand=True)
		t.insert("1.0", "\n".join(f"{a}  {b}" for a, b in reversed(self.changes)) or "Nothing written this session.")


def main():
	root = tk.Tk()
	App(root)
	root.mainloop()


if __name__ == "__main__":
	main()
