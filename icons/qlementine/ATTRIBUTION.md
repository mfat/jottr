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

## Browser toolbar

Every icon pack ships the same browser toolbar glyphs: `go-previous`,
`open-external` and `process-stop` from [Bootstrap Icons](https://github.com/twbs/bootstrap-icons)
(MIT, The Bootstrap Authors), `go-next` from [Codicons](https://github.com/microsoft/vscode-codicons)
(CC-BY-4.0, Microsoft), and `view-refresh` from
[Material Design Icons](https://github.com/google/material-design-icons)
(Apache License 2.0, Google).
