"""🐞 Error Log Master's know-how: what common errors mean and how to fix them (help_for), the easy ones fixed in a click
(🔧: missing synchronized tokens, duplicate loc keys with the same text, a missing UTF-8 BOM, misspellings), and the
localisation spell check. Every fix copies the file to tools/organisation_master/backups/error_fixes/<time>/ first."""
import datetime
import os
import re
import shutil
import time
from collections import defaultdict

import paths

TOKENS_FILE = "common/synchronized_dynamic_tokens/tokens.txt"
REPLACE_FILE = "localisation/english/replace/rr_replace_l_english.yml"  # (HOI4: keys in replace/ override the game's, no clash)
DLC = {"goe": "Götterdämmerung", "aat": "Arms Against Tyranny", "bba": "By Blood Alone", "nsb": "No Step Back",
	   "lar": "La Résistance", "mtg": "Man the Guns", "wtt": "Waking the Tiger", "dod": "Death or Dishonor",
	   "toa": "Trial of Allegiance", "tfv": "Together for Victory", "bftb": "Battle for the Bosporus", "gtd": "Gotterdammerung",
	   "ttr": "Trial by Fire", "noa": "Night of the Assassins"}


def dlc_of(rel_path):
	"""The DLC a game localisation file belongs to (goe_focus_l_english.yml: Götterdämmerung), or None."""
	name = os.path.basename(rel_path).lower()
	return DLC.get(name.split("_", 1)[0]) if "_" in name else None

