"""The shared look of Organisation Master: text size (View > Text size, Ctrl + / Ctrl -), named fonts that follow
it, themes (Theme menu: tools/organisation_master/themes/<name>/theme.json), collapsible sections (click a
section's title bar), striped and sortable lists, sliders that jump to a click."""
import colorsys
import json
import os
import re
import tkinter as tk
from tkinter import ttk, font as tkfont

# named fonts: (family, size at 100%, weight)
FONTS = {
	"om_tiny": ("Segoe UI", 8, "normal"),
	"om_small": ("Segoe UI", 9, "normal"),
	"om_small_bold": ("Segoe UI", 9, "bold"),
	"om_body": ("Segoe UI", 10, "normal"),
	"om_bold": ("Segoe UI", 10, "bold"),
	"om_head": ("Segoe UI", 10, "bold"),
	"om_title": ("Segoe UI", 14, "bold"),
	"om_big": ("Segoe UI", 15, "normal"),
	"om_mono": ("Consolas", 10, "normal"),
}
SCALES = (("Small", 0.85), ("Normal", 1.0), ("Large", 1.15), ("Larger", 1.3), ("Huge", 1.5))
HEAD_BG, HEAD_FG, HEAD_HOVER = "#e4e9f0", "#1f2d3d", "#d5dde8"
STRIPE = "#f4f6f9"
MUTED = "#667"
# Classic: the native Windows look (the colours the tools were drawn with)
CLASSIC = {"name": "Classic", "dark": False, "colors": {
	"background": "#f0f0f0", "surface": "#ffffff", "foreground": "#000000", "muted": MUTED, "border": "#a0a0a0", "copper": "#1f5fa8",
	"header_background": HEAD_BG, "header_foreground": HEAD_FG, "header_hover": HEAD_HOVER, "stripe": STRIPE,
	"selection_background": "#0078d7", "selection_foreground": "#ffffff", "button_background": "#e1e1e1", "button_foreground": "#000000",
	"button_active": "#e5f1fb", "input_background": "#ffffff", "input_foreground": "#000000", "age_green": "#2e7d32",
	"age_yellow": "#b58900", "age_red": "#c62828", "blocked_background": "#fbe3e3"}}
P = dict(CLASSIC["colors"])  # the palette in use
THEME = {"t": CLASSIC}
THEME_HOOKS = []  # called after a theme change (redraw what has theme pictures, e.g. task icons)
KEEP_COLOURS = [False]  # (Culture / Country Master: their colours - cultures, countries, swatches - stay as they are)
_themes = {}  # name -> theme (Classic + tools/organisation_master/themes/*/theme.json)
_imgs = {}

_scale = [1.0]
_fonts = {}
_sections = []


def init(root, scale=1.0):
	for name, (family, size, weight) in FONTS.items():
		if name not in tkfont.names(root):  # (kept: a Font object deletes its font when it's forgotten)
			_fonts[name] = tkfont.Font(root, name=name, family=family, size=size, weight=weight)
	set_scale(root, scale)
	install_selection_navigation(root)
	install_type_to_find(root)


_find = {"text": "", "at": 0.0}


def _row_label(tree, iid):
	"""A row's name as you'd type it: its text (or first column), without leading icons / stars."""
	text = str(tree.item(iid, "text") or "")
	if not text.strip() and "tree" not in str(tree.cget("show")):
		vals = tree.item(iid, "values")
		text = str(vals[0]) if vals else ""
	i = 0
	while i < len(text) and not text[i].isalnum():
		i += 1
	return text[i:].lower()


def _visible_rows(tree, parent=""):
	for iid in tree.get_children(parent):
		yield iid
		if tree.item(iid, "open"):
			yield from _visible_rows(tree, iid)


def _type_to_find(event):
	"""Any list: a letter jumps to the first row starting with it (again: the next one); letters typed quickly narrow it
	("un" -> United...). Rows inside closed groups are skipped."""
	if event.state & (0x4 | 0x20000) or not event.char or not event.char.isalpha():  # (Ctrl / Alt: shortcuts; 0x8 is Num Lock on Windows)
		return
	import time
	tree, ch, now = event.widget, event.char.lower(), time.monotonic()
	typed = _find["text"] + ch if now - _find["at"] < 0.8 and _find.get("tree") == str(tree) else ch
	_find.update(text=typed, at=now, tree=str(tree))
	rows = list(_visible_rows(tree))
	if not rows:
		return
	cur = tree.focus() or (tree.selection() or [""])[0]
	start = rows.index(cur) if cur in rows else -1
	same = len(set(typed)) == 1 and len(typed) > 1  # ("uuu": the next U each time, like Windows Explorer)
	want = ch if same else typed
	first = 1 if (len(typed) == 1 or same) else 0  # (one letter: start after the current row; more: it may still fit)
	for k in range(len(rows)):
		iid = rows[(start + first + k) % len(rows)]
		if _row_label(tree, iid).startswith(want):
			tree.selection_set(iid)
			tree.focus(iid)
			tree.see(iid)
			return "break"


def install_type_to_find(root):
	if getattr(root, "_type_to_find_installed", False):
		return
	root._type_to_find_installed = True
	root.bind_class("Treeview", "<KeyPress>", _type_to_find, add="+")


