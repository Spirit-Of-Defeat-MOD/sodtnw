"""Zoomable idea pictures and safe, watched working copies for external editors."""
import hashlib
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
import tkinter as tk
from tkinter import ttk, messagebox
import uuid

from PIL import Image, ImageOps, ImageTk

import ui
from external_file import open_file


def signature(path):
    try:
        stat = os.stat(path)
        return stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns
    except OSError:
        return None


def read_image(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert('RGBA')


THUMB = (110, 80)  # (the picture thumbnails' box, before ui scaling: Ideas, GFX)


def thumbnail(path, box=THUMB):
    """A PhotoImage of a picture fitted in box (scaled for the UI), or None when it can't be read."""
    try:
        im = read_image(path)
        im.thumbnail((ui.px(box[0]), ui.px(box[1])))
        ph = ImageTk.PhotoImage(im)
        im.close()
        return ph
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def picture_label(parent, path, on_click, on_menu=None, box=THUMB, keep=None, missing='(not here yet)'):
    """A clickable thumbnail (Ideas' pictures, GFX's): packed left in parent; click -> on_click(), right-click ->
    on_menu(event). keep: a list the PhotoImage is kept in (Tk drops images nobody holds)."""
    ph = thumbnail(path, box) if path and os.path.isfile(path) else None
    if keep is not None:
        keep.append(ph)
    lab = tk.Label(parent, image=ph, text='' if ph else missing, cursor='hand2', relief='solid', borderwidth=1)
    lab.image = ph
    lab.pack(side='left', padx=(0, 4))
    lab.bind('<Button-1>', lambda ev: on_click())
    if on_menu:
        lab.bind('<Button-3>', on_menu)
    return lab


def show_picture(owner, path, kind='Picture'):
    """Pops a picture out in the zoomable viewer (the one Ideas uses); 'Open…' opens it in its own app. A picture the
    viewer can't read (some DDS formats) opens in its own app straight away."""
    if not os.path.isfile(path):
        return None
    try:
        read_image(path).close()
    except (OSError, ValueError, Image.DecompressionBombError):
        open_file(path)
        return None
    viewer = PictureViewer(owner, path, lambda: open_file(path), kind=kind)
    viewer.hist_btn.pack_forget()  # (no versions: it's the mod's file)
    return viewer


class PictureViewer(tk.Toplevel):
    def __init__(self, owner, path, open_external, kind='Idea picture'):
        super().__init__(owner)
        self.kind = kind
        self._om_nonmodal = True
        self.path, self.external = str(path), open_external
        self.image = self.photo = None
        self.zoom = 1.0
        self.fit_mode = True
        self.job = None
        self.zoom_job = None
        self.zoom_target = self.zoom
        self.title(kind)
        self.transient(owner.winfo_toplevel())
        self.geometry(f'{min(ui.px(1100), self.winfo_screenwidth()-80)}x{min(ui.px(780), self.winfo_screenheight()-100)}')
        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text='Open…', command=self.open_file).pack(side='left')
        self.pictures = None  # (IdeaPictures: the versions of this picture)
        self.current_name = Path(path).name
        self.hist_btn = ttk.Button(toolbar, text='🕘 History', command=self.show_history)
        self.hist_btn.pack(side='left', padx=(6, 0))
        self.restore_btn = ttk.Button(toolbar, text='↩ Restore this version', command=self.restore_version)
        self.version_note = ttk.Label(toolbar, text='', style='Muted.TLabel')
        controls = ttk.Frame(toolbar)
        controls.pack(side='right')
        ttk.Button(controls, text='Fit', width=5, command=self.fit).pack(side='left', padx=2)
        ttk.Button(controls, text='100%', width=6, command=lambda: self.set_zoom(1)).pack(side='left', padx=2)
        ttk.Button(controls, text='−', width=3, command=lambda: self.zoom_by(1/1.12)).pack(side='left', padx=2)
        self.percent = ttk.Label(controls, text='100%', width=7, anchor='center')
        self.percent.pack(side='left')
        ttk.Button(controls, text='+', width=3, command=lambda: self.zoom_by(1.12)).pack(side='left', padx=2)
        self.info = ttk.Label(self, padding=(8, 3), style='Muted.TLabel',
            text='Wheel: zoom · Drag: pan · Open: edit in your default image app; Save updates the idea.')
        self.info.pack(side='bottom', fill='x')
        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(frame, highlightthickness=0, background=ui.P['input_background'], cursor='fleur')
        self.picture_item = self.canvas.create_image(0, 0, anchor='nw', tags='picture')
        ys = ttk.Scrollbar(frame, command=self.scroll_y)
        xs = ttk.Scrollbar(frame, orient='horizontal', command=self.scroll_x)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        ys.pack(side='right', fill='y')
        xs.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self.resized)
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda e: self.wheel(e, 1))
        self.canvas.bind('<Button-5>', lambda e: self.wheel(e, -1))
        self.canvas.bind('<ButtonPress-1>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B1-Motion>', self.pan)
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<Destroy>', self.destroyed, add='+')
        self.load(path)
        ui.theme_all(self)
        ui.title_bar(self)

    def load(self, path):
        try:
            image = read_image(path)
            if image.getextrema()[3] == (255, 255):
                opaque = image.convert('RGB')
                image.close()
                image = opaque  # Avoid expensive alpha resampling for ordinary JPEGs.
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            self.info.configure(text=f'Picture unavailable: {error}')
            return False
        old = self.image
        self.cancel_zoom()
        self.image, self.path = image, str(path)
        if old is not None:
            old.close()
        self.title(f'{self.kind} — {Path(path).name}')
        if self.fit_mode:
            self.fit()
        else:
            self.queue_draw()
        return True

    def open_file(self):
        self.external()

    def show_history(self):
        versions = self.pictures.versions(self.record_id, self.current_name) if self.pictures else []
        m = tk.Menu(self, tearoff=0)
        viewing = Path(self.path).name
        m.add_command(label=('● ' if viewing == self.current_name else '    ') + 'Current version',
                      command=lambda: self.view_version(self.current_name))
        if not versions:
            m.add_command(label='    (no earlier versions: they appear when the picture is edited)', state='disabled')
        for v in versions:
            when = (v.get('when') or '')[:16].replace('T', ' ')
            m.add_command(label=('● ' if viewing == v['name'] else '    ') + f"{when}  ·  {v.get('by') or '?'}",
                          command=lambda n=v['name']: self.view_version(n))
        m.tk_popup(self.hist_btn.winfo_rootx(), self.hist_btn.winfo_rooty() + self.hist_btn.winfo_height())

    def view_version(self, name):
        path = Path(self.pictures.owner.picture_dir(), name)
        if not path.is_file():
            messagebox.showinfo('Idea picture', 'That version is not on this computer (yet).', parent=self)
            return
        self.load(path)
        old = name != self.current_name
        if old:
            self.version_note.configure(text='(an earlier version)')
            self.restore_btn.pack(side='left', padx=(6, 0))
            self.version_note.pack(side='left', padx=(6, 0))
        else:
            self.restore_btn.pack_forget()
            self.version_note.pack_forget()

    def restore_version(self):
        name = Path(self.path).name
        if self.pictures and name != self.current_name and self.pictures.restore(self.record_id, self.current_name, name):
            self.current_name = name
            self.restore_btn.pack_forget()
            self.version_note.pack_forget()

    def fit(self):
        if self.image is None:
            return
        self.cancel_zoom()
        self.fit_mode = True
        self.zoom = min(1, max(1, self.canvas.winfo_width()-12)/self.image.width,
                        max(1, self.canvas.winfo_height()-12)/self.image.height)
        self.zoom_target = self.zoom
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.queue_draw()

    def origin(self):
        return (max(0, (self.canvas.winfo_width()-self.image.width*self.zoom)/2),
                max(0, (self.canvas.winfo_height()-self.image.height*self.zoom)/2))

    def set_zoom(self, value, x=None, y=None):
        if self.image is None:
            return
        canvas = self.canvas
        x = canvas.winfo_width()/2 if x is None else x
        y = canvas.winfo_height()/2 if y is None else y
        ox, oy = self.origin()
        anchor = ((canvas.canvasx(x)-ox)/self.zoom, (canvas.canvasy(y)-oy)/self.zoom)
        self.cancel_zoom()
        self.zoom_target = min(16, max(min(.02, 1/max(self.image.size)), value))
        self.fit_mode = False
        start, goal, begun = self.zoom, self.zoom_target, time.monotonic()
        def frame():
            self.zoom_job = None
            frame_started = time.monotonic()
            progress = min(1, (frame_started-begun)/.16)
            eased = 1-(1-progress)**3
            self.zoom = math.exp(math.log(start)+(math.log(goal)-math.log(start))*eased) if progress < 1 else goal
            self.position_zoom(anchor, x, y)
            if self.job is not None:
                self.after_cancel(self.job)
                self.job = None
            # Use a lighter filter while moving, then sharpen the final frame.
            self.draw(fast=progress < 1)
            if progress < 1:
                self.zoom_job = self.after(max(1, 16-round((time.monotonic()-frame_started)*1000)), frame)
        self.zoom_job = self.after(1, frame)

    def position_zoom(self, anchor, x, y):
        canvas = self.canvas
        self.region()
        ox, oy = self.origin()
        width = max(canvas.winfo_width(), self.image.width*self.zoom)
        height = max(canvas.winfo_height(), self.image.height*self.zoom)
        canvas.xview_moveto((anchor[0]*self.zoom+ox-x)/width)
        canvas.yview_moveto((anchor[1]*self.zoom+oy-y)/height)

    def cancel_zoom(self):
        if self.zoom_job is not None:
            self.after_cancel(self.zoom_job)
            self.zoom_job = None
        self.zoom_target = self.zoom

    def zoom_by(self, factor, x=None, y=None):
        self.set_zoom(self.zoom_target*factor, x, y)

    def wheel(self, event, direction=None):
        direction = direction if direction is not None else max(-4, min(4, event.delta/120))
        if direction:
            self.zoom_by(1.12**direction, event.x, event.y)
        return 'break'

    def scroll_x(self, *args):
        self.cancel_zoom()
        self.canvas.xview(*args)
        self.queue_draw()

    def scroll_y(self, *args):
        self.cancel_zoom()
        self.canvas.yview(*args)
        self.queue_draw()

    def pan(self, event):
        self.cancel_zoom()
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.queue_draw()

    def resized(self, event=None):
        self.fit() if self.fit_mode else self.queue_draw()

    def region(self):
        self.canvas.configure(scrollregion=(0, 0, max(self.canvas.winfo_width(), self.image.width*self.zoom),
                                          max(self.canvas.winfo_height(), self.image.height*self.zoom)))

    def queue_draw(self):
        # Throttle rather than debounce: a stream of wheel/motion events must not
        # keep postponing the visible frame until the user stops interacting.
        if self.job is None:
            self.job = self.after(16, self.draw)

    def draw(self, fast=False):
        self.job = None
        if self.image is None:
            return
        self.region()
        canvas, zoom = self.canvas, self.zoom
        ox, oy = self.origin()
        left = max(0, math.floor((canvas.canvasx(0)-ox)/zoom))
        top = max(0, math.floor((canvas.canvasy(0)-oy)/zoom))
        right = min(self.image.width, math.ceil((canvas.canvasx(canvas.winfo_width())-ox)/zoom))
        bottom = min(self.image.height, math.ceil((canvas.canvasy(canvas.winfo_height())-oy)/zoom))
        if right > left and bottom > top:
            # Resize only the visible crop, even when a large original is zoomed to 1600%.
            crop = self.image.crop((left, top, right, bottom))
            rendered = crop.resize((max(1, round((right-left)*zoom)), max(1, round((bottom-top)*zoom))),
                                   Image.Resampling.BILINEAR if fast else Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(rendered, master=self)
            canvas.coords(self.picture_item, ox+left*zoom, oy+top*zoom)
            canvas.itemconfigure(self.picture_item, image=photo, state='normal')
            self.photo = photo
        else:
            canvas.itemconfigure(self.picture_item, state='hidden')
        self.percent.configure(text=f'{zoom*100:.0f}%')

    def destroyed(self, event):
        if event.widget is self:
            self.cancel_zoom()
            if self.job is not None:
                self.after_cancel(self.job)
                self.job = None
            if self.image is not None:
                self.image.close()
                self.image = None


class IdeaPictures:
    """Keep editors off the live-sync checkout; publish each saved edit as a new attachment revision."""
    def __init__(self, owner):
        self.owner = owner
        self.viewers, self.edits = [], []
        self.signatures = {}
        self.job = owner.after(1000, self.poll)
        owner.bind('<Destroy>', self.destroyed, add='+')

    def records(self):
        data = self.owner.todo.data
        return data.get('ideas', []) + data.get('idea_header_details', [])

    def record(self, record_id):
        return next((row for row in self.records() if row.get('id') == record_id), None)

    def preview(self, name):
        row = self.owner.selected_record()
        if not row:
            return
        path = Path(self.owner.picture_dir(), name)
        if not path.is_file():
            messagebox.showinfo('Idea picture', 'This picture is not available on this computer yet.', parent=self.owner)
            return
        for viewer in self.viewers:
            if viewer.winfo_exists() and viewer.record_id == row['id'] and viewer.path == str(path):
                viewer.deiconify()
                viewer.lift()
                return viewer
        viewer = PictureViewer(self.owner, path, lambda: self.open_external(viewer.record_id, viewer.current_name))
        viewer.record_id = row['id']
        viewer.pictures = self
        n = len(self.versions(row['id'], name))
        viewer.hist_btn.configure(text=f'🕘 History ({n})' if n else '🕘 History')
        self.viewers.append(viewer)
        return viewer

    # ---------- 🕘 history: the versions a picture had (their files stay in idea_pictures, synced) ----------
    def remember(self, row, new, old):
        hist = row.setdefault('picture_history', {})
        hist[new] = [{'name': old, 'when': time.strftime('%Y-%m-%dT%H:%M:%S'), 'by': self.owner.me()}] + hist.pop(old, [])

    def versions(self, record_id, name):
        row = self.record(record_id) or {}
        return list((row.get('picture_history') or {}).get(name, []))

    def restore(self, record_id, current, older):
        """An earlier version becomes the current one; the one it replaces goes into the history (nothing is lost)."""
        row = self.record(record_id)
        if row is None or current not in row.get('pictures', []):
            return False
        hist = row.setdefault('picture_history', {})
        past = [v for v in hist.pop(current, []) if v['name'] != older]
        hist[older] = [{'name': current, 'when': time.strftime('%Y-%m-%dT%H:%M:%S'), 'by': self.owner.me(), 'restored': True}] + past
        row['pictures'] = [older if value == current else value for value in row['pictures']]
        self.owner.touch(row)
        self.owner.fill_links()
        self.owner.app.set_status('Idea picture: the earlier version is current again (the newer one is in its History).')
        return True

    def open_external(self, record_id, name):
        row = self.record(record_id)
        if row is None or name not in row.get('pictures', []):
            return
        try:
            session = next((s for s in self.edits if s['id'] == record_id and s['name'] == name), None)
            if session is None:
                source = Path(self.owner.picture_dir(), name)
                folder = Path(os.environ.get('APPDATA') or tempfile.gettempdir(), 'OrganisationMaster', 'idea_edits')
                folder.mkdir(parents=True, exist_ok=True)
                working = folder / (uuid.uuid4().hex + source.suffix)
                shutil.copy2(source, working)
                session = dict(id=record_id, name=name, working=working, signature=signature(working), candidate=None,
                               digest=hashlib.sha256(working.read_bytes()).digest())
                self.edits.append(session)
            open_file(session['working'])
        except OSError as error:
            messagebox.showerror('Open picture', f'Could not open the picture in the default app:\n{error}', parent=self.owner)

    def import_edit(self, session, current):
        row = self.record(session['id'])
        if row is None or session['name'] not in row.get('pictures', []):
            return
        try:
            data = session['working'].read_bytes()
            digest = hashlib.sha256(data).digest()
            if digest == session['digest']:
                session['signature'] = current
                return
            image = read_image(session['working'])
            image.close()  # Reject incomplete writes; retry on the next poll.
            if signature(session['working']) != current:
                return
            name = f"{row['id']}-{uuid.uuid4().hex[:12]}{session['working'].suffix}"
            target = Path(self.owner.picture_dir(), name)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix+'.tmp')
            temporary.write_bytes(data)
            temporary.replace(target)
        except (OSError, ValueError, Image.DecompressionBombError):
            return
        old = session['name']
        row['pictures'] = [name if value == old else value for value in row['pictures']]
        self.remember(row, name, old)
        session.update(name=name, signature=current, candidate=None, digest=digest)
        self.owner.touch(row, feedback=False)
        for viewer in self.viewers:
            if viewer.winfo_exists() and viewer.record_id == row['id'] and Path(viewer.path).name == old:
                viewer.load(target)
            if viewer.winfo_exists() and viewer.record_id == row['id'] and viewer.current_name == old:
                viewer.current_name = name
        self.owner.fill_links()
        self.owner.app.set_status('Idea picture updated from the external editor.')

    def poll(self):
        self.job = None
        self.viewers = [v for v in self.viewers if v.winfo_exists()]
        for session in self.edits:
            current = signature(session['working'])
            if current and current != session['signature']:
                if current == session['candidate']:
                    self.import_edit(session, current)
                else:
                    session['candidate'] = current
        row = self.owner.selected_record() or {}
        paths = {str(Path(self.owner.picture_dir(), name)) for name in row.get('pictures', [])}
        paths.update(v.path for v in self.viewers)
        signatures = {path: signature(path) for path in paths}
        changed = {path for path, sig in signatures.items() if path in self.signatures and sig != self.signatures[path]}
        if changed:
            self.owner.fill_links()
            for viewer in self.viewers:
                if viewer.path in changed:
                    viewer.load(viewer.path)
        self.signatures = signatures
        self.job = self.owner.after(1000, self.poll)

    def destroyed(self, event):
        if event.widget is self.owner:
            if self.job is not None:
                self.owner.after_cancel(self.job)
                self.job = None
            # Keep working copies: an external editor may still have unsaved changes.
