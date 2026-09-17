# Material Symbols UI icons (Rounded)

These SVGs are selected from [Google Fonts Icons / Material Symbols](https://fonts.google.com/icons)
(Rounded style) and bundled with Jottr as an optional icon theme. Glyphs were chosen
for each toolbar, menu, and settings action.

At runtime they are embedded through the Qt Resource System
(`icons/material.qrc` → `src/jottr/resources/icons_material.rcc`) and tinted
for the active light/dark theme. Regenerate with:

```bash
python3 scripts/compile_icons.py
```

License: Apache License 2.0 (Google Material Design Icons).

Source: https://github.com/google/material-design-icons
