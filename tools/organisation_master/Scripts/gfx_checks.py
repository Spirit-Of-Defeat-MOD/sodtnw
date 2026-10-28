"""🖼 GFX tab checks beyond "missing" (no Tk here: they run in the scan's thread).

⚠ Broken: pictures that are there but wrong - a DDS / TGA format HOI4 can't read, the wrong size next to its family,
flags without alpha. Only file headers are read (a few bytes each), remembered by size + time in
%LOCALAPPDATA%/OrganisationMaster/gfx_headers.json, so 30,000 pictures on OneDrive don't take minutes every scan.
🗑 Unused: picture files nothing points at, spriteTypes for cultures / religions / sub-ideologies that no longer exist,
and flags for tags that don't exist. remove() takes one out of the mod, with a backup of everything it touches.
📈 Progress: how many are left per section, per day (todo_tasks.json "gfx" "history"), for the tab and the Monthly Report.
"""
import datetime
import json
import os
import re
import shutil
import struct
import tempfile
import time
from collections import Counter

PICTURE_EXT = (".dds", ".tga", ".png")
UNUSED_FOLDERS = ("gfx/interface/culture", "gfx/interface/religion", "gfx/interface/ideologies", "gfx/leaders")
FLAG_SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
TEXT_DIRS = ("common", "events", "history", "interface", "localisation", "gfx", "map", "music", "sound", "portraits")
TEXT_EXT = (".txt", ".gui", ".gfx", ".yml", ".asset")


def header_cache_file():
	return os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "OrganisationMaster", "gfx_headers.json")


def read_header(path):
	"""(width, height, problem) from the file's first bytes; problem "" when HOI4 can read it."""
	try:
		with open(path, "rb") as f:
			b = f.read(128)
	except OSError as ex:
		return 0, 0, f"can't be opened ({ex.strerror})"
	if not b:
		return 0, 0, "the file is empty"
	ext = os.path.splitext(path)[1].lower()
	if ext == ".dds":
		if b[:4] != b"DDS " or len(b) < 128:
			return 0, 0, "not a DDS picture (a renamed PNG / JPG?) - save it as DDS"
		h, w = struct.unpack("<II", b[12:20])
		flags, fourcc = struct.unpack("<I", b[80:84])[0], b[84:88]
		if fourcc in (b"DXT1", b"DXT3", b"DXT5"):
			return w, h, ""
		if fourcc == b"\0\0\0\0" and flags & 0x40:  # (uncompressed RGB / RGBA)
			return w, h, ""
		name = fourcc.decode("ascii", "replace").strip("\0") or "unknown"
		if fourcc == b"DX10":
			return w, h, "DX10 (BC7) DDS - HOI4 can't read it: save as DXT5 (BC3) or uncompressed 8.8.8.8"
		return w, h, f"{name} DDS - HOI4 needs DXT1 / DXT5 or uncompressed"
	if ext == ".tga":
		if len(b) < 18:
			return 0, 0, "the TGA file is cut off"
		kind, (w, h), depth = b[2], struct.unpack("<HH", b[12:16]), b[16]
		if kind == 10:
			return w, h, "RLE-compressed TGA - save it uncompressed"
		if kind != 2:
			return w, h, f"unusual TGA (type {kind}) - save as 32-bit uncompressed true colour"
		return w, h, "" if depth in (24, 32) else f"{depth}-bit TGA - save as 32-bit"
	if ext == ".png":
		if b[:8] != b"\x89PNG\r\n\x1a\n":
			return 0, 0, "not a PNG picture - save it as PNG"
		w, h = struct.unpack(">II", b[16:24])
		return w, h, ""
	return 0, 0, ""


