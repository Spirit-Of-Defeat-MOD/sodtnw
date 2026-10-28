"""Small portable regional review maps, carried inside the synced task."""
import base64
import os
import zlib
import tkinter as tk
from tkinter import ttk
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageTk, ImageFilter

import ui


def capture(state_map, ids, colors=None):
    ids = sorted({int(sid) for sid in ids if 0 < int(sid) < 65535})
    mask = np.isin(state_map, ids)
    ys = np.flatnonzero(mask.any(axis=1))
    xs = np.flatnonzero(mask.any(axis=0))
    if not len(xs):
        raise ValueError("These states have no map pixels.")
    height, width = state_map.shape
    # Minimal circular extent keeps regions crossing the world seam together.
    gaps = np.diff(np.r_[xs, xs[0] + width])
    cut = int(gaps.argmax())
    start = int(xs[(cut + 1) % len(xs)])
    span = int((xs[cut] - start) % width) + 1
    pad = max(12, int(max(span, ys[-1] - ys[0] + 1) * .12))
    xindex = (np.arange(min(width, span + 2 * pad)) + start - pad) % width
    crop = state_map[max(0, int(ys[0]) - pad):min(height, int(ys[-1]) + pad + 1), xindex]
    scale = min(1., 900 / crop.shape[1], 460 / crop.shape[0])
    size = (max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale)))
    raster = np.asarray(Image.fromarray(crop.astype(np.uint16)).resize(size, Image.Resampling.NEAREST)).copy()
    # Preserve at least one hit-test pixel for very small selected islands.
    for sid in ids:
        if not np.any(raster == sid):
            points = np.argwhere(crop == sid)
            if len(points):
                y, x = points[len(points) // 2]
                raster[min(size[1] - 1, int(y * scale)), min(size[0] - 1, int(x * scale))] = sid
    if colors is not None:
        rgb = np.asarray(colors, dtype=np.uint8)[raster]
    else:
        rgb = np.empty((*raster.shape, 3), dtype=np.uint8)
        rgb[:] = (105, 121, 114)
        rgb[(raster == 0) | (raster == 65535)] = (35, 48, 65)
    pack = lambda value: base64.b64encode(zlib.compress(value, 9)).decode("ascii")
    return dict(kind="state-map", version=1, width=size[0], height=size[1], ids=ids,
                states=pack(raster.astype("<u2").tobytes()), colors=pack(rgb.tobytes()))


def decode(payload):
    w, h = payload.get("width"), payload.get("height")
    if (payload.get("kind") != "state-map" or payload.get("version") != 1 or type(w) is not int
            or type(h) is not int or not 0 < w <= 900 or not 0 < h <= 460):
        raise ValueError("Invalid map snapshot")
    def unpack(key, count):
        decoder = zlib.decompressobj()
        raw = decoder.decompress(base64.b64decode(payload[key], validate=True), count + 1)
        if len(raw) != count or not decoder.eof or decoder.unused_data:
            raise ValueError("Invalid map pixels")
        return raw
    raster = np.frombuffer(unpack("states", w * h * 2), dtype="<u2").reshape(h, w)
    rgb = np.frombuffer(unpack("colors", w * h * 3), dtype=np.uint8).reshape(h, w, 3)
    return raster, rgb


def local_snapshot(root, ids):
    from culture_master import MapData
    cache = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CultureMaster")
    return decode(capture(MapData(root, cache).stmap, ids))


class RegionalMap(ttk.Frame):
    def __init__(self, parent, root, select):
        super().__init__(parent)
        self.root_path, self.select = root, select
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="review-map")
        self.future = self.job = None
        self.key = self.payload = self.data = self.photo = self.transform = None
        self.names, self.approved, self.changed = {}, set(), set()
        self.active = None
        self.expanded = False
        self.button = ttk.Button(self, text="▸ Show on Map", style="Tool.TButton", command=self.toggle)
        self.button.pack(anchor="w")
        self.body = ttk.Frame(self)
        self.caption = ttk.Label(self.body, style="Muted.TLabel", wraplength=800)
        self.caption.pack(anchor="w", pady=(6, 4))
        self.canvas = tk.Canvas(self.body, height=ui.px(280), width=1, highlightthickness=1)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda _event: self.render())
        self.canvas.bind("<Button-1>", self.clicked)
        self.canvas.bind("<Motion>", lambda event: self.canvas.configure(cursor="hand2" if self.hit(event) in self.names else ""))
        self.bind("<Destroy>", self.destroyed, add="+")
        ui.THEME_HOOKS.append(self.render)

    def set_review(self, task, sid):
        members = (task or {}).get("review_states") or []
        key = (task or {}).get("ref") or (task or {}).get("link")
        payload = (task or {}).get("review_map")
        if key != self.key or payload != self.payload:
            if self.job:
                self.after_cancel(self.job)
                self.job = None
            if self.future:
                self.future.cancel()
                self.future = None
            self.data = self.photo = None
            if key != self.key:
                self.expanded = False
            self.key, self.payload = key, payload
        self.active = sid
        self.names = {row["id"]: row.get("name", str(row["id"])) for row in members}
        self.approved = {int(key) for key, value in ((task or {}).get("review_approvals") or {}).items()
                         if str(key).isdigit() and value.get("approved")}
        if len(members) > 1:
            if not self.winfo_manager():
                self.pack(fill="x", pady=(8, 0))
            self.update_visibility()
        else:
            self.pack_forget()

    def toggle(self):
        self.expanded = not self.expanded
        self.update_visibility()

    def update_visibility(self):
        self.button.configure(text="▾ Hide Map" if self.expanded else "▸ Show on Map")
        if not self.expanded:
            self.body.pack_forget()
            return
        self.body.pack(fill="x")
        if self.data is not None:
            self.render()
        elif self.future is None:
            self.caption.configure(text="Loading regional map…")
            self.future = self.pool.submit(decode, self.payload) if self.payload else self.pool.submit(local_snapshot, self.root_path, list(self.names))
            self.job = self.after(40, self.poll)

    def poll(self):
        self.job = None
        if not self.future.done():
            self.job = self.after(40, self.poll)
            return
        try:
            self.data = self.future.result()
        except Exception:
            self.caption.configure(text="Map unavailable. Reflag this region in the updated Culture Master to attach a snapshot.")
        self.future = None
        self.render()

    def render(self):
        if not self.expanded or self.data is None:
            return
        raster, original = self.data
        color = lambda key: np.array(self.winfo_rgb(ui.P[key]), dtype=np.float32) / 257
        rgb = (original * .4 + color("background") * .6).astype(np.uint8)
        selected = np.isin(raster, list(self.names))
        rgb[selected] = original[selected]
        rgb[np.isin(raster, list(self.approved))] = (42, 139, 79)
        rgb[np.isin(raster, list(self.changed))] = (40, 112, 185)
        active = raster == self.active
        rgb[active] = (42, 139, 79) if self.active in self.approved else (40, 112, 185) if self.active in self.changed else color("selection_background")
        edge = np.zeros(raster.shape, dtype=bool)
        edge[:-1] |= raster[:-1] != raster[1:]
        edge[:, :-1] |= raster[:, :-1] != raster[:, 1:]
        rgb[edge & selected] = color("header_foreground")
        image = Image.fromarray(rgb)
        if active.any():
            outline = Image.fromarray((active * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
            outline = np.asarray(outline) > 0
            image_array = np.asarray(image).copy()
            image_array[outline & ~active] = color("selection_foreground")
            image = Image.fromarray(image_array)
        width, height = max(1, self.canvas.winfo_width() - 4), ui.px(280)
        ratio = min(width / image.width, height / image.height)
        image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.NEAREST)
        x, y = (width + 4 - image.width) // 2, (height - image.height) // 2
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.canvas.configure(background=ui.P["background"], highlightbackground=ui.P["border"], height=height)
        self.canvas.delete("all")
        self.canvas.create_image(x, y, anchor="nw", image=self.photo)
        self.transform = x, y, image.width, image.height
        self.caption.configure(text=f"Selected: {self.names.get(self.active, self.active)} ({self.active}). Click a review state to inspect it. Green = approved; blue = changes to review.",
                               wraplength=max(200, width))

    def hit(self, event):
        if self.data is None or self.transform is None:
            return None
        x, y, w, h = self.transform
        if not x <= event.x < x + w or not y <= event.y < y + h:
            return None
        raster = self.data[0]
        return int(raster[min(raster.shape[0] - 1, int((event.y - y) * raster.shape[0] / h)),
                          min(raster.shape[1] - 1, int((event.x - x) * raster.shape[1] / w))])

    def clicked(self, event):
        sid = self.hit(event)
        if sid in self.names:
            self.select(sid)

    def destroyed(self, event):
        if event.widget is self:
            if self.job:
                self.after_cancel(self.job)
            self.pool.shutdown(wait=False, cancel_futures=True)
            if self.render in ui.THEME_HOOKS:
                ui.THEME_HOOKS.remove(self.render)
