"""Theme-aware bevelled globe icons, projected from public-domain country outlines."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageTk

import ui
import paths  # (Scripts/paths.py: where the tool's files are)


CATALOG = '__regions__'
_data = {}
_images = {}


def data(folder):
    key = str(folder)
    if key not in _data:
        base = Path(folder) / 'regions'
        if not (base / 'regions.json').is_file():
            base = Path(paths.BUNDLE) / 'icons' / 'regions'
        with (base / 'regions.json').open(encoding='utf-8') as source:
            manifest = json.load(source)
        with Image.open(base / 'countries.png') as source:
            atlas = np.asarray(source.convert('L')).copy()
        _data[key] = (manifest['regions'], atlas)
    return _data[key]


def all_icons(folder):
    return [('region:' + r['id'], r['label']) for r in data(folder)[0]]


def render(folder, region_id, size):
    regions, atlas = data(folder)
    region = next((r for r in regions if r['id'] == region_id), None)
    if region is None:
        raise ValueError('Unknown globe region: ' + region_id)
    s = max(32, int(size)) * 4
    yy, xx = np.mgrid[:s, :s].astype(float)
    # Inverse orthographic projection: no polygons can spill past the globe rim.
    x = (xx / s - .5) / .405
    y = (.465 - yy / s) / .405
    rho = np.sqrt(x*x + y*y)
    inside = rho <= 1
    z = np.sqrt(np.maximum(0, 1-rho*rho))
    lon0, lat0 = np.radians(region['center'])
    lat = np.arcsin(np.clip(z*np.sin(lat0) + y*np.cos(lat0), -1, 1))
    lon = lon0 + np.arctan2(x, z*np.cos(lat0) - y*np.sin(lat0))
    lon_deg = (np.degrees(lon) + 180) % 360 - 180
    lat_deg = np.degrees(lat)
    a_h, a_w = atlas.shape
    countries = atlas[np.clip(((90-lat_deg)/180*a_h).astype(int), 0, a_h-1),
                      np.clip(((lon_deg+180)/360*a_w).astype(int), 0, a_w-1)]
    land = countries > 0
    selected = np.isin(countries, region['countries']) & inside
    if region_id == 'europe':
        # Russia is transcontinental; stop at the Urals rather than painting Siberia.
        selected &= lon_deg < 60
    if region_id == 'asia':
        # Match Europe's Urals split while including Asian Russia.
        selected &= (countries != 76) | (lon_deg >= 60)
    if region_id == 'north-pole':
        selected = (lat_deg >= 78) & inside
    # A light metallic bevel gives the selected area depth without hiding its shape.
    mask = Image.fromarray((selected*255).astype(np.uint8))
    bevel = np.asarray(mask.filter(ImageFilter.GaussianBlur(max(1, s*.004))), dtype=float)/255
    gy, gx = np.gradient(bevel)
    edge_light = np.clip((gx+gy)*s*.22, -1, 1)
    accent = np.array(ImageColor.getrgb(ui._mix(ui.P['copper'], '#ffcf73', .46)), dtype=float)
    ocean = np.array([32., 69., 90.])
    earth = np.array([113., 145., 134.])
    ice = np.array([206., 222., 222.])
    rgb = np.where(land[..., None], earth, ocean)
    rgb = np.where(((lat_deg < -69) & land)[..., None], ice, rgb)
    rgb = np.where(selected[..., None], accent, rgb)
    rgb += selected[..., None] * edge_light[..., None] * 65
    # Thin meridians and parallels disappear naturally towards the limb.
    grid = ((np.abs((lon_deg+15) % 30-15) < .65) |
            (np.abs((lat_deg+15) % 30-15) < .65)) & ~selected
    rgb += grid[..., None] * 12
    light = np.clip(.52 + .5*z - .20*x + .24*y, .3, 1.24)
    rgb *= light[..., None]
    specular = np.exp(-((x+.35)**2 + (y-.5)**2)/.035) * 48
    rgb += specular[..., None]
    rgba = np.empty((s, s, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    rgba[..., 3] = inside.astype(np.uint8)*255
    sphere = Image.fromarray(rgba)
    out = Image.new('RGBA', (s, s))
    draw = ImageDraw.Draw(out)
    metal = ui._mix(ui.P['copper'], '#6b5743', .45)
    shine = ui._mix(metal, '#fff5d3', .72)
    dark = ui._mix(metal, '#090d19', .7)
    # Small plinth and a raised circular rim, matching the flag-pin metalwork.
    draw.ellipse((s*.31, s*.906, s*.73, s*.985), fill=(0, 0, 0, 75))
    draw.rounded_rectangle((s*.445, s*.845, s*.555, s*.935), radius=s*.02, fill=dark)
    draw.ellipse((s*.30, s*.906, s*.70, s*.975), fill=dark)
    draw.ellipse((s*.32, s*.902, s*.68, s*.948), fill=metal)
    draw.arc((s*.33, s*.905, s*.67, s*.944), 190, 330, fill=shine, width=max(1, s//110))
    draw.arc((s*.32, s*.902, s*.68, s*.948), 185, 345, fill=shine, width=max(1, s//85))
    rim = (s*.074, s*.039, s*.926, s*.891)
    draw.ellipse(rim, fill=dark)
    draw.ellipse((s*.08, s*.045, s*.92, s*.885), outline=metal, width=max(2, s//65))
    draw.arc(rim, 135, 315, fill=shine, width=max(2, s//65))
    draw.arc((s*.078, s*.043, s*.922, s*.887), 195, 258, fill='#fff5d7', width=max(1, s//180))
    out.alpha_composite(sphere)
    # The tiny Pacific islands need a readable glint at task-list sizes.
    if region_id in ('australia-polynesia','oceania'):
        draw = ImageDraw.Draw(out)
        for lo, la in ((-172, -14), (-150, -17), (-175, -21)):
            dl = np.radians(lo)-lon0
            phi = np.radians(la)
            depth = np.sin(lat0)*np.sin(phi)+np.cos(lat0)*np.cos(phi)*np.cos(dl)
            if depth > 0:
                ix = s*(.5+.405*np.cos(phi)*np.sin(dl))
                iy = s*(.465-.405*(np.cos(lat0)*np.sin(phi)-np.sin(lat0)*np.cos(phi)*np.cos(dl)))
                r = max(1, s*.008)
                draw.ellipse((ix-r, iy-r, ix+r, iy+r), fill=tuple(np.clip(accent,0,255).astype(int)))
    return out.resize((size, size), Image.Resampling.LANCZOS)


def image(folder, region_id, size):
    key = (str(folder), region_id, size, ui.P['copper'])
    if key not in _images:
        try:
            _images[key] = ImageTk.PhotoImage(render(folder, region_id, size))
        except (OSError, ValueError, KeyError):
            return ''
    return _images[key]
