"""To Do Master > 🔄 Live Sync...: checks every step of the live To Do (todo_sync.py) on this PC, says what's wrong in
plain words and offers the fix: Git installed, sync.json there, a git name, GitHub access to the To Do's repository
(signed in? added to it?), the local copy, and whether it's syncing now."""
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox, simpledialog

import todo_sync
import ui

APP_NAME = "Organisation Master"
GIT_DOWNLOAD = "https://git-scm.com/download/win"
OK, BAD, WARN, WAIT = "✔", "✖", "⚠", "…"
COLOURS = {OK: "#2e9d4a", BAD: "#d03c3c", WARN: "#d08a1e", WAIT: "#888888"}


def run(args, cwd=None, timeout=40, prompt=False):
	"""(ok, stdout, stderr) of a command; no console window; no password prompt unless prompt."""
	env = dict(os.environ)
	if not prompt:
		env["GIT_TERMINAL_PROMPT"] = "0"
	try:
		r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
						   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
	except subprocess.TimeoutExpired:
		return False, "", "timed out"
	except OSError as ex:
		return False, "", str(ex)


def repo_page(url):
	"""https://github.com/Org/Repo.git -> https://github.com/Org/Repo"""
	return url[:-4] if url.endswith(".git") else url


def access_problem(err):
	"""What a failed 'git ls-remote' means: 'signin', 'noaccess', 'offline' or 'other'."""
	e = err.lower()
	if any(w in e for w in ("could not resolve host", "timed out", "failed to connect", "connection was reset", "network is unreachable")):
		return "offline"
	if any(w in e for w in ("authentication failed", "could not read username", "terminal prompts disabled", "logon failed",
							"invalid username or password", "credential")):
		return "signin"
	if any(w in e for w in ("repository not found", "not found", "403", "permission", "denied", "access")):
		return "noaccess"
	return "other"


