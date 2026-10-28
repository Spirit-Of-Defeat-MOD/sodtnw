"""Country reviews, like Culture Master's state reviews: Country Master > right-click a country > Flag for Review...
(reasons, a note, a snapshot of the country and a fingerprint of its files) goes through the local inbox into a To Do
task (Country System > Review Countries). Its Selected task panel shows the flag, the snapshot, whether the country's
files changed since it was flagged / approved, Open in Country Master and Approve (which completes the task)."""
import hashlib
import os
import threading
import tkinter as tk
from tkinter import ttk

import ui

PROJECT, GROUP = "Country System", "Review Countries"
REASONS = ("Needs Leaders", "History Check", "Politics / Parties", "Ideas / National Spirits", "Army / OOB", "Flag / Cosmetics",
		   "Needs Lore Update")
LINK = "country_review:"


def ask(root, name, tag):
	"""(reasons, note) or None: what to look at in this country."""
	w = tk.Toplevel(root)
	w.title(f"Flag {tag} for Review")
	w.transient(root)
	w.resizable(False, False)
	f = ttk.Frame(w, padding=12)
	f.pack()
	ttk.Label(f, text=f"Flag {name} ({tag}) for Review", font=("Segoe UI", 11, "bold")).pack(anchor="w")
	ttk.Label(f, text="It becomes a task in To Do Master: Country System > Review Countries.", foreground="#777").pack(anchor="w", pady=(2, 8))
	ticks = {}
	for r in REASONS:
		ticks[r] = tk.BooleanVar(w, value=False)
		ttk.Checkbutton(f, text=r, variable=ticks[r]).pack(anchor="w")
	ttk.Label(f, text="Note (optional)").pack(anchor="w", pady=(8, 0))
	note = tk.Text(f, height=4, width=56, wrap="word")
	note.pack(fill="x")
	out = {}

	def ok():
		out["r"] = ([r for r, v in ticks.items() if v.get()], note.get("1.0", "end").strip())
		w.destroy()
	bf = ttk.Frame(f)
	bf.pack(fill="x", pady=(10, 0))
	ttk.Button(bf, text="Flag for Review", command=ok).pack(side="right")
	ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="right", padx=6)
	w.grab_set()
	w.wait_window()
	return out.get("r")


def files_of(data, tag):
	"""The country's own files (relative): its history file and its characters' files that are its own (TAG*.txt)."""
	c = data.countries.get(tag)
	out = []
	if c is not None and c.history:
		out.append(c.history)
	for cid in getattr(c, "characters", []) if c is not None else []:
		ch = getattr(data, "characters", {}).get(cid)
		rel = getattr(ch, "rel", None)
		if rel and os.path.basename(rel).upper().startswith(tag) and rel not in out:
			out.append(rel)
	return out


def fingerprint(root, files):
	"""A digest of the country's files as saved now (None if none can be read)."""
	h = hashlib.sha1()
	got = False
	for rel in sorted(files or []):
		try:
			with open(os.path.join(root, rel.replace("\\", "/")), "rb") as f:
				h.update(rel.encode("utf-8"))
				h.update(f.read())
			got = True
		except OSError:
			h.update(b"missing:" + rel.encode("utf-8"))
	return h.hexdigest() if got else None


def snapshot(app, tag):
	"""What the country looked like when flagged (shown in the task, so a reviewer sees it without opening anything)."""
	data = app.data
	c = data.countries[tag]
	try:
		ruling = app.ruling(tag)
	except Exception:
		ruling = None
	leaders = []
	for cid in c.characters[:12]:
		ch = data.characters.get(cid)
		if ch is not None:
			leaders.append(data.label(ch.name_key, ch.name_key) if hasattr(data, "label") else ch.name_key)
	ideas = [data.label(i, i) if hasattr(data, "label") else i for i in c.ideas[:12]]
	files = files_of(data, tag)
	return {"tag": tag, "name": data.name(tag, ruling) if hasattr(data, "name") else tag, "ruling": ruling or "",
			"leaders": leaders, "characters": len(c.characters), "ideas": ideas, "states": len(c.states), "cores": len(c.cores),
			"files": files, "fingerprint": fingerprint(app.mod_root, files)}


def tag_of(task):
	link = (task or {}).get("link") or ""
	return link[len(LINK):] if link.startswith(LINK) else None


