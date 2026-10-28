"""Shared achievement badges, derived from recorded work and retained on each developer."""
import collections
import datetime
import tkinter as tk
from tkinter import ttk

import icons
import ui
from notebook_theme import theme_notebook
from theme_secret_catalog import THEME_BADGES

GAME_COUNT = 10  # (the RR games: rr_games_data.GAMES; Grand Tour needs every one)
QUIZ_GAMES = ("holy", "shock", "minority", "flags", "borders", "passport", "ideology", "station")  # (question rounds; not RRdle / Pinpoint)

# id, title, themed icon, group, metric, target, requirement
BADGES = (
	("first", "First Across the Line", "checkmark", "Progress", "done", 1, "Complete your first task."),
	("five", "Finding Your Stride", "checklist", "Progress", "done", 5, "Complete 5 tasks."),
	("ten", "Reliable Pair of Hands", "tools", "Progress", "done", 10, "Complete 10 tasks."),
	("twentyfive", "Quarter Century", "star", "Progress", "done", 25, "Complete 25 tasks."),
	("fifty", "Half a Hundred", "shield", "Progress", "done", 50, "Complete 50 tasks."),
	("hundred", "Centurion", "castle", "Progress", "done", 100, "Complete 100 tasks."),
	("month_winner", "Win Developer of the Month", "trophy", "Progress", "months_won", 1, "Finish a calendar month with the most completed tasks. Awarded after month-end; ties count."),
	("quick", "Quick Turnaround", "rocket", "Progress", "quick", 1, "Complete a task within 24 hours of its creation."),
	("patient", "Long Game", "hourglass", "Progress", "old", 1, "Complete a task that was open for at least 30 days."),
	("critical", "Pressure Tested", "warning", "Progress", "critical", 1, "Complete a Critical-priority task."),
	("dependencies", "Chain Reaction", "chain", "Progress", "dependencies", 1, "Complete a task with recorded dependencies."),
	("shared", "Better Together", "handshake", "Progress", "shared", 1, "Complete a task credited to more than one developer."),
	("variety", "Many Hats", "toolbox", "Progress", "categories", 5, "Complete tasks in 5 different categories."),
	("projects", "World Builder", "globe", "Progress", "projects", 3, "Complete tasks in 3 different projects."),
	("map", "Here Be Maps", "map", "Specialists", "Map", 1, "Complete a Map task."),
	("art", "Gallery Opening", "palette", "Specialists", "Art", 1, "Complete an Art task."),
	("music", "On Air", "radio", "Specialists", "Music", 1, "Complete a Music task."),
	("mechanic", "Under the Hood", "gear", "Specialists", "Mechanic", 1, "Complete a Mechanic task."),
	("bug", "Bug Hunter", "bug", "Specialists", "Bug", 1, "Complete a Bug task."),
	("loc", "Words Have Power", "speech", "Specialists", "Localisation", 1, "Complete a Localisation task."),
	("idea", "Lightbulb Moment", "lightbulb", "Community", "ideas", 1, "Post an idea."),
	("ideas", "Idea Factory", "factory", "Community", "ideas", 5, "Post 5 ideas."),
	("approved", "Greenlit", "flag", "Community", "approved", 1, "Have one of your ideas approved."),
	("vc", "Present and Accounted For", "team", "Community", "vcs", 1, "Be listed as an attendee of a Dev VC."),
	("scribe", "Keeper of the Minutes", "fountain_pen", "Community", "minutes", 1, "Be the note taker for a Dev VC with recorded discussion, decisions or notes."),
	("one_more", "Just One More Task", "clock", "Funny", "best_day", 5, "Complete 5 tasks on the same day. Apparently sleep is optional."),
	("meeting", "This Meeting Became a Task", "microphone", "Funny", "vc_tasks", 3, "Turn 3 VC proposals into tasks. The meeting has escaped containment."),
	("attachments", "Attachment Issues", "documents", "Funny", "attachments", 1, "Complete a task with at least 3 links. You brought receipts."),
	("ancient", "It Was Like That When I Got Here", "archive", "Funny", "ancient", 1, "Complete a task at least 90 days old. Archaeology counts as development."),
	("duck", "Rubber Duck Supreme", "question", "Funny", "duck", 1, "Hidden: the Dev list's Dev column heading deserves a closer inspection."),
	("spooked", "Spooked", "alt_crescent_moon", "Funny", "spooked", 1, "Pop the rare floating ghost in the Halloween theme."),
	("music_master", "On the Record", "headphones", "Masters", "Music Master", 1, "Successfully save work to a music mod in Music Master."),
	("culture_master", "Culture Keeper", "globe", "Masters", "Culture Master", 1, "Successfully save changes to the mod in Culture Master."),
	("country_master", "State of Affairs", "compass", "Masters", "Country Master", 1, "Successfully save changes to the mod in Country Master."),
	("music_playlist", "Playlist Curator", "checklist", "Masters", "music_playlist", 1, "Save a radio station's playlist file in Music Master."),
	("music_track", "Drop the Needle", "play", "Masters", "music_track", 1, "Save an audio track into a music mod through Music Master."),
	("music_mix", "Fine Tuning", "scales", "Masters", "music_mix", 1, "Save a music .asset file containing track definitions or playback settings."),
	("music_art", "Sleeve Notes", "picture", "Masters", "music_art", 1, "Save radio-station artwork through Music Master."),
	("music_dial", "Dial Designer", "radio", "Masters", "music_dial", 1, "Save music-player interface or sprite definitions through Music Master."),
	("music_name", "Name That Station", "pencil", "Masters", "music_name", 1, "Save music localisation, such as a radio station's displayed name."),
	("music_research", "Musical Detective", "magnifier", "Masters", "music_research", 1, "Complete a linked Research Music task for a planned radio station."),
	("music_upload", "Ready for Airplay", "upload", "Masters", "music_upload", 1, "Complete a linked Upload Tracks task for a planned radio station."),
	("culture_states", "Set the Scene", "map", "Masters", "culture_states", 1, "Save the state culture setup in RR_culture_scripted_effects.txt through Culture Master."),
	("culture_tree", "Family Tree", "branches", "Masters", "culture_tree", 1, "Save culture hierarchy or culture idea definitions through Culture Master."),
	("culture_faith", "Matters of Faith", "open_book", "Masters", "culture_faith", 1, "Save religion definitions or religion setup scripts through Culture Master."),
	("culture_language", "Speaking Volumes", "speech", "Masters", "culture_language", 1, "Save language definitions or language setup scripts through Culture Master."),
	("culture_icons", "A Picture of Culture", "palette", "Masters", "culture_icons", 1, "Save a culture, religion or language icon through Culture Master."),
	("culture_migration", "On the Move", "compass", "Masters", "culture_migration", 1, "Save migratory-culture setup or homeland changes through Culture Master."),
	("culture_tokens", "In Sync", "chain", "Masters", "culture_tokens", 1, "Save synchronized dynamic-token definitions through Culture Master."),
	("culture_names", "What's in a Name?", "fountain_pen", "Masters", "culture_names", 1, "Save culture-system names or descriptions in localisation through Culture Master."),
	("culture_population", "Population Census", "team", "Masters", "culture_population", 1, "Save state-history population changes through Culture Master."),
	("country_history", "Set the Starting Line", "calendar", "Masters", "country_history", 1, "Save a country's starting history through Country Master."),
	("country_identity", "National Identity", "flag", "Masters", "country_identity", 1, "Save a common/countries definition through Country Master."),
	("country_flag", "Raise the Colours", "paintbrush", "Masters", "country_flag", 1, "Save a national flag image through Country Master."),
	("country_characters", "Casting Call", "team", "Masters", "country_characters", 1, "Save character or leader definitions through Country Master."),
	("country_ideas", "National Spirit", "lightbulb", "Masters", "country_ideas", 1, "Save national-spirit or idea definitions through Country Master."),
	("country_oob", "Order of Battle", "shield", "Masters", "country_oob", 1, "Save an army, navy or air-force order-of-battle file through Country Master."),
	("country_politics", "Political Spectrum", "scales", "Masters", "country_politics", 1, "Save ideology definitions or party sub-ideology graphics through Country Master."),
	("country_names", "A Country by Any Other Name", "document", "Masters", "country_names", 1, "Save country-related localisation through Country Master."),
	("country_review", "Portrait, Approved", "checkmark", "Masters", "country_review", 1, "Explicitly finish a linked portrait review by choosing Not marked in Country Master."),
	("gfx_review_25", "Fresh Eyes", "magnifier", "Masters", "gfx_reviews", 25, "Review 25 pictures in 🖼 GFX > 🔎 Review swiper."),
	("gfx_review_100", "Eagle Eye", "picture", "Masters", "gfx_reviews", 100, "Review 100 pictures in 🖼 GFX > 🔎 Review swiper."),
) + tuple((key, title, icon, "Theme secrets", key, 1, theme + ": " + requirement)
	for key, title, icon, theme, requirement in THEME_BADGES) + (
	# 🎲 the RR games (Organisation Master's games window): the silly side, not just high scores
	("game_tourist", "Grand Tour", "globe", "Games", "game_kinds", GAME_COUNT, f"Play every RR game at least once ({GAME_COUNT} of them)."),
	("game_marathon", "Just One More Round", "clock", "Games", "game_best_day", 10, "Play 10 game rounds in one day. The backlog can wait."),
	("game_night", "Night Owl", "alt_crescent_moon", "Games", "game_night", 1, "Play a round between midnight and 5 am."),
	("game_zero", "Participation Trophy", "trophy", "Games", "game_zero", 1, "Answer at least 5 questions in a round and get every one wrong."),
	("game_speed", "Speedrun Any%", "alt_jagged_lightning_bolt", "Games", "game_speed", 1, "Get 5 or more right in a quiz round in under 30 seconds."),
	("game_hard", "Glutton for Punishment", "alt_burning_torch", "Games", "game_hard_kinds", 3, "Finish a round on Hard in 3 different games."),
	("game_quit", "Tactical Retreat", "alt_broken_crown", "Games", "game_quit", 3, "End 3 rounds early. It was a strategic withdrawal."),
	("rrdle_first", "Did You Peek?", "eye", "Games", "rrdle_first", 1, "Solve an RRdle with your first guess."),
	("rrdle_last", "Photo Finish", "hourglass", "Games", "rrdle_last", 1, "Solve an RRdle with your very last guess."),
	("rrdle_days", "Daily Habit", "calendar", "Games", "rrdle_days", 5, "Play RRdle on 5 different days."),
	("rrdle_slow", "The Scenic Route", "alt_steam_locomotive", "Games", "rrdle_slow", 1, "Take more than 15 minutes to solve an RRdle."),
	("pin_far", "Wrong Hemisphere", "compass", "Games", "pin_far", 1, "Miss a Pinpoint state by more than 8,000 km."),
	("pin_close", "Agonisingly Close", "target", "Games", "pin_close", 1, "Click within 25 km of a Pinpoint state without landing in it."),
	("pin_hattrick", "Hat-Trick", "alt_military_medal", "Games", "pin_hattrick", 1, "Land 3 exact hits in a single Pinpoint round."),
	("sleigh_coal", "Lump of Coal", "alt_coal_lumps", "Games", "sleigh_coal", 1, "Finish a Santa sleigh run without delivering a single present."),
)
FUN = "Fun & Games"  # (the section the secrets, hidden jokes and game badges are in)


