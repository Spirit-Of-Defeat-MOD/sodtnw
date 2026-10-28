"""Program changes, newest first. Add a new stable ID for each future update.

Seen IDs are local preferences per developer; viewing older notes never hides future entries.
"""
import tkinter as tk
from tkinter import ttk

import ui
import icons

# Stable colors identify the master; the glyphs come from the active theme's task sheet.
MASTER_STYLES = {
    "To Do Master": ("#A52A35", "clipboard"),
    "Music Master": ("#7039A5", "music"),
    "Culture Master": ("#236B3A", "globe"),
    "Country Master": ("#000000", "flag"),
    "Organisation Master": ("#384453", "gear"),
}


def entry_masters(entry):
    out = []
    for name in entry["tool"].split("/"):
        name = "To Do Master" if name.strip() in ("Ideas", "Dev VCs") else name.strip()
        name = name if name in MASTER_STYLES else "Organisation Master"
        if name not in out:
            out.append(name)
    return out


CHANGES = (
    dict(id="2026-10-27-om-companion", date="27 October 2026", tool="Organisation Master",
         title="🟢 Always shared",
         points=("Opening Culture, Country or Model Master starts Organisation Master minimised if it isn't running, so 🟢 Online, Developer Activity and 💬 Requests from them reach the team straight away.",
                 "Settings > 🟢 Start in the background with the other masters turns it off.")),
    dict(id="2026-10-27-master-requests", date="27 October 2026", tool="Organisation Master",
         title="💬 Requests from every master",
         points=("Culture Master, Country Master and Model Master have 💬 Request in their menu bar: a bug, an idea or a change, in a few words and some details (with what you're on now added if you like) and a priority.",
                 "It goes straight into the To Do under Tools › Requests › that master, live (or the next time Organisation Master opens). The Requests and master tasks are made the first time.")),
    dict(id="2026-10-27-guides-every-master", date="27 October 2026", tool="Organisation Master",
         title="📖 Guides in every master",
         points=("Culture Master, Country Master and Model Master now have their own 📖 Guides (top left), pointing at the real thing like Organisation Master's: a Getting started tour, then one per part - religions, migratory peoples and languages; the country's pages, collapses and sub-ideologies; colours and camo, and stickers.",
                 "Each master runs its Getting started tour the first time it opens on your PC.",
                 "A new 🐞 Error Log Master guide in Organisation Master's Guides walks through the logs, the checks, the tabs and what to do with an error.")),
    dict(id="2026-10-27-model-master-compact-browser", date="27 October 2026", tool="Model Master",
         title="A compact Model Master browser",
         points=("One sidebar replaces the two long country/model columns. Change… opens a searchable country/culture chooser that folds away after selection.",
                 "Models are grouped by type with expand/collapse controls. Names get the full row; source/type and the exact entity name appear below the list. Search also matches source and country names.",
                 "Normal, Desert and Snow versions share one model row, with Appearance toggles above the preview. Switching a version loads its actual model and editable textures.",
                 "Shared cultures now filters to shared graphical-culture models correctly.")),
    dict(id="2026-10-27-model-master-themed-tabs", date="27 October 2026", tool="Model Master",
         title="Readable Colours and Stickers tabs in every theme",
         points=("The editor tabs now use each theme's own surfaces, selection colours and accent border, and update immediately when switching themes.",
                 "Normal, selected, hovered and disabled tab labels have contrast-checked text colours; Classic keeps its native tab surface.")),
    dict(id="2026-10-27-model-master-studio-ui", date="27 October 2026", tool="Model Master",
         title="A clearer Model Master and new tactical stickers",
         points=("Resizable country/model browsers, a compact search and type filter, and scrolling colour/sticker editors keep controls reachable at smaller window sizes.",
                 "Colour areas have clearer original/new swatches and labelled strength controls. Sticker tiles show their names and can be searched or filtered by Stock, Team and Flags.",
                 "Eight generated transparent, tintable tactical emblems join the stock library: wolf, raven, bear, boar, panther, stag, winged wheel and an engineers' wreath.",
                 "The built executable reads shared area reviews, schemes and sticker assets beside the tool, rather than from its temporary extraction folder.")),
    dict(id="2026-10-27-model-master", date="27 October 2026", tool="Model Master",
         title="🪖 Model Master",
         points=("A new master: every unit model the game can show - the base game, every DLC and RR's own (about 3,400) - by country and type (Infantry, Tanks, Planes, Ships, Artillery, Vehicles, Weapons), in a 3D preview you can turn and zoom. Normal / Snow / Desert looks too.",
                 "🎨 Colour them Dawn of War style: each texture is split into its colour areas (uniform, helmet, skin, paint, tracks...) - pick a new colour for each, rename them, merge them, touch them up with a brush. Light, shade and wear stay.",
                 "Save the colours as a scheme (\"Polish khaki\", \"Red Army winter\") and put it on any other model.",
                 "🏳 Apply to a country writes the recoloured textures and that country's entities into the mod - one model, or all of a country's tanks / infantry... at once - so its units really look that way in game. Models > What's applied takes them out again.",
                 "🖌 Touch up uses Photoshop's controls, with a brush ring you can see: B brush, E eraser, G fill, X swap, Alt+click to pick an area, Alt+right-drag or [ ] for the size, Shift+click for a straight line, wheel to zoom, Space+drag to move, Ctrl+Z / Ctrl+Y.",
                 "🏷 Stickers: drag symbols, your own PNGs or a country's flag onto a model - move them on it, size (Ctrl+wheel), turn (Alt+wheel), fade and recolour them. They wrap over the model's surface like decals, are saved with schemes, and Apply puts them into the game.",
                 "▦ Camo patterns: paint an area in camouflage instead of one colour - 29 patterns in use up to the 1960s (Splittermuster, Telo mimetico, Frogskin, pea dot, Denison, Lizard, ERDL, Tigerstripe, DPM, Strichtarn, Hinterhalt, Caunter, dazzle...). Change their colours, size and turn, shuffle them, save your own. They're made on the model itself, so they run on across the texture's seams.",
                 "Every pattern has Brightness, Vibrancy and Contrast sliders, to change it on the fly.",
                 "🧱 Materials in the same window: steel, gunmetal, scratched / rusty / blackened / blued iron, bronze, brass, copper, gold, silver, wood (and dark, pale and rotting), leather (brown, black, worn), fur, sheepskin, canvas, wool, rubber, concrete, stone, bone...",
                 "🙂 Faces: 5 skin tones for each of 9 peoples, with a touch of colour in the cheeks; the window opens on them for a Skin area.",
                 "Right-click a colour area to jump to it on the model: it turns to face you, zoomed in and lit up.",
                 "Colour areas are now 🧩 Segments, with sub-segments: Uniform > Tunic and Trousers > Collar, Piping, Buttons, Insignia, Shoulder boards. 🔗 a sub-segment takes its segment's colour (Tunic and Trousers with the Uniform); ⛓ it keeps its own (the piping stays white on a red tunic). ⋯ splits them off by colour, adds new ones, moves them under another.",
                 "🏷 Stickers can go Under segments (a badge behind the webbing straps) or Only on them (just the buttons).",
                 "⇄ Link segments anywhere in the tree so they share one colour - Hands (under Tunic) and Face (under Helmet) - from ⋯ > Link with.")),
    dict(id="2026-10-27-unintentional-outcomes", date="27 October 2026", tool="Organisation Master",
         title="🤔 Potential Unintentional Outcomes",
         points=("A new tab in 🐞 Error Log Master (filled by ▶ Check the mod's files): script that gives no error but probably doesn't do what was meant.",
                 "Focus trees: focuses on the same spot, mutually exclusive written on one side only (both can be taken), focuses that do nothing or can never be taken.",
                 "Events that fire by themselves for every country, events that can repeat forever, options showing the same text. A country's decision (GER_...) every country can see.",
                 "every_country / every_state doing big things (war, annexing, states, ideas) with no limit, and empty limit = { }.",
                 "Placeholder text left in (TODO, placeholder, WIP...) and long texts copy-pasted word for word onto different things - the base game's own text is left out.",
                 "Each has 💡 why it looks unintended; 🙈 Accept → Intentional marks the ones that are meant, for everyone.")),
    dict(id="2026-10-25-selected-error-alert-animations", date="25 October 2026", tool="Organisation Master",
         title="An incoming alert in every theme’s own style",
         points=("All thirteen chosen scenes now have polished pixel animation sheets with supporting motion and particles; Soviet Terminal keeps its 1980s wireframes, refined as flat WarGames-style terminal vectors: descending bomb, impact arcs and a clean outlined mushroom cloud.",
                 "The duck patches a pipe, stars form a warning, the bugle raises a flag, the thermometer freezes, eyes emerge from a folder and a gear smoulders. The remaining themes reveal the sandwich report, spider web, snow globe bug, glitching sunset, blossom warning, spinning coin and stamped report.",
                 "Animations play once above the readable error message, then settle. Each has its own timed sound effects, respecting Sound feedback and volume without interrupting the Radio. Theme switches restart the right scene; closing the popup stops its animation and sound.")),
    dict(id="2026-10-25-error-log-alert-themes", date="25 October 2026", tool="Organisation Master",
         title="Themed error reports and incoming alerts",
         points=("Error Log Master and incoming alerts now follow the active theme, including tabs, code highlights, severity colours and live theme changes. The crowded filter controls have their own row.",
                 "Soviet Terminal alerts show a falling wireframe bomb, an impact ring and a growing wireframe mushroom cloud. The animation stays above the message and response controls.")),
    dict(id="2026-10-25-error-alerts", date="25 October 2026", tool="Organisation Master",
         title="🚨 Error alerts, capitals, and a tidier Error Log Master",
         points=("🚨 Alert a dev (Error Log Master): flash an error at a teammate - on their Organisation Master it pops up on top, flashing, until they answer ✋ I'm on it (it's claimed for them and opens at the error) or ⏳ Can't now (with why). You're told their answer. Settings > 🚨 Error alerts can pop up for me turns it off for you (yours then wait on the side-bar button).",
                 "\"Attempting to set capital state ... they dont own it\": it now says which country it is (from its name), shows its history file and the states it owns - and 🔧 sets the right capital (the one its comment names, else the most victory points).",
                 "\"Reloading Database: common/ideas\" is explained: not an error - the game reloads a folder when a file in it is saved while you play.",
                 "The error's details (bottom left) are tidier and in sections you can fold - click ▾ 💡 or ▾ 📜 The error lines to close them; it remembers.",
                 "~20 more errors explained (from another mod's playthrough log): the AI's invalid commands (merge_navies - harmless, 🟡), variables read in the wrong scope in texts, border-war checks, random_lists where nothing can happen, missing songs, resistance on states without it, events with no valid option, event targets never saved, leader roles, GUI elements the game expects... Errors with names in them (states) now group together.",
                 "📈 Trend works with few points: launch errors and the mod check each get their own panel and scale, runs spaced evenly, with the change since the run before.")),
    dict(id="2026-10-25-implemented-ideas", date="25 October 2026", tool="To Do Master",
         title="✅ Implemented Ideas",
         points=("💡 Ideas: once an approved idea's task is Completed, the idea moves to its own ✅ Implemented Ideas list - out of Approved and All, so the lists only show what's still to do.",)),
    dict(id="2026-10-25-error-log-master-2", date="25 October 2026", tool="Organisation Master",
         title="🐞 Error Log Master: severity, Fix all, claims and more",
         points=("Every error is 🔴 breaks things, 🟠 wrong in game or 🟡 cosmetic - worst first, and you can show only the 🔴 ones.",
                 "🔧 Fix all on a group fixes every one in it at once (all the misspellings, all the // comments...).",
                 "An unclosed { : it shows where it opens and where the } most likely goes (where the indentation steps back out) - 🔧 puts it there.",
                 "Did you mean...? A name used but never defined shows the closest real one - 🔧 renames it. Base-game leftovers (a copied game file still using something the mod took out) are marked, 🔧 comments the line out.",
                 "New checks: the map (provinces in no state or two, victory points outside their state, strategic regions, supply nodes, railways), Culture Master's data, and performance hints (nested every_ loops, on_daily, 24-bit flags).",
                 "👤 Only mine: just the errors in files you changed last - also in 📬 Since you were last here. ✋ Claim an error so nobody else picks it up.",
                 "➕ task: the row shows its task, and fixing the error completes the task by itself. 🙈 Accept asks why (intentional, base-game leftover, harmless, will fix later).",
                 "📈 Trend tab: how many errors there were run by run - and the Monthly Report has a 🐞 Errors line.",
                 "Reads game.log, setup.log and graphics.log too. And it watches the files you're editing: a mistake shows up as 🐞 on the side-bar button within 20 seconds, before you even launch the game.",
                 "Only RR's errors are shared with the team: after a launch of another mod (Pax...) its log is shown, but nothing from it goes in the live sync - Recently fixed, the trend, tasks and 🆕 stay RR's.")),
    dict(id="2026-10-25-error-log-master", date="25 October 2026", tool="Organisation Master",
         title="🐞 Error Log Master",
         points=("In the side bar under To Do Master: a pop-out that reads the game's error.log and text.log after a launch (by itself) and groups thousands of lines into a short list by kind - 🆕 marks what's new since the run before. Hide known noise for everyone with 🙈.",
                 "🔎 Not in the log: checks the mod's files for errors the game never reports (or only hits in play): unclosed { }, events that are fired but don't exist, missing GFX sprites, broken localisation files, duplicate loc keys, focuses and events with no text.",
                 "📄 opens the file at the line; ➕ makes a Bug task for whoever last changed that file.",
                 "Click an error to see all of it at the bottom, with 💡 what it means and how to fix it - and 🔧 Fix it for the easy ones: missing tokens, a duplicate loc key with the same text, a missing BOM, a misspelling (the file is backed up first).",
                 "A loc key in two files: 🔧 shows every copy with its text and lets you pick the one to use - without editing the game's files (the mod's text goes to replace/, which overrides the game's cleanly). Clashes with base-game files are highlighted 🎮; a DLC file (goe_, nsb_...) can be switched off with an empty file in one click.",
                 "Reads far more kinds of error (from another mod's log we were sent): every way the game names a file and line, messages over two lines, and 💡 explanations for ~30 common errors - effects in the wrong scope, misplaced keys, two limits in an if, removed doctrines and tech categories, missing 3D models...",
                 "The mod check finds much more (tried on all 28 installed mods to keep false alarms out): flags checked but never set, ideas / country tags / characters / focuses used but never defined, things defined twice, undeclared event namespaces, undefined decision categories, missing texture files.",
                 "If the last launch wasn't RR (you played Pax...), the game's logs are shown read only, saying which mod ran. More explanations for errors seen in Pax's log, and 🔧 for 24-bit flags (→ 32-bit).",
                 "🔧 now also fixes // comments (→ #), stray commas and stray backticks. 📂 Open a log reads any error.log someone sends (another mod's is read only).",
                 "Duplicate ideas: 🔧 shows every definition - keep one and the others are commented out. 📄 Open goes to the one you're looking at.",
                 "A fixed error leaves the list and goes in ✅ Recently fixed - fixed with 🔧, or already fixed in the files since the log was written - with who fixed it, when and where. ✓ Checked clears the list for you (the others still see it).",
                 "An error with several parts (several duplicate ideas, tokens or files): ◀ ▶ above the code - or the ← / → keys - step through them, and 🔧 fixes the one you're on, in whatever order you like.",
                 "Clicking an error now shows the code itself at the bottom right: the lines around it, with the line and the name highlighted - the file it names, where a token is used, each definition of a duplicate idea, each copy of a loc key.",
                 "Spelling: choose British or American English for the whole team (or typos only) - it flags the other one's spellings (colour / color...).",
                 "🌐 Localisation has its own tab: duplicate keys with both texts, broken loc files, missing text and a spell check. 🙈 Dismiss hides one for everyone. The \"N errors.\" total now sits with the token errors it counts.")),
    dict(id="2026-10-25-self-swap", date="25 October 2026", tool="To Do Master",
         title="🎭 Self swap: FaceApp a portrait with itself",
         points=("In ✨ Remini's window, 🎭 Self swap → puts the original portrait's face back onto your edited Remini version - the FaceApp step - with the face swap models VisoMaster uses. It runs on any PC's CPU (about 20 seconds).",
                 "It opens as the next step with its own overlay: strength, eraser / restore brush, Photoshop's keys. Then save it or use it in the mod.",
                 "The first time it asks to download its models (~430 MB); Settings > ✨ Remini can set it up too.",
                 "Right-click ✨ Remini's or 🎭 Self swap's picture (or Ctrl+C / Ctrl+V): copy the result, the top layer or the original to work on it in Photoshop etc., then 📥 paste it back on top - the strength slider and eraser work on what you pasted.")),
    dict(id="2026-10-25-type-to-find", date="25 October 2026", tool="All masters",
         title="Type to find in lists, and Photoshop's brush keys in ✨ Remini",
         points=("In any list (GFX, the To Do, Country Master's countries...): press a letter to jump to the first one starting with it - U for United Kingdom, U again for United States. Type a few letters quickly to narrow it down. (Thanks George!)",
                 "✨ Remini's Edit overlay: Alt + right-drag sizes the brush smoothly (left / right) and sets its level (up / down), like Photoshop. Also [ ] for size, E eraser, B brush, X swap, 1-0 for the level.")),
    dict(id="2026-10-25-remini-settings", date="25 October 2026", tool="Organisation Master / Country Master",
         title="✨ Remini set-up in Settings, and two new rework reasons",
         points=("Settings > ✨ Remini (GFPGAN): see if it's set up on your PC (Python, CPU or ⚡ GPU, model, size on disk), Set up / Repair, switch to an NVIDIA GPU (about 15× faster), or Uninstall.",
                 "Marking a picture for rework: icons can be \"Looks too AI\", portraits can be \"Needs a Remini\" (Country Master's Mark for rework has it too).",
                 "✨ Remini's ✏ Edit overlay: lay Remini's version over the original - a Strength slider, an 🧽 Eraser that rubs parts of it out at a % level (🖌 Restore paints it back), Ctrl+Z per stroke. Save or use the edited result, or 💾 save just the overlay layer.")),
    dict(id="2026-10-25-undo", date="25 October 2026", tool="To Do Master",
         title="↶ Undo that works with live sync, and in the swipers",
         points=("Ctrl+Z / ↶ Undo used to forget everything whenever the others' changes came in (every few seconds with live sync). Now it keeps your last 20 changes and takes back only yours, keeping theirs.",
                 "🖼 GFX has its own ↶ Undo, and undoing ✓ Reworked (or a rework mark) shows straight away - Country Master's list follows too.",
                 "Both swipers have ↶ Undo (or Backspace): the last card comes back and its \"looks fine\" / rework mark / skip / claimed task is taken back.")),
    dict(id="2026-10-25-remini", date="25 October 2026", tool="To Do Master",
         title="✨ Remini in 🖼 GFX",
         points=("Pick a portrait (or have it on the Review swiper's card) and press ✨ Remini: GFPGAN (TencentARC's face restoration) restores and upscales it on your PC, 2× or 4×.",
                 "See it next to the original or overlaid, then 💾 save it as a PNG or ⬇ use it in the mod (at the original's size; the original is backed up).",
                 "The first time it asks to set itself up: about 1 GB of downloads (PyTorch, GFPGAN and its models), ~2 GB on disk.")),
    dict(id="2026-10-25-online-now", date="25 October 2026", tool="Organisation Master",
         title="🟢 See what the others are up to",
         points=("Developer activity (leads): whoever has a tool open is lit up green, and 🟢 What they're up to says what they're doing - painting a culture in Culture Master, editing a country in Country Master, playing an RR game, reviewing pictures...",
                 "Settings > 🟢 Share what I'm doing: off and the others only see that you're online.")),
    dict(id="2026-10-25-faster-and-since", date="25 October 2026", tool="Organisation Master",
         title="Faster, plus 📬 Since you were last here",
         points=("Opens faster (the exe unpacks ~750 fewer files) and saves / syncs lighter: the activity log keeps one entry per burst of edits instead of one per keystroke-save (the shared file went from 6.3 to about 3 MB).",
                 "📬 Since you were last here: on opening, what happened while you were away - tasks given to you, your tasks the others changed, completed and new tasks, ideas, reworks, who's asking for a task. Settings turns it off or shows it again.",
                 "🙋 Leads clicking a dev who asked for a task get the best-fitting open tasks (their skills, what they want to learn, projects they know, priority, age) and can give one in a click.")),
    dict(id="2026-10-25-gfx-compare", date="25 October 2026", tool="To Do Master",
         title="🔀 Before / after, and a shared Review swiper",
         points=("🖼 GFX > 🔀 Before / after: a picture as it was when marked for rework next to how it is now, or ⧉ overlaid (Space / click flips, a slider blends). Reworked ones stay in the list to compare.",
                 "🔎 Review swiper: \"looks fine\" is shared now - the card says who it already looked fine to. A 🔎 Today counter, and two new badges: Fresh Eyes (25 reviews) and Eagle Eye (100).")),
    dict(id="2026-10-25-ask-for-a-task", date="25 October 2026", tool="To Do Master",
         title="🙋 Ask for a task",
         points=("Out of work? Dev mode > 🙋 Ask for a task (under the Dev list). You light up for the leads (and they get a ping) until you're given a task; then it goes away by itself.",
                 "Press it again to take it back.")),
    dict(id="2026-10-25-achievement-tab-themes", date="25 October 2026", tool="Organisation Master",
         title="Achievement tabs match your theme too",
         points=("Badges and Developers now share the themed tab styling used in RR Games, including selected and hover colours. Open achievement pages update when you change themes.",)),
    dict(id="2026-10-25-gfx-review-swiper", date="25 October 2026", tool="To Do Master",
         title="🔎 Review swiper in 🖼 GFX",
         points=("Next to 🃏 Swipe for a task: go through the pictures the mod already has (portraits, flags, culture and religion icons, ideologies, focus and idea icons), one big card at a time.",
                 "→ Looks fine (you won't see it again), ← Needs review: pick the level (Needs Touchup / Needs Severe Recorrection / Something about it) and say what's wrong; it goes into 🔁 Needs Rework for everyone. ↓ Not sure: it comes round again later.",
                 "Pictures already in 🔁 Needs Rework aren't dealt. Small icons are shown bigger, pixel-sharp, so they're easy to judge.")),
    dict(id="2026-10-25-games-tab-themes", date="25 October 2026", tool="Organisation Master",
         title="RR Games tabs match your theme",
         points=("Play, Leaderboards and Round results now use the active theme’s colours, including their selected and hover states. Switching themes updates them immediately.",)),
    dict(id="2026-10-25-mechanics-bolt-and-effort", date="25 October 2026", tool="To Do Master",
         title="The bolt finally goes in",
         points=("Mechanics now shows the bolt progressively tightening into its base and staying fully seated while the duck wipes his brow.",
                 "Strained duck grunts and ratchet clicks accompany the effort, with a finishing clink. Technology adds pickup, curious inspection, charge-up, soot-puff and subtle blink sounds around its zap. Shared sound settings apply.")),
    dict(id="2026-10-25-celebration-tester", date="25 October 2026", tool="To Do Master",
         title="Try a celebration without completing anything",
         points=("Settings > Celebration tester previews Culture Map, Mechanics and Technology immediately. These previews stay on your PC and do not publish a milestone completion.",
                 "Ctrl+K also finds each tester by name.")),
    dict(id="2026-10-25-ai-tasks", date="25 October 2026", tool="To Do Master",
         title="Claude and ChatGPT add To Dos straight into the To Do",
         points=("The AIs now add parked work as To Do tasks (set by Claude / Chat Jipity) instead of a text file; they turn up by themselves within a few seconds, no restart.",
                 "Everything from Templates/AI_Notes/To_Do.txt moved in: RR-0688 to RR-0712 (culture bugs under RR-0698, dual leader checks under RR-0683).")),
    dict(id="2026-10-25-technology-duck-celebration", date="25 October 2026", tool="To Do Master",
         title="Technology: duck and cover",
         points=("The Trotsky duck picks up a raygun backwards, peers down the wrong end and gets a harmless cartoon zap. He stays covered in soot and keeps blinking while the celebration runs.",
                 "Choose Technology duck in the milestone animation selector, or use Automatic for Technology/Tech milestone names. Preview remains local and never completes the milestone.")),
    dict(id="2026-10-25-mechanics-duck-celebration", date="25 October 2026", tool="To Do Master",
         title="A milestone worth wrenching over",
         points=("The Trotsky duck celebrates Mechanics by straining to tighten a bolt, finishing the job and wiping his brow. Confetti, music and special thanks follow the final turn.",
                 "The milestone completion dialog now lets you choose the animation explicitly, or use Automatic for Culture Map and Mechanics milestones.")),
    dict(id="2026-10-25-shared-milestone-celebrations", date="25 October 2026", tool="To Do Master",
         title="Celebrate milestones together",
         points=("Right-click a milestone to complete it, select special thanks and preview its celebration. Each developer receives the announcement once through Live Sync, including on their next launch after being offline.",
                 "Culture Map Completion celebrates with the map-holding Trotsky duck changing six cultural hats, confetti, animated thanks and Kool & the Gang’s Celebration. Individual task statuses stay as they are.")),
    dict(id="2026-10-25-country-intentional-selection", date="25 October 2026", tool="Country Master",
         title="Safer character editing and cleaner navigation",
         points=("Scrolling over leader ideology or dual-leader choices no longer changes them. Type to autocomplete or open the dropdown to choose explicitly.",
                 "Country pages and editor sections use full-width selectors with no leftover native tab strips, including Classic. Recruited at game start sits under traits in a compact character form without a scrollbar.")),
    dict(id="2026-10-25-country-character-panel", date="25 October 2026", tool="Country Master",
         title="Room to browse and edit characters",
         points=("A full-width Country page selector replaces the squeezed tab strip. Character role filters fit the panel in every theme.",
                 "The character list has horizontal and vertical scrolling, with a draggable divider above the editor. Character details, dual leaders and script editing have their own tabs, so the map can stay visible.")),
    dict(id="2026-10-24-cm-state-order", date="24 October 2026", tool="Culture Master",
         title="Reorder a state's cultures and religions",
         points=("Drag an entry up or down the state panel list to change the order its subcultures / religions are written in, no removing and re-adding.",
                 "Only entries of the same strength can swap places: a weaker one can't go above a stronger one. Dragging onto the top row makes it the majority. Undo works as usual.")),
    dict(id="2026-10-24-presence", date="24 October 2026", tool="Organisation Master",
         title="👋 See when the others start work",
         points=("When another dev opens Organisation Master, Culture Master or Country Master, a small pop-up shows it (where achievements pop up) with a very light ping.",
                 "Settings > 👋 Show when other devs open a tool turns it off. The same person opening the same tool again within half an hour isn't announced twice.")),
    dict(id="2026-10-24-rework-in-gfx", date="24 October 2026", tool="To Do Master / Country Master",
         title="Portrait reworks live in 🖼 GFX now",
         points=("The ~200 portrait rework tasks moved to 🖼 GFX > 🔁 Needs Rework, shared and live for everyone (with their category, who marked them, when, the note and who'd claimed them). The old tasks are in the 🗑 Trash.",
                 "Marking (or unmarking) a portrait in Country Master goes straight to that list for the whole team. Claim one in GFX; ✓ Reworked takes it off for everyone.",
                 "The To Do keeps one task per kind of picture (🔁 Rework Generics, 🔁 Rework Portraits, and one for any other GFX section that gets marks, e.g. 🔁 Rework Flags) while any of that kind waits; each completes itself when its kind is empty.",
                 "Art review tasks can be claimed but stay in the General To Do for everyone.")),
    dict(id="2026-10-24-medium-flags-fix", date="24 October 2026", tool="Organisation Master",
         title="Medium flag rounds start properly again",
         points=("Medium now excludes off-map countries without a base flag instead of trying to load a missing image and ending the round. On-map countries retain their startup flag and name.",)),
    dict(id="2026-10-24-cm-characters", date="24 October 2026", tool="Country Master",
         title="👥 Characters tab",
         points=("The Leaders tab is now Characters: everyone a country has, grouped by role (Country leaders, Field marshals, Generals, Admirals, Advisors, Scientists), with a role filter and counts, and more room in the list.",
                 "🔍 Search by name, id, ideology or trait; tick All countries to find a leader anywhere, and picking one takes you to their country with them picked.",
                 "The Overview has 👥 N characters to jump straight there.")),
    dict(id="2026-10-24-rework-notes", date="24 October 2026", tool="Country Master / To Do Master",
         title="Say what's wrong when marking a portrait for rework",
         points=("Country Master: picking a rework category (right-click a generic or a leader portrait > Mark for rework) asks what's wrong with it (optional); ✎ Rework note... changes it later. A generic with a note shows 📝, a leader portrait shows the note under it.",
                 "The note goes with the mark to the To Do's Art Reviews task and to 🖼 GFX > 🔁 Needs Rework.")),
    dict(id="2026-10-24-gfx-first-scan", date="24 October 2026", tool="To Do Master",
         title="GFX shows up straight away on every PC",
         points=("The 🖼 GFX list was empty on a PC that had never scanned the mod: the first scan takes about 5 minutes and showed nothing while it ran. It now starts from a shared scan that comes with the tool, and your own scan updates it in the background.",
                 "While a scan runs you see what it's doing and for how long; if it fails, the reason shows in the list.",
                 "Animated pictures (frameAnimatedSpriteType / noOfFrames) are judged by one frame, so animated portraits like V's no longer show as ⚠ Broken.")),
    dict(id="2026-10-24-guides-search-check", date="24 October 2026", tool="Organisation Master",
         title="📖 Guides, 🔎 Search everything and a data check",
         points=("📖 Guides (top left): a tour of Organisation Master and one for each part (To Do, Ideas, Dev VCs, GFX, Music, Live Sync, Games). Each step lights up the real button, with an arrow and a ghost cursor showing where to click.",
                 "🔎 Ctrl+K searches everything: tasks, projects, ideas, Dev VCs, GFX pictures, countries, pages and guides; pick one and you're there.",
                 "🩺 The To Do checks itself after start-up: links to things that were deleted are tidied, and anything a person should decide is listed in Settings > Check the To Do data...",
                 "For the future: new masters start from a template and register themselves.",
                 "Fixed: 🔎 Search opened behind the window (nothing seemed to happen). The data check also points a Dev VC proposal at the right task when its first copy was removed as a duplicate.")),
    dict(id="2026-10-24-achievement-popups", date="24 October 2026", tool="Organisation Master",
         title="Your achievements get a little celebration",
         points=("New achievements show a themed popup with their badge, title and requirement, plus an unlock chime. It slides in and fades away after about ten seconds, or when clicked.",
                 "Simultaneous unlocks queue one at a time. Existing badges and incoming sync history stay quiet; sound follows Settings volume and mute.")),
    dict(id="2026-10-24-seasonal-sprite-polish", date="24 October 2026", tool="Organisation Master",
         title="Seasonal sprite and sound polish",
         points=("Smoother Halloween sprite animation in the newer character style.",
                 "Collecting a Santa present now plays a short bell jingle, respecting sound settings and volume.")),
    dict(id="2026-10-24-fun-and-games", date="24 October 2026", tool="Organisation Master",
         title="🎲 Fun & Games achievements",
         points=("The theme secrets and the hidden jokes have their own section now: Fun & Games.",
                 "15 new ones for the RR games: Grand Tour, Just One More Round, Night Owl, Participation Trophy, Speedrun Any%, Glutton for Punishment, Tactical Retreat, Did You Peek?, Photo Finish, Daily Habit, The Scenic Route, Wrong Hemisphere, Agonisingly Close, Hat-Trick and Lump of Coal. Games you've already played count.")),
    dict(id="2026-10-24-gfx-families-history", date="24 October 2026", tool="To Do Master",
         title="GFX: families in the list, and back / forward",
         points=("Cultures hold their subcultures in the list (religion groups their religions, ideologies their sub-ideologies): expand one to do the family as a batch. A parent whose own picture is done but whose children aren't shows in green; pick it for its picture, ✋ all of them, or 🤖 Ask AI for the family.",
                 "The mouse's back / forward buttons (and ◀ ▶ on the picked one) go back and forth between the pictures you've looked at, e.g. through 🔗 Related.",
                 "🤖 Ask AI sends a family together with its parent's picture state, so the AI's suggestions for it match.")),
    dict(id="2026-10-24-gfx-related", date="24 October 2026", tool="To Do Master",
         title="GFX: 🔗 Related pictures",
         points=("Each culture, subculture, religion group, religion / sect, ideology and sub-ideology shows its relatives in 🔗 Related: a culture its subcultures, a subculture its culture, an ideology its sub-ideologies and so on.",
                 "Ones with a picture show it (click to look, right-click for 🔁 Needs rework); ones that are missing or broken have a 🔍 button that jumps straight to them.")),
    dict(id="2026-10-24-games-result-reactions", date="24 October 2026", tool="Organisation Master",
         title="A little reaction to every round",
         points=("Result artwork now gives a short Perfect, Good, OK or Bad reaction: celebratory hops and confetti, sparkles, a small nod or a rueful wobble. Zero scores use Bad too.",
                 "RRdle has just Solved and Unsolved reactions; paused daily puzzles stay neutral. Pinpoint scales its 10,000-point score into the same four bands.")),
    dict(id="2026-10-24-games-round-review", date="24 October 2026", tool="Organisation Master",
         title="RR Games: a little character, clearer answers and Play Again",
         points=("Every game has its own small sprite illustration and themed arcade trim. Correct answers now stay visible in a reserved strip until Next; finishing opens your round score and an answer review, even when it did not beat your best.",
                 "Play Again starts another round directly. Finished RRdle offers unscored Practice; paused daily puzzles offer Resume. Pinpoint retains the full summary map.",
                 "Country names and flags use the saved startup cosmetic tag and ruling ideology on Easy/Normal. Hard can alternate startup and base names; typed answers accept both, retaining tag qualifiers for shared names.")),
    dict(id="2026-10-24-arctic-animation-polish", date="24 October 2026", tool="Organisation Master",
         title="Arctic Station animation polish",
         points=("Improved support for overlapping Arctic Station sprite animations.",)),
    dict(id="2026-10-24-gfx-ai-rating", date="24 October 2026", tool="To Do Master",
         title="GFX: rate the AI's suggestions, and your own suggestion box",
         points=("The 🤖 AI suggestion and a 📝 Human suggestion are separate boxes now; write yours in the human one (it says who wrote it last).",
                 "👍 Good / 👎 Not good... on the AI's suggestion: say why (Not fitting the theme, Nonsensical, Too basic, Wrong / inaccurate, Too detailed for its size, Doesn't match its family's style, Links broken, Copies another entry, Other) and comment. 🤖 Ask AI tells the AI how its suggestions went and asks again for the ones rated not good.")),
    dict(id="2026-10-24-gfx-rework", date="24 October 2026", tool="To Do Master",
         title="GFX: 🔁 Needs Rework",
         points=("A fourth list beside Missing / Broken / Unused: pictures that are there but need redoing. Right-click any picture under 'Look at these' (or the picture itself) > 🔁 Needs rework..., pick how bad (Needs Touchup, Needs Severe Recorrection, Something about it) and say what's wrong.",
                 "Portraits marked for rework in Country Master show up here too. Claim one like any other (a 'Rework: ...' task in Missing GFX); ✓ I made it, or ✓ Reworked / not needed, takes the mark away (Country Master's are unmarked in Country Master).")),
    dict(id="2026-10-24-gfx-link-pictures", date="24 October 2026", tool="To Do Master",
         title="GFX: image links show their pictures",
         points=("Image links that are pictures (yours and the AI's) show as thumbnails under the list all the time; click one to look at it in the zoomable viewer. \"Show pictures\" hides them (remembered).",
                 "🔎 Find pictures looks for a culture's culture (not its people), with quick buttons to look again: Flag / emblem, Traditional dress, Ornament / pattern, Just the name.")),
    dict(id="2026-10-24-gfx-pictures-focus-ideas", date="24 October 2026", tool="To Do Master",
         title="GFX: pop-out pictures, National Focus and National Ideas",
         points=("Every picture in 🖼 GFX (its family, its other versions, your drafts) uses the same thumbnails as Ideas: click one and it pops out in the zoomable viewer, DDS and TGA included.",
                 "🗑 Unused and ⚠ Broken pictures show the picture itself, not just its path.",
                 "New sections: 🎯 National Focus (focus icons the mod's trees ask for that aren't there) and 📜 National Ideas (national spirits' pictures; laws, designers, advisors and the culture system's token ideas are left out).",
                 "Beside Status: 🤖 when an AI has suggested something for a missing picture, 📝 when a person has (its Notes).",
                 "GFX questions (❓ Needs clarification, yours or an AI's) all go under Ideas > Art & Visuals › GFX Clarification; the ones already asked were moved there.")),
    dict(id="2026-10-24-stallonian-animation-polish", date="24 October 2026", tool="Organisation Master",
         title="Stallonian Gambit animation polish",
         points=("More small sprite animation details for Stallonian Gambit, matching the style of the other theme characters.",)),
    dict(id="2026-10-24-gfx-themed-cards", date="24 October 2026", tool="To Do Master",
         title="GFX briefs dressed for every theme",
         points=("Swipe cards now match all fourteen themes, with illustrated headers, matching surfaces and readable text: frost, festive ornaments, celestial details, industrial insignia and more.",
                 "Family references have framed previews and the output filename has its own footer. Long briefs stay inside the card; Details opens the full text.")),
    dict(id="2026-10-24-shelved-ideas", date="24 October 2026", tool="Ideas",
         title="Shelved Ideas, with why",
         points=("🗄 Shelve... asks why (Already decided / known, Not for RR, Too big for now, After release, Nobody to do it, Covered by another idea or task, Changed our minds, Other) and takes an optional note.",
                 "A 🗄 Shelved Ideas section (left side, like the To Do's Archive) lists them grouped by reason; click one to open it, right-click to change why or reopen it. Show has Shelved and Duplicates separately now.",
                 "✨ Only new (next to Show hidden): just the ideas posted, or commented on, by others since you last looked.")),
    dict(id="2026-10-24-gfx-broken-unused", date="24 October 2026", tool="To Do Master",
         title="🖼 GFX: broken and unused pictures, whole families, progress and previews",
         points=("⚠ Broken lists pictures that are there but wrong: a DDS / TGA format HOI4 can't read, the wrong size next to the rest of its family, flags that aren't 32-bit, and icons with no spriteType so the game can't show them.",
                 "🗑 Unused lists picture files nothing points at, spriteTypes for cultures, religions or sub-ideologies that are gone, and flags for tags that don't exist. Remove takes one out of the mod (backed up in backups/gfx_removed); Keep it hides one you want to hold on to.",
                 "✋ The whole family takes a set at once (all of a culture's subculture icons, a country's flags): one task with a sub-task each, completed with its last picture.",
                 "📈 Progress shows how many are left per section and how many fewer since counting began and this month; the Monthly Report shows GFX left at the start and end of the month.",
                 "👁 Preview in game shows your draft at the size the game draws it, next to its family, at actual size and x2 (flags at all three sizes).")),
    dict(id="2026-10-24-name-that-station", date="24 October 2026", tool="Organisation Master / Music Master",
         title="Name That Station: RR radio music quiz",
         points=("RR Games now plays clips from the installed RR music mods. Easy gives a 12-second clip and up to three station choices; Normal gives seven seconds and up to four song choices; Hard gives four seconds and typed station answers with autocomplete.",
                 "Ten-question rounds have separate synced leaderboards. Replay, Stop and volume controls are included; adverts and jingles are excluded, and the radio/other previews stop when a quiz clip takes over.")),
    dict(id="2026-10-24-gfx-tab", date="24 October 2026", tool="To Do Master",
         title="🖼 GFX: every missing picture in one place",
         points=("A new GFX mode between Project mode and Ideas lists every missing culture icon, religious icon, flag, portrait and ideology / sub-ideology icon, found by scanning the mod (Rescan any time).",
                 "Each one has a 🤖 suggestion, reference pictures from its family, image links (searches, 🔎 Wikimedia Commons finds with previews, or your own) and pictures you add, like a task's Icon / Art.",
                 "🃏 Swipe for a task deals random ones: left skips it (just for you), right makes it your task in project Missing GFX (or ✋ claim any from the list). ✓ I made it completes it and counts in the Archive's Monthly Report under 🖼 GFX made; a rescan also completes tasks whose picture is now in the mod.",
                 "Mark anything the scan gets wrong as not actually missing. Open in Culture / Country Master jumps straight to the culture, religion, country, portrait or sub-ideology.",
                 "❓ Needs clarification (by anyone, or by the AI writing suggestions) highlights an entry nobody is sure about and asks the team in 💡 Ideas.")),
    dict(id="2026-10-24-guess-that-ideology", date="24 October 2026", tool="Organisation Master",
         title="Guess That Ideology! joins RR Games",
         points=("Identify a political leader's ideology from their portrait. Easy asks for their main ideology; Normal draws sub-ideology choices from every group; Hard keeps all choices within the correct main ideology.",
                 "Ten-question rounds have separate synced leaderboards by difficulty. Answers use recorded leader roles, accepting multiple valid roles where applicable.")),
    dict(id="2026-10-24-games-country-name-qualifiers", date="24 October 2026", tool="Organisation Master",
         title="Shared country names get clear identifiers in RR Games",
         points=("Countries sharing a name now show their tag in brackets across answer buttons, suggestions, hints and results, including breakaways and formables.",
                 "Typed answers accept the qualified name or tag. An ambiguous bare country name asks for its tag without using a guess.")),
    dict(id="2026-10-24-rrdle-pinpoint", date="24 October 2026", tool="Organisation Master",
         title="RRdle and Pinpoint join RR Games",
         points=("RRdle: one mystery country per UTC day and difficulty, shared through Live Sync. Guess with geography, ideology, population and culture hints; resume the same daily attempt or play unlimited unscored Practice. Share copies a spoiler-free emoji grid.",
                 "Pinpoint: find ten named states on a zoomable, draggable world map. Exact hits earn 1,000 points; nearby clicks earn distance-based points. Medium and Hard add timers, and the results map shows every guess.",
                 "RRdle leaderboards show current/best streaks, win rate and average winning guesses; Pinpoint records best points and time. Both offer Easy, Medium and Hard.")),
    dict(id="2026-10-24-run-copy", date="24 October 2026", tool="Organisation Master / Culture Master / Country Master",
         title="Pull from GitHub with the masters open",
         points=("The masters now run from a copy (in AppData), so the exes in the repository are never locked: a git pull with Organisation, Culture or Country Master open no longer fails half way.",
                 "After a pull that brings a new build, Organisation Master's ⚠ Update says so and Restart now starts it.")),
    dict(id="2026-10-24-scripts-folder", date="24 October 2026", tool="Organisation Master",
         title="Tidier tool folder, smaller exes",
         points=("Organisation Master's code now lives in tools/organisation_master/Scripts; the folder itself only has the start script, the exe and the tool's files.",
                 "Pictures and sounds are no longer copied into the exes: all three masters read them from tools/organisation_master, so the exes are smaller (Organisation Master about 32 MB, Culture / Country Master about 30 MB).")),
    dict(id="2026-10-24-rr-games", date="24 October 2026", tool="Organisation Master",
         title="RR Games: six quick games for the dev team",
         points=("RR Games on the top bar opens Holy Guesswork, Culture Shock, Spot the Minority, Flagrant Misidentification, Borderline Genius and Passport Please.",
                 "Each game has three difficulties using saved mod data, with separate developer leaderboards for every game and difficulty.",
                 "Flag rounds speed up to a five-second limit; harder map rounds hide the shape before you type your answer. Scores travel with the team's shared data.",
                 "Culture Shock shows culture/religion composition tables. Borderline Genius Medium keeps multiple choice and includes breakaways and formables. Spot the Minority highlights the target state on a square regional map.")),
    dict(id="2026-10-24-subideology-mapmode", date="24 October 2026", tool="Country Master",
         title="Sub-ideology colours reach the Sub-ideology map mode",
         points=("Giving a sub-ideology its own colour (or making a new one) now writes it to common/map_modes/mapmode_subideology.txt as well, in the fractions of 255 that file needs (69 94 126 -> red 0.27, green 0.37, blue 0.49); one that isn't there yet is added in its ideology's part.",
                 "\"Shows cyan in game\" next to its colour: tell the tool a colour comes out bright cyan and it remembers it for everyone (mapmode_cyan.json), moving the colour to the nearest one that works; no colour known to show cyan is written again.",
                 "Tools > Add missing sub-ideologies to the Sub-ideology map mode fills in any that were never added.",
                 "New Tag (next to Switch off all, above the list): a brand-new country in one window: tag, name, long name, adjective, country file, map colour, capital (typed or clicked on the map), ruling ideology and flag. It's written like the mod's others (country_tags, colors.txt, a history file, the names) and opens straight away.")),
    dict(id="2026-10-24-smaller-exe", date="24 October 2026", tool="Organisation Master",
         title="A much smaller Organisation Master",
         points=("The exe is down from about 62 MB to 40 MB: the theme secrets' pictures are stored at the size they're drawn (they look the same), and parts of the libraries the tool never uses are left out.",
                 "The in-game To Do list is only written again when it changed, so OneDrive isn't kept busy on every save.")),
    dict(id="2026-10-23-burg-ritual-visible-collisions", date="23 October 2026", tool="Organisation Master",
         title="Visible penguin obstacles",
         points=("The penguin checks visible list and editor edges at beak height. Empty layout panels and controls below his path no longer make him hit an invisible wall.",)),
    dict(id="2026-10-23-cat-task-claws", date="23 October 2026", tool="Organisation Master",
         title="A cat with a proper scratching target",
         points=("The Rising Sun cat claws the selected task's title, with repeating fur detail along its stretching arm and a clearer three-clawed paw.",
                 "Selecting a different task clears the old scratches. The marks still fade over five seconds.")),
    dict(id="2026-10-23-arctic-penguin-slide", date="23 October 2026", tool="Organisation Master",
         title="An Arctic weather strip and a clumsy penguin",
         points=("Arctic Station's thermometer now sits in a matching weather strip above the Radio.",
                 "The little pixel penguin slides out from the strip, collides with a visible panel edge, bounces up in surprise and tumbles below the window. With a clear path he slides off the opposite side, leaving a small landing-confetti burst.")),
    dict(id="2026-10-23-imperial-eagle-celebration", date="23 October 2026", tool="Organisation Master",
         title="A grander Andorran celebration",
         points=("The imperial eagle is three times larger with no square panel behind it, and confetti falls across the whole window.",
                 "The birthday-party sound plays first, followed by the Andorran anthem. Escape or switching themes dismisses the effect and stops both clips.")),
    dict(id="2026-10-23-region-globe-icons", date="23 October 2026", tool="To Do Master",
         title="Raised globe icons for regions and continents",
         points=("The icon picker has a Regions & continents page with twelve globe icons, each facing and highlighting its area.",
                 "The bevelled metal rims and raised highlights follow the current theme, alongside the existing Flag Icon option.")),
    dict(id="2026-10-23-update-warning", date="23 October 2026", tool="Organisation Master",
         title="A warning when your build is out of date",
         points=("An orange ⚠ in the menu bar (and the window title) when GitHub has a newer Organisation, Culture or Country Master than your copy: pull, then restart. It checks quietly every 10 minutes and never changes your files.",
                 "If the exe on your PC changed while the tool was open (you pulled or rebuilt), it offers Restart now. Live Sync setup shows the build check too.")),
    dict(id="2026-10-23-trash", date="23 October 2026", tool="To Do Master / Ideas",
         title="🗑 Trash: restore deleted tasks, projects and ideas",
         points=("Deleted tasks, projects and ideas go to the Trash (To Do tool row) for 90 days. Restore puts one back as it was; a restored project takes back its tasks that are still without a project.",
                 "A restore syncs to everyone and wins over the older delete.")),
    dict(id="2026-10-23-stale-nudges", date="23 October 2026", tool="To Do Master",
         title="⏰ Stale tasks and friendly nudges",
         points=("Claimed, open tasks nobody has touched for 21 days (your choice) are listed under ⏰ Stale tasks: leads see everyone's, devs their own. Blocked, waiting, in-review and Needs Fleshing tasks don't count.",
                 "Copy a nudge gives a friendly Discord message per dev; Snooze 2 weeks leaves a task alone. You get a quiet reminder about your own at start-up.")),
    dict(id="2026-10-23-country-reviews", date="23 October 2026", tool="Country Master / To Do Master",
         title="Country reviews",
         points=("Country Master: right-click a country > Flag for Review... with reasons (leaders, history, politics, ideas, army, flag, lore) and a note. It becomes a task in Country System > Review Countries.",
                 "The task shows the country's flag and a snapshot (ruling party, characters, ideas, states), whether its files changed since it was flagged or approved, Open in Country Master, and Approve, which completes it.")),
    dict(id="2026-10-23-picture-history", date="23 October 2026", tool="Ideas",
         title="🕘 Idea picture history",
         points=("Every external edit of an idea picture keeps the version it replaced. 🕘 History in the picture viewer lists them; pick one to look at it and ↩ Restore this version to make it current again (nothing is lost).",)),
    dict(id="2026-10-23-auto-flags", date="23 October 2026", tool="To Do Master / Ideas",
         title="Flags picked up from names",
         points=("Projects, groupings and idea categories / headings named after a country (\"Germany\", \"British Navy\", \"ENG focus tree\") show its flag, with the ideology's flag when the name says one (\"Communist China\", \"Fascist Britain\").",
                 "Only when they have no icon of their own: a picked icon always wins.")),
    dict(id="2026-10-23-auto-region-icons", date="23 October 2026", tool="To Do Master",
         title="Continents get their globe, not a stray flag",
         points=("Projects, groupings and idea headings named after a region or continent (North America, Middle East, Australia/Polynesia, Western Europe, Antarctica...) get its globe icon automatically.",
                 "Fixed false flags: one-word country names that are ordinary words (\"North\", \"Union\", \"Empire\"...) no longer count, so \"North America\" or \"North Korea\" don't get the wrong flag. The longer name wins: \"South Africa\" keeps its flag, \"Africa\" gets the globe.")),
    dict(id="2026-10-23-sync-no-flash", date="23 October 2026", tool="To Do Master",
         title="Live sync without the flash",
         points=("When the others' changes come in, only what changed is drawn again: the task list, the selected task, the Ideas list and the open Dev VC stay as they are unless their own data changed (the whole window used to redraw and flash for a moment).",
                 "Saving is quicker too (the To Do file is written without the slow indenting), so the window no longer stalls on each sync.")),
    dict(id="2026-10-23-sync-notes-fix", date="23 October 2026", tool="To Do Master / Dev VCs",
         title="Live sync no longer eats VC notes",
         points=("Fixed: someone just watching a Dev VC could send an older copy of its notes back, deleting what the note taker had just typed.",
                 "Two people writing in the same notes now both keep their text: different lines combine, and lines both changed keep the note taker's version first with the other's after it.",
                 "Incoming changes keep you on the VC you're in, with your cursor and scroll where they were.",
                 "Live sync no longer says 'offline' when two people send at the same moment or one fetch is slow: it takes the other change in and sends again straight away.",
                 "Fixed: deleting a line from the notes no longer brings it back (or doubles it) when another PC still has the older copy. Each notes box remembers who last wrote it and when; an older copy of the same person's text never beats the newer one.")),
    dict(id="2026-10-23-future-agenda", date="23 October 2026", tool="Dev VCs",
         title="Agenda control and a Future Agenda",
         points=("Agenda items can be edited, ticked, moved up or down, deleted or moved to a Future Agenda (tool buttons or right-click; several at once).",
                 "The Future Agenda is the team's list of items parked for a later VC: edit them, delete them, or bring them into the VC you have open with ⇧ Into this VC.",
                 "Bring to Agenda (Ideas, and now right-click a task) goes to the next Dev VC, not the one just held: a VC dated after today, or else the Future Agenda's Next Dev VC list, which the next VC you make takes in.",
                 "Every agenda item shows who put it forward; right-click > Put forward by changes it.",
                 "Drag a section by its ⠿ grip (Agenda, Notes, Action items, ...) to put the VC's sections in another order. Each VC keeps its own order; a new VC starts with the last one's.")),
    dict(id="2026-10-23-sound-volume", date="23 October 2026", tool="Organisation Master",
         title="Sound volume",
         points=("Settings > Sound volume... sets how loud the clicks, chimes and theme sounds are, for all three masters (the Radio and Music Master keep their own volume).",)),
    dict(id="2026-10-23-rising-sun-cat-palette", date="23 October 2026", tool="Organisation Master",
         title="Softer Rising Sun colours and a mischievous cat",
         points=("Rising Sun backgrounds and buttons are 10% darker. Boxes created in another theme now follow the palette when you switch.",
                 "The small pixel cat reaches up to the Ideas tab with a stretching arm, scratches it, and leaves claw marks fading over five seconds.")),
    dict(id="2026-10-23-sorel-panel-fire-terminal-win", date="23 October 2026", tool="Organisation Master",
         title="Burning panels and a terminal victory badge",
         points=("The Sorel effect burns along the open interface panels and sidebar controls before the scorched theme takes over. Its control now uses RR's Sorelian eagle.",
                 "The Soviet terminal victory badge requires winning tic-tac-toe. Draws no longer qualify.")),
    dict(id="2026-10-23-vaporwave-clean-sunset", date="23 October 2026", tool="Organisation Master",
         title="Cleaner sunset and cassette animation",
         points=("The sun's stripes now follow its circular edge and disappear cleanly behind the horizon. The sky darkens smoothly without overlapping stripe boxes.",
                 "Vaporwave's animation has a separate cassette area with matching artwork and rotating reels, accompanied by the supplied ZHGYV sound. Closing the animation stops its sound.")),
    dict(id="2026-10-23-theme-effects-visibility", date="23 October 2026", tool="Organisation Master",
         title="Visible theme animations and refreshed artwork",
         points=("Theme effects now render inside the app, including borderless mode, with new simplified characters and icons, including a waddling duck.",
                 "The clock appears in every theme. Midnight's clock flashes and plays a chime when the local date reaches midnight; sound settings still apply.",
                 "Vaporwave's radio has a cassette face and a bottom animation control. The terminal opponent is more forgiving, and the reversible scorched theme has a fire transition.")),
    dict(id="2026-10-23-hidden-theme-discoveries", date="23 October 2026", tool="Organisation Master",
         title="Hidden theme discoveries and achievements",
         points=("Each of the 14 themes now has its own hidden interaction, with 17 new badges in the Theme secrets achievement filter. Halloween's rare ghost remains too.",
                 "Field Grey has an optional Drum setting. The new effects respect Sound feedback, and changing themes clears their animations and sound channels.",
                 "The sidebar artwork now yields space to controls on smaller windows. Easter eggs are cosmetic; the scorched Sorel variation is reversible.")),
    dict(id="2026-10-23-project-heading-theme-fix", date="23 October 2026", tool="To Do Master",
         title="Project headings keep their theme when adding tasks",
         points=("Opening New Task or a dependency picker no longer resets the main project headings to pale hardcoded backgrounds.",
                 "Project headings use the current theme's accent tint—orange in Halloween—while keeping each project's own text colour. The picker styles its own rows, and theme changes remain consistent.")),
    dict(id="2026-10-23-selection-arrow-navigation", date="23 October 2026", tool="Organisation Master",
         title="Arrow keys leave highlighted words at the right place",
         points=("With text selected, Right now places the typing cursor at the selection's end and Left at its start, including double-clicked words.",
                 "This applies to text boxes and editable single-line fields, including new dialogs. Shift/Ctrl shortcuts retain their usual behaviour.")),
    dict(id="2026-10-23-smooth-picture-zoom", date="23 October 2026", tool="Ideas",
         title="Smoother picture zoom",
         points=("Picture zoom now eases between smaller steps and follows the pointer. Rapid wheel input accumulates smoothly, including finer trackpad input.",
                 "The viewer uses faster rendering while zooming, sharpens once you stop, and keeps the same canvas image instead of removing and recreating it every frame.")),
    dict(id="2026-10-23-idea-picture-zoom-editor", date="23 October 2026", tool="Ideas",
         title="Larger idea pictures, zoom and external editing",
         points=("Click an idea picture to view it in a larger window. Zoom with the wheel or top-right +/− controls, drag to pan, or use Fit / 100%.",
                 "Open in the top-left launches the default image app. Save over the opened working copy to refresh the picture and its thumbnail automatically, even after closing the preview while Organisation Master stays open.",
                 "Saved external edits become new attachment revisions so live sync cannot overwrite the file open in your editor. Save As to a different filename must be attached separately.")),
    dict(id="2026-10-23-picture-editor-library-isolation", date="23 October 2026", tool="Ideas",
         title="Independent image-editor launches",
         points=("Launching an idea picture in an external editor now clears the packaged tool's temporary DLL search path for that launch, then restores the tool's own settings.",
                 "Picture import and clipboard reads release their source files explicitly. This addresses possible file locks; a temporary-folder cleanup warning alone does not identify its cause.")),
    dict(id="2026-10-22-halloween-ghost-project-refresh", date="22 October 2026", tool="Organisation Master / Ideas",
         title="A rare Halloween visitor and fresh project headings",
         points=("Halloween has a very rare floating ghost. Click it for a soft Ooh and a fade away; it follows the sound setting. Popping it earns the selected developer the Spooked achievement.",
                 "New and renamed projects now refresh the Ideas project headings and project picker immediately.")),
    dict(id="2026-10-22-music-save-receipt-song-order", date="22 October 2026", tool="Music Master",
         title="Music save receipts and draggable song order",
         points=("Save to mod now lists the files created, updated or deleted, grouped by music mod, with the backup location and a copyable summary.",
                 "In Order in the file mode, drag one or several selected songs to the insertion line. Save to mod writes the new station order while preserving each song's complete chance script.",
                 "Other sort modes remain display-only. Discard restores the last saved order.")),
    dict(id="2026-10-22-waveform-playback-volume", date="22 October 2026", tool="Music Master",
         title="Waveform playback, seeking and volume",
         points=("Play original, Play edit, Pause/Resume and Stop now sit directly above the waveform, with a moving playhead.",
                 "Right-click the waveform to play or jump to that source position. Left dragging still adjusts trim boundaries.",
                 "An in-game volume slider sits directly below the waveform, updates preview loudness immediately and saves the selected volume for station imports.")),
    dict(id="2026-10-22-audio-recovery-eq-queues", date="22 October 2026", tool="Music Master",
         title="Recoverable workshops, EQ and station song queues",
         points=("Workshop audio and edits autosave locally. After a crash, reopening the workshop offers recovery; Recover session lets you return to an interrupted batch later.",
                 "Added a ten-band graphic EQ, bass/treble controls and optional noise reduction with strength, floor, profile and tracking options. Preview, export and station imports use the same settings.",
                 "Existing stations now accept planned songs with title, artist and YouTube links. Their linked queue can be edited and downloaded without uploading a file first.",
                 "Station actions now use equal columns across two rows, keeping Open in player and the other buttons visible.")),
    dict(id="2026-10-22-workshop-review-layout", date="22 October 2026", tool="Music Master",
         title="Visible track review controls",
         points=("Fixed the workshop divider hiding the audio editor. The queue and editor now keep usable widths on opening and resizing.",
                 "Review selected and double-clicking a queued track reveal its waveform and edit controls. Finished batch downloads also open the editor automatically.")),
    dict(id="2026-10-22-workshop-spreadsheet-source", date="22 October 2026", tool="Music Master",
         title="Spreadsheet tracks open correctly in the workshop",
         points=("Fixed imported planned tracks treating their spreadsheet source label as an audio filename. Their YouTube links now enter the download queue normally, while local audio still opens for editing.",
                 "Batch downloads open the first successful track for review. Previous/Next track controls move through the queue while keeping each track's trim points, gain, fades and volume.")),
    dict(id="2026-10-22-youtube-track-workshop", date="22 October 2026", tool="Music Master",
         title="YouTube downloads and a small audio editor",
         points=("Download selected planned tracks or a whole queue with yt-dlp. Audio tools install and update from their official releases on each PC.",
                 "Preview audio, drag waveform trim points, adjust gain and fades, and export stereo Ogg Vorbis at 44.1 kHz.",
                 "Add edited tracks to a station or replace an existing song's audio; changes wait for Save to mod and use the normal backup system.")),
    dict(id="2026-10-22-live-music-plans", date="22 October 2026", tool="Music Master",
         title="Live station plans and missing-station downloads",
         points=("Planned stations, songs, notes, logos, statuses and music mod names/colors now travel through Live Sync alongside To Dos.",
                 "Stations made by other developers appear grey in Radio stations until their files are available locally.",
                 "Pull station updates updates installed music repositories; Get missing music mods downloads the missing ones. Both run in the background and preserve local edits.")),
    dict(id="2026-10-22-cursor-drag-in-list-no-group", date="22 October 2026", tool="To Do Master / Culture Master",
         title="Cursor-following rows, in-list drops and embossed flags",
         points=("Dragged entries now move with the cursor as full rows, keeping their name, icon and columns. No separate popup or rotating text.",
                 "No Group is now a temporary row inside the task list, reachable even in long lists. Dropping there releases the task from its project, parent and grouping; sub-tasks travel with their parent and Undo restores the move.",
                 "Country flag icons now match the generic waving flag on a pole, with a bevelled metallic rim, embossed lighting and shadows.")),
    dict(id="2026-10-22-country-party-coalitions", date="22 October 2026", tool="Country Master",
         title="Coalitions and confidence-and-supply",
         points=("Country Master now edits confidence-and-supply support, named governing coalitions and multiple opposition coalitions.",
                 "Coalition membership and names follow party renames and leading-faction changes, with the updated data saved into country history and localisation.")),
    dict(id="2026-10-22-drag-names-no-group-flag-icons", date="22 October 2026", tool="To Do Master / Culture Master",
         title="Visible drag names, No Group drops and flag-pin icons",
         points=("Fixed missing row names during drag animations, including rows with icons and bold fonts.",
                 "Dragging tasks in Dev or Project mode reveals a No Group drop line at the bottom of the task list. Dropping there clears grouping while preserving each task's project and parent; Undo restores it.",
                 "Every Organisation Master icon picker now includes Flag Icon. Enter ENG, ENG_fascist, ENG_fascism or a cosmetic flag tag to create a themed flag-pin badge using Country Master's flag lookup.")),
    dict(id="2026-10-22-inline-drag-group-projects", date="22 October 2026", tool="To Do Master / Culture Master",
         title="Inline drag motion and project assignments for idea groups",
         points=("Drag movement now stays inside the original list row, with upright text and columns. The floating preview card has been removed.",
                 "Right-click an idea category or heading and choose Assign to Project to move the group and its ideas together. In Projects view, this affects only that project's copy of the group.",
                 "Group assignments are remembered for new ideas, while explicit project choices still take precedence. Categories, headings, discussion and linked review tasks are preserved.")),
    dict(id="2026-10-22-drag-wobble-project-ideas", date="22 October 2026", tool="To Do Master / Culture Master",
         title="Drag previews and project idea reviews",
         points=("Drag tasks, projects, ideas, headings, categories or Culture Master's file-order entries with a gently wobbling preview. Rows and drop targets stay steady.",
                 "The Ideas sidebar switches between Categories and Projects. Project rows include their ideas' categories, and posting with a project selected links the new idea to it.",
                 "Pending project ideas get one linked review task under Idea Reviews, with the project lead as reviewer. Category and project edits update the review; resolving or unlinking the idea closes its pending review.")),
    dict(id="2026-10-22-review-map-smooth-switching", date="22 October 2026", tool="To Do Master",
         title="Smoother state review navigation",
         points=("Selecting another state on the review map keeps the panel and map in place while its composition loads, then updates the contents together.",
                 "Dropdown and previous/next navigation use the same transition, without briefly blanking tables or expanding empty cards.")),
    dict(id="2026-10-22-review-change-tracking", date="22 October 2026", tool="To Do Master",
         title="State review progress and change tracking",
         points=("State dropdowns show green ticks for approved states and blue question marks for saved composition changes since the review was created. Approve Changes accepts the updated composition.",
                 "A small progress bar tracks approvals. Further saved edits after approval require another review; open reviewers check in the background every five seconds.",
                 "Empty migratory tribe and cult/order cards now share one compact line.")),
    dict(id="2026-10-22-review-map-approvals", date="22 October 2026", tool="Culture Master / To Do Master",
         title="Regional review maps and state approvals",
         points=("New regional reviews carry a map snapshot through Live Sync. Expand Show on Map below the data source; click a review state on the map to inspect it.",
                 "The state-name heading now collapses the reviewer. Approve as is sits below Open in Culture Master and marks the state green. Approving every state completes the review task.",
                 "Click an approved state's button again to remove its approval. Approvals support Undo and Live Sync.")),
    dict(id="2026-10-22-state-review-readability", date="22 October 2026", tool="To Do Master",
         title="Clearer state review panels",
         points=("State reviews now have larger icons and rows, with separate culture/religion names, groups, presence and majority/minority columns.",
                 "Migratory tribes and cults/orders have their own cards. Previous/next controls make regional reviews easier to browse, and tables stack vertically in narrower windows.")),
    dict(id="2026-10-22-master-change-badges", date="22 October 2026", tool="Organisation Master",
         title="Master colors and themed icons in Recent Changes",
         points=("Updates are identified by master: red for To Do, purple for Music, green for Culture and black for Country.",
                 "Each master has an icon from your active theme. Updates covering multiple masters show a badge for each.")),
    dict(id="2026-10-22-update-popup-readability", date="22 October 2026", tool="Organisation Master",
         title="Clearer Recent Changes popup",
         points=("The Got it / Close button stays fully visible when resizing the popup or using larger text.",
                 "Theme-colored heading bands and dividers separate each update. Their colors follow theme changes while the popup is open.")),
    dict(id="2026-10-22-regional-reviews", date="22 October 2026", tool="Culture Master / To Do Master",
         title="Named reviews for several states",
         points=("Shift-click states, or right-click and add them to the review selection. Selected states are tinted cyan.",
                 "Choose Flag selected states for Review and enter a name, such as Yunnan Cultures Review. All states become one task.",
                 "Use the state dropdown in Selected task to inspect each state's composition or open it in Culture Master.")),
    dict(id="2026-10-22-state-review-details", date="22 October 2026", tool="Culture Master / To Do Master",
         title="State reviews with reasons and composition",
         points=("Flag for Review offers Needs Minorities, Unsure Placement and Needs Lore Update, plus optional notes.",
                 "Requests go to Culture System > Review States. Reflagging an individual state updates its task and reopens a completed review.",
                 "Selected task shows cultures and religions with available icons, presence, migratory tribes/bands and cults/orders. It uses current saved files, with a labelled flagged snapshot as a fallback.")),
    dict(id="2026-10-22-culture-token-repair", date="22 October 2026", tool="Culture Master",
         title="Missing culture tokens repaired",
         points=("Fixed 83 missing synchronized tokens reported by the game.",
                 "Save to mod now also repairs missing tokens for existing defined entries, including those imported or saved by an older version. Pending token repairs appear beside the unsaved-change count.")),
    dict(id="2026-10-22-portrait-task-previews", date="22 October 2026", tool="To Do Master",
         title="Portraits shown inside review tasks",
         points=("Portrait Review and Generic Review tasks show their portrait beside the notes in Selected task.",
                 "Click the preview to open the original image. Images load in the background; unavailable files display a short message.")),
    dict(id="2026-10-22-native-idea-headers", date="22 October 2026", tool="Ideas",
         title="Edit Idea headers in Selected Idea",
         points=("Single-click a category or heading to edit its shared details, comments and links directly in Selected Idea.",
                 "Details save automatically when you change selection. Voting and task approval controls are hidden while a header is selected.")),
)


