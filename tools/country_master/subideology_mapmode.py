"""The Sub-ideology map mode (common/map_modes/mapmode_subideology.txt) kept in step with the sub-ideologies' colours.

Unlike common/ideologies (color = { 69 94 126 }), the map mode takes each channel as a fraction of 255 with two decimals
(set_temp_variable = { red = 0.27 }). A sub-ideology given its own colour (or a new one) is written there too, added in
its ideology's part of the file if it isn't there yet.

Some values show as bright cyan in game. Which ones isn't known in advance, so they're learnt: Country Master > a
sub-ideology > "Shows cyan in game" records its values in mapmode_cyan.json (in git, shared by the team), and every
value written avoids them by the smallest nudge (0.01 at a time)."""
import itertools
import json
import os
import re
import sys

REL = "common/map_modes/mapmode_subideology.txt"
CYAN_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)),
						 "mapmode_cyan.json")  # (next to CountryMaster.exe / this file: tools/country_master, in git)
CHANNELS = ("red", "green", "blue")
RX_HAS = r"^\s*has_country_leader_ideology\s*=\s*{}\s*(?:#.*)?$"


def fractions(rgb):
	"""(69, 94, 126) -> ('0.27', '0.37', '0.49')."""
	return tuple(f"{min(255, max(0, int(c))) / 255:.2f}" for c in rgb)


def load_bad(path=CYAN_FILE):
	"""{'colours': [['0.07', '0.30', '0.55'], ...], 'values': ['0.13', ...]}: whole colours and single channel values
	seen to show cyan."""
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, ValueError):
		data = {}
	return {"colours": [list(c) for c in data.get("colours", [])], "values": list(data.get("values", []))}


def save_bad(bad, path=CYAN_FILE):
	with open(path, "w", encoding="utf-8") as f:
		json.dump({"_note": "Sub-ideology map mode values that show bright cyan in game (Country Master avoids them).",
				   "colours": sorted(bad["colours"]), "values": sorted(set(bad["values"]))}, f, indent=1)


def is_bad(triple, bad):
	return list(triple) in bad["colours"] or any(v in bad["values"] for v in triple)


def safe(triple, bad):
	"""triple, or the nearest one that isn't known to show cyan (one channel 0.01 at a time, then more)."""
	if not is_bad(triple, bad):
		return triple
	base = [round(float(v) * 100) for v in triple]
	steps = sorted(itertools.product(range(-3, 4), repeat=3), key=lambda d: (sum(map(abs, d)), max(map(abs, d)), d))
	for d in steps:
		cand = tuple(f"{min(100, max(0, b + s)) / 100:.2f}" for b, s in zip(base, d))
		if not is_bad(cand, bad):
			return cand
	return triple


def find(lines, token):
	"""(first, last) line of the token's 'if = { limit = { has_country_leader_ideology = token } ... }', or None."""
	rx = re.compile(RX_HAS.format(re.escape(token)))
	at = next((i for i, l in enumerate(lines) if rx.match(l)), None)
	if at is None:
		return None
	first = next((i for i in range(at, -1, -1) if re.match(r"^\s*if\s*=\s*\{", lines[i])), None)
	if first is None:
		return None
	depth = 0
	for i in range(first, len(lines)):
		line = re.sub(r"#.*", "", lines[i])
		depth += line.count("{") - line.count("}")
		if depth == 0:
			return first, i
	return None


def block(indent, token, triple):
	return ([f"{indent}if = {{", f"{indent}\tlimit = {{", f"{indent}\t\thas_country_leader_ideology = {token}", f"{indent}\t}}"]
			+ [f"{indent}\tset_temp_variable = {{ {ch} = {v} }}" for ch, v in zip(CHANNELS, triple)] + [f"{indent}}}"])


def sync(lines, token, rgb, siblings, bad):
	"""lines with the token's colour set (added after its siblings' blocks if it isn't there).
	-> (lines, 'same' / 'updated' / 'added' / None (nowhere to put it), the values written)."""
	triple = safe(fractions(rgb), bad)
	lines = list(lines)
	at = find(lines, token)
	if at is not None:
		first, last = at
		changed = False
		for ch, v in zip(CHANNELS, triple):
			rx = re.compile(r"(set_temp_variable\s*=\s*\{\s*%s\s*=\s*)[-\d.]+" % ch)
			hit = next((i for i in range(first, last + 1) if rx.search(lines[i])), None)
			if hit is None:  # (a block without this channel: added before its closing brace)
				indent = re.match(r"\s*", lines[first]).group(0) + "\t"
				lines.insert(last, f"{indent}set_temp_variable = {{ {ch} = {v} }}")
				last += 1
				changed = True
			else:
				new = rx.sub(lambda m: m.group(1) + v, lines[hit], count=1)
				changed |= new != lines[hit]
				lines[hit] = new
		return lines, "updated" if changed else "same", triple
	# Not there yet: after the last block of one of its ideology's other sub-ideologies.
	spots = [find(lines, s) for s in siblings if s != token]
	spots = [s for s in spots if s]
	if spots:
		first, last = max(spots, key=lambda s: s[1])
	else:  # (the ideology's first one: before the end of the colour block, after the last sub-ideology there is)
		every = [i for i, l in enumerate(lines) if re.match(r"^\s*has_country_leader_ideology\s*=", l)]
		if not every:
			return lines, None, triple
		first, last = find(lines, lines[every[-1]].split("=", 1)[1].split("#")[0].strip())
	indent = re.match(r"\s*", lines[first]).group(0)
	lines[last + 1:last + 1] = block(indent, token, triple)
	return lines, "added", triple
