"""Flags picked up automatically from names: a project, grouping or idea heading called "United Kingdom", "British
Navy", "ENG focus tree" or "Communist China" gets that country's flag (with the ideology's flag when the name says
one: "Fascist Britain", "British Union"), unless it has an icon of its own. Region and continent names ("North
America", "Middle East", "Australia/Polynesia") get their globe icon (region_icons) instead: the longer name wins, so
"South Africa" is still a flag and "Africa" the globe.

The index is built once in the background from the localisation (country names, adjectives, ideology-specific
names) of the mod and the base game, for every tag that has a flag; ideology words come from common/ideologies."""
import glob
import json
import os
import re
import threading

import flag_icons
import paths  # (Scripts/paths.py: where the tool's files are)

RX_LOC = re.compile(r'^\s*([A-Z][A-Z0-9]{2})(?:_(ADJ|[a-z][a-z_]*))?:\d*\s*"([^"]+)"')
RX_KEY = re.compile(r'^\s*([a-z][a-z0-9_]*):\d*\s*"([^"]+)"')
MIN_NAME = 4  # (shorter names match too much by chance)
# One-word country names that are ordinary words ("North", "Union"...): they'd put a flag on "North America" / "North Korea".
GENERIC = {"north", "south", "east", "west", "northern", "southern", "eastern", "western", "central", "upper", "lower",
		   "union", "empire", "republic", "kingdom", "federation", "confederation", "state", "states", "free", "new", "old",
		   "greater", "great", "united", "commune", "federal", "nation", "league", "pact", "front", "council", "alliance",
		   "realm", "dominion", "territory", "territories", "provisional", "government", "colony", "colonies", "order",
		   "reich", "mandate", "protectorate", "coast", "islands", "isles", "land", "lands", "time", "reality", "world"}
# Names for each globe in icons/regions (its own label counts too).
REGION_NAMES = {"north-america": ("north america",), "central-america": ("central america", "caribbean"),
				"south-america": ("south america", "latin america"), "europe": ("europe",),
				"western-europe": ("western europe", "west europe"), "middle-east": ("middle east", "near east"),
				"africa": ("africa",), "asia": ("asia", "asian"), "oceania": ("oceania", "oceanian"),
				"australia-polynesia": ("australia/polynesia", "polynesia", "australasia",
				"pacific islands"), "antarctica": ("antarctica", "antarctic"), "north-pole": ("north pole", "arctic"),
				"china": ("china",), "ussr": ("ussr",)}


def region_names():
	"""lower-case name -> globe region id, for the regions there are icons of."""
	try:
		with open(os.path.join(paths.BUNDLE, "icons", "regions", "regions.json"), encoding="utf-8") as f:
			regions = json.load(f)["regions"]
	except (OSError, ValueError, KeyError):
		return {}
	out = {}
	for r in regions:
		for n in (r.get("label", ""),) + REGION_NAMES.get(r["id"], ()):
			if n:
				out[n.lower()] = r["id"]
	return out