def _selection_edge(event, right):
	"""Plain arrows collapse selected text; modified arrows keep Tk's selection/navigation."""
	if event.state & (0x1 | 0x4 | 0x8 | 0x80 | 0x20000):  # Shift, Ctrl, Alt / AltGr
		return
	w = event.widget
	try:
		if str(w.cget("state")) == "disabled":
			return
		if w.winfo_class() == "Text":
			selection = w.tag_ranges("sel")
			if not selection:
				return
			# Tk's cursor helper also clears the selection, scrolls into view and
			# adds the normal undo separator without changing the text.
			w.tk.call("tk::TextSetCursor", w, selection[-1] if right else selection[0])
		else:
			if not w.selection_present():
				return
			position = w.index("sel.last" if right else "sel.first")
			w.tk.call("tk::EntrySetCursor", w, position)
		return "break"
	except tk.TclError:
		return


def install_selection_navigation(root):
	"""A binding before native text classes, also applied to dialogs created later."""
	if getattr(root, "_selection_navigation_installed", False):
		return
	root._selection_navigation_installed = True
	tag = "OM.SelectionNavigation"
	root.bind_class(tag, "<KeyPress-Left>", lambda event: _selection_edge(event, False))
	root.bind_class(tag, "<KeyPress-Right>", lambda event: _selection_edge(event, True))
	classes = {"Text", "Entry", "TEntry", "Spinbox", "TSpinbox", "TCombobox"}
	def prepare(event=None, widget=None):
		w = widget if widget is not None else event.widget
		if isinstance(w, str):
			return
		if w.winfo_class() in classes:
			tags = w.bindtags()
			if tag not in tags:
				index = tags.index(w.winfo_class()) if w.winfo_class() in tags else 0
				w.bindtags(tags[:index] + (tag,) + tags[index:])
		if widget is not None:
			for child in w.winfo_children():
				prepare(widget=child)
	root.bind_all("<Map>", prepare, add="+")
	prepare(widget=root)


def scale():
	return _scale[0]


def px(n):
	"""A size in pixels at the current text size."""
	return int(round(n * _scale[0]))


def drag_autoscroll(tree, event, after=None):
	"""While dragging (call it on every motion): held near the top / bottom edge, the list slowly scrolls by itself, and
	keeps going while the pointer rests there (faster past the edge). after(): called after each step and each wheel
	scroll (e.g. to show the new drop target). drag_autoscroll_stop when the drag ends."""
	zone, h = px(28), tree.winfo_height()
	st = tree.__dict__.setdefault("_autoscroll", {"job": None})
	st["dir"] = -1 if event.y < zone else 1 if event.y > h - zone else 0
	st["fast"] = event.y < 0 or event.y > h
	tree._drag_scrolled = after

	def step():
		st["job"] = None
		if not st["dir"] or not tree.winfo_exists():
			return
		tree.yview_scroll(st["dir"], "units")
		if after:
			after()
		st["job"] = tree.after(60 if st["fast"] else 150, step)

	if st["dir"] and st["job"] is None:
		st["job"] = tree.after(200, step)  # (a short pause first: passing the edge doesn't scroll)
	elif not st["dir"] and st["job"] is not None:
		tree.after_cancel(st["job"])
		st["job"] = None


def drag_autoscroll_stop(tree):
	st = tree.__dict__.get("_autoscroll")
	if st and st["job"] is not None:
		tree.after_cancel(st["job"])
		st["job"] = None
	tree._drag_scrolled = None


def drag_wobble(tree, event, rows, origin=None):
	"""Animate an item preview only after the caller's drag threshold has been crossed."""
	from drag_feedback import DragWobble
	if not hasattr(tree, "_drag_wobble"):
		tree._drag_wobble = DragWobble(tree, P, scale())
	elif tree._drag_wobble.canvas is None:
		tree._drag_wobble.palette, tree._drag_wobble.scale = P, scale()
	tree._drag_wobble.move(event, rows, origin)


def _resize_columns(w, ratio):
	"""Columns of every list follow a text size change."""
	if isinstance(w, ttk.Treeview):
		for c in ("#0",) + tuple(w["columns"]):
			try:
				w.column(c, width=max(20, int(round(int(w.column(c, "width")) * ratio))))
			except tk.TclError:
				pass
	for c in w.winfo_children():
		_resize_columns(c, ratio)


def set_scale(root, s):
	if _scale[0] != s and _fonts:
		_resize_columns(root, s / _scale[0])
	_scale[0] = s
	for name, (family, size, weight) in FONTS.items():
		tkfont.nametofont(name, root).configure(family=family, size=max(7, round(size * s)))
	for std, size in (("TkDefaultFont", 10), ("TkTextFont", 10), ("TkHeadingFont", 10), ("TkMenuFont", 10), ("TkTooltipFont", 9)):
		try:
			tkfont.nametofont(std, root).configure(family=FONTS["om_body"][0], size=max(7, round(size * s)))
		except tk.TclError:
			pass
	st = ttk.Style(root)
	st.configure("Treeview", rowheight=px(25), font="TkDefaultFont")
	st.configure("Treeview.Heading", font="om_bold", padding=(px(4), px(3)))
	st.configure("TButton", padding=(px(8), px(3)))
	st.configure("Tool.TButton", padding=(px(6), px(2)))
	st.configure("Muted.TLabel", foreground=MUTED)
	st.configure("Head.TLabel", font="om_head")
	st.configure("Title.TLabel", font="om_title")
	st.configure("TNotebook.Tab", padding=(px(12), px(4)), font="om_bold")
	st.configure("Nav.TButton", font="om_body", anchor="w", padding=(px(10), px(6)))
	st.configure("Small.TButton", font="om_tiny", padding=(2, 0))
	st.configure("View.TRadiobutton", font="om_bold", padding=(px(10), px(4)))
	st.configure("Section.TFrame", background=HEAD_BG)


