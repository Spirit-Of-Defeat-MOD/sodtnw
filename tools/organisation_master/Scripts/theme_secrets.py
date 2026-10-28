"""Hidden theme controls, short nonmodal animations and a terminal minigame."""
import collections
import copy
import datetime
import math
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk, ImageOps

import secret_art
import terminal_ai
from secret_audio import SecretAudio
from sorel_burn import SorelBurn
from rising_cat import CatScratch
from imperial_eagle import ImperialEagle
from penguin_slide import PenguinParade
from burg_ritual import BurgRitual
from santa_game import SantaGame
from candy_burst import CandyBurst
from marching_band import MarchingBand
from skeleton_hand import SkeletonHand
from midnight_moon import MidnightMoon
from idea_sandwich import IdeaSandwich
from theme_secret_catalog import unlock
import ui
import paths  # (Scripts/paths.py: where the tool's files are)


class Scene:
    def __init__(self, owner, kind, duration=7, travel=False):
        self.owner, self.kind, self.duration, self.travel = owner, kind, duration, travel
        self.root = owner.root
        # An embedded layer survives borderless/fullscreen mode and Windows compositing.
        logical_height=270 if kind=='vapor' else 220
        self.scale = min(ui.scale(), max(.3, (self.root.winfo_width()-24)/360),
                         max(.3, (self.root.winfo_height()-70)/logical_height))
        if kind not in ('sunset','vapor'):self.scale *= .82
        if travel:self.scale *= .72
        self.width, self.height = round(360*self.scale), round(logical_height*self.scale)
        parent = self.root
        if kind == 'logo':
            parent = tk.Toplevel(self.root)
            parent.withdraw()
            parent._om_nonmodal = parent._om_bar = parent._om_effect_layer = True
            parent.overrideredirect(True)
            parent.transient(self.root)
            parent.configure(background='#ed7b25')
            parent.attributes('-transparentcolor', '#ed7b25')
            parent.attributes('-disabled',True)
        self.canvas = tk.Canvas(parent, width=self.width, height=self.height,
            borderwidth=0, highlightthickness=1, highlightbackground=ui.P['copper'],
            background=ui.P['surface'], cursor='hand2', takefocus=False)
        self.canvas._om_bar = True  # The animation paints its own colours.
        if kind=='logo':self.canvas._om_effect_layer=True
        self.window = self.canvas
        if kind == 'logo':
            self.window = parent
            self.canvas.configure(background='#ed7b25', highlightthickness=0)
            self.canvas.pack()
        self.canvas.bind('<Button-1>', lambda e: self.close())
        self.started = time.monotonic()
        self.job = None
        self.logo_bounds=self.logo_item=None
        self.photo = owner.image(kind, self.scale)
        if kind=='logo' and self.photo:
            self.width,self.height=self.photo.width(),self.photo.height()
            self.canvas.configure(width=self.width,height=self.height)
        self.frames = owner.frames(kind, self.scale)
        if self.frames:
            self.width=max(frame.width() for frame in self.frames)+ui.px(12)
            self.height=max(frame.height() for frame in self.frames)+ui.px(12)
            self.canvas.configure(width=self.width,height=self.height,highlightthickness=0)
        self.frame()

    def frame(self):
        self.job = None
        if not self.window.winfo_exists():return
        start = time.monotonic()
        elapsed = start-self.started
        if (self.duration is not None and elapsed >= self.duration) or self.root.state() not in ('normal','zoomed'):
            self.close()
            return
        if self.kind == 'logo':
            hotspot = self.owner.square
            px, py = self.root.winfo_pointerxy()
            if not (hotspot.winfo_ismapped() and
                    hotspot.winfo_rootx() <= px < hotspot.winfo_rootx()+hotspot.winfo_width() and
                    hotspot.winfo_rooty() <= py < hotspot.winfo_rooty()+hotspot.winfo_height()):
                self.close()
                return
        width,height = self.root.winfo_width(),self.root.winfo_height()
        if width<self.width+8 or height<self.height+25:
            self.close();return
        if self.kind == 'logo':
            def bounce(value, span):
                span=max(1,span)
                return span-abs(value%(2*span)-span)
            x=bounce(elapsed*110,width-self.width)
            y=bounce(elapsed*77,height-self.height-30)+25
        elif self.kind=='duck':
            x=(width-self.width)/2+math.sin(elapsed*.8)*min(100,(width-self.width)*.15)
            y=(height-self.height)*.55
        elif self.travel:
            x=(width-self.width)*elapsed/self.duration
            y=(height-self.height)*.65+math.sin(elapsed*3)*6
        else:
            x=(width-self.width)/2
            y=(height-self.height)/2
        x=max(0,min(width-self.width,x));y=max(0,min(height-self.height,y))
        if self.kind == 'logo':
            # Keep the transparent native window stationary. Moving/re-raising it
            # every frame makes Windows repeatedly repaint the colour-keyed logo.
            bounds=(width,height,self.root.winfo_rootx(),self.root.winfo_rooty())
            if bounds!=self.logo_bounds:
                self.window.lift(self.root)
                self.window.geometry(f'{width}x{height}+{bounds[2]}+{bounds[3]}')
                self.canvas.configure(width=width,height=height)
                self.logo_bounds=bounds
            elif self.window.tk.getboolean(self.window.tk.call('wm','stackorder',str(self.window),'isbelow',str(self.root))):
                self.window.lift(self.root)
            if self.logo_item is None:
                if self.photo:self.logo_item=self.canvas.create_image(round(x),round(y),image=self.photo,anchor='nw')
                else:self.logo_item=self.canvas.create_text(round(x),round(y),text='RR',anchor='nw',fill=ui.P['foreground'],font='om_title')
            else:self.canvas.coords(self.logo_item,round(x),round(y))
            if not self.window.winfo_ismapped():self.window.deiconify()
            self.job=self.root.after(max(1,16-round((time.monotonic()-start)*1000)),self.frame)
            return
        else:
            self.canvas.place(x=round(x),y=round(y),width=self.width,height=self.height)
            self.canvas.tk.call('raise',str(self.canvas))
        px,py=self.root.winfo_pointerxy()
        pointer=((px-(self.window.winfo_rootx()+self.width/2))/max(1,self.width),
                 (py-(self.window.winfo_rooty()+self.height/2))/max(1,self.height))
        if self.frames:
            self.canvas.delete('all')
            if self.kind=='duck':index=int(elapsed*8)%len(self.frames)
            else:index=round((math.sin(elapsed*(3.8 if self.kind=='skeleton' else 2))+1)*(len(self.frames)-1)/2)
            bob=math.sin(elapsed*4)*self.scale*(3 if self.kind=='duck' else 1.5)
            self.canvas.create_image(self.width/2,self.height/2+bob,image=self.frames[index])
            if self.kind=='eagle':
                for n in range(18):
                    x=(17+n*31)%self.width;y=(elapsed*32+n*23)%self.height
                    self.canvas.create_rectangle(x,y,x+3*self.scale,y+6*self.scale,
                        fill=('#e8bb53','#c67aa0','#81b8c5')[n%3],outline='')
        else:
            secret_art.draw(self.canvas,self.kind,elapsed,pointer,self.photo,self.scale)
        if self.kind=='logo' and self.photo:
            self.canvas.move('all',self.width/2-180*self.scale,self.height/2-110*self.scale)
        self.job=self.root.after(max(1,16-round((time.monotonic()-start)*1000)),self.frame)

    def close(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job=None
        if self.window.winfo_exists():self.window.destroy()
        if self.kind=='vapor':self.owner.audio.stop('zhgyv')


class DuckWalk:
    """A small colour-keyed sprite; no opaque panel or global topmost window."""
    def __init__(self,owner,duration=9):
        self.owner,self.root=owner,owner.root
        self.scale=ui.scale()*.38
        self.frames=owner.frames('duck',self.scale)
        self.wave_frames=owner.frames('duck_wave',self.scale)
        self.width=max(frame.width() for frame in self.frames)+4
        self.height=max(frame.height() for frame in self.frames)+4
        self.window=tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal=True;self.window._om_bar=True;self.window._om_effect_layer=True
        self.window.overrideredirect(True);self.window.transient(self.root)
        self.window.configure(background='#ed7b25')
        self.window.attributes('-transparentcolor','#ed7b25')
        self.canvas=tk.Canvas(self.window,width=self.width,height=self.height,highlightthickness=0,
                              borderwidth=0,background='#ed7b25',takefocus=False)
        self.canvas._om_bar=True;self.canvas._om_effect_layer=True
        self.canvas.pack()
        self.canvas.bind('<Button-1>',lambda e:self.close())
        self.duration=max(9,duration);self.started=time.monotonic();self.job=None
        anchor=owner.app.logo_label
        if not anchor.winfo_ismapped() or anchor.winfo_height()<30:anchor=owner.app.nav_title
        self.start_x=anchor.winfo_rootx()-self.root.winfo_rootx()+anchor.winfo_width()-8
        self.foot_y=anchor.winfo_rooty()-self.root.winfo_rooty()+anchor.winfo_height()+ui.px(30)
        self.distance=ui.px(260)
        self.window.deiconify();self.window.lift(self.root);self.frame()

    def frame(self):
        self.job=None
        if not self.window.winfo_exists():return
        elapsed=time.monotonic()-self.started
        if elapsed>self.duration or self.root.state() not in ('normal','zoomed'):
            self.close();return
        root_w,root_h=self.root.winfo_width(),self.root.winfo_height()
        begin=max(2,min(root_w-self.width-8,self.start_x))
        end=max(begin,min(root_w-self.width-8,begin+self.distance))
        travel=min(1,elapsed/4)
        # The reveal is clipped at the logo's edge before the complete sprite emerges.
        left=begin-self.width+travel*(end-begin+self.width)
        visible_left=max(begin,left)
        visible_width=max(1,min(self.width,round(left+self.width-visible_left)))
        top=max(3,min(root_h-self.height-8,self.foot_y-self.height))
        self.window.lift(self.root)  # Raise before moving: Tk otherwise restores the old position.
        self.window.geometry(f'{visible_width}x{self.height}+{self.root.winfo_rootx()+round(visible_left)}+{self.root.winfo_rooty()+round(top)}')
        self.canvas.configure(width=visible_width,height=self.height)
        self.canvas.delete('all')
        frames=self.frames if travel<1 else self.wave_frames
        index=int(elapsed*8)%len(frames)
        self.canvas.create_image(left-visible_left+self.width/2,self.height/2,image=frames[index])
        self.job=self.root.after(16,self.frame)

    def close(self):
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        if self.window.winfo_exists():self.window.destroy()


class TerminalGame(tk.Toplevel):
    LINES=terminal_ai.LINES
    def __init__(self, owner):
        super().__init__(owner.root)
        self.owner=owner
        self._om_nonmodal=True
        self.title('TERMINAL // SHALL WE PLAY A GAME?')
        self.transient(owner.root)
        self.resizable(False,False)
        self.jobs=set()
        body=ttk.Frame(self,padding=14);body.pack()
        ttk.Label(body,text='TIC-TAC-TOE',style='Title.TLabel').pack()
        self.status=ttk.Label(body,text='You are X. Your move.');self.status.pack(pady=(5,8))
        self.canvas=tk.Canvas(body,width=ui.px(270),height=ui.px(270),background='#030c06',highlightthickness=1,highlightbackground='#368555')
        self.canvas.pack()
        self.canvas.bind('<Button-1>',self.click)
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=(10,0))
        ttk.Button(buttons,text='New game',command=self.reset).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(buttons,text='Close',command=self.destroy).pack(side='left',fill='x',expand=True)
        self.bind('<Destroy>',self.destroyed,add='+')
        self.reset();ui.theme_all(self);ui.title_bar(self)
        self.update_idletasks()
        x=owner.root.winfo_rootx()+max(0,(owner.root.winfo_width()-self.winfo_reqwidth())//2)
        y=owner.root.winfo_rooty()+max(0,(owner.root.winfo_height()-self.winfo_reqheight())//2)
        self.geometry(f'+{x}+{y}')

    def later(self, delay, fn):
        token=None
        def run():
            self.jobs.discard(token)
            fn()
        token=self.after(delay,run);self.jobs.add(token)

    def reset(self):
        for job in self.jobs:self.after_cancel(job)
        self.jobs.clear()
        self.board=['']*9;self.busy=False;self.over=False
        self.canvas.delete('all')
        for p in (1,2):
            x=ui.px(90*p)
            self.canvas.create_line(x,8,x,ui.px(270)-8,fill='#36794b',width=2)
            self.canvas.create_line(8,x,ui.px(270)-8,x,fill='#36794b',width=2)
        self.status.configure(text='You are X. Your move.')

    @classmethod
    def result(cls, board):
        return terminal_ai.result(board)

    @classmethod
    def score(cls, board, turn):
        return terminal_ai.score(tuple(board),turn)

    def click(self,event):
        size=ui.px(90)
        col,row=int(event.x//size),int(event.y//size)
        if not 0<=col<3 or not 0<=row<3 or self.busy or self.over:return
        index=row*3+col
        if self.board[index]:return
        self.place_mark(index,'X')

    def place_mark(self,index,mark):
        self.board[index]=mark;self.busy=True
        begun=time.monotonic();unit=ui.px(90);x=index%3*unit+unit/2;y=index//3*unit+unit/2;r=unit*.29
        tag='mark'+str(index)
        def animate():
            progress=min(1,(time.monotonic()-begun)/.16)
            self.canvas.delete(tag)
            if mark=='X':
                for sign in (-1,1):
                    self.canvas.create_line(x-r,y-sign*r,x-r+2*r*progress,y-sign*r+2*sign*r*progress,fill='#a2f3ad',width=4,tags=tag)
            else:self.canvas.create_arc(x-r,y-r,x+r,y+r,start=90,extent=-max(.1,359.9*progress),style='arc',outline='#52bcd3',width=4,tags=tag)
            if progress<1:self.later(16,animate)
            else:self.finish_move(mark)
        animate()

    def finish_move(self,mark):
        result=self.result(self.board)
        if result:
            self.over=True;self.busy=False
            self.status.configure(text={'X':'HUMAN VICTORY. Unexpected.','O':'TERMINAL WINS. Try again.','draw':'A STRANGE GAME. A draw.'}[result])
            if result=='X':unlock(self.owner.app,'egg_terminal_win')
        elif mark=='X':
            self.status.configure(text='Terminal is thinking…')
            self.later(220,self.computer)
        else:
            self.busy=False;self.status.configure(text='Your move.')

    def computer(self):
        if self.over:return
        choice=terminal_ai.choose_move(self.board)
        if choice is not None:self.place_mark(choice,'O')

    def destroyed(self,event):
        if event.widget is self:
            for job in self.jobs:self.after_cancel(job)
            self.jobs.clear()


class ThemeSecrets:
    def __init__(self, app):
        self.app,self.root=app,app.root
        self.todo=app.todo_page()
        self.audio=SecretAudio(app)
        self.scene=self.game=None
        self.burned=False;self.sorel_original=None
        self.taps=0;self.beats=collections.deque();self.closed=False
        self.hover_job=self.clock_job=None
        self.hiding={}
        self.theme=''
        self.art_cache={}
        self.last_clock=datetime.datetime.now()
        self.clock_flash_until=0
        self.changes_panels=[]
        self.treats=None
        self.drum_var=tk.BooleanVar(value=bool(app.config.get('marching_band',app.config.get('secret_drum',False))))
        app.settings_menu.add_separator()
        app.settings_menu.add_checkbutton(label='Marching band',variable=self.drum_var,command=self.toggle_drum)
        self.drum_index=app.settings_menu.index('end')
        app.status.pack_configure(before=app.body)
        self.drum_strip=MarchingBand(self)
        self.drum=self.drum_strip.widgets['drum']
        self.clock=self.hotspot('clock',app.status,'◷',lambda:self.midnight.toggle(),width=32)
        self.clock.bind('<Leave>',self.cancel_hover,add='+')
        self.temperature=self.hotspot('temperature',app.nav,'−17°C',lambda:self.activate('egg_arctic','penguin',travel=True),width=100,height=40)
        self.temperature.secret_size=(200,58)
        self.temperature._om_bar=True
        self.temperature.configure(takefocus=True)
        self.temperature.bind('<Configure>',lambda e:self.paint(self.temperature))
        self.temperature.bind('<Return>',lambda e:self.temperature.secret_command())
        self.temperature.bind('<space>',lambda e:self.temperature.secret_command())
        self.gear=self.hotspot('sorel_eagle',self.todo.health_btn,'',None,width=22,height=19)
        self.gear.bind('<Double-Button-1>',lambda e:self.scorch())
        self.screw=self.hotspot('screw',app.menubar,'⊙',self.terminal,width=24)
        self.moustache=self.hotspot('moustache',self.todo.identity,'〰',lambda:self.activate('egg_stallonian','portrait',sound='stallonian_secret'),width=25)
        self.sandwich=self.hotspot('sandwich',self.todo.idea_pane.head_btn.master,'',self.snack,width=24,height=22)
        self.pumpkin=self.hotspot('trick_pumpkin',app.menubar,'🎃',self.trick_or_treat,width=28,height=22)
        self.scratch=self.hotspot('scratch',self.todo.views_row,'╱╱',lambda:self.activate('egg_halloween','skeleton',sound='skeleton_jingle'),width=22)
        self.bell=self.hotspot('bell',app.radio,'♧',lambda:self.activate('egg_sleigh','sleigh',sound='christmas_bell',travel=True),width=32,height=32)
        self.stocking=self.hotspot('stocking',self.todo.mode_buttons['vc'],'♧',lambda:self.activate('egg_stocking','stocking'),width=22,height=18)
        self.ink=self.hotspot('ink',self.todo.notes_frame,'⌁',None,width=28,height=15)
        self.ink.bind('<Enter>',lambda e:self.hover('egg_rising','cat'))
        self.ink.bind('<Leave>',self.cancel_hover,add='+')
        self.ornament=self.hotspot('ornament',self.todo.project_section.tools,'♛',lambda:self.activate('egg_andorran','eagle'),width=23)
        self.square=self.hotspot('square',app.status,'▪',None,width=18)
        self.square.bind('<Enter>',lambda e:self.hover('egg_classic','logo'),add='+')
        self.square.bind('<Leave>',self.leave_classic,add='+')
        for target in (app.logo_label,app.nav_title):target.bind('<Button-1>',self.duck_tap,add='+')
        self.root.bind('<Escape>',lambda e:None if isinstance(self.scene,BurgRitual) else self.dismiss(),add='+')
        self.midnight=MidnightMoon(self)
        ui.THEME_HOOKS.append(self.retheme)
        self.retheme();self.clock_tick()

    def hotspot(self,key,parent,glyph,command,width=24,height=22):
        c=tk.Canvas(parent,width=ui.px(width),height=ui.px(height),borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=False)
        c.secret_glyph=glyph;c.secret_size=(width,height);c.secret_command=command
        c.bind('<Button-1>',lambda e: (command() if command else None,'break')[1])
        c.bind('<Enter>',lambda e:self.paint(c,True))
        c.bind('<Leave>',lambda e:self.paint(c,False))
        self.hiding[key]=c
        return c

    def paint_weather(self,c,hover=False):
        w=max(ui.px(180),c.winfo_width())
        h=ui.px(58)
        c.configure(height=h,background=ui.P['background'])
        c.delete('all')
        c.create_rectangle(1,1,w-2,h-2,fill=ui.P['header_hover'] if hover else ui.P['surface'],
                           outline=ui.P['copper'] if hover else ui.P['border'])
        c.create_rectangle(2,2,ui.px(39),h-3,fill=ui.P['header_background'],outline='')
        photo=self.icon('temperature',ui.px(30),ui.px(43))
        if photo:
            c.secret_photo=photo
            c.create_image(ui.px(21),h/2,image=photo)
        c.create_text(ui.px(48),ui.px(15),text='ARCTIC STATION',anchor='w',fill=ui.P['muted'],font=('Segoe UI',ui.px(8),'bold'))
        c.create_text(ui.px(48),ui.px(36),text='−17°C',anchor='w',fill=ui.P['foreground'],font=('Segoe UI',ui.px(13),'bold'))
        c.create_text(w-ui.px(13),ui.px(36),text='›',fill=ui.P['copper'],font=('Segoe UI',ui.px(18),'bold'))

    def paint_clock(self,hover=False):
        c=self.clock;w,h=ui.px(48),ui.px(22)
        bg=ttk.Style(self.root).lookup('TLabel','background') or ui.P['background']
        if self.theme=='Midnight' and self.midnight.active:
            from midnight_moon import sky_colour
            position=(c.winfo_rooty()-self.root.winfo_rooty()+h/2)/max(1,self.root.winfo_height())
            bg=sky_colour(position,self.midnight.display_amount)
        if not (isinstance(bg,str) and len(bg)==7 and bg.startswith('#')):  # (a named colour - 'systemButtonFace' on a first start - as #rrggbb)
            try:r,g,b=self.root.winfo_rgb(bg);bg='#%02x%02x%02x'%(r>>8,g>>8,b>>8)
            except Exception:bg=ui.P.get('background','#ffffff')
        from midnight_moon import readable_ink
        foreground=readable_ink(bg)
        c.configure(width=w,height=h,background=bg)
        c.secret_size=(48,22)
        item=getattr(c,'clock_item',None)
        if item is None or not c.type(item):
            c.clock_item=c.create_text(w/2,h/2,text=c.secret_glyph,fill=foreground,font=('Segoe UI',max(8,ui.px(11))))
        else:
            c.coords(item,w/2,h/2);c.itemconfigure(item,text=c.secret_glyph,fill=foreground,font=('Segoe UI',max(8,ui.px(11))))

    def paint(self,c,hover=False):
        if c is self.clock:return self.paint_clock(hover)
        if c is self.temperature:
            return self.paint_weather(c,hover)
        bg=ttk.Style(self.root).lookup('TFrame','background') or ui.P['background']
        if c in (self.clock,self.square):bg=ttk.Style(self.root).lookup('TLabel','background') or bg
        if c in (self.screw,self.pumpkin):bg=ui.P['header_background']
        c.configure(background=bg,width=ui.px(c.secret_size[0]),height=ui.px(c.secret_size[1]))
        c.delete('all');w,h=ui.px(c.secret_size[0]),ui.px(c.secret_size[1])
        asset=next((k for k in ('drum','bell','stocking','temperature','sorel_eagle','trick_pumpkin') if c is self.hiding.get(k)),None)
        photo=self.icon(asset,w,h) if asset else None
        if photo:
            c.secret_photo=photo
            c.create_image(w/2 if asset!='temperature' else h/2,h/2,image=photo)
            if asset=='temperature':
                c.create_text(h+3,h/2,text='−17°C',anchor='w',fill=ui.P['foreground'],font=('Segoe UI',ui.px(12),'bold'))
        elif c is self.drum:
            c.create_oval(13,12,w-12,h-12,fill='#654c36',outline=ui.P['copper'],width=2)
            c.create_oval(13,7,w-12,26,fill='#cfbd90',outline='#e5cea2',width=2)
            for x in (20,35,50):c.create_line(x,24,x+7,h-14,fill='#c8ae7c',width=2)
        elif c is self.stocking:
            c.create_polygon(4,3,12,3,12,h-6,16,h-5,16,h-1,5,h-1,4,h-5,fill=ui.P['copper'],outline='')
            c.create_rectangle(3,2,13,6,fill=ui.P['foreground'],outline='')
        elif c is self.bell:
            c.create_polygon(w*.25,h*.73,w*.32,h*.3,w*.5,h*.17,w*.68,h*.3,w*.75,h*.73,
                smooth=True,fill=ui.P['copper'],outline=ui.P['foreground'])
            c.create_line(w*.2,h*.75,w*.8,h*.75,fill=ui.P['copper'],width=2)
            c.create_oval(w*.44,h*.78,w*.56,h*.91,fill=ui.P['copper'],outline='')
        elif c is self.sandwich:
            # A tiny, unlabelled sandwich tucked into the Ideas heading's tools.
            p=ui.scale()
            for yy,colour in ((6,'#e6b771'),(9,'#72a04b'),(11,'#b65139'),(13,'#e5c966'),(15,'#c88c49')):
                c.create_rectangle(4*p,yy*p,20*p,(yy+3)*p,fill=colour,outline='')
            c.create_line(5*p,5*p,18*p,5*p,fill='#f4d89b',width=max(1,ui.px(2)))
        elif c is self.moustache:
            for sign in (-1,1):
                c.create_polygon(w*.5,h*.45,w*(.5+sign*.17),h*.29,w*(.5+sign*.38),h*.47,
                    w*(.5+sign*.46),h*.31,w*(.5+sign*.36),h*.72,w*(.5+sign*.13),h*.67,
                    smooth=True,fill=ui.P['copper'] if hover else ui.P['muted'],outline='')
        else:
            c.create_text(w/2,h/2,text=c.secret_glyph,fill=ui.P['copper'] if hover else ui.P['muted'],font=('Segoe UI',max(8,ui.px(11))))
        if hover:c.create_rectangle(1,1,w-2,h-2,outline=ui.P['copper'])

    def retheme(self):
        if self.closed:return
        name=ui.THEME['t'].get('name','Classic')
        if name!=self.theme:
            if self.midnight.active:self.midnight.deactivate()
            self.dismiss();self.audio.stop();self.taps=0;self.beats.clear();self.cancel_hover()
            if self.burned and name!='Sons of Sorel':
                ui._themes['Sons of Sorel']=self.sorel_original;self.burned=False
            if self.game and self.game.winfo_exists():self.game.destroy()
        if self.treats and name!='Halloween':self.treats.close();self.treats=None
        self.theme=name
        if name!='BurgSys':
            for panel in list(self.changes_panels):
                if panel.winfo_exists():panel.destroy()
        for c in self.hiding.values():
            c.pack_forget();c.place_forget();c.grid_forget()
        self.drum_strip.pack_forget()
        footer_pad=ui.px(4)
        self.app.status.configure(padding=(ui.px(20) if name=='Classic' else 0,footer_pad,ui.px(62),footer_pad))
        self.todo.mode_buttons['vc'].configure(padding='')
        self.clock.place(relx=1,rely=.5,anchor='e',x=-3)
        if name=='Arctic Station':self.temperature.pack(side='bottom',after=self.app.radio,fill='x',padx=8,pady=(0,6))
        elif name=='Sons of Sorel':self.gear.place(relx=1,rely=.5,anchor='e',x=-3)
        elif name=='Soviet Terminal':self.screw.pack(side='right',padx=4)
        elif name=='Stallonian Gambit':
            self.moustache.pack(side='left',padx=(0,4))
            self.sandwich.pack(side='right',padx=4)
        elif name=='Halloween':
            self.scratch.pack(side='right',padx=4)
            self.place_pumpkin()
        elif name=='Christmas':
            self.bell.pack(side='top',anchor='e')
            self.todo.mode_buttons['vc'].configure(padding=(ui.px(10),ui.px(4),ui.px(28),ui.px(4)))
            self.stocking.place(relx=1,x=-ui.px(3),rely=.5,anchor='e')
        elif name=='Rising Sun':self.ink.grid(row=2,column=0,sticky='w')
        elif name=='Andorran Dream':self.ornament.pack(side='left',padx=2)
        elif name=='Classic':self.square.place(x=1,rely=.5,anchor='w')
        self.app.settings_menu.entryconfigure(self.drum_index,state='normal' if name=='Field Grey' else 'disabled')
        if name=='Field Grey' and self.drum_var.get():
            self.drum_strip.pack(side='bottom',fill='x',before=self.app.body)
            self.drum_strip.retheme()
        for c in self.hiding.values():self.paint(c)
        if name=='Midnight' and self.midnight.active:self.midnight.request()
        self.app.schedule_logo()

    def asset_path(self,name):
        external=Path(self.app.tool_dir,'secret_assets',name+'.png')
        return external if external.is_file() else Path(paths.BUNDLE)/'secret_assets'/(name+'.png')

    def icon(self,name,width,height):
        name='thermometer' if name=='temperature' else name
        path=self.asset_path(name)
        if not path.is_file():return None
        key=('icon',name,width,height)
        if key not in self.art_cache:
            with Image.open(path) as source:
                im=source.convert('RGBA');im=im.crop(im.getbbox())
                im.thumbnail((height-2 if name=='thermometer' else width-4,height-2),Image.Resampling.LANCZOS)
                self.art_cache[key]=ImageTk.PhotoImage(im,master=self.root)
        return self.art_cache[key]

    def frames(self,kind,scale):
        if kind not in ('duck','duck_wave','penguin','skeleton','sleigh','stocking','cat','eagle'):return []
        path=self.asset_path('duck' if kind=='duck_wave' else kind)
        if not path.is_file():return []
        key=('frames',kind,round(scale,2))
        if key not in self.art_cache:
            with Image.open(path) as source:
                im=source.convert('RGBA')
                if kind in ('duck','duck_wave'):
                    cells=[im.crop((round(col*im.width/4),round(row*im.height/2),round((col+1)*im.width/4),round((row+1)*im.height/2)))
                           for row in range(2) for col in range(4)]
                    boxes=[cell.getbbox() for cell in cells if cell.getbbox()]
                    box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
                    frames=[]
                    cells=[cell.crop(box) for cell in cells]
                    for cell in cells:
                        if kind=='duck_wave':
                            wave=cells[0].copy()
                            wave.paste(cell.crop((0,0,cell.width,round(cell.height*.64))),(0,0))
                            cell=wave
                        else:cell=cell.copy()
                        cell.thumbnail((round(255*scale),round(177*scale)),Image.Resampling.LANCZOS)
                        frames.append(ImageTk.PhotoImage(cell,master=self.root))
                    self.art_cache[key]=frames
                    return frames
                im=im.crop(im.getbbox())
                im.thumbnail((round(300*scale),round(177*scale)),Image.Resampling.LANCZOS)
                limit={'skeleton':10,'penguin':3,'sleigh':2,'stocking':3,'cat':0,'eagle':2}[kind]
                frames=[]
                for step in range(17):
                    if kind=='cat':
                        frame=im.resize((round(im.width*(.94+.12*step/16)),im.height),Image.Resampling.BICUBIC)
                    else:frame=im.rotate((step/8-1)*limit,Image.Resampling.BICUBIC,expand=True)
                    frames.append(ImageTk.PhotoImage(frame,master=self.root))
                self.art_cache[key]=frames
        return self.art_cache[key]

    def attach_changes(self,window):
        if self.theme!='BurgSys':return
        panel=tk.Canvas(window,height=ui.px(86),background='#09070b',highlightthickness=1,
                        highlightbackground='#6e2940',cursor='hand2')
        panel._om_bar=True
        panel.pack(side='bottom',fill='x',padx=12,pady=10)
        self.changes_panels.append(panel)
        def redact(event=None):
            if not panel.winfo_exists():return
            panel.delete('all');w=panel.winfo_width();h=ui.px(86)
            panel.create_rectangle(16,14,w-16,h-14,fill='#020203',outline='#72314c')
            panel.create_text(w/2,h/2,text='CLASSIFIED   ▰ ▰ ▰ ▰ ▰',fill='#a48a9b',font=('Consolas',14,'bold'))
        panel.bind('<Configure>',redact)
        def reveal(event=None):
            unlock(self.app,'egg_burg');begun=time.monotonic()
            was_active=isinstance(self.scene,BurgRitual) and not self.scene.closed
            self.dismiss()
            if not was_active:self.scene=BurgRitual(self)
            panel.unbind('<Configure>')
            def glow():
                if not panel.winfo_exists():return
                panel.delete('all');w=panel.winfo_width();h=ui.px(86)
                pulse=(math.sin((time.monotonic()-begun)*3)+1)/2
                for dx,dy in ((-2,0),(2,0),(0,-2),(0,2)):
                    panel.create_text(w/2+dx,h/2+dy,text='Himmler was Added',fill='#7f123c',font=('Georgia',ui.px(20),'bold'))
                panel.create_text(w/2,h/2,text='Himmler was Added',fill='#ff9eac' if pulse>.5 else '#d75174',font=('Georgia',ui.px(20),'bold'))
                panel.secret_job=panel.after(33,glow)
            if not hasattr(panel,'secret_job'):glow()
        def cleanup(event):
            if event.widget is panel:
                if hasattr(panel,'secret_job'):panel.after_cancel(panel.secret_job)
                if panel in self.changes_panels:self.changes_panels.remove(panel)
        panel.bind('<Button-1>',reveal);panel.bind('<Destroy>',cleanup)

    def image(self,kind,scale):
        if kind=='vapor':
            images={}
            for name,size in (('palm',(80,115)),('cassette',(100,66))):
                path=self.asset_path(name)
                if path.is_file():
                    with Image.open(path) as source:
                        im=source.convert('RGBA');im=im.crop(im.getbbox())
                        im.thumbnail((round(size[0]*scale),round(size[1]*scale)),Image.Resampling.LANCZOS)
                        if name=='palm':
                            images['left']=ImageTk.PhotoImage(im,master=self.root)
                            images['right']=ImageTk.PhotoImage(ImageOps.mirror(im),master=self.root)
                        else:images['cassette']=ImageTk.PhotoImage(im,master=self.root)
            return images
        path=None;size=180
        if kind=='portrait':path=Path(self.app.tool_dir,'themes','Stallonian Gambit','assets','stallonian_badge.png')
        elif kind=='logo':
            path=Path(self.app.tool_dir,'themes','Revolution Realised','assets','logo.png');size=300
        if path and path.is_file():
            try:
                with Image.open(path) as im:
                    im=im.convert('RGBA');im.thumbnail((round(size*scale),round(size*scale)),Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(im,master=self.root)
            except OSError:pass
        return None

    def snack(self):
        if self.closed or self.theme!='Stallonian Gambit' or self.todo.mode.get()!='idea':return
        if not self.todo.idea_pane.list.winfo_ismapped():return
        self.dismiss()
        self.scene=IdeaSandwich(self)

    def activate(self,key,kind,sound=None,duration=7,travel=False):
        if self.closed:return
        if kind=='penguin':
            if self.theme!='Arctic Station':return
            if isinstance(self.scene,PenguinParade) and not self.scene.closed:
                self.scene.launch();return
            self.dismiss()
            unlock(self.app,key)
            self.scene=PenguinParade(self)
            return
        if kind=='stocking' and isinstance(self.scene,CandyBurst) and not self.scene.closed:
            self.scene.launch();return
        if kind=='sleigh':
            if not any(dev.get('name')==self.todo.me.get() for dev in self.todo.data.get('devs',[])):
                self.app.set_status('Choose your developer name before playing.');return
            self.dismiss();self.scene=SantaGame(self);return
        if kind=='cat' and (not self.todo.cur or not self.todo.d_title.winfo_ismapped()):return
        self.dismiss()
        unlock(self.app,key)
        if kind=='vapor':sound=sound or 'zhgyv';duration=max(duration,11.2)
        if sound:self.audio.play(sound)
        if kind=='duck':self.scene=DuckWalk(self,duration)
        elif kind=='cat':self.scene=CatScratch(self)
        elif kind=='eagle':self.scene=ImperialEagle(self)
        elif kind=='stocking':self.scene=CandyBurst(self)
        elif kind=='skeleton':self.scene=SkeletonHand(self)
        else:self.scene=Scene(self,kind,duration,travel)

    def dismiss(self):
        if self.scene:self.scene.close();self.scene=None

    def hover(self,key,kind):
        self.cancel_hover()
        self.hover_job=self.root.after(600,lambda:self.hover_fire(key,kind))

    def hover_fire(self,key,kind):
        self.hover_job=None
        self.activate(key,kind,duration=None if kind=='logo' else 7)

    def leave_classic(self,event=None):
        self.cancel_hover()
        if self.scene and getattr(self.scene,'kind',None)=='logo':self.dismiss()

    def cancel_hover(self,event=None):
        if self.hover_job is not None:self.root.after_cancel(self.hover_job);self.hover_job=None

    def duck_tap(self,event=None):
        if self.theme!='Revolution Realised':return
        self.taps+=1
        if self.taps>=7:self.taps=0;self.activate('egg_rr','duck')

    def clock_tick(self):
        if self.closed:return
        self.clock.secret_glyph=datetime.datetime.now().strftime('%H:%M')
        self.clock.secret_size=(48,22)
        now=datetime.datetime.now()
        if (self.theme=='Midnight' and now.date()!=self.last_clock.date()
                and now.hour==0 and now.minute==0
                and 0<(now-self.last_clock).total_seconds()<5):
            self.audio.play('midnight_chime')
            self.clock_flash_until=time.monotonic()+8
        self.last_clock=now
        self.paint(self.clock)
        if self.theme=='Midnight' and not self.midnight.active and time.monotonic()<self.clock_flash_until and now.second%2==0:
            self.clock.configure(background=ui.P['copper'])
            for item in self.clock.find_all():
                if self.clock.type(item)=='text':self.clock.itemconfigure(item,fill=ui.P['background'])
        self.clock_job=self.root.after(1000,self.clock_tick)

    def place_pumpkin(self):
        if self.theme!='Halloween':return
        exit_button=self.app.fs_buttons[0]
        if exit_button.winfo_manager()=='pack':self.pumpkin.pack(side='right',after=exit_button,padx=3)
        else:self.pumpkin.pack(side='right',padx=3)

    def trick_or_treat(self):
        if self.closed or self.theme!='Halloween':return
        if self.treats and not self.treats.closed:self.treats.launch()
        else:self.treats=CandyBurst(self,source=self.pumpkin,theme='Halloween',kind='treat')

    def toggle_drum(self):
        self.app.config['marching_band']=self.drum_var.get();self.app.save_config();self.retheme()

    def hit_drum(self):
        if self.theme!='Field Grey' or not self.drum_var.get():return
        self.audio.play('field_drum');unlock(self.app,'egg_field')
        now=time.monotonic();self.beats.append(now)
        while self.beats and now-self.beats[0]>10:self.beats.popleft()
        if len(self.beats)>=16:unlock(self.app,'egg_field_combo')

    def scorch(self):
        if self.theme!='Sons of Sorel':return
        if isinstance(self.scene,SorelBurn):
            self.dismiss()
            if not self.burned:return
        if self.burned:
            ui._themes[self.theme]=self.sorel_original;self.burned=False
            ui.apply_theme(self.root,self.theme)
            self.dismiss();return
        self.dismiss()
        self.sorel_original=ui._themes[self.theme]
        self.scene=SorelBurn(self)

    def apply_scorch(self):
        if self.closed or self.theme!='Sons of Sorel':return
        burned=copy.deepcopy(self.sorel_original)
        burned['id']='sons-of-sorel-scorched';burned.pop('assets',None);burned.pop('gradients',None)
        burned['icon_theme_id']=self.sorel_original.get('id')
        burned['colors'].update(background='#100f0e',surface='#201b18',sidebar='#171310',foreground='#d4c5ae',muted='#a48a72',
            copper='#df7a3c',header_background='#30231d',header_foreground='#e6b984',header_hover='#493022',
            stripe='#261d18',selection_background='#67402b',selection_foreground='#f6dbc0',button_background='#36231b',
            button_foreground='#d9b38d',button_active='#613925',button_pressed='#6b3a25',button_pressed_foreground='#ffe0be',
            input_background='#151210',input_foreground='#dbcebb',border='#664936')
        self.burned=True;ui._themes[self.theme]=burned;ui.apply_theme(self.root,self.theme)
        unlock(self.app,'egg_sorel')

    def terminal(self):
        if self.theme!='Soviet Terminal':return
        unlock(self.app,'egg_terminal')
        if self.game and self.game.winfo_exists():self.game.lift();return
        self.game=TerminalGame(self)

    def close(self):
        self.closed=True;self.dismiss();self.cancel_hover();self.audio.stop()
        self.drum_strip.close()
        self.midnight.close()
        if self.treats:self.treats.close()
        for panel in list(self.changes_panels):
            if panel.winfo_exists():panel.destroy()
        if self.clock_job:self.root.after_cancel(self.clock_job);self.clock_job=None
        if self.game and self.game.winfo_exists():self.game.destroy()
        if self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)
        if self.burned:ui._themes['Sons of Sorel']=self.sorel_original
