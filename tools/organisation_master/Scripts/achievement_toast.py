"""Queued, nonmodal achievement celebrations for the current developer."""
from collections import deque
import math
import time
import tkinter as tk

from achievements import BADGES,badge_tool
from gfx_card_style import ornament,fitted_text,blend
from secret_audio import SecretAudio
import icons
import ui

CATALOG={row[0]:row for row in BADGES}


class UnlockTracker:
    """Seed existing badges; union snapshots so undo/sync cannot replay an unlock."""
    def __init__(self,data):
        self.seen={dev['name']:set(dev.get('achievements') or {}) for dev in data.get('devs',[])}

    def update(self,data,player,quiet=False):
        earned=[]
        for dev in data.get('devs',[]):
            name=dev['name'];keys=set(dev.get('achievements') or {})
            before=self.seen.setdefault(name,set())
            if name==player and not quiet:earned.extend(key for key in CATALOG if key in keys-before)
            before.update(keys)
        return earned


def toast_pose(elapsed,exit_elapsed=None):
    entrance=max(0,min(1,elapsed/.35));entrance=1-(1-entrance)**3
    exit_progress=max(0,min(1,(elapsed-9.65)/.35 if exit_elapsed is None else exit_elapsed/.25))
    exit_progress=exit_progress*exit_progress*(3-2*exit_progress)
    return (1-entrance)*22+exit_progress*10,entrance*(1-exit_progress)