def stripe(tree):
	"""Alternate row colour: call after filling (keeps the rows' own tags). Also sorts the list again when a column
	title was clicked (sortable), and gives its row colours the theme's look."""
	if getattr(tree, "_sort", None):
		apply_sort(tree)
	theme_tree(tree)
	tree.tag_configure("odd", background=P["stripe"])

	def rows(parent=""):
		for i in tree.get_children(parent):
			yield i
			if tree.item(i, "open"):
				yield from rows(i)
	for i, iid in enumerate(rows()):
		tags = [t for t in tree.item(iid, "tags") if t != "odd"]
		if i % 2 and not any(t.startswith(NO_STRIPE) for t in tags):  # (folder rows keep their own colour)
			tags.insert(0, "odd")  # first = lowest priority: a row's own background (blocked, playing) wins
		tree.item(iid, tags=tags)


class Section(ttk.Frame):
	"""A titled block whose body folds away when its title bar is clicked (remembered per key in the config)."""

	def __init__(self, parent, title, key=None, app=None, collapsed=False, expand=True, **kw):
		super().__init__(parent, **kw)
		self.key, self.app, self.expand = key, app, expand
		hb, hf = P["header_background"], P["header_foreground"]
		self.head = tk.Frame(self, background=hb, cursor="hand2")
		self.head._om_head = True
		self.head.pack(fill="x")
		self.arrow = tk.Label(self.head, text="▾", background=hb, foreground=hf, font="om_head", width=2)
		self.arrow.pack(side="left")
		self.title = tk.Label(self.head, text=title, background=hb, foreground=hf, font="om_head", anchor="w")
		self.title.pack(side="left", pady=px(3))
		self.count = tk.Label(self.head, text="", background=hb, foreground=P["muted"], font="om_small")
		self.count.pack(side="left", padx=6)
		self.tools = tk.Frame(self.head, background=hb)  # buttons in the title bar (right)
		self.tools.pack(side="right", padx=2)
		self.head_extras = []  # (labels added to the title bar by a user of the section: coloured like the title)
		self.body = ttk.Frame(self, padding=(0, px(4), 0, px(6)))
		for w in (self.head, self.arrow, self.title, self.count):
			w.bind("<Button-1>", lambda ev: self.toggle())
			w.bind("<Enter>", lambda ev: self._hover(True))
			w.bind("<Leave>", lambda ev: self._hover(False))
		saved = (app.config.get("collapsed", {}).get(key) if app and key else None)
		self.collapsed = collapsed if saved is None else saved
		if not self.collapsed:
			self.body.pack(fill="both", expand=True)
		self.arrow.config(text="▸" if self.collapsed else "▾")
		_sections.append(self)

	def _hover(self, on):
		c = P["header_hover"] if on else P["header_background"]
		for w in (self.head, self.arrow, self.title, self.count, self.tools, *self.head_extras):
			w.config(background=c)
		for w in self.tools.winfo_children():
			if w.winfo_class() in ("Label", "Frame"):
				w.config(background=c)

	def recolour(self):
		for w in (self.head, self.arrow, self.title, self.tools, *self.head_extras):
			w.config(background=P["header_background"])
		for w in (self.arrow, self.title, *self.head_extras):
			w.config(foreground=P["header_foreground"])
		self.count.config(background=P["header_background"], foreground=P["muted"])
		for w in self.tools.winfo_children():
			if w.winfo_class() in ("Label", "Frame"):
				w.config(background=P["header_background"], foreground=P["header_foreground"]) if w.winfo_class() == "Label" else w.config(background=P["header_background"])

	def place_in(self, **kw):
		"""pack this section (expand only while it's open)."""
		self._pack = kw
		self.pack(**dict(kw, expand=self.expand and not self.collapsed))
		return self

	def toggle(self, collapsed=None):
		self.collapsed = (not self.collapsed) if collapsed is None else collapsed
		if self.collapsed:
			self.body.pack_forget()
		else:
			self.body.pack(fill="both", expand=True)
		self.arrow.config(text="▸" if self.collapsed else "▾")
		if hasattr(self, "_pack"):
			self.pack_configure(expand=self.expand and not self.collapsed)
		if self.app and self.key:
			self.app.config.setdefault("collapsed", {})[self.key] = self.collapsed
			self.app.save_config()

	def set_count(self, text):
		self.count.config(text=text)


def all_sections(collapsed):
	for s in list(_sections):
		try:
			if s.winfo_exists():
				s.toggle(collapsed)
		except tk.TclError:
			pass


NO_STRIPE = ("project", "group", "pc")
_scrollframes = []
_OWN_WHEEL = ("Treeview", "Text", "Listbox", "TCombobox", "Scrollbar", "TScrollbar")


class ScrollFrame(ttk.Frame):
	"""A page that scrolls up and down when it's taller than the window (put things in .inner). It fills the window
	when there's room, so sections that expand still do."""

	def __init__(self, parent):
		super().__init__(parent)
		bg = ttk.Style(self).lookup("TFrame", "background") or "#f0f0f0"
		self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=bg)
		self.vs = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.vs.set)
		self.vs.pack(side="right", fill="y")
		self.canvas.pack(side="left", fill="both", expand=True)
		self.inner = ttk.Frame(self.canvas)
		self.win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
		self.canvas.bind("<Configure>", lambda ev: self.update_size())
		self._last = None
		_scrollframes.append(self)
		if len(_scrollframes) == 1:
			self.bind_all("<MouseWheel>", _wheel, add="+")
		self._poll()

	def update_size(self):
		cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
		h = max(ch, self.inner.winfo_reqheight())
		if (cw, h) != self._last:
			self._last = (cw, h)
			self.canvas.itemconfigure(self.win, width=cw, height=h)
			self.canvas.configure(scrollregion=(0, 0, cw, h))

	def _poll(self):
		"""(a section opening or closing changes what the page needs: check now and then)"""
		try:
			if self.winfo_ismapped():
				self.update_size()
			self.after(300, self._poll)
		except tk.TclError:
			pass


