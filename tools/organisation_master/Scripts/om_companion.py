"""Opening any other master starts Organisation Master minimised when it isn't running, so what you do there (🟢 Online,
Developer Activity, 💬 Requests) reaches the team: the masters only write it on this PC, and Organisation Master shares it.

Not when Organisation Master has never been set up on this PC (its first start is its own tour), nor when Settings >
"🟢 Start in the background with the other masters" is off. Running = its own now-doing line is fresh, or a process of
it is there (the exe runs from a copy named OrganisationMaster-...)."""
import json
import os
import subprocess
import sys
import time

APPDATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OrganisationMaster")
LINE = os.path.join(APPDATA, "now", "Organisation Master.json")  # (now_doing.py's file for it)
LOCK = os.path.join(APPDATA, "starting.lock")  # (two masters opening at once start it once)


def settings():
	try:
		with open(os.path.join(APPDATA, "config.json"), encoding="utf-8") as f:
			return json.load(f)
	except (OSError, ValueError):
		return {}


def running():
	try:
		if time.time() - os.path.getmtime(LINE) < 90:
			return True
	except OSError:
		pass
	try:
		out = subprocess.check_output(["tasklist", "/fo", "csv", "/nh"], text=True, timeout=8,
									  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
		return any(row.strip('"').lower().startswith("organisationmaster") for row in out.splitlines())
	except (OSError, subprocess.SubprocessError):
		return True  # (can't tell: better not to start a second one)


def ensure(om_folder, env=None):
	"""Starts Organisation Master minimised (--background) if it's wanted here and not running. True when it did."""
	cfg = settings()
	if not cfg.get("launch_asked") or not cfg.get("start_with_masters", True):
		return False
	try:
		if time.time() - os.path.getmtime(LOCK) < 60:
			return False
	except OSError:
		pass
	if running():
		return False
	exe, script = os.path.join(om_folder, "OrganisationMaster.exe"), os.path.join(om_folder, "organisation_master.py")
	try:
		os.makedirs(APPDATA, exist_ok=True)
		open(LOCK, "w").close()
		if os.path.isfile(exe):
			subprocess.Popen([exe, "--background"], env=env)
		elif os.path.isfile(script):
			subprocess.Popen([sys.executable, script, "--background"], env=env)
		else:
			return False
		return True
	except OSError:
		return False
