"""A small cat stretches up to scratch the selected task's title."""
import math
import time
import tkinter as tk
from tkinter import font as tkfont

from PIL import Image, ImageTk

import ui


def pose(elapsed):
    """Rise, reach, rake around the title, retract, then fade the marks."""
    rise=min(1,elapsed/.65)
    reach=max(0,min(1,(elapsed-.65)/1.05));reach=reach*reach*(3-2*reach)
    if elapsed>5.7:reach*=max(0,1-(elapsed-5.7)/.8)
    retreat=max(0,min(1,(elapsed-6.5)/.7))
    scratch=max(0,min(1,(elapsed-1.7)/4))
    fade=max(0,min(1,(elapsed-6)/5))
    return rise,reach,retreat,scratch,fade


def scratch_strokes(rect,scale=1):
    x,y,w,h=rect;p=scale
    strokes=[]
    for f in (.12,.45,.8):strokes.append((x+w*f,y-5*p,5*p,9*p))
    strokes.append((x+w+4*p,y+h*.4,-9*p,6*p))
    for f in (.8,.45,.12):strokes.append((x+w*f,y+h+5*p,-6*p,-9*p))
    strokes.append((x-5*p,y+h*.5,9*p,-6*p))
    return strokes


def stroke_pose(elapsed,strokes):
    phase=max(0,min(len(strokes)-.0001,(elapsed-1.7)/.5))
    index=int(phase);local=phase-index;x,y,dx,dy=strokes[index]
    if local<=.58:
        progress=local/.58
        return (x+dx*progress,y+dy*progress),(dx,dy)
    if index==len(strokes)-1:return (x+dx,y+dy),(dx,dy)
    nx,ny,ndx,ndy=strokes[index+1];progress=(local-.58)/.42
    progress=progress*progress*(3-2*progress)
    return (x+dx+(nx-x-dx)*progress,y+dy+(ny-y-dy)*progress-math.sin(progress*math.pi)*8),(ndx,ndy)


