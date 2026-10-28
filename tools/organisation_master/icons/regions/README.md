# Region globe icons

Fourteen theme-aware globe options in the task icon picker. The renderer projects a public-domain country atlas onto a sphere, then adds theme-coloured metallic rims, relief shading and highlights. No network access is used by the tool.

Geography: Natural Earth, 1:50m Admin 0 countries, public domain.
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson
Terms: https://www.naturalearthdata.com/about/terms-of-use/

`countries.png` stores a country index per pixel in an equirectangular atlas. `regions.json` stores the selected country indices and facing angle. The atlas was rasterised from the country polygon rings, including dateline wrapping and interior holes.

North America excludes the seven Central American mainland countries. Middle East includes Egypt and Turkey. Western Europe includes the British Isles, Iberia, France, Germany, the Low Countries, Switzerland, Austria and Italy with their small neighbours. USSR shows the fifteen former constituent republics. Australia/Polynesia includes the wider Oceania island region; tiny Polynesian islands receive visible glints. North Pole highlights the Arctic cap north of 78 degrees, including ocean ice.

The globe options describe broad geographic areas rather than the mod's changing political borders.

Asia includes East, South, Southeast, Central and Western Asia, plus Russia east of the Urals (matching the existing Europe split). Oceania has its own option and automatic name match, showing Australia, New Zealand and the Pacific islands; the original Australia/Polynesia option remains available. Both use the existing atlas and theme-aware globe renderer.
