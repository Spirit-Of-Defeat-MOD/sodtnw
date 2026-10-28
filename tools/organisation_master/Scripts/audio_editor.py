"""Music Master's download queue and small, non-destructive track editor."""
import copy
from pathlib import Path
import queue
import re
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import uuid

import ui
from audio_recovery import RecoverySession, recoverable, find_download
from audio_processing import (AudioJob, Cancelled, convert_audio, download_audio,
    edit_settings, install_tools, parse_time, probe_audio, tool_paths, waveform, EQ_FREQUENCIES)


def time_text(seconds):
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{seconds:06.3f}"


class AudioEditor(tk.Toplevel):
    def __init__(self, music, tracks=(), replacement=None, target_hint=None):
        super().__init__(music)
        from music_master import Player, TOOL_DIR
        self.music = music
        self.replacement = replacement
        self._om_nonmodal = True
        self.title("Music Master — Download / edit audio")
        height = min(ui.px(790), self.winfo_screenheight() - 90)
        width = min(ui.px(1110), self.winfo_screenwidth() - 70)
        self.geometry(f"{width}x{height}")
        self.minsize(min(ui.px(850), width), min(ui.px(650), height))
        self.transient(music.winfo_toplevel())
        self.tools_folder = Path(TOOL_DIR) / "audio_tools"
        self.tools = tool_paths(self.tools_folder)
        self.recovery_root = Path(TOOL_DIR) / "audio_recovery"
        self.recovery = self.temp = RecoverySession(self.recovery_root)
        self.workspace = self.recovery.path
        self.autosave_job = self.startup_job = None
        self.player = Player()
        self.playback_track = None
        self.preview_start = self.preview_end = 0
        self.items = {}
        self.current = None
        self.job = self.worker = None
        self.events = queue.Queue()
        self.busy = self.closing = self.destroyed = False
        self.poll_job = None
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self.on_destroy, add="+")
        music._audio_editors = getattr(music, "_audio_editors", set())
        music._audio_editors.add(self)
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        header = ttk.Frame(body)
        header.pack(fill="x")
        ttk.Label(header, text="Track workshop", style="Title.TLabel").pack(side="left")
        self.setup_button = ttk.Button(header, text="Set up / update audio tools", command=self.setup)
        self.setup_button.pack(side="right")
        self.recover_button = ttk.Button(header, text="Recover session…", command=self.offer_recovery)
        self.recover_button.pack(side="right", padx=6)
        ttk.Label(body, text="Download YouTube links, keep the section you want, adjust levels and export Ogg Vorbis.",
            style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        target = ttk.Frame(body)
        target.pack(fill="x", pady=(0, 10))
        self.targets = {}
        for mod in music._loaded.values():
            for station in mod.stations.values():
                label = f"{music.short_name(mod)} / {station.title or station.token}"
                if label in self.targets:
                    label += " (" + station.token + ")"
                self.targets[label] = (mod, station.token)
        initial = next((label for label, (mod, token) in self.targets.items()
            if mod is music.mod and music.station and token == music.station.token), "")
        if target_hint is not None:
            initial = next((label for label, (mod, token) in self.targets.items()
                if Path(mod.root).name == target_hint[0] and token == target_hint[1]), "")
        ttk.Label(target, text="Add to station:").pack(side="left")
        self.target = tk.StringVar(value=initial)
        self.target_box = ttk.Combobox(target, textvariable=self.target, values=list(self.targets), state="readonly", width=55)
        self.target_box.pack(side="left", padx=8, fill="x", expand=True)
        if replacement:
            self.target_box.state(["disabled"])
            ttk.Label(target, text="Replaces audio on Save to mod; game name stays the same", style="Muted.TLabel").pack(side="right")
        pane = self.pane = ttk.PanedWindow(body, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left = ttk.Frame(pane, width=ui.px(350))
        left.pack_propagate(False)
        right_scroll = self.editor_scroll = ui.ScrollFrame(pane)
        right_scroll.configure(width=ui.px(700))
        right_scroll.pack_propagate(False)
        right = ttk.Frame(right_scroll.inner, padding=(12, 0, 8, 0))
        right.pack(fill="both", expand=True)
        pane.add(left, weight=1); pane.add(right_scroll, weight=3)
        # Position only after the pane has its real width, rather than its initial 1px size.
        self.split_ready = False
        pane.bind("<Configure>", self.ensure_editor_layout)
        pane.bind("<ButtonRelease-1>", self.ensure_editor_layout, add="+")
        self.tree = ttk.Treeview(left, columns=("state",), show="tree headings", height=12, selectmode="extended")
        self.tree.heading("#0", text="Track"); self.tree.heading("state", text="Status")
        self.tree.column("#0", width=ui.px(175), minwidth=90); self.tree.column("state", width=ui.px(110), minwidth=75)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.show_track)
        row = ttk.Frame(left); row.pack(fill="x", pady=(6, 0))
        self.download_button = ttk.Button(row, text="Download selected", command=self.download)
        self.download_button.pack(fill="x")
        self.all_button = ttk.Button(row, text="Download all", command=lambda: self.download(all_tracks=True))
        self.all_button.pack(fill="x", pady=(4, 0))
        self.local_button = ttk.Button(left, text="Open local audio…", command=self.open_local)
        self.local_button.pack(fill="x", pady=(4, 0))
        self.new_button = ttk.Button(left, text="+ YouTube link", command=self.add_link)
        self.new_button.pack(fill="x", pady=(4, 0))
        self.review_button = ttk.Button(left, text="Review selected ▶", command=self.review_selected)
        self.review_button.pack(fill="x", pady=(8, 0))
        self.tree.bind("<Double-1>", lambda event: self.review_selected())
        queue_hint = ttk.Label(left, text="Ctrl / Shift selects several tracks. Download all, then review them in order.",
            style="Muted.TLabel", wraplength=ui.px(265))
        queue_hint.pack(fill="x", pady=(8, 0))
        for control in (queue_hint, self.new_button, self.local_button, row, self.review_button):
            control.pack_configure(side="bottom", before=self.tree)
        navigation = ttk.Frame(right)
        navigation.pack(fill="x", pady=(0, 8))
        self.previous_button = ttk.Button(navigation, text="◀ Previous track", command=lambda: self.select_track(-1))
        self.previous_button.pack(side="left")
        self.track_number = ttk.Label(navigation, text="", anchor="center")
        self.track_number.pack(side="left", fill="x", expand=True, padx=8)
        self.next_button = ttk.Button(navigation, text="Next track ▶", command=lambda: self.select_track(1))
        self.next_button.pack(side="right")
        fields = ttk.Frame(right); fields.pack(fill="x")
        self.variables = {key: tk.StringVar() for key in ("title", "artist", "url", "start", "end", "gain", "fade_in", "fade_out", "volume",
            "bass", "treble", "noise", "noise_reduction", "noise_floor", "noise_type", "noise_track",
            *("eq_" + str(index) for index in range(len(EQ_FREQUENCIES))))}
        self.edit_widgets = [self.previous_button, self.next_button]
        for row_number, (key, label) in enumerate((("title", "Title"), ("artist", "Artist"), ("url", "YouTube link"))):
            ttk.Label(fields, text=label).grid(row=row_number, column=0, sticky="w", pady=3, padx=(0, 8))
            entry = ttk.Entry(fields, textvariable=self.variables[key], width=50)
            entry.grid(row=row_number, column=1, sticky="ew", pady=3)
            self.edit_widgets.append(entry)
        fields.columnconfigure(1, weight=1)
        self.details = ttk.Label(right, text="Pick a track or open a local audio file.", style="Muted.TLabel")
        self.details.pack(anchor="w", pady=8)
        preview = ttk.Frame(right)
        preview.pack(fill="x", pady=(0, 4))
        self.original_button = ttk.Button(preview, text="▶ Play original", width=1, command=self.play_original)
        self.preview_button = ttk.Button(preview, text="▶ Play edit", width=1, command=self.preview_edit)
        self.pause_button = ttk.Button(preview, text="⏸ Pause", width=1, command=self.toggle_pause)
        self.stop_button = ttk.Button(preview, text="■ Stop", width=1, command=self.stop_playback)
        for column, button in enumerate((self.original_button, self.preview_button, self.pause_button, self.stop_button)):
            button.grid(row=0, column=column, sticky="ew", padx=2)
            preview.columnconfigure(column, weight=1, uniform="audio_playback")
        self.playhead = ttk.Label(right, text="Right-click the waveform to play from that position.", style="Muted.TLabel")
        self.playhead.pack(anchor="w", pady=(0, 4))
        self.wave = tk.Canvas(right, height=ui.px(100), background=ui.P["surface"], highlightthickness=1,
            highlightbackground=ui.P["border"])
        self.wave.pack(fill="x", pady=(0, 8))
        self.wave.bind("<Configure>", lambda event: self.draw_wave())
        self.wave.bind("<Button-1>", self.wave_drag)
        self.wave.bind("<B1-Motion>", self.wave_drag)
        self.wave.bind("<Button-3>", self.seek_wave)
        volume_row = ttk.Frame(right)
        volume_row.pack(fill="x", pady=(0, 8))
        ttk.Label(volume_row, text="In-game volume").pack(side="left")
        self.volume_slider = ttk.Scale(volume_row, from_=0, to=1, variable=self.variables["volume"],
            command=lambda value: self.variables["volume"].set(f"{float(value):.2f}"))
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=8)
        volume_entry = ttk.Entry(volume_row, textvariable=self.variables["volume"], width=6)
        volume_entry.pack(side="right")
        self.edit_widgets.extend((self.volume_slider, volume_entry))
        self.drag_edge = None
        trim = ttk.LabelFrame(right, text="Keep this part", padding=8); trim.pack(fill="x")
        for r, (key, label) in enumerate((("start", "Start"), ("end", "End"))):
            ttk.Label(trim, text=label).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
            entry = ttk.Entry(trim, textvariable=self.variables[key], width=14)
            entry.grid(row=r, column=1, sticky="w", pady=3); self.edit_widgets.append(entry)
            button = ttk.Button(trim, text="Use playhead", command=lambda k=key: self.use_playhead(k))
            button.grid(row=r, column=2, padx=6); self.edit_widgets.append(button)
        ttk.Label(trim, text="Seconds, m:ss or h:mm:ss. Drag either edge on the waveform.",
            style="Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.kept_label = ttk.Label(trim, text="", style="Head.TLabel")
        self.kept_label.grid(row=0, column=3, rowspan=2, padx=10)
        levels = ttk.LabelFrame(right, text="Levels and fades", padding=8); levels.pack(fill="x", pady=(8, 0))
        ttk.Label(levels, text="Audio gain (dB)").grid(row=0, column=0, sticky="w")
        gain = ttk.Scale(levels, from_=-24, to=12, variable=self.variables["gain"],
            command=lambda value: self.variables["gain"].set(f"{float(value):.1f}"))
        gain.grid(row=0, column=1, sticky="ew", padx=8); self.edit_widgets.append(gain)
        gain_entry = ttk.Entry(levels, textvariable=self.variables["gain"], width=7)
        gain_entry.grid(row=0, column=2); self.edit_widgets.append(gain_entry)
        for r, (key, label) in enumerate((("fade_in", "Fade in (seconds)"), ("fade_out", "Fade out (seconds)")), 1):
            ttk.Label(levels, text=label).grid(row=r, column=0, sticky="w", pady=3)
            entry = ttk.Entry(levels, textvariable=self.variables[key], width=9)
            entry.grid(row=r, column=1, sticky="w", padx=8); self.edit_widgets.append(entry)
        levels.columnconfigure(1, weight=1)
        ttk.Label(levels, text="Gain changes the audio file. A limiter prevents clipping. In-game volume is separate.",
            style="Muted.TLabel", wraplength=ui.px(430)).grid(row=4, column=0, columnspan=3, sticky="w", pady=(5, 0))
        tone = ttk.LabelFrame(right, text="Bass and treble", padding=8)
        tone.pack(fill="x", pady=(8, 0))
        for row_number, key in enumerate(("bass", "treble")):
            ttk.Label(tone, text=key.title() + " (dB)").grid(row=row_number, column=0, sticky="w", pady=3)
            slider = ttk.Scale(tone, from_=-12, to=12, variable=self.variables[key],
                command=lambda value, name=key: self.variables[name].set(f"{float(value):.1f}"))
            slider.grid(row=row_number, column=1, sticky="ew", padx=8)
            entry = ttk.Entry(tone, textvariable=self.variables[key], width=6)
            entry.grid(row=row_number, column=2)
            self.edit_widgets.extend((slider, entry))
        tone.columnconfigure(1, weight=1)
        equalizer = ttk.LabelFrame(right, text="Graphic EQ · ±12 dB", padding=8)
        equalizer.pack(fill="x", pady=(8, 0))
        for index, frequency in enumerate(EQ_FREQUENCIES):
            key = "eq_" + str(index)
            text = f"{frequency / 1000:g}k" if frequency >= 1000 else f"{frequency:g}"
            ttk.Label(equalizer, text=text, font="om_small").grid(row=0, column=index)
            slider = ttk.Scale(equalizer, orient="vertical", from_=12, to=-12, length=ui.px(100),
                variable=self.variables[key], command=lambda value, name=key: self.variables[name].set(f"{float(value):.1f}"))
            slider.grid(row=1, column=index, pady=4)
            entry = ttk.Entry(equalizer, textvariable=self.variables[key], width=4, font="om_small", justify="center")
            entry.grid(row=2, column=index, sticky="ew", padx=1)
            equalizer.columnconfigure(index, weight=1, uniform="eq")
            self.edit_widgets.extend((slider, entry))
        flat = ttk.Button(equalizer, text="Reset EQ and tone to flat", command=self.flat_eq)
        flat.grid(row=3, column=0, columnspan=len(EQ_FREQUENCIES), sticky="ew", pady=(8, 0))
        self.edit_widgets.append(flat)
        denoise = ttk.LabelFrame(right, text="Noise reducer", padding=8)
        denoise.pack(fill="x", pady=(8, 0))
        enable = ttk.Checkbutton(denoise, text="Enable noise reduction", variable=self.variables["noise"], onvalue="1", offvalue="0")
        enable.grid(row=0, column=0, columnspan=2, sticky="w")
        self.edit_widgets.append(enable)
        for row_number, (key, text, low, high) in enumerate((
                ("noise_reduction", "Reduction strength (dB)", .01, 30), ("noise_floor", "Noise floor (dB)", -80, -20)), 1):
            ttk.Label(denoise, text=text).grid(row=row_number, column=0, sticky="w", pady=3)
            entry = ttk.Spinbox(denoise, from_=low, to=high, textvariable=self.variables[key], width=8)
            entry.grid(row=row_number, column=1, sticky="w", padx=8)
            self.edit_widgets.append(entry)
        ttk.Label(denoise, text="Noise profile").grid(row=3, column=0, sticky="w")
        profile = ttk.Combobox(denoise, values=("white", "vinyl", "shellac"), state="readonly",
            textvariable=self.variables["noise_type"], width=12)
        profile.grid(row=3, column=1, sticky="w", padx=8)
        track = ttk.Checkbutton(denoise, text="Automatically track the noise floor", variable=self.variables["noise_track"], onvalue="1", offvalue="0")
        track.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.edit_widgets.extend((profile, track))
        ttk.Label(denoise, text="Use Preview edit to check the result. Strong reduction can remove musical detail.",
            style="Muted.TLabel", wraplength=ui.px(430)).grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))
        actions = ttk.Frame(body); actions.pack(fill="x", pady=(12, 0))
        self.export_button = ttk.Button(actions, text="Export .ogg…", command=self.export)
        self.export_button.pack(side="left")
        self.import_button = ttk.Button(actions, text="Replace audio" if replacement else "Add selected to station", command=self.add_to_station)
        self.import_button.pack(side="left", padx=6)
        ttk.Button(actions, text="Close", command=self.close).pack(side="right")
        self.cancel_button = ttk.Button(actions, text="Cancel operation", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=6)
        self.progress_bar = ttk.Progressbar(body, mode="indeterminate"); self.progress_bar.pack(fill="x", pady=(8, 4))
        self.message = ttk.Label(body, text="Ready. Audio tools are installed on this PC only.", style="Muted.TLabel", wraplength=ui.px(1000))
        self.message.pack(fill="x")
        # Reserve the footer before the expanding editor, keeping actions reachable on smaller screens.
        for footer in (self.message, self.progress_bar, actions):
            footer.pack_configure(side="bottom", before=pane)
        self.action_buttons = [self.setup_button, self.recover_button, self.download_button, self.all_button, self.local_button,
            self.new_button, self.review_button, self.original_button, self.preview_button, self.pause_button, self.export_button, self.import_button]
        for track in tracks:
            self.insert_track(track)
        if not self.items:
            self.insert_track(dict(title="New track", url=""))
        self.tree.selection_set(next(iter(self.items)))
        for key in ("start", "end"):
            self.variables[key].trace_add("write", lambda *args: self.draw_wave())
        for variable in list(self.variables.values()) + [self.target]:
            variable.trace_add("write", lambda *args: self.schedule_recovery())
        self.variables["volume"].trace_add("write", lambda *args: self.apply_playback_volume())
        ui.theme_all(self)
        ui.title_bar(self)
        ui.THEME_HOOKS.append(self.recolour)
        self.poll_job = self.after(100, self.poll)
        self.save_recovery(capture=False)
        self.startup_job = self.after(150, self.start_session)

    def start_session(self):
        self.startup_job = None
        self.offer_recovery(quiet=True)
        if not self.destroyed and not self.busy:
            self.load_existing()

    def schedule_recovery(self):
        if self.destroyed:
            return
        if self.autosave_job:
            self.after_cancel(self.autosave_job)
        self.autosave_job = self.after(350, self.save_recovery)

    def save_recovery(self, capture=True):
        if self.autosave_job:
            self.after_cancel(self.autosave_job)
            self.autosave_job = None
        if self.destroyed:
            return
        if capture:
            self.store_fields()
        replacement = None
        if self.replacement:
            replacement = [self.replacement[0].root, *self.replacement[1:]]
        try:
            self.recovery.save(dict(items=self.items, selected=self.current, target=self.target.get(), replacement=replacement))
        except OSError as error:
            self.message.config(text="Recovery could not be saved: " + str(error))

    def offer_recovery(self, quiet=False):
        if self.busy or self.destroyed:
            return
        candidates = recoverable(self.recovery_root)
        if not candidates:
            if not quiet:
                self.message.config(text="No interrupted workshop sessions to recover.")
            return
        session, data = candidates[0]
        for other, _ in candidates[1:]:
            other.release()
        try:
            count = len(data["items"])
            restore = messagebox.askyesnocancel("Recover track workshop",
                f"An interrupted workshop contains {count} track(s), downloaded audio and saved edits.\n\n"
                "Yes: restore it.\nNo: discard that interrupted session.\nCancel: keep it for later.\n\n"
                "Any current downloaded work is kept as a separate recovery session.", parent=self)
            if restore is False:
                session.cleanup()
                return
            if restore is None:
                return
            self.player.stop()
            self.save_recovery()
            old_session = self.recovery
            if any(item["source"] for item in self.items.values()):
                old_session.release()
            else:
                old_session.cleanup()
            self.recovery = self.temp = session
            self.workspace = session.path
            self.tree.delete(*self.tree.get_children())
            self.items = {}
            self.current = None
            for ident, saved in data["items"].items():
                if not ident.isalnum() or not isinstance(saved, dict):
                    continue
                self.insert_track(saved, ident=ident)
                item = self.items[ident]
                item.update(saved)
                if not item["source"] or not Path(item["source"]).is_file():
                    item["source"] = find_download(self.workspace / ident)
                    item.update(duration=0, peaks=[])
                item["status"] = "Ready" if item["duration"] else "Needs loading" if item["source"] else "Not downloaded"
                self.tree.item(ident, values=(item["status"],))
                if item.get("original_preview") and not Path(item["original_preview"]).is_file():
                    item.pop("original_preview", None)
            self.replacement = None
            previous = data.get("replacement")
            if previous:
                mod = next((mod for mod in self.music._loaded.values()
                    if Path(mod.root).resolve() == Path(previous[0]).resolve()), None)
                if mod and previous[1] in mod.stations and previous[3] in mod.songs:
                    self.replacement = (mod, *previous[1:])
            self.import_button.config(text="Replace audio" if self.replacement else "Add selected to station")
            self.target_box.config(state="disabled" if self.replacement else "readonly")
            self.target.set(data.get("target", "") if data.get("target") in self.targets else "")
            if self.items:
                selected = data.get("selected")
                self.tree.selection_set(selected if selected in self.items else next(iter(self.items)))
            self.show_track()
            self.ensure_editor_layout(force=True)
            self.save_recovery(capture=False)
            self.message.config(text="Recovered audio, queue and edits. Review before exporting or adding to a station; nothing was written automatically.")
            self.load_existing()
        finally:
            if session is not self.recovery:
                session.release()

    def insert_track(self, track, ident=None):
        ident = ident or uuid.uuid4().hex
        item = dict(title=track.get("title", "New track"), artist=track.get("artist", ""), url=track.get("url", track.get("link", "")),
            # Plan 'source' describes provenance (e.g. 'spreadsheet'), never a local audio file.
            source=track.get("audio_path", ""), duration=0, peaks=[], status="Not downloaded", start=0, end=None,
            gain=0, fade_in=0, fade_out=0, volume=track.get("volume", 0.65))
        item.update(bass=0, treble=0, noise="0", noise_reduction=12, noise_floor=-50, noise_type="white", noise_track="1")
        item.update({"eq_" + str(index): 0 for index in range(len(EQ_FREQUENCIES))})
        self.items[ident] = item
        self.tree.insert("", "end", iid=ident, text=item["title"], values=(item["status"],))
        return ident

    def ensure_editor_layout(self, event=None, force=False):
        if self.destroyed:
            return
        width = self.pane.winfo_width()
        if width < 100:
            return
        minimum = min(ui.px(260), int(width * .30))
        maximum = width - min(ui.px(430), int(width * .55))
        position = self.pane.sashpos(0)
        if force or not self.split_ready or not minimum <= position <= maximum:
            self.pane.sashpos(0, min(ui.px(350), int(width * .35)))
        self.split_ready = True

    def review_selected(self):
        if self.busy:
            return
        if not self.tree.selection():
            ready = next((ident for ident, item in self.items.items() if item["duration"]), None)
            if ready:
                self.tree.selection_set(ready)
        self.ensure_editor_layout(force=True)
        self.show_track()
        self.editor_scroll.canvas.yview_moveto(0)

    def store_fields(self):
        if self.current not in self.items:
            return
        item = self.items[self.current]
        for key in ("title", "artist", "url"):
            item[key] = self.variables[key].get().strip()
        # Incomplete text is kept as text until an operation validates it.
        for key in self.variables.keys() - {"title", "artist", "url"}:
            item[key + "_text"] = self.variables[key].get()
        self.tree.item(self.current, text=item["title"] or "Untitled")

    def show_track(self, event=None):
        self.store_fields()
        selection = self.tree.selection()
        if self.playback_track and (not selection or selection[0] != self.playback_track):
            self.stop_playback()
        self.current = selection[0] if selection else None
        if self.current not in self.items:
            return
        item = self.items[self.current]
        order = list(self.tree.get_children())
        index = order.index(self.current)
        self.track_number.config(text=f"Track {index + 1} of {len(order)}")
        self.previous_button.state(["disabled"] if self.busy or index == 0 else ["!disabled"])
        self.next_button.state(["disabled"] if self.busy or index == len(order) - 1 else ["!disabled"])
        for key in self.variables:
            default = time_text(item[key] or 0) if key in ("start", "end") else str(item.get(key, ""))
            self.variables[key].set(item.get(key + "_text", default))
        self.details.config(text=f"{time_text(item['duration'])}  ·  {Path(item['source']).name}" if item["duration"] else "Download this track or open a local audio file first.")
        self.playhead.config(text=f"{time_text(item.get('playhead', 0))} / {time_text(item['duration'])} · Right-click waveform to seek")
        self.draw_wave()

    def select_track(self, direction):
        if self.busy:
            return
        self.store_fields()
        order = list(self.tree.get_children())
        if not order:
            return
        index = order.index(self.current) if self.current in order else 0
        index = max(0, min(len(order) - 1, index + direction))
        self.player.stop()
        self.tree.selection_set(order[index])
        self.tree.focus(order[index])
        self.tree.see(order[index])

    def selected_ids(self):
        self.store_fields()
        return list(self.tree.selection())

    def settings(self, item):
        start = parse_time(item.get("start_text", "0"))
        end_text = item.get("end_text", "").strip()
        end = parse_time(end_text) if end_text else item["duration"]
        return edit_settings(item["duration"], start=start, end=end,
            gain=float(item.get("gain_text", item["gain"])), fade_in=float(item.get("fade_in_text", item["fade_in"])),
            fade_out=float(item.get("fade_out_text", item["fade_out"])),
            bass=float(item.get("bass_text", item["bass"])), treble=float(item.get("treble_text", item["treble"])),
            eq=[float(item.get(f"eq_{index}_text", item[f"eq_{index}"])) for index in range(len(EQ_FREQUENCIES))],
            noise=str(item.get("noise_text", item["noise"])) == "1",
            noise_reduction=float(item.get("noise_reduction_text", item["noise_reduction"])),
            noise_floor=float(item.get("noise_floor_text", item["noise_floor"])),
            noise_type=item.get("noise_type_text", item["noise_type"]),
            noise_track=str(item.get("noise_track_text", item["noise_track"])) == "1")

    def flat_eq(self):
        for key in ("bass", "treble", *("eq_" + str(index) for index in range(len(EQ_FREQUENCIES)))):
            self.variables[key].set("0")

    def draw_wave(self):
        self.wave.delete("all")
        item = self.items.get(self.current)
        if not item or not item["duration"]:
            self.wave.create_text(max(1, self.wave.winfo_width()) / 2, ui.px(50), text="Waveform appears after loading audio", fill=ui.P["muted"])
            return
        width, height = max(1, self.wave.winfo_width()), max(1, self.wave.winfo_height())
        duration = item["duration"]
        try:
            start, end = parse_time(self.variables["start"].get()), parse_time(self.variables["end"].get())
        except ValueError:
            return
        for i, peak in enumerate(item["peaks"]):
            x = i * width / max(1, len(item["peaks"]))
            self.wave.create_line(x, height / 2 - peak * height * .43, x, height / 2 + peak * height * .43, fill=ui.P["muted"])
        left, right = start / duration * width, end / duration * width
        self.wave.create_rectangle(left, 1, right, height - 1, outline=ui.P["copper"], width=2)
        for x in (left, right):
            self.wave.create_line(x, 0, x, height, fill=ui.P["selection_background"], width=3)
        self.kept_label.config(text=f"Keep {time_text(max(0, end-start))}")
        self.draw_playhead()

    def draw_playhead(self):
        self.wave.delete("audio_playhead")
        item = self.items.get(self.current)
        if not item or not item["duration"]:
            return
        x = max(0, min(item["duration"], item.get("playhead", 0))) / item["duration"] * self.wave.winfo_width()
        self.wave.create_line(x, 0, x, self.wave.winfo_height(), fill=ui.P["foreground"], width=2, tags="audio_playhead")
        self.wave.create_polygon(x-4, 0, x+4, 0, x, 7, fill=ui.P["foreground"], outline="", tags="audio_playhead")

    def playback_volume(self):
        try:
            value = float(self.variables["volume"].get())
            if 0 <= value <= 1:
                return value
        except ValueError:
            pass
        return .65

    def apply_playback_volume(self):
        if self.player.path and hasattr(self.player, "set_volume"):
            self.player.set_volume(self.playback_volume())

    def begin_playback(self, path, ident, start, end, position=None):
        if self.current != ident:
            return
        absolute = start if position is None else max(start, min(end-.01, position))
        self.preview_start, self.preview_end, self.playback_track = start, end, ident
        self.player.play(path, volume=self.playback_volume(), start=absolute-start, length=end-start)
        self.items[ident]["playhead"] = absolute
        self.pause_button.config(text="⏸ Pause")
        self.draw_playhead()

    def toggle_pause(self):
        if self.player.path and not self.busy:
            self.player.pause()
            self.pause_button.config(text="▶ Resume" if self.player.paused else "⏸ Pause")

    def stop_playback(self):
        self.player.stop()
        if self.playback_track in self.items:
            self.items[self.playback_track]["playhead"] = 0
        self.playback_track = None
        self.pause_button.config(text="⏸ Pause")
        self.draw_playhead()
        if self.current in self.items:
            item = self.items[self.current]
            self.playhead.config(text=f"{time_text(item.get('playhead', 0))} / {time_text(item['duration'])} · Right-click waveform to seek")

    def seek_wave(self, event):
        if self.busy or self.current not in self.items:
            return "break"
        duration = self.items[self.current]["duration"]
        if not duration:
            return "break"
        position = max(0, min(duration-.01, event.x / max(1, self.wave.winfo_width()) * duration))
        try:
            if (self.player.path and self.playback_track == self.current
                    and self.preview_start <= position < self.preview_end):
                self.player.seek(position-self.preview_start)
                if self.player.paused:
                    self.player.pause()
                self.pause_button.config(text="⏸ Pause")
                self.items[self.current]["playhead"] = position
                self.draw_playhead()
            else:
                self.items[self.current]["playhead"] = position
                self.draw_playhead()
                self.play_original(position=position)
        except Exception as error:
            messagebox.showerror("Playback", str(error), parent=self)
        return "break"

    def recolour(self):
        if not self.destroyed:
            self.wave.config(background=ui.P["surface"], highlightbackground=ui.P["border"])
            self.draw_wave()

    def wave_drag(self, event):
        if self.busy or self.current not in self.items or not self.items[self.current]["duration"]:
            return
        duration = self.items[self.current]["duration"]
        value = max(0, min(duration, event.x / max(1, self.wave.winfo_width()) * duration))
        try:
            start, end = parse_time(self.variables["start"].get()), parse_time(self.variables["end"].get())
        except ValueError:
            return
        if event.type == tk.EventType.ButtonPress:
            self.drag_edge = "start" if abs(value-start) < abs(value-end) else "end"
        key = self.drag_edge or "start"
        value = min(value, end - .01) if key == "start" else max(value, start + .01)
        self.variables[key].set(time_text(max(0, min(duration, value))))

    def use_playhead(self, key):
        if self.player.path and not self.busy:
            position = self.player.position() + getattr(self, "preview_start", 0)
            self.variables[key].set(time_text(position))

    def start(self, work, done):
        if self.busy:
            return
        self.store_fields(); self.player.stop()
        self.save_recovery(capture=False)
        self.busy = True
        for button in self.action_buttons + self.edit_widgets:
            button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self.progress_bar.start(12)
        self.job = AudioJob(lambda text: self.events.put(("progress", text)))

        def run():
            try:
                result = work(self.job)
                self.events.put(("done", done, result))
            except Cancelled:
                self.events.put(("cancelled",))
            except Exception as error:
                self.events.put(("error", str(error)))
            finally:
                if self.destroyed:
                    self.temp.cleanup()
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def poll(self):
        self.poll_job = None
        if self.destroyed:
            return
        terminal = None
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                self.message.config(text=event[1][-500:])
            elif event[0] == "loaded":
                ident, result = event[1:]
                self.items[ident].update(result)
                self.tree.item(ident, values=("Ready",))
                self.save_recovery(capture=False)
            else:
                terminal = event
        if terminal is not None:
            self.busy = False
            self.progress_bar.stop()
            for button in self.action_buttons + self.edit_widgets:
                button.state(["!disabled"])
            self.cancel_button.state(["disabled"])
            self.tools = tool_paths(self.tools_folder)
            self.current = None
            self.show_track()
            if self.closing:
                self.destroy(); return
            if terminal[0] == "done":
                self.message.config(text="Ready")
                try:
                    terminal[1](terminal[2])
                except Exception as error:
                    messagebox.showerror("Track workshop", str(error), parent=self)
            elif terminal[0] == "error":
                self.message.config(text="Operation failed; existing mod files were left unchanged.")
                messagebox.showerror("Track workshop", terminal[1], parent=self)
            else:
                self.message.config(text="Cancelled")
            self.save_recovery()
        if self.player.path and self.playback_track in self.items:
            item = self.items[self.playback_track]
            position = min(self.preview_end, self.preview_start + self.player.position())
            if getattr(self.player, "finished", lambda: False)():
                position = self.preview_end
                self.player.stop()
                self.playback_track = None
                self.pause_button.config(text="⏸ Pause")
            item["playhead"] = position
            if self.current in self.items and item is self.items[self.current]:
                self.playhead.config(text=f"{time_text(position)} / {time_text(item['duration'])} · Right-click waveform to seek")
                self.draw_playhead()
        self.poll_job = self.after(100, self.poll)

    def ensure_tools(self, job):
        return install_tools(self.tools_folder, job)

    def setup(self):
        self.start(lambda job: install_tools(self.tools_folder, job, update=True),
            lambda result: self.message.config(text="yt-dlp, FFmpeg, FFprobe and Deno are ready."))

    def load_info(self, ident, source, tools, job, info=None):
        source = Path(source)
        if not source.resolve().is_relative_to(self.workspace.resolve()):
            # Staged imports and external files may disappear independently after a crash.
            saved_source = self.workspace / ident / ("original" + source.suffix)
            saved_source.parent.mkdir(parents=True, exist_ok=True)
            job.check()
            shutil.copy2(source, saved_source)
            source = saved_source
        data = probe_audio(source, tools, job)
        result = dict(source=str(source), duration=data["duration"], end=data["duration"],
            end_text=time_text(data["duration"]), peaks=waveform(source, tools, job), status="Ready")
        tags = data.get("tags", {})
        item = self.items[ident]
        if item["title"] in ("New track", ""):
            result["title"] = (info or {}).get("track") or tags.get("title") or (info or {}).get("title") or Path(source).stem
        if not item["artist"]:
            result["artist"] = (info or {}).get("artist") or tags.get("artist") or ""
        self.events.put(("loaded", ident, result))

    def download(self, all_tracks=False):
        ids = list(self.items) if all_tracks else self.selected_ids()
        self.store_fields()
        requests = [(ident, self.items[ident]["url"]) for ident in ids if not self.items[ident]["source"]]
        if not requests:
            self.message.config(text="Select a track which has not been downloaded, or open local audio."); return
        def work(job):
            tools = self.ensure_tools(job)
            failures = []
            for ident, url in requests:
                job.check()
                try:
                    source, info = download_audio(url, self.workspace / ident, tools, job)
                    self.load_info(ident, source, tools, job, info)
                except Cancelled:
                    raise
                except Exception as error:
                    failures.append(self.items[ident]["title"] + ": " + str(error))
            return failures
        def done(failures):
            ready = [ident for ident, _ in requests if self.items[ident]["duration"]]
            if ready:
                self.store_fields()
                self.tree.selection_set(ready[0])
                self.tree.focus(ready[0])
                self.tree.see(ready[0])
                self.review_selected()
                self.message.config(text=f"{len(ready)} tracks downloaded. Review each with Previous / Next track; each keeps its own trim, gain and fades.")
            if failures:
                messagebox.showwarning("Some downloads failed", "\n\n".join(failures), parent=self)
        self.start(work, done)

    def load_existing(self):
        requests = [(ident, item["source"]) for ident, item in self.items.items() if item["source"] and not item["duration"]]
        if not requests:
            return
        def work(job):
            tools = self.ensure_tools(job)
            for ident, source in requests:
                self.load_info(ident, source, tools, job)
        self.start(work, lambda result: None)

    def open_local(self):
        paths = filedialog.askopenfilenames(parent=self, title="Open audio",
            filetypes=[("Audio", "*.ogg *.opus *.mp3 *.m4a *.wav *.flac *.webm *.mp4 *.aac"), ("All files", "*.*")])
        if not paths:
            return
        ids = [self.insert_track(dict(title=Path(path).stem, audio_path=path)) for path in paths]
        self.tree.selection_set(ids)
        self.load_existing()

    def add_link(self):
        if not self.busy:
            ident = self.insert_track(dict(title="New track"))
            self.tree.selection_set(ident)

    def play_original(self, position=None):
        ids = self.selected_ids()
        if not ids or not self.items[ids[0]]["duration"]:
            return
        ident = ids[0]
        item = copy.deepcopy(self.items[ident])
        def play(path):
            self.begin_playback(path, ident, 0, item["duration"], position)
        if item.get("original_preview"):
            try:
                play(item["original_preview"])
            except Exception as error:
                messagebox.showerror("Preview", str(error), parent=self)
            return
        item["settings"] = edit_settings(item["duration"])
        def done(results):
            path = results[0][2]
            self.items[ident]["original_preview"] = path
            play(path)
        self.start(lambda job: self.render([(ident, item)], job), done)

    def render_requests(self, ids):
        requests = []
        for ident in ids:
            item = copy.deepcopy(self.items[ident])
            if not item["source"] or not item["duration"]:
                raise ValueError("Download or load " + item["title"] + " first.")
            if not item["title"].strip():
                raise ValueError("Give each track a title.")
            item["settings"] = self.settings(item)
            volume = float(item.get("volume_text", item["volume"]))
            if not 0 <= volume <= 1:
                raise ValueError("In-game volume must be between 0 and 1.")
            item["volume"] = volume
            requests.append((ident, item))
        return requests

    def render(self, requests, job):
        from music_master import slug
        tools = self.ensure_tools(job)
        results = []
        for ident, item in requests:
            output = self.workspace / ident / (slug(item["title"]) or "track")
            output = output.parent / (output.name + "-" + uuid.uuid4().hex[:8] + ".ogg")
            convert_audio(item["source"], output, tools, job, item["settings"], item["title"], item["artist"])
            results.append((ident, item, str(output)))
        return results

    def preview_edit(self):
        try:
            requests = self.render_requests(self.selected_ids()[:1])
        except ValueError as error:
            messagebox.showerror("Preview", str(error), parent=self); return
        def done(results):
            if results:
                ident, item, path = results[0]
                self.begin_playback(path, ident, item["settings"]["start"], item["settings"]["end"])
        self.start(lambda job: self.render(requests, job), done)

    def export(self):
        try:
            requests = self.render_requests(self.selected_ids())
        except ValueError as error:
            messagebox.showerror("Export", str(error), parent=self); return
        if not requests:
            return
        if len(requests) == 1:
            path = filedialog.asksaveasfilename(parent=self, title="Export Ogg Vorbis", defaultextension=".ogg",
                initialfile=requests[0][1]["title"] + ".ogg", filetypes=[("Ogg Vorbis", "*.ogg")])
            if not path:
                return
            destinations = [Path(path)]
        else:
            folder = filedialog.askdirectory(parent=self, title="Export selected Ogg tracks")
            if not folder:
                return
            from music_master import slug
            destinations = []
            for _, item in requests:
                candidate = Path(folder) / ((slug(item["title"]) or "track") + ".ogg")
                number = 2
                while candidate.exists() or candidate in destinations:
                    candidate = Path(folder) / f"{slug(item['title']) or 'track'}_{number}.ogg"; number += 1
                destinations.append(candidate)
        def done(results):
            for (_, _, source), target in zip(results, destinations):
                shutil.copy2(source, target)
            self.message.config(text=f"Exported {len(results)} Ogg Vorbis file(s).")
        self.start(lambda job: self.render(requests, job), done)

    def add_to_station(self):
        from music_master import join_artist
        target = self.replacement[:2] if self.replacement else self.targets.get(self.target.get())
        if not target:
            messagebox.showinfo("Track workshop", "Choose a local station, or make the planned station first. You can export .ogg files without a station.", parent=self); return
        mod, token = target
        try:
            requests = self.render_requests(self.selected_ids())
            if self.replacement and len(requests) != 1:
                raise ValueError("Select one track to replace the song audio.")
            names = [join_artist(item["title"], item["artist"]) for _, item in requests]
            if len(names) != len(set(names)) or (not self.replacement and any(name in mod.songs for name in names)):
                raise ValueError("A selected song name is already in this music mod. Rename it before adding.")
            if token not in mod.stations:
                raise ValueError("The target station is no longer available.")
        except ValueError as error:
            messagebox.showerror("Track workshop", str(error), parent=self); return
        if not requests:
            return
        def done(results):
            from music_master import STAGING
            staged = []
            for ident, item, source in results:
                destination = Path(STAGING) / "audio_imports" / uuid.uuid4().hex / Path(source).name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                staged.append((str(destination), join_artist(item["title"], item["artist"]), item["volume"], 1))
            # Other windows may have selected a different station during conversion.
            self.music.mod = mod
            self.music.station = mod.stations[token]
            if self.replacement:
                self.music.stage_file(self.replacement[2], staged[0][0], mod=mod)
                song = mod.songs.get(self.replacement[3])
                if song:
                    lines = mod.text_lines(song.rel)
                    for index in range(song.entry.first, song.entry.last + 1):
                        lines[index] = re.sub(r"(\bvolume\s*=\s*)[\d.]+",
                            lambda match: match.group(1) + self.music.num(staged[0][2]), lines[index])
                    self.music.write(song.rel, lines, mod=mod)
                mod.load(); self.music.after_change()
            else:
                self.music.write_songs(mod.stations[token], staged)
            for ident, _, _ in results:
                self.tree.item(ident, values=("Staged",))
                self.items[ident]["status"] = "Staged"
            self.message.config(text="Audio staged. Use Save to mod in Music Master to write it to the game files.")
            getattr(self.music.app, "feedback", lambda *args: None)("success")
        self.start(lambda job: self.render(requests, job), done)

    def cancel(self):
        if self.job and self.busy:
            self.job.cancel()
            self.message.config(text="Cancelling…")

    def close(self):
        if self.busy:
            self.closing = True
            self.cancel()
        else:
            self.destroy()

    def on_destroy(self, event):
        if event.widget is not self:
            return
        self.destroyed = True
        if self.poll_job:
            self.after_cancel(self.poll_job)
        for job in (self.autosave_job, self.startup_job):
            if job:
                self.after_cancel(job)
        self.player.stop()
        if self.job:
            self.job.cancel()
        if not self.worker or not self.worker.is_alive():
            self.temp.cleanup()
        self.music._audio_editors.discard(self)
        if self.recolour in ui.THEME_HOOKS:
            ui.THEME_HOOKS.remove(self.recolour)