class CountryReviewPanel(ttk.Frame):
	"""In To Do's Selected task: the country being reviewed."""

	def __init__(self, parent, root, navigate, approve):
		super().__init__(parent)
		self.root_dir, self.navigate, self.approve = root, navigate, approve
		self.task = None
		self.photo = None
		self._job = None
		top = ttk.Frame(self)
		top.pack(fill="x", pady=(4, 2))
		self.flag = tk.Label(top, borderwidth=0)
		self.flag.pack(side="left", padx=(0, 8))
		head = ttk.Frame(top)
		head.pack(side="left", fill="x", expand=True)
		self.title = ttk.Label(head, text="", style="Head.TLabel")
		self.title.pack(anchor="w")
		self.status_lbl = ttk.Label(head, text="", style="Muted.TLabel")
		self.status_lbl.pack(anchor="w")
		self.body = ttk.Label(self, text="", justify="left", wraplength=ui.px(640))
		self.body.pack(anchor="w", pady=(2, 4))
		bar = ttk.Frame(self)
		bar.pack(fill="x", pady=(0, 6))
		ttk.Button(bar, text="Open in Country Master", command=self.open).pack(side="left")
		self.approve_btn = ttk.Button(bar, text="✔ Approve as is", command=self.toggle)
		self.approve_btn.pack(side="left", padx=6)

	def show(self, task):
		tag = tag_of(task)
		self.task = task
		if not tag:
			self.pack_forget()
			return
		if not self.winfo_manager():
			self.pack(fill="x")
		snap = task.get("review_country") or {}
		try:
			import flag_icons
			self.photo = flag_icons.image(self.root_dir, tag, ui.px(40))
		except Exception:
			self.photo = None
		self.flag.config(image=self.photo or "")
		self.title.config(text=f"{snap.get('name') or tag} ({tag})")
		lines = []
		if task.get("review_reasons"):
			lines.append("Review: " + ", ".join(task["review_reasons"]))
		if snap.get("ruling"):
			lines.append(f"Ruling: {snap['ruling']}")
		lines.append(f"States: {snap.get('states', '?')} owned, {snap.get('cores', '?')} cores   ·   Characters: {snap.get('characters', '?')}")
		if snap.get("leaders"):
			lines.append("Characters: " + ", ".join(snap["leaders"]) + (" ..." if snap.get("characters", 0) > len(snap["leaders"]) else ""))
		if snap.get("ideas"):
			lines.append("Ideas: " + ", ".join(snap["ideas"]))
		self.body.config(text="\n".join(lines) + "\n(as it was when flagged)")
		self.status_lbl.config(text="checking its files...")
		self.check()

	def status(self, current):
		"""'approved' / 'changed' / 'open' for the country's files as saved now."""
		task = self.task or {}
		approval = (task.get("review_approvals") or {}).get("country") or {}
		base = approval.get("fingerprint") if approval.get("approved") else (task.get("review_country") or {}).get("fingerprint")
		if approval.get("approved") and (current is None or current == base):
			return "approved"
		if current is not None and base is not None and current != base:
			return "changed"
		return "open"

	def check(self):
		task = self.task
		files = (task.get("review_country") or {}).get("files") or []
		box = {}
		threading.Thread(target=lambda: box.update(fp=fingerprint(self.root_dir, files)), daemon=True).start()

		def wait():
			if not self.winfo_exists() or self.task is not task:
				return
			if "fp" not in box:
				self._job = self.after(150, wait)
				return
			self.current = box["fp"]
			s = self.status(self.current)
			approval = (task.get("review_approvals") or {}).get("country") or {}
			self.status_lbl.config(text={"approved": f"✔ approved by {approval.get('by', '?')} on {(approval.get('when') or '')[:10]}",
									"changed": "? its files changed since it was flagged / approved",
									"open": "waiting for a review"}[s],
							  foreground={"approved": "#2e9d4a", "changed": "#3a7bd5", "open": ""}[s])
			self.approve_btn.config(text={"approved": "✖ Remove approval", "changed": "✔ Approve changes", "open": "✔ Approve as is"}[s])
		wait()

	def toggle(self):
		if self.task is None:
			return
		approved = self.status(getattr(self, "current", None)) == "approved"
		self.approve(self.task, not approved, getattr(self, "current", None))

	def open(self):
		tag = tag_of(self.task)
		if tag:
			import master_links
			self.navigate(master_links.make("country", "country", tag))
