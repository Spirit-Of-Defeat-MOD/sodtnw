"""Small sprite illustrations and themed arcade trim for the games window."""
from pathlib import Path
from functools import lru_cache
import math
import time
import tkinter as tk
from notebook_theme import theme_notebook

from PIL import Image, ImageTk

import paths
import ui


ORDER=('holy','shock','minority','flags','borders','passport','ideology','station','rrdle','pinpoint')
ACCENTS=('#cfa55c','#79b499','#d3a26f','#c87978','#87a9c9','#cba273','#b99ad8','#ca92d6','#7ab8ae','#db986b')


def theme_game_tabs(root):
    theme_notebook(root,'RRGame.TNotebook')


def result_band(game,score=0,solved=False):
    if game=='rrdle':return 'solved' if solved else 'unsolved'
    points=float(score)/1000 if game=='pinpoint' else float(score)
    return 'perfect' if points>=10 else 'good' if points>=7 else 'ok' if points>=4 else 'bad'


def result_motion(band,elapsed):
    """A short reaction which always settles back to the normal portrait."""
    if elapsed<0 or elapsed>=3 or band=='paused':return 0.,0.,0.
    fade=max(0,1-elapsed/3)
    if band in ('perfect','solved'):
        return math.sin(elapsed*8)*2*fade,-abs(math.sin(elapsed*math.pi*2.4))*11*fade,math.sin(elapsed*8)*6*fade
    if band=='good':
        return 0.,-abs(math.sin(elapsed*math.pi*2))*7*fade,math.sin(elapsed*6)*4*fade
    if band=='ok':return 0.,math.sin(elapsed*6)*2.5*fade,math.sin(elapsed*4)*2*fade
    return math.sin(elapsed*16)*5*fade,math.sin(min(1,elapsed/3)*math.pi)*4,-math.sin(elapsed*16)*7*fade