def badge_tool(key):
	"""The section a badge is listed in: its master, or 🎲 Fun & Games (theme secrets, the hidden jokes, the RR games)."""
	if key in FUN_KEYS:
		return FUN
	if key == "music" or key.startswith("music_"):
		return "Music Master"
	if key.startswith("culture_"):
		return "Culture Master"
	if key.startswith("country_"):
		return "Country Master"
	return "Organisation Master"


FUN_KEYS = {b[0] for b in BADGES if b[3] in ("Theme secrets", "Games")} | {"duck", "spooked"}


def game_metrics(data, stats):
	"""The 🎲 game badges' counts, from the saved rounds (rr_game_scores, sleigh_scores)."""
	kinds, hard, days, rr_days = (collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(collections.Counter),
								  collections.defaultdict(set))
	for r in data.get("rr_game_scores", []):
		name = r.get("dev")
		if name not in stats:
			continue
		s, game = stats[name], r.get("game")
		kinds[name].add(game)
		when = timestamp(r.get("when"))
		if when is not None:
			try:
				local = when.astimezone()
				days[name][local.date().isoformat()] += 1
				s["game_night"] += local.hour < 5
			except (ValueError, OverflowError):
				pass
		answered, score, finished = r.get("answered") or 0, r.get("score") or 0, r.get("completed")
		if game in QUIZ_GAMES:
			s["game_zero"] += answered >= 5 and score == 0
			s["game_speed"] += score >= 5 and 0 < (r.get("duration") or 0) < 30
			s["game_quit"] += not finished
			if finished and r.get("difficulty") == "hard":
				hard[name].add(game)
		elif game == "rrdle":
			guesses = r.get("guesses") or []
			rr_days[name].add(r.get("day"))
			if finished:
				s["rrdle_first"] += len(guesses) == 1
				s["rrdle_last"] += score == 1
				s["rrdle_slow"] += (r.get("duration") or 0) > 15 * 60
				if r.get("difficulty") == "hard":
					hard[name].add(game)
		elif game == "pinpoint":
			clicks = r.get("clicks") or []
			s["pin_far"] += any((c.get("km") or 0) > 8000 for c in clicks)
			s["pin_close"] += any(not c.get("inside") and (c.get("km") or 99) <= 25 for c in clicks)
			s["pin_hattrick"] += (r.get("hits") or sum(1 for c in clicks if c.get("inside"))) >= 3
			if finished and r.get("difficulty") == "hard":
				hard[name].add(game)
	for r in data.get("sleigh_scores", []):
		if r.get("dev") in stats:
			stats[r["dev"]]["sleigh_coal"] += bool(r.get("finished")) and not r.get("score")
	for name, s in stats.items():
		s.update(game_kinds=len(kinds[name] - {None}), game_hard_kinds=len(hard[name]),
				 game_best_day=max(days[name].values(), default=0), rrdle_days=len(rr_days[name] - {None}))


