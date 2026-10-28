"""Durable shared milestone announcements and a once-per-developer celebration."""
from collections import deque
from datetime import datetime, timezone
import copy
import hashlib
import math
import os
import random
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

import paths
import ui
from gfx_card_style import blend
from secret_audio import SecretAudio

EVENTS = "milestone_celebrations"
SEEN = "milestone_celebration_seen"
HATS = ("Cowboy", "Sombrero", "Bowler", "Ceremonial mask", "Conical hat", "Ushanka")
DURATION = 32.0


def event_key(name):
    return "milestone-" + hashlib.sha256(name.strip().casefold().encode()).hexdigest()[:24]


def animation_for(name):
    text = name.casefold()
    if "technolog" in text or "tech" in text.split():
        return "technology_duck"
    if "mechanic" in text:
        return "mechanics_duck"
    if "culture" in text and "map" in text:
        return "culture_duck"
    return "celebration"


def mechanics_frame(elapsed):
    """The bolt lowers through successive tightening frames and stays seated afterward."""
    if elapsed < 1: return 0
    if elapsed < 6: return min(7, 1 + int((elapsed-1)*7/5))
    if elapsed < 7.5: return 8
    if elapsed < 9: return 9
    if elapsed < 10.2: return 10
    if elapsed < 11: return 11
    if elapsed < 12: return 10
    return 11


def mechanics_sound_step(elapsed):
    return min(3, int((elapsed-1)/1.25)) if 1 <= elapsed < 6 else -1


def technology_frame(elapsed):
    """One backwards-raygun gag, followed by a continuous soot-covered blink loop."""
    if elapsed < 1.6: return 0
    if elapsed < 3.2: return 1
    if elapsed < 5.6: return 2
    if elapsed < 5.82: return 3
    blink = (elapsed-5.82) % 2.7
    if blink < 2.1: return 4
    if blink < 2.2: return 5
    if blink < 2.32: return 6
    if blink < 2.42: return 7
    return 4


TECHNOLOGY_SOUNDS = ((1.6,"milestone_technology_pickup"), (3.2,"milestone_technology_hmm"),
                     (4.5,"milestone_technology_charge"), (5.6,"milestone_laser_zap"),
                     (5.82,"milestone_technology_puff"))


def technology_sound_step(elapsed):
    return max((i for i,(when,_) in enumerate(TECHNOLOGY_SOUNDS) if elapsed >= when),default=-1)


def publish(data, name, who, thanks, animation=None):
    milestone = next(m for m in data.get("milestones", []) if m["name"] == name)
    key = milestone.get("completed_event") or event_key(name)
    if key in data.get(EVENTS, {}):
        return None
    event = dict(id=key, name=name, by=who, at=datetime.now(timezone.utc).isoformat(),
                 thanks=list(dict.fromkeys(thanks)), animation=animation or animation_for(name))
    data.setdefault(EVENTS, {})[key] = event
    milestone.update(completed_event=key, completed_at=event["at"], completed_by=who)
    return event


def merge_records(*snapshots):
    """Append-only event snapshots and per-developer receipts survive stale/older clients."""
    events, seen = {}, {}
    for data in snapshots:
        for key, event in data.get(EVENTS, {}).items():
            if not isinstance(event, dict) or event.get("id") != key:
                continue
            old = events.get(key)
            chosen = min((old, event), key=lambda e: (e.get("at", ""), e.get("by", ""))) if old else event
            combined = sorted(set((old or {}).get("thanks", [])) | set(event.get("thanks", [])))
            events[key] = dict(copy.deepcopy(chosen), thanks=combined)
        for player, receipts in data.get(SEEN, {}).items():
            for key, stamp in receipts.items():
                seen.setdefault(player, {})[key] = max(stamp, seen.get(player, {}).get(key, ""))
    return {EVENTS: events, SEEN: seen}


def restore_status(data):
    for milestone in data.get("milestones", []):
        key = milestone.get("completed_event") or event_key(milestone["name"])
        event = data.get(EVENTS, {}).get(key)
        if event:
            milestone.update(completed_event=key, completed_at=event["at"], completed_by=event.get("by", ""))


def unseen(data, player, local=()):
    seen = set(data.get(SEEN, {}).get(player, {})) | set(local)
    return sorted((event for key, event in data.get(EVENTS, {}).items() if key not in seen and event.get("id") == key),
                  key=lambda e: (e.get("at", ""), e["id"])) if player else []


