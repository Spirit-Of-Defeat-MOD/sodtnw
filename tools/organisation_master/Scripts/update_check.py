"""Is this build out of date? Two checks, in the background:

- the exe on disk changed after this one started (pulled or rebuilt while open): restart to use it;
- GitHub has a newer exe than this PC's copy of the RR repository (a quiet 'git fetch', which never touches your
  files): pull, then restart. Culture Master and Country Master's exes are checked the same way.

The result shows in the menu bar (an orange ⚠ Update...), the window title and Live Sync setup."""
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "Organisation Master"
EXES = (("Organisation Master", "tools/organisation_master/OrganisationMaster.exe"),
		("Culture Master", "tools/culture_master/CultureMaster.exe"),
		("Country Master", "tools/country_master/CountryMaster.exe"))
try:  # (new masters: tools/<folder>/master.json)
	import masters as _masters
	EXES += tuple((m["name"], f"tools/{m['folder']}/{m['exe']}") for m in _masters.discovered() if m.get("exe"))
except Exception:
	pass
EVERY = 10 * 60 * 1000  # (ms between checks)


def git(cwd, *args, timeout=60):
	try:
		r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
						   timeout=timeout, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
						   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		return r.returncode == 0, r.stdout.strip()
	except (OSError, subprocess.SubprocessError):
		return False, ""


def file_key(path):
	try:
		st = os.stat(path)
		return st.st_mtime_ns, st.st_size
	except OSError:
		return None


class UpdateCheck:
	def __init__(self, app):
		self.app = app
		self.frozen = getattr(sys, "frozen", False)
		self.exe = sys.executable if self.frozen else None
		self.started = file_key(self.exe) if self.exe else None
		self.state = {"restart": False, "pull": [], "checked": None, "error": ""}
		self.banner = None
		self._busy = False

	def start(self, menubar):
		self.banner = menubar.add_right("⚠ Update...", self.explain, hover="#c46a00")
		self.banner.pack_forget()
		self.app.root.after(20000, self.check)  # (once the tool has settled)

	def check(self):
		if self._busy or not self.app.root.winfo_exists():
			return
		self._busy = True
		box = {}
		threading.Thread(target=lambda: box.update(r=self._check()), daemon=True).start()

		def wait():
			if "r" not in box:
				self.app.root.after(500, wait)
				return
			self._busy = False
			self.state.update(box["r"])
			self.show()
			self.app.root.after(EVERY, self.check)
		wait()

	def _check(self):
		out = {"checked": time.strftime("%H:%M"), "error": ""}
		out["restart"] = bool(self.exe and self.started and file_key(self.exe) != self.started)
		root = self.app.mod_root
		ok, _ = git(root, "fetch", "-q", "origin")
		if not ok:
			out["error"] = "couldn't reach GitHub"
			out["pull"] = self.state.get("pull", [])
			return out
		branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")[1] or "main"
		upstream = f"origin/{branch}" if git(root, "rev-parse", "-q", "--verify", f"origin/{branch}")[0] else "origin/main"
		pull = []
		for name, rel in EXES:
			ok, n = git(root, "rev-list", "--count", f"HEAD..{upstream}", "--", rel)
			if ok and n.isdigit() and int(n) > 0:
				pull.append(name)
		out["pull"] = pull
		return out

	def outdated(self):
		return bool(self.state["restart"] or self.state["pull"])

	def summary(self):
		"""(ok, title, detail) for Live Sync setup and the explanation window."""
		s = self.state
		if not self.frozen:
			return True, "Running from source", "Not the packaged exe: no build check."
		if s["pull"]:
			return False, "A newer build is on GitHub", (", ".join(s["pull"]) + (" has" if len(s["pull"]) == 1 else " have") +
														 " been updated. Pull the RR repository (GitHub Desktop: Fetch origin, then Pull), then restart "
														 "Organisation Master.")
		if s["restart"]:
			return False, "A newer build is on this PC", "OrganisationMaster.exe changed after this window opened (pulled or rebuilt): restart to use it."
		if s["checked"] is None:
			return True, "Build check: not run yet", "It runs about 20 seconds after start, then every 10 minutes."
		return True, "Your build is up to date", f"checked at {s['checked']}" + (f" ({s['error']}: checked this PC only)" if s["error"] else "")

	def show(self):
		if self.banner is None or not self.banner.winfo_exists():
			return
		root = self.app.root
		base = root.title().split("  ·  ⚠")[0]
		if self.outdated():
			self.banner.config(text="⚠ Pull the update" if self.state["pull"] else "⚠ Restart to update")
			self.banner.pack(side="right")
			self.banner.config(foreground="#ff9a2e")
			root.title(base + "  ·  ⚠ update available")
		else:
			self.banner.pack_forget()
			root.title(base)

	def explain(self):
		ok, title, detail = self.summary()
		w = tk.Toplevel(self.app.root)
		w.title("Update")
		w.transient(self.app.root)
		w.resizable(False, False)
		f = ttk.Frame(w, padding=14)
		f.pack()
		ttk.Label(f, text=("✔ " if ok else "⚠ ") + title, style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text=detail, wraplength=420, justify="left").pack(anchor="w", pady=(6, 0))
		ttk.Label(f, text="An old build can miss fixes the others rely on (Live Sync, the in-game To Do list), so update soon.",
				  style="Muted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(8, 0))
		bb = ttk.Frame(f)
		bb.pack(fill="x", pady=(12, 0))
		if self.state["restart"] and not self.state["pull"]:
			ttk.Button(bb, text="↻ Restart now", command=lambda: (w.destroy(), self.restart())).pack(side="left")
		ttk.Button(bb, text="Check again", command=lambda: (w.destroy(), self.check())).pack(side="left", padx=6)
		ttk.Button(bb, text="Close", command=w.destroy).pack(side="right")

	def restart(self):
		if not self.exe:
			return
		if not messagebox.askyesno(APP_NAME, "Restart Organisation Master with the new build?\n\nYour work is saved as you go; "
											 "anything still being typed is saved first.", parent=self.app.root):
			return
		try:
			import run_copy
			subprocess.Popen([self.exe], cwd=os.path.dirname(self.exe), close_fds=True, env=run_copy.clean_env())
		except OSError as ex:
			messagebox.showerror(APP_NAME, f"Can't start the new build:\n{ex}", parent=self.app.root)
			return
		self.app.quit()