# ---------- what it means / how to fix it ----------
HELP = (
	(lambda k, t: k == "Focuses on the same spot", "Focuses on the same spot",
	 "Two focuses end up at the same place in the tree (x / y counted from their relative_position_id), so one is drawn "
	 "over the other and players can't see or click it.\nFix: move one (x / y), or check its relative_position_id points "
	 "at the focus you meant. 🙈 Accept → Intentional if they're never both visible (allow_branch / offset).", None),
	(lambda k, t: k == "Mutually exclusive on one side only", "Mutually exclusive on one side only",
	 "Focus A lists B as mutually exclusive but B doesn't list A. The game checks it on the focus being taken, so after "
	 "A, B can still be taken - both end up done (and the tree doesn't draw the exclusive line properly).\nFix: add "
	 "mutually_exclusive = { focus = A } to B too.", None),
	(lambda k, t: k == "Focuses that do nothing", "A focus that does nothing",
	 "The focus has no completion_reward (or an empty one): completing it gives nothing - often a placeholder that was "
	 "never filled in.\nFix: give it its reward, or 🙈 Accept → Intentional if it's only a step to unlock others.", None),
	(lambda k, t: k == "Can never be taken", "A focus that can never be taken",
	 "available = { always = no } with no bypass: nobody can ever start it.\nFix: if it's waiting for content, fine "
	 "(🙈 Intentional); otherwise give it its real available.", None),
	(lambda k, t: k == "Events that fire by themselves for everyone", "An event that fires for everyone",
	 "The event has mean_time_to_happen (so the game tries it on its own) but no trigger and isn't is_triggered_only - "
	 "every country gets it, at random, from day one.\nFix: add is_triggered_only = yes if something fires it, or a "
	 "trigger (tag = ..., a flag) saying who it's for.", None),
	(lambda k, t: k == "Events that can repeat forever", "An event that can repeat",
	 "It fires by itself (mean_time_to_happen) and nothing stops it happening again: no fire_only_once and its trigger "
	 "checks no flag / variable / idea that the event changes.\nFix: add fire_only_once = yes, or set a flag in the "
	 "event and check NOT = { has_country_flag = ... } in the trigger. 🙈 Intentional if it's meant to recur.", None),
	(lambda k, t: k == "Event options with the same text", "Options with the same text",
	 "Several options of one event use the same name = loc key, so they show the same text - usually a copy-pasted option "
	 "whose name wasn't changed.\nFix: give each option its own name (event.1.a, .b, .c) and text.", None),
	(lambda k, t: k == "A tag's decision every country can see", "A tag's decision every country can see",
	 "The decision is named for one country (GER_...) but neither it nor its category checks the tag (no allowed, "
	 "tag = or original_tag =), so every country gets it.\nFix: add allowed = { original_tag = GER } to the decision or "
	 "its category.", None),
	(lambda k, t: k == "Loops over everything with no limit", "A loop over everything, unfiltered",
	 "every_country / every_state with no limit runs its effects on every single one - war, annexing, states, ideas for "
	 "the whole world. Sometimes meant (a debug decision), usually a forgotten limit.\nFix: add limit = { ... } "
	 "(tag, is_neighbor_of, is_owned_by...).", None),
	(lambda k, t: k == "An empty limit", "An empty limit",
	 "limit = { } has nothing in it, so it lets everything through - usually a condition that was deleted or never "
	 "written.\nFix: write the condition, or remove the empty limit.", None),
	(lambda k, t: k == "Placeholder text", "Placeholder text",
	 "The text players see still says TODO / placeholder / FIXME / WIP / lorem ipsum.\nFix: write the real text (or 🙈 "
	 "Intentional if the feature isn't live yet).", None),
	(lambda k, t: k == "Copy-pasted text", "Copy-pasted text",
	 "Two different things (focuses, ideas, tooltips...) have word-for-word the same long text - often a copy whose text "
	 "was never changed for the second one.\nFix: write the second one's own text, or reuse the first key ($KEY$) if "
	 "they're meant to match (🙈 Intentional).", None),
	(lambda k, t: "AI tried to post an invalid command" in t, "The AI tried something it can't do",
	 "The game's own AI asked for an order that isn't allowed right then (merge_navies when the fleets can't merge, and "
	 "so on) and the game refused it. It's the AI, not the mod's script - the base game logs thousands of these too.\n"
	 "Nothing to fix; 🙈 hide it. (Only worth a look if it's always the same mod-made unit or fleet.)", None),
	(lambda k, t: "invalid scope for var" in t, "A variable read in the wrong scope (in a text)",
	 "A localisation text shows a variable ([?ROOT.some_var] / [ROOT.GetName] style) but the scope it's read from isn't "
	 "the one that has it - so the text shows nothing or 0. The key named is the variable.\nFix: in the loc text (or the "
	 "scripted localisation feeding it) read it from the scope that set it (THIS / FROM / a saved event target), or "
	 "set the variable on ROOT before the text is shown. Search the mod's localisation for the variable's name.", None),
	(lambda k, t: "has_border_war_between" in t and "No combat between states" in t, "A border war check with no border war",
	 "has_border_war_between is checked while those two states aren't fighting a border war, so the game complains "
	 "every time it's evaluated (usually an on_action or a decision's visible/available).\nFix: check "
	 "has_border_war = yes (or that the war started) first, in the same limit/AND, so this only runs during the war.", None),
	(lambda k, t: "all entries in random_list have" in t, "A random_list where nothing can happen",
	 "Every entry of the random_list has 0 chance right now (their weights' modifiers took them all to 0), so it does "
	 "nothing.\nFix: give one entry a base weight that stays above 0 (a 'nothing happens' entry is fine), or wrap the "
	 "random_list in an if so it only runs when one of them can happen.", None),
	(lambda k, t: "Song doesnt exist" in t, "A song that isn't there",
	 "play_song (or a music effect) names a song no music file defines - often a song from a music mod that isn't "
	 "running, or a typo.\nFix: check the name against music/*.txt (the song's name =), or only play it when its music "
	 "is loaded.", None),
	(lambda k, t: "does not have resistance" in t or "already has a resistance" in t, "Resistance on a state that has none",
	 "add_resistance / add_compliance (or a check of them) runs on a state with no resistance - it isn't occupied, or it's "
	 "a core of its owner - so it does nothing (or the other way round: start_resistance on a state that already has "
	 "it).\nFix: check first - has_resistance = yes before add_resistance / add_compliance, NOT = { has_resistance = yes } "
	 "before start_resistance.", None),
	(lambda k, t: "Invalid equipment version" in t, "Equipment that doesn't exist (add to stockpile)",
	 "add_equipment_to_stockpile names an equipment type (or a variant name / version) the country can't have - the "
	 "type is wrong, it's an archetype, or the variant name doesn't exist for that country.\nFix: use a real equipment "
	 "(infantry_equipment_1...), and for a named variant create it first (create_equipment_variant) or drop the "
	 "version_name.", None),
	(lambda k, t: "appears to not have been unlocked" in t, "A variant made before its tech",
	 "create_equipment_variant makes a plane / tank / ship design on a module or airframe the country hasn't researched "
	 "yet - the game warns it can break later.\nFix: give the tech first (set_technology / its history file), then "
	 "create the variant.", None),
	(lambda k, t: "Invalid icon" in t and "create_equipment_variant" in t, "An equipment variant with a missing icon",
	 "The variant's icon = names a GFX_ sprite no .gfx file defines, so it shows a blank or default picture.\nFix: "
	 "define the sprite (interface/*.gfx) or point at an existing one.", None),
	(lambda k, t: "on unlocked template" in t, "Changing a division template found by name",
	 "add_units_to_division_template runs on a template the player can rename, so it may not find it later.\nFix: only "
	 "use it on templates you made locked (is_locked = yes in the division_template), or make a new template instead.", None),
	(lambda k, t: "several country leader roles, ideology is mandatory" in t, "Which leader role? (ideology missing)",
	 "The character is a country leader for more than one ideology, so swap_country_leader_traits / a leader effect "
	 "doesn't know which role you mean.\nFix: add ideology = <sub-ideology> to the effect.", None),
	(lambda k, t: "Could not find country leader role" in t, "A leader role that isn't there",
	 "remove_country_leader_role (or similar) names an ideology the character has no country leader role for - removed "
	 "already, or never added.\nFix: guard it: if = { limit = { has_country_leader_role = { ... } } } (or check the "
	 "ideology name against the character's file).", None),
	(lambda k, t: "invalid event target" in t, "An event target that wasn't saved",
	 "event_target:<name> is used but nothing saved it (save_event_target_as / save_global_event_target_as) - or it was "
	 "cleared, or it only exists inside another event chain.\nFix: save it before use (global if other events read it), "
	 "and check it exists: limit = { has_event_target = <name> }.", None),
	(lambda k, t: "No valid option for event" in t, "An event with no option to pick",
	 "Every option of the event has a trigger that's false for this country, so there's nothing to choose (the event "
	 "does nothing, or the AI gets stuck).\nFix: give it one option without a trigger (or with the opposite of the "
	 "others).", None),
	(lambda k, t: "diplomatic_relation" in t and "already exists" in t, "A pact that's already there",
	 "diplomatic_relation adds a relation (non-aggression pact, guarantee...) the two countries already have - harmless, "
	 "nothing changes.\nFix (to quiet it): check first, e.g. limit = { NOT = { has_non_aggression_pact_with = JAP } }.", None),
	(lambda k, t: "Could not find" in t and " in window " in t, "A GUI element the game expects is missing",
	 "The game's code looks for an element by name in this window (portrait_dismiss_btn in "
	 "operation_operative_leader_portrait_window...) and the mod's .gui file doesn't have it - usually a .gui copied from "
	 "an older game version.\nFix: compare the window with the game's own interface file and add the missing element "
	 "(it can be invisible), or re-copy the game's window and redo the mod's change.", None),
	(lambda k, t: t.startswith("No font with name"), "A font that isn't named",
	 "Something asks for a font with an empty (or unknown) name - a .gui / .gfx font = that's blank, or a text style "
	 "naming a font no .font file defines. Usually harmless (the default font is used).", None),
	(lambda k, t: t.startswith("Unknown promotion"), "A text command the game doesn't know",
	 "A localisation text uses a [...] command with a name the game doesn't recognise (\"SPD\" here) - typically a party / "
	 "tag name written where a scope or function was expected.\nFix: search the mod's localisation for it (\"SPD\") inside "
	 "[ ] and correct it (e.g. [SPD.GetName] needs SPD to be a country tag that exists).", None),
	(lambda k, t: "Army changed general while deploying" in t, "The AI swapped a general mid-deployment",
	 "The game's AI changed an army's general while it was deploying. The message itself says this can be fine; it's "
	 "not the mod's script. Nothing to fix.", None),
	(lambda k, t: t.startswith("Reloading Database"), "The game reloaded a folder (not an error)",
	 "Not a mistake in the mod. While the game runs in debug mode it watches the mod's files: when a file in this folder "
	 "(here common/ideas) is saved while you're playing, it reads the whole folder again and writes this line.\n"
	 "Errors just after it (same time stamp) come from that reload - a reload can complain about things a fresh start "
	 "doesn't (\"already exists\", duplicate ideas), so check them on a clean launch before fixing anything.\n"
	 "If you didn't save anything: something else wrote to the folder while the game ran - OneDrive syncing, a git pull, "
	 "or a master (Culture Master saves _culture.txt). Nothing to fix; 🙈 hide it if it's noise.", None),
	(lambda k, t: "Attempting to set capital state" in t, "A capital the country doesn't own",
	 "The country is given a capital state it doesn't own at that moment, so the game ignores it and picks one itself "
	 "(often far from where you meant).\nUsually the capital = line in its history/countries file points at a state "
	 "another country owns (a typo, or the states were given away / renumbered). It can also be a set_capital effect "
	 "run before the country gets the state.\nFix: 🔧 shows the country's history (code panel) and the states it owns - "
	 "pick the right one and it rewrites capital = .", "capital"),
	(lambda k, t: "is a dynamic token" in t, "Dynamic tokens (multiplayer out-of-sync risk)",
	 "The script makes token:X out of something at runtime (a culture, a party...), but X isn't listed in "
	 "common/synchronized_dynamic_tokens. Single player works; in multiplayer the players' games can go out of sync.\n"
	 "Fix: list each X in common/synchronized_dynamic_tokens/tokens.txt, one per line. 🔧 Fix it adds the missing ones "
	 "(ones added since this run are skipped).", "tokens"),
	(lambda k, t: "dynamic token that does not exist" in t, "A token that doesn't exist",
	 "Something asks for token:X, but X was never made. Usually it's a culture / religion / party that's in a list but not in "
	 "synchronized_dynamic_tokens - or a typo (check the names below first: a misspelt one needs fixing where it's used).\n"
	 "Fix: 🔧 Fix it adds them to common/synchronized_dynamic_tokens/tokens.txt.", "tokens"),
	(lambda k, t: re.fullmatch(r"#? ?errors\.|\d+ errors\.", t) is not None, "The token errors' total",
	 "The game's count of the token problems above ('Token … is a dynamic token' / 'does not exist'). It goes away when they're "
	 "fixed: 🔧 Fix it adds every missing token from this log.", "tokens"),
	(lambda k, t: "Duplicate localization" in t or "loc key collisions" in t or k == "Localisation keys defined twice", "The same loc key twice",
	 "One localisation key is in two files. The game shows only one of them (whichever loads last), so the other text "
	 "never appears - and which one wins can change.\nFix: keep one. When both say the same thing, 🔧 Fix it comments out "
	 "the extra copy. When they differ, pick the right text and delete the other line.", "dupe"),
	(lambda k, t: t.startswith("Duplicate idea"), "Two ideas with the same name",
	 "Two national ideas / spirits share an idea key; the game keeps one and drops the other.\nFix: 🔧 Fix it shows every "
	 "definition; keep one and the others are commented out (when they differ, keep the right one - or rename one instead: "
	 "its key, its loc and everything that adds it).", "ideas"),
	(lambda k, t: k == "Map" and "sea province" in t, "A sea province in a state",
	 "A state lists a province that's sea on the map (map/definition.csv). States are land (lakes are fine).\nFix: take it out "
	 "of the state, or fix its type in definition.csv if it's really land.", None),
	(lambda k, t: k == "Map" and "is in state" in t, "A province in two states",
	 "Two states both list the province: the game gives it to one and complains.\nFix: take it out of one of them.", None),
	(lambda k, t: k == "Map" and "doesn't have" in t, "A province that isn't on the map",
	 "A state lists a province id map/definition.csv doesn't have (removed, or a typo).\nFix: take it out or fix the id.", None),
	(lambda k, t: k == "Map" and "victory points" in t, "Victory points outside the state",
	 "victory_points = { province value } names a province that isn't one of the state's.\nFix: use one of its provinces.", None),
	(lambda k, t: k == "Map" and "no state" in t, "Land provinces in no state",
	 "These land provinces belong to no state: nobody can own them.\nFix: add each to a state (Culture Master's map shows "
	 "them as gaps).", None),
	(lambda k, t: k == "Map" and "strategic region" in t, "Strategic regions",
	 "Every land and sea province must be in exactly one strategic region (weather, air zones, navies).\nFix: add the missing "
	 "ones to a region in map/strategicregions, or take the doubled one out of one.", None),
	(lambda k, t: k == "Map", "The map's bookkeeping",
	 "A map file (supply nodes, railways...) uses a province that isn't land on the map - usually after map edits.\nFix: open "
	 "the line and point it at the right province, or remove it.", None),
	(lambda k, t: k == "Culture data", "Culture data (Culture Master's check)",
	 "From Culture Master's Tools > Check for problems: states whose cultures / religions don't add up, majorities that "
	 "aren't the largest, tokens that aren't synchronized...\nFix: open Culture Master and correct the state (its 'Missing "
	 "data' map mode shows them).", None),
	(lambda k, t: k == "Performance hints" and "24-bit flag" in t, "A 24-bit flag",
	 "The flag is a 24-bit TGA: it loads slowly.\nFix: 🔧 Fix it saves it as 32-bit (it looks the same).", "flag32"),
	(lambda k, t: k == "Performance hints" and "on_daily" in t, "A daily on_action",
	 "on_daily runs for every country, every single day - the costliest place for script.\nFix: keep it to a few cheap "
	 "checks, or move the work to on_weekly / on_monthly.", None),
	(lambda k, t: k == "Performance hints", "A loop inside a loop",
	 "A loop over every state / country inside another one: thousands of checks each time it runs.\nFix: narrow the outer "
	 "loop (a limit, or a list / array of the ones that matter), or run it less often.", None),
	(lambda k, t: "Consider using" in t and "bpp" in t, "A 24-bit flag",
	 "The flag is a 24-bit TGA (no transparency): the game loads it slowly and complains each time.\nFix: 🔧 Fix it saves it "
	 "(and its medium / small copies) as 32-bit TGA - the look doesn't change.", "flag32"),
	(lambda k, t: "music files should be in" in t, "A music file at the wrong sample rate",
	 "The game plays music best at 44.1 kHz; this one isn't (often 48 kHz), so it's resampled while playing.\nFix: convert it to "
	 "44.1 kHz (Music Master's audio tools, or any audio editor) and save it over the old one.", None),
	(lambda k, t: "Reached max recursive depth" in t, "Scripted localisation that calls itself",
	 "A scripted localisation (or loc key) ends up using itself - directly or round a loop - so the game gives up.\nFix: find "
	 "the loop in common/scripted_localisation / the loc text ([...] inside its own text) and break it.", None),
	(lambda k, t: "Missing music_station faceplate" in t, "A music station without its faceplate",
	 "The radio station is defined but the GUI it needs (a containerWindowType named <station>_faceplate in interface/*.gui) "
	 "isn't there, so its player can't show.\nFix: add the faceplate window (copy another station's and rename it) - Music "
	 "Master makes these for RR's stations.", None),
	(lambda k, t: "Failed to find entity" in t, "A 3D model that isn't there",
	 "An attachment (or a unit's graphics) points at an entity no gfx/entities/*.asset defines.\nFix: add the entity, or point "
	 "it at one that exists. The code view shows where the name is used.", None),
	(lambda k, t: "outgoing xor paths" in t, "A tech tree XOR the game can't draw",
	 "A technology has more than one pair of either-or (XOR) branches in that folder; the tree only draws the first.\nFix: "
	 "only if it looks wrong in game - simplify the XORs or move one into another row. Harmless otherwise.", None),
	(lambda k, t: "Faction goal not found" in t or "did not match any of the rule groups" in t, "A faction setting that doesn't exist",
	 "A faction template names a goal / rule that isn't defined (factions were reworked in a recent HOI4 version).\nFix: define "
	 "it in common/factions (goals / rules) or point at an existing one.", None),
	(lambda k, t: "Missing icon for focus" in t or "Missing icon shine" in t, "A focus icon (or its shine) that isn't there",
	 "The focus's icon sprite isn't defined - or it is, but its shine version (goals_shine.gfx, for the glint when the focus is "
	 "available) isn't.\nFix: add the spriteType (and its _shine copy), or use an icon that has them.", None),
	(lambda k, t: "Not a valid value" in t, "A value the key doesn't accept",
	 "The key is fine but its value isn't one it takes (yes where a number or name is expected, a misspelt name, a value from "
	 "an older HOI4).\nFix: open the line and check the value.", None),
	(lambda k, t: "Invalid localize key for country_culture" in t, "A country without its culture's text",
	 "A country's culture (the newer culture system's country_culture) has no localisation key.\nFix: add the culture's loc "
	 "key, or check the country's culture setting.", None),
	(lambda k, t: "Invalid Decision ID for targeted decision" in t, "A targeted decision that doesn't exist",
	 "activate_targeted_decision (or similar) names a decision id that isn't defined - often a placeholder like A left in.\n"
	 "Fix: put the real decision id there.", None),
	(lambda k, t: "Market access between" in t, "Market access that can't be given",
	 "give_market_access between two countries the game won't allow (one doesn't exist at that point, or they're at war / "
	 "embargoed).\nFix: check both tags exist at start and the history order.", None),
	(lambda k, t: "too far away from center" in t, "Unit models too far from the province centre",
	 "map/unitstacks.txt places a province's units / buildings far from it (usually after map edits).\nFix: regenerate the "
	 "positions (Nudger in the game's debug mode) or correct the entry - only matters if it looks wrong on the map.", None),
	(lambda k, t: re.search(r"(?:Invalid effect '|effect-type: )(has_|is_|any_|all_|not_)", t) is not None, "A trigger used as an effect",
	 "has_* / is_* / any_* are triggers - questions, not actions - and can't run as an effect.\nFix: put it inside a limit / "
	 "trigger (e.g. if = { limit = { has_completed_focus = X } ... }).", None),
	(lambda k, t: re.search(r"(?:Invalid effect '|effect-type: )[A-Z]{2,3}_", t) is not None, "A scripted effect that doesn't exist",
	 "A mod effect with that name (TAG_...) isn't defined in common/scripted_effects - removed, renamed or misspelt.\nFix: "
	 "define it or correct the name.", None),
	# (the mod check's new kinds)
	(lambda k, t: k == "Flags checked but never set" or "nothing ever sets it" in t, "A flag nothing sets",
	 "A has_*_flag checks a flag no effect anywhere sets (base game included, when the mod keeps its files): the check is "
	 "always false. Usually a typo, or the thing that set it was removed.\nFix: set it where it should be, fix the name, or "
	 "remove the check.", None),
	(lambda k, t: k == "Ideas used but never defined", "An idea that doesn't exist",
	 "add_ideas / has_idea / remove_ideas names an idea no common/ideas file defines (often a base-game idea when the mod "
	 "replaces common/ideas).\nFix: define it, correct the name, or remove the line.", None),
	(lambda k, t: k == "Country tags used but never defined", "A country tag that doesn't exist",
	 "tag = / original_tag = / exists = ... names a tag that isn't in common/country_tags - a typo or a removed country "
	 "(base-game leftovers are common).\nFix: correct it or remove the line.", None),
	(lambda k, t: k == "Characters used but never defined", "A character that doesn't exist",
	 "recruit_character / has_character / ... names a character no common/characters file defines.\nFix: define the character "
	 "or correct the id.", None),
	(lambda k, t: k == "Focuses used but never defined", "A focus that doesn't exist",
	 "A prerequisite / mutually_exclusive / has_completed_focus names a focus id nobody defines - renamed or removed.\nFix: "
	 "correct the id or remove it.", None),
	(lambda k, t: k == "Defined twice", "Defined twice",
	 "The same focus / event / idea id is defined twice: the game keeps one and silently drops the other.\nFix: remove the "
	 "copy, or rename one (and what refers to it).", None),
	(lambda k, t: k == "Event namespaces never declared", "An event namespace nobody declares",
	 "Events use ns.N ids but no events file has add_namespace = ns: those events don't load.\nFix: add add_namespace = ns "
	 "at the top of their file.", None),
	(lambda k, t: k == "Decision categories never defined", "Decisions in a category that doesn't exist",
	 "A decisions file puts decisions in a category common/decisions/categories doesn't define: none of them show.\nFix: "
	 "define the category or move them into an existing one.", None),
	(lambda k, t: k == "Texture files that aren't there", "A picture file that isn't there",
	 "A spriteType's texturefile points at a file that's in neither the mod nor the game: the sprite shows blank.\nFix: add "
	 "the file or fix the path (🖼 GFX tracks RR's missing pictures).", None),
	(lambda k, t: "Invalid effect '//'" in t or "effect-type: //" in t, "// isn't a comment in HOI4",
	 "HOI4 script comments start with #. A // is read as a key, so the game complains - and can lose the line after it.\n"
	 "Fix: 🔧 Fix it turns the // into #.", "comment"),
	(lambda k, t: "Unexpected token: ," in t or "Unexpected token: ,," in t, "A comma in the script",
	 "HOI4 script doesn't use commas between values (a = 1 b = 2, not a = 1, b = 2). The game stops reading that block there.\n"
	 "Fix: 🔧 Fix it takes the commas out of that line.", "comma"),
	(lambda k, t: "Malformed token" in t and "`" in t, "A stray ` in the script",
	 "A backtick slipped in (often next to 1, on the same key): the value can't be read.\nFix: 🔧 Fix it removes it.", "backtick"),
	(lambda k, t: "Malformed token" in t, "A value the game can't read",
	 "A number or name with a typo in it (a stray symbol, a missing space between two values).\nFix: open the line and correct it.", None),
	(lambda k, t: "'='" in t or "type: =," in t or "token: =," in t or "( = )" in t, "A stray =",
	 "Two = in a row (a = = b), or an = with nothing in front of it - often a key deleted by mistake, or a line split in two.\n"
	 "Fix: open the line and put the key back (or take the extra = out).", None),
	(lambda k, t: "Unexpected token" in t and "trigger_only_once" in t, "trigger_only_once isn't an event field",
	 "Events don't have trigger_only_once. For an event that should fire once use fire_only_once = yes (or is_triggered_only = "
	 "yes when something else fires it).\nFix: change the key on that line.", None),
	(lambda k, t: "Unexpected token" in t or "unexpected token" in t, "A key in the wrong place",
	 "The game met a key where it doesn't belong: a field that block doesn't have (e.g. available inside a character, "
	 "original_tag in a decision category - triggers go in visible / allowed = { }), a key outside its block (often a "
	 "missing } just above), or a stray =.\nFix: open the line; move the key into the right block, or check the braces above it.", None),
	(lambda k, t: "Multiple limits" in t, "Two limits in one if",
	 "An if = { } can have only one limit = { }; the game ignores the rest.\nFix: put all the conditions in one limit "
	 "(they're AND-ed), or split it into if / else_if.", None),
	(lambda k, t: "Invalid scope type for effect" in t, "An effect in the wrong scope",
	 "The effect works on a different kind of thing than the scope it's in - e.g. a country effect (add_ideas, set_technology, "
	 "set_oob) inside a state or character scope, or a state effect in a country one.\nFix: wrap it in the right scope (TAG = { }, "
	 "a state = { }...). Many in a row in one history file usually mean a missing } further up put them inside another block.", None),
	(lambda k, t: "Non assign trigger is not enclosed" in t, "A trigger without its = { }",
	 "A trigger that needs a block or a value was written bare (often value / a name on its own line, or a missing = ).\n"
	 "Fix: open the line and give it its = { ... } or = value.", None),
	(lambda k, t: "does not have a default icon case" in t, "A focus icon with no default",
	 "The focus has icon = { trigger = { } value = GFX_... } cases but none without a trigger, so sometimes it has no icon.\n"
	 "Fix: add one icon = GFX_... (or a case with no trigger) as the default.", None),
	(lambda k, t: "Invalid effect 'NOT'" in t or "effect-type: NOT" in t, "NOT used as an effect",
	 "NOT is a trigger: it can only go where conditions go (limit, trigger, allowed...).\nFix: put it inside the effect's "
	 "if = { limit = { NOT = { ... } } ... }.", None),
	(lambda k, t: "Invalid date" in t, "A date the game can't read",
	 "A history date block is written wrong (it must be like 1936.1.1 = { }).\nFix: open the line and correct the date.", None),
	(lambda k, t: "Unknown effect-type" in t or "Invalid effect" in t, "An effect that doesn't exist",
	 "The game doesn't know that effect: a typo, an effect renamed or removed in a newer HOI4 (add_autonomy is now "
	 "add_autonomy_ratio / add_autonomy_score; technology = in history is now set_technology = { }), or a trigger used as one.\n"
	 "Fix: check the name against the HOI4 wiki's effect list.", None),
	(lambda k, t: "Unknown trigger-type" in t or "Invalid trigger" in t, "A trigger that doesn't exist",
	 "The game doesn't know that trigger here: a typo, a renamed / removed one, a scope or tag used as a trigger (ROOT = ...), "
	 "or an extra = (a = = b).\nFix: check the line and the HOI4 wiki's trigger list.", None),
	(lambda k, t: "invalid database object" in t, "A name that doesn't exist (any more)",
	 "A doctrine / technology / other name the game doesn't have - usually removed in a newer HOI4 (the old doctrines like "
	 "masterful_blitz, trench_warfare were replaced by grand doctrines). The game then reads it as a variable.\nFix: update it "
	 "to the new name or remove it. The code view shows where it's used.", None),
	(lambda k, t: "Unknown technology category" in t, "A technology category that doesn't exist",
	 "add_tech_bonus names a category the game doesn't have (removed or renamed in a newer HOI4, like cl_tech).\nFix: use an "
	 "existing category (common/technology_tags) or remove it.", None),
	(lambda k, t: "Invalid Decision Category" in t, "A decision category that doesn't exist",
	 "Decisions point at a category nobody defined (or one with special letters in its name: keep keys plain a-z, 0-9, _).\n"
	 "Fix: define it in common/decisions/categories, or fix the name.", None),
	(lambda k, t: "Invalid focus" in t, "A focus that doesn't exist",
	 "A list of focuses (a bookmark's, a tree's) names one that was removed or renamed.\nFix: take it out or correct the id.", None),
	(lambda k, t: "Entity referenced in equipment graphic database" in t, "A 3D model that doesn't exist",
	 "An equipment's graphics point at an entity (3D model) no .asset file defines, so the unit shows no / a default model.\n"
	 "Fix: add the entity in gfx/entities, or point it at an existing one. The code view shows where it's named.", None),
	(lambda k, t: "recruit_character should only happen" in t, "recruit_character outside history",
	 "recruit_character is meant for history files (game start); elsewhere it can fail.\nFix: recruit them in the country's "
	 "history, or ignore it if it works as intended.", None),
	(lambda k, t: "supported_version" in t, "Another mod's .mod file",
	 "A subscribed mod's descriptor has an old supported_version. Nothing to do with RR - it's harmless.\nFix: none needed "
	 "(🙈 hide it).", None),
	(lambda k, t: k.startswith("Script errors"), "A key or value the game doesn't understand",
	 "At that file and line the game met a key, trigger or effect it doesn't know, or one used in the wrong scope "
	 "(a country trigger in a state scope...). Usually a typo or a copy-paste from another mod / version.\n"
	 "Fix: open the file at the line and compare with a working example.", None),
	(lambda k, t: t.startswith("Braces") or "never closed" in t or "} too many" in t, "{ } that don't add up",
	 "A block isn't closed (or closed twice). The game reads on as if it were, so everything after it can end up inside the "
	 "wrong block - silently: ideas, events or states just stop working.\nFix: open the file at the line given (where the "
	 "unclosed { opens) and add the missing } where that block should end. A good editor highlights the matching brace.", None),
	(lambda k, t: "is fired here but no event has that id" in t, "An event that doesn't exist",
	 "A decision / effect / on_action fires an event id nobody wrote (events/ replaces the base game's, so base-game events "
	 "aren't there either). In game nothing happens.\nFix: write the event, point it at the right id, or remove the call.", None),
	(lambda k, t: "isn't a spriteType" in t, "A picture the game doesn't know",
	 "GFX_x is used, but no interface/*.gfx file defines a spriteType with that name: the icon is blank.\nFix: add a spriteType "
	 "(name = \"GFX_x\" texturefile = \"gfx/...\") or fix the name. 🖼 GFX lists the missing pictures to make.", None),
	(lambda k, t: "No UTF-8 BOM" in t, "A localisation file without its BOM",
	 "HOI4 only reads localisation files saved as \"UTF-8 with BOM\"; without it the whole file is ignored.\nFix: 🔧 Fix it saves "
	 "it with the BOM (in an editor: Save with encoding > UTF-8 with BOM).", "bom"),
	(lambda k, t: "isn't l_<language>" in t, "A localisation file without its header",
	 "The first line of a localisation file must be l_english: (or the language); otherwise it's skipped.\nFix: add the line at the top.", None),
	(lambda k, t: t.startswith("Malformed line"), "A broken localisation line",
	 "Each line must be  key:0 \"text\"  - a missing quote or colon breaks it (and sometimes the lines after it).\nFix: open it and mend the line.", None),
	(lambda k, t: "has no name" in t or "has no text" in t, "Missing text",
	 "The focus / event has no localisation, so the game shows its raw key.\nFix: add  key:0 \"Text\"  to a localisation file.", None),
	(lambda k, t: t.startswith(("British spelling", "American spelling")), "The other English",
	 "The mod's text is written in one English (the Spelling: choice above the list) and this word is the other one's "
	 "spelling (color / colour, organize / organise...).\nFix: 🔧 Fix it changes it on that line - or dismiss it where it's a "
	 "name or meant (a quote, an American organisation's name...).", "spelling"),
	(lambda k, t: t.startswith("Spelling"), "A misspelling",
	 "A common misspelling in the text players read.\nFix: 🔧 Fix it corrects it in the file (or dismiss it if it's meant).", "spelling"),
)
RED = {"{ } that don't add up", "An event namespace nobody declares", "Decisions in a category that doesn't exist",
	   "A localisation file without its BOM", "A localisation file without its header", "A broken localisation line", "Defined twice",
	   "An event that doesn't exist", "A sea province in a state", "A province in two states", "A province that isn't on the map",
	   "Land provinces in no state", "Strategic regions", "A key in the wrong place", "Two limits in one if", "An effect in the wrong scope",
	   "A trigger without its = { }", "NOT used as an effect", "A stray =", "// isn't a comment in HOI4", "A comma in the script",
	   "A date the game can't read", "A value the game can't read", "A stray ` in the script", "Two ideas with the same name",
	   "trigger_only_once isn't an event field", "A trigger used as an effect"}