class Headers:
	"""read_header() with a cache by path, size and modified time (plus the TGA bit depth for flags)."""

	def __init__(self):
		self.path = header_cache_file()
		try:
			with open(self.path, encoding="utf-8") as f:
				self.old = json.load(f)
		except (OSError, ValueError):
			self.old = {}
		self.new = {}

	def get(self, path):
		try:
			st = os.stat(path)
		except OSError:
			return 0, 0, "can't be opened", 0
		sig = f"{st.st_size}:{st.st_mtime_ns}"
		got = self.old.get(path)
		if not got or got[0] != sig:
			w, h, problem = read_header(path)
			depth = 0
			if path.lower().endswith(".tga") and not problem:
				with open(path, "rb") as f:
					depth = f.read(18)[16]
			got = [sig, w, h, problem, depth]
		self.new[path] = got
		return got[1], got[2], got[3], got[4]

	def save(self):
		try:
			os.makedirs(os.path.dirname(self.path), exist_ok=True)
			with open(self.path, "w", encoding="utf-8") as f:
				json.dump(self.new, f)
		except OSError:
			pass


def animated(root):
	"""{texture (lower-case, relative): {frame counts}} for the mod's animated sprites (frameAnimatedSpriteType, or a spriteType
	with noOfFrames > 1): their frames sit side by side, so the picture is frames times as wide as one frame."""
	out = {}
	folder = os.path.join(root, "interface")
	rx = re.compile(r"\b(?:frameAnimatedSpriteType|spriteType)\s*=\s*\{([^{}]*)\}", re.I)
	for dirpath, _, files in os.walk(folder):
		for f in files:
			if not f.lower().endswith(".gfx"):
				continue
			try:
				with open(os.path.join(dirpath, f), encoding="utf-8-sig", errors="replace") as fh:
					text = re.sub(r"#[^\n]*", "", fh.read())
			except OSError:
				continue
			for m in rx.finditer(text):
				body = m.group(1)
				tex = re.search(r'\btexturefile\s*=\s*"([^"]+)"', body, re.I)
				n = re.search(r"\bnoOfFrames\s*=\s*(\d+)", body, re.I)
				if tex and n and int(n.group(1)) > 1:
					key = tex.group(1).replace("\\", "/").lower()
					out.setdefault(key, set()).add(int(n.group(1)))  # (two sprites can share a picture with different counts)
	return out


def frame_size(root, path, w, h, frames):
	"""(w, h) of one frame: the whole picture for a still one."""
	counts = (frames or {}).get(os.path.relpath(path, root).replace("\\", "/").lower())
	if not counts or not w:
		return w, h
	n = next((c for c in sorted(counts) if w % c == 0), max(counts))  # (the count that splits it evenly)
	return w // n, h


def usual_size(sizes):
	"""The size most of a family has (at least 3 of them, and 60 %), else None."""
	sizes = [s for s in sizes if s[0]]
	if len(sizes) < 3:
		return None
	size, n = Counter(sizes).most_common(1)[0]
	return size if n >= 0.6 * len(sizes) else None


# ---------- ⚠ broken ----------
def broken(root, members, hd, exact=True, frames=None):
	"""members = [dict(section, kind, family, family_name, path, name, token, link)] of one family (pictures that exist).
	A broken item for each one HOI4 can't read, or whose size isn't its family's (exact) / is stretched (not exact).
	frames: animated(root) - an animated picture is compared by one frame (it's frames times as wide)."""
	infos = []
	for m in members:
		w, h, problem, depth = hd.get(m["path"])
		fw, fh = frame_size(root, m["path"], w, h, frames)
		infos.append((m, (fw, fh, problem, depth), (w, h) != (fw, fh)))
	want = usual_size([(w, h) for _, (w, h, p, _), _ in infos if not p])
	out = []
	for m, (w, h, problem, _), moving in infos:
		if not problem and want and (w, h) != want:
			each = " a frame (it's animated)" if moving else ""
			if exact:
				problem = f"is {w}x{h}{each}; the rest of its family is {want[0]}x{want[1]}"
			elif h and want[1] and abs(w / h - want[0] / want[1]) > 0.05 * want[0] / want[1]:
				problem = f"is {w}x{h}{each} - stretched next to the usual {want[0]}x{want[1]}"
		if problem:
			out.append(broken_item(root, m, problem, want))
	return out


