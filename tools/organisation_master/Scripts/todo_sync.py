"""Live To Do: the To Do Master's data (todo_tasks.json) kept in a git repository of its own (sync.json: "remote"),
pulled and pushed in the background, so nobody has to commit or push it. Being its own repository, the RR repository
(and the Discord git tracker watching it) never sees these commits.

The local copy is a clone in %LOCALAPPDATA%/OrganisationMaster/todo_sync. Changes are merged per task and per field
(both sides' changes kept; the same field changed on both sides: the newer task wins), RR numbers given out twice
are renumbered."""
import copy
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

BRANCH = "main"
FILE = "todo_tasks.json"
PICTURES = "idea_pictures"  # (the Ideas' pictures: synced with it)
MUSIC_LOGOS = "planned_station_logos"
CLONE = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "OrganisationMaster", "todo_sync")
MISSING = object()


def settings(tool_dir):
	try:
		return json.load(open(os.path.join(tool_dir, "sync.json"), encoding="utf-8"))
	except (OSError, ValueError):
		return {}


def git(*args, stdin=None, timeout=60):
	"""(ok, output) of a git command in the clone. No console window, no password prompt in a console (the Git
	Credential Manager's own sign-in window still comes up when needed)."""
	try:
		r = subprocess.run(["git", "-C", CLONE, *args], input=stdin, capture_output=True, text=True, encoding="utf-8",
						   timeout=timeout, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
						   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		return r.returncode == 0, (r.stdout if r.returncode == 0 else r.stderr).strip()
	except (OSError, subprocess.SubprocessError) as ex:
		return False, str(ex)


def dump(data):
	return json.dumps(data, indent=1, ensure_ascii=False)


def parse(text):
	try:
		return json.loads(text) if text else None
	except ValueError:
		return None


# ---------------- merging (base: the last version both sides had) ----------------
def _ident(items):
	for k in ("ref", "id", "name"):
		if items and all(isinstance(x, dict) and k in x for x in items):
			return k
	return None


def _scalar(x):
	return x is None or isinstance(x, (str, int, float, bool))


def merge_text(base, mine, theirs):
	"""Both sides changed a text (Dev VC notes, descriptions...): line by line, so two people typing in different places
	both keep theirs; lines both changed keep mine then theirs (nothing typed is lost)."""
	b, m, t = (s.splitlines(keepends=True) for s in (base, mine, theirs))
	for lines in (b, m, t):  # (a last line without its newline still counts as the same line)
		if lines and not lines[-1].endswith("\n"):
			lines[-1] += "\n"

	def hunks(other):
		return [(i1, i2, other[j1:j2]) for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, b, other, autojunk=False).get_opcodes()
				if op != "equal"]

	def version(hs, lo, hi):
		out, at = [], lo
		for i1, i2, rep in hs:
			out += b[at:i1] + rep
			at = i2
		return out + b[at:hi]
	changes = sorted([(i1, i2, rep, 0) for i1, i2, rep in hunks(m)] + [(i1, i2, rep, 1) for i1, i2, rep in hunks(t)], key=lambda h: (h[0], h[1]))
	out, at, k = [], 0, 0
	while k < len(changes):
		lo, hi = changes[k][0], changes[k][1]
		group = [changes[k]]
		k += 1
		while k < len(changes) and (changes[k][0] < hi or changes[k][0] == lo == changes[k][1] or changes[k][0] == hi == lo):
			hi = max(hi, changes[k][1])
			group.append(changes[k])
			k += 1
		out += b[at:lo]
		mv = version([(i1, i2, rep) for i1, i2, rep, side in group if side == 0], lo, hi)
		tv = version([(i1, i2, rep) for i1, i2, rep, side in group if side == 1], lo, hi)
		out += mv if mv == tv or not any(side for *_, side in group) else tv if all(side for *_, side in group) else mv + [x for x in tv if x not in mv]
		at = hi
	out += b[at:]
	text = "".join(out)
	return text if mine.endswith("\n") or theirs.endswith("\n") else text[:-1] if text.endswith("\n") else text


