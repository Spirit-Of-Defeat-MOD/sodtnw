"""Ideas (To Do Master > 💡 Ideas): small ideas before they're tasks. Anyone posts one into a category, votes (👍 Good,
🔥 Super Want), comments, adds links and pictures and can bring it to the next Dev VC's agenda; a lead approves it into a
task or sub-task, or sends it back as Needs Fleshing. Kept in todo_tasks.json ("ideas", "idea_categories"), pictures in
idea_pictures/ next to it, so they're live like the rest. What's new since you last looked is your own (settings).
"""
import copy
import datetime
import json
import os
import tkinter as tk
import uuid
import webbrowser
from tkinter import ttk, messagebox, simpledialog, filedialog, colorchooser

from PIL import Image, ImageGrab

import ui
import idea_header_details
import master_links
from idea_picture_viewer import IdeaPictures, picture_label

APP_NAME = "Organisation Master"
SEED = ["Focus Trees", "Events & Decisions", "Mechanics", "Map & Countries", "Art & Visuals", "Music & Sound", "Balance",
		"Lore & Alt History", "Tools & Workflow", "Misc"]
TASK_CATEGORY = {"Focus Trees": "Focus tree", "Events & Decisions": "Events", "Mechanics": "Mechanic", "Map & Countries": "Map",
				 "Art & Visuals": "Art", "Music & Sound": "Music", "Balance": "Balance", "Lore & Alt History": "Content",
				 "Tools & Workflow": "Tools"}  # (an idea's category -> the task category it starts with when approved)
STATES = {"open": "💡 Open", "fleshing": "🧩 Needs Fleshing", "approved": "✔ Approved", "shelved": "🗄 Shelved", "duplicate": "♊ Duplicate",
		  "implemented": "✅ Implemented"}  # (implemented: approved and its task finished - worked out, not stored)
ACTIVE = ("open", "fleshing")
SHOW = (("active", "Open + Needs Fleshing"), ("open", "Open"), ("fleshing", "Needs Fleshing"), ("approved", "Approved"),
		("implemented", "✅ Implemented Ideas"), ("shelved", "🗄 Shelved"), ("duplicate", "♊ Duplicates"), ("all", "All"))
SHELVE_REASONS = ("Already decided / known", "Not for RR", "Too big for now", "After release", "Nobody to do it",
				  "Covered by another idea or task", "Changed our minds", "Other")
SIZES = ("", "Small", "Medium", "Large")
SORTS = ("Newest", "Most wanted", "Most comments", "Size")
GROUP_SORTS = ("A-Z", "Most ideas", "Most wanted")
NO_PROJECT = "No project"
VOTES = (("good", "👍 Good"), ("super", "🔥 Super Want"), ("dislike", "👎 Dislike"))
ALL_IDEAS = "All ideas"
SEP = " › "  # (headings inside categories: "Focus Trees › Majors › United Kingdom")
PICTURES = "idea_pictures"  # (next to todo_tasks.json: in the live repository, so everyone sees them)
FLASH_AT = 10  # (this many new ideas since you last looked: the Ideas button flashes)


def stamp():
	return datetime.datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def in_cat(i, c):
	"""In this category / heading, or a heading inside it."""
	cat = i.get("category") or ""
	return cat == c or cat.startswith(c + SEP)


def wanted(i):
	v = i.get("votes") or {}
	return 2 * len(v.get("super", [])) + len(v.get("good", [])) - len(v.get("dislike", []))  # (a dislike counts against it)


def month_name(key):
	return datetime.date(int(key[:4]), int(key[5:7]), 1).strftime("%B %Y")


