"""A small pixel skeleton rises to shake the selected task or offer a hand."""
import math
import time
import tkinter as tk
from tkinter import font as tkfont

from PIL import Image,ImageTk

import ui


def smooth(value):
    value=max(0,min(1,value))
    return value*value*(3-2*value)


def pose(elapsed,selected):
    rise=smooth(elapsed/.85)
    reach=smooth((elapsed-.85)/.85)
    retreat=smooth((elapsed-4.8)/.75)
    sink=smooth((elapsed-5.55)/.85)
    shake=math.sin((elapsed-1.7)*25)*ui.px(7) if selected and 1.7<elapsed<4.8 else 0
    return rise,reach*(1-retreat),sink,shake


class SkeletonHand:
    DURATION=6.4

    def __init__(self,owner):
        self.owner,self.root=owner,owner.root
        self.target=owner.todo.d_title
        self.task_ref=(owner.todo.cur or {}).get('ref')
        self.selected=bool(self.task_ref and self.target.winfo_ismapped())
        self.started=time.monotonic();self.job=None;self.closed=False;self.bounds=None
        self.unit=max(1,round(ui.scale()*1.5))
        with Image.open(owner.asset_path('skeleton_pixel')) as source:
            sprite=source.convert('RGBA')
            box=sprite.getchannel('A').point(lambda alpha:255 if alpha>80 else 0).getbbox()
            sprite=sprite.crop(box or sprite.getbbox());sprite.thumbnail((48,72),Image.Resampling.NEAREST)
            sprite=sprite.resize((sprite.width*self.unit,sprite.height*self.unit),Image.Resampling.NEAREST)
            self.photo=ImageTk.PhotoImage(sprite,master=self.root)
        self.window=tk.Toplevel(self.root);self.window.withdraw()
        self.window._om_nonmodal=self.window._om_bar=self.window._om_effect_layer=True
        self.window.overrideredirect(True);self.window.transient(self.root)
        self.key='#102633';self.window.configure(background=self.key)
        self.window.attributes('-transparentcolor',self.key);self.window.attributes('-disabled',True)
        self.canvas=tk.Canvas(self.window,background=self.key,borderwidth=0,highlightthickness=0,takefocus=False)
        self.canvas._om_bar=self.canvas._om_effect_layer=True;self.canvas.pack(fill='both',expand=True)
        self.frame()

    def bone(self,a,b):
        c=self.canvas;p=self.unit
        c.create_line(*a,*b,fill='#2c1727',width=5*p,capstyle='butt')
        c.create_line(*a,*b,fill='#d6c7ab',width=3*p,capstyle='butt')
        c.create_line(a[0]-p,a[1],b[0]-p,b[1],fill='#fff0d1',width=p)
        for x,y in (a,b):c.create_rectangle(x-2*p,y-2*p,x+2*p,y+2*p,fill='#e7d7b7',outline='#2c1727',width=p)

    def arm(self,shoulder,hand,side,grip):
        p=self.unit;c=self.canvas
        elbow=((shoulder[0]+hand[0])/2+side*ui.px(16),(shoulder[1]+hand[1])/2+ui.px(18))
        self.bone(shoulder,elbow);self.bone(elbow,hand)
        x,y=hand
        c.create_rectangle(x-3*p,y-3*p,x+3*p,y+3*p,fill='#e7d7b7',outline='#2c1727',width=p)
        for finger in range(4):
            fx=x+(finger-1.5)*2*p
            fy=y-((4 if grip else 6)+(finger%2))*p
            c.create_line(fx,y-p,fx,fy,fx+side*p,fy-p,fill='#2c1727',width=2*p)
            c.create_line(fx,y-p,fx,fy,fx+side*p,fy-p,fill='#fff0d1',width=p)
        self.bone((x+side*2*p,y+p),(x+side*5*p,y-2*p))

    def title_geometry(self,width):
        target=self.target
        font=tkfont.Font(root=self.root,font=target.cget('font'))
        text=target.cget('text')
        max_width=max(ui.px(60),min(target.winfo_width(),width-ui.px(40)))
        while len(text)>3 and font.measure(text)+ui.px(20)>max_width:text=text[:-4]+'…'
        tw=min(max_width,font.measure(text)+ui.px(20))
        x=max(ui.px(8),min(width-tw-ui.px(8),target.winfo_rootx()-self.root.winfo_rootx()))
        y=target.winfo_rooty()-self.root.winfo_rooty()
        return x,y,tw,max(ui.px(28),target.winfo_height()),text

    def frame(self):
        self.job=None
        if self.closed:return
        now=time.monotonic();elapsed=now-self.started
        if (elapsed>=self.DURATION or self.owner.theme!='Halloween' or self.root.state() not in ('normal','zoomed')
                or (self.owner.todo.cur or {}).get('ref')!=self.task_ref
                or (self.selected and not self.target.winfo_ismapped())):
            self.close();return
        w,h=self.root.winfo_width(),self.root.winfo_height()
        bounds=(w,h,self.root.winfo_rootx(),self.root.winfo_rooty())
        if bounds!=self.bounds:
            self.window.lift(self.root);self.window.geometry(f'{w}x{h}+{bounds[2]}+{bounds[3]}')
            self.canvas.configure(width=w,height=h);self.bounds=bounds
        elif self.window.tk.getboolean(self.window.tk.call('wm','stackorder',str(self.window),'isbelow',str(self.root))):self.window.lift(self.root)
        if not self.window.winfo_ismapped():self.window.deiconify()
        c=self.canvas;c.delete('all')
        rise,reach,sink,shake=pose(elapsed,self.selected)
        bw,bh=self.photo.width(),self.photo.height()
        if self.selected:
            tx,ty,tw,th,title=self.title_geometry(w)
            body_x=max(bw/2+ui.px(12),min(w-bw/2-ui.px(12),tx+tw/2))
            floor=min(h-ui.px(8),ty+th+bh+ui.px(30))
        else:
            body_x=max(bw,min(w-bw,w*.73));floor=h-ui.px(16)
        bottom=floor+(1-rise+sink)*bh
        top=bottom-bh
        shoulders=[(body_x+side*bw*.39,top+bh*.55) for side in (-1,1)]
        hands=[]
        for side,shoulder in zip((-1,1),shoulders):
            rest=(shoulder[0]+side*ui.px(12),shoulder[1]+ui.px(34))
            if self.selected:
                grip=(tx+(0 if side==-1 else tw)+shake,ty+th*.65+math.sin(elapsed*21)*abs(shake)*.25)
                hand=(rest[0]+(grip[0]-rest[0])*reach,rest[1]+(grip[1]-rest[1])*reach)
            elif side==1:
                hand=(rest[0]+reach*ui.px(28+math.sin(elapsed*11)*12),rest[1]-reach*ui.px(74))
            else:hand=rest
            hands.append(hand)
            self.arm(shoulder,hand,side,self.selected and reach>.95)
        c.create_image(round(body_x),round(bottom),image=self.photo,anchor='s')
        if self.selected and reach>.95:
            # Cover only the original title; the real widget and task data stay intact.
            c.create_rectangle(tx,ty,tx+tw,ty+th,fill=self.target.cget('background'),outline='')
            x,y=tx+shake,ty+math.sin(elapsed*21)*abs(shake)*.25
            c.create_rectangle(x,y,x+tw,y+th,fill=ui.P['surface'],outline=ui.P['copper'],width=max(1,ui.px(2)),tags='held_task')
            c.create_text(x+ui.px(10),y+th/2,text=title,anchor='w',font=self.target.cget('font'),fill=self.target.cget('foreground'),tags='held_task')
            for side,hand in zip((-1,1),hands):self.arm(shoulders[0 if side==-1 else 1],hand,side,True)
        elif not self.selected and reach>.5 and sink<.2:
            bubble_w,bubble_h=ui.px(150),ui.px(36)
            bx=max(ui.px(8),min(w-bubble_w-ui.px(8),body_x-bubble_w/2))
            by=max(ui.px(8),top-bubble_h-ui.px(22))
            c.create_polygon(bx,by,bx+bubble_w,by,bx+bubble_w,by+bubble_h,bx+bubble_w*.6,by+bubble_h,
                body_x,by+bubble_h+ui.px(10),bx+bubble_w*.43,by+bubble_h,bx,by+bubble_h,
                fill='#fff0d1',outline='#412038',width=max(1,ui.px(2)),tags='speech')
            c.create_text(bx+bubble_w/2,by+bubble_h/2,text='Need a Hand?',font='om_bold',fill='#412038',tags='speech')
        self.job=self.root.after(max(12,33-round((time.monotonic()-now)*1000)),self.frame)

    def close(self):
        if self.closed:return
        self.closed=True
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        if self.window.winfo_exists():self.window.destroy()
        self.owner.audio.stop('skeleton_jingle')
