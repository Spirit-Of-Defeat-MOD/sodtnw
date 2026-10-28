"""Which masters there are. Culture and Country Master are built in; a new master registers itself with a master.json
in its folder (tools/<folder>/master.json, see master_template/), and Organisation Master's Masters menu, the activity
inbox, rr:// links and the update check all pick it up.

master.json: {"name": "Focus Master", "exe": "FocusMaster.exe", "script": "focus_master.py",
              "description": "one line for Organisation Master's side bar", "link": "focus", "link_kinds": ["tree", "focus"]}"""
import json
import os

import paths

BUILT_IN = (
	{"name": "Culture Master", "folder": "culture_master", "exe": "CultureMaster.exe", "script": "culture_master.py",
	 "description": "Cultures, religions, languages and their map: groups, minorities, orders, migratory cultures and bands."},
	{"name": "Country Master", "folder": "country_master", "exe": "CountryMaster.exe", "script": "country_master.py",
	 "description": "Countries: leaders, ideas, OOB, collapses, sub-ideologies, parties, formables, generics."},
)


def discovered():
	"""The masters with a master.json in tools/<folder> (the template folder itself isn't one)."""
	tools = os.path.dirname(paths.TOOL)
	out = []
	try:
		folders = sorted(os.listdir(tools))
	except OSError:
		return out
	for folder in folders:
		path = os.path.join(tools, folder, "master.json")
		if folder in ("organisation_master",) or not os.path.isfile(path):
			continue
		try:
			with open(path, encoding="utf-8") as f:
				m = json.load(f)
		except (OSError, ValueError):
			continue
		if m.get("name") and m.get("script") and m["name"] not in {b["name"] for b in BUILT_IN}:
			out.append(dict(m, folder=folder))
	return out


def every():
	return list(BUILT_IN) + discovered()
