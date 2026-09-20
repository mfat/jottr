# Qlementine UI icons

These SVGs are selected from [Qlementine Icons](https://github.com/oclero/qlementine-icons)
and bundled with Jottr as an optional icon theme. Glyphs were chosen for each
toolbar, menu, and settings action.

At runtime they are embedded through the Qt Resource System
(`icons/qlementine.qrc` → `src/jottr/resources/icons_qlementine.rcc`) and tinted
for the active light/dark theme. Regenerate with:

```bash
python3 scripts/compile_icons.py
```

Qlementine ships no heading, ordered-list, quote or code-block glyph, so
`format-heading`, `format-list-numbered`, `format-quote` and `format-code-block`
come from [Bootstrap Icons](https://github.com/twbs/bootstrap-icons) (MIT),
whose 16px line weight matches.

License: MIT License (Olivier Cléro; Bootstrap Icons, The Bootstrap Authors).

Source: https://github.com/oclero/qlementine-icons
