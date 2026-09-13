# Theming Widgets and Dialogs

This document explains how Jottr's light/dark appearance reaches widgets, and the rules new widgets, dialogs, and windows must follow so they pick up dark mode, Window Color Schemes, and live desktop switches.

Every rule here comes from a bug that shipped: dialogs that stayed light in dark mode, windows that snapped back to an old theme after a widget style change, icons tinted for the wrong background, and a desktop that was dark while Jottr started light.

## Where Colors Come From

Two settings decide the chrome colors:

- `window_color_scheme` — a KDE `.colors` scheme (`BreezeDark`, `Oxygen`, …) or `""` for **Default**.
- `ui_theme` — `System`, `Light`, or `Dark`. Only used under Default. Default migrates it to `System`, so in practice Default follows the desktop.

Resolve them together, never one at a time:

```python
from jottr.window_color_scheme import effective_chrome_theme, find_window_color_scheme

theme = effective_chrome_theme(
    settings_manager.get_window_color_scheme(),
    settings_manager.get_ui_theme(),
)
colors = theme["app"]  # "surface", "text", "accent", ...
```

`effective_chrome_theme` handles every case: a named scheme's colors, Default + `System` resolved through the desktop (Breeze Light/Dark when installed), and explicit Light/Dark. `ThemeManager.get_ui_theme(ui_theme)` alone ignores the desktop and named schemes — using it is how the tab rail got the wrong color.

A scheme is named when `find_window_color_scheme(scheme_id).path` is non-empty. Named schemes install their palette on the application; Default chrome uses `ThemeManager.apply_app_palette(target, theme)`.

### The desktop's light/dark preference

Use `jottr.system_color_scheme.system_color_scheme()` or `system_prefers_dark()`. Do not read `QStyleHints.colorScheme()` to learn what the desktop wants: Qt reports `Light` on native GNOME Wayland when the session is dark, and `Unknown` inside the Flatpak. The resolver asks the desktop portal first, then GTK settings, then Qt.

Only the main window subscribes to desktop changes (`connect_system_color_scheme_changed` in `TextEditorApp.watch_system_color_scheme`). It restyles through `apply_app_style`; new UI should be refreshed from there rather than subscribing on its own.

## Pick the Right Kind of Widget

### Child widgets

Widgets inside the main window (panels, tabs, bars) inherit the application palette and the chrome stylesheet. Usually nothing is needed.

If the widget paints colors itself, read them at paint time from `effective_chrome_theme` (see `LeftAlignedDocumentTabBar.theme_app_colors`) or from its own `palette()`. Never cache colors in `__init__`; they go stale on the next theme change.

### Short-lived dialogs

Modal dialogs (`QMessageBox`, font picker, snippet editor, search site) are fine as long as you:

- Pass the main window (or another themed widget) as `parent`.
- Set the window icon with `apply_dialog_window_icon(dialog, "icon-name", settings_manager)`.
- Do not build a separate Light/Dark palette. Inherit the app or parent palette (see `FontSelectionDialog`).
- For message boxes, use `ask_themed_question` / `apply_message_box_icons` so buttons get bundled, tinted icons.

They open and close within one theme, so they never need refreshing.

### Long-lived top-level windows

A non-modal window that can stay open while the theme changes (the Settings window is the reference) needs all of the following. A top-level window does **not** inherit its parent's palette, even when it has a parent.

1. **Set its palette explicitly**, the same way the main window does:

   ```python
   def _apply_palette(self):
       from jottr.qt_style import reconcile_chrome_theme_with_color_scheme
       from jottr.window_color_scheme import effective_chrome_theme, find_window_color_scheme

       app = QApplication.instance()
       scheme_id = self.settings_manager.get_window_color_scheme()
       if find_window_color_scheme(scheme_id).path:
           self.setPalette(app.palette())
           return
       ui_theme = self.settings_manager.get_ui_theme()
       theme = reconcile_chrome_theme_with_color_scheme(
           effective_chrome_theme(scheme_id, ui_theme, app), ui_theme, app
       )
       ThemeManager.apply_app_palette(self, theme)
   ```

   `reconcile_chrome_theme_with_color_scheme` is for Default only; it realigns chrome when the platform refuses a Light/Dark pin. Never apply it to a named scheme.