YELLOW = {"A misspelling", "The other English", "A 24-bit flag", "A music file at the wrong sample rate", "A tech tree XOR the game can't draw",
		  "Unit models too far from the province centre", "Another mod's .mod file", "A daily on_action", "A loop inside a loop",
		  "recruit_character outside history", "Missing text", "Dynamic tokens (multiplayer out-of-sync risk)",
		  "The game reloaded a folder (not an error)", "The AI tried something it can't do", "A border war check with no border war",
		  "A random_list where nothing can happen", "A song that isn't there", "Resistance on a state that has none",
		  "A variant made before its tech", "An equipment variant with a missing icon", "Changing a division template found by name",
		  "A pact that's already there", "A font that isn't named", "The AI swapped a general mid-deployment",
		  "A focus that does nothing", "A focus that can never be taken", "An event that can repeat", "Options with the same text",
		  "An empty limit", "Copy-pasted text"}
SEVERITY = {"🔴": "breaks things", "🟠": "wrong in game", "🟡": "cosmetic / minor"}


def severity(kind, text):
	"""🔴 breaks the game (things stop loading / working), 🟠 wrong in game, 🟡 cosmetic or minor."""
	title = help_for(kind, text)[0]
	return "🔴" if title in RED else "🟡" if title in YELLOW else "🟠"