def broken_item(root, m, problem, want=None):
	rel = os.path.relpath(m["path"], root).replace("\\", "/")
	return dict(id=f"broken:{rel}", section=m["section"], kind=m["kind"], problem="broken", name=m["name"], token=m.get("token", ""),
				detail=f"⚠ {problem}", file=rel, refs=[m["path"]] + m.get("refs", [])[:5], link=m.get("link"),
				family=m.get("family", ""), family_name=m.get("family_name", ""), search=m.get("search", m["name"]),
				want=list(want) if want else None, note="", parent=m.get("parent", ""), group=m.get("group", ""), main=m.get("main", ""))


def broken_flags(root, hd, flag_name):
	"""The mod's own flags (big, medium/, small/): readable 32-bit TGAs of the size HOI4 draws."""
	out = []
	for sub, want in FLAG_SIZES.items():
		folder = os.path.join(root, "gfx", "flags", sub)
		if not os.path.isdir(folder):
			continue
		for f in os.listdir(folder):
			if not f.lower().endswith(".tga"):
				continue
			path = os.path.join(folder, f)
			w, h, problem, depth = hd.get(path)
			if not problem and (w, h) != want:
				problem = f"is {w}x{h}; {'big' if not sub else sub} flags are {want[0]}x{want[1]}"
			if not problem and depth != 32:
				problem = f"{depth}-bit TGA (no transparency) - flags need 32-bit"
			if problem:
				stem = f[:-4]
				tag = stem.split("_")[0]
				out.append(broken_item(root, dict(section="flag", kind={"": "flag", "medium": "medium_flag", "small": "small_flag"}[sub],
					family=f"flag:{tag}", family_name=f"{flag_name(tag)} flags", path=path, name=f"{flag_name(tag)} ({stem}){' - ' + sub if sub else ''}",
					token=tag, search=f"flag of {flag_name(tag)}"), problem, want))
	return out


# ---------- 🗑 unused ----------
def references(root, game):
	"""(GFX_ names used outside .gfx files, the start of names built in script - "GFX_x_[?var]" -, picture paths named
	anywhere, cosmetic tags) in the mod; the base game's .gfx paths too (a mod file can replace one of its pictures)."""
	names, built, paths, cosmetic = set(), set(), set(), set()
	name_rx = re.compile(r"\b(GFX_\w+)(\[?)")
	path_rx = re.compile(r'"(gfx[/\\][^"\n]+?\.(?:dds|tga|png))"|\b(gfx[/\\][^\s"{}=#]+?\.(?:dds|tga|png))\b', re.I)  # (quoted ones can have spaces)
	cosmetic_rx = re.compile(r"\b(?:set|has)_cosmetic_tag\s*=\s*\"?(\w+)")
	for base, dirs in ((root, TEXT_DIRS), (game, ("interface",))):
		if not base:
			continue
		for d in dirs:
			for folder, _, files in os.walk(os.path.join(base, d)):
				for f in files:
					if not f.lower().endswith(TEXT_EXT if base == root else (".gfx",)):
						continue
					try:
						with open(os.path.join(folder, f), encoding="utf-8-sig", errors="replace") as fh:
							text = fh.read()
					except OSError:
						continue
					if base == root and not f.lower().endswith(".gfx"):
						for name, bracket in name_rx.findall(text):
							(built if bracket else names).add(name)
						cosmetic.update(w.lower() for w in cosmetic_rx.findall(text))
						if f.lower() == "cosmetic.txt":
							cosmetic.update(w.lower() for w in re.findall(r"^(\w+)\s*=\s*\{", text, re.M))
					paths.update(re.sub(r"[/\\]+", "/", a or b).lower() for a, b in path_rx.findall(text))
	# (a family's own start - GFX_culture_[...] - only keeps its numbered ones: the others are checked by token)
	numbered = built & {"GFX_culture_", "GFX_subculture_", "GFX_religion_", "GFX_ideology_"}
	built -= numbered | {"GFX_"}
	return names, built, numbered, paths, cosmetic


