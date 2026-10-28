"""🖼 GFX (To Do Master > GFX mode): every picture the mod asks for that isn't there - culture icons, religious icons,
flags, portraits and ideology / sub-ideology icons - found by scanning the mod (Culture Master's and Country Master's files).

Each one has a 🤖 suggestion (written by Claude / ChatGPT into gfx_suggestions.json, else made from the mod's data),
reference pictures (its siblings' icons, the country's other flags), image links (searches, Wikimedia Commons finds
or your own) and pictures you add (the same picture store as a task's 🎨 Icon / Art). 🃏 Swipe deals random ones: left =
not this one (only you stop seeing it), right = you'll make it (a task for you in project Missing GFX). Anything the
scan gets wrong can be marked "not actually missing". ❓ Needs clarification (by anyone, or by an AI in
gfx_suggestions.json: "needs_clarification": its question) highlights one nobody is sure about and posts it as an idea
in 💡 Ideas (Art & Visuals › GFX Clarification) for the team to answer.

Besides 🔍 Missing there are ⚠ Broken (there, but HOI4 can't read it / wrong size / no spriteType) and 🗑 Unused
(nothing points at it: 🗑 Remove takes it out, with a backup) - see gfx_checks.py. ✋ The whole family claims a set at
once (a parent task with a sub-task each); 📈 Progress counts what's left per section per day; 👁 Preview shows a
draft at the size the game draws it, next to its family.

Shared, synced: todo_tasks.json "gfx" {"items": {id: {pictures, links, note, not_missing, task, clarify, updated}},
"history": {date: {section: left}}}; clarify = {by, when, question, idea}; the idea carries "gfx": the item id.
Personal (config.json): gfx_skipped (swiped left), gfx_section, gfx_swipe_sections.
"""
import json
import os
import random
import re
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from tkinter import ttk, messagebox, simpledialog

import gfx_card_style
import gfx_checks
from idea_picture_viewer import picture_label, show_picture
import master_links
import paths
import ui

APP_NAME = "Organisation Master"
SECTIONS = (("culture", "🎭 Culture Icons"), ("religion", "⛪ Religious Icons"), ("flag", "🏳 Flags"), ("portrait", "🖼 Portraits"), ("ideology", "⚑ Ideologies"),
			("focus", "🎯 National Focus"), ("idea", "📜 National Ideas"))
SECTION_NAME = dict(SECTIONS)
SECTION_COLOUR = {"culture": "#b5651d", "religion": "#7a4fb0", "flag": "#2f6fb3", "portrait": "#3d8a4f", "ideology": "#a83232",
				  "focus": "#8a6d1f", "idea": "#2d7d7a"}
KIND_LABEL = {"culture": "Culture icon", "sub": "Subculture icon", "rgroup": "Religion group icon", "religion": "Religion icon",
			  "flag": "Flag", "ideo_flag": "Ideology flag", "small_flag": "Small flag", "medium_flag": "Medium flag",
			  "generic": "Generic portrait", "generic_small": "Small generic portrait", "leader": "Leader portrait",
			  "main_ideology": "Ideology icon", "sub_ideology": "Sub-ideology icon",
			  "focus": "National focus icon", "national_idea": "National idea (spirit) icon",
			  "rework": "Picture to rework", "unused_file": "Unused picture file", "unused_sprite": "spriteType for nothing", "unused_flag": "Flag for no tag"}
PROBLEMS = (("missing", "🔍 Missing"), ("broken", "⚠ Broken"), ("unused", "🗑 Unused"), ("rework", "🔁 Needs Rework"))
REWORK_REASONS = ("Needs Touchup", "Needs Severe Recorrection", "Something about it", "Looks too AI", "Needs a Remini")  # (Country Master's categories)
PORTRAIT_ONLY, ICON_ONLY = ("Needs a Remini",), ("Looks too AI",)  # (✨ Remini is for faces; "too AI" is for icons)


def reasons_for(section):
	"""The rework reasons offered for a picture of this GFX section."""
	return tuple(r for r in REWORK_REASONS if r not in (ICON_ONLY if section == "portrait" else PORTRAIT_ONLY))
CM_REWORK_FILES = ("portraits_to_rework.txt", "generics_to_rework.txt")  # (in tools/country_master: its rework marks)
DEFAULT_SIZE = {"flag": (82, 52), "ideo_flag": (82, 52), "medium_flag": (41, 26), "small_flag": (10, 7), "sub_ideology": (69, 74),
				"main_ideology": (69, 74), "leader": (156, 210), "generic": (156, 210), "focus": (94, 86), "national_idea": (64, 64)}  # (when its family doesn't say)
SHOW = ("To do", "❓ Needs clarification", "Taken (has a task)", "✓ Made (until a rescan finds it)", "Not actually missing / kept", "Everything")
KEEP_REASONS = ("It's used in a way the scan can't see", "Keep it for later (a planned culture / country)", "Other")
FAMILY_LINK = "gfx_family:"  # (the parent task of a ✋ whole family)
CLARIFY_CATEGORY = "Art & Visuals"  # (the Ideas category its question goes in)
CLARIFY_HEADING = "GFX Clarification"  # (and the heading inside it: every GFX question together)
CLARIFY_COLOUR = "#e08a00"
NOT_MISSING_REASONS = ("It's there (the scan is wrong)", "It uses another picture on purpose", "Not needed (never shown in game)", "Other")
GFX_PROJECT = "Missing GFX"
LINK = "gfx:"  # (a task's link to its GFX item)
AI_NAMES = ("Claude", "ChatGPT", "Chat Jipity", "Codex", "AI")  # (who counts as an AI in gfx_suggestions.json "by")
AI_RATE_REASONS = ("Not fitting the theme", "Nonsensical", "Too basic", "Wrong / inaccurate (facts or symbols)",
				   "Too detailed for its size", "Doesn't match its family's style", "Links broken / not useful",
				   "Copies another entry's suggestion", "Other")
RATINGS_FILE = "gfx_suggestion_ratings.json"  # (next to gfx_suggestions.json: the team's ratings, for the AI's next run)
AI_FILE = "gfx_suggestions.json"  # (next to todo_tasks.json in tools/organisation_master; Claude / ChatGPT fill it)
SWIPE_FAR = 150  # (pixels a card is dragged before it counts as a swipe)
USER_AGENT = "RevolutionRealized-OrganisationMaster/1.0 (Hearts of Iron IV mod dev tool)"
IMAGE_RX = re.compile(r"\.(png|jpe?g|gif|webp|bmp)(\?.*)?$", re.I)


def stamp():
	return time.strftime("%Y-%m-%dT%H:%M:%S")


def cache_file():
	return os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "OrganisationMaster", "gfx_scan.json.gz")


def write_cache(when, items):
	"""This PC's last scan, gzipped (it lists every picture in the mod: ~12 MB as plain JSON, ~1.5 MB like this)."""
	import gzip
	os.makedirs(os.path.dirname(cache_file()), exist_ok=True)
	with gzip.open(cache_file() + ".tmp", "wt", encoding="utf-8", compresslevel=3) as f:
		json.dump({"when": when, "items": items}, f, ensure_ascii=False)
	os.replace(cache_file() + ".tmp", cache_file())
	try:
		os.remove(cache_file()[:-3])  # (the old plain one)
	except OSError:
		pass


def read_cache():
	import gzip
	with gzip.open(cache_file(), "rt", encoding="utf-8") as f:
		return json.load(f)


SEED_FILE = "gfx_scan_seed.json.gz"  # (in tools/organisation_master, in git: a PC's first look, before its own scan)


def seed_path():
	return os.path.join(paths.TOOL, SEED_FILE)


def write_seed(items, when, mod_root, game):
	"""Saves a scan as the shared starting one: paths made relative (<MOD>/, <GAME>/) so it works on any PC."""
	import gzip
	text = json.dumps({"when": when, "items": items}, ensure_ascii=False)
	for prefix, mark in ((mod_root, "<MOD>"), (game, "<GAME>")):
		if prefix:
			for form in {os.path.normpath(prefix), os.path.normpath(prefix).replace("\\", "/")}:
				text = text.replace(json.dumps(form)[1:-1], mark)
	with gzip.open(seed_path(), "wt", encoding="utf-8") as f:
		f.write(text)


def read_seed(mod_root):
	"""The shared starting scan with this PC's folders put back, or None."""
	import gzip
	try:
		with gzip.open(seed_path(), "rt", encoding="utf-8") as f:
			text = f.read()
	except OSError:
		return None
	try:
		from cm_data import find_game
		game = find_game(mod_root) or ""
	except Exception:
		game = ""
	for mark, prefix in (("<MOD>", mod_root), ("<GAME>", game)):
		text = text.replace(mark, json.dumps(os.path.normpath(prefix))[1:-1] if prefix else "")
	try:
		return json.loads(text)
	except ValueError:
		return None


# ---------- the scan (no Tk here: it runs in a thread) ----------
class Present:
	"""The mod's own pictures that are there (not missing), for 🔎 Review swiper: items with problem "present", one per
	file (the first entry that uses it names it). Base-game pictures aren't listed."""

	def __init__(self, root):
		self.root, self.base = root, os.path.normcase(os.path.abspath(root)) + os.sep
		self.found = {}

	def add(self, section, kind, path, name, family, family_name, link=None, detail="", sprite=None, token=None):
		if not path:
			return
		full = os.path.abspath(path if os.path.isabs(path) else os.path.join(self.root, path))
		if not os.path.normcase(full).startswith(self.base):
			return
		rel = os.path.relpath(full, self.root).replace("\\", "/")
		if rel.lower() in self.found or not os.path.isfile(full):
			return
		self.found[rel.lower()] = dict(id="present:" + rel.lower(), problem="present", section=section, kind=kind, name=name, path=full,
			file=rel, family=family, family_name=family_name, link=link, detail=detail or rel, sprite=sprite, token=token or name, refs=[full])

	def items(self):
		return list(self.found.values())