DEFAULT_HELP = ("What to do", "Open the file (when the message names one) at the line and look there; ➕ To Do task makes a task for "
				"whoever last changed it.", None)


def help_for(kind, text):
	"""(title, explanation, fixer name or None) for an error."""
	for match, title, text_, fix in HELP:
		try:
			if match(kind or "", text or ""):
				return title, text_, fix
		except Exception:
			continue
	return DEFAULT_HELP


# ---------- editing the mod's files safely ----------
def backup(mod_root, rel_path, stamp):
	src = os.path.join(mod_root, rel_path)
	dst = os.path.join(paths.TOOL, "backups", "error_fixes", stamp, rel_path)
	os.makedirs(os.path.dirname(dst), exist_ok=True)
	shutil.copy2(src, dst)


def read_lines(path):
	"""(lines with their line ends, had a BOM)."""
	raw = open(path, "rb").read()
	bom = raw.startswith(b"\xef\xbb\xbf")
	return raw.decode("utf-8-sig", errors="replace").splitlines(keepends=True), bom


def write_lines(path, lines, bom):
	with open(path, "wb") as f:
		f.write((b"\xef\xbb\xbf" if bom else b"") + "".join(lines).encode("utf-8"))


def now_stamp():
	return datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ---------- 🔧 tokens ----------
