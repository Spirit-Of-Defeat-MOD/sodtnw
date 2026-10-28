# Christmas

Dark festive theme, version 3: cranberry-red backgrounds, plum-charcoal panels, evergreen headers, gold-lettered red buttons and icy-blue selections. Both icon catalogs use evergreen, red, gold and snowy ivory with restrained frost and holiday trim.

## Resources

- `theme.json`: complete palette and font settings using the existing schema; stable ID `christmas`.
- `../../icons/task_icons_christmas.png` and matching JSON: 80 generic task symbols.
- `../../icons/alt_history/alt_history_christmas.png` and matching JSON: 80 alternate-history symbols.
- Each catalog's `theme_icon_sets.json` maps `christmas` to these files.

## Claude integration

Discover the theme through the existing loader. The `copper` key is warm gold. Ivory task text, muted lavender labels, evergreen headers and icy-blue selections distinguish the working areas while retaining the red background. Preserve green/yellow/red task-age semantics and text scaling. `button_pressed` and `button_pressed_foreground` keep pressed controls readable.

Use each manifest's own crop coordinates and preserve stable icon IDs, transparency and proportions. Keep the alternate-history catalog alongside the original; see its README for multi-catalog support. Cache images by catalog, theme, icon ID and size and retain PhotoImage references.

Keep festive decoration on icons and out of editors: no falling snow, blinking lights or textures behind task notes. Standard Segoe UI keeps the work area readable.

The palette is loaded directly from `theme.json`; the shared UI supports its pressed-button colours.
