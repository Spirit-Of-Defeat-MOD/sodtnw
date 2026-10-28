"""Music Master (part of Organisation Master): radio stations and songs of HOI4 music mods.

A music mod (like Revolution_Realized_Musics / Revolution-Realised-Music-Crimson-Tunes) holds:
	music/<station>.txt                 music_station = "<station>" and its songs:  music = { song = "<name>" chance = { ... } }
	music/<station>/*.ogg               the song files
	music/*.asset                       every song:  music = { name = "<name>" file = "<station>/<file>.ogg" volume = 0.65 }
	localisation/*.yml                  <station>_TITLE:0 "Station name"
	interface/*.gfx                     GFX_<station>_album_art (304x120, 2 frames: normal / picked)
	interface/*.gui                     <station>_faceplate (the player) and <station>_stations_entry (the station button)
"""
import json
import os
import queue
import re
import shutil
import struct
import subprocess
import tempfile
import time
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import ttk, messagebox, filedialog, simpledialog, colorchooser

from PIL import Image, ImageDraw, ImageTk

import ui
from culture_master import TextFile
from cm_data import parse, read_text
from music_live import MusicLive

APP_NAME = "Organisation Master"
TOOL_DIR = None  # set by organisation_master.py
PLANS_FILE = "planned_music_stations.json"
PLAN_LOGOS = "planned_station_logos"  # next to PLANS_FILE: the logos picked for planned stations
DEFAULT_VOLUME = 0.65
# album art made before Save to mod waits here
STAGING = os.path.join(tempfile.gettempdir(), "OrganisationMaster_staging")
SONG_SORTS = ("Order in the file", "Song", "Artist", "Length", "Volume", "Chance")
SONG_SORT_COLS = {"Song": "#0", "Artist": "artist", "Length": "time", "Volume": "volume", "Chance": "chance"}


def split_artist(name):
	"""'Title - Artist' (the name the game shows) -> (title, artist)."""
	if " - " in (name or ""):
		a, b = name.rsplit(" - ", 1)
		return a.strip(), b.strip()
	return (name or "").strip(), ""


def join_artist(title, artist):
	title, artist = title.strip().replace('"', "'"), artist.strip().replace('"', "'")
	return f"{title} - {artist}" if artist else title


def norm_song(n):
	return re.sub(r"[^a-z0-9]+", "", (n or "").lower())
ART_SIZE = (304, 120)  # 2 frames of 152 x 120
STATUSES = ("Idea", "Collecting songs", "Ready to make", "Uploading Songs", "Awaiting Art", "Made")
ALL_RR = "★ All RR music mods"
MOD_COLOURS = ("#1f5fa8", "#b0361f", "#2e7d32", "#7b3fa0", "#b06f00", "#00838f", "#8d2a5c")
UNDECIDED = "(not decided)"
PLANNED_MOD = "planned:"  # music mods that have no folder yet: "planned:<slug>"


def git(cwd, *args):
	"""Output of a git command ('' when git or the repository isn't there)."""
	try:
		r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", timeout=20,
						   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		return r.stdout if r.returncode == 0 else ""
	except (OSError, subprocess.SubprocessError):
		return ""


_GIT_USER = []


def git_user():
	"""Who is adding things: the git name (user.name) of the RR repository, else the Windows user."""
	if not _GIT_USER:
		import getpass
		_GIT_USER.append(git(TOOL_DIR or ".", "config", "user.name").strip() or getpass.getuser())
	return _GIT_USER[0]


class Player:
	_owner = None  # pygame has one music stream: previews and sidebar radio take turns.

	"""Plays the station songs (.ogg) inside the tool, with pygame's mixer (started on the first play)."""

	def __init__(self):
		self.mixer = None
		self.path = None      # the song playing (or paused)
		self.length = 0
		self.offset = 0.0     # where the last play / seek started (s)
		self.paused = False
		self.error = None

	def _mixer(self):
		if self.mixer is None:
			try:
				os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
				import pygame
				if not pygame.mixer.get_init():
					pygame.mixer.init()
				self.mixer = pygame.mixer
			except Exception as ex:
				self.error = str(ex)
				raise
		return self.mixer

	def play(self, path, volume=1.0, start=0.0, length=None):
		m = self._mixer()
		if Player._owner is not None:
			Player._owner.stop()
		Player._owner = self
		m.music.load(path)
		m.music.set_volume(max(0.0, min(1.0, float(volume if volume is not None else 1.0))))
		m.music.play(start=start)
		self.path, self.offset, self.paused = path, start, False
		self.length = self.length if length is None else length

	def seek(self, secs):
		if self.path:
			vol = self.mixer.music.get_volume()
			paused = self.paused
			self.play(self.path, vol, secs)
			if paused:
				self.pause()

	def pause(self):
		if self.path and self.mixer:
			if self.paused:
				self.mixer.music.unpause()
			else:
				self.mixer.music.pause()
			self.paused = not self.paused

	def set_volume(self, volume):
		if self.path and self.mixer and Player._owner is self:
			self.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))

	def stop(self):
		if self.mixer and Player._owner is self:
			self.mixer.music.stop()
			self.mixer.music.unload()
			Player._owner = None
		self.path, self.paused = None, False

	def position(self):
		if not (self.path and self.mixer):
			return 0.0
		return self.offset + max(0, self.mixer.music.get_pos()) / 1000

	def finished(self):
		return bool(self.path and self.mixer and not self.paused and not self.mixer.music.get_busy())


def chance_summary(e):
	"""A song's chance = { } in a few words: '1', '2 if has_war = no', '0 unless is_tag = USA'..."""
	ch = next((x for x in (e.value if e.block else []) if x.key == "chance" and x.block), None)
	if ch is None:
		return "1"
	parts = []
	base = [x.value for x in ch.value if x.key == "factor" and not x.block]
	if base:
		parts.append(str(base[0]))

	def conds(block):
		out = []
		for x in block:
			if x.key == "factor":
				continue
			if x.block:
				inner = ", ".join(conds(x.value))
				out.append(f"{x.key} {{ {inner} }}" if x.key not in ("NOT",) else f"not ({inner})")
			else:
				out.append(f"{x.key} = {x.value}")
		return out
	for m in ch.value:
		if m.key == "modifier" and m.block:
			f = next((x.value for x in m.value if x.key == "factor" and not x.block), "1")
			c = conds(m.value)
			parts.append(f"×{f}" + (f" if {', '.join(c)}" if c else "") if (c or base) else str(f))
	return "  |  ".join(parts) or "1"


def block_inner(lines, e):
	"""The text inside an entry's { } (the entry's lines, between its first '{' and last '}')."""
	text = "\n".join(lines[e.first:e.last + 1])
	a = text.find("{", text.find(e.key) if e.key in text else 0)
	b = text.rfind("}")
	return text[a + 1:b] if a >= 0 and b > a else ""


def tidy_code(text):
	"""Script typed in a box -> one statement per line, indented by its { } depth (tabs); # comments kept."""
	toks = []
	for line in text.split("\n"):
		code, _, comment = line.partition("#")
		toks += re.findall(r'"[^"]*"|[{}]|[<>!]?=|[<>]|[^\s{}=<>!"]+', code)
		if comment.strip():
			toks.append("#" + comment.rstrip())
	out, depth, i = [], 0, 0
	while i < len(toks):
		t = toks[i]
		if t.startswith("#"):
			out.append("\t" * depth + t)
		elif t == "}":
			depth = max(0, depth - 1)
			out.append("\t" * depth + "}")
		elif t == "{":
			out.append("\t" * depth + "{")
			depth += 1
		elif i + 2 < len(toks) and toks[i + 1] in ("=", "<", ">", "<=", ">=", "!="):
			op, val = toks[i + 1], toks[i + 2]
			if val == "{":
				out.append("\t" * depth + f"{t} {op} {{")
				depth += 1
			else:
				out.append("\t" * depth + f"{t} {op} {val}")
			i += 2
		else:
			out.append("\t" * depth + t)
		i += 1
	return out


def volume_control(parent, var, on_change=None, length=170):
	"""A volume slider (0 - 1) with its number next to it; double-click the number to type one."""
	f = ttk.Frame(parent)
	try:
		start = float(var.get())
	except ValueError:
		start = DEFAULT_VOLUME
	pos = tk.DoubleVar(value=start)
	num = ttk.Label(f, text=f"{start:.2f}", width=5, anchor="e", cursor="xterm")
	ent = ttk.Entry(f, textvariable=var, width=6)

	def slid(_=None):
		v = round(pos.get(), 2)
		var.set(f"{v:g}")
		num.config(text=f"{v:.2f}")
		if on_change:
			on_change(v)

	def typed(_=None):
		try:
			v = max(0.0, min(1.0, float(var.get())))
		except ValueError:
			v = pos.get()
		pos.set(v)
		slid()
		ent.pack_forget()
		num.pack(side="left", padx=(6, 0))

	def edit(_=None):
		num.pack_forget()
		ent.pack(side="left", padx=(6, 0))
		ent.focus_set()
		ent.select_range(0, "end")
	sc = ttk.Scale(f, from_=0, to=1, variable=pos, orient="horizontal", length=length, command=slid)
	sc.pack(side="left")
	ui.jump_scale(sc, pos, on_move=lambda v: slid())
	num.pack(side="left", padx=(6, 0))
	num.bind("<Double-1>", edit)
	ent.bind("<Return>", typed)
	ent.bind("<FocusOut>", typed)
	return f


def _icon(kind, colour):
	"""14 x 14 ▶ / ■ for the song lists."""
	im = Image.new("RGBA", (16, 14), (0, 0, 0, 0))
	d = ImageDraw.Draw(im)
	if kind == "play":
		d.polygon([(3, 1), (3, 12), (13, 6.5)], fill=colour)
	else:
		d.rectangle([3, 2, 12, 11], fill=colour)
	return im


def today():
	return time.strftime("%Y-%m-%d")


def added_text(x):
	if not x.get("added_by"):
		return ""
	return f"added by {x['added_by']}" + (f" on {x['added']}" if x.get("added") else "") + (" (from the RR spreadsheet)" if x.get("source") == "spreadsheet" else "")
# The RR spreadsheet's Music tab (station rows, then their songs: title, YouTube link, artist, in game?)
SHEET_CSV = "https://docs.google.com/spreadsheets/d/1BiNhdPK4WSEDZ6qphtaVNj2SMaS2Ifs-bcc_PpwIioo/export?format=csv&gid=529155526"


def is_rr_music(root, name=""):
	"""An RR music mod: 'Revolution Realised/Realized ... Music' in its folder or name."""
	text = (os.path.basename(root) + " " + name).lower()
	return bool(re.search(r"revolution.?reali[sz]ed", text)) and "music" in text


def norm_title(t):
	"""Station names compared loosely: 'The Voice of the Worker' = 'Voice of the Worker', 'Patriotic 66' ~ 'Patriot 66'."""
	t = re.sub(r"\bthe\b", "", (t or "").lower())
	return re.sub(r"[^a-z0-9]+", "", t)


def same_title(a, b):
	import difflib
	x, y = norm_title(a), norm_title(b)
	return bool(x) and (x == y or difflib.SequenceMatcher(None, x, y).ratio() >= 0.86)


def parse_sheet(rows):
	"""The Music tab -> [{title, theme, songs: [{title, artist, link, in_game}]}]."""
	out, cur = [], None
	for r in rows[1:]:
		a, b, c, _, e = [x.strip() for x in (list(r) + [""] * 5)[:5]]
		if not (a or b or c):
			continue
		if b.startswith("- ") or re.fullmatch(r"\d+ Songs?", c):
			cur = {"title": a, "theme": b[2:].strip() if b.startswith("- ") else b, "songs": []}
			out.append(cur)
		elif cur is not None and (a or b.startswith("http")):
			cur["songs"].append({"title": a or "(no title)", "artist": c, "link": b if b.startswith("http") else "", "in_game": e.upper() == "TRUE"})
	return out


def plan_song(x):
	"""Plan songs are dicts (title, artist, link, in_game); older plans kept plain lines."""
	return x if isinstance(x, dict) else {"title": str(x), "artist": "", "link": "", "in_game": False}


def song_line(x):
	x = plan_song(x)
	return ("✓ " if x.get("in_game") else "") + x["title"] + (f" - {x['artist']}" if x.get("artist") else "") + (f" | {x['link']}" if x.get("link") else "")


def parse_song_line(line):
	done = line.startswith("✓")
	line = line.lstrip("✓ ").strip()
	link = ""
	if " | " in line:
		line, link = line.rsplit(" | ", 1)
	title, artist = (line.rsplit(" - ", 1) + [""])[:2] if " - " in line else (line, "")
	return {"title": title.strip(), "artist": artist.strip(), "link": link.strip(), "in_game": done}


# ---------------------------------------------------------------- ogg files
def ogg_info(path):
	"""(seconds, {TITLE, ARTIST, ...}) of an Ogg Vorbis file, from its headers and last page; (None, {}) if unreadable."""
	try:
		with open(path, "rb") as f:
			head = f.read(65536)
			f.seek(0, 2)
			size = f.tell()
			f.seek(max(0, size - 65536))
			tail = f.read()
	except OSError:
		return None, {}
	tags = {}
	i = head.find(b"\x01vorbis")
	if head[:4] != b"OggS" or i < 0:
		return None, tags
	rate = struct.unpack_from("<I", head, i + 12)[0]
	j = tail.rfind(b"OggS")
	secs = None
	if j >= 0 and rate:
		gran = struct.unpack_from("<q", tail, j + 6)[0]
		secs = gran / rate if gran > 0 else None
	k = head.find(b"\x03vorbis")
	try:
		vl = struct.unpack_from("<I", head, k + 7)[0]
		p = k + 11 + vl
		n = struct.unpack_from("<I", head, p)[0]
		p += 4
		for _ in range(min(n, 64)):
			ln = struct.unpack_from("<I", head, p)[0]
			p += 4
			kv = head[p:p + ln].decode("utf-8", "replace")
			p += ln
			if "=" in kv:
				a, b = kv.split("=", 1)
				tags[a.upper()] = b
	except (struct.error, ValueError):
		pass
	return secs, tags


def mmss(secs):
	return f"{int(secs) // 60}:{int(secs) % 60:02d}" if secs else ""


def slug(text):
	return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "song"


# ---------------------------------------------------------------- the mod
class Song:
	def __init__(self, name, file, volume, rel, entry):
		self.name, self.file, self.volume, self.rel, self.entry = name, file, volume, rel, entry


class Station:
	def __init__(self, token, rel):
		self.token, self.rel = token, rel
		self.title = None
		self.songs = []  # [(song name, chance factor, Entry)] in its file
		self.art = None  # its album art file (full path)


def music_mod_name(root):
	"""Discover a mod's label without parsing its stations, assets and localisation."""
	name = os.path.basename(root)
	desc = os.path.join(root, "descriptor.mod")
	if os.path.exists(desc):
		m = re.search(r'^\s*name\s*=\s*"([^"]*)"', read_text(desc), re.M)
		if m:
			name = m.group(1)
	return name