def scan(root, progress=lambda text: None):
	"""[item]: every missing, ⚠ broken and 🗑 unused picture. item = {id, section, kind, problem (missing / broken / unused;
	missing when it isn't there), name, detail, file (the file it should be), refs (pictures to look at), link (rr:// to
	its master), search (words to look for pictures with), note (what else it needs), family / family_name (✋ claim the
	whole family)}."""
	import culture_master as cm
	from cm_data import CountryData, find_game
	items = []
	present = Present(root)
	hd = gfx_checks.Headers()
	wanted = set()  # (icon files an entry uses by its name: not 🗑 unused even without a spriteType)
	families = {}  # (family key -> [pictures that exist], for ⚠ broken)
	progress("GFX: reading cultures and religions...")
	d = cm.ModData(root)
	sprites = {}
	for rel in (cm.F_GFX, cm.F_REL_GFX):
		sprites.update(d.read_sprites(cm.TextFile(d.path(rel)).lines))

	def icon(n):
		rel = sprites.get(cm.sprite_name(n), cm.ModData.icon_path(n))
		path = os.path.join(root, rel)
		return rel, path if os.path.isfile(path) else None

	def top(n):
		while n.parent:
			n = n.parent
		return n
	def relatives(n, section):
		"""🔗 Its parent and children with icons of their own (a culture's subcultures, a subculture's culture, a religion
		group's religions, a religion's group and sects): [{id, kind, name, role, path (or None)}]."""
		out = []
		for m, role in ([(n.parent, "parent")] if n.parent else []) + [(ch, "child") for ch in n.children]:
			if m.kind in ("culture", "sub", "religion", "rgroup"):
				out.append(dict(id=f"{section}:{m.kind}:{m.token}", kind=m.kind, name=m.label(), role=role, path=icon(m)[1]))
		return out
	for section, kinds, gfx in (("culture", ("culture", "sub"), cm.F_GFX), ("religion", ("rgroup", "religion"), cm.F_REL_GFX)):
		for kind in kinds:
			for n in d.nodes[kind].values():
				rel, have = icon(n)
				fam = (f"{n.parent.kind}:{n.parent.token}", f"{n.parent.label()} {KIND_LABEL[kind].lower()}s") if n.parent else (kind, KIND_LABEL[kind] + "s")
				link = master_links.make("culture", "node", f"{kind}:{n.token}", system=section)
				wanted.add(rel.replace("\\", "/").lower())
				if have:
					member = dict(section=section, kind=kind, family=fam[0], family_name=fam[1], path=have, name=n.label(),
								  token=n.token, link=link, parent=n.parent.label() if n.parent else "", group=top(n).label())
					families.setdefault((section, fam[0]), []).append(member)
					present.add(section, kind, have, n.label(), fam[0], fam[1], link, f"{KIND_LABEL[kind]} · {fam[1]}", token=n.token)
					if cm.sprite_name(n) not in sprites:  # (the picture is there, but the game has no name to show it by)
						items.append(gfx_checks.broken_item(root, member, f"no spriteType {cm.sprite_name(n)} in {gfx} - the game can't show it"))
					continue
				family = [s for s in (n.parent.children if n.parent else []) if s is not n] + list(n.children)
				refs = [p for p in (icon(s)[1] for s in family) if p][:6]
				name = n.label()
				if kind == "sub":
					detail = f"Subculture of {n.parent.label() if n.parent else '?'} · {top(n).label()} group"
				elif kind == "culture":
					detail = f"Culture of the {top(n).label()} group · {len(n.children)} subcultures"
				elif kind == "religion":
					detail = f"Religion of the {n.parent.label() if n.parent else '?'} group"
				else:
					detail = f"Religion group · {len(n.children)} religions"
				sprite = cm.sprite_name(n)
				items.append(dict(id=f"{section}:{kind}:{n.token}", section=section, kind=kind, name=name, token=n.token,
					related=relatives(n, section),
					detail=detail, file=rel, refs=refs, parent=n.parent.label() if n.parent else "", group=top(n).label(),
					family=fam[0], family_name=fam[1], link=link,
					search=f"{name} {'religion symbol' if section == 'religion' else 'culture'}",
					note="" if sprite in sprites else f"Also needs its spriteType {sprite} in {gfx}."))
	progress("GFX: reading countries (flags and portraits)...")
	c = CountryData(root, find_game(root), cache_dir=os.path.join(paths.TOOL, ".rr_games_cache", "countries"))
	mains = list(c.mains)
	sizes = {}
	for size in ("small", "medium"):
		have = set()
		for base in c.bases:
			folder = os.path.join(base, "gfx", "flags", size)
			if os.path.isdir(folder):
				have |= {f.lower() for f in os.listdir(folder)}
		sizes[size] = have
	mod_flags = os.path.join(root, "gfx", "flags")
	own = {f.lower(): f for f in os.listdir(mod_flags)} if os.path.isdir(mod_flags) else {}
	for tag in sorted(c.countries):
		name = c.name(tag)
		variants = [f"{tag}.tga"] + [f"{tag}_{i}.tga" for i in mains]
		refs = [c.flag_map[v.lower()] for v in variants if v.lower() in c.flag_map][:6]
		link = master_links.make("country", "country", tag)
		base = dict(section="flag", token=tag, refs=refs, link=link, search=f"flag of {name}", note="", family=f"flag:{tag}",
					family_name=f"{name} flags")
		if not c.has_flag(tag):
			missing = [i for i in mains if not c.has_flag(tag, i)]
			if len(missing) == len(mains):
				items.append(dict(base, id=f"flag:{tag}", kind="flag", name=f"{name} ({tag})", file=f"gfx/flags/{tag}.tga",
					detail=f"No flag at all · needs {tag}.tga (or one per ideology), plus small/ and medium/ copies"))
			else:
				for i in missing:
					items.append(dict(base, id=f"flag:{tag}_{i}", kind="ideo_flag", name=f"{name} ({tag}) - {i}", ideology=i,
						file=f"gfx/flags/{tag}_{i}.tga", detail=f"{i.title()} flag · no plain {tag}.tga to fall back on",
						search=f"{i} flag of {name}"))
		for low, real in own.items():  # (its own big flags without their small / medium copies)
			if not low.endswith(".tga") or not (low == f"{tag.lower()}.tga" or low.startswith(tag.lower() + "_")):
				continue
			stem = real[:-4]
			if stem[len(tag) + 1:] not in [""] + mains:
				continue
			for size in ("small", "medium"):
				if low not in sizes[size]:
					items.append(dict(base, id=f"flag:{size}:{stem}", kind=f"{size}_flag", name=f"{name} ({stem}) - {size}",
						file=f"gfx/flags/{size}/{real}", refs=[os.path.join(mod_flags, real)],
						detail=f"{size.title()} copy of {real} ({'10x7' if size == 'small' else '41x26'})"))
	generics = {}
	for tag in c.countries:
		for cat, _, sprite in c.generics_of(tag):
			large, small = c.generic_missing(cat, sprite)
			for missing, key in ((large, sprite), (small, sprite + "_small")):
				if missing:
					generics.setdefault(key, (cat, sprite, set()))[2].add(tag)
	for key, (cat, sprite, tags) in sorted(generics.items()):
		small = key != sprite
		tex = c.sprite_texture(key)
		rel = os.path.relpath(tex, root).replace("\\", "/") if tex and os.path.isabs(tex) else (tex or "")
		first = sorted(tags)[0]
		refs = [p for p in ([c.portrait_path(sprite)] if small else []) if p]
		refs += [p for p in (c.portrait_path(sp) for _, _, sp in c.generics_of(first) if sp != sprite) if p][:6 - len(refs)]
		items.append(dict(id=f"portrait:{key}", section="portrait", kind="generic_small" if small else "generic",
			name=key.removeprefix("GFX_"), token=key, file=rel, refs=refs, tags=sorted(tags),
			family=f"portraits:{first}", family_name=f"{c.name(first)} portraits",
			detail=f"Generic {cat} portrait{' (small, for units)' if small else ''} · used by {', '.join(sorted(tags)[:6])}"
				   + (f" +{len(tags) - 6}" if len(tags) > 6 else ""),
			link=master_links.make("country", "portrait", sprite), search=f"{c.name(first)} {cat} officer portrait 1930s",
			note="" if tex else f"Also needs its spriteType {key} in an interface/*.gfx file."))
	for cid, ch in c.characters.items():
		if ch.leaders() and not c.has_large_portrait(ch):
			tag = getattr(ch, "tag", None) or cid[:3]
			name = c.label(ch.name_key, "") or cid
			items.append(dict(id=f"portrait:leader:{cid}", section="portrait", kind="leader", name=name, token=cid,
				family=f"portraits:{tag}", family_name=f"{c.name(tag) if tag in c.countries else tag} portraits",
				file=next((v for _, size, v in ch.portrait_slots if size == "large"), ""), refs=[],
				detail=f"Leader of {c.name(tag) if tag in c.countries else tag} · {ch.rel}",
				link=master_links.make("country", "country", tag) if tag in c.countries else None,
				search=f"{name} portrait", note=""))
	def ideo_icon(sprite):
		tex = c.sprite_texture(sprite)
		return tex, tex if tex and os.path.isfile(tex if os.path.isabs(tex) else os.path.join(root, tex)) else None
	for main, subs in c.ideologies.items():
		# (the main ideologies' icons are GFX_ideology_<main>_group, as in the base game)
		tex, have = ideo_icon(f"GFX_ideology_{main}_group")
		main_rel = dict(id=f"ideology:main:{main}", kind="main_ideology", name=c.label(main, main.title()), role="parent", path=have)
		sub_rels = [dict(id=f"ideology:sub:{s}", kind="sub_ideology", name=c.label(s, s), role="child", path=ideo_icon(f"GFX_ideology_{s}")[1]) for s in subs]
		if not have:
			items.append(dict(id=f"ideology:main:{main}", section="ideology", kind="main_ideology", name=c.label(main, main.title()),
				token=main, file=f"gfx/interface/ideologies/{main}_group.dds", refs=[], detail=f"Main ideology · {len(subs)} sub-ideologies", related=sub_rels,
				link=None, search=f"{main} political symbol", note="" if tex else f"Also needs its spriteType GFX_ideology_{main}_group."))
		with_icons = [p for p in (ideo_icon(f"GFX_ideology_{s}")[1] for s in subs) if p]
		for sub in subs:
			tex, have = ideo_icon(f"GFX_ideology_{sub}")
			fam = (f"ideology:{main}", f"{c.label(main, main.title())} sub-ideologies")
			wanted.add(f"gfx/interface/ideologies/{main}_{sub}.dds".lower())
			if have:
				families.setdefault(("ideology", "all"), []).append(dict(section="ideology", kind="sub_ideology", family=fam[0],
					family_name=fam[1], path=have if os.path.isabs(have) else os.path.join(root, have), name=c.label(sub, sub),
					token=sub, main=main, link=master_links.make("country", "ideology", sub)))
				present.add("ideology", "sub_ideology", have, c.label(sub, sub), fam[0], fam[1], master_links.make("country", "ideology", sub),
							f"Sub-ideology of {c.label(main, main.title())}", token=sub)
				continue
			name = c.label(sub, sub)
			items.append(dict(id=f"ideology:sub:{sub}", section="ideology", kind="sub_ideology", name=name, token=sub, main=main,
				file=os.path.relpath(tex, root).replace("\\", "/") if tex and os.path.isabs(tex) else (tex or f"gfx/interface/ideologies/{main}_{sub}.dds"),
				refs=with_icons[:6], detail=f"Sub-ideology of {c.label(main, main.title())} · {sub}", family=fam[0], family_name=fam[1], related=[main_rel],
				link=master_links.make("country", "ideology", sub), search=f"{name} political symbol",
				note="" if tex else f"Also needs its spriteType GFX_ideology_{sub} in interface/rr_ideologies.gfx (Country Master's sub-ideology editor adds it with the icon)."))
	items += focus_and_idea_icons(root, c, progress, present)
	# ---- ⚠ broken: the pictures that are there ----
	progress("GFX: checking the pictures that are there (⚠ broken)...")
	frames = gfx_checks.animated(root)  # (animated portraits / icons: judged by one frame)
	for (section, _), members in families.items():
		items += gfx_checks.broken(root, members, hd, frames=frames)
	items += gfx_checks.broken_flags(root, hd, c.name)
	for f in sorted(os.listdir(mod_flags)) if os.path.isdir(mod_flags) else []:  # (the mod's own big flags)
		if f.lower().endswith(".tga"):
			tag = f[:-4].split("_")[0].upper()
			present.add("flag", "flag", os.path.join(mod_flags, f), f"{c.name(tag)} ({f[:-4]})", f"flag:{tag}", f"{c.name(tag)} flags",
						master_links.make("country", "country", tag) if tag in c.countries else None, f"Flag · gfx/flags/{f}", token=tag)
	seen, large = set(), []
	mod_base = os.path.normcase(os.path.abspath(root)) + os.sep
	for cid, ch in c.characters.items():
		tag = getattr(ch, "tag", None) or cid[:3]
		for _, size, v in ch.portrait_slots:
			path = c.portrait_path(v) if size == "large" else None
			if path and os.path.normcase(os.path.abspath(path)).startswith(mod_base) and path not in seen:  # (paths come with / and \ mixed)
				seen.add(path)
				large.append(dict(section="portrait", kind="leader", family=f"portraits:{tag}", family_name=f"{c.name(tag) if tag in c.countries else tag} portraits",
					path=path, name=c.label(ch.name_key, "") or cid, token=cid, link=master_links.make("country", "portrait", v)))
				present.add("portrait", "leader", path, c.label(ch.name_key, "") or cid, f"portraits:{tag}", large[-1]["family_name"],
							large[-1]["link"], f"Leader portrait · {cid}", sprite=v, token=cid)
	for tag in c.countries:
		for cat, _, sp in c.generics_of(tag):
			path = c.portrait_path(sp)
			if path and os.path.normcase(os.path.abspath(path)).startswith(mod_base) and path not in seen:  # (paths come with / and \ mixed)
				seen.add(path)
				large.append(dict(section="portrait", kind="generic", family=f"portraits:{tag}", family_name=f"{c.name(tag)} portraits",
					path=path, name=sp.removeprefix("GFX_"), token=sp, link=master_links.make("country", "portrait", sp)))
				present.add("portrait", "generic", path, sp.removeprefix("GFX_"), f"portraits:{tag}", f"{c.name(tag)} portraits",
							large[-1]["link"], f"Generic {cat} portrait · {tag}", sprite=sp, token=sp)
	items += gfx_checks.broken(root, large, hd, exact=False, frames=frames)  # (portraits: only stretched ones, sizes vary a little)
	hd.save()
	# ---- 🗑 unused ----
	progress("GFX: looking for pictures nothing uses (🗑 unused)...")
	nodes = {k: set(d.nodes[k]) for k in ("culture", "sub", "religion", "rgroup")}
	cosmetics = {cos for per in c.cosmetics.values() for cos in per}
	subs = {s for ss in c.ideologies.values() for s in ss}
	items += gfx_checks.unused(root, c.game, nodes, subs, set(c.ideologies), set(c.countries), cosmetics, c.name, wanted)
	items += present.items()
	progress(f"GFX: {len(items)} found.")
	return items


LAW_CATEGORIES = {"economy", "trade_laws", "mobilization_laws"}  # (laws even where a mod's file leaves out 'law = yes')
NOT_SPIRITS = {"hidden_ideas", "political_advisor", "theorist", "army_chief", "navy_chief", "air_chief", "high_command"}
# What a spirit shows in game; an idea with none of these (and no picture) is a token the scripts use, never seen.
SPIRIT_CONTENT = {"modifier", "targeted_modifier", "research_bonus", "equipment_bonus", "rule", "on_add", "on_remove", "picture"}


def focus_and_idea_icons(root, c, progress=lambda text: None, present=None):
	"""🎯 National focus icons and 📜 national idea (spirit) icons the mod's own files ask for that aren't there
	(no spriteType, or its file is missing). Laws, designers, advisors and hidden ideas aren't national ideas here.
	One item per sprite (several focuses / ideas can share one)."""
	import cm_data as cd
	mod = os.path.normcase(os.path.abspath(root)) + os.sep

	def own(f):
		return os.path.normcase(os.path.abspath(f)).startswith(mod)

	def state(sprite):
		"""(texture the spriteType names or None, the full path when that file is there or None)"""
		have = c.sprite_texture(sprite)
		return (c._sprites.get(sprite) or c._sprites_lower.get(sprite.lower())), have

	def file_for(sprite, folder):
		rel, _ = state(sprite)
		return rel or f"gfx/interface/{folder}/{sprite[4:] if sprite.lower().startswith('gfx_') else sprite}.dds"

	def note_for(sprite, gfx_file):
		return "" if state(sprite)[0] else f"Also needs its spriteType {sprite} in an interface/*.gfx file ({gfx_file})."
	items = []
	# ---- 🎯 national focus ----
	progress("GFX: reading national focus trees...")
	found = {}  # sprite -> {"uses": [(focus id, tree)], "family": (key, name)}
	have_by_tree = {}
	for f in c._files(cd.D_FOCUS):
		if not own(f):
			continue
		try:
			top = c._entries(f)
		except Exception:
			continue
		for tree in top:
			if not (tree.block and tree.key in ("focus_tree", "shared_focus", "joint_focus")):
				continue
			tree_id = str(tree.get("id", "")) if tree.key == "focus_tree" else os.path.splitext(os.path.basename(f))[0]
			fam = (f"focus:{tree_id}", f"{tree_id} focus tree" if tree.key == "focus_tree" else f"{tree_id} (shared focuses)")
			focuses = [x for x in tree.value if x.key == "focus" and x.block] if tree.key == "focus_tree" else [tree]
			for fo in focuses:
				fid = str(fo.get("id", "?"))
				sprites = []
				for ic in fo.all("icon"):
					if ic.block:  # (icon = { trigger = { ... } value = GFX_... }: each one it can show)
						sprites += [str(v.value) for v in ic.value if v.key == "value" and not v.block]
					elif ic.value:
						sprites.append(str(ic.value))
				for sp in dict.fromkeys(sprites):
					_, have = state(sp)
					if have:
						have_by_tree.setdefault(fam[0], []).append(have)
						if present:
							present.add("focus", "focus", have, c.label(fid, fid), fam[0], fam[1], None, f"{sp} · focus {fid}", sprite=sp, token=sp)
						continue
					rec = found.setdefault(sp, {"uses": [], "family": fam})
					rec["uses"].append(fid)
	for sp, rec in found.items():
		uses, fam = rec["uses"], rec["family"]
		name = c.label(uses[0], uses[0])
		more = f" (+{len(uses) - 1} more focuses)" if len(uses) > 1 else ""
		items.append(dict(id=f"focus:{sp}", section="focus", kind="focus", name=name, token=sp,
			file=file_for(sp, "goals"), refs=list(dict.fromkeys(have_by_tree.get(fam[0], [])))[:6],
			detail=f"{sp} · used by {', '.join(uses[:3])}{more}", family=fam[0], family_name=fam[1],
			link=None, search=name, note=note_for(sp, "e.g. interface/goals.gfx")))
	# ---- 📜 national ideas (spirits) ----
	progress("GFX: reading national ideas...")
	laws = set(LAW_CATEGORIES)
	for f in c._files(cd.D_IDEAS):  # (a category is a law wherever any file says 'law = yes')
		try:
			top = c._entries(f)
		except Exception:
			continue
		for e in top:
			if e.key == "ideas" and e.block:
				laws |= {cat.key for cat in e.value if cat.block and (str(cat.get("law", "")) == "yes" or str(cat.get("designer", "")) == "yes")}
	found, have_by_tag = {}, {}
	for f in c._files(cd.D_IDEAS):
		if not own(f):
			continue
		try:
			top = c._entries(f)
		except Exception:
			continue
		for e in top:
			if e.key != "ideas" or not e.block:
				continue
			for cat in e.value:
				if not cat.block or not cat.key or cat.key in laws or cat.key in NOT_SPIRITS or cat.key.endswith("_advisor"):
					continue
				for idea in cat.value:
					if not (idea.block and idea.key) or idea.key in ("law", "designer", "use_list_view"):
						continue
					if not any(x.key in SPIRIT_CONTENT for x in idea.value):
						continue  # (a token: allowed = { always = no } and nothing to show)
					pic = idea.get("picture")
					pic = str(pic) if pic and not isinstance(pic, list) else None
					sp = pic if pic and pic.lower().startswith("gfx_") else f"GFX_idea_{pic or idea.key}"
					if pic and not state(sp)[1] and state("GFX_" + pic)[1]:
						sp = "GFX_" + pic  # (picture = idea_unknown: GFX_idea_unknown)
					tag = idea.key[:3].upper() if idea.key[:3].upper() in c.countries and (len(idea.key) == 3 or idea.key[3] == "_") else ""
					_, have = state(sp)
					if have:
						have_by_tag.setdefault(tag, []).append(have)
						if present:
							present.add("idea", "national_idea", have, c.label(idea.key, idea.key), f"ideas:{tag or c.rel(f)}",
										f"{c.name(tag)} national ideas" if tag else f"National ideas in {os.path.basename(c.rel(f))}",
										master_links.make("country", "country", tag) if tag else None, f"{sp} · {idea.key}", sprite=sp, token=sp)
						continue
					found.setdefault(sp, {"uses": [], "tag": tag, "rel": c.rel(f)})["uses"].append(idea.key)
	for sp, rec in found.items():
		uses, tag = rec["uses"], rec["tag"]
		name = c.label(uses[0], uses[0])
		more = f" (+{len(uses) - 1} more)" if len(uses) > 1 else ""
		fam = (f"ideas:{tag or rec['rel']}", f"{c.name(tag)} national ideas" if tag else f"National ideas in {os.path.basename(rec['rel'])}")
		items.append(dict(id=f"idea:{sp}", section="idea", kind="national_idea", name=name, token=sp,
			file=file_for(sp, "ideas"), refs=list(dict.fromkeys(have_by_tag.get(tag, [])))[:6],
			detail=f"{sp} · {', '.join(uses[:3])}{more} · {rec['rel']}", family=fam[0], family_name=fam[1],
			link=master_links.make("country", "country", tag) if tag else None, search=name,
			note=note_for(sp, "e.g. interface/ideas.gfx")))
	return items


# ---------- 🔁 the shared rework list (todo_tasks.json gfx.rework, live-synced) ----------
def rework_store(data):
	return data.setdefault("gfx", {}).setdefault("rework", {})


def portrait_key(sprite):
	return "portrait:" + sprite.lower()


def mark_portrait(data, sprite, reason, used="", when="", by="", note="", kind="generic", claimed=(), file=None):
	"""A portrait in 🔁 Needs Rework for everyone (from Country Master's Mark for rework, or the old To Do tasks).
	True when something changed."""
	store = rework_store(data)
	key = portrait_key(sprite)
	old = store.get(key) or {}
	tag = sprite[4:7] if re.match(r"GFX_[A-Z0-9]{3}_", sprite) else ""
	m = dict(old, sprite=sprite, name=sprite.removeprefix("GFX_"), section="portrait", portrait_kind=kind,
			 reason=reason if reason in REWORK_REASONS else old.get("reason", REWORK_REASONS[0]), used=used or old.get("used", ""),
			 note=note or old.get("note", ""), by=old.get("by") or by, when=old.get("when") or when or stamp(),
			 family=f"portraits:{tag}" if tag else "portraits", family_name=old.get("family_name") or (f"{tag} portraits" if tag else "Portraits"),
			 link=master_links.make("country", "portrait", sprite))
	m["file"] = file if file is not None else old.get("file", "")
	if claimed:
		m["claimed"] = sorted(set(old.get("claimed") or []) | set(claimed))
	if m == old:
		return False
	store[key] = m
	(data["gfx"].get("rework_done") or {}).pop(key, None)  # (marked again: no longer done)
	return True


def unmark(data, key, who):
	"""Out of 🔁 Needs Rework for everyone; remembered as done, so a PC's older copy of the list can't bring it back."""
	m = rework_store(data).pop(key, None)
	if m is None:
		return False
	done = {"when": stamp(), "by": who}
	done.update({k: m[k] for k in ("file", "name", "section", "sprite", "reason") if m.get(k)})  # (for 🔀 Before / after)
	if m.get("when"):
		done["marked"] = m["when"]
	data["gfx"].setdefault("rework_done", {})[key] = done
	return True


def done_since(data, key, day):
	"""Reworked / unmarked on or after this day (YYYY-MM-DD)?"""
	t = (data.get("gfx", {}).get("rework_done") or {}).get(key)
	return bool(t) and (t.get("when") or "")[:10] >= (day or "")


