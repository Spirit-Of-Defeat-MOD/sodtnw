"""🖼 GFX > 🔀 Before / after: a picture as it was when it was marked for 🔁 rework next to how it is now.
"Before" comes from git: the file as committed before it was marked (every PC has the history, nothing is copied).
Side by side, or ⧉ Overlay: one on top of the other - Space / click flips between them for a quick glance, the slider
blends them. Zoom: the mouse wheel, 1:1, Fit. The window lists what's waiting for rework and what was reworked lately."""
import datetime
import io
import os
import subprocess
import tkinter as tk
from tkinter import ttk

import ui

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
UPSCALE = 4


def git(root, *args):
	try:
		return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=20, creationflags=NO_WINDOW).stdout
	except (OSError, subprocess.SubprocessError):
		return b""


def before_bytes(root, rel, marked):
	"""(the file's bytes as committed before it was marked, the commit's date) or (None, why)."""
	if not rel or rel.startswith("game:") or os.path.isabs(rel):
		return None, "a base-game picture (no history in the mod)"
	day = (marked or "")[:10]
	until = (day + "T23:59:59") if len(marked or "") <= 10 else marked
	rev = git(root, "rev-list", "-1", f"--before={until}", "HEAD", "--", rel).decode().strip()
	if not rev:
		rev = git(root, "rev-list", "-1", "--reverse", "HEAD", "--", rel).decode().strip().splitlines()[:1]
		rev = rev[0] if rev else ""
	if not rev:
		return None, "not in git yet"
	data = git(root, "show", f"{rev}:{rel}")
	date = git(root, "show", "-s", "--format=%cs", rev).decode().strip()
	return (data, date) if data else (None, "not found in git")


def pil(source):
	from PIL import Image
	try:
		return Image.open(io.BytesIO(source) if isinstance(source, bytes) else source).convert("RGBA")
	except Exception:
		return None


def entries(pane):
	"""[(label, info)] what's in 🔁 Needs Rework now, then what was reworked lately (newest first)."""
	data = pane.todo.data.get("gfx") or {}
	out = []
	for key, m in sorted((data.get("rework") or {}).items(), key=lambda kv: kv[1].get("when") or "", reverse=True):
		if m.get("file"):
			out.append((f"🔁 {m.get('name') or key}  · {m.get('reason', '')}", dict(m, key=key, done=None)))
	done = [(k, m) for k, m in (data.get("rework_done") or {}).items() if m.get("file")]
	for key, m in sorted(done, key=lambda kv: kv[1].get("when") or "", reverse=True)[:150]:
		out.append((f"✓ {m.get('name') or key}  · reworked {m.get('when', '')[:10]} by {m.get('by', '?')}", dict(m, key=key, done=m.get("when"))))
	return out