def token_names(rows):
	names = []
	for r in rows:
		m = re.search(r"Token (\S+) is a dynamic token", r["msg"]) or re.search(r"dynamic token that does not exist: (\S+)", r["msg"])
		if m:
			names.append(m.group(1).strip().rstrip(".,"))
	return list(dict.fromkeys(names))


def listed_tokens(mod_root):
	out = set()
	folder = os.path.join(mod_root, os.path.dirname(TOKENS_FILE))
	for name in os.listdir(folder) if os.path.isdir(folder) else []:
		if name.endswith(".txt"):
			for line in read_lines(os.path.join(folder, name))[0]:
				w = line.split("#")[0].strip()
				if w:
					out.add(w)
	return out


def fix_tokens(mod_root, names):
	"""The names not listed yet go at the end of tokens.txt. (added, already there)."""
	have = listed_tokens(mod_root)
	add = [n for n in names if n not in have]
	if add:
		path = os.path.join(mod_root, TOKENS_FILE)
		backup(mod_root, TOKENS_FILE, now_stamp())
		lines, bom = read_lines(path)
		nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
		if lines and not lines[-1].endswith(("\n", "\r")):
			lines[-1] += nl
		lines += [f"# Added by Error Log Master, {datetime.date.today()} #{nl}"] + [n + nl for n in add]
		write_lines(path, lines, bom)
	return add, len(names) - len(add)


# ---------- 🔧 duplicate loc keys ----------
def loc_line_no(mod_root, rel_path, key):
	"""(0-based line index, its text value) of key in a localisation file, or (None, None)."""
	try:
		lines, _ = read_lines(os.path.join(mod_root, rel_path))
	except OSError:
		return None, None
	rx = re.compile(r'^\s*' + re.escape(key) + r':\d*\s*"(.*)"')
	for i, l in enumerate(lines):
		m = rx.match(l)
		if m:
			return i, m.group(1)
	return None, None


def copies(mod_root, key, entries, game=None):
	"""Every copy of a key: [{file, text, mod (True: the mod's - else the game's), line (the mod's: 0-based), dlc}]. entries:
	[(file, text as the log says, or None)]."""
	out, seen = [], set()
	for f, val in entries:
		if f in seen:
			continue
		seen.add(f)
		i, v = loc_line_no(mod_root, f, key)
		if i is not None:
			out.append(dict(file=f, text=v, mod=True, line=i, dlc=None))
		else:
			if val is None and game:
				val = loc_line_no(game, f, key)[1]
			if val is not None:
				out.append(dict(file=f, text=val, mod=False, line=None, dlc=dlc_of(f)))
	return out


def comment_out(mod_root, rel_path, i, why, stamp):
	path = os.path.join(mod_root, rel_path)
	backup(mod_root, rel_path, stamp)
	lines, bom = read_lines(path)
	end = "\r\n" if lines[i].endswith("\r\n") else "\n" if lines[i].endswith("\n") else ""
	lines[i] = f" # {lines[i].rstrip()}  # ({why}: Error Log Master){end}"
	write_lines(path, lines, bom)


def put_in_replace(mod_root, key, text, stamp):
	"""key: "text" in the mod's replace/ file (made with its BOM and header if needed; an older line for key replaced)."""
	path = os.path.join(mod_root, REPLACE_FILE)
	if os.path.isfile(path):
		backup(mod_root, REPLACE_FILE, stamp)
		lines, bom = read_lines(path)
	else:
		os.makedirs(os.path.dirname(path), exist_ok=True)
		lines, bom = ["l_english:\r\n", " # Keys that override the base game's (localisation in replace/ wins, without a clash).\r\n"], True
	nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
	new = f' {key}:0 "{text}"{nl}'
	rx = re.compile(r"^\s*" + re.escape(key) + r":\d*\s*\"")
	for i, l in enumerate(lines):
		if rx.match(l):
			lines[i] = new
			break
	else:
		if lines and not lines[-1].endswith(("\n", "\r")):
			lines[-1] += nl
		lines.append(new)
	write_lines(path, lines, bom)


def use_copy(mod_root, key, all_copies, chosen):
	"""The chosen copy is the one the game uses; the base game is never edited. The mod's other copies are commented out;
	the mod's text beating the game's goes to replace/ (where it overrides without a clash). Returns the files changed."""
	stamp, changed = now_stamp(), []
	keep = all_copies[chosen]
	game_has = any(not c["mod"] for c in all_copies)
	for n, c in enumerate(all_copies):
		if not c["mod"] or (n == chosen and not game_has):
			continue
		why = f"moved to {REPLACE_FILE}" if n == chosen else f"the game uses the copy in {keep['file']}"
		comment_out(mod_root, c["file"], c["line"], why, stamp)
		changed.append(c["file"])
	if keep["mod"] and game_has:
		put_in_replace(mod_root, key, keep["text"], stamp)
		changed.append(REPLACE_FILE)
	return list(dict.fromkeys(changed))


def make_empty(mod_root, rel_path):
	"""An empty file in the mod with the game's file's name: the game's whole file is switched off. False if the mod has one."""
	path = os.path.join(mod_root, rel_path)
	if os.path.exists(path):
		return False
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "wb") as f:
		f.write(b"\xef\xbb\xbf" + (f"l_english:\r\n # Empty on purpose: switches off the game's {os.path.basename(rel_path)}"
										f" ({dlc_of(rel_path) or 'base game'}), made by Error Log Master on {datetime.date.today()}.\r\n").encode("utf-8"))
	return True


def dupe_state(mod_root, key, entries):
	"""entries: [(file, its text as text.log says, or None)]. (the mod's copies [(file, line index, text)], the base game's
	copies [(file, text)], whether every copy says the same)."""
	mod, base = [], []
	for f, val in dict.fromkeys((f, v) for f, v in entries):
		i, v = loc_line_no(mod_root, f, key)
		if i is not None:
			mod.append((f, i, v))
		elif val is not None:
			base.append((f, val))
	texts = {v for _, _, v in mod} | {v for _, v in base}
	return mod, base, len(mod) + len(base) > 1 and len(texts) == 1


def dupe_plan(mod_root, key, entries):
	"""(the mod copies to comment out, which one stays) when every copy says the same, else ([], None)."""
	mod, base, same = dupe_state(mod_root, key, entries)
	if not same or not mod:
		return [], None
	if len(mod) > 1:
		return mod[1:], mod[0][0]
	return mod, f"the base game's {base[0][0]}"  # (the game has the same text: the mod's copy isn't needed)