def remark_cm_file(mod_root, m):
	"""A portrait's line back in this PC's tools/country_master/portraits_to_rework.txt (an undone ✓ Reworked: Country
	Master shows it marked again). True when it was added."""
	path = os.path.join(os.path.dirname(paths.TOOL), "country_master", "portraits_to_rework.txt")
	mod, sprite = os.path.basename(os.path.normpath(mod_root)), m.get("sprite")
	if not sprite:
		return False
	try:
		with open(path, encoding="utf-8") as f:
			lines = f.read().splitlines()
	except OSError:
		lines = []
	if any(not l.startswith("#") and [x.strip() for x in l.split("|")][:2] == [mod, sprite] for l in lines):
		return False
	note = " ".join(str(m.get("note") or "").replace("|", "/").split())
	kind = "portrait" if m.get("portrait_kind") in ("leader", "portrait") else "generic"
	lines.append(f"{mod} | {sprite} | {m.get('reason', REWORK_REASONS[0])} | {m.get('used', '')} | {(m.get('when') or '')[:10]} | {kind}"
				 + (f" | {note}" if note else ""))
	with open(path, "w", encoding="utf-8", newline="\r\n") as f:
		f.write("\n".join(lines) + "\n")
	return True


def follow_undo(mod_root, before, after):
	"""After an undo (or any jump back) of the shared rework list: this PC's Country Master file matches it - portraits
	back on the list get their line back, portraits off it lose theirs."""
	old, new = (before.get("gfx") or {}).get("rework") or {}, (after.get("gfx") or {}).get("rework") or {}
	for key in set(new) - set(old):
		remark_cm_file(mod_root, new[key])
	for key in set(old) - set(new):
		if old[key].get("sprite"):
			unmark_cm_file(mod_root, old[key]["sprite"])


def unmark_cm_file(mod_root, sprite):
	"""Takes the portrait's line out of this PC's tools/country_master/portraits_to_rework.txt (Country Master shows it
	unmarked). True when there was one."""
	path = os.path.join(os.path.dirname(paths.TOOL), "country_master", "portraits_to_rework.txt")
	mod = os.path.basename(os.path.normpath(mod_root))
	try:
		with open(path, encoding="utf-8") as f:
			lines = f.read().splitlines()
	except OSError:
		return False
	keep = [l for l in lines if not (not l.startswith("#") and [x.strip() for x in l.split("|")][:2] == [mod, sprite])]
	if len(keep) == len(lines):
		return False
	with open(path, "w", encoding="utf-8", newline="\r\n") as f:
		f.write("\n".join(keep) + "\n")
	return True


CHILD_KINDS = {"sub": ("culture", "culture"), "religion": ("religion", "rgroup"), "sub_ideology": ("ideology", "main")}


def parent_id(item):
	"""The id its parent row has (a subculture's culture, a religion's group, a sub-ideology's ideology), or None."""
	how = CHILD_KINDS.get(item["kind"])
	fam = item.get("family") or ""
	if not how or ":" not in fam:
		return None
	return f"{how[0]}:{how[1]}:{fam.split(':', 1)[1]}"


def problem(item):
	return item.get("problem", "missing")


def family(item):
	"""(key, name) of its family (✋ claim them all); older cached scans have none: its section and kind."""
	return item.get("family") or f"{item['section']}:{item['kind']}", item.get("family_name") or KIND_LABEL.get(item["kind"], item["kind"]) + "s"


def suggestion(item, ai):
	"""The 🤖 suggestion: what Claude / ChatGPT wrote for it, else one made from what the mod knows."""
	text = (ai.get(item["id"]) or {}).get("suggestion")
	if text:
		return text, True
	k, n = item["kind"], item["name"]
	if problem(item) == "unused":
		return ("Nothing in the mod points at it. Remove it to slim the mod down (🗑 Remove keeps a backup), or Keep it if "
				"it's used in a way the scan can't see, or is for something planned."), False
	if problem(item) == "rework":
		return (f"Marked for rework ({item.get('reason', 'Needs Touchup')}). Redraw or touch it up in its family's style (the "
				f"pictures under 'Look at these'), same size and file, then ✓ Reworked."
				+ (f" Note: {item['mark_note']}" if item.get("mark_note") else "")), False
	if problem(item) == "broken":
		d, want = item["detail"], item.get("want")
		if "spriteType" in d:
			fix = "Add its spriteType (Culture Master adds one when you set the icon there, or copy a sibling's block in the .gfx file)."
		elif "DDS" in d or "TGA" in d or "PNG" in d or "picture" in d:
			fix = "Open it and save it again in the format named above (Paint.NET / GIMP: DDS as DXT5, TGA as 32-bit uncompressed)."
		elif want:
			fix = f"Resize it to {want[0]}x{want[1]} (or redraw it at that size) so it lines up with its family."
		else:
			fix = "Save it again at the size the rest of its family uses."
		return f"{d.lstrip('⚠ ')}. {fix}", False
	if k == "sub":
		text = (f"A small round icon for the {n} subculture, in the style of the other {item['parent']} icons so the family "
				f"reads together. Use a symbol people link to {n} people: a regional flag or coat of arms, a landmark, a "
				f"traditional pattern or dress.")
	elif k == "culture":
		text = (f"An icon for the {n} culture ({item['group']} group): the national or ethnic flag / emblem most linked to "
				f"{n} people, simple enough to read at icon size; its subcultures' icons can borrow its colours.")
	elif k == "religion":
		text = (f"An icon for {n} ({item['parent']}): its best-known symbol (as used on Wikipedia's religion boxes), one or two "
				f"colours, the same frame and size as the other religion icons.")
	elif k == "rgroup":
		text = f"An icon for the {n} religion group: the symbol shared by its religions, plain and bold, like the other group icons."
	elif k in ("flag", "ideo_flag"):
		ideo = item.get("ideology")
		text = (f"A flag for {n}" + (f" under {ideo}: its usual flag restyled the way the other {ideo} flags in the mod are "
				f"(colours, emblem swap)" if ideo else ": its real flag if it had one, else one made from its region's colours and "
				f"symbols") + ". 82x52 TGA (32-bit), plus 41x26 in medium/ and 10x7 in small/.")
	elif k in ("small_flag", "medium_flag"):
		text = "Scale the big flag down (no new art needed): the reference picture is the flag to shrink."
	elif k == "sub_ideology":
		text = (f"A 69x74 icon for the {n} sub-ideology of {item['main']}: the emblem, party symbol or flag colours people link to "
				f"{n}, in the style of the other {item['main']} sub-ideology icons.")
	elif k == "main_ideology":
		text = f"The {n} ideology's icon: its classic symbol, bold and simple, like the base game's ideology icons."
	elif k == "leader":
		text = f"A portrait of {n} in the style of the mod's other leader portraits (156x210)."
	elif k == "focus":
		text = (f"A national focus icon for \"{n}\" (94x86, in the shield-and-frame style of the tree's other icons): one clear "
				f"object or scene that says what the focus does. A base-game goal icon that fits can be used instead.")
	elif k == "national_idea":
		text = (f"A national spirit picture for \"{n}\" (64x64 with the usual idea frame): one strong image of what the spirit "
				f"is about. A base-game idea picture that fits can be used instead (set its picture = to that one).")
	else:
		text = ("A generic portrait in the style of the country's other generics" + (" - the small unit version of the large one "
				"(shown in reference)" if k == "generic_small" else "") + ".")
	return text, False


def search_words(item):
	"""What 🔎 looks for. Cultures: their culture (dress, crafts, patterns, flags), never photos of people; scans saved
	before this said "people symbol"."""
	words = item.get("search") or item["name"]
	if item["kind"] in ("culture", "sub"):
		words = re.sub(r"\s*people symbol$", "", words)
		words = words if words.endswith(" culture") else f"{words} culture"
		return f"{words} -portrait"
	return words.replace(" hoi4 focus icon", "").replace(" hoi4 national spirit icon", "")


def search_options(item):
	"""[(button, words)]: other ways to look for it in 🔎 Find pictures (small cultures find little under one wording)."""
	n = item["name"]
	if item["kind"] in ("culture", "sub"):
		return [("Culture", f"{n} culture -portrait"), ("Flag / emblem", f"{n} flag"), ("Traditional dress", f"{n} traditional costume"),
				("Ornament / pattern", f"{n} ornament"), ("Just the name", n)]
	if item["kind"] in ("religion", "rgroup"):
		return [("Symbol", f"{n} symbol"), ("Emblem", f"{n} emblem"), ("Just the name", n)]
	return []


