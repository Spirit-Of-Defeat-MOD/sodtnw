"""📖 The other masters' guides (Organisation Master's own are in guides.py, which runs them all): Culture Master,
Country Master and Model Master. Each master calls guides.attach(app, menubar, name, BOOK) while it builds its menu bar:
a 📖 Guides menu top left, and the first guide the first time that master opens on a PC.

Steps point at the real widgets by the attributes the masters keep (app.tree, app.canvas...) or by their text
(guides.find); one that can't be found just shows its card in the middle of the window."""
from guides import find, step


def shown(*wheres):
	"""The first of these that's on screen (a narrow or short window can cut some parts off)."""
	def where(app):
		for w in wheres:
			try:
				got = w(app)
				if got is not None and got.winfo_ismapped():
					return got
			except Exception:
				continue
		return None
	return where


# ---------- Culture Master ----------
def layer(key):
	def go(app):
		if app.system.get() != key:
			app.system.set(key)
			app.switch_system()
	return go


CULTURE = {
	"general": dict(title="Getting started", intro="A look around Culture Master.", steps=[
		step("Welcome to Culture Master", "Who lives where: every state's cultures, religions and languages, painted on the "
			 "map. What you change is written into the mod's own files when you Save, so it shows up in git like a hand edit."),
		step("Layers", "Culture, Religion or Language. Each layer has its own list, map modes, tools and brush.",
			 lambda a: find(a.mode_frame.master, "Culture"), layer("culture"), click=True),
		step("Map modes", "What the map colours by: groups, cultures, subcultures, affinities, migratory peoples, the brush's "
			 "strength in each state, or Missing data (states that don't add up).", lambda a: a.mode_frame),
		step("Tools", "Select (click a state to see it), Paint (pure: the state becomes 100% the brush), +1 / -1 strength, "
			 "and the layer's own. The number in [ ] is its key.", lambda a: a.tool_frame),
		step("The list", "Groups, cultures and subcultures (or religions, or languages). Pick one: that's your brush. "
			 "Double-click to edit it, right-click for more, drag to reorder when sorted by File order.", lambda a: a.tree),
		step("Search, Gap Finder and Sort", "Search by name or token. The Gap Finder shows only what's missing something "
			 "(no states, no icon, no localisation...) in amber, with a red count. Sort by name, token, states, population "
			 "or the files' order.", lambda a: a.gap_box),
		step("New, Edit, Show on map", "Make a new group / culture / subculture (it writes the idea, the arrays, "
			 "localisation, map colour and icon), edit the picked one, or light up its states on the map.",
			 lambda a: a.tree_buttons),
		step("The brush", "What you're painting with, and its colour.", lambda a: a.brush_swatch.master),
		step("The map", "Click a state with Select to see it; paint with the other tools (drag over several). Right-click "
			 "a state for its menu; right- or middle-drag to move the map; scroll to zoom. State # (top right) jumps to one.",
			 lambda a: a.canvas),
		step("The state", "What lives in the picked state and how strongly. Strengths add up to 5; a red warning says when "
			 "they don't. Double-click a row for its note; drag rows to reorder.", lambda a: a.comp),
		step("Changing it by hand", "+1 / -1, make one the majority, take it out, or put the brush in.",
			 lambda a: a.edit_buttons),
		step("Low population state", "The state keeps one subculture and one religion at strength 1, which counts as "
			 "absolute (the low_population_state flag). Click the population to type a new one.", lambda a: a.low_pop_check),
		step("Copy and paste states", "Ctrl+C / Ctrl+V: a state's culture and religion (and its low population flag and "
			 "order) onto another.", shown(lambda a: a.copy_frame, lambda a: a.edit_buttons)),
		step("Save to mod", "Ctrl+S writes everything; the old files are copied to tools/culture_master/backups first. "
			 "Check recent changes lists what's been saved. Ctrl+Z / Ctrl+Y undo and redo (also in the File and Edit menus).",
			 shown(lambda a: a.save_btn, lambda a: find(a.root, "File"))),
		step("Check for problems", "Tools > Check for problems: states that don't add up to 5, missing colours or "
			 "localisation, old religion ids...", lambda a: find(a.root, "Tools")),
	]),
	"religion": dict(title="🙏 Religions", intro="Religions, orders and sections.", steps=[
		step("The Religion layer", "Religion groups and religions, painted like cultures.",
			 lambda a: find(a.mode_frame.master, "Religion"), layer("religion"), click=True),
		step("Sections", "Shows the # Section comments of the religion file as levels in the list.",
			 lambda a: a.sections_check, layer("religion")),
		step("Orders only", "Only the religious orders.", lambda a: a.only_check, layer("religion")),
		step("Religious orders", "A state can have one order: set the brush as it, take it out, or change its strength. "
			 "Paint order [5] paints it straight on the map.", lambda a: a.order_frame, layer("religion")),
	]),
	"migratory": dict(title="🐎 Migratory peoples", intro="Migratory cultures, their bands and ranges.", steps=[
		step("Migratory cultures", "A state can have one migratory culture, with its strength and its band.",
			 lambda a: a.mig_frame, layer("culture")),
		step("Bands", "A migratory culture's bands: make one (New band...), edit it, take it out. A band has its own "
			 "token, so it's never the same as a subculture's.", lambda a: a.band_box, layer("culture")),
		step("Ranges", "Paint band range [6] paints where a band roams; Show band range lights it up, and Show all band "
			 "ranges draws every one on the Migratory map.", lambda a: find(a.mig_frame, "Paint band range"), layer("culture")),
		step("Migratory only", "Lists only the migratory cultures and their bands.", lambda a: a.only_check, layer("culture")),
	]),
	"language": dict(title="🗣 Languages", intro="Languages, alphabets and literacy.", steps=[
		step("The Language layer", "Language families, groups and languages, and the alphabets they're written in. Which "
			 "language a state speaks comes from its subcultures, so here you look rather than paint.",
			 lambda a: find(a.mode_frame.master, "Language"), layer("language"), click=True),
		step("Languages or alphabets", "Pick what the list holds.", lambda a: a.view_frame, layer("language")),
		step("New language / alphabet", "Make a language or an alphabet; Edit... changes the picked one.",
			 lambda a: a.tree_buttons, layer("language")),
		step("Literacy", "The Brush literacy map mode shows how literate each state is in the picked language.",
			 lambda a: a.mode_frame, layer("language")),
	]),
}