def merge(base, mine, theirs, mine_wins=True):
	if mine == theirs:
		return mine
	if base is not MISSING and mine == base:
		return theirs
	if base is not MISSING and theirs == base:
		return mine
	if (isinstance(base, str) and isinstance(mine, str) and isinstance(theirs, str)
			and ("\n" in base + mine + theirs or max(len(mine), len(theirs)) > 60 and " " in mine + theirs)):  # (written text, not a name, status or link)
		return merge_text(base, mine, theirs)
	if isinstance(mine, dict) and isinstance(theirs, dict):
		b = base if isinstance(base, dict) else {}
		if isinstance(mine.get("updated"), str) and isinstance(theirs.get("updated"), str):
			mine_wins = mine["updated"] >= theirs["updated"]  # (a task: the one changed last wins a clash)
		out = {}
		for k in list(mine) + [k for k in theirs if k not in mine]:
			bk = b.get(k, MISSING)
			if k in mine and k in theirs:
				out[k] = merge(bk, mine[k], theirs[k], mine_wins)
			elif k in mine:
				if bk is MISSING or bk != mine[k]:  # (added here, or changed here while they removed it)
					out[k] = mine[k]
			elif bk is MISSING or bk != theirs[k]:
				out[k] = theirs[k]
		return out
	if isinstance(mine, list) and isinstance(theirs, list):
		b = base if isinstance(base, list) else []
		key = _ident(mine + theirs) if mine or theirs else None
		if key:
			bm = {x[key]: x for x in b if isinstance(x, dict) and key in x}
			mm = {x[key]: x for x in mine}
			tm = {x[key]: x for x in theirs}
			out = []
			for k in list(dict.fromkeys([x[key] for x in theirs] + [x[key] for x in mine])):
				if k in mm and k in tm:
					out.append(merge(bm.get(k, MISSING), mm[k], tm[k], mine_wins))
				elif k in mm:
					if k not in bm or bm[k] != mm[k]:
						out.append(mm[k])
				elif k not in bm or bm[k] != tm[k]:
					out.append(tm[k])
			return out
		if len(mine) == len(theirs) == len(b) and b:  # (the same list with items changed in place: agenda ticks...)
			return [merge(x, y, z, mine_wins) for x, y, z in zip(b, mine, theirs)]
		return [x for x in theirs if x in mine or x not in b] + [x for x in mine if x not in theirs and x not in b]
	return mine if mine_wins else theirs


def _num(ref):
	m = re.match(r"RR-(\d+)$", ref or "")
	return int(m.group(1)) if m else 0


def preserve_recorded_changes(base_task, task):
	"""A strict older history subset is a stale snapshot, not an explicit reopen/unclaim."""
	if not base_task or task.get("created") != base_task.get("created"):
		return task
	before, history = base_task.get("history") or [], task.get("history") or []
	if (not before or len(history) >= len(before) or any(event not in before for event in history)
			or str(task.get("updated") or "") > str(base_task.get("updated") or "")):
		return task
	repaired = copy.deepcopy(task)
	latest = {event.get("field"): event for event in before}
	closure_recorded = False
	for field, event in latest.items():
		if field in (None, "created", "history", "updated", "closed"):
			continue
		if event.get("new") == base_task.get(field) and field in base_task:
			repaired[field] = copy.deepcopy(base_task[field])
			closure_recorded |= field in ("status", "archived")
	if closure_recorded:
		if "closed" in base_task:
			repaired["closed"] = base_task["closed"]
		else:
			repaired.pop("closed", None)
	repaired["history"] = copy.deepcopy(before)
	repaired["updated"] = base_task.get("updated", task.get("updated"))
	return repaired


VC_TEXTS = ("discussion", "decisions", "actions", "notes")