def _wheel(ev):
	"""The mouse wheel scrolls the page, except over lists and text boxes (they scroll themselves)."""
	try:
		w = ev.widget.winfo_containing(ev.x_root, ev.y_root)
	except (tk.TclError, AttributeError):
		return
	if w is None or w.winfo_class() in _OWN_WHEEL:
		return
	while w is not None:
		for sf in _scrollframes:
			if w is sf:
				lo, hi = sf.canvas.yview()
				if hi - lo < 1:
					sf.canvas.yview_scroll(-1 if ev.delta > 0 else 1, "units")
				return
		w = w.master


# ---------------- sortable lists ----------------
def _sort_key(v):
	v = str(v).strip()
	m = re.fullmatch(r"(\d+):(\d\d)", v)
	if m:
		return (0, int(m.group(1)) * 60 + int(m.group(2)), "")
	m = re.fullmatch(r"(\d+)h (\d+)m", v)
	if m:
		return (0, int(m.group(1)) * 60 + int(m.group(2)), "")
	m = re.match(r"[×x]?(-?\d+(?:\.\d+)?)", v)
	if m and (m.end() == len(v) or not v[m.end()].isalpha()):
		return (0, float(m.group(1)), v.lower())
	return (1 if v else 2, 0, v.lower())


def apply_sort(tree):
	col, rev = tree._sort
	rows = list(tree.get_children(""))
	val = (lambda i: tree.item(i, "text")) if col == "#0" else (lambda i: tree.set(i, col))
	rows.sort(key=lambda i: _sort_key(val(i)), reverse=rev)
	for n, i in enumerate(rows):
		tree.move(i, "", n)


def sortable(tree, on_change=None):
	"""Click a column title to sort the list by it (again: the other way); stays sorted after it's filled again."""
	tree._sort = None

	def by(col):
		rev = not tree._sort[1] if tree._sort and tree._sort[0] == col else False
		tree._sort = (col, rev)
		stripe(tree)
		if on_change:
			on_change(col, rev)
	for col in ("#0",) + tuple(tree["columns"]):
		tree.heading(col, command=lambda c=col: by(c))


# ---------------- sliders ----------------
def jump_scale(scale, var, on_move=None, on_release=None):
	"""A ttk.Scale that jumps to where it's clicked (and follows the mouse while held), instead of creeping."""
	def at(ev):
		lo, hi = float(scale.cget("from")), float(scale.cget("to"))
		w = max(1, scale.winfo_width() - 16)
		var.set(lo + (hi - lo) * min(1.0, max(0.0, (ev.x - 8) / w)))
		if on_move:
			on_move(var.get())
		return "break"
	scale.bind("<Button-1>", at)
	scale.bind("<B1-Motion>", at)
	scale.bind("<ButtonRelease-1>", lambda ev: (on_release(var.get()) if on_release else None, "break")[1])


