"""🐞 Error Log Master's "Not in the log" checks: problems in the mod's files the game only reports when it trips over
them in play, or never (it silently skips them). No Tk here: run(...) runs in a thread.

Each problem: {check, file (mod-relative), line, message, key (the same problem on every run: "new since last time")}.
- Braces: { } that don't add up in a script / GUI file (one missing } quietly swallows everything after it).
- Events called but never written (events/ is a replace_path: the base game's events aren't there).
- GFX_ sprites used but never defined (in the mod's or the game's interface/*.gfx).
- Localisation files: the UTF-8 BOM HOI4 needs, the l_english: header, malformed lines, keys defined twice.
- Missing localisation: national focuses, event titles / descriptions.
- References to things that don't exist: flags checked but never set, ideas / country tags / characters / focuses used
  but never defined, decision categories never defined, spriteType texture files that aren't there, event namespaces
  never declared; and things defined twice (focus ids, event ids, ideas). The base game's own definitions count unless the
  mod replaces that folder (its descriptor.mod's replace_path). A name that doesn't exist gets the closest real ones
  (suggest: "did you mean"), and one in a file the mod copied from the base game is marked (leftover).
- The map: provinces in no state or in two, states with provinces the map doesn't have, state ids used twice, provinces
  in no strategic region or in two, victory points outside their state, supply nodes / railways on unknown provinces.
- Culture data (RR's culture system): Culture Master's own Check for problems.
- Performance hints: every_state / every_country loops inside each other, on_daily on_actions, 24-bit flags.
"""
import difflib
import os
import re
from collections import defaultdict

SCRIPT_DIRS = ("common", "events", "history", "interface")
SCRIPT_EXT = (".txt", ".gui", ".gfx")
EVENT_TYPES = r"(?:country|news|state|unit_leader|operative_leader)_event"
_GAME_CACHE = {}  # (the base game's definitions, read once per folder: checking many mods in a row)


def rel(root, path):
	return os.path.relpath(path, root).replace("\\", "/")


def read(path):
	with open(path, encoding="utf-8-sig", errors="replace") as f:
		return f.read()


def strip_comments(text):
	"""# to the end of the line goes (outside "strings"); line numbers stay the same."""
	out = []
	for line in text.split("\n"):
		if "#" in line:
			q = False
			for i, ch in enumerate(line):
				if ch == '"':
					q = not q
				elif ch == "#" and not q:
					line = line[:i]
					break
		out.append(line)
	return "\n".join(out)


def files(root, dirs, exts):
	for d in dirs:
		for base, _, names in os.walk(os.path.join(root, d)):
			for n in names:
				if n.lower().endswith(exts):
					yield os.path.join(base, n)


TOKEN = re.compile(r'"[^"\n]*"|[{}]|\n')


def braces(path, text, root):
	"""Unclosed { (where it opened) or a } too many (where)."""
	stack, line, out = [], 1, []
	for m in TOKEN.finditer(strip_comments(text)):
		t = m.group()
		if t == "\n":
			line += 1
		elif t == "{":
			stack.append(line)
		elif t == "}":
			if stack:
				stack.pop()
			else:
				out.append(dict(check="Braces", file=rel(root, path), line=line, message="A } too many (nothing open to close)"))
	if stack:
		out.append(dict(check="Braces", file=rel(root, path), line=stack[0],
						message=f"{len(stack)} {{ never closed - the first one opens here (everything after it may be swallowed)"))
	return out


def replaced_paths(root):
	"""The folders the mod replaces (its descriptor.mod's replace_path): the base game's files there don't count."""
	try:
		text = read(os.path.join(root, "descriptor.mod"))
	except OSError:
		return set()
	return {m.strip("/").lower() for m in re.findall(r'^\s*replace_path\s*=\s*"([^"]+)"', text, re.M)}


def game_texts(game, folder, exts=(".txt",)):
	"""{path: comment-free text} of the base game's folder (cached)."""
	key = (game, folder, exts)
	if key not in _GAME_CACHE:
		out = {}
		for p in files(game, (folder,), exts) if game else []:
			try:
				out[p] = strip_comments(read(p))
			except OSError:
				continue
		_GAME_CACHE[key] = out
	return _GAME_CACHE[key]


