"""🖼 GFX > 🔎 Review swiper: deals the mod's pictures that are there and aren't in 🔁 Needs Rework, one card at a time.
→ Looks fine (you won't be dealt it again), ← Needs review: pick the level (Needs Touchup / Needs Severe Recorrection /
Something about it) and say what's wrong, and it goes into 🔁 Needs Rework for everyone (portraits the same way Country
Master marks them). ↓ Not sure: the next one, this one comes round again later. Zoom: the mouse wheel, + / -,
1 = its real size (to see if the game stretches it), 0 = fit the card.
Shared (todo_tasks.json gfx): review_passed {picture id: {dev: day}} (looked fine to them: the card says who; you aren't
dealt the ones you passed), review_counts {dev: {total, day, today}} (the counter and the 🔎 review badges).
Personal (config.json): gfx_review_sections."""
import os
import tkinter as tk
from tkinter import ttk

import gfx_card_style
import gfx_master as gm
import ui

FAR = gm.SWIPE_FAR
UPSCALE = 4  # (small icons are drawn bigger, pixel-sharp, so you can judge them; at most this many times)


MIN_ZOOM, MAX_ZOOM = 0.1, 32  # (times its real size)
WHEEL_STEP, BUTTON_STEP = 1.15, 1.5  # (one wheel notch / one + or - press)


def load(path):
	"""The picture (PIL, RGBA), or None if unreadable."""
	from PIL import Image
	try:
		return Image.open(path).convert("RGBA")
	except Exception:
		return None


def fit_scale(im, box):
	"""Fitted in box: bigger for small ones (up to UPSCALE), smaller for big ones."""
	return min(box[0] / im.width, box[1] / im.height, UPSCALE)


