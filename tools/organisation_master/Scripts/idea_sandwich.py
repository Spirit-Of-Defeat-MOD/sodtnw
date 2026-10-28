"""Stallonian Gambit's small, purely visual snack break."""
import math
import time
import tkinter as tk

from PIL import Image, ImageTk

import ui


def smooth(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


def pose(elapsed):
    """Appear, collect the idea, squeeze, bite, chew, wink and leave."""
    if elapsed < 1.5:
        frame = 0
    elif elapsed < 2.6:
        frame = 1
    elif elapsed < 3.3:
        frame = 2
    elif elapsed < 3.8:
        frame = 3
    elif elapsed < 4.4:
        frame = 4
    elif elapsed < 5.25:
        frame = 5
    elif elapsed < 5.9:
        frame = 6
    else:
        frame = 7
    return frame, smooth(elapsed / .65), smooth((elapsed - .7) / .8), smooth((elapsed - 1.6) / 1.0), smooth((elapsed - 7.1) / .65)


class IdeaSandwich:
    DURATION = 7.8

    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.pane = owner.todo.idea_pane
        self.tree = self.pane.list
        self.idea = (self.pane.cur or {}).get('id')
        self.selection_at_start = self.idea
        # An unselected list still offers a real visible idea, without changing selection.
        if not self.idea:
            def visible(parent=''):
                for ident in self.tree.get_children(parent):
                    if self.pane.idea(ident) and self.tree.bbox(ident, '#0'):
                        return ident
                    if self.tree.item(ident, 'open'):
                        found = visible(ident)
                        if found:
                            return found
            self.idea = visible()
        self.title = (self.pane.idea(self.idea) or {}).get('title', 'A tasty idea') if self.idea else 'A tasty idea'
        self.unit = max(1, round(ui.scale() * 2))
        self.size = 64 * self.unit
        self.frames = []
        with Image.open(owner.asset_path('stallonian_sandwich')) as source:
            sheet = source.convert('RGBA')
            for n in range(8):
                x, y = n % 4, n // 4
                cell = sheet.crop((x*sheet.width//4, y*sheet.height//2,
                                   (x+1)*sheet.width//4, (y+1)*sheet.height//2))
                # Deliberate small pixel silhouette, enlarged with sharp pixel edges.
                cell = cell.resize((64,64),Image.Resampling.LANCZOS).resize((self.size,self.size),Image.Resampling.NEAREST)
                self.frames.append(ImageTk.PhotoImage(cell,master=self.root))
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window._om_nonmodal = self.window._om_bar = self.window._om_effect_layer = True
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.key = '#102633'
        self.window.configure(background=self.key)
        self.window.attributes('-transparentcolor', self.key)
        self.window.attributes('-disabled', True)
        self.canvas = tk.Canvas(self.window,background=self.key,highlightthickness=0,borderwidth=0,takefocus=False)
        self.canvas._om_bar = self.canvas._om_effect_layer = True
        self.canvas.pack(fill='both',expand=True)
        self.closed = False
        self.job = self.bounds = None
        self.started = time.monotonic()
        self.card_cache = {}
        self.frame()

    def target(self):
        if self.idea:
            if not self.tree.exists(self.idea):
                return None
            box = self.tree.bbox(self.idea, '#0')
            if not box:
                return None
            x,y,w,h = box
            return (self.tree.winfo_rootx()-self.root.winfo_rootx()+x,
                    self.tree.winfo_rooty()-self.root.winfo_rooty()+y,w,h)
        return (self.tree.winfo_rootx()-self.root.winfo_rootx()+ui.px(20),
                self.tree.winfo_rooty()-self.root.winfo_rooty()+ui.px(40),ui.px(230),ui.px(26))

    def paper(self, width, height):
        """A rendered copy of the title, compressed as a real image with the card."""
        key = (width,height)
        if key not in self.card_cache:
            # Tk's PostScript cannot preserve our transparent sprites, so use a
            # tiny Pillow title card; no desktop capture or live widget edits.
            from PIL import ImageDraw, ImageFont
            im=Image.new('RGBA',(width,height),ui.P['surface'])
            draw=ImageDraw.Draw(im)
            draw.rectangle((0,0,width-1,height-1),outline=ui.P['copper'],width=max(1,self.unit))
            try:
                font=ImageFont.truetype('segoeui.ttf',max(10,round(12*ui.scale())))
            except OSError:
                font=ImageFont.load_default()
            title=self.title
            while len(title)>3 and draw.textlength(title,font=font)>width-ui.px(18):
                title=title[:-4]+'…'
            draw.text((ui.px(8),height/2),title,font=font,fill=ui.P['foreground'],anchor='lm')
            self.card_cache[key]=im
        return self.card_cache[key]

    def frame(self):
        self.job = None
        if self.closed:
            return
        began = time.monotonic()
        elapsed = began-self.started
        target = self.target() if self.tree.winfo_exists() else None
        if (elapsed>=self.DURATION or self.owner.theme!='Stallonian Gambit'
                or self.owner.todo.mode.get()!='idea' or not self.tree.winfo_ismapped()
                or (self.pane.cur or {}).get('id') != self.selection_at_start
                or self.root.state() not in ('normal','zoomed') or target is None):
            self.close()
            return
        width,height=self.root.winfo_width(),self.root.winfo_height()
        bounds=(width,height,self.root.winfo_rootx(),self.root.winfo_rooty())
        if bounds!=self.bounds:
            self.window.lift(self.root)
            self.window.geometry(f'{width}x{height}+{bounds[2]}+{bounds[3]}')
            self.bounds=bounds
        if not self.window.winfo_ismapped():
            self.window.deiconify()
            self.window.lift(self.root)
        c=self.canvas;c.delete('all')
        index,rise,collect,squish,leave=pose(elapsed)
        tx,ty,tw,th=target
        source_width=tw
        tw=min(tw,ui.px(310))
        size=self.size
        cx=max(size*.5+8,min(width-size*.5-8,tx+tw+size*.25))
        cy=max(size*.5+8,min(height-size*.5-8,ty+size*.55))
        cy+=(1-rise+leave)*size
        if index in (5,6):
            cy+=math.sin(elapsed*20)*ui.px(1.5)
        # Hide only the row title under the copy. The Treeview is never modified.
        if self.idea and collect>0 and elapsed<7.1:
            c.create_rectangle(tx,ty,tx+source_width,ty+th,fill=ui.P['selection_background'] if self.idea in self.tree.selection() else ui.P['surface'],outline='')
        c.create_image(round(cx),round(cy),image=self.frames[index])
        if .7<=elapsed<2.6:
            hand_x,hand_y=cx+size*.06,cy+size*.16
            pcx=tx+tw/2+(hand_x-tx-tw/2)*collect
            pcy=ty+th/2+(hand_y-ty-th/2)*collect
            pw=max(1,round(tw*(1-squish)+size*.24*squish))
            ph=max(1,round(th*(1-squish)+size*.09*squish))
            original=self.paper(max(1,round(tw)),max(1,round(th)))
            self.card_photo=ImageTk.PhotoImage(original.resize((pw,ph),Image.Resampling.BILINEAR),master=self.root)
            c.create_image(round(pcx),round(pcy),image=self.card_photo)
            # A warm outline and bread layers arrive as the idea is squeezed.
            if squish>.6:
                alpha=(squish-.6)/.4
                for oy,col in ((-ph/2,'#e4ae5b'),(ph/2,'#be7c39')):
                    c.create_line(pcx-pw/2,pcy+oy,pcx+pw/2,pcy+oy,fill=col,width=max(1,round(self.unit*alpha*2)))
        if 4.4<elapsed<5.9:
            for n in range(4):
                t=(elapsed-4.4+n*.14)% .65
                xx=cx+size*.2+math.sin(n*2)*t*ui.px(20)
                yy=cy+size*.02+t*t*ui.px(40)
                c.create_rectangle(xx,yy,xx+self.unit,yy+self.unit,fill='#e4ae5b',outline='')
        self.job=self.root.after(max(12,33-round((time.monotonic()-began)*1000)),self.frame)

    def close(self):
        if self.closed:
            return
        self.closed=True
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job=None
        if self.window.winfo_exists():
            self.window.destroy()