class RecentChanges:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.text = None

    def identity(self):
        return str(self.app.config.get("todo_me") or "local").strip().casefold()

    def unseen(self):
        saved = self.app.config.get("program_changes_seen") or {}
        seen = saved.get(self.identity(), []) if isinstance(saved, dict) else []
        return [entry for entry in CHANGES if entry["id"] not in seen]

    def startup(self):
        if getattr(self.app, "_quitting", False) or not self.unseen():
            return
        root = self.app.root
        # Let identity confirmation and launch settings finish before announcing changes.
        def startup_dialog(parent):
            for widget in parent.winfo_children():
                if (isinstance(widget, tk.Toplevel) and widget.winfo_viewable()
                        and widget.title() in ("Launch settings", "Who are you?")):
                    return True
                if startup_dialog(widget):
                    return True
            return False

        if root.grab_current() or startup_dialog(root):
            root.after(1500, self.startup)
            return
        if getattr(self.app, "first_start", False):  # (a new PC: the history isn't news - all of it counts as seen)
            self.mark_seen(self.identity(), CHANGES)
            return
        self.show(only_new=True)

    def mark_seen(self, identity, entries):
        saved = self.app.config.get("program_changes_seen")
        if not isinstance(saved, dict):
            saved = self.app.config["program_changes_seen"] = {}
        before = set(saved.get(identity, []))
        after = before | {entry["id"] for entry in entries}
        if after != before:
            saved[identity] = sorted(after)
            self.app.save_config()

    def show(self, only_new=False):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return
        entries = self.unseen() if only_new else list(CHANGES)
        if not entries:
            return
        identity = self.identity()
        w = self.window = tk.Toplevel(self.app.root)
        w.title("What's new" if only_new else "Recent Changes")
        width = min(ui.px(760), max(360, w.winfo_screenwidth() - 80))
        height = min(ui.px(550), max(300, w.winfo_screenheight() - 100))
        w.geometry(f"{width}x{height}")
        w.minsize(min(ui.px(500), width), min(ui.px(350), height))
        w.transient(self.app.root)
        frame = ttk.Frame(w, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        ttk.Label(frame, text="What's new in the tools" if only_new else "Recent Changes", font="om_title").grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(frame, text="New updates appear once. Reopen this list beside Achievements in the top bar.",
                             style="Muted.TLabel", wraplength=width - ui.px(40))
        subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        frame.bind("<Configure>", lambda event: subtitle.configure(wraplength=max(1, event.width - 28)))
        area = ttk.Frame(frame)
        area.grid(row=2, column=0, sticky="nsew")
        text = self.text = tk.Text(area, wrap="word", font="om_body", relief="flat", padx=8, pady=8,
                                  cursor="arrow", takefocus=True, width=1, height=8)
        scroll = ttk.Scrollbar(area, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.tag_configure("meta", font="om_small", spacing3=6)
        text.tag_configure("point", lmargin1=6, lmargin2=20, spacing3=5)
        for master, (color, _icon) in MASTER_STYLES.items():
            text.tag_configure("title:" + master, font="om_bold", spacing1=6, spacing3=6,
                               lmargin1=6, lmargin2=6, background=color, foreground="#ffffff")
            text.tag_configure("badge:" + master, font="om_small_bold", background=color, foreground="#ffffff")
            text.tag_configure("divider:" + master, font=("Segoe UI", max(2, ui.px(2))),
                               spacing1=4, spacing3=6, background=color)
        image_slots = []
        self.photos = []
        for index, entry in enumerate(entries):
            masters = entry_masters(entry)
            primary = masters[0]
            if index:
                text.insert("end", "\n", ("divider:" + primary,))
            text.insert("end", entry["title"] + "\n", ("title:" + primary,))
            for master in masters:
                # A transparent placeholder keeps badge layout stable while themes change.
                photo = tk.PhotoImage(master=w, width=ui.px(18), height=ui.px(18))
                self.photos.append(photo)
                start = text.index("end-1c")
                name = text.image_create("end", image=photo, align="center", padx=4)
                text.tag_add("icon", start, start + "+1c")
                image_slots.append((name, master))
                text.insert("end", " " + master + " ", ("badge:" + master,))
                text.insert("end", "  ")
            detail = (" · " + entry["tool"] if entry["tool"] in ("Ideas", "Dev VCs") else "")
            text.insert("end", detail + " · " + entry["date"] + "\n", "meta")
            for point in entry["points"]:
                text.insert("end", "• " + point + "\n", "point")
            text.insert("end", "\n")
        text.configure(state="disabled")

        def recolor():
            text.tag_configure("meta", foreground=ui.P["muted"])
            text.tag_configure("icon", background=ui.P["input_background"])
            for name, master in image_slots:
                try:
                    photo = icons.image(MASTER_STYLES[master][1], ui.px(18))
                except (OSError, ValueError, KeyError, tk.TclError):
                    photo = None
                if photo:
                    text.image_configure(name, image=photo)

        recolor()
        ui.THEME_HOOKS.append(recolor)

        def cleanup(event):
            if event.widget is w and recolor in ui.THEME_HOOKS:
                ui.THEME_HOOKS.remove(recolor)

        w.bind("<Destroy>", cleanup, add="+")
        ttk.Button(frame, text="Got it" if only_new else "Close", command=w.destroy).grid(row=3, column=0, sticky="e", pady=(10, 0))
        w.bind("<Escape>", lambda _event: w.destroy())
        viewed = False

        def mapped(event):
            nonlocal viewed
            if event.widget is w and not viewed:
                viewed = True
                self.mark_seen(identity, entries)

        w.bind("<Map>", mapped, add="+")
        return w