KEY_OPEN = re.compile(r'([\w.\-@:\[\]$]+)\s*=\s*\{|\{|\}|\n')


def keys_at(text, depth, pos=False):
	"""[(key, line)] of the blocks key = { that open at this depth (0: the file's top level); pos: (key, line, where the
	block's inside starts)."""
	out, d, line = [], 0, 1
	for m in KEY_OPEN.finditer(text):
		t = m.group()
		if t == "\n":
			line += 1
		elif t == "}":
			d = max(0, d - 1)
		else:
			if m.group(1) and d == depth:
				out.append((m.group(1), line, m.end()) if pos else (m.group(1), line))
			d += 1
	return out


def field(text, start, name):
	"""The value of name = x directly inside the block whose inside starts at start (not in a block within it), or None."""
	d, i = 1, start
	rx = re.compile(r"\{|\}|\b" + re.escape(name) + r"\s*=\s*([\w.\-]+)")
	while d > 0:
		m = rx.search(text, i)
		if not m:
			return None
		if m.group() == "{":
			d += 1
		elif m.group() == "}":
			d -= 1
		elif d == 1:
			return m.group(1)
		i = m.end()
	return None


IDEA_FIELDS = {"allowed", "allowed_civil_war", "allowed_to_remove", "visible", "available", "modifier", "targeted_modifier",
			   "research_bonus", "equipment_bonus", "rule", "on_add", "on_remove", "cancel", "do_effect", "traits", "ai_will_do",
			   "name", "picture", "cost", "removal_cost", "level", "ledger", "law", "designer", "use_list_view", "default"}


def dlc_files(game):
	"""The base game's files packed in its dlc/*.zip (some DLC pictures only live there), lower-case paths."""
	key = (game, "dlc zips")
	if key not in _GAME_CACHE:
		import zipfile
		names = set()
		for base, _, fs in os.walk(os.path.join(game, "dlc")) if game else []:
			for f in fs:
				if f.lower().endswith(".zip"):
					try:
						names |= {n.lower() for n in zipfile.ZipFile(os.path.join(base, f)).namelist()}
					except (OSError, zipfile.BadZipFile):
						continue
		_GAME_CACHE[key] = names
	return _GAME_CACHE[key]


def where(t, m):
	return t.count("\n", 0, m.start()) + 1


def suggester(known):
	"""name -> up to 3 real names that look like it (only names that start alike and are about as long are compared: fast
	on 20,000 names)."""
	by = defaultdict(list)
	for k in known:
		by[k[:2].lower()].append(k)

	def suggest(name):
		pool = [k for k in by.get(name[:2].lower(), ()) if abs(len(k) - len(name)) <= 4]
		lower = {k.lower(): k for k in pool}
		got = difflib.get_close_matches(name.lower(), list(lower), n=3, cutoff=0.82)
		digits = lambda x: re.sub(r"\d+", "#", x.lower())  # (news.41 vs news.42: another one of a numbered set, not a typo)
		return [lower[g] for g in got if digits(g) != digits(name)]
	return suggest


DYNAMIC = re.compile(r"[@\[\]$]|_$|^(?:yes|no|THIS|ROOT|FROM|PREV|OWNER|CONTROLLER)$")


