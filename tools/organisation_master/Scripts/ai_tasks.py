"""For Claude / ChatGPT: add To Do tasks to Organisation Master (live, while it's open) instead of writing them in a text
file. Each task goes into this PC's activity inbox; the running Organisation Master adds it within a few seconds and
live sync shares it (a closed one adds it next time it opens). Don't close / reopen Organisation Master for this.

    python tools/organisation_master/Scripts/ai_tasks.py tasks.json [--who "Chat Jipity"]

tasks.json: a list of {"title", "note", "project", "category", "priority", "devs", "parent", "key"} (only title is
needed). Use existing projects / categories / dev names (the To Do lists them); parent is a task's RR number; key is a
short unique id (e.g. "dual-leaders-check-mad"). A task whose key or title is already in the To Do is skipped, so
sending the same list twice is harmless. who defaults to Claude."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_activity

MOD_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def send(tasks, who="Claude"):
	sent = 0
	for task in tasks:
		if isinstance(task, dict) and str(task.get("title") or "").strip():
			sent += master_activity.record("AI", MOD_ROOT, "add_task", who=who, state=task)
	return sent


if __name__ == "__main__":
	args = sys.argv[1:]
	who = "Claude"
	if "--who" in args:
		i = args.index("--who")
		who = args[i + 1]
		del args[i:i + 2]
	if len(args) != 1:
		sys.exit(__doc__)
	with open(args[0], encoding="utf-8") as f:
		tasks = json.load(f)
	print(f"{send(tasks, who)} task(s) sent to Organisation Master as {who}.")