def note_taker_first(base, mine, theirs, out, me):
	"""Dev VC texts (notes...) after the general merge. Each records who wrote it last and when ('edited'):
	- a copy older than the other side's, by the same person, is stale (a PC still showing an earlier version): the newer
	  text wins outright, so deleting a line sticks;
	- both sides written since the version they share, by different people: line by line, the note taker's lines first
	  (merge() puts this PC's first, so it's turned round when this PC isn't the note taker)."""
	def by_id(side):
		return {v["id"]: v for v in side.get("vcs", []) if isinstance(v, dict) and "id" in v}
	bv, mv, tv = by_id(base), by_id(mine), by_id(theirs)
	for v in out.get("vcs", []):
		if v.get("id") not in tv or v.get("id") not in mv:
			continue
		b, m, t = bv.get(v["id"], {}), mv[v["id"]], tv[v["id"]]
		taker = v.get("note_taker")
		for k in VC_TEXTS:
			bk, mk, tk = (x.get(k, "") if isinstance(x.get(k, ""), str) else "" for x in (b, m, t))
			if mk == tk:
				continue
			ms, ts_, bs = ((x.get("edited") or {}).get(k) or {} for x in (m, t, b))
			if ms.get("when") and ts_.get("when") and ms["when"] != ts_["when"]:
				(new, ns), (old, os_) = sorted(((mk, ms), (tk, ts_)), key=lambda p: p[1]["when"], reverse=True)
				both_wrote = os_.get("by") != ns.get("by") and old != bk and os_["when"] > (bs.get("when") or 0)
				if not both_wrote:
					v[k] = new
					v.setdefault("edited", {})[k] = dict(ns)
					continue
				first, second = (mk, tk) if taker == me or not taker else (tk, mk)
				v[k] = merge_text(bk, first, second)
				v.setdefault("edited", {})[k] = dict(ns)
			elif taker and taker != me and mk != bk and tk != bk:
				v[k] = merge_text(bk, tk, mk)


