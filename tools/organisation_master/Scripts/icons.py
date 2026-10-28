"""Task icons: the sprite sheets in tools/organisation_master/icons/ - one per theme, the same icon ids in each;
each set's theme_icon_sets.json says which sheet goes with which theme (Classic uses the Revolution Realised sheet).
Two sets (the picker's pages): the task icons, and the alternate-history ones in icons/alt_history/ (ids "alt_...")."""
import json
import os
import tkinter as tk
from tkinter import ttk

import ui

DIR = None  # set by Organisation Master: tools/organisation_master/icons
MOD_ROOT = None  # Country Master's mod-first flag lookup for generated flag-pin icons.
FALLBACK = "revolution-realised"
CATALOGS = (("Task icons", ""), ("Alternate history", "alt_history"))  # (page name, folder under icons/)
_sets = {}       # catalog folder -> {theme id: {sheet, manifest}}
_manifests = {}  # (catalog, theme id) -> manifest
_sheets = {}
_cache = {}


def _folder(cat):
	return os.path.join(DIR, cat) if cat else DIR


def _load_sets(cat=""):
	if cat not in _sets and DIR:
		try:
			_sets[cat] = json.load(open(os.path.join(_folder(cat), "theme_icon_sets.json"), encoding="utf-8"))
		except (OSError, ValueError):
			_sets[cat] = {}
	return _sets.get(cat, {})


def set_id(cat=""):
	"""The sheet of this set for the theme in use."""
	sets = _load_sets(cat)
	tid = ui.THEME["t"].get("icon_theme_id") or ui.THEME["t"].get("id") or ""
	return tid if tid in sets else FALLBACK if FALLBACK in sets else next(iter(sets), None)


def manifest(sid=None, cat=""):
	sid = sid or set_id(cat)
	key = (cat, sid)
	if sid and key not in _manifests:
		try:
			_manifests[key] = json.load(open(os.path.join(_folder(cat), _load_sets(cat)[sid]["manifest"]), encoding="utf-8"))
		except (OSError, ValueError, KeyError):
			_manifests[key] = {"icons": []}
	return _manifests.get(key, {"icons": []})


def catalogs():
	"""The sets that are there: [(name, folder)]."""
	return [(n, c) for n, c in CATALOGS if _load_sets(c)] + ([("Regions & continents", "__regions__")] if DIR else [])


def catalog_of(icon_id):
	"""Which set an icon id is in."""
	if str(icon_id or "").startswith("region:"):
		return "__regions__"
	for _, c in catalogs():
		if c == "__regions__":
			continue
		if any(i["id"] == icon_id for i in manifest(cat=c).get("icons", [])):
			return c
	return None


def _components(alpha, cut=40):
	"""The separate shapes of a sheet (8-connected, from its transparency): [(left, top, right, bottom, pixels)]."""
	import numpy as np
	mask = alpha > cut
	parent = []

	def find(i):
		while parent[i] != i:
			parent[i] = parent[parent[i]]
			i = parent[i]
		return i
	runs, prev = [], []  # runs: (y, x0, x1, id)
	for y in range(mask.shape[0]):
		row = mask[y].astype(np.int8)
		d = np.diff(np.concatenate(([0], row, [0])))
		starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
		cur = []
		j = 0
		for x0, x1 in zip(starts.tolist(), ends.tolist()):
			i = len(parent)
			parent.append(i)
			while j < len(prev) and prev[j][2] < x0 - 1:
				j += 1
			k = j
			while k < len(prev) and prev[k][1] <= x1 + 1:
				a, b = find(prev[k][3]), find(i)
				if a != b:
					parent[b] = a
				k += 1
			run = (y, x0, x1, i)
			cur.append(run)
			runs.append(run)
		prev = cur
	boxes = {}
	for y, x0, x1, i in runs:
		r = find(i)
		b = boxes.get(r)
		n = x1 - x0 + 1
		boxes[r] = [x0, y, x1 + 1, y + 1, n] if b is None else [min(b[0], x0), min(b[1], y), max(b[2], x1 + 1), max(b[3], y + 1), b[4] + n]
	return list(boxes.values())


def _split(values, k):
	"""Centres of k groups of 1-D values (split at the k-1 widest gaps)."""
	v = sorted(values)
	if len(v) < k:
		return None
	gaps = sorted(range(1, len(v)), key=lambda i: v[i] - v[i - 1], reverse=True)[:k - 1]
	cuts = sorted(gaps)
	groups, last = [], 0
	for c in cuts + [len(v)]:
		groups.append(v[last:c])
		last = c
	return [sum(g) / len(g) for g in groups]