def fix_dupe(mod_root, key, entries):
	"""Every copy says the same: the extra ones in the mod commented out. Returns the files changed."""
	drop, keep = dupe_plan(mod_root, key, entries)
	stamp, changed = now_stamp(), []
	for f, i, _ in drop:
		path = os.path.join(mod_root, f)
		backup(mod_root, f, stamp)
		lines, bom = read_lines(path)
		end = "\r\n" if lines[i].endswith("\r\n") else "\n" if lines[i].endswith("\n") else ""
		lines[i] = f" # {lines[i].rstrip()}  # (the same as in {keep}: Error Log Master){end}"
		write_lines(path, lines, bom)
		changed.append(f)
	return changed


# ---------- 🔧 duplicate ideas ----------
def idea_names(rows):
	return list(dict.fromkeys(m.group(1) for r in rows for m in [re.search(r"Duplicate idea\. (\S+) is a duplicate", r["msg"])] if m))


def find_defs(mod_root, key, folder="common/ideas"):
	"""Every definition of key (key = { ... }) in the folder's .txt files: [{file, start, end (0-based lines), text}]."""
	out = []
	rx = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*\{")
	base = os.path.join(mod_root, folder)
	for root, _, names in os.walk(base):
		for n in sorted(names):
			if not n.endswith(".txt"):
				continue
			path = os.path.join(root, n)
			try:
				lines, _ = read_lines(path)
			except OSError:
				continue
			for i, l in enumerate(lines):
				if not rx.match(l):
					continue
				depth, j = 0, i
				while j < len(lines):
					code = lines[j].split("#")[0]
					depth += code.count("{") - code.count("}")
					if depth <= 0:
						break
					j += 1
				out.append(dict(file=os.path.relpath(path, mod_root).replace("\\", "/"), start=i, end=min(j, len(lines) - 1),
								text="".join(lines[i:j + 1])))
	return out


def same_defs(defs):
	norm = {re.sub(r"\s+|#.*", "", d["text"]) for d in defs}
	return len(norm) == 1


def remove_defs(mod_root, drop, keep):
	"""The dropped definitions commented out, a note above each (bottom-up per file: the line numbers still fit)."""
	stamp, changed = now_stamp(), []
	for f in dict.fromkeys(d["file"] for d in drop):
		path = os.path.join(mod_root, f)
		backup(mod_root, f, stamp)
		lines, bom = read_lines(path)
		for d in sorted((d for d in drop if d["file"] == f), key=lambda d: -d["start"]):
			nl = "\r\n" if lines[d["start"]].endswith("\r\n") else "\n"
			indent = re.match(r"\s*", lines[d["start"]]).group()
			for i in range(d["start"], d["end"] + 1):
				lines[i] = "#" + lines[i]
			lines.insert(d["start"], f"{indent}# Duplicate removed by Error Log Master on {datetime.date.today()} "
										f"(the game uses the one in {keep['file']}:{keep['start'] + 1}):{nl}")
		write_lines(path, lines, bom)
		changed.append(f)
	return changed


# ---------- 🔧 one line: // comments, commas, backticks ----------
def fix_lines(mod_root, targets, what):
	"""In each (file, line): // -> #, commas out (outside "quotes"), or ` out - on that line or the nearest within 2 that
	has it. Returns the files changed."""
	need = {"comment": "//", "comma": ",", "backtick": "`"}[what]
	stamp, changed = now_stamp(), []
	by_file = {}
	for f, line in targets:
		if f and line:
			by_file.setdefault(f, set()).add(line)
	for f, lines_no in by_file.items():
		path = os.path.join(mod_root, f)
		try:
			lines, bom = read_lines(path)
		except OSError:
			continue
		done = False
		for n in sorted(lines_no):
			for i in sorted(range(max(0, n - 3), min(len(lines), n + 2)), key=lambda i: abs(i - (n - 1))):
				code, q, out = lines[i], False, []
				if need not in code:
					continue
				j = 0
				while j < len(code):
					ch = code[j]
					if ch == '"':
						q = not q
					if not q and ch == "#" and what != "comment":
						out.append(code[j:])  # (a real comment: left alone)
						break
					if not q and code.startswith(need, j):
						out.append("#" if what == "comment" else " " if what == "comma" else "")
						j += len(need)
						if what == "comment":
							out.append(code[j:])
							break
						continue
					out.append(ch)
					j += 1
				new = "".join(out)
				if new != code:
					if not done:
						backup(mod_root, f, stamp)
						done = True
					lines[i] = new
					break
		if done:
			write_lines(path, lines, bom)
			changed.append(f)
	return changed


# ---------- 🔧 24-bit flags -> 32-bit ----------
def flag_files(mod_root, rows):
	"""The flag .tga files 24-bit warnings name (Error loading flag for country NRM : Ideology ni : Path gfx/flags/medium/)."""
	out = []
	for r in rows:
		m = re.search(r"country (\w+) : Ideology (\w*) : Path ([\w/]+)", r["msg"])
		if m:
			tag, ideo, folder = m.groups()
			name = f"{tag}_{ideo}.tga" if ideo else f"{tag}.tga"
			for cand in (folder.rstrip("/") + "/" + name, folder.rstrip("/") + "/" + tag + ".tga"):
				if os.path.isfile(os.path.join(mod_root, cand)) and cand not in out:
					out.append(cand)
					break
	return out


def fix_flag32(mod_root, rels):
	"""Each 24-bit TGA re-saved as 32-bit (fully opaque: it looks the same). Returns the files changed."""
	from PIL import Image
	stamp, changed = now_stamp(), []
	for f in rels:
		path = os.path.join(mod_root, f)
		try:
			im = Image.open(path)
			if im.mode == "RGBA":
				continue
			im = im.convert("RGBA")
		except OSError:
			continue
		backup(mod_root, f, stamp)
		im.save(path, "TGA")
		changed.append(f)
	return changed


# ---------- 🔧 braces: where the missing } belongs ----------
def indent_of(line):
	return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())


def brace_plan(mod_root, rel_path, line):
	"""("insert", line index, the } line) for a never-closed { (where its block's indentation says it ends: the first later
	line indented no deeper than it), ("remove", line index, "") for a } too many alone on its line, or None."""
	try:
		lines, _ = read_lines(os.path.join(mod_root, rel_path))
	except OSError:
		return None
	i = line - 1
	if i >= len(lines):
		return None
	if lines[i].split("#")[0].strip() == "}":
		return ("remove", i, "")
	if "{" not in lines[i].split("#")[0]:
		return None
	base = indent_of(lines[i])
	pad = re.match(r"[ \t]*", lines[i]).group()
	nl = "\r\n" if lines[i].endswith("\r\n") else "\n"
	last = i
	for j in range(i + 1, len(lines)):
		code = lines[j].split("#")[0]
		if not code.strip():
			continue
		if indent_of(lines[j]) <= base and not code.strip().startswith("}"):
			return ("insert", last + 1, pad + "}" + nl)
		last = j
	return ("insert", len(lines), pad + "}" + nl)


def fix_brace(mod_root, rel_path, line):
	"""The brace_plan carried out (backup first). True when it changed."""
	plan = brace_plan(mod_root, rel_path, line)
	if not plan:
		return False
	what, i, text = plan
	path = os.path.join(mod_root, rel_path)
	backup(mod_root, rel_path, now_stamp())
	lines, bom = read_lines(path)
	if what == "remove":
		end = "\r\n" if lines[i].endswith("\r\n") else "\n"
		lines[i] = f"#{lines[i].rstrip()}  # (a }} too many: Error Log Master){end}"
	else:
		if i > 0 and not lines[i - 1].endswith(("\n", "\r")):
			lines[i - 1] += text[-2:] if text.endswith("\r\n") else "\n"
		lines.insert(i, text.rstrip("\r\n") + "  # (added by Error Log Master: this block was never closed)" + ("\r\n" if text.endswith("\r\n") else "\n"))
	write_lines(path, lines, bom)
	return True


# ---------- 🔧 did you mean / base-game leftovers ----------
def fix_rename(mod_root, rel_path, line, old, new):
	"""old -> new on that line (whole names only). True when it changed."""
	path = os.path.join(mod_root, rel_path)
	lines, bom = read_lines(path)
	i = line - 1
	if i >= len(lines):
		return False
	code, _, comment = lines[i].partition("#")
	new_code = re.sub(r"(?<![\w.\-])" + re.escape(old) + r"(?![\w\-])", new, code)
	if new_code == code:
		return False
	backup(mod_root, rel_path, now_stamp())
	lines[i] = new_code + ("#" + comment if comment else "")
	write_lines(path, lines, bom)
	return True


SINGLE = re.compile(r"^\s*[\w.\-@:]+\s*=\s*[\w.\-@:\"]+\s*(?:#.*)?$")


def can_comment_line(mod_root, rel_path, line):
	"""The line is one plain statement (has_idea = X): commenting it out can't break the block around it."""
	try:
		lines, _ = read_lines(os.path.join(mod_root, rel_path))
	except OSError:
		return False
	return 0 < line <= len(lines) and bool(SINGLE.match(lines[line - 1].rstrip("\r\n")))


