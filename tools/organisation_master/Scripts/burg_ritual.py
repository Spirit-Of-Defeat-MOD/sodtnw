"""Toggleable native panel trim for the hidden BurgSys effect."""
import math
import time
import tkinter as tk

from PIL import Image, ImageChops, ImageFilter, ImageTk

import ui
from sorel_burn import visible_rect


def sun_frames(path, size, root):
    # Find the outline at full source resolution. Doing morphology after shrinking
    # the reference closes its spokes into the solid discs seen in the old effect.
    with Image.open(path) as source:
        mask = source.convert('RGBA').getchannel('A')
        mask = mask.crop(mask.getbbox())
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(7)),
                              mask.filter(ImageFilter.MinFilter(5)))
    edge.thumbnail((size*3, size*3), Image.Resampling.LANCZOS)
    pad = 12
    stroke = Image.new('L', (size*3+2*pad, size*3+2*pad))
    stroke.paste(edge, ((stroke.width-edge.width)//2,(stroke.height-edge.height)//2))
    out = Image.new('RGBA', stroke.size, '#b985e5')
    out.putalpha(stroke)
    # Native canvases blend these transparent pixels with their actual panel
    # colour. There is no colour-keyed overlay, black fill or dark glow layer.
    return [ImageTk.PhotoImage(out.rotate(n*7.5,resample=Image.Resampling.BICUBIC)
            .resize((size+8,size+8),Image.Resampling.LANCZOS),master=root) for n in range(48)]


class BurgRitual:
    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.started = time.monotonic()
        self.job = None
        self.closed = False
        self.channel = owner.audio.play_sequence(('burg_demon','burg_laugh'))
        self.frames = sun_frames(owner.asset_path('burg_sun'),ui.px(96),self.root)
        self.panels = {}
        self.next_panels = 0
        self.frame()

    def sync_panels(self):
        eligible = []
        for section in list(ui._sections):
            rect = visible_rect(section,self.root)
            if rect and not section.collapsed and section.body.winfo_manager() == 'pack':
                left,top,right,bottom = rect
                if right-left >= ui.px(550) and bottom-top >= ui.px(135):
                    eligible.append((section,(right-left)*(bottom-top)))
        # A few large, readable seals, rather than a stamp on every tiny header.
        chosen = {section for section,_ in sorted(eligible,key=lambda item:item[1],reverse=True)[:3]}
        for section in list(self.panels):
            if section not in chosen:
                canvas = self.panels.pop(section)
                if canvas.winfo_exists():canvas.destroy()
        for section in chosen:
            if section in self.panels:continue
            canvas = tk.Canvas(section,width=ui.px(116),height=ui.px(110),
                background=ui.P['background'],highlightthickness=0,borderwidth=0,takefocus=False)
            canvas._om_bar = canvas._om_effect_layer = True
            # Reserve a real strip alongside the body. Native stacking means the
            # Files Changed dialog naturally covers this trim, like any other UI.
            canvas.pack(side='right',fill='y',before=section.body,padx=(ui.px(3),0))
            self.panels[section] = canvas

    def sigil(self,c,x,y,r,t,pulse):
        colour = ui._mix('#b985e5','#754397',.25*(1-pulse))
        points = [(x+math.cos(math.pi/2+n*math.tau/5+t*.1)*r*.8,
                   y+math.sin(math.pi/2+n*math.tau/5+t*.1)*r*.8) for n in range(5)]
        star = [v for index in (0,2,4,1,3,0) for v in points[index]]
        c.create_oval(x-r,y-r,x+r,y+r,outline=colour,width=max(1,ui.px(1)))
        c.create_line(*star,fill=colour,width=max(1,ui.px(1)),joinstyle='round')

    def frame(self):
        self.job = None
        if self.closed:return
        began = time.monotonic()
        if self.owner.theme != 'BurgSys':
            self.close();return
        if began >= self.next_panels:
            self.sync_panels();self.next_panels=began+.2
        t=began-self.started
        for n,canvas in enumerate(self.panels.values()):
            if not canvas.winfo_exists() or not canvas.winfo_ismapped():continue
            w,h=canvas.winfo_width(),canvas.winfo_height()
            canvas.delete('all')
            canvas.create_line(0,ui.px(8),0,h-ui.px(8),fill=ui.P['border'])
            index=(int(t*2.4)*(1 if n%2 else -1)+n*7)%48
            canvas.create_image(w/2,min(h/2,ui.px(60)),image=self.frames[index])
            if h>=ui.px(205):
                self.sigil(canvas,w/2,h-ui.px(33),ui.px(19),t+n,(math.sin(t*1.8)+1)/2)
        if self.channel:
            if not self.owner.app.sound_settings.enabled():self.channel.stop()
            else:
                for name in ('burg_demon','burg_laugh'):
                    sound=self.owner.audio.sounds.get(name)
                    if sound:sound.set_volume(.4*self.owner.app.sound_settings.volume())
        self.job=self.root.after(max(15,42-round((time.monotonic()-began)*1000)),self.frame)

    def close(self):
        if self.closed:return
        self.closed=True
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        if self.channel:self.channel.stop();self.channel=None
        for canvas in self.panels.values():
            if canvas.winfo_exists():canvas.destroy()
        self.panels.clear()
