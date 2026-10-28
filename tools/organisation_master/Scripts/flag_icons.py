"""Country Master's flag lookup, rendered as bevelled waving flags on metallic poles."""
import math
import os
import re
import time
import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from cm_data import CountryData, find_game
import ui

_sources = {}
_images = {}


def normalise(value):
    value = value.strip()
    if value.lower().endswith(".tga"):
        value = value[:-4]
    if not re.fullmatch(r"[A-Za-z0-9]{3}(?:_[A-Za-z0-9_]+)?", value) or len(value) > 120:
        raise ValueError("Enter a country tag or flag variant, for example ENG or ENG_fascist.")
    return value[:3].upper() + value[3:].lower()


class FlagSource(CountryData):
    """Reuse Country Master's index and fallback rules without loading countries, states or maps."""
    def __init__(self, root):
        self.root, self.game = root, find_game(root)
        self.replaced = self._read_replace_paths()
        try:
            self._load_ideologies()
        except (OSError, ValueError):
            self.ideologies = {}
        self.checked = 0
        self.signature = None
        self.refresh(True)

    def refresh(self, force=False):
        now = time.monotonic()
        if not force and now - self.checked < 2:
            return
        self.checked = now
        signature = []
        for base in self.bases:
            try:
                signature.append(os.stat(os.path.join(base, "gfx", "flags")).st_mtime_ns)
            except OSError:
                signature.append(None)
        if signature != self.signature:
            self._load_flag_files()
            self.signature = signature

    def resolve(self, token, force=False):
        token = normalise(token)
        self.refresh(force)
        exact = self.flag_map.get((token + ".tga").lower())
        if exact:
            return exact
        aliases = {"fascist": "fascism", "communist": "communism", "non_aligned": "neutrality", "nonaligned": "neutrality"}
        for suffix, replacement in aliases.items():
            if token.lower().endswith("_" + suffix):
                exact = self.flag_map.get((token[:-len(suffix)] + replacement + ".tga").lower())
                if exact:
                    return exact
        return self.cosmetic_flag(token)


def source(root):
    key = os.path.abspath(root)
    if key not in _sources:
        _sources[key] = FlagSource(key)
    return _sources[key]


def render(path, size):
    """Match the generic flag silhouette, with a waved texture and raised metallic edges."""
    s = max(16, int(size)) * 4
    out = Image.new("RGBA", (s, s))
    draw = ImageDraw.Draw(out)
    accent = ui.P["copper"]
    metal, shine, dark = ui._mix(accent, "#000000", .25), ui._mix(accent, "#ffffff", .65), ui._mix(accent, "#000000", .78)
    # Bevelled pole and a spherical finial, lit from the upper left.
    draw.rounded_rectangle((s*.095,s*.15,s*.18,s*.96),radius=s*.035,fill=dark)
    draw.rounded_rectangle((s*.11,s*.16,s*.166,s*.94),radius=s*.024,fill=metal)
    draw.line((s*.121,s*.18,s*.121,s*.92),fill=shine,width=max(2,int(s*.014)))
    draw.ellipse((s*.055,s*.035,s*.215,s*.195),fill=dark)
    draw.ellipse((s*.068,s*.046,s*.202,s*.181),fill=accent)
    draw.ellipse((s*.078,s*.052,s*.172,s*.146),fill=shine)
    draw.ellipse((s*.094,s*.062,s*.145,s*.106),fill="#fff8dc")
    y, x = np.mgrid[0:s,0:s].astype(float) / s
    u = (x-.22)/.71
    top = .205 + .042*np.sin(u*2*math.pi-.45) + .025*u
    v = (y-top)/.47
    inside = (u>=0)&(u<=1)&(v>=0)&(v<=1)&(u<=1-.15*(1-np.abs(2*v-1)))
    mask = Image.fromarray((inside*255).astype(np.uint8))
    edge = max(3,int(s*.04)//2*2+1)
    outer = mask.filter(ImageFilter.MaxFilter(edge))
    shadow = Image.new("RGBA",(s,s),(0,0,0,0))
    shadow.paste((0,0,0,150),(int(s*.016),int(s*.022),s+int(s*.016),s+int(s*.022)),outer)
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s*.012)))
    # Embossed rim: the upper/left edge catches light, the lower/right edge recedes.
    blur = np.asarray(outer.filter(ImageFilter.GaussianBlur(max(1,s*.008))),dtype=float)/255
    gy,gx = np.gradient(blur)
    light = np.clip((gx+gy)*s*.35,-1,1)
    from PIL import ImageColor
    base = np.array(ImageColor.getrgb(metal),dtype=float)
    bright = np.array(ImageColor.getrgb(shine),dtype=float)
    low = np.array(ImageColor.getrgb(dark),dtype=float)
    rgb = base + np.maximum(light,0)[...,None]*(bright-base) + np.maximum(-light,0)[...,None]*(low-base)
    rim = Image.fromarray(np.clip(rgb,0,255).astype(np.uint8)).convert("RGBA")
    out.alpha_composite(Image.composite(rim,Image.new("RGBA",(s,s)),outer))
    if path:
        with Image.open(path) as flag:
            fabric = np.asarray(flag.convert("RGBA").resize((s,s),Image.Resampling.LANCZOS))
    else:
        blank = Image.new("RGBA",(s,s),ui.P["surface"])
        pen = ImageDraw.Draw(blank)
        pen.line([(s*.43,s*.28),(s*.60,s*.28),(s*.60,s*.43),(s*.50,s*.52),(s*.50,s*.61)],fill=shine,width=max(2,int(s*.03)))
        pen.ellipse((s*.48,s*.70,s*.53,s*.75),fill=shine)
        fabric = np.asarray(blank)
    sampled = fabric[np.clip((v*(s-1)).astype(int),0,s-1),np.clip((u*(s-1)).astype(int),0,s-1)].copy()
    shading = .91 + .13*np.cos(u*2*math.pi-.5) + .035*(.5-v)
    sampled[...,:3] = np.clip(sampled[...,:3].astype(float)*shading[...,None],0,255).astype(np.uint8)
    sampled[...,3] = np.where(inside,sampled[...,3],0)
    out.alpha_composite(Image.fromarray(sampled))
    return out.resize((size, size), Image.Resampling.LANCZOS)