class Celebrations:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.audio = SecretAudio(app)
        self.pending = deque()
        self.queued = set()
        self.window = None
        self.job = None
        self.closed = False
        self.photos = {}
        self.sheet = None
        self.sheet_kind = None
        self.resume = None
        self.root.after(4800, self.observe_current)

    def observe_current(self):
        if not self.closed:
            todo = self.app.todo_page()
            self.observe(todo.data, todo.me.get())

    def observe(self, data, player):
        local = self.app.config.get("milestone_seen", {}).get(player, [])
        for event in unseen(data, player, local):
            key = (player, event["id"])
            if key not in self.queued:
                self.pending.append((player, copy.deepcopy(event), False))
                self.queued.add(key)
        if self.pending and self.window is None and self.job is None:
            self.job = self.root.after(700, self.show_next)

    def preview(self, name, thanks=(), animation=None):
        event = dict(id="preview", name=name, thanks=list(thanks), by="", animation=animation or animation_for(name))
        self.pending.appendleft((self.app.todo_page().me.get(), event, True))
        if self.window is None and self.job is None:
            self.job = self.root.after(100, self.show_next)

    def show_next(self):
        self.job = None
        if self.closed or not self.pending or getattr(self.app, "_quitting", False):
            return
        # Queue while a dialog/minigame is in use, or the tool is minimized/in the background.
        if self.root.grab_current() is not None or self.root.state() not in ("normal", "zoomed") or self.root.focus_displayof() is None:
            self.job = self.root.after(500, self.show_next)
            return
        todo = self.app.todo_page()
        while self.pending:
            player, event, preview = self.pending.popleft()
            if player != todo.me.get():
                self.queued.discard((player, event["id"]))
                continue
            if not preview and not any(e["id"] == event["id"] for e in unseen(todo.data, player, self.app.config.get("milestone_seen", {}).get(player, []))):
                self.queued.discard((player, event["id"]))
                continue
            break
        else:
            return
        self.player, self.event, self.is_preview = player, event, preview
        self.window = w = tk.Toplevel(self.root)
        w.withdraw(); w.title("Milestone completed")
        w._om_bar = w._om_effect_layer = True
        w.transient(self.root); w.resizable(False, False)
        width = min(ui.px(980), self.root.winfo_width() - 30)
        height = min(ui.px(710), self.root.winfo_height() - 30)
        width, height = max(400, width), max(400, height)
        x = self.root.winfo_rootx() + (self.root.winfo_width()-width)//2
        y = self.root.winfo_rooty() + (self.root.winfo_height()-height)//2
        w.geometry(f"{width}x{height}+{x}+{y}")
        w.configure(background=ui.P["surface"])
        self.canvas = tk.Canvas(w, highlightthickness=0, background=ui.P["surface"])
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill="both", expand=True)
        bar = ttk.Frame(w, padding=(12, 8)); bar.pack(fill="x")
        ttk.Label(bar, text="Preview" if preview else "A milestone worth celebrating!").pack(side="left")
        ttk.Button(bar, text="Celebrate on!  ✓", command=self.dismiss).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", self.dismiss)
        w.bind("<Escape>", lambda e: self.dismiss())
        w.attributes("-alpha", 0); w.deiconify(); w.lift(); w.grab_set()
        self.started = time.monotonic()
        rng = random.Random(event["id"])
        self.confetti = [(rng.random(), rng.random(), rng.uniform(.08,.28), rng.uniform(0,math.tau), rng.choice(("#f8b44c","#e87091","#5dc4c3","#f5e690","#a48be0","#91d78c"))) for _ in range(180)]
        kind = event.get("animation", "celebration")
        if self.sheet is None or self.sheet_kind != kind:
            self.sheet_kind = kind
            filename = {"mechanics_duck": "milestone_mechanics_duck.png", "technology_duck": "milestone_technology_duck.png"}.get(kind, "milestone_culture_duck.png")
            path = os.path.join(paths.TOOL, "secret_assets", filename)
            try:
                with Image.open(path) as image:
                    self.sheet = image.convert("RGBA")
            except OSError:
                self.sheet = None
        self.photos.clear()
        playback = getattr(getattr(self.app, "radio", None), "playback", None)
        self.resume = None
        if playback and playback.active and playback.player.path and not playback.player.paused and self.app.sound_settings.enabled():
            self.resume = (playback.player, playback.player.path)
            playback.player.pause()
        self.technology_sound_step = -1
        self.last_technology_blink = -1
        self.mechanics_sound_step = -1
        self.mechanics_seated = False
        self.music_started = kind not in ("mechanics_duck", "technology_duck")
        if self.music_started:
            self.audio.play("milestone_celebration")
        self.animate()

    def duck(self, index, size, pose):
        key = (index, size, pose)
        if key not in self.photos and self.sheet is not None:
            columns = 4 if self.sheet_kind in ("mechanics_duck", "technology_duck") else 3
            rows = 3 if self.sheet_kind == "mechanics_duck" else 2
            sw, sh = self.sheet.size; cw, ch = sw//columns, sh//rows
            x,y = index%columns*cw, index//columns*ch
            image = self.sheet.crop((x,y,x+cw,y+ch)).resize((size,size),Image.Resampling.NEAREST)
            image = image.rotate(pose, resample=Image.Resampling.NEAREST, expand=True)
            self.photos[key] = ImageTk.PhotoImage(image, master=self.root)
        return self.photos.get(key)

    def animate(self):
        self.job = None
        if self.window is None or self.closed:
            return
        elapsed = time.monotonic()-self.started
        if elapsed >= DURATION:
            self.dismiss(); return
        c, p = self.canvas, ui.P
        width, height = c.winfo_width(), c.winfo_height()
        if width < 10:
            self.job = self.root.after(30, self.animate); return
        c.delete("all"); c.configure(background=p["surface"])
        for row in range(32):
            c.create_rectangle(0,height*row/32,width,height*(row+1)/32+1,outline="",fill=blend(p["header_background"],p["surface"],row/31))
        c.create_rectangle(8,8,width-9,height-9,outline=p["copper"],width=2)
        scale = min(width/980,height/650)
        mechanics = self.event.get("animation") == "mechanics_duck"
        technology = self.event.get("animation") == "technology_duck"
        done_at = 6 if mechanics or technology else 0
        finished = elapsed >= done_at
        if mechanics:
            step = mechanics_sound_step(elapsed)
            if step > self.mechanics_sound_step:
                self.audio.play("milestone_strain_a" if step % 2 == 0 else "milestone_strain_b")
                self.mechanics_sound_step = step
            if finished and not self.mechanics_seated:
                self.audio.play("milestone_bolt_seated"); self.mechanics_seated = True
        if technology:
            step = technology_sound_step(elapsed)
            if step > self.technology_sound_step:
                self.audio.play(TECHNOLOGY_SOUNDS[step][1]); self.technology_sound_step = step
            if technology_frame(elapsed) == 6:
                blink = int((elapsed-5.82)/2.7)
                if blink > self.last_technology_blink:
                    self.audio.play("milestone_technology_blink"); self.last_technology_blink = blink
        if finished and not self.music_started:
            self.audio.play("milestone_celebration"); self.music_started = True
        heading = "CELEBRATION TIME!" if finished else "WHAT COULD GO WRONG?" if technology else "ONE... MORE... TURN!"
        c.create_text(width/2,height*.09,text=heading,fill=p["header_foreground"],font=("Segoe UI",max(16,int(33*scale)),"bold"))
        c.create_text(width/2,height*.20,text=self.event["name"],width=width*.87,justify="center",fill=p["foreground"],font=("Segoe UI",max(12,int(24*scale)),"bold"))
        hat = int(elapsed/4) % 6
        phase = elapsed % 4
        bounce = abs(math.sin(elapsed*math.pi*2))*10*scale
        pose = round(math.sin(elapsed*math.pi)*3)
        size = max(120,int(290*scale))
        if mechanics:
            size = max(140,int(330*scale))
            hat = mechanics_frame(elapsed)
            pose = 0
            bounce = 0  # The workbench stays planted while the duck works.
        if technology:
            size = max(140,int(330*scale))
            hat = technology_frame(elapsed)
            pose = 0
            bounce = 0  # Hold the soot-covered pose steady; only the eyes keep blinking.
        photo = self.duck(hat,size,pose) if self.event.get("animation") in ("culture_duck", "mechanics_duck", "technology_duck") else None
        if photo:
            c.create_image(width/2,height*.49-bounce,image=photo)
        else:
            c.create_text(width/2,height*.49,text="🏆",font=("Segoe UI",max(30,int(100*scale))),fill=p["copper"])
        if phase < .55 and not mechanics and not technology:
            for n in range(12):
                angle=n*math.tau/12;radius=(30+phase*100)*scale
                x=width/2+math.cos(angle)*radius;y=height*.38+math.sin(angle)*radius*.55
                c.create_oval(x-3,y-3,x+3,y+3,fill=blend(p["copper"],p["surface"],phase/.55),outline="")
        names = self.event.get("thanks", [])
        thanks_at = 8 if mechanics or technology else 0
        thanks_time = max(0,elapsed-thanks_at)
        slot = min(3.2,(DURATION-thanks_at)/max(1,len(names)))
        cycle = thanks_time % slot
        edge = min(.35,slot*.2)
        fade = min(1,cycle/edge,(slot-cycle)/edge)
        color = blend(p["surface"],p["foreground"],max(.35,fade))
        c.create_text(width/2,height*.76,text=("SPECIAL THANKS" if names else "THANK YOU, TEAM!") if finished else "EXPERIMENTAL TECHNOLOGY" if technology else "PUTTING IN THE HARD WORK",fill=p["copper"],font=("Segoe UI",max(10,int(16*scale)),"bold"))
        name = names[int(thanks_time/slot)%len(names)] if names else "Everyone who made this milestone possible"
        if not finished:
            name = "Is this the sight?" if technology else "Nearly there..."
        c.create_text(width/2,height*.84,text=name,width=width*.85,fill=color,font=("Segoe UI",max(12,int(28*scale)),"bold"))
        if names:
            c.create_text(width/2,height*.94,text=" · ".join(names),width=width*.88,justify="center",fill=p["muted"],font=("Segoe UI",max(9,int(12*scale))))
        for x0,y0,speed,angle,color in self.confetti if finished else ():
            x=(x0*width+math.sin(elapsed*1.5+angle)*22)%width
            y=((y0+elapsed*speed)*height)%(height+30)-15
            angle+=elapsed*2
            dx,dy=math.cos(angle)*4*scale,math.sin(angle)*4*scale
            c.create_polygon(x-dx,y-dy,x+dy/2,y-dx/2,x+dx,y+dy,x-dy/2,y+dx/2,fill=color,outline="")
        self.window.attributes("-alpha",min(1,elapsed/.4,(DURATION-elapsed)/.5))
        self.job = self.root.after(33,self.animate)

    def dismiss(self):
        if self.window is None:
            return
        if self.job is not None:
            self.root.after_cancel(self.job); self.job = None
        self.audio.stop()
        self.window.grab_release(); self.window.destroy(); self.window = None
        self.photos.clear()
        if self.resume:
            player, path = self.resume
            if player.path == path and player.paused:
                player.pause()
            self.resume = None
        if self.is_preview:
            callback = self.event.get("_on_close")
            if callback: callback()
        if not self.is_preview:
            key = self.event["id"]; player = self.player
            self.queued.discard((player,key))
            local = self.app.config.setdefault("milestone_seen", {}).setdefault(player, [])
            if key not in local:
                local.append(key); self.app.save_config()
            todo = self.app.todo_page()
            todo.data.setdefault(SEEN, {}).setdefault(player, {})[key] = datetime.now(timezone.utc).isoformat()
            todo.save(undoable=False,feedback=False)
        if self.pending and self.job is None:
            self.job = self.root.after(400,self.show_next)

    def close(self):
        # Interrupted by shutdown: leave it unseen so the developer gets it next time.
        self.closed = True
        if self.job is not None:
            self.root.after_cancel(self.job); self.job = None
        self.audio.stop()
        if self.window is not None:
            self.window.destroy(); self.window = None
        self.pending.clear(); self.photos.clear()


