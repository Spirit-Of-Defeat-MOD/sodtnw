"""Dev VCs (To Do Master > 🎙 Dev VCs): the team's voice calls - date, note taker, attendees, a carry-forward agenda,
what was discussed, decisions, action items and notes - and the tasks that come out of them.

Kept in todo_tasks.json ("vcs"). Tasks are proposed (from the Action items, or by Claude / ChatGPT from a note left in
Templates/AI_Notes/Dev_VC/), reviewed one by one, then committed into To Do Master. Only Action items become tasks;
Discussion and Decisions stay as they are, so tentative ideas don't turn into commitments.
"""
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font as tkfont

import ui

APP_NAME = "Organisation Master"
REF = re.compile(r"\bRR-\d{4}\b")
TEXTS = (("discussion", "Discussion", 6), ("decisions", "Decisions", 4), ("actions", "Action items (these become tasks)", 5),
		 ("notes", "Notes", 6))
AI_FOLDER = os.path.join("Templates", "AI_Notes", "Dev_VC")
DENIAL_REASONS = ("Completed", "Changed Opinion", "Duplicate", "Not a Task")


def held(v):
	"""A VC that has happened: anything written in it or proposed from it."""
	return any(v.get(k) for k, *_ in TEXTS) or bool(v.get("proposals"))


def upcoming_vc(data):
	"""The next Dev VC if it's already made: dated after today (today's is the one just held) and nothing written in it yet."""
	import datetime
	today = datetime.date.today().isoformat()
	ahead = [v for v in data.get("vcs", []) if (v.get("date") or "") > today and not held(v)]
	return min(ahead, key=lambda v: (v.get("date", ""), v["id"])) if ahead else None


def future_list(data):
	"""The Future Agenda (team-wide): items with next=True go into the next VC when it's made, the rest wait for later."""
	items = data.setdefault("vc_future_agenda", [])
	for old in data.pop("vc_next_agenda", None) or []:  # (the older 'next VC' list)
		if old.get("text") not in [x.get("text") for x in items]:
			items.append(dict(future_item(old.get("text", ""), "", ""), next=True, **({"from": old["from"]} if old.get("from") else {})))
	return items


def future_item(text, parked_from, by):
	import datetime
	return {"id": "fa-" + os.urandom(4).hex(), "text": text, "parked_from": parked_from, "by": by,
			"when": datetime.datetime.now().replace(microsecond=0).isoformat()}


def bring_to_agenda(data, text, source, by):
	"""Onto the next Dev VC's agenda (the one not held yet; if it isn't made yet, the Future Agenda's Next Dev VC list,
	which it takes in when it's made). Returns where it went."""
	v = upcoming_vc(data)
	if v:
		if text not in [a.get("text") for a in v.get("agenda", [])]:
			v.setdefault("agenda", []).append({"text": text, "done": False, "from": source, "by": by})
		return f"Dev VC {v.get('date', '')}"
	items = future_list(data)
	same = next((x for x in items if x.get("text") == text), None)
	if same:
		same["next"] = True
	else:
		items.append(dict(future_item(text, source, by), next=True, **{"from": source}))
	return "the next Dev VC"


def vc_label(v):
	return f"{v.get('date', '')}  {v.get('title', '') or 'Dev VC'}"


