# Adwaita-Qt (vendored)

Source: https://github.com/FedoraQt/adwaita-qt  
Pinned commit: `0a774368916def5c9889de50f3323dec11de781e`

Jottr vendors this Qt style plugin so Adwaita widget styles work without a
system `adwaita-qt6` package. Upstream marks the project as unmaintained.

Local change: `src/style/adwaitastyle.cpp` `drawMenuBarItemControl` paints a
rounded chip using Adwaita's `selectedMenuColor` (same soft gray as popup menu
hover) and keeps `WindowText` for the label.

## License

- GPL-2.0-or-later (`LICENSE.GPL2`, `COPYING`)
- LGPL-2.0-or-later (`LICENSE.LGPL2`) for library portions as noted upstream
