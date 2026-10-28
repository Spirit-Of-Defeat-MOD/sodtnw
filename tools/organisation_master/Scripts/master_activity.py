"""Per-event local inbox: other masters report saved work without editing the live task database."""
import datetime
import hashlib
import json
import os
import subprocess
import uuid

MASTERS = ("Organisation Master", "To Do Master", "Ideas", "Dev VCs", "Music Master", "Culture Master", "Country Master",
		   "AI")  # ("AI": Claude / ChatGPT adding To Do tasks, see ai_tasks.py)
try:  # (new masters register themselves: tools/<folder>/master.json)
	import masters as _masters
	MASTERS += tuple(m["name"] for m in _masters.discovered())
except Exception:
	pass
ACTIONS = ("opened", "saved", "changed", "portrait_unmarked", "portrait_marked", "state_review", "country_review", "add_task")


def root_key(root):
	return hashlib.sha256(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:20]


def inbox(root):
	base = os.environ.get("APPDATA", os.path.expanduser("~"))
	return os.path.join(base, "OrganisationMaster", "activity", root_key(root))


def actor(root):
	try:
		base = os.environ.get("APPDATA", os.path.expanduser("~"))
		with open(os.path.join(base, "OrganisationMaster", "config.json"), encoding="utf-8") as f:
			name = json.load(f).get("todo_me")
		if name:
			return name
	except (OSError, ValueError):
		pass
	try:
		return subprocess.check_output(["git", "-C", root, "config", "user.name"], text=True, timeout=3,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).strip()
	except (OSError, subprocess.SubprocessError):
		return ""


def record(master, root, action="saved", files=(), who=None, sprite=None, state=None, detail=None):
	if master not in MASTERS or action not in ACTIONS:
		return False
	event = dict(id=uuid.uuid4().hex, master=master, action=action, files=list(files), who=who or actor(root),
		when=datetime.datetime.now().astimezone().isoformat())
	if detail:
		event["detail"] = str(detail)
	if sprite:
		event["sprite"] = sprite
	if state is not None:
		event["state"] = state
	try:
		folder = inbox(root)
		os.makedirs(folder, exist_ok=True)
		path = os.path.join(folder, event["id"] + ".json")
		with open(path + ".tmp", "w", encoding="utf-8") as f:
			json.dump(event, f, ensure_ascii=False)
		os.replace(path + ".tmp", path)
		return True
	except OSError:
		return False  # A missing activity inbox must not interrupt a successful mod save.


def pending(root):
	try:
		files = os.listdir(inbox(root))
	except OSError:
		return []
	events = []
	for filename in files:
		if len(filename) != 37 or not filename.endswith(".json"):
			continue
		path = os.path.join(inbox(root), filename)
		try:
			with open(path, encoding="utf-8") as f:
				event = json.load(f)
			if (event.get("id") + ".json" == filename and event.get("master") in MASTERS
				and event.get("action") in ACTIONS
				and isinstance(event.get("who"), str) and event["who"].strip()):
				events.append((path, event))
		except (OSError, ValueError, TypeError, AttributeError):
			continue
	return sorted(events, key=lambda row: (row[1].get("when", ""), row[1]["id"]))


def acknowledge(paths):
	for path in paths:
		try:
			os.remove(path)
		except OSError:
			pass
