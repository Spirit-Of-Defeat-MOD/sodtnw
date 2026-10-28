# Vaporwave

Dark purple interface with smooth pink-violet-cyan gradients, chrome pastel icons and pale lavender text. Bright gradients are accents; working areas stay dark for reading notes.

## Resources

- `theme.json`: complete existing color/font schema plus gradient stop definitions and asset paths.
- `assets/button.png`: vertical violet-to-teal gradient for the current image-button loader.
- `assets/section_header.png`: dark horizontal magenta-violet-teal gradient.
- `assets/sidebar.png`: vertical plum-midnight-teal gradient.
- `assets/backdrop.png`: subtle diagonal dark gradient.
- `assets/accent_strip.png`: bright pink-violet-cyan accent, not a text background.
- `../../icons/task_icons_vaporwave.png` and matching JSON: 80 generic symbols.
- `../../icons/alt_history/alt_history_vaporwave.png` and matching JSON: 80 alternate-history symbols.

## Claude integration

The stable theme ID is `vaporwave`. The current loader reads colors/fonts and `assets.button`. It does not yet consume the other gradient assets or the `gradients` metadata: these are prepared for integration, with solid-color fallbacks already supplied.

Use the supplied PNGs or interpolate the exact stops in `theme.json` at the actual widget dimensions. Keep reusable PhotoImages alive. For resizable section headers, layer the image beneath the title and controls using a Canvas or image-backed container; preserve collapse behavior, accessibility, text scaling and focus handling. Gradients must not cover text or intercept events. Render sidebar/backdrop at the current container size; cache by asset, size and scale. The 6px accent strip is decorative and should not sit behind text.

`parchment_foreground` is deliberately pale because the current image-button path uses that key for all image-button labels. Its disabled-text override is currently a hardcoded dark brown in ui.py: when integrating, replace that override with an appropriately contrasting theme muted color. This package does not change ui.py.

No gradients behind notes, list cells or editors. Task age remains green/yellow/red, distinct from the decorative cyan and pink. Keep task titles in pale lavender rather than age colors. No flickering neon, animated scanlines or glow on body text.

Both icon catalogs' `theme_icon_sets.json` entries map this theme ID. Crop from the selected sheet's own manifest, preserve alpha, and keep stable task icon IDs. The alternate-history catalog remains an additional set.

Only resources and icon registry data were added. No application source or executable was changed or rebuilt.