def references(root, game, clean, replaced, progress):
	"""Things used that don't exist, and things defined twice."""
	out = []
	mod = {rel(root, p): t for p, t in clean.items()}

	def folder(name, exts=(".txt",)):
		"""[(file label, text)] of the mod's folder, plus the base game's when the mod doesn't replace it."""
		own = [(r, t) for r, t in mod.items() if r.startswith(name + "/") and r.endswith(exts)]
		if game and name.lower() not in replaced and not any(name.lower().startswith(x + "/") for x in replaced):
			own += [("<game>/" + os.path.relpath(p, game).replace("\\", "/"), t) for p, t in game_texts(game, name, exts).items()]
		return own

	def report(check, found, message, known=None, name_in_message=True):
		"""One problem per name; known: the real names (the closest become "did you mean"); a file the base game has too
		(copied into the mod) makes it a leftover."""
		suggest = suggester(known) if known else None
		for name, (r, line) in sorted(found.items()):
			p = dict(check=check, file=r, line=line, message=message(name), key=f"{check}:{name}", name=name)
			if suggest:
				p["suggest"] = suggest(name)
			if game and not r.startswith("<game>") and os.path.isfile(os.path.join(game, r)):
				p["leftover"] = True
				p["message"] += "  (in a file the mod copied from the base game)"
			out.append(p)

	# ---- flags checked but never set ----
	progress("matching flags...")
	kinds = ("country", "global", "state", "character", "unit_leader")
	set_ = {k: set() for k in kinds}
	checked = {k: {} for k in kinds}
	sources = list(mod.items())
	for name in ("common", "events", "history"):
		if game and name not in replaced:
			sources += [("<game>", t) for t in game_texts(game, name).values()]
	for r, t in sources:
		for m in re.finditer(r"\b(set|clr|modify)_(country|global|state|character|unit_leader)_flag\s*=\s*(?:\{[^{}]*?\bflag\s*=\s*)?([\w.\-@\[\]$]+)", t):
			set_[m.group(2)].add(m.group(3))
		if r == "<game>":
			continue
		for m in re.finditer(r"\bhas_(country|global|state|character|unit_leader)_flag\s*=\s*(?:\{[^{}]*?\bflag\s*=\s*)?([\w.\-@\[\]$]+)", t):
			checked[m.group(1)].setdefault(m.group(2), (r, where(t, m)))
	for k in kinds:
		made = [re.compile("^" + ".+".join(re.escape(x) for x in re.split(r"@[\w.]*|\[[^\]]*\]|\$[^$]*\$", f)) + "$")
				for f in set_[k] if DYNAMIC.search(f)]
		missing = {f: w for f, w in checked[k].items() if f not in set_[k] and not DYNAMIC.search(f)
				   and not any(rx.match(f) for rx in made)}  # (set_country_flag = X_@ROOT makes X_GER...)
		report("Flags checked but never set", missing, lambda f, k=k: f"{k.replace('_', ' ')} flag {f} is checked but nothing ever sets it (a typo, or it was removed)",
			   known={f for f in set_[k] if not DYNAMIC.search(f)})
	# ---- ideas used but not defined; ideas defined twice ----
	progress("matching ideas...")
	ideas, idea_at = set(), defaultdict(list)
	for r, t in folder("common/ideas"):
		for k, line in keys_at(t, 2):
			if k in IDEA_FIELDS:
				continue  # (a field of an idea: the file's braces are off - Braces says where)
			ideas.add(k)
			if not r.startswith("<game>"):
				idea_at[k].append((r, line))
	for r, t in folder("common/characters"):
		ideas |= set(re.findall(r"\bidea_token\s*=\s*([\w\-]+)", t))  # (advisors are added like ideas)
	used = {}
	for r, t in mod.items():
		for m in re.finditer(r"\b(?:add_ideas|remove_ideas|has_idea|add_idea|remove_idea|idea)\s*=\s*(\{[^{}]*\}|[\w\-]+)", t):
			for name in re.findall(r"[\w\-]+", m.group(1)):
				if name not in ideas and not DYNAMIC.search(name) and name not in ("days", "idea", "yes", "no"):
					used.setdefault(name, (r, where(t, m)))
	report("Ideas used but never defined", used, lambda n: f"Idea {n} is added / checked here but no common/ideas file defines it", known=ideas)
	for k, at in idea_at.items():
		if len(at) > 1:
			out.append(dict(check="Defined twice", file=at[1][0], line=at[1][1], key=f"idea2:{k}",
							message=f"Idea {k} is defined again here (also {at[0][0]}:{at[0][1]}) - the game keeps one"))
	# ---- country tags used but not defined ----
	progress("matching country tags...")
	tags = set()
	for r, t in folder("common/country_tags"):
		tags |= set(re.findall(r"^\s*([A-Z][A-Z0-9]{2})\s*=", t, re.M))
	if tags:
		used = {}
		for r, t in mod.items():
			for m in re.finditer(r"\b(?:tag|original_tag|country_exists|exists|is_subject_of|is_puppet_of|has_war_with|is_in_faction_with)\s*=\s*([A-Z][A-Z0-9]{2})\b", t):
				tg = m.group(1)
				if tg not in tags and not re.fullmatch(r"D\d\d|TAG|THE|AND|NOT|ALL|ANY", tg):
					used.setdefault(tg, (r, where(t, m)))
		report("Country tags used but never defined", used, lambda tg: f"{tg} isn't a country tag (common/country_tags) - a typo or a removed country")
	# ---- characters used but not defined ----
	progress("matching characters...")
	chars = set()
	for r, t in folder("common/characters"):
		chars |= {k for k, _ in keys_at(t, 1)}
	if chars:
		used = {}
		lower = {c.lower() for c in chars}  # (the game matches character ids whatever the capitals: big mods rely on it)
		for r, t in mod.items():
			for m in re.finditer(r"\b(?:recruit_character|has_character|promote_character|retire_character|character)\s*=\s*([A-Za-z][\w\-]+)\b", t):
				c = m.group(1)
				if c.lower() not in lower and not DYNAMIC.search(c):
					used.setdefault(c, (r, where(t, m)))
		report("Characters used but never defined", used, lambda c: f"Character {c} is used here but no common/characters file defines it", known=chars)
	# ---- focuses: used but missing, defined twice ----
	progress("matching national focuses...")
	focuses, focus_at = set(), defaultdict(list)
	for r, t in folder("common/national_focus"):
		for m in re.finditer(r"\b(?:focus|shared_focus|joint_focus)\s*=\s*\{", t):
			fid = field(t, m.end(), "id")
			if fid:
				focuses.add(fid)
				if not r.startswith("<game>"):
					focus_at[fid].append((r, where(t, m)))
	if focuses:
		used = {}
		for r, t in mod.items():
			for m in re.finditer(r"\b(?:has_completed_focus|complete_national_focus|unlock_national_focus|focus_progress|has_focus_tree|is_focus_selected)\s*=\s*([\w\-]+)", t):
				f = m.group(1)
				if f not in focuses and not DYNAMIC.search(f) and "focus_tree" not in m.group(0):
					used.setdefault(f, (r, where(t, m)))
			if r.startswith("common/national_focus/"):
				for block in re.finditer(r"\b(?:prerequisite|mutually_exclusive)\s*=\s*\{([^{}]*)\}", t):
					for f in re.findall(r"\bfocus\s*=\s*([\w\-]+)", block.group(1)):
						if f not in focuses:
							used.setdefault(f, (r, where(t, block)))
		report("Focuses used but never defined", used, lambda f: f"Focus {f} is used here (prerequisite / completed / ...) but no focus has that id", known=focuses)
	for f, at in focus_at.items():
		if len(at) > 1:
			out.append(dict(check="Defined twice", file=at[1][0], line=at[1][1], key=f"focus2:{f}",
							message=f"Focus {f} is defined again here (also {at[0][0]}:{at[0][1]})"))
	# ---- events: defined twice, namespaces never declared ----
	progress("checking event ids and namespaces...")
	event_at, spaces = defaultdict(list), set()
	for r, t in mod.items():
		if r.startswith("events/"):
			spaces |= {x.lower() for x in re.findall(r"\badd_namespace\s*=\s*([\w\-]+)", t)}
			for k, line, at in keys_at(t, 0, pos=True):
				if re.fullmatch(EVENT_TYPES, k):
					ev = field(t, at, "id")
					if ev and "." in ev:
						event_at[ev].append((r, line))
	for ev, at in event_at.items():
		if len(at) > 1:
			out.append(dict(check="Defined twice", file=at[1][0], line=at[1][1], key=f"event2:{ev}",
							message=f"Event {ev} is defined again here (also {at[0][0]}:{at[0][1]}) - only one fires"))
	missing = {}
	for ev, at in event_at.items():
		ns = ev.split(".")[0]
		if ns.lower() not in spaces:
			missing.setdefault(ns, at[0])
	report("Event namespaces never declared", missing, lambda ns: f"Events use the namespace {ns} but no events file has add_namespace = {ns}")
	# ---- decision categories never defined ----
	progress("matching decision categories...")
	cats = set()
	for r, t in folder("common/decisions/categories"):
		cats |= {k for k, _ in keys_at(t, 0)}
	if cats:
		used = {}
		for r, t in mod.items():
			if r.startswith("common/decisions/") and not r.startswith("common/decisions/categories/"):
				for k, line in keys_at(t, 0):
					if k not in cats and not DYNAMIC.search(k):
						used.setdefault(k, (r, line))
		report("Decision categories never defined", used, lambda c: f"Decisions are in the category {c}, which common/decisions/categories doesn't define (they don't show)", known=cats)
	# ---- texture files that aren't there ----
	progress("checking spriteType texture files...")
	used = {}
	for r, t in mod.items():
		if r.endswith(".gfx"):
			for m in re.finditer(r'\btexture[Ff]ile\s*=\s*"([^"]+)"', t):
				f = re.sub(r"/+", "/", m.group(1).replace("\\", "/")).lstrip("/")  # (gfx//interface//x.tga is fine)
				stem = os.path.splitext(f)[0]
				options = [f] + [stem + e for e in (".dds", ".tga", ".png") if not f.endswith(e)]  # (the game takes a .dds for a .tga)
				if not any(os.path.isfile(os.path.join(base, o)) for o in options for base in (root, game) if base) and \
						not any(o.lower() in dlc_files(game) for o in options):
					used.setdefault(f, (r, where(t, m)))
	report("Texture files that aren't there", used, lambda f: f"{f} is a spriteType's texturefile but there's no such file (the picture is blank)")
	return out


