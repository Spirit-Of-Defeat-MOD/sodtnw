"""🚨 Error alerts: Error Log Master can flash an error at another dev. It goes in the shared To Do data
("error_alerts": {id, to, by, when, key, link, title, sev, where, note, state, answer, answered}); every Organisation
Master looks every few seconds (the live sync brings the others' alerts in) and, for one to you, opens a window that
stays on top and flashes until you answer: ✋ I'm on it (the error is claimed for you and Error Log Master opens at it)
or ⏳ Can't now (with why). The one who sent it is told the answer.
Settings > 🚨 Error alerts can pop up for me (personal; shared as the dev's "alerts_off" so senders know) - off, they
wait in Error Log Master's side-bar button (🚨) instead."""
import ctypes
import datetime
import uuid
import tkinter as tk
from tkinter import ttk

import ui
from error_alert_style import AlertHeader
from error_alert_audio import AlertAudio

TICK = 5000
KEEP_DAYS = 7


def now():
	return datetime.datetime.now().replace(microsecond=0).isoformat()


def alerts(data):
	return data.setdefault("error_alerts", [])


def send(todo, to, item_key, link, title, sev, where, note):
	a = dict(id=uuid.uuid4().hex[:12], to=to, by=todo.me.get(), when=now(), key=item_key, link=link, title=title, sev=sev,
			 where=where, note=note, state="open")
	lst = alerts(todo.data)
	cut = (datetime.datetime.now() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
	lst[:] = [x for x in lst if x.get("when", "") >= cut] + [a]
	todo.save(feedback=False)
	return a


def for_key(data, key):
	return [a for a in data.get("error_alerts", []) if a.get("key") == key]


def alerts_off(data, name):
	return bool(next((d.get("alerts_off") for d in data.get("devs", []) if d["name"] == name), False))


def flash(win, on=True):
	"""The taskbar button flashes (Windows) until the window is in front."""
	try:
		class FLASHWINFO(ctypes.Structure):
			_fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
						("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]
		hwnd = int(win.wm_frame(), 16)
		info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3 | 12 if on else 0, 0, 0)  # (FLASHW_ALL | FLASHW_TIMERNOFG)
		ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
	except Exception:
		pass


class AlertWindow(tk.Toplevel):
	"""The alert, on top of everything, its border flashing red until it's answered (no ✕: answer it)."""

	def __init__(self, app, alert, done):
		super().__init__(app.root)
		self.app, self.alert, self.done = app, alert, done
		self._blink_job = None
		self._flash_job = None
		self._om_nonmodal = True
		self.title(f"🚨 Error alert from {alert.get('by', '?')}")
		self.attributes("-topmost", True)
		self.protocol("WM_DELETE_WINDOW", lambda: self.bell())  # (it has to be answered)
		self.red = ui.P.get("age_red", "#c62828")
		self.border = tk.Frame(self, background=self.red, padx=6, pady=6)
		self.border._om_bar = True
		self.border.pack(fill="both", expand=True)
		f = ttk.Frame(self.border, padding=16)
		f.pack(fill="both", expand=True)
		self.header = AlertHeader(f,AlertAudio(app.sound_settings) if hasattr(app,"sound_settings") else None)
		self.header.pack(fill="x", pady=(0,12))
		ttk.Label(f, text=f"🚨 {alert.get('by', '?')} needs you on an error now", font="om_head", wraplength=ui.px(520)).pack(anchor="w")
		ttk.Label(f, text=f"{alert.get('sev', '')} {alert.get('title', '')}", font="om_bold", wraplength=ui.px(520)).pack(anchor="w", pady=(10, 2))
		if alert.get("where"):
			ttk.Label(f, text=f"📄 {alert['where']}", style="Muted.TLabel", wraplength=ui.px(520)).pack(anchor="w")
		if alert.get("note"):
			ttk.Label(f, text=f"“{alert['note']}”", wraplength=ui.px(520)).pack(anchor="w", pady=(8, 0))
		ttk.Label(f, text=f"Sent {alert.get('when', '')[11:16]}", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(14, 0))
		bf.columnconfigure(0,weight=1,uniform="response")
		bf.columnconfigure(1,weight=1,uniform="response")
		ttk.Button(bf, text="✋ I'm on it (open it)", width=1, command=self.take).grid(row=0,column=0,sticky="ew",padx=(0,4))
		self.why = tk.StringVar()
		ttk.Button(bf, text="⏳ Can't now...", width=1, command=self.cant).grid(row=0,column=1,sticky="ew",padx=(4,0))
		self.update_idletasks()
		x = app.root.winfo_rootx() + max(0, (app.root.winfo_width() - self.winfo_width()) // 2)
		y = app.root.winfo_rooty() + 120
		self.geometry(f"+{x}+{y}")
		self.lift()
		self.focus_force()
		self._flash_job = self.after(200, lambda: flash(self))
		getattr(app, "feedback", lambda *_: None)("priority_critical")
		ui.THEME_HOOKS.append(self.retheme)
		self.bind("<Destroy>",self.cleanup,add="+")
		self.retheme()
		self.blink(0)

	def retheme(self):
		if self.winfo_exists():
			ui.theme_all(self)
			self.configure(background=ui.P["background"])
			self.red=ui.P["age_red"]
			self.border.configure(background=self.red)

	def cleanup(self,event):
		if event.widget is self:
			for job in (self._blink_job,self._flash_job):
				if job is not None:
					try:self.after_cancel(job)
					except tk.TclError:pass
			if self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)

	def blink(self, n):
		if not self.winfo_exists():
			return
		self.border.configure(background=ui._mix(self.red,ui.P["background"],.2 if n%2==0 else .55))
		self._blink_job = self.after(700, lambda: self.blink(n + 1))

	def answer(self, state, text):
		a = self.alert
		a.update(state=state, answer=text, answered=now())
		todo = self.app.todo_page()
		lst = alerts(todo.data)
		if not any(x is a or x.get("id") == a["id"] for x in lst):  # (it came in while the sync held changes back)
			lst.append(a)
		for x in lst:
			if x.get("id") == a["id"] and x is not a:
				x.update(a)
		if state == "taking" and a.get("key"):
			todo.data.setdefault("error_claims", {})[a["key"]] = {"who": todo.me.get(), "when": datetime.date.today().isoformat()}
		todo.save(feedback=False)
		flash(self, False)
		self.destroy()
		self.done(a)

	def take(self):
		self.answer("taking", "✋ on it")
		try:
			import error_log_master
			w = error_log_master.show(self.app)
			w.after(300, lambda: w.go_to(self.alert.get("key")))
		except Exception:
			pass

	def cant(self):
		d = tk.Toplevel(self)
		d.title("⏳ Can't now")
		d._om_nonmodal = True
		d.attributes("-topmost", True)
		d.transient(self)
		f = ttk.Frame(d, padding=12)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text=f"Why? ({self.alert.get('by', '?')} sees this)").pack(anchor="w")
		why = tk.StringVar(value="In the middle of something - in a bit")
		for r in ("In the middle of something - in a bit", "Not my area - someone else?", "Away from the mod right now"):
			ttk.Radiobutton(f, text=r, variable=why, value=r).pack(anchor="w")
		e = ttk.Entry(f, width=50)
		e.pack(fill="x", pady=(6, 0))
		ttk.Label(f, text="(or type your own)", style="Muted.TLabel").pack(anchor="w")

		def ok():
			text = e.get().strip() or why.get()
			d.destroy()
			self.answer("declined", "⏳ " + text)
		ttk.Button(f, text="Send", command=ok).pack(anchor="e", pady=(8, 0))
		d.grab_set()