# ---------- Country Master ----------
def country_layer(key):
	def go(app):
		if app.layer.get() != key:
			app.layer.set(key)
			app.switch_layer()
	return go


def country_page(name):
	def go(app):
		for i, t in enumerate(app.tabs.tabs()):
			if app.tabs.tab(t, "text") == name:
				app.tabs.select(i)
				return
	return go


COUNTRY = {
	"general": dict(title="Getting started", intro="A look around Country Master.", steps=[
		step("Welcome to Country Master", "Every tag: what it starts the game with (names, flags, politics, leaders, ideas, "
			 "army) and how it can appear (collapses, bombs, events, formables). Each page saves straight into the mod's "
			 "files; the old file goes to tools/country_master/backups first."),
		step("Start date", "One tab per bookmark date: the history, owners and cores as the game has them then.",
			 lambda a: a.date_bar),
		step("Layers", "Countries, Sub-ideologies or Formables.", lambda a: a.layer_row, country_layer("countries")),
		step("Show", "What the list holds: every country, those on the map at start, the collapses, the Time / Reality / "
			 "Myth Bombs, the ones that can spawn by event...", lambda a: a.show_box, country_layer("countries")),
		step("Gap Finder and Sort", "Only the countries with a problem (no leader, no flag, a missing portrait...), in "
			 "amber with a red count. Sort by name, tag, states, population or continent; Sub-ideologies groups them by "
			 "ruling party.", lambda a: find(a.country_controls, "Gap Finder")),
		step("The list", "Pick a country to see it. A collapse or bomb: click to preview it on the map, double-click (or "
			 "right-click) to keep it on. Right-click a country for Show on map and the events that make it.",
			 lambda a: a.tree),
		step("New Tag", "A new country: tag, names, colour, capital, ideology and flags - written to the tag, colour, "
			 "history and localisation files.", lambda a: find(a.root, "New Tag")),
		step("Map modes", "Owners, the picked country's cores, ideology, sub-ideology, brush strength, continents. View "
			 "picks which ideology's leaders it goes by.", lambda a: a.mode_buttons["owner"].master),
		step("The map", "Click a state to pick its owner; right- or middle-drag to move; scroll to zoom. Right-click for "
			 "Show on map and more.", lambda a: a.canvas),
		step("The country", "Its flag and name; drag the divider to the left of it to give it more room.",
			 lambda a: a.head_title),
		step("Country page", "Overview, Parties, Generics, Characters, National ideas, OOB, History file, How it appears. "
			 "Each has its own Save button.", lambda a: a.country_page, click=True),
		step("Check recent changes", "Everything saved this session: when, and the files it wrote. Double-click one to go "
			 "back to it.", lambda a: find(a.root, "Check recent changes")),
	]),
	"pages": dict(title="📄 The country's pages", intro="What each page edits (pick a country first).", steps=[
		step("Overview", "Names (and per ideology), map colour, flags, capital, stability, war support, research slots, "
			 "ruling party, elections, popularities, the leader shown at start, a cosmetic tag and its collapses. Click a "
			 "section title to fold it.", lambda a: a.tabs, country_page("Overview")),
		step("Parties", "The parties at the start (Globus's party system): names, popularities, leaders.",
			 lambda a: a.tabs, country_page("Parties")),
		step("Generics", "Its generic portraits - the random ones for generals, admirals, advisors, operatives. "
			 "Right-click one to mark it for rework.", lambda a: a.tabs, country_page("Generics")),
		step("Characters", "Everyone it recruits at start plus every TAG_ character, by role. Pick a role, search, "
			 "and edit them in the form (or as script); New character... adds one. Leaders added later by focuses, "
			 "decisions or events can be shown too.", lambda a: a.tabs, country_page("Characters")),
		step("National ideas", "The ideas it starts with and every TAG_ idea, with their pictures. Add one, or edit the "
			 "whole idea below.", lambda a: a.tabs, country_page("National ideas")),
		step("OOB", "Its order of battle file: templates, divisions and ships.", lambda a: a.tabs, country_page("OOB")),
		step("History file", "The whole history file, to edit by hand.", lambda a: a.tabs, country_page("History file")),
		step("How it appears", "The events that can make it (launch one to see it on the map), its states at start, the "
			 "collapses and bombs that make it or break it up, and its cores.", lambda a: a.tabs, country_page("How it appears")),
	]),
	"collapses": dict(title="💥 Collapses and bombs", intro="Previewing how countries break up.", steps=[
		step("Collapses", "Show > Collapses lists every debug collapse with the countries it makes.",
			 lambda a: a.show_box, country_layer("countries")),
		step("Preview or switch on", "Click one to preview it on the map; double-click to keep it switched on, so you can "
			 "stack several. Collapse all switches every collapse on; Switch off all clears them.",
			 lambda a: find(a.root, "Collapse all")),
		step("Bombs", "The Time, Reality and Myth Bombs are in Show too, and work the same way.", lambda a: a.show_box),
	]),
	"subs": dict(title="🎭 Sub-ideologies and formables", intro="The other two layers.", steps=[
		step("Sub-ideologies", "Every sub-ideology like the religions in Culture Master: icon, name, description, colour. "
			 "Double-click one to edit it; the Brush strength map shows its popularity.",
			 lambda a: a.layer_row, country_layer("subs"), click=True),
		step("Formables", "Nations that can be formed or reformed: Both / Formable / Reformable, with the map showing what "
			 "each needs. Tools > New formable nation... makes one.", lambda a: a.layer_row, country_layer("formables")),
		step("Back to countries", "Layer: Countries brings the country list back.", lambda a: a.layer_row, country_layer("countries")),
	]),
}


