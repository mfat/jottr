# Symbolic UI icons

These SVGs are adapted from the [Adwaita Icon Theme](https://gitlab.gnome.org/GNOME/adwaita-icon-theme)
symbolic set and bundled with Jottr for consistent UI chrome offline and in
packaged builds.

At runtime they are embedded through the Qt Resource System
(`icons/symbolic.qrc` → `src/jottr/resources/icons_symbolic.rcc`) and tinted
for the active light/dark theme. Regenerate with:

```bash
python3 scripts/compile_icons.py
```

Adwaita has no heading, code, quote, checkbox, code-file or eraser glyph, so
`format-heading`, `format-code`, `format-quote`, `format-list-task`,
`format-code-block` and `format-clear` come from the GNOME
[Icon Library](https://gitlab.gnome.org/World/design/icon-library) icon dev kit
(CC0-1.0, Jakub Steiner), drawn in the same symbolic style.

License: CC-BY-SA-3.0 or LGPL-3 (and CC-BY-SA-4.0 where noted upstream);
CC0-1.0 for the icon dev kit glyphs.

Source: https://download.gnome.org/sources/adwaita-icon-theme/

## Browser toolbar

Every icon pack ships the same browser toolbar glyphs: `go-previous`,
`open-external` and `process-stop` from [Bootstrap Icons](https://github.com/twbs/bootstrap-icons)
(MIT, The Bootstrap Authors), `go-next` from [Codicons](https://github.com/microsoft/vscode-codicons)
(CC-BY-4.0, Microsoft), and `view-refresh` from
[Material Design Icons](https://github.com/google/material-design-icons)
(Apache License 2.0, Google).
