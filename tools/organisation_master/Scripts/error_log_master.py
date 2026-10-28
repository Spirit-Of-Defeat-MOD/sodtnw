"""🐞 Error Log Master (the side bar, between To Do Master and Music Master): a pop-out that makes the game's error logs
usable, and finds the errors that never get there.

📜 From the game's logs: logs/error.log (and text.log) of the last launch, read again by itself whenever the game writes
them. Errors are grouped by kind (the part of the game that complained; all the token ones - and the "N errors." total
they add up to - are under Tokens) and by message pattern (2,000 "Token X is a dynamic token" lines are one row: X
varies). 🆕 = new since the run before. 🙈 Hide errors like this hides a pattern for everyone (todo_tasks.json error_noise).
🌐 Localisation: everything about the text - the game's duplicate keys (text.log, with both texts), the mod check's
localisation-file problems and missing text, and a spell check of the English text. 🙈 Dismiss hides one for everyone
(todo_tasks.json error_dismissed).
🔎 Not in the log: Scripts/mod_lint.py checks the mod's files (braces, events never written, undefined GFX_ sprites);
the last check is kept, 🆕 since the one before.
Clicking one shows it all at the bottom with 💡 what it means and how to fix it (Scripts/error_fixes.py), and:
🔧 Fix it for the easy ones (missing synchronized tokens, a duplicate loc key with the same text, a missing BOM, a
misspelling; the file is backed up first), 📄 Open the file at its line (VS Code when it's there), ➕ a To Do task (Bug)
for whoever last changed that file (git), once per error (link errorlog:<id>).
The bottom right shows the code itself: the lines around each place the error points at (the file and line it names,
where a token is used, every definition of a duplicate idea, each copy of a loc key - 🎮 the game's from the game's
folder), the line and the name highlighted in the theme's colours.
✅ Recently fixed: what got fixed (by 🔧 here, or found fixed in the files since the log was written: a log's token / duplicate
idea errors), by whom, when, in which files - shared (todo_tasks.json error_fixed, kept 30 days); ✓ Checked clears it
for you (config error_fixed_seen) - the others still see it until they check. A fixed error leaves the lists.
Personal: %LOCALAPPDATA%\\OrganisationMaster\\error_log_seen.json (what the last runs had), mod_lint.json (the last check)."""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import tkinter as tk
from collections import defaultdict
from tkinter import messagebox, ttk

import error_fixes as fx
import ui
from notebook_theme import theme_notebook

FIXED_DAYS = 30  # (✅ Recently fixed keeps a fix this long for whoever hasn't checked)

HOME = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "OrganisationMaster")
SEEN = os.path.join(HOME, "error_log_seen.json")
LINT_CACHE = os.path.join(HOME, "mod_lint.json")
LOGS = ("error.log", "text.log")
EXTRA_LOGS = ("game.log", "setup.log", "graphics.log")  # (mostly chatter: only their lines that sound like a problem)
EXTRA_KEEP = re.compile(r"\b(?:error|invalid|missing|failed|failure|could not|couldn't|cannot|can't|not found|unknown|corrupt)\b", re.I)
SEV_ORDER = {"🔴": 0, "🟠": 1, "🟡": 2}
SEV_PICK = ("All", "🔴 Breaks things", "🔴🟠 Breaks + wrong in game")
REASONS = ("Intentional", "Base-game leftover", "Harmless", "Will fix later")
LINE = re.compile(r"\[(\d\d:\d\d:\d\d)\]\[([^\]]*)\]\[([^\]:]+)(?::\d+)?\]: (.*)")
DIRS = r"(?:common|events|history|interface|gfx|localisation|map|music|sound|portraits|mod)"
EXT = r"(?:txt|gui|gfx|yml|csv|dds|tga|png|asset|mod|lua)"
FILE_REFS = (  # ((file, line) in the message: the most precise kind first)
	re.compile(r'near line: (\d+)"\s+in file: "([^"]+)"'),  # (the line inside the quotes is where it really is)
	re.compile(r'in file: "([^"]+)"\s+near line: (\d+)'),
	re.compile(r"\b(" + DIRS + r"/[^:\n\"()]+?\." + EXT + r"):(\d+)"),  # common/decisions/TEU.txt:2108
	re.compile(r"\bin (" + DIRS + r"/[^\n\"]+?\." + EXT + r")\s+line\s*:\s*(\d+)"),  # in history/countries/BEL - Belgium.txt line : 3
	re.compile(r"\bfile:\s*\"?([^\"\n]+?\." + EXT + r")\"?(?:.{0,20}?\bline:\s*(\d+))?", re.I),
	re.compile(r"\b(" + DIRS + r"/[\w./\- ]+?\." + EXT + r")(?:\D{0,12}(\d+))?"),
)
PATH = re.compile(r'"(?:[^"]*/)?[^"/]+\.' + EXT + r'"|\b' + DIRS + r"/[^:\n\"()]+?\." + EXT + r"\b")
TOKENS = "Tokens (dynamic / missing)"
LOC = "Localisation"
KINDS = {"scopedvariable.cpp": TOKENS, "lexer.cpp": TOKENS, "gameitemdatabase.h": TOKENS,  # ("1110 errors." is the tokens' total)
		 "idea_database.cpp": "Duplicate ideas", "localize.cpp": LOC, "persistent.cpp": "Script errors (bad keys / values)",
		 "effectimplementation.cpp": "Effects", "triggerimplementation.cpp": "Triggers", "eventmanager.cpp": "Events",
		 "gameapplication.cpp": "The game", "spritetype.cpp": "GFX / sprites", "texturehandler.cpp": "GFX / sprites",
		 "gfx_dx11.cpp": "GFX / sprites", "focus.cpp": "National focuses", "decisions.cpp": "Decisions", "ideas.cpp": "Ideas",
		 "character.cpp": "Characters", "countryhistory.cpp": "Country history", "statehistory.cpp": "State history",
		 "parser.cpp": "Script errors (bad keys / values)", "effect.cpp": "Effects", "trigger.cpp": "Triggers",
		 "nationalfocus.cpp": "National focuses", "dlc.cpp": "Mod files (.mod) - other mods", "equipment_graphic_database.cpp":
		 "Equipment graphics / 3D models", "database_scoped_variables.cpp": "Unknown names (doctrines, techs...)",
		 "bookmark.cpp": "Bookmarks", "technology.cpp": "Technologies", "unit.cpp": "Units", "oob.cpp": "Units / OOBs",
		 "map.cpp": "Map", "province.cpp": "Map", "state.cpp": "States", "strategicregion.cpp": "Map", "ai.cpp": "AI",
		 "pdx_audiomusic_sdl.cpp": "Music / sound", "musicmanager.cpp": "Music / sound", "pdx_entity.cpp": "Equipment graphics / 3D models",
		 "technologytemplate.cpp": "Technologies", "faction_template.cpp": "Factions", "cultural_formatter.cpp": "Localisation",
		 "flagtextureatlas.cpp": "Flags", "international_market_effect_implementation.cpp": "Market / trade",
		 "provincegraphics.cpp": "Map (unit positions)"}


def last_run_mods(mod_root):
	"""(the mods the last launch had enabled - names -, whether RR was one of them) from the launcher's dlc_load.json, or
	(None, True) when it can't tell."""
	base = os.path.normpath(os.path.join(mod_root, "..", ".."))
	try:
		with open(os.path.join(base, "dlc_load.json"), encoding="utf-8") as f:
			enabled = json.load(f).get("enabled_mods") or []
	except (OSError, ValueError):
		return None, True
	names, ours = [], False
	for m in enabled:
		try:
			text = open(os.path.join(base, m), encoding="utf-8", errors="replace").read()
		except OSError:
			names.append(m)
			continue
		name = (re.search(r'^name\s*=\s*"([^"]*)"', text, re.M) or [None, m])[1]
		path = (re.search(r'^path\s*=\s*"([^"]*)"', text, re.M) or [None, ""])[1]
		names.append(name)
		ours |= bool(path) and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(mod_root))
	return names, ours
LOC_CHECKS = ("Localisation files", "Localisation keys defined twice", "Missing localisation", "Spelling")
DUPE = re.compile(r"Duplicate localization found, key: (.+?), file: (.+?), value: (.*)$")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log_dir(mod_root):
	return os.path.normpath(os.path.join(mod_root, "..", "..", "logs"))


def file_ref(msg):
	"""(file, line) the message points at, or (None, None)."""
	for n, rx in enumerate(FILE_REFS):
		m = rx.search(msg)
		if m:
			f, line = (m.group(2), m.group(1)) if n == 0 else (m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
			return f.replace("\\", "/").strip(), int(line) if line else None
	return None, None


def parse(text, name):
	"""[row] of a log's text: {log, time, date, src, kind, msg, file, line}. A message that runs over several lines (the
	game does that for some) is kept whole."""
	rows, last = [], None
	for line in text.splitlines():
		m = LINE.match(line)
		if not m:
			if last is not None and line.strip():
				last["msg"] += " / " + line.strip()  # (the rest of the line before)
				if not last["file"]:
					last["file"], last["line"] = file_ref(last["msg"])
			continue
		src, msg = m.group(3), m.group(4).strip()
		last = None
		if name == "text.log" and "localiz" not in src and "Duplicate" not in msg:
			continue  # (text.log: only its localisation complaints)
		if name in EXTRA_LOGS and not EXTRA_KEEP.search(msg):
			continue  # (game.log / setup.log / graphics.log: only what sounds like a problem)
		if not msg.strip("= "):
			continue  # (===== under the error total: a separator)
		f, ln = file_ref(msg)
		last = dict(log=name, time=m.group(1), date=m.group(2), src=src, kind=KINDS.get(src, src.rsplit(".", 1)[0]),
					msg=msg, file=f, line=ln)
		rows.append(last)
	return rows


def read_logs(mod_root, files=None):
	"""[row] of the logs (the game's, or the files given: 📂 Open a log); and the newest log's time."""
	rows, newest = [], 0
	for path in files or [os.path.join(log_dir(mod_root), n) for n in LOGS + EXTRA_LOGS]:
		try:
			newest = max(newest, os.path.getmtime(path))
			with open(path, encoding="utf-8", errors="replace") as f:
				text = f.read()
		except OSError:
			continue
		rows += parse(text, os.path.basename(path) if os.path.basename(path) in LOGS + EXTRA_LOGS else "error.log")
	return rows, newest


NAME_RUNS = ((re.compile(r"(No combat between states ).+$"), r"\1…"),
			 (re.compile(r"(add_\w+ ).+?( does not have resistance)"), r"\1…\2"),
			 (re.compile(r"(\w+ - Invalid icon ')[^']*'"), r"\1…'"))


def patterns(rows):
	"""{(kind, pattern): [rows]}: messages of one source with the same words except some (names, numbers) are one pattern."""
	buckets = defaultdict(list)
	for r in rows:
		text = re.sub(r",?\s*value:.*$", "", r["msg"]) if "Duplicate localization" in r["msg"] else r["msg"]  # (a loc key's text: not part of the error)
		text = PATH.sub("‹file›", text)  # (the same error in another file is the same error)
		for rx, keep in NAME_RUNS:  # (names of any length - states, songs: one error however many words they have)
			text = rx.sub(keep, text)
		text = re.sub(r"\d+", "#", text)
		words = text.split(" ")
		# (Error: "Unexpected token: ..." and Error: "Malformed token: ..." aren't one error: their first words count)
		head = re.sub(r'^Error:\s*"?', "", text).split(" ")[:2] if text.startswith("Error:") else []
		head = head[:1] if len(head) > 1 and re.search(r"[_\d#'.]", head[1]) else head
		symbols = tuple(w for w in words if not re.sub(r"[\W_#]", "", w))  # ('//', ',,', '=': a different mistake, its own row)
		buckets[(r["src"], len(words), words[0], " ".join(head), symbols)].append((r, words))
	out = defaultdict(list)
	for (src, n, *_), items in buckets.items():
		varies = set()
		if len(items) > 1:
			first = items[0][1]
			for _, words in items[1:]:
				varies |= {i for i in range(n) if words[i] != first[i]}
		for r, words in items:
			pattern = " ".join("…" if i in varies else w for i, w in enumerate(words))
			pattern = re.sub(r"\d+", "#", pattern) if not varies and len(items) > 1 else pattern
			out[(r["kind"], pattern)].append(r)
	return out


def dupes(rows):
	"""{key: [(file, value)]} of text.log's duplicate loc keys."""
	out = defaultdict(list)
	for r in rows:
		m = DUPE.search(r["msg"])
		if m:
			pair = (m.group(2).strip().replace("\\", "/"), m.group(3))
			if pair not in out[m.group(1).strip()]:
				out[m.group(1).strip()].append(pair)
	return out


def sig(*parts):
	return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]


def load(path, default):
	try:
		with open(path, encoding="utf-8") as f:
			return json.load(f)
	except (OSError, ValueError):
		return default


def store(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False)


def open_file(mod_root, rel, line=None):
	path = os.path.join(mod_root, rel)
	if not os.path.isfile(path):
		return False
	code = shutil.which("code")
	if code:
		subprocess.Popen([code, "-g", f"{path}:{line or 1}"], creationflags=NO_WINDOW)
	else:
		os.startfile(path)
	return True


def last_changer(mod_root, rel):
	"""Who last changed the file (git), or ""."""
	try:
		out = subprocess.run(["git", "-C", mod_root, "log", "-1", "--format=%an", "--", rel], capture_output=True, text=True, timeout=15,
							 creationflags=NO_WINDOW)
		return out.stdout.strip()
	except (OSError, subprocess.SubprocessError):
		return ""


_AUTHORS = {}


