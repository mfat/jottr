# Symbolic UI icons

These SVGs are adapted from the [Adwaita Icon Theme](https://gitlab.gnome.org/GNOME/adwaita-icon-theme)
symbolic set and bundled with Jottr for consistent UI chrome offline and in
packaged builds.

At runtime they are embedded through the Qt Resource System
(`icons/symbolic.qrc` → `src/jottr/resources/rc_symbolic_icons.py`) and tinted
for the active light/dark theme. Regenerate the resource module with:

```bash
python3 scripts/compile_icons.py
```

License: CC-BY-SA-3.0 or LGPL-3 (and CC-BY-SA-4.0 where noted upstream).

Source: https://download.gnome.org/sources/adwaita-icon-theme/
