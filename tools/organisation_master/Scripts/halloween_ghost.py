"""An occasional Halloween visitor, drawn without taking keyboard focus."""
import math
import random
import time
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk, ImageOps

import ui
import paths


def flight_pose(elapsed,direction,width,height,size,lane):
    progress=max(0,min(1,elapsed/16))
    x=max(0,width-size)*(progress if direction==1 else 1-progress)
    y=max(0,min(height-size,height*lane+math.sin(elapsed*1.8)*12+math.sin(elapsed*.7)*5))
    opacity=max(0,min(1,elapsed/.65,(16-elapsed)/.65))
    index=(0,1,2,3,2,1)[int(elapsed*7)%6]
    angle=round(math.sin(elapsed*1.6)*2)*3
    return x,y,opacity,index,angle


def pop_pose(elapsed):
    index=4 if elapsed<.16 else 5 if elapsed<.36 else 6 if elapsed<.68 else 7
    opacity=max(0,min(1,(1.1-elapsed)/.65))
    return -14*min(1,elapsed/1.1),opacity,index


class HalloweenGhost:
    CHECK_MS = 60_000
    CHANCE = 1 / 60  # About one visit per active hour, never guaranteed on launch.

    def __init__(self, app):
        self.app, self.root = app, app.root
        self.window = None
        self.timer = self.frame = None
        self.last_visit = float('-inf')
        self.closed = False
        self.sprite_cache = {}
        self.schedule()

    def eligible(self):
        return (not self.closed and not getattr(self.app, '_quitting', False)
                and ui.THEME['t'].get('name') == 'Halloween'
                and self.root.state() in ('normal', 'zoomed')
                and self.root.focus_displayof() is not None and self.root.grab_current() is None)

    def schedule(self):
        if not self.closed:
            self.timer = self.root.after(self.CHECK_MS, self.check)

    def check(self):
        self.timer = None
        if (self.window is None and self.eligible() and time.monotonic() - self.last_visit > 600
                and random.random() < self.CHANCE):
            self.spawn()
        self.schedule()

    def spawn(self):
        if self.window is not None or not self.eligible():
            return False
        self.direction = random.choice((-1, 1))
        self.size = max(64, ui.px(88))
        try:
            self.photos = self.load_sprites(self.direction)
        except (OSError, ValueError):
            return False  # An incomplete asset checkout must not break the tool.
        window = tk.Toplevel(self.root)
        window.withdraw()
        window._om_nonmodal = True
        window._om_bar = window._om_effect_layer = True
        window.overrideredirect(True)
        window.transient(self.root)
        window.configure(background='#ed7b25')
        window.attributes('-transparentcolor', '#ed7b25')
        window.attributes('-alpha', 0.0)
        window.wm_attributes('-topmost', False)
        canvas = self.canvas = tk.Canvas(window, width=self.size, height=self.size, background='#ed7b25',
                           highlightthickness=0, borderwidth=0, cursor='hand2', takefocus=False)
        canvas.pack()
        canvas._om_bar = canvas._om_effect_layer = True
        canvas.bind('<Button-1>', self.catch)
        self.window = window
        self.started = self.last_visit = time.monotonic()
        self.caught = None
        self.height_fraction = random.uniform(.22, .7)
        window.deiconify()
        self.animate()
        return True

    def load_sprites(self,direction):
        unit=max(1,round(ui.scale()*2));key=(unit,direction)
        if key not in self.sprite_cache:
            with Image.open(Path(paths.TOOL)/'secret_assets'/'ghost_pixel.png') as source:
                atlas=source.convert('RGBA');cells=[]
                for n in range(8):
                    x,y=n%4,n//4
                    cell=atlas.crop((x*atlas.width//4,y*atlas.height//2,(x+1)*atlas.width//4,(y+1)*atlas.height//2))
                    if direction<0:cell=ImageOps.mirror(cell)
                    cells.append(cell.resize((32,32),Image.Resampling.LANCZOS))
            photos={}
            for n,cell in enumerate(cells):
                size=round(32*unit*(1 if n<5 else 1+(n-4)*.07))
                sprite=cell.resize((size,size),Image.Resampling.NEAREST)
                for angle in ((-6,-3,0,3,6) if n<4 else (0,)):
                    image=sprite.rotate(angle,Image.Resampling.NEAREST,expand=True) if angle else sprite
                    photos[n,angle]=ImageTk.PhotoImage(image,master=self.root)
            self.sprite_cache[key]=photos
        return self.sprite_cache[key]

    def catch(self, event=None):
        if self.window is not None and self.caught is None:
            self.caught = time.monotonic()
            self.catch_position = self.position
            self.app.feedback('ghost')
            self.award()
        return 'break'

    def award(self):
        todo = self.app.todo_page()
        dev = next((dev for dev in todo.data['devs'] if dev['name'] == todo.me.get()), None)
        if dev is None or 'halloween_ghost' in (dev.get('secrets') or []):
            return
        dev.setdefault('secrets', []).append('halloween_ghost')
        todo.save(undoable=False, feedback=False)
        if todo.achievement_pane is not None:
            todo.achievement_pane.fill()
        self.app.set_status(f"Spooked unlocked for {dev['name']}!")

    def animate(self):
        self.frame = None
        if self.window is None:
            return
        if not self.eligible():
            self.dismiss()
            return
        now = time.monotonic()
        elapsed = now - self.started
        caught_age = now-self.caught if self.caught is not None else None
        if (caught_age is not None and caught_age>=1.1) or (caught_age is None and elapsed>=16):
            self.dismiss()
            return
        width, height = self.root.winfo_width(), self.root.winfo_height()
        if caught_age is not None:
            rise,fade,index=pop_pose(caught_age)
            x,y=self.catch_position;y+=rise;angle=0
        else:
            x,y,fade,index,angle=flight_pose(elapsed,self.direction,width,height,self.size,self.height_fraction)
        self.position=x,y
        self.canvas.delete('all')
        self.canvas.create_image(self.size/2,self.size/2,image=self.photos[index,angle])
        self.window.lift(self.root)
        self.window.geometry(f'{self.size}x{self.size}+{self.root.winfo_rootx()+int(x)}+{self.root.winfo_rooty()+int(y)}')
        self.window.attributes('-alpha', .92 * max(0, fade))
        self.frame = self.root.after(33, self.animate)

    def dismiss(self):
        if self.frame is not None:
            self.root.after_cancel(self.frame)
            self.frame = None
        if self.window is not None:
            self.window.destroy()
            self.window = None

    def close(self):
        self.closed = True
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.dismiss()
