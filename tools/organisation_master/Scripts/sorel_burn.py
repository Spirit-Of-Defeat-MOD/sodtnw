"""Fire anchored to the visible interface, followed by its scorched theme."""
import math
import time
import tkinter as tk

import ui


def visible_rect(widget, root):
    """Intersect a panel with its ancestors, including a scrolling canvas viewport."""
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped() or widget.winfo_toplevel() is not root:
            return None
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        left, top, right, bottom = 0, 0, root.winfo_width(), root.winfo_height()
        current = widget
        while current is not root:
            x, y = current.winfo_rootx()-rx, current.winfo_rooty()-ry
            left, top = max(left, x), max(top, y)
            right, bottom = min(right, x+current.winfo_width()), min(bottom, y+current.winfo_height())
            current = current.master
        if right-left >= 24 and bottom-top >= 20:
            return left, top, right, bottom
    except tk.TclError:
        pass
    return None


class SorelBurn:
    CHANGE_AT = 2.6
    DURATION = 4.0

    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.started = time.monotonic()
        self.job = None
        self.applied = False
        self.closed = False
        self.targets = []
        self.next_targets = 0
        self.bounds = None
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal = True
        self.window._om_bar = self.window._om_effect_layer = True
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.window.configure(background='#ff00ff')
        self.window.attributes('-transparentcolor', '#ff00ff')
        try:
            self.window.attributes('-disabled', True)  # Keep keyboard focus on the real UI.
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.window, background='#ff00ff', borderwidth=0,
                                highlightthickness=0, takefocus=False)
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill='both', expand=True)
        self.window.deiconify()
        self.frame()

    def collect_targets(self):
        targets = []
        for section in list(ui._sections):
            if section.collapsed:
                continue
            rect = visible_rect(section, self.root)
            if rect:
                targets.append((rect, section.title.cget('text')))
        # Burn the actual sidebar controls too, rather than an unrelated picture.
        widgets = list(self.owner.app.nav_buttons.values())
        widgets.append(self.owner.app.radio)
        for widget in widgets:
            rect = visible_rect(widget, self.root)
            if rect:
                targets.append((rect, 'sidebar'))
        self.targets = targets

    def frame(self):
        self.job = None
        if self.closed:
            return
        if not self.window.winfo_exists():
            self.close()
            return
        begun = time.monotonic()
        elapsed = begun-self.started
        if (self.root.state() not in ('normal', 'zoomed')
                or self.owner.theme != 'Sons of Sorel'):
            self.close()
            return
        if elapsed >= self.DURATION:
            if not self.applied:
                self.applied = True
                self.owner.apply_scorch()
            self.close()
            return
        # Raise before requesting geometry: raising relative to the owner afterward
        # makes Windows/Tk restore the old coordinates when the main window moves.
        bounds = (self.root.winfo_width(), self.root.winfo_height(),
                  self.root.winfo_rootx(), self.root.winfo_rooty())
        if bounds != self.bounds:
            self.window.lift(self.root)
            w, h, x, y = bounds
            self.window.geometry(f'{w}x{h}+{x}+{y}')
            self.canvas.configure(width=w, height=h)
            self.bounds = bounds
        if begun >= self.next_targets:
            self.collect_targets()
            self.next_targets = begun+.1
        if elapsed >= self.CHANGE_AT and not self.applied:
            self.applied = True
            self.owner.apply_scorch()
        intensity = min(1, elapsed/.65, max(0, (self.DURATION-elapsed)/.9))
        self.canvas.delete('all')
        for index, (rect, _name) in enumerate(self.targets):
            self.draw_panel(rect, elapsed, intensity, index)
        delay = max(12, 33-round((time.monotonic()-begun)*1000))
        self.job = self.root.after(delay, self.frame)

    def draw_panel(self, rect, elapsed, intensity, seed):
        x0, y0, x1, y1 = rect
        scale = ui.scale()
        # A charred rim hugs the panel's own frame; the transparent middle leaves
        # its task names, buttons and other content visible throughout the effect.
        self.canvas.create_rectangle(x0+1, y0+1, x1-1, y1-1, outline='#54251b',
                                     width=max(1, round(3*intensity*scale)))
        count = max(3, min(14, round((x1-x0)/(34*scale))))
        for edge, base in (('bottom', y1-2), ('header', y0+min(y1-y0-2, ui.px(27)))):
            edge_count = count if edge == 'bottom' else max(2, count//2)
            for n in range(edge_count):
                phase = n*1.7+seed*2.3+(0 if edge == 'bottom' else 1.4)
                x = x0+(n+.5)*(x1-x0)/edge_count
                height = (14+24*(.5+.5*math.sin(elapsed*7+phase)))*scale*intensity
                if edge == 'header':
                    height *= .65
                height = min(height, max(1, base-y0))
                half = min(14*scale, (x1-x0)/count*.6)
                sway = math.sin(elapsed*5+phase)*half*.6
                for fraction, colour in ((1, '#ef6718'), (.42, '#ffda70')):
                    tip = base-height*fraction
                    self.canvas.create_polygon(x-half, base, x-half*.8, base-height*.25*fraction,
                        x+sway, tip, x+half*.65, base-height*.3*fraction, x+half, base,
                        smooth=True, splinesteps=12, fill=colour, outline='')
        # Tiny embers rise within each panel, never in a detached central box.
        for n in range(4):
            x = x0+(x1-x0)*((n*.233+seed*.117) % 1)
            y = y1-((elapsed*35+n*19) % max(1, min(y1-y0, 65*scale)))
            self.canvas.create_oval(x, y, x+2*scale, y+2*scale, fill='#eaa14a', outline='')

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window.winfo_exists():
            self.window.destroy()
