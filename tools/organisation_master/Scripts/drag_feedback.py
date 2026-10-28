"""Full-row drag images that follow the pointer without a separate popup or rotating text."""
import tkinter as tk
from math import sin, tau
from time import monotonic
from tkinter import ttk, font as tkfont


class DragWobble:
    def __init__(self, tree, palette, scale):
        self.tree, self.palette, self.scale = tree, palette, scale
        self.canvas = self.job = None
        self.surfaces = {}
        self.rows = []
        self.geometry = {}
        self.origin = self.pointer = None
        self.started_at = None
        self.tag = "DragWobble" + str(id(self))
        tree.bindtags((self.tag,) + tree.bindtags())
        for event in ("<ButtonPress-1>", "<ButtonRelease-1>", "<Escape>", "<Unmap>", "<FocusOut>"):
            tree.bind_class(self.tag, event, self.stop)
        tree.bind_class(self.tag, "<Destroy>", self.destroy)

    def move(self, event, rows, origin=None):
        self.rows = [row for row in rows if self.tree.exists(row)]
        if not self.rows:
            self.stop()
            return
        if self.origin is None:
            self.origin = origin or (event.x, event.y)
            self.started_at = monotonic()
        self.pointer = (event.x, event.y)
        if self.job:
            self.tree.after_cancel(self.job)
        self.tick()

    def tick(self):
        self.job = None
        if not self.tree.winfo_ismapped():
            self.stop()
            return
        live = [row for row in self.rows if self.tree.exists(row)]
        if not live:
            self.stop()
            return
        dx, dy = self.pointer[0] - self.origin[0], self.pointer[1] - self.origin[1]
        # Animate labels inside the cursor-following row; its box and icons stay steady.
        elapsed = monotonic() - self.started_at
        strength = min(1.0, elapsed / 0.12) * self.scale
        sway_x = round(3 * strength * sin(elapsed * tau * 2))
        sway_y = round(strength * sin(elapsed * tau * 4))
        style = ttk.Style(self.tree)
        name = self.tree.cget("style") or "Treeview"
        bg = style.lookup(name, "background", ("selected",)) or self.palette["selection_background"]
        fg = style.lookup(name, "foreground", ("selected",)) or self.palette["selection_foreground"]
        try:
            font = tkfont.nametofont(str(style.lookup(name, "font") or "TkDefaultFont"), root=self.tree)
        except tk.TclError:
            font = tkfont.Font(self.tree, font=style.lookup(name, "font"))
        columns = tuple(map(str, self.tree.cget("displaycolumns")))
        if columns == ("#all",):
            columns = tuple(map(str, self.tree.cget("columns")))
        # Tk returns Tcl index objects for 'show', which do not compare equal to Python strings.
        columns = (("#0",) if "tree" in map(str, self.tree.cget("show")) else ()) + tuple(columns)
        base_font = font
        for row, canvas in list(self.surfaces.items()):
            if row not in live:
                canvas.destroy()
                del self.surfaces[row]
        for row in live:
            font = base_font
            for tag in self.tree.item(row, "tags"):
                tagged_font = str(self.tree.tag_configure(tag, "font"))
                if tagged_font:
                    try:
                        font = tkfont.nametofont(tagged_font, root=self.tree)
                    except tk.TclError:
                        font = tkfont.Font(self.tree, font=tagged_font)
                    break
            if row not in self.geometry:
                box = self.tree.bbox(row)
                if box:
                    self.geometry[row] = (box, {column: self.tree.bbox(row, column) for column in columns})
            box, cells = self.geometry.get(row, (None, {}))
            if not box:
                if row in self.surfaces:
                    self.surfaces[row].place_forget()
                continue
            canvas = self.surfaces.get(row)
            if canvas is None:
                canvas = self.surfaces[row] = tk.Canvas(self.tree, highlightthickness=0,
                    borderwidth=0, takefocus=False)
                # The row under the pointer would swallow the wheel: it scrolls the list instead.
                canvas.bind("<MouseWheel>", self.wheel)
            canvas.configure(background=bg)
            canvas.place(x=1 + dx, y=box[1] + dy,
                width=max(1, self.tree.winfo_width() - 2), height=box[3])
            canvas.tk.call("raise", str(canvas))
            canvas.delete("all")
            for column in columns:
                cell = cells.get(column)
                if not cell:
                    continue
                x, _, width, _ = cell
                left, right = x + 4, x + width - 4
                text = str(self.tree.item(row, "text") if column == "#0" else self.tree.set(row, column))
                if column == "#0":
                    depth, parent = 0, self.tree.parent(row)
                    while parent:
                        depth += 1
                        parent = self.tree.parent(parent)
                    indent = style.lookup(name, "indent") or 20
                    left = x + (depth + 1) * int(indent) + 1
                    if self.tree.get_children(row):
                        canvas.create_text(left - 10, box[3] / 2,
                            text="▾" if self.tree.item(row, "open") else "▸", font=font, fill=fg)
                    images = self.tree.item(row, "image")
                    if images:
                        image = images[0]
                        canvas.create_image(left, box[3] / 2, image=image, anchor="w")
                        left += int(self.tree.tk.call("image", "width", image)) + 4 * self.scale
                room = max(0, right - left - 2 * self.scale)
                if font.measure(text) > room:
                    while text and font.measure(text + "…") > room:
                        text = text[:-1]
                    text = text + "…" if text else ""
                anchor = self.tree.column(column, "anchor") if column != "#0" else "w"
                tx = right if anchor == "e" else (left + right) / 2 if anchor == "center" else left
                canvas.create_text(tx + sway_x - 1, box[3] / 2 + sway_y,
                    text=text, font=font, fill=fg, anchor=anchor)
            self.canvas = canvas
        overlay = getattr(self.tree, "_drag_drop_overlay", None)
        if overlay is not None and overlay.winfo_ismapped():
            overlay.tk.call("raise", str(overlay))
        self.job = self.tree.after(33, self.tick)

    def wheel(self, event):
        self.tree.yview_scroll(-1 if event.delta > 0 else 1, "units")
        scrolled = getattr(self.tree, "_drag_scrolled", None)
        if scrolled:
            scrolled()
        return "break"

    def stop(self, _event=None):
        if self.job:
            self.tree.after_cancel(self.job)
            self.job = None
        for canvas in self.surfaces.values():
            canvas.destroy()
        self.surfaces.clear()
        self.canvas = None
        self.rows = []
        self.geometry.clear()
        self.origin = self.pointer = None
        self.started_at = None

    def destroy(self, event):
        if event.widget is self.tree:
            self.stop()
            for sequence in ("<ButtonPress-1>", "<ButtonRelease-1>", "<Escape>", "<Unmap>", "<FocusOut>", "<Destroy>"):
                self.tree.unbind_class(self.tag, sequence)
