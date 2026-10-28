"""🤔 Potential Unintentional Outcomes: script that works (no error anywhere) but probably doesn't do what was meant -
focuses on the same spot, a mutually exclusive written on one side only, events that fire for everyone by themselves,
a tag's decision every country can see, every_country with no limit, placeholder or copy-pasted text...
Part of the mod check (mod_lint.run): each problem has tab = "outcome" and shows in Error Log Master's own tab; 🙈 Accept
(Intentional) marks the ones that are meant. The explanations are in error_fixes.HELP (by check name)."""
import os
import re
from collections import defaultdict

FOCUS_SPOT = "Focuses on the same spot"
ONE_SIDED = "Mutually exclusive on one side only"
EMPTY_FOCUS = "Focuses that do nothing"
NEVER = "Can never be taken"
SELF_FIRING = "Events that fire by themselves for everyone"
REPEATING = "Events that can repeat forever"
SAME_OPTION = "Event options with the same text"
TAG_DECISION = "A tag's decision every country can see"
NO_LIMIT = "Loops over everything with no limit"
EMPTY_LIMIT = "An empty limit"
PLACEHOLDER = "Placeholder text"
COPY_TEXT = "Copy-pasted text"
CHECKS = (FOCUS_SPOT, ONE_SIDED, EMPTY_FOCUS, NEVER, SELF_FIRING, REPEATING, SAME_OPTION, TAG_DECISION, NO_LIMIT, EMPTY_LIMIT,
		  PLACEHOLDER, COPY_TEXT)

BIG_EFFECTS = re.compile(r"\b(declare_war_on|annex_country|puppet|create_wargoal|transfer_state|set_state_owner|add_state_core|"
						 r"set_politics|add_ideas|white_peace|kill_country_leader|set_capital|add_state_claim|"
						 r"set_cosmetic_tag|destroy_unit|delete_unit|remove_state_core|release|start_civil_war)\b")
LOOPS = re.compile(r"\b(every_country|every_other_country|every_state|every_neighbor_country)\s*=\s*\{")
PLACEHOLDER_RX = re.compile(r"\b(TODO|FIXME|PLACEHOLDER|lorem ipsum|insert (?:text|description) here)\b|^\s*WIP\b|\bWIP\s*$", re.I)


def close(t, i):
	"""The index of the } closing the block whose inside starts at i (just after its {)."""
	d = 1
	while i < len(t):
		c = t[i]
		if c == "{":
			d += 1
		elif c == "}":
			d -= 1
			if d == 0:
				return i
		i += 1
	return len(t)


def blocks(t, start, end, name):
	"""[(match start, inside start, inside end)] of name = { ... } directly inside t[start:end] (depth 1 of it)."""
	out, d, i = [], 0, start
	rx = re.compile(r"\{|\}|\b(" + name + r")\s*=\s*\{")
	while True:
		m = rx.search(t, i, end)
		if not m:
			return out
		if m.group(1):
			if d == 0:
				e = close(t, m.end())
				out.append((m.start(), m.end(), e))
				i = e + 1
				continue
			d += 1
		elif m.group() == "{":
			d += 1
		else:
			d -= 1
		i = m.end()


def value(t, s, e, name):
	"""name = x directly inside t[s:e] (not in a block within it)."""
	d, i = 0, s
	rx = re.compile(r"\{|\}|\b" + re.escape(name) + r"\s*=\s*([\w.\-@]+)")
	while True:
		m = rx.search(t, i, e)
		if not m:
			return None
		if m.group() == "{":
			d += 1
		elif m.group() == "}":
			d -= 1
		elif d == 0:
			return m.group(1)
		i = m.end()


def line_of(t, i):
	return t.count("\n", 0, i) + 1


def issue(check, file, line, message, key, word=None):
	return dict(check=check, file=file, line=line, message=message, key=f"outcome:{key}", tab="outcome", word=word)


