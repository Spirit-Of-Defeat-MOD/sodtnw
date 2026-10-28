"""Small candy canes burst from the stocking and bounce off visible controls."""
import math
import random
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import ui
from sorel_burn import visible_rect


def collect_obstacles(root):
    rectangles=[]
    pending=list(root.winfo_children())
    while pending:
        widget=pending.pop()
        if (getattr(widget,'_om_effect_layer',False) or widget.winfo_toplevel() is not root
                or not widget.winfo_ismapped()):continue
        pending.extend(widget.winfo_children())
        if widget.winfo_class() not in ('Treeview','Text','Listbox','TButton','Button','TEntry','Entry','TCombobox'):continue
        rect=visible_rect(widget,root)
        if rect:rectangles.append(rect)
    # Section title bars are visible UI surfaces too; layout frames are not.
    for section in list(ui._sections):
        header=getattr(section,'head',None)
        if header:
            rect=visible_rect(header,root)
            if rect:rectangles.append(rect)
    return list(dict.fromkeys(rectangles))


def hit_surface(x,y,nx,ny,rect,radius):
    """Sweep the candy centre against an expanded visible rectangle."""
    l,t,r,b=rect;l-=radius;t-=radius;r+=radius;b+=radius
    if l<x<r and t<y<b:return None
    dx,dy=nx-x,ny-y
    enter,leave=0.,1.;normal=None
    for origin,delta,low,high,nlow,nhigh in ((x,dx,l,r,(-1,0),(1,0)),(y,dy,t,b,(0,-1),(0,1))):
        if abs(delta)<1e-8:
            if not low<=origin<=high:return None
            continue
        first,last=(low-origin)/delta,(high-origin)/delta
        n=nlow
        if first>last:first,last=last,first;n=nhigh
        if first>=enter:enter=first;normal=n
        leave=min(leave,last)
        if enter>leave:return None
    if normal is not None and 0<=enter<=1:return enter,normal
    return None


def advance(candy,dt,rects,width,height,scale):
    if candy.get('resting'):return
    radius=3*scale
    candy['vy']+=520*scale*dt
    x,y=candy['x'],candy['y'];nx=x+candy['vx']*dt;ny=y+candy['vy']*dt
    hits=[]
    for index,rect in enumerate(rects):
        if index in candy['hit']:continue
        if (max(x,nx)+radius<rect[0] or min(x,nx)-radius>rect[2]
                or max(y,ny)+radius<rect[1] or min(y,ny)-radius>rect[3]):continue
        hit=hit_surface(x,y,nx,ny,rect,radius)
        if hit:hits.append((hit[0],hit[1],index))
    if hits:
        at,normal,index=min(hits,key=lambda item:item[0]);candy['hit'].add(index)
        nx=x+(nx-x)*at+normal[0]*scale;ny=y+(ny-y)*at+normal[1]*scale
        if normal[0]:candy['vx']=-candy['vx']*.68
        else:
            candy['vy']=-candy['vy']*.62
            # Keep moving across a ledge rather than resting on a control.
            if abs(candy['vx'])<65*scale:candy['vx']=(-1 if candy['vx']<0 else 1)*65*scale
        candy['spin']*=-.8
    if nx<radius:nx=radius;candy['vx']=abs(candy['vx'])*.65
    if nx>width-radius:nx=width-radius;candy['vx']=-abs(candy['vx'])*.65
    if ny>height-9*scale:
        ny=height-9*scale
        if abs(candy['vy'])>65*scale:candy['vy']=-abs(candy['vy'])*.35
        else:candy['vy']=0
        candy['vx']*=.88;candy['spin']*=.8
        if candy['vy']==0 and abs(candy['vx'])<8*scale:candy['resting']=True
    candy['x'],candy['y']=nx,ny
    candy['angle']+=candy['spin']*dt