def start(app):
	"""Every few seconds: alerts to you pop up (one at a time); answers to yours are shown in the status bar."""
	shown, told = set(), set()
	app.error_alert_pending = 0

	def tick():
		try:
			todo = app.todo_page()
			me = todo.me.get()
			lst = todo.data.get("error_alerts", [])
			held = getattr(todo, "incoming_alerts", None)  # (the sync is holding the others' changes back for an open dialog)
			if held:
				have = {a.get("id") for a in lst}
				lst = lst + [a for a in held if a.get("id") not in have]
			mine = [a for a in lst if a.get("to") == me and a.get("state") == "open"]
			app.error_alert_pending = len(mine)
			on = app.config.get("error_alerts", True)
			if on and mine and not any(isinstance(w, AlertWindow) for w in app.root.winfo_children()):
				a = next((a for a in mine if a["id"] not in shown), mine[0])
				shown.add(a["id"])
				AlertWindow(app, a, lambda a: None)
			for a in lst:
				if a.get("by") == me and a.get("state") != "open" and a["id"] not in told and a.get("answered", "") >= getattr(app, "_alerts_since", ""):
					told.add(a["id"])
					app.set_status(f"🚨 {a['to']} answered your error alert ({a.get('title', '')[:50]}): {a.get('answer', '')}")
					getattr(app, "feedback", lambda *_: None)("presence")
			btn = getattr(app, "error_btn", None)
			if btn is not None:
				text = btn.cget("text").replace("  🚨", "")
				btn.configure(text=text + ("  🚨" if mine and not on else ""))
		except Exception:
			pass
		app.root.after(TICK, tick)
	app._alerts_since = now()  # (answers that came while you were away aren't announced again)
	app.root.after(TICK, tick)


def set_enabled(app, on):
	"""Settings: pop-ups on / off (personal), shared on your dev entry so a sender knows."""
	app.config["error_alerts"] = on
	app.save_config()
	todo = app.todo_page()
	dev = next((d for d in todo.data.get("devs", []) if d["name"] == todo.me.get()), None)
	if dev is not None and bool(dev.get("alerts_off")) != (not on):
		dev["alerts_off"] = not on
		todo.save(feedback=False)
