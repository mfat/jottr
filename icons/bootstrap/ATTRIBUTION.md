# Bootstrap UI icons

These SVGs are selected from [Bootstrap Icons](https://icons.getbootstrap.com/)
1.13.1 and bundled with Jottr as an optional icon theme. Glyphs were chosen for
each toolbar/settings action by meaning, not to mirror Adwaita shapes.

At runtime they are embedded through the Qt Resource System
(`icons/bootstrap.qrc` → `src/jottr/resources/rc_bootstrap_icons.py`) and tinted
for the active light/dark theme. Regenerate the resource module with:

```bash
python3 scripts/compile_icons.py
```

License: MIT (Bootstrap Icons).

Source: https://github.com/twbs/bootstrap-icons