# HASHED OUT 2026-10-25 at Mike's request: the Celebration tester is removed (see AGENTS.md); don't bring it back unasked.
# TEST_SCENES / test_animation / tester_menu stay for the tests, but nothing in the app uses them any more.
TEST_SCENES = (("Culture Map", "culture_duck"), ("Mechanics", "mechanics_duck"), ("Technology", "technology_duck"))


def test_animation(app, title, animation):
    """Local preview only: no milestone, receipt or shared completion is created."""
    player = app.todo_page().me.get()
    app.milestone_celebrations.preview(title + " Completion", [player] if player else [], animation=animation)


def tester_menu(app, parent):
    menu = tk.Menu(parent, tearoff=0)
    for title, animation in TEST_SCENES:
        menu.add_command(label=title, command=lambda t=title,a=animation: test_animation(app,t,a))
    return menu


def complete_dialog(todo, name=None):
    """Explicit completion, optional individual thanks and a local-only preview."""
    from tkinter import messagebox
    names = [m["name"] for m in todo.data.get("milestones", [])]
    if not names:
        messagebox.showinfo("Milestones", "Add a milestone first from the Milestones section.", parent=todo.winfo_toplevel())
        return
    w = tk.Toplevel(todo); w.title("Complete a milestone")
    w.transient(todo.winfo_toplevel()); w.grab_set()
    f = ttk.Frame(w, padding=16); f.pack(fill="both", expand=True)
    f.columnconfigure(0, weight=1)
    ttk.Label(f, text="A milestone worth celebrating", font="om_head").grid(row=0,column=0,columnspan=3,sticky="w")
    chosen = tk.StringVar(value=name if name in names else names[0])
    combo = ttk.Combobox(f,textvariable=chosen,values=names,state="readonly",width=48)
    combo.grid(row=1,column=0,columnspan=3,sticky="ew",pady=(12,8))
    styles = {"Automatic": None, "Culture map duck": "culture_duck", "Mechanics duck": "mechanics_duck", "Technology duck": "technology_duck", "Confetti celebration": "celebration"}
    animation_choice = tk.StringVar(value="Automatic")
    style_row = ttk.Frame(f); style_row.grid(row=2,column=0,columnspan=3,sticky="ew",pady=(0,8))
    ttk.Label(style_row,text="Animation").pack(side="left",padx=(0,8))
    ttk.Combobox(style_row,textvariable=animation_choice,values=list(styles),state="readonly",width=24).pack(side="left",fill="x",expand=True)
    ttk.Label(f,text="The whole team gets the celebration through Live Sync. Offline developers see it on their next launch.",wraplength=520).grid(row=3,column=0,columnspan=3,sticky="w")
    ttk.Label(f,text="Special thanks (choose any developers)",font="om_bold").grid(row=4,column=0,columnspan=3,sticky="w",pady=(16,6))
    thanks = tk.Listbox(f,selectmode="multiple",exportselection=False,height=8)
    thanks.grid(row=5,column=0,columnspan=2,sticky="nsew")
    scrollbar=ttk.Scrollbar(f,orient="vertical",command=thanks.yview);scrollbar.grid(row=5,column=2,sticky="ns")
    thanks.configure(yscrollcommand=scrollbar.set)
    developers=todo.dev_names()
    for dev in developers:thanks.insert("end",dev)
    ttk.Label(f,text="Completing this milestone keeps its individual tasks as they are.",wraplength=520).grid(row=6,column=0,columnspan=3,sticky="w",pady=(10,12))
    bar=ttk.Frame(f);bar.grid(row=7,column=0,columnspan=3,sticky="ew")
    for col in range(3):bar.columnconfigure(col,weight=1,uniform="actions")
    def picked():return [developers[i] for i in thanks.curselection()]
    def finish():
        milestone=todo.milestone(chosen.get())
        if milestone is None:return
        event=publish(todo.data,chosen.get(),todo.me.get(),picked(),animation=styles[animation_choice.get()])
        if event is None:
            messagebox.showinfo("Milestone", "This milestone has already been completed and announced.", parent=w)
            return
        w.destroy()
        todo.save(undoable=False,feedback=False)
        todo.fill_milestones()
        todo.show_milestone(chosen.get())
    def preview():
        selected=picked();title=chosen.get()
        w.grab_release();w.withdraw()
        manager=todo.app.milestone_celebrations
        manager.preview(title,selected,animation=styles[animation_choice.get()])
        manager.pending[0][1]["_on_close"] = lambda: (w.deiconify(),w.grab_set()) if w.winfo_exists() else None
    ttk.Button(bar,text="Preview animation",command=preview).grid(row=0,column=0,sticky="ew",padx=(0,4))
    ttk.Button(bar,text="Complete & celebrate",command=finish).grid(row=0,column=1,sticky="ew",padx=4)
    ttk.Button(bar,text="Cancel",command=w.destroy).grid(row=0,column=2,sticky="ew",padx=(4,0))
