"""👋 A small pop-up (where the achievements pop up) with a very light ping when another dev opens one of the tools:
Organisation Master, Culture Master, Country Master or a new master. It comes from the "opened" activity everyone's
tools share through live sync; Settings > "Show when other devs open a tool" turns it off (this PC)."""
from collections import deque
import datetime
import time
import tkinter as tk

import ui

SHOW_FOR = 5.0       # seconds on screen
RECENT = 15 * 60     # an "opened" older than this (arrived late, e.g. after being offline) isn't announced
QUIET = 30 * 60      # the same dev opening the same tool again within this: not announced again


def tools():
	"""The tools an opening is announced for (not page switches inside Organisation Master)."""
	names = {"Organisation Master", "Culture Master", "Country Master"}
	try:
		import masters
		names |= {m["name"] for m in masters.discovered()}
	except Exception:
		pass
	return names


class PresenceToasts:
	def __init__(self, app):
		self.app, self.root = app, app.root
		todo = app.todo_page()
		self.seen = {e.get("id") for e in todo.data.get("master_activity", [])}  # (what was there already isn't news)
		self.last = {}
		self.pending = deque()
		self.window = None
		self.job = None
		self.tools = tools()

	def enabled(self):
		return self.app.config.get("presence_toasts", True)

	def observe(self, data, me):
		"""After every save / sync: another dev's fresh "opened" of a tool -> a pop-up."""
		now = time.time()
		for e in data.get("master_activity", []):
			eid = e.get("id")
			if not eid or eid in self.seen:
				continue
			self.seen.add(eid)
			who, tool = e.get("who"), e.get("master")
			if e.get("action") != "opened" or tool not in self.tools or not who or who == me or not self.enabled():
				continue
			try:
				age = now - datetime.datetime.fromisoformat(e.get("when")).timestamp()
			except (TypeError, ValueError):
				continue
			if age > RECENT or now - self.last.get((who, tool), 0) < QUIET:
				continue
			self.last[(who, tool)] = now
			self.pending.append((who, tool))
		if self.pending and self.window is None and self.job is None:
			self.job = self.root.after(400, self.show_next)

	def show_next(self):
		self.job = None
		if not self.pending or getattr(self.app, "_quitting", False):
			return
		if self.root.state() not in ("normal", "zoomed"):
			self.job = self.root.after(1000, self.show_next)
			return
		self.who, self.tool = self.pending.popleft()
		w = self.window = tk.Toplevel(self.root)
		w.withdraw()
		w._om_nonmodal = w._om_bar = w._om_effect_layer = True
		w.overrideredirect(True)
		w.transient(self.root)
		w.attributes("-alpha", 0)
		self.canvas = tk.Canvas(w, highlightthickness=0, borderwidth=0, cursor="hand2", takefocus=False)
		self.canvas._om_bar = self.canvas._om_effect_layer = True
		self.canvas.pack(fill="both", expand=True)
		self.canvas.bind("<Button-1>", lambda ev: self.close_popup())
		w.deiconify()
		w.lift()
		self.started = time.monotonic()
		feedback = getattr(self.app, "feedback", None)
		if feedback:
			feedback("presence")  # (a very light ping; silent when sounds are off)
		self.animate()

	def animate(self):
		self.job = None
		if self.window is None:
			return
		t = time.monotonic() - self.started
		if t >= SHOW_FOR:
			return self.close_popup()
		r = self.root
		width, height = ui.px(300), ui.px(54)
		above = 0
		ach = getattr(self.app, "achievement_toasts", None)
		if ach is not None and getattr(ach, "window", None) is not None:
			above = ui.px(145) + ui.px(8)  # (an achievement on screen: just above it)
		x = r.winfo_rootx() + max(0, r.winfo_width() - width - ui.px(16))
		y = r.winfo_rooty() + max(0, r.winfo_height() - height - ui.px(24)) - above
		fade = min(1.0, t / 0.3, (SHOW_FOR - t) / 0.4)
		slide = round((1 - min(1.0, t / 0.3)) * ui.px(12))
		self.window.geometry(f"{width}x{height}+{x}+{y + slide}")
		self.window.attributes("-alpha", max(0.0, fade) * 0.96)
		c, p = self.canvas, ui.P
		c.delete("all")
		c.configure(background=p["surface"])
		c.create_rectangle(1, 1, width - 2, height - 2, outline=p["border"])
		c.create_rectangle(0, 0, ui.px(4), height, fill=p["copper"], outline="")
		c.create_text(ui.px(26), height / 2, text="👋", font="om_head")
		c.create_text(ui.px(48), ui.px(10), anchor="nw", text=self.who, font="om_small_bold", fill=p["foreground"])
		c.create_text(ui.px(48), ui.px(29), anchor="nw", text=f"opened {self.tool}", font="om_small", fill=p["muted"])
		c.create_line(ui.px(10), height - ui.px(4), ui.px(10) + (width - ui.px(20)) * max(0.0, 1 - t / SHOW_FOR), height - ui.px(4),
					  fill=p["copper"], width=ui.px(2))
		self.job = self.root.after(33, self.animate)

	def close_popup(self):
		if self.job is not None:
			self.root.after_cancel(self.job)
			self.job = None
		if self.window is not None:
			self.window.destroy()
			self.window = None
		if self.pending:
			self.job = self.root.after(300, self.show_next)

	def close(self):
		self.pending.clear()
		self.close_popup()