def image(root, token, size):
    try:
        path = source(root).resolve(token)
        stat = os.stat(path) if path else None
        signature = (path, stat.st_mtime_ns, stat.st_size) if stat else (None,)
    except (OSError, ValueError):
        path, signature = None, (None,)
    key = (root, token, size, signature, ui.P["copper"], ui.P["surface"])
    if key not in _images:
        try:
            picture = render(path, size)
        except (OSError, ValueError, Image.DecompressionBombError):
            picture = render(None, size)
        _images[key] = ImageTk.PhotoImage(picture)
    return _images[key]


def pick(parent, root, current, on_pick):
    window = tk.Toplevel(parent)
    window.title("Flag Icon")
    window.transient(parent.winfo_toplevel())
    body = ttk.Frame(window, padding=14)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Country tag / flag variant", font="om_bold").pack(anchor="w")
    value = tk.StringVar(window, value=current[5:] if str(current or "").startswith("flag:") else "")
    entry = ttk.Entry(body, textvariable=value, width=42, font="om_body")
    entry.pack(fill="x", pady=(5, 4))
    ttk.Label(body, text="Examples: ENG, ENG_fascist, ENG_fascism or a cosmetic flag tag.", style="Muted.TLabel", wraplength=420).pack(anchor="w")
    preview = ttk.Label(body, anchor="center")
    preview.pack(fill="x", pady=10)
    status = ttk.Label(body, style="Muted.TLabel", wraplength=420, justify="left")
    status.pack(fill="x")
    state = {"job": None, "token": None}

    def refresh():
        state["job"] = None
        state["token"] = None
        try:
            token = normalise(value.get())
            path = source(root).resolve(token, force=True)
            if not path:
                raise ValueError("No flag found. Check the tag and that the flag exists in the mod or base game.")
            with Image.open(path) as candidate:
                candidate.verify()
            photo = image(root, token, ui.px(100))
            preview.configure(image=photo)
            preview.photo = photo
            status.configure(text=f"{token} · {os.path.basename(path)}\nUses Country Master's mod-first flag lookup.")
            state["token"] = token
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            preview.configure(image="")
            status.configure(text=str(error))
        apply.state(["!disabled"] if state["token"] else ["disabled"])

    def changed(*_):
        if state["job"]:
            window.after_cancel(state["job"])
        apply.state(["disabled"])
        state["job"] = window.after(180, refresh)

    def accept():
        if state["job"]:
            window.after_cancel(state["job"])
        refresh()
        if state["token"]:
            token = state["token"]
            window.destroy()
            on_pick("flag:" + token)

    actions = ttk.Frame(body)
    actions.pack(fill="x", pady=(12, 0))
    apply = ttk.Button(actions, text="Use Flag Icon", command=accept)
    apply.pack(side="right")
    ttk.Button(actions, text="Cancel", command=window.destroy).pack(side="right", padx=6)
    value.trace_add("write", changed)
    entry.bind("<Return>", lambda _event: accept())
    window.bind("<Escape>", lambda _event: window.destroy())
    def destroyed(event):
        if event.widget is window and state["job"]:
            window.after_cancel(state["job"])
            state["job"] = None
    window.bind("<Destroy>", destroyed, add="+")
    refresh()
    entry.focus_set()
    window.grab_set()
    return window