# ---------- focus trees ----------
def focus_checks(texts):
	out = []
	focuses = {}  # id -> (file, line, mutually exclusive ids)
	for r, t in texts.items():
		if not r.startswith("common/national_focus/"):
			continue
		for fs, s, e in blocks(t, 0, len(t), "focus_tree|shared_focus|joint_focus"):
			tree = value(t, s, e, "id") or os.path.basename(r)
			items = blocks(t, s, e, "focus") if t[fs:s].startswith("focus_tree") else [(fs, s, e)]
			pos = {}
			for a, b, c in items:
				fid = value(t, b, c, "id")
				if not fid:
					continue
				line = line_of(t, a)
				excl = set()
				for _, ms, me in blocks(t, b, c, "mutually_exclusive"):
					excl |= set(re.findall(r"\bfocus\s*=\s*([\w.\-]+)", t[ms:me]))
				focuses[fid] = (r, line, excl)
				body = t[b:c]
				x, y = value(t, b, c, "x"), value(t, b, c, "y")
				if t[fs:s].startswith("focus_tree") and x is not None and y is not None and not re.search(r"\boffset\s*=\s*\{", body):
					try:
						pos[fid] = (int(x), int(y), value(t, b, c, "relative_position_id"), r, line)
					except ValueError:
						pass
				reward = blocks(t, b, c, "completion_reward")
				if not reward and not re.search(r"\b(select_effect|complete_tooltip)\s*=", body) or reward and not t[reward[0][1]:reward[0][2]].strip():
					out.append(issue(EMPTY_FOCUS, r, line, f"Focus {fid} has no completion_reward: completing it does nothing", f"emptyfocus:{fid}", fid))
				for _, av, ae in blocks(t, b, c, "available"):
					if re.fullmatch(r"\s*always\s*=\s*no\s*", t[av:ae]) and not re.search(r"\bbypass\s*=\s*\{", body):
						out.append(issue(NEVER, r, line, f"Focus {fid}: available = {{ always = no }} and no bypass - it can never be taken",
										 f"never:{fid}", fid))
			# (where each focus really is: x / y are counted from its relative_position_id's place)
			done = {}

			def where(fid, seen=()):
				if fid in done:
					return done[fid]
				if fid not in pos or fid in seen:
					return None
				x, y, rel_id, *_ = pos[fid]
				if rel_id:
					base = where(rel_id, seen + (fid,))
					if base is None:
						return None
					x, y = x + base[0], y + base[1]
				done[fid] = (x, y)
				return done[fid]
			spots = defaultdict(list)
			for fid in pos:
				p = where(fid)
				if p is not None:
					spots[p].append(fid)
			for (x, y), ids in spots.items():
				if len(ids) > 1:
					r_, line = pos[ids[1]][3], pos[ids[1]][4]
					out.append(issue(FOCUS_SPOT, r_, line, f"{' and '.join(ids[:4])} sit on the same spot ({x}, {y}) in {tree} - one hides the other",
									 f"spot:{tree}:{x}:{y}", ids[1]))
	seen_pairs = set()
	for fid, (r, line, excl) in focuses.items():
		for other in sorted(excl):
			if other not in focuses or fid in focuses[other][2]:
				continue
			pair = tuple(sorted((fid, other)))
			if pair in seen_pairs:
				continue
			seen_pairs.add(pair)
			out.append(issue(ONE_SIDED, r, line, f"{fid} is mutually exclusive with {other}, but {other} doesn't say so back - "
								 f"{other} can still be taken after {fid}", f"onesided:{pair[0]}:{pair[1]}", other))
	return out


# ---------- events ----------
EVENT_BLOCK = r"country_event|news_event|state_event|unit_leader_event|operative_leader_event"


def event_checks(texts):
	out = []
	for r, t in texts.items():
		if not r.startswith("events/"):
			continue
		for a, s, e in blocks(t, 0, len(t), EVENT_BLOCK):
			eid = value(t, s, e, "id")
			if not eid:
				continue
			line = line_of(t, a)
			triggered = value(t, s, e, "is_triggered_only") == "yes"
			mtth = blocks(t, s, e, "mean_time_to_happen")
			trig = blocks(t, s, e, "trigger")
			if mtth and not triggered:
				if not trig or not t[trig[0][1]:trig[0][2]].strip():
					out.append(issue(SELF_FIRING, r, line, f"{eid} has mean_time_to_happen and no trigger: it fires by itself for every country",
									 f"selffire:{eid}", eid))
				elif value(t, s, e, "fire_only_once") != "yes" and not re.search(r"\bhas_(?:country|global|state)_flag\b|\bhas_variable\b|\bhas_idea\b",
																			 t[trig[0][1]:trig[0][2]]):
					out.append(issue(REPEATING, r, line, f"{eid} fires by itself (mean_time_to_happen), isn't fire_only_once and its trigger "
										 "checks no flag - it can happen again and again", f"repeat:{eid}", eid))
			names = defaultdict(list)
			for oa, os_, oe in blocks(t, s, e, "option"):
				n = value(t, os_, oe, "name")
				if n:
					names[n].append(line_of(t, oa))
			for n, lines in names.items():
				if len(lines) > 1:
					out.append(issue(SAME_OPTION, r, lines[1], f"{eid}: {len(lines)} options are all called {n} - they show the same text",
									 f"sameoption:{eid}:{n}", n))
	return out


