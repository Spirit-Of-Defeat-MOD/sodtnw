"""🟢 What you're up to right now, for the team (Dev mode's Online now, the 👋 pop-up when someone opens a tool).

Every master writes a line about what you're doing to this PC's %APPDATA%\\OrganisationMaster\\now\\<tool>.json
(report: "Painting Aleutian (culture)", "Editing Japan (JAP) · Characters", "Playing RRdle (Hard)"...) and clears it
when it closes. Organisation Master gathers this PC's lines into the shared To Do data (todo_tasks.json "presence":
{dev: {doing: [{tool, text}], when}}), at most every PUBLISH_EVERY seconds, so the others see it through live sync.
Settings > "🟢 Share what I'm doing" off: the others only see that you're online."""
import datetime
import json
import os
import time

FOLDER = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OrganisationMaster", "now")
FRESH = 3 * 60  # (a tool's line older than this: the tool has stopped / crashed)
ONLINE = 12 * 60  # (a dev whose presence is older than this isn't online any more)
HEARTBEAT = 5 * 60  # (published again this often even when nothing changed, so they stay "online")
PUBLISH_EVERY = 30  # (seconds between two publishes: live sync isn't spammed while you paint)
_last = {}


def _path(tool):
	return os.path.join(FOLDER, "".join(c for c in tool if c.isalnum() or c in " _-").strip() + ".json")


def stamp():
	return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def report(tool, text):
	"""This tool is open and you're doing text. Cheap to call often: written when it changes, else once a minute."""
	text = " ".join(str(text or "").split())[:120]
	now = time.time()
	old = _last.get(tool)
	if old and old[0] == text and now - old[1] < 60:
		return
	since = old[2] if old and old[0] == text else stamp()
	_last[tool] = (text, now, since)
	try:
		os.makedirs(FOLDER, exist_ok=True)
		with open(_path(tool) + ".tmp", "w", encoding="utf-8") as f:
			json.dump({"tool": tool, "text": text, "since": since, "when": now}, f, ensure_ascii=False)
		os.replace(_path(tool) + ".tmp", _path(tool))
	except OSError:
		pass


def clear(tool):
	_last.pop(tool, None)
	try:
		os.remove(_path(tool))
	except OSError:
		pass


def local():
	"""[{tool, text, since}] the tools open on this PC, what changed last first."""
	out = []
	try:
		names = os.listdir(FOLDER)
	except OSError:
		return out
	for name in names:
		if not name.endswith(".json"):
			continue
		try:
			with open(os.path.join(FOLDER, name), encoding="utf-8") as f:
				e = json.load(f)
		except (OSError, ValueError):
			continue
		if time.time() - float(e.get("when", 0)) <= FRESH and e.get("tool"):
			out.append({"tool": e["tool"], "text": e.get("text", ""), "since": e.get("since", "")})
	return sorted(out, key=lambda e: e["since"], reverse=True)


def moment(s):
	try:
		d = datetime.datetime.fromisoformat(s)
		return d if d.tzinfo else d.astimezone()
	except (TypeError, ValueError):
		return None


def online(data, name):
	"""Their presence if they're online now (else None)."""
	p = (data.get("presence") or {}).get(name)
	when = moment((p or {}).get("when"))
	if not p or p.get("offline") or when is None:
		return None
	return p if (datetime.datetime.now().astimezone() - when).total_seconds() <= ONLINE else None


def describe(p, short=False):
	"""'painting Aleutian (Culture Master)' / 'online'."""
	doing = (p or {}).get("doing") or []
	if not doing:
		return "online"
	first = doing[0]
	text = f"{first['text']} ({first['tool']})" if first.get("text") else f"in {first['tool']}"
	if not short and len(doing) > 1:
		text += " · also " + ", ".join(d["tool"] for d in doing[1:])
	return text


class Publisher:
	"""In Organisation Master: this PC's tools' lines into the shared data (throttled), and offline on closing."""

	def __init__(self, todo, share):
		self.todo, self.share = todo, share  # (share(): Settings > Share what I'm doing)
		self.published = 0

	def tick(self):
		"""True when the shared presence changed (the caller saves)."""
		me = self.todo.me.get()
		if not me:
			return False
		doing = [{"tool": e["tool"], "text": e["text"] if self.share() else ""} for e in local()]
		store = self.todo.data.setdefault("presence", {})
		old = store.get(me) or {}
		now = time.time()
		changed = old.get("doing") != doing or old.get("offline")
		if (changed and now - self.published >= PUBLISH_EVERY) or now - self.published >= HEARTBEAT:
			store[me] = {"doing": doing, "when": stamp()}
			self.published = now
			return True
		return False

	def offline(self):
		me = self.todo.me.get()
		if me:
			self.todo.data.setdefault("presence", {})[me] = {"doing": [], "when": stamp(), "offline": True}