class MusicMod:
	"""Everything about the stations and songs of one music mod."""

	def __init__(self, root):
		self.root = root
		self.name = music_mod_name(root)
		self.pending_text = {}   # rel -> lines: changed text files, written on Save to mod
		self.pending_files = {}  # rel -> the file to copy there on Save to mod (None: delete it)
		self.load()

	def path(self, rel):
		return os.path.join(self.root, rel)

	def rel(self, path):
		return os.path.relpath(path, self.root).replace("\\", "/")

	def files(self, folder, ext):
		"""rel paths of the folder's files with that extension (with the unsaved ones, without the deleted ones)."""
		d = self.path(folder)
		out = []
		for base, _, names in os.walk(d):
			out += [self.rel(os.path.join(base, n)) for n in sorted(names) if n.lower().endswith(ext)]
		for rel in list(self.pending_text) + [r for r, src in self.pending_files.items() if src]:
			if rel.startswith(folder + "/") and rel.lower().endswith(ext) and rel not in out:
				out.append(rel)
		return [r for r in out if self.exists(r)]

	# (reads go through the unsaved changes)
	def exists(self, rel):
		if rel in self.pending_text:
			return True
		if rel in self.pending_files:
			return self.pending_files[rel] is not None
		return os.path.exists(self.path(rel))

	def real(self, rel):
		"""The file to read for rel: an unsaved copy's source, else the mod's file (None: not there)."""
		if rel in self.pending_files:
			return self.pending_files[rel]
		p = self.path(rel)
		return p if os.path.exists(p) else None

	def read(self, rel):
		if rel in self.pending_text:
			return "\n".join(self.pending_text[rel])
		return read_text(self.path(rel))

	def text_lines(self, rel):
		if rel in self.pending_text:
			return list(self.pending_text[rel])
		p = self.path(rel)
		return list(TextFile(p).lines) if os.path.exists(p) else []

	def pending_count(self):
		return len(self.pending_text) + len(self.pending_files)

	def load(self):
		self.songs = {}       # name -> Song (from the .asset files)
		self.dup_names = []   # (name, rel, rel of the earlier one): a song name given twice in the .asset files
		self.asset_files = []
		for rel in self.files("music", ".asset"):
			self.asset_files.append(rel)
			for e in parse(self.read(rel)):
				if e.key == "music" and e.block:
					name = str(e.get("name", "")).strip('"')
					if name:
						if name in self.songs:
							self.dup_names.append((name, rel, self.songs[name].rel))
						self.songs[name] = Song(name, str(e.get("file", "")).strip('"'), e.get("volume"), rel, e)
		self.stations = {}
		for rel in sorted(r for r in self.files("music", ".txt") if r.count("/") == 1):
			top = parse(self.read(rel))
			token = next((str(e.value).strip('"') for e in top if e.key == "music_station" and not e.block), None)
			if not token:
				continue
			st = self.stations[token] = Station(token, rel)
			for e in top:
				if e.key == "music" and e.block:
					st.songs.append((str(e.get("song", "")).strip('"'), chance_summary(e), e))
		# Names (<station>_TITLE), album art (GFX_<station>_album_art)
		self.loc_files = self.files("localisation", ".yml")
		for f in self.loc_files:
			for line in self.text_lines(f):
				m = re.match(r'^\s*(\w+)_TITLE:\d*\s*"(.*)"', line)
				if m and m.group(1) in self.stations:
					self.stations[m.group(1)].title = m.group(2)
		self.gfx_files = self.files("interface", ".gfx")
		self.gui_files = self.files("interface", ".gui")
		for f in self.gfx_files:
			text = self.read(f)
			for m in re.finditer(r'name\s*=\s*"GFX_(\w+)_album_art"\s*texturefile\s*=\s*"([^"]+)"', text):
				if m.group(1) in self.stations:
					rel = re.sub(r"/+", "/", m.group(2).replace("\\", "/"))
					self.stations[m.group(1)].art_rel = rel
					self.stations[m.group(1)].art = self.real(rel)

	def song_path(self, song):
		"""The song's file to play / measure (an unsaved one too); None when it isn't there."""
		return self.real("music/" + song.file) if song else None

	def issues(self):
		"""Gap Finder: [(kind, text, station token or None, song name or None)] - duplicates, missing music and
		other things that don't add up."""
		out = []
		for name, rel, first in self.dup_names:
			out.append(("Duplicate song name", f"'{name}' is in the .asset files twice ({first} and {rel})", None, name))
		groups = {}
		for n in self.songs:
			groups.setdefault(norm_song(n), []).append(n)
		for names in groups.values():
			if len(names) > 1:
				out.append(("Same song, different spelling", " / ".join(f"'{n}'" for n in names), None, names[0]))
		files = {}
		for n, song in self.songs.items():
			files.setdefault(song.file.lower(), []).append(n)
		for f, names in files.items():
			if len(names) > 1:
				out.append(("Same file for two songs", f"music/{f}: " + ", ".join(f"'{n}'" for n in names), None, names[0]))
		played = set()
		for st in self.stations.values():
			seen = {}
			for n, _, _ in st.songs:
				played.add(n)
				seen[n] = seen.get(n, 0) + 1
				if n not in self.songs:
					out.append(("Missing music: no .asset entry", f"{st.title or st.token}: '{n}' has no music = {{ }} in the .asset files", st.token, n))
				elif not self.song_path(self.songs[n]):
					out.append(("Missing music: no file", f"{st.title or st.token}: '{n}' - music/{self.songs[n].file} isn't there", st.token, n))
			for n, k in seen.items():
				if k > 1:
					out.append(("Song twice in a station", f"{st.title or st.token}: '{n}' is in it {k} times", st.token, n))
			if not st.title:
				out.append(("Station without a name", f"{st.token}: no {st.token}_TITLE", st.token, None))
			if not st.art:
				out.append(("Station without album art", f"{st.token}: no GFX_{st.token}_album_art picture", st.token, None))
		for n in self.songs:
			if n not in played:
				out.append(("Song in no station", f"'{n}' is in the .asset files but no station plays it", None, n))
		used = {("music/" + s.file).lower() for s in self.songs.values()}
		for rel in self.files("music", ".ogg"):
			if rel.lower() not in used:
				out.append(("Unused .ogg file", f"{rel} - no song uses it", None, None))
		return out

	def problems(self):
		return [text for _, text, _, _ in self.issues()]


def find_music_mods(mod_dir):
	"""Folders of the mod folder that have music/*.asset files (or station .txt files)."""
	out = []
	try:
		names = sorted(os.listdir(mod_dir))
	except OSError:
		return out
	for n in names:
		d = os.path.join(mod_dir, n, "music")
		if os.path.isdir(d) and any(f.lower().endswith((".asset", ".txt")) for f in os.listdir(d)):
			out.append(os.path.join(mod_dir, n))
	return out


def make_album_art(src, dst):
	"""304 x 120: the picture twice (152 x 120), the second with the red 'picked' frame and tick of the RR stations."""
	im = Image.open(src).convert("RGBA")
	fw, fh = ART_SIZE[0] // 2, ART_SIZE[1]
	# fill the frame (cut the overflow), like the existing station art
	scale = max(fw / im.width, fh / im.height)
	im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
	left, top = (im.width - fw) // 2, (im.height - fh) // 2
	im = im.crop((left, top, left + fw, top + fh))
	out = Image.new("RGBA", ART_SIZE, (0, 0, 0, 0))
	for k, colour in ((0, (40, 40, 40, 255)), (1, (205, 40, 40, 255))):
		fr = im.copy()
		d = ImageDraw.Draw(fr)
		d.rectangle([0, 0, fw - 1, fh - 1], outline=colour, width=2)
		if k:
			d.line([(fw - 18, 9), (fw - 13, 14), (fw - 5, 4)], fill=colour, width=3)
		out.paste(fr, (k * fw, 0))
	os.makedirs(os.path.dirname(dst), exist_ok=True)
	out.save(dst, "DDS")


