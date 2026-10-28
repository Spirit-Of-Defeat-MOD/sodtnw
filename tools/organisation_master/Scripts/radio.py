"""Compact, read-only station playback for Organisation Master's sidebar."""
import os
from pathlib import Path
from PIL import Image, ImageTk
import random
import re
import threading
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

import music_master as music
import ui
import paths  # (Scripts/paths.py: where the tool's files are)


@dataclass(frozen=True)
class Track:
    name: str
    path: str
    volume: float = 1.0

    def matches(self, words):
        text = self.name + " " + os.path.basename(self.path)
        return bool(re.search(r"\b(?:" + words + r")\b", text.replace("_", " "), re.I))

    @property
    def ad(self):
        return self.matches("ad|ads|advert|adverts|advertisement|advertisements|advertising|commercial|commercials")

    @property
    def jingle(self):
        return self.matches("jingle|jingles")


def stations_in(mod_dir):
    """Read installed RR stations only; no edits, downloads or live-sync side effects."""
    stations, errors = {}, []
    for root in music.find_music_mods(mod_dir):
        descriptor = music.read_text(os.path.join(root, "descriptor.mod"))
        match = re.search(r'^\s*name\s*=\s*"([^" ](?:[^"\n]*))"', descriptor, re.M)
        name = match.group(1) if match else ""
        if not music.is_rr_music(root, name):
            continue
        try:
            mod = music.MusicMod(root)
            for station in mod.stations.values():
                tracks, missing = [], 0
                for song_name, _chance, _entry in station.songs:
                    song = mod.songs.get(song_name)
                    path = mod.song_path(song)
                    if not path or not os.path.isfile(path):
                        missing += 1
                        continue
                    try:
                        volume = float(song.volume) if song.volume is not None else music.DEFAULT_VOLUME
                    except (TypeError, ValueError):
                        volume = music.DEFAULT_VOLUME
                    tracks.append(Track(song_name, path, volume))
                key = os.path.normcase(os.path.abspath(root)) + "|" + station.token
                short = re.sub(r"^revolution reali[sz]ed music\s*[:\-]\s*", "", mod.name, flags=re.I)
                title = re.sub(r"§.", "", station.title or station.token)
                stations[key] = (f"{title} · {short}", tracks, missing)
        except Exception as ex:
            errors.append(f"{os.path.basename(root)}: {ex}")
    return stations, errors


class Playback:
    """Bounded queue playback; a broken track cannot cause an endless retry loop."""
    def __init__(self, player=None):
        self.player = player or music.Player()
        self.tracks, self.queue = [], []
        self.index = -1
        self.active = False
        self.volume = 0.5
        self.shuffle = self.no_ads = self.skip_jingles = self.repeat = False
        self.message = "Choose a station"
        self.durations = {}

    @property
    def current(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else None

    def load(self, tracks):
        self.stop()
        self.tracks = list(tracks)
        self.rebuild()

    def rebuild(self):
        current = self.current if self.active else None
        upcoming = self.queue[self.index + 1:] if current is not None else []
        paused = self.player.paused
        self.queue = [t for t in self.tracks if not (self.no_ads and t.ad) and not (self.skip_jingles and t.jingle)]
        if self.shuffle:
            random.shuffle(self.queue)
        if current in self.queue and self.shuffle:
            self.queue.remove(current)
            self.queue.insert(0, current)
        self.index = self.queue.index(current) if current in self.queue else -1
        if current is not None and self.index < 0:
            self.player.stop()
            self.active = False
            following = next((track for track in upcoming if track in self.queue), None)
            self._play(self.queue.index(following) if following is not None else len(self.queue))
            if paused and self.active:
                self.player.pause()
        elif not self.active:
            self.message = f"Ready · {len(self.queue)} tracks" if self.queue else "No tracks match these options"

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))
        if self.active and self.current and self.player.mixer:
            self.player.mixer.music.set_volume(max(0.0, min(1.0, self.current.volume * self.volume)))

    def _play(self, index, direction=1):
        for _ in range(len(self.queue)):
            if not 0 <= index < len(self.queue):
                if not self.repeat:
                    break
                index %= len(self.queue)
            track = self.queue[index]
            try:
                if not os.path.isfile(track.path):
                    raise OSError("Track file missing")
                if track.path not in self.durations:
                    self.durations[track.path] = music.ogg_info(track.path)[0] or 0
                self.player.play(track.path, max(0.0, min(1.0, track.volume * self.volume)), length=self.durations[track.path])
                self.index, self.active = index, True
                self.message = track.name
                return
            except Exception:
                index += direction
        self.player.stop()
        self.index, self.active = len(self.queue), False
        self.message = "Station finished" if self.queue and not self.repeat and index >= len(self.queue) else "No playable tracks"

    def play_pause(self):
        if self.active:
            self.player.pause()
        else:
            self._play(max(0, self.index) if self.index < len(self.queue) else 0)

    def next(self):
        self._play(self.index + 1 if self.index < len(self.queue) else 0)

    def previous(self):
        index = self.index if self.active and self.player.position() > 3 else self.index - 1
        self._play(max(0, min(len(self.queue) - 1, index)))

    def stop(self):
        self.player.stop()
        self.index, self.active = -1, False
        self.message = "Stopped"

    def tick(self):
        if self.active and not self.player.path:
            self.active = False
            self.message = "Stopped for Music Master preview"
        elif self.active and self.player.finished():
            self.next()


