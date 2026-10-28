# Soviet Terminal

WarGames-inspired military computer terminal: near-black backgrounds, phosphor green accents, pale mint text, and Consolas typography. The theme uses the same JSON settings schema as Midnight.

## Resources

- `theme.json`: complete palette and font settings; ID `soviet-terminal`.
- `../../icons/task_icons_soviet_terminal.png` and matching JSON: the original 80 generic symbols, restyled in green.
- `../../icons/alt_history/alt_history_soviet_terminal.png` and matching JSON: the second 80-symbol alternate-history set, in the same style.
- Both catalogs' `theme_icon_sets.json` files map this theme ID to the appropriate resources.

## Claude integration

Discover this folder through the existing theme loader. Preserve its ID when saving user preferences. Apply font settings to named fonts as well as standard Tk fonts if the current loader does not yet support the family field. Respect the existing text-size preference.

Use pale mint for task titles and normal text, brighter green for selection accents and active controls. Reserve green/yellow/red task age colors for the timer; do not darken task titles based on age. Muted labels remain high contrast against black. Keep warning amber and red to distinguish task age and blockers despite the mostly monochrome styling.

The two PNG sheets have true transparency. Use each manifest's crop coordinates, retain existing stable icon IDs and preserve alpha when resizing. The alternate-history catalog remains separate and needs the same additional-set support as other themes.

No flicker, animated cursor, CRT blur or scanline overlay is needed: the palette and typography provide the terminal appearance while keeping notes readable. Optional decorative effects should never cover text or editors.

Only theme resources and icon registry data were added; application source and executable were not modified or rebuilt.
