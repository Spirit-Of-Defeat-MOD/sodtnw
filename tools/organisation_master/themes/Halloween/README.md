# Halloween

Dark slasher-horror theme, version 3: charcoal-blue panels, bruised-violet headers, blood-red buttons, bone text, cold teal selections and restrained pumpkin-orange highlights. Both icon sheets use fictional prop-blood smears, spatters and short drips while preserving the original symbols. Earlier pumpkin-orange assets are preserved under `backups/`.

## Resources

- `theme.json`: the same palette/font schema as Midnight; stable ID `halloween`.
- `../../icons/task_icons_halloween.png` and matching JSON: 80 generic task symbols.
- `../../icons/alt_history/alt_history_halloween.png` and matching JSON: 80 alternate-history symbols.
- Both catalogs' `theme_icon_sets.json` files map `halloween` to its resources.

## Claude integration

Discover the theme through the existing loader. The `copper` key means accent; here it is warm pumpkin orange. Pale bone text and muted lavender labels sit on cool dark surfaces, with blood-red buttons and violet headers. Teal selections distinguish the active row from red warnings. Preserve green/yellow/red task age semantics. `button_pressed` and `button_pressed_foreground` keep pressed controls readable. Keep ordinary Segoe UI for reading notes.

Use each icon sheet's manifest crop boxes and stable IDs. Preserve transparency and resize proportionally. Keep the second catalog alongside the first; do not replace old task icon assignments. Follow the existing alternate-history README for multi-catalog support.

Blood effects belong on the icons. Keep editors, notes and task text clear of blood overlays, flashing effects or animated shadows so the horror styling does not obscure working information.

The palette is loaded directly from `theme.json`; the shared UI supports its pressed-button colours.