class Radio(ttk.LabelFrame):
    def __init__(self, parent, app, owner=None):
        super().__init__(parent, text="♫ Radio", padding=6)
        self.app = app
        self.owner = owner or self
        self._popup = self._popup_view = self._placeholder = None
        self._job = None
        self.playback = owner.playback if owner is not None else Playback()
        self.stations, self.keys = (owner.stations, owner.keys) if owner is not None else ({}, [])
        self._closed = False
        self._scan = None
        self._result = None
        self.options = owner.options if owner is not None else {key: tk.BooleanVar(value=bool(app.config.get("radio_" + key, False)))
                        for key in ("shuffle", "no_ads", "skip_jingles", "repeat")}
        self.station = owner.station if owner is not None else tk.StringVar()
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.combo = ttk.Combobox(top, textvariable=self.station, state="readonly", width=1)
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", self.choose)
        self.combo.configure(values=[self.stations[key][0] for key in self.keys])
        menu = tk.Menu(self, tearoff=0)
        menu.add_checkbutton(label="Repeat station", variable=self.options["repeat"], command=self.settings)
        menu.add_checkbutton(label="Skip jingles", variable=self.options["skip_jingles"], command=self.settings)
        menu.add_separator()
        menu.add_command(label="Reload stations", command=self.scan)
        menu.add_separator()
        menu.add_command(label="Pop out radio", command=self.toggle_popout)
        menu.configure(postcommand=lambda: menu.entryconfigure(menu.index("end"), label=self.popout_label()))
        self.menu = menu
        ttk.Menubutton(top, text="⋯", menu=menu, width=2).pack(side="right", padx=(3, 0))
        now_area = self.now_area = ttk.Frame(self, height=ui.px(42))
        now_area.pack(fill="x", pady=(5, 2))
        now_area.pack_propagate(False)
        self.now = ttk.Label(now_area, text="Loading stations…", wraplength=ui.px(195), font="om_tiny")
        self.now.pack(fill="both", expand=True)
        self.cassette_canvas=tk.Canvas(now_area,highlightthickness=0,borderwidth=0,background='#251634')
        self.cassette_canvas._om_bar=True
        self.cassette_canvas.bind('<Configure>',lambda event:self.draw_cassette())
        self.cassette_button=ttk.Button(self,text='▶  Sunset • B side',style='Small.TButton',command=self.cassette_sunset)
        self._cassette_source=None;self._cassette_photo=None
        self._cassette_size=None
        self._cassette_fit_job=None
        self.bind('<Configure>',self.schedule_cassette_fit,add='+')
        controls = ttk.Frame(self)
        controls.pack(fill="x")
        self.buttons = []
        for col, (label, command) in enumerate((("◀", self.playback.previous), ("▶", self.playback.play_pause),
                                                ("■", self.playback.stop), ("▶|", self.playback.next))):
            controls.columnconfigure(col, weight=1, uniform="radio")
            button = ttk.Button(controls, text=label, width=3, style="Small.TButton", command=lambda c=command: self.action(c))
            button.grid(row=0, column=col, sticky="ew", padx=1)
            self.buttons.append(button)
        options = ttk.Frame(self)
        options.pack(fill="x", pady=3)
        ttk.Checkbutton(options, text="Shuffle", variable=self.options["shuffle"], command=self.settings).pack(side="left")
        ttk.Checkbutton(options, text="No ads", variable=self.options["no_ads"], command=self.settings).pack(side="right")
        volume = ttk.Frame(self)
        volume.pack(fill="x")
        ttk.Label(volume, text="Vol", font="om_tiny").pack(side="left", padx=(0, 5))
        try:
            initial = max(0, min(1, float(app.config.get("radio_volume", 0.5))))
        except (TypeError, ValueError):
            initial = 0.5
        self.volume = owner.volume if owner is not None else tk.DoubleVar(value=initial)
        self.playback.volume = initial
        slider = ttk.Scale(volume, variable=self.volume, from_=0, to=1, command=self.volume_changed)
        slider.pack(side="left", fill="x", expand=True)
        self.info = ttk.Label(self, text="", style="Muted.TLabel", font="om_tiny")
        self.info.pack(fill="x", pady=(3, 0))
        self.bind("<Destroy>", self.destroyed, add="+")
        self.now.bind("<Configure>", lambda event: self.now.configure(wraplength=max(ui.px(100), event.width)))
        self.context = tk.Menu(self, tearoff=0)
        self.context.add_command(label="Pop out radio", command=self.toggle_popout)
        self.bind_context(self)
        if owner is None:
            self.after(500, self.scan)
            self._job = self.after(250, self.tick)
        else:
            self.render()
        ui.theme_all(self)
        ui.THEME_HOOKS.append(self.theme_radio)
        self.theme_radio()

    def cassette_sunset(self):
        secrets=getattr(self.app,'theme_secrets',None)
        if secrets:secrets.activate('egg_vapor','vapor')

    def theme_radio(self):
        vapor=ui.THEME['t'].get('name')=='Vaporwave'
        style=ttk.Style(self)
        style.configure('Cassette.TLabelframe',background='#251634',bordercolor='#b46fda',borderwidth=2,relief='ridge')
        style.configure('Cassette.TLabelframe.Label',background='#251634',foreground='#8ff5ec')
        style.configure('Cassette.TFrame',background='#251634')
        style.configure('Cassette.TLabel',background='#251634',foreground='#f3c2f1')
        style.configure('Cassette.Display.TLabel',background='#c9afdc',foreground='#28143c')
        style.layout('Cassette.Small.TButton',ui._imgs.get('TButton.layout0',style.layout('TButton')))
        style.configure('Cassette.Small.TButton',background='#472451',foreground='#8ff5ec',padding=(2,1),font='om_tiny')
        self.cassette_button.configure(style='Cassette.Small.TButton')
        self.configure(text='▣  CASSETTE // RADIO' if vapor else '♫ Radio',style='Cassette.TLabelframe' if vapor else 'TLabelframe')
        for widget in self.winfo_children():
            if isinstance(widget,ttk.Frame):widget.configure(style='Cassette.TFrame' if vapor else 'TFrame')
        for button in self.buttons:button.configure(style='Cassette.Small.TButton' if vapor else 'Small.TButton')
        self.info.configure(style='Cassette.TLabel' if vapor else 'Muted.TLabel')
        self.now_area.configure(height=ui.px(92 if vapor else 42))
        self.now.pack_forget();self.now.place_forget()
        if vapor:
            self.cassette_canvas.place(x=0,y=0,relwidth=1,relheight=1)
            self.now.configure(style='Cassette.Display.TLabel',anchor='center',justify='center')
            self.now.place(relx=.5,rely=.22,anchor='center',relwidth=.65,height=ui.px(22))
            self.cassette_button.pack(fill='x',pady=(5,0))
            self.draw_cassette()
            self.schedule_cassette_fit()
        else:
            self.cassette_canvas.place_forget();self.cassette_button.pack_forget()
            self.now.configure(style='TLabel',anchor='w',justify='left');self.now.pack(fill='both',expand=True)
        if hasattr(self.app,'_logo_job'):self.app.schedule_logo()

    def schedule_cassette_fit(self,event=None):
        if event is not None and event.widget is not self:return
        if self._cassette_fit_job is not None:self.after_cancel(self._cassette_fit_job)
        self._cassette_fit_job=self.after(60,self.fit_cassette)

    def fit_cassette(self):
        self._cassette_fit_job=None
        if self._closed or ui.THEME['t'].get('name')!='Vaporwave':return
        other=self.winfo_reqheight()-self.now_area.winfo_reqheight()
        def vertical_padding(value):
            parts=value if isinstance(value,(tuple,list)) else self.tk.splitlist(str(value))
            values=[self.winfo_pixels(p) for p in parts]
            if not values:return 0
            if len(values)==1:return values[0]*2
            if len(values)==4:return values[1]+values[3]
            return sum(values)
        available=self.master.winfo_height()-vertical_padding(self.master.cget('padding'))
        for child in self.master.pack_slaves():
            if child is self or child is getattr(self.app,'logo_label',None):continue
            available-=child.winfo_reqheight()+vertical_padding(child.pack_info().get('pady',0))
        available-=vertical_padding(self.pack_info().get('pady',0)) if self.winfo_manager()=='pack' else 0
        height=max(ui.px(28),min(ui.px(92),available-other-2))
        if height!=self.now_area.winfo_reqheight():self.now_area.configure(height=height)

    def draw_cassette(self):
        if ui.THEME['t'].get('name')!='Vaporwave':return
        path=Path(self.app.tool_dir,'secret_assets','cassette.png')
        if not path.is_file():path=Path(paths.BUNDLE)/'secret_assets'/'cassette.png'
        if self._cassette_source is None and path.is_file():
            with Image.open(path) as source:
                im=source.convert('RGBA');self._cassette_source=im.crop(im.getbbox())
        w=max(2,self.now_area.winfo_width());h=max(2,self.now_area.winfo_height())
        if self._cassette_source is not None and self._cassette_size!=(w,h):
            im=self._cassette_source.copy();im.thumbnail((w,h),Image.Resampling.LANCZOS)
            self._cassette_photo=ImageTk.PhotoImage(im,master=self);self._cassette_size=(w,h)
        self.cassette_canvas.delete('all')
        if self._cassette_photo:self.cassette_canvas.create_image(w/2,h/2,image=self._cassette_photo)
        if self._cassette_photo:self.now.place_configure(width=max(40,round(self._cassette_photo.width()*.7)),relwidth=0)
        self.now.tk.call('raise',str(self.now))

    def popout_label(self):
        return "Dock radio in sidebar" if self.owner._popup is not None else "Pop out radio"

    def bind_context(self, widget):
        widget.bind("<Button-3>", self.context_menu, add="+")
        for child in widget.winfo_children():
            if not isinstance(child, tk.Menu):
                self.bind_context(child)

    def context_menu(self, event):
        self.context.entryconfigure(0, label=self.popout_label())
        try:
            self.context.tk_popup(event.x_root, event.y_root)
        finally:
            self.context.grab_release()
        return "break"

    def toggle_popout(self):
        owner = self.owner
        if owner._popup is None:
            owner.popout()
        else:
            owner.dock()

    def popout(self):
        if self.owner is not self:
            return self.owner.popout()
        if self._popup is not None:
            self._popup.deiconify()
            self._popup.lift()
            return
        self._dock_pack = self.pack_info()
        popup = self._popup = tk.Toplevel(self.winfo_toplevel())
        popup._om_nonmodal = True  # Utility window: it must not pause live To Do sync.
        popup.title("Radio — Organisation Master")
        popup.geometry(self.app.config.get("radio_popout_geometry", f"{ui.px(360)}x{ui.px(260)}"))
        popup.minsize(ui.px(280), ui.px(230))
        popup.protocol("WM_DELETE_WINDOW", self.dock)
        self._popup_view = Radio(popup, self.app, owner=self)
        self._popup_view.pack(fill="both", expand=True, padx=8, pady=8)
        if self._placeholder is None:
            self._placeholder = ttk.Button(self.master, text="♫ Radio · Dock", command=self.dock, style="Small.TButton")
            self._placeholder.bind("<Button-3>", self.context_menu)
        self._placeholder.pack(before=self, **self._dock_pack)
        self.pack_forget()
        ui.theme_all(popup)

    def dock(self):
        if self.owner is not self:
            return self.owner.dock()
        if self._popup is None:
            return
        popup = self._popup
        if popup.winfo_exists():
            self.app.config["radio_popout_geometry"] = popup.geometry()
        self._popup = self._popup_view = None
        self.pack(before=self._placeholder, **self._dock_pack)
        self._placeholder.pack_forget()
        if popup.winfo_exists():
            popup.destroy()
        self.app.save_config()
        self.render()

    def settings(self):
        for key, var in self.options.items():
            setattr(self.playback, key, var.get())
            self.app.config["radio_" + key] = var.get()
        self.playback.rebuild()
        self.app.save_config()
        self.render()

    def volume_changed(self, _value=None):
        self.playback.set_volume(self.volume.get())
        self.app.config["radio_volume"] = self.volume.get()

    def scan(self):
        if self.owner is not self:
            return self.owner.scan()
        if self._closed:
            return
        if self._scan and self._scan.is_alive():
            return
        self.info.configure(text="Loading stations…")
        def work():
            try:
                self._result = stations_in(self.app.mod_dir)
            except Exception as ex:
                self._result = ({}, [str(ex)])
        self._scan = threading.Thread(target=work, daemon=True)
        self._scan.start()

    def choose(self, _event=None):
        index = self.combo.current()
        if not 0 <= index < len(self.keys):
            return
        key = self.keys[index]
        self.app.config["radio_station"] = key
        self.app.save_config()
        for option, var in self.options.items():
            setattr(self.playback, option, var.get())
        self.playback.load(self.stations[key][1])
        self.render()

    def action(self, command):
        command()
        self.render()

    def render(self):
        if self.owner is not self and self.keys is not self.owner.keys:
            self.stations, self.keys = self.owner.stations, self.owner.keys
            self.combo.configure(values=[self.stations[key][0] for key in self.keys])
        engine = self.playback
        self.now.configure(text=engine.message)
        self.buttons[1].configure(text="▶" if not engine.active or engine.player.paused else "Ⅱ")
        for button in self.buttons:
            button.state(["!disabled"] if engine.queue else ["disabled"])
        if engine.active:
            self.info.configure(text=f"{engine.index + 1}/{len(engine.queue)} · {music.mmss(engine.player.position())} / {music.mmss(engine.player.length)}")
        else:
            missing = self.stations.get(self.app.config.get("radio_station"), (None, [], 0))[2]
            self.info.configure(text=f"{len(engine.queue)} tracks" + (f" · {missing} missing" if missing else ""))
        if self.owner is self and self._popup_view is not None:
            self._popup_view.render()

    def tick(self):
        if self._closed:
            return
        if self._result is not None:
            self.stations, errors = self._result
            self._result = None
            self.keys = sorted(self.stations, key=lambda key: (self.stations[key][0].casefold(), key))
            self.combo.configure(values=[self.stations[key][0] for key in self.keys])
            self.app.config["radio_scan_errors"] = errors
            if self.keys:
                pick = self.app.config.get("radio_station")
                self.combo.current(self.keys.index(pick) if pick in self.keys else 0)
                self.choose()
            else:
                self.playback.load([])
                self.playback.message = "No RR stations found · use ⋯ to reload"
        self.playback.tick()
        self.render()
        self._job = self.after(250, self.tick)

    def close(self):
        self._closed = True
        if self.owner is self:
            if self._popup is not None:
                popup = self._popup
                self._popup = self._popup_view = None
                popup.destroy()
            self.playback.stop()
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    def destroyed(self, event):
        if event.widget is self:
            if self._cassette_fit_job is not None:self.after_cancel(self._cassette_fit_job)
            if self.theme_radio in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.theme_radio)
            self.close()
            if self.owner is not self and self.owner._popup_view is self and not self.owner._closed:
                self.owner.after_idle(self.owner.dock)