def map_checks(root, game, replaced, progress):
	"""The map's bookkeeping: provinces, states, strategic regions, victory points, supply nodes, railways."""
	progress("checking the map...")
	out = []

	def pick(rel_path):
		own = os.path.join(root, rel_path)
		return own if os.path.isfile(own) else os.path.join(game, rel_path) if game and os.path.isfile(os.path.join(game, rel_path)) else None
	definition = pick("map/definition.csv")
	if not definition:
		return out
	kinds = {}
	for line in open(definition, encoding="utf-8-sig", errors="replace"):
		parts = line.strip().split(";")
		if len(parts) > 4 and parts[0].isdigit() and int(parts[0]) > 0:
			kinds[int(parts[0])] = parts[4].strip().lower()

	def folder_files(name):
		got = {}
		for base in ([game] if game and name not in replaced else []) + [root]:
			d = os.path.join(base, name)
			for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
				if f.endswith(".txt"):
					got[f] = (os.path.join(d, f), base == root)  # (the mod's file of the same name wins)
		return got
	state_of, state_at, state_ids = {}, {}, defaultdict(list)
	for f, (path, own) in folder_files("history/states").items():
		t = strip_comments(read(path))
		r = rel(root, path) if own else "<game>/history/states/" + f
		m = re.search(r"\bid\s*=\s*(\d+)", t)
		if not m:
			continue
		sid = int(m.group(1))
		state_ids[sid].append(r)
		pm = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", t)
		provs = [int(x) for x in re.findall(r"\d+", pm.group(1))] if pm else []
		state_at[sid] = (r, t.count("\n", 0, pm.start()) + 1 if pm else 1)
		for pv in provs:
			if pv not in kinds:
				out.append(dict(check="Map", file=r, line=state_at[sid][1], key=f"map:noprov:{sid}:{pv}",
								message=f"State {sid} lists province {pv}, which map/definition.csv doesn't have"))
			elif kinds[pv] == "sea":  # (lakes in states are normal: the base game has 118)
				out.append(dict(check="Map", file=r, line=state_at[sid][1], key=f"map:sea:{sid}:{pv}",
								message=f"State {sid} lists province {pv}, which is a sea province on the map"))
			elif pv in state_of and state_of[pv] != sid:
				out.append(dict(check="Map", file=r, line=state_at[sid][1], key=f"map:twice:{pv}",
								message=f"Province {pv} is in state {sid} and also in state {state_of[pv]}"))
			state_of.setdefault(pv, sid)
		for vm in re.finditer(r"\bvictory_points\s*=\s*\{\s*(\d+)", t):
			if int(vm.group(1)) not in provs:
				out.append(dict(check="Map", file=r, line=t.count("\n", 0, vm.start()) + 1, key=f"map:vp:{sid}:{vm.group(1)}",
								message=f"State {sid} has victory points on province {vm.group(1)}, which isn't one of its provinces"))
	for sid, fs in state_ids.items():
		if len(fs) > 1:
			out.append(dict(check="Map", file=fs[1], line=1, key=f"map:sid:{sid}", message=f"State id {sid} is used by {len(fs)} files: {', '.join(fs)}"))
	if state_ids:
		loose = [pv for pv, k in kinds.items() if k == "land" and pv not in state_of]
		if loose:
			out.append(dict(check="Map", file="map/definition.csv", line=1, key="map:stateless",
							message=f"{len(loose)} land provinces are in no state: {', '.join(map(str, loose[:30]))}" + (" ..." if len(loose) > 30 else "")))
	region_of = {}
	for f, (path, own) in folder_files("map/strategicregions").items():
		t = strip_comments(read(path))
		r = rel(root, path) if own else "<game>/map/strategicregions/" + f
		pm = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", t)
		for pv in (int(x) for x in re.findall(r"\d+", pm.group(1))) if pm else ():
			if pv in region_of and region_of[pv] != f:
				out.append(dict(check="Map", file=r, line=t.count("\n", 0, pm.start()) + 1, key=f"map:region2:{pv}",
								message=f"Province {pv} is in two strategic regions ({region_of[pv]} too)"))
			region_of.setdefault(pv, f)
	if region_of:
		loose = [pv for pv, k in kinds.items() if k in ("land", "sea") and pv not in region_of]
		if loose:
			out.append(dict(check="Map", file="map/definition.csv", line=1, key="map:regionless",
							message=f"{len(loose)} provinces are in no strategic region (weather, air, navies): {', '.join(map(str, loose[:30]))}" +
							(" ..." if len(loose) > 30 else "")))
	for name, rx in (("map/supply_nodes.txt", r"^\s*\d+\s+(\d+)"), ("map/railways.txt", None)):
		path = pick(name)
		if not path:
			continue
		r = rel(root, path) if path.startswith(root) else "<game>/" + name
		for n, line in enumerate(open(path, encoding="utf-8-sig", errors="replace"), 1):
			nums = [int(x) for x in line.split()] if line.strip() and not line.strip().startswith("#") and re.fullmatch(r"[\d\s]+", line.strip()) else []
			provs = nums[1:2] if rx else nums[2:]
			bad = [pv for pv in provs if kinds.get(pv) != "land"]
			if bad:
				out.append(dict(check="Map", file=r, line=n, key=f"map:{name}:{n}",
								message=f"{os.path.basename(name)} line {n} uses province(s) {', '.join(map(str, bad))} that aren't land provinces on the map"))
	return out