# ---------------- themes ----------------
def _rgb(c):
	try:
		r, g, b = (v // 257 for v in tk._default_root.winfo_rgb(c))
		return r, g, b
	except (tk.TclError, AttributeError):
		return None


def _hex(rgb):
	return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _mix(a, b, t):
	ra, rb = _rgb(a), _rgb(b)
	if not ra or not rb:
		return a
	return _hex([x + (y - x) * t for x, y in zip(ra, rb)])


def _lum(c):
	r = _rgb(c)
	return (0.299 * r[0] + 0.587 * r[1] + 0.114 * r[2]) / 255 if r else 0.5


NEUTRAL_FG = {"#000000", "#000", "black", "systembuttontext", "systemwindowtext", "#333", "#333333", "#1f2d3d", "#444", "#444444",
			  "#555", "#555555", "#29291e"}
MUTED_FG = {"#777", "#777777", "#666", "#666666", "#667", "#667", "#888", "#888888", "#aaa", "#aaaaaa", "#bbbbbb", "#999", "#999999"}
NEUTRAL_BG = {"systembuttonface", "#f0f0f0", "systemwindow", "white", "#ffffff", "#fff", "#f6f6f6", "systemmenu", ""}


def fg_for(c, dark=None):
	"""A text colour of the tools in the theme: plain ones become the theme's, coloured ones stay readable."""
	dark = THEME["t"].get("dark") if dark is None else dark
	k = (c or "").lower()
	if THEME["t"] is CLASSIC:
		return c
	ages = {CLASSIC["colors"]["age_green"]: "age_green", CLASSIC["colors"]["age_yellow"]: "age_yellow", CLASSIC["colors"]["age_red"]: "age_red"}
	if k in ages:
		return P[ages[k]]
	if not k or k in NEUTRAL_FG:
		return P["foreground"]
	if k in MUTED_FG:
		return P["muted"]
	if dark and _lum(c) < 0.55:  # dark colour on a dark theme: lighten it (keeps its hue)
		h, l_, sat = colorsys.rgb_to_hls(*[v / 255 for v in _rgb(c)])
		return _hex([v * 255 for v in colorsys.hls_to_rgb(h, max(l_, 0.68), min(1, sat * 0.9))])
	return c


def bg_for(c, field=False):
	"""A background colour of the tools in the theme (highlights keep a hint of their colour)."""
	k = (c or "").lower()
	if THEME["t"] is CLASSIC:
		return c
	if k == HEAD_BG.lower():
		return P["header_background"]
	if k == CLASSIC["colors"]["blocked_background"]:
		return P["blocked_background"]
	if k == STRIPE.lower():
		return P["stripe"]
	if not k or k in NEUTRAL_BG:
		return P["input_background"] if field else P["background"]
	if KEEP_COLOURS[0] and not _greyish(c):
		return c  # (a real colour: a culture, a country, a swatch)
	return _mix(c, P["surface"], 0.78 if THEME["t"].get("dark") else 0.35)


def _greyish(c):
	r = _rgb(c)
	return bool(r) and max(r) - min(r) < 18


def project_row_tag(tree, tag, colour, bold=True):
	"""Preserve a project's identity while tinting its background with the active theme."""
	classic_background = _mix(colour, "#ffffff", 0.86)
	tree.__dict__.setdefault("_om_tags", {})[tag] = (colour, classic_background)
	tree.__dict__.setdefault("_om_project_tags", set()).add(tag)
	tree.tag_configure(tag, foreground=fg_for(colour),
		background=classic_background if THEME["t"] is CLASSIC else _mix(P["copper"], P["surface"], 0.86),
		font="om_bold" if bold else "TkDefaultFont")


def theme_tree(tree):
	"""A list's row colours (tags) in the theme; the colours they were made with are kept for switching back."""
	orig = tree.__dict__.setdefault("_om_tags", {})
	for tag in tree.tk.splitlist(tree.tk.call(tree._w, "tag", "names")):
		if tag == "odd":
			continue
		if tag not in orig:
			orig[tag] = (str(tree.tag_configure(tag, "foreground") or ""), str(tree.tag_configure(tag, "background") or ""))
		f, b = orig[tag]
		kw = {}
		if f:
			kw["foreground"] = fg_for(f)
		if b:
			kw["background"] = (_mix(P["copper"], P["surface"], 0.86)
				if tag in getattr(tree, "_om_project_tags", ()) and THEME["t"] is not CLASSIC else bg_for(b))
		if kw:
			tree.tag_configure(tag, **kw)


def theme_widget(w):
	"""The theme's colours on one plain tk widget (ttk ones follow the style)."""
	# <Map> can hand over a widget's path name (a string) instead of the widget, e.g. a combobox's list # Globus
	if isinstance(w, str) or getattr(w, "_om_effect_layer", False):
		return
	try:
		cls = w.winfo_class()
	except tk.TclError:
		return
	if cls == "Toplevel":
		w.after_idle(lambda: title_bar(w))
	p = w
	while p is not None:
		if getattr(p, "_om_bar", False):
			return  # (the menu bar colours itself)
		p = getattr(p, "master", None)
	if cls not in ("Frame", "Label", "Text", "Listbox", "Canvas", "Toplevel", "Tk", "Entry", "Checkbutton", "Radiobutton", "Button", "Menu", "Message"):
		return
	o = w.__dict__.get("_om0")
	if o is None:
		o = {}
		for opt in ("background", "foreground", "insertbackground", "selectbackground", "selectforeground", "activebackground", "activeforeground"):
			try:
				o[opt] = str(w.cget(opt))
			except tk.TclError:
				pass
		w._om0 = o
		# Widgets created after launch inherit the current option-database palette.
		# Remember those as palette roles, rather than treating yesterday's dark
		# background as a deliberate custom colour when switching to a light theme.
		roles = {}
		for opt, value in o.items():
			if opt == "selectbackground":
				keys = ("selection_background", "input_background", "background")
			elif opt == "selectforeground":
				keys = ("selection_foreground", "input_foreground", "foreground")
			elif opt in ("background", "activebackground"):
				keys = ("input_background", "background", "surface", "header_background", "stripe", "button_background") if cls in ("Text", "Entry", "Listbox") else ("background", "surface", "header_background", "stripe", "input_background", "button_background")
			else:
				keys = ("foreground", "input_foreground", "muted", "header_foreground", "age_green", "age_yellow", "age_red")
			role = next((key for key in keys if value.lower() == P.get(key, "").lower()), None)
			if role and opt == "background" and cls in ("Text", "Entry", "Listbox"):
				role = "input_background"
			if role and THEME["t"] is not CLASSIC:
				roles[opt] = role
				o[opt] = CLASSIC["colors"][role]
		w._om_palette_roles = roles
	head = False
	p = w
	for _ in range(4):
		if p is None:
			break
		if getattr(p, "_om_head", False):
			head = True
			break
		p = getattr(p, "master", None)
	kw = {}
	if THEME["t"] is CLASSIC:
		kw = dict(o)
	elif cls in ("Text", "Listbox", "Entry"):
		special = o.get("background", "").lower() not in NEUTRAL_BG
		kw = {"background": bg_for(o["background"]) if special else P["input_background"], "foreground": P["input_foreground"],
			  "selectbackground": P["selection_background"], "selectforeground": P["selection_foreground"]}
		if "insertbackground" in o:
			kw["insertbackground"] = P["input_foreground"]
	elif cls == "Menu":
		kw = {"background": P["surface"], "foreground": P["foreground"], "activebackground": P["selection_background"],
			  "activeforeground": P["selection_foreground"]}
	elif head:
		kw = {"background": P["header_background"]}
		if "foreground" in o:
			kw["foreground"] = P["header_foreground"] if (o["foreground"].lower() in NEUTRAL_FG or o["foreground"] == HEAD_FG) else fg_for(o["foreground"])
	else:
		if "background" in o:
			kw["background"] = bg_for(o["background"])
		if "foreground" in o:
			kw["foreground"] = fg_for(o["foreground"])
		for a in ("activebackground", "selectbackground"):
			if a in o:
				kw[a] = P["selection_background"] if a == "selectbackground" else bg_for(o[a])
	if THEME["t"] is not CLASSIC and not head:
		for opt, role in getattr(w, "_om_palette_roles", {}).items():
			if opt in kw:
				kw[opt] = P[role]
	try:
		w.configure(**{k: v for k, v in kw.items() if v})
	except tk.TclError:
		pass


def theme_all(w):
	theme_widget(w)
	if isinstance(w, ttk.Treeview):
		stripe(w)
	for c in w.winfo_children():
		theme_all(c)


def load_themes(folder):
	"""Classic + every themes/<name>/theme.json."""
	_themes.clear()
	_themes["Classic"] = CLASSIC
	try:
		names = sorted(os.listdir(folder))
	except OSError:
		names = []
	for n in names:
		p = os.path.join(folder, n, "theme.json")
		try:
			t = json.load(open(p, encoding="utf-8"))
		except (OSError, ValueError):
			continue
		t["dir"] = os.path.join(folder, n)
		c = dict(CLASSIC["colors"])
		c.update(t.get("colors", {}))
		t["colors"] = c
		t.setdefault("dark", _lum(c["background"]) < 0.4)
		_themes[t.get("name", n)] = t
	return list(_themes)


def theme_names():
	return list(_themes) or ["Classic"]


def _button_images(t):
	"""The theme's button picture (assets.button) as normal / hover / pressed / disabled images."""
	a = (t.get("assets") or {}).get("button") or {}
	path = os.path.join(t.get("dir", ""), a.get("file", "")) if a.get("file") else None
	if not path or not os.path.exists(path):
		return None
	from PIL import Image, ImageEnhance, ImageTk
	im = Image.open(path).convert("RGBA")
	if a.get("brightness", 1) != 1:
		im = ImageEnhance.Brightness(im).enhance(a["brightness"])
	out = {}
	for k, f in (("normal", None), ("active", 1.12), ("pressed", 0.82), ("disabled", "grey")):
		x = im
		if f == "grey":
			x = ImageEnhance.Color(im).enhance(0.15)
			x = ImageEnhance.Brightness(x).enhance(0.8)
		elif f:
			x = ImageEnhance.Brightness(im).enhance(f)
		out[k] = ImageTk.PhotoImage(x)
	return out


def logo_watermark(size, background, opacity=0.07):
	"""The theme's logo (assets.logo), faded into the background colour (a watermark), size x size; None if it has none."""
	t = THEME.get("t") or {}
	a = (t.get("assets") or {}).get("logo") or {}
	path = os.path.join(t.get("dir", ""), a.get("file", "")) if a.get("file") else None
	if not path or not os.path.exists(path) or size < 16:
		return None
	from PIL import Image, ImageTk
	try:
		im = Image.open(path).convert("RGBA")
	except OSError:
		return None
	im.thumbnail((size, size), Image.LANCZOS)
	bg = Image.new("RGBA", im.size, background)
	im.putalpha(im.getchannel("A").point(lambda v: int(v * opacity)))
	bg.alpha_composite(im)
	return ImageTk.PhotoImage(bg.convert("RGB"))


def apply_theme(root, name, fonts=True, colors=None, notify=True):
	"""Switch the whole window (and the dialogs to come) to a theme. fonts=False: leave the text sizes alone (the
	other masters keep theirs). colors/notify support transient palette previews without changing saved themes or firing theme hooks."""
	t = _themes.get(name) or CLASSIC
	if colors is not None:
		t = dict(t, colors=dict(colors))
	THEME["t"] = t
	P.clear()
	P.update(t["colors"])
	st = ttk.Style(root)
	engine = "vista" if t is CLASSIC and "vista" in st.theme_names() else "clam"
	if st.theme_use() != engine:
		st.theme_use(engine)
	fam = (t.get("fonts") or {}).get("family")
	if fam and fonts:
		for n, (family, size, weight) in list(FONTS.items()):
			if n != "om_mono":
				FONTS[n] = (fam, size, weight)
	if fonts:
		set_scale(root, _scale[0])  # (sizes and paddings are per ttk theme)
	if t is not CLASSIC:
		c = P
		st.configure(".", background=c["background"], foreground=c["foreground"], fieldbackground=c["input_background"],
					 bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["background"], troughcolor=c["surface"],
					 selectbackground=c["selection_background"], selectforeground=c["selection_foreground"], insertcolor=c["foreground"])
		st.map(".", foreground=[("disabled", c["muted"])])
		st.configure("TFrame", background=c["background"])
		st.configure("TLabel", background=c["background"], foreground=c["foreground"])
		st.configure("Muted.TLabel", foreground=c["muted"])
		st.configure("TButton", background=c["button_background"], foreground=c["button_foreground"], bordercolor=c["border"],
					 focuscolor=c["copper"])
		st.map("TButton", background=[("pressed", c.get("button_pressed", c["selection_background"])), ("active", c["button_active"])],
			   foreground=[("disabled", c["muted"]), ("pressed", c.get("button_pressed_foreground", c["selection_foreground"]))])
		st.configure("TMenubutton", background=c["button_background"], foreground=c["button_foreground"], arrowcolor=c["foreground"])
		st.map("TMenubutton", background=[("active", c["button_active"])])
		for w in ("TEntry", "TCombobox", "TSpinbox"):
			st.configure(w, fieldbackground=c["input_background"], foreground=c["input_foreground"], arrowcolor=c["foreground"],
						 background=c["button_background"])
			st.map(w, fieldbackground=[("readonly", c["input_background"]), ("disabled", c["background"])],
				   foreground=[("readonly", c["input_foreground"])], selectbackground=[("readonly", c["input_background"])],
				   selectforeground=[("readonly", c["input_foreground"])])
		st.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["foreground"], bordercolor=c["border"])
		st.map("Treeview", background=[("selected", c["selection_background"])], foreground=[("selected", c["selection_foreground"])])
		st.configure("Treeview.Heading", background=c["header_background"], foreground=c["header_foreground"], bordercolor=c["border"])
		st.map("Treeview.Heading", background=[("active", c["header_hover"])])
		for w in ("TRadiobutton", "TCheckbutton", "View.TRadiobutton"):
			st.configure(w, background=c["background"], foreground=c["foreground"], indicatorbackground=c["input_background"],
						 indicatorforeground=c["foreground"])
			st.map(w, background=[("active", c["background"])], indicatorbackground=[("selected", c["copper"])])
		st.configure("TScrollbar", background=c["button_background"], troughcolor=c["background"], arrowcolor=c["foreground"],
					 bordercolor=c["border"])
		st.map("TScrollbar", background=[("active", c["button_active"])])
		st.configure("TScale", background=c["copper"], troughcolor=c["surface"], bordercolor=c["border"])
		st.configure("TPanedwindow", background=c["background"])
		st.configure("Sash", sashthickness=px(6), gripcount=0, background=c["border"])
		st.configure("TSeparator", background=c["border"])
		st.configure("TNotebook", background=c["background"])
		# the theme's own button picture (RR: copper frame, parchment), if it has one
		imgs = _button_images(t)
		if "TButton.layout0" not in _imgs:
			_imgs["TButton.layout0"] = st.layout("TButton")
		if imgs:
			key = "OMButton." + t.get("id", name)
			if key not in _imgs:
				st.element_create(key + ".bg", "image", imgs["normal"], ("disabled", imgs["disabled"]), ("pressed", imgs["pressed"]),
								  ("active", imgs["active"]), border=(12, 8, 12, 8), sticky="nsew")
				_imgs[key] = imgs
			lay = [(key + ".bg", {"sticky": "nsew", "children": [("Button.padding", {"sticky": "nsew", "children": [
				("Button.label", {"sticky": "nsew"})]})]})]
			for w in ("TButton", "Tool.TButton", "Nav.TButton", "Small.TButton"):
				st.layout(w, lay)
			pf = c.get("parchment_foreground", "#29291e")
			st.configure("TButton", foreground=pf)
			st.map("TButton", foreground=[("disabled", "#6b6658")], background=[])
			st.configure("TButton", padding=(px(8), px(3)))
			st.configure("Tool.TButton", padding=(px(6), px(1)))
			st.configure("Nav.TButton", padding=(px(12), px(6)))
		else:
			for w in ("TButton", "Tool.TButton", "Nav.TButton", "Small.TButton"):
				st.layout(w, _imgs["TButton.layout0"])
	for pat, val in (("*Background", P["background"]), ("*Foreground", P["foreground"]), ("*Menu.background", P["surface"]),
					 ("*Menu.foreground", P["foreground"]), ("*Menu.activeBackground", P["selection_background"]),
					 ("*Text.background", P["input_background"]), ("*Text.foreground", P["input_foreground"]),
					 ("*Listbox.background", P["input_background"]), ("*Listbox.foreground", P["input_foreground"]),
					 ("*TCombobox*Listbox.background", P["input_background"]), ("*TCombobox*Listbox.foreground", P["input_foreground"]),
					 ("*TCombobox*Listbox.selectBackground", P["selection_background"])):
		root.option_add(pat, val if t is not CLASSIC else "")
	if t is CLASSIC:
		root.option_clear()
	for sec in list(_sections):
		try:
			if sec.winfo_exists():
				sec.recolour()
		except tk.TclError:
			pass
	theme_all(root)
	if notify:
		title_bar(root)
	if notify:
		for hook in list(THEME_HOOKS):
			try:
				hook()
			except tk.TclError:
				pass
	if not getattr(root, "_om_mapbind", False):  # (dialogs and widgets made later)
		root._om_mapbind = True
		root.bind_all("<Map>", lambda ev: theme_widget(ev.widget), add="+")
	previous = getattr(root, "_om_sound_theme", name)
	root._om_sound_theme = name
	if previous != name:
		feedback = getattr(root, "_sound_feedback", None)
		if feedback:
			feedback.feedback("theme_change")


