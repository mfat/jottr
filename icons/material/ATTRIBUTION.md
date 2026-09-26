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

## Browser toolbar

Every icon pack ships the same browser toolbar glyphs: `go-previous`,
`open-external` and `process-stop` from [Bootstrap Icons](https://github.com/twbs/bootstrap-icons)
(MIT, The Bootstrap Authors), `go-next` from [Codicons](https://github.com/microsoft/vscode-codicons)
(CC-BY-4.0, Microsoft), and `view-refresh` from
[Material Design Icons](https://github.com/google/material-design-icons)
(Apache License 2.0, Google).

## Side panels

Every icon pack ships the same `list-add` glyph for the Snippets panel's
New button, from [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)
(MIT, Microsoft Corporation).