def _grid(values, weights, k, size):
	"""Centres of k evenly spaced rows (or columns) fitted to the shapes' centres: the same pitch all the way, so icons
	that spill into the next cell (a tall microphone, a long brush) can't throw the rows off."""
	import numpy as np
	v, w = np.array(values, float), np.array(weights, float)
	if len(v) < k:
		return None
	base = size / k
	best = None
	for pitch in np.arange(base * 0.85, base * 1.06, 0.5):
		for first in np.arange(pitch * 0.25, pitch * 0.95, 1.0):
			centres = first + pitch * np.arange(k)
			if centres[-1] > size:
				break
			d = np.minimum(np.abs(v[:, None] - centres[None, :]).min(1), pitch / 2)
			score = float((d * w).sum())
			if best is None or score < best[0]:
				best = (score, centres)
	return [float(c) for c in best[1]] if best else None


FIT_VERSION = 2  # (the .fit.json caches of an older way of measuring are measured again)


def fit_boxes(sid, cat=""):
	"""Where each icon really is on the sheet (its manifest's boxes can be off): {id: box}. Measured once from the
	sheet's transparency - every shape goes to the nearest grid cell - and kept next to it (<sheet>.fit.json)."""
	m = manifest(sid, cat)
	sheet = os.path.join(_folder(cat), _load_sets(cat)[sid]["sheet"])
	cache = sheet + ".fit.json"
	try:
		if os.path.getmtime(cache) >= os.path.getmtime(sheet):
			got = json.load(open(cache, encoding="utf-8"))
			if got.get("version") == FIT_VERSION:
				return got["boxes"]
	except (OSError, ValueError):
		pass
	import numpy as np
	from PIL import Image
	cols, rows = m.get("columns", 10), m.get("rows", 8)
	alpha = np.array(Image.open(sheet).convert("RGBA"))[:, :, 3]
	comps = [c for c in _components(alpha) if c[4] >= 60]  # (no stray specks)
	big = [c for c in comps if c[4] >= 400]
	ys = _grid([(c[1] + c[3]) / 2 for c in big], [c[4] for c in big], rows, alpha.shape[0])
	xs = _grid([(c[0] + c[2]) / 2 for c in big], [c[4] for c in big], cols, alpha.shape[1])
	if not ys or not xs:
		return {}
	# a shape spanning two cells (two icons touching on the sheet): cut it halfway between the cells' centres
	pieces = []
	for c in comps:
		boxes = [list(c[:4])]
		for axis, centres in ((0, xs), (1, ys)):
			out = []
			for b in boxes:
				inside = [v for v in centres if b[axis] < v < b[axis + 2]]
				cuts = [(inside[i] + inside[i + 1]) / 2 for i in range(len(inside) - 1)]
				lo = b[axis]
				for cut_at in cuts + [b[axis + 2]]:
					nb = list(b)
					nb[axis], nb[axis + 2] = int(lo), int(cut_at)
					out.append(nb)
					lo = cut_at
			boxes = out
		pieces += [b + [c[4]] for b in boxes]
	comps = pieces
	cells = {}
	for c in comps:
		cy, cx = (c[1] + c[3]) / 2, (c[0] + c[2]) / 2
		r = min(range(rows), key=lambda i: abs(ys[i] - cy))
		k = min(range(cols), key=lambda i: abs(xs[i] - cx))
		b = cells.get((r, k))
		cells[(r, k)] = c[:4] if b is None else [min(b[0], c[0]), min(b[1], c[1]), max(b[2], c[2]), max(b[3], c[3])]
	out = {}
	for ic in m.get("icons", []):
		b = cells.get((ic.get("row"), ic.get("column")))
		if b:
			out[ic["id"]] = b
	try:
		json.dump({"version": FIT_VERSION, "boxes": out}, open(cache, "w", encoding="utf-8"))
	except OSError:
		pass
	return out


_fits = {}


def all_icons(cat=None):
	"""[(id, label)] of a set (None: every set), in the sheet's order."""
	out = []
	for _, c in catalogs():
		if cat is None or c == cat:
			if c == "__regions__":
				import region_icons
				out += region_icons.all_icons(DIR)
			else:
				out += [(i["id"], i.get("label", i["id"])) for i in manifest(cat=c).get("icons", [])]
	return out


def label(icon_id):
	if str(icon_id or "").startswith("flag:"):
		return "Flag icon: " + icon_id[5:]
	return next((l for i, l in all_icons() if i == icon_id), icon_id or "")


