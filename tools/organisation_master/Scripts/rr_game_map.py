"""Zoomable viewport for the RR Games map; click and drag are distinct actions."""
import math
import tkinter as tk

import numpy as np
from PIL import Image,ImageTk

import ui


class GameMap(tk.Canvas):
    def __init__(self,parent,select):
        super().__init__(parent,height=260,width=1,highlightthickness=1,cursor='crosshair')
        self.select=select;self.geo=None;self.base=None;self.zoom=1.;self.scale=1.;self.offset=(0.,0.)
        self.press=None;self.moved=False;self.enabled=True;self.results=[];self.selected=None;self.flash=True
        self.bind('<Configure>',self.resized)
        self.bind('<MouseWheel>',self.wheel)
        self.bind('<ButtonPress-1>',self.down);self.bind('<B1-Motion>',self.drag);self.bind('<ButtonRelease-1>',self.up)

    def set_world(self,geo,level,owner=None):
        self.geo=geo;self.results=[];self.selected=None;self.flash=True
        self.level=level;self.owner=owner
        self.base=(geo.plain if level=='hard' else geo.political).copy()
        if owner and level=='easy':
            ids=[sid for sid,tag in geo.data.state_owner.items() if tag==owner]
            mask=np.isin(geo.small,ids);rgb=np.asarray(self.base).copy()
            rgb[mask]=(rgb[mask].astype(float)*.72+np.array([255,235,135])*.28).astype('uint8')
            self.base=Image.fromarray(rgb)
        self.reset()

    def reset(self):
        if not self.geo:return
        w=max(1,self.winfo_width());h=max(1,self.winfo_height())
        self.zoom=1.;self.scale=min(w/self.geo.width,h/self.geo.height)
        self.offset=((w-self.geo.width*self.scale)/2,(h-self.geo.height*self.scale)/2);self.render()

    def resized(self,event):
        if not self.geo:return
        if self.zoom==1:self.reset()
        else:self.render()

    def world(self,x,y):
        return ((x-self.offset[0])/self.scale,(y-self.offset[1])/self.scale)

    def screen(self,point):return (self.offset[0]+point[0]*self.scale,self.offset[1]+point[1]*self.scale)

    def wheel(self,event):
        if not self.geo:return 'break'
        anchor=self.world(event.x,event.y);factor=1.25 if event.delta>0 else .8
        fit=min(max(1,self.winfo_width())/self.geo.width,max(1,self.winfo_height())/self.geo.height)
        new=max(1.,min(24.,self.zoom*factor));self.zoom=new;self.scale=fit*new
        self.offset=(event.x-anchor[0]*self.scale,event.y-anchor[1]*self.scale)
        self.clamp();self.render();return 'break'

    def clamp(self):
        if not self.geo:return
        coords=[]
        for offset,length,view in zip(self.offset,(self.geo.width,self.geo.height),(self.winfo_width(),self.winfo_height())):
            extent=length*self.scale
            coords.append((view-extent)/2 if extent<=view else min(0,max(view-extent,offset)))
        self.offset=tuple(coords)

    def down(self,event):self.press=(event.x,event.y,self.offset);self.moved=False

    def drag(self,event):
        if self.press is None or self.geo is None:return
        x,y,offset=self.press
        if math.hypot(event.x-x,event.y-y)>5:self.moved=True
        if self.moved:
            self.offset=(offset[0]+event.x-x,offset[1]+event.y-y);self.clamp();self.render()

    def up(self,event):
        press,self.press=self.press,None
        if press is None or self.moved or not self.enabled or self.geo is None:return
        point=self.world(event.x,event.y)
        if 0<=point[0]<self.geo.width and 0<=point[1]<self.geo.height:self.select(point)

    def render(self):
        self.configure(background=ui.P['input_background'],highlightbackground=ui.P['border']);self.delete('all')
        if self.base is None or self.geo is None:return
        w=max(1,self.winfo_width());h=max(1,self.winfo_height());geo=self.geo
        base=self.base
        if self.selected is not None and self.flash:
            rgb=np.asarray(base).copy();mask=geo.small==self.selected;rgb[mask]=(255,220,75);base=Image.fromarray(rgb)
        x0,y0=self.world(0,0);x1,y1=self.world(w,h)
        ratio=base.width/geo.width;ry=base.height/geo.height
        detailed=self.scale>ratio
        if detailed:ratio=ry=1.
        left=max(0,math.floor(x0*ratio));top=max(0,math.floor(y0*ry))
        right=min(geo.width if detailed else base.width,math.ceil(x1*ratio));bottom=min(geo.height if detailed else base.height,math.ceil(y1*ry))
        if right>left and bottom>top:
            image=geo.region((left,top,right,bottom),self.level,self.owner,self.selected if self.flash else None) if detailed else base.crop((left,top,right,bottom))
            image=image.resize((max(1,round((right-left)/ratio*self.scale)),max(1,round((bottom-top)/ry*self.scale))),Image.Resampling.NEAREST)
            self.photo=ImageTk.PhotoImage(image,master=self)
            x,y=self.screen((left/ratio,top/ry));self.create_image(x,y,anchor='nw',image=self.photo)
        for index,result in enumerate(self.results,1):
            target=self.screen(result['target']);click=self.screen(result['click']) if result['click'] else None
            if click:
                # Draw the shortest line across a wrapped longitude seam.
                tx=target[0];dx=tx-click[0];period=geo.width*self.scale
                if abs(dx)>period/2:tx-=math.copysign(period,dx)
                for shift in (-period,0,period):
                    self.create_line(click[0]+shift,click[1],tx+shift,target[1],fill='#ffe39a',width=2)
                self.create_oval(click[0]-4,click[1]-4,click[0]+4,click[1]+4,fill='#ef6c63',outline='#ffffff')
            self.create_oval(target[0]-4,target[1]-4,target[0]+4,target[1]+4,fill='#f7d14d',outline='#ffffff')
            self.create_text(target[0]+8,target[1]-8,text=str(index),fill='#ffffff',font='om_small_bold',anchor='w')
        if self.selected is not None and self.flash and not np.any(geo.small==self.selected):
            x,y=self.screen(geo.positions[self.selected]);self.create_oval(x-5,y-5,x+5,y+5,outline='#ffe54d',width=3)