def fix_comment_line(mod_root, rel_path, line, why):
	path = os.path.join(mod_root, rel_path)
	if not can_comment_line(mod_root, rel_path, line):
		return False
	backup(mod_root, rel_path, now_stamp())
	lines, bom = read_lines(path)
	i = line - 1
	end = "\r\n" if lines[i].endswith("\r\n") else "\n" if lines[i].endswith("\n") else ""
	lines[i] = f"#{lines[i].rstrip()}  # ({why}: Error Log Master){end}"
	write_lines(path, lines, bom)
	return True


# ---------- 🔧 a capital the country doesn't own ----------
RX_CAPITAL = re.compile(r"Attempting to set capital state #(\d+) for (.+?), they dont own it")
_CAPITAL_CACHE = {}


def _cached(key, make, ttl=60):
	hit = _CAPITAL_CACHE.get(key)
	if hit and time.time() - hit[0] < ttl:
		return hit[1]
	value = make()
	_CAPITAL_CACHE[key] = (time.time(), value)
	return value


def country_names(mod_root, game_root=None):
	"""{country name: {tags}} from the localisation (TAG, TAG_DEF, TAG_<ideology>, TAG_<ideology>_DEF - not _ADJ)."""
	def make():
		out = defaultdict(set)
		rx = re.compile(r'^\s*([A-Z][A-Z0-9]{2})(?:_[a-z_]+?)?(?:_DEF)?:\d*\s*"(.*)"')
		roots = [os.path.join(mod_root, "localisation")] + ([os.path.join(game_root, "localisation")] if game_root else [])
		for loc in roots:
			for d, _, fs in os.walk(loc):
				for f in fs:
					if not f.endswith(".yml") or "english" not in (d + f).lower():
						continue
					try:
						for line in open(os.path.join(d, f), encoding="utf-8-sig", errors="replace"):
							m = rx.match(line)
							if m and not m.group(0).split(":")[0].endswith("_ADJ"):
								out[m.group(2).strip()].add(m.group(1))
					except OSError:
						pass
		return out
	return _cached(("names", mod_root, game_root), make, ttl=600)