def timestamp(value):
	try:
		return datetime.datetime.fromisoformat(value)
	except (ValueError, TypeError):
		return None


def completed_at(task):
	if task.get("status") != "Completed" and task.get("archived") != "Completed":
		return None
	if task.get("closed"):
		return timestamp(task["closed"])
	for event in reversed(task.get("history", [])):
		if event.get("field") in ("status", "archived") and event.get("new") == "Completed":
			return timestamp(event.get("when"))
	return None


def saved_work_metrics(master, files):
	"""Classify only concrete saved paths; old receipts containing just a mod name imply no specific operation."""
	metrics = set()
	for filename in files:
		if not isinstance(filename, str):
			continue
		path = "/" + filename.replace("\\", "/").lower().lstrip("/")
		name = path.rsplit("/", 1)[-1]
		loc = "/localisation/" in path or "/localization/" in path
		image = path.endswith((".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".webp"))
		if master == "Music Master":
			if "/music/" in path and path.endswith(".txt"):
				metrics.add("music_playlist")
			if "/music/" in path and path.endswith((".ogg", ".mp3", ".wav", ".flac")):
				metrics.add("music_track")
			if "/music/" in path and path.endswith(".asset"):
				metrics.add("music_mix")
			if "/gfx/" in path and image:
				metrics.add("music_art")
			if "/interface/" in path and path.endswith((".gfx", ".gui")):
				metrics.add("music_dial")
			if loc and path.endswith(".yml"):
				metrics.add("music_name")
		elif master == "Culture Master":
			if name == "rr_culture_scripted_effects.txt":
				metrics.add("culture_states")
			if name in ("rr_culture_on_actions.txt", "_culture.txt"):
				metrics.add("culture_tree")
			if name in ("rr_religion_on_actions.txt", "rr_religion_scripted_effects.txt", "_religion.txt"):
				metrics.add("culture_faith")
			if name in ("rr_language_on_actions.txt", "rr_language_scripted_effects.txt", "_language.txt"):
				metrics.add("culture_language")
			if any(folder in path for folder in ("/gfx/interface/culture/", "/gfx/interface/religion/", "/gfx/interface/language/")) and image:
				metrics.add("culture_icons")
			if name == "rr_migratory_cultures_effects.txt":
				metrics.add("culture_migration")
			if "/common/synchronized_dynamic_tokens/" in path and path.endswith(".txt"):
				metrics.add("culture_tokens")
			if loc and path.endswith(".yml"):
				metrics.add("culture_names")
			if "/history/states/" in path and path.endswith(".txt"):
				metrics.add("culture_population")
		elif master == "Country Master":
			for folder, metric in (("/history/countries/", "country_history"), ("/common/countries/", "country_identity"),
				("/common/characters/", "country_characters"), ("/common/ideas/", "country_ideas"), ("/history/units/", "country_oob")):
				if folder in path and path.endswith(".txt"):
					metrics.add(metric)
			if "/gfx/flags/" in path and image:
				metrics.add("country_flag")
			if "/common/ideologies/" in path or path.endswith("/tools/party_gfx/subs.json"):
				metrics.add("country_politics")
			if loc and path.endswith(".yml"):
				metrics.add("country_names")
	return metrics


def statistics(data, today=None):
	current_month = (today or datetime.date.today()).strftime("%Y-%m")
	stats = {d["name"]: collections.Counter() for d in data.get("devs", [])}
	categories, projects, days, months = (collections.defaultdict(set), collections.defaultdict(set),
		collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter))
	for task in data.get("tasks", []):
		creator = task.get("set_by")
		if creator in stats and str(task.get("link", "")).startswith("vc:"):
			stats[creator]["vc_tasks"] += 1
		end = completed_at(task)
		if not end:
			continue
		devs = set(task.get("devs") or [])
		for name in devs & stats.keys():
			s = stats[name]
			s["done"] += 1
			link = str(task.get("link") or "")
			if link.startswith("music_step:"):
				s["music_research"] += link.endswith(":research")
				s["music_upload"] += link.endswith(":upload")
			category = task.get("category")
			if category:
				categories[name].add(category)
				if category in ("Map", "Art", "Music", "Mechanic", "Bug", "Localisation"):
					s[category] += 1
			if task.get("project"):
				projects[name].add(task["project"])
			days[name][end.date().isoformat()] += 1
			months[end.strftime("%Y-%m")][name] += 1
			s["critical"] += task.get("priority") == "Critical"
			s["dependencies"] += bool(task.get("depends_on"))
			s["shared"] += len(devs) > 1
			s["attachments"] += len(set(task.get("links") or [])) >= 3
			start = timestamp(task.get("created"))
			if start:
				try:
					age = (end - start).total_seconds() / 86400
				except TypeError:
					continue  # Mixed timezone formats do not establish a reliable duration.
				s["quick"] += 0 <= age <= 1
				s["old"] += age >= 30
				s["ancient"] += age >= 90
	for month, counts in months.items():
		if month >= current_month:
			continue
		most = max(counts.values())
		for name, count in counts.items():
			stats[name]["months_won"] += count == most
	for idea in data.get("ideas", []):
		if idea.get("by") in stats:
			s = stats[idea["by"]]
			s["ideas"] += 1
			s["approved"] += idea.get("state") == "approved"
	for vc in data.get("vcs", []):
		for name in set(vc.get("attendees") or []) & stats.keys():
			stats[name]["vcs"] += 1
		if vc.get("note_taker") in stats and any(str(vc.get(k) or "").strip() for k in ("discussion", "decisions", "notes")):
			stats[vc["note_taker"]]["minutes"] += 1
	for dev in data.get("devs", []):
		name = dev["name"]
		stats[name].update(categories=len(categories[name]), projects=len(projects[name]), best_day=max(days[name].values(), default=0),
			duck=int("rubber_duck" in (dev.get("secrets") or [])),
			spooked=int("halloween_ghost" in (dev.get("secrets") or [])),
			gfx_reviews=((data.get("gfx") or {}).get("review_counts") or {}).get(name, {}).get("total", 0))
		for key, *_ in THEME_BADGES:
			stats[name][key] = int(key in (dev.get("secrets") or []))
		stats[name]["egg_sleigh_10"] = max(stats[name].get("egg_sleigh_10",0),
			int(any(r.get("dev")==name and r.get("score",0)>=10 for r in data.get("sleigh_scores",[]))))
	game_metrics(data, stats)
	seen = set()
	for event in data.get("master_activity", []):
		if event.get("id") and event["id"] in seen:
			continue
		if event.get("id"):
			seen.add(event["id"])
		if event.get("who") not in stats:
			continue
		s = stats[event["who"]]
		master = event.get("master", "")
		if event.get("action") == "saved" and master in ("Music Master", "Culture Master", "Country Master"):
			s[master] += 1
			for metric in saved_work_metrics(master, event.get("files") or []):
				s[metric] += 1
		elif master == "Country Master" and event.get("action") == "portrait_unmarked":
			s["country_review"] += 1
	return stats


def award(data, stats=None):
	"""Record new badges once; synced developer dictionaries retain earned badges."""
	stats = statistics(data) if stats is None else stats
	changed = False
	when = datetime.datetime.now().replace(microsecond=0).isoformat()
	for dev in data.get("devs", []):
		if stats[dev["name"]]["months_won"] and not dev.get("champion_verified"):
			dev["champion_verified"] = True  # Retain a genuine month-end win even if old tasks are later removed.
			changed = True
		if "champion" in (dev.get("achievements") or {}):
			old = dev["achievements"].pop("champion")
			if dev.get("champion_verified"):
				dev["achievements"].setdefault("month_winner", old)
			changed = True
		for key, _, _, _, metric, target, _ in BADGES:
			if stats[dev["name"]][metric] >= target and key not in (dev.get("achievements") or {}):
				dev.setdefault("achievements", {})[key] = when
				changed = True
	return changed


class Achievements(ttk.Frame):
	def __init__(self, parent, todo):
		super().__init__(parent, padding=12)
		self.todo, self.app = todo, todo.app
		self._images = []
		self._section_open = {}
		top = ttk.Frame(self)
		top.pack(fill="x")
		ttk.Label(top, text="Achievements", font="om_title").pack(side="left")
		ttk.Button(top, text="Refresh", command=self.fill).pack(side="right")
		self.summary = ttk.Label(self, style="Muted.TLabel")
		self.summary.pack(anchor="w", pady=(4, 12))
		filters = ttk.Frame(self)
		filters.pack(fill="x", pady=(0, 8))
		ttk.Label(filters, text="Developer").pack(side="left")
		self.dev = tk.StringVar(value="All developers")
		self.dev_box = ttk.Combobox(filters, textvariable=self.dev, state="readonly", width=24)
		self.dev_box.pack(side="left", padx=(6, 16))
		self.group = tk.StringVar(value="All badges")
		ttk.Combobox(filters, textvariable=self.group, values=["All badges", "Progress", "Specialists", "Community", "Masters", "Funny", "Theme secrets", "Games"],
			state="readonly", width=18).pack(side="left")
		self.search = tk.StringVar()
		ttk.Label(filters, text="Search").pack(side="left", padx=(16, 6))
		ttk.Entry(filters, textvariable=self.search, width=28).pack(side="left", fill="x", expand=True)
		theme_notebook(self, "Achievement.TNotebook")
		self.tabs = ttk.Notebook(self, style="Achievement.TNotebook")
		self.tabs.pack(fill="both", expand=True)
		badges, people = ttk.Frame(self.tabs), ttk.Frame(self.tabs)
		self.tabs.add(badges, text="🏅 Badges")
		self.tabs.add(people, text="👥 Developers")
		self.tree = self.table(badges, ("requirement", "progress", "earned"),
			(("#0", "Achievement", 270), ("requirement", "Requirement", 410), ("progress", "Progress", 135), ("earned", "Earned by", 300)))
		self.people = self.table(people, ("badges", "funny", "latest"),
			(("#0", "Developer", 240), ("badges", "Badges", 100), ("funny", "Funny", 100), ("latest", "Latest badge", 300)))
		self.tree.bind("<<TreeviewSelect>>", lambda _: self.show())
		self.people.bind("<Double-1>", self.pick_person)
		detail = ttk.Frame(self, padding=(0, 12))
		detail.pack(fill="x")
		self.picture = ttk.Label(detail)
		self.picture.pack(side="left", padx=(0, 12))
		text = ttk.Frame(detail)
		text.pack(side="left", fill="x", expand=True)
		self.title = ttk.Label(text, font="om_title")
		self.title.pack(anchor="w")
		self.description = ttk.Label(text, wraplength=950, justify="left")
		self.description.pack(anchor="w", pady=4)
		self.holders = ttk.Label(text, style="Muted.TLabel", wraplength=950, justify="left")
		self.holders.pack(anchor="w")
		detail.bind("<Configure>", lambda event: [label.configure(wraplength=max(ui.px(240), event.width - ui.px(80)))
			for label in (self.description, self.holders)])
		for var in (self.dev, self.group, self.search):
			var.trace_add("write", lambda *_: self.fill())
		ui.THEME_HOOKS.append(self.retheme)
		self.bind("<Destroy>", self.destroyed, add="+")
		self.fill()
		self._job = self.after(2000, self.poll)

	@staticmethod
	def table(parent, columns, headings):
		parent.columnconfigure(0, weight=1)
		parent.rowconfigure(0, weight=1)
		tree = ttk.Treeview(parent, columns=columns, height=17, selectmode="browse")
		for key, text, width in headings:
			tree.heading(key, text=text)
			tree.column(key, width=ui.px(width), minwidth=ui.px(90))
		tree.grid(row=0, column=0, sticky="nsew")
		ttk.Scrollbar(parent, orient="vertical", command=tree.yview).grid(row=0, column=1, sticky="ns")
		ttk.Scrollbar(parent, orient="horizontal", command=tree.xview).grid(row=1, column=0, sticky="ew")
		tree.configure(yscrollcommand=parent.grid_slaves(row=0, column=1)[0].set,
			xscrollcommand=parent.grid_slaves(row=1, column=0)[0].set)
		return tree

	def retheme(self):
		if self.winfo_exists():
			theme_notebook(self, "Achievement.TNotebook")
			self.fill()

	def fill(self):
		if not self.winfo_exists():
			return
		self.stats = statistics(self.todo.data)
		if award(self.todo.data, self.stats):
			self.todo.save(undoable=False, feedback=False)
		self._state = self.todo._saved
		ttk.Style(self).configure("Achievements.Treeview", rowheight=ui.px(30))
		self.tree.configure(style="Achievements.Treeview")
		devs = self.todo.data.get("devs", [])
		self.dev_box.configure(values=["All developers"] + [d["name"] for d in devs])
		if self.dev.get() not in self.dev_box.cget("values"):
			self.dev.set("All developers")
		selected = next((d for d in devs if d["name"] == self.dev.get()), None)
		count = sum(len(d.get("achievements") or {}) for d in devs)
		self.summary.configure(text=f"{len(BADGES)} badges · {len(THEME_BADGES)} theme secrets · {len(devs)} developers · {count} earned badges across the team. Shared tasks credit every assigned dev.")
		keep, scroll = self.tree.selection(), self.tree.yview()
		self._section_open.update({key: bool(self.tree.item(key, "open")) for key in self.tree.get_children()})
		self.tree.delete(*self.tree.get_children())
		self._images = []
		self.tree.tag_configure("locked", foreground=ui.P.get("muted", "#888888"))
		self.tree.tag_configure("section", font="om_bold")
		for key, title, icon, group, metric, target, requirement in sorted(BADGES, key=lambda b: b[0] in FUN_KEYS):  # (🎲 Fun & Games last)
			if self.group.get() not in ("All badges", group) or self.search.get().lower() not in (title + " " + requirement).lower():
				continue
			tool = badge_tool(key)
			section = "tool:" + tool
			if not self.tree.exists(section):
				section_icon = {"Organisation Master": "trophy", "Music Master": "radio", "Culture Master": "globe", "Country Master": "flag", FUN: "star"}[tool]
				img = icons.image(section_icon, ui.px(22))
				self._images.append(img)
				self.tree.insert("", "end", iid=section, text=tool, image=img, tags=("section",),
					open=self._section_open.get(section, True), values=("Click the arrow to expand or collapse", "", ""))
			earned = [d["name"] for d in devs if key in (d.get("achievements") or {})]
			unlocked = selected and key in (selected.get("achievements") or {})
			progress = ("Earned" if unlocked else f"{min(target, self.stats[selected['name']][metric])}/{target}") if selected else f"{len(earned)}/{len(devs)} devs"
			img = icons.image(icon, ui.px(22))
			self._images.append(img)
			self.tree.insert(section, "end", iid=key, text=title, image=img, values=(requirement, progress, ", ".join(earned) or "Not earned yet"),
				tags=("locked",) if selected and not unlocked else ())
		for section in self.tree.get_children():
			children = self.tree.get_children(section)
			self.tree.item(section, text=f"{section[5:]} ({len(children)})")
		if keep and self.tree.exists(keep[0]):
			self.tree.selection_set(keep)
		elif self.tree.get_children():
			self.tree.selection_set(self.tree.get_children(self.tree.get_children()[0])[0])
		if scroll:
			self.tree.yview_moveto(scroll[0])
		self.people.delete(*self.people.get_children())
		funny = {b[0] for b in BADGES if b[3] == "Funny"}
		for d in sorted(devs, key=lambda d: (-len(d.get("achievements") or {}), d["name"].lower())):
			earned = d.get("achievements") or {}
			latest = max(earned, key=earned.get) if earned else None
			label = next((b[1] for b in BADGES if b[0] == latest), "—")
			self.people.insert("", "end", iid=d["name"], text=d["name"], values=(f"{len(earned)}/{len(BADGES)}", f"{len(funny & earned.keys())}/5", label))
		self.show()

	def show(self):
		row = self.tree.selection()
		badge = next((b for b in BADGES if row and b[0] == row[0]), None)
		if not badge:
			section = row and row[0].startswith("tool:")
			self.title.configure(text=row[0][5:] if section else "No matching badges")
			self.description.configure(text="Use the arrow beside this tool to expand or collapse its achievements. General milestones and task badges are in Organisation Master." if section else "Try another filter.")
			self.holders.configure(text="")
			self.picture.configure(image="")
			return
		key, title, icon, group, _, _, requirement = badge
		self._detail_image = icons.image(icon, ui.px(48))
		self.picture.configure(image=self._detail_image)
		self.title.configure(text=title)
		self.description.configure(text=f"{group} · {requirement}")
		holders = [f"{d['name']} ({d['achievements'][key][:10]})" for d in self.todo.data.get("devs", []) if key in (d.get("achievements") or {})]
		self.holders.configure(text="Earned by: " + (", ".join(holders) or "Nobody yet. Your move.") + "\nDates show when the badge was recorded; existing work counts too.")

	def pick_person(self, _):
		selected = self.people.selection()
		if selected:
			self.dev.set(selected[0])
			self.tabs.select(0)

	def poll(self):
		if self.winfo_ismapped() and self._state != self.todo._saved:
			self.fill()
		self._job = self.after(2000, self.poll)

	def flush(self):
		pass  # This pane has no unsaved text fields.

	def destroyed(self, event):
		if event.widget is self:
			if self.retheme in ui.THEME_HOOKS:
				ui.THEME_HOOKS.remove(self.retheme)
			if getattr(self, "_job", None):
				self.after_cancel(self._job)