# ---------------- the top of the window ----------------
def title_bar(win):
	"""The window's title bar in the theme (Windows 11: its colour and text; Classic: the normal Windows one)."""
	try:
		import ctypes
		win.update_idletasks()
		hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
		set_attr = ctypes.windll.dwmapi.DwmSetWindowAttribute
		classic = THEME["t"] is CLASSIC

		def colorref(c):
			r, g, b = _rgb(c) or (0, 0, 0)
			return r | (g << 8) | (b << 16)
		dark = ctypes.c_int(0 if classic else int(THEME["t"].get("dark", False)))
		set_attr(hwnd, 20, ctypes.byref(dark), 4)  # (dark mode: the min / max / close buttons)
		caption = ctypes.c_int(0xFFFFFFFF if classic else colorref(P["header_background"]))
		text = ctypes.c_int(0xFFFFFFFF if classic else colorref(P["header_foreground"]))
		set_attr(hwnd, 35, ctypes.byref(caption), 4)  # (caption colour, Windows 11)
		set_attr(hwnd, 36, ctypes.byref(text), 4)  # (caption text colour)
	except Exception:
		pass  # (older Windows, or not Windows: the normal title bar)


class MenuBar(tk.Frame):
	"""A menu bar drawn by the tool (Windows draws the normal one itself, in its own colours): it follows the theme."""

	def __init__(self, root, menu):
		super().__init__(root, borderwidth=0, highlightthickness=0)
		self._om_bar = True
		self.items = []
		for i in range(menu.index("end") + 1):
			kind = menu.type(i)
			if kind not in ("cascade", "command"):
				continue
			b = tk.Label(self, text=menu.entrycget(i, "label").strip(), padx=px(10), pady=px(3), font="TkMenuFont", cursor="hand2")
			b.pack(side="left")
			if kind == "cascade":
				sub = root.nametowidget(menu.entrycget(i, "menu"))
				b.bind("<Button-1>", lambda ev, b=b, sub=sub: self.open(b, sub))
			else:
				b.bind("<Button-1>", lambda ev, i=i: menu.invoke(i))
			b.bind("<Enter>", lambda ev, b=b: b.config(background=P["header_hover"]))
			b.bind("<Leave>", lambda ev, b=b: b.config(background=P["header_background"]))
			self.items.append(b)
		self.recolour()
		THEME_HOOKS.append(self.recolour)

	def open(self, b, sub):
		sub.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

	def add_right(self, text, command, hover=None):
		"""A button at the right end of the bar (packed / hidden by whoever made it)."""
		b = tk.Label(self, text=text, padx=px(12), pady=px(3), font="TkMenuFont", cursor="hand2")
		b.bind("<Button-1>", lambda ev: command())
		b.bind("<Enter>", lambda ev: b.config(background=hover or P["header_hover"], foreground="#ffffff" if hover else P["header_foreground"]))
		b.bind("<Leave>", lambda ev: b.config(background=P["header_background"], foreground=P["header_foreground"]))
		self.items.append(b)
		self.recolour()
		return b

	def recolour(self):
		self.config(background=P["header_background"])
		for b in self.items:
			b.config(background=P["header_background"], foreground=P["header_foreground"])


