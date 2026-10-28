"""A transparent imperial eagle celebration with window-wide confetti."""
import math
import random
import time
import tkinter as tk

import ui


class ImperialEagle:
    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.started = time.monotonic()
        self.job = None
        self.closed = False
        self.bounds = None
        self.duration = 124.5
        self.channel = owner.audio.play_sequence(('andorran_intro', 'andorran_anthem'))
        try:
            self.duration = sum(owner.audio.load(n).get_length()
                                for n in ('andorran_intro', 'andorran_anthem')) + .3
        except Exception:
            pass
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal = True
        self.window._om_bar = self.window._om_effect_layer = True
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.window.configure(background='#10120d')
        self.window.attributes('-transparentcolor', '#10120d')
        self.canvas = tk.Canvas(self.window, background='#10120d', borderwidth=0,
                                highlightthickness=0, takefocus=False)
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill='both', expand=True)
        self.eagle_rect = None
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.tag_bind('eagle', '<Enter>', lambda e: self.canvas.configure(cursor='hand2'))
        self.canvas.tag_bind('eagle', '<Leave>', lambda e: self.canvas.configure(cursor=''))
        self.window.bind('<Escape>', lambda e: self.close())
        rng = random.Random(9173)
        self.particles = [(rng.random(), rng.random(), rng.uniform(20,65),
                           rng.uniform(0, math.tau), rng.choice(('#f1cd66', '#dc9f47', '#e8b5c8', '#a7d9d3', '#f5e5af')),
                           rng.uniform(2,4)) for _ in range(115)]
        self.frames = []
        self.window.deiconify()
        self.frame()

    def frame(self):
        self.job = None
        if self.closed:
            return
        start = time.monotonic()
        elapsed = start-self.started
        if (elapsed >= self.duration or self.owner.theme != 'Andorran Dream'
                or self.root.state() not in ('normal', 'zoomed')):
            self.close()
            return
        bounds = (self.root.winfo_width(), self.root.winfo_height(),
                  self.root.winfo_rootx(), self.root.winfo_rooty())
        width, height, left, top = bounds
        if bounds != self.bounds:
            self.window.lift(self.root)
            self.window.geometry(f'{width}x{height}+{left}+{top}')
            self.canvas.configure(width=width, height=height)
            # Three times the old sprite's .82 UI scale, capped only for small windows.
            scale = min(ui.scale()*.82*3, width*.86/300, height*.84/177)
            self.frames = self.owner.frames('eagle', scale)
            self.bounds = bounds
        c = self.canvas
        c.delete('all')
        if self.frames:
            frame = self.frames[round((math.sin(elapsed*1.6)+1)*(len(self.frames)-1)/2)]
            eagle = c.create_image(width/2, height*.48+math.sin(elapsed*1.8)*ui.px(3), image=frame, tags='eagle')
            self.eagle_rect = c.bbox(eagle)
        # The particles are distributed over the whole client area from frame one.
        for n, (u,v,speed,phase,colour,size) in enumerate(self.particles):
            x = u*width + math.sin(elapsed*.7+phase)*ui.px(18)
            y = (v*(height+20)+elapsed*speed*ui.scale()) % (height+20)-10
            wobble = math.sin(elapsed*3+phase)
            span = max(.6, abs(wobble))*size*ui.scale()
            c.create_polygon(x-span,y-size,x+span,y-size*.5,x+span*.6,y+size,x-span,y+size*.5,
                             fill=colour, outline='')
        enabled = self.owner.app.sound_settings.enabled()
        if self.channel:
            if not enabled:
                self.channel.stop()
            else:
                for name in ('andorran_intro', 'andorran_anthem'):
                    sound = self.owner.audio.sounds.get(name)
                    if sound:
                        sound.set_volume(.4*self.owner.app.sound_settings.volume())
        self.job = self.root.after(max(12, 33-round((time.monotonic()-start)*1000)), self.frame)

    def click(self, event):
        if self.eagle_rect:
            left, top, right, bottom = self.eagle_rect
            if left <= event.x <= right and top <= event.y <= bottom:
                self.close()
                return 'break'

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.channel:
            self.channel.stop()  # Also cancels the queued anthem.
            self.channel = None
        if self.window.winfo_exists():
            self.window.destroy()