def authors(mod_root):
	"""{file: who last changed it} from one git log (cached for the session): for 👤 Only mine and 📬."""
	if mod_root not in _AUTHORS:
		out = {}
		try:
			log = subprocess.run(["git", "-C", mod_root, "log", "-n", "4000", "--name-only", "--format=%x00%an"], capture_output=True,
								 text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW).stdout
		except (OSError, subprocess.SubprocessError):
			log = ""
		who = ""
		for line in log.splitlines():
			if line.startswith("\x00"):
				who = line[1:]
			elif line.strip() and who:
				out.setdefault(line.strip(), who)
		_AUTHORS[mod_root] = out
	return _AUTHORS[mod_root]


def my_files(mod_root, todo):
	"""The files the dev using this PC changed last (git name or dev name)."""
	me = todo.me.get()
	dev = next((d for d in todo.data.get("devs", []) if d["name"] == me), {})
	names = {me.casefold(), (dev.get("git") or "").casefold()} - {""}
	return {f for f, a in authors(mod_root).items() if a.casefold() in names}


# ---------- 🐞 the side bar's badge: errors in the files you've just changed ----------
QUICK_EXT = (".txt", ".gui", ".gfx", ".yml")


def quick_check(mod_root, rel_path):
	"""The fast checks on one file (as it's saved): braces, // comments, a loc file's BOM / header. [problem]."""
	import mod_lint
	path = os.path.join(mod_root, rel_path)
	try:
		raw = open(path, "rb").read()
	except OSError:
		return []
	text = raw.decode("utf-8-sig", errors="replace")
	out = []
	if rel_path.endswith(".yml"):
		if not raw.startswith(b"\xef\xbb\xbf"):
			out.append(dict(check="Localisation files", file=rel_path, line=1, message="No UTF-8 BOM: HOI4 ignores the whole file"))
	else:
		out += mod_lint.braces(path, text, mod_root)
		for n, line in enumerate(text.split("\n"), 1):
			code = re.sub(r'"[^"]*"', "", line).split("#")[0]
			if "//" in code:
				out.append(dict(check="Script errors (bad keys / values)", file=rel_path, line=n, message="Invalid effect '//' - // isn't a comment in HOI4"))
	for p in out:
		p["group"] = "📝 In files you just changed"
		p["key"] = f"quick:{p['file']}:{p['line']}:{p['message']}"
	return out


def start_watch(app):
	"""Every 20 s: the mod's changed files (git status) checked again when they're saved; the side bar button shows how many
	problems they have (🐞 n) and the window lists them first."""
	app.error_quick, seen = [], {}

	def scan():
		try:
			st = subprocess.run(["git", "-C", app.mod_root, "status", "--porcelain", "--", "common", "events", "history", "interface", "localisation"],
								capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=NO_WINDOW).stdout
		except (OSError, subprocess.SubprocessError):
			return None
		files = []
		for line in st.splitlines():
			f = line[3:].split(" -> ")[-1].strip().strip('"')
			if f.endswith(QUICK_EXT) and os.path.isfile(os.path.join(app.mod_root, f)):
				files.append(f)
		found = []
		for f in files:
			m = os.path.getmtime(os.path.join(app.mod_root, f))
			if seen.get(f, (None,))[0] != m:
				seen[f] = (m, quick_check(app.mod_root, f))
			found += seen[f][1]
		return found

	def tick():
		box = {}
		th = threading.Thread(target=lambda: box.update(found=scan()), daemon=True)
		th.start()

		def done():
			if th.is_alive():
				return app.root.after(500, done)
			if box.get("found") is not None:
				app.error_quick = box["found"]
				btn = getattr(app, "error_btn", None)
				if btn is not None and btn.winfo_exists():
					btn.config(text=f"Error Log Master  ↗   🐞 {len(app.error_quick)}" if app.error_quick else "Error Log Master  ↗")
				w = getattr(app, "error_log_window", None)
				if w is not None and w.winfo_exists() and [p["key"] for p in app.error_quick] != getattr(w, "_quick_keys", None):
					w.fill()
			app.root.after(20000, tick)
		done()
	app.root.after(8000, tick)


def ask(parent, title, text, buttons=(("OK", True),), extra=None):
	"""A message box drawn in the theme: the value of the button pressed (None: closed). extra(frame): more widgets."""
	w = tk.Toplevel(parent)
	w.title(title)
	w.transient(parent.winfo_toplevel())
	w.configure(background=ui.P["background"])
	w.resizable(False, False)
	f = ttk.Frame(w, padding=16)
	f.pack(fill="both", expand=True)
	ttk.Label(f, text=title, font="om_bold").pack(anchor="w")
	ttk.Label(f, text=text, wraplength=ui.px(560), justify="left").pack(anchor="w", pady=(6, 0))
	if extra:
		extra(f)
	out = {}
	bf = ttk.Frame(f)
	bf.pack(fill="x", pady=(14, 0))
	for i, (label, value) in enumerate(reversed(buttons)):
		b = ttk.Button(bf, text=label, command=lambda v=value: (out.update(v=v), w.destroy()))
		b.pack(side="right", padx=(6, 0))
		if i == 0:
			b.focus_set()
			w.bind("<Return>", lambda ev, v=value: (out.update(v=v), w.destroy()))
	w.bind("<Escape>", lambda ev: w.destroy())
	w.update_idletasks()
	px, py = parent.winfo_rootx() + parent.winfo_width() // 2, parent.winfo_rooty() + parent.winfo_height() // 3
	w.geometry(f"+{max(0, px - w.winfo_width() // 2)}+{max(0, py - w.winfo_height() // 2)}")
	w.grab_set()
	w.wait_window()
	return out.get("v")


def vanilla_colours():
	"""(background, foreground) for rows that clash with a base-game file, from the theme."""
	mix = getattr(ui, "_mix", None)
	bg = mix(ui.P.get("age_yellow", "#b58900"), ui.P.get("surface", "#ffffff"), 0.72) if mix else "#fff3c4"
	return bg, ui.P.get("foreground", "#000000")


