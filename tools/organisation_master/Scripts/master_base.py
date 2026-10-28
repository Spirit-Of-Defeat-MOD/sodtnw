"""The shared start of a master (Culture / Country Master's way, in one place): a new master is a MasterApp subclass that
fills in build() (and build_menu() / open_target() if it wants), and gets for free:

- the mod folder found (or asked for once, remembered), its window title, size and position remembered;
- the shared theme, Theme menu, sounds (Settings > Sound feedback / volume) and the themed menu bar;
- File (Open the mod folder, Reload, Quit) and "◂ Organisation Master" in the menu bar;
- a status line, set_status(), feedback(), saved() (records the save for To Do Master's activity, the change log and
  the achievements), "opened" recorded, rr:// links from the other masters (open_target), a graceful close.

Start a new one from tools/organisation_master/master_template (see its README.md)."""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import paths
import ui

FROZEN = getattr(sys, "frozen", False)


def is_mod(d):
	"""A HOI4 mod folder (Revolution Realized or another): descriptor.mod and common/."""
	return bool(d) and os.path.isfile(os.path.join(d, "descriptor.mod")) and os.path.isdir(os.path.join(d, "common"))


def find_mod_root(argv, config):
	"""The mod: the first argument (Organisation Master passes it), else the folder this tool is in (tools/<x> of the
	mod), else the one picked last time, else ask."""
	if len(argv) > 1 and is_mod(argv[1]):
		return os.path.abspath(argv[1])
	d = paths.TOOL
	for _ in range(4):
		if is_mod(d):
			return d
		d = os.path.dirname(d)
	if is_mod(config.get("mod_root")):
		return config["mod_root"]
	d = filedialog.askdirectory(title="Pick the mod folder")
	if not is_mod(d):
		messagebox.showerror("Master", "That folder isn't a HOI4 mod (no descriptor.mod / common folder).")
		return None
	return d


def clean_env():
	"""The environment for another PyInstaller exe (without this one's own variables)."""
	return {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}


