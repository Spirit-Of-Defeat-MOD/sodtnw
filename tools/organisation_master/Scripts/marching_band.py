"""Clickable Field Grey instruments with small rising musical notes."""
import math
import random
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image,ImageTk

import ui


class MarchingBand(ttk.Frame):
    INSTRUMENTS=(('horn','French horn'),('tuba','Tuba'),('cymbals','Cymbals'),('bugle','Bugle'),('drum','Military drum'))

    def __init__(self,owner):
        super().__init__(owner.root)
        self.owner=owner;self.widgets={};self.photos={};self.notes=[];self.job=None;self.closed=False
        self.random=random.Random()
        for key,title in self.INSTRUMENTS:
            canvas=tk.Canvas(self,width=ui.px(72),height=ui.px(96),highlightthickness=0,borderwidth=0,cursor='hand2',takefocus=True)
            canvas._om_bar=True
            canvas.pack(side='right',padx=ui.px(3))
            canvas.bind('<Button-1>',lambda e,k=key:self.play(k))
            canvas.bind('<Return>',lambda e,k=key:self.play(k))
            canvas.bind('<space>',lambda e,k=key:self.play(k))
            canvas.bind('<Enter>',lambda e,c=canvas:self.hover(c,True))
            canvas.bind('<Leave>',lambda e,c=canvas:self.hover(c,False))
            canvas.instrument_title=title;canvas.hovered=False
            self.widgets[key]=canvas
        self.retheme()

    def hover(self,canvas,hovered):
        canvas.hovered=hovered;self.paint()

    def retheme(self):
        self.notes.clear()
        for key in self.widgets:
            path=self.owner.asset_path('field_'+key)
            if path.is_file():
                with Image.open(path) as source:
                    image=source.convert('RGBA')
                    box=image.getchannel('A').point(lambda alpha:255 if alpha>100 else 0).getbbox()
                    image=image.crop(box or image.getbbox())
                    image.thumbnail((ui.px(62),ui.px(48)),Image.Resampling.NEAREST)
                    self.photos[key]=ImageTk.PhotoImage(image,master=self)
        self.paint()

    def play(self,key):
        if self.closed or self.owner.theme!='Field Grey' or not self.owner.drum_var.get():return 'break'
        if key=='drum':self.owner.hit_drum()
        else:self.owner.audio.play('field_'+key)
        now=time.monotonic()
        self.notes.extend(dict(key=key,born=now,phase=self.random.uniform(0,math.tau),
            x=self.random.uniform(-15,15),glyph=self.random.choice(('♪','♫'))) for _ in range(3))
        self.notes=self.notes[-90:]
        if self.job is None:self.animate()
        return 'break'

    def paint(self):
        now=time.monotonic();bg=ui.P['background']
        for key,canvas in self.widgets.items():
            canvas.configure(background=bg);canvas.delete('all')
            w,h=ui.px(72),ui.px(96)
            if canvas.hovered:
                canvas.create_rectangle(2,h-ui.px(58),w-2,h-2,fill=ui.P['surface'],outline=ui.P['border'])
            if key in self.photos:canvas.create_image(w/2,h-ui.px(30),image=self.photos[key])
            for note in self.notes:
                if note['key']!=key:continue
                age=now-note['born'];progress=min(1,age/1.45)
                x=w/2+ui.px(note['x']+math.sin(age*4+note['phase'])*5)
                y=h-ui.px(50+progress*38)
                canvas.create_text(x,y,text=note['glyph'],fill=ui._mix(ui.P['copper'],bg,max(0,(progress-.55)/.45)),font=('Segoe UI',ui.px(12),'bold'))

    def animate(self):
        self.job=None
        if self.closed:return
        if self.owner.theme!='Field Grey' or not self.owner.drum_var.get():self.notes.clear()
        now=time.monotonic();self.notes=[note for note in self.notes if now-note['born']<1.45]
        self.paint()
        if self.notes:self.job=self.after(25,self.animate)

    def close(self):
        self.closed=True
        if self.job is not None:self.after_cancel(self.job);self.job=None
