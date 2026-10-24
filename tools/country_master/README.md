# Country Master

The country side of Revolution Realized, next to Culture Master: every tag, what it starts the game with, and how it
can appear. Edits are written into the normal mod files, so they show up in git like hand edits.

## Running it

- Double-click `CountryMaster.exe` (it finds the mod by itself when it sits in `tools/country_master/`). Culture
  Master's menu bar has **▸ Country Master** and this one has **▸ Culture Master** to open the other tool.
- From source: `python country_master.py [mod folder]` (needs `pip install pillow numpy`; it uses
  `../culture_master/culture_master.py` for the map and file code). Rebuild the exe with `build.bat`.
- The map comes from the same cache as Culture Master (`%LOCALAPPDATA%\CultureMaster`).
- Flags, portraits and country files the mod doesn't have are read from the base game
  (`C:\SteamLibrary\steamapps\common\Hearts of Iron IV` and the other usual Steam folders, or set `HOI4_GAME`).

## Any mod

Country Master works on any HOI4 mod, not just Revolution Realized:
- It opens the mod it sits in (a folder above it with `descriptor.mod`), the folder given on the command line, the last
  one opened, or asks for one (File > **Open another mod...**). The base game is found in the usual Steam folders, or
  it asks once (remembered in `%APPDATA%\CountryMaster\config.json`).
- Files are read like the game does: the mod's file when it has one, else the base game's, except in folders the mod
  replaces (`replace_path` in its `descriptor.mod`). A mod without its own map uses the base game's map.
- **Writes only ever go into the mod.** Changing something only the base game has first copies that file into the mod
  (same path, so it overrides the game's, as in the game); the base game folder is never written to. New localisation
  / sprites go to the mod's own file when it has the usual one (`countries_l_english.yml`, `parties_l_english.yml`,
  `rr_ideologies.gfx`), else to `localisation/english/country_master_l_english.yml` /
  `interface/country_master_ideologies.gfx`.
- Collapses / bombs: Revolution Realized's debug categories, or in any mod a decision category whose name has
  "collapse" or "bomb" in it (only decisions that make or break up countries are kept).
- The mod's own main ideologies are used everywhere (Pax Britannica's `ni`, `ds`, `rc`, `cn`, ...), not just the
  vanilla four: names rows, popularities, flags, the View box ("All <ideology name>") and the Sub-ideologies list. All
  files in `common/ideologies` are read; a sub-ideology's note can sit after its `{` or after a one-line `}`. Main
  ideologies without a colour of their own get a fixed colour.
- Characters with a `country_leader` role per ideology are read role by role (the leader of each ideology is found).
- Names in lists and titles are shown without colour codes / icons (`§O...§!`, `£GFX_...`); edit boxes keep them.
- The base game's DLC folders (`dlc/dlc028_la_resistance/...`) are read like the game does, under the base game:
  their sprites, pictures, flags and portrait lists count (generic operatives and such come from there).
- Uncompressed .dds pictures are read with numpy (PIL does those in slow Python): portraits load ~100x faster.
- **Start date** (tabs at the top): one per bookmark date in `common/bookmarks` (Cold War Iron Curtain: 1949.5.23,
  1960.1.1, 1973.1.1), starting on the earliest default one; the last one picked is remembered per mod. History is
  read the way the game applies it on that date: the undated lines, then every dated block (`1949.1.1 = { }`) up to
  the date, oldest first, with `if` / `else_if` / `else` decided by their `limit` (every DLC counted as owned, `date`
  checks against the start date, anything else as true). That goes for the ruling party, popularities, leaders, ideas,
  cosmetic tag and OOB, and for state owners and cores (`owner`, `add_core_of`, `remove_core_of` in dated blocks).
  Editing the Overview changes the line that is in effect (inside its dated / if block).
- Leaders made the old way in a history file (`create_country_leader`, `create_field_marshal`,
  `create_corps_commander`, `create_navy_leader` with `name = "..."` and `picture = "x.dds"`, looked for in
  `gfx/leaders/<TAG>/`) are read as the country's characters: shown in Leaders with their portrait, counted as the
  ruling party's leader and by the Gap Finder; editing them changes their block in the history file.