@lru_cache(maxsize=10)
def mascot_source(game):
    with Image.open(Path(paths.TOOL)/'secret_assets'/'rr_games_mascots.png') as source:
        n=ORDER.index(game);w,h=source.size
        return source.convert('RGBA').crop((n%5*w//5,n//5*h//2,(n%5+1)*w//5,(n//5+1)*h//2)).resize((64,64),Image.Resampling.LANCZOS)


class ResultArtwork(tk.Canvas):
    """Independent of quiz timers and scores; motion stays inside its small badge."""
    LABELS={'perfect':'Perfect!', 'good':'Good!', 'ok':'OK', 'bad':'Bad',
            'solved':'Solved!', 'unsolved':'Unsolved', 'paused':'Paused'}

    def __init__(self,parent):
        super().__init__(parent,width=ui.px(120),height=ui.px(108),highlightthickness=0)
        self._om_bar=True
        self.game='holy';self.band='paused';self.started=0;self.job=None;self.frames={}
        self.bind('<Map>',lambda e:self.animate())
        self.bind('<Unmap>',lambda e:self.stop())
        self.bind('<Destroy>',self.destroyed,add='+')

    def play(self,game,band):
        self.stop();self.game,self.band=game,band
        self.started=time.monotonic();self.animate()

    def picture(self,angle):
        angle=round(angle/2)*2;size=ui.px(76);key=(self.game,size,angle)
        if key not in self.frames:
            try:
                image=mascot_source(self.game).resize((size,size),Image.Resampling.NEAREST)
                if angle:image=image.rotate(angle,resample=Image.Resampling.NEAREST,expand=True)
                self.frames[key]=ImageTk.PhotoImage(image,master=self)
            except (OSError,ValueError):return None
        return self.frames[key]

    def draw(self):
        self.delete('all');p=ui.P;s=ui.scale();w,h=ui.px(120),ui.px(108)
        self.configure(width=w,height=h,background=p['background'])
        elapsed=max(0,time.monotonic()-self.started)
        dx,dy,angle=result_motion(self.band,elapsed)
        self.create_oval(12*s,4*s,108*s,96*s,fill=p['header_background'],outline=p['border'])
        if elapsed<3:
            if self.band in ('perfect','solved'):
                colours=(p['copper'],p['age_green'],p['age_yellow'],'#83b8d5')
                for n in range(18):
                    age=elapsed-n*.055
                    if not 0<age<1.4:continue
                    direction=n*2.4;vx=math.cos(direction)*(20+n%4*6);vy=-35-abs(math.sin(direction))*22
                    x=60+vx*age;y=44+vy*age+43*age*age
                    colour=ui._mix(colours[n%4],p['header_background'],max(0,(age-1)/.4))
                    self.create_rectangle((x-1)*s,(y-2)*s,(x+1)*s,(y+2)*s,fill=colour,outline='')
            elif self.band=='good':
                for n,(x,y) in enumerate(((23,22),(98,30),(30,66))):
                    reach=max(0,math.sin(min(1,max(0,(elapsed-n*.2)/1.1))*math.pi))*3*s
                    if reach:
                        self.create_line(x*s-reach,y*s,x*s+reach,y*s,fill=p['copper'],width=max(1,ui.px(2)))
                        self.create_line(x*s,y*s-reach,x*s,y*s+reach,fill=p['copper'],width=max(1,ui.px(2)))
            elif self.band in ('bad','unsolved') and .3<elapsed<1.8:
                y=(28+(elapsed-.3)*12)*s
                self.create_oval(93*s,y,97*s,y+6*s,fill='#83b8d5',outline='')
        photo=self.picture(angle)
        if photo:self.create_image(round((60+dx)*s),round((49+dy)*s),image=photo)
        colour=p['age_green'] if self.band in ('perfect','good','solved') else p['muted']
        self.create_text(60*s,100*s,text=self.LABELS[self.band],font='om_small_bold',fill=colour)

    def animate(self):
        self.stop();self.draw()
        if self.winfo_ismapped() and time.monotonic()-self.started<3:
            self.job=self.after(33,self.animate)

    def stop(self):
        if self.job is not None:
            self.after_cancel(self.job);self.job=None

    def destroyed(self,event):
        if event.widget is self:self.stop()


class GameBanner(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,height=ui.px(82),highlightthickness=0,borderwidth=0)
        self._om_bar=True
        self.game='holy';self.title='RR Games';self.subtitle='Pick your next challenge'
        self.photos={};self.job=None
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Destroy>',self.destroyed,add='+')
        self.animate()

    def artwork(self,game,size=72):
        key=(game,ui.px(size))
        if key not in self.photos:
            try:
                cell=mascot_source(game).resize((ui.px(size),ui.px(size)),Image.Resampling.NEAREST)
                self.photos[key]=ImageTk.PhotoImage(cell,master=self)
            except (OSError,ValueError):
                return None
        return self.photos[key]

    def set_game(self,game,title,subtitle):
        self.game,self.title,self.subtitle=game,title,subtitle
        self.draw()

    def draw(self):
        self.delete('all');p=ui.P;w=max(200,self.winfo_width());h=ui.px(82)
        self.configure(height=h,background=p['background'])
        accent=ACCENTS[ORDER.index(self.game)]
        for n in range(20):
            self.create_rectangle(0,h*n/20,w,h*(n+1)/20+1,fill=ui._mix(p['header_background'],p['surface'],n/30),outline='')
        self.create_rectangle(0,0,ui.px(4),h,fill=accent,outline='')
        self.create_line(ui.px(16),h-2,w-ui.px(16),h-2,fill=p['border'])
        self.create_text(ui.px(18),ui.px(13),anchor='nw',text='R R   G A M E S   /   D E V   A R C A D E',font='om_small',fill=p['muted'])
        self.create_text(ui.px(18),ui.px(31),anchor='nw',text=self.title,font='om_title',fill=p['header_foreground'],width=max(100,w-ui.px(160)))
        self.create_text(ui.px(18),ui.px(62),anchor='nw',text=self.subtitle,font='om_small',fill=p['muted'])
        cx=w-ui.px(62);cy=h/2+math.sin(time.monotonic()*2)*ui.px(1)
        for dx,dy in ((-46,-19),(41,22),(-35,27)):
            x,y=cx+ui.px(dx),cy+ui.px(dy)
            self.create_line(x-3,y,x+3,y,fill=accent);self.create_line(x,y-3,x,y+3,fill=accent)
        photo=self.artwork(self.game)
        if photo:self.create_image(cx,cy,image=photo)

    def animate(self):
        self.job=None
        if self.winfo_ismapped():self.draw()
        self.job=self.after(100,self.animate)

    def destroyed(self,event):
        if event.widget is self and self.job is not None:
            self.after_cancel(self.job);self.job=None


def stage(canvas):
    p=ui.P;w=max(100,canvas.winfo_width());h=max(100,canvas.winfo_height())
    canvas.configure(background=p['input_background'])
    canvas.create_rectangle(6,6,w-6,h-6,outline=p['border'])
    for x,y,sx,sy in ((12,12,1,1),(w-12,12,-1,1),(12,h-12,1,-1),(w-12,h-12,-1,-1)):
        canvas.create_line(x+sx*18,y,x,y,x,y+sy*18,fill=ui._mix(p['copper'],p['border'],.45),width=max(1,ui.px(2)))