def merge_data(base, mine, theirs, me=None):
	"""The To Do data of both sides together (me: who this PC is, for the note taker's priority). mine is changed (RR numbers given out on both sides are renumbered here;
	a task both sides made for the same link (Music / Country Master) is kept once)."""
	base = base or {}
	# Older clients can send a stale whole-file snapshot. Absence alone is not a delete.
	mine, theirs = dict(mine), dict(theirs)
	base_tasks = {task["ref"]: task for task in base.get("tasks", [])}
	for side in (mine, theirs):
		side["tasks"] = [preserve_recorded_changes(base_tasks.get(task["ref"]), task) for task in side.get("tasks", [])]
	deletions = {}
	for collection, key in (("projects", "name"), ("tasks", "ref")):
		field = "deleted_" + collection
		journal = {}
		for side in (base, mine, theirs):
			for ident, entry in (side.get(field) or {}).items():
				if ident not in journal or entry.get("when", "") > journal[ident].get("when", ""):
					journal[ident] = entry
		deletions[collection] = journal
		for side in (mine, theirs):
			items = list(side.get(collection, []))
			present = {item[key] for item in items}
			for item in base.get(collection, []):
				entry = journal.get(item[key])
				deleted = entry is not None and entry.get("created") == item.get("created") and not entry.get("restored")
				if item[key] not in present and not deleted:
					items.append(copy.deepcopy(item))
			side[collection] = items
	b_refs = {t["ref"] for t in base.get("tasks", [])}
	t_tasks = {t["ref"]: t for t in theirs.get("tasks", [])}
	t_links = {t["link"]: t["ref"] for t in theirs.get("tasks", []) if t.get("link") and t["ref"] not in b_refs}
	used = set(t_tasks) | {t["ref"] for t in mine.get("tasks", [])}
	n = max(mine.get("next_ref", 1), theirs.get("next_ref", 1), max(map(_num, used), default=0) + 1)
	remap, keep = {}, []
	for t in mine.get("tasks", []):
		r = t["ref"]
		if r not in b_refs and t.get("link") in t_links:
			remap[r] = t_links[t["link"]]  # (the same task, made on both sides)
			continue
		if r not in b_refs and r in t_tasks and (t_tasks[r].get("created"), t_tasks[r].get("set_by")) != (t.get("created"), t.get("set_by")):
			while f"RR-{n:04d}" in used:
				n += 1
			remap[r] = t["ref"] = f"RR-{n:04d}"
			used.add(t["ref"])
		keep.append(t)
	if remap:
		mine["tasks"] = keep
		for t in keep:
			if t.get("follow_up_of") in remap:
				t["follow_up_of"] = remap[t["follow_up_of"]]
			if any(isinstance(link, str) and link.startswith("task:") and link[5:] in remap for link in t.get("links", [])):
				t["links"] = ["task:" + remap.get(link[5:], link[5:]) if isinstance(link, str) and link.startswith("task:") else link for link in t["links"]]
			if t.get("parent") in remap:
				t["parent"] = remap[t["parent"]]
			if any(d in remap for d in t.get("depends_on", [])):
				t["depends_on"] = [remap.get(d, d) for d in t["depends_on"]]
	out = merge(base, mine, theirs)
	from milestone_celebration import merge_records, restore_status
	if any("milestone_celebrations" in side or "milestone_celebration_seen" in side for side in (base, mine, theirs)):
		out.update(merge_records(base, mine, theirs))
		restore_status(out)
	# A daily answer is write-once. Preserve the shared base; for simultaneous
	# first publications the already-published remote wins, including on stale PCs.
	daily = {}
	for side in (mine, theirs, base):
		for day, levels in side.get("rr_daily", {}).items():
			for level, tag in levels.items():
				if isinstance(tag, str):daily.setdefault(day, {})[level] = tag
	if daily:out["rr_daily"] = daily
	# Scores are retained run records: stale clients may not know the field, and
	# catches can only increase a run's score. Never discard a recorded best.
	for score_key in ("sleigh_scores", "rr_game_scores"):
		if not any(score_key in side for side in (base, mine, theirs)):
			continue
		runs = {}
		for side in (base, mine, theirs):
			for run in side.get(score_key, []):
				key = run.get("id")
				if not key: continue
				old = runs.get(key)
				def rank(r):
					if r.get("game") == "rrdle":
						return (len(r.get("guesses", [])), r.get("updated", ""), bool(r.get("finished")), r.get("score", 0))
					return (r.get("score", 0), bool(r.get("finished") or r.get("completed")))
				if old is None or rank(run) > rank(old):
					runs[key] = run
		out[score_key] = list(runs.values())
	note_taker_first(base, mine, theirs, out, me)
	for collection, key in (("projects", "name"), ("tasks", "ref")):
		journal = deletions[collection]
		if journal:
			out["deleted_" + collection] = journal
			out[collection] = [item for item in out.get(collection, []) if not (
				item[key] in journal and journal[item[key]].get("created") == item.get("created")
				and not journal[item[key]].get("restored"))]  # (restored from the 🗑 Trash: alive again)
	out["next_ref"] = max(n, max((_num(t["ref"]) for t in out.get("tasks", [])), default=0) + 1)
	return out, remap


def blocking_dialog_open(page):
	"""Editing dialogs defer incoming changes; floating utility windows do not."""
	main = str(page.winfo_toplevel())
	for window in page.tk.splitlist(page.tk.call("wm", "stackorder", ".")):
		if str(window) == main:
			continue
		try:
			widget = page.nametowidget(str(window))
		except KeyError:
			return True  # A native Tk dialog has no Python wrapper.
		if not getattr(widget, "_om_nonmodal", False):
			return True
	return False