- Countries only named per ideology (`SOV_communism`, no `SOV`) use their ruling party's name, else the first there is.
- The first start on a new mod builds its state map (about half a minute); after that it is cached.

## The list on the left

Every tag in `common/country_tags` (not the dynamic D01... ones), with its flag, its states on the map right now and
its **Est. pop** (the `manpower` of those states).

- **Show** picks what the list holds:
  - *All countries*
  - *On the map at start* (owns states in `history/states`)
  - *Collapses* (each debug collapse decision, `RR_debug_collapse*` in `common/decisions/debug_decisions.txt`,
    with the countries it makes)
  - *Time Bombs*, *Reality Bombs*, *Myth Bombs* (the `rr_debug_time_bombs` decisions, split by name)
  - *Can spawn by event* (an event option releases it, transfers states to it or gives it cores; the events the
    collapses / bombs fire are left out, they are under those)
  - *Can spawn by script or cores* (has cores in `history/states`, or a decision / event / focus / scripted effect /
    on_action releases it: `release`, `release_puppet`, `add_core_of`, `transfer_state` into it...)
  - *No way to spawn yet*
  - *Generics type*: every country grouped by where its generic portraits come from: **Has own** (a block of its
    own, or of its cosmetic tag, in `portraits/`), **Shared: Europe / Africa / ...** (none of its own: the game uses
    the continent block of its capital's continent), **No generics**.
- **Gap Finder** narrows it to the countries with a problem (bold amber rows, red count): no leader for every
  ideology (a recruited country leader for democratic, communism, fascism and neutrality), no collapse (on the map at
  start but no collapse decision breaks it up), no flag, a missing ideology flag (and no base flag to fall back on),
  no name, no map colour, a map colour out of range (over 255: PRM has 267), no national ideas, a recruited leader without a *large* portrait (a small one only doesn't count), a recruited character that isn't
  defined anywhere.
- **Sort by** *Name*, *Tag*, *States*, *Est. pop* or *Continent* (its capital's, else where most of its states are);
  ▲/▼ reverses it. The Country, Tag, States and Est. pop headers sort too.
- **Sub-ideologies** groups the countries by ruling party, then by the sub-ideology of the leader the game shows at
  start (social_conservatism, fascism_austrofascist...).

**Collapses and bombs:** click one in the list to **preview** it on the map; double-click it (or right-click) to keep
it **switched on**. Several can be on at once (Tools > Switch off all). States that changed hands are hatched and
country borders are drawn dark, so the new countries show even when their colours are close. A country's own
collapses are also in Overview > Collapses with a Switch on / off button, and in its right-click menu
("Collapse it: ..."). How a collapse is worked out:
- The decision and the events it fires are read: `STATE = { add_core_of = TAG }`, `TAG = { transfer_state = X }`,
  `X = { release = Y }` and `TAG = { collapse_nation_fail = yes }`.
- Like `collapse_nation_fail`, every country that doesn't exist yet and has a core on a state of the collapsing
  country gets that state. The collapse's own new cores go first.
- `if` / `else` branches are all read, so a state that depends on a condition shows its first outcome.

**Collapse types:** some collapse events have several options (England: Devolution / Complete / Anglo-Saxon
Heptarchy, the USSR's parade / stampede of nations...). Each option is its own row under the decision; only one type
of a decision is on at a time. **Collapse all** (button under the list, or Tools) switches on every collapse at once
(the first type of the ones with several); **Switch off all** undoes it. **Fold list / Unfold list** open or close
every row.

## Sub-ideologies layer

**Layer: Sub-ideologies** (top left) lists the types of `common/ideologies/00_ideologies.txt` like the religions in
Culture Master: Democratic / Communist / Nationalist / Autocratic, then (with **Sections** ticked) the banner sections
of the file (`####MAINLINE####`, `SPECIFICS`, `RELIGIOUS`...), then each sub-ideology with its colour, token, how many
countries on the map have it and their Est. pop.
- **Gap Finder**: no icon, no description, no map colour, no name, not used by any country's leader.
- **Sort by** File order (default), Name, Token, Countries, Est. pop (Reverse flips it).
- Clicking a row only changes what the current map mode shows (the mode itself stays):
  - **Sub-ideology** map: an ideology row (Fascism...) colours every country by its leader's sub-ideology for it
    (View becomes All Fascism); a sub-ideology row lights up the countries with it and greys the rest.
  - **Brush strength** map: an ideology row shows its popularity everywhere; a sub-ideology row its popularity
    where the leader for its ideology has it.
- The right side edits it like a religion: **icon** (69x74, `GFX_ideology_<token>` in `interface/rr_ideologies.gfx`,
  `gfx/interface/ideologies/<ideology>_<token>.dds`), **name**, token, **section** (moves its lines under another
  banner), **info** (the `# note` after `token = {`), **quote / quote by / description** (`<token>_desc` in
  `parties_l_english.yml`, written `§Y"quote"§! - by` then the text) and **map colour** (`color = { r g b }` in its
  type). Below it: every country with a leader of it.
- **Banner**: mods like Pax Britannica start descriptions with a picture (`£GFX_..._banner`) and write the quote
  `§Y“quote”§!` / `-§OBy§!` on its own line. The banner is shown (its sprite name can be changed, **Browse...** makes a
  new picture the size and folder of the mod's other banners, with its sprite), the quote goes in Quote / Quote by,
  and saving writes the description back in the mod's own layout (new lines, colours, curly quotes). A new
  description uses the layout of its ideology's other sub-ideologies.
- **Double-click** a sub-ideology (or right-click > **Edit...**, or **Edit in a window...**) edits it in its own window
  (several can be open). **New sub-ideology...** (button; right-click an ideology > *Add a new sub-ideology to X*, or a
  sub-ideology > *Add a new sub-ideology after this*) opens a window: ideology, name, token (numbered ones like
  `NI_VARIANT_15` are continued), section, note and colour (none = the ideology's). It is written after the last one of
  its section in the same style (one line `X = { ... } #NOTE` or a block), its name next to the others' names, and
  then opens in the edit window.

## Ideology view

The **View** box on the map bar picks which leader counts for each country: *On game start* (the ruler) or *All
Democratic / Communism / Fascism / Neutrality* (each country's leader of that ideology, as if it took over). It is
used by the **Ideology** map mode (with All X: which countries have a leader for X), the **Sub-ideology** map mode
(the colour of that leader's sub-ideology), the Sub-ideologies grouping of the country list and the countries
counts of the sub-ideology list.


**All its sub-ideologies (stripes)** (the View box, on the Sub-ideology map): every country is drawn in diagonal
stripes, one per sub-ideology its leaders have (one leader per ideology, the ruling party first), each in that
sub-ideology's colour - so you can see at a glance whether a country's own sub-ideology colours are too close to each
other. Click a country: the status line lists them with their colours and says which ones are *too close*. Gap Finder
> *Sub-ideology colours too close (its leaders)* lists every country with such a pair (at least one of the two with a
colour of its own; distance under 25).
## The map

Click a state to pick its owner; right-click for its owner, cores, the collapses / bombs that give it away
(switch them on or off from there), **Launch** the events that make a country with it, and **Open the state's file**. Wheel zooms, right / middle drag pans. Map modes:
- **Countries**: owners in their colours. The selected country stays bright and everyone else is dimmed.
- **Cores of the selected**: its cores, bright where it owns them.
- **Ideology**: each owner's ruling party (or, with View: All X, who has a leader for X).
- **Sub-ideology**: the colour of the sub-ideology of each owner's leader (View picks which leader). A
  sub-ideology without a `color` of its own (258 of them) uses its ideology's colour from `00_ideologies.txt`
  (Nationalist brown, Communist red...), so Italy's Classical Fascism shows brown. Clicking a state says which
  leader and sub-ideology it has; on the Sub-ideologies layer it also opens that sub-ideology on the right
  ("Clicked: Kingdom of Italy (ITA) - Benito Mussolini") without changing the map.
- **Brush strength**: the popularity of the sub-ideology / ideology picked in the Sub-ideologies list.
- **Continents**: the continent of each state.

## The country (right side)

The country side starts narrow (drag the divider to widen it). The map never moves or changes mode by itself: right-click an entry (country, collapse / bomb, ideology or
sub-ideology) > **Show on map** to highlight its states and zoom there; do it again (or **Clear Show on map**, also
in the map's right-click menu) to clear it.
Each tab has its own Save button. **Check recent changes** (small button under the list, or File; hover it for
the last one) lists everything saved this session with the time and the files it wrote; double-click one to go
back to that country / sub-ideology. Saving writes immediately; the old file is copied to
`tools/country_master/backups/<time>/` first (there is no undo, use the backup or git).

- **Cosmetic tags**: a country that starts with `set_cosmetic_tag = X` (130 of them, e.g. Ireland as `IRE_ENG`,
  France as `FRA_start`) shows X's name, flag and map colour (`common/countries/cosmetic.txt`) everywhere: the list,
  the title ("Irish Home Rule State (IRE as IRE_ENG)"), the map. When X has no names / flags of its own, the tag's
  are used, like the game does. Overview > **Cosmetic tag** edits it (empty = remove the line). Under the box are
  all of the country's **known cosmetic tags** (1,124 over 447 countries; the ones the base game has too - a vanilla flag, `_DEF`/`_ADJ` name or cosmetic.txt colour - are tinted blue and marked *vanilla*, and **Switch off vanilla cosmetic tags** above the list hides them, remembered between runs; the one in use always shows) with a tick, flag, name and where they were
  found: *flag* (gfx/flags), *name* (X_DEF / X_ADJ / X_<ideology> localisation), *colour* (cosmetic.txt), *set in
  script* (a `set_cosmetic_tag = X` in decisions / events / focuses / effects / history: X starting with TAG_ goes to
  that tag, others to the country whose block they're in) and *at start*. Tick one to start with it, untick it for
  none: the header, names, map colour and flags switch to it straight away ("not saved" until you press Save
  overview, which writes it; name / colour edits go to the tag being shown). While it has one,
  the names, colour and flags in the Overview are X's. Gap Finder: *Cosmetic tag at start* and *Cosmetic tag
  without a name / flag / colour*.
- **Overview** (scrolls; click a section title to fold it, or Fold all / Unfold all): names (`TAG`, `TAG_DEF`, `TAG_ADJ` and the `TAG_<ideology>` versions; new ones go to
  `countries_l_english.yml`), map colour (`common/countries/colors.txt`), its flags (base and each ideology, in a row that scrolls sideways; missing ones are marked), capital,
  stability, war support, research slots, ruling party, elections, popularities, the leader the game shows at
  start, and its **Collapses** (switch them on / off right there). History values change the line that sets them now (the last one: the game applies them in order) or get a
  new line.
- **Leaders**: every character it recruits at start plus every `TAG_` character, with portrait (the large one first; the ▶ arrow on the picture switches to the small one used on units / doctrines and to its other portraits (civilian / army / navy); a leader without a working large portrait is red in the list and in the Gap Finder). Name, leader ideology
  (all sub-ideologies), expire date, leader traits and "recruited at start" have fields; the box below edits the
  whole character (generals' skills, advisor roles, portraits...). **New character...** adds one to
  `common/characters/TAG.txt`, names it and recruits it (its `GFX_` portrait sprite still needs a picture).
- **National ideas**: the ideas it starts with plus every `TAG_` country idea, with picture. Name, description and
  "starts with it" (`add_ideas` in its history) have fields; the box below edits the whole idea. **Add an idea it
  starts with...** takes any idea token.
- **OOB**: which OOB file it uses (`oob = "..."`), how many templates / divisions / ships that file has, and the whole
  file to edit. Most countries share `generic`; **Make its own OOB file** copies it to `history/units/TAG.txt`.
- **History file**: the whole history file.
- **Formables** (Layer > *Formables*: the Show row becomes *Both* / *Formable* / *Reformable*, and the map modes
  Ideology / Sub-ideology / Brush strength become **Formable** (every state some formable nation needs, in that
  nation's colour; a picked one bright, the others dimmed; click a state to pick the formable needing it, again for
  the next one), **Reformable** (the same for reformable nations) and **Required for formable** (the picked one's
  required states: green where a country that can form it holds them, red elsewhere, blue = only cored); leaving
  the layer brings the map mode back; right-click a state > *Formables that need it*; **Sort by** orders them too: Name, Tag = the cosmetic tag, States / Est. pop = the required ones,
  Continent): every formable and reformable nation - a decision that sets a cosmetic tag (or
  changes tag) once the country controls the states its `available` asks for (RR: 75 formable, 161 reformable). Each
  row has the result's flag, its cosmetic tag, how many states it needs and their population; under it the countries
  that can form it (any country when nothing says). Click one: its required (and cored) states light up on the map
  (right-click > Show on map zooms there) and the right side shows it - what it becomes (per country when the
  decision gives different tags), who can form it, required states (or *any N of them*), cores, global flag, file -
  with its decision text to edit and save. A country's *How it appears* lists what it can form.
  **New formable...** (Tools menu, or the formable panel): name, description, decision text, id, who can form it,
  required states (typed, or tick *Pick the required states on the map* and click them), extra cores, the cosmetic
  tag it becomes with its names, map colour and flag. Written like RR's: the category (`RR_formable_categories.txt`
  / reformable), the decision (`RR_formable_nation_decisions.txt` / reformable: allowed, highlighted states,
  visible, available `controls_state`, `set_cosmetic_tag`, cores, global flag, AI), the names in
  `RR_formable_nations_l_english.yml` / `countries_l_english.yml`, the colour in `cosmetic.txt`, the flag in
  `gfx/flags/` (+ medium, small). Mods without those files get `country_master_formable_*.txt`.
- **Parties** (tab; mods with Globus's party system, `RR_political_effects.txt`): the country's parties at the start
  date - each a democratic sub-ideology - with name, sub-ideology, popularity, leader and government (ruling party,
  coalition partner, banned), bloc members under the party leading their bloc, and the total (should be 100%).
  Edit a party (name, popularity, leader from its characters, bloc, government, colour) > *Apply to the list*;
  **New party...** (any democratic sub-ideology it doesn't have yet), **Remove party**, the generic-names tick.
  **Save parties** writes: the party lines of the history file in Globus's format (the old ones are replaced where
  they were, `recruit_character` added for a leader not recruited yet), the names (`<TAG>_party_<sub-ideology>` in
  `RR_parties_gui_l_english.yml`) and colours. A colour belongs to the sub-ideology (shared by every country with that
  party): it goes into its `color` in the ideologies file and the pie / list sprites (`rr_party_pie_slices.dds`,
  `rr_party_colors.dds`) and `tools/party_gfx/subs.json` are made again like `make_party_gfx.py` does. A
  sub-ideology new to the party system is registered as `RR_party_tokens.txt` says (rr_party_registry_setup, the
  dummy idea, the synchronized token, its sprite frame). Gap Finder: *Parties don't add up to 100%*.
  - **Sub-ideology** of a party can be changed (the box in its form > Apply): its name, popularity, leader, bloc and
    government move to the new token.
  - Up to **3 parties of one sub-ideology** per country: the 2nd and 3rd get their own tokens (`socialism_2`,
    `socialism_3`, shown as *Socialism #2*), registered like any new party token, with `socialism_2:0 "$socialism$"`
    so the game's tooltip names its ideology, their own names (`USA_party_socialism_2`) and colour (by default a
    lighter / darker shade of the sub-ideology's). When more than 63 party tokens are registered the pie / colour
    sprites get 128 frames (and `noOfFrames` in `RR_parties_ui.gfx` follows).
- **Leaders added later** (Leaders tab, *Also show leaders added by: National focuses / Decisions / Events* tick
  boxes, remembered): every leader an event, decision or national focus gives the country is listed with the others,
  in blue, the last column saying *focus* / *decision* / *event*. Leaders they create (`create_country_leader`,
  `create_field_marshal`, `create_corps_commander`, `create_navy_leader`) get the full sheet: name, ideology, expire,
  traits and portrait, and Save changes their block in that event / decision / focus file. `recruit_character`,
  `promote_character` (also `= yes` in a character's own scope) and `add_country_leader_role` mark the character they
  name (red when it is defined nowhere). Right-click a leader: where it comes from, open the file. The country is the
  `TAG = { }` scope it is in, else the portrait folder (`gfx/leaders/FRA/...`), the option's / if's / event's /
  decision's `tag =`, the focus tree's country, the countries that fire the event (through other events too), the
  event namespace (`AFG_PM.1`) or the character's `TAG_` start; events fired for several countries say so.
- DX10 .dds pictures (`B8G8R8A8_UNORM_SRGB` and other uncompressed 8-bit formats, which PIL can't read) are read too.
- **Generics**: its generic portraits (the random ones for generals, admirals, advisors, operatives...): where
  they come from (its own `TAG = { ... }` block and its files, or the shared continent block and how many other
  countries use it), then each group (Army - male, Navy, Political - communism - male...) with every portrait
  large, and for army / navy also its small one (`<sprite>_small`, used on units). Missing pictures are red.
  Pictures load in the background (a continent can have hundreds). Right-click a portrait > **Mark for rework** > *Needs Touchup* /
  *Needs Severe Recorrection* / *Something about it* (or *Not marked*) - see **Rework list** below. Gap Finder: *No generic portraits at all*,
  *No generic portraits of its own (shared)*, *Generic portrait without a picture (large, or small for army /
  navy)*.
- **Rework list**: right-click a generic (Generics tab) or the leader portrait on the Leaders tab (the one shown:
  large, small... switch with the arrow) > **Mark for rework** > one of three categories: *Needs Touchup* (orange),
  *Needs Severe Recorrection* (red), *Something about it* (purple), or *Not marked*. It goes into
  `tools/country_master/portraits_to_rework.txt` (`mod | sprite | category | used by | date | generic or portrait`, every mod in one file;
  **Open the rework list** on the Generics tab opens it). Marked portraits get a frame and ⚑ in their category's
  colour; leaders with one get a ⚑ in the Leaders list. Gap Finder: *Portrait marked for rework (any)* and one per
  category list the countries that use a marked generic or leader portrait. (The older `generics_to_rework.txt` is
  read and moved into the new file as *Needs Touchup*.)
  Each mark also becomes a task in Organisation Master's To Do (project **Art Reviews**, grouping *Country Master
  checks*): generics under **Generic Review**, leader portraits under **Portrait Review**. Unmarking completes it.
- **How it appears**: the **events that can make it** (each option that does something different is its own row,
  with how many states it gives it; double-click or right-click > **Launch** shows it on the map like a collapse,
  again switches it off; right-click also opens the event file), then its states at start, the collapses / bombs
  that make it (with how many states), the ones where it collapses, its cores, and the script files that can bring
  it in. Events are read from their effects: `release` / `release_puppet`, `TAG = { transfer_state = N }`,
  `N = { transfer_state_to = TAG / add_core_of = TAG }`, `every_state = { limit = { state = N / is_core_of = TAG }
  transfer_state_to = TAG }`; the event's country is the `tag = ` in its trigger when it has one. Right-click a
  country in the list > *Events that make it* launches them too.

## Notes

- A history file written with another case (`FLo - Florida.txt`) is read as that tag and listed in
  Tools > Problems found while loading. The tool never makes a second file for a tag that has one.
- Collapse results are a preview of the script, not the game: `if` limits and later events aren't evaluated.