# ---------------- one theme for all the masters ----------------
THEME_FILE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OrganisationMaster", "theme.json")


def theme_settings():
	try:
		return json.load(open(THEME_FILE, encoding="utf-8"))
	except (OSError, ValueError):
		return {}


def theme_for(master):
	"""The theme a master uses: its own (when "Just for this master" is ticked), else the shared one."""
	s = theme_settings()
	return (s.get("own") or {}).get(master) or s.get("theme", "Classic")


def choose_theme(master, name, own):
	"""own: just for this master; else the shared theme (and this master follows it again)."""
	s = theme_settings()
	s.setdefault("own", {})
	if own:
		s["own"][master] = name
	else:
		s["own"].pop(master, None)
		s["theme"] = name
	os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
	with open(THEME_FILE, "w", encoding="utf-8") as f:
		json.dump(s, f, indent=1)


def theme_menu(root, menu, master, fonts=True):
	"""Theme > the themes, and "Just for this master". The theme follows the other masters' changes (shared file)."""
	tm = tk.Menu(menu, tearoff=0)
	cur = tk.StringVar(root, value=theme_for(master))
	own = tk.BooleanVar(root, value=bool((theme_settings().get("own") or {}).get(master)))

	def pick(name):
		choose_theme(master, name, own.get())
		apply_theme(root, name, fonts)
		state["mtime"] = _mtime()

	def toggle_own():
		choose_theme(master, cur.get(), own.get())
		if not own.get():  # (back to the shared theme)
			cur.set(theme_for(master))
			apply_theme(root, cur.get(), fonts)
		state["mtime"] = _mtime()
	for name in theme_names():
		tm.add_radiobutton(label=name, variable=cur, value=name, command=lambda n=name: pick(n))
	tm.add_separator()
	tm.add_checkbutton(label=f"Just for {master} (the other masters keep theirs)", variable=own, command=toggle_own)
	menu.add_cascade(label="Theme", menu=tm)
	state = {"mtime": _mtime()}

	def follow():  # (another master changed the shared theme)
		try:
			m = _mtime()
			if m != state["mtime"]:
				state["mtime"] = m
				want = theme_for(master)
				own.set(bool((theme_settings().get("own") or {}).get(master)))
				if want != cur.get():
					cur.set(want)
					apply_theme(root, want, fonts)
			root.after(2000, follow)
		except tk.TclError:
			pass
	root.after(2000, follow)
	return tm


def _mtime():
	try:
		return os.path.getmtime(THEME_FILE)
	except OSError:
		return 0


def setup_master(root, menu, master, themes_dir):
	"""For Culture / Country Master: the shared theme, the Theme menu, and a menu bar drawn in the theme (in place of
	Windows' own). Their colours and text sizes stay as they are."""
	KEEP_COLOURS[0] = True
	install_type_to_find(root)
	for name, (family, size, weight) in FONTS.items():  # (named fonts the themed parts use)
		if name not in tkfont.names(root):
			_fonts[name] = tkfont.Font(root, name=name, family=family, size=size, weight=weight)
	load_themes(themes_dir)
	from sound_feedback import MasterSounds
	MasterSounds(root, menu, theme=lambda: theme_for(master))
	theme_menu(root, menu, master, fonts=False)
	root.config(menu="")
	bar = MenuBar(root, menu)
	first = root.pack_slaves()
	bar.pack(side="top", fill="x", **({"before": first[0]} if first else {}))
	apply_theme(root, theme_for(master), fonts=False)
	root.after(300, lambda: title_bar(root))
	return bar


def tool_button(parent, text, command):
	"""A small button for a section's title bar."""
	return ttk.Button(parent, text=text, command=command, style="Tool.TButton")
