"""Christmas present catching, with a retained, live-synced developer scoreboard."""
import datetime
import math
import time
import tkinter as tk
from tkinter import ttk
import uuid

from PIL import Image, ImageTk

import ui
from theme_secret_catalog import unlock


def best_scores(data):
    scores = {}
    for run in data.get('sleigh_scores', []):
        name = run.get('dev', '')
        if name:
            scores[name] = max(scores.get(name, 0), int(run.get('score', 0)))
    return sorted(scores.items(), key=lambda item: (-item[1], item[0].lower()))


def sprite_row(path, columns, size, root):
    """Trim an atlas with one shared box, then keep its small, crisp pixel steps."""
    with Image.open(path) as source:
        atlas=source.convert('RGBA')
        cells=[atlas.crop((round(n*atlas.width/columns),0,round((n+1)*atlas.width/columns),atlas.height)) for n in range(columns)]
    boxes=[cell.getchannel('A').point(lambda a:255 if a>40 else 0).getbbox() for cell in cells]
    boxes=[box for box in boxes if box]
    box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    photos=[]
    for cell in cells:
        cell=cell.crop(box)
        # Logical half-resolution grid avoids tiny smooth details and shimmer.
        cell.thumbnail((max(1,size[0]//2),max(1,size[1]//2)),Image.Resampling.NEAREST)
        cell=cell.resize((cell.width*2,cell.height*2),Image.Resampling.NEAREST)
        frame=Image.new('RGBA',size)
        frame.paste(cell,((size[0]-cell.width)//2,size[1]-cell.height))
        photos.append(ImageTk.PhotoImage(frame,master=root))
    return photos


class PresentRun:
    """The game clock and rules, independent of Tk and saving."""
    def __init__(self):
        self.time = 0.
        self.score = 0
        self.gifts = []
        self.spawned = 0
        self.next_drop = 1.2
        self.last_drop = -100.
        self.over = False

    @property
    def speed(self):
        return 1 + self.score * .055

    def santa(self, width, height, scale=1):
        progress = min(1, self.time / 8)
        if progress < 1:
            x = 80 + 100*math.sin(math.pi*progress)
            climb=height/scale-290
            y = height/scale-180-progress*climb-climb*.12*math.sin(progress*6*math.pi)
            return x*scale, y*scale
        phase = (self.time-8)*.45
        return ((80+(width/scale-160)*(.5-.5*math.cos(phase)))*scale,
                (110+38*math.sin(phase*3))*scale)

    def tick(self, dt, width, height, scale=1):
        if self.over:
            return
        self.time += dt*self.speed
        if self.time >= self.next_drop:
            self.last_drop = self.time
            x, y = self.santa(width, height, scale)
            for n in range(1+min(2, self.score//20)):
                self.spawned += 1
                self.gifts.append(dict(id=self.spawned, kind=(self.spawned-1)%5,
                    x=max(24*scale,min(width-24*scale,x-48*scale+n*44*scale)),y=y+8*scale))
            self.next_drop = self.time + max(.22, 1.15/(1+self.score*.025))
        for gift in self.gifts:
            gift['y'] += dt*(72+3*self.score)*scale
        if any(g['y'] > height+24*scale for g in self.gifts):
            self.over = True

    def throw_pose(self):
        if 0<=self.time-self.last_drop<.18:
            return 3
        remaining=self.next_drop-self.time
        if 0<remaining<=.55:
            return min(2,int((.55-remaining)/(.55/3)))
        return None

    def catch(self, x, y, radius=24):
        if self.over:
            return False
        for gift in reversed(self.gifts):
            if abs(gift['x']-x)<=radius and abs(gift['y']-y)<=radius:
                self.gifts.remove(gift)
                self.score += 1
                return True
        return False


def show_leaderboard(owner, score):
    window=tk.Toplevel(owner.root)
    window.title('Present catch — leaderboard');window.transient(owner.root)
    body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
    ttk.Label(body,text=f'You caught {score} presents',font='om_title').pack(anchor='w',pady=(0,8))
    tree=ttk.Treeview(body,columns=('dev','score'),show='headings',height=10)
    tree.heading('dev',text='Developer');tree.heading('score',text='Best run')
    tree.column('dev',width=200);tree.column('score',width=90,anchor='center');tree.pack(fill='both',expand=True)
    def fill():
        for item in tree.get_children():tree.delete(item)
        for name,points in best_scores(owner.todo.data):tree.insert('','end',values=(name,points))
        window._score_job=window.after(1500,fill)
    def cleanup(event):
        if event.widget is window and getattr(window,'_score_job',None):window.after_cancel(window._score_job)
    buttons=ttk.Frame(body);buttons.pack(fill='x',pady=(8,0))
    ttk.Button(buttons,text='Close',command=window.destroy).pack(side='right')
    window.bind('<Destroy>',cleanup);fill()
    return window


class SantaGame:
    def __init__(self,owner):
        self.owner,self.root=owner,owner.root
        self.todo=owner.todo;self.player=self.todo.me.get()
        self.run=PresentRun();self.run_id=uuid.uuid4().hex
        self.when=datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.closed=False;self.job=None;self.bounds=None;self.last=time.monotonic()
        self.last_save=self.last;self.dirty=False;self.next_hoho=0
        self.loop_channel=None;self.had_focus=False
        size=(ui.px(160),ui.px(88))
        self.sleigh=sprite_row(owner.asset_path('santa_flight'),4,size,self.root)
        self.throw_frames=sprite_row(owner.asset_path('santa_throw'),4,size,self.root)
        self.gift_photos=sprite_row(owner.asset_path('christmas_presents'),5,(ui.px(40),ui.px(44)),self.root)
        self.window=tk.Toplevel(self.root);self.window.withdraw()
        self.window._om_nonmodal=True
        self.window._om_bar=self.window._om_effect_layer=True
        self.window.overrideredirect(True);self.window.transient(self.root)
        self.window.configure(background='#270d17')
        self.window.attributes('-transparentcolor','#270d17')
        self.canvas=tk.Canvas(self.window,background='#270d17',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=False)
        self.canvas._om_bar=self.canvas._om_effect_layer=True
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Button-1>',self.click)
        self.window.bind('<Escape>',self.escape)
        self.canvas.bind('<KeyPress>',lambda e:self.escape(e) if e.keysym=='Escape' else 'break')
        self.canvas.bind('<KeyRelease>',lambda e:'break')
        self.input_tag='SantaInput_'+self.run_id
        self.input_widgets=[]
        self.previous_focus=self.root.focus_get()
        self.previous_grab=self.root.grab_current()
        for sequence in ('<ButtonPress>','<ButtonRelease>','<KeyPress>','<KeyRelease>','<MouseWheel>','<Motion>'):
            self.root.bind_class(self.input_tag,sequence,self.block_background)
        self.lock_background(self.root)
        self.window.deiconify();self.window.grab_set();self.canvas.focus_set();self.frame()

    def escape(self,event=None):
        self.owner.dismiss()
        return 'break'

    def block_background(self,event):
        if getattr(event,'keysym','')=='Escape':self.escape()
        return 'break'

    def lock_background(self,widget):
        if widget is self.window:return
        widget.bindtags((self.input_tag,)+widget.bindtags())
        self.input_widgets.append(widget)
        for child in widget.winfo_children():self.lock_background(child)

    def release_input(self):
        if self.root.grab_current() is self.window:self.window.grab_release()
        for widget in self.input_widgets:
            if widget.winfo_exists():widget.bindtags(tuple(tag for tag in widget.bindtags() if tag!=self.input_tag))
        for sequence in ('<ButtonPress>','<ButtonRelease>','<KeyPress>','<KeyRelease>','<MouseWheel>','<Motion>'):
            self.root.unbind_class(self.input_tag,sequence)
        if self.previous_grab and self.previous_grab.winfo_exists():self.previous_grab.grab_set()
        if self.previous_focus and self.previous_focus.winfo_exists():self.previous_focus.focus_set()

    def save_score(self,finished=False):
        scores=self.todo.data.setdefault('sleigh_scores',[])
        existing=next((r for r in scores if r.get('id')==self.run_id),None)
        record=dict(id=self.run_id,dev=self.player,score=self.run.score,when=self.when,finished=finished)
        if existing:
            record['score']=max(existing.get('score',0),record['score']);existing.update(record)
        else:scores.append(record)
        self.todo.save(undoable=False,feedback=False)
        self.dirty=False;self.last_save=time.monotonic()

    def click(self,event):
        if self.closed:return
        if self.run.catch(event.x,event.y,ui.px(24)):
            self.dirty=True
            self.owner.audio.play('santa_collect')
            if self.run.score==10:
                self.save_score();unlock(self.owner.app,'egg_sleigh_10')
            return 'break'

    def frame(self):
        self.job=None
        if self.closed:return
        now=time.monotonic();dt=min(.05,now-self.last);self.last=now
        if self.owner.theme!='Christmas' or self.todo.me.get()!=self.player:
            self.close();return
        from todo_sync import blocking_dialog_open
        focused=self.root.focus_displayof() is not None
        self.had_focus=self.had_focus or focused
        paused=(self.root.state() not in ('normal','zoomed') or blocking_dialog_open(self.todo)
                or (self.had_focus and not focused))
        self.paused=paused
        if paused:
            if self.root.grab_current() is self.window:self.window.grab_release()
            self.window.withdraw();self.bounds=None
            self.stop_audio();self.job=self.root.after(100,self.frame);return
        if not self.window.winfo_ismapped():
            self.window.deiconify();self.window.grab_set();self.canvas.focus_set()
        bounds=(self.root.winfo_width(),self.root.winfo_height(),self.root.winfo_rootx(),self.root.winfo_rooty())
        w,h,x,y=bounds
        if bounds!=self.bounds:
            self.window.lift(self.root);self.window.geometry(f'{w}x{h}+{x}+{y}')
            self.canvas.configure(width=w,height=h);self.bounds=bounds
        elif self.window.tk.getboolean(self.window.tk.call('wm','stackorder',str(self.window),'isbelow',str(self.root))):
            self.window.lift(self.root)
        self.run.tick(dt,w,h,ui.scale())
        if self.run.over:
            self.close();return
        c=self.canvas;c.delete('all')
        sx,sy=self.run.santa(w,h,ui.scale())
        pose=self.run.throw_pose()
        photo=self.sleigh[int(self.run.time*7)%len(self.sleigh)] if pose is None else self.throw_frames[pose]
        c.create_image(sx,sy,image=photo)
        for gift in self.run.gifts:
            c.create_image(gift['x'],gift['y'],image=self.gift_photos[gift['kind']],tags=('present',f'gift:{gift["id"]}'))
        if self.owner.app.sound_settings.enabled():
            try:
                if self.loop_channel is None or not self.loop_channel.get_busy():
                    clip=self.owner.audio.load('santa_bells');clip.set_volume(.18*self.owner.app.sound_settings.volume())
                    self.loop_channel=clip.play(loops=-1)
                else:self.owner.audio.sounds['santa_bells'].set_volume(.18*self.owner.app.sound_settings.volume())
            except Exception:pass
            if self.run.time>=self.next_hoho:
                self.owner.audio.play('santa_hoho');self.next_hoho=self.run.time+12
        else:self.stop_audio()
        if self.dirty and now-self.last_save>=1:self.save_score()
        self.job=self.root.after(max(10,16-round((time.monotonic()-now)*1000)),self.frame)

    def stop_audio(self):
        if self.loop_channel:self.loop_channel.stop();self.loop_channel=None
        self.owner.audio.stop('santa_hoho')
        self.owner.audio.stop('santa_collect')

    def close(self):
        if self.closed:return
        self.closed=True
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        self.stop_audio()
        self.release_input()
        self.save_score(finished=True)
        if self.window.winfo_exists():self.window.destroy()
        if self.run.over and not getattr(self.owner,'closed',False):
            show_leaderboard(self.owner,self.run.score)
