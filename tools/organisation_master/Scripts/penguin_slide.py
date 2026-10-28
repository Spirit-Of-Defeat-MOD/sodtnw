"""A pixel penguin emerges from the weather strip and collides with a real UI edge."""
import math
import random
import time
import tkinter as tk

from PIL import Image, ImageTk

import ui
from sorel_burn import visible_rect


def collision_edges(root, reveal, floor, width, height):
    """Only painted controls can be obstacles; plain layout frames have no wall."""
    result = []
    pending = list(root.winfo_children())
    nose_y = floor-height*.48
    while pending:
        widget = pending.pop()
        if widget.winfo_toplevel() is not root or not widget.winfo_ismapped():
            continue
        if getattr(widget,'_om_effect_layer',False):
            continue
        pending.extend(widget.winfo_children())
        cls = widget.winfo_class()
        # Section bodies stretch through empty space; do not treat their bounds
        # as walls. Lists and framed editors have a visible physical edge.
        solid = cls in ('Treeview','Text','Listbox','Entry','TEntry','TCombobox')
        if cls in ('Text','Listbox','Entry'):
            solid = any(int(float(widget.cget(option))) > 0 for option in ('borderwidth','highlightthickness'))
        if not solid:
            continue
        rect = visible_rect(widget,root)
        if rect:
            left,top,right,bottom = rect
            if top <= nose_y <= bottom:
                result.extend(edge for edge in (left,right)
                              if reveal+width+ui.px(35) < edge < root.winfo_width()-ui.px(8))
    return result


def motion(t, start, wall, width, floor, scale, through=False, travel_time=2.1):
    if through:
        progress = min(1, t/travel_time)
        return start+(wall+width-start)*progress**1.12, floor, 'slide' if t < travel_time else 'finish', max(0,t-travel_time)
    if t < 2.1:
        return start + (wall-width-start)*(t/2.1)**1.12, floor, 'slide', 0
    impact = t-2.1
    if impact < .14:
        return wall-width, floor, 'impact', 0
    flight = impact-.14
    x = wall-width-72*scale*flight
    y = floor-350*scale*flight+325*scale*flight*flight
    return x, y, 'shock' if flight < .65 else 'fall', flight


class PenguinParade:
    """One secret scene with up to ten independently timed penguins."""
    LIMIT = 10

    def __init__(self, owner):
        self.owner = owner
        self.penguins = []
        self.sprites = None
        self._closed = False
        self.launch()

    @property
    def closed(self):
        return self._closed or not any(not penguin.closed for penguin in self.penguins)

    def launch(self):
        if self._closed:
            return
        self.penguins = [penguin for penguin in self.penguins if not penguin.closed]
        if len(self.penguins) >= self.LIMIT:
            return
        penguin = PenguinSlide(self.owner, self.sprites)
        self.sprites = (penguin.photos, penguin.turns)
        self.penguins.append(penguin)

    def close(self):
        self._closed = True
        for penguin in self.penguins:
            penguin.close()
        self.penguins.clear()
        self.sprites = None