def culture_checks(root, progress):
	"""RR's culture system: Culture Master's own Check for problems, one problem per line it lists."""
	if not os.path.isfile(os.path.join(root, "common/scripted_effects/RR_culture_scripted_effects.txt")):
		return []
	progress("checking the culture data (Culture Master's check)...")
	try:
		import culture_master as cm
		lines = cm.ModData(root).validate()
	except Exception as ex:
		return [dict(check="Culture data", file="common/scripted_effects/RR_culture_scripted_effects.txt", line=1, key="culture:failed",
					 message=f"Culture Master's check couldn't run: {type(ex).__name__}: {ex}")]
	out, head = [], ""
	for line in lines:
		if not line.strip() or line.startswith("=====") or line.startswith("Every token used"):
			head = line.strip("= ") if line.startswith("=====") else head
			continue
		if not line.startswith("    "):
			head = line.rstrip(":")
			continue
		out.append(dict(check="Culture data", file="common/scripted_effects/RR_culture_scripted_effects.txt", line=1,
						key=f"culture:{head}:{line.strip()}"[:300], message=f"{head}: {line.strip()}"[:400]))
		if len(out) >= 400:
			break
	return out


def performance(root, clean, progress):
	"""Things that slow the game down: loops in loops, daily on_actions, 24-bit flags."""
	progress("looking for slow script...")
	out = []
	loop = re.compile(r"\b(every_country|every_state|every_other_country|all_country|all_state|any_state|any_country|random_state)\s*=\s*\{")
	for p, t in clean.items():
		r = rel(root, p)
		if not r.endswith(".txt"):
			continue
		for m in re.finditer(r"\b(every_country|every_state|every_other_country)\s*=\s*\{", t):
			d, i, inner = 1, m.end(), None
			while d and i < len(t):
				c = t[i]
				if c == "{":
					d += 1
				elif c == "}":
					d -= 1
				i += 1
			inner = loop.search(t, m.end(), i)
			if inner and inner.group(1).startswith(("every_", "all_")) and inner.group(1) != m.group(1) or (inner and inner.group(1) == m.group(1)):
				out.append(dict(check="Performance hints", file=r, line=t.count("\n", 0, m.start()) + 1, key=f"perf:loop:{r}:{m.start()}",
								message=f"{inner.group(1)} inside {m.group(1)}: a loop over everything for each of everything (slow when it runs often)"))
		if r.startswith("common/on_actions/"):
			for m in re.finditer(r"\bon_daily(?:_\w+)?\s*=\s*\{", t):
				out.append(dict(check="Performance hints", file=r, line=t.count("\n", 0, m.start()) + 1, key=f"perf:daily:{r}:{m.start()}",
								message="on_daily runs for every country every day: keep it tiny, or move it to on_weekly / on_monthly"))
	folder = os.path.join(root, "gfx", "flags")
	slow = []
	for base, _, names in os.walk(folder):
		for n in names:
			if n.lower().endswith(".tga"):
				try:
					with open(os.path.join(base, n), "rb") as f:
						head = f.read(18)
					if len(head) == 18 and head[16] == 24:
						slow.append(os.path.relpath(os.path.join(base, n), root).replace("\\", "/"))
				except OSError:
					continue
	for f in slow:
		out.append(dict(check="Performance hints", file=f, line=1, key=f"perf:flag24:{f}", message=f"{os.path.basename(f)} is a 24-bit flag (loads slowly: save it as 32-bit)"))
	return out


