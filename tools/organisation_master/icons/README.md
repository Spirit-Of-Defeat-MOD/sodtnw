# RR task icons

80 generic task icons in `task_icons_rr.png`, arranged in 10 columns and 8 rows. Transparent PNG, original generated resolution preserved.

`task_icons_rr.json` provides stable icon IDs, labels, and pixel crop boxes. Use these boxes rather than assuming 160px cells: the generated output dimensions differ from the requested dimensions. Crop, then fit proportionally into the desired UI icon size. Keep the sheet unchanged so coordinates remain valid.

Style: strategy-game symbols in copper/brass, parchment, and olive. Generated with the built-in image generation tool. No application code or executable was changed.

## Theme variants

- Revolution Realised: `task_icons_rr.png` (copper, brass, olive).
- Midnight: `task_icons_midnight.png` (navy, silver, amber).
- Field Grey: `task_icons_field_grey.png` (pewter, stone, olive).

Each sheet has a matching JSON manifest with the same 80 stable icon IDs and ordering. Use each sheet's own crop coordinates. `theme_icon_sets.json` maps theme IDs to sheets and manifests. Variants generated with the built-in image tool: preserve all 80 symbols and the grid while restyling materials for each theme. Theme definitions and app code are unchanged.