class CandyBurst:
    LIMIT=500
    REST_SECONDS=25
    FADE_SECONDS=3

    def __init__(self,owner,source=None,theme='Christmas',kind='cane'):
        self.owner,self.root=owner,owner.root
        self.source=source or owner.stocking;self.theme=theme;self.kind=kind
        self.closed=False;self.job=None;self.bounds=None
        self.started=self.last=time.monotonic();self.scale=ui.scale()
        self.rects=collect_obstacles(self.root)
        icon=self.source
        self.size=.9*min(icon.winfo_width(),icon.winfo_height())
        self.candies=[];self.rng=random.Random()
        self.window=tk.Toplevel(self.root);self.window.withdraw()
        self.window._om_nonmodal=self.window._om_bar=self.window._om_effect_layer=True
        self.window.overrideredirect(True);self.window.transient(self.root)
        self.key='#140b23';self.window.configure(background=self.key)
        self.window.attributes('-transparentcolor',self.key)
        self.window.attributes('-disabled',True)
        self.canvas=tk.Canvas(self.window,background=self.key,borderwidth=0,highlightthickness=0,takefocus=False)
        self.canvas._om_bar=self.canvas._om_effect_layer=True
        self.canvas.pack(fill='both',expand=True);self.window.deiconify()
        # An upright hook, with individually striped segments at the icon's scale.
        self.path=[(0,.46),(0,.12),(0,-.17)]
        self.path +=[(.22+.22*math.cos(a),-.17+.22*math.sin(a)) for a in [math.pi+i*math.pi/9 for i in range(10)]]
        self.photo_sets=[self.make_photos(variant) for variant in range(3 if kind=='treat' else 1)]
        self.launch()
        self.frame()

    def make_photos(self,variant=0):
        # Pre-render small rotations once so 500 canes need only 500 canvas items.
        side=max(12,math.ceil(self.size*1.5));factor=4
        source=Image.new('RGBA',(side*factor,side*factor))
        draw=ImageDraw.Draw(source)
        if self.kind=='treat':
            mid=side*factor/2;span=self.size*factor
            orange,purple,green='#f18325','#bd69de','#8dc348'
            colour=(orange,purple,green)[variant]
            if variant==2:
                points=[(mid,mid-span*.45),(mid-span*.32,mid+span*.35),(mid+span*.32,mid+span*.35)]
                draw.polygon(points,fill=orange,outline='#492339',width=max(1,factor))
                draw.polygon([(mid,mid-span*.45),(mid-span*.1,mid-span*.2),(mid+span*.1,mid-span*.2)],fill='#fff2d5')
                draw.polygon([(mid-span*.1,mid-span*.2),(mid+span*.1,mid-span*.2),(mid+span*.23,mid+span*.12),(mid-span*.23,mid+span*.12)],fill='#f7cf49')
            else:
                for sign in (-1,1):
                    draw.polygon([(mid+sign*span*.22,mid),(mid+sign*span*.47,mid-span*.23),(mid+sign*span*.47,mid+span*.23)],fill=colour,outline='#492339',width=factor)
                draw.rounded_rectangle((mid-span*.28,mid-span*.24,mid+span*.28,mid+span*.24),radius=span*.1,fill=colour,outline='#492339',width=factor)
                draw.line((mid-span*.13,mid-span*.14,mid+span*.05,mid-span*.14),fill='#fff2d5',width=factor)
        else:
            points=[((side/2+x*self.size)*factor,(side/2+y*self.size)*factor) for x,y in self.path]
            draw.line(points,fill='#722526',width=max(2,round(self.size*.22*factor)),joint='curve')
            draw.line(points,fill='#fff0d5',width=max(1,round(self.size*.15*factor)),joint='curve')
            for n in (0,2,4,7,10):draw.line(points[n:n+2],fill='#dd2537',width=max(1,round(self.size*.16*factor)))
        source=source.resize((side,side),Image.Resampling.LANCZOS)
        photos=[]
        for fade in range(7):
            tinted=Image.blend(source,Image.new('RGBA',source.size,self.key),fade/7)
            tinted.putalpha(source.getchannel('A'))
            photos.append([ImageTk.PhotoImage(tinted.rotate(n*15,resample=Image.Resampling.NEAREST),master=self.root) for n in range(24)])
        return photos

    def launch(self):
        if self.closed:return 0
        count=min(30,self.LIMIT-len(self.candies))
        icon=self.source
        x=icon.winfo_rootx()-self.root.winfo_rootx()+icon.winfo_width()/2
        y=icon.winfo_rooty()-self.root.winfo_rooty()+icon.winfo_height()/2
        now=time.monotonic()
        for n in range(count):
            self.candies.append(dict(x=x,y=y,vx=self.rng.uniform(-410,100)*self.scale,
                vy=self.rng.uniform(-290,40)*self.scale,angle=self.rng.uniform(0,math.tau),
                spin=self.rng.uniform(-8,8),hit=set(),born=now+n*.012,resting=False,
                landed=None,item=None,photo=None,variant=self.rng.randrange(len(self.photo_sets))))
        return count

    def frame(self):
        self.job=None
        if self.closed:return
        now=time.monotonic();dt=min(.05,now-self.last);self.last=now
        if not self.candies or self.owner.theme!=self.theme or self.root.state() not in ('normal','zoomed'):
            self.close();return
        w,h=self.root.winfo_width(),self.root.winfo_height()
        bounds=(w,h,self.root.winfo_rootx(),self.root.winfo_rooty())
        if bounds!=self.bounds:
            self.window.lift(self.root);self.window.geometry(f'{w}x{h}+{bounds[2]}+{bounds[3]}');self.bounds=bounds
            self.rects=collect_obstacles(self.root)
        elif self.window.tk.getboolean(self.window.tk.call('wm','stackorder',str(self.window),'isbelow',str(self.root))):self.window.lift(self.root)
        steps=max(1,math.ceil(dt*120))
        for candy in self.candies[:]:
            if now<candy['born']:continue
            if candy['landed'] is not None:
                age=now-candy['landed']
                if age>self.REST_SECONDS+self.FADE_SECONDS:
                    if candy['item'] is not None:self.canvas.delete(candy['item'])
                    self.candies.remove(candy);continue
            for _ in range(steps):advance(candy,dt/steps,self.rects,w,h,self.scale)
            if candy['resting'] and candy['landed'] is None:candy['landed']=now
            fade=0 if candy['landed'] is None else max(0,min(6,int((now-candy['landed']-self.REST_SECONDS)/self.FADE_SECONDS*7)))
            frame=round(math.degrees(candy['angle'])/15)%24
            photo=(fade,frame)
            if candy['item'] is None:
                candy['item']=self.canvas.create_image(candy['x'],candy['y'],image=self.photo_sets[candy['variant']][fade][frame])
                candy['photo']=photo
            else:
                if candy['photo']!=photo:
                    self.canvas.itemconfigure(candy['item'],image=self.photo_sets[candy['variant']][fade][frame]);candy['photo']=photo
                if not candy['resting'] or candy['landed']==now:self.canvas.coords(candy['item'],candy['x'],candy['y'])
        self.job=self.root.after(16,self.frame)

    def close(self):
        if self.closed:return
        self.closed=True
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        if self.window.winfo_exists():self.window.destroy()
