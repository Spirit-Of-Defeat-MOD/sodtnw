# Alternate-history task icons — set 2

80 symbols per theme in a 10-column, 8-row transparent PNG atlas. Includes snowflake, needle, sword, gun, lightning, electricity, tank, airplane, and motorbike, plus military, science, industry, politics, climate and infrastructure subjects.

`catalog.json` defines the same 80 stable `alt_` IDs across themes. `theme_icon_sets.json` maps the existing theme IDs to this set's sheets and manifests. Sons of Sorel retains theme ID `crimson-bureau`; BurgSys retains `obsidian`.

Each sheet has a matching manifest with its actual image dimensions and pixel crop boxes. Boxes use Pillow's left/top/right/bottom convention (right and bottom exclusive). Use the selected sheet's coordinates rather than assuming fixed cell dimensions. Preserve transparency and scale proportionally. Inspect fit at small display sizes; the current application's alpha-based fit logic can also be used for generated atlas artwork.

## Claude integration

This is an additional asset catalog, not an application change. Keep the original icons and theme settings intact. Extend the icon loader and picker to enumerate both catalogs, resolving an icon by theme ID and stable icon ID. Cache by catalog, theme, icon ID and size, so the two sheets cannot share an incorrect cached image. Retain PhotoImage references and fall back gracefully for absent assets. Old task icon IDs remain valid. No app source or executable has been changed or rebuilt for this delivery.

Generation: built-in image generation tool. The original sheet uses RR copper/brass/olive. Five reference-based variants preserve all 80 subjects and ordering while matching Midnight, Field Grey, Sons of Sorel, Arctic Station and BurgSys. Prompt records are provided in `generation_prompts.json`.