class PenguinSlide:
    def __init__(self, owner, sprites=None):
        self.owner, self.root = owner, owner.root
        self.started = time.monotonic()
        self.closed = False
        self.job = None
        self.bounds = None
        self.scale = ui.scale()
        self.width, self.height = ui.px(96), ui.px(74)
        self.photos = []
        self.turns = []
        if sprites is not None:
            self.photos, self.turns = sprites
        else:
            self.load_sprites(owner)
        self.setup(owner)

    def load_sprites(self, owner):
        with Image.open(owner.asset_path('penguin_slide')) as source:
            atlas = source.convert('RGBA')
            for index in range(4):
                cell = atlas.crop((round(index*atlas.width/4), 0, round((index+1)*atlas.width/4), atlas.height))
                cell = cell.crop(cell.getbbox())
                cell.thumbnail((self.width, self.height), Image.Resampling.NEAREST)
                self.photos.append(ImageTk.PhotoImage(cell, master=self.root))
                if index == 3:
                    for angle in range(0, 360, 15):
                        self.turns.append(ImageTk.PhotoImage(cell.rotate(angle, resample=Image.Resampling.NEAREST, expand=True), master=self.root))

    def setup(self, owner):
        anchor = owner.temperature
        self.reveal = anchor.winfo_rootx()-self.root.winfo_rootx()+anchor.winfo_width()-ui.px(8)
        self.start = self.reveal-self.photos[0].width()
        self.floor = anchor.winfo_rooty()-self.root.winfo_rooty()+anchor.winfo_height()-ui.px(4)
        self.wall = self.root.winfo_width()-ui.px(8)
        candidates = collision_edges(self.root,self.reveal,self.floor,self.width,self.photos[0].height())
        if candidates:
            self.wall = min(candidates)
        self.through = not candidates
        if self.through:
            self.wall = self.root.winfo_width()
        self.travel_time = max(2.1,min(4.5,(self.wall-self.start)/(420*self.scale))) if self.through else 2.1
        self.duration = self.travel_time+1.2 if self.through else 7
        rng = random.Random(167)
        self.confetti = [(rng.uniform(65,165),rng.uniform(-210,-65),rng.uniform(0,math.tau),
                          rng.choice(('#e9faff','#83bdd1','#b8551f','#f2cf82'))) for _ in range(22)]
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal = True
        self.window._om_bar = self.window._om_effect_layer = True
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.key = ui.P['background']
        self.window.configure(background=self.key)
        self.window.attributes('-transparentcolor', self.key)
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.window, background=self.key, borderwidth=0,
                                highlightthickness=0, takefocus=False)
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill='both', expand=True)
        self.window.deiconify()
        self.frame()

    def frame(self):
        self.job = None
        if self.closed:
            return
        began = time.monotonic()
        elapsed = began-self.started
        if (elapsed > self.duration or self.owner.theme != 'Arctic Station'
                or self.root.state() not in ('normal', 'zoomed')):
            self.close()
            return
        bounds = (self.root.winfo_width(), self.root.winfo_height(),
                  self.root.winfo_rootx(), self.root.winfo_rooty())
        w, h, left, top = bounds
        if bounds != self.bounds:
            self.window.lift(self.root)
            self.window.geometry(f'{w}x{h}+{left}+{top}')
            self.canvas.configure(width=w, height=h)
            self.bounds = bounds
        x, foot, state, flight = motion(elapsed, self.start, self.wall, self.photos[0].width(), self.floor, self.scale,
                                        self.through,self.travel_time)
        if state == 'fall' and foot-self.height > h+self.height:
            self.close()
            return
        c = self.canvas
        c.delete('all')
        if state == 'slide':
            photo = self.photos[0]
            # Clip the reveal rather than covering any of the interface with a box.
            cut = max(0, round(self.reveal-x))
            if cut < photo.width():
                if cut:
                    clipped = tk.PhotoImage(master=self.root, width=photo.width()-cut, height=photo.height())
                    clipped.tk.call(str(clipped), 'copy', str(photo), '-from', cut, 0, photo.width(), photo.height(), '-to', 0, 0)
                    self.reveal_photo = clipped
                    c.create_image(round(x+cut), round(foot), image=clipped, anchor='sw')
                else:
                    c.create_image(round(x), round(foot), image=photo, anchor='sw')
            for n in range(3):
                trail_x = max(self.reveal, x-ui.px(8+n*7))
                if trail_x < x:
                    c.create_line(trail_x, foot-ui.px(3+n*4), x-ui.px(3), foot-ui.px(3+n*4),
                                  fill=ui._mix('#7eb7cc', self.key, n*.2), width=max(1, ui.px(2)))
        elif state == 'finish':
            # A small off-screen landing celebration, spilling back from the exit edge.
            for speed,vy,phase,colour in self.confetti:
                cx = w-ui.px(3)-speed*self.scale*flight
                cy = self.floor+vy*self.scale*flight+170*self.scale*flight*flight
                span = ui.px(3)*max(.25,abs(math.sin(phase+flight*8)))
                fill = ui._mix(colour,self.key,max(0,min(1,(flight-.65)/.55)))
                c.create_rectangle(cx-span,cy-ui.px(2),cx+span,cy+ui.px(2),fill=fill,outline='')
        else:
            photo = self.photos[1] if state == 'impact' else self.photos[2] if state == 'shock' else self.turns[int((flight-.65)*240/15) % len(self.turns)]
            c.create_image(round(x+self.photos[0].width()/2), round(foot), image=photo, anchor='s')
            if state == 'shock':
                c.create_text(x+self.width*.65, foot-photo.height()-ui.px(13), text='!',
                              fill=ui.P['copper'], font=('Consolas', ui.px(17), 'bold'))
            if state == 'impact':
                for dy in (-13, 0, 13):
                    c.create_line(self.wall-ui.px(2), self.floor-self.height*.45,
                                  self.wall+ui.px(8), self.floor-self.height*.45+ui.px(dy),
                                  fill=ui.P['copper'], width=max(1, ui.px(2)))
        self.job = self.root.after(max(10, 16-round((time.monotonic()-began)*1000)), self.frame)

    def close(self):
        self.closed = True
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window.winfo_exists():
            self.window.destroy()