class SyncSetup(tk.Toplevel):
	def __init__(self, page):
		super().__init__(page.winfo_toplevel())
		self.page, self.app = page, page.app
		self.title("Live Sync setup")
		self.transient(page.winfo_toplevel())
		self.resizable(False, False)
		self.minsize(ui.px(720), 1)
		f = ttk.Frame(self, padding=14)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="🔄 Live Sync setup", style="Title.TLabel").pack(anchor="w")
		ttk.Label(f, text="Live Sync keeps everyone's To Do (tasks, ideas, Dev VC notes) the same without anyone committing or "
						  "pushing: it lives in its own GitHub repository, so the RR repository and the Discord tracker never see it. "
						  "This checks each step on your PC; fix the first ✖ and press Check again.",
				  style="Muted.TLabel", wraplength=ui.px(700), justify="left").pack(anchor="w", pady=(4, 10))
		self.rows = ttk.Frame(f)
		self.rows.pack(fill="x")
		self.summary = ttk.Label(f, text="", style="Head.TLabel", wraplength=ui.px(700), justify="left")
		self.summary.pack(anchor="w", pady=(10, 0))
		bb = ttk.Frame(f)
		bb.pack(fill="x", pady=(10, 0))
		self.again = ttk.Button(bb, text="↻ Check again", command=self.check)
		self.again.pack(side="left")
		ttk.Button(bb, text="📋 Copy a report (for Mike)", command=self.copy_report).pack(side="left", padx=6)
		ttk.Button(bb, text="Close", command=self.destroy).pack(side="right")
		self.results = []
		self.geometry(f"+{page.winfo_rootx() + 160}+{page.winfo_rooty() + 60}")
		self.check()

	# ---------- the checks (a thread: git can take a few seconds) ----------
	def check(self):
		self.again.state(["disabled"])
		self.show([(WAIT, "Checking...", "Git, the sync setting, GitHub access and your local copy.", [])])
		self.summary.config(text="")
		box = {}
		threading.Thread(target=lambda: box.update(r=self.checks()), daemon=True).start()
		self._wait(box)

	def _wait(self, box):
		if not self.winfo_exists():
			return
		if "r" not in box:
			self.after(200, lambda: self._wait(box))
			return
		self.again.state(["!disabled"])
		self.results = box["r"]
		self.show(self.results)

	def checks(self):
		out = []
		page, sync = self.page, self.page.sync
		# 1. Git
		ok, ver, err = run(["git", "--version"], timeout=15)
		if not ok:
			out.append((BAD, "Git isn't installed", "Live Sync uses Git. Install Git for Windows (keep the default options: they include "
														  "the GitHub sign-in window), then restart Organisation Master.",
						[("Download Git", lambda: webbrowser.open(GIT_DOWNLOAD))]))
			return out
		out.append((OK, "Git is installed", ver, []))
		# 1b. this build (an old one can miss fixes Live Sync relies on)
		uc = getattr(page.app, "update_check", None)
		if uc is not None:
			ok_b, title, detail = uc.summary()
			out.append((OK if ok_b else WARN, title, detail, [] if ok_b else [("What to do...", uc.explain)]))
		# 2. sync.json
		cfg = todo_sync.settings(self.tool_dir())
		remote = (cfg.get("remote") or sync.remote or "").strip()
		if not remote:
			out.append((BAD, "No To Do repository set (sync.json)", "sync.json (next to OrganisationMaster.exe) says which repository the "
							"To Do lives in, and it comes with the RR repository. Pull the latest RR (GitHub Desktop: Fetch origin, then "
							"Pull), then restart Organisation Master.", [("Open the tool's folder", lambda: os.startfile(self.tool_dir()))]))
			return out
		out.append((OK, "The To Do's repository is set", repo_page(remote), [("Open it on GitHub", lambda: webbrowser.open(repo_page(remote)))]))
		# 3. who you are
		g, match = page.git_match()
		if not g:
			out.append((WARN, "No git name", "Your git name tells the tool which dev you are. GitHub Desktop: File > Options > Git; or set it here.",
						[("Set my git name...", self.set_git_name)]))
		elif not match:
			out.append((WARN, f"Your git name ({g}) isn't in the Dev list", "Pick which dev you are (or add yourself) so your changes carry your name.",
						[("Who am I?...", page.confirm_me)]))
		else:
			out.append((OK, f"You are {match}", f"git name {g}", []))
		# 4. GitHub access
		ok, heads, err = run(["git", "ls-remote", "--heads", remote], timeout=40)
		if not ok:
			why = access_problem(err)
			text = {"signin": ("Not signed in to GitHub", "Git couldn't log in to GitHub. Press Sign in: a small window opens and a "
														  "GitHub sign-in page with it - sign in with the GitHub account that was added to the "
														  "To Do repository."),
					"noaccess": ("No access to the To Do repository", "GitHub says the repository isn't there for you: either your GitHub "
										"account hasn't been added to it yet (ask Mike: Copy a request), or you're signed in with another "
										"account (Sign out, then Sign in with the right one)."),
					"offline": ("Can't reach GitHub", "No connection to github.com. Check your internet; your changes are kept and sent when it's back."),
					"other": ("GitHub said no", err[-300:] or "an unknown problem")}[why]
			actions = {"signin": [("Sign in to GitHub", lambda: self.sign_in(remote))],
					   "noaccess": [("Copy a request for Mike", lambda: self.copy_request(remote)), ("Sign out", self.sign_out),
									("Sign in to GitHub", lambda: self.sign_in(remote))],
					   "offline": [], "other": [("Sign in to GitHub", lambda: self.sign_in(remote)), ("Copy a request for Mike", lambda: self.copy_request(remote))]}[why]
			out.append((BAD, text[0], text[1], actions))
			return out
		out.append((OK, "You have access to the To Do repository", "signed in to GitHub" + ("" if heads else " (it's empty: the first PC to open the To Do fills it)"), []))
		# 5. the local copy
		clone = todo_sync.CLONE
		if not os.path.isdir(os.path.join(clone, ".git")):
			out.append((WARN, "No local copy yet", f"It's made the first time the To Do syncs ({clone}). Press Sync now.",
						[("Sync now", self.sync_now)]))
		else:
			url = run(["git", "-C", clone, "remote", "get-url", "origin"], timeout=15)[1]
			if url != remote:
				out.append((BAD, "The local copy points somewhere else", f"It's linked to {url or '?'}, not {remote}. Repair makes a fresh copy "
								"(your changes in the To Do are kept and merged in).", [("Repair", self.repair)]))
			elif not os.path.exists(os.path.join(clone, todo_sync.FILE)) and heads:
				out.append((BAD, "The local copy is broken", "The To Do file is missing from it. Repair makes a fresh copy (your changes are kept).",
							[("Repair", self.repair)]))
			else:
				ahead = run(["git", "-C", clone, "rev-list", "--count", f"origin/{todo_sync.BRANCH}..HEAD"], timeout=15)[1]
				extra = f"{ahead} change{'s' if ahead != '1' else ''} not sent yet" if ahead not in ("", "0") else "nothing waiting to be sent"
				out.append((OK, "The local copy is fine", f"{clone}  ·  {extra}", [("Open the folder", lambda: os.startfile(clone))]))
		# 6. syncing now
		state = page.sync_label.cget("text") if hasattr(page, "sync_label") else ""
		if not sync.on:
			out.append((WARN, "Live Sync is off in this window", "It was started without a repository: restart Organisation Master to switch it on.", []))
		elif state.startswith("●"):
			out.append((OK, "Syncing", state, [("Sync now", self.sync_now)]))
		else:
			out.append((WARN, "Not synced yet", state or "waiting for the first sync", [("Sync now", self.sync_now)]))
		return out

	def tool_dir(self):
		return sys.modules[type(self.page).__module__].TOOL_DIR  # (where OrganisationMaster.exe and sync.json are)

	# ---------- showing them ----------
	def show(self, results):
		for w in self.rows.winfo_children():
			w.destroy()
		for r, (mark, title, detail, actions) in enumerate(results):
			tk.Label(self.rows, text=mark, fg=COLOURS[mark], font=("Segoe UI", 16, "bold"), width=2).grid(row=r, column=0, sticky="n", pady=(2, 6))
			box = ttk.Frame(self.rows)
			box.grid(row=r, column=1, sticky="w", pady=(2, 6))
			ttk.Label(box, text=title, style="Head.TLabel").pack(anchor="w")
			ttk.Label(box, text=detail, style="Muted.TLabel", wraplength=ui.px(470), justify="left").pack(anchor="w")
			bf = ttk.Frame(self.rows)
			bf.grid(row=r, column=2, sticky="ne", padx=(10, 0), pady=(2, 6))
			for text, fn in actions:
				ttk.Button(bf, text=text, style="Tool.TButton", command=fn).pack(fill="x", pady=(0, 2))
		self.rows.columnconfigure(1, weight=1)
		marks = [m for m, *_ in results]
		if WAIT in marks:
			self.summary.config(text="")
		elif BAD in marks:
			self.summary.config(text="✖ Not working yet: fix the first ✖ above, then Check again.", foreground=COLOURS[BAD])
		elif WARN in marks:
			self.summary.config(text="⚠ Nearly there: see the ⚠ above.", foreground=COLOURS[WARN])
		else:
			self.summary.config(text="✔ All good: your To Do is live.", foreground=COLOURS[OK])

	def copy_report(self):
		"""Every check as text, to paste to whoever helps (Discord)."""
		g, match = self.page.git_match()
		lines = [f"Live Sync check for {match or g} ({time.strftime('%Y-%m-%d %H:%M')}):"]
		lines += [f"{mark} {title}: {detail}" for mark, title, detail, _ in self.results]
		self.clipboard_clear()
		self.clipboard_append("\n".join(lines))
		self.summary.config(text="📋 Report copied: paste it to Mike on Discord.", foreground=COLOURS[OK])

	# ---------- fixes ----------
	def sign_in(self, remote):
		"""A small console window running git against the repository: the GitHub sign-in window comes up with it."""
		if not messagebox.askokcancel(APP_NAME, "A small black window opens and, with it, a GitHub sign-in window (or page in your browser).\n\n"
												"Sign in with the GitHub account that was added to the To Do repository, then press a key in the "
												"black window to close it.", parent=self):
			return
		cmd = (f'title GitHub sign-in for the RR To Do & echo Signing in to GitHub for the RR To Do... & echo. & '
			   f'git ls-remote --heads "{remote}" >nul && (echo. & echo Done: you have access. You can close this window.) '
			   f'|| (echo. & echo Still no access - see the Live Sync window in Organisation Master.) & echo. & pause')
		# One command-line string, not a list: from a list Python escapes the quotes around the URL as \",
		# cmd passes them on and git gets '"https://...' ("protocol '"https' is not supported"). # Globus
		# The sign-in has to be allowed to ask: drop anything inherited that turns git's or the credential
		# manager's prompts off, or the GitHub window never appears. # Globus
		env = dict(os.environ)
		for k in ("GIT_TERMINAL_PROMPT", "GCM_INTERACTIVE", "GIT_ASKPASS", "SSH_ASKPASS"):
			env.pop(k, None)
		p = subprocess.Popen("cmd /c " + cmd, env=env, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
		self.summary.config(text="Waiting for the sign-in window to close...", foreground=COLOURS[WAIT])

		def wait():
			if not self.winfo_exists():
				return
			if p.poll() is None:
				self.after(500, wait)
			else:
				self.check()
		wait()

	def sign_out(self):
		if not messagebox.askyesno(APP_NAME, "Forget the GitHub login saved on this PC?\n\nDo this if you're signed in with the wrong GitHub "
											 "account; then press Sign in and use the account that was added to the To Do repository. "
											 "(GitHub Desktop has its own login and isn't affected.)", parent=self):
			return
		try:
			subprocess.run(["git", "credential", "reject"], input="protocol=https\nhost=github.com\n\n", text=True, timeout=20,
						   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		except (OSError, subprocess.SubprocessError):
			pass
		self.check()

	def copy_request(self, remote):
		g, match = self.page.git_match()
		text = (f"Hi Mike, could you add my GitHub account to the RR To Do repository ({repo_page(remote)}) for Live Sync? "
				f"I'm {match or g} (git name {g}). My GitHub username is: ")
		self.clipboard_clear()
		self.clipboard_append(text)
		messagebox.showinfo(APP_NAME, "Copied. Paste it to Mike (Discord) and add your GitHub username at the end.\n\n"
									  "When you've been added, GitHub emails you an invitation: accept it, then press Check again.", parent=self)

	def set_git_name(self):
		n = (simpledialog.askstring("Git name", "Your git name (the name your commits show; usually your GitHub name):", parent=self) or "").strip()
		if n:
			run(["git", "config", "--global", "user.name", n], timeout=15)
			self.check()

	def sync_now(self):
		self.page.sync.soon(100)
		self.summary.config(text="Syncing... (Check again in a few seconds)", foreground=COLOURS[WAIT])
		self.after(6000, self.check)

	def repair(self):
		"""A fresh local copy: the old one is kept beside it (renamed); what's on screen is merged into the new one."""
		if not messagebox.askyesno(APP_NAME, "Make a fresh local copy of the To Do?\n\nThe old copy is kept (renamed) beside it, and the To Do "
											 "as it is on your screen is merged into the new one, so nothing of yours is lost.", parent=self):
			return
		sync, clone = self.page.sync, todo_sync.CLONE
		try:
			if os.path.isdir(clone):
				shutil.move(clone, clone + time.strftime("_old_%Y%m%d-%H%M%S"))
		except OSError as ex:
			messagebox.showerror(APP_NAME, f"Can't move the old copy (close anything using it):\n{ex}", parent=self)
			return
		sync.seed = "{}"  # (no common past: everything on both sides is kept, a clash goes to the newer change)
		sync.ready = False
		self.sync_now()