2. **Reapply it on every `StyleChange`.** Qt's stylesheet style restores the palette a widget had when it was *first* polished on every repolish: a widget style swap, the deferred chrome stylesheet restore after that swap, or the widget's own `setStyleSheet`. Without this, the window snaps back to the theme it was opened with.

   ```python
   def changeEvent(self, event):
       super().changeEvent(event)
       if getattr(self, "_loading", True) or getattr(self, "_applying_palette", False):
           return
       if event.type() == QEvent.Type.StyleChange:
           self._applying_palette = True
           try:
               self._apply_palette()
           finally:
               self._applying_palette = False
   ```

   Skip it until construction finishes, and guard against re-entrancy, because reapplying can repolish again. A refresh triggered by a repolish must only repaint this window; it must not call `apply_qt_color_scheme` or `activate_window_color_scheme`, which change the whole application (the Settings window passes `pin_app_scheme=False` for this).

3. **Let the main window refresh it.** `TextEditorApp.apply_app_style` ends by refreshing the open Settings window. Register a new long-lived window the same way, after the main window's own palette is set.

4. **Resolve from saved settings, not from your own controls.** Menus change settings and restyle before an open window's combo boxes are synced, so reading a combo gives the previous value. Every control saves to `SettingsManager` before it notifies the host, so saved settings are always current.

5. **Order matters when you apply everything yourself:** set the stylesheet first, then the palette, then rebuild icons.

## Stylesheets

- Style Jottr chrome by object name through `ThemeManager.build_app_stylesheet`; do not add app-wide color rules elsewhere.
- A widget-level stylesheet repolishes that widget and triggers the palette restore described above. Keep it font-only where possible (`ThemeManager.build_font_stylesheet`), and set the palette after it.
- Never hard-code light or dark colors in QSS. Take them from the theme dict.

## Icons

- Use `themed_symbolic_icon(name, settings_manager, palette=...)` for dialogs and lists, or the main window's `build_themed_icon(name)` for chrome. They tint bundled SVGs from `resolve_icon_color`, which follows the effective chrome theme and the Icon Contrast setting.
- Provide Selected and Disabled modes (the helpers do). Otherwise each Qt style invents its own tint, and icons change after a widget style swap.
- Rebuild icons after a theme change; tints are baked into pixmaps. `apply_app_style` clears `_themed_icon_cache` and refreshes actions and tabs; do the same for icons you own (see `SettingsDialog.refresh_settings_nav_icons`).

## Checklist

Before merging a new widget, dialog, or window:

- [ ] Colors come from `effective_chrome_theme` or the widget's palette at paint time, never from `ThemeManager.get_ui_theme` or constants.
- [ ] Desktop light/dark comes from `system_color_scheme()`, not `QStyleHints`.
- [ ] Dialogs have a themed parent and `apply_dialog_window_icon`.
- [ ] Long-lived top-level windows set their palette, reapply it on `StyleChange`, are refreshed from `apply_app_style`, and read saved settings.
- [ ] Palette is set after any stylesheet on the same widget.
- [ ] Icons are tinted through the helpers and rebuilt on theme change.
- [ ] Tested under a theme switch and a widget style swap (below).

## Testing

Tests run on Qt's `offscreen` platform. `tests/conftest.py` deletes the windows and dialogs each test leaves behind; without it the suite slows down quadratically and stale windows react to later tests' theme changes. Run the whole suite with `pytest -n auto`.

A useful theming test for a window:

1. Build it under an explicit theme (`settings.save_ui_theme("Light")` before construction), so a fallback to its first palette is detectable whatever the test machine's desktop prefers.
2. `show()` it. Hidden widgets are not repolished like the running app, and hidden resizes deliver no resize event.
3. Switch the theme the way the app does (`save_ui_theme` / `set_window_color_scheme` + `apply_app_style`) and assert on `palette().color(QPalette.ColorRole.Window).lightnessF()`.
4. Swap the widget style (`save_qt_style` + `apply_widget_style`), call `QApplication.processEvents()` for the deferred stylesheet restore, and assert again.
5. Confirm the test fails without your fix. Several palette tests in this suite passed on broken code until they showed the window and started from the opposite theme.

`test_main_window_palette_follows_later_ui_theme_switches` and `test_settings_window_palette_follows_menu_scheme_and_widget_style` in `tests/test_editor_and_main.py` are working examples.
