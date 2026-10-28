"""💬 Request (in every master's menu bar but Organisation Master's): a bug, an idea or a change for that master, sent
straight into the To Do under Tools > Requests > <the master> > the request.

It goes through the masters' activity inbox (master_activity.py), like ai_tasks.py: a running Organisation Master adds it
within a few seconds and live sync shares it; a closed one adds it the next time it opens. Organisation Master makes the
Requests and <master> tasks the first time (todo_master.import_ai_task, "under")."""
import tkinter as tk
import uuid
from tkinter import ttk

import master_activity

PROJECT, CATEGORY = "Tools", "Tools"
KINDS = (("🐞 Bug", "Something's wrong"), ("💡 Idea", "Something new it could do"), ("🔧 Change", "Something that should work differently"))


def send(master, mod_root, title, note="", kind="", priority="Normal"):
	"""Puts the request in the inbox; True when it's on its way."""
	state = dict(title=(f"{kind.split()[-1]}: " if kind else "") + title.strip(), note=note.strip(), project=PROJECT,
				 category="Bug" if kind.endswith("Bug") else CATEGORY, priority=priority, key="request-" + uuid.uuid4().hex[:12],
				 under=["Requests", master], under_category=CATEGORY)
	return master_activity.record(master, mod_root, "add_task", who=master_activity.actor(mod_root), state=state)


def window(root, master, mod_root, context=None, status=None):
	"""The Request window. context(): what you're looking at now, offered as a line of the note; status(text): the
	master's status bar."""
	w = tk.Toplevel(root)
	w.title(f"💬 Request - {master}")
	w.transient(root)
	w._om_nonmodal = True
	f = ttk.Frame(w, padding=14)
	f.pack(fill="both", expand=True)
	ttk.Label(f, text=f"Ask for something in {master}", font=("Segoe UI", 12, "bold")).pack(anchor="w")
	ttk.Label(f, text=f"It goes straight into the To Do: Tools › Requests › {master}.", foreground="#888888").pack(anchor="w", pady=(0, 10))
	kind = tk.StringVar(value=KINDS[0][0])
	row = ttk.Frame(f)
	row.pack(fill="x")
	for k, tip in KINDS:
		ttk.Radiobutton(row, text=k, value=k, variable=kind).pack(side="left", padx=(0, 12))
	ttk.Label(f, text="In a few words:").pack(anchor="w", pady=(10, 2))
	title = tk.StringVar()
	e = ttk.Entry(f, textvariable=title, width=60)
	e.pack(fill="x")
	e.focus_set()
	ttk.Label(f, text="Details (what happened, what you expected, how to get there...):").pack(anchor="w", pady=(10, 2))
	try:  # (the theme's colours: a plain Text is white on a dark theme)
		import ui
		look = dict(background=ui.P["input_background"], foreground=ui.P["foreground"], insertbackground=ui.P["foreground"])
	except Exception:
		look = {}
	note = tk.Text(f, width=60, height=8, wrap="word", relief="flat", padx=6, pady=4, **look)
	note.pack(fill="both", expand=True)
	where = ""
	try:
		where = (context() or "").strip() if context else ""
	except Exception:
		pass
	add_where = tk.BooleanVar(value=bool(where))
	if where:
		ttk.Checkbutton(f, text=f"Add what I'm on: {where[:80]}", variable=add_where).pack(anchor="w", pady=(6, 0))
	bottom = ttk.Frame(f)
	bottom.pack(fill="x", pady=(10, 0))
	ttk.Label(bottom, text="Priority").pack(side="left")
	prio = ttk.Combobox(bottom, values=("Low", "Normal", "High", "Critical"), state="readonly", width=9)
	prio.set("Normal")
	prio.pack(side="left", padx=6)
	msg = ttk.Label(f, text="", foreground="#c0392b")
	msg.pack(anchor="w")

	def ok(ev=None):
		t = " ".join(title.get().split())
		if not t:
			msg.config(text="Say what it is in a few words first.")
			return
		body = note.get("1.0", "end").strip()
		if where and add_where.get():
			body = (body + "\n\n" if body else "") + f"(In {master}: {where})"
		if send(master, mod_root, t, body, kind.get(), prio.get()):
			w.destroy()
			if status:
				status(f"💬 Request sent to the To Do (Tools › Requests › {master}): {t}")
		else:
			msg.config(text="Couldn't write it to Organisation Master's inbox - is the mod folder right?")
	ttk.Button(bottom, text="Send", command=ok).pack(side="right")
	ttk.Button(bottom, text="Cancel", command=w.destroy).pack(side="right", padx=6)
	e.bind("<Return>", ok)
	w.bind("<Escape>", lambda ev: w.destroy())
	return w