class Compare(tk.Toplevel):
	def __init__(self, pane, key=None):
		super().__init__(pane)
		self.pane, self.root_dir = pane, pane.app.mod_root
		self._om_nonmodal = True
		self.title("🔀 Before / after")
		self.geometry(f"{ui.px(1100)}x{ui.px(720)}")
		self.before = self.after_im = None
		self.zoom = None
		self.showing = "after"
		left = ttk.Frame(self, padding=(8, 8, 0, 8))
		left.pack(side="left", fill="y")
		ttk.Label(left, text="Marked for rework / reworked lately", style="Muted.TLabel").pack(anchor="w")
		self.list = ttk.Treeview(left, show="tree", selectmode="browse", height=30)
		self.list.column("#0", width=ui.px(300))
		self.list.pack(fill="y", expand=True)
		self.infos = {}
		for label, info in entries(pane):
			iid = self.list.insert("", "end", text=label)
			self.infos[iid] = info
		self.list.bind("<<TreeviewSelect>>", lambda ev: self.pick())
		right = ttk.Frame(self, padding=8)
		right.pack(side="left", fill="both", expand=True)
		bar = ttk.Frame(right)
		bar.pack(fill="x")
		self.mode = tk.StringVar(value=pane.app.config.get("gfx_compare_mode", "side"))
		for value, text in (("side", "◫ Side by side"), ("overlay", "⧉ Overlay")):
			ttk.Radiobutton(bar, text=text, variable=self.mode, value=value, command=self.mode_changed, style="View.TRadiobutton").pack(side="left", padx=(0, 4))
		self.flip_btn = ttk.Button(bar, text="Showing: after (Space flips)", command=self.flip)
		self.flip_btn.pack(side="left", padx=(12, 4))
		ttk.Label(bar, text="Blend").pack(side="left", padx=(8, 2))
		self.blend = tk.DoubleVar(value=0)
		self.blend_scale = ttk.Scale(bar, from_=0, to=1, variable=self.blend, command=lambda v: self.draw(), length=ui.px(140))
		self.blend_scale.pack(side="left")
		ttk.Button(bar, text="Fit", width=4, command=lambda: self.set_zoom(None)).pack(side="right")
		ttk.Button(bar, text="1:1", width=4, command=lambda: self.set_zoom(1)).pack(side="right", padx=2)
		self.info = ttk.Label(right, text="", style="Muted.TLabel")
		self.info.pack(anchor="w", pady=(4, 4))
		self.canvas = tk.Canvas(right, highlightthickness=0, background=ui.P.get("input_background", "#ffffff"))
		self.canvas.pack(fill="both", expand=True)
		self.canvas.bind("<Configure>", lambda ev: self.draw())
		self.canvas.bind("<MouseWheel>", lambda ev: self.set_zoom((self.zoom or self._scale or 1) * (1.15 if ev.delta > 0 else 1 / 1.15)))
		self.canvas.bind("<Button-1>", lambda ev: self.flip())
		self.bind("<space>", lambda ev: self.flip())
		self.bind("<Key-1>", lambda ev: self.set_zoom(1))
		self.bind("<Key-0>", lambda ev: self.set_zoom(None))
		self._scale = 1
		self.mode_changed(save=False)
		pick = next((i for i, x in self.infos.items() if x["key"] == key), None) or next(iter(self.infos), None)
		if pick:
			self.list.selection_set(pick)
			self.list.see(pick)
		else:
			self.info.config(text="Nothing marked for rework or reworked lately.")
		self.focus_set()

	def pick(self):
		sel = self.list.selection()
		info = self.infos.get(sel[0]) if sel else None
		if not info:
			return
		rel = info["file"]
		full = rel if os.path.isabs(rel) else os.path.join(self.root_dir, rel)
		self.after_im = pil(full) if os.path.isfile(full) else None
		data, date = before_bytes(self.root_dir, rel, info.get("when") or "")
		self.before = pil(data) if data else None
		same = data is not None and os.path.isfile(full) and open(full, "rb").read() == data
		parts = [f"{info.get('name') or rel}", f"marked {(info.get('when') or '')[:10]} by {info.get('by', '?')}" if not info.get("done") else
				 f"reworked {info['done'][:10]}"]
		parts.append(f"before = as committed {date}" if data else f"no before picture: {date}")
		if same:
			parts.append("not changed yet")
		if self.before and self.after_im:
			parts.append(f"{self.before.width}×{self.before.height} → {self.after_im.width}×{self.after_im.height} px")
		self.info.config(text="  ·  ".join(parts))
		self.draw()

	def mode_changed(self, save=True):
		if save:
			self.pane.app.config["gfx_compare_mode"] = self.mode.get()
			self.pane.app.save_config()
		overlay = self.mode.get() == "overlay"
		for w in (self.flip_btn, self.blend_scale):
			w.state(["!disabled"] if overlay else ["disabled"])
		self.draw()

	def flip(self):
		if self.mode.get() != "overlay":
			return
		self.showing = "before" if self.showing == "after" else "after"
		self.blend.set(0)
		self.flip_btn.config(text=f"Showing: {self.showing} (Space flips)")
		self.draw()

	def set_zoom(self, zoom):
		self.zoom = None if zoom is None else min(32, max(0.1, zoom))
		self.draw()

	def photo(self, im, box, scale):
		from PIL import Image, ImageTk
		size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
		out = im.resize(size, Image.NEAREST if scale > 1 else Image.LANCZOS)
		w, h = min(size[0], box[0]), min(size[1], box[1])
		out = out.crop(((size[0] - w) // 2, (size[1] - h) // 2, (size[0] - w) // 2 + w, (size[1] - h) // 2 + h))
		return ImageTk.PhotoImage(out)

	def draw(self):
		from PIL import Image
		c = self.canvas
		c.delete("all")
		W, H = c.winfo_width(), c.winfo_height()
		if W < 40:
			return
		muted = ui.P.get("muted", "#777777")
		self._photos = []
		pics = [("Before", self.before), ("Now", self.after_im)]
		if self.mode.get() == "overlay":
			a, b = (self.before, self.after_im) if self.showing == "before" else (self.after_im, self.before)
			if a is None:
				c.create_text(W / 2, H / 2, text=f"No {self.showing} picture", fill=muted, font="om_head")
				return
			im = a
			if b is not None and self.blend.get() > 0:  # (the other one blended over it)
				im = Image.blend(a, b.resize(a.size, Image.NEAREST), float(self.blend.get()))
			box = (W - 20, H - 40)
			self._scale = self.zoom or min(box[0] / im.width, box[1] / im.height, UPSCALE)
			ph = self.photo(im, box, self._scale)
			self._photos.append(ph)
			c.create_image(W / 2, (H - 20) / 2, image=ph)
			label = f"{'BEFORE' if self.showing == 'before' else 'NOW'}" + (f"  +{round(self.blend.get() * 100)}% of the other" if self.blend.get() > 0 else "")
			c.create_text(W / 2, H - 8, anchor="s", text=f"{label}  ·  {self._scale:.2g}×  ·  click / Space flips", fill=muted, font="om_small")
			return
		half = W / 2
		box = (int(half - 20), H - 40)
		have = [p for _, p in pics if p is not None]
		self._scale = self.zoom or min([min(box[0] / p.width, box[1] / p.height, UPSCALE) for p in have] or [1])
		for i, (name, im) in enumerate(pics):
			cx = half * i + half / 2
			if im is None:
				c.create_text(cx, H / 2, text=f"No {name.lower()} picture", fill=muted, font="om_body")
			else:
				ph = self.photo(im, box, self._scale)
				self._photos.append(ph)
				c.create_image(cx, (H - 20) / 2, image=ph)
			c.create_text(cx, H - 8, anchor="s", text=f"{name.upper()}  ·  {self._scale:.2g}×", fill=muted, font="om_small")
		c.create_line(half, 10, half, H - 30, fill=ui.P.get("border", "#cccccc"))
