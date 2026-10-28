"""Themed, bounded error-alert header animations."""
import time
import tkinter as tk
import ui
from error_alert_scenes import SCENES,draw_scene,DURATION
from soviet_alert_wireframe import draw_soviet


def nuke_scene(elapsed):
    if elapsed < 1.5: return "fall", max(0,elapsed/1.5)
    if elapsed < 2.05: return "blast", (elapsed-1.5)/.55
    if elapsed < 5: return "cloud", (elapsed-2.05)/2.95
    return "settled", 1.0


class AlertHeader(tk.Canvas):
    def __init__(self,parent,audio=None):
        super().__init__(parent,height=ui.px(100),width=ui.px(520),highlightthickness=0,borderwidth=0)
        self._om_effect_layer=True
        self.job=None;self.theme=None;self.started=time.monotonic();self.audio=audio
        self.bind("<Configure>",lambda e:self.draw(time.monotonic()-self.started))
        self.bind("<Destroy>",self.destroyed,add="+")
        ui.THEME_HOOKS.append(self.retheme)
        self.retheme()

    def retheme(self):
        name=ui.THEME["t"]["name"]
        if self.job is not None:self.after_cancel(self.job);self.job=None
        if name!=self.theme:
            self.started=time.monotonic()
            if hasattr(self,"_scene_images"):self._scene_images.clear()
            if self.audio:self.audio.play(name)
        self.theme=name
        self.configure(height=ui.px(176),background=ui.P["header_background"])
        self.tick()

    def tick(self):
        self.job=None
        elapsed=time.monotonic()-self.started
        if self.audio:self.audio.update()
        self.draw(elapsed)
        if (self.theme=="Soviet Terminal" or self.theme in SCENES) and elapsed<DURATION:
            self.job=self.after(33,self.tick)

    def draw(self,elapsed):
        if not self.winfo_exists():return
        self.delete("all");p=ui.P;w=max(1,self.winfo_width());h=max(1,self.winfo_height())
        self.configure(background=p["header_background"])
        self.create_line(0,h-1,w,h-1,fill=p["border"])
        if self.theme!="Soviet Terminal":
            sx=w/520;sy=h/176
            self.create_text(14*sx,24*sy,text="INCOMING ERROR ALERT",anchor="w",fill=p["header_foreground"],font="om_bold")
            self.create_text(14*sx,53*sy,text="A teammate needs your attention",anchor="w",fill=p["foreground"],font="om_small",width=230*sx)
            self.create_text(14*sx,89*sy,text=SCENES.get(self.theme,"Review the diagnostic report"),anchor="w",fill=p["muted"],font="om_small",width=230*sx)
            self.create_text(14*sx,140*sy,text="ACTION REQUIRED",anchor="w",fill=p["age_red"],font="om_small_bold")
            draw_scene(self,self.theme,elapsed,270*sx,6*sy,245*sx,164*sy,p)
            return
        draw_soviet(self,elapsed,w,h,p,nuke_scene(elapsed))

    def destroyed(self,event):
        if event.widget is self:
            if self.audio:self.audio.stop()
            if self.job is not None:self.after_cancel(self.job);self.job=None
            if self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)
            if hasattr(self,"_scene_images"):self._scene_images.clear()