# ---------- Model Master ----------
def model_tab(i):
	return lambda app: app.editor_tabs.select(i)


def some_model(app):
	"""A model to look at (GER's infantry) when none is picked yet."""
	if getattr(app, "model", None) is None:
		try:
			app.open_target("rr://model/entity/GER_infantry_entity")
		except Exception:
			pass
	app.editor_tabs.select(0)


MODEL = {
	"general": dict(title="Getting started", intro="A look around Model Master.", steps=[
		step("Welcome to Model Master", "Every unit model the game can show - the base game, every DLC and RR's own - by "
			 "country and type, in 3D. Recolour them Dawn of War style, add camo and stickers, and Apply them to a country "
			 "so its units really look that way in game."),
		step("Whose models", "The country (or shared culture) whose models are listed. Change… to pick another.",
			 lambda a: a.owner_switch),
		step("Search and type", "Search every model by name; Type narrows it to infantry, tanks, planes, ships...",
			 lambda a: find(a.root, "Search models").master),
		step("The models", "Pick one to see it.", lambda a: a.list, some_model),
		step("The preview", "Drag to turn it, Shift+drag to move it, scroll to zoom, double-click to reset. Click a part of "
			 "the model: its colour area lights up, on the model and in the list. Drag the bar beside it for a bigger view.",
			 lambda a: a.view_box),
		step("Normal / Snow / Desert", "The model's other looks, when it has them.", lambda a: a.looks),
		step("Colours and Stickers", "The two sides of painting a model.", lambda a: a.editor_tabs),
		step("Apply to a country", "Writes the model as you've painted it into the mod for a country (one model, or all "
			 "its tanks, infantry...). Models > What's applied takes it out again.",
			 lambda a: find(a.root, "Apply to a country"), model_tab(0)),
	]),
	"colours": dict(title="🎨 Colours and camo", intro="Recolouring areas, camo patterns, schemes.", steps=[
		step("Texture", "A model can have several textures (the soldier, his rifle, his bike); each has its own segments.",
			 lambda a: a.part_box, some_model),
		step("Segments", "Each texture is split into segments (Uniform, Helmet, Skin...). The left swatch lights one up "
			 "on the model, right-clicking it turns the model to it; the next box picks its new colour; Strength sets how "
			 "far it's recoloured. Light, shade and wear always stay.", lambda a: a.rows),
		step("Sub-segments", "A segment can have sub-segments under it: Uniform > Tunic and Trousers > Collar, Piping, "
			 "Buttons, Insignia... 🔗 means it takes its segment's colour when it has none of its own (Tunic and Trousers "
			 "with the Uniform); ⛓ keeps its own (the piping stays white when the tunic goes red) - click to switch. ▾ folds "
			 "them away. ⋯ splits sub-segments off by colour, adds a new one to paint in Touch up, moves a segment under "
			 "another, links it with any other segment so they share one colour (⇄: Hands and Face), or merges.",
			 lambda a: a.rows),
		step("▦ Camo, materials and faces", "The ▦ box paints the segment in a camouflage pattern (29 in use up to the "
			 "1960s), a material (steel, rusty iron, gold, wood, leather, fur...) or a face (5 skin tones for each of 9 "
			 "peoples). Change its colours, size, turn, brightness, vibrancy and contrast, 🎲 shuffle it, or save your own. "
			 "It's made on the model, so it runs on across the texture's seams.", lambda a: a.rows),
		step("Touch up segments", "Paint the segments by hand with Photoshop's keys: B brush, E eraser, G fill, Alt+click "
			 "to pick a segment, [ ] for the size, Ctrl+Z to undo. Save segments keeps them for the whole team.",
			 lambda a: find(a.root, "Touch up segments")),
		step("Re-detect segments", "Splits the texture again by colour, into at most Segment limit segments.",
			 lambda a: find(a.root, "Re-detect segments")),
		step("Colour schemes", "Save the colours (camo and stickers too) as a scheme - \"Polish khaki\", \"Red Army "
			 "winter\" - and put it on any other model: segments are matched by name.", lambda a: a.scheme_box),
	]),
	"stickers": dict(title="🏷 Stickers", intro="Symbols, pictures and flags on a model.", steps=[
		step("The library", "Stock stickers, the team's own (Import image…) and countries' flags (Add flag…). Drag one "
			 "onto the model, or pick it and click the model.", lambda a: a.lib, lambda a: (some_model(a), model_tab(1)(a))),
		step("Moving it", "Drag a sticker on the model to move it; Ctrl+scroll sizes it, Alt+scroll turns it, Delete takes "
			 "it off. Stickers wrap over the model's surface like a game's decals.", lambda a: a.view_box, model_tab(1)),
		step("On this model", "The stickers on the model: pick one to change its size, turn, opacity, colour (or its own "
			 "colours) and mirror it.", lambda a: a.placed, model_tab(1)),
		step("Layer", "Under ▾ tucks the sticker beneath segments - a badge behind the webbing straps, a number under the "
			 "buttons. Only on ▾ keeps it to them - a colour on just the buttons or the collar.",
			 lambda a: a.st_layers["under"][0], model_tab(1)),
		step("In the game", "Schemes keep the stickers, and Apply bakes them into the textures it writes.",
			 lambda a: a.placed, model_tab(1)),
	]),
}
