# Qlementine UI icons

These SVGs are selected from [Qlementine Icons](https://github.com/oclero/qlementine-icons)
and bundled with Jottr as an optional icon theme. Glyphs were chosen for each
toolbar, menu, and settings action.

At runtime they are embedded through the Qt Resource System
(`icons/qlementine.qrc` → `src/jottr/resources/rc_qlementine_icons.py`) and tinted
for the active light/dark theme. Regenerate the resource module with:

```bash
python3 scripts/compile_icons.py
```

License: MIT License (Olivier Cléro).

Source: https://github.com/oclero/qlementine-icons