class ErrorLogMaster(tk.Toplevel):
	def __init__(self, app):
		super().__init__(app.root)
		self.app, self.todo, self.root_dir = app, app.todo_page(), app.mod_root
		self._om_nonmodal = True
		self.title("🐞 Error Log Master")
		self.geometry(f"{ui.px(1180)}x{ui.px(800)}")
		self.rows, self.groups, self.problems, self.log_time, self.spell = [], {}, [], 0, []
		self.items = {}  # (tree row -> what it is)
		top = ttk.Frame(self, padding=(10, 8, 10, 0))
		top.pack(fill="x")
		ttk.Label(top, text="🐞 Error Log Master", font="om_title").pack(side="left")
		ttk.Button(top, text="↻ Read the logs again", command=self.back_to_game).pack(side="left", padx=(16, 4))
		ttk.Button(top, text="📂 Open a log...", command=self.open_log).pack(side="left", padx=4)
		self.lint_btn = ttk.Button(top, text="▶ Check the mod's files", command=self.lint)
		self.lint_btn.pack(side="left", padx=4)
		# Filters get their own row, rather than being squeezed beyond the title actions.
		top = ttk.Frame(self,padding=(10,4,10,0))
		top.pack(fill="x")
		self.search = tk.StringVar()
		ttk.Label(top, text="🔍").pack(side="left", padx=(16, 2))
		ttk.Entry(top, textvariable=self.search, width=24).pack(side="left")
		self.only_new = tk.BooleanVar(value=False)
		self.show_hidden = tk.BooleanVar(value=False)
		ttk.Checkbutton(top, text="🆕 Only new", variable=self.only_new, command=self.fill).pack(side="left", padx=(12, 4))
		ttk.Checkbutton(top, text="Show hidden / dismissed", variable=self.show_hidden, command=self.fill).pack(side="left", padx=4)
		self.only_mine = tk.BooleanVar(value=False)
		ttk.Checkbutton(top, text="👤 Only mine", variable=self.only_mine, command=self.fill).pack(side="left", padx=4)
		self.sev_var = tk.StringVar(value=SEV_PICK[0])
		sev = ttk.Combobox(top, textvariable=self.sev_var, values=SEV_PICK, state="readonly", width=24)
		sev.pack(side="left", padx=(8, 0))
		sev.bind("<<ComboboxSelected>>", lambda ev: self.fill())
		self.search.trace_add("write", lambda *_: self.fill())
		ttk.Label(top, text="Spelling:").pack(side="left", padx=(12, 2))
		self.spelling_var = tk.StringVar(value=self.todo.data.get("loc_spelling", "Typos only"))
		box = ttk.Combobox(top, textvariable=self.spelling_var, values=fx.SPELLINGS, state="readonly", width=11)
		box.pack(side="left")
		box.bind("<<ComboboxSelected>>", lambda ev: self.spelling_changed())
		self.status = ttk.Label(self, text="", style="Muted.TLabel", padding=(10, 4))
		self.status.pack(anchor="w")
		# ---- the picked error, in full (a fixed area at the bottom: in a paned window it got squeezed to nothing) ----
		bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
		bottom.pack(side="bottom", fill="x")
		bar = ttk.Frame(bottom)
		bar.pack(fill="x", pady=(6, 4))
		self.fix_btn = ttk.Button(bar, text="🔧 Fix it", command=self.fix, state="disabled")
		self.fix_btn.pack(side="left")
		self.open_btn = ttk.Button(bar, text="📄 Open the file", command=self.open_it, state="disabled")
		self.open_btn.pack(side="left", padx=6)
		self.task_btn = ttk.Button(bar, text="➕ To Do task", command=self.make_task, state="disabled")
		self.task_btn.pack(side="left")
		self.hide_btn = ttk.Button(bar, text="🙈 Hide", command=self.hide, state="disabled")
		self.hide_btn.pack(side="left", padx=6)
		self.claim_btn = ttk.Button(bar, text="✋ Claim", command=self.claim, state="disabled")
		self.claim_btn.pack(side="left")
		self.alert_btn = ttk.Button(bar, text="🚨 Alert a dev...", command=self.alert_dev, state="disabled")
		self.alert_btn.pack(side="left", padx=6)
		split = ttk.PanedWindow(bottom, orient="horizontal")
		split.pack(fill="x")
		box = ttk.Frame(split)
		split.add(box, weight=1)
		self.detail = tk.Text(box, height=15, wrap="word", font="om_small", relief="flat", padx=8, pady=6, width=60,
							  background=ui.P.get("input_background", "#ffffff"), foreground=ui.P.get("foreground", "#000000"))
		ys = ttk.Scrollbar(box, command=self.detail.yview)
		self.detail.configure(yscrollcommand=ys.set)
		ys.pack(side="right", fill="y")
		self.detail.pack(side="left", fill="both", expand=True)
		cbox = ttk.Frame(split)  # (the code, around the error)
		split.add(cbox, weight=1)
		self.parts_bar = ttk.Frame(cbox)  # (◀ 2 of 4: kale ▶ - an error with several parts: step through them, ← / → too)
		ttk.Button(self.parts_bar, text="◀", width=3, command=lambda: self.step(-1)).pack(side="left")
		self.parts_label = ttk.Label(self.parts_bar, text="", anchor="center", font="om_small_bold")
		self.parts_label.pack(side="left", fill="x", expand=True)
		ttk.Button(self.parts_bar, text="▶", width=3, command=lambda: self.step(1)).pack(side="right")
		self.code = tk.Text(cbox, height=15, wrap="none", relief="flat", padx=6, pady=6, width=60,
							font=("Consolas", max(8, round(9 * ui.scale()))),
							background=ui.P.get("surface", "#ffffff"), foreground=ui.P.get("foreground", "#000000"))
		cy = ttk.Scrollbar(cbox, command=self.code.yview)
		cx = ttk.Scrollbar(cbox, orient="horizontal", command=self.code.xview)
		self.code.configure(yscrollcommand=cy.set, xscrollcommand=cx.set)
		cy.pack(side="right", fill="y")
		cx.pack(side="bottom", fill="x")
		self._code_first = cy
		self.code.pack(side="left", fill="both", expand=True)
		mix = getattr(ui, "_mix", lambda a, b, k: a)
		self.code.tag_configure("where", font="om_small_bold", foreground=ui.P.get("copper", "#1f5fa8"))
		self.code.tag_configure("num", foreground=ui.P.get("muted", "#777777"))
		self.code.tag_configure("hit", background=mix(ui.P.get("age_red", "#c62828"), ui.P.get("surface", "#ffffff"), 0.8))
		self.code.tag_configure("word", foreground=ui.P.get("age_red", "#c62828"), font=("Consolas", max(8, round(9 * ui.scale())), "bold"),
								underline=True)
		self.code.tag_configure("vanilla", background=vanilla_colours()[0])
		self.code.configure(state="disabled")
		self._snap = {}
		self.detail.tag_configure("head", font="om_bold")
		self.detail.tag_configure("title", font="om_bold", spacing3=2)
		self.detail.tag_configure("meta", foreground=ui.P.get("muted", "#777777"), spacing3=4)
		self.detail.tag_configure("sec", font="om_small_bold", spacing1=8, spacing3=3,
								  background=mix(ui.P.get("copper", "#2e6da4"), ui.P.get("input_background", "#ffffff"), 0.85))
		self.detail.tag_configure("body", lmargin1=14, lmargin2=14)
		self.detail.tag_configure("mono", font=("Consolas", max(8, round(8 * ui.scale()))))
		self.detail.tag_configure("stamp", foreground=ui.P.get("muted", "#777777"), font=("Consolas", max(8, round(8 * ui.scale()))))
		self.detail.tag_configure("help", foreground=ui.P.get("copper", "#2e6da4"), lmargin1=14, lmargin2=14)
		self.closed_secs = set(app.config.get("error_detail_closed", []))  # (the detail's folded sections: ▸ 💡, ▸ 📜...)
		self.detail.tag_configure("vanilla", background=vanilla_colours()[0])
		self.detail.configure(state="disabled")
		self.tabs = ttk.Notebook(self,style="ErrorLog.TNotebook")
		self.tabs.pack(fill="both", expand=True, padx=10)
		self.log_tree = self.make_tree(self.tabs)
		self.loc_tree = self.make_tree(self.tabs)
		self.lint_tree = self.make_tree(self.tabs)
		self.outcome_tree = self.make_tree(self.tabs)
		self.tabs.add(self.log_tree.master, text="📜 From the game's logs")
		self.tabs.add(self.loc_tree.master, text="🌐 Localisation")
		self.tabs.add(self.lint_tree.master, text="🔎 Not in the log")
		self.tabs.add(self.outcome_tree.master, text="🤔 Potential Unintentional Outcomes")
		fixed_tab = ttk.Frame(self.tabs)
		fbar = ttk.Frame(fixed_tab)
		fbar.pack(fill="x", pady=(4, 4))
		self.fixed_note = ttk.Label(fbar, text="", style="Muted.TLabel")
		self.fixed_note.pack(side="left")
		ttk.Button(fbar, text="✓ Checked - clear the list (for me)", command=self.checked).pack(side="right")
		self.fixed_tree = ttk.Treeview(fixed_tab, columns=("by", "when", "where"), selectmode="browse")
		for col, text, w in (("#0", "Fixed", 520), ("by", "By", 90), ("when", "When", 120), ("where", "Files", 330)):
			self.fixed_tree.heading(col, text=text)
			self.fixed_tree.column(col, width=ui.px(w), stretch=col in ("#0", "where"))
		self.fixed_tree.pack(fill="both", expand=True)
		self.fixed_tree.bind("<<TreeviewSelect>>", lambda ev: self.show(self.fixed_tree))
		self.fixed_tree.bind("<Double-1>", lambda ev: self.open_it())
		self.tabs.add(fixed_tab, text="✅ Recently fixed")
		self.trend = tk.Canvas(self.tabs, highlightthickness=0, background=ui.P.get("surface", "#ffffff"))
		self.trend.bind("<Configure>", lambda ev: self.draw_trend())
		self.tabs.add(self.trend, text="📈 Trend")
		self.tabs.bind("<<NotebookTabChanged>>", lambda ev: self.show(None))
		self.cur, self.part = None, 0
		self.log_files, self.foreign = None, False  # (📂 another error.log; foreign: not RR's - nothing here can be fixed from it)
		self.bind("<Left>", lambda ev: self.step(-1, key=True))
		self.bind("<Right>", lambda ev: self.step(1, key=True))
		got = load(LINT_CACHE, {})
		self.problems, self.lint_when, self.lint_prev = got.get("problems", []), got.get("when"), set(got.get("prev", []))
		ui.THEME_HOOKS.append(self.retheme)
		self.bind("<Destroy>",self.theme_cleanup,add="+")
		self.retheme()
		self.read()
		self.watch()
		self.protocol("WM_DELETE_WINDOW", self.close)
		threading.Thread(target=lambda: authors(self.root_dir), daemon=True).start()  # (👤 Only mine: ready in a moment)

	def retheme(self):
		if not self.winfo_exists():return
		p=ui.P;mix=ui._mix
		ui.theme_all(self)
		self.configure(background=p["background"])
		theme_notebook(self,"ErrorLog.TNotebook")
		for text,bg in ((self.detail,p["input_background"]),(self.code,p["surface"])):
			text.configure(background=bg,foreground=p["input_foreground"],insertbackground=p["input_foreground"],
				selectbackground=p["selection_background"],selectforeground=p["selection_foreground"])
		self.code.tag_configure("where",foreground=p["copper"])
		self.code.tag_configure("num",foreground=p["muted"])
		self.code.tag_configure("hit",background=mix(p["age_red"],p["surface"],.8))
		self.code.tag_configure("word",foreground=p["age_red"])
		for tag in ("meta","stamp"):self.detail.tag_configure(tag,foreground=p["muted"])
		self.detail.tag_configure("sec",background=mix(p["copper"],p["input_background"],.85))
		self.detail.tag_configure("help",foreground=p["copper"])
		for text in (self.detail,self.code):text.tag_configure("vanilla",background=vanilla_colours()[0])
		for tree in (self.log_tree,self.loc_tree,self.lint_tree,self.outcome_tree,self.fixed_tree):
			tree.tag_configure("new",foreground=p["age_red"])
			tree.tag_configure("hidden",foreground=p["muted"])
			tree.tag_configure("fixable",foreground=p["age_green"])
			bg,fg=vanilla_colours();tree.tag_configure("vanilla",background=bg,foreground=fg)
		self.draw_trend()

	def theme_cleanup(self,event):
		if event.widget is self and self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)

	def make_tree(self, parent):
		f = ttk.Frame(parent)
		t = ttk.Treeview(f, columns=("count", "new", "where"), selectmode="browse")
		t.heading("#0", text="Error")
		t.column("#0", width=ui.px(600))
		for c, text, w in (("count", "×", 60), ("new", "", 40), ("where", "Where", 330)):
			t.heading(c, text=text)
			t.column(c, width=ui.px(w), stretch=c == "where", anchor="e" if c == "count" else "w")
		ys = ttk.Scrollbar(f, command=t.yview)
		t.configure(yscrollcommand=ys.set)
		ys.pack(side="right", fill="y")
		t.pack(fill="both", expand=True)
		t.tag_configure("group", font="om_bold")
		t.tag_configure("new", foreground=ui.P["age_red"])
		t.tag_configure("hidden", foreground=ui.P["muted"])
		t.tag_configure("fixable", foreground=ui.P["age_green"])
		t.tag_configure("vanilla")  # (🎮 clashes with a base-game file: coloured from the theme in fill)
		t.bind("<<TreeviewSelect>>", lambda ev, t=t: self.show(t))
		t.bind("<Double-1>", lambda ev: self.open_it())
		t.bind("<Left>", lambda ev: self.step(-1, key=True))  # (a list's own ← / → open and close groups: only when there are parts)
		t.bind("<Right>", lambda ev: self.step(1, key=True))
		return t

	# ---------- shared lists: hidden patterns, dismissed errors ----------
	def noise(self):
		return self.todo.data.setdefault("error_noise", [])

	def dismissed(self):
		return self.todo.data.setdefault("error_dismissed", {})

	def hidden(self, kind, pattern):
		return any(n.get("kind") == kind and n.get("pattern") == pattern for n in self.noise())

	# ---------- reading ----------
	def open_log(self):
		"""📂 Any error.log (a teammate's, another mod's): read like the game's. Not RR's: read only (its files aren't ours)."""
		from tkinter import filedialog
		path = filedialog.askopenfilename(parent=self, title="📂 Open an error log", filetypes=[("Logs", "*.log *.txt"), ("All files", "*.*")])
		if not path:
			return
		ours = ask(self, "📂 Open a log", f"Is {os.path.basename(path)} from a Revolution Realized game?\n\nIf it's another mod's, "
				   "its files aren't ours: it's shown to read only (no 🔧 fixes, tasks or code - they'd point at RR's files).",
				   (("Another mod's", False), ("Revolution Realized's", True)))
		if ours is None:
			return
		self.log_files, self.foreign = [path], not ours
		self.read()

	def back_to_game(self):
		self.log_files, self.foreign = None, False
		self.read()

	def read(self):
		self.rows, self.log_time = read_logs(self.root_dir, self.log_files)
		if not self.log_files:  # (the game's logs: from whichever mod ran last - read only when it wasn't RR)
			self.run_mods, ours = last_run_mods(self.root_dir)
			self.foreign = not ours
		if self.log_files or self.foreign:  # (a log from elsewhere or another mod's launch: nothing "new since the run before",
			self.groups, self.dupes = patterns(self.rows), dupes(self.rows)  # nothing found fixed - only RR's errors go in the live sync)
			self.before, self.fixed_now = set(), set()
			try:
				self.spell = fx.spelling(self.root_dir, self.todo.data.get("loc_spelling", "Typos only")) if not (self.foreign and self.log_files) else []
			except OSError:
				self.spell = []
			return self.fill()
		self.groups = patterns(self.rows)
		self.dupes = dupes(self.rows)
		try:
			self.spell = fx.spelling(self.root_dir, self.todo.data.get("loc_spelling", "Typos only"))
		except OSError:
			self.spell = []
		seen = load(SEEN, {})
		now = {sig(k, p) for k, p in self.groups}
		if seen.get("time") != self.log_time:  # (a new run: what the last one had is "before"; nothing of it fixed yet)
			seen = {"time": self.log_time, "before": seen.get("now", []), "now": sorted(now), "fixed": []}
			store(SEEN, seen)
			if not self.foreign and self.rows:
				self.record_trend("log", [(fx.severity(k, p), len(r)) for (k, p), r in self.groups.items()])
				present = {self.link_for(("log", k, p, r)) for (k, p), r in self.groups.items()} | \
						  {self.link_for(("dupe", k, v)) for k, v in self.dupes.items()}
				self.complete_gone("log", present, "Gone from the game's error log (a newer launch doesn't have it)")
		self.before = set(seen.get("before", []))
		self.fixed_now = set(seen.get("fixed", []))
		self.fill()
		self.after(30, self.late_fixed)  # (the window shows first; the "already fixed in the files" look follows)

	def late_fixed(self):
		if not self.winfo_exists():
			return
		before = len(self.fixed_now)
		self.find_fixed()
		if len(self.fixed_now) != before:
			self.fill()

	def find_fixed(self):
		"""The log's errors that are fixed in the files since it was written (its tokens all listed, its duplicate ideas
		defined once): they leave the list and go in ✅ Recently fixed."""
		listed = None
		for (kind, pattern), rows in self.groups.items():
			k = sig(kind, pattern)
			if k in self.fixed_now:
				continue
			fix = fx.help_for(kind, pattern)[2]
			done = False
			if fix == "tokens":
				listed = listed if listed is not None else fx.listed_tokens(self.root_dir)
				names = fx.token_names(rows)
				done = bool(names) and all(n in listed for n in names)
			elif fix == "ideas":
				names = fx.idea_names(rows)
				done = bool(names) and all(len(fx.find_defs(self.root_dir, n)) <= 1 for n in names)
			elif fix == "capital":  # (every country's history now names a state it owns)
				cps = [fx.capital_problem(self.root_dir, m, self.game()) for m in dict.fromkeys(r["msg"] for r in rows)]
				done = bool(cps) and all(cp and cp["capital"] in {s_[0] for s_ in cp["owned"]} for cp in cps)
			if done:
				self.mark_fixed(k, f"{pattern}  ({len(rows)} in the log)", [], by="found fixed in the files")
		if listed is not None:  # (the tokens' total goes with them)
			for (kind, pattern), rows in self.groups.items():
				if kind == TOKENS and fx.help_for(kind, pattern)[0].startswith("The token errors' total") and \
						all(sig(k2, p2) in self.fixed_now for (k2, p2) in self.groups if k2 == TOKENS and (k2, p2) != (kind, pattern)):
					self.mark_fixed(sig(kind, pattern), pattern + "  (the token errors' total)", [], by="found fixed in the files")

	# ---------- ✅ Recently fixed ----------
	def fixed_log(self):
		return self.todo.data.setdefault("error_fixed", [])

	def mark_fixed(self, key, title, files, by=None):
		"""key (a log pattern's sig, a problem's key) is fixed: off the lists, into ✅ Recently fixed (once per log run)."""
		if key in self.fixed_now:
			return
		self.fixed_now.add(key)
		seen = load(SEEN, {})
		if seen.get("time") == self.log_time:
			seen["fixed"] = sorted(set(seen.get("fixed", [])) | {key})
			store(SEEN, seen)
		log = self.fixed_log()
		eid = sig(key, str(self.log_time))
		if any(e.get("id") == eid for e in log):
			return
		now = datetime.datetime.now().replace(microsecond=0).isoformat()
		log.append({"id": eid, "what": title, "files": list(files), "by": by or self.todo.me.get(), "when": now})
		links = {"errorlog:" + key, "errorlog:" + sig(key)} | ({"errorlog:" + sig("dupe", key[5:])} if key.startswith("dupe:") else set())
		self.complete_links(links, f"Fixed ({by or self.todo.me.get()}) - {title[:80]}")
		cut = (datetime.datetime.now() - datetime.timedelta(days=FIXED_DAYS)).isoformat()
		log[:] = [e for e in log if e.get("when", "") >= cut][-300:]
		self.todo.save(feedback=False)

	def unseen_fixes(self):
		seen = self.app.config.get("error_fixed_seen", "")
		return [e for e in self.fixed_log() if e.get("when", "") > seen]

	def checked(self):
		"""✓ Checked: the list cleared for you (the others still see it until they check)."""
		self.app.config["error_fixed_seen"] = datetime.datetime.now().replace(microsecond=0).isoformat()
		self.app.save_config()
		self.fill()

	def watch(self):
		"""The logs read again by themselves when the game writes them (after a launch)."""
		if not self.winfo_exists():
			return
		newest = max((os.path.getmtime(os.path.join(log_dir(self.root_dir), n)) for n in LOGS
					  if os.path.isfile(os.path.join(log_dir(self.root_dir), n))), default=0)
		if newest and newest != self.log_time and not self.log_files:
			self.read()
			self.app.set_status("🐞 Error Log Master: the game wrote new logs - read.")
		self.after(3000, self.watch)

	def lint(self):
		"""▶ The mod's files checked (Scripts/mod_lint.py, ~45 s, in the background)."""
		import mod_lint
		self.lint_btn.state(["disabled"])
		box = {"text": "starting..."}

		def work():
			try:
				from cm_data import find_game
				game = find_game(self.root_dir)
			except Exception:
				game = None
			try:
				box["problems"] = mod_lint.run(self.root_dir, game, lambda t: box.update(text=t))
			except Exception as ex:
				box["error"] = f"{type(ex).__name__}: {ex}"
		th = threading.Thread(target=work, daemon=True)
		th.start()

		def wait():
			if not self.winfo_exists():
				return
			if th.is_alive():
				self.status.config(text="🔎 Checking the mod's files: " + box["text"])
				return self.after(300, wait)
			self.lint_btn.state(["!disabled"])
			if "error" in box:
				return self.status.config(text="🔎 The check failed: " + box["error"])
			self.lint_prev = {p["key"] for p in self.problems}
			self.problems = box["problems"]
			self.record_trend("check", [(fx.severity(p["check"], p["message"]), 1) for p in self.problems])
			self.complete_gone("check", {self.link_for(("lint", p)) for p in self.problems}, "Gone from the mod check (fixed in the files)")
			self.lint_when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
			store(LINT_CACHE, {"when": self.lint_when, "problems": self.problems, "prev": sorted(self.lint_prev)})
			self.fill()
		wait()

	# ---------- the lists ----------
	def match(self, text):
		words = self.search.get().lower().split()
		return all(w in text.lower() for w in words)

	def fill(self):
		self.items = {}
		dis = self.dismissed()
		show_all = self.show_hidden.get()
		mine = my_files(self.root_dir, self.todo) if self.only_mine.get() and self.root_dir in _AUTHORS else None
		# 📜 the logs (localisation is in its own tab)
		t = self.log_tree
		t.delete(*t.get_children())
		by_kind = defaultdict(list)
		for (kind, pattern), rows in self.groups.items():
			if kind == LOC or sig(kind, pattern) in self.fixed_now:  # (fixed: in ✅ Recently fixed)
				continue
			hide = self.hidden(kind, pattern)
			new = sig(kind, pattern) not in self.before and bool(self.before)
			sev = fx.severity(kind, pattern)
			if (hide and not show_all) or (self.only_new.get() and not new) or not self.sev_ok(sev):
				continue
			if mine is not None and not any(r["file"] in mine for r in rows):
				continue
			if not self.match(pattern + " " + kind + " " + " ".join(r["file"] or "" for r in rows[:50])):
				continue
			by_kind[kind].append((pattern, rows, new, hide, sev))
		shown = 0
		worst = lambda es: min(SEV_ORDER[e[-1]] for e in es)
		for kind in sorted(by_kind, key=lambda k: (worst(by_kind[k]), -sum(len(e[1]) for e in by_kind[k]))):
			entries = by_kind[kind]
			g = t.insert("", "end", text=f"{'🔴🟠🟡'[worst(entries)]} {kind}  ({len(entries)})", values=(sum(len(e[1]) for e in entries), "", ""),
						 open=True, tags=("group",))
			kids = []
			for pattern, rows, new, hide, sev in sorted(entries, key=lambda e: (SEV_ORDER[e[4]], re.match(r"#? ?errors\.|\d+ errors\.", e[0]) is not None,
																					 not e[2], -len(e[1]))):
				files = sorted({r["file"] for r in rows if r["file"]})
				where = files[0] + (f" (+{len(files) - 1} files)" if len(files) > 1 else "") if files else rows[0]["log"]
				item = ("log", kind, pattern, rows)
				fixable = fx.help_for(kind, pattern)[2] in ("tokens", "ideas", "comment", "comma", "backtick", "flag32")  # (a loc one's 🔧 is in 🌐 Localisation)
				iid = t.insert(g, "end", text=f"{sev} " + ("🔧 " if fixable else "") + pattern + self.decor(item),
							   values=(len(rows), "🆕" if new else "", where), tags=("new",) if new else ("hidden",) if hide else ("fixable",) if fixable else ())
				self.items[(str(t), iid)] = item
				kids.append(item)
				shown += 1
			self.items[(str(t), g)] = ("group", kind, kids)
		ui.stripe(t)
		# 🌐 localisation: the game's duplicate keys, the mod check's text problems, spelling
		t = self.loc_tree
		t.delete(*t.get_children())
		loc_n = 0
		sev_dupe = fx.severity(LOC, "Duplicate localization")
		dupe_rows = [(k, v) for k, v in sorted(self.dupes.items()) if (show_all or f"dupe:{k}" not in dis) and self.sev_ok(sev_dupe)
					 and self.match(k + " " + " ".join(f for f, _ in v)) and (mine is None or any(f in mine for f, _ in v))]
		if dupe_rows:
			n_game = sum(1 for _, v in dupe_rows if any(not os.path.isfile(os.path.join(self.root_dir, f)) for f, _ in v))
			g = t.insert("", "end", text=f"{sev_dupe} Keys in more than one file (the game's text.log)  ({len(dupe_rows)}" +
						 (f", 🎮 {n_game} with the base game" if n_game else "") + ")", values=(len(dupe_rows), "", ""), open=True, tags=("group",))
			bg, fg = vanilla_colours()
			t.tag_configure("vanilla", background=bg, foreground=fg)
			kids = []
			for k, v in dupe_rows:
				same = len({val for _, val in v}) == 1
				game = [f for f, _ in v if not os.path.isfile(os.path.join(self.root_dir, f))]
				item = ("dupe", k, v)
				label = f"{sev_dupe} " + ("🎮 " if game else "") + ("🔧 " if same else "") + f"{k}  -  {'same text' if same else 'different texts'}" + \
						(f"  ·  clashes with the base game's {os.path.basename(game[0])}" if game else "") + self.decor(item)
				iid = t.insert(g, "end", text=label, values=(len(v), "", v[0][0] + (f" (+{len(v) - 1})" if len(v) > 1 else "")),
							   tags=("hidden",) if f"dupe:{k}" in dis else ("vanilla",) if game else ("fixable",) if same else ())
				self.items[(str(t), iid)] = item
				kids.append(item)
				loc_n += 1
			self.items[(str(t), g)] = ("group", "Keys in more than one file", kids)
		other = [(p, r) for (kind, p), r in self.groups.items() if kind == LOC and "Duplicate localization" not in p]
		if other:
			g = t.insert("", "end", text=f"Other complaints in the game's logs  ({len(other)})", values=("", "", ""), open=True, tags=("group",))
			for p, r in other:
				iid = t.insert(g, "end", text=f"{fx.severity(LOC, p)} {p}", values=(len(r), "", r[0]["log"]))
				self.items[(str(t), iid)] = ("log", LOC, p, r)
				loc_n += 1
		loc_problems = [p for p in self.problems if p["check"] in LOC_CHECKS] + self.spell
		if dupe_rows:  # (keys text.log already lists aren't shown twice)
			loc_problems = [p for p in loc_problems if not (p["check"] == "Localisation keys defined twice" and p["key"][8:] in self.dupes)]
		loc_n += self.lint_groups(t, loc_problems, mine)
		ui.stripe(t)
		# 🔎 the mod check's other problems (and the files you've just changed, first)
		t = self.lint_tree
		t.delete(*t.get_children())
		quick = list(getattr(self.app, "error_quick", []) or [])
		self._quick_keys = [p["key"] for p in quick]
		lint_n = self.lint_groups(t, quick + [p for p in self.problems if p["check"] not in LOC_CHECKS and p.get("tab") != "outcome"], mine)
		ui.stripe(t)
		# 🤔 no error, but probably not what was meant (outcome_checks.py, part of the mod check)
		t = self.outcome_tree
		t.delete(*t.get_children())
		outcome_n = self.lint_groups(t, [p for p in self.problems if p.get("tab") == "outcome"], mine)
		ui.stripe(t)
		# ✅ recently fixed (since you last checked)
		t = self.fixed_tree
		t.delete(*t.get_children())
		fixes = sorted(self.unseen_fixes(), key=lambda e: e.get("when", ""), reverse=True)
		for e in fixes:
			iid = t.insert("", "end", text="✅ " + e.get("what", "?"), values=(e.get("by", "?"), e.get("when", "")[:16].replace("T", " "),
																		  ", ".join(e.get("files") or []) or "-"))
			self.items[(str(t), iid)] = ("fixed", e)
		ui.stripe(t)
		self.fixed_note.config(text=f"{len(fixes)} fixed since you last checked (by anyone; kept {FIXED_DAYS} days)." if fixes
							   else "Nothing new fixed since you last checked.")
		self.tabs.tab(4, text=f"✅ Recently fixed ({len(fixes)})")
		when = datetime.datetime.fromtimestamp(self.log_time).strftime("%d %b %H:%M") if self.log_time else "no logs found"
		source = (f"📂 {os.path.basename(self.log_files[0])}" + (" (another mod's: read only)" if self.foreign else "") + " - ↻ goes back to the game's logs. "
				  if self.log_files else f"⚠ The last launch ran {', '.join(getattr(self, 'run_mods', None) or ['other mods'])}, not RR: read only. "
				  if self.foreign else "")
		self.status.config(text=source + f"📜 Logs from {when}: {len(self.rows)} lines, {len(self.groups)} kinds of error" +
							(f", {sum(1 for k, p in self.groups if sig(k, p) not in self.before)} 🆕 since the run before" if self.before else "") +
							"   ·   🔎 Mod check: " + (f"{len(self.problems)} problems ({self.lint_when})" if self.lint_when else "not run yet - ▶ Check the mod's files") +
							("   ·   👤 only files you changed last" if mine is not None else "   ·   👤 (working out who changed what...)" if self.only_mine.get() else ""))
		self.tabs.tab(0, text=f"📜 From the game's logs ({shown})")
		self.tabs.tab(1, text=f"🌐 Localisation ({loc_n})")
		self.tabs.tab(2, text=f"🔎 Not in the log ({lint_n})")
		self.tabs.tab(3, text=f"🤔 Potential Unintentional Outcomes ({outcome_n})")
		self.draw_trend()
		self.show(None)

	def sev_ok(self, sev):
		pick = self.sev_var.get()
		return pick == SEV_PICK[0] or sev in pick.split()[0]

	def lint_groups(self, t, problems, mine=None):
		dis = self.dismissed()
		checks = defaultdict(list)
		for p in problems:
			if (p["key"] in dis and not self.show_hidden.get()) or not self.match(p["message"] + " " + p["file"] + " " + p["check"]):
				continue
			if mine is not None and p["file"] not in mine:
				continue
			sev = fx.severity(p["check"], p["message"])
			if not self.sev_ok(sev):
				continue
			new = bool(self.lint_prev) and p["check"] != "Spelling" and p["key"] not in self.lint_prev and not p.get("group")
			if self.only_new.get() and not new:
				continue
			checks[p.get("group") or p["check"]].append((p, new, sev))
		n = 0
		worst = lambda es: min(SEV_ORDER[e[2]] for e in es)
		for check in sorted(checks, key=lambda c: (not c.startswith("📝"), worst(checks[c]), c)):
			g = t.insert("", "end", text=f"{'🔴🟠🟡'[worst(checks[check])]} {check}  ({len(checks[check])})", values=(len(checks[check]), "", ""),
						 open=True, tags=("group",))
			kids = []
			for p, new, sev in sorted(checks[check], key=lambda e: (SEV_ORDER[e[2]], not e[1], e[0]["file"], e[0]["line"] or 0)):
				item = ("lint", p)
				fixable = self.lint_fix(p) is not None
				extra = (f"  →  did you mean {p['suggest'][0]}?" if p.get("suggest") else "")
				iid = t.insert(g, "end", text=f"{sev} " + ("🔧 " if fixable else "") + p["message"] + extra + self.decor(item),
							   values=("", "🆕" if new else "", f"{p['file']}:{p['line']}"),
							   tags=("new",) if new else ("hidden",) if p["key"] in dis else ("fixable",) if fixable else ())
				self.items[(str(t), iid)] = item
				kids.append(item)
				n += 1
			self.items[(str(t), g)] = ("group", check, kids)
		return n

	# ---------- the picked one ----------
	def show(self, tree):
		sel = tree.selection() if tree is not None else ()
		cur = self.items.get((str(tree), sel[0])) if sel else None  # (each tab numbers its rows from I001: keyed by the tab too)
		if cur is not self.cur:
			self.part = 0
		self.cur = cur
		d = self.detail
		d.configure(state="normal")
		d.delete("1.0", "end")
		cur = self.cur
		if cur is None:
			d.insert("end", "Pick an error to see all of it here, with what it means and how to fix it. Double-click opens its file.\n\n"
					 "Pick a group's row (its name) to 🔧 fix all the easy ones in it at once.")
		elif cur[0] == "group":
			kids = cur[2]
			auto = [k for k in kids if self.auto_fix(k)]
			d.insert("end", f"{cur[1]}: {len(kids)}\n", "head")
			d.insert("end", (f"🔧 {len(auto)} of them can be fixed in one go (Fix all) - the rest need a look each." if auto else
							 "None of these can be fixed automatically: open them one by one.") + "\n")
		else:
			title, text = self.help()[:2] if cur[0] != "fixed" else ("Fixed", "It's gone from the lists. ✓ Checked clears this list for you.")
			ins = lambda s_, *tags: d.insert("end", s_, tags)
			# The top (always shown): what it is, how bad, where.
			if cur[0] == "log":
				_, kind, pattern, rows = cur
				ins(f"{pattern}\n", "title")
				sev = fx.severity(kind, pattern)
				ins(f"{sev} {fx.SEVERITY[sev]}   ·   {kind}   ·   {len(rows)} time{'s' if len(rows) != 1 else ''} in "
					f"{', '.join(sorted({r['log'] for r in rows}))}\n", "meta")
			elif cur[0] == "fixed":
				e = cur[1]
				ins(f"✅ {e.get('what')}\n", "title")
				ins(f"Fixed by {e.get('by', '?')} on {e.get('when', '')[:16].replace('T', ' ')}" +
					("   ·   " + ", ".join(e["files"]) if e.get("files") else "") + "\n", "meta")
			elif cur[0] == "dupe":
				_, key, where = cur
				ins(f"{key} is in {len(where)} files\n", "title")
				ins("🔴 the game uses one of them at random\n", "meta")

				def copies():
					for f, val in where:
						game = not os.path.isfile(os.path.join(self.root_dir, f))
						ins(f"{'🎮 base game' if game else '📁 mod'}: {f}" + (f" ({fx.dlc_of(f)} DLC)" if game and fx.dlc_of(f) else "") +
							f"\n      \"{val}\"\n", "vanilla" if game else "body")
				self.section("copies", f"📁 The copies ({len(where)})", copies)
			else:
				p = cur[1]
				sev = fx.severity(p["check"], p["message"])
				ins(f"{p['message']}\n", "title")
				ins(f"{sev} {fx.SEVERITY[sev]}   ·   {p['check']}   ·   {p['file']}, line {p['line']}\n", "meta")
				notes = []
				if p.get("suggest"):
					notes.append(f"🔎 Did you mean: {', '.join(p['suggest'])}?  (🔧 puts it in)")
				if p.get("leftover"):
					notes.append("🎮 This file is a copy of a base-game file: the line is probably a leftover from it.")
				if p["check"] == "Braces":
					plan = fx.brace_plan(self.root_dir, p["file"], p["line"]) if not p["file"].startswith("<game>") else None
					if plan:
						notes.append(f"🔧 The missing }} most likely goes before line {plan[1] + 1} (where the indentation steps back out - "
									 "see the code)." if plan[0] == "insert" else f"🔧 Line {plan[1] + 1} is just an extra }}: Fix it comments it out.")
				if notes:
					self.section("found", "🔎 Found", lambda: ins("\n".join(notes) + "\n", "body"))
			if cur[0] == "log" and fx.help_for(cur[1], cur[2])[2] == "capital":
				self.section("country", "🏳 The country", self.capital_info)
			self.section("help", f"💡 {title}", lambda: ins(text + "\n", "help"))
			key = self.item_id(cur)
			status = []
			acc = self.accepted(cur)
			if acc:
				status.append(f"🙈 Accepted by {acc.get('by', '?')} ({acc.get('when', '')}): {acc.get('reason', 'hidden')}" +
							  (f" - {acc['note']}" if acc.get("note") else ""))
			c = self.claims().get(key) if key else None
			if c:
				status.append(f"✋ {c['who']} is on it (since {c.get('when', '')}).")
			t = self.todo.linked(self.link_for(cur)) if cur[0] in ("log", "dupe", "lint") else None
			if t:
				status.append(f"➕ Task {t['ref']} ({t.get('status')})")
			for a in __import__("error_alerts").for_key(self.todo.data, key) if key else []:
				status.append(f"🚨 {a.get('by', '?')} alerted {a.get('to', '?')} ({a.get('when', '')[5:16].replace('T', ' ')}): "
							  + (a.get("answer") or "waiting for an answer"))
			if status:
				self.section("status", "📋 Who's on it", lambda: ins("\n".join(status) + "\n", "body"))
			if cur[0] == "log":
				def lines():
					for r in cur[3][:300]:
						ins(f"[{r['time']}] ", "stamp")
						ins(f"{r['msg']}\n", "mono")
					if len(cur[3]) > 300:
						ins(f"... and {len(cur[3]) - 300} more\n", "meta")
				self.section("lines", f"📜 The error lines ({len(cur[3])})", lines)
		d.configure(state="disabled")
		self.snapshot() if not (cur and cur[0] == "group") else self.code_note("Pick one of the group's errors to see its code.")
		self.open_btn.state(["!disabled"] if cur and cur[0] != "group" and self.where()[0] else ["disabled"])
		active = cur is not None and cur[0] not in ("fixed",) and not (self.foreign and cur[0] in ("log", "dupe", "group"))
		single = active and cur[0] != "group"
		self.task_btn.state(["!disabled"] if single else ["disabled"])
		self.fix_btn.state(["!disabled"] if active and self.can_fix() else ["disabled"])
		self.fix_btn.config(text=f"🔧 Fix all ({sum(1 for k in cur[2] if self.auto_fix(k))})" if cur and cur[0] == "group" else "🔧 Fix it")
		self.hide_btn.state(["!disabled"] if single else ["disabled"])
		self.claim_btn.state(["!disabled"] if single else ["disabled"])
		self.alert_btn.state(["!disabled"] if single else ["disabled"])
		if single:
			mine = (self.claims().get(self.item_id(cur)) or {}).get("who")
			self.claim_btn.config(text="✋ Unclaim" if mine == self.todo.me.get() else f"✋ Claim (now {mine})" if mine else "✋ Claim")
		if cur and cur[0] == "log":
			self.hide_btn.config(text="👁 Show errors like this again" if self.hidden(cur[1], cur[2]) else "🙈 Accept / hide (for everyone)...")
		elif single:
			self.hide_btn.config(text="👁 Bring it back" if self.item_key() in self.dismissed() else "🙈 Accept / dismiss (for everyone)...")

	def section(self, key, title, body):
		"""A foldable part of the detail: ▾ title (click: ▸ folded - remembered for next time), then what body() inserts."""
		d = self.detail
		closed = key in self.closed_secs
		d.insert("end", ("▸ " if closed else "▾ ") + title + "\n", ("sec", "h_" + key))
		start = d.index("end-1c")
		body()
		d.tag_add("b_" + key, start, "end-1c")
		d.tag_configure("b_" + key, elide=closed)
		d.tag_bind("h_" + key, "<Button-1>", lambda ev, k=key: self.toggle_section(k))
		d.tag_bind("h_" + key, "<Enter>", lambda ev: d.configure(cursor="hand2"))
		d.tag_bind("h_" + key, "<Leave>", lambda ev: d.configure(cursor=""))

	def toggle_section(self, key):
		d = self.detail
		closed = key not in self.closed_secs
		(self.closed_secs.add if closed else self.closed_secs.discard)(key)
		self.app.config["error_detail_closed"] = sorted(self.closed_secs)
		self.app.save_config()
		d.configure(state="normal")
		r = d.tag_ranges("h_" + key)
		if r:
			d.delete(r[0], f"{r[0]}+1c")
			d.insert(r[0], "▸" if closed else "▾", ("sec", "h_" + key))
		d.tag_configure("b_" + key, elide=closed)
		d.configure(state="disabled")
		return "break"

	def capital_info(self):
		"""🏳 For a capital error: each country's tag, its history's capital = line and the states it owns."""
		ins = lambda s_, *tags: self.detail.insert("end", s_, tags or ("body",))
		cps = self.capitals()
		if not cps:
			ins("Couldn't tell which country this is (its name isn't in the localisation).\n")
		for cp in cps:
			ins(f"{cp['tag'] or '?'}", "head")
			ins(f"  {cp['name']}" + (f"   (also: {', '.join(t for t in cp['tags'] if t != cp['tag'])})" if len(cp["tags"]) > 1 else "") + "\n")
			if cp["history"]:
				where = f"state {cp['capital']}" + (f" ({cp['state_name']})" if cp["capital"] == cp["state"] and cp.get("state_name") else "")
				ins(f"📄 {cp['history']}, line {cp['line']}: capital = {where}" + (f"   #{cp['comment']}" if cp["comment"] else "") + "\n")
				if cp["capital"] != cp["state"]:
					ins("   Its history names another capital: the bad one is set by an effect (set_capital, or states moving at the start).\n")
			else:
				ins("📄 No history/countries file for it.\n")
			if cp.get("owner") and cp["owner"] != cp["tag"]:
				ins(f"🏳 State {cp['state']} belongs to {cp['owner']}.\n")
			if cp["owned"]:
				ins(f"✔ It owns {len(cp['owned'])}: " + ", ".join(f"{s_} {n}" + (f" ({vp:g} VP)" if vp else "") for s_, n, _, vp in cp["owned"][:8]) +
					(" ..." if len(cp["owned"]) > 8 else "") + "\n")
				if cp["suggest"] and cp["capital"] == cp["state"]:
					ins(f"🔧 Fix it suggests {cp['suggest'][0]} {cp['suggest'][1]}" +
						(" (its comment says so)" if cp["comment"] and cp["suggest"][1].lower() in cp["comment"].lower() else " (the most victory points)") + "\n")
			else:
				ins("✖ It owns no states at the start (history/states owner =): it needs one before it can have a capital.\n")

	def code_note(self, text):
		c = self.code
		c.configure(state="normal")
		c.delete("1.0", "end")
		c.insert("end", text, "num")
		c.configure(state="disabled")
		self.parts_bar.pack_forget()

	# ---------- ✋ claims, ➕ tasks, 🙈 accepted, 📈 trend ----------
	def item_id(self, cur):
		if not cur:
			return None
		return sig(cur[1], cur[2]) if cur[0] == "log" else f"dupe:{cur[1]}" if cur[0] == "dupe" else cur[1]["key"] if cur[0] == "lint" else None

	def link_for(self, cur):
		return "errorlog:" + (sig(cur[1], cur[2]) if cur[0] == "log" else sig("dupe", cur[1]) if cur[0] == "dupe" else sig(cur[1]["key"]))

	def claims(self):
		return self.todo.data.setdefault("error_claims", {})

	def decor(self, item):
		"""'  ✋ Nilo  ➕ RR-0712' after a row: who's on it, its task."""
		out = ""
		c = self.claims().get(self.item_id(item))
		if c:
			out += f"  ✋ {c['who']}"
		t = self.todo.linked(self.link_for(item))
		if t and t.get("status") not in ("Completed", "Not Possible"):
			out += f"  ➕ {t['ref']}"
		acc = self.accepted(item)
		if acc and self.show_hidden.get():
			out += f"  (accepted: {acc.get('reason', 'hidden')})"
		return out

	def accepted(self, item):
		if item[0] == "log":
			return next((n for n in self.noise() if n.get("kind") == item[1] and n.get("pattern") == item[2]), None)
		key = self.item_id(item)
		return self.dismissed().get(key) if key else None

	def alert_dev(self):
		"""🚨 Flash this error at a dev: on their Organisation Master it pops up on top until they answer (error_alerts.py)."""
		import error_alerts
		import now_doing
		cur, todo = self.cur, self.todo
		me = todo.me.get()
		devs = [d["name"] for d in todo.data.get("devs", []) if d["name"] != me]
		if not devs:
			return
		f_, line = self.where()
		owner = last_changer(self.root_dir, f_) if f_ else None
		dev_of = lambda who: next((d["name"] for d in todo.data["devs"] if who and who.casefold() in {d["name"].casefold(), (d.get("git") or "").casefold()}), None)
		pick = tk.StringVar(value=dev_of(owner) if dev_of(owner) in devs else devs[0])
		note = tk.StringVar()

		def body(f):
			for n in devs:
				on = now_doing.online(todo.data, n)
				off = error_alerts.alerts_off(todo.data, n)
				ttk.Radiobutton(f, text=n + ("   🟢 online: pops up now" if on and not off else "   🟢 online" if on else "   (offline: when they open it)")
								+ ("   · alerts off: waits for them" if off else "") + ("   · last changed the file" if n == dev_of(owner) else ""),
								variable=pick, value=n).pack(anchor="w", pady=(2, 0))
			ttk.Label(f, text="A note (optional):").pack(anchor="w", pady=(8, 0))
			ttk.Entry(f, textvariable=note, width=60).pack(fill="x")
		title = self.help()[0] if cur[0] != "lint" else cur[1]["message"]
		text = cur[2] if cur[0] == "log" else f"{cur[1]} is in more than one file" if cur[0] == "dupe" else cur[1]["message"]
		if not ask(self, "🚨 Error alert", f"Flash this at a dev - it pops up on top of their screen until they answer:\n\n{text[:200]}",
				   (("Cancel", False), ("🚨 Send", True)), extra=body):
			return
		sev = fx.severity(*((cur[1], cur[2]) if cur[0] == "log" else (LOC, "Duplicate localization") if cur[0] == "dupe" else (cur[1]["check"], cur[1]["message"])))
		error_alerts.send(todo, pick.get(), self.item_id(cur), self.link_for(cur), text[:200], sev,
						  f"{f_}" + (f", line {line}" if line else "") if f_ else "", note.get().strip())
		self.status.config(text=f"🚨 Sent to {pick.get()} - you'll see their answer here and in the status bar.")
		self.fill()

	def go_to(self, key):
		"""Picks the error with this id (an alert's) in whichever tab has it."""
		for (tree_name, iid), item in self.items.items():
			if item[0] != "group" and self.item_id(item) == key:
				tree = self.nametowidget(tree_name)
				for n, tab in enumerate(self.tabs.tabs()):
					if str(tree).startswith(tab):
						self.tabs.select(n)
				tree.see(iid)
				tree.selection_set(iid)
				return True
		return False

	def claim(self):
		"""✋ You're on it (everyone sees) - or not any more."""
		key, me = self.item_id(self.cur), self.todo.me.get()
		claims = self.claims()
		if (claims.get(key) or {}).get("who") == me:
			claims.pop(key)
		else:
			claims[key] = {"who": me, "when": datetime.date.today().isoformat()}
		self.todo.save(feedback=False)
		self.fill()

	def complete_links(self, links, why):
		"""➕ The tasks made for these errors, completed (they're fixed)."""
		done = 0
		for link in links:
			t = self.todo.linked(link)
			if t and t.get("status") not in ("Completed", "Not Possible"):
				self.todo.change(t, "status", "Completed", note=why)
				done += 1
		if done:
			self.todo.save(feedback=False)
			self.todo.fill()

	def complete_gone(self, source, present, why):
		"""Tasks made from this kind of list (log / check) whose error isn't in it any more: done."""
		gone = [t["link"] for t in self.todo.tasks if str(t.get("link") or "").startswith("errorlog:") and t.get("error_source") == source
				and t.get("status") not in ("Completed", "Not Possible") and t["link"] not in present]
		if gone:
			self.complete_links(gone, why)

	def record_trend(self, source, sevs):
		"""📈 One point: the total (and per severity) of a launch's log or of a mod check."""
		trend = self.todo.data.setdefault("error_trend", [])
		count = {"🔴": 0, "🟠": 0, "🟡": 0}
		for sev, n in sevs:
			count[sev] += n
		trend.append({"when": datetime.datetime.now().replace(microsecond=0).isoformat(), "source": source, "total": sum(count.values()),
					  "red": count["🔴"], "orange": count["🟠"], "yellow": count["🟡"], "by": self.todo.me.get()})
		del trend[:-200]
		self.todo.save(feedback=False)

	def draw_trend(self):
		"""📈 Two panels, each on its own scale: the launches' errors and the mod check's problems, run by run (evenly
		spaced, dated), the total with its 🔴 part under it."""
		c = self.trend
		if not c.winfo_exists():
			return
		c.delete("all")
		c.configure(background=ui.P.get("surface", "#ffffff"))
		W, H = c.winfo_width(), c.winfo_height()
		if W < 160 or H < 160:
			return
		muted, fg = ui.P.get("muted", "#777777"), ui.P.get("foreground", "#000000")
		grid = ui.P.get("border", "#cccccc")
		points = self.todo.data.get("error_trend") or []
		c.create_text(14, 10, anchor="nw", text="📈 Errors over time", font="om_head", fill=fg)
		c.create_text(W - 14, 14, anchor="ne", text="A point per launch (a new error.log) and per mod check.", font="om_small", fill=muted)
		panels = (("log", "📜 Launch errors", ui.P.get("age_yellow", "#b58900")), ("check", "🔎 Mod check (Not in the log)", ui.P.get("copper", "#1f5fa8")))
		red = ui.P.get("age_red", "#c62828")
		ph = (H - 50) / len(panels)
		for n, (src, label, colour) in enumerate(panels):
			pts = [p for p in points if p.get("source") == src][-40:]
			top, bottom = 50 + n * ph + 26, 50 + (n + 1) * ph - 30
			left, right = 64, W - 40
			now = f"{pts[-1]['total']}  (🔴 {pts[-1].get('red', 0)})" if pts else ""
			if len(pts) > 1:
				diff = pts[-1]["total"] - pts[-2]["total"]
				now += f"   {'▼' if diff < 0 else '▲' if diff > 0 else '='} {abs(diff)} since the run before" if diff else "   = same as the run before"
			c.create_text(left - 50, top - 22, anchor="w", text=f"{label}   {now}", font="om_small_bold", fill=colour)
			if not pts:
				c.create_text((left + right) / 2, (top + bottom) / 2, text="Nothing yet - " + ("launch the game." if src == "log" else "run the mod check."),
							  font="om_body", fill=muted)
				continue
			top_value = max(p["total"] for p in pts) or 1
			for v in (0, top_value // 2, top_value):
				y = bottom - (bottom - top) * v / top_value
				c.create_line(left, y, right, y, fill=grid, dash=(2, 4))
				c.create_text(left - 6, y, anchor="e", text=str(v), font="om_small", fill=muted)
			step = (right - left) / max(1, len(pts) - 1)
			xs = [left + step * i if len(pts) > 1 else (left + right) / 2 for i in range(len(pts))]
			for field, col, width in (("total", colour, 2), ("red", red, 1)):
				xy = [(x, bottom - (bottom - top) * p.get(field, 0) / top_value) for x, p in zip(xs, pts)]
				if len(xy) > 1:
					c.create_line(*[v for pt in xy for v in pt], fill=col, width=width)
				for x, y in xy:
					c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=col, outline="")
			for i in sorted({0, len(pts) - 1} | set(range(0, len(pts), max(1, len(pts) // 6)))):
				c.create_text(xs[i], bottom + 12, text=pts[i]["when"][5:16].replace("T", " "), font="om_small", fill=muted)
			if len(pts) == 1:
				c.create_text((left + right) / 2, top + 4, anchor="n", text="One run so far: the line starts with the next one.", font="om_small", fill=muted)
		c.create_text(W - 14, H - 8, anchor="se", text="━ total    ━ 🔴 breaks things", font="om_small", fill=muted)

	# ---------- the code around it ----------
	def grep(self, pattern, fixed=True, word=True, limit=3):
		"""[(file, line)] where the mod has pattern (git grep: fast on the whole mod), up to limit files."""
		args = ["git", "-C", self.root_dir, "grep", "-n", "-I", "--max-count=1"] + (["-F"] if fixed else ["-E"]) + (["-w"] if word else [])
		args += ["-e", pattern, "--", "common", "events", "history", "interface", "localisation"]
		try:
			out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, creationflags=NO_WINDOW).stdout
		except (OSError, subprocess.SubprocessError):
			return []
		hits = []
		for l in out.splitlines():
			m = re.match(r"(.+?):(\d+):", l)
			if m:
				hits.append((m.group(1), int(m.group(2))))
			if len(hits) >= limit:
				break
		return hits

	def parts(self):
		"""[(title, places)] of the picked error - several for one with several parts (each duplicate idea, each token,
		each file): ◀ ▶ step through them. places: a list, or a function making it (worked out when the part is shown).
		A place: (full path, label, line (1-based), first line to show, last line, word to mark, the game's)."""
		cur = self.cur
		mod = lambda f: os.path.join(self.root_dir, f)
		if cur[0] == "fixed":
			return [("", [(mod(f), f, 1, None, None, None, False) for f in cur[1].get("files") or [] if os.path.isfile(mod(f))][:3])]
		if cur[0] == "lint" and cur[1]["check"] == "Braces" and not cur[1]["file"].startswith("<game>"):
			p = cur[1]
			plan = fx.brace_plan(self.root_dir, p["file"], p["line"])
			out = [("Where the { opens", [(mod(p["file"]), p["file"], p["line"], None, None, "{", False)])]
			if plan:
				out.append(("Where the } would go" if plan[0] == "insert" else "The extra }",
							[(mod(p["file"]), p["file"] + "|  (🔧 adds the } here)" if plan[0] == "insert" else p["file"], plan[1] + 1, None, None, "}", False)]))
			return out
		if cur[0] == "lint":
			p = cur[1]
			word = (re.match(r"(.+)", p["word"]) if p.get("word") else None) or (re.search(r"\b(GFX_[\w\-]+|[\w\-]+\.\d+)\b", p["message"]) or re.search(r'"([^"]+)"', p["message"]) or
					re.search(r"(?:Focus|title|desc|flag|Idea|Character|Event|namespace|category) ([\w.\-@]+)", p["message"]) or
					re.match(r"([A-Z][A-Z0-9]{2}) isn't a country tag", p["message"]) or re.match(r"([\w/.\-]+\.\w+) is a spriteType", p["message"]))
			return [("", [(mod(p["file"]), p["file"], p["line"], None, None, word.group(1) if word else None, False)])]
		if cur[0] == "dupe":
			out = []
			for c in fx.copies(self.root_dir, cur[1], cur[2], self.game()):
				full = mod(c["file"]) if c["mod"] else os.path.join(self.game() or "", c["file"])
				line = c["line"] + 1 if c["mod"] else (fx.loc_line_no(self.game(), c["file"], cur[1])[0] or 0) + 1 if self.game() else 1
				out.append((full, ("🎮 base game: " if not c["mod"] else "") + c["file"], line, None, None, cur[1], not c["mod"]))
			return [("", out)]
		_, kind, pattern, rows = cur
		fix = fx.help_for(kind, pattern)[2]
		if fix == "capital":
			parts = []
			for cp in self.capitals():
				places = []
				if cp["history"]:
					places.append((mod(cp["history"]), cp["history"] + f"|  ({cp['tag']}'s history)", cp["line"] or 1, 1, None,
								   "capital", False))
				for sid, name, f, _vp in cp["owned"][:4]:
					places.append((mod(f), f + f"|  ({cp['tag']} owns it)", 1, 1, 12, f"owner = {cp['tag']}", False))
				parts.append((f"{cp['tag'] or '?'}: {cp['name']}", places))
			return parts or [("", [])]
		if fix == "ideas":
			parts = []
			for name in fx.idea_names(rows):
				defs = fx.find_defs(self.root_dir, name)
				parts.append((f"{name}" + ("" if len(defs) > 1 else "  (fixed already: defined once)"),
							  [(mod(d["file"]), d["file"], d["start"] + 1, d["start"] + 1, d["end"] + 1, name, False) for d in defs]))
			return sorted(parts, key=lambda p: "fixed already" in p[0]) or [("", [])]  # (the ones still to do first)
		if fix == "tokens":
			def where(name):
				return lambda: [(mod(f), f + f"|  (where {name} is used)", line, None, None, name, False)
								for f, line in (self.grep(f"token:{name}", word=False) or self.grep(name))[:3]]
			return [(name, where(name)) for name in fx.token_names(self.token_rows())] or [("", [])]
		files = list(dict.fromkeys(r["file"] for r in rows if r["file"] and os.path.isfile(mod(r["file"]))))
		if not files:  # (the message names something but no file - a 3D model, a doctrine: where the mod uses it)
			names = list(dict.fromkeys(n for r in rows for n in re.findall(r'"([\w\-]+)"|:\s*([\w\-]{4,})\.?(?:\s|$)', r["msg"]) for n in n if n))
			def used(name):
				return lambda: [(mod(f), f + f"|  (where {name} is used)", line, None, None, name, False) for f, line in self.grep(name)[:3]]
			if names:
				return [(n, used(n)) for n in names]
		if len(files) > 1:
			return [(f, [(mod(f), f, next(r["line"] for r in rows if r["file"] == f) or 1, None, None, None, False)]) for f in files]
		return [("", [(mod(r["file"]), r["file"], r["line"] or 1, None, None, None, False) for r in rows[:1] if r["file"] and os.path.isfile(mod(r["file"]))])]

	def capitals(self):
		"""The picked capital error's countries: fx.capital_problem for each different message (worked out once)."""
		cur = self.cur
		cache = self.__dict__.setdefault("_capitals", {})
		key = id(cur)
		if key not in cache:
			msgs = list(dict.fromkeys(r["msg"] for r in cur[3]))
			found = [fx.capital_problem(self.root_dir, m, self.game()) for m in msgs]
			cache[key] = [f for f in found if f]
		return cache[key]

	def step(self, d, key=False):
		"""◀ ▶ / ← →: the error's previous / next part. (A key with nothing to step through does what it always does.)"""
		parts = self._snap.get(id(self.cur)) if self.cur else None
		if not parts or len(parts) < 2:
			return None if key else "break"
		self.part = (self.part + d) % len(parts)
		self.snapshot()
		self.open_btn.state(["!disabled"] if self.where()[0] else ["disabled"])  # (📄 Open: this part's file)
		return "break"

	def current_part(self):
		parts = self._snap.get(id(self.cur)) if self.cur else None
		return parts[self.part][0] if parts and len(parts) > 1 else None

	def snapshot(self):
		"""The code around each place, the line and the name highlighted."""
		c = self.code
		c.configure(state="normal")
		c.delete("1.0", "end")
		if self.cur is not None and self.foreign and self.cur[0] in ("log", "dupe"):
			c.insert("end", "Another mod's log: its files aren't in RR, so there's no code to show.", "num")
			c.configure(state="disabled")
			self.parts_bar.pack_forget()
			return
		if self.cur is None:
			c.insert("end", "The code around the error shows here.", "num")
			c.configure(state="disabled")
			return
		key = id(self.cur)
		if key not in self._snap:
			try:
				self._snap = {key: self.parts()}  # (worked out once per click; a part's places when it's shown)
			except Exception as ex:
				self._snap = {key: [("", [])]}
				c.insert("end", f"(couldn't find the code: {ex})\n", "num")
		parts = self._snap[key]
		self.part = min(self.part, len(parts) - 1)
		title, places = parts[self.part]
		if callable(places):
			places = places()
			parts[self.part] = (title, places)
		if len(parts) > 1:
			self.parts_label.config(text=f"{self.part + 1} of {len(parts)}:  {title}   (← / →)")
			if not self.parts_bar.winfo_manager():
				self.parts_bar.pack(side="top", fill="x", before=self._code_first)  # (above the code and its scroll bars)
		else:
			self.parts_bar.pack_forget()
		if not places:
			c.insert("end", "No code to show for this one: the message doesn't say where.\n", "num")
		for full, label, line, first, last, word, game in places[:6]:
			try:
				with open(full, encoding="utf-8-sig", errors="replace") as f:
					lines = f.read().split("\n")
			except OSError:
				c.insert("end", f"{label}: can't open it\n\n", "num")
				continue
			line = max(1, min(line or 1, len(lines)))
			first = max(1, (first or line) - 5)
			last = min(len(lines), (last or line) + 5, first + 40)
			name, _, note = label.partition("|")
			c.insert("end", f"{name}:{line}{note}\n", ("where", "vanilla") if game else "where")
			for n in range(first, last + 1):
				text = lines[n - 1].rstrip("\r").replace("\t", "    ")
				start = c.index("end-1c")
				c.insert("end", f"{n:>6} │ ", "num")
				body = c.index("end-1c")
				c.insert("end", text + "\n")
				if word and word in text:
					i = 0
					while True:
						i = text.find(word, i)
						if i < 0:
							break
						c.tag_add("word", f"{body}+{i}c", f"{body}+{i + len(word)}c")
						i += len(word)
				if n == line:
					c.tag_add("hit", start, f"{start} lineend+1c")
			c.insert("end", "\n")
		c.configure(state="disabled")

	def help(self):
		cur = self.cur
		if cur[0] == "log":
			return fx.help_for(cur[1], cur[2])
		if cur[0] == "dupe":
			return fx.help_for(LOC, "Duplicate localization")
		return fx.help_for(cur[1]["check"], cur[1]["message"])

	def item_key(self):
		return f"dupe:{self.cur[1]}" if self.cur[0] == "dupe" else self.cur[1]["key"] if self.cur[0] == "lint" else None

	def where(self):
		"""(file in the mod, line) 📄 Open goes to: the first mod file the code panel shows for the part you're on (a
		duplicate idea's definition, where a token is used...), else what the error names."""
		cur = self.cur
		if not cur or (self.foreign and cur[0] in ("log", "dupe")):
			return None, None
		parts = self._snap.get(id(cur))
		if parts and not callable(parts[min(self.part, len(parts) - 1)][1]):
			root = os.path.normcase(os.path.abspath(self.root_dir)) + os.sep
			for full, _, line, *_rest in parts[min(self.part, len(parts) - 1)][1]:
				if os.path.normcase(os.path.abspath(full)).startswith(root):
					return os.path.relpath(full, self.root_dir).replace("\\", "/"), line
		if cur[0] == "fixed":
			return ((cur[1].get("files") or [None])[0], None)
		if cur[0] == "lint":
			return cur[1]["file"], cur[1]["line"]
		if cur[0] == "dupe":
			f = next((f for f, _ in cur[2] if os.path.isfile(os.path.join(self.root_dir, f))), None)
			i = fx.loc_line_no(self.root_dir, f, cur[1])[0] if f else None
			return f, (i + 1) if i is not None else None
		r = next((r for r in cur[3] if r["file"]), None)
		return (r["file"], r["line"]) if r else (None, None)

	# ---------- 🔧 fixes ----------
	def lint_fix(self, p):
		"""The 🔧 for a mod-check problem: brace (where the } goes), rename (did you mean), leftover (comment the line out),
		bom, spelling, flag32, dupe - or None."""
		if p["file"].startswith("<game>"):
			return None
		fix = fx.help_for(p["check"], p["message"])[2]
		if fix in ("bom", "spelling", "flag32", "dupe"):
			return fix
		if p["check"] == "Braces":
			return "brace"
		if p.get("suggest"):
			return "rename"
		if p.get("leftover"):
			cache = self.__dict__.setdefault("_cc", {})
			key = (p["file"], p["line"])
			if key not in cache:
				cache[key] = fx.can_comment_line(self.root_dir, p["file"], p["line"])
			return "leftover" if cache[key] else None
		return None

	def auto_fix(self, item):
		"""(what it does, a function doing it -> files changed) for a fix that needs no choice, or None (Fix all uses these)."""
		root = self.root_dir
		if item[0] == "lint":
			p = item[1]
			fix = self.lint_fix(p)
			if fix == "bom":
				return "BOM", lambda: [p["file"]] if fx.fix_bom(root, p["file"]) else []
			if fix == "spelling":
				return "spelling", lambda: [p["file"]] if fx.fix_spelling(root, p) else []
			if fix == "flag32":
				return "32-bit flag", lambda: fx.fix_flag32(root, [p["file"]])
			if fix == "rename" and len(p["suggest"]) == 1:
				return f"→ {p['suggest'][0]}", lambda: [p["file"]] if fx.fix_rename(root, p["file"], p["line"], p.get("name") or "", p["suggest"][0]) else []
			if fix == "leftover":
				return "leftover commented out", lambda: [p["file"]] if fx.fix_comment_line(root, p["file"], p["line"], "base-game leftover") else []
			return None
		if item[0] == "dupe" and len({v for _, v in item[2]}) == 1:
			def go():
				cs = fx.copies(root, item[1], item[2], self.game())
				if len(cs) < 2:
					return []
				pick = next((n for n, c in enumerate(cs) if not c["mod"]), 0)
				return fx.use_copy(root, item[1], cs, pick)
			return "duplicate key", go
		if item[0] == "log" and not self.foreign:
			fix = fx.help_for(item[1], item[2])[2]
			rows = item[3]
			if fix in ("comment", "comma", "backtick"):
				return fix, lambda: fx.fix_lines(root, [(r["file"], r["line"]) for r in rows if r["file"]], fix)
			if fix == "flag32":
				return "32-bit flags", lambda: fx.fix_flag32(root, fx.flag_files(root, rows))
		return None

	def fix_all(self, kids):
		"""🔧 Fix all: every error of the group that needs no choice, one confirm, each recorded as fixed."""
		todo = [(k, self.auto_fix(k)) for k in kids]
		todo = [(k, a) for k, a in todo if a]
		if not todo:
			return
		kinds = defaultdict(int)
		for _, (what, _) in todo:
			kinds[what] += 1
		if not ask(self, "🔧 Fix all", f"Fix {len(todo)} of {len(kids)} in one go?\n\n" + "\n".join(f"  {n} × {w}" for w, n in kinds.items()) +
				   ("\n\nThe rest need a choice: open them one by one." if len(todo) < len(kids) else "") +
				   "\n\nEach file is backed up first (backups/error_fixes).", (("Cancel", False), ("Fix them", True))):
			return
		fixed, files = 0, set()
		for item, (_, go) in todo:
			try:
				changed = go()
			except OSError:
				changed = []
			if changed:
				fixed += 1
				files |= set(changed)
				self.record_fix(item, None, changed)
				if item[0] == "lint":
					self.problems = [p for p in self.problems if p["key"] != item[1]["key"]]
				if item[0] == "dupe":
					self.dupes.pop(item[1], None)
		for f in files:
			self.app.log(f)
		store(LINT_CACHE, {"when": self.lint_when, "problems": self.problems, "prev": sorted(self.lint_prev)})
		self.spell = fx.spelling(self.root_dir, self.spelling_var.get())
		self.status.config(text=f"🔧 Fixed {fixed} of {len(todo)} in {len(files)} file(s). (A copy of each file is in backups/error_fixes.)")
		getattr(self.app, "feedback", lambda *_: None)("success")
		self.fill()

	def can_fix(self):
		if self.cur[0] == "group":
			return any(self.auto_fix(k) for k in self.cur[2])
		if self.cur[0] == "lint":
			return self.lint_fix(self.cur[1]) is not None
		fix = self.help()[2]
		if fix in ("tokens", "ideas"):
			return True
		if fix == "capital":
			return self.cur[0] == "log" and any(cp["history"] and cp["line"] and cp["capital"] == cp["state"] and cp["owned"]
												for cp in self.capitals())
		if fix in ("comment", "comma", "backtick"):
			return self.cur[0] == "log"
		if fix == "flag32":
			return self.cur[0] == "log" and bool(fx.flag_files(self.root_dir, self.cur[3]))
		if fix == "dupe":
			return self.cur[0] in ("dupe", "lint")  # (the chooser: same text or not)
		if fix in ("bom", "spelling"):
			return self.cur[0] == "lint"
		return False

	def token_rows(self):
		"""The log rows a token fix covers: this pattern's - or, for the errors' total, every token row."""
		_, kind, pattern, rows = self.cur
		if fx.help_for(kind, pattern)[0].startswith("The token errors' total"):
			return [r for (k, _), rs in self.groups.items() if k == TOKENS for r in rs]
		return rows

	def fix(self):
		cur = self.cur
		if cur[0] == "group":
			return self.fix_all(cur[2])
		fix = self.lint_fix(cur[1]) if cur[0] == "lint" else self.help()[2]
		changed = []
		if fix == "brace":
			p = cur[1]
			plan = fx.brace_plan(self.root_dir, p["file"], p["line"])
			if not plan:
				return ask(self, "🔧 Fix it", "Couldn't work out where the brace goes - open the file and look at the indentation.")
			text = (f"Add the missing }} before line {plan[1] + 1} of {p['file']} (where the block's indentation ends - the code view shows it)?"
					if plan[0] == "insert" else f"Comment out the extra }} on line {plan[1] + 1} of {p['file']}?")
			if not ask(self, "🔧 Fix it", text + "\n\nCheck it after: indentation is a good guess, not a proof.", (("Cancel", False), ("Do it", True))):
				return
			changed = [p["file"]] if fx.fix_brace(self.root_dir, p["file"], p["line"]) else []
			msg = f"🔧 Braces fixed in {p['file']}."
		elif fix == "rename":
			p = cur[1]
			pick = tk.StringVar(value=p["suggest"][0])

			def body(f):
				for s_ in p["suggest"]:
					ttk.Radiobutton(f, text=s_, variable=pick, value=s_).pack(anchor="w", pady=(4, 0))
			if not ask(self, "🔎 Did you mean", f"Replace {p.get('name')} on line {p['line']} of {p['file']} with:", (("Cancel", False), ("Replace", True)), extra=body):
				return
			changed = [p["file"]] if fx.fix_rename(self.root_dir, p["file"], p["line"], p.get("name") or "", pick.get()) else []
			msg = f"🔧 {p.get('name')} → {pick.get()} in {p['file']}."
		elif fix == "leftover":
			p = cur[1]
			if not ask(self, "🔧 Fix it", f"Comment out line {p['line']} of {p['file']} (a base-game leftover)?", (("Cancel", False), ("Comment it out", True))):
				return
			changed = [p["file"]] if fx.fix_comment_line(self.root_dir, p["file"], p["line"], "base-game leftover") else []
			msg = f"🔧 Line {p['line']} of {p['file']} commented out."
		elif fix == "flag32" and cur[0] == "lint":
			changed = fx.fix_flag32(self.root_dir, [cur[1]["file"]])
			msg = f"🔧 {cur[1]['file']} is 32-bit now."
		elif fix == "capital":
			got = self.choose_capital()
			if got is None:
				return
			changed, msg = got
		elif fix == "tokens":
			names = fx.token_names(self.token_rows())
			have = fx.listed_tokens(self.root_dir)
			add = [n for n in names if n not in have]
			if not add:
				return ask(self, "🔧 Fix it", f"All {len(names)} are in common/synchronized_dynamic_tokens already (added since this run). "
						   "The next launch's log won't have them.")
			if not ask(self, "🔧 Fix it", f"Add {len(add)} token{'s' if len(add) != 1 else ''} to {fx.TOKENS_FILE}?\n\n" +
					   ", ".join(add[:40]) + (" ..." if len(add) > 40 else "") +
					   (f"\n\n({len(names) - len(add)} more are there already.)" if len(names) > len(add) else ""),
					   (("Cancel", False), ("Add them", True))):
				return
			added, _ = fx.fix_tokens(self.root_dir, add)
			changed, msg = [fx.TOKENS_FILE], f"🔧 {len(added)} tokens added to {fx.TOKENS_FILE}."
		elif fix == "dupe":
			key = cur[1] if cur[0] == "dupe" else cur[1]["key"][8:]
			entries = list(cur[2]) if cur[0] == "dupe" else [(cur[1]["file"], None)] + [(f, None) for f in re.findall(r"also in (\S+?):\d+", cur[1]["message"])]
			got = self.choose_copy(key, entries)
			if got is None:
				return
			changed, msg = got
		elif fix == "ideas":
			part = self.current_part()
			names = [part.split("  (")[0]] if part else fx.idea_names(cur[3])  # (several: the one you're looking at)
			got = self.choose_ideas(names)
			if got is None:
				return
			changed, msg = got
		elif fix == "flag32":
			flags = fx.flag_files(self.root_dir, cur[3])
			if not ask(self, "🔧 Fix it", f"Save {len(flags)} flag(s) as 32-bit TGA?\n\n" + "\n".join(flags[:20]), (("Cancel", False), ("Convert them", True))):
				return
			changed = fx.fix_flag32(self.root_dir, flags)
			msg = f"🔧 {len(changed)} flag(s) are 32-bit now."
			if changed:
				self.mark_fixed(sig(cur[1], cur[2]), cur[2], changed)
		elif fix in ("comment", "comma", "backtick"):
			part = self.current_part()
			rows = [r for r in cur[3] if r["file"] and (not part or r["file"] == part)]
			what = {"comment": "// turned into #", "comma": "commas taken out", "backtick": "stray ` taken out"}[fix]
			if not ask(self, "🔧 Fix it", f"{what[0].upper() + what[1:]} on {len(rows)} line(s):\n\n" +
					   "\n".join(f"{r['file']}:{r['line']}" for r in rows[:15]) + ("\n..." if len(rows) > 15 else ""),
					   (("Cancel", False), ("Fix them", True))):
				return
			changed = fx.fix_lines(self.root_dir, [(r["file"], r["line"]) for r in rows], fix)
			msg = f"🔧 {what} in {len(changed)} file(s)."
			if changed:
				key = sig(cur[1], cur[2]) if not part else sig(cur[1], cur[2], part)
				self.mark_fixed(key, cur[2] if not part else f"{cur[2]} ({part})", changed)
		elif fix == "bom":
			changed = [cur[1]["file"]] if fx.fix_bom(self.root_dir, cur[1]["file"]) else []
			msg = f"🔧 {cur[1]['file']} saved with its BOM: the game reads it now."
		elif fix == "spelling":
			changed = [cur[1]["file"]] if fx.fix_spelling(self.root_dir, cur[1]) else []
			msg = f"🔧 \"{cur[1]['word']}\" → \"{cur[1]['fix']}\" in {cur[1]['file']}."
		else:
			return
		for f in changed:
			self.app.log(f)
		if changed:
			self.record_fix(cur, fix, changed)
		if cur[0] == "lint" and changed:
			self.problems = [p for p in self.problems if p["key"] != cur[1]["key"]]
			store(LINT_CACHE, {"when": self.lint_when, "problems": self.problems, "prev": sorted(self.lint_prev)})
		if cur[0] == "dupe" and changed:
			self.dupes.pop(cur[1], None)
		if fix == "spelling":
			self.spell = fx.spelling(self.root_dir, self.spelling_var.get())
		self.status.config(text=(msg if changed else "Nothing needed changing.") + "  (A copy of each file is in backups/error_fixes.)")
		getattr(self.app, "feedback", lambda *_: None)("success")
		self.fill()

	def game(self):
		if not hasattr(self, "_game"):
			try:
				from cm_data import find_game
				self._game = find_game(self.root_dir)
			except Exception:
				self._game = None
		return self._game

	def choose_capital(self):
		"""🏳 Pick the capital from the states the country owns (the one its comment names, else the most victory points)."""
		todo = [cp for cp in self.capitals() if cp["history"] and cp["line"] and cp["capital"] == cp["state"] and cp["owned"]]
		part = self.current_part()
		cp = next((c for c in todo if part and part.startswith(f"{c['tag']}:")), todo[0])
		pick = tk.IntVar(value=cp["suggest"][0])

		def body(f):
			for sid, name, rel, vp in cp["owned"][:25]:
				ttk.Radiobutton(f, text=f"{sid}  {name}" + (f"   ({vp:g} VP)" if vp else ""), variable=pick, value=sid).pack(anchor="w", pady=(2, 0))
			if len(cp["owned"]) > 25:
				ttk.Label(f, text=f"... and {len(cp['owned']) - 25} more (the biggest are listed)", style="Muted.TLabel").pack(anchor="w")
		where = f"state {cp['state']}" + (f" ({cp['state_name']})" if cp.get("state_name") else "") + (f", owned by {cp['owner']}" if cp.get("owner") else "")
		if not ask(self, "🏳 Set the capital", f"{cp['tag']} ({cp['name']}): {cp['history']} line {cp['line']} says capital = {where}.\n\n"
				   f"Its capital should be one of the {len(cp['owned'])} state(s) it owns:", (("Cancel", False), ("Set it", True)), extra=body):
			return None
		sid = pick.get()
		name = next(n for s_, n, _, _ in cp["owned"] if s_ == sid)
		if not fx.fix_capital(self.root_dir, cp["history"], cp["line"], sid, name):
			return [], "Couldn't change the capital line."
		self.__dict__.get("_capitals", {}).pop(id(self.cur), None)
		if len(todo) == 1:  # (the last country of this error: all of it is fixed)
			self.mark_fixed(sig(self.cur[1], self.cur[2]), self.cur[2], [cp["history"]])
		else:
			self.mark_fixed(sig(self.cur[1], self.cur[2], cp["tag"]), f"{cp['tag']}'s capital → {sid} {name}", [cp["history"]])
		return [cp["history"]], f"🔧 {cp['tag']}'s capital is {sid} ({name}) now."

	def choose_copy(self, key, entries):
		"""🔧 for a key in more than one file: every copy with its text (🎮 the base game's, highlighted), pick the one the game
		should use. The base game's files are never edited: the mod's text over a game key goes to replace/, the game's
		text means the mod's copies are commented out. A DLC file's copy can also be switched off whole (an empty file).
		(files changed, message) or None."""
		cs = fx.copies(self.root_dir, key, entries, self.game())
		if len(cs) < 2:
			ask(self, "🔧 Fix it", f"{key} is only in one file now ({cs[0]['file'] if cs else 'none'}) - fixed already?")
			return None
		same = len({c["text"] for c in cs}) == 1
		default = next((n for n, c in enumerate(cs) if not c["mod"]), 0) if same else 0
		pick = tk.IntVar(value=default)
		bg, fg = vanilla_colours()
		made = []

		def body(f):
			ttk.Label(f, text="Which text should the game use?" + ("  (They all say the same.)" if same else ""),
					  font="om_bold").pack(anchor="w", pady=(10, 4))
			for n, c in enumerate(cs):
				row = tk.Frame(f, background=bg if not c["mod"] else ui.P["background"], padx=6, pady=4)
				row.pack(fill="x", pady=2)
				where = (f"📁 The mod: {c['file']}" if c["mod"] else
						 f"🎮 The base game: {c['file']}" + (f"  ({c['dlc']} DLC)" if c["dlc"] else ""))
				ttk.Radiobutton(row, text=where, variable=pick, value=n).pack(anchor="w")
				tk.Label(row, text=f"\"{c['text']}\"", wraplength=ui.px(540), justify="left", font="om_small",
						 background=row["background"], foreground=fg if not c["mod"] else ui.P["foreground"]).pack(anchor="w", padx=(24, 0))
			if any(not c["mod"] for c in cs):
				ttk.Label(f, text="🎮 The base game's files are never edited. Using the mod's text moves it to "
								  f"{fx.REPLACE_FILE} (HOI4 lets keys there override the game's without a clash); using the "
								  "game's text comments out the mod's copies.", wraplength=ui.px(560), justify="left",
						  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
			for c in cs:
				if not c["mod"] and c["dlc"] and not os.path.exists(os.path.join(self.root_dir, c["file"])):
					box = ttk.Frame(f)
					box.pack(fill="x", pady=(8, 0))
					ttk.Label(box, text=f"{os.path.basename(c['file'])} is {c['dlc']} DLC text. If the mod doesn't use that DLC's "
										"content, an empty file with the same name in the mod switches the whole file off "
										"(the mod already does it for some, e.g. aat_focus).", wraplength=ui.px(560), justify="left").pack(anchor="w")

					def empty(c=c, box=box):
						if fx.make_empty(self.root_dir, c["file"]):
							made.append(c["file"])
							self.app.log(c["file"])
							for w in box.winfo_children():
								w.destroy()
							ttk.Label(box, text=f"✓ Made an empty {c['file']} in the mod: the game's file is switched off "
												"from the next launch.").pack(anchor="w")
					ttk.Button(box, text=f"📄 Make an empty {os.path.basename(c['file'])} in the mod", command=empty).pack(anchor="w", pady=(4, 0))
		go = ask(self, f"🔧 {key} is in {len(cs)} files", "One text has to win: choose it and the others stop clashing.",
				 (("Cancel", False), ("Use this one", True)), extra=body)
		if made and not go:
			return made, f"📄 Empty file made: {', '.join(made)}."
		if not go:
			return None
		changed = fx.use_copy(self.root_dir, key, cs, pick.get())
		chosen = cs[pick.get()]
		return made + changed, (f"🔧 {key}: the game uses " + ("the mod's text (in replace/)" if chosen["mod"] and any(not c["mod"] for c in cs)
								 else f"the copy in {chosen['file']}") + (f"; {len(changed)} file(s) changed." if changed else "."))

	def choose_ideas(self, names):
		"""🔧 for duplicate ideas: each name's definitions (code shown), which to keep (the first by default); the others
		are commented out. (files changed, message) or None."""
		found = {n: fx.find_defs(self.root_dir, n) for n in names}
		dup = {n: d for n, d in found.items() if len(d) > 1}
		if not dup:
			ask(self, "🔧 Fix it", "These are each defined once now - fixed since this run:\n\n" + ", ".join(names))
			return None
		picks = {n: tk.IntVar(value=0) for n in dup}

		def body(f):
			done = [n for n in names if n not in dup]
			if done:
				ttk.Label(f, text="Already fixed since this run: " + ", ".join(done), style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
			for n, defs in dup.items():
				ttk.Label(f, text=f"{n}  -  {len(defs)} definitions" + ("  (all the same)" if fx.same_defs(defs) else "  (they differ!)"),
						  font="om_bold").pack(anchor="w", pady=(10, 2))
				for i, d in enumerate(defs):
					ttk.Radiobutton(f, text=f"Keep {d['file']}:{d['start'] + 1}", variable=picks[n], value=i).pack(anchor="w")
					tk.Label(f, text=d["text"].strip()[:300], font=("Consolas", max(8, round(9 * ui.scale()))), justify="left", anchor="w",
							 background=ui.P["surface"], foreground=ui.P["foreground"], padx=6).pack(fill="x", padx=(24, 0), pady=(0, 2))
		if not ask(self, "🔧 Duplicate ideas", "Keep one definition of each; the others are commented out (a note says which one stays).",
				   (("Cancel", False), ("Remove the duplicates", True)), extra=body):
			return None
		changed = []
		for n, defs in dup.items():
			keep = defs[picks[n].get()]
			changed += fx.remove_defs(self.root_dir, [d for d in defs if d is not keep], keep)
		return list(dict.fromkeys(changed)), f"🔧 Duplicates of {', '.join(dup)} removed."

	def record_fix(self, cur, fix, changed):
		"""A 🔧 fix that changed files: the error leaves the lists and goes in ✅ Recently fixed (its task completes)."""
		if cur[0] == "lint":
			self.mark_fixed(cur[1]["key"], cur[1]["message"], changed)
		elif cur[0] == "dupe":
			self.mark_fixed(f"dupe:{cur[1]}", f"{cur[1]} - in more than one localisation file", changed)
		elif cur[0] == "log":
			_, kind, pattern, rows = cur
			part = self.current_part()
			if fix == "ideas" and part:
				self.mark_fixed(sig(kind, pattern, part), f"Duplicate idea: {part.split('  (')[0]}", changed)
			self.find_fixed()  # (the whole error, when every part of it is done; the tokens' total with them)
			if fix == "tokens" and sig(kind, pattern) not in self.fixed_now:
				self.mark_fixed(sig(kind, pattern), pattern, changed)

	# ---------- other actions ----------
	def open_it(self):
		f, line = self.where()
		if f and not open_file(self.root_dir, f, line):
			ask(self, "🐞 Error Log Master", f"{f} isn't in the mod (a base-game file?).")

	def make_task(self):
		"""➕ A Bug task for this error (once: its link), given to whoever last changed the file."""
		todo, cur = self.todo, self.cur
		title, text = self.help()[:2]
		if cur[0] == "log":
			_, kind, pattern, rows = cur
			link, name = self.link_for(cur), pattern
			note = f"From the game's {', '.join(sorted({r['log'] for r in rows}))} ({kind}), {len(rows)} time(s):\n" + "\n".join(r["msg"] for r in rows[:15])
		elif cur[0] == "dupe":
			link, name = self.link_for(cur), f"{cur[1]} is in {len(cur[2])} localisation files"
			note = "\n".join(f"{f}: \"{v}\"" for f, v in cur[2])
		else:
			p = cur[1]
			link, name = self.link_for(cur), p["message"]
			note = f"Error Log Master's mod check ({p['check']}):\n{p['message']}\n{p['file']}, line {p['line']}"
		have = todo.linked(link)
		if have:
			self.app.show_page("To Do Master")
			todo.show_task(have["ref"])
			return self.status.config(text=f"🐞 There's already a task for this: {have['ref']}.")
		f, line = self.where()
		if f:
			note += f"\n\nFile: {f}" + (f", line {line}" if line else "")
		note += f"\n\n💡 {title}: {text}"
		who = last_changer(self.root_dir, f) if f else ""
		dev = next((d["name"] for d in todo.data["devs"] if who and who.casefold() in {d["name"].casefold(), (d.get("git") or "").casefold()}), None)
		t = todo.add_task(f"Fix: {name[:90]}", category="Bug", link=link, setter_note=note + "\n\n(Made in 🐞 Error Log Master.)",
						  devs=[dev] if dev else [], error_source="check" if cur[0] == "lint" else "log")  # (completed when it's gone from there)
		todo.save()
		todo.fill_filters()
		todo.fill()
		getattr(self.app, "feedback", lambda *_: None)("new_task")
		self.fill()  # (the row shows ➕ RR-....)
		self.status.config(text=f"➕ {t['ref']} made" + (f", given to {dev} (last changed {f})" if dev else " (in the General To Do)") + ".")

	def hide(self):
		"""🙈 A log pattern hidden / an error dismissed, for everyone, with why (accepted: intentional, a base-game leftover...)
		- or brought back."""
		cur = self.cur
		bring_back = (cur[0] == "log" and self.hidden(cur[1], cur[2])) or (cur[0] != "log" and self.item_key() in self.dismissed())
		reason, note = tk.StringVar(value=REASONS[0]), tk.StringVar()
		if not bring_back:
			def body(f):
				for r in REASONS:
					ttk.Radiobutton(f, text=r, variable=reason, value=r).pack(anchor="w", pady=(2, 0))
				ttk.Label(f, text="A note (optional):").pack(anchor="w", pady=(8, 0))
				ttk.Entry(f, textvariable=note, width=60).pack(fill="x")
			if not ask(self, "🙈 Accept it", "Hidden for everyone - say why, so the others know it's on purpose.", (("Cancel", False), ("Accept", True)), extra=body):
				return
		why = {"reason": reason.get(), "note": note.get().strip()}
		if cur[0] == "log":
			_, kind, pattern, _ = cur
			noise = self.noise()
			if self.hidden(kind, pattern):
				noise[:] = [n for n in noise if not (n.get("kind") == kind and n.get("pattern") == pattern)]
			else:
				noise.append(dict({"kind": kind, "pattern": pattern, "by": self.todo.me.get(), "when": datetime.date.today().isoformat()}, **why))
		else:
			dis, key = self.dismissed(), self.item_key()
			if key in dis:
				dis.pop(key)
			else:
				dis[key] = dict({"by": self.todo.me.get(), "when": datetime.date.today().isoformat()}, **why)
		self.todo.save()
		self.fill()

	def spelling_changed(self):
		"""The team's English (shared): British flags American spellings, American the other way round."""
		self.todo.data["loc_spelling"] = self.spelling_var.get()
		self.todo.save()
		self.spell = fx.spelling(self.root_dir, self.spelling_var.get())
		self.fill()
		self.tabs.select(1)

	def close(self):
		self.app.error_log_window = None
		self.destroy()


def show(app):
	"""The one Error Log Master window (brought to the front if it's open)."""
	w = getattr(app, "error_log_window", None)
	if w is not None and w.winfo_exists():
		w.deiconify()
		w.lift()
		return w
	app.error_log_window = ErrorLogMaster(app)
	return app.error_log_window