# ---------------- the background sync ----------------
class Sync:
	"""Runs git in a thread; the merging and the data stay on the window's (tk) thread. page: the To Do Master
	(.data, .apply_remote(data), .sync_status(text))."""

	def __init__(self, page, tool_dir):
		self.page = page
		self.cfg = settings(tool_dir)
		self.remote = (self.cfg.get("remote") or "").strip()
		self.ready = bool(self.remote) and os.path.isdir(os.path.join(CLONE, ".git"))
		self.busy = False
		self.seed = None  # (the data as loaded from the RR folder, before the clone was there)
		self._job = None
		self._result = None

	@property
	def on(self):
		return bool(self.remote)

	def path(self):
		return os.path.join(CLONE, FILE) if self.ready else None

	def start(self, seed_text):
		if not self.on:
			self.page.sync_status("Live sync off (no repository in sync.json)")
			return
		self.seed = seed_text if not self.ready else None
		self.page.after(1500, self.cycle)

	def soon(self, ms=3000):
		"""After a change: sent a few seconds later (a burst of changes goes in one commit)."""
		if not self.on:
			return
		if self._job:
			self.page.after_cancel(self._job)
		self._job = self.page.after(ms, self.cycle)

	def _thread(self, work, then):
		self.busy = True

		def run():
			try:
				self._result = ("ok", work())
			except Exception as ex:  # (shown, never fatal)
				self._result = ("error", ex)
		threading.Thread(target=run, daemon=True).start()
		self._wait(then)

	def _wait(self, then):
		if self._result is None:
			self.page.after(150, lambda: self._wait(then))
			return
		kind, value = self._result
		self._result = None
		self.busy = False
		if kind == "error":
			self._misses = getattr(self, "_misses", 0) + 1
			self.page.sync_status(f"○ Live sync: {value}" if self._misses >= 3 else "● Live (reconnecting...)")
			self.soon(20000 if self._misses >= 3 else 4000)
		else:
			then(value)

	# phase 1 (thread): get the others' version
	def cycle(self):
		self._job = None
		if not self.page.winfo_exists():
			return
		if self.busy:  # (a change while one is on its way: right after it)
			self._again = True
			return
		self._thread(self._fetch, self._merge)

	def _fetch(self):
		if not os.path.isdir(os.path.join(CLONE, ".git")):
			os.makedirs(os.path.dirname(CLONE), exist_ok=True)
			r = subprocess.run(["git", "clone", "-q", self.remote, CLONE], capture_output=True, text=True, encoding="utf-8",
							   timeout=120, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
							   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
			if r.returncode != 0:
				raise RuntimeError("can't reach the To Do repository (" + (r.stderr.strip().splitlines() or ["?"])[-1] + ")")
		elif git("remote", "get-url", "origin")[1] != self.remote:
			git("remote", "set-url", "origin", self.remote)
		online, _ = git("fetch", "-q", "origin", BRANCH, timeout=25)
		has_remote = git("rev-parse", "-q", "--verify", f"refs/remotes/origin/{BRANCH}")[0]
		for assets in (PICTURES, MUSIC_LOGOS):
			if has_remote and git("ls-tree", "-d", "--name-only", f"origin/{BRANCH}", assets)[1]:
				git("checkout", f"origin/{BRANCH}", "--", assets)
		theirs = git("show", f"origin/{BRANCH}:{FILE}")[1] if has_remote else None
		base = None
		ok, mb = git("merge-base", "HEAD", f"origin/{BRANCH}") if has_remote else (False, "")
		if ok:
			base = git("show", f"{mb}:{FILE}")[1]
		return {"online": online, "theirs": parse(theirs), "base": parse(base), "has_remote": has_remote}

	# phase 2 (tk thread): merge into what's on screen
	def _merge(self, got):
		page = self.page
		first = not self.ready
		if first:
			self.ready = True  # (from now on the data is the clone's file)
		theirs, base = got["theirs"], got["base"]
		if first and self.seed is not None:
			base = parse(self.seed)  # (what this PC had before: its changes since are kept)
		page.flush_notes(save=False)
		music = getattr(page.app, "existing_music_page", lambda: None)()
		if music is not None:
			music.flush_plan()
			if self.ready:
				music.copy_plan_logos(Path(CLONE))
		for pane in ("vc_pane", "idea_pane"):  # (a Dev VC note / idea typed a moment ago)
			if hasattr(page, pane):
				getattr(page, pane).flush()
		mine = json.loads(json.dumps(page.data))
		if theirs is None:  # (an empty repository: this PC's To Do starts it, if it has any tasks)
			if not mine.get("tasks"):
				page.sync_status("○ Live sync: the To Do repository is empty (waiting for someone to start it)")
				self.ready = False
				self.soon(30000)
				return
			merged, remap = mine, {}
		else:
			merged, remap = merge_data(base if base is not None else theirs, mine, theirs, page.me.get())
		if merged != page.data or first:
			if blocking_dialog_open(page):  # Keep editing dialogs safe while allowing floating Radio.
				page.incoming_alerts = merged.get("error_alerts") or []  # (🚨 an error alert still pops up: error_alerts.py)
				if first:
					self.ready = False
				self.soon(5000)
				return
			page.incoming_alerts = None
			page.apply_remote(merged, remap, first)
		if theirs is None or merged != theirs:
			self._thread(lambda: self._push(dump(merged), got["has_remote"]), self._pushed)
		else:  # (nothing of ours to send: theirs is now the version both sides had, the base of the next merge)
			self._thread(lambda: git("reset", "-q", f"origin/{BRANCH}"), lambda _: self._done(got["online"]))

	# phase 3 (thread): send the merged version
	def _push(self, text, has_remote, who=None):
		if has_remote:
			git("reset", "-q", f"origin/{BRANCH}")  # (on top of theirs: their files in the index, ours go in below)
		ok, sha = git("hash-object", "-w", "--stdin", stdin=text)
		if not ok:
			raise RuntimeError(sha)
		git("update-index", "--add", "--cacheinfo", f"100644,{sha},{FILE}")
		for assets in (PICTURES, MUSIC_LOGOS):
			if os.path.isdir(os.path.join(CLONE, assets)):
				git("add", assets)
		who = who or self.page.me.get() or "Organisation Master"
		name = git("config", "user.name")[1] or who
		mail = git("config", "user.email")[1] or "organisation-master@users.noreply.github.com"
		ok, out = git("-c", f"user.name={name}", "-c", f"user.email={mail}", "commit", "-q", "-m", f"To Do: {who}")
		if not ok and "nothing to commit" not in out:
			raise RuntimeError(out)
		ok, out = git("push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")
		if ok:
			return "sent"
		low = out.lower()
		return "beaten" if any(w in low for w in ("rejected", "fetch first", "non-fast-forward", "stale info")) else "offline"

	def _pushed(self, result):
		if result == "beaten":  # (someone sent theirs a moment before: not offline - merge theirs in and send again now)
			self.page.sync_status("● Live (taking in someone's change...)")
			self.soon(300)
			return
		self._done(result == "sent")

	def _done(self, online):
		self._misses = 0 if online else getattr(self, "_misses", 0) + 1
		if getattr(self, "_again", False):
			self._again = False
			self.soon(500)
			return
		if online:
			self.page.sync_status(f"● Live (synced {time.strftime('%H:%M')})")
		elif self._misses < 3:  # (one slow fetch or push isn't 'offline': try again shortly, quietly)
			self.page.sync_status("● Live (reconnecting...)")
			self.soon(4000)
			return
		else:
			self.page.sync_status("○ Live sync: offline - your changes are kept and sent when it's back")
		self.soon(20000 if online else 15000)

	def final(self):
		"""Closing: anything not sent yet goes now - in a thread of its own, so the window closes at once (the program
		keeps running, unseen, the few seconds the fetch and push take: the thread isn't a daemon)."""
		if not self.ready or self.busy:
			return None
		text, who = dump(self.page.data), self.page.me.get()  # (the data and name now: the window is about to go)

		def send():
			try:
				mine = parse(text)
				has_remote = git("rev-parse", "-q", "--verify", f"refs/remotes/origin/{BRANCH}")[0]
				if has_remote and parse(git("show", f"origin/{BRANCH}:{FILE}")[1]) == mine:
					return
				git("fetch", "-q", "origin", BRANCH, timeout=8)
				out = text
				theirs = parse(git("show", f"origin/{BRANCH}:{FILE}")[1])
				if theirs is not None and theirs != mine:
					ok, mb = git("merge-base", "HEAD", f"origin/{BRANCH}")
					base = parse(git("show", f"{mb}:{FILE}")[1]) if ok else theirs
					merged, _ = merge_data(base, mine, theirs, who)
					out = dump(merged)
					with open(os.path.join(CLONE, FILE), "w", encoding="utf-8") as f:
						f.write(out)  # (the copy here matches what was sent)
				self._push(out, git("rev-parse", "-q", "--verify", f"refs/remotes/origin/{BRANCH}")[0], who)
			except Exception:
				pass  # (sent next time it opens)
		th = threading.Thread(target=send, name="todo-final-sync", daemon=False)
		th.start()
		return th