def image(icon_id, size):
	"""The icon (of whichever set it's in, for the theme in use) as a PhotoImage of size x size (cached), or ""."""
	if str(icon_id or "").startswith("region:"):
		import region_icons
		return region_icons.image(DIR, icon_id[7:], size) if DIR else ""
	if str(icon_id or "").startswith("flag:"):
		import flag_icons
		root = MOD_ROOT or (os.path.dirname(os.path.dirname(os.path.dirname(DIR))) if DIR else None)
		return flag_icons.image(root, icon_id[5:], size) if root else ""
	cat = catalog_of(icon_id) if icon_id else None
	if cat is None:
		return ""
	sid = set_id(cat)
	if not sid:
		return ""
	key = (cat, sid, icon_id, size)
	if key in _cache:
		return _cache[key]
	if (cat, sid) not in _fits:
		_fits[(cat, sid)] = fit_boxes(sid, cat)
	box = _fits[(cat, sid)].get(icon_id) or next((i["box"] for i in manifest(sid, cat).get("icons", []) if i["id"] == icon_id), None)
	if not box:
		return ""
	from PIL import Image, ImageTk
	if (cat, sid) not in _sheets:
		_sheets[(cat, sid)] = Image.open(os.path.join(_folder(cat), _load_sets(cat)[sid]["sheet"])).convert("RGBA")
	im = _sheets[(cat, sid)].crop(tuple(box))
	bb = im.getbbox()  # (trim the empty margin so the symbol fills the small size)
	if bb:
		im = im.crop(bb)
	im.thumbnail((size, size), Image.LANCZOS)
	out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	out.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
	_cache[key] = ImageTk.PhotoImage(out)
	return _cache[key]


def pick(parent, title, current=None, on_pick=None):
	"""A window with every icon (search, hover for its name); on_pick(id) - None for the default."""
	w = tk.Toplevel(parent)
	w.title(title)
	w.transient(parent.winfo_toplevel())
	f = ttk.Frame(w, padding=10)
	f.pack(fill="both", expand=True)
	top = ttk.Frame(f)
	top.pack(fill="x")
	ttk.Label(top, text="🔍").pack(side="left")
	q = tk.StringVar()
	e = ttk.Entry(top, textvariable=q, width=24, font="TkDefaultFont")
	e.pack(side="left", padx=4)
	e.focus_set()
	name = ttk.Label(top, text=f"Now: {label(current)}" if current else "Now: the default", style="Muted.TLabel", width=30, anchor="w")
	name.pack(side="left", padx=10)
	ttk.Button(top, text="Default", command=lambda: (w.destroy(), on_pick and on_pick(None))).pack(side="right")
	def choose_flag():
		import flag_icons
		root = MOD_ROOT or (os.path.dirname(os.path.dirname(os.path.dirname(DIR))) if DIR else None)
		if root:
			flag_icons.pick(w, root, current, lambda icon: (w.destroy(), on_pick and on_pick(icon)))
	ttk.Button(top, text="Flag Icon…", command=choose_flag).pack(side="right", padx=4)
	cats = catalogs()
	page = {"n": next((k for k, (_, c) in enumerate(cats) if c == catalog_of(current)), 0) if current else 0}
	nav = ttk.Frame(f)
	nav.pack(fill="x", pady=(8, 0))
	prev_b = ttk.Button(nav, text="◀", width=3, command=lambda: turn(-1))
	prev_b.pack(side="left")
	page_l = ttk.Label(nav, text="", style="Head.TLabel", anchor="center")
	page_l.pack(side="left", fill="x", expand=True)
	next_b = ttk.Button(nav, text="▶", width=3, command=lambda: turn(1))
	next_b.pack(side="right")
	grid = ttk.Frame(f)
	grid.pack(pady=(8, 0))
	size = ui.px(36)
	# Opening on the short region page must still leave room for the full sheets.
	for col in range(10):
		grid.columnconfigure(col, minsize=size + ui.px(6))
	for row in range(8):
		grid.rowconfigure(row, minsize=size + ui.px(6))

	def turn(d):
		page["n"] = (page["n"] + d) % max(1, len(cats))
		fill()

	def fill(*_):
		for c in grid.winfo_children():
			c.destroy()
		words = q.get().lower().split()
		if words:  # (a search looks through every page)
			page_l.config(text="Search: every page")
			shown = [(i, l) for i, l in all_icons() if all(x in f"{i} {l}".lower() for x in words)][:80]
		else:
			name_, cat = cats[page["n"]] if cats else ("", "")
			page_l.config(text=f"{name_}   ({page['n'] + 1} / {len(cats)})")
			shown = all_icons(cat)
		for b_ in (prev_b, next_b):
			b_.state(["disabled"] if words or len(cats) < 2 else ["!disabled"])
		for n, (i, l) in enumerate(shown):
			b = tk.Label(grid, image=image(i, size), cursor="hand2", relief="solid" if i == current else "flat", borderwidth=2 if i == current else 0,
						 padx=3, pady=3)
			b.grid(row=n // 10, column=n % 10)
			b.bind("<Enter>", lambda ev, l=l: name.config(text=l))
			b.bind("<Leave>", lambda ev: name.config(text=f"Now: {label(current)}" if current else "Now: the default"))
			b.bind("<Button-1>", lambda ev, i=i: (w.destroy(), on_pick and on_pick(i)))
		if not shown:
			ttk.Label(grid, text="No icon matches.", style="Muted.TLabel").grid(row=0, column=0)
	q.trace_add("write", fill)
	fill()
	w.update_idletasks()  # (the window keeps this size: hovering or searching doesn't resize it)
	w.geometry(f"{w.winfo_reqwidth()}x{w.winfo_reqheight()}")
	w.resizable(False, False)