def _grep(mod_root, pattern, where):
	"""{file: [(line, text)]} from git grep (one quick call instead of opening thousands of files), or None."""
	import subprocess
	try:
		r = subprocess.run(["git", "-C", mod_root, "grep", "-n", "-I", "-E", "-e", pattern, "--", where], capture_output=True,
						   text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
	except (OSError, subprocess.SubprocessError):
		return None
	if r.returncode not in (0, 1):
		return None
	out = defaultdict(list)
	for l in r.stdout.splitlines():
		f, n, text = l.split(":", 2)
		out[f].append((int(n), text))
	return out


def country_states(mod_root):
	"""{TAG: [(state id, name, file, victory points)]} - the (first) owner = in each history/states file."""
	def quick():
		owners = _grep(mod_root, r"^[^#]*\bowner\s*=\s*[A-Z][A-Z0-9]{2}\b", "history/states")
		if owners is None:
			return None
		vps = _grep(mod_root, r"^[^#]*victory_points\s*=", "history/states") or {}
		ids = _grep(mod_root, r"^[^#]*\bid\s*=\s*[0-9]+", "history/states") or {}
		out = defaultdict(list)
		for f, hits in owners.items():
			owner = re.search(r"\bowner\s*=\s*([A-Z][A-Z0-9]{2})", hits[0][1]).group(1)
			sid = re.search(r"\bid\s*=\s*(\d+)", ids[f][0][1]) if f in ids else re.match(r"(\d+)", os.path.basename(f))
			if not sid:
				continue
			vp = sum(float(v) for _, t in vps.get(f, []) for v in re.findall(r"victory_points\s*=\s*\{\s*\d+\s+([\d.]+)", t))
			name = re.sub(r"^\d+\s*-\s*", "", os.path.splitext(os.path.basename(f))[0]).strip()
			out[owner].append((int(sid.group(1)), name, f, vp))
		return out

	def make():
		got = quick()
		if got is not None:
			return got
		out = defaultdict(list)
		folder = os.path.join(mod_root, "history", "states")
		for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
			try:
				text = strip_comments(open(os.path.join(folder, f), encoding="utf-8-sig", errors="replace").read())
			except OSError:
				continue
			sid, owner = re.search(r"\bid\s*=\s*(\d+)", text), re.search(r"\bowner\s*=\s*([A-Z][A-Z0-9]{2})\b", text)
			if not sid or not owner:
				continue
			vps = sum(float(v) for v in re.findall(r"victory_points\s*=\s*\{\s*\d+\s+([\d.]+)", text))
			name = re.sub(r"^\d+\s*-\s*", "", os.path.splitext(f)[0]).strip()
			out[owner.group(1)].append((int(sid.group(1)), name, "history/states/" + f, vps))
		return out
	return _cached(("states", mod_root), make, ttl=300)


def strip_comments(text):
	return re.sub(r"#[^\n]*", "", text)


def country_history(mod_root, tag):
	folder = os.path.join(mod_root, "history", "countries")
	f = next((f for f in sorted(os.listdir(folder)) if f.upper().startswith(tag + " ") or f.upper().startswith(tag + "-")
			  or os.path.splitext(f)[0].upper() == tag), None) if os.path.isdir(folder) else None
	return "history/countries/" + f if f else None


def capital_of(mod_root, tag):
	"""(history file, line (1-based), capital state id, the line's comment) or Nones."""
	rel = country_history(mod_root, tag)
	if not rel:
		return None, None, None, ""
	lines, _ = read_lines(os.path.join(mod_root, rel))
	for i, line in enumerate(lines):
		m = re.match(r"\s*capital\s*=\s*(\d+)\s*(#.*)?$", line.rstrip("\r\n"))
		if m:
			return rel, i + 1, int(m.group(1)), (m.group(2) or "").lstrip("#").strip()
	return rel, None, None, ""


def capital_problem(mod_root, msg, game_root=None):
	"""What a capital error is about: {state, name, tags, tag, history, line, capital, comment, owned, owner, suggest}."""
	m = RX_CAPITAL.search(msg)
	if not m:
		return None
	sid, name = int(m.group(1)), m.group(2).strip()
	tags = sorted(country_names(mod_root, game_root).get(name, ()))
	states = country_states(mod_root)
	info = None
	for tag in tags:  # (the tag whose history names this state first)
		rel, line, cap, comment = capital_of(mod_root, tag)
		cand = dict(tag=tag, history=rel, line=line, capital=cap, comment=comment)
		if cap == sid or info is None:
			info = cand
		if cap == sid:
			break
	info = info or dict(tag=None, history=None, line=None, capital=None, comment="")
	owned = sorted(states.get(info["tag"], []), key=lambda s: (-s[3], s[0])) if info["tag"] else []
	owner = next((t for t, ss in states.items() for s in ss if s[0] == sid), None)
	want = info["comment"].lower()
	suggest = next((s for s in owned if want and (s[1].lower() in want or want in s[1].lower())), owned[0] if owned else None)
	return dict(info, state=sid, name=name, tags=tags, owned=owned, owner=owner, suggest=suggest,
				state_name=next((s[1] for ss in states.values() for s in ss if s[0] == sid), None))


def fix_capital(mod_root, rel_path, line, sid, name):
	"""capital = <sid> #<name> on that line of the country's history file."""
	path = os.path.join(mod_root, rel_path)
	lines, bom = read_lines(path)
	i = line - 1
	if not re.match(r"\s*capital\s*=\s*\d+", lines[i]):
		return False
	backup(mod_root, rel_path, now_stamp())
	end = "\r\n" if lines[i].endswith("\r\n") else "\n" if lines[i].endswith("\n") else ""
	indent = re.match(r"\s*", lines[i]).group(0)
	lines[i] = f"{indent}capital = {sid} #{name}{end}"
	write_lines(path, lines, bom)
	_CAPITAL_CACHE.clear()
	return True


# ---------- 🔧 BOM ----------
def fix_bom(mod_root, rel_path):
	path = os.path.join(mod_root, rel_path)
	lines, bom = read_lines(path)
	if bom:
		return False
	backup(mod_root, rel_path, now_stamp())
	write_lines(path, lines, True)
	return True


# ---------- spelling ----------
MISSPELLINGS = {
	"recieve": "receive", "recieved": "received", "acheive": "achieve", "acheived": "achieved", "beleive": "believe",
	"belive": "believe", "wich": "which", "teh": "the", "untill": "until", "occured": "occurred", "occuring": "occurring",
	"occurence": "occurrence", "seperate": "separate", "seperatist": "separatist", "seperatists": "separatists",
	"definately": "definitely", "goverment": "government", "goverments": "governments", "governement": "government",
	"enviroment": "environment", "independance": "independence", "independant": "independent", "existance": "existence",
	"foriegn": "foreign", "soverign": "sovereign", "soveriegn": "sovereign", "sovereignity": "sovereignty",
	"millitary": "military", "agression": "aggression", "agressive": "aggressive", "accross": "across", "adress": "address",
	"arguement": "argument", "begining": "beginning", "beggining": "beginning", "comittee": "committee", "commitee": "committee",
	"comunist": "communist", "comunism": "communism", "communsim": "communism", "facist": "fascist", "facism": "fascism",
	"fascim": "fascism", "parliment": "parliament", "parlament": "parliament", "polical": "political", "politcal": "political",
	"publically": "publicly", "recomend": "recommend", "reccomend": "recommend", "refered": "referred", "relevent": "relevant",
	"religous": "religious", "resistence": "resistance", "succesful": "successful", "successfull": "successful",
	"sucessful": "successful", "sucess": "success", "suprise": "surprise", "tommorow": "tomorrow", "truely": "truly",
	"wierd": "weird", "neccessary": "necessary", "neccesary": "necessary", "necesary": "necessary", "ocurred": "occurred",
	"posession": "possession", "possesion": "possession", "priviledge": "privilege", "rebelion": "rebellion",
	"revolutionairy": "revolutionary", "revoltion": "revolution", "thier": "their", "alledged": "alleged",
	"apparant": "apparent", "appearence": "appearance", "assasination": "assassination", "assasinated": "assassinated",
	"assasin": "assassin", "attrocities": "atrocities", "beaurocracy": "bureaucracy", "buisness": "business",
	"carribean": "Caribbean", "cemetary": "cemetery", "collegue": "colleague", "concious": "conscious", "dissapear": "disappear",
	"dissapointed": "disappointed", "embarass": "embarrass", "excercise": "exercise", "familar": "familiar", "finaly": "finally",
	"fourty": "forty", "gaurd": "guard", "harrass": "harass", "hierachy": "hierarchy", "immediatly": "immediately",
	"interupt": "interrupt", "knowlege": "knowledge", "liason": "liaison", "maintainance": "maintenance",
	"noticable": "noticeable", "occassion": "occasion", "oppurtunity": "opportunity", "persue": "pursue", "persuit": "pursuit",
	"pharoah": "pharaoh", "prefered": "preferred", "propoganda": "propaganda", "responsability": "responsibility",
	"rythm": "rhythm", "sargent": "sergeant", "seige": "siege", "strenght": "strength", "supress": "suppress",
	"tatics": "tactics", "teritory": "territory", "tradgedy": "tragedy", "transfered": "transferred", "vehical": "vehicle",
	"villian": "villain", "withdrawl": "withdrawal", "writting": "writing", "goverened": "governed", "economicly": "economically",
	"threshhold": "threshold", "temperment": "temperament", "whereever": "wherever", "agressors": "aggressors",
}
# American -> British (the other way round for American English). -ize / -or words get their usual endings.
_IZE = ("organiz", "realiz", "recogniz", "mobiliz", "demobiliz", "nationaliz", "industrializ", "moderniz", "centraliz",
		"decentraliz", "civiliz", "colonializ", "colonis", "stabiliz", "destabiliz", "legaliz", "neutraliz", "normaliz",
		"prioritiz", "specializ", "standardiz", "subsidiz", "sympathiz", "utiliz", "westerniz", "apologiz", "criticiz",
		"emphasiz", "jeopardiz", "memoriz", "militariz", "demilitariz", "minimiz", "maximiz", "mesmeriz", "monopoliz",
		"polariz", "privatiz", "radicaliz", "revolutioniz", "authoriz", "characteriz", "harmoniz", "symboliz", "terroriz")
_OR = ("color", "colour", "favor", "honor", "labor", "armor", "harbor", "neighbor", "rumor", "vigor", "valor", "behavior",
	   "endeavor", "flavor", "glamor", "humor", "odor", "savior", "splendor", "tumor", "vapor", "parlor", "clamor", "rancor")
VARIANTS = {}
for stem in _IZE:
	if stem.endswith("s"):
		continue
	for end in ("e", "es", "ed", "ing", "ation", "ations", "er", "ers"):
		VARIANTS[stem + end] = stem[:-1] + "s" + end
for w in _OR:
	if w.endswith("our"):
		continue
	for end in ("", "s", "ed", "ing", "ful", "able", "ite", "ites", "less"):
		VARIANTS[w + end] = w[:-2] + "our" + end
VARIANTS.update({"center": "centre", "centers": "centres", "centered": "centred", "theater": "theatre", "theaters": "theatres",
				 "defense": "defence", "defenses": "defences", "offense": "offence", "offenses": "offences", "gray": "grey",
				 "catalog": "catalogue", "maneuver": "manoeuvre", "maneuvers": "manoeuvres", "maneuvering": "manoeuvring",
				 "aluminum": "aluminium", "jewelry": "jewellery", "plow": "plough", "traveled": "travelled", "traveling": "travelling",
				 "traveler": "traveller", "travelers": "travellers", "canceled": "cancelled", "canceling": "cancelling",
				 "modeling": "modelling", "labeled": "labelled", "fueled": "fuelled", "fueling": "fuelling", "signaling": "signalling",
				 "rivaled": "rivalled", "counselor": "counsellor", "counselors": "counsellors", "enrollment": "enrolment",
				 "fulfillment": "fulfilment", "skillful": "skilful", "willful": "wilful", "analyze": "analyse", "analyzed": "analysed",
				 "paralyze": "paralyse", "paralyzed": "paralysed", "program": None, "pajamas": "pyjamas", "mustache": "moustache",
				 "sulfur": "sulphur", "meter": None, "liter": "litre", "liters": "litres", "kilometer": "kilometre",
				 "kilometers": "kilometres", "fiber": "fibre", "caliber": "calibre", "somber": "sombre", "luster": "lustre",
				 "specter": "spectre", "saber": "sabre", "dialog": None, "check": None, "tire": None, "ax": "axe"})
VARIANTS = {a: b for a, b in VARIANTS.items() if b}
SPELLINGS = ("British", "American", "Typos only")  # (the team's choice: todo_tasks.json loc_spelling)
WORD = re.compile(r"[A-Za-z]+")
SKIP = re.compile(r"\$[^$]*\$|\[[^\]]*\]|§.|£\S+")  # ($variables$, [scripted loc], §colour codes, £icons: not words)


def spelling(mod_root, variant="British"):
	"""Misspellings in the mod's English localisation text: [{check, file, line, message, key, word, fix}]. variant:
	British flags American spellings (color -> colour), American the other way round, Typos only neither."""
	extra = VARIANTS if variant == "British" else {b: a for a, b in VARIANTS.items()} if variant == "American" else {}
	out = []
	folder = os.path.join(mod_root, "localisation")
	for base, _, names in os.walk(folder):
		for n in names:
			if not (n.endswith(".yml") and "english" in n):
				continue
			path = os.path.join(base, n)
			rel = os.path.relpath(path, mod_root).replace("\\", "/")
			try:
				st = os.stat(path)
			except OSError:
				continue
			stamp_ = (st.st_mtime_ns, st.st_size, variant)
			hit = _SPELL_CACHE.get(path)
			if hit and hit[0] == stamp_:  # (unchanged since the last look: its result again - opening is quick)
				out += hit[1]
				continue
			try:
				lines, _ = read_lines(path)
			except OSError:
				continue
			start = len(out)
			for i, l in enumerate(lines):
				m = re.match(r'^\s*([\w.\-]+):\d*\s*"(.*)"', l)
				if not m:
					continue
				text = SKIP.sub(" ", m.group(2))
				for w in WORD.findall(text):
					fix = MISSPELLINGS.get(w.lower())
					style = None
					if not fix and w.lower() in extra:
						fix, style = extra[w.lower()], variant
					if fix:
						good = fix[0].upper() + fix[1:] if w[0].isupper() else fix
						what = f"{style} spelling" if style else "Spelling"
						out.append(dict(check="Spelling", file=rel, line=i + 1, word=w, fix=good, style=style,
										message=f"{what}: \"{w}\" → \"{good}\" ({m.group(1)})", key=f"spell:{rel}:{m.group(1)}:{w}"))
			_SPELL_CACHE[path] = (stamp_, out[start:])
	return out


_SPELL_CACHE = {}


def fix_spelling(mod_root, p):
	"""The word corrected on its line (in the text only). True when it changed."""
	path = os.path.join(mod_root, p["file"])
	lines, bom = read_lines(path)
	i = p["line"] - 1
	if i >= len(lines):
		return False
	m = re.match(r'^(\s*[\w.\-]+:\d*\s*")(.*)(".*)$', lines[i], re.S)
	if not m:
		return False
	new = re.sub(r"\b" + re.escape(p["word"]) + r"\b", p["fix"], m.group(2))
	if new == m.group(2):
		return False
	backup(mod_root, p["file"], now_stamp())
	lines[i] = m.group(1) + new + m.group(3)
	write_lines(path, lines, bom)
	return True