class Ideas(ttk.Frame):
	def __init__(self, parent, todo):
		super().__init__(parent)
		self.todo = todo
		self.app = todo.app
		todo.data.setdefault("ideas", [])
		todo.data.setdefault("idea_categories", list(SEED))
		self.migrate_headings()
		self.post_heading = ""  # (a heading row picked in the list: new ideas go in it)
		self.cur = None
		self.cur_header = None
		self._job = None
		self._loading = False
		self._dirty = False  # (you edited the selected idea's fields: only then are they written back)
		self._thumbs = []
		self.picture_viewer = IdeaPictures(self)
		self._blink = None
		self._badge = "💡 Ideas"
		if "idea_seen" not in self.app.config:  # (the first time: what's there already isn't "new")
			self.app.config["idea_seen"] = stamp()
		self.seen = self.app.config["idea_seen"]

		pw = ttk.PanedWindow(self, orient="horizontal")
		pw.pack(fill="both", expand=True)
		# ---- left: categories, what to show, the monthly report ----
		left = ttk.Frame(pw, padding=(0, 0, 8, 0), width=ui.px(340))
		left.pack_propagate(False)
		pw.add(left, weight=1)
		sec = ui.Section(left, "Browse ideas", "idea_cats", self.app, expand=False).place_in(fill="x")
		ui.tool_button(sec.tools, "+ Category", lambda: self.add_category()).pack(side="left", padx=2)
		self.sidebar_mode = tk.StringVar(value=self.app.config.get("idea_sidebar", "categories"))
		switch = ttk.Frame(sec.body)
		switch.pack(fill="x", pady=(0, 5))
		for col, (key, label) in enumerate((("categories", "Categories"), ("projects", "Projects"))):
			switch.columnconfigure(col, weight=1, uniform="idea_sidebar_tabs")
			ttk.Radiobutton(switch, text=label, variable=self.sidebar_mode, value=key,
				command=self.sidebar_changed, style="View.TRadiobutton").grid(row=0, column=col, sticky="ew")
		cb = ttk.Frame(sec.body, width=ui.px(320), height=ui.px(300))
		cb.pack_propagate(False)
		cb.pack(fill="x")
		t = self.cats = ttk.Treeview(cb, columns=("n",), show="tree headings", selectmode="browse")
		t.heading("#0", text="Category")
		t.heading("n", text="Open")
		t.column("#0", width=ui.px(220), stretch=True)
		t.column("n", width=ui.px(60), anchor="e", stretch=False)
		t.pack(side="left", fill="both", expand=True)
		cat_scroll = ttk.Scrollbar(cb, command=t.yview)
		cat_scroll.pack(side="right", fill="y")
		t.configure(yscrollcommand=cat_scroll.set)
		t.bind("<<TreeviewSelect>>", lambda ev: self.fill_ideas())
		t.bind("<Button-3>", self.cat_menu)
		self._cat_drag = None
		self._cat_order_undo = []
		t.bind("<ButtonPress-1>", self.cat_drag_press, add="+")
		t.bind("<B1-Motion>", self.cat_drag_motion, add="+")
		t.bind("<ButtonRelease-1>", self.cat_drag_release, add="+")
		t.bind("<Escape>", self.cat_drag_cancel, add="+")
		t.bind("<<TreeviewOpen>>", lambda ev: self.after_idle(self.remember_cat_folds))
		t.bind("<<TreeviewClose>>", lambda ev: self.after_idle(self.remember_cat_folds))
		self.sidebar_hint = ttk.Label(sec.body, style="Muted.TLabel",
				  wraplength=ui.px(310), justify="left")
		self.sidebar_hint.pack(anchor="w", pady=(4, 0))
		sec = ui.Section(left, "Show", "idea_show", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		shown = self.app.config.get("idea_show", "active")
		self.show_var = tk.StringVar(value="shelved" if shown == "closed" else shown)  # (the old "Shelved / Duplicates")
		for key, text in SHOW:
			ttk.Radiobutton(sec.body, text=text, variable=self.show_var, value=key,
							command=lambda: (self.app.config.update(idea_show=self.show_var.get()), self.app.save_config(), self.fill_ideas())).pack(anchor="w")
		# ---- shelved ideas (like the To Do's Archive): out of the way, grouped by why ----
		sec = ui.Section(left, "🗄 Shelved Ideas", "idea_shelved", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.shelf_sec = sec
		sf = ttk.Frame(sec.body, width=ui.px(320), height=ui.px(200))
		sf.pack_propagate(False)
		sf.pack(fill="x")
		st = self.shelf = ttk.Treeview(sf, columns=("by",), show="tree", selectmode="browse")
		st.column("#0", width=ui.px(240), stretch=True)
		st.column("by", width=ui.px(70), anchor="e", stretch=False)
		st.pack(side="left", fill="both", expand=True)
		shelf_scroll = ttk.Scrollbar(sf, command=st.yview)
		shelf_scroll.pack(side="right", fill="y")
		st.configure(yscrollcommand=shelf_scroll.set)
		st.tag_configure("reason", font="om_bold")
		st.bind("<<TreeviewSelect>>", self.shelf_pick)
		st.bind("<Button-3>", self.shelf_menu)
		ttk.Label(sec.body, text="Click one to open it. Right-click: change why it's shelved, or reopen it.", style="Muted.TLabel",
				  wraplength=ui.px(310), justify="left").pack(anchor="w", pady=(4, 0))
		sec = ui.Section(left, "📅 Monthly Ideas Report", "idea_report", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		ui.tool_button(sec.tools, "📋 Copy", self.copy_report).pack(side="left", padx=2)
		row = ttk.Frame(sec.body)
		row.pack(fill="x")
		older = ttk.Label(row, text="◀", style="Head.TLabel", cursor="hand2")
		older.bind("<Button-1>", lambda ev: self.step_month(1))
		older.pack(side="left")
		self.rep_month = tk.StringVar()
		self.rep_box = ttk.Combobox(row, textvariable=self.rep_month, state="readonly", width=15, font="TkDefaultFont")
		self.rep_box.pack(side="left", padx=4)
		self.rep_box.bind("<<ComboboxSelected>>", lambda ev: self.fill_report())
		newer = ttk.Label(row, text="▶", style="Head.TLabel", cursor="hand2")
		newer.bind("<Button-1>", lambda ev: self.step_month(-1))
		newer.pack(side="left")
		self.rep_text = tk.Text(sec.body, height=12, width=1, wrap="word", font="om_small", relief="flat", cursor="arrow")
		self.rep_text.pack(fill="x", pady=(4, 0))
		self.rep_text.tag_configure("head", font="om_small_bold")

		# ---- right: post, the list, the selected idea ----
		right = ttk.Frame(pw, padding=(8, 0, 0, 0))
		pw.add(right, weight=4)
		sec = ui.Section(right, "💡 Post an idea", "idea_post", self.app, expand=False).place_in(fill="x")
		row = ttk.Frame(sec.body)
		row.pack(fill="x")
		actions = ttk.Frame(row)
		actions.pack(side="right")
		actions.columnconfigure((0, 1), weight=1, uniform="idea_post_actions")
		self.undo_btn = ttk.Button(actions, text="↶ Undo", command=self.todo.undo, width=12)
		self.undo_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
		self.todo.register_undo_button(self.undo_btn)
		ttk.Button(actions, text="Post", command=self.post, width=12).grid(row=0, column=1, sticky="ew", padx=(2, 0))
		self.new_title = tk.StringVar()
		e = self.new_title_entry = ttk.Entry(row, textvariable=self.new_title, font="TkDefaultFont")
		e.pack(side="left", fill="x", expand=True)
		e.bind("<Return>", lambda ev: self.post())
		self.new_cat = tk.StringVar()
		self.new_cat_box = ttk.Combobox(row, textvariable=self.new_cat, state="readonly", width=34, font="TkDefaultFont")
		self.new_cat_box.pack(side="left", padx=6)
		self.new_cat_box.bind("<<ComboboxSelected>>", lambda ev: (setattr(self, "post_heading", ""), self.post_where.config(text="")))
		self.post_where = ttk.Label(row, text="", style="Muted.TLabel")
		self.post_where.pack(side="left", padx=(6, 0))
		ttk.Label(sec.body, text="One line is enough (Enter posts it); add details, links and pictures below once it's there. "
								 "Not a commitment: a lead approves it into a task when it's time.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

		sec = ui.Section(right, "Ideas", "idea_list", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.list_sec = sec
		self.head_btn = ui.tool_button(sec.tools, "📑 + Heading", self.add_heading_here)
		self.head_btn.pack(side="left", padx=2)
		row = ttk.Frame(sec.body)
		row.pack(fill="x", pady=(0, 4))
		ttk.Label(row, text="🔍 Search").pack(side="left")
		self.search = tk.StringVar()
		ttk.Entry(row, textvariable=self.search, width=30, font="TkDefaultFont").pack(side="left", padx=(4, 16))
		self.search.trace_add("write", lambda *_: self.fill_ideas())
		ttk.Label(row, text="Sort").pack(side="left")
		self.sort = tk.StringVar(value=self.app.config.get("idea_sort", SORTS[0]))
		sb = ttk.Combobox(row, textvariable=self.sort, values=SORTS, state="readonly", width=15, font="TkDefaultFont")
		sb.pack(side="left", padx=4)
		sb.bind("<<ComboboxSelected>>", lambda ev: (self.app.config.update(idea_sort=self.sort.get()), self.app.save_config(), self.fill_ideas()))
		self.new_note = ttk.Label(row, text="", style="Muted.TLabel")
		self.new_note.pack(side="right")
		row = ttk.Frame(sec.body)
		row.pack(fill="x", pady=(0, 4))
		cfg = self.app.config
		self.grouped = tk.BooleanVar(value=cfg.get("idea_group", True))
		ttk.Checkbutton(row, text="📁 Group by project", variable=self.grouped, command=self.group_changed).pack(side="left")
		ttk.Label(row, text="Projects").pack(side="left", padx=(16, 4))
		self.group_sort = tk.StringVar(value=cfg.get("idea_group_sort", GROUP_SORTS[0]))
		gb = ttk.Combobox(row, textvariable=self.group_sort, values=GROUP_SORTS, state="readonly", width=12, font="TkDefaultFont")
		gb.pack(side="left")
		gb.bind("<<ComboboxSelected>>", lambda ev: self.group_changed())
		self.show_hidden = tk.BooleanVar(value=False)
		self.hidden_btn = ttk.Checkbutton(row, text="Show hidden", variable=self.show_hidden, command=self.fill_ideas)
		self.hidden_btn.pack(side="left", padx=(16, 0))
		self.only_new = tk.BooleanVar(value=False)  # (ideas and comments by others since you last looked)
		self.new_btn = ttk.Checkbutton(row, text="✨ Only new", variable=self.only_new, command=self.fill_ideas)
		self.new_btn.pack(side="left", padx=(12, 0))
		for text, fn in (("⊞ Open all", lambda: self.fold_all(False)), ("⊟ Fold all", lambda: self.fold_all(True))):
			ttk.Button(row, text=text, style="Tool.TButton", command=fn).pack(side="right", padx=(4, 0))
		lf = ttk.Frame(sec.body, height=ui.px(260))
		lf.pack_propagate(False)
		lf.pack(fill="x")
		t = self.list = ttk.Treeview(lf, columns=("task", "good", "super", "dislike", "talk", "size", "category", "by", "posted", "state"),
									 show="tree headings", selectmode="browse")
		for col, text, w, st in (("#0", "Idea", 300, True), ("task", "Task", 75, False), ("good", "👍", 40, False), ("super", "🔥", 40, False), ("dislike", "👎", 40, False), ("talk", "💬", 40, False),
								 ("size", "Size", 70, False), ("category", "Category", 190, False), ("by", "By", 90, False),
								 ("posted", "Posted", 85, False), ("state", "Status", 175, False)):
			t.heading(col, text=text)
			t.column(col, width=ui.px(w), stretch=st, anchor="center" if col in ("good", "super", "dislike", "talk") else "w")
		ys = ttk.Scrollbar(lf, command=t.yview)
		t.config(yscrollcommand=ys.set)
		t.pack(side="left", fill="both", expand=True)
		ys.pack(side="left", fill="y")
		t.tag_configure("droptarget", background="#3a6ea5", foreground="#ffffff")
		t.tag_configure("new", font="om_bold")
		t.tag_configure("approved", foreground="#2e7d32")
		t.tag_configure("implemented", foreground="#5a9a6a")
		t.tag_configure("fleshing", foreground="#b06f00")
		t.tag_configure("shelved", foreground="#888")
		t.tag_configure("duplicate", foreground="#888")
		t.tag_configure("group", font="om_bold")
		t.tag_configure("heading", font="om_bold")
		t.tag_configure("hiddengrp", foreground="#888")
		t.bind("<<TreeviewSelect>>", lambda ev: self.list_picked())
		t.bind("<<TreeviewOpen>>", lambda ev: self.after_idle(self.remember_folds))
		t.bind("<<TreeviewClose>>", lambda ev: self.after_idle(self.remember_folds))
		t.bind("<Button-3>", self.list_menu)
		self._dnd = None
		t.bind("<ButtonPress-1>", self.dnd_press, add="+")
		t.bind("<B1-Motion>", self.dnd_motion, add="+")
		t.bind("<ButtonRelease-1>", self.dnd_release, add="+")
		t.bind("<Delete>", lambda ev: self.delete())
		ttk.Label(sec.body, text="Bold / 🆕: new since you last looked.   Right-click a category / 📑 heading row: + Heading, 🎨 Colour, rename; an idea: 📑 Heading (move it).", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

		sec = ui.Section(right, "Selected idea", "idea_sel", self.app, expand=False).place_in(fill="x", pady=(8, 0))
		self.selected_section = sec
		body = ttk.Frame(sec.body)
		body.pack(fill="x")
		body.columnconfigure(0, weight=3)
		body.columnconfigure(1, weight=2)
		g = ttk.Frame(body)
		g.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
		self.header_label = ttk.Label(g, font="om_bold", wraplength=ui.px(700))
		top = ttk.Frame(g)
		top.pack(fill="x")
		self.v_title = tk.StringVar()
		ttk.Entry(top, textvariable=self.v_title, font="om_bold").pack(side="left", fill="x", expand=True)
		self.v_cat = tk.StringVar()
		self.cat_box = ttk.Combobox(top, textvariable=self.v_cat, state="readonly", width=30, font="TkDefaultFont")
		self.cat_box.pack(side="left", padx=(6, 0))
		ttk.Label(top, text="📑").pack(side="left", padx=(6, 0))
		self.v_head = tk.StringVar()
		self.head_box = ttk.Combobox(top, textvariable=self.v_head, state="readonly", width=22, font="TkDefaultFont")
		self.head_box.pack(side="left", padx=(2, 0))
		self.v_cat.trace_add("write", lambda *_: self.fill_head_box())
		ttk.Label(top, text="Size").pack(side="left", padx=(8, 2))
		self.v_size = tk.StringVar()
		ttk.Combobox(top, textvariable=self.v_size, values=SIZES, state="readonly", width=8, font="TkDefaultFont").pack(side="left")
		lk = ttk.Frame(g)
		lk.pack(fill="x", pady=(4, 0))
		ttk.Label(lk, text="Linked to  📁").pack(side="left")
		self.v_proj = tk.StringVar()
		self.proj_box = ttk.Combobox(lk, textvariable=self.v_proj, state="readonly", width=22, font="TkDefaultFont")
		self.proj_box.pack(side="left", padx=(2, 8))
		ttk.Label(lk, text="task").pack(side="left")
		self.v_task = tk.StringVar()
		self.task_box = ttk.Combobox(lk, textvariable=self.v_task, state="readonly", width=40, font="TkDefaultFont")
		self.task_box.pack(side="left", padx=(2, 0))
		self.v_proj.trace_add("write", lambda *_: self.fill_task_box())
		for var in (self.v_title, self.v_cat, self.v_head, self.v_size, self.v_proj, self.v_task):
			var.trace_add("write", lambda *_: self.changed())
		self.details_label = ttk.Label(g, text="Details", style="Muted.TLabel")
		self.details_label.pack(anchor="w", pady=(6, 0))
		self.text = tk.Text(g, height=4, wrap="word", font="om_body", relief="solid", borderwidth=1, undo=True)
		self.text.pack(fill="x")
		self.text.bind("<KeyRelease>", lambda ev: self.changed())
		self.info = ttk.Label(g, text="", style="Muted.TLabel", cursor="hand2", wraplength=ui.px(700), justify="left")
		self.info.pack(anchor="w", pady=(4, 0))
		self.info.bind("<Button-1>", self.info_click)
		# links and pictures
		lr = ttk.Frame(g)
		lr.pack(fill="x", pady=(6, 0))
		ttk.Label(lr, text="Links and pictures", style="Muted.TLabel").pack(side="left")
		self.media_btns = []
		for text, fn in (("+ Link...", self.add_link), ("+ File...", self.add_file), ("+ Picture...", self.add_picture), ("📋 Paste", self.paste_picture)):
			b = ttk.Button(lr, text=text, style="Tool.TButton", command=fn)
			b.pack(side="left", padx=(6, 0))
			self.media_btns.append(b)
		self.links = tk.Listbox(g, height=3, activestyle="none", font="om_small", relief="flat")
		self.links.pack(fill="x", pady=(4, 0))
		self.links.bind("<Double-1>", lambda ev: self.open_link())
		self.links.bind("<Button-3>", self.link_menu)
		self.pics = ttk.Frame(g)
		self.pics.pack(fill="x", pady=(4, 0))
		# what to do with it
		b1 = ttk.Frame(g)
		b1.pack(fill="x", pady=(8, 0))
		self.btn_approve = ttk.Button(b1, text="✔ Approve into a task...", command=self.approve)
		self.btn_approve.pack(side="left")
		self.btn_flesh = ttk.Button(b1, text="🧩 Needs Fleshing", command=lambda: self.set_state("fleshing"))
		self.btn_flesh.pack(side="left", padx=4)
		self.btn_agenda = ttk.Button(b1, text="📋 Bring to Agenda", command=self.to_agenda)
		self.btn_agenda.pack(side="left")
		b2 = ttk.Frame(g)
		b2.pack(fill="x", pady=(4, 0))
		self.btn_shelve = ttk.Button(b2, text="🗄 Shelve...", command=self.shelve)
		self.btn_shelve.pack(side="left")
		self.btn_reopen = ttk.Button(b2, text="↩ Reopen", command=lambda: self.set_state("open"))
		self.btn_reopen.pack(side="left", padx=4)
		self.btn_dup = ttk.Button(b2, text="♊ Duplicate of...", command=self.mark_duplicate)
		self.btn_dup.pack(side="left")
		self.btn_delete = ttk.Button(b2, text="Delete", command=self.delete)
		self.btn_delete.pack(side="right")
		# votes and comments
		c = ttk.Frame(body)
		c.grid(row=0, column=1, sticky="nsew")
		vr = ttk.Frame(c)
		vr.pack(fill="x")
		self.vote_btns = {}
		for key, text in VOTES:
			b = self.vote_btns[key] = ttk.Button(vr, text=text, command=lambda k=key: self.vote(k))
			b.pack(side="left", padx=(0, 4))
		self.voters = ttk.Label(c, text="", style="Muted.TLabel", wraplength=ui.px(420), justify="left")
		self.voters.pack(anchor="w", pady=(2, 6))
		ttk.Label(c, text="Comments", style="Muted.TLabel").pack(anchor="w")
		self.thread = tk.Text(c, height=9, wrap="word", font="om_small", relief="solid", borderwidth=1, cursor="arrow")
		self.thread.pack(fill="both", expand=True)
		self.thread.tag_configure("who", font="om_small_bold")
		self.thread.tag_configure("when", foreground="#888")
		self.thread.tag_configure("newc", background="#5a4a1a")
		cr = ttk.Frame(c)
		cr.pack(fill="x", pady=(4, 0))
		self.comment_var = tk.StringVar()
		ce = ttk.Entry(cr, textvariable=self.comment_var, font="TkDefaultFont")
		ce.pack(side="left", fill="x", expand=True)
		ce.bind("<Return>", lambda ev: self.add_comment())
		self.btn_comment = ttk.Button(cr, text="Comment", command=self.add_comment)
		self.btn_comment.pack(side="left", padx=(4, 0))
		self.idea_only = [(w, w.pack_info()) for w in (top, lk, b1, b2, vr, self.voters)]
		self.fill()
		self.after(2000, self.update_badge)

	# ---------- data ----------
	@property
	def ideas(self):
		return self.todo.data.setdefault("ideas", [])

	@property
	def categories(self):
		return self.todo.data.setdefault("idea_categories", list(SEED))

	def me(self):
		return self.todo.me.get()

	def idea(self, iid):
		return next((i for i in self.ideas if i["id"] == iid), None)

	def can_change(self, idea):
		return self.todo.is_lead() or idea.get("by") == self.me()

	def picked_category(self):
		sel = self.cats.selection()
		if sel and sel[0].startswith(("pc:", "ph:")):
			return json.loads(sel[0][3:])[1]
		return sel[0][2:] if sel and sel[0].startswith("c:") else None

	def picked_project(self):
		sel = self.cats.selection()
		if sel and sel[0].startswith("p:"):
			return sel[0][2:]
		if sel and sel[0].startswith(("pc:", "ph:")):
			return json.loads(sel[0][3:])[0]
		return None

	def picked_heading(self):
		sel = self.cats.selection()
		return json.loads(sel[0][3:])[2] if sel and sel[0].startswith("ph:") else None

	def group_project(self, category, heading=""):
		matches = [row for row in self.todo.data.get("idea_header_details", []) if "project" in row and
			((not row.get("heading") and (category == row.get("category") or category.startswith(row.get("category", "") + SEP))) or
			 (category == row.get("category") and (heading == row.get("heading") or heading.startswith(row.get("heading", "") + SEP))))]
		if not matches:
			return ""
		row = max(matches, key=lambda row: len(row.get("category", "")) + len(row.get("heading", "")))
		return row["project"] if self.todo.project(row["project"]) else ""

	def group_members(self, category, heading="", project=None):
		return [i for i in self.ideas if (in_cat(i, category) if not heading else
			(i.get("category") == category and ((i.get("heading") or "") == heading or (i.get("heading") or "").startswith(heading + SEP))))
			and (project is None or self.project_of(i) == project)]

	def group_project_menu(self, menu, category, heading="", source_project=None):
		inside = self.group_members(category, heading, source_project)
		allowed = all(self.can_change(i) for i in inside) and (bool(inside) or self.todo.is_lead())
		sub = tk.Menu(menu, tearoff=0)
		for project in self.todo.project_names() + [""]:
			sub.add_command(label=project or "No Project", state="normal" if allowed else "disabled",
				command=lambda project=project: self.assign_group_project(category, heading, project, source_project))
		menu.add_cascade(label="Assign to Project", menu=sub)

	def assign_group_project(self, category, heading, project, source_project=None):
		self.flush()
		if project and not self.todo.project(project):
			return
		inside = self.group_members(category, heading, source_project)
		if not all(self.can_change(i) for i in inside) or not inside and not self.todo.is_lead():
			self.app.set_status("Only a lead or the poster of every idea in the group can assign it.")
			return
		meta = idea_header_details.get(self.todo.data, category, heading)
		if meta is None:
			meta = dict(id="header-" + uuid.uuid4().hex, category=category, heading=heading,
				title=category + (SEP + heading if heading else ""), text="", links=[], comments=[], by=self.me(), created=stamp())
			self.todo.data.setdefault("idea_header_details", []).append(meta)
		meta.update(project=project, updated=stamp(), updated_by=self.me())
		if heading:
			heads = self.todo.data.setdefault("idea_headings", {}).setdefault(category, [])
			if heading not in heads:
				heads.append(heading)
		for i in inside:
			i["project"] = project
			if self.task_of(i) and (self.task_of(i).get("project") or "") != project:
				i["task"] = ""
			i["updated"] = stamp()
		self.todo.save()
		self.fill()
		if self.sidebar_mode.get() == "projects" and self.cats.exists("p:" + project):
			self.cats.selection_set("p:" + project)
			self.fill_ideas()
		self.app.set_status(f"Assigned {category + (SEP + heading if heading else '')} and {len(inside)} ideas to {project or 'No Project'}.")

	def sidebar_changed(self):
		self.flush()
		self.app.config["idea_sidebar"] = self.sidebar_mode.get()
		self.app.save_config()
		self.cats.selection_remove(*self.cats.selection())
		self.fill()

	def cat_paths(self):
		"""Every category and heading, parents first (in the order they were made); ideas' own too."""
		out = []
		for c in list(self.categories) + [i.get("category") or "" for i in self.ideas]:
			bits = [b for b in c.split(SEP) if b]
			for k in range(1, len(bits) + 1):
				q = SEP.join(bits[:k])
				if q not in out:
					out.append(q)
		parents = {}
		for c in out:  # (each heading right under its parent)
			parents.setdefault(SEP.join(c.split(SEP)[:-1]), []).append(c)

		def walk(p):
			for c in parents.get(p, []):
				yield c
				yield from walk(c)
		return list(walk(""))

	@property
	def colours(self):
		return self.todo.data.setdefault("idea_cat_colours", {})

	def cat_colour(self, c):
		"""A heading's colour: its own, else its parent's (and up)."""
		bits = (c or "").split(SEP)
		for k in range(len(bits), 0, -1):
			col = self.colours.get(SEP.join(bits[:k]))
			if col:
				return col
		return None

	def colour_tag(self, tree, col):
		tag = "fg" + col
		tree.tag_configure(tag, foreground=col)
		return tag

	def migrate_headings(self):
		"""Headings made as nested categories ("Focus Trees › Majors") -> the category + a heading in its idea list."""
		data = self.todo.data
		heads = data.setdefault("idea_headings", {})
		cats = []
		for c in data.get("idea_categories", []):
			top, _, rest = c.partition(SEP)
			if top not in cats:
				cats.append(top)
			if rest and rest not in heads.setdefault(top, []):
				heads[top].append(rest)
		for i in data.get("ideas", []):
			top, _, rest = (i.get("category") or "").partition(SEP)
			if rest:
				i["category"] = top
				i["heading"] = rest + (SEP + i["heading"] if i.get("heading") else "")
				if top not in cats:
					cats.append(top)
		if cats != data.get("idea_categories"):
			data["idea_categories"] = cats

	def headings(self, cat, extra=()):
		"""A category's headings, each right under its parent (made ones, and any its ideas use)."""
		out = []
		for h in list(self.todo.data.setdefault("idea_headings", {}).get(cat, [])) + list(extra):
			bits = [b for b in (h or "").split(SEP) if b]
			for k in range(1, len(bits) + 1):
				q = SEP.join(bits[:k])
				if q not in out:
					out.append(q)
		kids = {}
		for h in out:
			kids.setdefault(h.rsplit(SEP, 1)[0] if SEP in h else "", []).append(h)

		def walk(parent):
			for h in kids.get(parent, []):
				yield h
				yield from walk(h)
		return list(walk(""))

	def place(self, i):
		"""Category › heading › sub-heading."""
		return (i.get("category") or "") + (SEP + i["heading"] if i.get("heading") else "")

	def task_of(self, i):
		return self.todo.task(i["task"]) if i.get("task") else None

	def state_of(self, i):
		"""Its state for the lists: an approved idea whose task is Completed is ✅ implemented (off the other lists)."""
		state = i.get("state", "open")
		if state == "approved" and i.get("ref"):
			t = self.todo.task(i["ref"])
			if t and t.get("status") == "Completed":
				return "implemented"
		return state

	def project_of(self, i):
		"""Its project: its linked task's (wherever that is now), else its own."""
		t = self.task_of(i)
		return (t.get("project") if t else i.get("project")) or ""

	def task_label(self, t):
		return f"{t['ref']}  {t.get('title', '')}"

	def fill_head_box(self):
		heads = [""] + self.headings(self.v_cat.get())
		self.head_box.config(values=heads)
		if self.v_head.get() not in heads:
			self.v_head.set("")

	def fill_task_box(self):
		p = self.v_proj.get()
		tasks = [t for t in self.todo.tasks if (t.get("project") or "") == p and not (t.get("status") in ("Completed", "Not Possible") or t.get("archived"))]
		cur = self.task_of(self.cur) if self.cur else None
		if cur and cur not in tasks and (cur.get("project") or "") == p:
			tasks.append(cur)
		labels = [""] + [self.task_label(t) for t in sorted(tasks, key=lambda t: t["ref"])]
		self.task_box.config(values=labels)
		if self.v_task.get() not in labels:
			self.v_task.set("")

	def touch(self, i, feedback=True):
		i["updated"] = stamp()
		self.todo.save(feedback=feedback)

	def picture_dir(self):
		return os.path.join(os.path.dirname(self.todo.path()), PICTURES)

	# ---------- new since you last looked (your own) ----------
	def is_new(self, i):
		if i.get("by") != self.me() and (i.get("created") or "") > self.seen:
			return True
		return any(c.get("by") != self.me() and (c.get("when") or "") > self.seen for c in i.get("comments", []))

	def new_ideas(self):
		seen = self.app.config.get("idea_seen", stamp())
		return [i for i in self.ideas if i.get("by") != self.me() and (i.get("created") or "") > seen]

	def enter(self):
		self.seen = self.app.config.get("idea_seen", stamp())  # (what's new is shown while you're here)
		self.update_badge()

	def leave(self):
		self.flush()
		self.app.config["idea_seen"] = stamp()
		self.app.save_config()
		self.seen = self.app.config["idea_seen"]
		self.update_badge()

	def update_badge(self):
		"""The Ideas mode button: how many new; flashing from FLASH_AT new (until you look)."""
		btn = getattr(self.todo, "mode_buttons", {}).get("idea")
		if btn is None or not self.winfo_exists():
			return
		n = 0 if self.todo.mode.get() == "idea" else len(self.new_ideas())
		self._badge = "💡 Ideas" + (f" ({n} new)" if n else "")
		if self._blink and n < FLASH_AT:  # (looked, or fewer new now: stop flashing straight away)
			self.after_cancel(self._blink)
			self._blink = None
		if not self._blink:
			btn.config(text=self._badge, style="View.TRadiobutton")
		if n >= FLASH_AT and not self._blink:
			self._blink = self.after(700, lambda: self.blink(True))

	def blink(self, on):
		btn = self.todo.mode_buttons["idea"]
		if not self.winfo_exists():
			return
		if self.todo.mode.get() == "idea" or len(self.new_ideas()) < FLASH_AT:
			self._blink = None
			btn.config(text=self._badge, style="View.TRadiobutton")
			return
		ttk.Style().configure("Flash.View.TRadiobutton", foreground="#ffb300")
		btn.config(text=("✨" + self._badge[1:]) if on else self._badge, style="Flash.View.TRadiobutton" if on else "View.TRadiobutton")
		self._blink = self.after(700, lambda: self.blink(not on))

	# ---------- lists ----------
	def fill(self):
		t = self.cats
		self._cat_drag = None
		t.configure(cursor="")
		keep = t.selection()
		t.delete(*t.get_children())
		active = [i for i in self.ideas if i.get("state", "open") in ACTIVE]
		t.insert("", "end", iid="all", text=ALL_IDEAS, values=(len(active),))
		closed = set(self.app.config.get("idea_cat_closed", []))
		paths = self.cat_paths()
		projects = self.sidebar_mode.get() == "projects"
		t.heading("#0", text="Project / Category" if projects else "Category")
		if projects:
			names = list(dict.fromkeys(self.todo.project_names() + [self.project_of(i) for i in self.ideas if self.project_of(i)])) + [""]
			for name in names:
				members = [i for i in self.ideas if self.project_of(i) == name]
				col = (self.todo.project(name) or {}).get("colour")
				t.insert("", "end", iid="p:" + name, text=name or "No Project", open=True,
					values=(sum(i.get("state", "open") in ACTIVE for i in members) or "",),
					tags=(self.colour_tag(t, col),) if col else ())
				assigned = [row for row in self.todo.data.get("idea_header_details", []) if row.get("project") == name]
				for category in dict.fromkeys([i.get("category") or "" for i in members] + [row["category"] for row in assigned]):
					col = self.cat_colour(category)
					t.insert("p:" + name, "end", iid="pc:" + json.dumps([name, category]), text=category or "(no category)",
						values=(sum(i.get("state", "open") in ACTIVE and (i.get("category") or "") == category for i in members) or "",),
						tags=(self.colour_tag(t, col),) if col else ())
					heads = self.headings(category, [row.get("heading", "") for row in assigned if row["category"] == category]
						+ [i.get("heading", "") for i in members if i.get("category") == category])
					for heading in heads:
						h_members = [i for i in members if i.get("category") == category and
							((i.get("heading") or "") == heading or (i.get("heading") or "").startswith(heading + SEP))]
						if not h_members and not any(row["category"] == category and
							(row.get("heading") == heading or row.get("heading", "").startswith(heading + SEP)) for row in assigned):
							continue
						parent = "ph:" + json.dumps([name, category, heading.rsplit(SEP, 1)[0]]) if SEP in heading else "pc:" + json.dumps([name, category])
						t.insert(parent, "end", iid="ph:" + json.dumps([name, category, heading]), text=heading.split(SEP)[-1], open=True,
							values=(sum(i.get("state", "open") in ACTIVE for i in h_members) or "",))
		else:
			for c in paths:
				parent = "c:" + c.rsplit(SEP, 1)[0] if SEP in c else ""
				col = self.cat_colour(c)
				t.insert(parent, "end", iid="c:" + c, text=c.split(SEP)[-1], open=c not in closed,
					values=(sum(1 for i in active if in_cat(i, c)) or "",), tags=(self.colour_tag(t, col),) if col else ())
		self.sidebar_hint.configure(text="Choose a project or a category inside it. Posted ideas go to the selected project and keep their category."
			if projects else "Drag categories to reorder them. Right-click: colour, rename / remove (leads).")
		ui.stripe(t)
		t.selection_set(keep[0] if keep and t.exists(keep[0]) else "all")
		for box in (self.new_cat_box, self.cat_box):
			box.config(values=paths)
		self.proj_box.config(values=[""] + self.todo.project_names())
		if self.new_cat.get() not in paths:
			self.new_cat.set(paths[0] if paths else "")
		self.fill_ideas()
		self.fill_shelf()
		self.fill_report()
		self.update_badge()

	def shown(self, i, cat, show, q):
		state = self.state_of(i)
		if cat and not in_cat(i, cat):
			return False
		if show == "active" and state not in ACTIVE or show == "closed" and state not in ("shelved", "duplicate") \
				or show not in ("active", "closed", "all") and state != show or show == "all" and state == "implemented":
			return False
		if q:
			hay = " ".join([i.get("title", ""), i.get("text", ""), i.get("category", ""), i.get("by", ""), i.get("size", ""), i.get("ref", ""),
							self.project_of(i), i.get("task", ""), i.get("heading", "")]
						   + [c.get("text", "") + " " + c.get("by", "") for c in i.get("comments", [])] + i.get("links", [])).lower()
			return all(w in hay for w in q.split())
		return True

	def fill_ideas(self):
		t = self.list
		keep = (t.selection() or [None])[0] or (self.cur["id"] if self.cur else None)  # (the picked idea stays picked)
		t.delete(*t.get_children())
		cat, show, q = self.picked_category(), self.show_var.get(), self.search.get().strip().lower()
		if cat:
			self.new_cat.set(cat)
		heading = self.picked_heading()
		if heading is not None:
			self.post_heading = heading
		rows = [i for i in self.ideas if self.shown(i, cat, show, q)]
		fresh = sum(1 for i in self.ideas if self.is_new(i))
		self.new_btn.config(text=f"✨ Only new ({fresh})")
		if self.only_new.get():
			rows = [i for i in rows if self.is_new(i)]
		if heading is not None:
			rows = [i for i in rows if (i.get("heading") or "") == heading or (i.get("heading") or "").startswith(heading + SEP)]
		project = self.picked_project()
		if project is not None:
			rows = [i for i in rows if self.project_of(i) == project]
		key = {"Most wanted": lambda i: (wanted(i), i.get("created", "")), "Most comments": lambda i: (len(i.get("comments", [])), i.get("created", "")),
			   "Size": lambda i: (SIZES.index(i.get("size", "")) if i.get("size", "") in SIZES else 0, i.get("created", ""))}.get(
			self.sort.get(), lambda i: i.get("created", ""))
		new = 0
		rows = sorted(rows, key=key, reverse=True)
		cfg = self.app.config
		hidden = set(cfg.get("idea_hidden_groups", []))
		closed = set(cfg.get("idea_closed_groups", []))
		groups = {}
		if self.grouped.get():
			for i in rows:
				groups.setdefault(self.project_of(i), []).append(i)
			gs = self.group_sort.get()
			order = sorted(groups, key=lambda p: (p == "", -len(groups[p]) if gs == "Most ideas" else -sum(map(wanted, groups[p])) if gs == "Most wanted" else 0,
												  p.lower()))
			self.hidden_btn.config(text=f"Show hidden ({sum(1 for p in groups if p in hidden)})")
			if cat and project in (None, "") and "" not in groups and self.headings(cat):
				groups[""] = []  # (its empty headings show at the top level)
				order.append("")
		else:
			order = [None]
			groups[None] = rows
		shown = 0
		closed_rows = set(cfg.get("idea_closed_rows", [])) | {"grp:" + g for g in closed}
		for p in order:
			parent = ""
			if p:  # (a project's folder; ideas with no project sit at the top level)
				if p in hidden and not self.show_hidden.get():
					continue
				ideas_ = groups[p]
				v = [i.get("votes") or {} for i in ideas_]
				parent = "grp:" + p
				pc = (self.todo.project(p) or {}).get("colour") if p else None
				flag = self.todo.project_icon(p) if p and ((self.todo.project(p) or {}).get("icon") or self.todo.auto_icon(p)) else ""
				t.insert("", "end", iid=parent, open=p not in closed, image=flag,
						 text=(("" if flag else "📁 ") + p if p else "📂 " + NO_PROJECT) + (" (hidden)" if p in hidden else ""),
						 values=("", sum(len(x.get("good", [])) for x in v) or "", sum(len(x.get("super", [])) for x in v) or "", sum(len(x.get("dislike", [])) for x in v) or "",
								 sum(len(i.get("comments", [])) for i in ideas_) or "", "", "", "", "", f"{len(ideas_)} idea{'s' if len(ideas_) != 1 else ''}"),
						 tags=("group",) + (("hiddengrp",) if p in hidden else ()) + ((self.colour_tag(t, pc),) if pc else ()))
			key_p = p or ""
			cats = [cat] if cat else [c for c in self.categories if any(i.get("category") == c for i in groups[p])] + \
				sorted({i.get("category") or "" for i in groups[p]} - set(self.categories))
			heads_at = {}
			for c in cats:
				ideas_c = [i for i in groups[p] if (i.get("category") or "") == c]
				base = parent
				if not cat:  # (every category shown: a row per category)
					base = f"cat:{key_p}|{c}"
					col = self.cat_colour(c)
					meta = idea_header_details.get(self.todo.data, c, "") or {}
					flag = self.todo.flag_image(c)
					t.insert(parent, "end", iid=base, open=base not in closed_rows, image=flag,
							 text=("" if flag else "🗂 ") + (c or "(no category)") + (" 📝" if meta else ""),
							 values=("", "", "", "", len(meta.get("comments", [])) or "", "", "", "", "", f"{len(ideas_c)} idea{'s' if len(ideas_c) != 1 else ''}"),
							 tags=("group",) + ((self.colour_tag(t, col),) if col else ()))
				for h in self.headings(c, [i.get("heading") for i in ideas_c if i.get("heading")]) if (cat or ideas_c) else []:
					if (not cat or key_p) and not any((i.get("heading") or "") == h or (i.get("heading") or "").startswith(h + SEP) for i in ideas_c):
						continue  # (an empty heading only shows when its category is picked, under No project)
					row = f"hd:{key_p}|{c}|{h}"
					up = heads_at.get((c, h.rsplit(SEP, 1)[0])) if SEP in h else base
					n = sum(1 for i in ideas_c if (i.get("heading") or "") == h or (i.get("heading") or "").startswith(h + SEP))
					col = self.cat_colour(c + SEP + h)
					meta = idea_header_details.get(self.todo.data, c, h) or {}
					flag = self.todo.flag_image(h.split(SEP)[-1])
					t.insert(up or base, "end", iid=row, open=row not in closed_rows, image=flag,
							 text=("" if flag else "📑 ") + h.split(SEP)[-1] + (" 📝" if meta else ""),
							 values=("", "", "", "", len(meta.get("comments", [])) or "", "", "", "", "", f"{n} idea{'s' if n != 1 else ''}"),
							 tags=("heading",) + ((self.colour_tag(t, col),) if col else ()))
					heads_at[(c, h)] = row
				heads_at[(c, "")] = base
			for i in groups[p]:
				where = heads_at.get(((i.get("category") or ""), i.get("heading") or "")) or heads_at.get(((i.get("category") or ""), "")) or parent
				state = self.state_of(i)
				label = STATES.get(state, state) + (f" → {i['ref']}" if i.get("ref") else "")
				fresh = self.is_new(i)
				new += fresh
				shown += 1
				v = i.get("votes") or {}
				t.insert(where, "end", iid=i["id"], text=("🆕 " if fresh else "") + i.get("title", ""),
						 values=(i.get("task", ""), len(v.get("good", [])) or "", len(v.get("super", [])) or "", len(v.get("dislike", [])) or "", len(i.get("comments", [])) or "",
								 i.get("size", ""), self.place(i), i.get("by", ""), (i.get("created") or "")[:10], label),
						 tags=(state,) + (("new",) if fresh else ()) + ((self.colour_tag(t, col),) if (col := self.cat_colour(self.place(i))) else ()))
		ui.stripe(t)
		self.list_sec.count.config(text=f"({shown})")
		self.new_note.config(text=f"🆕 {new} new since you last looked" if new else "")
		if keep and t.exists(keep):
			t.selection_set(keep)  # (a folded project stays folded)
		else:
			self.cur = None
			self.show()

	# ---------- grouped by project: fold, sort, hide (your own) ----------
	def group_changed(self):
		self.app.config.update(idea_group=self.grouped.get(), idea_group_sort=self.group_sort.get())
		self.app.save_config()
		self.fill_ideas()

	def folder_rows(self, row=""):
		for r in self.list.get_children(row):
			if self.list.get_children(r):
				yield r
				yield from self.folder_rows(r)

	def remember_folds(self):
		t = self.list
		closed = set(self.app.config.get("idea_closed_rows", [])) | {"grp:" + g for g in self.app.config.get("idea_closed_groups", [])}
		for r in self.folder_rows():
			(closed.discard if t.item(r, "open") else closed.add)(r)
		self.app.config["idea_closed_rows"] = sorted(closed)
		self.app.config["idea_closed_groups"] = sorted(r[4:] for r in closed if r.startswith("grp:"))
		self.app.save_config()

	def fold_all(self, closed):
		for r in list(self.folder_rows()):
			self.list.item(r, open=not closed)
		self.remember_folds()

	# ---------- headings in the idea list (like the task list's groupings) ----------
	def row_place(self, row):
		"""A category / heading row -> (category, heading path) ("" = the category itself), else None."""
		if row.startswith("cat:"):
			return row[4:].split("|", 1)[1], ""
		if row.startswith("hd:"):
			_, c, h = row[3:].split("|", 2)
			return c, h
		return None

	def list_picked(self):
		"""A category / heading row picked: new ideas go there (Post shows where)."""
		sel = self.list.selection()
		at = self.row_place(sel[0]) if sel else None
		if at:
			self.new_cat.set(at[0])
			self.post_heading = at[1]
		elif sel and self.idea(sel[0]) is None:
			self.post_heading = ""
		self.post_where.config(text=(f"→ {at[0]}{SEP}{at[1]}" if at and at[1] else ""))
		self.show()

	def show_header_details(self, category=None, heading=""):
		if category is None:
			sel = self.list.selection()
			at = self.row_place(sel[0]) if sel else None
			if not at:
				return
			category, heading = at
		self.show(header=(category, heading))
		if self.selected_section.collapsed:
			self.selected_section.toggle()
		self.text.focus_set()

	def relocate_headers(self, transform):
		self.flush()
		idea_header_details.relocate(self.todo.data, transform)
		if self.cur_header is not None:
			self.cur_header = transform(*self.cur_header)

	def refresh_selected_rows(self):
		if self.cur_header is None:
			self.fill_ideas()
			return
		# Update metadata without rebuilding the tree or changing the selection mid-edit.
		for row in self.list_rows():
			at = self.row_place(row)
			if at != self.cur_header:
				continue
			meta = self.selected_record() or {}
			label = self.list.item(row, "text").removesuffix(" 📝")
			self.list.item(row, text=label + (" 📝" if meta else ""))
			self.list.set(row, "talk", len(meta.get("comments", [])) or "")

	def selected_record(self, create=False):
		if self.cur_header is None:
			return self.cur
		category, heading = self.cur_header
		row = idea_header_details.get(self.todo.data, category, heading)
		if row is None and create:
			row = dict(id="header-" + uuid.uuid4().hex, category=category, heading=heading,
				title=category + (SEP + heading if heading else ""), text="", links=[], comments=[],
				by=self.me(), created=stamp())
			self.todo.data.setdefault("idea_header_details", []).append(row)
		return row

	def save_selected(self, row, feedback=True):
		if self.cur_header is not None:
			row["updated_by"] = self.me()
		self.touch(row, feedback=feedback)


	def add_heading(self, cat, parent=""):
		n = (simpledialog.askstring("New heading", f"Heading in {cat + (SEP + parent if parent else '')} (e.g. United Kingdom):", parent=self) or "").replace("›", "-").strip()
		if not n:
			return
		h = parent + SEP + n if parent else n
		heads = self.todo.data.setdefault("idea_headings", {}).setdefault(cat, [])
		if h not in self.headings(cat):
			heads.append(h)
			self.todo.save()
		self.fill_ideas()
		for row in self.list_rows():
			if self.row_place(row) == (cat, h):
				self.list.see(row)
				self.list.selection_set(row)
				break

	def list_rows(self, row=""):
		for r in self.list.get_children(row):
			yield r
			yield from self.list_rows(r)

	def rename_heading(self, cat, old):
		last = old.split(SEP)[-1]
		n = (simpledialog.askstring("Rename heading", f"New name for {last}:", initialvalue=last, parent=self) or "").replace("›", "-").strip()
		new = (old.rsplit(SEP, 1)[0] + SEP + n) if SEP in old else n
		if not n or new == old or new in self.headings(cat):
			return
		swap = lambda h: new + h[len(old):] if h == old or (h or "").startswith(old + SEP) else h
		heads = self.todo.data.setdefault("idea_headings", {}).setdefault(cat, [])
		heads[:] = list(dict.fromkeys(swap(h) for h in heads))
		self.relocate_headers(lambda c, h: (c, swap(h)) if c == cat else (c, h))
		for i in self.ideas:
			if (i.get("category") or "") == cat and i.get("heading"):
				i["heading"] = swap(i["heading"])
		cols = self.colours
		for k in [k for k in cols if k.startswith(cat + SEP)]:
			nk = cat + SEP + swap(k[len(cat + SEP):])
			if nk != k:
				cols[nk] = cols.pop(k)
		self.todo.save()
		self.fill_ideas()

	def remove_heading(self, cat, h):
		inside = [i for i in self.ideas if (i.get("category") or "") == cat and ((i.get("heading") or "") == h or (i.get("heading") or "").startswith(h + SEP))]
		up = h.rsplit(SEP, 1)[0] if SEP in h else ""
		if inside and not messagebox.askyesno(APP_NAME, f"Remove the heading {h.split(SEP)[-1]}?\n\nIts {len(inside)} idea{'s' if len(inside) != 1 else ''} "
														 f"move up to {(cat + SEP + up) if up else cat}.", parent=self):
			return
		gone = lambda x: x == h or (x or "").startswith(h + SEP)
		self.relocate_headers(lambda c, x: (c, up) if c == cat and gone(x) else (c, x))
		heads = self.todo.data.setdefault("idea_headings", {}).setdefault(cat, [])
		heads[:] = [x for x in heads if not gone(x)]
		for i in inside:
			i["heading"] = up
		for k in [k for k in self.colours if k == cat + SEP + h or k.startswith(cat + SEP + h + SEP)]:
			self.colours.pop(k)
		self.todo.save()
		self.fill_ideas()

	# ---------- drag & drop: ideas into headings / categories / projects; headings into headings ----------
	def dnd_press(self, ev):
		t = self.list
		row = t.identify_row(ev.y)
		self._dnd = None
		if row and t.identify_region(ev.x, ev.y) in ("tree", "cell") and (self.idea(row) or row.startswith("hd:")):
			self._dnd = {"row": row, "x": ev.x, "y": ev.y, "on": False, "target": None}

	def dnd_target(self, row):
		"""What a drop on this row does: ("idea", category, heading, project or None) / ("heading", category, parent) or None."""
		d = self._dnd
		if not row or row == d["row"]:
			return None
		grouped = self.grouped.get()
		project = lambda key_p: key_p if grouped else None  # (projects only change when the list is grouped by them)
		if d["row"].startswith("hd:"):  # (a heading: into a category or another heading, not into itself)
			_, c0, h0 = d["row"][3:].split("|", 2)
			at = self.row_place(row)
			if not at or (at[0] == c0 and (at[1] == h0 or at[1].startswith(h0 + SEP))):
				return None
			return ("heading", at[0], at[1])
		if row.startswith("grp:"):
			i = self.idea(d["row"])
			return ("idea", i.get("category") or "", i.get("heading") or "", row[4:])
		if row.startswith("cat:"):
			key_p, c = row[4:].split("|", 1)
			return ("idea", c, "", project(key_p))
		if row.startswith("hd:"):
			key_p, c, h = row[3:].split("|", 2)
			return ("idea", c, h, project(key_p))
		o = self.idea(row)  # (onto another idea: into its place)
		return ("idea", o.get("category") or "", o.get("heading") or "", self.project_of(o) if grouped else None) if o else None

	def dnd_motion(self, ev):
		d = self._dnd
		if not d:
			return
		if not d["on"] and abs(ev.x - d["x"]) + abs(ev.y - d["y"]) < 8:
			return
		d["on"] = True
		t = self.list
		t.config(cursor="fleur")
		ui.drag_wobble(t, ev, [d["row"]], origin=(d["x"], d["y"]))
		row = t.identify_row(ev.y)
		if d["target"] != row:
			if d["target"] and t.exists(d["target"]):
				t.item(d["target"], tags=[g for g in t.item(d["target"], "tags") if g != "droptarget"])
			d["target"] = row
			if row and self.dnd_target(row) is not None:
				t.item(row, tags=("droptarget",) + tuple(t.item(row, "tags")))
		return "break"

	def dnd_release(self, ev):
		d = self._dnd
		t = self.list
		t.config(cursor="")
		if not d or not d["on"]:
			self._dnd = None
			return
		if d["target"] and t.exists(d["target"]):
			t.item(d["target"], tags=[g for g in t.item(d["target"], "tags") if g != "droptarget"])
		row = t.identify_row(ev.y)
		where = self.dnd_target(row) if row else None
		self._dnd = None
		if where is None:
			return
		if where[0] == "heading":
			_, c0, h0 = d["row"][3:].split("|", 2)
			self.move_heading(c0, h0, where[1], where[2])
			return
		i = self.idea(d["row"])
		if not i or not self.can_change(i):
			self.app.set_status("Only the idea's poster or a lead can move it.")
			return
		self.flush()
		_, c, h, project = where
		i["category"], i["heading"] = c, h
		if project is not None and project != self.project_of(i):
			i["project"] = project
			if self.task_of(i) and (self.task_of(i).get("project") or "") != project:
				i["task"] = ""  # (its task is in another project)
		self.touch(i)
		self.fill()
		if self.list.exists(i["id"]):
			self.list.see(i["id"])
			self.list.selection_set(i["id"])
		self.app.set_status(f"Moved \"{i.get('title', '')}\" to {self.place(i)}" + (f" (📁 {self.project_of(i) or NO_PROJECT})" if project is not None else "") + ".")

	def move_heading(self, c0, h0, c, parent):
		"""A heading (with its sub-headings and ideas) into another heading / category."""
		new = (parent + SEP if parent else "") + h0.split(SEP)[-1]
		swap = lambda h: new + h[len(h0):] if h == h0 or (h or "").startswith(h0 + SEP) else h
		self.relocate_headers(lambda cat, h: (c, swap(h))
			if cat == c0 and (h == h0 or h.startswith(h0 + SEP)) else (cat, h))
		heads = self.todo.data.setdefault("idea_headings", {})
		moving = [h for h in self.headings(c0) if h == h0 or h.startswith(h0 + SEP)]
		heads[c0] = [h for h in heads.get(c0, []) if h not in moving]
		dest = heads.setdefault(c, [])
		for h in moving:
			if swap(h) not in dest:
				dest.append(swap(h))
		for i in self.ideas:
			if (i.get("category") or "") == c0 and ((i.get("heading") or "") == h0 or (i.get("heading") or "").startswith(h0 + SEP)):
				i["category"], i["heading"] = c, swap(i["heading"])
				i["updated"] = stamp()
		cols = self.colours
		for k in [k for k in cols if k == c0 + SEP + h0 or k.startswith(c0 + SEP + h0 + SEP)]:
			cols[c + SEP + swap(k[len(c0 + SEP):])] = cols.pop(k)
		self.todo.save()
		self.fill()
		self.app.set_status(f"Moved the heading {h0.split(SEP)[-1]} to {c + SEP + new}.")

	def move_to_heading(self, i, h):
		if not self.can_change(i):
			self.app.set_status("Only the idea's poster or a lead can move it.")
			return
		i["heading"] = h
		self.touch(i)
		self.fill_ideas()

	def hide_group(self, p, hide=True):
		hidden = set(self.app.config.get("idea_hidden_groups", []))
		(hidden.add if hide else hidden.discard)(p)
		self.app.config["idea_hidden_groups"] = sorted(hidden)
		self.app.save_config()
		self.fill_ideas()
		self.app.set_status((f"{p or NO_PROJECT}'s ideas hidden (Show hidden brings them back)." if hide else f"{p or NO_PROJECT}'s ideas shown again."))

	def add_heading_here(self, menu_at=None):
		"""+ Heading: in the picked heading / category row of the list, else in the category picked on the left, else
		pick the category first (a menu)."""
		sel = self.list.selection()
		at = self.row_place(sel[0]) if sel else None
		if at:
			return self.add_heading(*at)
		cat = self.picked_category()
		if cat:
			return self.add_heading(cat)
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="+ Heading in which category?", state="disabled")
		for c in self.categories:
			m.add_command(label=c, command=lambda c=c: self.add_heading(c))
		x, y = menu_at or (self.head_btn.winfo_rootx(), self.head_btn.winfo_rooty() + self.head_btn.winfo_height())
		m.tk_popup(x, y)

	def list_menu(self, ev):
		row = self.list.identify_row(ev.y)
		if not row:  # (empty space: an empty category has no rows to right-click)
			cat = self.picked_category()
			m = tk.Menu(self, tearoff=0)
			if cat:
				m.add_command(label=f"📑 + Heading in {cat}...", command=lambda: self.add_heading(cat))
				m.add_command(label=f"💡 New idea in {cat}...", command=lambda: self.post_here(cat, ""))
			else:
				sub = tk.Menu(m, tearoff=0)
				for c in self.categories:
					sub.add_command(label=c, command=lambda c=c: self.add_heading(c))
				m.add_cascade(label="📑 + Heading in...", menu=sub)
			m.add_separator()
			m.add_command(label="⊞ Open all", command=lambda: self.fold_all(False))
			m.add_command(label="⊟ Fold all", command=lambda: self.fold_all(True))
			m.tk_popup(ev.x_root, ev.y_root)
			return
		m = tk.Menu(self, tearoff=0)
		at = self.row_place(row)
		if at:
			c, h = at
			self.list.selection_set(row)
			m.add_command(label=(c + SEP + h) if h else c, state="disabled")
			m.add_command(label="Details, comments & links…", command=lambda: self.show_header_details(c, h))
			m.add_command(label="💡 New idea here...", command=lambda: self.post_here(c, h))
			m.add_command(label="+ Heading inside it..." if h else "+ Heading...", command=lambda: self.add_heading(c, h))
			self.category_menu(m, c, lambda name: self.set_heading_category(c, h, name))
			key_p = row.split(":", 1)[1].split("|", 1)[0]
			self.group_project_menu(m, c, h, key_p if self.grouped.get() else None)
			m.add_command(label="🎨 Colour...", command=lambda: self.pick_colour(c + SEP + h if h else c))
			if (c + SEP + h if h else c) in self.colours:
				m.add_command(label="No colour of its own", command=lambda: self.pick_colour(c + SEP + h if h else c, clear=True))
			if h:
				m.add_separator()
				m.add_command(label="Rename heading...", command=lambda: self.rename_heading(c, h))
				m.add_command(label="Remove heading", command=lambda: self.remove_heading(c, h))
			m.add_separator()
			m.add_command(label="⊞ Open all", command=lambda: self.fold_all(False))
			m.add_command(label="⊟ Fold all", command=lambda: self.fold_all(True))
			m.tk_popup(ev.x_root, ev.y_root)
			return
		if row.startswith("grp:"):
			p = row[4:]
			hidden = p in self.app.config.get("idea_hidden_groups", [])
			m.add_command(label=f"📁 {p or NO_PROJECT}", state="disabled")
			if p:
				m.add_command(label="💡 Add an idea to it...", command=lambda: self.add_linked(project=p))
			m.add_command(label="👁 Show it again" if hidden else "🙈 Hide this project's ideas", command=lambda: self.hide_group(p, not hidden))
			m.add_separator()
			m.add_command(label="⊞ Open all", command=lambda: self.fold_all(False))
			m.add_command(label="⊟ Fold all", command=lambda: self.fold_all(True))
		else:
			self.list.selection_set(row)
			i = self.idea(row)
			if not i:
				return
			review = self.todo.linked("idea_review:" + i["id"])
			if review:
				m.add_command(label=f"Go to review task {review['ref']}", command=lambda: self.open_task(review["ref"]))
			if self.task_of(i):
				m.add_command(label=f"Go to {i['task']}", command=lambda: self.open_task(i["task"]))
			if i.get("ref") and self.todo.task(i["ref"]):
				m.add_command(label=f"Go to its task {i['ref']}", command=lambda: self.open_task(i["ref"]))
			m.add_command(label="📋 Bring to Agenda", command=self.to_agenda)
			if i.get("state") == "shelved":
				m.add_command(label="🗄 Why it's shelved...", command=lambda: self.shelve(i))
			self.category_menu(m, i.get("category") or "", lambda name: self.set_category(i, name), self.can_change(i))
			sub = tk.Menu(m, tearoff=0)
			c = i.get("category") or ""
			for h in [""] + self.headings(c):
				sub.add_command(label=("● " if (i.get("heading") or "") == h else "    ") + ("    " * h.count(SEP)) + (h.split(SEP)[-1] if h else "(no heading)"),
								command=lambda h=h: self.move_to_heading(i, h))
			sub.add_separator()
			sub.add_command(label="New heading...", command=lambda: self.add_heading(c))
			m.add_cascade(label="📑 Heading", menu=sub)
			sub = tk.Menu(m, tearoff=0)
			cur = self.project_of(i)
			for name in self.todo.project_names() + [""]:
				sub.add_command(label=("● " if cur == name else "    ") + (name or "(no project)"), command=lambda n=name: self.set_project(i, n))
			m.add_cascade(label="📁 Project", menu=sub)
		m.tk_popup(ev.x_root, ev.y_root)

	def category_menu(self, menu, current, command, enabled=True):
		sub = tk.Menu(menu, tearoff=0)
		for name in self.categories:
			sub.add_command(label=("● " if name == current else "    ") + name,
						command=lambda name=name: command(name), state="normal" if enabled and name != current else "disabled")
		menu.add_cascade(label="Category", menu=sub)

	def set_category(self, i, name):
		if not self.can_change(i):
			self.app.set_status("Only the idea's poster or a lead can change it.")
			return
		self.flush()
		if name == (i.get("category") or ""):
			return
		i["category"] = name
		if i.get("heading"):
			heads = self.todo.data.setdefault("idea_headings", {}).setdefault(name, [])
			for h in self.headings(name, [i["heading"]]):
				if h not in heads:
					heads.append(h)
		self.touch(i)
		self.fill()
		self.app.set_status(f"Moved idea to {name}.")

	def set_heading_category(self, source, heading, name):
		"""Move the whole heading, including nested headings and their ideas."""
		self.flush()
		if source == name:
			return
		inside = [i for i in self.ideas if (i.get("category") or "") == source and
				  (not heading or (i.get("heading") or "") == heading or (i.get("heading") or "").startswith(heading + SEP))]
		if not all(self.can_change(i) for i in inside):
			self.app.set_status("Only a lead or the poster of every idea in this heading can move it.")
			return
		if heading:
			self.move_heading(source, heading, name, "")
			return
		heads = self.todo.data.setdefault("idea_headings", {})
		dest = heads.setdefault(name, [])
		for h in self.headings(source, [i.get("heading", "") for i in inside]):
			if h not in dest:
				dest.append(h)
		heads[source] = []
		self.relocate_headers(lambda c, h: (name, h) if c == source else (c, h))
		for i in inside:
			i["category"], i["updated"] = name, stamp()
		for key in [key for key in self.colours if key.startswith(source + SEP)]:
			self.colours.setdefault(name + key[len(source):], self.colours[key])
			self.colours.pop(key)
		self.todo.save()
		self.fill()
		self.app.set_status(f"Moved {len(inside)} ideas and their headings to {name}.")

	def set_project(self, i, name):
		"""Right-click an idea > 📁 Project: links it to a project (a task of another project is let go)."""
		if not self.can_change(i):
			self.app.set_status("Only the idea's poster or a lead can change it.")
			return
		self.flush()
		i["project"] = name
		if self.task_of(i) and (self.task_of(i).get("project") or "") != name:
			i["task"] = ""
		self.touch(i)
		self.fill()
		if self.list.exists(i["id"]):
			self.list.see(i["id"])
			self.list.selection_set(i["id"])
		self.app.set_status(f"\"{i.get('title', '')}\" is now " + (f"in 📁 {name}." if name else "without a project."))

	# ---------- an idea linked to a project / task (To Do: right-click > Add a linked idea) ----------
	def add_linked(self, project="", task=None):
		t = self.todo.task(task) if task else None
		project = (t.get("project") if t else project) or ""
		w = tk.Toplevel(self)
		w.title("Add a linked idea")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text="💡 An idea for " + (self.task_label(t) if t else f"📁 {project}"), style="Head.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
		if t and project:
			ttk.Label(f, text=f"(in 📁 {project})", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
		title = tk.StringVar()
		paths = self.cat_paths()
		cat = tk.StringVar(value=self.picked_category() or (paths[0] if paths else ""))
		e = ttk.Entry(f, textvariable=title, width=56, font="TkDefaultFont")
		for n, (label, widget) in enumerate((("Idea", e), ("Category", ttk.Combobox(f, textvariable=cat, values=paths, state="readonly",
																					 width=40, font="TkDefaultFont"))), start=2):
			ttk.Label(f, text=label, style="Muted.TLabel").grid(row=n, column=0, sticky="w", padx=(0, 8), pady=(6, 2))
			widget.grid(row=n, column=1, sticky="w", pady=(6, 2))
		ttk.Label(f, text="Details (optional)", style="Muted.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
		text = tk.Text(f, height=3, width=56, wrap="word", font="om_body", relief="solid", borderwidth=1)
		text.grid(row=5, column=0, columnspan=2, sticky="w")
		e.focus_set()

		def ok(ev=None):
			if not title.get().strip():
				return
			i = self.new_idea(title.get().strip(), cat.get(), text=text.get("1.0", "end").strip(), project=project, task=t["ref"] if t else "")
			w.destroy()
			self.todo.save()
			self.fill()
			self.app.set_status(f"💡 Idea added for {t['ref'] if t else project} (in the Ideas mode, under 📁 {project or NO_PROJECT}).")
			return i
		e.bind("<Return>", ok)
		self._linked_ok = (title, cat, ok)
		bf = ttk.Frame(f)
		bf.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="💡 Add the idea", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def show_linked(self, project="", task=None):
		"""To Do > right-click > See its ideas: Ideas mode, that project's group open, the task's first idea picked."""
		self.todo.mode.set("idea")
		self.todo.mode_changed()
		self.show_var.set("all")
		self.search.set("")
		self.cats.selection_set("all")
		self.grouped.set(True)
		p = (self.todo.task(task) or {}).get("project", project) if task else project
		self.hide_group(p, False)
		first = next((i for i in sorted(self.linked_ideas(project=p, task=task), key=lambda i: i.get("created", ""), reverse=True)
					  if self.list.exists(i["id"])), None)
		if first:
			row = first["id"]
			up = self.list.parent(row)
			while up:  # (its project folder, category and headings opened)
				self.list.item(up, open=True)
				up = self.list.parent(up)
			self.list.selection_set(row)
			self.list.see(row)

	def linked_ideas(self, project="", task=None):
		review_idea = (self.todo.task(task) or {}).get("idea") if task else None
		return [i for i in self.ideas if (i.get("task") == task or i["id"] == review_idea if task else self.project_of(i) == project)]

	# ---------- post ----------
	def post_here(self, cat, h):
		"""Right-click a category / heading > New idea here: the post box, set to it."""
		self.new_cat.set(cat)
		self.post_heading = h
		self.post_where.config(text=f"→ {cat}{SEP}{h}" if h else "")
		self.new_title_entry.focus_set()

	def new_idea(self, title, category, text="", project=None, task="", heading=""):
		if project is None:
			project = self.group_project(category, heading)
		i = {"id": "idea-" + uuid.uuid4().hex[:10], "title": title, "text": text, "category": category, "heading": heading, "by": self.me(),
			 "created": stamp(), "updated": stamp(), "state": "open", "size": "", "votes": {"good": [], "super": [], "dislike": []}, "comments": [],
			 "links": [], "pictures": [], "project": project, "task": task}
		self.ideas.append(i)
		return i

	def post(self):
		title = self.new_title.get().strip()
		if not title:
			return
		i = self.new_idea(title, self.new_cat.get(), project=self.picked_project(),
			heading=self.post_heading if self.post_heading in self.headings(self.new_cat.get()) else "")
		self.new_title.set("")
		self.todo.save()
		self.fill()
		if self.list.exists(i["id"]):
			self.list.selection_set(i["id"])
			self.list.see(i["id"])
			self.show()  # (picked straight away: a picture pasted right after goes on it)
		self.app.set_status(f"Idea posted in {i['category']}.")

	# ---------- the selected idea ----------
	def show(self, header=None):
		self.flush()
		sel = self.list.selection()
		self.cur_header = header or (self.row_place(sel[0]) if sel else None)
		self.cur = self.idea(sel[0]) if sel and self.cur_header is None else None
		header = self.cur_header
		self.selected_section.count.config(text="Header" if header else "")
		for widget, options in self.idea_only:
			if header:
				widget.pack_forget()
			elif not widget.winfo_manager():
				# Restore each control in its original position among its siblings.
				siblings = widget.master.winfo_children()
				following = next((w for w in siblings[siblings.index(widget) + 1:]
					if w.winfo_manager() == "pack"), None)
				widget.pack(**dict(options, **({"before": following} if following else {})))
		if header:
			self.header_label.config(text="📑 " + header[0] + (SEP + header[1] if header[1] else ""))
			self.header_label.pack(fill="x", before=self.details_label)
		else:
			self.header_label.pack_forget()
		i = self.cur
		self._loading = True
		self.v_title.set(i.get("title", "") if i else "")
		self.v_cat.set(i.get("category", "") if i else "")
		self.v_size.set(i.get("size", "") if i else "")
		self.fill_head_box()
		self.v_head.set(i.get("heading", "") if i else "")
		self.v_proj.set(self.project_of(i) if i else "")
		self.fill_task_box()
		lt = self.task_of(i) if i else None
		self.v_task.set(self.task_label(lt) if lt else "")
		self.text.delete("1.0", "end")
		record = self.selected_record() or {}
		self.text.insert("1.0", record.get("text", ""))
		self.text.edit_reset()
		self._loading = False
		self._dirty = False
		self.fill_links()
		self.fill_thread()
		on = lambda ok: ["!disabled"] if ok else ["disabled"]
		for b in self.media_btns[:2] + [self.btn_comment]:
			b.state(on(i is not None or header is not None))
		for b in self.media_btns[2:] + list(self.vote_btns.values()):
			b.state(on(i is not None))
		if not i:
			self.info.config(text="Shared header details · changes save automatically. Anyone can add comments and links."
				if header else "Pick an idea (or post one above).")
			self.voters.config(text="")
			for b in (self.btn_approve, self.btn_flesh, self.btn_agenda, self.btn_shelve, self.btn_reopen, self.btn_dup, self.btn_delete):
				b.state(["disabled"])
			return
		state = i.get("state", "open")
		bits = [f"Posted by {i.get('by', '?')} on {(i.get('created') or '')[:10]}"]
		if state == "approved":
			bits.append(f"approved by {i.get('approved_by', '?')}" + (f": it's task {i['ref']} (click to go to it)" if i.get("ref") else "")
						+ (" - ✅ done: in Implemented Ideas" if self.state_of(i) == "implemented" else ""))
		elif state == "fleshing":
			bits.append(f"🧩 needs fleshing out (said {i.get('fleshing_by', '?')})")
		elif state == "shelved":
			bits.append(f"🗄 shelved by {i.get('shelved_by', '?')}" + (f": {i['shelve_reason']}" if i.get("shelve_reason") else "")
						+ (f" ({i['shelve_note']})" if i.get("shelve_note") else ""))
		elif state == "duplicate":
			o = self.idea(i.get("dup_of"))
			bits.append("♊ a duplicate of " + (f"\"{o['title']}\" (click to go to it)" if o else "an idea that's gone"))
		if i.get("agenda"):
			bits.append(f"📋 on the agenda: {i['agenda']}")
		if self.task_of(i) and state != "approved":
			bits.append(f"🔗 for {i['task']} (click to go to it)")
		self.info.config(text="   ·   ".join(bits))
		lead, mine = self.todo.is_lead(), self.can_change(i)
		self.btn_approve.state(on(lead and state in ACTIVE))
		ft = self.todo.task(i["from_task"]) if i.get("from_task") else None
		self.btn_approve.config(text=f"✔ Fleshed out → back to {ft['ref']}" if ft else "✔ Approve into a task...")
		self.btn_flesh.state(on(lead and state == "open"))
		self.btn_agenda.state(on(state in ACTIVE))
		self.btn_shelve.state(on(mine and state in ACTIVE))
		self.btn_reopen.state(on(mine and state in ("fleshing", "shelved", "duplicate")))
		self.btn_dup.state(on(mine and state in ACTIVE))
		self.btn_delete.state(on(mine))
		v = i.get("votes") or {}
		for key, text in VOTES:
			names = v.get(key, [])
			self.vote_btns[key].config(text=("✓ " if self.me() in names else "") + text + (f"  ·  {len(names)}" if names else ""))
		self.voters.config(text="   ".join(f"{text}: {', '.join(v.get(key, []))}" for key, text in VOTES if v.get(key)) or "No votes yet.")

	def info_click(self, ev):
		i = self.cur
		if not i:
			return
		if i.get("state") == "approved" and i.get("ref"):
			self.open_task(i["ref"])
		elif i.get("state") == "duplicate" and self.idea(i.get("dup_of")):
			self.go_to_idea(i["dup_of"])
		elif self.task_of(i):
			self.open_task(i["task"])

	def go_to_idea(self, iid):
		self.show_var.set("all")
		self.cats.selection_set("all")
		self.search.set("")
		self.fill_ideas()
		if self.list.exists(iid):
			if self.list.parent(iid):
				self.list.item(self.list.parent(iid), open=True)
			self.list.selection_set(iid)
			self.list.see(iid)

	def changed(self):
		if self._loading or (self.cur is None and self.cur_header is None):
			return
		self._dirty = True
		if self._job:
			self.after_cancel(self._job)
		self._job = self.after(900, self.flush)

	def flush(self):
		if self._job:
			self.after_cancel(self._job)
			self._job = None
		if self.cur_header is not None and not self._loading and self._dirty:
			self._dirty = False
			text = self.text.get("1.0", "end-1c")
			if text != (self.selected_record() or {}).get("text", ""):
				row = self.selected_record(create=True)
				row["text"] = text
				self.save_selected(row, feedback=False)
				self.refresh_selected_rows()
			return
		i = self.cur
		if i is None or self._loading or not self._dirty:
			return  # (nothing typed: what's in the fields may be older than the idea - another dev's change, a renamed heading)
		self._dirty = False
		new = {"title": self.v_title.get().strip() or i.get("title", ""), "category": self.v_cat.get(), "size": self.v_size.get(),
			   "text": self.text.get("1.0", "end").rstrip(), "project": self.v_proj.get(), "heading": self.v_head.get(),
			   "task": self.v_task.get().split()[0] if self.v_task.get() else ""}
		if new["project"] == self.project_of(i) and new["task"] == i.get("task", ""):
			new["project"] = i.get("project", "")  # (unchanged: a task's ideas follow the task)
		if any(i.get(k, "") != v for k, v in new.items()):
			if not self.can_change(i):
				self.app.set_status("Only the idea's poster or a lead can change it (anyone can vote, comment and add links / pictures).")
				self.show()
				return
			refill = any(new[k] != i.get(k, "") for k in ("category", "heading", "size", "project", "task"))
			i.update(new)
			self.touch(i, feedback=False)
			if refill:
				self.fill()
			elif self.list.exists(i["id"]):
				self.list.item(i["id"], text=i["title"])

	def close(self):
		if self.winfo_manager():
			self.leave()
		self.flush()

	def set_state(self, state):
		i = self.cur
		if not i:
			return
		self.flush()
		i["state"] = state
		if state in ("shelved", "fleshing"):
			i[state + "_by"] = self.me()
			i[state + "_on"] = stamp()
		if state == "open":
			i.pop("dup_of", None)
		self.touch(i)
		self.fill()

	# ---------- shelving: why, and the 🗄 Shelved Ideas section ----------
	def ask_shelve_reason(self, i):
		"""(reason, note) or None: why an idea is shelved."""
		w = tk.Toplevel(self)
		w.title("Shelve idea")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=f"Shelve \"{i.get('title', '')}\"", font="om_bold", wraplength=ui.px(420)).pack(anchor="w")
		ttk.Label(f, text="Why? It goes into 🗄 Shelved Ideas under this reason.", style="Muted.TLabel").pack(anchor="w", pady=(2, 6))
		reason = tk.StringVar(value=i.get("shelve_reason") or SHELVE_REASONS[0])
		for r in SHELVE_REASONS:
			ttk.Radiobutton(f, text=r, variable=reason, value=r).pack(anchor="w")
		ttk.Label(f, text="Note (optional)").pack(anchor="w", pady=(8, 0))
		note = tk.Text(f, height=3, width=52, wrap="word", font="om_body")
		note.insert("1.0", i.get("shelve_note", ""))
		note.pack(fill="x")
		out = {}

		def ok():
			out["r"] = (reason.get(), note.get("1.0", "end").strip())
			w.destroy()
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(10, 0))
		ttk.Button(bf, text="🗄 Shelve", command=ok).pack(side="right")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="right", padx=6)
		w.grab_set()
		w.wait_window()
		return out.get("r")

	def shelve(self, i=None):
		"""🗄 Shelve... (or change why a shelved idea is shelved)."""
		i = i or self.cur
		if not i:
			return
		got = self.ask_shelve_reason(i)
		if got is None:
			return
		self.flush()
		i["shelve_reason"], i["shelve_note"] = got
		if not i["shelve_note"]:
			i.pop("shelve_note")
		if i.get("state") == "shelved":
			self.touch(i)
			self.fill()
		else:
			self.cur = i
			self.set_state("shelved")

	def fill_shelf(self):
		t = self.shelf
		keep = t.selection()
		t.delete(*t.get_children())
		shelved = sorted((i for i in self.ideas if i.get("state") == "shelved"), key=lambda i: i.get("shelved_on") or "", reverse=True)
		groups = {}
		for i in shelved:
			groups.setdefault(i.get("shelve_reason") or "(no reason given)", []).append(i)
		order = [r for r in SHELVE_REASONS if r in groups] + sorted(r for r in groups if r not in SHELVE_REASONS)
		for r in order:
			t.insert("", "end", iid="r:" + r, text=f"{r}  ({len(groups[r])})", open=True, tags=("reason",))
			for i in groups[r]:
				t.insert("r:" + r, "end", iid="i:" + i["id"], text=i.get("title", ""), values=(i.get("shelved_by", ""),))
		self.shelf_sec.title.config(text=f"🗄 Shelved Ideas ({len(shelved)})" if shelved else "🗄 Shelved Ideas")
		t.selection_set([k for k in keep if t.exists(k)])

	def shelf_pick(self, ev=None):
		sel = self.shelf.selection()
		if not sel or not sel[0].startswith("i:") or (self.cur and self.cur["id"] == sel[0][2:]):
			return
		iid = sel[0][2:]
		self.show_var.set("shelved")
		self.cats.selection_set("all")
		self.search.set("")
		self.fill_ideas()
		if self.list.exists(iid):
			if self.list.parent(iid):
				self.list.item(self.list.parent(iid), open=True)
			self.list.selection_set(iid)
			self.list.see(iid)

	def shelf_menu(self, ev):
		row = self.shelf.identify_row(ev.y)
		if not row or not row.startswith("i:"):
			return
		self.shelf.selection_set(row)
		i = self.idea(row[2:])
		if not i:
			return
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="🗄 Why it's shelved...", command=lambda: self.shelve(i))
		m.add_command(label="↺ Reopen", command=lambda: self.reopen(i), state="normal" if self.can_change(i) else "disabled")
		m.tk_popup(ev.x_root, ev.y_root)

	def reopen(self, i):
		self.cur = i
		self.set_state("open")

	def delete(self):
		i = self.cur
		if not i or not self.can_change(i):
			return
		if not messagebox.askyesno(APP_NAME, f"Delete the idea \"{i.get('title', '')}\" (and its comments)?\n\n(Shelving keeps it findable.)", parent=self):
			return
		self.todo.data.setdefault("deleted_ideas", {})[i["id"]] = {"item": copy.deepcopy(i), "when": stamp(), "who": self.me()}  # (🗑 Trash)
		self.todo.data["ideas"] = [x for x in self.ideas if x["id"] != i["id"]]
		self.cur = None
		self.todo.save()
		self.fill()

	# ---------- votes ----------
	def vote(self, key):
		i = self.cur
		if not i:
			return
		self.flush()
		votes = i.setdefault("votes", {})
		names = votes.setdefault(key, [])
		adding = self.me() not in names
		if self.me() in names:
			names.remove(self.me())
		else:
			names.append(self.me())
			for other in (("good", "super") if key == "dislike" else ("dislike",)):  # (a dislike and a want cancel each other)
				if self.me() in votes.get(other, []):
					votes[other].remove(self.me())
		self.touch(i, feedback=False)
		if adding:
			self.app.feedback({"good": "reaction_like", "super": "reaction_super", "dislike": "reaction_dislike"}[key])
		self.fill_ideas()

	# ---------- comments ----------
	def fill_thread(self):
		tx = self.thread
		tx.config(state="normal")
		tx.delete("1.0", "end")
		i = self.selected_record()
		for c in (i or {}).get("comments", []):
			tags = ("newc",) if c.get("by") != self.me() and (c.get("when") or "") > self.seen else ()
			tx.insert("end", c.get("by", "?"), ("who",) + tags)
			tx.insert("end", "  " + (c.get("when") or "")[:16].replace("T", " ") + "\n", ("when",) + tags)
			tx.insert("end", c.get("text", "") + "\n\n", tags)
		if i and not i.get("comments"):
			tx.insert("end", "No comments yet.", ("when",))
		tx.config(state="disabled")
		tx.see("end")

	def add_comment(self, text=None, idea=None):
		text = (text or self.comment_var.get()).strip()
		if not text or (idea is None and self.cur is None and self.cur_header is None):
			return
		self.flush()
		i = idea if idea is not None else self.selected_record(create=True)
		i.setdefault("comments", []).append({"id": "c-" + uuid.uuid4().hex[:8], "by": self.me(), "when": stamp(), "text": text})
		if idea is None:
			self.comment_var.set("")
		self.save_selected(i) if idea is None else self.touch(i)
		self.refresh_selected_rows()
		self.fill_thread()

	# ---------- links and pictures (anyone adds; the poster or a lead removes) ----------
	def fill_links(self):
		self.links.delete(0, "end")
		i = self.selected_record() or {}
		for link in i.get("links", []):
			self.links.insert("end", "🔗 " + link)
		for w in self.pics.winfo_children():
			w.destroy()
		self._thumbs = []
		folder = self.picture_dir()
		for name in i.get("pictures", []):
			picture_label(self.pics, os.path.join(folder, name), lambda n=name: self.picture_viewer.preview(n),
						  lambda ev, n=name: self.picture_menu(ev, n), keep=self._thumbs)

	def append_link(self, link):
		if self.cur is None and self.cur_header is None:
			return
		self.flush()
		i = self.selected_record(create=True)
		if link not in i.setdefault("links", []):
			i["links"].append(link)
			self.save_selected(i)
		self.fill_links()
		self.refresh_selected_rows()

	def add_link(self):
		if self.cur is None and self.cur_header is None:
			return
		url = (simpledialog.askstring("Add a link", "Web address, master link or file path:", parent=self) or "").strip()
		if url:
			self.append_link(url)

	def add_file(self):
		if self.cur is None and self.cur_header is None:
			return
		path = filedialog.askopenfilename(parent=self, initialdir=self.app.mod_root)
		if path:
			try:
				if os.path.commonpath((os.path.abspath(path), os.path.abspath(self.app.mod_root))) == os.path.abspath(self.app.mod_root):
					path = os.path.relpath(path, self.app.mod_root).replace("\\", "/")
			except ValueError:
				pass
			self.append_link(path)

	def open_link(self):
		sel = self.links.curselection()
		i = self.selected_record()
		if not sel or not i:
			return
		link = i.get("links", [])[sel[0]]
		self.flush()
		try:
			target = master_links.from_file(link, self.app.mod_root)
		except ValueError:
			target = None
		if target:
			self.app.navigate_master(target)
		else:
			path = link if os.path.isabs(link) else os.path.join(self.app.mod_root, link)
			if os.path.exists(path):
				os.startfile(path)
			else:
				webbrowser.open(link if "://" in link else "https://" + link)

	def remove_link(self, index):
		self.flush()
		i = self.selected_record()
		if i and (self.cur_header is not None or self.can_change(i)):
			i["links"].pop(index)
			self.save_selected(i)
			self.fill_links()
			self.refresh_selected_rows()

	def link_menu(self, ev):
		i = self.selected_record()
		n = self.links.nearest(ev.y)
		if not i or n < 0 or n >= len(i.get("links", [])):
			return
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="Open", command=lambda: (self.links.selection_clear(0, "end"), self.links.selection_set(n), self.open_link()))
		m.add_command(label="Copy", command=lambda: (self.clipboard_clear(), self.clipboard_append(i["links"][n])))
		m.add_command(label="Remove", state="normal" if self.cur_header is not None or self.can_change(i) else "disabled",
			command=lambda: self.remove_link(n))
		m.tk_popup(ev.x_root, ev.y_root)

	def save_picture(self, im):
		i = self.cur
		if not i:
			return
		os.makedirs(self.picture_dir(), exist_ok=True)
		name = f"{i['id']}-{uuid.uuid4().hex[:6]}.jpg"
		im = im.convert("RGBA")
		flat = Image.new("RGB", im.size, (255, 255, 255))
		flat.paste(im, mask=im.split()[3])
		flat.thumbnail((1600, 1600))  # (kept small: everyone downloads it)
		flat.save(os.path.join(self.picture_dir(), name), quality=85)
		i.setdefault("pictures", []).append(name)
		self.touch(i)
		self.fill_links()

	def add_picture(self):
		if not self.cur:
			return
		path = filedialog.askopenfilename(parent=self, title="A picture for the idea",
										  filetypes=[("Pictures", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.dds *.tga"), ("All files", "*.*")])
		if path:
			try:
				with Image.open(path) as image:
					self.save_picture(image)
			except OSError as ex:
				messagebox.showerror(APP_NAME, f"Can't read that picture:\n{ex}", parent=self)

	def paste_picture(self):
		if not self.cur:
			return
		im = ImageGrab.grabclipboard()
		if isinstance(im, list) and im:  # (a copied file)
			try:
				with Image.open(im[0]) as image:
					im = image.copy()
			except OSError:
				im = None
		if not isinstance(im, Image.Image):
			messagebox.showinfo(APP_NAME, "There's no picture on the clipboard (copy one, or take a screenshot with Win+Shift+S).", parent=self)
			return
		try:
			self.save_picture(im)
		finally:
			im.close()

	def picture_menu(self, ev, name):
		i = self.cur
		if not i:
			return
		m = tk.Menu(self, tearoff=0)
		m.add_command(label="View / zoom", command=lambda: self.picture_viewer.preview(name))
		m.add_command(label="Open in default app", command=lambda: self.picture_viewer.open_external(i['id'], name))
		m.add_command(label="Remove", state="normal" if self.can_change(i) else "disabled",
					  command=lambda: (i["pictures"].remove(name), self.touch(i), self.fill_links()))
		m.tk_popup(ev.x_root, ev.y_root)

	# ---------- duplicate (with a comment) ----------
	def mark_duplicate(self):
		i = self.cur
		if not i or not self.can_change(i):
			return
		self.flush()
		others = [x for x in self.ideas if x["id"] != i["id"] and x.get("state") != "duplicate"]
		if not others:
			messagebox.showinfo(APP_NAME, "There's no other idea to point it at.", parent=self)
			return
		labels = [f"{x.get('title', '')}  ({x.get('category', '')}, {x.get('by', '')})" for x in others]
		w = self._dup_win = tk.Toplevel(self)
		w.title("Duplicate of...")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text=f"\"{i.get('title', '')}\" is a duplicate of", style="Head.TLabel").pack(anchor="w")
		pick = tk.StringVar(value=labels[0])
		ttk.Combobox(f, textvariable=pick, values=labels, state="readonly", width=60, font="TkDefaultFont").pack(anchor="w", pady=(4, 8))
		ttk.Label(f, text="Why (needed: it goes in both ideas' comments)", style="Muted.TLabel").pack(anchor="w")
		why = tk.Text(f, height=3, width=60, wrap="word", font="om_body", relief="solid", borderwidth=1)
		why.pack(anchor="w")

		def ok():
			text = why.get("1.0", "end").strip()
			if not text:
				messagebox.showerror(APP_NAME, "Write why it's a duplicate.", parent=w)
				return
			o = others[labels.index(pick.get())]
			w.destroy()
			i.update(state="duplicate", dup_of=o["id"])
			self.add_comment(f"♊ Duplicate of \"{o.get('title', '')}\": {text}", idea=i)
			for key, names in (i.get("votes") or {}).items():  # (its votes count for the original)
				have = o.setdefault("votes", {}).setdefault(key, [])
				have += [n for n in names if n not in have]
			self.add_comment(f"♊ \"{i.get('title', '')}\" ({i.get('by', '?')}) was marked a duplicate of this: {text}", idea=o)
			self.fill()
		self._dup_ok = (pick, why, ok)
		ttk.Button(f, text="♊ Mark as duplicate", command=ok).pack(anchor="e", pady=(10, 0))

	# ---------- bring to the Dev VC agenda ----------
	def to_agenda(self):
		i = self.cur
		if not i:
			return
		self.flush()
		text = f"💡 Idea: {i.get('title', '')} ({i.get('by', '?')}, {i.get('category', '')})"
		import dev_vc
		where = dev_vc.bring_to_agenda(self.todo.data, text, "Ideas", self.todo.me.get())
		i["agenda"] = where
		self.todo.vc_pane.fill_agenda()
		self.todo.vc_pane.fill_future()
		self.touch(i)
		self.show()
		self.app.set_status(f"On the agenda of {where}.")

	# ---------- approve into a task (or a sub-task) ----------
	# ---------- a task set to Needs Fleshing: its idea ----------
	def task_fleshing(self, t, on):
		"""A task's status went to Needs Fleshing (on: make / reopen its idea, 🧩 Needs Fleshing) or away from it (its idea is done)."""
		i = self.idea(t.get("idea")) if t.get("idea") else None
		if on:
			if i is None:
				rev = {v: k for k, v in TASK_CATEGORY.items()}
				cat = rev.get(t.get("category"), "Misc")
				if cat not in self.categories:
					self.categories.append(cat)
				note = f"{t['ref']} {t.get('title', '')} needs fleshing out before anyone goes on with it."
				i = self.new_idea(t.get("title", ""), cat, text=note + (f"\n\n{t['setter_note']}" if t.get("setter_note") else ""),
								  project=t.get("project", ""), task=t["ref"])
				i["from_task"] = t["ref"]
				i["seed_text"] = i["text"]  # (what it started with: only what's written after goes back to the task)
				t["idea"] = i["id"]
			i.update(state="fleshing", fleshing_by=self.me(), fleshing_on=stamp(), updated=stamp())
			self.todo.save()
			self.fill()
			self.app.set_status(f"{t['ref']} needs fleshing: its idea \"{i['title']}\" is in 💡 Ideas (🧩 Needs Fleshing).")
		elif i is not None and i.get("state") in ACTIVE:
			i.update(state="approved", ref=t["ref"], approved_by=self.me(), approved_on=stamp(), updated=stamp())
			self.todo.save()
			self.fill()

	def open_idea(self, iid):
		self.todo.mode.set("idea")
		self.todo.mode_changed()
		self.go_to_idea(iid)

	def fleshed_out(self, i, t):
		"""✔ Fleshed out: the task goes back to To do, with what the idea worked out added to its note."""
		if not messagebox.askyesno(APP_NAME, f"Fleshed out?\n\n{t['ref']} {t.get('title', '')} goes back to To do, with this idea's details "
											 "and comments added to its note.", parent=self):
			return
		bits = []
		text, seed = (i.get("text") or "").strip(), (i.get("seed_text") or "").strip()
		added = text[len(seed):].strip() if seed and text.startswith(seed) else ("" if text == seed else text)
		if added:
			bits.append(added)
		if i.get("comments"):
			bits.append("Comments:\n" + "\n".join(f"- {c.get('by', '?')}: {c.get('text', '')}" for c in i["comments"][-10:]))
		if i.get("links"):
			bits.append("Links: " + "  ".join(i["links"]))
		if bits:
			t["setter_note"] = ((t.get("setter_note") or "") + "\n\nFleshed out (idea):\n" + "\n\n".join(bits)).strip()
		i.update(state="approved", ref=t["ref"], approved_by=self.me(), approved_on=stamp())
		self.todo.change(t, "status", "To do", note="fleshed out in Ideas")
		self.touch(i)
		self.todo.fill()
		self.fill()
		self.app.set_status(f"Fleshed out: {t['ref']} is back to To do.")

	def approve(self):
		i = self.cur
		if not i or not self.todo.is_lead():
			return
		self.flush()
		ft = self.todo.task(i["from_task"]) if i.get("from_task") else None
		if ft:
			return self.fleshed_out(i, ft)
		cats = self.todo.data["categories"]
		top = (i.get("category") or "").split(SEP)[0]
		guess = TASK_CATEGORY.get(top, top)
		w = self._approve_win = tk.Toplevel(self)
		w.title("Approve into a task")
		w.transient(self.winfo_toplevel())
		w.resizable(False, False)
		f = ttk.Frame(w, padding=12)
		f.pack()
		ttk.Label(f, text="Approve into a task", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
		title = tk.StringVar(value=i.get("title", ""))
		cat = tk.StringVar(value=guess if guess in cats else (cats[0] if cats else ""))
		proj = tk.StringVar(value=self.project_of(i))
		prio = tk.StringVar(value="High" if len((i.get("votes") or {}).get("super", [])) >= 3 else "Normal")
		lt = self.task_of(i)
		under = tk.StringVar(value=f"{lt['ref']}  {lt.get('title', '')}" if lt and not (lt.get("status") in ("Completed", "Not Possible") or lt.get("archived")) else "")
		planning = tk.BooleanVar(value=True)
		open_tasks = [t for t in self.todo.tasks if t.get("status") not in ("Completed", "Not Possible") and not t.get("archived")]
		under_labels = [""] + [f"{t['ref']}  {t.get('title', '')}" for t in sorted(open_tasks, key=lambda t: t["ref"])]
		pb = ttk.Combobox(f, textvariable=proj, values=[""] + self.todo.project_names(), state="readonly", width=30, font="TkDefaultFont")
		ub = ttk.Combobox(f, textvariable=under, values=under_labels, state="readonly", width=48, font="TkDefaultFont")

		def under_picked(ev=None):
			p = self.todo.task(under.get().split()[0]) if under.get() else None
			if p:
				proj.set(p.get("project", ""))
			pb.config(state="disabled" if p else "readonly")
		ub.bind("<<ComboboxSelected>>", under_picked)
		if under.get():
			pb.config(state="disabled")  # (its linked task: a sub-task of it to start with)
		rows = (("Task", ttk.Entry(f, textvariable=title, width=50, font="TkDefaultFont")),
				("Category", ttk.Combobox(f, textvariable=cat, values=cats, state="readonly", width=24, font="TkDefaultFont")),
				("Sub-task of", ub), ("Project", pb),
				("Priority", ttk.Combobox(f, textvariable=prio, values=("Low", "Normal", "High", "Critical"), state="readonly", width=12, font="TkDefaultFont")))
		for n, (label, widget) in enumerate(rows, start=1):
			ttk.Label(f, text=label, style="Muted.TLabel").grid(row=n, column=0, sticky="w", padx=(0, 8), pady=2)
			widget.grid(row=n, column=1, sticky="w", pady=2)
		ttk.Label(f, text="(Sub-task of: empty = a task of its own; or an open task, and it goes in that task's project)",
				  style="Muted.TLabel").grid(row=7, column=0, columnspan=2, sticky="w")
		ttk.Checkbutton(f, text="Needs Planning first (think it through before anyone starts)", variable=planning).grid(
			row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))

		def ok():
			if not title.get().strip():
				return
			v = i.get("votes") or {}
			note = [f"From an idea by {i.get('by', '?')} ({self.place(i)})."]
			extra = [f"Size guess: {i['size']}" if i.get("size") else "",
					 f"Votes: 👍 {len(v.get('good', []))}  🔥 {len(v.get('super', []))}  👎 {len(v.get('dislike', []))}" if any(v.values()) else ""]
			if any(extra):
				note.append("  ·  ".join(x for x in extra if x))
			if i.get("text"):
				note.append(i["text"])
			if i.get("links"):
				note.append("Links: " + "  ".join(i["links"]))
			if i.get("comments"):
				note.append("Comments:\n" + "\n".join(f"- {c.get('by', '?')}: {c.get('text', '')}" for c in i["comments"][-10:]))
			parent = under.get().split()[0] if under.get() else ""
			t = self.todo.add_task(title.get().strip(), category=cat.get(), project=proj.get(), priority=prio.get(), parent=parent,
								   needs_planning=planning.get(), setter_note="\n".join(note), link="idea:" + i["id"])
			i.update(state="approved", ref=t["ref"], approved_by=self.me(), approved_on=stamp())
			w.destroy()
			self.touch(i)
			self.todo.fill_filters()
			self.todo.fill()
			self.fill()
			self.app.set_status(f"Idea approved: {t['ref']} {t['title']}" + (f" (a sub-task of {parent})" if parent else "")
								+ (" (in Needs Planning)." if planning.get() else "."))
		self._approve_ok = (under, under_picked, ok)
		bf = ttk.Frame(f)
		bf.grid(row=9, column=0, columnspan=2, sticky="e", pady=(10, 0))
		ttk.Button(bf, text="✔ Make the task", command=ok).pack(side="left")
		ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=4)

	def open_task(self, ref):
		if not self.todo.task(ref):
			messagebox.showinfo(APP_NAME, f"{ref} isn't in To Do Master.", parent=self)
			return
		self.flush()
		self.todo.mode.set(self.app.config.get("todo_last_mode", "dev"))
		self.todo.mode_changed()
		self.todo.go_to(ref)

	# ---------- monthly ideas report ----------
	def report_months(self):
		keys = {(i.get("created") or "")[:7] for i in self.ideas if i.get("created")} | {datetime.date.today().strftime("%Y-%m")}
		return sorted(keys, reverse=True)

	def step_month(self, d):
		names = list(self.rep_box.cget("values"))
		if self.rep_month.get() in names:
			self.rep_month.set(names[min(max(names.index(self.rep_month.get()) + d, 0), len(names) - 1)])
			self.fill_report()

	def report(self):
		"""(month key, [(head, [lines])])"""
		keys = self.report_months()
		names = [month_name(k) for k in keys]
		self.rep_box.config(values=names)
		if self.rep_month.get() not in names:
			self.rep_month.set(names[0])
		key = keys[names.index(self.rep_month.get())]
		inm = lambda s: (s or "")[:7] == key
		posted = [i for i in self.ideas if inm(i.get("created"))]
		approved = [i for i in self.ideas if inm(i.get("approved_on"))]
		fleshing = [i for i in self.ideas if inm(i.get("fleshing_on")) and i.get("state") == "fleshing"]
		shelved = [i for i in self.ideas if inm(i.get("shelved_on")) and i.get("state") == "shelved"]
		comments = sum(1 for i in self.ideas for c in i.get("comments", []) if inm(c.get("when")))
		by = {}
		for i in posted:
			by[i.get("by", "?")] = by.get(i.get("by", "?"), 0) + 1
		top = sorted((i for i in posted if wanted(i) > 0), key=wanted, reverse=True)[:5]
		v = lambda i: " ".join(f"{e}{len((i.get('votes') or {}).get(k, []))}" for k, e in (("super", "🔥"), ("good", "👍"), ("dislike", "👎")))
		parts = [("Summary", [f"💡 {len(posted)} posted  ·  ✔ {len(approved)} approved  ·  🧩 {len(fleshing)} need fleshing  ·  "
							  f"🗄 {len(shelved)} shelved  ·  💬 {comments} comments"]),
				 ("Most wanted (posted this month)", [f"{i.get('title', '')}  ({v(i)})" for i in top] or ["-"]),
				 ("Approved into tasks", [f"{i.get('title', '')} → {i.get('ref', '')}" for i in approved] or ["-"]),
				 ("Ideas by", [", ".join(f"{n} {c}" for n, c in sorted(by.items(), key=lambda kv: -kv[1]))] if by else ["-"])]
		return key, parts

	def fill_report(self):
		key, parts = self.report()
		tx = self.rep_text
		tx.config(state="normal")
		tx.delete("1.0", "end")
		for head, lines in parts:
			tx.insert("end", head + "\n", "head")
			tx.insert("end", "\n".join(lines) + "\n\n")
		tx.config(state="disabled")

	def copy_report(self):
		key, parts = self.report()
		text = f"**Monthly Ideas Report: {month_name(key)}**\n\n" + "\n\n".join(
			f"**{head}**\n" + "\n".join(("- " + x if head not in ("Summary", "Ideas by") and x != "-" else x) for x in lines) for head, lines in parts)
		self.clipboard_clear()
		self.clipboard_append(text)
		self.app.set_status(f"Monthly Ideas Report for {month_name(key)} copied: paste it anywhere.")

	# ---------- categories ----------
	def cat_drag_press(self, ev):
		t = self.cats
		row = t.identify_row(ev.y)
		self._cat_drag = None
		if row.startswith("c:") and t.identify_region(ev.x, ev.y) in ("tree", "cell") and "indicator" not in t.identify_element(ev.x, ev.y):
			self._cat_drag = {"row": row, "x": ev.x, "y": ev.y, "on": False}

	def cat_drag_motion(self, ev):
		d = self._cat_drag
		if not d or not self.cats.exists(d["row"]):
			return
		if not d["on"] and abs(ev.x - d["x"]) + abs(ev.y - d["y"]) < 8:
			return
		d["on"] = True
		t = self.cats
		t.configure(cursor="fleur")
		ui.drag_wobble(t, ev, [d["row"]], origin=(d["x"], d["y"]))
		if ev.y < ui.px(24):
			t.yview_scroll(-1, "units")
		elif ev.y > t.winfo_height() - ui.px(20):
			t.yview_scroll(1, "units")
		if not 0 <= ev.x < t.winfo_width() or ev.y < ui.px(20) or ev.y >= t.winfo_height():
			return "break"
		row = t.identify_row(ev.y)
		parent = t.parent(d["row"])
		if row == d["row"]:
			return "break"
		if row == "all" and not parent:
			index = 1  # All ideas always stays first.
		elif not row:
			index = len(t.get_children(parent))
		elif row.startswith("c:") and t.parent(row) == parent:
			box = t.bbox(row)
			index = t.index(row) + (ev.y >= box[1] + box[3] / 2)
		else:
			return "break"  # Reorder siblings; never change a category's hierarchy.
		if t.index(d["row"]) < index:
			index -= 1
		t.move(d["row"], parent, index)
		return "break"

	def cat_drag_release(self, ev):
		d = self._cat_drag
		self._cat_drag = None
		t = self.cats
		t.configure(cursor="")
		if not d or not d["on"]:
			return
		if not (0 <= ev.x < t.winfo_width() and ui.px(20) <= ev.y < t.winfo_height()):
			self.fill()  # Dropped outside: discard the preview.
			return "break"

		def walk(parent=""):
			for row in t.get_children(parent):
				if row.startswith("c:"):
					yield row[2:]
					yield from walk(row)

		order = list(walk())
		previous = self.cat_paths()
		if order != previous:
			self._cat_order_undo.append(previous)
			self._cat_order_undo = self._cat_order_undo[-20:]
			self.todo.data["idea_categories"] = order
			self.todo.save()
			self.app.set_status("Idea category order saved.")
		self.fill()
		return "break"

	def cat_drag_cancel(self, ev=None):
		if self._cat_drag:
			self._cat_drag = None
			self.cats.configure(cursor="")
			self.fill()
			return "break"

	def undo_category_order(self):
		if not self._cat_order_undo:
			return
		previous = self._cat_order_undo.pop()
		current = self.cat_paths()
		# Keep later additions/renames and never resurrect a removed category.
		order = [c for c in previous if c in current] + [c for c in current if c not in previous]
		if order != current:
			self.todo.data["idea_categories"] = order
			self.todo.save()
			self.app.set_status("Previous idea category order restored.")
		self.fill()

	def add_category(self, parent=None):
		"""A category (parent None), or a heading inside one."""
		n = (simpledialog.askstring("New heading" if parent else "New idea category",
									(f"Heading inside {parent}:" if parent else "Category:"), parent=self) or "").replace("›", "-").strip()
		if not n:
			return
		path = parent + SEP + n if parent else n
		if path in self.cat_paths():
			return
		cats = self.categories
		if parent:  # (right after its parent's other headings)
			after = [k for k, c in enumerate(cats) if c == parent or c.startswith(parent + SEP)]
			cats.insert(after[-1] + 1 if after else len(cats), path)
		else:
			cats.append(path)
		self.todo.save()
		self.fill()
		if self.cats.exists("c:" + path):
			if parent and self.cats.exists("c:" + parent):
				self.cats.item("c:" + parent, open=True)
			self.cats.selection_set("c:" + path)
			self.cats.see("c:" + path)

	def remember_cat_folds(self):
		if self.sidebar_mode.get() != "categories":
			return
		closed = set()

		def walk(row):
			for c in self.cats.get_children(row):
				if c.startswith("c:") and self.cats.get_children(c) and not self.cats.item(c, "open"):
					closed.add(c[2:])
				walk(c)
		walk("")
		self.app.config["idea_cat_closed"] = sorted(closed)
		self.app.save_config()

	def cat_menu(self, ev):
		row = self.cats.identify_row(ev.y)
		m = tk.Menu(self, tearoff=0)
		if row.startswith("p:"):
			self.cats.selection_set(row)
			m.add_command(label=row[2:] or "No Project", state="disabled")
			m.add_command(label="Add an idea…", command=lambda: self.add_linked(project=row[2:]))
			m.tk_popup(ev.x_root, ev.y_root)
			return
		if row.startswith("ph:"):
			project, category, heading = json.loads(row[3:])
			self.cats.selection_set(row)
			m.add_command(label=heading, state="disabled")
			self.group_project_menu(m, category, heading, project)
			m.add_command(label="Details, comments & links…", command=lambda: self.show_header_details(category, heading))
			m.add_command(label="New idea here…", command=lambda: self.post_here(category, heading))
			m.tk_popup(ev.x_root, ev.y_root)
			return
		m.add_command(label="Undo change", command=self.undo_category_order,
					  state="normal" if self._cat_order_undo else "disabled")
		if not row or not row.startswith(("c:", "pc:")):
			m.tk_popup(ev.x_root, ev.y_root)
			return
		m.add_separator()
		self.cats.selection_set(row)
		path = json.loads(row[3:])[1] if row.startswith("pc:") else row[2:]
		lead = self.todo.is_lead()
		m.add_command(label=path, state="disabled")
		self.group_project_menu(m, path, source_project=json.loads(row[3:])[0] if row.startswith("pc:") else None)
		m.add_command(label="Details, comments & links…", command=lambda: self.show_header_details(path, ""))
		m.add_command(label="📑 + Heading (in its idea list)...", command=lambda: (self.cats.selection_set(row), self.fill_ideas(), self.add_heading(path)))
		m.add_command(label="💡 New idea in it...", command=lambda: (self.cats.selection_set(row), self.post_here(path, "")))
		m.add_command(label="🎨 Colour...", command=lambda: self.pick_colour(path))
		if path in self.colours:
			m.add_command(label="No colour of its own", command=lambda: self.pick_colour(path, clear=True))
		m.add_separator()
		m.add_command(label="Rename...", command=lambda: self.rename_category(path), state="normal" if lead else "disabled")
		m.add_command(label="Remove", command=lambda: self.remove_category(path), state="normal" if lead else "disabled")
		m.tk_popup(ev.x_root, ev.y_root)

	def pick_colour(self, path, clear=False):
		if clear:
			self.colours.pop(path, None)
		else:
			col = colorchooser.askcolor(self.cat_colour(path) or "#e0a030", parent=self, title=f"Colour: {path}")[1]
			if not col:
				return
			self.colours[path] = col
			getattr(self.app, "feedback", lambda *_: None)("colour")
		self.todo.save()
		self.fill()

	def moved(self, old, new):
		"""old -> new for a heading and everything inside it: the categories, the ideas, the colours, your folds."""
		swap = lambda c: new + c[len(old):] if c == old or c.startswith(old + SEP) else c
		self.todo.data["idea_categories"] = list(dict.fromkeys(swap(c) for c in self.categories))
		self.relocate_headers(lambda c, h: (swap(c), h))
		heads = self.todo.data.setdefault("idea_headings", {})
		for c in [c for c in heads if swap(c) != c]:
			heads[swap(c)] = list(dict.fromkeys(heads.get(swap(c), []) + heads.pop(c)))
		for i in self.ideas:
			i["category"] = swap(i.get("category") or "")
		cols = self.colours
		for k in [k for k in cols if swap(k) != k]:
			cols[swap(k)] = cols.pop(k)
		self.app.config["idea_cat_closed"] = sorted({swap(c) for c in self.app.config.get("idea_cat_closed", [])})

	def rename_category(self, old):
		last = old.split(SEP)[-1]
		n = (simpledialog.askstring("Rename", f"New name for {last}:", initialvalue=last, parent=self) or "").replace("›", "-").strip()
		new = (old.rsplit(SEP, 1)[0] + SEP + n) if SEP in old else n
		if not n or new == old or new in self.cat_paths():
			return
		self.moved(old, new)
		self.todo.save()
		self.fill()

	def remove_category(self, path):
		inside = [c for c in self.cat_paths() if c.startswith(path + SEP)]
		used = sum(1 for i in self.ideas if in_cat(i, path))
		up = path.rsplit(SEP, 1)[0] if SEP in path else "Misc"
		if (used or inside) and not messagebox.askyesno(APP_NAME, f"Remove {path}" + (f" and its {len(inside)} heading{'s' if len(inside) != 1 else ''}" if inside else "")
															   + "?" + (f"\n\nIts {used} idea{'s' if used != 1 else ''} move to {up}." if used else ""), parent=self):
			return
		gone = {path} | set(inside)
		self.relocate_headers(lambda c, h: (up, h) if c in gone else (c, h))
		self.todo.data["idea_categories"] = [c for c in self.categories if c not in gone]
		if (used or any(r.get("category") == up for r in self.todo.data.get("idea_header_details", []))) and up not in self.cat_paths() + self.categories:
			self.categories.append(up)
		heads = self.todo.data.setdefault("idea_headings", {})
		for c in gone:
			if c in heads:
				heads[up] = list(dict.fromkeys(heads.get(up, []) + heads.pop(c)))
		for i in self.ideas:
			if (i.get("category") or "") in gone:
				i["category"] = up
		for c in gone:
			self.colours.pop(c, None)
		self.todo.save()
		self.fill()