def render(im, box, scale):
	"""A PhotoImage of im at scale (sharp pixels when bigger), cropped to its middle when bigger than box."""
	from PIL import Image, ImageTk
	scale = min(scale, 4096 / max(im.width, im.height))  # (no giant pictures in memory)
	size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
	w, h = min(size[0], int(box[0])), min(size[1], int(box[1]))
	if (w, h) != size and scale > 1:  # (zoomed in past the card: only the middle part is resized)
		cw, ch = min(im.width, w / scale), min(im.height, h / scale)  # (the part of the picture that shows)
		left, top = (im.width - cw) / 2, (im.height - ch) / 2
		return ImageTk.PhotoImage(im.resize((w, h), Image.NEAREST, box=(left, top, left + cw, top + ch)))
	return ImageTk.PhotoImage(im.resize(size, Image.NEAREST if scale > 1 else Image.LANCZOS).crop(
		((size[0] - w) // 2, (size[1] - h) // 2, (size[0] - w) // 2 + w, (size[1] - h) // 2 + h)))


class ReviewSwiper(ttk.Frame):
	def __init__(self, pane):
		super().__init__(pane)
		self.pane, self.app = pane, pane.app
		self.card, self._drag, self._photo = None, None, None
		self.zoom = None  # (None: fit the card; else times its real size - kept from card to card)
		self.zoom_label = self._target = self._zoom_job = None
		self._im = (None, None)  # (path, the picture: read once per card)
		self._keys = {}  # (picture id -> its 🔁 rework key)
		bar = ttk.Frame(self)
		bar.pack(fill="x", pady=(0, 4))
		ttk.Label(bar, text="Review from:").pack(side="left")
		chosen = self.app.config.get("gfx_review_sections") or [k for k, _ in gm.SECTIONS]
		self.sections = {}
		for key, text in gm.SECTIONS:
			v = self.sections[key] = tk.BooleanVar(value=key in chosen)
			ttk.Checkbutton(bar, text=text, variable=v, command=self.sections_changed).pack(side="left", padx=4)
		self.passed_btn = ttk.Button(bar, text="", command=self.reset_passed)
		self.passed_btn.pack(side="right")
		self.count_label = ttk.Label(bar, text="", style="Muted.TLabel")
		self.count_label.pack(side="right", padx=8)
		self.canvas = c = tk.Canvas(self, highlightthickness=0, background=ui.P.get("background", "#f0f0f0"))
		c.pack(fill="both", expand=True)
		c.bind("<Configure>", lambda ev: self.draw())
		c.bind("<ButtonPress-1>", self.drag_start)
		c.bind("<B1-Motion>", self.drag_move)
		c.bind("<ButtonRelease-1>", self.drag_end)
		for key, fn in (("<Left>", lambda ev: self.swipe(-1)), ("<Right>", lambda ev: self.swipe(1)), ("<Down>", lambda ev: self.not_sure()),
						("<plus>", lambda ev: self.zoom_by(1)), ("<equal>", lambda ev: self.zoom_by(1)), ("<KP_Add>", lambda ev: self.zoom_by(1)),
						("<minus>", lambda ev: self.zoom_by(-1)), ("<KP_Subtract>", lambda ev: self.zoom_by(-1)),
						("<Key-1>", lambda ev: self.set_zoom(1)), ("<Key-0>", lambda ev: self.set_zoom(None)),
						("<MouseWheel>", lambda ev: self.zoom_by(ev.delta / 120, WHEEL_STEP))):
			c.bind(key, fn)
		buttons = ttk.Frame(self)
		buttons.pack(pady=(4, 8))
		self.undo_btn = ttk.Button(buttons, text="↶ Undo  (Backspace)", command=self.undo, width=20, state="disabled")
		self.undo_btn.pack(side="left", padx=(4, 12))
		for text, fn in (("🔁 Needs review  (←)", lambda: self.swipe(-1)), ("🤷 Not sure  (↓)", self.not_sure),
						 ("✓ Looks fine  (→)", lambda: self.swipe(1))):
			ttk.Button(buttons, text=text, command=fn, width=24).pack(side="left", padx=4)
		c.bind("<BackSpace>", lambda ev: self.undo())
		zf = ttk.Frame(buttons)
		zf.pack(side="left", padx=(16, 0))
		ttk.Button(zf, text="－", width=3, command=lambda: self.zoom_by(-1)).pack(side="left")
		self.zoom_label = ttk.Label(zf, text="Fit", width=7, anchor="center")
		self.zoom_label.pack(side="left")
		ttk.Button(zf, text="＋", width=3, command=lambda: self.zoom_by(1)).pack(side="left")
		ttk.Button(zf, text="1:1", width=4, command=lambda: self.set_zoom(1)).pack(side="left", padx=(6, 0))
		ttk.Button(zf, text="Fit", width=4, command=lambda: self.set_zoom(None)).pack(side="left", padx=(2, 0))
		self.later = []  # (🤷 not sure: dealt again once the rest are done)
		self.history = []  # (the cards you swiped this time, last last: ↶ Undo brings them back)

	# ---------- which pictures ----------
	def me(self):
		return self.pane.todo.me.get()

	def gfx(self):
		return self.pane.todo.data.setdefault("gfx", {})

	def passed(self):
		"""{picture id: {dev: day}}: who it looked fine to (shared). This PC's older personal list moves in once."""
		store = self.gfx().setdefault("review_passed", {})
		mine = self.app.config.pop("gfx_review_passed", None)
		if mine:
			for pid, when in mine.items():
				store.setdefault(pid, {})[self.me()] = str(when)[:10]
			self.app.save_config()
			self.pane.todo.save(feedback=False)
		return store

	def passed_by_me(self):
		me = self.me()
		return {pid for pid, who in self.passed().items() if me in who}

	def count(self):
		"""Your reviews: one more (total and today), for the counter and the 🔎 badges."""
		day = gm.stamp()[:10]
		c = self.gfx().setdefault("review_counts", {}).setdefault(self.me(), {"total": 0, "day": day, "today": 0})
		if c.get("day") != day:
			c.update(day=day, today=0)
		c["total"] = c.get("total", 0) + 1
		c["today"] = c.get("today", 0) + 1

	def show_count(self):
		c = (self.gfx().get("review_counts") or {}).get(self.me()) or {}
		today = c.get("today", 0) if c.get("day") == gm.stamp()[:10] else 0
		self.count_label.config(text=f"🔎 Today: {today} reviewed · {c.get('total', 0)} in all")

	def sections_changed(self):
		self.app.config["gfx_review_sections"] = [k for k, v in self.sections.items() if v.get()]
		self.app.save_config()
		self.deal()

	def marked(self):
		"""Files and sprites already in 🔁 Needs Rework (marked here or in Country Master)."""
		marks = self.pane.rework_marks()
		files = {os.path.normcase(os.path.basename(m.get("file") or "")) for m in marks.values() if m.get("file")}
		sprites = {(m.get("sprite") or "").lower() for m in marks.values()}
		return set(marks), files, sprites

	def rework_key(self, x):
		"""(worked out once per picture: doing it for 12,000 pictures on every card was slow)"""
		key = self._keys.get(x["id"])
		if key is None:
			key = self._keys[x["id"]] = self.pane.rework_key(x["path"])[1]
		return key

	def pool(self):
		on = {k for k, v in self.sections.items() if v.get()}
		passed = self.passed_by_me()
		keys, files, sprites = self.marked()
		out = []
		for x in self.pane.present:
			if x["section"] not in on or x["id"] in passed:
				continue
			if (x.get("sprite") or "").lower() in sprites or self.rework_key(x) in keys \
					or os.path.normcase(os.path.basename(x["path"])) in files and x["section"] == "portrait":
				continue
			out.append(x)
		out.sort(key=lambda x: (x["section"], x.get("family_name") or "", x["name"].lower()))  # (a family's pictures together)
		return out

	def deal(self, keep=False):
		pool = self.pool()
		ids = {x["id"] for x in pool}
		if keep and self.card and self.card["id"] in ids:
			pass
		else:
			fresh = [x for x in pool if x["id"] not in self.later]
			self.card = (fresh or pool or [None])[0]
			if not fresh:
				self.later.clear()
		self.show_count()
		n = len(self.passed_by_me())
		self.passed_btn.config(text=f"↺ Look again at the {n} that looked fine" if n else "Nothing passed yet",
							   state="normal" if n else "disabled")
		self._left = len(pool)  # (counted once per card: counting every frame made the swipe choppy)
		self.draw()
		self.canvas.focus_set()

	def reset_passed(self):
		"""Your "looks fine"s go (the others' stay)."""
		me = self.me()
		store = self.passed()
		for pid in [p for p, who in store.items() if me in who]:
			store[pid].pop(me, None)
			if not store[pid]:
				del store[pid]
		self.pane.todo.save(feedback=False)
		self.deal()

	# ---------- the card ----------
	def draw(self, dx=0):
		"""The whole card, drawn in the middle and then slid dx across (dragging / sliding only moves it: offset)."""
		c = self.canvas
		c.delete("all")
		self._dx = 0
		W, H = c.winfo_width(), c.winfo_height()
		if W < 50:
			return
		c.configure(background=ui.P["background"])
		item = self.card
		muted = ui.P.get("muted", "#777777")
		if item is None:
			text = ("Scanning the mod..." if self.pane._scanning else
					"Nothing left to review here.\n(Tick more sections, or look again at the ones that looked fine.)"
					if self.pane.present else "Rescan the mod (↻) to list its pictures for review.")
			c.create_text(W // 2, H // 2, text=text, font="om_head", justify="center", fill=muted)
			return
		cw, ch = min(ui.px(560), W - ui.px(32)), min(ui.px(640), H - ui.px(40))
		x0, y0 = (W - cw) // 2, (H - ch) // 2 - ui.px(8)
		self._card = (x0, y0, cw)
		kind = f"{gm.SECTION_NAME[item['section']]} · {gm.KIND_LABEL.get(item['kind'], item['kind'])}"
		y, limit, fg, muted, accent = gfx_card_style.shell(c, x0, y0, cw, ch, item, gm.SECTION_COLOUR[item["section"]], kind)
		pad = ui.px(18)
		fam, detail = item.get("family_name") or "", item.get("detail") or ""
		fine = sorted(self.passed().get(item["id"], {}))
		if fine:
			detail += f"\n✓ Looked fine to {', '.join(fine)}"
		y = gfx_card_style.fitted_text(c, x0 + pad, y, detail if fam in detail else f"{fam} · {detail}",
									   cw - pad * 2, ui.px(54), font="om_small", fill=muted) + ui.px(8)
		box = (cw - pad * 2, max(ui.px(60), limit - y - ui.px(30)))
		self._pic = (x0 + cw / 2, y + box[1] / 2, box, y + box[1] + ui.px(6), muted)
		c.addtag_all("card")
		self.draw_pic()
		c.create_text(W // 2, H - 6, anchor="s", text=f"{getattr(self, '_left', 0)} left to review · drag the card or use the arrow keys · "
					  "zoom: mouse wheel, + / -, 1 = real size, 0 = fit", font="om_small", fill=muted)
		self.offset(dx)

	def offset(self, dx):
		"""The card dx across (its canvas items moved, nothing redrawn), with NEEDS REVIEW (left) / LOOKS FINE (right) past
		40 pixels."""
		c = self.canvas
		if not hasattr(self, "_card") or self.card is None:
			return
		c.move("card", dx - self._dx, 0)
		self._dx = dx
		c.delete("stamp")
		x0, y0, cw = self._card
		if dx < -40:
			c.create_text(x0 + dx + cw - 20, y0 + ui.px(100), anchor="ne", text="NEEDS REVIEW", font=("Segoe UI", 20, "bold"), fill="#c0392b",
						  angle=-15, tags="stamp")
		elif dx > 40:
			c.create_text(x0 + dx + 20, y0 + ui.px(100), anchor="nw", text="LOOKS FINE", font=("Segoe UI", 20, "bold"), fill="#2e9d4a",
						  angle=15, tags="stamp")

	def drag_start(self, ev):
		self.canvas.focus_set()
		self._drag = ev.x

	def drag_move(self, ev):
		if self._drag is not None and self.card:
			self.offset(ev.x - self._drag)

	def drag_end(self, ev):
		start, self._drag = self._drag, None
		if start is None or not self.card:
			return
		dx = ev.x - start
		if abs(dx) > FAR:
			self.swipe(1 if dx > 0 else -1, dx)
		else:
			self.slide(dx, 0, lambda: None)

	def slide(self, frm, to, then, step=0):
		"""(the card moves on: off the side, or back to the middle; eased, about a sixth of a second)"""
		steps = 12
		step += 1
		t = step / steps
		self.offset(round(frm + (to - frm) * (1 - (1 - t) ** 3)))
		if step < steps:
			self.after(14, lambda: self.slide(frm, to, then, step))
		else:
			then()

	def picture(self):
		path = self.card["path"]
		if self._im[0] != path:
			self._im = (path, load(path))
		return self._im[1]

	def draw_pic(self):
		"""Only the picture and its size line (zooming redraws just these)."""
		c = self.canvas
		c.delete("pic")
		if self.card is None or not hasattr(self, "_pic"):
			return
		cx, cy, box, below, muted = self._pic
		cx += getattr(self, "_dx", 0)  # (the card may be part-way across)
		im = self.picture()
		if im is None:
			c.create_text(cx, cy, text="(can't show this picture here)", font="om_body", fill=muted, tags=("pic", "card"))
			return
		self._scale = self.zoom or fit_scale(im, box)
		self._photo = render(im, box, self._scale)
		w, h = self._photo.width(), self._photo.height()
		c.create_rectangle(cx - w / 2 - 3, cy - h / 2 - 3, cx + w / 2 + 3, cy + h / 2 + 3, fill=ui.P["input_background"],
						   outline=ui.P["border"], tags=("pic", "card"))
		c.create_image(cx, cy, image=self._photo, tags=("pic", "card"))
		c.create_text(cx, below, anchor="n", font="om_small", fill=muted, tags=("pic", "card"),
					  text=f"{im.width}×{im.height} px · shown at {self._scale:.2g}×" + ("" if self.zoom else " (fit)"))
		if self.zoom_label:
			self.zoom_label.config(text="Fit" if self.zoom is None else f"{self.zoom:.2g}×")

	# ---------- zoom: the wheel, + / -, 1 = real size, 0 = fit; it glides there ----------
	def set_zoom(self, zoom):
		"""Glide to zoom (None: to fit the card)."""
		im = self.picture() if self.card else None
		if im is None or not hasattr(self, "_pic"):
			self.zoom = zoom
			return self.draw()
		self._target = zoom
		if self._zoom_job is None:
			self._zoom_job = self.after(0, self.glide)

	def zoom_by(self, steps, factor=None):
		now = self._target if self._zoom_job is not None and self._target else self.zoom or getattr(self, "_scale", 1) or 1
		self.set_zoom(min(MAX_ZOOM, max(MIN_ZOOM, now * (factor or BUTTON_STEP) ** steps)))

	def glide(self):
		self._zoom_job = None
		if self.card is None or self.picture() is None:
			return
		goal = self._target or fit_scale(self.picture(), self._pic[2])
		now = self.zoom or self._scale
		if abs(goal / now - 1) < 0.01:
			self.zoom = self._target
		else:
			self.zoom = now * (goal / now) ** 0.35  # (a third of the way each frame: quick, then settles)
		self.draw_pic()
		if self.zoom != self._target:
			self._zoom_job = self.after(16, self.glide)

	# ---------- the swipes ----------
	def swipe(self, way, frm=0):
		item = self.card
		if item is None:
			return
		if way < 0:  # (← needs review)
			got = self.pane.ask_rework(item["name"], item["section"])  # (the level and what's wrong)
			if got is None:
				return self.slide(frm, 0, lambda: None)
		W = self.canvas.winfo_width()

		def done():
			self.history.append(item)
			self.undo_btn.state(["!disabled"])
			self.count()
			if way > 0:  # (→ looks fine: for everyone to see on the card)
				self.passed().setdefault(item["id"], {})[self.me()] = gm.stamp()[:10]
				self.pane.todo.save(feedback=False)
			else:
				self.mark(item, got)
			self.deal()
		self.slide(frm, way * W, done)

	def mark(self, item, got):
		"""Into 🔁 Needs Rework for everyone (a portrait under its sprite, as Country Master marks it)."""
		if item["section"] == "portrait" and item.get("sprite"):
			todo = self.pane.todo
			gm.mark_portrait(todo.data, item["sprite"], got[0], when=gm.stamp()[:10], by=todo.me.get(), note=got[1],
							 kind="leader" if item["kind"] == "leader" else "generic", file=item["file"])
			todo.rework_task()
			todo.save()
			self.pane.refresh_items()
			self.app.set_status(f"GFX: {item['name']} is in 🔁 Needs Rework ({got[0]}).")
		else:
			self.pane.mark_rework(item["path"], item, got=got)

	def undo(self):
		"""↶ The last swipe taken back (its "looks fine" or its rework mark, through the To Do's Undo) and its card back."""
		if self.history:
			self.pane.todo.undo()  # (calls undone() when it's done)

	def undone(self):
		"""After any Undo: the last swiped card is dealt again (slides back in) if it's back in the pile."""
		if not self.history:
			return
		item = self.history.pop()
		self.show_count()
		self.undo_btn.state(["!disabled"] if self.history else ["disabled"])
		if item["id"] in {x["id"] for x in self.pool()}:
			self.card = item
			self.draw()
			self.slide(-self.canvas.winfo_width(), 0, lambda: None)

	def not_sure(self):
		if self.card:
			self.later.append(self.card["id"])
			self.deal()
