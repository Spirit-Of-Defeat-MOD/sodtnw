"""A small, asynchronous portrait preview for Country Master review tasks."""
import os
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk

from PIL import Image, ImageTk

import portrait_links
import ui


def load_preview(mod_root, sprite, links, size):
    """Decode off the UI thread; prefer the source image already attached to the task."""
    paths = []
    for link in reversed(links):
        if not isinstance(link, str) or os.path.splitext(link)[1].lower() not in (
                ".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            continue
        path = (portrait_links.game_link_path(mod_root, link) if link.startswith("game:")
                else link if os.path.isabs(link) else os.path.join(mod_root, link))
        if path:
            paths.append(path)

    def read(path):
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                image.thumbnail(size, Image.Resampling.LANCZOS)
                return path, image
        except (OSError, ValueError, Image.DecompressionBombError):
            return None

    for path in paths:
        result = read(path)
        if result:
            return result
    # Older tasks may not have a file link yet. Resolve the sprite without loading a master.
    link = portrait_links.resolve_portraits(mod_root, [sprite]).get(sprite)
    if link:
        path = (portrait_links.game_link_path(mod_root, link) if link.startswith("game:")
                else os.path.join(mod_root, link))
        if path:
            return read(path)
    return None


class PortraitPreview(ttk.Frame):
    def __init__(self, parent, mod_root):
        super().__init__(parent)
        self.mod_root = mod_root
        self.photo = self.path = None
        self.future = self.job = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="portrait-preview")
        ttk.Label(self, text="Portrait", style="Muted.TLabel").pack(anchor="w")
        self.image = ttk.Label(self, anchor="center")
        self.image.pack(pady=(4, 0))
        self.caption = ttk.Label(self, style="Muted.TLabel", wraplength=ui.px(170), justify="center")
        self.caption.pack()
        self.image.bind("<Button-1>", self.open_file)
        self.bind("<Destroy>", self.destroyed, add="+")

    def show(self, sprite, links=()):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        if self.future:
            self.future.cancel()
            self.future = None
        self.photo = self.path = None
        self.image.configure(image="", text="", cursor="")
        self.grid_remove()
        if not sprite:
            return
        self.grid(row=0, column=2, rowspan=2, sticky="n", padx=(12, 0))
        self.caption.configure(text="Loading portrait…")
        self.future = self.pool.submit(load_preview, self.mod_root, sprite, tuple(links),
                                       (ui.px(160), ui.px(210)))
        self.job = self.after(40, self.poll)

    def poll(self):
        self.job = None
        if not self.future.done():
            self.job = self.after(40, self.poll)
            return
        try:
            result = self.future.result()
        except Exception:
            result = None
        self.future = None
        if result:
            self.path, image = result
            self.photo = ImageTk.PhotoImage(image, master=self)
            self.image.configure(image=self.photo, cursor="hand2")
            self.caption.configure(text="Click to open original")
        else:
            self.caption.configure(text="Portrait unavailable on this computer.")

    def open_file(self, _event=None):
        if self.path and os.path.isfile(self.path):
            os.startfile(self.path)

    def destroyed(self, event):
        if event.widget is self:
            if self.job:
                self.after_cancel(self.job)
                self.job = None
            self.pool.shutdown(wait=False, cancel_futures=True)