class DevVC(ttk.Frame):
	def __init__(self, parent, todo):
		super().__init__(parent)
		self.todo = todo
		self.app = todo.app
		todo.data.setdefault("vcs", [])
		self.cur = None
		self._job = None
		self._loading = False

		pw = self.panes = ttk.PanedWindow(self, orient="horizontal")
		pw.pack(fill="both", expand=True)
		pw.bind("<Map>", lambda ev: self.after_idle(self._restore_list_width))
		pw.bind("<ButtonRelease-1>", lambda ev: self._save_list_width(), add="+")
		# ---- left: the VCs, like tabs ----
		left = ttk.Frame(pw, width=ui.px(460))
		left.pack_propagate(False)
		pw.add(left, weight=0)
		grip = self.sidebar_grip = ttk.Label(left, text="⋮", width=2, anchor="center", cursor="size_we", style="Muted.TLabel")
		grip.pack(side="right", fill="y", padx=(4, 0))
		grip.bind("<B1-Motion>", self._drag_list_width)
		grip.bind("<ButtonRelease-1>", lambda ev: self._save_list_width())
		sec = ui.Section(left, "Dev VCs", "vc_list", self.app).place_in(fill="both")
		nav = ttk.Frame(sec.body)
		nav.pack(fill="x", pady=(0, 4))
		nav.columnconfigure((0, 1), weight=1, uniform="vc_nav")
		ttk.Button(nav, text="◀ Older", style="Tool.TButton", command=lambda: self.flick(1)).grid(row=0, column=0, sticky="ew", padx=(0, 2))
		ttk.Button(nav, text="Newer ▶", style="Tool.TButton", command=lambda: self.flick(-1)).grid(row=0, column=1, sticky="ew", padx=(2, 0))
		ttk.Button(nav, text="+ New VC", style="Tool.TButton", command=self.new_vc).grid(row=1, column=0, sticky="ew", padx=(0, 2), pady=(4, 0))
		self.delete_button = ttk.Button(nav, text="Delete", style="Tool.TButton", command=self.delete_vc)
		self.delete_button.grid(row=1, column=1, sticky="ew", padx=(2, 0), pady=(4, 0))
		list_area = ttk.Frame(sec.body)
		list_area.pack(fill="both", expand=True)
		list_area.columnconfigure(0, weight=1)
		list_area.rowconfigure(0, weight=1)
		t = self.list = ttk.Treeview(list_area, columns=("sent", "pending", "denied"), show="tree headings", selectmode="browse")
		t.heading("#0", text="Date  /  VC")
		t.column("#0", width=ui.px(210), stretch=True)
		for key, label, width in (("sent", "Sent", 50), ("pending", "Pending", 65), ("denied", "Denied", 60)):
			t.heading(key, text=label)
			t.column(key, width=ui.px(width), anchor="e", stretch=False)
		t.grid(row=0, column=0, sticky="nsew")
		ys = ttk.Scrollbar(list_area, command=t.yview)
		ys.grid(row=0, column=1, sticky="ns")
		xs = ttk.Scrollbar(list_area, orient="horizontal", command=t.xview)
		xs.grid(row=1, column=0, sticky="ew")
		t.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
		t.tag_configure("open", foreground="#b06f00")
		t.tag_configure("resolved", foreground="#969696")
		t.bind("<<TreeviewSelect>>", lambda ev: self.show())
		self.winfo_toplevel().bind("<Prior>", lambda ev: self.winfo_ismapped() and self._not_typing(ev) and self.flick(-1), add="+")
		self.winfo_toplevel().bind("<Next>", lambda ev: self.winfo_ismapped() and self._not_typing(ev) and self.flick(1), add="+")
		ttk.Label(sec.body, text="Orange: proposals to review. Grey: all sent or denied. Drag ⋮ to resize. PgUp / PgDn: switch VC.", style="Muted.TLabel",
				  wraplength=ui.px(280), justify="left").pack(anchor="w", pady=(4, 0))

		# ---- right: the VC ----
		right = ttk.Frame(pw, padding=(8, 0, 0, 0))
		pw.add(right, weight=4)
		self.right = right
		head = ui.Section(right, "Dev VC", "vc_head", self.app, expand=False).place_in(fill="x")
		self.head_sec = head
		self.undo_btn = ttk.Button(head.tools, text="↶ Undo", style="Tool.TButton", command=self.todo.undo)
		self.undo_btn.pack(side="right", padx=2)
		self.todo.register_undo_button(self.undo_btn)
		g = head.body
		self.v = {k: tk.StringVar() for k in ("title", "date", "taker")}
		for i, (k, text, w) in enumerate((("title", "Title", 40), ("date", "Date (YYYY-MM-DD)", 14), ("taker", "Note taker", 18))):
			ttk.Label(g, text=text, style="Muted.TLabel").grid(row=0, column=2 * i, sticky="w", padx=(0 if i == 0 else 14, 4))
			if k == "taker":
				self.taker_box = ttk.Combobox(g, textvariable=self.v[k], width=w, state="readonly", font="TkDefaultFont")
				self.taker_box.grid(row=0, column=2 * i + 1, sticky="w")
			else:
				ttk.Entry(g, textvariable=self.v[k], width=w, font="om_bold" if k == "title" else "TkDefaultFont").grid(row=0, column=2 * i + 1, sticky="w")
			self.v[k].trace_add("write", lambda *_: self.changed())
		ttk.Label(g, text="Attendees", style="Muted.TLabel").grid(row=1, column=0, sticky="nw", pady=(6, 0))
		self.att_frame = ttk.Frame(g)
		self.att_frame.grid(row=1, column=1, columnspan=5, sticky="w", pady=(6, 0))
		self.att = {}

		# agenda (carry forward)
		sec = ui.Section(right, "Agenda", "vc_agenda", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		agenda_area = self._resizable_area(sec, "agenda", 130)
		ui.tool_button(sec.tools, "+ Item", self.add_item).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "↪ Carry forward from the last VC", self.carry_forward).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "✎ Edit", self.agenda_edit).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "⏭ To Future Agenda", self.to_future).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "🗑 Delete", self.remove_item).pack(side="left", padx=2)
		self.agenda = ttk.Treeview(agenda_area, columns=("by", "from"), show="tree headings", height=4, selectmode="extended")
		self.agenda.heading("#0", text="Item  (click ☐ to tick it off; unticked ones can be carried into the next VC)")
		self.agenda.heading("by", text="Put forward by")
		self.agenda.heading("from", text="Carried from")
		self.agenda.column("#0", width=ui.px(440), stretch=True)
		self.agenda.column("by", width=ui.px(110), stretch=False)
		self.agenda.column("from", width=ui.px(150), stretch=False)
		self.agenda.pack(side="left", fill="both", expand=True)
		agenda_scroll = ttk.Scrollbar(agenda_area, command=self.agenda.yview)
		agenda_scroll.pack(side="right", fill="y")
		self.agenda.configure(yscrollcommand=agenda_scroll.set)
		self.agenda.tag_configure("done", foreground="#888")
		self.agenda.tag_configure("carried", foreground="#7b3fa0")
		self.agenda.bind("<ButtonRelease-1>", self.agenda_click)
		self.agenda.bind("<Double-1>", self.agenda_edit)
		self.agenda.bind("<Delete>", lambda ev: self.remove_item())
		self.agenda.bind("<Button-3>", self.agenda_context)
		self.agenda_menu = tk.Menu(self.agenda, tearoff=False)
		for label, cmd in (("✎ Edit...", self.agenda_edit), ("☑ Tick / untick", self.agenda_tick), (None, None),
						   ("▲ Move up", lambda: self.agenda_move(-1)), ("▼ Move down", lambda: self.agenda_move(1)), (None, None),
						   ("⏭ Move to Future Agenda", self.to_future), ("🗑 Delete", self.remove_item)):
			self.agenda_menu.add_separator() if label is None else self.agenda_menu.add_command(label=label, command=cmd)

		# future agenda: parked items for some later VC (the team's, not one VC's)
		sec = ui.Section(right, "Future Agenda", "vc_future_agenda", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.future_sec = sec
		future_area = self._resizable_area(sec, "future_agenda", 100)
		ui.tool_button(sec.tools, "+ Item", self.add_future).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "⇧ Into this VC", self.from_future).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "✎ Edit", self.future_edit).pack(side="left", padx=2)
		ui.tool_button(sec.tools, "🗑 Delete", self.future_delete).pack(side="left", padx=2)
		f = self.future = ttk.Treeview(future_area, columns=("by", "from"), show="tree headings", height=3, selectmode="extended")
		f.heading("#0", text="Item  (Next Dev VC: goes into the next VC you make; Later: parked; double-click to edit)")
		f.heading("by", text="Put forward by")
		f.heading("from", text="From")
		f.column("#0", width=ui.px(440), stretch=True)
		f.column("by", width=ui.px(110), stretch=False)
		f.column("from", width=ui.px(150), stretch=False)
		f.tag_configure("group", font="om_bold")
		f.pack(side="left", fill="both", expand=True)
		future_scroll = ttk.Scrollbar(future_area, command=f.yview)
		future_scroll.pack(side="right", fill="y")
		f.configure(yscrollcommand=future_scroll.set)
		f.bind("<Double-1>", self.future_edit)
		f.bind("<Delete>", lambda ev: self.future_delete())
		f.bind("<Button-3>", self.future_context)
		self.future_menu = tk.Menu(f, tearoff=False)
		for label, cmd in (("⇧ Into this VC's agenda", self.from_future), ("📅 For the next Dev VC", lambda: self.future_next(True)),
						   ("🗄 For later", lambda: self.future_next(False)), ("✎ Edit...", self.future_edit), ("🗑 Delete", self.future_delete)):
			self.future_menu.add_command(label=label, command=cmd)

		# the texts
		self.texts = {}
		for key, title, h in TEXTS:
			sec = ui.Section(right, title, f"vc_{key}", self.app, expand=False).place_in(fill="x", pady=(8, 0))
			area = self._resizable_area(sec, key, h * 20 + 8)
			box = tk.Text(area, height=h, wrap="word", font="om_body", relief="solid", borderwidth=1, undo=True)
			box.pack(side="left", fill="both", expand=True)
			scroll = ttk.Scrollbar(area, command=box.yview)
			scroll.pack(side="right", fill="y")
			box.configure(yscrollcommand=scroll.set)
			box.tag_configure("ref", foreground="#1f5fa8", underline=True)
			box.tag_bind("ref", "<Button-1>", lambda ev, b=box: self.ref_click(b, ev))
			box.tag_bind("ref", "<Enter>", lambda ev, b=box: b.config(cursor="hand2"))
			box.tag_bind("ref", "<Leave>", lambda ev, b=box: b.config(cursor="xterm"))
			box.bind("<KeyRelease>", lambda ev: self.changed())
			self.texts[key] = box
			if key == "actions":
				ttk.Label(sec.body, text="One per line, e.g.  Mike & Globus: fix the Siberian coast #Antarctica !high   "
										 "(Name: = devs, #Project, !low / !high / !critical, under RR-0001 = a sub-task of it)",
						  style="Muted.TLabel", wraplength=ui.px(800), justify="left").pack(anchor="w")

		# tasks: extract, AI note, review, commit
		sec = ui.Section(right, "Tasks from this VC", "vc_tasks", self.app).place_in(fill="both", pady=(8, 0))
		self.tasks_sec = sec
		self.proposal_mode = tk.StringVar(value="task")
		controls = ttk.Frame(sec.body)
		controls.pack(fill="x", pady=(0, 4))
		controls.columnconfigure((0, 1, 2, 3), weight=1, uniform="vc_proposal_controls")
		controls.rowconfigure((0, 1), weight=1, uniform="vc_proposal_rows")
		switch = ttk.Frame(controls)
		switch.grid(row=0, column=0, sticky="w", padx=2, pady=2)
		for value, label in (("task", "Proposed Tasks"), ("idea", "Proposed Ideas")):
			ttk.Radiobutton(switch, text=label, value=value, variable=self.proposal_mode,
							command=self.fill_props).pack(side="left", padx=(0, 8))
		ttk.Button(controls, text="+ Propose idea", command=self.new_proposed_idea).grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
		self.move_button = ttk.Button(controls, text="Move to Ideas", command=self.move_proposals)
		self.move_button.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)
		ttk.Button(controls, text="Remove", command=self.drop).grid(row=0, column=3, sticky="nsew", padx=2, pady=2)
		self.extract_button = ttk.Button(controls, text="⇣ Extract from Action items", command=self.extract)
		self.extract_button.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
		ttk.Button(controls, text="📝 Note for Claude / ChatGPT", command=self.ai_note).grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
		self.ai_load_button = ttk.Button(controls, text="Load the AI's tasks", command=self.ai_load)
		self.ai_load_button.grid(row=1, column=2, sticky="nsew", padx=2, pady=2)
		self.commit_button = ttk.Button(controls, text="✔ Commit ticked", command=self.commit)
		self.commit_button.grid(row=1, column=3, sticky="nsew", padx=2, pady=2)
		pf = ttk.Frame(sec.body, width=ui.px(600), height=ui.px(170))
		pf.pack_propagate(False)
		pf.pack(fill="both", expand=True)
		p = self.props = ttk.Treeview(pf, columns=("pick", "devs", "project", "priority", "category", "state"), show="tree headings", selectmode="extended")
		for col, text, w, st in (("#0", "Proposed task", 300, True), ("pick", "✓", 34, False), ("devs", "Dev(s)", 130, False),
								 ("project", "Project", 120, False), ("priority", "Priority", 70, False), ("category", "Category", 90, False),
								 ("state", "State / reason", 230, False)):
			p.heading(col, text=text)
			p.column(col, width=ui.px(w), stretch=st, anchor="center" if col == "pick" else "w")
		ys = ttk.Scrollbar(pf, command=p.yview)
		xs = ttk.Scrollbar(pf, orient="horizontal", command=p.xview)
		pf.columnconfigure(0, weight=1)
		pf.rowconfigure(0, weight=1)
		pf.grid_propagate(False)
		p.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
		p.grid(row=0, column=0, sticky="nsew")
		ys.grid(row=0, column=1, sticky="ns")
		xs.grid(row=1, column=0, sticky="ew")
		p.tag_configure("committed", foreground="#2e7d32")
		self._denied_font = tkfont.Font(self, **tkfont.nametofont("TkDefaultFont").actual())
		self._denied_font.configure(overstrike=True)
		p.tag_configure("denied", font=self._denied_font, foreground="#888888")
		p.bind("<ButtonRelease-1>", self.prop_click)
		p.bind("<Double-1>", self.prop_double)
		self.prop_menu = tk.Menu(p, tearoff=False)
		self.denial_menu = tk.Menu(self.prop_menu, tearoff=False)
		for reason in DENIAL_REASONS:
			self.denial_menu.add_command(label=reason, command=lambda reason=reason: self.deny_proposals(reason))
		self.prop_menu.add_cascade(label="Deny", menu=self.denial_menu)
		self.prop_menu.add_command(label="Restore denied", command=self.restore_proposals)
		p.bind("<Button-3>", self.prop_context)
		ttk.Label(sec.body, text="Double-click to edit; tick entries to send them. Right-click to deny or restore a proposal. "
								 "Click a sent entry's reference to open it.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
		# the sections below the VC's header can be dragged into another order by their ⠿ grip (kept per VC)
		self.movable = {s.key: s for s in right.pack_slaves() if isinstance(s, ui.Section) and s is not head}
		self.default_order = list(self.movable)
		for s in self.movable.values():
			grip = tk.Label(s.head, text="⠿", background=s.head.cget("background"), foreground=s.title.cget("foreground"),
							font="om_head", cursor="fleur")
			grip.pack(side="left", before=s.arrow, padx=(2, 0))
			grip.bind("<ButtonPress-1>", lambda ev, s=s: self.drag_start(s))
			grip.bind("<B1-Motion>", self.drag_move)
			grip.bind("<ButtonRelease-1>", self.drag_end)
			s.head_extras.append(grip)
		self._dragging = None
		self.empty = ttk.Label(right, text="No Dev VC yet: + New VC (left).", style="Muted.TLabel")
		self.fill()

	# ---------- section order (drag the ⠿ grips; per VC) ----------
	def section_order(self, v=None):
		saved = [k for k in ((v or self.cur) or {}).get("section_order", []) if k in self.movable]
		return saved + [k for k in self.default_order if k not in saved]

	def arrange(self, order=None):
		order = order or self.section_order()
		if [s.key for s in self.right.pack_slaves() if s in self.movable.values()] == order:
			return  # (already so: repacking would make the page flicker)
		for k in order:
			self.movable[k].pack_forget()
		for k in order:
			s = self.movable[k]
			s.pack(**dict(s._pack, expand=s.expand and not s.collapsed))

	def drag_start(self, section):
		self._dragging = section
		self._order = self.section_order()
		section.head.config(cursor="fleur")

	def drag_move(self, ev):
		s = self._dragging
		if s is None:
			return
		y = ev.y_root
		others = [k for k in self._order if k != s.key]
		at = sum(1 for k in others if y > self.movable[k].winfo_rooty() + self.movable[k].head.winfo_height() // 2)
		order = others[:at] + [s.key] + others[at:]
		if order != self._order:
			self._order = order
			self.arrange(order)
			self.right.update_idletasks()

	def drag_end(self, ev):
		s, self._dragging = self._dragging, None
		if s is None or not self.cur:
			return
		order = self._order
		if order != self.section_order():
			self.cur["section_order"] = order
			self.todo.save(feedback=False)
			self.app.set_status("Section order saved for this VC.")

	def _restore_list_width(self):
		if not self.panes.winfo_ismapped():
			return
		width = self.app.config.get("vc_list_width", 460)
		if not isinstance(width, (int, float)) or not 260 <= width <= 2000:
			width = 460
		self._set_list_width(ui.px(width))

	def _set_list_width(self, width):
		maximum = max(ui.px(260), self.panes.winfo_width() - ui.px(400))
		self.panes.sashpos(0, max(ui.px(260), min(maximum, int(width))))

	def _drag_list_width(self, ev):
		self._set_list_width(ev.x_root - self.panes.winfo_rootx())

	def _save_list_width(self):
		if self.panes.winfo_ismapped():
			self.app.config["vc_list_width"] = round(self.panes.sashpos(0) / ui.scale())
			self.app.save_config()

	def _resizable_area(self, section, key, default_height):
		"""A locally remembered editor height; folding the section also hides its handle."""
		heights = self.app.config.setdefault("vc_editor_heights", {})
		minimum = 60
		saved = heights.get(key, default_height)
		if not isinstance(saved, (int, float)) or not minimum <= saved <= 2000:
			saved = default_height
		area = ttk.Frame(section.body, height=ui.px(saved))
		area.pack_propagate(False)
		area.pack(fill="both", expand=True)
		grip = ttk.Label(section.body, text="⋯  Drag to resize · double-click to reset", anchor="center",
						 style="Muted.TLabel", font="om_tiny", cursor="size_ns")
		grip.pack(fill="x")
		drag = {}

		def start(ev):
			drag.update(y=ev.y_root, height=area.winfo_height())

		def move(ev):
			if drag:
				area.configure(height=max(ui.px(minimum), min(ui.px(2000), drag["height"] + ev.y_root - drag["y"])))

		def finish(ev):
			if drag:
				heights[key] = round(int(area.cget("height")) / ui.scale())
				drag.clear()
				self.app.save_config()

		def reset(ev):
			drag.clear()
			area.configure(height=ui.px(default_height))
			heights.pop(key, None)
			self.app.save_config()
			return "break"

		grip.bind("<ButtonPress-1>", start)
		grip.bind("<B1-Motion>", move)
		grip.bind("<ButtonRelease-1>", finish)
		grip.bind("<Double-Button-1>", reset)
		return area

	# ---------- data ----------
	@property
	def vcs(self):
		return self.todo.data.setdefault("vcs", [])

	def vc(self, vid):
		return next((v for v in self.vcs if v["id"] == vid), None)

	def ordered(self):
		return sorted(self.vcs, key=lambda v: (v.get("date", ""), v["id"]), reverse=True)

	def _not_typing(self, ev):
		return ev.widget.winfo_class() not in ("Text", "Entry", "TEntry", "TCombobox")

	def fill(self, keep=None):
		t = self.list
		keep = keep or (self.cur["id"] if self.cur else None)
		t.delete(*t.get_children())
		for v in self.ordered():
			proposals = v.get("proposals", [])
			pend = sum(1 for p in proposals if p.get("state") not in ("committed", "denied"))
			done = sum(1 for p in proposals if p.get("state") == "committed")
			denied = sum(1 for p in proposals if p.get("state") == "denied")
			tags = ("open",) if pend else ("resolved",) if proposals else ()
			t.insert("", "end", iid=v["id"], text=vc_label(v), values=(done, pend, denied), tags=tags)
		ui.stripe(t)
		self.taker_box.config(values=self.todo.dev_names())
		if keep and t.exists(keep):
			t.selection_set(keep)
		elif t.get_children():
			t.selection_set(t.get_children()[0])
		else:
			self.cur = None
			self.show()

	def flick(self, d):
		ids = list(self.list.get_children())
		if not ids:
			return
		i = ids.index(self.cur["id"]) if self.cur and self.cur["id"] in ids else 0
		j = max(0, min(len(ids) - 1, i + d))
		self.list.selection_set(ids[j])
		self.list.see(ids[j])

	# ---------- a VC on the right ----------
	def show(self):
		self.flush()
		sel = self.list.selection()
		self.cur = self.vc(sel[0]) if sel else None
		v = self.cur
		self.fill_future()
		if v is None:
			self.empty.pack(anchor="w", pady=20)
			return
		self.empty.pack_forget()
		self.arrange()
		self._loading = True
		self.head_sec.title.config(text=f"Dev VC  ·  {vc_label(v)}")
		self.v["title"].set(v.get("title", ""))
		self.v["date"].set(v.get("date", ""))
		self.v["taker"].set(v.get("note_taker", ""))
		names = self.todo.dev_names()
		if list(self.att) != names:  # (the ticks are only remade when the devs change: no flicker on every refresh)
			for w in self.att_frame.winfo_children():
				w.destroy()
			self.att = {}
			for i, n in enumerate(names):
				self.att[n] = tk.BooleanVar(value=False)
				ttk.Checkbutton(self.att_frame, text=n, variable=self.att[n], command=self.changed).grid(row=0, column=i, sticky="w", padx=(0, 10))
		for n, var in self.att.items():
			if var.get() != (n in v.get("attendees", [])):
				var.set(n in v.get("attendees", []))
		same_vc = getattr(self, "_shown_id", None) == v["id"]
		self._shown_id = v["id"]
		for key, box in self.texts.items():
			text = v.get(key, "")
			if same_vc and box.get("1.0", "end-1c") == text:
				continue  # (others' changes came in elsewhere: this box, its cursor and undo stay as they are)
			where, top = box.index("insert"), box.yview()[0]
			box.delete("1.0", "end")
			box.insert("1.0", text)
			box.edit_reset()
			if same_vc:  # (their text came in while you're here: your cursor and scroll stay put)
				box.mark_set("insert", where)
				box.yview_moveto(top)
			self.mark_refs(box)
		self.fill_agenda()
		self.fill_props()
		self._loading = False

	def changed(self):
		if self._loading or not self.cur:
			return
		if self._job:
			self.after_cancel(self._job)
		self._job = self.after(900, self.flush)

	def refresh_remote(self):
		"""Others' changes came in: the list again and the open VC shown again in place (its unsaved typing was already
		flushed into the data before the merge; the old VC object is dropped so it's never flushed over the merged one)."""
		vc_id = self.cur and self.cur["id"]
		if self._job:
			self.after_cancel(self._job)
			self._job = None
		self.cur = None
		self.fill(keep=vc_id)
		self.show()  # (now, not when the list's select event comes round: nothing typed in between is lost)

	def flush(self):
		if self._job:
			self.after_cancel(self._job)
			self._job = None
		v = self.cur
		if v is None or self._loading:
			return
		new = {"title": self.v["title"].get().strip(), "date": self.v["date"].get().strip(), "note_taker": self.v["taker"].get(),
			   "attendees": [n for n, b in self.att.items() if b.get()]}
		for key, box in self.texts.items():
			new[key] = box.get("1.0", "end").rstrip()
			self.mark_refs(box)
		if any(v.get(k) != x for k, x in new.items()):
			relabel = new["title"] != v.get("title") or new["date"] != v.get("date")
			import time
			for key in self.texts:  # (who wrote each text last and when: live sync tells a stale copy from a real edit)
				if new[key] != v.get(key, ""):
					v.setdefault("edited", {})[key] = {"by": self.todo.me.get(), "when": round(time.time(), 3)}
			v.update(new)
			self.todo.save(feedback=False)
			if relabel and self.list.exists(v["id"]):
				self.list.item(v["id"], text=vc_label(v))
				self.head_sec.title.config(text=f"Dev VC  ·  {vc_label(v)}")

	def close(self):
		self.flush()

	# ---------- task references: click to go to the task ----------
	def mark_refs(self, box):
		box.tag_remove("ref", "1.0", "end")
		text = box.get("1.0", "end")
		for m in REF.finditer(text):
			box.tag_add("ref", f"1.0+{m.start()}c", f"1.0+{m.end()}c")

	def ref_click(self, box, ev):
		i = box.index(f"@{ev.x},{ev.y}")
		for a, b in zip(box.tag_ranges("ref")[0::2], box.tag_ranges("ref")[1::2]):
			if box.compare(a, "<=", i) and box.compare(i, "<", b):
				self.open_task(box.get(a, b))
				return "break"

	def open_task(self, ref):
		if not self.todo.task(ref):
			messagebox.showinfo(APP_NAME, f"{ref} isn't in To Do Master.")
			return
		self.flush()
		self.todo.mode.set(self.app.config.get("todo_last_mode", "dev"))
		self.todo.mode_changed()
		self.todo.go_to(ref)

	# ---------- new / delete ----------
	def new_vc(self):
		self.flush()
		prev = self.ordered()[0] if self.vcs else None
		import datetime
		v = {"id": f"vc{len(self.vcs) + 1}-{os.urandom(2).hex()}", "title": "Dev VC", "date": datetime.date.today().isoformat(),
			 "note_taker": self.todo.me.get(), "attendees": [self.todo.me.get()], "agenda": [], "proposals": []}
		for key, *_ in TEXTS:
			v[key] = ""
		if (prev or {}).get("section_order"):  # (starts with the last VC's layout)
			v["section_order"] = list(prev["section_order"])
		left =[a for a in (prev or {}).get("agenda", []) if not a.get("done")]
		if left and messagebox.askyesno(APP_NAME, f"Carry forward the {len(left)} unresolved agenda item{'s' if len(left) != 1 else ''} "
												  f"of {vc_label(prev)}?"):
			v["agenda"] = [self.carried(a, a.get("from") or prev.get("date", "")) for a in left]
		items = future_list(self.todo.data)  # (brought to the agenda before this VC was made)
		have = {a["text"] for a in v["agenda"]}
		for it in [x for x in items if x.get("next")]:
			items.remove(it)
			if it["text"] not in have:
				v["agenda"].append(self.carried(it, it.get("from") or "Future Agenda"))
			self.relink_idea(it, f"Dev VC {v['date']}")
		self.vcs.append(v)
		self.todo.save()
		self.cur = None
		self.fill()
		self.list.selection_set(v["id"])

	def delete_vc(self):
		v = self.cur
		if v and messagebox.askyesno(APP_NAME, f"Delete {vc_label(v)} and its notes? (Tasks already committed stay.)"):
			self.vcs.remove(v)
			self.cur = None
			self.todo.save()
			self.fill()

	# ---------- agenda ----------
	def fill_agenda(self):
		a = self.agenda
		keep = a.selection()
		a.delete(*a.get_children())
		for i, it in enumerate((self.cur or {}).get("agenda", [])):
			a.insert("", "end", iid=str(i), text=("☑ " if it.get("done") else "☐ ") + it.get("text", ""), values=(it.get("by", ""), it.get("from", "")),
					 tags=("done",) if it.get("done") else ("carried",) if it.get("from") else ())
		a.config(height=max(3, min(10, len(a.get_children()) + 1)))
		a.selection_set([k for k in keep if a.exists(k)])

	def agenda_click(self, ev):
		row = self.agenda.identify_row(ev.y)
		if row and self.agenda.identify_column(ev.x) == "#0" and ev.x < ui.px(40):
			it = self.cur["agenda"][int(row)]
			it["done"] = not it.get("done")
			self.todo.save()
			self.fill_agenda()

	def agenda_rows(self):
		return sorted((int(r) for r in self.agenda.selection()), key=int) if self.cur else []

	def agenda_context(self, ev):
		row = self.agenda.identify_row(ev.y)
		if not row:
			return
		if row not in self.agenda.selection():
			self.agenda.selection_set(row)
		self.agenda.update_idletasks()
		self._owner_sub(self.agenda_menu, lambda: [self.cur["agenda"][r] for r in self.agenda_rows()])
		self.agenda_menu.tk_popup(ev.x_root, ev.y_root)

	def _owner_sub(self, menu, items):
		"""(Re)makes the menu's last entry, the 'Put forward by' cascade, for the current dev list."""
		if menu.index("end") is not None and menu.type("end") == "cascade":
			menu.delete("end")
		self.owner_menu(menu, items)

	def agenda_edit(self, ev=None):
		row = self.agenda.identify_row(ev.y) if ev is not None else None
		rows = [int(row)] if row else self.agenda_rows()[:1]
		if not rows:
			return
		it = self.cur["agenda"][rows[0]]
		s = simpledialog.askstring("Agenda item", "Item:", initialvalue=it.get("text", ""), parent=self)
		if s is not None and s.strip() and s.strip() != it.get("text"):
			it["text"] = s.strip()
			self.todo.save()
			self.fill_agenda()

	def agenda_tick(self):
		rows = self.agenda_rows()
		if rows:
			done = not all(self.cur["agenda"][r].get("done") for r in rows)
			for r in rows:
				self.cur["agenda"][r]["done"] = done
			self.todo.save()
			self.fill_agenda()

	def agenda_move(self, d):
		rows = self.agenda_rows()
		items = (self.cur or {}).get("agenda", [])
		if not rows or not (0 <= rows[0] + d and rows[-1] + d < len(items)):
			return
		picked = [items[r] for r in rows]
		for r in reversed(rows):
			del items[r]
		at = rows[0] + d
		items[at:at] = picked
		self.todo.save()
		self.fill_agenda()
		self.agenda.selection_set([str(at + i) for i in range(len(picked))])

	def relink_idea(self, item, where):
		"""An item brought from Ideas: keep its idea's 'on the agenda' note right ('' = off the agenda)."""
		if item.get("from") != "Ideas":
			return
		import datetime
		for idea in self.todo.data.get("ideas", []):
			if item.get("text", "").startswith(f"💡 Idea: {idea.get('title', '')} ("):
				if where:
					idea["agenda"] = where
				else:
					idea.pop("agenda", None)
				idea["updated"] = datetime.datetime.now().replace(microsecond=0).isoformat()
				return

	def carried(self, item, source):
		"""An agenda item made from another (carried, parked, brought back): it keeps who put it forward."""
		return {"text": item.get("text", ""), "done": False, "from": source, "by": item.get("by", "")}

	# ---------- future agenda (the next VC's items before it's made, and parked items for later) ----------
	@property
	def future_items(self):
		return future_list(self.todo.data)

	def fill_future(self):
		f = self.future
		keep = f.selection()
		f.delete(*f.get_children())
		groups = (("next", "📅 Next Dev VC", [x for x in self.future_items if x.get("next")]),
				  ("later", "🗄 Later", [x for x in self.future_items if not x.get("next")]))
		for key, label, items in groups:
			f.insert("", "end", iid=key, text=f"{label} ({len(items)})", open=True, tags=("group",))
			for it in items:
				f.insert(key, "end", iid=it["id"], text=it.get("text", ""), values=(it.get("by", ""), it.get("parked_from") or it.get("from", "")))
		f.config(height=max(3, min(10, len(self.future_items) + 2)))
		self.future_sec.title.config(text=f"Future Agenda ({len(self.future_items)})" if self.future_items else "Future Agenda")
		f.selection_set([k for k in keep if f.exists(k)])

	def future_next(self, nxt):
		for it in self.future_rows():
			it["next"] = nxt
			self.relink_idea(it, "the next Dev VC" if nxt else "the Future Agenda")
		self.todo.save()
		self.fill_future()

	def future_rows(self):
		ids = set(self.future.selection())
		for group in ("next", "later"):  # (a group row picked: all of it)
			if group in ids:
				ids |= set(self.future.get_children(group))
		return [it for it in self.future_items if it["id"] in ids]

	def owner_menu(self, menu, items):
		"""A 'Put forward by' cascade setting who owns the picked agenda items."""
		sub = tk.Menu(menu, tearoff=False)
		for n in self.todo.dev_names():
			sub.add_command(label=n, command=lambda n=n: self.set_owner(items(), n))
		menu.add_cascade(label="👤 Put forward by", menu=sub)
		return sub

	def set_owner(self, items, name):
		for it in items:
			it["by"] = name
		self.todo.save()
		self.fill_agenda()
		self.fill_future()

	def future_context(self, ev):
		row = self.future.identify_row(ev.y)
		if not row:
			return
		if row not in self.future.selection():
			self.future.selection_set(row)
		self.future.update_idletasks()
		self._owner_sub(self.future_menu, self.future_rows)
		self.future_menu.tk_popup(ev.x_root, ev.y_root)

	def _future_item(self, text, parked_from, src=None):
		it = future_item(text, parked_from, (src or {}).get("by") or self.todo.me.get())
		if src and src.get("from"):
			it["from"] = src["from"]
		return it

	def to_future(self):
		rows = self.agenda_rows()
		if not rows:
			return
		items = self.cur["agenda"]
		have = {it.get("text") for it in self.future_items}
		for it in [items[r] for r in rows]:
			items.remove(it)
			if it.get("text") not in have:
				self.future_items.append(self._future_item(it.get("text", ""), vc_label(self.cur), it))
			self.relink_idea(it, "the Future Agenda")
		self.todo.save()
		self.agenda.selection_set([])
		self.fill_agenda()
		self.fill_future()
		self.app.set_status(f"{len(rows)} item{'s' if len(rows) != 1 else ''} moved to the Future Agenda.")

	def from_future(self):
		picked = self.future_rows()
		if not picked:
			return
		if not self.cur:
			messagebox.showinfo(APP_NAME, "Pick a VC (left) to bring them into.")
			return
		have = {a.get("text") for a in self.cur.get("agenda", [])}
		for it in picked:
			self.future_items.remove(it)
			if it.get("text") not in have:
				self.cur.setdefault("agenda", []).append(self.carried(it, it.get("from") or "Future Agenda"))
			self.relink_idea(it, f"Dev VC {self.cur.get('date', '')}")
		self.todo.save()
		self.fill_agenda()
		self.fill_future()

	def add_future(self):
		s = simpledialog.askstring("Future Agenda", "What should a later VC talk about?", parent=self)
		if s and s.strip():
			self.future_items.append(dict(self._future_item(s.strip(), ""), next="next" in self.future.selection() or any(
				x.get("next") for x in self.future_rows())))
			self.todo.save()
			self.fill_future()

	def future_edit(self, ev=None):
		row = self.future.identify_row(ev.y) if ev is not None else None
		it = next((x for x in self.future_items if x["id"] == row), None) if row else (self.future_rows() or [None])[0]
		if it is None:
			return
		s = simpledialog.askstring("Future Agenda", "Item:", initialvalue=it.get("text", ""), parent=self)
		if s is not None and s.strip() and s.strip() != it.get("text"):
			it["text"] = s.strip()
			self.todo.save()
			self.fill_future()

	def future_delete(self):
		picked = self.future_rows()
		if not picked or not messagebox.askyesno(APP_NAME, f"Delete {len(picked)} Future Agenda item{'s' if len(picked) != 1 else ''}?"):
			return
		for it in picked:
			self.future_items.remove(it)
			self.relink_idea(it, "")
		self.todo.save()
		self.fill_future()

	def add_item(self):
		if not self.cur:
			return
		s = simpledialog.askstring("Agenda item", "What's on the agenda?", parent=self)
		if s and s.strip():
			self.cur.setdefault("agenda", []).append({"text": s.strip(), "done": False, "from": "", "by": self.todo.me.get()})
			self.todo.save()
			self.fill_agenda()

	def remove_item(self):
		rows = self.agenda_rows()
		if not rows or not messagebox.askyesno(APP_NAME, f"Delete {len(rows)} agenda item{'s' if len(rows) != 1 else ''}? "
														 "(⏭ To Future Agenda keeps them for later instead.)"):
			return
		for r in reversed(rows):
			self.relink_idea(self.cur["agenda"].pop(r), "")
		self.todo.save()
		self.agenda.selection_set([])
		self.fill_agenda()

	def carry_forward(self):
		"""The unticked agenda items of the VC before this one, into this one."""
		v = self.cur
		if not v:
			return
		older = [x for x in self.ordered() if (x.get("date", ""), x["id"]) < (v.get("date", ""), v["id"])]
		if not older:
			messagebox.showinfo(APP_NAME, "There's no earlier VC.")
			return
		prev = older[0]
		have = {a["text"] for a in v.get("agenda", [])}
		left = [a for a in prev.get("agenda", []) if not a.get("done") and a["text"] not in have]
		for a in left:
			v.setdefault("agenda", []).append(self.carried(a, a.get("from") or prev.get("date", "")))
		self.todo.save()
		self.fill_agenda()
		self.app.set_status(f"{len(left)} unresolved item{'s' if len(left) != 1 else ''} carried from {vc_label(prev)}.")

	# ---------- proposed tasks: extract, AI, review, commit ----------
	def parse_action(self, line):
		"""'Mike & Globus: fix the coast #Antarctica !high under RR-0001' -> a proposed task."""
		devs_all = {d.lower(): d for d in self.todo.dev_names()}
		projects = {p.lower(): p for p in self.todo.project_names()}
		p = {"title": "", "devs": [], "project": "", "priority": "Normal", "category": "", "parent": "", "note": "", "state": "proposed"}
		m = re.match(r"^\s*(?:[-*•]\s*)?([^:]{1,60}):\s*(.+)$", line)
		if m and all(n.strip().lstrip("@").lower() in devs_all for n in re.split(r"\s*(?:&|,|and|\+)\s*", m.group(1)) if n.strip()):
			p["devs"] = [devs_all[n.strip().lstrip("@").lower()] for n in re.split(r"\s*(?:&|,|and|\+)\s*", m.group(1)) if n.strip()]
			line = m.group(2)
		for at in re.findall(r"@(\w+)", line):
			if at.lower() in devs_all and devs_all[at.lower()] not in p["devs"]:
				p["devs"].append(devs_all[at.lower()])
		line = re.sub(r"@\w+", lambda mm: mm.group(0)[1:], line)
		m = re.search(r"#([\w][\w \-]*?)(?=\s+!|\s+under\b|$|\s+#)", line)
		if m and m.group(1).strip().lower() in projects:
			p["project"] = projects[m.group(1).strip().lower()]
			line = line.replace(m.group(0), "")
		m = re.search(r"!(low|normal|high|critical)\b", line, re.I)
		if m:
			p["priority"] = m.group(1).capitalize()
			line = line.replace(m.group(0), "")
		m = re.search(r"\bunder\s+(RR-\d{4})\b", line, re.I)
		if m:
			p["parent"] = m.group(1).upper()
			par = self.todo.task(p["parent"])
			if par and not p["project"]:
				p["project"] = par.get("project", "")
			line = line.replace(m.group(0), "")
		p["title"] = re.sub(r"\s{2,}", " ", line).strip(" -:")
		return p

	def extract(self):
		v = self.cur
		if not v:
			return
		self.flush()
		self.proposal_mode.set("task")
		have = {p["title"].lower() for p in v.get("proposals", []) if p.get("kind", "task") == "task"}
		new = [self.parse_action(l) for l in v.get("actions", "").splitlines() if l.strip()]
		unique = []
		for proposal in new:
			if proposal["title"] and proposal["title"].lower() not in have:
				unique.append(proposal)
				have.add(proposal["title"].lower())
		new = unique
		v.setdefault("proposals", []).extend(new)
		self.todo.save()
		self.fill_props()
		self.fill()
		self.app.set_status(f"{len(new)} proposed task{'s' if len(new) != 1 else ''} from the Action items: review them, then Commit ticked."
							if new else "Nothing new in the Action items.")

	def ai_paths(self):
		v = self.cur
		folder = os.path.join(self.app.mod_root, AI_FOLDER)
		base = f"VC_{v.get('date', '')}_{re.sub(r'[^A-Za-z0-9]+', '_', v.get('title', '') or 'Dev_VC').strip('_')}_{v['id']}"
		idea = self.proposal_mode.get() == "idea"
		return folder, os.path.join(folder, base + ("_ideas.md" if idea else ".md")), os.path.join(folder, base + ("_ideas.json" if idea else "_tasks.json"))

	def ai_note(self):
		"""A note Claude / ChatGPT can read to propose the tasks (they write them back next to it)."""
		v = self.cur
		if not v:
			return
		self.flush()
		folder, md, js = self.ai_paths()
		os.makedirs(folder, exist_ok=True)
		devs = ", ".join(self.todo.dev_names())
		projects = ", ".join(self.todo.project_names())
		cats = ", ".join(self.todo.data["categories"])
		open_tasks = "\n".join(f"- {t['ref']} {t.get('title', '')} ({', '.join(t.get('devs') or []) or 'nobody'}; {t.get('project') or 'no project'})"
							   for t in self.todo.tasks if not t.get("archived") and t.get("status") not in ("Completed", "Not Possible")
							   and not str(t.get("link", "")).startswith("music_"))[:12000]
		agenda = "\n".join(("[x] " if a.get("done") else "[ ] ") + a["text"] for a in v.get("agenda", []))
		text = f"""# Dev VC: {vc_label(v)}

**For Claude / ChatGPT.** Read this VC and propose the To Do Master tasks it calls for. Write them to
`{os.path.basename(js)}` next to this file (a JSON list, format below). Organisation Master > To Do Master > 🎙 Dev VCs >
"Load the AI's tasks" reads it; the team reviews each task before committing it.

Rules:
- Make tasks only from **Action items**, and from **Decisions** that clearly need work. Don't turn ideas that were only
  discussed into tasks.
- Don't repeat tasks that already exist (the open tasks are listed below) - mention them in "note" instead.
- devs: only from: {devs}. project: one of: {projects} (or ""). category: one of: {cats}. priority: Low / Normal / High / Critical.
- parent: an existing task's RR number when it's a sub-task of it (or "").

Format:
```json
[{{"title": "Fix the Siberian coast", "devs": ["Mike"], "project": "Antarctica", "priority": "High", "category": "Map",
  "parent": "RR-0001", "note": "Why / where it came from in the VC"}}]
```

## The VC
- Date: {v.get('date', '')}
- Note taker: {v.get('note_taker', '')}
- Attendees: {', '.join(v.get('attendees', []))}

### Agenda
{agenda or '-'}

### Discussion
{v.get('discussion', '') or '-'}

### Decisions
{v.get('decisions', '') or '-'}

### Action items
{v.get('actions', '') or '-'}

### Notes
{v.get('notes', '') or '-'}

## Open tasks already in To Do Master
{open_tasks or '-'}
"""
		if self.proposal_mode.get() == "idea":
			categories = ", ".join(self.todo.idea_pane.categories)
			context = text[text.index("## The VC"):text.index("## Open tasks already in To Do Master")]
			existing = "\n".join("- " + i.get("title", "") for i in self.todo.data.get("ideas", []))
			text = (f"# Proposed ideas from {vc_label(v)}\n\nRead the VC below and propose ideas for the Ideas area. "
					f"Write a JSON list to `{os.path.basename(js)}` next to this note. Use Load the AI's ideas to review them.\n\n"
					"Capture tentative suggestions and possibilities from Discussion and Notes. Do not turn committed action items into ideas. "
					"Do not repeat existing ideas. Do not invent commitments or owners.\n"
					f"category: one of {categories}; project: one of {projects} or an empty string.\n"
					'Format: [{"title": "Idea title", "category": "Misc", "project": "", "note": "Context and source"}]\n\n'
					+ context + "\n## Existing ideas\n" + (existing or "-") + "\n")
		with open(md, "w", encoding="utf-8") as f:
			f.write(text)
		self.app.log(os.path.relpath(md, self.app.mod_root))
		self.clipboard_clear()
		self.clipboard_append(text)
		messagebox.showinfo(APP_NAME, f"Note written (and copied, to paste into ChatGPT):\n{os.path.relpath(md, self.app.mod_root)}\n\n"
									  f"Ask Claude to fill it in, or paste ChatGPT's answer with {self.ai_load_button.cget('text')}.")

	def ai_load(self):
		"""The AI's tasks: its _tasks.json next to the note, or pasted text (JSON, or one task per line)."""
		v = self.cur
		if not v:
			return
		kind = self.proposal_mode.get()
		label = "ideas" if kind == "idea" else "tasks"
		_, _, js = self.ai_paths()
		items = None
		if os.path.exists(js):
			try:
				items = json.load(open(js, encoding="utf-8"))
			except ValueError as ex:
				messagebox.showerror(APP_NAME, f"{os.path.basename(js)} doesn't read: {ex}")
				return
		else:
			w = tk.Toplevel(self)
			w.title(f"Paste the AI's {label}")
			w.transient(self.winfo_toplevel())
			f = ttk.Frame(w, padding=12)
			f.pack()
			ttk.Label(f, text="Paste the AI's answer (its JSON list, or one task per line like the Action items):").pack(anchor="w")
			box = tk.Text(f, width=80, height=16, font="om_mono")
			box.pack(pady=6)
			box.focus_set()
			out = {}
			ttk.Button(f, text="Load", command=lambda: (out.update(t=box.get("1.0", "end")), w.destroy())).pack(anchor="e")
			w.grab_set()
			self.wait_window(w)
			text = out.get("t", "").strip()
			if not text:
				return
			m = re.search(r"\[.*\]", text, re.S)
			try:
				items = json.loads(m.group(0)) if m else None
			except ValueError:
				items = None
			if items is None:
				items = ([{"title": l.strip().lstrip("-*• ")} for l in text.splitlines() if l.strip()]
						 if kind == "idea" else [self.parse_action(l) for l in text.splitlines() if l.strip()])
		have = {p["title"].lower() for p in v.get("proposals", []) if p.get("kind", "task") == kind}
		names = set(self.todo.dev_names())
		new = []
		for it in items if isinstance(items, list) else []:
			if not isinstance(it, dict) or not str(it.get("title", "")).strip() or str(it["title"]).strip().lower() in have:
				continue
			if kind == "idea":
				cats = self.todo.idea_pane.categories
				new.append({"title": str(it["title"]).strip(), "kind": "idea", "state": "proposed", "from_ai": True,
							"category": it.get("category") if it.get("category") in cats else self.default_idea_category(),
							"project": it.get("project", "") if it.get("project", "") in self.todo.project_names() else "",
							"note": str(it.get("note", it.get("text", "")))})
				have.add(str(it["title"]).strip().lower())
				continue
			pri = str(it.get("priority", "Normal")).capitalize()
			new.append({"title": str(it["title"]).strip(), "devs": [d for d in it.get("devs", []) if d in names],
						"project": it.get("project", "") if it.get("project", "") in self.todo.project_names() else "",
						"priority": pri if pri in ("Low", "Normal", "High", "Critical") else "Normal",
						"category": it.get("category", "") if it.get("category", "") in self.todo.data["categories"] else "",
						"parent": it.get("parent", "") if self.todo.task(it.get("parent", "")) else "", "note": str(it.get("note", "")),
						"state": "proposed", "from_ai": True})
			have.add(str(it["title"]).strip().lower())
		v.setdefault("proposals", []).extend(new)
		self.todo.save()
		self.fill_props()
		self.fill()
		self.app.set_status(f"{len(new)} proposed {label} from the AI: review them before sending.")

	def proposals(self):
		kind = self.proposal_mode.get()
		return [(i, x) for i, x in enumerate((self.cur or {}).get("proposals", [])) if x.get("kind", "task") == kind]

	def selected_proposals(self):
		selected = set(self.props.selection())
		return [x for i, x in self.proposals() if str(i) in selected]

	def prop_context(self, ev):
		row = self.props.identify_row(ev.y)
		if not row or not self.cur:
			return "break"
		if row not in self.props.selection():
			self.props.selection_set(row)
		self.props.focus(row)
		selected = self.selected_proposals()
		self.prop_menu.entryconfigure("Deny", state="normal" if any(x.get("state") != "committed" for x in selected) else "disabled")
		self.prop_menu.entryconfigure("Restore denied", state="normal" if any(x.get("state") == "denied" for x in selected) else "disabled")
		ui.theme_widget(self.prop_menu)
		ui.theme_widget(self.denial_menu)
		try:
			self.prop_menu.tk_popup(ev.x_root, ev.y_root)
		finally:
			self.prop_menu.grab_release()
		return "break"

	def default_idea_category(self):
		cats = self.todo.idea_pane.categories
		return "Misc" if "Misc" in cats else (cats[0] if cats else "")

	def deny_proposals(self, reason):
		if reason not in DENIAL_REASONS:
			return
		for x in self.selected_proposals():
			if x.get("state") != "committed":
				x.update(state="denied", denial_reason=reason, pick=False)
		self.todo.save()
		self.fill_props()
		self.fill()

	def restore_proposals(self):
		for x in self.selected_proposals():
			if x.get("state") == "denied":
				x.update(state="proposed", pick=True)
				x.pop("denial_reason", None)
		self.todo.save()
		self.fill_props()
		self.fill()

	def move_proposals(self):
		kind = "task" if self.proposal_mode.get() == "idea" else "idea"
		for x in self.selected_proposals():
			if x.get("state") != "committed":
				x["kind"] = kind
				if kind == "idea":
					x["category"] = self.default_idea_category()
				elif x.get("category") not in self.todo.data["categories"]:
					x["category"] = ""
		self.todo.save()
		self.proposal_mode.set(kind)
		self.fill_props()

	def new_proposed_idea(self):
		if self.cur:
			self.proposal_mode.set("idea")
			self.fill_props()
			self.edit_idea_proposal({"title": "", "kind": "idea", "state": "proposed",
								 "category": self.default_idea_category()}, new=True)

	def edit_idea_proposal(self, proposal, new=False):
		vc = self.cur
		w = tk.Toplevel(self)
		w.title("Proposed idea")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack(fill="both", expand=True)
		values = {}
		for row, (key, label, choices) in enumerate((("title", "Title", None),
				("category", "Idea category", self.todo.idea_pane.categories),
				("project", "Project", [""] + self.todo.project_names()))):
			ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
			values[key] = tk.StringVar(value=proposal.get(key, ""))
			if choices is None:
				ttk.Entry(f, textvariable=values[key], width=65).grid(row=row, column=1, sticky="ew")
			else:
				ttk.Combobox(f, textvariable=values[key], values=choices, state="readonly", width=62).grid(row=row, column=1, sticky="ew")
		ttk.Label(f, text="Context / notes").grid(row=3, column=0, sticky="nw", pady=4)
		note = tk.Text(f, width=65, height=8, wrap="word", font="om_body")
		note.grid(row=3, column=1)
		note.insert("1.0", proposal.get("note", ""))

		def save():
			if not values["title"].get().strip():
				return
			proposal.update({k: v.get().strip() for k, v in values.items()})
			proposal["note"] = note.get("1.0", "end").strip()
			if new:
				vc.setdefault("proposals", []).append(proposal)
			self.todo.save()
			w.destroy()
			self.fill_props()
			self.fill()

		ttk.Button(f, text="Save proposal", command=save).grid(row=4, column=1, sticky="e", pady=(8, 0))
		w.grab_set()

	def fill_props(self):
		p = self.props
		selected = p.selection()
		idea = self.proposal_mode.get() == "idea"
		self.tasks_sec.title.config(text="Ideas from this VC" if idea else "Tasks from this VC")
		p.heading("#0", text="Proposed idea" if idea else "Proposed task")
		p.configure(displaycolumns=("pick", "project", "category", "state") if idea else ("pick", "devs", "project", "priority", "category", "state"))
		self.move_button.configure(text="Move to Tasks" if idea else "Move to Ideas")
		self.ai_load_button.configure(text="Load the AI's ideas" if idea else "Load the AI's tasks")
		self.commit_button.configure(text="✔ Send ticked to Ideas" if idea else "✔ Commit ticked")
		if idea:
			self.extract_button.grid_remove()
		elif not self.extract_button.winfo_manager():
			self.extract_button.grid()
		self._denied_font.configure(**tkfont.nametofont("TkDefaultFont").actual())
		self._denied_font.configure(overstrike=True)
		p.delete(*p.get_children())
		for i, x in self.proposals():
			done = x.get("state") == "committed"
			denied = x.get("state") == "denied"
			p.insert("", "end", iid=str(i), text=("🤖 " if x.get("from_ai") else "") + x["title"],
					 values=("✔" if done else "✕" if denied else "☑" if x.get("pick", True) else "☐", ", ".join(x.get("devs", [])) or "-", x.get("project", "") or "-",
							 x.get("priority", "Normal"), x.get("category", ""),
							 "Denied: " + x.get("denial_reason", "") if denied else ("Open idea" if idea else x.get("ref", "")) if done else ("under " + x["parent"] if x.get("parent") else "")),
					 tags=("denied",) if denied else ("committed",) if done else ())
		p.selection_set([i for i in selected if p.exists(i)])
		ui.stripe(p)
		n = sum(1 for _, x in self.proposals() if x.get("state") not in ("committed", "denied"))
		self.tasks_sec.set_count(f"{n} to review" if n else "")

	def prop_click(self, ev):
		row = self.props.identify_row(ev.y)
		if not row:
			return
		x = self.cur["proposals"][int(row)]
		col = self.props.identify_column(ev.x)
		if not col:
			return
		column = self.props.column(col, "id")
		if column == "pick" and x.get("state") not in ("committed", "denied"):
			x["pick"] = not x.get("pick", True)
			self.todo.save()
			self.fill_props()
		elif column == "state" and x.get("state") == "committed":
			self.open_proposal(x)

	def open_proposal(self, proposal):
		if proposal.get("kind", "task") == "idea":
			if not any(i["id"] == proposal.get("idea_id") for i in self.todo.data.get("ideas", [])):
				messagebox.showinfo(APP_NAME, "This idea is no longer in the Ideas area.")
				return
			self.flush()
			self.todo.mode.set("idea")
			self.todo.mode_changed()
			self.todo.idea_pane.go_to_idea(proposal["idea_id"])
		else:
			self.open_task(proposal.get("ref", ""))

	def prop_double(self, ev):
		row = self.props.identify_row(ev.y)
		if not row:
			return
		x = self.cur["proposals"][int(row)]
		if x.get("state") == "committed":
			self.open_proposal(x)
			return
		if x.get("state") == "denied":
			messagebox.showinfo(APP_NAME, "Denied: " + x.get("denial_reason", "") + "\nRight-click > Restore denied to review this proposal again.")
			return
		if x.get("kind", "task") == "idea":
			self.edit_idea_proposal(x)
			return
		w = tk.Toplevel(self)
		w.title("Proposed task")
		w.transient(self.winfo_toplevel())
		f = ttk.Frame(w, padding=12)
		f.pack()
		tv = tk.StringVar(value=x["title"])
		ttk.Label(f, text="Task", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
		ttk.Entry(f, textvariable=tv, width=60, font="om_bold").grid(row=0, column=1, sticky="we")
		row, get = self.todo.common_fields(f, 1, x.get("project", ""), x.get("devs", []))
		# (common_fields starts at Normal / the first category: put this one's back)
		for wdg in f.grid_slaves():
			if isinstance(wdg, ttk.Combobox):
				vals = list(wdg.cget("values"))
				for want in (x.get("priority"), x.get("category")):
					if want in vals:
						wdg.set(want)
		ttk.Label(f, text="Sub-task of", style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=2)
		opts = ["(none)"] + [f"{o['ref']}  {o.get('title', '')}" for o in self.todo.tasks if o.get("status") not in ("Completed", "Not Possible") and not o.get("archived")]
		pv = tk.StringVar(value=next((o for o in opts if x.get("parent") and o.startswith(x["parent"] + " ")), "(none)"))
		ttk.Combobox(f, textvariable=pv, values=opts, state="readonly", width=56, font="TkDefaultFont").grid(row=row, column=1, sticky="w")
		ttk.Label(f, text="Note", style="Muted.TLabel").grid(row=row + 1, column=0, sticky="nw", pady=2)
		note = tk.Text(f, width=60, height=4, font="om_body", wrap="word")
		note.grid(row=row + 1, column=1, sticky="we")
		note.insert("1.0", x.get("note", ""))
		needs_ai = tk.BooleanVar(value=bool(x.get("needs_ai")))
		ttk.Checkbutton(f, text="Needs AI", variable=needs_ai).grid(row=row + 2, column=1, sticky="w", pady=(6, 0))

		def ok():
			c = get()
			x.update(title=tv.get().strip() or x["title"], devs=c["devs"], project=c["project"], priority=c["priority"], category=c["category"],
					 parent="" if pv.get().startswith("(") else pv.get().split()[0], note=note.get("1.0", "end").strip(), needs_ai=needs_ai.get())
			w.destroy()
			self.todo.save()
			self.fill_props()
		ttk.Button(f, text="OK", command=ok).grid(row=row + 3, column=1, sticky="e", pady=(10, 0))

	def drop(self):
		sel = sorted((int(i) for i in self.props.selection()), reverse=True)
		if not sel or not self.cur:
			return
		for i in sel:
			if self.cur["proposals"][i].get("state") != "committed":
				del self.cur["proposals"][i]
		self.todo.save()
		self.fill_props()
		self.fill()

	def commit(self):
		"""Send pending proposals in the visible panel to their destination."""
		v = self.cur
		idea = self.proposal_mode.get() == "idea"
		destination = "Ideas" if idea else "To Do Master"
		todo = [x for _, x in self.proposals() if x.get("state") not in ("committed", "denied") and x.get("pick", True)]
		if not todo:
			messagebox.showinfo(APP_NAME, "No pending ticked proposals to send.")
			return
		if not messagebox.askyesno(APP_NAME, f"Add {len(todo)} {'idea' if idea else 'task'}{'s' if len(todo) != 1 else ''} to {destination}?\n\n"
											 + "\n".join("  " + x["title"] + ("" if idea else f"  ({', '.join(x.get('devs', [])) or 'nobody'})") for x in todo[:12])):
			return
		for x in todo:
			if idea:
				category = x.get("category") if x.get("category") in self.todo.idea_pane.categories else self.default_idea_category()
				i = self.todo.idea_pane.new_idea(x["title"], category,
						text=f"From the Dev VC {vc_label(v)}.\n\n" + x.get("note", ""), project=x.get("project", ""))
				i["source_vc"] = v["id"]
				x.update(state="committed", idea_id=i["id"])
				continue
			t = self.todo.add_task(x["title"], devs=list(x.get("devs", [])), project=x.get("project", ""), priority=x.get("priority", "Normal"),
								   needs_ai=bool(x.get("needs_ai")),
								   category=x.get("category") or (self.todo.data["categories"][0] if self.todo.data["categories"] else ""),
								   parent=x.get("parent", ""), link="vc:" + v["id"],
								   setter_note=f"From the Dev VC {vc_label(v)}." + (f" {x['note']}" if x.get("note") else ""))
			x.update(state="committed", ref=t["ref"])
		self.todo.save()
		self.todo.fill_filters()
		if idea:
			self.todo.idea_pane.fill()
		self.todo.fill()
		self.fill_props()
		self.fill()
		self.app.set_status(f"{len(todo)} {'idea' if idea else 'task'}{'s' if len(todo) != 1 else ''} added to {destination}.")