class MasterApp:
	NAME = "New Master"  # (shown in the title, the theme's "Just for this master", activity and achievements)
	ICON = None          # (an .ico next to the script / built into the exe)
	SIZE = "1300x850"

	def __init__(self, root, mod_root, config):
		self.root, self.mod_root, self.config = root, mod_root, config
		self.config["mod_root"] = mod_root
		root.title(f"{self.NAME} - {mod_root}")
		root.geometry(config.get("geometry", self.SIZE))
		root.bind("<Configure>", lambda ev: ev.widget is root and self.config.update(geometry=root.geometry()))
		menu = tk.Menu(root)
		fm = tk.Menu(menu, tearoff=0)
		fm.add_command(label="Open the mod folder", command=lambda: os.startfile(self.mod_root))
		fm.add_command(label="Reload from disk", command=self.reload)
		fm.add_separator()
		fm.add_command(label="Quit", command=self.quit)
		menu.add_cascade(label="File", menu=fm)
		self.build_menu(menu)
		menu.add_command(label="💬 Request", command=self.request)
		menu.add_command(label="  ◂ Organisation Master", command=self.open_organisation_master)
		self.menubar = ui.setup_master(root, menu, self.NAME, os.path.join(paths.TOOL, "themes"))
		ui.KEEP_COLOURS[0] = False  # (a new master follows the theme fully, unlike Culture / Country Master's own colours)
		ui.apply_theme(root, ui.theme_for(self.NAME), fonts=False)
		self.status = ttk.Label(root, text="", style="Muted.TLabel", anchor="w", padding=(8, 2))
		self.status.pack(side="bottom", fill="x")
		self.body = ttk.Frame(root, padding=8)
		self.body.pack(fill="both", expand=True)
		self.build(self.body)
		root.protocol("WM_DELETE_WINDOW", self.quit)
		self.record("opened")
		root.after(3000, self.keep_organisation_master)  # (🟢 so what you do here reaches the team)
		sounds = getattr(root, "_sound_feedback", None)
		if sounds is not None:
			sounds._ready = True
			sounds.play_startup()

	# ---- for the master to fill in ----
	def build_menu(self, menu):
		"""Menus between File and ◂ Organisation Master."""

	def build(self, body):
		"""The window's contents, in body."""

	def reload(self):
		"""File > Reload from disk."""
		self.set_status("Nothing to reload.")

	def request(self):
		"""💬 A bug, idea or change for this master, straight into the To Do (Tools > Requests > this master)."""
		import master_request
		master_request.window(self.root, self.NAME, self.mod_root, context=self.request_context, status=self.set_status)

	def request_context(self):
		"""What you're on now, offered as a line of a Request's note."""
		return ""

	def open_target(self, link):
		"""An rr://<link>/<kind>/<value> link from another master or To Do Master (master_links.parse(link))."""

	# ---- shared ----
	def set_status(self, text):
		self.status.config(text=text)

	def feedback(self, kind="success"):
		sounds = getattr(self.root, "_sound_feedback", None)
		if sounds is not None:
			sounds.feedback(kind)

	def record(self, action, files=(), **extra):
		try:
			from master_activity import record
			record(self.NAME, self.mod_root, action=action, files=files, **extra)
		except Exception:
			pass  # (not registered / no inbox: nothing to tell To Do Master)

	def saved(self, files, text=None):
		"""After writing files to the mod: To Do Master hears of it (activity, achievements), a sound, the status."""
		self.record("saved", files)
		self.feedback("success")
		self.set_status(text or f"Saved {', '.join(files)}.")

	def keep_organisation_master(self):
		"""Organisation Master shares this master's activity with the team: started minimised if it isn't running."""
		import threading

		def go():
			try:
				import om_companion
				if om_companion.ensure(os.path.join(os.path.dirname(paths.TOOL), "organisation_master"), clean_env()):
					self.root.after(0, lambda: self.set_status("🟢 Started Organisation Master in the background, so the team sees what you do here."))
			except Exception:
				pass
		threading.Thread(target=go, daemon=True).start()

	def open_organisation_master(self):
		folder = os.path.join(os.path.dirname(paths.TOOL), "organisation_master")
		exe, script = os.path.join(folder, "OrganisationMaster.exe"), os.path.join(folder, "organisation_master.py")
		try:
			if os.path.isfile(exe):
				subprocess.Popen([exe], env=clean_env())
			else:
				subprocess.Popen([sys.executable, script], env=clean_env())
		except OSError as ex:
			messagebox.showerror(self.NAME, f"Can't open Organisation Master:\n{ex}")

	def quit(self):
		save_config(self.NAME, self.config)
		sounds = getattr(self.root, "_sound_feedback", None)
		if sounds is not None:
			sounds.close()
		else:
			self.root.destroy()


def config_path(name):
	return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), name.replace(" ", ""), "config.json")


def load_config(name):
	try:
		with open(config_path(name), encoding="utf-8") as f:
			return json.load(f)
	except (OSError, ValueError):
		return {}


def save_config(name, config):
	try:
		os.makedirs(os.path.dirname(config_path(name)), exist_ok=True)
		with open(config_path(name), "w", encoding="utf-8") as f:
			json.dump(config, f, indent=1)
	except OSError:
		pass


def run(cls, script_file):
	"""The master's main(): its window, the mod, an rr:// link it was opened with."""
	root = tk.Tk()
	if cls.ICON:
		try:
			root.iconbitmap(os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(script_file))), cls.ICON))
		except tk.TclError:
			pass
	config = load_config(cls.NAME)
	mod = find_mod_root(sys.argv, config)
	if not mod:
		root.destroy()
		return
	app = cls(root, mod, config)
	from master_links import argument
	link = argument(sys.argv)
	if link is not None:
		root.after(200, lambda: app.open_target(link))
	root.mainloop()