class AchievementToasts:
    def __init__(self,app):
        self.app,self.root=app,app.root
        todo=app.todo_page();self.player=todo.me.get();self.tracker=UnlockTracker(todo.data)
        self.pending=deque();self.window=None;self.job=None;self.closed=False
        self.audio=SecretAudio(app);self.started=self.exiting=None;self.bounds=None
        ui.THEME_HOOKS.append(self.retheme)

    def observe(self,data,player,quiet=False):
        if self.closed:return
        if player!=self.player:
            self.pending.clear();self.destroy_popup();self.player=player
        self.pending.extend(self.tracker.update(data,player,quiet))
        if self.window is None and self.pending and self.job is None:
            self.job=self.root.after(150,self.show_next)

    def show_next(self):
        self.job=None
        if self.closed or not self.pending or getattr(self.app,'_quitting',False):return
        # Let dialogs and the present-catching input grab finish first.
        if self.root.state() not in ('normal','zoomed') or self.root.grab_current() is not None or self.root.focus_displayof() is None:
            self.job=self.root.after(350,self.show_next);return
        try:focus=self.root.focus_get()
        except (KeyError,tk.TclError):focus=None
        self.parent=focus.winfo_toplevel() if focus is not None else self.root
        if (getattr(self.parent,'_om_effect_layer',False) or self.parent.winfo_width()<ui.px(340)
                or self.parent.winfo_height()<ui.px(200)):self.parent=self.root
        self.key=self.pending.popleft()
        self.window=tk.Toplevel(self.root);self.window.withdraw()
        self.window._om_nonmodal=self.window._om_bar=self.window._om_effect_layer=True
        self.window.overrideredirect(True);self.window.transient(self.parent)
        self.window.configure(background=ui.P['surface'])
        self.window.attributes('-alpha',0)
        self.canvas=tk.Canvas(self.window,background=ui.P['surface'],highlightthickness=0,borderwidth=0,cursor='hand2',takefocus=False)
        self.canvas._om_bar=self.canvas._om_effect_layer=True
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Button-1>',self.dismiss)
        self.started=time.monotonic();self.exiting=None;self.bounds=None
        self.photo=None;self.photo_theme=None
        self.window.deiconify();self.window.lift(self.parent)
        self.audio.play('achievement_unlock')
        self.animate()

    def draw(self,elapsed,width,height):
        c=self.canvas;c.delete('all');p=ui.P;s=ui.scale()
        row=CATALOG[self.key];_,title,icon,_,_,_,requirement=row
        header=p['header_background'];body=p['surface'];accent=p['copper']
        c.configure(background=body)
        for n in range(16):
            c.create_rectangle(0,height*n/16,width,height*(n+1)/16+1,fill=blend(header,body,n/15),outline='')
        c.create_rectangle(1,1,width-2,height-2,outline=p['border'])
        c.create_line(2,2,width-3,2,fill=blend(accent,p['foreground'],.3))
        c.create_rectangle(0,0,ui.px(4),height,fill=accent,outline='')
        cx,cy=ui.px(43),ui.px(58)
        c.create_oval(cx-ui.px(28),cy-ui.px(28),cx+ui.px(28),cy+ui.px(28),fill=header,outline=accent,width=ui.px(2))
        signature=(ui.THEME['t']['name'],ui.px(39),icon)
        if signature!=self.photo_theme:
            self.photo=icons.image(icon,ui.px(39));self.photo_theme=signature
        lift=-abs(math.sin(min(elapsed,1)*math.pi*2))*ui.px(3) if elapsed<1 else 0
        if self.photo:c.create_image(cx,cy+lift,image=self.photo)
        else:c.create_text(cx,cy+lift,text='★',font='om_big',fill=accent)
        if elapsed<1.2:
            for n in range(5):
                angle=n*math.tau/5+elapsed*.7
                radius=(30+min(1,elapsed)*7)*s
                x,y=cx+math.cos(angle)*radius,cy+math.sin(angle)*radius
                c.create_line(x-2*s,y,x+2*s,y,fill=accent)
                c.create_line(x,y-2*s,x,y+2*s,fill=accent)
        tx=ui.px(85);space=width-tx-ui.px(18)
        c.create_text(tx,ui.px(12),anchor='nw',text='ACHIEVEMENT UNLOCKED',font='om_small_bold',fill=p['header_foreground'])
        end=fitted_text(c,tx,ui.px(34),title,space,ui.px(40),font='om_head',fill=p['foreground'])
        fitted_text(c,tx,end+ui.px(4),requirement,space,ui.px(34),font='om_small',fill=p['foreground'])
        c.create_text(tx,height-ui.px(17),anchor='sw',text=self.player+' · '+badge_tool(self.key),font='om_tiny',fill=p['muted'],width=space)
        ornament(c,ui.THEME['t']['name'],width-ui.px(43),ui.px(8),ui.px(27),accent,blend(header,accent,.25),header)
        remaining=max(0,1-elapsed/10)
        c.create_line(ui.px(12),height-ui.px(7),ui.px(12)+(width-ui.px(24))*remaining,height-ui.px(7),fill=accent,width=ui.px(2))

    def animate(self):
        self.job=None
        if self.closed or self.window is None:return
        now=time.monotonic();elapsed=now-self.started
        exit_elapsed=None if self.exiting is None else now-self.exiting
        if elapsed>=10 or (exit_elapsed is not None and exit_elapsed>=.25) or not self.parent.winfo_exists() or self.parent.state() not in ('normal','zoomed'):
            self.destroy_popup();self.next_pending();return
        width=min(ui.px(440),max(ui.px(240),self.parent.winfo_width()-ui.px(24)))
        height=ui.px(145)
        pose_elapsed=elapsed if exit_elapsed is None else self.exiting-self.started
        offset,alpha=toast_pose(pose_elapsed,exit_elapsed)
        x=self.parent.winfo_rootx()+max(0,self.parent.winfo_width()-width-ui.px(16))
        y=self.parent.winfo_rooty()+max(0,self.parent.winfo_height()-height-ui.px(24))+round(offset*ui.scale())
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        self.window.attributes('-alpha',alpha)
        self.draw(elapsed,width,height)
        self.job=self.root.after(33,self.animate)

    def dismiss(self,event=None):
        if self.window is not None and self.exiting is None:self.exiting=time.monotonic()
        return 'break'

    def next_pending(self):
        if self.pending and not self.closed:self.job=self.root.after(200,self.show_next)

    def destroy_popup(self):
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
        if self.window is not None:
            self.window.destroy();self.window=None
        self.photo=None

    def retheme(self):
        if self.window is not None:self.photo_theme=None

    def close(self):
        self.closed=True;self.pending.clear();self.destroy_popup();self.audio.stop('achievement_unlock')
        if self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)
