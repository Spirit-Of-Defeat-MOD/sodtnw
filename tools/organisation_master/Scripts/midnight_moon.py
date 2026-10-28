"""A draggable moon descends into mountains, painting Midnight into dawn."""
import math
from functools import lru_cache
import tkinter as tk
from tkinter import ttk

import ui
from theme_secret_catalog import unlock


@lru_cache(maxsize=512)
def rgb(colour):
    if colour.startswith('#'):
        value=colour[1:]
        if len(value)==3:value=''.join(char*2 for char in value)
        return tuple(int(value[i:i+2],16) for i in (0,2,4))
    return ui._rgb(colour)


def mix(left,right,amount):
    a,b=rgb(left),rgb(right)
    return '#%02x%02x%02x' % tuple(max(0,min(255,round(x+(y-x)*amount))) for x,y in zip(a,b))


def sky_colour(position,amount):
    stops=((0,'#201a38'),(.58,'#563365'),(.85,'#76515f'),(1,'#92733d'))
    position=max(0,min(1,position))
    for (a,left),(b,right) in zip(stops,stops[1:]):
        if position<=b:
            dawn=mix(left,right,(position-a)/(b-a));break
    return mix('#141a24',dawn,amount)


def palette(base,amount):
    targets=dict(background='#392547',surface='#392a48',sidebar='#30233f',border='#725b83',
        header_background='#50365e',header_hover='#644471',stripe='#42304f',selection_background='#79516f',
        button_background='#513b60',button_active='#6a4a75',input_background='#231c31',
        copper='#e4bd71',button_pressed='#79516f',blocked_background='#563044')
    return {key:mix(value,targets[key],amount) if key in targets else value for key,value in base.items()}


def readable_ink(background):
    def luminance(colour):
        channels=[int(colour[i:i+2],16)/255 for i in (1,3,5)]
        channels=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(v*w for v,w in zip(channels,(.2126,.7152,.0722)))
    bg=luminance(background)
    def contrast(colour):
        fg=luminance(colour)
        return (max(bg,fg)+.05)/(min(bg,fg)+.05)
    ink=max(('#171322','#fff2db'),key=contrast)
    return ink if contrast(ink)>=4.5 else max(('#000000','#ffffff'),key=contrast)