# ---------------------------------------------------------------- the window part
class MusicMaster(MusicLive, ttk.Frame):
	def __init__(self, parent, app):
		super().__init__(parent, padding=6)
		self.app = app
		self.mod = None
		self._photos = []
		top = ttk.Frame(self)
		top.pack(fill="x", pady=(0, 2))
		ttk.Label(top, text="Music mod:", style="Head.TLabel").pack(side="left")
		self.mod_var = tk.StringVar()
		self.mod_box = ttk.Combobox(top, textvariable=self.mod_var, state="readonly", width=56, font="TkDefaultFont")
		self.mod_box.pack(side="left", padx=4)
		self.mod_box.bind("<<ComboboxSelected>>", lambda ev: self.open_view(self.mod_var.get()))
		ttk.Button(top, text="New music mod...", command=self.new_mod).pack(side="left", padx=2)
		ttk.Button(top, text="Open its folder", command=lambda: self.mod and os.startfile(self.mod.root)).pack(side="left", padx=2)
		ttk.Button(top, text="Reload", command=lambda: self.open_view(self.mod_var.get(), reload=True)).pack(side="left", padx=2)
		self.gap_btn = ttk.Button(top, text="🔍 Gap Finder", command=self.gap_finder)
		self.gap_btn.pack(side="left", padx=(12, 2))

		self.winfo_toplevel().bind("<Control-s>", lambda ev: self.winfo_ismapped() and self.save_all(), add="+")
		info = ttk.Frame(self)
		info.pack(fill="x", pady=(2, 6))
		self.mod_info = ttk.Label(info, text="", style="Muted.TLabel")
		self.mod_info.pack(side="left")
		self.legend = ttk.Frame(info)
		self.legend.pack(side="left", padx=10)
		# Save to mod: changes wait here until saved (like Culture Master)
		self.discard_btn = ttk.Button(info, text="Discard", command=self.discard_all)
		self.discard_btn.pack(side="right", before=self.mod_info)
		self.save_btn = ttk.Button(info, text="💾 Save to mod", command=self.save_all)
		self.save_btn.pack(side="right", padx=4, before=self.mod_info)
		self.unsaved_label = ttk.Label(info, text="", foreground="#b06f00")
		self.unsaved_label.pack(side="right", padx=6, before=self.mod_info)
		self._loaded = {}     # root -> MusicMod
		self._dur = {}        # (path, mtime) -> seconds
		self._duration_pending = set()
		self._duration_keys = {}
		self._station_duration_paths = {}
		self._duration_requests = queue.Queue()
		self._duration_results = queue.SimpleQueue()
		self._duration_stop = threading.Event()
		self._duration_workers = []
		self._duration_job = None
		self.bind("<Destroy>", self._destroy_metadata, add="+")
		self._blame = {}      # (mod root, file) -> "added by ..."
		self.mod_meta = {}    # music mod (folder, or planned:<slug>) -> {"name", "colour"}: from the plans file
		self.view_mods = []   # the mods shown (one, or every RR music mod)

		pw = ttk.PanedWindow(self, orient="horizontal")
		pw.pack(fill="both", expand=True)
		left = ttk.Frame(pw, padding=(0, 0, 6, 0), width=ui.px(500))  # (the sash decides its width: drag it)
		left.pack_propagate(False)
		pw.add(left, weight=1)
		right = ttk.Frame(pw, padding=(6, 0, 0, 0))
		pw.add(right, weight=3)

		# Stations
		sec = self.sec_stations = ui.Section(left, "Radio stations", "music_stations", self.app, expand=False).place_in(fill="x")
		ui.tool_button(sec.tools, "+ New station", self.new_station).pack(side="left", padx=2)
		pullbar = ttk.Frame(sec.body)
		pullbar.pack(fill="x", pady=(0, 4))
		self.pull_stations_button = ttk.Button(pullbar, text="Pull station updates", command=self.pull_stations, state="disabled")
		self.pull_stations_button.pack(side="left", fill="x", expand=True)
		self.download_stations_button = ttk.Button(pullbar, text="Get missing music mods",
			command=lambda: self.pull_stations(download=True), state="disabled")
		self.download_stations_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

		box = ttk.Frame(sec.body)
		box.pack(fill="x")
		t = self.st_tree = ttk.Treeview(box, columns=("songs", "time"), height=10, selectmode="browse")
		t.heading("#0", text="Station")
		t.heading("songs", text="Songs")
		t.heading("time", text="Length")
		t.column("#0", width=ui.px(200), stretch=True, minwidth=ui.px(150))
		t.column("songs", width=ui.px(60), anchor="e", stretch=False)
		t.column("time", width=ui.px(75), anchor="e", stretch=False)
		ys = ttk.Scrollbar(box, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		for i, c in enumerate(MOD_COLOURS):
			t.tag_configure(f"m{i}", foreground=c)
		t.bind("<<TreeviewSelect>>", lambda ev: self.show_station())
		t.bind("<ButtonRelease-1>", self.click_station)

		# Planned stations
		sec = self.sec_plans = ui.Section(left, "Planned music stations", "music_plans", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		ui.tool_button(sec.tools, "+ New plan", lambda: self.edit_plan(new=True)).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "Import from spreadsheet", self.import_sheet).pack(side="left", padx=2)
		box = ttk.Frame(sec.body)
		box.pack(fill="x")
		p = self.plan_tree = ttk.Treeview(box, columns=("mod", "status", "songs"), height=10, selectmode="extended")
		p.heading("#0", text="Plan")
		p.heading("mod", text="Music mod")
		p.heading("status", text="Status")
		p.heading("songs", text="Songs")
		p.column("#0", width=ui.px(170), stretch=True, minwidth=ui.px(140))
		p.column("mod", width=ui.px(130), stretch=False)
		p.column("status", width=ui.px(120), stretch=False)
		p.column("songs", width=ui.px(62), anchor="e", stretch=False)
		ys = ttk.Scrollbar(box, command=p.yview)
		p.config(yscrollcommand=ys.set)
		p.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		for i, c in enumerate(MOD_COLOURS):
			p.tag_configure(f"m{i}", foreground=c)
		p.tag_configure("undecided", foreground="#777")
		p.bind("<Double-1>", lambda ev: self.edit_plan())
		p.bind("<<TreeviewSelect>>", lambda ev: self.show_plan())
		p.bind("<Button-3>", self.plan_menu)
		p.bind("<ButtonRelease-1>", lambda ev: p.identify_row(ev.y) and self.show_plan())
		pb = ttk.Frame(sec.body)
		pb.pack(fill="x", pady=(4, 0))
		ttk.Button(pb, text="Edit...", command=self.edit_plan).pack(side="left")
		ttk.Button(pb, text="Delete", command=self.delete_plan).pack(side="left", padx=4)
		ttk.Button(pb, text="Attach to music mod...", command=self.attach_plans).pack(side="left")
		ttk.Button(pb, text="Make the station", command=self.plan_to_station).pack(side="left", padx=4)
		ttk.Label(sec.body, text="Right-click a plan for its music mod (or a new one).", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

		# The right side shows the picked station, or the picked planned station
		self.right = right
		self.plan_pane = ttk.Frame(right)
		self.station_pane = right = ttk.Frame(right)
		right.pack(fill="both", expand=True)
		self.cur_plan = None
		self._plan_job = None
		self._adopt = None

		# The station
		sec = ui.Section(right, "Station", "music_station_head", self.app, expand=False).place_in(fill="x")
		head = ttk.Frame(sec.body)
		head.pack(fill="x")
		self.art_label = tk.Label(head, text="(no album art)", width=20, height=6, relief="groove")
		self.art_label.pack(side="left")
		hf = ttk.Frame(head)
		hf.pack(side="left", fill="x", expand=True, padx=12)
		self.st_title = ttk.Label(hf, text="Pick a station", style="Title.TLabel")
		self.st_title.pack(anchor="w")
		self.st_info = ttk.Label(hf, text="", style="Muted.TLabel", justify="left")
		self.st_info.pack(anchor="w", pady=(2, 0))
		hb = ttk.Frame(hf)
		hb.pack(anchor="w", pady=(8, 0))
		ttk.Button(hb, text="Rename...", command=self.rename_station).pack(side="left")
		ttk.Button(hb, text="Album art...", command=self.change_art).pack(side="left", padx=4)
		ttk.Button(hb, text="Open its file", command=lambda: self.station and os.startfile(self.mod.path(self.station.rel))).pack(side="left")

		sec = self.sec_songs = ui.Section(right, "Songs", "music_station_songs", self.app).place_in(fill="both", pady=(8, 0))
		tk.Label(sec.tools, text="Sort by", background=ui.HEAD_BG, font="om_small").pack(side="left", padx=(12, 4))
		self.song_sort = tk.StringVar(value=self.app.config.get("music_song_sort", SONG_SORTS[0]))
		sb_ = ttk.Combobox(sec.tools, textvariable=self.song_sort, values=SONG_SORTS, state="readonly", width=16, font="TkDefaultFont")
		sb_.pack(side="left")
		sb_.bind("<<ComboboxSelected>>", lambda ev: self.set_song_sort(self.song_sort.get()))
		self.song_dir = ui.tool_button(sec.tools, "▲", lambda: self.set_song_sort(self.song_sort.get(), flip=True))
		self.song_dir.config(width=3)
		self.song_dir.pack(side="left", padx=2)
		right = sec.body
		self.song_add_actions = self.balanced_buttons(right, (
			("Add audio files…", self.add_songs), ("Plan a song…", self.plan_station_song),
			("Download / edit…", self.audio_workshop)))
		sf = ttk.Frame(right, width=ui.px(500), height=ui.px(250))
		sf.pack_propagate(False)
		sf.pack(fill="both", expand=True)
		s = self.song_tree = ttk.Treeview(sf, columns=("artist", "time", "volume", "chance", "file"), selectmode="extended")
		for col, text, w in (("#0", "Song", 260), ("artist", "Artist", 170), ("time", "Length", 70), ("volume", "Volume", 80),
							 ("chance", "Chance", 170), ("file", "File (double-click to change)", 240)):
			s.heading(col, text=text)
			s.column(col, width=ui.px(w), anchor="w" if col in ("#0", "artist", "file", "chance") else "e",
					 stretch=col in ("#0", "artist", "file", "chance"))
		ys = ttk.Scrollbar(sf, command=s.yview)
		xs = ttk.Scrollbar(sf, orient="horizontal", command=s.xview)
		s.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
		xs.pack(side="bottom", fill="x")
		s.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		s.tag_configure("problem", foreground="#b00")
		s.tag_configure("playing", background="#e3f0d8", font="om_bold")
		s.bind("<Double-1>", self.song_double)
		s.bind("<Button-1>", self.song_click, add="+")
		self.player = Player()
		self._play_row = None   # (mod root, token, song name) playing
		self.img_play = ImageTk.PhotoImage(_icon("play", "#2e7d32"))
		self.img_stop = ImageTk.PhotoImage(_icon("stop", "#c62828"))
		self.img_play_off = ImageTk.PhotoImage(_icon("play", "#bbbbbb"))
		self.img_video = ImageTk.PhotoImage(_icon("play", "#c62828"))
		nb = self.now_bar = tk.Frame(right, background="#eef4ea", padx=6, pady=4)
		nb.pack(fill="x", pady=(6, 4))
		self.btn_stop = ttk.Button(nb, text="■ Stop", width=1, command=self.stop_song)
		self.btn_stop.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
		self.btn_pause = ttk.Button(nb, text="⏸ Pause", width=1, command=self.pause_song)
		self.btn_pause.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
		self.now_label = tk.Label(nb, text="Click ▶ in front of a song to play it here.", foreground="#555", background="#eef4ea",
								  font="om_body", anchor="w", wraplength=ui.px(240))
		self.now_label.grid(row=0, column=2, sticky="ew", padx=6)
		self.now_pos = tk.DoubleVar()
		self.now_scale = ttk.Scale(nb, from_=0, to=1, variable=self.now_pos, orient="horizontal")
		self.now_scale.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
		# a click jumps to that point of the song (holding and moving follows the mouse)
		ui.jump_scale(self.now_scale, self.now_pos, on_move=lambda v: setattr(self, "_seeking", True), on_release=lambda v: self.seek_song())
		self._seeking = False
		self.now_time = tk.Label(nb, text="", width=12, background="#eef4ea", font="om_body")
		self.now_time.grid(row=1, column=2, sticky="e", padx=6)
		for column in range(3):
			nb.columnconfigure(column, weight=1, uniform="playback")
		self.btn_stop.state(["disabled"])
		self.btn_pause.state(["disabled"])
		self.song_actions = self.balanced_buttons(right, (
			("Edit song…", self.edit_song), ("Trim / levels…", lambda: self.audio_workshop(edit=True)),
			("Move to station…", self.move_songs), ("Remove", self.remove_songs),
			("▶ / ■ Play", self.play_song), ("Open in player", self.open_song)))
		ttk.Label(right, text="In Order in the file, drag songs to reorder them. Save to mod writes the new station order.",
			style="Muted.TLabel", wraplength=ui.px(760)).pack(anchor="w", pady=(4, 0))
		queue_sec = self.station_queue_sec = ui.Section(right, "Planned songs for this station", "music_station_queue", self.app,
			expand=False).place_in(fill="x", pady=(6, 0))
		self.balanced_buttons(queue_sec.body, (("Plan a song…", self.plan_station_song),
			("Edit planned song…", self.edit_station_queue), ("Download queue…", lambda: self.audio_workshop(station_queue=True))))
		self.station_queue = ttk.Treeview(queue_sec.body, columns=("artist", "link"), height=3, show="tree headings", selectmode="extended")
		for col, text, width in (("#0", "Song", 230), ("artist", "Artist", 130), ("link", "YouTube", 260)):
			self.station_queue.heading(col, text=text)
			self.station_queue.column(col, width=ui.px(width), minwidth=60, stretch=True)
		self.station_queue.pack(fill="x")
		self.station_queue.bind("<Double-1>", lambda event: self.edit_station_queue())
		ttk.Label(right, text="Songs must be Ogg Vorbis (.ogg): HOI4 plays nothing else. Adding copies the file into "
							  "music/<station>/, writes its music = { } in the .asset file and in the station's file.",
				  style="Muted.TLabel", wraplength=800, justify="left").pack(anchor="w", pady=(6, 0))
		self.build_plan_pane(self.plan_pane)
		ui.sortable(self.st_tree)
		ui.sortable(self.plan_tree)
		ui.sortable(self.song_tree, on_change=self.song_sorted)
		from music_order import SongOrderDrag
		self.song_drag = SongOrderDrag(self)
		self._song_rev = bool(self.app.config.get("music_song_rev"))
		self.set_song_sort(self.song_sort.get(), refill=False)
		self.station = None
		self.plans = self.load_plans()
		self.fill_mods()
		self.init_music_live()
		self.after(300, lambda: self.save_plans() if any(not p.get("id") for p in self.plans) else self.sync_todo())

	# ---------- helpers ----------
	def status(self, text):
		self.app.set_status(text)

	def write(self, rel, lines, mod=None):
		"""A text file of the music mod changed: kept until Save to mod."""
		m = mod or self.mod
		lines = list(lines)
		while lines and not lines[-1].strip():  # one newline at the end, not one more each save
			lines.pop()
		m.pending_text[rel] = lines
		self.update_save()

	def lines(self, rel):
		return self.mod.text_lines(rel)

	def stage_file(self, rel, src, mod=None):
		"""A file to copy into the music mod (src) - or delete (None) - on Save to mod."""
		(mod or self.mod).pending_files[rel] = src
		self.update_save()

	def stage_art(self, src, rel, mod=None):
		"""Album art made now (304 x 120 .dds), copied into the mod on Save to mod."""
		m = mod or self.mod
		dst = os.path.join(STAGING, os.path.basename(m.root), rel)
		make_album_art(src, dst)
		self.stage_file(rel, dst, m)

	def unsaved(self):
		return [m for m in self._loaded.values() if m.pending_count()]

	def update_save(self):
		n = sum(m.pending_count() for m in self.unsaved()) if hasattr(self, "_loaded") else 0
		if hasattr(self, "save_btn"):
			self.save_btn.config(text=f"💾 Save to mod ({n})" if n else "💾 Save to mod")
			self.save_btn.state(["!disabled"] if n else ["disabled"])
			self.discard_btn.state(["!disabled"] if n else ["disabled"])
			self.unsaved_label.config(text=f"{n} unsaved change{'s' if n != 1 else ''}" if n else "")

	def _backup(self, m, rel, when):
		src = m.path(rel)
		if os.path.exists(src):
			dst = os.path.join(TOOL_DIR, "backups", when, os.path.basename(m.root), rel)
			os.makedirs(os.path.dirname(dst), exist_ok=True)
			if not os.path.exists(dst):
				shutil.copy2(src, dst)

	def _write_disk(self, m, rel, lines):
		path = m.path(rel)
		if os.path.exists(path):
			tf = TextFile(path)
			tf.lines = list(lines)
			tf.ends = [tf.nl] * len(lines)
			tf.save()
		else:
			os.makedirs(os.path.dirname(path), exist_ok=True)
			bom = "\ufeff" if rel.endswith(".yml") else ""
			with open(path, "w", encoding="utf-8", newline="\r\n") as f:
				f.write(bom + "\n".join(lines) + "\n")

	def save_all(self):
		"""Save to mod: every unsaved change of every music mod (each file backed up first)."""
		mods = self.unsaved()
		if not mods:
			self.status("Nothing to save.")
			return True
		when = time.strftime("%Y-%m-%d_%H-%M-%S")
		n = 0
		saved_files = []
		report = []
		backup_dir = os.path.join(TOOL_DIR, "backups", when)
		try:
			for m in mods:
				for rel, lines in m.pending_text.items():
					existed = os.path.exists(m.path(rel))
					self._backup(m, rel, when)
					self._write_disk(m, rel, lines)
					saved_files.append(f"{os.path.basename(m.root)}/{rel}")
					report.append((m.name, "Updated" if existed else "Created", f"{os.path.basename(m.root)}/{rel}"))
					self.app.log(f"{os.path.basename(m.root)}/{rel}")
					n += 1
				for rel, src in m.pending_files.items():
					dst = m.path(rel)
					existed = os.path.exists(dst)
					self._backup(m, rel, when)
					if src is None:
						if os.path.exists(dst):
							if self.player.path and os.path.normcase(self.player.path) == os.path.normcase(dst):
								self.stop_song()
							os.remove(dst)
					elif os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dst)):
						os.makedirs(os.path.dirname(dst), exist_ok=True)
						shutil.copy2(src, dst)
					if src is not None:
						saved_files.append(f"{os.path.basename(m.root)}/{rel}")
					report.append((m.name, ("Deleted" if existed else "Already absent") if src is None else
						("Updated" if existed else "Created"), f"{os.path.basename(m.root)}/{rel}"))
					self.app.log(f"{os.path.basename(m.root)}/{rel}" + (" (deleted)" if src is None else ""))
					n += 1
				m.pending_text.clear()
				m.pending_files.clear()
				m.load()
		except OSError as ex:
			messagebox.showerror(APP_NAME, f"Saving stopped: {ex}\n\n{n} file change(s) were written before the error. What wasn't written is still unsaved.")
			if report:
				self.show_saved_files(report, backup_dir, complete=False)
			self.update_save()
			return False
		shutil.rmtree(STAGING, ignore_errors=True)
		self.after_change()
		self.publish_stations()
		self.status(f"Saved {n} file{'s' if n != 1 else ''} to {', '.join(m.name for m in mods)} (backups in tools/organisation_master/backups/{when}).")
		if n:
			from master_activity import record
			record("Music Master", self.app.mod_root, files=saved_files, who=self.app.todo_page().me.get())
		getattr(self.app, "feedback", lambda *_: None)("success")
		self.show_saved_files(report, backup_dir)
		return True

	def show_saved_files(self, report, backup_dir, complete=True):
		"""A scrollable receipt for the actual writes, including removals and backup location."""
		window = tk.Toplevel(self)
		window._om_nonmodal = True
		window.title("Saved to music mods" if complete else "Music files saved before the error")
		window.transient(self.winfo_toplevel())
		window.geometry(f"{min(ui.px(900), window.winfo_screenwidth()-60)}x{min(ui.px(470), window.winfo_screenheight()-90)}")
		body = ttk.Frame(window, padding=12)
		body.pack(fill="both", expand=True)
		ttk.Label(body, text=f"{'Saved' if complete else 'Partially saved'} · {len(report)} file change(s)", style="Title.TLabel").pack(anchor="w")
		counts = {kind: sum(action == kind for _, action, _ in report) for kind in ("Created", "Updated", "Deleted", "Already absent")}
		ttk.Label(body, text="  ·  ".join(f"{count} {kind.lower()}" for kind, count in counts.items() if count),
			style="Muted.TLabel").pack(anchor="w", pady=(4, 8))
		text = "Saved:\n" + "\n".join(f"  {path} ({action})" for _, action, path in report)
		has_backups = os.path.isdir(backup_dir)
		text += "\n\nBackups of the old files:\n  " + backup_dir if has_backups else "\n\nNo existing files required a backup."
		footer = ttk.Frame(body)
		footer.pack(side="bottom", fill="x", pady=(8, 0))
		def copy_report():
			window.clipboard_clear()
			window.clipboard_append(text)
		for column, (label, command) in enumerate((("Copy summary", copy_report),
			("Open backups", lambda: os.startfile(backup_dir)), ("Close", window.destroy))):
			button = ttk.Button(footer, text=label, command=command, width=1)
			button.grid(row=0, column=column, sticky="ew", padx=2)
			footer.columnconfigure(column, weight=1, uniform="saved_buttons")
			if column == 1 and not has_backups:
				button.state(["disabled"])
		ttk.Label(body, text=("Backups: " + backup_dir) if has_backups else "No existing files required a backup.",
			style="Muted.TLabel", wraplength=ui.px(820)).pack(side="bottom", fill="x", pady=(8, 0))
		box = ttk.Frame(body)
		box.pack(fill="both", expand=True)
		tree = ttk.Treeview(box, columns=("mod", "action", "file"), show="headings", height=12)
		for key, label, width in (("mod", "Music mod", 230), ("action", "Change", 100), ("file", "File", 480)):
			tree.heading(key, text=label)
			tree.column(key, width=ui.px(width), minwidth=ui.px(80), stretch=key != "action")
		ys = ttk.Scrollbar(box, command=tree.yview)
		xs = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
		tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
		ys.pack(side="right", fill="y")
		xs.pack(side="bottom", fill="x")
		tree.pack(fill="both", expand=True)
		for row in report:
			tree.insert("", "end", values=row)
		ui.stripe(tree)
		ui.theme_all(window)
		ui.title_bar(window)
		return window

	def discard_all(self):
		mods = self.unsaved()
		if not mods or not messagebox.askyesno(APP_NAME, f"Throw away {sum(m.pending_count() for m in mods)} unsaved changes?"):
			return
		for m in mods:
			m.pending_text.clear()
			m.pending_files.clear()
			m.load()
		shutil.rmtree(STAGING, ignore_errors=True)
		self.after_change()
		self.status("Unsaved changes thrown away.")

	def after_change(self):
		"""Redraw after the mods changed (station kept)."""
		tok = self.station.token if self.station else None
		if self.mod and tok:
			self.station = self.mod.stations.get(tok)
		self.fill_stations()
		self.update_save()

	def close(self):
		"""Organisation Master closing: unsaved changes? (False = don't close)"""
		if getattr(self, "_music_pulling", False):
			messagebox.showinfo(APP_NAME, "A music repository is still updating. Please wait for it to finish before closing.", parent=self)
			return False
		if any(editor.busy for editor in getattr(self, "_audio_editors", ())):
			messagebox.showinfo(APP_NAME, "The track workshop is still working. Finish or cancel its operation before closing.", parent=self)
			return False
		self.flush_plan()
		self.player.stop()
		if self.unsaved():
			a = messagebox.askyesnocancel(APP_NAME, f"Music Master has {sum(m.pending_count() for m in self.unsaved())} unsaved "
													"changes. Save them to the music mods before closing?")
			if a is None:
				return False
			if a:
				return self.save_all()
		return True

		# ---------- mods ----------
	def open_target(self, target):
		"""Select a linked plan or station without reloading staged music edits."""
		self.flush_plan()
		if target["kind"] == "plan":
			plan = next((p for p in self.plans if p.get("id") == target["value"]), None)
			if plan is None:
				messagebox.showinfo(APP_NAME, "That planned station is no longer available.", parent=self)
				return False
			folder = plan.get("mod") or ""
		else:
			plan = None
			folder = target.get("mod") or ""
		label = next((name for name, root in self._mods.items() if root and os.path.basename(root).casefold() == folder.casefold()), None)
		if label:
			folder = os.path.basename(self._mods[label])
			self.mod_var.set(label)
			self.open_view(label)
		elif not plan:
			messagebox.showinfo(APP_NAME, "The linked music mod could not be found. Check that it is installed next to RR.", parent=self)
			return False
		if plan:
			self.fill_plans()
			iid = str(self.plans.index(plan))
			if not self.plan_tree.exists(iid):
				return False
			self.plan_tree.selection_set(iid)
			self.plan_tree.see(iid)
			self.sec_plans.toggle(False)
			self.show_plan()
		else:
			iid = next((row for row in self.st_tree.get_children() if row.split("|", 1) == [folder, target["value"]]), None)
			if iid is None:
				messagebox.showinfo(APP_NAME, "That radio station is no longer available in the linked music mod.", parent=self)
				return False
			self.st_tree.selection_set(iid)
			self.st_tree.see(iid)
			self.sec_stations.toggle(False)
			self.show_station()
		self.status("Opened linked " + ("planned station" if plan else "radio station") + ".")
		return True

	def get_mod(self, root, reload=False):
		key = os.path.normcase(os.path.abspath(root))
		if key not in self._loaded:
			self._loaded[key] = MusicMod(root)
		elif reload:
			self._loaded[key].load()  # (from the files + the unsaved changes)
		return self._loaded[key]

	def rr_mods(self):
		return [r for r in self._roots if is_rr_music(r, self._names.get(r, ""))]

	@staticmethod
	def _key(mod_or_folder):
		return os.path.basename(mod_or_folder.root) if isinstance(mod_or_folder, MusicMod) else (mod_or_folder or "")

	def mod_colour(self, mod_or_folder):
		"""A music mod's colour: the one picked for it, else by its place among the RR music mods."""
		key = self._key(mod_or_folder)
		if self.mod_meta.get(key, {}).get("colour"):
			return self.mod_meta[key]["colour"]
		folders = [os.path.basename(r) for r in self.rr_mods()] or [key]
		i = folders.index(key) if key in folders else len(folders)
		return MOD_COLOURS[i % len(MOD_COLOURS)]

	def colour_tag(self, tree, mod_or_folder):
		c = self.mod_colour(mod_or_folder)
		tag = "c" + c.lstrip("#")
		tree.tag_configure(tag, foreground=c)
		return tag

	def short_name(self, mod_or_folder):
		"""What a music mod is called in the lists: its own short name, else its name without "Revolution Realised Music: "."""
		key = self._key(mod_or_folder)
		if self.mod_meta.get(key, {}).get("name"):
			return self.mod_meta[key]["name"]
		root = next((r for r in getattr(self, "_roots", []) if os.path.basename(r) == key), None)
		name = self._names.get(root, key) if root else key
		return re.sub(r"^revolution reali[sz]ed music\s*[:\-]\s*", "", name, flags=re.I) or name

	def mod_exists(self, key):
		return any(os.path.basename(r) == key for r in getattr(self, "_roots", []))

	def fill_mods(self):
		self._roots = find_music_mods(self.app.mod_dir)
		self._names = {}
		for r in self._roots:
			try:
				self._names[r] = music_mod_name(r)
			except Exception:
				self._names[r] = os.path.basename(r)
		rr = self.rr_mods()
		self._mods = {}
		if rr or getattr(self, "catalog", {}):
			self._mods[ALL_RR] = None
		for r in rr + [r for r in self._roots if r not in rr]:
			self._mods[("" if r in rr else "Other: ") + f"{self.short_name(os.path.basename(r)) if r in rr else self._names[r]}  ({os.path.basename(r)})"] = r
		self.mod_box.config(values=list(self._mods))
		last = self.app.config.get("music_view") or self.app.config.get("music_mod")
		pick = last if last in self._mods else next((k for k, v in self._mods.items() if v and last and
													 os.path.normcase(os.path.abspath(v)) == os.path.normcase(os.path.abspath(last))),
													next(iter(self._mods), None))
		if pick:
			self.mod_var.set(pick)
			self.open_view(pick)
		else:
			self.mod_info.config(text="No music mod in the mod folder yet: make one with New music mod...")
			self.fill_stations()
			self.fill_plans()

	def open_view(self, label, reload=False):
		"""Shows one music mod, or every RR music mod at once (colour coded)."""
		if label not in getattr(self, "_mods", {}):
			return
		roots = self.rr_mods() if label == ALL_RR else [self._mods[label]]
		try:
			self.view_mods = [self.get_mod(r, reload) for r in roots]
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't read a music mod:\n{ex}")
			return
		self.mod = self.view_mods[0] if self.view_mods else None
		self.app.config["music_view"] = label
		self.app.save_config()
		for w in self.legend.winfo_children():
			w.destroy()
		if label == ALL_RR:
			n = sum(len(m.stations) for m in self.view_mods)
			self.mod_info.config(text=f"{len(self.view_mods)} RR music mods, {n} stations:")
			for m in self.view_mods:
				tk.Label(self.legend, text=f"■ {self.short_name(m)} ({len(m.stations)})", fg=self.mod_colour(m),
						 font="om_small_bold").pack(side="left", padx=(0, 12))
		else:
			m = self.mod
			n = sum(len(s.songs) for s in m.stations.values())
			self.mod_info.config(text=f"{m.root}  -  {len(m.stations)} stations, {n} station songs, {len(m.songs)} songs in "
									  f"{', '.join(m.asset_files) or 'no .asset file'}")
		self.station = None
		self.fill_stations()
		self.fill_plans()
		self.update_save()
		self.status(f"Showing {label}.")

	def open_mod(self, root):
		"""Shows this one music mod (after it was made or changed)."""
		self.get_mod(root, reload=True)
		label = next((k for k, v in self._mods.items() if v and os.path.normcase(os.path.abspath(v)) == os.path.normcase(os.path.abspath(root))), None)
		if label:
			self.mod_var.set(label)
			self.open_view(label)

	def new_mod(self, planned=None):
		"""A new music mod in the mod folder: descriptor, launcher .mod file, and empty asset / interface / names files."""
		self._adopt = planned
		w = tk.Toplevel(self)
		w.title("New music mod")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		v = {k: tk.StringVar() for k in ("name", "folder", "prefix", "version", "active")}
		v["version"].set(self.app.game_version())
		if planned:
			v["name"].set("Revolution Realised Music: " + self.short_name(planned))
		typed = set()
		rows = (("name", "Name (in the launcher):"), ("folder", "Folder:"), ("prefix", "File prefix:"), ("version", "Supported version:"),
				("active", "Main menu line (optional):"))
		for r, (k, text) in enumerate(rows):
			ttk.Label(f, text=text).grid(row=r, column=0, sticky="w", pady=2)
			e = ttk.Entry(f, textvariable=v[k], width=50)
			e.grid(row=r, column=1, sticky="we")
			e.bind("<Key>", lambda ev, k=k: typed.add(k))

		def follow(*_):
			n = v["name"].get().strip()
			if "folder" not in typed:
				v["folder"].set(re.sub(r"[^A-Za-z0-9_\-]+", "_", n).strip("_"))
			if "prefix" not in typed:
				v["prefix"].set("RR_" + "".join(x[0] for x in re.findall(r"[A-Za-z0-9]+", n.replace("Revolution Realised", "").replace("Music", ""))).upper()[:4])
			if "active" not in typed:
				v["active"].set(f"§t {n}§! is active." if n else "")
		v["name"].trace_add("write", follow)
		thumb = {"path": None}
		tl = ttk.Label(f, text="no thumbnail", foreground="#777")

		def pick_thumb():
			pth = filedialog.askopenfilename(parent=w, filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")])
			if pth:
				thumb["path"] = pth
				tl.config(text=os.path.basename(pth))
		ttk.Button(f, text="Thumbnail...", command=pick_thumb).grid(row=len(rows), column=0, sticky="w", pady=4)
		tl.grid(row=len(rows), column=1, sticky="w")
		ttk.Label(f, text="Makes the folder with descriptor.mod, the launcher's <folder>.mod, music/<prefix>_music.asset, "
						  "interface/<prefix>_musicplayer.gfx and <prefix>_music_stations.gui, and the names file. The main menu "
						  "line goes in localisation/english/replace (shown when the mod is on).",
				  foreground="#777", wraplength=430, justify="left").grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w")

		def ok():
			name, folder, prefix = v["name"].get().strip(), v["folder"].get().strip(), v["prefix"].get().strip()
			if not name or not re.fullmatch(r"[A-Za-z0-9_\-]+", folder) or not re.fullmatch(r"[A-Za-z0-9_]+", prefix):
				messagebox.showerror(APP_NAME, "Give it a name, a folder (letters, numbers, _ -) and a prefix.", parent=w)
				return
			root = os.path.join(self.app.mod_dir, folder)
			if os.path.exists(root) or os.path.exists(root + ".mod"):
				messagebox.showerror(APP_NAME, f"{folder} already exists in the mod folder.", parent=w)
				return
			w.destroy()
			self.create_mod(root, name, prefix, v["version"].get().strip() or "1.13.*", v["active"].get().strip(), thumb["path"])
		bf = ttk.Frame(f)
		bf.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="Create", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def create_mod(self, root, name, prefix, version, active, thumb):
		folder = os.path.basename(root)
		os.makedirs(os.path.join(root, "music"))
		desc = [f'version="{version}"', "tags={", '\t"Sound"', "}", f'name="{name}"', f'supported_version="{version}"']
		if thumb:
			Image.open(thumb).convert("RGB").resize((256, 256)).save(os.path.join(root, "thumbnail.png"))
			desc.append('picture="thumbnail.png"')

		def put(rel, text, bom=False):
			p = os.path.join(root, rel)
			os.makedirs(os.path.dirname(p), exist_ok=True)
			with open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\r\n") as fh:
				fh.write(text)
		put("descriptor.mod", "\n".join(desc) + "\n")
		launcher = desc + [f'path="{root.replace(os.sep, "/")}"']
		with open(root + ".mod", "w", encoding="utf-8", newline="\r\n") as fh:
			fh.write("\n".join(launcher) + "\n")
		put(f"music/{prefix}_music.asset", f"# Songs of {name} (made by Organisation Master > Music Master)\n")
		put(f"interface/{prefix}_musicplayer.gfx", "spriteTypes = {\n}\n")
		put(f"interface/{prefix}_music_stations.gui", "guiTypes = {\n}\n")
		put(f"localisation/{prefix}_music_l_english.yml", "l_english:\n\n  ##### Radio Stations #####\n", bom=True)
		if active:
			put(f"localisation/english/replace/{prefix}_addons_l_english.yml",
				f'l_english:\n {prefix}_active:0 "{active}"\n', bom=True)
		self.app.log(f"new music mod {folder}")
		self.adopt_planned(folder, name)
		self.fill_mods()
		self.open_mod(root)
		self.status(f"Made {name} in {root} (and {folder}.mod for the launcher). Add a station next.")

	# ---------- stations ----------
	def duration(self, path, background=False):
		if not path:
			return None
		try:
			key = (path, os.path.getmtime(path))
		except OSError:
			self._duration_keys.pop(path, None)
			return None
		self._duration_keys[path] = key
		if key not in self._dur:
			if background:
				if key not in self._duration_pending and not self._duration_stop.is_set():
					self._duration_pending.add(key)
					self._duration_requests.put(key)
					self._start_duration_workers()
				return None
			self._dur[key] = ogg_info(path)[0]
		return self._dur[key]

	def _start_duration_workers(self):
		if not self._duration_workers:
			def work():
				while not self._duration_stop.is_set():
					try:
						key = self._duration_requests.get(timeout=0.2)
					except queue.Empty:
						continue
					try:
						secs = ogg_info(key[0])[0]
					except Exception:
						secs = None
					self._duration_results.put((key, secs))
			for _ in range(2):
				thread = threading.Thread(target=work, daemon=True)
				self._duration_workers.append(thread)
				thread.start()
		if self._duration_job is None:
			self._duration_job = self.after(100, self._poll_durations)

	def _poll_durations(self):
		self._duration_job = None
		changed = False
		while True:
			try:
				key, secs = self._duration_results.get_nowait()
			except queue.Empty:
				break
			self._duration_pending.discard(key)
			self._dur[key] = secs
			changed = True
		if changed:
			self._refresh_duration_labels()
		if self._duration_pending and self._duration_job is None and not self._duration_stop.is_set():
			self._duration_job = self.after(100, self._poll_durations)

	def _length_pending(self, path):
		return self._duration_keys.get(path) in self._duration_pending

	def _cached_length(self, path):
		key = self._duration_keys.get(path)
		return self._dur.get(key), key in self._duration_pending

	def _refresh_duration_labels(self):
		# Update cells in place: keep selection, sorting, scroll and playback untouched.
		for mod in self.view_mods:
			for token, station in mod.stations.items():
				secs, pending, bad = 0, False, not station.title or not station.art
				iid = f"{os.path.basename(mod.root)}|{token}"
				for path in self._station_duration_paths.get(iid, []):
					length, waiting = self._cached_length(path)
					secs += length or 0
					pending |= waiting
					bad |= length is None and not waiting
				iid = f"{os.path.basename(mod.root)}|{token}"
				if self.st_tree.exists(iid):
					self.st_tree.set(iid, "time", "…" if pending else f"{int(secs // 3600)}h {int(secs % 3600 // 60):02d}m" if secs else "")
					self.st_tree.item(iid, text=("⚠ " if bad else "") + (station.title or token))
		if not self.station:
			return
		total, pending = 0, False
		paths = self._station_duration_paths.get(f"{os.path.basename(self.mod.root)}|{self.station.token}", [])
		for i, (name, _, _) in enumerate(self.station.songs):
			path = paths[i] if i < len(paths) else None
			length, waiting = self._cached_length(path)
			total += length or 0
			pending |= waiting
			if not self.song_tree.exists(str(i)):
				continue
			self.song_tree.set(str(i), "time", "…" if waiting else mmss(length))
			problem = length is None and not waiting
			playing = self._play_row == (self.mod.root, self.station.token, name)
			tags = tuple(tag for tag in self.song_tree.item(str(i), "tags") if tag not in ("problem", "playing"))
			self.song_tree.item(str(i), image=self.img_stop if playing else self.img_play_off if problem else self.img_play,
				tags=tags + (("problem",) if problem else ("playing",) if playing else ()))
		self.sec_songs.set_count(f"{len(self.station.songs)} songs, {int(total // 60)} min" + (" · reading lengths…" if pending else ""))
		credit = self.st_info.cget("text").partition("\n")[2]
		self.st_info.config(text=f"{self.short_name(self.mod)}  -  {len(self.station.songs)} songs, {int(total // 60)} min  -  {self.station.rel}  -  folder music/{self.station.token}/"
			+ (f"\n{credit}" if credit else ""))

	def _destroy_metadata(self, event):
		if event.widget is not self:
			return
		self._duration_stop.set()
		if self._duration_job is not None:
			self.after_cancel(self._duration_job)
			self._duration_job = None

	def fill_stations(self):
		self._station_duration_paths = {}
		t = self.st_tree
		t.delete(*t.get_children())
		many = len(self.view_mods) > 1
		keep = (os.path.basename(self.mod.root), self.station.token) if self.station and self.mod else None
		for mod in self.view_mods:
			folder = os.path.basename(mod.root)
			for token, st in sorted(mod.stations.items(), key=lambda x: (x[1].title or x[0]).lower()):
				secs, bad, pending = 0, False, False
				paths = self._station_duration_paths[f"{folder}|{token}"] = []
				for n, _, _ in st.songs:
					song = mod.songs.get(n)
					p = mod.song_path(song)
					paths.append(p)
					d = self.duration(p, background=True) if song else None
					if d is None and not self._length_pending(p):
						bad = True
					secs += d or 0
					pending |= self._length_pending(p)
				bad = bad or not st.title or not st.art
				t.insert("", "end", iid=f"{folder}|{token}", text=("⚠ " if bad else "") + (st.title or token),
						 values=(len(st.songs), "…" if pending else f"{int(secs // 3600)}h {int(secs % 3600 // 60):02d}m" if secs else ""),
						 tags=(self.colour_tag(t, mod),) if many or is_rr_music(mod.root, mod.name) else ())
		if hasattr(self, "_music_base"):
			self.fill_missing_stations()
		ui.stripe(t)
		self.sec_stations.set_count(f"{len(t.get_children())}")
		self.update_gaps()
		if keep and t.exists("|".join(keep)):
			t.selection_set("|".join(keep))
		elif t.get_children():
			t.selection_set(t.get_children()[0])
		else:
			self.station = None
			self.show_station()

	def show_pane(self, which):
		new, old = (self.plan_pane, self.station_pane) if which == "plan" else (self.station_pane, self.plan_pane)
		if not new.winfo_ismapped():
			old.pack_forget()
			new.pack(fill="both", expand=True)

	def click_station(self, event):
		row = self.st_tree.identify_row(event.y)
		if row and self.st_tree.identify_region(event.x, event.y) in ("tree", "cell") and row in self.st_tree.selection():
			self.show_station()
			getattr(self.app, "feedback", lambda *_: None)("select")

	def show_station(self):
		if hasattr(self, "song_drag"):
			self.song_drag.cancel()
		self.show_pane("station")
		sel = self.st_tree.selection()
		st = None
		missing = getattr(self, "_missing_music", {}).get(sel[0]) if sel else None
		if missing:
			self.station = None
			self.fill_station_queue()
			self.song_tree.delete(*self.song_tree.get_children())
			self.st_title.config(text=missing["title"] + " — not downloaded", foreground=ui.P["muted"])
			self.st_info.config(text="This station is available from another developer.\n"
				"Use Pull station updates, or Get missing music mods if its mod is not installed.")
			self.art_label.config(image="", text="Not downloaded", width=20, height=6)
			return
		if sel and "|" in sel[0]:
			folder, token = sel[0].split("|", 1)
			mod = next((m for m in self.view_mods if os.path.basename(m.root) == folder), None)
			if mod:
				self.mod = mod  # songs / station tools work on the station's own mod
				st = mod.stations.get(token)
		self.station = st
		self.fill_station_queue()
		self.song_tree.delete(*self.song_tree.get_children())
		if st is None:
			self.st_title.config(text="Pick a station" if any(m.stations for m in self.view_mods) else "No stations yet")
			self.st_info.config(text="")
			self.art_label.config(image="", text="(no album art)", width=20, height=6)
			return
		self.st_title.config(text=f"{st.title or '(no name)'}  ({st.token})", foreground=self.mod_colour(self.mod))
		img = None
		if st.art and os.path.exists(st.art):
			try:
				im = Image.open(st.art).convert("RGBA").crop((0, 0, ART_SIZE[0] // 2, ART_SIZE[1]))
				img = ImageTk.PhotoImage(im)
			except Exception:
				img = None
		self._photos = [img] if img else []
		self.art_label.config(image=img or "", text="" if img else "(no album art)", width=152 if img else 20, height=120 if img else 6)
		total = 0
		for i, (n, factor, e) in enumerate(st.songs):
			song = self.mod.songs.get(n)
			p = self.mod.song_path(song)
			secs = self.duration(p, background=True) if song else None
			total += secs or 0
			problem = not song or not p or (secs is None and not self._length_pending(p))
			playing = self._play_row == (self.mod.root, st.token, n)
			title, artist = split_artist(n)
			self.song_tree.insert("", "end", iid=str(i), text=" " + title, values=(artist, "…" if self._length_pending(p) else mmss(secs), song.volume if song else "", factor,
																		 (song.file if song else "(no music = { } in the .asset)") + ("" if not song or p else "  (missing)")),
								  image=self.img_stop if playing else self.img_play_off if problem else self.img_play,
								  tags=("problem",) if problem else ("playing",) if playing else ())
		ui.stripe(self.song_tree)
		self.sec_songs.set_count(f"{len(st.songs)} songs, {int(total // 60)} min")
		self.st_info.config(text=f"{self.short_name(self.mod)}  -  {len(st.songs)} songs, {int(total // 60)} min  -  {st.rel}  -  folder music/{st.token}/"
								 + (f"\n{self.station_added(self.mod, st.rel)}" if self.station_added(self.mod, st.rel) else ""))

	def set_song_sort(self, key, flip=False, refill=True):
		"""The song list's order: Sort by (or a click on a column title); Order in the file = as the station file has them."""
		if flip:
			self._song_rev = not self._song_rev
		self.song_sort.set(key)
		self.app.config["music_song_sort"] = key
		self.app.config["music_song_rev"] = self._song_rev
		self.app.save_config()
		self.song_dir.config(text="▼" if self._song_rev else "▲")
		self.song_dir.state(["disabled"] if key == SONG_SORTS[0] else ["!disabled"])
		if hasattr(self, "song_drag"):
			self.song_drag.cancel()
		col = SONG_SORT_COLS.get(key)
		self.song_tree._sort = (col, self._song_rev) if col else None
		if refill and self.station:
			self.show_station()

	def song_sorted(self, col, rev):
		"""A click on a column title of the song list: the Sort by box follows."""
		key = next((k for k, c in SONG_SORT_COLS.items() if c == col), None)
		self._song_rev = rev
		if key:
			self.song_dir.state(["!disabled"])
			if hasattr(self, "song_drag"):
				self.song_drag.cancel()
			self.song_sort.set(key)
			self.song_dir.config(text="▼" if rev else "▲")
			self.app.config["music_song_sort"], self.app.config["music_song_rev"] = key, rev
			self.app.save_config()

	def song_double(self, ev):
		t = self.song_tree
		row = t.identify_row(ev.y)
		if not row or self.on_play_icon(t, ev):
			return
		if t.identify_column(ev.x) == "#5":  # the File column: point the song at another file
			t.selection_set(row)
			self.relink_song()
		else:
			self.edit_song()

	def pick_song_file(self, parent, st):
		"""An .ogg for a song: its path under music/ (one from outside the mod is copied into music/<station>/ on Save)."""
		m = self.mod
		p = filedialog.askopenfilename(parent=parent, title="The song's file (.ogg)", initialdir=m.path(f"music/{st.token}") if st else m.path("music"),
									   filetypes=[("Ogg Vorbis", "*.ogg"), ("All files", "*.*")])
		if not p:
			return None
		music = os.path.normcase(os.path.abspath(m.path("music")))
		full = os.path.normcase(os.path.abspath(p))
		if full.startswith(music + os.sep):
			return os.path.relpath(p, m.path("music")).replace("\\", "/")
		fn = slug(os.path.splitext(os.path.basename(p))[0]) + ".ogg"
		rel = f"{st.token}/{fn}"
		k = 2
		while m.exists("music/" + rel):
			rel = f"{st.token}/{slug(os.path.splitext(os.path.basename(p))[0])}_{k}.ogg"
			k += 1
		self.stage_file("music/" + rel, p)
		return rel

	def set_song_file(self, song, rel):
		"""Writes a song's new file = "..." in its .asset entry."""
		lines = self.lines(song.rel)
		for k in range(song.entry.first, song.entry.last + 1):
			lines[k] = re.sub(r'(\bfile\s*=\s*)"[^"]*"', lambda mm: mm.group(1) + f'"{rel}"', lines[k])
		self.write(song.rel, lines)

	def relink_song(self):
		sel = self.selected_songs()
		if len(sel) != 1:
			return
		song = self.mod.songs.get(sel[0][0])
		if not song:
			messagebox.showinfo(APP_NAME, "This song has no music = { } in the .asset files: add it with Add songs.")
			return
		rel = self.pick_song_file(self, self.station)
		if rel and rel != song.file:
			self.set_song_file(song, rel)
			self.mod.load()
			self.after_change()
			self.status(f"'{song.name}' now plays music/{rel} (not saved yet: Save to mod).")

	def station_added(self, mod, rel):
		"""git: who added the station's file to its music mod ('added by NAME on DATE')."""
		key = (mod.root, rel)
		if key not in self._blame:
			out = git(mod.root, "log", "--diff-filter=A", "--follow", "--format=%an|%ad", "--date=short", "--", rel).strip().splitlines()
			if out:
				who, _, when = out[-1].partition("|")
				self._blame[key] = f"added by {who} on {when}"
			else:
				self._blame[key] = "not committed yet" if git(mod.root, "rev-parse", "--git-dir") else ""
		return self._blame[key]

	def selected_songs(self):
		return [self.station.songs[int(i)] for i in self.song_tree.selection()] if self.station else []

	def asset_file_for(self, st):
		"""The .asset file this station's songs are in (else the mod's first / a new one)."""
		for n, _, _ in st.songs:
			if n in self.mod.songs:
				return self.mod.songs[n].rel
		return self.mod.asset_files[0] if self.mod.asset_files else "music/music.asset"

	def new_station(self, plan=None):
		if not self.mod:
			return
		rr = self.rr_mods() or [self.mod.root]
		folders = [os.path.basename(r) for r in rr]
		want = (plan or {}).get("mod") or os.path.basename(self.mod.root)
		w = tk.Toplevel(self)
		w.title("New radio station")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		title = tk.StringVar(value=(plan or {}).get("title", ""))
		token = tk.StringVar(value=(plan or {}).get("token", "") or slug(title.get()))
		typed = {"t": bool(plan and plan.get("token"))}
		ttk.Label(f, text="Name:").grid(row=0, column=0, sticky="w", pady=2)
		ttk.Entry(f, textvariable=title, width=40).grid(row=0, column=1, sticky="we")
		ttk.Label(f, text="Token:").grid(row=1, column=0, sticky="w", pady=2)
		te = ttk.Entry(f, textvariable=token, width=40)
		te.grid(row=1, column=1, sticky="we")
		te.bind("<Key>", lambda ev: typed.update(t=True))
		title.trace_add("write", lambda *_: typed["t"] or token.set(slug(title.get())))
		logo = self.plan_logo_path(plan)
		art = {"path": logo if logo and os.path.exists(logo) else None}
		al = ttk.Label(f, text=f"the plan's logo ({os.path.basename(logo)})" if art["path"] else "no album art yet", foreground="#777")

		def pick_art():
			p = filedialog.askopenfilename(parent=w, filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.dds *.tga"), ("All files", "*.*")])
			if p:
				art["path"] = p
				al.config(text=os.path.basename(p))
		ttk.Button(f, text="Album art...", command=pick_art).grid(row=2, column=0, sticky="w", pady=4)
		al.grid(row=2, column=1, sticky="w")
		modv = tk.StringVar(value=want if want in folders else (folders[0] if folders else ""))
		ttk.Label(f, text="Music mod:").grid(row=5, column=0, sticky="w", pady=2)
		ttk.Combobox(f, textvariable=modv, values=folders, state="readonly", width=38).grid(row=5, column=1, sticky="we")
		ttk.Label(f, text="Writes music/<token>.txt and the music/<token>/ folder, <token>_TITLE, GFX_<token>_album_art "
						  "(304x120: the picture as the normal and the picked button) and the player / station button windows "
						  "in the .gui (a copy of another station's).", foreground="#777", wraplength=380,
				  justify="left").grid(row=3, column=0, columnspan=2, sticky="w")

		def ok():
			tok, name = token.get().strip(), title.get().strip()
			if not name or not re.fullmatch(r"[a-z][a-z0-9_]*", tok):
				messagebox.showerror(APP_NAME, "Give it a name and a token (a-z, 0-9, _).", parent=w)
				return
			target = self.get_mod(rr[folders.index(modv.get())]) if modv.get() in folders else self.mod
			if tok in target.stations or target.exists(f"music/{tok}.txt"):
				messagebox.showerror(APP_NAME, f"{tok} already exists in {target.name}.", parent=w)
				return
			w.destroy()
			self.mod = target
			self.create_station(tok, name, art["path"])
			if plan is not None:
				plan["status"] = "Made"
				plan["token"] = tok
				plan["mod"] = os.path.basename(target.root)
				self.save_plans()
				self.fill_plans()
		bf = ttk.Frame(f)
		bf.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="Create", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def create_station(self, tok, name, art_src):
		m = self.mod
		self.write(f"music/{tok}.txt", ["", f'music_station = "{tok}"', ""])
		# name
		loc = next((f for f in m.loc_files if "replace" not in f), None) or "localisation/music_l_english.yml"
		lines = self.lines(loc) or ["l_english:", "", "  ##### Radio Stations #####"]
		hits = [i for i, l in enumerate(lines) if re.match(r"^\s*\w+_TITLE:", l)]
		at = hits[-1] + 1 if hits else len(lines)
		indent = re.match(r"\s*", lines[hits[-1]]).group(0) if hits else "  "
		lines.insert(at, f'{indent}{tok}_TITLE:0 "{name}"')
		self.write(loc, lines)
		# album art + sprite
		gfx = m.gfx_files[0] if m.gfx_files else "interface/music_musicplayer.gfx"
		tex = f"gfx/interface/topbar/musicplayer/RR_{tok}_bg.dds"
		if art_src:
			self.stage_art(art_src, tex, m)
		lines = self.lines(gfx) or ["spriteTypes = {", "}"]
		close = max(i for i, l in enumerate(lines) if l.strip().startswith("}"))
		lines[close:close] = ["\tspriteType = {", f'\t\tname = "GFX_{tok}_album_art"', f'\t\ttexturefile = "{tex}"', "\t\tnoOfFrames = 2", "\t}"]
		self.write(gfx, lines)
		# player + station button: a copy of another station's windows (this mod's, else the template)
		gui = m.gui_files[0] if m.gui_files else "interface/music_stations.gui"
		block = self.station_gui(tok)
		lines = self.lines(gui) or ["guiTypes = {", "}"]
		close = max(i for i, l in enumerate(lines) if l.strip().startswith("}"))
		lines[close:close] = ["", f"\t## {name}"] + block
		self.write(gui, lines)
		m.load()
		if m not in self.view_mods:
			self.view_mods.append(m)
		self.station = m.stations.get(tok)
		self.fill_stations()
		self.status(f"Made station {name} ({tok}) in {m.name}. Add its songs with Add songs...")

	def station_gui(self, tok):
		"""<tok>_faceplate and <tok>_stations_entry, copied from a station of this mod (or of another music mod)."""
		for mod in [self.mod] + [MusicMod(r) for r in find_music_mods(self.app.mod_dir) if r != self.mod.root]:
			for rel in mod.gui_files:
				lines = mod.text_lines(rel)
				for old in mod.stations:
					a = next((i for i, l in enumerate(lines) if re.search(rf'name\s*=\s*"{old}_faceplate"', l)), None)
					b = next((i for i, l in enumerate(lines) if re.search(rf'name\s*=\s*"{old}_stations_entry"', l)), None)
					if a is None or b is None:
						continue
					out = []
					for start in (a, b):
						s0 = start
						while s0 > 0 and "containerWindowType" not in lines[s0]:
							s0 -= 1
						depth, k = 0, s0
						while k < len(lines):
							depth += lines[k].count("{") - lines[k].count("}")
							if depth <= 0 and k > s0:
								break
							k += 1
						out += [l.replace(f"{old}_", f"{tok}_") for l in lines[s0:k + 1]] + [""]
					return out
		raise RuntimeError("No station window to copy (no music mod has a <station>_faceplate in its .gui yet).")

	def rename_station(self):
		st = self.station
		if not st:
			return
		name = simpledialog.askstring(APP_NAME, "Station name:", initialvalue=st.title or "", parent=self)
		if not name:
			return
		for rel in self.mod.loc_files:
			lines = self.lines(rel)
			for i, l in enumerate(lines):
				m = re.match(rf'^(\s*{st.token}_TITLE:\d*\s*")(.*)("[^"]*)$', l)
				if m:
					lines[i] = m.group(1) + name + m.group(3)
					self.write(rel, lines)
					self.mod.load()
					self.fill_stations()
					return
		self.status("Its _TITLE line wasn't found.")

	def change_art(self):
		st = self.station
		if not st:
			return
		p = filedialog.askopenfilename(parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.dds *.tga"), ("All files", "*.*")])
		if not p:
			return
		if getattr(st, "art_rel", None):
			self.stage_art(p, st.art_rel)
		else:  # no sprite yet
			tex = f"gfx/interface/topbar/musicplayer/RR_{st.token}_bg.dds"
			self.stage_art(p, tex)
			gfx = self.mod.gfx_files[0] if self.mod.gfx_files else "interface/music_musicplayer.gfx"
			lines = self.lines(gfx) or ["spriteTypes = {", "}"]
			close = max(i for i, l in enumerate(lines) if l.strip().startswith("}"))
			lines[close:close] = ["\tspriteType = {", f'\t\tname = "GFX_{st.token}_album_art"', f'\t\ttexturefile = "{tex}"', "\t\tnoOfFrames = 2", "\t}"]
			self.write(gfx, lines)
		self.mod.load()
		self.fill_stations()

	# ---------- songs ----------
	def balanced_buttons(self, parent, actions, columns=3):
		frame = ttk.Frame(parent)
		frame.pack(fill="x", pady=(4, 0))
		for index, (text, command) in enumerate(actions):
			button = ttk.Button(frame, text=text, command=command, width=1)
			button.grid(row=index // columns, column=index % columns, sticky="ew", padx=2, pady=2)
		for column in range(columns):
			frame.columnconfigure(column, weight=1, uniform="song_actions")
		return frame

	def station_plan(self, create=False):
		if not self.station or not self.mod:
			return None
		folder, token = os.path.basename(self.mod.root), self.station.token
		plan = next((plan for plan in self.plans if plan.get("mod") == folder and plan.get("token") == token), None)
		if plan is None and create:
			plan = dict(title=self.station.title or token, mod=folder, token=token, status="Made",
				songs=[], notes="", added_by=git_user(), added=today())
			self.plans.append(plan)
			self.save_plans()
			self.fill_plans()
		return plan

	def fill_station_queue(self):
		if not hasattr(self, "station_queue"):
			return
		tree = self.station_queue
		tree.delete(*tree.get_children())
		plan = self.station_plan()
		if plan:
			existing = {norm_song(name) for name, _, _ in self.station.songs}
			for index, song in enumerate(plan.get("songs", [])):
				if song.get("in_game") or norm_song(join_artist(song.get("title", ""), song.get("artist", ""))) in existing:
					continue
				tree.insert("", "end", iid=str(index), text=song.get("title", ""), values=(song.get("artist", ""), song.get("link", "")))
		ui.stripe(tree)
		self.station_queue_sec.set_count(str(len(tree.get_children())))

	def plan_station_song(self):
		if not self.station:
			messagebox.showinfo(APP_NAME, "Pick an existing radio station first.", parent=self)
			return
		self.plan_edit_song(new=True, plan=self.station_plan(create=True))

	def edit_station_queue(self):
		selected = self.station_queue.selection()
		plan = self.station_plan()
		if plan and selected:
			self.plan_edit_song(plan=plan, song_index=int(selected[0]))

	def audio_workshop(self, planned=False, edit=False, station_queue=False):
		from audio_editor import AudioEditor
		for editor in getattr(self, "_audio_editors", ()):
			editor.lift()
			editor.focus_set()
			return
		tracks, replacement, hint = [], None, None
		if planned or station_queue:
			self.flush_plan()
			plan = self.station_plan() if station_queue else self.cur_plan
			if plan is None:
				messagebox.showinfo(APP_NAME, "Pick a planned station first.", parent=self)
				return
			rows = ([int(row) for row in self.station_queue.selection()] or [int(row) for row in self.station_queue.get_children()]) if station_queue else (self._plan_song_rows() or list(range(len(plan.get("songs", [])))))
			tracks = [dict(plan_song(plan["songs"][index])) for index in rows]
			hint = (plan.get("mod", ""), plan.get("token", ""))
		elif edit:
			selected = self.selected_songs()
			if len(selected) != 1:
				messagebox.showinfo(APP_NAME, "Select one station song to trim or adjust.", parent=self)
				return
			name = selected[0][0]
			song = self.mod.songs.get(name)
			source = self.mod.song_path(song)
			if not source:
				messagebox.showinfo(APP_NAME, "This song's audio file is missing. Download or relink it first.", parent=self)
				return
			title, artist = split_artist(name)
			tracks = [dict(title=title, artist=artist, audio_path=source, volume=song.volume)]
			replacement = (self.mod, self.station.token, "music/" + song.file, name)
		elif self.station:
			plan = self.station_plan()
			if plan:
				tracks = [dict(plan_song(plan["songs"][int(row)])) for row in self.station_queue.get_children()]
			hint = (os.path.basename(self.mod.root), self.station.token)
		AudioEditor(self, tracks, replacement=replacement, target_hint=hint)

	def add_songs(self):
		st = self.station
		if not st:
			messagebox.showinfo(APP_NAME, "Pick (or make) a station first.")
			return
		files = filedialog.askopenfilenames(parent=self, title="Songs (.ogg)", filetypes=[("Ogg Vorbis", "*.ogg"), ("All files", "*.*")])
		if not files:
			return
		bad = [f for f in files if not f.lower().endswith(".ogg") or ogg_info(f)[0] is None]
		if bad:
			messagebox.showerror(APP_NAME, "Only Ogg Vorbis files can be added (HOI4 plays nothing else):\n" + "\n".join(os.path.basename(b) for b in bad[:10])
								 + "\n\nConvert them first (Audacity: Export > Ogg Vorbis).")
			files = [f for f in files if f not in bad]
			if not files:
				return
		# One row per file: its name (Title - Artist from its tags, else the file name), volume and chance.
		w = tk.Toplevel(self)
		w.title(f"Add songs to {st.title or st.token}")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="Song  /  Artist  (in game: Song - Artist)").grid(row=0, column=0, sticky="w")
		ttk.Label(f, text="Volume (double-click the number to type it)").grid(row=0, column=1)
		ttk.Label(f, text="Chance (factor)").grid(row=0, column=2)
		ttk.Label(f, text="Length").grid(row=0, column=3)
		rows = []
		for r, src in enumerate(files, start=1):
			secs, tags = ogg_info(src)
			guess = (f"{tags['TITLE']} - {tags['ARTIST']}" if tags.get("TITLE") and tags.get("ARTIST") else tags.get("TITLE")) or \
				os.path.splitext(os.path.basename(src))[0].replace("_", " ")
			nv, vv, cv = tk.StringVar(value=guess), tk.StringVar(value=str(DEFAULT_VOLUME)), tk.StringVar(value="1")
			g0, g1 = split_artist(guess)
			tv_, av_ = tk.StringVar(value=g0), tk.StringVar(value=g1)
			tv_.trace_add("write", lambda *_, nv=nv, tv_=tv_, av_=av_: nv.set(join_artist(tv_.get(), av_.get())))
			av_.trace_add("write", lambda *_, nv=nv, tv_=tv_, av_=av_: nv.set(join_artist(tv_.get(), av_.get())))
			nf = ttk.Frame(f)
			nf.grid(row=r, column=0, sticky="we", pady=2)
			ttk.Entry(nf, textvariable=tv_, width=34, font="TkDefaultFont").pack(side="left")
			ttk.Entry(nf, textvariable=av_, width=24, font="TkDefaultFont").pack(side="left", padx=(4, 0))
			volume_control(f, vv, on_change=lambda v, src=src: self.preview_volume(src, v)).grid(row=r, column=1, padx=6)
			ttk.Entry(f, textvariable=cv, width=6).grid(row=r, column=2, padx=2)
			ttk.Label(f, text=mmss(secs)).grid(row=r, column=3, padx=4)
			ttk.Button(f, text="▶ / ■", width=6, command=lambda src=src, vv=vv: self.preview(src, vv)).grid(row=r, column=4)
			rows.append((src, nv, vv, cv))

		def ok():
			items = []
			for src, nv, vv, cv in rows:
				name = nv.get().strip().replace('"', "'")
				if not name:
					continue
				if name in self.mod.songs or name in [x[1] for x in items]:
					messagebox.showerror(APP_NAME, f"There is already a song called '{name}'.", parent=w)
					return
				like = [n for n in self.mod.songs if norm_song(n) == norm_song(name)]
				if like and not messagebox.askyesno(APP_NAME, f"'{name}' looks like '{like[0]}', already in the mod. Add it anyway?", parent=w):
					return
				try:
					vol, ch = float(vv.get()), float(cv.get())
				except ValueError:
					messagebox.showerror(APP_NAME, "Volume and chance are numbers.", parent=w)
					return
				items.append((src, name, vol, ch))
			w.destroy()
			self.write_songs(st, items)
		bf = ttk.Frame(f)
		bf.grid(row=len(rows) + 1, column=0, columnspan=4, sticky="e", pady=(8, 0))
		ttk.Button(bf, text=f"Add {len(rows)} songs", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	@staticmethod
	def num(x):
		return str(int(x)) if float(x).is_integer() else str(x)

	def music_block(self, name, factor=1, code=None):
		"""music = { song chance = { } }: chance from a factor, or the chance block's own code."""
		if code is None:
			return ["music = {", f'\tsong = "{name}"', "\tchance = {", "\t\tmodifier = {", f"\t\t\tfactor = {self.num(factor)}", "\t\t}", "\t}", "}"]
		return ["music = {", f'\tsong = "{name}"', "\tchance = {"] + ["\t\t" + l for l in tidy_code(code)] + ["\t}", "}"]

	def chance_code(self, st, entry):
		"""The code inside a station song's chance = { } (as written in its file)."""
		ch = next((x for x in entry.value if x.key == "chance" and x.block), None) if entry.block else None
		if ch is None:
			return "modifier = {\n\tfactor = 1\n}"
		return "\n".join(tidy_code(block_inner(self.lines(st.rel), ch)))

	def write_songs(self, st, items):
		m = self.mod
		asset = self.asset_file_for(st)
		alines = self.lines(asset)
		# the new asset entries go after the last one of this station (else at the end, under its name)
		mine = [m.songs[n].entry.last for n, _, _ in st.songs if n in m.songs and m.songs[n].rel == asset]
		block = []
		for src, name, vol, ch in items:
			fn = slug(os.path.splitext(os.path.basename(src))[0]) + ".ogg"
			k = 2
			while m.exists(f"music/{st.token}/{fn}"):
				fn = f"{slug(os.path.splitext(os.path.basename(src))[0])}_{k}.ogg"
				k += 1
			self.stage_file(f"music/{st.token}/{fn}", src)  # (copied on Save to mod)
			block += ["music = {", f'\tname = "{name}"', f'\tfile = "{st.token}/{fn}"', f"\tvolume = {self.num(vol)}", "}"]
		if mine:
			at = max(mine) + 1
			alines[at:at] = block
		else:
			alines += ["", f"# {(st.title or st.token).upper()}"] + block
		self.write(asset, alines)
		slines = self.lines(st.rel)
		for _, name, _, ch in items:
			slines += self.music_block(name, ch)
		self.write(st.rel, slines)
		m.load()
		self.station = m.stations.get(st.token)
		self.fill_stations()
		self.status(f"Added {len(items)} songs to {st.title or st.token}.")

	def edit_song(self):
		sel = self.selected_songs()
		if len(sel) != 1:
			return
		name, factor, entry = sel[0]
		song = self.mod.songs.get(name)
		w = tk.Toplevel(self)
		w.title("Song")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		t0, a0 = split_artist(name)
		tv, av = tk.StringVar(value=t0), tk.StringVar(value=a0)
		nv, vv = tk.StringVar(value=name), tk.StringVar(value=str(song.volume if song else DEFAULT_VOLUME))
		ingame = ttk.Label(f, text="", style="Muted.TLabel")

		def show_name(*_):
			nv.set(join_artist(tv.get(), av.get()))
			ingame.config(text=f"In game: {nv.get()}")
		tv.trace_add("write", show_name)
		av.trace_add("write", show_name)
		ttk.Label(f, text="Song:").grid(row=10, column=0, sticky="w", pady=3)
		ttk.Entry(f, textvariable=tv, width=50, font="TkDefaultFont").grid(row=10, column=1, sticky="w")
		ttk.Label(f, text="Artist:").grid(row=11, column=0, sticky="w", pady=3)
		ttk.Entry(f, textvariable=av, width=50, font="TkDefaultFont").grid(row=11, column=1, sticky="w")
		ingame.grid(row=12, column=1, sticky="w")
		show_name()
		fv = tk.StringVar(value=song.file if song else "")
		ttk.Label(f, text="File (music/):").grid(row=13, column=0, sticky="w", pady=3)
		ff = ttk.Frame(f)
		ff.grid(row=13, column=1, sticky="w")
		ttk.Entry(ff, textvariable=fv, width=44, font="TkDefaultFont").pack(side="left")
		fok = ttk.Label(ff, text="")
		fok.pack(side="left", padx=6)
		fv.trace_add("write", lambda *_: fok.config(text="✓ there" if self.mod.exists("music/" + fv.get().strip()) else "✗ not there",
													 foreground="#2e7d32" if self.mod.exists("music/" + fv.get().strip()) else "#c62828"))
		fv.set(fv.get())
		ttk.Button(ff, text="Browse...", style="Tool.TButton",
				   command=lambda: (lambda r: r and fv.set(r))(self.pick_song_file(w, self.station))).pack(side="left")
		for r, (text, var) in enumerate((("Volume:", vv),), start=14):
			ttk.Label(f, text=text).grid(row=r, column=0, sticky="w", pady=3)
			if True:
				vf = ttk.Frame(f)
				vf.grid(row=r, column=1, sticky="w")
				p = self.mod.song_path(song) if song else None
				volume_control(vf, vv, on_change=lambda v, p=p: p and self.preview_volume(p, v), length=220).pack(side="left")
				if p:
					ttk.Button(vf, text="▶ / ■ hear it", command=lambda p=p: self.preview(p, vv)).pack(side="left", padx=8)
			else:
				ttk.Entry(f, textvariable=var, width=50 if r == 0 else 8, font="TkDefaultFont").grid(row=r, column=1, sticky="w")
		ttk.Label(f, text="Chance:").grid(row=20, column=0, sticky="nw", pady=3)
		cf = ttk.Frame(f)
		cf.grid(row=20, column=1, sticky="we")
		ttk.Label(cf, text="The code inside chance = { }. Each modifier multiplies the chance by its factor when its "
						   "triggers are true (factor = 0: never).", style="Muted.TLabel", wraplength=ui.px(520), justify="left").pack(anchor="w")
		code = tk.Text(cf, width=60, height=9, font="om_mono", wrap="none", relief="solid", borderwidth=1, undo=True,
					   tabs=(ui.px(28),))
		code.pack(fill="both", expand=True, pady=4)
		code.insert("1.0", self.chance_code(self.station, entry))
		hb = ttk.Frame(cf)
		hb.pack(anchor="w")

		def add(block):
			code.insert("end", ("\n" if code.get("1.0", "end").strip() else "") + block)
			code.see("end")

		def ask_tag(kind):
			tag = simpledialog.askstring("Country", "Country tag (e.g. USA):", parent=w)
			tag = (tag or "").strip().upper()
			if not tag:
				return
			add(f"modifier = {{\n\tfactor = 0\n\tNOT = {{ is_tag = {tag} }}\n}}" if kind == "only" else
				f"modifier = {{\n\tfactor = 2\n\tis_tag = {tag}\n}}")

		def ask_gov():
			g = simpledialog.askstring("Government", "Ideology (has_government = ...), e.g. democratic:", parent=w)
			if g and g.strip():
				add(f"modifier = {{\n\tfactor = 0\n\tNOT = {{ has_government = {g.strip()} }}\n}}")
		for text, cmd in (("Only for a country...", lambda: ask_tag("only")), ("More for a country...", lambda: ask_tag("more")),
						  ("Only at peace", lambda: add("modifier = {\n\tfactor = 0\n\thas_war = yes\n}")),
						  ("Only at war", lambda: add("modifier = {\n\tfactor = 0\n\thas_war = no\n}")),
						  ("Only for an ideology...", ask_gov)):
			ttk.Button(hb, text="+ " + text, style="Tool.TButton", command=cmd).pack(side="left", padx=(0, 4))
		if not song:
			ttk.Label(f, text="No music = { } in the .asset files (add it with Add songs)", foreground="#777").grid(row=21, column=0, columnspan=2, sticky="w", pady=(6, 0))

		def ok():
			new = nv.get().strip().replace('"', "'")
			if not tv.get().strip():
				messagebox.showerror(APP_NAME, "The song needs a name.", parent=w)
				return
			try:
				vol = float(vv.get())
			except ValueError:
				messagebox.showerror(APP_NAME, "The volume is a number (0 - 1).", parent=w)
				return
			body = code.get("1.0", "end").strip()
			if body.count("{") != body.count("}"):
				messagebox.showerror(APP_NAME, f"The chance code has {body.count('{')} {{ and {body.count('}')} }}: they must match.", parent=w)
				return
			try:
				parse(f"chance = {{ {body} }}")
			except Exception as ex:
				messagebox.showerror(APP_NAME, f"The chance code doesn't read:\n{ex}", parent=w)
				return
			if new != name and new in self.mod.songs:
				messagebox.showerror(APP_NAME, f"There is already a song called '{new}'.", parent=w)
				return
			w.destroy()
			st = self.station
			lines = self.lines(st.rel)
			lines[entry.first:entry.last + 1] = self.music_block(new, code=body)  # (the song's whole music = { } block)
			self.write(st.rel, lines)
			if song:
				lines = self.lines(song.rel)
				for k in range(song.entry.first, song.entry.last + 1):
					lines[k] = re.sub(r'(\bname\s*=\s*)"[^"]*"', lambda mm: mm.group(1) + f'"{new}"', lines[k])
					lines[k] = re.sub(r"(\bvolume\s*=\s*)[\d.]+", lambda mm: mm.group(1) + self.num(vol), lines[k])
					if fv.get().strip() and fv.get().strip() != song.file:
						lines[k] = re.sub(r'(\bfile\s*=\s*)"[^"]*"', lambda mm: mm.group(1) + f'"{fv.get().strip()}"', lines[k])
				self.write(song.rel, lines)
				# the same song in other stations follows its new name
				if new != name:
					for other in self.mod.stations.values():
						if other is st or not any(n == name for n, _, _ in other.songs):
							continue
						ol = self.lines(other.rel)
						ol = [re.sub(r'(\bsong\s*=\s*)"' + re.escape(name) + '"', lambda mm: mm.group(1) + f'"{new}"', l) for l in ol]
						self.write(other.rel, ol)
			self.mod.load()
			self.station = self.mod.stations.get(st.token)
			self.after_change()
		bf = ttk.Frame(f)
		bf.grid(row=30, column=0, columnspan=2, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="OK", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def _drop_from_station(self, st, entries):
		lines = self.lines(st.rel)
		drop = set()
		for e in entries:
			drop |= set(range(e.first, e.last + 1))
		self.write(st.rel, [l for i, l in enumerate(lines) if i not in drop])

	def move_songs(self):
		sel = self.selected_songs()
		if not sel:
			return
		others = {(s.title or t): t for t, s in self.mod.stations.items() if t != self.station.token}
		if not others:
			return
		w = tk.Toplevel(self)
		w.title("Move to station")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=10)
		f.pack()
		v = tk.StringVar(value=next(iter(others)))
		ttk.Label(f, text=f"Move {len(sel)} songs to:").pack(anchor="w")
		ttk.Combobox(f, textvariable=v, values=list(others), state="readonly", width=36).pack(pady=4)
		keep = tk.BooleanVar(value=False)
		ttk.Checkbutton(f, text="Keep them in this station too (copy)", variable=keep).pack(anchor="w")

		def ok():
			dest = self.mod.stations[others[v.get()]]
			w.destroy()
			have = {n for n, _, _ in dest.songs}
			dl = self.lines(dest.rel)
			for n, factor, e in sel:
				if n not in have:
					dl += self.music_block(n, code=self.chance_code(self.station, e))
			self.write(dest.rel, dl)
			if not keep.get():
				self._drop_from_station(self.station, [e for _, _, e in sel])
			self.mod.load()
			self.station = self.mod.stations.get(self.station.token)
			self.fill_stations()
			self.status(f"{len(sel)} songs {'copied' if keep.get() else 'moved'} to {dest.title or dest.token} (their files stay where they are).")
		ttk.Button(f, text="OK", command=ok).pack(side="right")

	def remove_songs(self):
		sel = self.selected_songs()
		if not sel:
			return
		if self._play_row and self._play_row[2] in [n for n, *_ in sel]:
			self.stop_song()  # its file may be deleted
		elsewhere = {n for t, s in self.mod.stations.items() if t != self.station.token for n, _, _ in s.songs}
		gone = [n for n, _, _ in sel if n not in elsewhere]
		if not messagebox.askyesno(APP_NAME, f"Take {len(sel)} songs out of {self.station.title or self.station.token}?\n\n"
								   + (f"{len(gone)} of them are in no other station: their music = {{ }} in the .asset goes too, "
									  "and you'll be asked about their files." if gone else "They stay in the other stations.")):
			return
		self._drop_from_station(self.station, [e for _, _, e in sel])
		files = []
		by_rel = {}
		for n in gone:
			song = self.mod.songs.get(n)
			if song:
				by_rel.setdefault(song.rel, []).append(song)
				files.append("music/" + song.file)
		for rel, songs in by_rel.items():
			lines = self.lines(rel)
			drop = set()
			for s in songs:
				drop |= set(range(s.entry.first, s.entry.last + 1))
			self.write(rel, [l for i, l in enumerate(lines) if i not in drop])
		files = [r for r in files if self.mod.exists(r)]
		if files and messagebox.askyesno(APP_NAME, f"Delete their {len(files)} .ogg files too, on Save to mod? (A copy goes to the backups.)"):
			for r in files:
				self.stage_file(r, None)
		self.mod.load()
		self.station = self.mod.stations.get(self.station.token)
		self.fill_stations()
		self.status(f"Removed {len(sel)} songs.")

	@staticmethod
	def on_play_icon(t, ev):
		return bool(t.identify_row(ev.y)) and t.identify_column(ev.x) == "#0" and (t.identify_element(ev.x, ev.y) == "image" or ev.x < 26)

	def preview(self, path, var):
		"""Plays a song file at the dialog's volume (again: stops it)."""
		if self.player.path and os.path.normcase(self.player.path) == os.path.normcase(path):
			self.stop_song()
			return
		try:
			vol = float(var.get())
		except ValueError:
			vol = DEFAULT_VOLUME
		try:
			self.player.play(path, vol, 0, self.duration(path) or 0)
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't play {os.path.basename(path)}:\n{ex}")
			return
		self._set_playing(("preview", path, os.path.basename(path)), os.path.splitext(os.path.basename(path))[0])

	def preview_volume(self, path, v):
		"""Moving a volume slider changes the playing song's volume straight away."""
		if self.player.path and self.player.mixer and os.path.normcase(self.player.path) == os.path.normcase(path):
			self.player.mixer.music.set_volume(v)

	def song_click(self, ev):
		"""A click on the ▶ / ■ in front of a song plays / stops it."""
		t = self.song_tree
		row = t.identify_row(ev.y)
		if self.on_play_icon(t, ev):
			self.toggle_song(int(row))
			return "break"

	def play_song(self):
		rows = sorted(int(i) for i in self.song_tree.selection())
		if rows:
			self.toggle_song(rows[0])

	def toggle_song(self, i):
		if not self.station or i >= len(self.station.songs):
			return
		n = self.station.songs[i][0]
		key = (self.mod.root, self.station.token, n)
		if self._play_row == key:
			self.stop_song()
			return
		song = self.mod.songs.get(n)
		p = self.mod.song_path(song)
		if not p:
			messagebox.showinfo(APP_NAME, f"{n} has no song file to play.")
			return
		try:
			self.player.play(p, song.volume, 0, self.duration(p) or 0)
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't play {os.path.basename(p)}:\n{ex}")
			return
		self._set_playing(key, n)

	def _set_playing(self, key, name):
		"""Marks the playing song (▶ -> ■) in the list and fills the now playing bar."""
		old = self._play_row
		self._play_row = key
		if self.station:
			for i, (n, _, _) in enumerate(self.station.songs):
				iid = str(i)
				if not self.song_tree.exists(iid) or "problem" in self.song_tree.item(iid, "tags"):
					continue
				on = key == (self.mod.root, self.station.token, n)
				self.song_tree.item(iid, image=self.img_stop if on else self.img_play, tags=("playing",) if on else ())
			ui.stripe(self.song_tree)
		if key:
			st = self.get_mod(key[0]).stations.get(key[1]) if old != key and key[0] != "preview" else None
			where = (st.title if st else None) or ("preview" if key[0] == "preview" else key[1])
			self.now_label.config(text=f"♪ {name}  ({where})" if old != key else self.now_label["text"], foreground="#2e7d32")
			self.now_scale.config(to=max(1, self.player.length))
			self.btn_stop.state(["!disabled"])
			self.btn_pause.state(["!disabled"])
			self.btn_pause.config(text="⏸ Pause")
			self._tick()
		else:
			self.now_label.config(text="Click ▶ in front of a song to play it here.", foreground="#555")
			self.now_pos.set(0)
			self.now_time.config(text="")
			self.btn_stop.state(["disabled"])
			self.btn_pause.state(["disabled"])

	def _tick(self):
		if not self._play_row:
			return
		if not self.player.path or self.player.finished():
			self.stop_song()
			return
		pos = self.player.position()
		if not self._seeking:
			self.now_pos.set(pos)
		self.now_time.config(text=f"{mmss(pos)} / {mmss(self.player.length)}")
		if getattr(self, "_tick_job", None):
			self.after_cancel(self._tick_job)
		self._tick_job = self.after(250, self._tick)

	def stop_song(self):
		self.player.stop()
		self._set_playing(None, "")

	def pause_song(self):
		self.player.pause()
		self.btn_pause.config(text="▶ Resume" if self.player.paused else "⏸ Pause")

	def seek_song(self, ev=None):
		self._seeking = False
		if self._play_row:
			self.player.seek(self.now_pos.get())

	def open_song(self):
		sel = self.selected_songs()
		song = self.mod.songs.get(sel[0][0]) if sel else None
		p = self.mod.song_path(song)
		if p and os.path.exists(p):
			os.startfile(p)

	GAP_ORDER = ("Duplicate song name", "Same song, different spelling", "Same file for two songs", "Song twice in a station",
				 "Missing music: no file", "Missing music: no .asset entry", "Station without a name", "Station without album art",
				 "Song in no station", "Unused .ogg file")

	def all_issues(self):
		return [(m, *i) for m in self.view_mods for i in m.issues()]

	def update_gaps(self):
		"""Duplicates and missing music are looked for on every load: their count is on the Gap Finder button."""
		if not hasattr(self, "gap_btn"):
			return
		issues = self.all_issues()
		dup = sum(1 for _, k, *_ in issues if k.startswith(("Duplicate", "Same", "Song twice")))
		miss = sum(1 for _, k, *_ in issues if k.startswith("Missing"))
		self.gap_btn.config(text="🔍 Gap Finder" + (f"  ⚠ {dup} duplicates, {miss} missing" if dup or miss else f" ({len(issues)})" if issues else ""))

	def check_mod(self):
		self.gap_finder()

	def gap_finder(self):
		"""Everything that doesn't add up in the music mods shown: duplicates, missing music, unused files..."""
		w = tk.Toplevel(self)
		w.title("Music Master - Gap Finder")
		w.geometry(f"{ui.px(900)}x{ui.px(520)}")
		w.transient(self.winfo_toplevel())
		top = ttk.Frame(w, padding=8)
		top.pack(fill="x")
		info = ttk.Label(top, text="")
		info.pack(side="left")
		box = ttk.Frame(w, padding=(8, 0, 8, 8))
		box.pack(fill="both", expand=True)
		t = ttk.Treeview(box, columns=("mod",), selectmode="browse")
		t.heading("#0", text="Found")
		t.heading("mod", text="Music mod")
		t.column("#0", width=ui.px(680), stretch=True)
		t.column("mod", width=ui.px(170), stretch=False)
		ys = ttk.Scrollbar(box, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		t.tag_configure("kind", font="om_bold")
		where = {}

		def fill():
			t.delete(*t.get_children())
			where.clear()
			issues = self.all_issues()
			kinds = {}
			for m, k, text, tok, song in issues:
				kinds.setdefault(k, []).append((m, text, tok, song))
			for k in sorted(kinds, key=lambda k: self.GAP_ORDER.index(k) if k in self.GAP_ORDER else 99):
				kid = t.insert("", "end", text=f"{k} ({len(kinds[k])})", open=k.startswith(("Duplicate", "Same", "Song twice", "Missing")), tags=("kind",))
				for m, text, tok, song in kinds[k]:
					iid = t.insert(kid, "end", text=text, values=(self.short_name(m),))
					where[iid] = (m, tok, song)
			info.config(text=f"{len(issues)} found in {', '.join(self.short_name(m) for m in self.view_mods)}. "
							 "Double-click one to go to it." if issues else "Nothing found: no duplicates, no missing music.")
			self.update_gaps()

		def go(ev=None):
			sel = t.selection()
			if not sel or sel[0] not in where:
				return
			m, tok, song = where[sel[0]]
			if not tok and song:  # the first station that plays it
				tok = next((s.token for s in m.stations.values() if any(n == song for n, _, _ in s.songs)), None)
			iid = f"{os.path.basename(m.root)}|{tok}" if tok else None
			if iid and self.st_tree.exists(iid):
				self.st_tree.selection_set(iid)
				self.st_tree.see(iid)
				self.show_station()
				if song and self.station:
					rows = [str(i) for i, (n, _, _) in enumerate(self.station.songs) if n == song]
					if rows:
						self.song_tree.selection_set(rows)
						self.song_tree.see(rows[0])
		t.bind("<Double-1>", go)
		ttk.Button(top, text="Look again", command=fill).pack(side="right")
		fill()

	# ---------- planned stations ----------
	def plans_path(self):
		return os.path.join(TOOL_DIR, PLANS_FILE)

	def load_plans(self):
		try:
			data = json.load(open(self.plans_path(), encoding="utf-8"))
		except (OSError, ValueError):
			data = []
		if isinstance(data, dict):
			self.mod_meta = data.get("music_mods", {})
			data = data.get("plans", [])
		self.fill_blame(data)
		return data

	def fill_blame(self, plans):
		"""Plans without "added_by" (written by hand, or by an older Music Master) get it from git blame of the plans file."""
		if all(p.get("added_by") for p in plans):
			return
		lines = git(TOOL_DIR, "blame", "--line-porcelain", "--", PLANS_FILE).splitlines()
		who, when, titles = None, None, {}
		for l in lines:
			if l.startswith("author "):
				who = l[7:]
			elif l.startswith("author-time "):
				when = time.strftime("%Y-%m-%d", time.localtime(int(l[12:])))
			elif l.startswith("\t") and '"title":' in l and who:
				m = re.search(r'"title":\s*"(.*)"', l)
				if m:
					titles.setdefault(json.loads(f'"{m.group(1)}"'), (who, when))
		for p in plans:
			if not p.get("added_by") and p.get("title") in titles:
				who, when = titles[p["title"]]
				if who != "Not Committed Yet":
					p["added_by"], p["added"] = who, when

	def save_plans(self):
		if self._plan_job:
			self.after_cancel(self._plan_job)
			self._plan_job = None
		for p in self.plans:  # (a lasting id: the To Do tasks of the station follow it through renames)
			p.setdefault("id", f"{slug(p.get('title', '')) or 'plan'}-{os.urandom(3).hex()}")
		self.publish_music_plans()
		self.write_plans_file()
		self.app.log(PLANS_FILE)
		self.sync_todo()

	def write_plans_file(self):
		with open(self.plans_path(), "w", encoding="utf-8") as f:
			json.dump({"music_mods": self.mod_meta, "plans": self.plans}, f, indent=1, ensure_ascii=False)

	def sync_todo(self):
		"""The planned stations as tasks in To Do Master's RR Music Mods project (music mod > station > steps)."""
		get = getattr(self.app, "todo_page", None)
		if not get or not hasattr(self, "_names"):
			return
		try:
			page = get()
			keys = {p.get("mod", "") for p in self.plans} | {os.path.basename(r) for r in self.rr_mods()}
			page.sync_music({k: self.short_name(k) for k in keys if k},
							[(p["id"], p.get("title", "") or "(no name)", p.get("mod", "")) for p in self.plans if p.get("id")],
							statuses={p["id"]: p.get("status", "") for p in self.plans if p.get("id")},
							artwork={p["id"] for p in self.plans if p.get("id") and p.get("logo")
									 and os.path.isfile(self.plan_logo_path(p))})
		except Exception as ex:
			self.status(f"Couldn't update To Do Master: {ex}")

	def fill_plans(self):
		t = self.plan_tree
		keep = set(t.selection())
		t.delete(*t.get_children())
		shown = {os.path.basename(m.root) for m in self.view_mods}
		order = sorted(range(len(self.plans)), key=lambda i: (self.plans[i].get("mod") not in shown, self.plans[i].get("status") == "Made",
															  self.plans[i].get("title", "").lower()))
		for i in order:
			p = self.plans[i]
			mod = p.get("mod") or ""
			if mod and mod not in shown and self.mod_exists(mod):
				continue  # a plan of another (real) music mod; plans of planned mods always show
			t.insert("", "end", iid=str(i), text=p.get("title", "?"), values=self.plan_values(p), tags=self.plan_tags(p))
		ui.stripe(t)
		self.sec_plans.set_count(f"{len(t.get_children())}")
		for i in keep:
			if t.exists(i):
				t.selection_add(i)

	def build_plan_pane(self, right):
		sec = ui.Section(right, "Planned station", "music_plan_head", self.app, expand=False).place_in(fill="x")
		head = ttk.Frame(sec.body)
		head.pack(fill="x")
		lf = ttk.Frame(head)
		lf.pack(side="left", anchor="n")
		self.plan_logo = tk.Label(lf, text="(no logo yet)\n\nclick to add one", width=20, height=7, relief="groove", fg="#777", cursor="hand2")
		self.plan_logo.pack()
		self.plan_logo.bind("<Button-1>", lambda ev: self.plan_pick_logo())
		lb = ttk.Frame(lf)
		lb.pack(fill="x", pady=(4, 0))
		ttk.Button(lb, text="Logo...", command=self.plan_pick_logo).pack(side="left", expand=True, fill="x")
		ttk.Button(lb, text="Remove", command=self.plan_remove_logo).pack(side="left")
		g = ttk.Frame(head)
		g.pack(side="left", fill="x", expand=True, padx=12, anchor="n")
		self.pv = {k: tk.StringVar() for k in ("title", "token", "mod", "status", "theme")}
		self.plan_name = tk.Entry(g, textvariable=self.pv["title"], font="om_title", relief="flat", width=40)
		self.plan_name.grid(row=0, column=0, columnspan=3, sticky="we", pady=(0, 8))
		self.plan_tok_hint = ttk.Label(g, text="", style="Muted.TLabel")
		for r, (k, text) in enumerate((("token", "Token"), ("mod", "Music mod"), ("status", "Status"), ("theme", "Theme / sound")), start=1):
			ttk.Label(g, text=text, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 10))
			if k in ("mod", "status"):
				cb = ttk.Combobox(g, textvariable=self.pv[k], state="readonly", width=46 if k == "mod" else 22, font="TkDefaultFont")
				cb.grid(row=r, column=1, sticky="w")
				if k == "mod":
					self.plan_mod_box = cb
				else:
					cb.config(values=STATUSES)
			else:
				ttk.Entry(g, textvariable=self.pv[k], width=48 if k == "theme" else 30, font="TkDefaultFont").grid(row=r, column=1, sticky="w")
		self.plan_tok_hint.grid(row=1, column=2, sticky="w", padx=6)
		g.columnconfigure(2, weight=1)
		hb = ttk.Frame(g)
		hb.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
		ttk.Button(hb, text="Make the station", command=self.plan_to_station).pack(side="left")
		ttk.Button(hb, text="Attach to music mod...", command=self.attach_plans).pack(side="left", padx=4)
		self.plan_info = ttk.Label(sec.body, text="", style="Muted.TLabel")
		self.plan_info.pack(anchor="w", pady=(8, 0))

		sec = ui.Section(right, "Songs", "music_plan_songs", self.app).place_in(fill="both", pady=(8, 0))
		ui.tool_button(sec.tools, "+ Add song", lambda: self.plan_edit_song(new=True)).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "Download / edit audio…", lambda: self.audio_workshop(planned=True)).pack(side="left", padx=2)
		sf = ttk.Frame(sec.body, width=ui.px(500), height=ui.px(250))
		sf.pack_propagate(False)
		sf.pack(fill="both", expand=True)
		s = self.plan_songs = ttk.Treeview(sf, columns=("artist", "game", "link", "by"), selectmode="extended")
		for col, text, w in (("#0", "Song", 260), ("artist", "Artist", 170), ("game", "In game", 70), ("link", "YouTube", 300), ("by", "Added by", 110)):
			s.heading(col, text=text)
			s.column(col, width=ui.px(w), anchor="center" if col == "game" else "w", stretch=col in ("#0", "artist", "link"))
		ys = ttk.Scrollbar(sf, command=s.yview)
		xs = ttk.Scrollbar(sf, orient="horizontal", command=s.xview)
		s.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
		xs.pack(side="bottom", fill="x")
		s.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		s.tag_configure("video", foreground="#1f5fa8")
		s.tag_configure("novideo", foreground="#777")
		s.tag_configure("done", foreground="#2e7d32")
		s.bind("<Double-1>", lambda ev: None if self.on_play_icon(s, ev) else self.plan_open_video(ev))
		s.bind("<Button-1>", self.plan_song_click, add="+")
		sb = ttk.Frame(sec.body)
		sb.pack(fill="x", pady=(6, 0))
		ttk.Button(sb, text="▶ Watch on YouTube", command=self.plan_open_video).pack(side="left")
		ttk.Button(sb, text="Edit song...", command=self.plan_edit_song).pack(side="left", padx=(12, 4))
		ttk.Button(sb, text="Remove", command=self.plan_remove_songs).pack(side="left")
		ttk.Button(sb, text="▲", width=3, command=lambda: self.plan_move_songs(-1)).pack(side="left", padx=(12, 0))
		ttk.Button(sb, text="▼", width=3, command=lambda: self.plan_move_songs(1)).pack(side="left")
		ttk.Button(sb, text="In game ✓ / ✗", command=self.plan_toggle_done).pack(side="left", padx=12)
		ttk.Label(sec.body, text="Click ▶ (or double-click a song) to watch its video; a song without a link searches YouTube for it.",
				  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
		sec = ui.Section(right, "Notes", "music_plan_notes", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.plan_notes = tk.Text(sec.body, height=4, font="om_body", wrap="word", relief="solid", borderwidth=1)
		self.plan_notes.pack(fill="x")
		self.plan_notes.bind("<KeyRelease>", lambda ev: self.plan_changed("notes"))
		self._plan_loading = False
		for k, var in self.pv.items():
			var.trace_add("write", lambda *_, k=k: self.plan_changed(k))

	def show_plan(self):
		plans = self._plans()
		if not plans:
			return
		self.flush_plan()
		self.show_pane("plan")
		p = self.cur_plan = plans[0]
		self._plan_choices = self.mod_choices()
		self._plan_loading = True
		for k in ("title", "token", "status", "theme"):
			self.pv[k].set(p.get(k, ""))
		self.plan_mod_box.config(values=list(self._plan_choices))
		self.pv["mod"].set(next((k for k, x in self._plan_choices.items() if x == p.get("mod", "")), UNDECIDED))
		self.plan_notes.delete("1.0", "end")
		self.plan_notes.insert("1.0", p.get("notes", ""))
		self._plan_loading = False
		self.plan_name.config(fg=self.mod_colour(p["mod"]) if p.get("mod") else "#333")
		self.show_plan_logo()
		self.fill_plan_songs()
		self.plan_token_hint()

	def plan_token_hint(self):
		p = self.cur_plan
		self.plan_tok_hint.config(text="" if p.get("token") else f"(empty: it will be {slug(p.get('title', ''))})")

	def show_plan_logo(self):
		p = self.cur_plan
		path = self.plan_logo_path(p)
		img = None
		if path and os.path.exists(path):
			try:
				im = Image.open(path).convert("RGBA")
				im.thumbnail((ART_SIZE[0] // 2, ART_SIZE[1]), Image.LANCZOS)
				img = ImageTk.PhotoImage(im)
			except Exception:
				img = None
		self._plan_photo = img
		if img:
			self.plan_logo.config(image=img, text="", width=ART_SIZE[0] // 2, height=ART_SIZE[1])
		else:
			self.plan_logo.config(image="", text="(no logo yet)\n\nclick to add one", width=20, height=7)

	def plan_pick_logo(self):
		p = self.cur_plan
		if not p:
			return
		src = filedialog.askopenfilename(title="Logo of " + p.get("title", ""),
										 filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.dds *.tga *.webp"), ("All files", "*.*")])
		if not src:
			return
		try:
			im = Image.open(src).convert("RGBA")
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't read that picture:\n{ex}")
			return
		im.thumbnail((608, 480), Image.LANCZOS)  # plenty for the 152 x 120 album art
		rel = f"{PLAN_LOGOS}/{slug(p.get('token') or p.get('title') or 'plan')}-{os.urandom(6).hex()}.png"
		os.makedirs(os.path.join(TOOL_DIR, PLAN_LOGOS), exist_ok=True)
		old = p.get("logo")
		im.save(os.path.join(TOOL_DIR, rel))
		if old and old != rel and not any(q is not p and q.get("logo") == old for q in self.plans):
			try:
				os.remove(os.path.join(TOOL_DIR, old))
			except OSError:
				pass
		p["logo"] = rel
		self.save_plans()
		self.show_plan_logo()
		self.status(f"Logo of {p.get('title')} saved as tools/organisation_master/{rel}.")

	def plan_remove_logo(self):
		p = self.cur_plan
		if not p or not p.get("logo"):
			return
		old = p.pop("logo")
		if not any(q.get("logo") == old for q in self.plans):
			try:
				os.remove(os.path.join(TOOL_DIR, old))
			except OSError:
				pass
		self.save_plans()
		self.show_plan_logo()

	def plan_changed(self, key):
		"""Edits on the right go straight into the plan (saved a moment later)."""
		p = self.cur_plan
		if self._plan_loading or p is None:
			return
		if key == "notes":
			p["notes"] = self.plan_notes.get("1.0", "end").strip()
		elif key == "mod":
			p["mod"] = self._plan_choices.get(self.pv["mod"].get(), "")
			self.plan_name.config(fg=self.mod_colour(p["mod"]) if p["mod"] else "#333")
		else:
			p[key] = self.pv[key].get().strip()
		if key in ("title", "token"):
			self.plan_token_hint()
		self.update_plan_row(p)
		if self._plan_job:
			self.after_cancel(self._plan_job)
		self._plan_job = self.after(800, self.flush_plan)

	def flush_plan(self):
		if self._plan_job:
			self.after_cancel(self._plan_job)
			self._plan_job = None
			self.save_plans()

	def update_plan_row(self, p):
		iid = str(self.plans.index(p)) if p in self.plans else None
		if not iid or not self.plan_tree.exists(iid):
			return
		self.plan_tree.item(iid, text=p.get("title") or "?", values=self.plan_values(p), tags=self.plan_tags(p))
		ui.stripe(self.plan_tree)

	def plan_values(self, p):
		mod = p.get("mod") or ""
		known = any(entry.get("mod") == mod for entry in getattr(self, "catalog", {}).values())
		label = self.short_name(mod) + ("" if self.mod_exists(mod) else " (not installed)" if known else " (planned)") if mod else UNDECIDED
		return label, p.get("status", ""), len(p.get("songs", []))

	def plan_tags(self, p):
		return (self.colour_tag(self.plan_tree, p["mod"]),) if p.get("mod") else ("undecided",)

	def fill_plan_songs(self):
		p = self.cur_plan
		t = self.plan_songs
		keep = t.selection()
		t.delete(*t.get_children())
		songs = p["songs"] = [plan_song(x) for x in p.get("songs", [])]
		for i, x in enumerate(songs):
			t.insert("", "end", iid=str(i), text=" " + x["title"], image=self.img_video, values=(x.get("artist", ""), "✓" if x.get("in_game") else "", x.get("link") or "(no video)",
																	 x.get("added_by", "")),
					 tags=("done",) if x.get("in_game") else ("video",) if x.get("link") else ("novideo",))
		ui.stripe(t)
		for i in keep:
			if t.exists(i):
				t.selection_add(i)
		vids = sum(1 for x in songs if x.get("link"))
		done = sum(1 for x in songs if x.get("in_game"))
		self.plan_info.config(text=(added_text(p) + "\n" if added_text(p) else "") + f"{len(songs)} songs  -  {vids} with a YouTube video  -  {done} already in game"
								   + (f"  -  logo: tools/organisation_master/{p['logo']}" if p.get("logo") else ""))
		self.update_plan_row(p)

	def plan_song_click(self, ev):
		"""The ▶ in front of a planned song opens its YouTube video."""
		t = self.plan_songs
		row = t.identify_row(ev.y)
		if self.on_play_icon(t, ev):
			t.selection_set(row)
			self.plan_open_video()
			return "break"

	def _plan_song_rows(self):
		return sorted(int(i) for i in self.plan_songs.selection())

	def plan_open_video(self, ev=None):
		if ev is not None and not self.plan_songs.identify_row(ev.y):
			return
		rows = self._plan_song_rows()
		if not rows or not self.cur_plan:
			return
		for i in rows[:10]:
			x = self.cur_plan["songs"][i]
			webbrowser.open(x["link"] if x.get("link") else
							"https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(f"{x['title']} {x.get('artist', '')}".strip()))

	def plan_edit_song(self, new=False, plan=None, song_index=None):
		p = plan if plan is not None else self.cur_plan
		if not p:
			return
		rows = [song_index] if song_index is not None else self._plan_song_rows()
		if not new and not rows:
			messagebox.showinfo(APP_NAME, "Pick a song first.")
			return
		x = {"title": "", "artist": "", "link": "", "in_game": False} if new else p["songs"][rows[0]]
		w = tk.Toplevel(self)
		w.title("Song of " + p.get("title", ""))
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=10)
		f.pack()
		v = {k: tk.StringVar(value=x.get(k, "")) for k in ("title", "artist", "link")}
		for r, (k, text) in enumerate((("title", "Song:"), ("artist", "Artist:"), ("link", "YouTube link:"))):
			ttk.Label(f, text=text).grid(row=r, column=0, sticky="w", pady=2)
			e = ttk.Entry(f, textvariable=v[k], width=60)
			e.grid(row=r, column=1, sticky="we")
			if r == 0:
				e.focus_set()
		done = tk.BooleanVar(value=bool(x.get("in_game")))
		ttk.Checkbutton(f, text="Already in game", variable=done).grid(row=3, column=1, sticky="w", pady=2)

		def ok(ev=None):
			if not v["title"].get().strip():
				messagebox.showerror(APP_NAME, "Give the song a name.", parent=w)
				return
			x.update({k: v[k].get().strip() for k in v}, in_game=done.get())
			if new:
				x.update(added_by=git_user(), added=today())
				p["songs"].append(x)
			self.save_plans()
			if self.cur_plan is p:
				self.fill_plan_songs()
			self.fill_plans()
			self.fill_station_queue()
			if new and self.cur_plan is p:
				iid = str(len(p["songs"]) - 1)
				self.plan_songs.selection_set(iid)
				self.plan_songs.see(iid)
			w.destroy()
			if plan is not None:
				self.after_idle(self.show_station)
		w.bind("<Return>", ok)
		bf = ttk.Frame(f)
		bf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def plan_remove_songs(self):
		rows = self._plan_song_rows()
		if not rows or not messagebox.askyesno(APP_NAME, f"Take {len(rows)} song{'s' if len(rows) != 1 else ''} out of {self.cur_plan.get('title')}?"):
			return
		for i in reversed(rows):
			del self.cur_plan["songs"][i]
		self.plan_songs.selection_set(())
		self.save_plans()
		self.fill_plan_songs()

	def plan_move_songs(self, d):
		rows = self._plan_song_rows()
		songs = self.cur_plan["songs"] if self.cur_plan else []
		if not rows or (d < 0 and rows[0] == 0) or (d > 0 and rows[-1] == len(songs) - 1):
			return
		for i in (rows if d < 0 else reversed(rows)):
			songs[i], songs[i + d] = songs[i + d], songs[i]
		self.plan_songs.selection_set(())
		self.fill_plan_songs()
		self.plan_songs.selection_set([str(i + d) for i in rows])
		self.plan_songs.see(str(rows[0] + d))
		self.save_plans()

	def plan_toggle_done(self):
		rows = self._plan_song_rows()
		if not rows:
			return
		songs = self.cur_plan["songs"]
		val = not all(songs[i].get("in_game") for i in rows)
		for i in rows:
			songs[i]["in_game"] = val
		self.save_plans()
		self.fill_plan_songs()

	def _plans(self):
		return [self.plans[int(i)] for i in self.plan_tree.selection()]

	def _plan(self):
		sel = self._plans()
		return sel[0] if sel else None

	def mod_choices(self):
		"""{label: folder} of the RR music mods (and '(not decided)')."""
		out = {UNDECIDED: ""}
		for r in self.rr_mods() or [m.root for m in self.view_mods]:
			out[f"{self.short_name(os.path.basename(r))}  ({os.path.basename(r)})"] = os.path.basename(r)
		for key in self.mod_meta:
			if key.startswith(PLANNED_MOD) and not self.mod_exists(key):
				out[f"{self.short_name(key)}  (planned, no folder yet)"] = key
		for entry in getattr(self, "catalog", {}).values():
			key = entry.get("mod", "")
			if key and not self.mod_exists(key):
				out[f"{self.short_name(key)}  (not installed)"] = key
		return out

	def plan_menu(self, ev):
		"""Right-click on a plan: which music mod it goes in, a new (planned) music mod, the music mod's name / colour."""
		row = self.plan_tree.identify_row(ev.y)
		if not row:
			return
		if row not in self.plan_tree.selection():
			self.plan_tree.selection_set(row)
		plans = self._plans()
		cur = {p.get("mod", "") for p in plans}
		m = tk.Menu(self, tearoff=0)
		m.add_command(label=f"Music mod of {plans[0].get('title') if len(plans) == 1 else f'{len(plans)} plans'}:", state="disabled")
		var = tk.StringVar(value=next(iter(cur)) if len(cur) == 1 else "\0")
		self._menu_var = var
		for label, key in self.mod_choices().items():
			m.add_radiobutton(label="  " + label, variable=var, value=key, foreground=self.mod_colour(key) if key else "#777",
							  command=lambda k=key: self.set_plan_mod(plans, k))
		m.add_separator()
		m.add_command(label="New music mod (planned)...", command=lambda: self.edit_mod_meta(None, plans))
		if len(cur) == 1 and next(iter(cur)):
			key = next(iter(cur))
			m.add_command(label=f"Name / colour of {self.short_name(key)}...", command=lambda: self.edit_mod_meta(key))
			if not self.mod_exists(key):
				m.add_command(label=f"Make {self.short_name(key)} now (New music mod...)", command=lambda: self.new_mod(planned=key))
		m.tk_popup(ev.x_root, ev.y_root)

	def set_plan_mod(self, plans, key):
		for p in plans:
			p["mod"] = key
		self.save_plans()
		self.fill_plans()
		if self.cur_plan in plans and self.plan_pane.winfo_ismapped():
			self.show_plan()
		self.status(f"{len(plans)} plan{'s' if len(plans) != 1 else ''} -> {self.short_name(key) if key else UNDECIDED}.")

	def edit_mod_meta(self, key, plans=None):
		"""A music mod's short name and colour; key None = a new planned music mod (no folder yet), for these plans."""
		w = tk.Toplevel(self)
		w.title("New music mod (planned)" if key is None else f"Music mod: {self.short_name(key)}")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=10)
		f.pack()
		name = tk.StringVar(value="" if key is None else self.short_name(key))
		colour = {"c": MOD_COLOURS[(len(self.rr_mods()) + len(self.mod_meta)) % len(MOD_COLOURS)] if key is None else self.mod_colour(key)}
		ttk.Label(f, text="Name (short, for the lists):").grid(row=0, column=0, sticky="w", pady=2)
		e = ttk.Entry(f, textvariable=name, width=36)
		e.grid(row=0, column=1, columnspan=2, sticky="we")
		e.focus_set()
		ttk.Label(f, text="Colour:").grid(row=1, column=0, sticky="w", pady=2)
		sw = tk.Label(f, text="  ■ " + (name.get() or "example") + "  ", fg=colour["c"], font="om_bold", relief="groove")
		sw.grid(row=1, column=1, sticky="w")
		name.trace_add("write", lambda *_: sw.config(text="  ■ " + (name.get() or "example") + "  "))

		def pick():
			c = colorchooser.askcolor(colour["c"], parent=w, title="Colour of the music mod")[1]
			if c:
				colour["c"] = c
				getattr(self.app, "feedback", lambda *_: None)("colour")
				sw.config(fg=c)
		ttk.Button(f, text="Colour...", command=pick).grid(row=1, column=2, sticky="w", padx=4)
		pal = ttk.Frame(f)
		pal.grid(row=2, column=1, columnspan=2, sticky="w")
		for c in MOD_COLOURS + ("#c62828", "#558b2f", "#4527a0", "#ef6c00", "#37474f"):
			b = tk.Label(pal, text="■", fg=c, font="om_big", cursor="hand2")
			b.pack(side="left")
			b.bind("<Button-1>", lambda ev, c=c: (colour.update(c=c), sw.config(fg=c)))
		if key is None:
			ttk.Label(f, text="A music mod that isn't made yet: plans can go in it now; Make ... now (right-click) or\n"
							  "New music mod... makes its folder later, and its plans follow.", foreground="#777").grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

		def ok(ev=None):
			n = name.get().strip()
			if not n:
				messagebox.showerror(APP_NAME, "Give it a name.", parent=w)
				return
			k = key
			if k is None:
				k = PLANNED_MOD + slug(n)
				if k in self.mod_meta:
					messagebox.showerror(APP_NAME, f"There's already a planned music mod called {n}.", parent=w)
					return
				self.mod_meta[k] = {"added_by": git_user(), "added": today()}
			self.mod_meta.setdefault(k, {}).update(name=n, colour=colour["c"])
			w.destroy()
			if plans:
				self.set_plan_mod(plans, k)
			else:
				self.save_plans()
				self.refresh_names()
		w.bind("<Return>", ok)
		bf = ttk.Frame(f)
		bf.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def refresh_names(self):
		"""After a name / colour change: the mod list, legend, stations and plans."""
		label = self.mod_var.get()
		root = self._mods.get(label)
		self.fill_mods()
		if root:
			self.open_mod(root)
		if self.cur_plan and self.plan_pane.winfo_ismapped():
			self.show_plan()

	def adopt_planned(self, folder, name):
		"""A new music mod made for a planned one: its plans, name and colour go to the real folder."""
		short = lambda n: re.sub(r"^revolution reali[sz]ed music\s*[:\-]\s*", "", n or "", flags=re.I).strip().lower()
		key = self._adopt or next((k for k, x in self.mod_meta.items() if k.startswith(PLANNED_MOD) and short(x.get("name")) == short(name)), None)
		self._adopt = None
		if not key or key not in self.mod_meta:
			return
		self.mod_meta[folder] = self.mod_meta.pop(key)
		for p in self.plans:
			if p.get("mod") == key:
				p["mod"] = folder
		self.save_plans()

	def attach_plans(self):
		plans = self._plans()
		if not plans:
			messagebox.showinfo(APP_NAME, "Pick one or more planned stations first (Ctrl / Shift click for several).")
			return
		choices = self.mod_choices()
		w = tk.Toplevel(self)
		w.title("Attach to music mod")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=10)
		f.pack()
		ttk.Label(f, text=f"Music mod of {len(plans)} planned station{'s' if len(plans) != 1 else ''}:").pack(anchor="w")
		cur = {p.get("mod", "") for p in plans}
		v = tk.StringVar(value=next((k for k, x in choices.items() if len(cur) == 1 and x in cur), UNDECIDED))
		ttk.Combobox(f, textvariable=v, values=list(choices), state="readonly", width=50).pack(pady=4)

		def ok():
			for p in plans:
				p["mod"] = choices[v.get()]
			self.save_plans()
			self.fill_plans()
			if self.cur_plan in plans and self.plan_pane.winfo_ismapped():
				self.show_plan()
			w.destroy()
			self.status(f"{len(plans)} plans attached to {v.get()}.")
		ttk.Button(f, text="OK", command=ok).pack(side="right")

	def edit_plan(self, new=False):
		plan = {"mod": os.path.basename(self.mod.root) if self.mod and len(self.view_mods) == 1 else "", "title": "", "token": "",
				"status": STATUSES[0], "theme": "", "songs": [], "notes": "", "added_by": git_user(), "added": today()} if new else self._plan()
		if plan is None:
			return
		choices = self.mod_choices()
		w = tk.Toplevel(self)
		w.title("Planned station")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=10)
		f.pack(fill="both", expand=True)
		v = {k: tk.StringVar(value=plan.get(k, "")) for k in ("title", "token", "status", "theme")}
		v["mod"] = tk.StringVar(value=next((k for k, x in choices.items() if x == plan.get("mod", "")), UNDECIDED))
		rows = (("title", "Name:"), ("mod", "Music mod:"), ("token", "Token (optional):"), ("status", "Status:"), ("theme", "Theme / sound:"))
		for r, (k, text) in enumerate(rows):
			ttk.Label(f, text=text).grid(row=r, column=0, sticky="w", pady=2)
			if k in ("status", "mod"):
				ttk.Combobox(f, textvariable=v[k], values=STATUSES if k == "status" else list(choices), state="readonly",
							 width=24 if k == "status" else 50).grid(row=r, column=1, sticky="w")
			else:
				ttk.Entry(f, textvariable=v[k], width=70).grid(row=r, column=1, sticky="we")
		ttk.Label(f, text="Songs (one per line: Title - Artist | link; ✓ at the start = already in game):").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
		sf = ttk.Frame(f)
		sf.grid(row=6, column=0, columnspan=2, sticky="nsew")
		songs = tk.Text(sf, width=96, height=16, font="om_body", wrap="none")
		ys = ttk.Scrollbar(sf, command=songs.yview)
		songs.config(yscrollcommand=ys.set)
		songs.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		songs.insert("1.0", "\n".join(song_line(x) for x in plan.get("songs", [])))
		ttk.Label(f, text="Notes:").grid(row=7, column=0, sticky="w", pady=(6, 0))
		notes = tk.Text(f, width=96, height=4, font="om_body")
		notes.grid(row=8, column=0, columnspan=2, sticky="we")
		notes.insert("1.0", plan.get("notes", ""))

		def ok():
			if not v["title"].get().strip():
				messagebox.showerror(APP_NAME, "Give it a name.", parent=w)
				return
			for k in ("title", "token", "status", "theme"):
				plan[k] = v[k].get().strip()
			plan["mod"] = choices[v["mod"].get()]
			old = {plan_song(x)["title"].lower(): plan_song(x) for x in plan.get("songs", [])}
			plan["songs"] = []
			for l in songs.get("1.0", "end").splitlines():
				if l.strip():
					x = parse_song_line(l.strip())
					was = old.get(x["title"].lower(), {})
					x.update({k: was[k] for k in ("id", "added_by", "added", "source") if k in was} or {"added_by": git_user(), "added": today()})
					plan["songs"].append(x)
			plan["notes"] = notes.get("1.0", "end").strip()
			if new:
				self.plans.append(plan)
			self.save_plans()
			self.fill_plans()
			w.destroy()
			if plan is self.cur_plan:
				self.show_plan()
		bf = ttk.Frame(f)
		bf.grid(row=9, column=0, columnspan=2, sticky="e", pady=(8, 0))
		ttk.Button(bf, text="Save", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def delete_plan(self):
		plans = self._plans()
		if plans and messagebox.askyesno(APP_NAME, f"Delete {len(plans)} plan{'s' if len(plans) != 1 else ''} ({', '.join(p.get('title', '') for p in plans[:4])})?"):
			for p in plans:
				self.plans.remove(p)
			if self.cur_plan in plans:
				self.cur_plan = None
				self.show_station()
			self.save_plans()
			self.fill_plans()

	def import_sheet(self):
		"""The RR spreadsheet's Music tab: stations that no RR music mod has yet become planned stations (with their
		songs); plans already there get the songs they don't have yet."""
		import csv
		import io
		import urllib.request
		url = self.app.config.get("music_sheet_csv", SHEET_CSV)
		try:
			with urllib.request.urlopen(url, timeout=30) as r:
				text = r.read().decode("utf-8")
		except Exception as ex:
			messagebox.showerror(APP_NAME, f"Can't read the spreadsheet:\n{url}\n\n{ex}")
			return
		self.apply_sheet(parse_sheet(list(csv.reader(io.StringIO(text)))))

	def apply_sheet(self, stations):
		in_game = [(st.title or t, m.name) for m in (self.get_mod(r) for r in self.rr_mods()) for t, st in m.stations.items()]
		added, merged, skipped = [], 0, []
		for s in stations:
			hit = next((x for x in in_game if same_title(x[0], s["title"])), None)
			if hit:
				skipped.append(f"{s['title']} (= {hit[0]} in {hit[1]})")
				continue
			plan = next((p for p in self.plans if same_title(p.get("title"), s["title"])), None)
			if plan is None:
				plan = {"mod": "", "title": s["title"], "token": "", "status": "Collecting songs" if s["songs"] else "Idea",
						"theme": s["theme"], "songs": [], "notes": "From the RR spreadsheet (Music tab).",
						"added_by": git_user(), "added": today(), "source": "spreadsheet"}
				self.plans.append(plan)
				added.append(s["title"])
			have = {plan_song(x)["title"].lower() for x in plan.get("songs", [])}
			new = [dict(x, added_by=git_user(), added=today(), source="spreadsheet") for x in s["songs"] if x["title"].lower() not in have]
			plan["songs"] = [plan_song(x) for x in plan.get("songs", [])] + new
			if new and plan.get("title") not in added:
				merged += len(new)
			if not plan.get("theme") and s["theme"]:
				plan["theme"] = s["theme"]
		self.save_plans()
		self.fill_plans()
		msg = (f"{len(added)} new planned stations, {merged} new songs in plans already there. "
			   f"{len(skipped)} stations of the sheet are already in game.")
		self.status(msg)
		messagebox.showinfo(APP_NAME, msg + ("\n\nNew: " + ", ".join(added) if added else "")
							+ "\n\nAlready in game: " + "; ".join(skipped[:30]) + "\n\nAttach the new ones to a music mod with Attach to music mod...")
		return added, merged, skipped

	def plan_to_station(self):
		plan = self._plan()
		if not plan:
			messagebox.showinfo(APP_NAME, "Pick a planned station first.")
			return
		iid = f"{plan.get('mod')}|{plan.get('token')}"
		if iid in getattr(self, "_missing_music", {}):
			messagebox.showinfo(APP_NAME, "This station has already been made. Use Pull station updates or Get missing music mods above.", parent=self)
			return
		if plan.get("mod") and not self.mod_exists(plan["mod"]):
			if messagebox.askyesno(APP_NAME, f"{self.short_name(plan['mod'])} is only planned: it has no folder yet.\n\nMake the music mod now?"):
				self.new_mod(planned=plan["mod"])
			return
		if plan.get("status") == "Made" and self.st_tree.exists(iid):
			self.st_tree.selection_set(iid)
			self.st_tree.see(iid)
			return
		self.new_station(plan)
