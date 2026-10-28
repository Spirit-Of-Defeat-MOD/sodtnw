"""🩺 The To Do data checked for things that point at nothing (live sync with several people makes them more likely):
the safe ones are fixed straight away, the rest are listed for a person to decide. Runs a few seconds after start-up
(and Settings > Check the To Do data...)."""
import collections
import re
import tkinter as tk
from tkinter import ttk

import ui


def check(data):
	"""(fixed, problems): lists of sentences. data is changed for the fixes."""
	fixed, problems = [], []
	tasks = data.get("tasks", [])
	refs = collections.Counter(t.get("ref") for t in tasks)
	have = set(refs)
	for ref, n in refs.items():
		if n > 1:
			problems.append(f"{n} tasks share the number {ref}: open them and give one a new number (or delete the copy).")
	projects = {p.get("name") for p in data.get("projects", [])}
	devs = {d.get("name") for d in data.get("devs", [])}
	for t in tasks:
		ref = t.get("ref", "?")
		if t.get("parent") and t["parent"] not in have:
			fixed.append(f"{ref} was a sub-task of {t['parent']}, which is gone: it's a task of its own now.")
			t.pop("parent")
		if t.get("follow_up_of") and t["follow_up_of"] not in have:
			fixed.append(f"{ref} followed up {t['follow_up_of']}, which is gone: link removed.")
			t.pop("follow_up_of")
		gone = [d for d in t.get("depends_on") or [] if d not in have]
		if gone:
			t["depends_on"] = [d for d in t["depends_on"] if d in have]
			fixed.append(f"{ref} waited on {', '.join(gone)}, which {'is' if len(gone) == 1 else 'are'} gone: no longer waiting on {'it' if len(gone) == 1 else 'them'}.")
		if t.get("project") and t["project"] not in projects:
			data.setdefault("projects", []).append({"name": t["project"], "note": "", "set_by": "data check"})
			projects.add(t["project"])
			fixed.append(f"The project {t['project']} (used by {ref}) was missing: made again.")
		strangers = [d for d in t.get("devs") or [] if d not in devs]
		if strangers:
			problems.append(f"{ref} is assigned to {', '.join(strangers)}, who {'isn' if len(strangers) == 1 else 'aren'}'t in the Dev list (renamed? add them, or reassign it).")
	nums = [int(m.group(1)) for r in have if r and (m := re.match(r"RR-(\d+)$", r))]
	if nums and (data.get("next_ref") or 0) <= max(nums):
		data["next_ref"] = max(nums) + 1
		fixed.append(f"The next task number was behind: now RR-{data['next_ref']:04d}.")
	ideas = data.get("ideas", [])
	ids = collections.Counter(i.get("id") for i in ideas)
	for iid, n in ids.items():
		if n > 1:
			problems.append(f"{n} ideas share the id {iid}: delete the copy.")
	cats = data.setdefault("idea_categories", [])
	heads = data.setdefault("idea_headings", {})
	for i in ideas:
		title = i.get("title", "?")[:50]
		if i.get("task") and i["task"] not in have:
			fixed.append(f"The idea \"{title}\" was linked to {i['task']}, which is gone: link removed.")
			i["task"] = ""
		if i.get("project") and i["project"] not in projects:
			fixed.append(f"The idea \"{title}\" was in the project {i['project']}, which is gone: no project now.")
			i["project"] = ""
		if i.get("dup_of") and i["dup_of"] not in ids:
			problems.append(f"The idea \"{title}\" is a duplicate of an idea that's gone: reopen it if it's still wanted.")
		cat = i.get("category")
		if cat and cat.split(" › ")[0] not in cats:
			cats.append(cat.split(" › ")[0])
			fixed.append(f"The idea category {cat} (used by \"{title}\") was missing: made again.")
		h = i.get("heading")
		if cat and h and h not in heads.setdefault(cat, []):
			heads[cat].append(h)
			fixed.append(f"The heading {cat} › {h} (used by \"{title}\") was missing: made again.")
	by_title = {}
	for t in tasks:  # (an open task first: a proposal's task that was removed as a duplicate lives on under another number)
		key = (t.get("title") or "").strip().lower()
		if key and (key not in by_title or (by_title[key].get("status") in ("Completed", "Not Possible") and t.get("status") not in ("Completed", "Not Possible"))):
			by_title[key] = t
	for v in data.get("vcs", []):
		for p in v.get("proposals", []):
			if p.get("state") == "committed" and p.get("ref") and p["ref"] not in have:
				same = by_title.get((p.get("title") or "").strip().lower())
				if same:
					fixed.append(f"Dev VC {v.get('date', '?')}: the proposal \"{p.get('title', '')[:60]}\" pointed at {p['ref']}, which is gone; "
								 f"the same task is {same['ref']}, so it points there now.")
					p["ref"] = same["ref"]
				else:
					problems.append(f"Dev VC {v.get('date', '?')}: a committed proposal points at {p['ref']}, which is gone (deleted? check the 🗑 Trash).")
	for item_id, r in ((data.get("gfx") or {}).get("items") or {}).items():
		if isinstance(r, dict) and r.get("task") and r["task"] not in have:
			fixed.append(f"The GFX item {item_id} was claimed by {r['task']}, which is gone: it's free to claim again.")
			r.pop("task")
	return fixed, problems


def show(parent, todo):
	"""Settings > Check the To Do data...: run it now and list what it found."""
	fixed, problems = todo.run_data_check(quiet=True)
	w = tk.Toplevel(parent)
	w.title("Check the To Do data")
	w.transient(parent.winfo_toplevel())
	f = ttk.Frame(w, padding=12)
	f.pack(fill="both", expand=True)
	ttk.Label(f, text="🩺 To Do data check", font="om_bold").pack(anchor="w")
	ttk.Label(f, text="Links to things that are gone are fixed by themselves; the rest needs a person.", style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
	box = tk.Text(f, width=90, height=18, wrap="word", font="om_body", relief="flat")
	box.pack(fill="both", expand=True)
	box.tag_configure("head", font="om_bold")
	if not fixed and not problems:
		box.insert("end", "✓ Everything points where it should.\n")
	if problems:
		box.insert("end", f"Needs a person ({len(problems)})\n", "head")
		box.insert("end", "".join(f"• {p}\n" for p in problems) + "\n")
	if fixed:
		box.insert("end", f"Fixed ({len(fixed)})\n", "head")
		box.insert("end", "".join(f"• {p}\n" for p in fixed))
	box.config(state="disabled")
	ttk.Button(f, text="Close", command=w.destroy).pack(anchor="e", pady=(8, 0))