def sprite_blocks(text):
	"""[(name, texturefile)] of the spriteTypes in a .gfx file's text."""
	out = []
	for m in re.finditer(r'\bname\s*=\s*"?([\w.\-]+)"?((?:(?!\bname\s*=)[\s\S]){0,400}?)\btexturefile\s*=\s*"([^"]+)"', text, re.I):
		out.append((m.group(1), m.group(3)))
	return out


def unused(root, game, nodes, subs, mains, tags, cosmetics, flag_name, wanted=()):
	"""Unused items. nodes: {kind: set of tokens} (culture / sub / religion / rgroup); subs, mains: ideology tokens;
	wanted: (lower-case) paths that are some entry's icon (no spriteType yet: ⚠ broken, not unused)."""
	names, built, numbered, paths, cosmetic = references(root, game)
	cosmetic |= {x.lower() for x in cosmetics}
	own = {"rr_cultures.gfx": "culture", "rr_religions.gfx": "religion", "rr_ideologies.gfx": "ideology"}  # (only the mod's own lists are judged)
	out = []
	defined = {}  # (texture path -> sprite names) in the mod's .gfx files
	for folder, _, files in os.walk(os.path.join(root, "interface")):
		for f in files:
			if not f.lower().endswith(".gfx"):
				continue
			full = os.path.join(folder, f)
			rel = os.path.relpath(full, root).replace("\\", "/")
			try:
				with open(full, encoding="utf-8-sig", errors="replace") as fh:
					blocks = sprite_blocks(fh.read())
			except OSError:
				continue
			for name, tex in blocks:
				defined.setdefault(re.sub(r"[/\\]+", "/", tex).lower(), set()).add(name)
				dead, kind = None, own.get(f.lower())
				if kind == "culture" and name.startswith("GFX_subculture_") and name[15:] not in nodes["sub"]:
					dead = f"no subculture {name[15:]}"
				elif kind == "culture" and name.startswith("GFX_culture_") and name[12:] not in nodes["culture"]:
					dead = f"no culture {name[12:]}"
				elif kind == "religion" and name.startswith("GFX_religion_") and name[4:] not in nodes["religion"] | nodes["rgroup"]:
					dead = f"no religion {name[4:]}"
				elif kind == "ideology" and name.startswith("GFX_ideology_"):
					base = re.sub(r"_(banner|group)$", "", name[13:])
					if base not in subs and base not in mains:
						dead = f"no ideology {base}"
				if dead and ("[" in name or any(name.startswith(n) and name[len(n):].isdigit() for n in numbered)):
					dead = None  # (a template, or GFX_culture_3 picked by number in script)
				if dead and name not in names and not any(name.startswith(b) for b in built):
					texrel = re.sub(r"[/\\]+", "/", tex)
					out.append(dict(id=f"unused:sprite:{name}", section="ideology" if "ideology" in name else "religion" if "religion" in name else "culture",
						kind="unused_sprite", problem="unused", name=name, token=name, sprite=name, gfx_file=rel, file=texrel,
						paths=[texrel] if os.path.isfile(os.path.join(root, texrel)) else [],
						refs=[os.path.join(root, texrel)] if os.path.isfile(os.path.join(root, texrel)) else [],
						detail=f"spriteType in {rel} for something that's gone ({dead})", link=None, search=name, note=""))
	gone = {x["file"].lower() for x in out}
	for d in UNUSED_FOLDERS:
		section = "portrait" if "leaders" in d else d.rsplit("/", 1)[-1].replace("ideologies", "ideology")
		for folder, _, files in os.walk(os.path.join(root, d)):
			for f in files:
				if not f.lower().endswith(PICTURE_EXT):
					continue
				full = os.path.join(folder, f)
				rel = os.path.relpath(full, root).replace("\\", "/")
				low = rel.lower()
				if low in paths or low in gone or low in wanted:
					continue
				out.append(dict(id=f"unused:file:{rel}", section=section, kind="unused_file", problem="unused", name=f, token=f,
					file=rel, paths=[rel], refs=[full], detail=f"No spriteType or script points at it ({os.path.dirname(rel)})",
					link=None, search=f, note=""))
	own = os.path.join(root, "gfx", "flags")
	if os.path.isdir(own):
		ideologies = sorted(mains, key=len, reverse=True)
		for f in os.listdir(own):
			if not f.lower().endswith(".tga"):
				continue
			stem = f[:-4]
			base = next((stem[:-len(i) - 1] for i in ideologies if stem.lower().endswith("_" + i.lower())), stem)
			if base.upper() in tags or base.lower() in cosmetic or base[:3].upper() in tags and base[3:4] == "_" or re.fullmatch(r"D\d\d", base, re.I):
				continue
			rels = [f"gfx/flags/{s + '/' if s else ''}{f}" for s in ("", "medium", "small")
					if os.path.isfile(os.path.join(root, "gfx", "flags", s, f))]
			out.append(dict(id=f"unused:flag:{stem}", section="flag", kind="unused_flag", problem="unused", name=f, token=base,
				file=rels[0], paths=rels, refs=[os.path.join(own, f)], detail=f"No country or cosmetic tag called {base}",
				link=None, search=f, note=""))
	return out