class CatScratch:
    DURATION = 11.1

    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.target = owner.todo.d_title
        self.task_ref = (owner.todo.cur or {}).get('ref')
        self.started = time.monotonic()
        self.job = None
        self.bounds = None
        self.closed = False
        self.meowed = False
        self.unit = max(1, round(ui.scale() * 1.5))
        self.body_width, self.body_height = 48 * self.unit, 64 * self.unit
        with Image.open(owner.asset_path('cat_pixel')) as source:
            sprite = source.convert('RGBA')
            sprite = sprite.crop(sprite.getbbox())
            sprite.thumbnail((48, 64), Image.Resampling.NEAREST)
            sprite = sprite.resize((sprite.width * self.unit, sprite.height * self.unit), Image.Resampling.NEAREST)
            self.photo = ImageTk.PhotoImage(sprite, master=self.root)
        self.body_width, self.body_height = self.photo.width(), self.photo.height()
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal = True
        self.window._om_bar = self.window._om_effect_layer = True
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.key_colour = ui.P['background']
        self.window.configure(background=self.key_colour)
        self.window.attributes('-transparentcolor', self.key_colour)
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.window, background=self.key_colour, borderwidth=0,
                                highlightthickness=0, takefocus=False)
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill='both', expand=True)
        self.window.deiconify()
        self.frame()

    def geometry(self):
        tab = self.target
        tx, ty = tab.winfo_rootx(), tab.winfo_rooty()
        tw, th = tab.winfo_width(), tab.winfo_height()
        # A fill-x label can be much wider than its title. Reach for the words.
        font = tkfont.Font(root=self.root,font=tab.cget('font'))
        tw = min(tw,max(ui.px(40),font.measure(tab.cget('text'))+ui.px(12)))
        floor = ty + th + ui.px(135)
        floor = min(floor, self.root.winfo_rooty() + self.root.winfo_height() - 8)
        left = max(self.root.winfo_rootx(), tx - self.body_width // 2 - ui.px(20))
        top = max(self.root.winfo_rooty(),ty-ui.px(30))
        width = min(self.root.winfo_rootx()+self.root.winfo_width()-left,
                    max(tw + self.body_width + ui.px(60), self.body_width + 24))
        return (left, top, width, max(th + self.body_height, floor - top)), (tx-left, ty-top, tw, th)

    def frame(self):
        self.job = None
        if self.closed:
            return
        began = time.monotonic()
        elapsed = began - self.started
        if (elapsed >= self.DURATION or self.root.state() not in ('normal', 'zoomed')
                or not self.target.winfo_ismapped() or self.owner.theme != 'Rising Sun'
                or (self.owner.todo.cur or {}).get('ref') != self.task_ref):
            self.close()
            return
        bounds, tab = self.geometry()
        left, top, width, height = bounds
        if bounds != self.bounds:
            self.window.lift(self.root)
            self.window.geometry(f'{width}x{height}+{left}+{top}')
            self.bounds = bounds
        c = self.canvas
        c.delete('all')
        rise, reach, retreat, scratch, fade = pose(elapsed)
        tx, ty, tw, th = tab
        strokes=scratch_strokes(tab,ui.scale())
        point,direction=stroke_pose(elapsed,strokes)
        if elapsed>=1.7 and not self.meowed:
            self.meowed=True;self.owner.audio.play('cat_meow')
        cat_x=min(width-self.body_width*.5-ui.px(10),tx+tw+self.body_width*.3)
        cat_bottom=height+(1-rise+retreat)*self.body_height
        body_top=cat_bottom-self.body_height
        if elapsed<7.2:
            c.create_image(round(cat_x),round(cat_bottom),image=self.photo,anchor='s')
            shoulder=(cat_x-self.body_width*.28,body_top+self.body_height*.61)
            length=max(1,math.hypot(*direction));forward=(direction[0]/length,direction[1]/length)
            # The claw tips meet the moving scratch, with the wrist behind them.
            target=(point[0]-forward[0]*7*self.unit,point[1]-forward[1]*7*self.unit)
            rest=(shoulder[0]-ui.px(5),shoulder[1]+ui.px(23))
            wrist=(rest[0]+(target[0]-rest[0])*reach,rest[1]+(target[1]-rest[1])*reach)
            elbow=(shoulder[0]+(wrist[0]-shoulder[0])*.43-ui.px(10)*reach,
                   shoulder[1]+(wrist[1]-shoulder[1])*.4+ui.px(20)*reach)
            self.arm_segment(shoulder,elbow,5*self.unit,4*self.unit)
            self.arm_segment(elbow,wrist,4*self.unit,3*self.unit)
            self.paw(wrist,math.atan2(direction[1],direction[0])+math.pi/2,reach>.95)
        if scratch>0 and fade<1:
            bg=self.target.cget('background')
            colour=ui._mix('#a53754',bg,fade);highlight=ui._mix('#f8d9d1',bg,fade)
            for index,(x,y,dx,dy) in enumerate(strokes):
                progress=max(0,min(1,(elapsed-1.7-index*.5)/.29))
                if progress<=0:continue
                length=max(1,math.hypot(dx,dy));nx,ny=-dy/length,dx/length
                for finger in (-1,0,1):
                    ox,oy=nx*finger*3*self.unit,ny*finger*3*self.unit
                    points=(x+ox,y+oy,x+ox+dx*.45*progress,y+oy+dy*.3*progress,
                            x+ox+dx*progress,y+oy+dy*progress)
                    c.create_line(*points,fill=colour,width=max(1,self.unit),tags=('scratch',f'scratch:{index}'))
                    c.create_line(*[v+self.unit*.5 for v in points],fill=highlight,width=max(1,self.unit//2),tags=('scratch',f'scratch:{index}'))
        self.job = self.root.after(max(12, 33-round((time.monotonic()-began)*1000)), self.frame)

    def arm_segment(self,start,end,start_width,end_width):
        c=self.canvas;p=self.unit;dx,dy=end[0]-start[0],end[1]-start[1]
        length=max(1,math.hypot(dx,dy));nx,ny=-dy/length,dx/length
        def offset(point,distance):return point[0]+nx*distance,point[1]+ny*distance
        points=(*offset(start,start_width),*offset(end,end_width),*offset(end,-end_width),*offset(start,-start_width))
        c.create_polygon(*points,fill='#474051',outline='#211e2b',width=p)
        c.create_line(*offset(start,-start_width*.35),*offset(end,-end_width*.35),fill='#66596b',width=2*p)
        # Repeating fur follows the forearm's direction and keeps a fixed pixel size.
        for distance in range(5*p,int(length)-3*p,7*p):
            ratio=distance/length;cx,cy=start[0]+dx*ratio,start[1]+dy*ratio
            span=start_width+(end_width-start_width)*ratio
            for side in (-1,1):
                c.create_line(cx+nx*span*side,cy+ny*span*side,
                    cx+nx*(span+p)*side-dx/length*p,cy+ny*(span+p)*side-dy/length*p,
                    fill='#211e2b',width=p)
            c.create_line(cx-nx*p,cy-ny*p,cx+nx*p,cy+ny*p,fill='#746477',width=p)

    def paw(self,wrist,angle,claws):
        c=self.canvas;p=self.unit;co,si=math.cos(angle),math.sin(angle)
        def at(x,y):return round(wrist[0]+(x*co-y*si)*p),round(wrist[1]+(x*si+y*co)*p)
        outline=((-4,3),(-5,0),(-5,-3),(-3,-5),(3,-5),(5,-3),(5,0),(4,3))
        c.create_polygon(*[v for point in outline for v in at(*point)],fill='#474051',outline='#211e2b',width=p)
        for finger in (-1,0,1):
            c.create_line(*at(finger*3,-1),*at(finger*3,-3),fill='#bd929b',width=2*p)
            if claws:c.create_line(*at(finger*3,-4),*at(finger*3,-6),*at(finger*3+1,-7),fill='#fff0d7',width=p)

    def close(self):
        if self.closed:return
        self.closed = True
        self.owner.audio.stop('cat_meow')
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window.winfo_exists():
            self.window.destroy()