def run(root, game=None, progress=lambda text: None):
	problems = []
	replaced = replaced_paths(root)
	scripts = {}
	progress("reading the mod's script files...")
	for p in files(root, SCRIPT_DIRS, SCRIPT_EXT):
		try:
			scripts[p] = read(p)
		except OSError:
			continue
	# ---- braces ----
	progress("checking { } in every file...")
	for p, text in scripts.items():
		problems += braces(p, text, root)
	clean = {p: strip_comments(t) for p, t in scripts.items()}
	# ---- events called but not written ----
	progress("matching events...")
	defined = set()
	for p, t in clean.items():
		if rel(root, p).startswith("events/"):
			defined |= set(re.findall(r"\bid\s*=\s*([\w\-]+\.[\w\-]+)", t))
	if game and "events" not in replaced:  # (the mod keeps the base game's events: those exist too)
		for t in game_texts(game, "events").values():
			defined |= set(re.findall(r"\bid\s*=\s*([\w\-]+\.[\w\-]+)", t))
	ev_suggest = suggester(defined)
	called = defaultdict(list)
	for p, t in clean.items():
		for m in re.finditer(EVENT_TYPES + r"\s*=\s*(?:\{[^{}]*?\bid\s*=\s*)?([A-Za-z_][\w\-]*\.\d+)\b", t):
			called[m.group(1)].append((p, t.count("\n", 0, m.start()) + 1))
	for ev, where in sorted(called.items()):
		if ev not in defined:
			p, line = where[0]
			more = f" (+{len(where) - 1} more places)" if len(where) > 1 else ""
			problems.append(dict(check="Events called but never written", file=rel(root, p), line=line, name=ev,
								 message=f"{ev} is fired here but no event has that id{more}", key=f"event:{ev}", suggest=ev_suggest(ev)))
	# ---- GFX_ sprites used but not defined ----
	progress("matching GFX sprites...")
	sprites = set()
	gfx_files = [p for p in scripts if p.lower().endswith(".gfx")]
	if game:
		gfx_files += list(files(game, ("interface",), (".gfx",)))
	for p in gfx_files:
		try:
			t = clean.get(p) or strip_comments(read(p))
		except OSError:
			continue
		sprites |= {s.lower() for s in re.findall(r'\bname\s*=\s*"?(GFX_[\w\-]+)', t)}
	used = {}
	for p, t in clean.items():
		if p.lower().endswith(".gfx"):
			continue
		for m in re.finditer(r'(?<![\w\[])(GFX_[A-Za-z0-9_\-]+)(?![\w\[\]])', t):
			s = m.group(1)
			if s.endswith("_") or s.lower() in sprites:
				continue  # (GFX_xxx_ + something added in script: can't tell)
			used.setdefault(s, (p, t.count("\n", 0, m.start()) + 1))
	sp_suggest = suggester(sprites)
	for s, (p, line) in sorted(used.items()):
		problems.append(dict(check="GFX sprites used but never defined", file=rel(root, p), line=line, name=s,
							 message=f"{s} isn't a spriteType in any interface/*.gfx (shows as nothing / a missing icon)", key=f"gfx:{s.lower()}",
							 suggest=[x for x in sp_suggest(s.lower())]))
	# ---- localisation files ----
	progress("checking the localisation...")
	loc_keys, first_at = set(), {}
	loc_line = re.compile(r'^\s*([\w.\-\[\]]+):\d*\s*"(.*)"\s*$')
	for p in files(root, ("localisation",), (".yml",)):
		r = rel(root, p)
		try:
			raw = open(p, "rb").read()
		except OSError:
			continue
		if not raw.startswith(b"\xef\xbb\xbf"):
			problems.append(dict(check="Localisation files", file=r, line=1, message="No UTF-8 BOM: HOI4 ignores the whole file"))
		text = raw.decode("utf-8-sig", errors="replace")
		lines = text.split("\n")
		header = next((i for i, l in enumerate(lines) if l.strip() and not l.strip().startswith("#")), None)
		if header is None:
			continue  # (only comments: an empty placeholder)
		if not re.match(r"^\s*l_\w+:\s*$", lines[header].split("#")[0]):
			problems.append(dict(check="Localisation files", file=r, line=(header or 0) + 1,
								 message="The first line isn't l_<language>: (the file is skipped)"))
			continue
		english = "l_english" in lines[header]
		for i, l in enumerate(lines[header + 1:], header + 2):
			s = l.strip()
			if not s or s.startswith("#") or re.match(r"^l_\w+:\s*$", s):  # (a second header line: harmless)
				continue
			body = s
			if body.count('"') >= 2:  # (a # after the closing quote is a comment)
				body = body[:body.rfind('"') + 1]
			m = loc_line.match(body)
			if not m:
				problems.append(dict(check="Localisation files", file=r, line=i, message=f"Malformed line: {s[:80]}"))
				continue
			if english:
				k = m.group(1)
				if k in first_at and first_at[k][0] != r + str(i):
					fr, fl = first_at[k][1]
					problems.append(dict(check="Localisation keys defined twice", file=r, line=i,
										 message=f"{k} is also in {fr}:{fl} (only one of them shows)", key=f"dupeloc:{k}"))
				else:
					first_at[k] = (r + str(i), (r, i))
				loc_keys.add(k)
	if game:
		for p in files(game, ("localisation/english",), (".yml",)):
			try:
				loc_keys |= set(re.findall(r'^\s*([\w.\-]+):\d*\s*"', read(p), re.M))
			except OSError:
				continue
	# ---- missing localisation: focuses, event titles / descriptions ----
	progress("looking for missing localisation...")
	for p, t in clean.items():
		r = rel(root, p)
		if r.startswith("common/national_focus/"):
			for m in re.finditer(r"\b(?:focus|shared_focus|joint_focus)\s*=\s*\{", t):
				k = field(t, m.end(), "text") or field(t, m.end(), "id")
				if k and k not in loc_keys:
					problems.append(dict(check="Missing localisation", file=r, line=t.count("\n", 0, m.start()) + 1,
										 message=f"Focus {k} has no name ({k}: in localisation)", key=f"loc:{k}"))
		elif r.startswith("events/"):
			for m in re.finditer(r'\b(title|desc)\s*=\s*([A-Za-z_][\w.\-]*)\s*(?=\s|$)', t):
				k = m.group(2)
				if k not in loc_keys and "." in k:
					problems.append(dict(check="Missing localisation", file=r, line=t.count("\n", 0, m.start()) + 1,
										 message=f"Event {m.group(1)} {k} has no text", key=f"loc:{k}"))
	problems += references(root, game, clean, replaced, progress)
	problems += map_checks(root, game, replaced, progress)
	problems += culture_checks(root, progress)
	problems += performance(root, clean, progress)
	try:  # (🤔 Potential Unintentional Outcomes: no error, but probably not what was meant)
		import outcome_checks
		problems += outcome_checks.run(root, clean, progress, game)
	except Exception:
		pass
	for x in problems:
		x.setdefault("key", f"{x['check']}:{x['file']}:{x['message']}")
	progress(f"{len(problems)} found.")
	return problems