def remove(root, item, backup_root):
	"""Takes an unused item out of the mod: its files, and its spriteType block (one .gfx edit). Everything is copied
	to backup_root/<time>/ first. Returns the changed paths (relative)."""
	stamp_dir = os.path.join(backup_root, time.strftime("%Y-%m-%d_%H%M%S"))
	changed = []

	def backup(rel):
		dest = os.path.join(stamp_dir, rel)
		os.makedirs(os.path.dirname(dest), exist_ok=True)
		shutil.copy2(os.path.join(root, rel), dest)
	if item.get("sprite") and item.get("gfx_file"):
		full = os.path.join(root, item["gfx_file"])
		with open(full, "rb") as f:
			raw = f.read()
		bom = raw.startswith(b"\xef\xbb\xbf")
		lines = raw.decode("utf-8-sig", errors="replace").splitlines(keepends=True)
		at = next((i for i, l in enumerate(lines) if re.search(rf'\bname\s*=\s*"?{re.escape(item["sprite"])}"?(\s|$)', l)), None)
		if at is not None:
			start = next((i for i in range(at, -1, -1) if re.search(r"\bspriteType\s*=\s*\{", lines[i], re.I)), None)
			if start is not None:
				depth, end = 0, None
				for i in range(start, len(lines)):
					depth += lines[i].count("{") - lines[i].count("}")
					if depth <= 0:
						end = i
						break
				block = "".join(lines[start:end + 1]) if end is not None else ""
				if end is not None and len(re.findall(r"\bname\s*=", block)) == 1:
					backup(item["gfx_file"])
					del lines[start:end + 1]
					with open(full, "wb") as f:
						f.write((b"\xef\xbb\xbf" if bom else b"") + "".join(lines).encode("utf-8"))
					changed.append(item["gfx_file"])
	for rel in item.get("paths", []):
		if os.path.isfile(os.path.join(root, rel)):
			backup(rel)
			os.remove(os.path.join(root, rel))
			changed.append(rel)
	return changed


# ---------- 📈 progress ----------
def counts(items):
	"""{section: number still to do} of a scan (missing + broken). Pictures to rework aren't counted (older scans had
	Country Master's rework marks without a problem, which made them count as missing)."""
	out = Counter(x["section"] for x in items if x.get("problem", "missing") in ("missing", "broken") and x.get("kind") != "rework")
	return dict(out)


def record(data, items):
	"""Today's counts into the shared history; True when that changed it."""
	hist = data.setdefault("gfx", {}).setdefault("history", {})
	today = datetime.date.today().isoformat()
	now = counts(items)
	if hist.get(today) == now:
		return False
	hist[today] = now
	return True


def history(data):
	return sorted((data.get("gfx") or {}).get("history", {}).items())


def month_change(data, month):
	"""(left before the month, left at its end or now) over all sections, or None when there's no history for it."""
	rows = history(data)
	before = [v for d, v in rows if d[:7] < month]
	during = [v for d, v in rows if d[:7] == month]
	if not during:
		return None
	start = before[-1] if before else during[0]
	return sum(start.values()), sum(during[-1].values())