# ---------- decisions ----------
def decision_checks(texts):
	out = []
	cats = {}
	for r, t in texts.items():
		if r.startswith("common/decisions/categories/"):
			for a, s, e in blocks(t, 0, len(t), r"[\w\-]+"):
				cats[re.match(r"[\w\-]+", t[a:s]).group()] = t[s:e]
	for r, t in texts.items():
		if not r.startswith("common/decisions/") or r.startswith("common/decisions/categories/"):
			continue
		for a, s, e in blocks(t, 0, len(t), r"[\w\-]+"):
			cat = re.match(r"[\w\-]+", t[a:s]).group()
			for da, ds, de in blocks(t, s, e, r"[\w\-]+"):
				name = re.match(r"[\w\-]+", t[da:ds]).group()
				m = re.match(r"([A-Z][A-Z0-9]{2})_", name)
				if not m:
					continue
				tag = m.group(1)
				body, cbody = t[ds:de], cats.get(cat, "")
				if re.search(r"\b" + tag + r"\b", body + cbody) or re.search(r"\b(original_tag|tag)\s*=", body + cbody) \
						or re.search(r"\ballowed\s*=\s*\{", body + cbody):
					continue
				out.append(issue(TAG_DECISION, r, line_of(t, da), f"{name} looks like {tag}'s decision, but nothing in it or its "
									 f"category ({cat}) checks for {tag}: every country can see it", f"tagdecision:{name}", name))
	return out


# ---------- script ----------
def script_checks(texts):
	out = []
	for r, t in texts.items():
		if not r.endswith(".txt"):
			continue
		for m in LOOPS.finditer(t):
			e = close(t, m.end())
			inside = t[m.end():e]
			if blocks(t, m.end(), e, "limit"):
				continue
			big = BIG_EFFECTS.search(inside)
			if big:
				out.append(issue(NO_LIMIT, r, line_of(t, m.start()), f"{m.group(1)} with no limit does {big.group(1)} - to every one of them",
								 f"nolimit:{r}:{line_of(t, m.start())}", m.group(1)))
		for m in re.finditer(r"\blimit\s*=\s*\{\s*\}", t):
			out.append(issue(EMPTY_LIMIT, r, line_of(t, m.start()), "limit = { } is empty: it lets everything through",
							 f"emptylimit:{r}:{line_of(t, m.start())}", "limit"))
	return out


# ---------- text ----------
def game_text(game, name):
	"""{key: text} of the base game's English file with this name (the mod's copy of it: its unchanged lines are Paradox's)."""
	out = {}
	if not game:
		return out
	for base, _, names in os.walk(os.path.join(game, "localisation")):
		if name in names:
			try:
				for l in open(os.path.join(base, name), encoding="utf-8-sig", errors="replace"):
					m = re.match(r'^\s*([\w.\-]+):\d*\s*"(.*)"\s*$', l)
					if m:
						out[m.group(1)] = m.group(2)
			except OSError:
				pass
	return out


def text_checks(root, game=None):
	out = []
	same = defaultdict(list)
	folder = os.path.join(root, "localisation")
	rx = re.compile(r'^\s*([\w.\-]+):\d*\s*"(.*)"\s*$')
	for base, _, names in os.walk(folder):
		for n in names:
			if not (n.endswith(".yml") and "english" in n.lower()) or "replace" in base.replace("\\", "/").split("/"):
				continue
			path = os.path.join(base, n)
			r = os.path.relpath(path, root).replace("\\", "/")
			try:
				lines = open(path, encoding="utf-8-sig", errors="replace").read().splitlines()
			except OSError:
				continue
			paradox = game_text(game, n)  # (a copied game file: its unchanged texts are Paradox's, not the mod's)
			for i, l in enumerate(lines):
				m = rx.match(l)
				if not m:
					continue
				key, val = m.group(1), m.group(2)
				if paradox.get(key) == val:
					continue
				hit = PLACEHOLDER_RX.search(val)
				if hit:
					a, b = max(0, hit.start() - 30), hit.end() + 30
					out.append(issue(PLACEHOLDER, r, i + 1, f"{key}: \"{'...' if a else ''}{val[a:b]}{'...' if b < len(val) else ''}\" - "
									 f"\"{hit.group().strip()}\" left in text the players see", f"placeholder:{key}", hit.group().strip()))
				norm = re.sub(r"\s+", " ", val).strip().lower()
				if len(norm) >= 80 and "$" not in norm:
					same[norm].append((key, r, i + 1))
	for norm, keys in same.items():
		keys = list(dict.fromkeys(keys))
		stems = {re.sub(r"_?\d+$", "", re.sub(r"(_desc|_d|\.d|\.t|_title|_tt|_short)$", "", k)) for k, _, _ in keys}
		if len(keys) > 1 and len(stems) > 1:
			k, r, line = keys[1]
			out.append(issue(COPY_TEXT, r, line, f"{k} has exactly the same text as {keys[0][0]}" + (f" (+{len(keys) - 2} more)" if len(keys) > 2 else "")
							 + f": \"{norm[:60]}...\"", f"copytext:{k}", k))
	return out


def run(root, clean, progress=lambda text: None, game=None):
	"""Every 🤔 check over the mod's files (clean: {path: text without comments}, as mod_lint reads them)."""
	progress("looking for things that might not be meant...")
	texts = {os.path.relpath(p, root).replace("\\", "/"): t for p, t in clean.items()}
	out = []
	for check in (focus_checks, event_checks, decision_checks, script_checks):
		try:
			out += check(texts)
		except Exception:
			continue
	try:
		out += text_checks(root, game)
	except Exception:
		pass
	return out