class AutoFlags:
	def __init__(self, root):
		self.root = root
		self.ready = False
		self.names = {}   # lower-case name -> (tag, ideology or None)
		self.words = {}   # lower-case ideology word -> main ideology
		self.tags = set()
		self.regions = {}  # lower-case name -> globe region id
		self._rx_names = self._rx_words = self._rx_regions = None
		self._cache = {}
		self._callbacks = []

	def start(self, done=None):
		"""Builds the index in a thread; done() (called through the Tk loop by whoever polls ready) after."""
		if done:
			self._callbacks.append(done)
		threading.Thread(target=self._build, daemon=True).start()

	def _build(self):
		try:
			src = flag_icons.source(self.root)
			self.src = src
			self.tags = {k[:3].upper() for k in src.flag_map if re.match(r"[a-z0-9]{3}[._]", k)}  # (most have ideology flags only)
			mains = dict(getattr(src, "ideologies", {}) or {})
			subs = {s: m for m, ss in mains.items() for s in ss}
			words = {}
			for m in mains:
				for w in {m, m.replace("_", " ")} | ({m[:-3] + "ist", m[:-3] + "ists"} if m.endswith("ism") else set()) \
						| ({m[:-1] + "cy", m.replace("democratic", "democrat")} if m.endswith("ic") else set()):
					words[w.lower()] = m
			for s, m in subs.items():
				for w in {s.replace("_", " ")} | ({s[:-3] + "ist"} if s.endswith("ism") else set()):
					words[w.lower()] = m
			game = getattr(src, "game", None)
			files = [(f, True) for f in glob.glob(os.path.join(game, "localisation", "english", "*.yml"))] if game else []
			files += [(f, False) for f in glob.glob(os.path.join(self.root, "localisation", "english", "**", "*.yml"), recursive=True)]
			names, rank, shared = {}, {}, {}

			def offer(name, tag, ideology, r):
				"""A name shared by several tags goes to the best source: the base game's country name, then the mod's,
				then adjectives, then ideology-only names (first come within the same rank)."""
				if r < rank.get(name, 99):
					names[name], rank[name] = (tag, ideology), r
			for f, base in files:
				try:
					with open(f, encoding="utf-8-sig", errors="replace") as fh:
						for line in fh:
							m = RX_LOC.match(line)
							if m:
								tag, suffix, value = m.group(1), m.group(2), m.group(3).strip()
								if tag not in self.tags or "$" in value or "[" in value or len(value) < MIN_NAME or value.lower() in GENERIC:
									continue
								if suffix is None:
									offer(value.lower(), tag, None, 0 if base else 1)
								elif suffix == "ADJ":
									offer(value.lower(), tag, None, 2 if base else 3)
								elif suffix in mains:
									shared.setdefault((value.lower(), tag), set()).add(suffix)
									offer(value.lower(), tag, suffix, 4 if base else 5)
								continue
							m = RX_KEY.match(line)
							if m and (m.group(1) in mains or m.group(1) in subs):
								w = m.group(2).strip().lower()
								if len(w) >= MIN_NAME and "$" not in w:
									words.setdefault(w, m.group(1) if m.group(1) in mains else subs[m.group(1)])
				except OSError:
					continue
			for name, (tag, ideology) in list(names.items()):  # (a name several of its ideologies use: the plain flag)
				if ideology and len(shared.get((name, tag), ())) > 1:
					names[name] = (tag, None)
			self.names, self.words = names, words
			alt = lambda keys: "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
			self._rx_names = re.compile(r"(?<![\w])(" + alt(names) + r")(?![\w])", re.I) if names else None
			self._rx_words = re.compile(r"(?<![\w])(" + alt(words) + r")(?![\w])", re.I) if words else None
			self.regions = region_names()
			self._rx_regions = re.compile(r"(?<![\w])(" + alt(self.regions) + r")(?![\w])", re.I) if self.regions else None
			self.ready = True
		except Exception:
			self.ready = False

	def match(self, text):
		"""'flag:TAG' / 'flag:TAG_ideology' for a name, 'region:id' for a region / continent, or None."""
		if not self.ready or not text:
			return None
		if text in self._cache:
			return self._cache[text]
		tag = ideology = None
		for tok in re.findall(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]{2})(?![A-Za-z0-9])", text):  # (an explicit tag: ENG, GER...)
			if tok in self.tags:
				tag = tok
				break
		if tag is None:
			m = self._rx_names.search(text) if self._rx_names else None
			r = max(self._rx_regions.findall(text), key=len) if self._rx_regions and self._rx_regions.search(text) else ""
			if r and (not m or len(r) > len(m.group(1))):  # ("North America": the globe; "South Africa": still the flag)
				self._cache[text] = "region:" + self.regions[r.lower()]
				return self._cache[text]
			if m:
				tag, ideology = self.names[m.group(1).lower()]
		if tag and self._rx_words:
			m = self._rx_words.search(text)
			if m:
				ideology = self.words[m.group(1).lower()]
		out = None
		if tag:
			out = f"flag:{tag}"
			if ideology:
				try:
					if self.src.flag_map.get(f"{tag}_{ideology}.tga".lower()) or self.src.resolve(f"{tag}_{ideology}"):
						out = f"flag:{tag}_{ideology}"
				except Exception:
					pass
		self._cache[text] = out
		return out