class MidnightMoon:
    def __init__(self,owner):
        self.owner,self.root=owner,owner.root
        self.amount=max(0,min(1,float(owner.app.config.get('midnight_dawn',0))))
        self.display_amount=self.amount
        self.moon_x=max(0,min(1,float(owner.app.config.get('midnight_moon_x',.48))))
        self.records=[];self.layer_items={}
        self.visible=False;self.active=False;self.closed=False;self.dragging=False
        self.job=self.watch_job=None;self.layers={};self.original_styles={};self.base=None
        self.canvas=tk.Canvas(owner.app.nav,width=ui.px(210),height=ui.px(134),borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.canvas._om_bar=self.canvas._om_effect_layer=True
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Up>',lambda e:self.key(-.04))
        self.canvas.bind('<Down>',lambda e:self.key(.04))
        self.canvas.bind('<Left>',lambda e:self.key_x(-.04))
        self.canvas.bind('<Right>',lambda e:self.key_x(.04))
        self.canvas.bind('<Configure>',lambda e:self.draw())

    def toggle(self):
        if self.closed or self.owner.theme!='Midnight':return
        if self.visible:
            self.canvas.pack_forget();self.visible=False
        else:
            self.visible=True
            self.canvas.pack(side='bottom',after=self.owner.app.radio,fill='x',padx=8,pady=(2,6))
            self.draw()
            if not self.active:self.activate()
        self.owner.app.schedule_logo()

    def activate(self):
        self.active=True;self.base=dict(ui._themes['Midnight']['colors'])
        self.collect_layout();self.request()
        if self.watch_job is None:self.watch_job=self.root.after(900,self.watch)

    def moon_position(self):
        w=max(ui.px(80),self.canvas.winfo_width());r=ui.px(11)
        return (r+ui.px(6)+(w-2*r-ui.px(12))*self.moon_x,
                ui.px(21)+self.amount*ui.px(65),r)

    def press(self,event):
        x,y,r=self.moon_position()
        near=math.hypot(event.x-x,event.y-y)<=r+ui.px(9)
        self.dragging=True
        self.offset_x=event.x-x if near else 0
        self.offset=event.y-y if near else 0
        self.canvas.focus_set();self.drag(event)
        return 'break'

    def drag(self,event):
        if not self.dragging:return 'break'
        w=max(ui.px(80),self.canvas.winfo_width());r=ui.px(11)
        grid=max(1,ui.px(4));left=r+ui.px(6);span=max(1,w-2*left)
        x=max(0,min(span,round((event.x-self.offset_x-left)/grid)*grid))
        self.moon_x=x/span
        distance=event.y-self.offset-ui.px(21);travel=ui.px(65)
        y=max(0,min(travel,round(distance/grid)*grid))
        if distance>=travel-grid/2:y=travel
        self.amount=y/travel
        self.draw();self.request()
        return 'break'

    def release(self,event=None):
        if self.dragging:
            self.dragging=False;self.request();self.save();unlock(self.owner.app,'egg_midnight')
        return 'break'

    def key(self,delta):
        self.amount=max(0,min(1,self.amount+delta));self.draw();self.request();self.save();unlock(self.owner.app,'egg_midnight')
        return 'break'

    def key_x(self,delta):
        self.moon_x=max(0,min(1,self.moon_x+delta));self.draw();self.save()
        return 'break'

    def save(self):
        self.owner.app.config['midnight_dawn']=round(self.amount,4)
        self.owner.app.config['midnight_moon_x']=round(self.moon_x,4);self.owner.app.save_config()

    def request(self):
        if self.active and self.job is None:self.job=self.root.after(16,self.apply)

    def draw(self):
        if self.closed:return
        c=self.canvas;w=max(ui.px(80),c.winfo_width());h=ui.px(134)
        c.configure(height=h,background=sky_colour(0,self.display_amount));c.delete('all')
        for y in range(0,h,3):c.create_rectangle(0,y,w,y+3,fill=sky_colour(y/h,self.display_amount),outline='')
        for n in range(16):
            x=(17+n*41)%w;y=ui.px(8+(n*19)%65)
            c.create_rectangle(x,y,x+ui.px(1),y+ui.px(1),fill=mix('#dde5f2',sky_colour(y/h,self.display_amount),self.display_amount*.88),outline='')
        mx,my,r=self.moon_position()
        for extra,fade in ((ui.px(6),.87),(ui.px(3),.7)):
            c.create_oval(mx-r-extra,my-r-extra,mx+r+extra,my+r+extra,fill=mix('#d8dbed',sky_colour(my/h,self.display_amount),fade),outline='')
        c.create_oval(mx-r,my-r,mx+r,my+r,fill='#e9e4d2',outline='#c7c9d3',width=max(1,ui.px(1)),tags='moon')
        c.create_oval(mx-r*.5,my-r*.5,mx-r*.1,my-r*.1,fill='#c9c6c4',outline='',tags='moon')
        c.create_oval(mx+r*.1,my+r*.15,mx+r*.5,my+r*.45,fill='#d2cfcb',outline='',tags='moon')
        # Mountain ridges cover the moon as it sinks, rather than letting it float over them.
        far=mix('#242c40','#563d61',self.display_amount)
        near=mix('#111827','#2c2540',self.display_amount)
        c.create_polygon(0,h*.8,w*.18,h*.43,w*.37,h*.76,w*.56,h*.57,w*.76,h*.82,w,h*.5,w,h,0,h,fill=far,outline='')
        c.create_polygon(0,h*.94,w*.16,h*.73,w*.32,h*.9,w*.47,h*.78,w*.64,h*.94,w*.82,h*.72,w,h*.9,w,h,0,h,fill=near,outline='')
        c.create_line(0,h-1,w,h-1,fill=ui.P['border'])

    def apply(self):
        self.job=None
        if not self.active or self.closed or self.owner.theme!='Midnight':return
        delta=self.amount-self.display_amount
        self.display_amount=self.amount if abs(delta)<.003 else self.display_amount+delta*.48
        self.colours_only(palette(self.base,self.display_amount))
        self.spatial()
        self.owner.app.menubar.recolour()
        for widget in self.owner.hiding.values():
            if widget.winfo_ismapped():self.owner.paint(widget)
        self.draw()
        if self.display_amount!=self.amount:self.request()

    def colours_only(self,colours):
        # Keep layouts, fonts, sorting, window geometry and task widgets untouched.
        ui.P.clear();ui.P.update(colours)
        ui.THEME['t']=dict(ui._themes['Midnight'],colors=dict(colours))
        c=colours;st=ttk.Style(self.root)
        st.configure('.',background=c['background'],foreground=c['foreground'],fieldbackground=c['input_background'],
            bordercolor=c['border'],lightcolor=c['surface'],darkcolor=c['background'],troughcolor=c['surface'])
        for name in ('TFrame','TLabel','TNotebook'):st.configure(name,background=c['background'])
        st.configure('TButton',background=c['button_background'],bordercolor=c['border'],focuscolor=c['copper'])
        st.map('TButton',background=[('pressed',c['button_pressed']),('active',c['button_active'])])
        st.configure('TMenubutton',background=c['button_background']);st.map('TMenubutton',background=[('active',c['button_active'])])
        for name in ('TEntry','TCombobox','TSpinbox'):
            st.configure(name,fieldbackground=c['input_background'],background=c['button_background'])
            st.map(name,fieldbackground=[('readonly',c['input_background']),('disabled',c['background'])],
                selectbackground=[('readonly',c['input_background'])])
        st.configure('Treeview',background=c['surface'],fieldbackground=c['surface'],bordercolor=c['border'])
        st.map('Treeview',background=[('selected',c['selection_background'])])
        st.configure('Treeview.Heading',background=c['header_background'],bordercolor=c['border'])
        st.map('Treeview.Heading',background=[('active',c['header_hover'])])
        st.configure('TSeparator',background=c['border'])
        for pattern,key in (('*Background','background'),('*Text.background','input_background'),('*Listbox.background','input_background'),('*TCombobox*Listbox.background','input_background')):
            self.root.option_add(pattern,c[key])

    def collect_layout(self):
        self.records=[];pending=[(self.root,False)]
        height=max(1,self.root.winfo_height());ry=self.root.winfo_rooty()
        while pending:
            widget,head=pending.pop()
            if (getattr(widget,'_om_bar',False) or getattr(widget,'_om_effect_layer',False)
                    or widget.winfo_toplevel() is not self.root):continue
            head=head or getattr(widget,'_om_head',False)
            pending.extend((child,head) for child in widget.winfo_children())
            if not widget.winfo_ismapped():continue
            cls=widget.winfo_class()
            pos=max(0,min(1,(widget.winfo_rooty()-ry+widget.winfo_height()/2)/height))
            original=None
            if cls in ('TFrame','TLabel','TLabelframe','Treeview'):
                original=self.original_styles.setdefault(widget,widget.cget('style') or cls)
            self.records.append((widget,cls,pos,head,original))
            if cls in ('Frame','TFrame') and not head and widget.winfo_width()>=ui.px(120) and widget.winfo_height()>=ui.px(95):
                if widget not in self.layers:
                    layer=tk.Canvas(widget,highlightthickness=0,borderwidth=0,takefocus=False)
                    layer._om_bar=layer._om_effect_layer=True
                    layer.place(x=0,y=0,relwidth=1,relheight=1)
                    layer.tk.call('lower',str(layer));self.layers[widget]=layer
                layer=self.layers[widget]
                w,h=widget.winfo_width(),widget.winfo_height();top=widget.winfo_rooty()-ry
                dimensions=(w,h,top,height)
                old=self.layer_items.get(widget)
                if old is None or old[0]!=dimensions:
                    layer.delete('all')
                    items=[(layer.create_rectangle(0,y,w,y+6,outline=''),(top+y)/height) for y in range(0,h,6)]
                    self.layer_items[widget]=(dimensions,items)

    def spatial(self):
        if not self.active:return
        st=ttk.Style(self.root);configured=set();amount=self.display_amount
        for widget,cls,pos,head,original in self.records:
            if not widget.winfo_exists():continue
            bg=ui.P['header_background'] if head else sky_colour(pos,amount)
            if original:
                bucket=round(pos*40);name=f'MidnightDawn{bucket}.{original}'
                if name not in configured:
                    role='surface' if cls=='Treeview' else 'background'
                    colour=mix(ui.P[role],sky_colour(bucket/40,amount),amount*.7)
                    st.configure(name,background=colour,fieldbackground=colour);configured.add(name)
                if widget.cget('style')!=name:widget.configure(style=name)
                if cls=='Treeview':widget.tag_configure('odd',background=ui.P['stripe'])
            elif cls in ('Frame','Label','Canvas'):
                if widget.cget('background')!=bg:widget.configure(background=bg)
            elif cls in ('Text','Entry','Listbox','Button','Checkbutton','Radiobutton','Menu'):
                ui.theme_widget(widget)
        for widget,(_,items) in self.layer_items.items():
            layer=self.layers[widget]
            if layer.winfo_exists():
                for item,pos in items:
                    colour=sky_colour(pos,amount)
                    if layer.itemcget(item,'fill')!=colour:layer.itemconfigure(item,fill=colour)

    def watch(self):
        self.watch_job=None
        if not self.active or self.closed:return
        if self.owner.theme!='Midnight':self.deactivate();return
        self.collect_layout();self.spatial()
        self.watch_job=self.root.after(900,self.watch)

    def deactivate(self):
        self.active=False;self.visible=False;self.dragging=False;self.canvas.pack_forget()
        for job in (self.job,self.watch_job):
            if job is not None:self.root.after_cancel(job)
        self.job=self.watch_job=None
        for layer in self.layers.values():
            if layer.winfo_exists():layer.destroy()
        self.layers.clear();self.layer_items.clear();self.records.clear()
        for widget,style in self.original_styles.items():
            if widget.winfo_exists():widget.configure(style=style)
        self.original_styles.clear()
        ui.theme_all(self.root)

    def close(self):
        if self.closed:return
        self.deactivate();self.closed=True