def search_links(item):
	q = urllib.parse.quote(search_words(item).replace(" -portrait", ""))
	return [("🔎 Wikimedia Commons", f"https://commons.wikimedia.org/w/index.php?search={q}&title=Special:MediaSearch&type=image"),
			("🔎 Google Images", f"https://www.google.com/search?tbm=isch&q={q}"),
			("🔎 Wikipedia", f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(item['name'])}")]


def image_url(link):
	"""A link that can be shown as a picture here (a direct image, or a Wikimedia Commons file page), else None."""
	m = re.match(r"https?://commons\.wikimedia\.org/wiki/(File:[^?#]+)", link)
	if m:
		return f"https://commons.wikimedia.org/wiki/Special:FilePath/{m.group(1)[5:]}?width=480"
	return link if re.match(r"https?://", link) and IMAGE_RX.search(link) else None


def fetch(url, timeout=20):
	req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	with urllib.request.urlopen(req, timeout=timeout) as r:
		return r.read()


def commons_search(words, limit=12):
	"""[(title, file page, thumbnail url)] from Wikimedia Commons."""
	q = urllib.parse.urlencode(dict(action="query", format="json", generator="search", gsrnamespace=6, gsrsearch=words,
									gsrlimit=limit, prop="imageinfo", iiprop="url", iiurlwidth=200))
	pages = json.loads(fetch("https://commons.wikimedia.org/w/api.php?" + q)).get("query", {}).get("pages", {})
	out = []
	for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
		info = (p.get("imageinfo") or [{}])[0]
		if info.get("thumburl"):
			out.append((p["title"][5:], info.get("descriptionurl") or info["url"], info["thumburl"]))
	return out


def photo(source, box):
	"""A PhotoImage of a picture (a path or bytes) fitted in box, or None."""
	from io import BytesIO
	from PIL import Image, ImageTk
	try:
		im = Image.open(BytesIO(source) if isinstance(source, bytes) else source)
		im = im.convert("RGBA")
		im.thumbnail(box)
		return ImageTk.PhotoImage(im)
	except Exception:  # (DDS / TGA variants PIL can't read, broken downloads)
		return None


class GFX(ttk.Frame):
	def __init__(self, parent, todo):
		super().__init__(parent)
		self.todo = todo
		self.app = todo.app
		self.items, self.by_id, self.scan_items, self.present = [], {}, [], []
		self._hist, self._hist_at, self.groups = [], -1, {}
		top = todo.winfo_toplevel()
		top.bind("<Button-4>", lambda ev: self.mouse_nav(ev, -1), add="+")  # (Windows: the mouse's back / forward buttons)
		top.bind("<Button-5>", lambda ev: self.mouse_nav(ev, 1), add="+")
		self.scanned = None  # (when the items on screen were found)
		self._scanning = False
		self._ai, self._ai_sig = {}, None
		self._thumbs, self._link_photos = [], {}
		self.cur = None
		self.card = None
		self._job = None
		self.load_cache()

		top = ttk.Frame(self)
		top.pack(fill="x", pady=(6, 4))
		self.view = tk.StringVar(value=self.app.config.get("gfx_view", "list"))
		for key, text in (("list", "📋 List"), ("swipe", "🃏 Swipe for a task"), ("review", "🔎 Review swiper")):
			ttk.Radiobutton(top, text=text, variable=self.view, value=key, command=self.view_changed,
							style="View.TRadiobutton").pack(side="left", padx=(0, 4))
		ttk.Button(top, text="↻ Rescan the mod", command=self.rescan).pack(side="left", padx=(16, 4))
		ttk.Button(top, text="🤖 Ask AI for suggestions...", command=self.ask_ai).pack(side="left", padx=4)
		ttk.Button(top, text="🔀 Before / after...", command=lambda: __import__("gfx_compare").Compare(self)).pack(side="left", padx=4)
		undo = ttk.Button(top, text="↶ Undo", command=self.todo.undo)
		undo.pack(side="left", padx=(12, 4))
		self.todo.register_undo_button(undo)
		import remini
		b = ttk.Button(top, text="✨ Remini", command=lambda: remini.start(self, self.remini_path()))
		b.pack(side="left", padx=4)
		remini.Tooltip(b, remini.TIP)
		self.scan_label = ttk.Label(top, text="", style="Muted.TLabel")
		self.scan_label.pack(side="left", padx=8)

		# ---- 📋 List: sections and filters | the missing pictures | the one picked ----
		self.list_view = pw = ttk.PanedWindow(self, orient="horizontal")
		left = ttk.Frame(pw, padding=(0, 0, 8, 0), width=ui.px(260))
		left.pack_propagate(False)
		pw.add(left, weight=0)
		self.problem = tk.StringVar(value=self.app.config.get("gfx_problem", "missing"))
		pf = ttk.Frame(left)
		pf.pack(fill="x", pady=(0, 6))
		self.problem_buttons = {}
		for key, text in PROBLEMS:
			b = self.problem_buttons[key] = ttk.Radiobutton(pf, text=text, variable=self.problem, value=key, command=self.problem_changed,
															style="View.TRadiobutton")
			b.pack(fill="x", pady=1)
		sec = ui.Section(left, "GFX", "gfx_sections", self.app, expand=False).place_in(fill="x")
		self.section = tk.StringVar(value=self.app.config.get("gfx_section", "culture"))
		self.section_buttons = {}
		for key, text in SECTIONS + (("all", "✱ All of them"),):
			b = self.section_buttons[key] = ttk.Radiobutton(sec.body, text=text, variable=self.section, value=key,
															command=self.section_changed, style="View.TRadiobutton")
			b.pack(fill="x", pady=1)
		sec = ui.Section(left, "Show", "gfx_filters", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.show = tk.StringVar(value=SHOW[0])
		ttk.Combobox(sec.body, textvariable=self.show, values=SHOW, state="readonly").pack(fill="x")
		self.kind = tk.StringVar(value="All kinds")
		self.kind_box = ttk.Combobox(sec.body, textvariable=self.kind, state="readonly")
		self.kind_box.pack(fill="x", pady=(4, 0))
		self.search = tk.StringVar()
		sf = ttk.Frame(sec.body)
		sf.pack(fill="x", pady=(4, 0))
		ttk.Label(sf, text="🔍").pack(side="left")
		ttk.Entry(sf, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=(4, 0))
		for v in (self.show, self.kind, self.search):
			v.trace_add("write", lambda *_: self.fill_list())
		sec = ui.Section(left, "📈 Progress", "gfx_progress", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.progress_box = sec.body
		ttk.Label(left, text="Right-click a row for more. Swipe mode deals them one at a time.", style="Muted.TLabel",
				  wraplength=ui.px(240)).pack(anchor="w", pady=(8, 0))

		mid = ttk.Frame(pw)
		pw.add(mid, weight=3)
		t = self.tree = ttk.Treeview(mid, columns=("kind", "detail", "sugg", "status"), show="tree headings", selectmode="extended")
		for col, text, width in (("#0", "Name", 220), ("kind", "Kind", 130), ("detail", "Detail", 300), ("sugg", "", 46), ("status", "Status", 140)):
			t.heading(col, text=text)
			t.column(col, width=ui.px(width), stretch=col in ("#0", "detail"), anchor="center" if col == "sugg" else "w")
		ys = ttk.Scrollbar(mid, command=t.yview)
		t.configure(yscrollcommand=ys.set)
		ys.pack(side="right", fill="y")
		t.pack(side="left", fill="both", expand=True)
		ui.sortable(t)
		t.tag_configure("not_missing", foreground="#888888")
		t.tag_configure("taken", foreground="#2e7d4a")
		t.tag_configure("made", foreground="#2e7d4a", font="om_bold")
		t.tag_configure("clarify", foreground=CLARIFY_COLOUR)
		t.tag_configure("group_done", foreground="#2e7d4a", font="om_bold")  # (its own picture is done; only its children aren't)
		t.tag_configure("group", font="om_bold")
		t.bind("<<TreeviewSelect>>", lambda ev: self.picked())
		t.bind("<Button-3>", self.row_menu)

		right = ttk.Frame(pw, padding=(8, 0, 0, 0), width=ui.px(430))
		pw.add(right, weight=2)
		self.detail = ui.ScrollFrame(right)
		self.detail.pack(fill="both", expand=True)

		# ---- 🃏 Swipe ----
		self.swipe_view = sv = ttk.Frame(self)
		bar = ttk.Frame(sv)
		bar.pack(fill="x", pady=(0, 4))
		ttk.Label(bar, text="Deal from:").pack(side="left")
		chosen = self.app.config.get("gfx_swipe_sections") or [k for k, _ in SECTIONS]
		self.swipe_sections = {}
		for key, text in SECTIONS:
			v = self.swipe_sections[key] = tk.BooleanVar(value=key in chosen)
			ttk.Checkbutton(bar, text=text, variable=v, command=self.swipe_sections_changed).pack(side="left", padx=4)
		self.skipped_btn = ttk.Button(bar, text="", command=self.reset_skipped)
		self.skipped_btn.pack(side="right")
		self.canvas = tk.Canvas(sv, highlightthickness=0, background=ui.P.get("background", "#f0f0f0"))
		self.canvas.pack(fill="both", expand=True)
		ui.THEME_HOOKS.append(self.card_theme_changed)
		self.canvas.bind("<Destroy>", self.card_theme_destroyed)
		self.canvas.bind("<Configure>", lambda ev: self.draw_card())
		self.canvas.bind("<ButtonPress-1>", self.drag_start)
		self.canvas.bind("<B1-Motion>", self.drag_move)
		self.canvas.bind("<ButtonRelease-1>", self.drag_end)
		buttons = ttk.Frame(sv)
		buttons.pack(pady=(4, 8))
		self.swipe_undo_btn = ttk.Button(buttons, text="↶ Undo  (Backspace)", command=self.swipe_undo, width=20, state="disabled")
		self.swipe_undo_btn.pack(side="left", padx=(4, 12))
		self.swiped = []  # ((item, way)) this time, last last: ↶ Undo brings them back
		self.canvas.bind("<BackSpace>", lambda ev: self.swipe_undo())
		for text, fn in (("✗ Not this one  (←)", lambda: self.swipe(-1)), ("✓ Not actually missing  (↓)", self.swipe_not_missing),
						 ("🔎 Details", self.swipe_details), ("♥ I'll make it  (→)", lambda: self.swipe(1))):
			ttk.Button(buttons, text=text, command=fn, width=24).pack(side="left", padx=4)
		for key, fn in (("<Left>", lambda ev: self.swipe(-1)), ("<Right>", lambda ev: self.swipe(1)), ("<Down>", lambda ev: self.swipe_not_missing())):
			self.canvas.bind(key, fn)
		# ---- 🔎 Review swiper ----
		import gfx_review
		self.review_view = gfx_review.ReviewSwiper(self)
		self.view_changed(save=False)

	def remini_path(self):
		"""✨ Remini's picture: the Review swiper's card, else the picked item's picture (None: Remini asks for a file)."""
		item = self.review_view.card if self.view.get() == "review" else self.card if self.view.get() == "swipe" else self.cur
		if not item:
			return None
		own = [] if problem(item) == "missing" else list(item.get("refs") or [])[:1]  # (a missing one's refs are other pictures)
		for p in [item.get("path")] + own + [item.get("file")]:
			if p:
				full = p if os.path.isabs(p) else os.path.join(self.app.mod_root, p)
				if os.path.isfile(full):
					return full
		return None

	# ---------- data ----------
	def store(self):
		return self.todo.data.setdefault("gfx", {}).setdefault("items", {})

	def rec(self, item_id, make=False):
		s = self.store()
		if make and item_id not in s:
			s[item_id] = {}
		return s[item_id] if item_id in s else {}  # (not s.get() or {}: a record just made is empty, and still the one to fill)

	def touch(self, item_id, feedback=True):
		self.store()[item_id]["updated"] = stamp()
		self.todo.save(feedback=feedback)

	def ai(self):
		"""gfx_suggestions.json (read again when it changes): {"items": {id: {suggestion, links, by}}}."""
		path = os.path.join(paths.TOOL, AI_FILE)
		try:
			sig = os.stat(path).st_mtime_ns
		except OSError:
			return {}
		if sig != self._ai_sig:
			try:
				with open(path, encoding="utf-8") as f:
					self._ai = json.load(f).get("items", {})
			except (OSError, ValueError):
				self._ai = {}
			self._ai_sig = sig
		return self._ai

	def marks(self, item):
		"""Beside Status: 🤖 an AI has suggested something for it (gfx_suggestions.json), 📝 a person has (its Notes, or a
		suggestion in that file signed by a dev)."""
		ai = self.ai().get(item["id"]) or {}
		by = (ai.get("by") or "Claude") if ai.get("suggestion") or ai.get("links") else None
		rec = self.rec(item["id"])
		human = bool((rec.get("note") or "").strip() or (rec.get("human_suggestion") or "").strip()) or (by is not None and by not in AI_NAMES)
		return ("🤖" if by in AI_NAMES else "") + ("📝" if human else "")

	def status(self, item):
		if problem(item) == "rework":
			return "taken" if (self.rework_marks().get(item.get("marked") or "") or {}).get("claimed") else "missing"
		r = self.rec(item["id"])
		if r.get("not_missing"):
			return "not_missing"
		task = self.todo.task(r["task"]) if r.get("task") else None
		if task and task.get("status") == "Completed":
			return "made"  # (done; it leaves the list when a rescan finds the picture in the mod)
		return "taken" if task and task.get("status") != "Not Possible" else "missing"

	def status_text(self, item):
		if problem(item) == "rework":
			who = (self.rework_marks().get(item.get("marked") or "") or {}).get("claimed")
			return f"✋ {', '.join(who)}" if who else f"🔁 {item.get('reason', 'rework')}"
		r = self.rec(item["id"])
		s = self.status(item)
		if s == "not_missing":
			return f"{'kept' if problem(item) == 'unused' else '✓ not missing'} ({r['not_missing'].get('by', '')})"
		if s in ("taken", "made"):
			task = self.todo.task(r["task"])
			return f"{'✓ made' if s == 'made' else '✋'} {r['task']} {', '.join(task.get('devs') or [])}"
		return {"broken": "broken", "unused": "unused", "rework": f"🔁 {item.get('reason', 'rework')}"}.get(problem(item), "missing")

	def load_cache(self):
		"""The last scan, so the tab is filled at once (a fresh scan follows in the background). A PC that has never
		scanned starts from the shared one in git (gfx_scan_seed.json.gz): the first scan of its own takes minutes."""
		try:
			got = read_cache()
			self.set_items(got["items"], got.get("when"))
			return
		except (OSError, ValueError, KeyError, EOFError):
			pass
		got = read_seed(self.app.mod_root)
		if got and got.get("items"):
			self.set_items(got["items"], got.get("when"))
			self.from_seed = True

	def set_items(self, items, when):
		self.scan_items = items
		self.scanned = when
		self.refresh_items()

	def game_dir(self):
		"""This PC's HOI4 folder (for "game:" pictures), found once."""
		if not hasattr(self, "_game_dir"):
			try:
				from cm_data import find_game
				self._game_dir = find_game(self.app.mod_root) or ""
			except Exception:
				self._game_dir = ""
		return self._game_dir

	def rework_marks(self):
		"""Pictures marked 🔁 Needs Rework in this tab (shared, synced): {key: {file, name, section, family, family_name,
		reason, note, by, when, link}}."""
		return self.todo.data.setdefault("gfx", {}).setdefault("rework", {})

	def refresh_items(self):
		"""The scan's items plus the shared 🔁 rework list (pictures marked here, portraits marked in Country Master)."""
		scan = [x for x in getattr(self, "scan_items", []) if problem(x) not in ("rework", "present")]  # (older scans had Country Master's file)
		self.present = [x for x in getattr(self, "scan_items", []) if problem(x) == "present"]  # (🔎 Review swiper's pictures)
		names = {x["family"]: x["family_name"] for x in scan if x.get("family") and x.get("family_name")}
		extra = []
		for key, m in self.rework_marks().items():
			f = m.get("file") or ""
			full = (os.path.join(self.game_dir(), f[5:]) if f.startswith("game:") else f if os.path.isabs(f) else os.path.join(self.app.mod_root, f)) if f else ""
			kind = {"generic": "Generic portrait · ", "leader": "Leader portrait · ", "portrait": "Leader portrait · "}.get(m.get("portrait_kind"), "")
			extra.append(dict(id="rework:" + key, section=m.get("section", "portrait"), kind="rework", problem="rework",
				name=m.get("name") or os.path.basename(f), token=m.get("sprite") or m.get("name", ""), file=f, refs=[full] if full else [],
				reason=m.get("reason", REWORK_REASONS[0]), mark_note=m.get("note", ""), marked=key, claimed=m.get("claimed") or [],
				detail=f"{m.get('reason', '')} · {kind}" + (f"used by {m['used']} · " if m.get("used") else "") +
					   f"marked by {m.get('by', '?')} on {(m.get('when') or '')[:10]}" + (f" · {m['note']}" if m.get("note") else ""),
				family=m.get("family") or "rework", family_name=names.get(m.get("family")) or m.get("family_name") or "Pictures to rework",
				link=m.get("link"), search=m.get("name", ""), note=""))
		self.items = scan + extra
		self.by_id = {x["id"]: x for x in self.items}

	def ask_rework(self, name, section=None):
		"""(reason, note) or None. section: which reasons fit (portraits: Needs a Remini; icons: Looks too AI)."""
		w = tk.Toplevel(self)
		w.title("Needs rework")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=f"🔁 {name} needs rework", font="om_bold").pack(anchor="w")
		ttk.Label(f, text="It goes into 🔁 Needs Rework for someone to claim.", style="Muted.TLabel").pack(anchor="w", pady=(2, 6))
		reason = tk.StringVar(value=REWORK_REASONS[0])
		for r in reasons_for(section) if section else REWORK_REASONS:
			ttk.Radiobutton(f, text=r, variable=reason, value=r).pack(anchor="w")
		ttk.Label(f, text="What's wrong with it? (optional)").pack(anchor="w", pady=(8, 0))
		note = tk.Text(f, height=3, width=48, wrap="word", font="om_body")
		note.pack(fill="x")
		out = {}

		def ok():
			out["r"] = (reason.get(), note.get("1.0", "end").strip())
			w.destroy()
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(10, 0))
		ttk.Button(bf, text="🔁 Needs rework", command=ok).pack(side="right")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="right", padx=6)
		w.grab_set()
		w.wait_window()
		return out.get("r")

	def rework_key(self, path):
		root = os.path.normcase(os.path.abspath(self.app.mod_root))
		full = os.path.abspath(path)
		rel = os.path.relpath(full, self.app.mod_root).replace("\\", "/") if os.path.normcase(full).startswith(root + os.sep) else full
		return rel, re.sub(r"[^a-z0-9_./-]+", "_", rel.lower())

	def mark_rework(self, path, source, got=None):
		"""Right-click a picture under 'Look at these' (or the picture itself) > 🔁 Needs rework..."""
		rel, key = self.rework_key(path)
		got = got or self.ask_rework(os.path.basename(path), (source or {}).get("section"))
		if got is None:
			return
		fam_key, fam_name = family(source) if source else ("rework", "Pictures to rework")
		self.rework_marks()[key] = {"file": rel, "name": os.path.splitext(os.path.basename(path))[0], "section": (source or {}).get("section", "portrait"),
									"family": fam_key, "family_name": fam_name, "reason": got[0], "note": got[1], "by": self.todo.me.get(),
									"when": stamp(), "link": (source or {}).get("link")}
		self.todo.rework_task()  # (the To Do's shared 🔁 task counts it)
		self.todo.save()
		self.refresh_items()
		self.fill_list()
		self.app.set_status(f"GFX: {os.path.basename(path)} is in 🔁 Needs Rework ({got[0]}).")
		return True

	def unmark_rework(self, item, quiet=False):
		"""✓ Reworked / not needed: off the shared list for everyone (a portrait also leaves this PC's Country Master list)."""
		m = self.rework_marks().get(item.get("marked") or "") or {}
		if unmark(self.todo.data, item.get("marked") or "", self.todo.me.get()):
			if m.get("sprite"):
				unmark_cm_file(self.app.mod_root, m["sprite"])
			self.todo.rework_task()
			self.todo.save()
			self.refresh_items()
			if not quiet:
				self.fill_list()
				self.show_item(None)
				self.app.set_status(f"GFX: {item['name']} is off the rework list.")

	def ref_menu(self, ev, path, item):
		_, key = self.rework_key(path)
		m = tk.Menu(self, tearoff=0)
		if key in self.rework_marks() or any(problem(x) == "rework" and x.get("refs") and os.path.normcase(os.path.abspath(x["refs"][0])) == os.path.normcase(os.path.abspath(path))
											 for x in self.items if x.get("refs")):
			m.add_command(label="🔁 Already in Needs Rework", state="disabled")
		else:
			m.add_command(label="🔁 Needs rework...", command=lambda: self.mark_rework(path, item))
		m.add_command(label="Look at it", command=lambda: self.view_picture(path))
		m.tk_popup(ev.x_root, ev.y_root)

	def rescan(self, quiet=False):
		if self._scanning:
			return
		self._scanning = True
		self.scan_label.config(text="Scanning the mod...")
		result = {}
		started = time.monotonic()
		first = not self.items

		def work():
			try:
				result["items"] = scan(self.app.mod_root, lambda text: result.update(progress=text))
			except Exception as ex:  # (a file the readers choke on: say so instead of dying in the thread)
				result["error"] = f"{type(ex).__name__}: {ex}"

		th = threading.Thread(target=work, daemon=True)
		th.start()

		def wait():
			if th.is_alive():
				if self.winfo_exists():
					step = (result.get("progress") or "Scanning the mod...").removeprefix("GFX: ")
					took = int(time.monotonic() - started)
					self.scan_label.config(text=f"Scanning: {step} ({took // 60}:{took % 60:02d})")
					self.list_note("🔍 Scanning the mod for missing pictures...\n\n" + step + f"\n({took // 60}:{took % 60:02d} so far)\n\n"
								   "The first scan on a PC takes a few minutes (about 5); after that the list shows at once and\n"
								   "a fresh scan runs quietly in the background. You can keep working meanwhile."
								   if first and not self.items else None)
				self.after(300, wait)
				return
			self._scanning = False
			if not self.winfo_exists():
				return
			self.list_note(None)
			if "error" in result:
				self.scan_label.config(text="Scan failed")
				if not self.items:
					self.list_note("⚠ The GFX scan failed:\n\n" + result["error"] + "\n\nRescan to try again, or tell Mike / Claude (Copy the text).")
				if not quiet:
					messagebox.showerror(APP_NAME, "The GFX scan failed:\n" + result["error"], parent=self)
				return
			self.set_items(result["items"], stamp())
			try:
				write_cache(self.scanned, self.items + self.present)
			except OSError:
				pass
			self.close_found()
			if gfx_checks.record(self.todo.data, self.items):
				self.todo.save(feedback=False)
			self.fill()
			self.app.set_status(f"GFX: {len(self.items)} missing pictures found.")
		self.after(300, wait)

	def list_note(self, text):
		"""A message over the (empty) list: the scan's progress, or its error. None hides it."""
		note = getattr(self, "_list_note", None)
		if text is None:
			if note is not None:
				note.place_forget()
			return
		if note is None:
			note = self._list_note = ttk.Label(self.tree.master, text="", justify="center", anchor="center", padding=16)
		note.config(text=text)
		note.place(relx=0.5, rely=0.35, anchor="center")
		note.lift()

	def close_found(self):
		"""Tasks made from GFX items whose picture is in the mod now: completed."""
		changed = False
		for item_id, r in self.store().items():
			task = self.todo.task(r["task"]) if r.get("task") else None
			if task and item_id not in self.by_id and not r.get("not_missing") and task.get("status") not in ("Completed", "Not Possible"):  # (made outside the tab)
				changed |= self.todo.change(task, "status", "Completed", note="GFX scan: the picture is in the mod now", who="Organisation Master")
		if changed:
			self.todo.save()
			self.todo.fill()

	# ---------- the page ----------
	def view_changed(self, save=True):
		if save:
			self.app.config["gfx_view"] = self.view.get()
			self.app.save_config()
		for frame in (self.list_view, self.swipe_view, self.review_view):
			frame.pack_forget()
		if self.view.get() == "swipe":
			self.swipe_view.pack(fill="both", expand=True)
			self.deal()
			self.canvas.focus_set()
		elif self.view.get() == "review":
			self.review_view.pack(fill="both", expand=True)
			self.review_view.deal()
		else:
			self.list_view.pack(fill="both", expand=True)
			self.fill_list()

	def fill(self):
		"""(the To Do pane's way in: on entering GFX mode and when the synced data changed)"""
		if self.scanned is None and not self._scanning:
			self.rescan(quiet=True)
		elif not self._scanning and not getattr(self, "_scanned_once", False):
			self._scanned_once = True
			self.rescan(quiet=True)  # (the cached list is on screen; fresh one in a few seconds)
		self.refresh_items()  # (rework marks from the others)
		self.ai_clarifications()
		self.scan_label.config(text=f"{sum(1 for x in self.items if problem(x) == 'missing')} missing · scanned {self.scanned.replace('T', ' ')[:16]}" if self.scanned else "")
		if self.view.get() == "swipe":
			if self.card is None or self.card["id"] not in self.by_id:
				self.deal()
		elif self.view.get() == "review":
			self.review_view.deal(keep=True)
		else:
			self.fill_list()

	def problem_changed(self):
		self.app.config["gfx_problem"] = self.problem.get()
		self.app.save_config()
		self.kind.set("All kinds")
		self.fill_list()

	def fill_progress(self):
		"""📈 Per section: left now, and how many fewer since the history began / this month."""
		box = self.progress_box
		for w in box.winfo_children():
			w.destroy()
		rows = gfx_checks.history(self.todo.data)
		now = gfx_checks.counts(self.items)
		if not rows:
			ttk.Label(box, text="Starts counting after the first scan.", style="Muted.TLabel").pack(anchor="w")
			return
		first_day, first = rows[0]
		month = time.strftime("%Y-%m")
		before = [v for d, v in rows if d[:7] < month]
		month_start = before[-1] if before else next(v for d, v in rows if d[:7] == month) if any(d[:7] == month for d, _ in rows) else first
		for key, text in SECTIONS:
			start, left = first.get(key, 0), now.get(key, 0)
			done = max(0, start - left)
			f = ttk.Frame(box)
			f.pack(fill="x", pady=1)
			ttk.Label(f, text=f"{text}: {left} left" + (f" · ✓ {done} done" if done else ""), font="om_small").pack(anchor="w")
			bar = ttk.Progressbar(f, maximum=max(start, left, 1), value=done)
			bar.pack(fill="x")
			gain = month_start.get(key, 0) - left
			if gain:
				ttk.Label(f, text=f"✓ {gain} fewer this month" if gain > 0 else f"{-gain} new this month", style="Muted.TLabel").pack(anchor="w")
		ttk.Label(box, text=f"Since {first_day} (missing + broken).", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

	def section_changed(self):
		self.app.config["gfx_section"] = self.section.get()
		self.app.save_config()
		self.kind.set("All kinds")
		self.fill_list()

	def shown_items(self):
		sec, show, kind, what = self.section.get(), self.show.get(), self.kind.get(), self.problem.get()
		words = self.search.get().lower().split()
		out = []
		for x in self.items:
			if problem(x) != what:
				continue
			if sec != "all" and x["section"] != sec:
				continue
			if kind != "All kinds" and KIND_LABEL.get(x["kind"]) != kind:
				continue
			s = self.status(x)
			if show == "❓ Needs clarification":
				if not self.clarify(x):
					continue
			elif show != "Everything" and s != {"To do": "missing", "Taken (has a task)": "taken",
												"✓ Made (until a rescan finds it)": "made"}.get(show, "not_missing"):
				continue
			text = f"{x['name']} {x.get('token', '')} {x['detail']}".lower()
			if all(w in text for w in words):
				out.append(x)
		return out

	def fill_list(self):
		if not hasattr(self, "tree"):
			return
		what = self.problem.get()
		counts = {k: sum(1 for x in self.items if x["section"] == k and problem(x) == what and self.status(x) == "missing") for k, _ in SECTIONS}
		for p, text in PROBLEMS:
			n = sum(1 for x in self.items if problem(x) == p and self.status(x) == "missing")
			self.problem_buttons[p].config(text=f"{text} ({n})")
		self.fill_progress()
		for k, text in SECTIONS:
			self.section_buttons[k].config(text=f"{text} ({counts[k]})")
		self.section_buttons["all"].config(text=f"✱ All of them ({sum(counts.values())})")
		sec = self.section.get()
		kinds = sorted({KIND_LABEL[x["kind"]] for x in self.items if (sec == "all" or x["section"] == sec) and problem(x) == what})
		self.kind_box.config(values=["All kinds"] + kinds)
		t = self.tree
		keep = t.selection()
		opened = {i for i in t.get_children() if t.item(i, "open")} | getattr(self, "_opened", set())
		t.delete(*t.get_children())
		rows = self.shown_items()
		ids = {x["id"] for x in rows}
		kids = {}
		for x in rows:
			pid = parent_id(x)
			if pid:
				kids.setdefault(pid, []).append(x)
		self.groups = {}
		searching = bool(self.search.get().strip())

		def row(x, parent=""):
			s = self.status(x)
			tags = ((s,) if s != "missing" else ()) + (("clarify",) if self.clarify(x) else ())
			n = len(kids.get(x["id"], []))
			t.insert(parent, "end", iid=x["id"], text=("❓ " if self.clarify(x) else "") + x["name"] + (f"  ({n} inside)" if n else ""),
					 values=(KIND_LABEL[x["kind"]], x["detail"], self.marks(x), self.status_text(x)), tags=tags,
					 open=x["id"] in opened or searching)
		for x in rows:
			pid = parent_id(x)
			if pid and pid in ids:
				continue  # (inside its parent's row)
			if pid:
				if t.exists("grp:" + pid):
					continue  # (its family's row is in already, with all of them inside)
				# (its parent isn't in this list: a row for it, green when its own picture is done)
				rel = next((r for r in x.get("related") or [] if r.get("role") == "parent"), {})
				listed = self.by_id.get(pid)
				done = listed is None or self.status(listed) in ("made", "not_missing")
				name = rel.get("name") or x.get("parent") or x.get("main") or pid.rsplit(":", 1)[-1]
				self.groups[pid] = dict(id=pid, name=name, path=rel.get("path"), kind=pid.split(":")[1], done=done, children=kids[pid])
				t.insert("", "end", iid="grp:" + pid, text=f"{name}  ({len(kids[pid])} inside)",
						 values=(KIND_LABEL[{"culture": "culture", "rgroup": "rgroup", "main": "main_ideology"}[pid.split(":")[1]]],
								 "✓ its own picture is done" if done else "its own picture is missing too (another list)", "",
								 "✓ done" if done else ""),
						 tags=("group_done",) if done else ("group",), open="grp:" + pid in opened or searching)
				for k in kids[pid]:
					row(k, "grp:" + pid)
				continue
			row(x)
			for k in kids.get(x["id"], []):
				row(k, x["id"])
		self._opened = {i for i in opened if t.exists(i)}
		ui.stripe(t)
		keep = [i for i in keep if t.exists(i)]
		if keep:
			t.selection_set(keep)
		elif self.cur and t.exists(self.cur["id"]):
			t.selection_set(self.cur["id"])
		else:
			self.show_item(None)

	def picked(self):
		sel = self.tree.selection()
		if len(sel) == 1 and sel[0].startswith("grp:"):
			return self.show_group(self.groups.get(sel[0][4:]))
		item = self.by_id.get(sel[0]) if len(sel) == 1 else None
		if item is not self.cur or item is None:
			self.show_item(item, count=len(sel))

	def show_group(self, g):
		"""A parent row (its own picture done, or in another list): its picture, its children to do, ✋ them all."""
		box = self.detail.inner
		for w in box.winfo_children():
			w.destroy()
		self.cur = None
		self._thumbs = []
		if not g:
			return
		head = tk.Frame(box, background="#2e7d4a" if g["done"] else SECTION_COLOUR.get(g["children"][0]["section"], "#555"))
		head.pack(fill="x")
		tk.Label(head, text=g["name"], font="om_head", foreground="white", background=head["background"], anchor="w").pack(fill="x", padx=8, pady=(6, 0))
		todo = [x for x in g["children"] if self.status(x) == "missing"]
		tk.Label(head, text=("✓ Its own picture is done" if g["done"] else "Its own picture isn't done either") +
				 f" · {len(g['children'])} inside need doing ({len(todo)} not taken yet)", font="om_small", foreground="white",
				 background=head["background"], anchor="w").pack(fill="x", padx=8, pady=(0, 6))
		if g.get("path") and os.path.isfile(g["path"]):
			sec = ttk.LabelFrame(box, text="Its picture (do the ones inside in the same style)", padding=6)
			sec.pack(fill="x", pady=(8, 0))
			row = ttk.Frame(sec)
			row.pack(anchor="w")
			self.thumb(row, g["path"], g["name"], lambda ev: self.ref_menu(ev, g["path"], g["children"][0]))
		bf = ttk.Frame(box)
		bf.pack(fill="x", pady=(8, 0))
		if todo:
			ttk.Button(bf, text=f"✋ I'll do all {len(todo)} inside", style="Tool.TButton", command=lambda: self.claim(todo)).pack(side="left", padx=(0, 4))
			ttk.Button(bf, text=f"🤖 Ask AI for these {len(todo)}", style="Tool.TButton", command=lambda: self.ask_ai(todo)).pack(side="left", padx=(0, 4))
		if g["id"] in self.by_id:
			ttk.Button(bf, text="🔍 Its own entry", style="Tool.TButton", command=lambda: self.go_item(g["id"])).pack(side="left")
		sec = ttk.LabelFrame(box, text=f"Inside ({len(g['children'])})", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		for x in g["children"]:
			r = ttk.Frame(sec)
			r.pack(fill="x")
			ttk.Button(r, text="🔍", width=3, style="Tool.TButton", command=lambda i=x["id"]: self.go_item(i)).pack(side="left")
			ttk.Label(r, text=f"{x['name']}  ·  {self.status_text(x)}  {self.marks(x)}").pack(side="left", padx=4)

	# ---------- the item picked: suggestion, references, links, pictures ----------
	def show_item(self, item, count=0, into=None):
		self.flush()
		box = into or self.detail.inner
		for w in box.winfo_children():
			w.destroy()
		if into is None:
			self.cur = item
		self._thumbs = [] if into is None else self._thumbs
		if item is None:
			ttk.Label(box, text=f"{count} picked - right-click for what to do with them all." if count > 1 else
					  "Pick a missing picture to see its suggestion, references and links.", style="Muted.TLabel").pack(anchor="w", pady=8)
			return
		r = self.rec(item["id"])
		wrap = ui.px(400)
		if into is None:
			self.remember(item["id"])
		head = tk.Frame(box, background=SECTION_COLOUR[item["section"]])
		head.pack(fill="x")
		nav = tk.Frame(head, background=head["background"])
		nav.pack(side="right", anchor="n", padx=4, pady=4)
		for text, step in (("◀", -1), ("▶", 1)):
			able = 0 <= self._hist_at + step < len(self._hist)
			b = tk.Label(nav, text=text, foreground="white" if able else "#bbbbbb", background=head["background"], font="om_head",
						 cursor="hand2" if able else "")
			b.pack(side="left")
			if able:
				b.bind("<Button-1>", lambda ev, d=step: self.step_history(d))
		tk.Label(head, text=item["name"], font="om_head", foreground="white", background=head["background"], anchor="w",
				 wraplength=wrap).pack(fill="x", padx=8, pady=(6, 0))
		tk.Label(head, text=f"{KIND_LABEL[item['kind']]} · {item['detail']}", font="om_small", foreground="white",
				 background=head["background"], anchor="w", wraplength=wrap, justify="left").pack(fill="x", padx=8, pady=(0, 6))
		q = self.clarify(item)
		if q:
			cl = tk.Frame(box, background=CLARIFY_COLOUR)
			cl.pack(fill="x", pady=(4, 0))
			tk.Label(cl, text=f"❓ Needs clarification ({q.get('by', '?')}): {q.get('question', '')}", foreground="white",
					 background=CLARIFY_COLOUR, wraplength=wrap, justify="left", anchor="w").pack(fill="x", padx=8, pady=4)
			cb = ttk.Frame(box)
			cb.pack(fill="x", pady=(2, 0))
			if q.get("idea") and self.todo.idea_pane.idea(q["idea"]):
				ttk.Button(cb, text="💡 See the idea", style="Tool.TButton", command=lambda: self.go_idea(q["idea"])).pack(side="left", padx=(0, 4))
			ttk.Button(cb, text="✓ Clarified", style="Tool.TButton", command=lambda: self.set_clarified([item])).pack(side="left")
		ttk.Label(box, text=self.status_text(item), style="Head.TLabel").pack(anchor="w", pady=(6, 0))
		if r.get("not_missing"):
			nm = r["not_missing"]
			ttk.Label(box, text=f"Marked not missing by {nm.get('by', '?')} ({nm.get('when', '')[:10]}): {nm.get('reason', '')}",
					  wraplength=wrap, style="Muted.TLabel").pack(anchor="w")
		f = ttk.Frame(box)
		f.pack(fill="x", pady=(4, 0))
		ttk.Label(f, text="Should be:").pack(side="left")
		e = ttk.Entry(f, font="om_small")
		e.insert(0, item.get("file") or "(no file named yet)")
		e.config(state="readonly")
		e.pack(side="left", fill="x", expand=True, padx=4)
		if item.get("note"):
			ttk.Label(box, text="⚠ " + item["note"], foreground="#c0392b", wraplength=wrap).pack(anchor="w")
		here = (item["file"] if os.path.isabs(item.get("file") or "") else os.path.join(self.app.mod_root, item.get("file") or "")) \
			if item.get("file") and problem(item) in ("unused", "broken", "rework") else None
		if here and os.path.isfile(here):
			sec = ttk.LabelFrame(box, text="This picture (click to look at it)", padding=6)
			sec.pack(fill="x", pady=(6, 0))
			row = ttk.Frame(sec)
			row.pack(anchor="w")
			self.thumb(row, here, os.path.basename(here), lambda ev: self.ref_menu(ev, here, item))

		bf = ttk.Frame(box)
		bf.pack(fill="x", pady=(6, 0))
		bf2 = ttk.Frame(box)
		bf2.pack(fill="x", pady=(2, 0))
		if item.get("link"):
			master = master_links.parse(item["link"])["master"]
			ttk.Button(bf, text=f"Open in {master}", style="Tool.TButton",
					   command=lambda: self.app.navigate_master(item["link"])).pack(side="left", padx=(0, 4))
		ttk.Button(bf, text="📂 Folder", style="Tool.TButton", command=lambda: self.open_folder(item)).pack(side="left", padx=(0, 4))
		bf3 = ttk.Frame(box)
		bf3.pack(fill="x", pady=(2, 0))
		unused = problem(item) == "unused"
		if self.status(item) in ("taken", "made"):
			ttk.Button(bf2, text=f"Go to {r['task']}", style="Tool.TButton", command=lambda: self.go_task(r["task"])).pack(side="left", padx=(0, 4))
		if self.status(item) == "taken":
			ttk.Button(bf2, text="✓ I made it", style="Tool.TButton", command=lambda: self.made([item])).pack(side="left", padx=(0, 4))
		elif self.status(item) == "missing" and unused:
			ttk.Button(bf2, text="🗑 Remove from the mod...", style="Tool.TButton", command=lambda: self.remove_unused([item])).pack(side="left", padx=(0, 4))
		elif self.status(item) == "missing":
			ttk.Button(bf2, text={"broken": "✋ I'll fix it", "rework": "✋ I'll rework it"}.get(problem(item), "✋ I'll make it"), style="Tool.TButton",
					   command=lambda: self.claim([item])).pack(side="left", padx=(0, 4))
			fam = self.family_open(item)
			if len(fam) > 1:
				ttk.Button(bf2, text=f"✋ The whole family ({len(fam)})", style="Tool.TButton",
						   command=lambda: self.claim_family(item)).pack(side="left", padx=(0, 4))
		if not q:
			ttk.Button(bf3, text="❓ Needs clarification...", style="Tool.TButton", command=lambda: self.ask_clarify([item])).pack(side="left", padx=(0, 4))
		if problem(item) == "rework":
			ttk.Button(bf3, text="🔀 Before / now", style="Tool.TButton",
					   command=lambda: __import__("gfx_compare").Compare(self, item.get("marked"))).pack(side="left", padx=(0, 4))
			ttk.Button(bf3, text="✓ Reworked / not needed", style="Tool.TButton", command=lambda: self.unmark_rework(item)).pack(side="left")
		elif r.get("not_missing"):
			ttk.Button(bf3, text="↺ Undo" if unused else "↺ It is missing", style="Tool.TButton", command=lambda: self.set_not_missing([item], None)).pack(side="left")
		elif unused:
			ttk.Button(bf3, text="Keep it...", style="Tool.TButton", command=lambda: self.ask_not_missing([item], keep=True)).pack(side="left")
		else:
			ttk.Button(bf3, text="✓ Not actually missing...", style="Tool.TButton", command=lambda: self.ask_not_missing([item])).pack(side="left")

		self.related_box(box, item)
		text, by_ai = suggestion(item, self.ai())
		sec = ttk.LabelFrame(box, text="🤖 AI suggestion" if by_ai else "🤖 AI suggestion (none yet: this one is from the mod's data - 🤖 Ask AI)", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		ttk.Label(sec, text=text, wraplength=wrap - ui.px(20), justify="left").pack(anchor="w")
		if by_ai:
			who = (self.ai().get(item["id"]) or {}).get("by") or "AI"
			rate = r.get("ai_rating") or {}
			row = ttk.Frame(sec)
			row.pack(fill="x", pady=(4, 0))
			ttk.Label(row, text=f"by {who}", style="Muted.TLabel").pack(side="left")
			ttk.Button(row, text="👎 Not good...", style="Tool.TButton", command=lambda: self.rate_ai(item, False)).pack(side="right")
			ttk.Button(row, text="👍 Good", style="Tool.TButton", command=lambda: self.rate_ai(item, True)).pack(side="right", padx=(0, 4))
			if rate:
				older = rate.get("suggestion") and rate["suggestion"] != text
				said = ("👍 Good" if rate.get("rating") == "good" else "👎 " + ", ".join(rate.get("reasons") or ["Not good"]))
				ttk.Label(sec, text=f"Rated {said} by {rate.get('by', '?')}" + (f": \"{rate['comment']}\"" if rate.get("comment") else "")
						  + (" (an older version of it)" if older else ""), style="Muted.TLabel", wraplength=wrap - ui.px(20),
						  justify="left").pack(anchor="w", pady=(2, 0))
		sec = ttk.LabelFrame(box, text="📝 Human suggestion", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		self.human = tk.Text(sec, height=3, wrap="word", font="om_body")
		self.human.insert("1.0", r.get("human_suggestion", ""))
		self.human.pack(fill="x")
		self.human.bind("<KeyRelease>", lambda ev: self.note_changed())
		if r.get("human_by"):
			ttk.Label(sec, text=f"last written by {r['human_by']} on {(r.get('human_when') or '')[:10]}", style="Muted.TLabel").pack(anchor="w")

		same = lambda p: here and os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(here))
		refs = [p for p in item.get("refs") or [] if not same(p)]  # (the picture itself is shown above)
		if refs:
			sec = ttk.LabelFrame(box, text="Look at these (its family / its other versions)", padding=6)
			sec.pack(fill="x", pady=(8, 0))
			row = ttk.Frame(sec)
			row.pack(anchor="w")
			for path in refs:
				self.thumb(row, path, os.path.basename(path), lambda ev, p=path: self.ref_menu(ev, p, item))
			ttk.Label(sec, text="Right-click one that needs reworking.", style="Muted.TLabel").pack(anchor="w")

		sec = ttk.LabelFrame(box, text="Image links", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		bar = ttk.Frame(sec)
		bar.pack(fill="x")
		for label, fn in (("🔎 Find pictures", lambda: self.find_pictures(item)), ("+ URL...", lambda: self.add_link(item))):
			ttk.Button(bar, text=label, style="Tool.TButton", command=fn).pack(side="left", padx=(0, 4))
		links = [(f"🤖 {u}", u) for u in (self.ai().get(item["id"]) or {}).get("links", [])] + [(u, u) for u in r.get("links", [])]
		links += search_links(item)
		lb = tk.Listbox(sec, height=min(8, len(links)), font="om_small", activestyle="none")
		for label, _ in links:
			lb.insert("end", label)
		lb.pack(fill="x", pady=(4, 0))
		lb.bind("<Double-1>", lambda ev: lb.curselection() and self.open_url(links[lb.curselection()[0]][1]))
		lb.bind("<Button-3>", lambda ev: self.link_menu(ev, lb, item, links))
		pictures = [u for _, u in links if image_url(u)]
		if pictures:
			show = tk.BooleanVar(value=self.app.config.get("gfx_link_pictures", True))

			def toggle():
				self.app.config["gfx_link_pictures"] = show.get()
				self.app.save_config()
				gallery.grid_remove() if not show.get() else gallery.grid()
			ttk.Checkbutton(bar, text=f"Show pictures ({len(pictures)})", variable=show, command=toggle).pack(side="right")
			holder = ttk.Frame(sec)
			holder.pack(fill="x", pady=(4, 0))
			gallery = ttk.Frame(holder)
			gallery.grid(row=0, column=0, sticky="w")
			for n, url in enumerate(pictures):
				self.link_thumb(gallery, url).grid(row=n // 4, column=n % 4, padx=(0, 4), pady=(0, 4), sticky="nw")
			if not show.get():
				gallery.grid_remove()
		ttk.Label(sec, text="Click a picture to look at it; double-click a link to open it in your browser.", style="Muted.TLabel").pack(anchor="w")

		sec = ttk.LabelFrame(box, text="🎨 Pictures (yours: drafts, finds, the finished one)", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		bar = ttk.Frame(sec)
		bar.pack(fill="x")
		for label, fn in (("+ Picture...", lambda: self.add_picture(item)), ("📋 Paste", lambda: self.paste_picture(item))):
			ttk.Button(bar, text=label, style="Tool.TButton", command=fn).pack(side="left", padx=(0, 4))
		ttk.Button(sec, text="👁 Preview in game", style="Tool.TButton", command=lambda: self.preview(item)).pack(anchor="w", pady=(4, 0))
		pics = ttk.Frame(sec)
		pics.pack(fill="x", pady=(4, 0))
		for name in r.get("pictures", []):
			self.thumb(pics, os.path.join(self.todo.art_dir(), name), name, lambda ev, n=name: self.picture_menu(ev, item, n))

		sec = ttk.LabelFrame(box, text="Notes", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		self.note = tk.Text(sec, height=4, wrap="word", font="om_body")
		self.note.insert("1.0", r.get("note", ""))
		self.note.pack(fill="x")
		self.note.bind("<KeyRelease>", lambda ev: self.note_changed())
		self._note_item = item["id"]

	ROLE = {"culture": ("Culture", "Subculture"), "sub": ("Culture", "Subculture"), "rgroup": ("Religion group", "Religion"),
			"religion": ("Religion group", "Sect / religion"), "main_ideology": ("Ideology", "Sub-ideology"),
			"sub_ideology": ("Ideology", "Sub-ideology")}

	def related_box(self, box, item):
		"""🔗 Related: its parent and children (culture / subcultures, religion group / religions, ideology / sub-ideologies).
		Ones with a picture show it (right-click: 🔁 Needs rework); ones in these lists (missing, broken...) jump there."""
		rel = item.get("related") or []
		if not rel:
			return
		sec = ttk.LabelFrame(box, text=f"🔗 Related ({len(rel)})", padding=6)
		sec.pack(fill="x", pady=(8, 0))
		grid = ttk.Frame(sec)
		grid.pack(anchor="w")
		for n, x in enumerate(rel[:24]):
			cell = ttk.Frame(grid, padding=(0, 0, 6, 6))
			cell.grid(row=n // 4, column=n % 4, sticky="nw")
			parent_label, child_label = self.ROLE.get(x["kind"], ("Parent", "Child"))
			if x.get("path") and os.path.isfile(x["path"]):
				picture_label(cell, x["path"], lambda p=x["path"]: self.view_picture(p), lambda ev, p=x["path"]: self.ref_menu(ev, p, item),
							  box=(64, 48), keep=self._thumbs).pack_configure(side="top", anchor="w")
			listed = self.by_id.get(x["id"])
			if listed:
				ttk.Button(cell, text=f"🔍 {self.status_text(listed)}", style="Tool.TButton",
						   command=lambda i=x["id"]: self.go_item(i)).pack(anchor="w")
			ttk.Label(cell, text=f"{x['name']}\n{parent_label if x['role'] == 'parent' else child_label}", style="Muted.TLabel",
					  wraplength=ui.px(110), justify="left").pack(anchor="w")
		if len(rel) > 24:
			ttk.Label(sec, text=f"... and {len(rel) - 24} more", style="Muted.TLabel").pack(anchor="w")

	def remember(self, item_id):
		"""The items you looked at, for ◀ ▶ and the mouse's back / forward buttons (a jump drops what was ahead)."""
		if self._hist and 0 <= self._hist_at < len(self._hist) and self._hist[self._hist_at] == item_id:
			return
		self._hist = self._hist[:self._hist_at + 1] + [item_id]
		self._hist = self._hist[-100:]
		self._hist_at = len(self._hist) - 1

	def step_history(self, d):
		at = self._hist_at + d
		while 0 <= at < len(self._hist) and self._hist[at] not in self.by_id:
			at += d  # (one that's gone since: skipped)
		if 0 <= at < len(self._hist):
			self._hist_at = at
			self.go_item(self._hist[at])

	def mouse_nav(self, ev, d):
		"""The mouse's back (button 4) / forward (button 5) buttons, while GFX is on screen."""
		if self.winfo_ismapped():
			self.step_history(d)
			return "break"

	def go_item(self, item_id):
		"""Jump to an item in the list: its problem, its section, every status; picked and shown."""
		x = self.by_id.get(item_id)
		if not x:
			return
		self.problem.set(problem(x))
		self.section.set(x["section"])
		self.show.set(SHOW[-1])
		self.kind.set("All kinds")
		self.search.set("")
		if self.view.get() != "list" and hasattr(self, "view"):
			self.view.set("list")
			self.view_changed()
		self.fill_list()
		if self.tree.exists(item_id):
			up = self.tree.parent(item_id)
			if up:
				self.tree.item(up, open=True)
			self.tree.selection_set(item_id)
			self.tree.see(item_id)

	def thumb(self, parent, path, tip, on_menu=None):
		"""The same thumbnails as Ideas' pictures: click pops the picture out in the zoomable viewer."""
		lab = picture_label(parent, path, lambda: self.view_picture(path), on_menu, keep=self._thumbs, missing="(not here)")
		lab._tip = tip
		return lab

	def view_picture(self, path):
		show_picture(self, path, kind="GFX")

	def note_changed(self):
		if self._job:
			self.after_cancel(self._job)
		self._job = self.after(1000, self.flush)

	def flush(self):
		if self._job:
			self.after_cancel(self._job)
			self._job = None
		item_id = getattr(self, "_note_item", None)
		changed = False
		for box, key in ((getattr(self, "note", None), "note"), (getattr(self, "human", None), "human_suggestion")):
			try:
				text = box.get("1.0", "end").strip() if box is not None else None
			except tk.TclError:
				continue
			if text is None or text == self.rec(item_id).get(key, ""):
				continue
			r = self.rec(item_id, make=True)
			r[key] = text
			if key == "human_suggestion":
				r["human_by"], r["human_when"] = self.todo.me.get(), stamp()
			changed = True
		if not changed:
			return
		self.touch(item_id, feedback=False)
		if item_id in self.by_id and self.tree.exists(item_id):  # (its 📝 mark, straight away)
			self.tree.set(item_id, "sugg", self.marks(self.by_id[item_id]))

	def close(self):
		self.flush()

	def redraw(self):
		"""After an undo or the others' changes: the shared rework list etc. read again, and shown."""
		cur = self.cur and self.cur.get("id")
		self.refresh_items()
		self.cur = self.by_id.get(cur) if cur else None
		if self.view.get() == "swipe":
			self.draw_card()
		elif self.view.get() == "review":
			self.review_view.deal(keep=True)
		else:
			self.fill_list()
			self.show_item(self.cur)

	# ---------- links ----------
	def open_url(self, url):
		import webbrowser
		webbrowser.open(url)

	def link_thumb(self, parent, url):
		"""A link's picture as a thumbnail (loaded in the background, kept for the session): click pops it out in the
		zoomable viewer, like Ideas' pictures."""
		src = image_url(url)
		lab = tk.Label(parent, text="Loading...", cursor="hand2", relief="solid", borderwidth=1, width=14, height=5)
		lab.bind("<Button-1>", lambda ev: self.pop_link(url))
		key = ("thumb", src)

		def put():
			if not lab.winfo_exists():
				return
			ph = self._link_photos.get(key)
			if ph:
				lab.config(image=ph, text="", width=0, height=0)
			else:
				lab.config(text="(no picture)")
		if key in self._link_photos:
			put()
			return lab
		got = {}
		th = threading.Thread(target=lambda: got.update(data=self._try_fetch(src)), daemon=True)
		th.start()

		def wait():
			if th.is_alive():
				self.after(200, wait)
				return
			self._link_photos[key] = photo(got["data"], (ui.px(110), ui.px(80))) if got.get("data") else None
			put()
		self.after(200, wait)
		return lab

	def pop_link(self, url):
		"""A link's picture, full size, in the viewer (downloaded to a temporary file first)."""
		src = image_url(url)
		if not src:
			return self.open_url(url)
		big = re.sub(r"width=\d+", "width=1600", src)
		self.app.set_status("GFX: fetching the picture...")
		got = {}
		th = threading.Thread(target=lambda: got.update(data=self._try_fetch(big) or self._try_fetch(src)), daemon=True)
		th.start()

		def wait():
			if th.is_alive():
				self.after(200, wait)
				return
			if not got.get("data"):
				self.app.set_status("GFX: couldn't load that picture - opening the link instead.")
				return self.open_url(url)
			ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lower()
			path = os.path.join(tempfile.gettempdir(), "om_gfx_link_" + str(abs(hash(src))) + (ext if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp") else ".png"))
			with open(path, "wb") as f:
				f.write(got["data"])
			self.app.set_status("")
			show_picture(self, path, kind="GFX link")
		self.after(200, wait)

	@staticmethod
	def _try_fetch(url):
		try:
			return fetch(url)
		except Exception:
			return None

	def add_link(self, item, url=None):
		url = url or simpledialog.askstring("Image link", "A link to a picture (or a page with one):", parent=self)
		if not url or not url.strip():
			return
		r = self.rec(item["id"], make=True)
		if url.strip() not in r.setdefault("links", []):
			r["links"].append(url.strip())
			self.touch(item["id"])
		if item is self.cur:
			self.show_item(item)

	def link_menu(self, ev, lb, item, links):
		i = lb.nearest(ev.y)
		if i < 0 or i >= len(links):
			return
		url = links[i][1]
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="Open in the browser", command=lambda: self.open_url(url))
		m.add_command(label="Copy the link", command=lambda: (self.clipboard_clear(), self.clipboard_append(url)))
		if url in self.rec(item["id"]).get("links", []):
			m.add_command(label="Remove", command=lambda: self.remove_link(item, url))
		m.tk_popup(ev.x_root, ev.y_root)

	def remove_link(self, item, url):
		r = self.rec(item["id"])
		if url in r.get("links", []):
			r["links"].remove(url)
			self.touch(item["id"])
			self.show_item(item)

	def find_pictures(self, item, words=None):
		"""🔎 Wikimedia Commons finds for it, as thumbnails: click one to see it big, ＋ keeps its link."""
		words = words or search_words(item)
		w = tk.Toplevel(self)
		w._om_nonmodal = True
		w.title(f"Pictures for {item['name']}")
		w.transient(self.winfo_toplevel())
		w.geometry(f"{ui.px(900)}x{ui.px(640)}")
		bar = ttk.Frame(w, padding=6)
		bar.pack(fill="x")
		q = tk.StringVar(value=words)
		ttk.Entry(bar, textvariable=q, width=50).pack(side="left")
		ttk.Button(bar, text="Search again", command=lambda: (w.destroy(), self.find_pictures(item, q.get()))).pack(side="left", padx=4)
		ttk.Label(bar, text="from Wikimedia Commons (free pictures)", style="Muted.TLabel").pack(side="left", padx=8)
		options = search_options(item)
		if options:
			ob = ttk.Frame(w, padding=(6, 0, 6, 4))
			ob.pack(fill="x")
			ttk.Label(ob, text="Look for:", style="Muted.TLabel").pack(side="left")
			for label, alt in options:
				ttk.Button(ob, text=label, style="Tool.TButton",
						   command=lambda alt=alt: (w.destroy(), self.find_pictures(item, alt))).pack(side="left", padx=(4, 0))
		body = ui.ScrollFrame(w)
		body.pack(fill="both", expand=True)
		msg = ttk.Label(body.inner, text="Searching...")
		msg.grid(row=0, column=0, sticky="w", padx=8, pady=8)
		got = {}

		def work():
			try:
				found = commons_search(words)
				got["rows"] = [(title, page, self._try_fetch(thumb)) for title, page, thumb in found]
			except Exception as ex:
				got["error"] = str(ex)
		th = threading.Thread(target=work, daemon=True)
		th.start()
		w._photos = []

		def wait():
			if th.is_alive():
				w.after(300, wait)
				return
			if not w.winfo_exists():
				return
			if got.get("error") or not got.get("rows"):
				msg.config(text="Nothing found." if not got.get("error") else f"Couldn't search: {got['error']}")
				return
			msg.destroy()
			for n, (title, page, data) in enumerate(got["rows"]):
				cell = ttk.Frame(body.inner, padding=4)
				cell.grid(row=n // 4, column=n % 4, sticky="n")
				ph = photo(data, (ui.px(200), ui.px(160))) if data else None
				w._photos.append(ph)
				lab = tk.Label(cell, image=ph, text="" if ph else "(no preview)", cursor="hand2")
				lab.pack()
				lab.bind("<Button-1>", lambda ev, p=page: self.open_url(p))
				ttk.Label(cell, text=title[:34], style="Muted.TLabel").pack()
				ttk.Button(cell, text="＋ Keep this link", style="Tool.TButton",
						   command=lambda p=page: (self.add_link(item, p), self.app.set_status("GFX: link kept."))).pack()
		w.after(300, wait)

	# ---------- pictures (the same store as a task's 🎨 Icon / Art) ----------
	def add_picture(self, item):
		im = self.todo.picture_from_file(f"Picture for {item['name']}")
		if im is not None:
			self.keep_picture(item, im)

	def paste_picture(self, item):
		im = self.todo.picture_from_clipboard()
		if im is not None:
			self.keep_picture(item, im)

	def keep_picture(self, item, im):
		safe = re.sub(r"[^\w-]+", "_", item["id"])[:60]
		name = self.todo.store_picture(im, f"gfx-{safe}")
		self.rec(item["id"], make=True).setdefault("pictures", []).append(name)
		self.touch(item["id"])
		self.show_item(item)

	def picture_menu(self, ev, item, name):
		path = os.path.join(self.todo.art_dir(), name)
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="Open", command=lambda: os.path.exists(path) and os.startfile(path))
		m.add_command(label="Open the folder", command=lambda: os.startfile(self.todo.art_dir()))
		m.add_command(label="Remove", command=lambda: self.remove_picture(item, name))
		m.tk_popup(ev.x_root, ev.y_root)

	def remove_picture(self, item, name):
		r = self.rec(item["id"])
		if name in r.get("pictures", []):
			r["pictures"].remove(name)
			self.touch(item["id"])
			self.show_item(item)

	def open_folder(self, item):
		folder = os.path.join(self.app.mod_root, os.path.dirname(item.get("file") or ""))
		while not os.path.isdir(folder) and folder != self.app.mod_root:
			folder = os.path.dirname(folder)
		os.startfile(folder)

	# ---------- what to do with them ----------
	def row_menu(self, ev):
		row = self.tree.identify_row(ev.y)
		if row and row not in self.tree.selection():
			self.tree.selection_set(row)
		items = [self.by_id[i] for i in self.tree.selection() if i in self.by_id]
		if not items:
			return
		m = tk.Menu(self, tearoff=0)
		n = f" ({len(items)})" if len(items) > 1 else ""
		if any(problem(x) == "unused" for x in items):
			m.add_command(label="🗑 Remove from the mod..." + n, command=lambda: self.remove_unused(items))
			m.add_command(label="Keep it..." + n, command=lambda: self.ask_not_missing(items, keep=True))
			m.add_separator()
		else:
			m.add_command(label="✋ I'll make it" + n, command=lambda: self.claim(items))
		if len(items) == 1 and len(self.family_open(items[0])) > 1:
			m.add_command(label=f"✋ The whole family: {family(items[0])[1]} ({len(self.family_open(items[0]))})",
						  command=lambda: self.claim_family(items[0]))
		if any(self.status(x) == "taken" for x in items):
			m.add_command(label="✓ I made it" + n, command=lambda: self.made(items))
		m.add_command(label="✓ Not actually missing..." + n, command=lambda: self.ask_not_missing(items))
		m.add_command(label="↺ It is missing" + n, command=lambda: self.set_not_missing(items, None))
		m.add_command(label="❓ Needs clarification..." + n, command=lambda: self.ask_clarify(items))
		if any(self.clarify(x) for x in items):
			m.add_command(label="✓ Clarified" + n, command=lambda: self.set_clarified(items))
		m.add_separator()
		m.add_command(label="🤖 Ask AI about these" + n, command=lambda: self.ask_ai(items))
		if len(items) == 1 and items[0].get("link"):
			m.add_command(label="Open in its master", command=lambda: self.app.navigate_master(items[0]["link"]))
		m.tk_popup(ev.x_root, ev.y_root)

	def ask_not_missing(self, items, keep=False):
		w = tk.Toplevel(self)
		w.title("Keep it" if keep else "Not actually missing")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both")
		names = items[0]['name'] if len(items) == 1 else f'{len(items)} of them'
		ttk.Label(f, text=f"Why keep {names}?" if keep else f"Why isn't {names} missing?").pack(anchor="w")
		reasons = KEEP_REASONS if keep else NOT_MISSING_REASONS
		why = tk.StringVar(value=reasons[0])
		for r in reasons:
			ttk.Radiobutton(f, text=r, variable=why, value=r).pack(anchor="w")
		more = ttk.Entry(f, width=50)
		more.pack(fill="x", pady=(6, 0))
		ttk.Label(f, text="(more about it, if you like)", style="Muted.TLabel").pack(anchor="w")

		def ok():
			text = why.get() + (f": {more.get().strip()}" if more.get().strip() else "")
			w.destroy()
			self.set_not_missing(items, text)
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(10, 0))
		ttk.Button(bf, text="Mark it", command=ok).pack(side="right")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="right", padx=4)
		w.grab_set()
		self.wait_window(w)

	def set_not_missing(self, items, reason):
		for item in items:
			r = self.rec(item["id"], make=True)
			if reason:
				r["not_missing"] = {"by": self.todo.me.get(), "when": stamp(), "reason": reason}
			else:
				r.pop("not_missing", None)
			r["updated"] = stamp()
		self.todo.save()
		self.app.set_status(f"GFX: {len(items)} marked {'not missing' if reason else 'missing again'}.")
		self.redraw()

	# ---------- ❓ Needs clarification: highlighted, and asked in 💡 Ideas ----------
	def clarify(self, item):
		"""Its open question ({by, when, question, idea}), or None (answered: ✓ Clarified, or its idea was closed)."""
		q = self.rec(item["id"]).get("clarify")
		if not q:
			return None
		idea = self.todo.idea_pane.idea(q["idea"]) if q.get("idea") else None
		import ideas
		return None if idea is not None and idea.get("state", "open") not in ideas.ACTIVE else q

	def ask_clarify(self, items):
		names = items[0]["name"] if len(items) == 1 else f"{len(items)} of them"
		question = simpledialog.askstring("Needs clarification", f"What's unclear about {names}? (it goes to 💡 Ideas for the team)",
										  parent=self)
		if question and question.strip():
			for item in items:
				self.add_clarify(item, question.strip(), self.todo.me.get())
			self.todo.save()
			self.todo.idea_pane.fill()
			self.app.set_status(f"GFX: {names} marked ❓ needs clarification (asked in 💡 Ideas).")
			self.redraw()

	def add_clarify(self, item, question, by):
		"""Marks it and posts the question as an idea (one per item: an idea for it already there is reused)."""
		pane = self.todo.idea_pane
		idea = next((i for i in pane.ideas if i.get("gfx") == item["id"] and i.get("state", "open") != "duplicate"), None)
		if idea is None:
			text = (f"{SECTION_NAME[item['section']]} · {KIND_LABEL[item['kind']]}: {item['name']} ({item.get('token', '')})\n"
					f"{item['detail']}\nShould be: {item.get('file') or '?'}\n\n❓ {question}\n\n(from the 🖼 GFX tab, asked by {by})")
			self.clarify_heading()
			idea = pane.new_idea(f"❓ GFX: {item['name']} - what should it be?", CLARIFY_CATEGORY, text=text, project="",
								 heading=CLARIFY_HEADING)
			idea["gfx"] = item["id"]
			if by != self.todo.me.get():
				idea["by"] = by
		r = self.rec(item["id"], make=True)
		r["clarify"] = {"by": by, "when": stamp(), "question": question, "idea": idea["id"]}
		r["updated"] = stamp()

	def set_clarified(self, items):
		for item in items:
			r = self.rec(item["id"])
			if r.pop("clarify", None) is not None:
				r["updated"] = stamp()
		self.todo.save()
		self.redraw()

	def clarify_heading(self):
		"""Art & Visuals › GFX Clarification exists in Ideas (made the first time it's needed)."""
		heads = self.todo.data.setdefault("idea_headings", {}).setdefault(CLARIFY_CATEGORY, [])
		if CLARIFY_HEADING not in heads:
			heads.append(CLARIFY_HEADING)
			return True
		return False

	def file_clarifications(self):
		"""GFX questions still loose in Art & Visuals go under its GFX Clarification heading (one a dev filed
		somewhere else stays there). True when something moved."""
		loose = [i for i in self.todo.idea_pane.ideas if i.get("gfx") and i.get("category") == CLARIFY_CATEGORY and not i.get("heading")]
		if not loose:
			return False
		self.clarify_heading()
		for i in loose:
			i["heading"] = CLARIFY_HEADING
			i["updated"] = stamp()
		return True

	def ai_clarifications(self):
		"""Entries an AI wasn't sure about (gfx_suggestions.json "needs_clarification"): marked and asked once."""
		changed = self.file_clarifications()
		for item_id, a in self.ai().items():
			item = self.by_id.get(item_id)
			r = self.rec(item_id)
			if item and a.get("needs_clarification") and "clarify" not in r and not r.get("ai_asked"):
				self.add_clarify(item, a["needs_clarification"], f"{a.get('by') or 'AI'} (AI)")
				self.rec(item_id)["ai_asked"] = True  # (✓ Clarified stays clarified: the AI's note doesn't ask again)
				changed = True
		if changed:
			self.todo.save()
			self.todo.idea_pane.fill()

	def go_idea(self, idea_id):
		self.todo.mode.set("idea")
		self.todo.mode_changed()
		self.todo.idea_pane.go_to_idea(idea_id)

	def family_open(self, item):
		"""The open (not taken) ones of its family, of the same kind of problem."""
		key = family(item)[0]
		return [x for x in self.items if family(x)[0] == key and problem(x) == problem(item) and self.status(x) == "missing"]

	def claim_family(self, item):
		"""✋ The whole family: a parent task (link gfx_family:<key>) with a sub-task for each open one."""
		members = self.family_open(item)
		key, name = family(item)
		if not members or not messagebox.askyesno(APP_NAME, f"Take all {len(members)} of {name}? You get one task with a sub-task each.", parent=self):
			return
		todo = self.todo
		self.ensure_project()
		verb = "Fix" if problem(item) == "broken" else "Make"
		parent = todo.linked(FAMILY_LINK + key) if todo.linked(FAMILY_LINK + key) and todo.linked(FAMILY_LINK + key).get("status") != "Completed" else None
		if parent is None:
			parent = todo.add_task(f"🖼 {verb} {name} ({len(members)})", project=GFX_PROJECT, category="Art", devs=[todo.me.get()],
								   group=SECTION_NAME[item["section"]], link=FAMILY_LINK + key, icon="picture",
								   setter_note=f"Taken from the 🖼 GFX tab as a family: {', '.join(x['name'] for x in members[:30])}"
											   + (f" and {len(members) - 30} more" if len(members) > 30 else "") + ".")
			todo.keep_group("proj:" + GFX_PROJECT, SECTION_NAME[item["section"]])
		self.claim(members, parent=parent["ref"])

	def ensure_project(self):
		todo = self.todo
		if not todo.project(GFX_PROJECT):
			todo.data["projects"].append({"name": GFX_PROJECT, "lead": "", "set_by": todo.me.get(), "created": stamp(),
										  "note": "Made from the 🖼 GFX tab: one task per missing picture someone took on.", "icon": "picture"})

	def claim(self, items, parent=""):
		"""✋ You'll make them: a task each for you in project Missing GFX (grouped by section; under parent for a family).
		A 🔁 rework is claimed on the shared list itself (it lives only in GFX)."""
		todo, me = self.todo, self.todo.me.get()
		rework = [x for x in items if problem(x) == "rework"]
		if rework:
			for x in rework:
				m = self.rework_marks().get(x.get("marked") or "")
				if m is not None and me not in (m.get("claimed") or []):
					m["claimed"] = sorted(set(m.get("claimed") or []) | {me})
			todo.save()
			self.refresh_items()
			self.app.set_status(f"GFX: {len(rework)} to rework {'is' if len(rework) == 1 else 'are'} yours (✓ Reworked when done).")
			items = [x for x in items if problem(x) != "rework"]
			if not items:
				self.redraw()
				return []
		self.ensure_project()
		refs = []
		for item in items:
			r = self.rec(item["id"], make=True)
			if self.status(item) != "missing":
				continue
			text, _ = suggestion(item, self.ai())
			note = f"{KIND_LABEL[item['kind']]} · {item['detail']}\nShould be: {item.get('file') or '?'}\n\n🤖 {text}"
			title = f"Rework: {item['name']}" if item["kind"] == "rework" else 				f"{ {'broken': 'Fix ', 'rework': 'Rework '}.get(problem(item), '')}{KIND_LABEL[item['kind']]}: {item['name']}"
			t = todo.add_task(title, project=GFX_PROJECT,
							  category="Art", devs=[me], group="" if parent else SECTION_NAME[item["section"]], parent=parent,
							  link=LINK + item["id"], setter_note=note, icon="picture", links=[item["link"]] if item.get("link") else [])
			if not parent:
				todo.keep_group("proj:" + GFX_PROJECT, SECTION_NAME[item["section"]])
			r["task"] = t["ref"]
			r["updated"] = stamp()
			refs.append(t["ref"])
		if refs:
			todo.save()
			todo.fill_filters()
			todo.fill()
			self.app.set_status(f"GFX: yours now - {', '.join(refs)} in project {GFX_PROJECT}.")
		self.redraw()
		return refs

	def made(self, items):
		"""✓ I made it: its task is completed (by you, who join its devs) - it counts in the Monthly Report's 🖼 GFX made.
		A 🔁 rework: off the shared list."""
		for x in [x for x in items if problem(x) == "rework"]:
			self.unmark_rework(x, quiet=True)
		items = [x for x in items if problem(x) != "rework"]
		me, refs = self.todo.me.get(), []
		for item in items:
			task = self.todo.task(self.rec(item["id"]).get("task") or "")
			if task is None or self.status(item) != "taken":
				continue
			if me not in (task.get("devs") or []):
				self.todo.change(task, "devs", (task.get("devs") or []) + [me])
			self.todo.change(task, "status", "Completed", note="Made (🖼 GFX tab)")
			refs.append(task["ref"])
			self.close_parent(task)
		if refs:
			self.todo.save()
			self.todo.fill()
			self.refresh_items()
			self.app.set_status(f"GFX: {len(refs)} made - {', '.join(refs)} completed. Put the picture in the mod and Rescan to clear it.")
		self.redraw()

	def close_parent(self, task):
		"""A ✋ whole family's task is completed with its last sub-task."""
		parent = self.todo.task(task.get("parent") or "")
		if parent and (parent.get("link") or "").startswith(FAMILY_LINK) and parent.get("status") != "Completed":
			if all(t.get("status") in ("Completed", "Not Possible") for t in self.todo.tasks if t.get("parent") == parent["ref"]):
				self.todo.change(parent, "status", "Completed", note="Every picture of the family is made (🖼 GFX tab)")

	# ---------- 🗑 unused: out of the mod (with a backup) ----------
	def remove_unused(self, items):
		items = [x for x in items if problem(x) == "unused" and not self.rec(x["id"]).get("not_missing")]
		if not items:
			return
		what = []
		for x in items[:12]:
			what += [f"  • {p}" for p in x.get("paths", [])] + ([f"  • spriteType {x['sprite']} in {x['gfx_file']}"] if x.get("sprite") else [])
		more = f"\n  ... and {len(items) - 12} more" if len(items) > 12 else ""
		backup = os.path.join(paths.TOOL, "backups", "gfx_removed")
		if not messagebox.askyesno(APP_NAME, f"Take {len(items)} out of the mod?\n\n" + "\n".join(what[:30]) + more +
								   f"\n\nEverything is copied to tools/organisation_master/backups/gfx_removed first.", parent=self):
			return
		done, failed = 0, []
		for x in items:
			try:
				for rel in gfx_checks.remove(self.app.mod_root, x, backup):
					self.app.log(rel)
				done += 1
				self.items.remove(x)
				self.by_id.pop(x["id"], None)
			except OSError as ex:
				failed.append(f"{x['name']}: {ex}")
		self.save_cache()
		self.fill_list()
		self.app.set_status(f"GFX: {done} taken out of the mod (backup in backups/gfx_removed).")
		if failed:
			messagebox.showerror(APP_NAME, "Couldn't remove:\n" + "\n".join(failed[:10]), parent=self)

	def save_cache(self):
		try:
			write_cache(self.scanned, self.items + self.present)
		except OSError:
			pass

	# ---------- 👁 preview: a draft at the size the game draws it, among its family ----------
	def preview(self, item):
		from PIL import Image, ImageTk
		pics = [os.path.join(self.todo.art_dir(), n) for n in self.rec(item["id"]).get("pictures", [])]
		pics = [p for p in pics if os.path.exists(p)]
		if not pics:
			messagebox.showinfo(APP_NAME, "Add a picture first (+ Picture or 📋 Paste): the preview shows it at the game's size.", parent=self)
			return
		refs = []
		for p in item.get("refs", [])[:6]:
			try:
				refs.append(Image.open(p).convert("RGBA"))
			except Exception:
				pass
		sizes = [im.size for im in refs]
		size = tuple(item.get("want") or ()) or (max(set(sizes), key=sizes.count) if sizes else DEFAULT_SIZE.get(item["kind"], (100, 100)))
		w = tk.Toplevel(self)
		w._om_nonmodal = True
		w.title(f"Preview: {item['name']}")
		w.transient(self.winfo_toplevel())
		bg = "#1d2024"  # (about the colour of HOI4's panels)
		w.configure(background=bg)
		pick = tk.StringVar(value=os.path.basename(pics[-1]))
		top = ttk.Frame(w, padding=6)
		top.pack(fill="x")
		ttk.Label(top, text="Picture:").pack(side="left")
		ttk.Combobox(top, textvariable=pick, values=[os.path.basename(p) for p in pics], state="readonly", width=40).pack(side="left", padx=4)
		ttk.Label(top, text=f"at {size[0]}x{size[1]}, like its family", style="Muted.TLabel").pack(side="left", padx=8)
		body = tk.Frame(w, background=bg, padx=16, pady=12)
		body.pack(fill="both", expand=True)
		w._photos = []

		def fit(im, box):
			"""(fitted inside the box, centred, the way a sprite of another size would be shown: no stretching)"""
			im = im.copy()
			im.thumbnail(box, Image.LANCZOS)
			out = Image.new("RGBA", box, (0, 0, 0, 0))
			out.paste(im, ((box[0] - im.width) // 2, (box[1] - im.height) // 2))
			return out

		def draw(*_):
			for c in body.winfo_children():
				c.destroy()
			w._photos.clear()
			draft = Image.open(os.path.join(self.todo.art_dir(), pick.get())).convert("RGBA")
			scales = [1, 2]
			if item["kind"] in ("flag", "ideo_flag"):
				rows = [("Big flag (82x52)", [fit(draft, (82, 52))]), ("Medium (41x26)", [fit(draft, (41, 26))]), ("Small (10x7)", [fit(draft, (10, 7))])]
			else:
				rows = [("Yours among its family", [fit(draft, size)] + [fit(r, size) for r in refs])]
			for title, ims in rows:
				for scale in scales:
					tk.Label(body, text=f"{title} - {'actual size' if scale == 1 else 'x2'}", background=bg, foreground="#c8c0a8",
							 font="om_small").pack(anchor="w", pady=(6, 2))
					row = tk.Frame(body, background=bg)
					row.pack(anchor="w")
					for n, im in enumerate(ims):
						big = im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale > 1 else im
						ph = ImageTk.PhotoImage(big)
						w._photos.append(ph)
						tk.Label(row, image=ph, background=bg, borderwidth=2 if n == 0 else 0, relief="solid",
								 highlightthickness=0).pack(side="left", padx=4)
		pick.trace_add("write", draw)
		draw()

	def go_task(self, ref):
		self.todo.mode.set(self.app.config.get("todo_last_mode", "dev"))
		self.todo.mode_changed()
		self.todo.go_to(ref)

	def rate_ai(self, item, good):
		"""👍 / 👎 the AI's suggestion (with why): kept with the item (synced) and in gfx_suggestion_ratings.json for the
		AI's next run (🤖 Ask AI puts the feedback in its request)."""
		text, by_ai = suggestion(item, self.ai())
		if not by_ai:
			return
		got = ([], "") if good else self.ask_rating(item)
		if got is None:
			return
		r = self.rec(item["id"], make=True)
		r["ai_rating"] = {"rating": "good" if good else "bad", "reasons": got[0], "comment": got[1], "by": self.todo.me.get(),
						  "when": stamp(), "suggestion": text, "ai": (self.ai().get(item["id"]) or {}).get("by") or "AI"}
		self.touch(item["id"])
		self.export_ratings()
		self.show_item(item)
		self.app.set_status(f"GFX: the AI's suggestion for {item['name']} rated {'👍' if good else '👎'} (the next 🤖 Ask AI hears about it).")

	def ask_rating(self, item):
		"""(reasons, comment) or None: what's wrong with the AI's suggestion."""
		w = tk.Toplevel(self)
		w.title("Rate the AI's suggestion")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=f"👎 What's wrong with the suggestion for {item['name']}?", font="om_bold").pack(anchor="w")
		ttk.Label(f, text="Tick all that fit. The AI gets this the next time it's asked.", style="Muted.TLabel").pack(anchor="w", pady=(2, 6))
		ticks = {}
		old = (self.rec(item["id"]).get("ai_rating") or {}).get("reasons") or []
		for reason in AI_RATE_REASONS:
			ticks[reason] = tk.BooleanVar(value=reason in old)
			ttk.Checkbutton(f, text=reason, variable=ticks[reason]).pack(anchor="w")
		ttk.Label(f, text="Comment (what would be better?)").pack(anchor="w", pady=(8, 0))
		note = tk.Text(f, height=3, width=52, wrap="word", font="om_body")
		note.insert("1.0", (self.rec(item["id"]).get("ai_rating") or {}).get("comment", ""))
		note.pack(fill="x")
		out = {}

		def ok():
			picked = [r for r, v in ticks.items() if v.get()]
			if not picked:
				messagebox.showinfo(APP_NAME, "Tick at least one reason (Other, with a comment, if none fit).", parent=w)
				return
			out["r"] = (picked, note.get("1.0", "end").strip())
			w.destroy()
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(10, 0))
		ttk.Button(bf, text="👎 Rate it", command=ok).pack(side="right")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="right", padx=6)
		w.grab_set()
		w.wait_window()
		return out.get("r")

	def ratings(self):
		"""{item id: its AI rating} for every item rated."""
		return {k: v["ai_rating"] for k, v in self.store().items() if isinstance(v, dict) and v.get("ai_rating")}

	def export_ratings(self):
		"""gfx_suggestion_ratings.json (tools/organisation_master): what the team thought of the AI's suggestions."""
		try:
			with open(os.path.join(paths.TOOL, RATINGS_FILE), "w", encoding="utf-8") as f:
				json.dump({"_note": "The team's ratings of the AI's GFX suggestions (gfx_suggestions.json). Before writing new ones, "
								   "avoid what was rated bad (reasons + comment) and keep doing what was rated good; rewrite a bad one.",
						   "items": self.ratings()}, f, indent=1, ensure_ascii=False)
		except OSError:
			pass

	def rating_feedback(self, items):
		"""Lines for 🤖 Ask AI: how the earlier suggestions went (the most common complaints, the liked ones, and these
		items' own ratings)."""
		rated = self.ratings()
		if not rated:
			return ""
		bad = [x for x in rated.values() if x.get("rating") == "bad"]
		counts = {}
		for x in bad:
			for reason in x.get("reasons") or []:
				counts[reason] = counts.get(reason, 0) + 1
		lines = [f"\nFeedback on your earlier suggestions ({len(rated)} rated: {len(rated) - len(bad)} good, {len(bad)} not good)."]
		if counts:
			lines.append("Most common problems: " + ", ".join(f"{k} ({n})" for k, n in sorted(counts.items(), key=lambda kv: -kv[1])[:5]) + ".")
		comments = [x for x in bad if x.get("comment")][-8:]
		if comments:
			lines.append("What the team said:")
			lines += [f"- \"{x['comment']}\" ({', '.join(x.get('reasons') or [])})" for x in comments]
		good = [x for x in rated.values() if x.get("rating") == "good"][-3:]
		if good:
			lines.append("Liked, for example:")
			lines += [f"- {x.get('suggestion', '')[:200]}" for x in good]
		mine = [(x, rated[x["id"]]) for x in items if x["id"] in rated and rated[x["id"]].get("rating") == "bad"]
		if mine:
			lines.append("These were rated not good - replace their suggestion:")
			lines += [f"- {x['id']}: {', '.join(r.get('reasons') or [])}" + (f" - \"{r['comment']}\"" if r.get("comment") else "") for x, r in mine]
		lines.append(f"(All ratings: tools/organisation_master/{RATINGS_FILE}.)")
		return "\n".join(lines) + "\n"

	def ask_ai(self, items=None):
		"""🤖 A request for Claude / ChatGPT, copied to the clipboard: these items (or ones without a suggestion yet, or whose
		suggestion was rated not good), with the team's feedback on the earlier ones."""
		ai = self.ai()
		self.export_ratings()  # (the file has everyone's ratings, synced ones too)
		if items is None:
			redo = {k for k, v in self.ratings().items() if v.get("rating") == "bad"}
			pool = [x for x in self.shown_items() if (x["id"] not in ai or x["id"] in redo) and problem(x) != "unused"] or [
				x for x in self.items if (x["id"] not in ai or x["id"] in redo) and self.status(x) == "missing" and problem(x) == "missing"]
			items = pool[:40]
		if not items:
			messagebox.showinfo(APP_NAME, "Every missing picture has an AI suggestion already.", parent=self)
			return
		lines = []
		for fam in dict.fromkeys(family(x)[0] for x in items):  # (a family together, so its suggestions match)
			members = [x for x in items if family(x)[0] == fam]
			pid = parent_id(members[0])
			if pid:
				rel = next((r for r in members[0].get("related") or [] if r.get("role") == "parent"), {})
				state = "its icon exists: match its style" if rel.get("path") else "its icon is missing too"
				lines.append(f"# Family: {family(members[0])[1]} (parent: {rel.get('name') or pid} - {state}). Keep these consistent with each other.")
			lines += [f"- {x['id']} | {x['name']} | {KIND_LABEL[x['kind']]} | {x['detail']}" for x in members]
		text = ("Fill in Revolution Realized's GFX suggestions (Hearts of Iron IV mod).\n"
				f"File: tools/organisation_master/{AI_FILE} = {{\"items\": {{<id>: {{\"suggestion\": text, \"links\": [urls], \"by\": your name}}}}}}"
				" (keep what's there; add these).\n"
				"suggestion: 1-3 sentences on what the picture should show - the real symbol / flag / emblem / look, colours, "
				"what to copy from real life - for an artist making it.\n"
				"links: 0-3 Wikimedia Commons file pages (https://commons.wikimedia.org/wiki/File:...) you are sure exist; "
				"leave it empty rather than guess.\n"
				"If you aren't sure what an entry even is (an unclear name or token), don't guess: give it "
				"\"needs_clarification\": your question instead of a suggestion - it goes to the team's Ideas.\n"
				+ self.rating_feedback(items) + "\n" + "\n".join(lines))
		self.clipboard_clear()
		self.clipboard_append(text)
		messagebox.showinfo(APP_NAME, f"A request for {len(items)} of them is on the clipboard: paste it to Claude or ChatGPT "
							"(working in the RR folder). Their suggestions show here as soon as the file is saved.", parent=self)

	# ---------- 🃏 Swipe ----------
	def skipped(self):
		return self.app.config.setdefault("gfx_skipped", {})

	def swipe_sections_changed(self):
		self.app.config["gfx_swipe_sections"] = [k for k, v in self.swipe_sections.items() if v.get()]
		self.app.save_config()
		self.deal()

	def pool(self):
		on = {k for k, v in self.swipe_sections.items() if v.get()}
		skipped = self.skipped()
		return [x for x in self.items if x["section"] in on and x["id"] not in skipped and self.status(x) == "missing"
				and problem(x) in ("missing", "broken")]

	def deal(self):
		pool = self.pool()
		if self.card in pool and len(pool) > 1:
			pool.remove(self.card)
		self.card = random.choice(pool) if pool else None
		n = len(self.skipped())
		self.skipped_btn.config(text=f"↺ Bring back the {n} I skipped" if n else "Nothing skipped", state="normal" if n else "disabled")
		self._left = len(self.pool())  # (counted once per card: counting every frame made the swipe choppy)
		self.draw_card()

	def reset_skipped(self):
		self.skipped().clear()
		self.app.save_config()
		self.deal()

	def card_theme_changed(self):
		if self.canvas.winfo_exists():
			self.canvas.configure(background=ui.P["background"])
			if self.view.get() == "swipe":
				self.draw_card()

	def card_theme_destroyed(self, event):
		if event.widget is self.canvas and self.card_theme_changed in ui.THEME_HOOKS:
			ui.THEME_HOOKS.remove(self.card_theme_changed)

	def draw_card(self, dx=0):
		"""The whole card, drawn in the middle and then slid dx across (dragging / sliding only moves it: card_offset)."""
		c = self.canvas
		c.delete("all")
		self._card_dx = 0
		W, H = c.winfo_width(), c.winfo_height()
		if W < 50:
			return
		item = self.card
		if item is None:
			c.create_text(W // 2, H // 2, text="No missing pictures to deal.\n(Tick more sections, or bring back the ones you skipped.)"
						  if not self._scanning else "Scanning the mod...", font="om_head", justify="center",
						  fill=ui.P.get("muted", "#777777"))
			return
		c.configure(background=ui.P["background"])
		cw, ch = min(ui.px(540), W - ui.px(32)), min(ui.px(620), H - ui.px(40))
		x0, y0 = (W - cw) // 2, (H - ch) // 2 - ui.px(8)
		self._card_box = (x0, y0, cw)
		colour = SECTION_COLOUR[item["section"]]
		kind = f"{SECTION_NAME[item['section']]} · {KIND_LABEL[item['kind']]}"
		if problem(item) == "broken":
			kind += " · ⚠ broken"
		y, limit, fg, muted, accent = gfx_card_style.shell(c, x0, y0, cw, ch, item, colour, kind)
		pad = ui.px(18)
		def text(value, font="om_small", fill=None, height=None):
			nonlocal y
			y = gfx_card_style.fitted_text(c, x0 + pad, y, value, cw - pad * 2,
				max(0, min(limit - y, height if height is not None else limit - y)),
				font=font, fill=fill or fg) + ui.px(10)
		text(item["detail"], fill=muted, height=ui.px(38))
		self._card_photos = []
		refs = item.get("refs", [])[:5]
		r = self.rec(item["id"])
		pics = [os.path.join(self.todo.art_dir(), n) for n in r.get("pictures", [])][:5 - len(refs)] if len(refs) < 5 else []
		if (refs or pics) and limit - y > ui.px(180):
			text("FAMILY REFERENCES" if refs else "ADDED PICTURES", fill=muted)
			x = x0 + pad
			box = min(ui.px(76), int((cw - pad * 2) / max(1, len(refs + pics))) - ui.px(8))
			for path in refs + pics:
				ph = photo(path, (box, box))
				if ph:
					self._card_photos.append(ph)
					c.create_rectangle(x-2, y-2, x+box+2, y+box+2, fill=ui.P["input_background"], outline=ui.P["border"])
					c.create_image(x+box/2, y+box/2, image=ph)
					x += box + ui.px(8)
			y += box + ui.px(14)
		q = self.clarify(item)
		if q and limit - y > ui.px(90):
			text("? NEEDS CLARIFICATION", fill=accent)
			text(q.get("question", ""), height=ui.px(40))
		brief, by_ai = suggestion(item, self.ai())
		text("SUGGESTION" + (" · AI" if by_ai else " · MOD DATA"), fill=accent)
		text(brief, font="om_body", height=max(0, limit-y-ui.px(20)))
		if y < limit:
			c.create_text(x0+pad, limit, anchor="sw", text="Full brief & references → Details", font="om_small", fill=muted)

		c.addtag_all("card")
		c.create_text(W // 2, H - 6, anchor="s", text=f"{getattr(self, '_left', len(self.pool()))} left to deal · drag the card or use the arrow keys",
					  font="om_small", fill=ui.P.get("muted", "#777777"))
		self.card_offset(dx)

	def card_offset(self, dx):
		"""The card dx across (its canvas items moved, nothing redrawn), with NOT THIS ONE / I'LL MAKE IT past 40 pixels."""
		c = self.canvas
		if self.card is None or not hasattr(self, "_card_box"):
			return
		c.move("card", dx - self._card_dx, 0)
		self._card_dx = dx
		c.delete("stamp")
		x0, y0, cw = self._card_box
		if dx < -40:
			c.create_text(x0 + dx + cw - 20, y0 + ui.px(100), anchor="ne", text="NOT THIS ONE", font=("Segoe UI", 20, "bold"), fill="#c0392b",
						  angle=-15, tags="stamp")
		elif dx > 40:
			c.create_text(x0 + dx + 20, y0 + ui.px(100), anchor="nw", text="I'LL MAKE IT", font=("Segoe UI", 20, "bold"), fill="#2e9d4a",
						  angle=15, tags="stamp")

	def drag_start(self, ev):
		self.canvas.focus_set()
		self._drag = ev.x

	def drag_move(self, ev):
		if getattr(self, "_drag", None) is not None and self.card:
			self.card_offset(ev.x - self._drag)

	def drag_end(self, ev):
		start, self._drag = getattr(self, "_drag", None), None
		if start is None or not self.card:
			return
		dx = ev.x - start
		if abs(dx) > SWIPE_FAR:
			self.swipe(1 if dx > 0 else -1, dx)
		else:
			self.slide(dx, 0, lambda: None)

	def slide(self, frm, to, then, step=0):
		"""(the card moves on: off the side, or back to the middle; eased, about a sixth of a second)"""
		steps = 12
		step += 1
		t = step / steps
		self.card_offset(round(frm + (to - frm) * (1 - (1 - t) ** 3)))
		if step < steps:
			self.after(14, lambda: self.slide(frm, to, then, step))
		else:
			then()

	def swipe(self, way, frm=0):
		item = self.card
		if item is None:
			return
		W = self.canvas.winfo_width()

		def done():
			self.swiped.append((item, way))
			self.swipe_undo_btn.state(["!disabled"])
			if way < 0:
				self.skipped()[item["id"]] = stamp()
				self.app.save_config()
			else:
				refs = self.claim([item])
				if refs:
					self.app.set_status(f"GFX: {item['name']} is yours - {refs[0]} (project {GFX_PROJECT}).")
			self.deal()
		self.slide(frm, way * W, done)

	def swipe_undo(self):
		"""↶ The last swipe taken back: a skip forgotten, a claimed task undone (the To Do's Undo); the card comes back."""
		if not self.swiped:
			return
		item, way = self.swiped[-1]
		if way > 0:
			return self.todo.undo()  # (calls undone() when it's done)
		self.swiped.pop()
		self.skipped().pop(item["id"], None)
		self.app.save_config()
		self.card_back(item)

	def card_back(self, item):
		self.swipe_undo_btn.state(["!disabled"] if self.swiped else ["disabled"])
		self.card = self.by_id.get(item["id"], item)
		self._left = len(self.pool())
		self.draw_card()
		self.slide(-self.canvas.winfo_width(), 0, lambda: None)

	def undone(self):
		"""After any Undo (Ctrl+Z, ↶): a swiper's last card comes back."""
		if self.view.get() == "review":
			self.review_view.undone()
		elif self.view.get() == "swipe" and self.swiped and self.swiped[-1][1] > 0:
			self.card_back(self.swiped.pop()[0])

	def swipe_not_missing(self):
		if self.card:
			self.ask_not_missing([self.card])
			if self.status(self.card) == "not_missing":
				self.deal()

	def swipe_details(self):
		if not self.card:
			return
		w = tk.Toplevel(self)
		w._om_nonmodal = True
		w.title(self.card["name"])
		w.transient(self.winfo_toplevel())
		w.geometry(f"{ui.px(480)}x{ui.px(700)}")
		sf = ui.ScrollFrame(w)
		sf.pack(fill="both", expand=True, padx=8, pady=8)
		self.show_item(self.card, into=sf.inner)
