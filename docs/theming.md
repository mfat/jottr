# Theming Widgets and Dialogs

This document explains how Jottr's light/dark appearance reaches widgets, and the rules new widgets, dialogs, and windows must follow so they pick up dark mode, the Interface Look, and live desktop switches.

Every rule here comes from a bug that shipped: dialogs that stayed light in dark mode, windows that snapped back to an old theme after a repolish, icons tinted for the wrong background, and a desktop that was dark while Jottr started light.

## Where Colors Come From

Jottr draws all chrome with Qt's **Fusion** style on every platform (`jottr.qt_style.APP_QT_STYLE`), wrapped in `JottrStyle`, a proxy that carries the app-wide rules below. Fusion ships with Qt and paints purely from the palette, so Jottr's palettes look the same everywhere. There is no Widget Style setting and no KDE `.colors` scheme support; older saved `qt_style` and `window_color_scheme` values are dropped on load (a named scheme becomes the Light or Dark it looked like).

Two settings decide the chrome colors:

- **Color Scheme**, `ui_theme`: `System` (Follow System), `Light`, or `Dark`.
- **Interface Look**, `interface_look`: `native` or `organic`.

Resolve them through one call:

```python
theme = ThemeManager.get_ui_theme(settings_manager.get_ui_theme())
colors = theme["app"]  # "surface", "text", "accent", ...
```

`get_ui_theme` resolves `System` through the desktop, then returns the White or Black theme (Native) or the Organic light or dark theme. Results are cached per look and resolved scheme; `apply_app_style` clears the cache (`ThemeManager.clear_ui_theme_cache`). Apply palettes with `ThemeManager.apply_app_palette(target, theme)`.

`apply_qt_color_scheme` also asks Qt for the matching Light/Dark appearance, which tints what the palette does not reach (window decorations, native dialogs). Some platform themes refuse it, notably GNOME's portal theme under a dark session. That is fine: never derive chrome colors from `QStyleHints.colorScheme()`, or a refused Light request turns the chrome dark.

### The Organic interface look

Organic is Jottr's own look: a warm cream (or dark) ground, pill-shaped menus, toolbar groups and tabs, and rounded panes. Native is a plain look drawn by Fusion from the palette.

- `SettingsManager` publishes the look to `ThemeManager.set_interface_look` on load and on save; `get_ui_theme` then returns `ThemeManager.organic_theme(dark)`.
- An Organic theme dict carries an extra `organic` section of stylesheet tokens (some translucent, as `rgba(r, g, b, a)`; parse them with `ThemeManager.css_color`).

### The desktop's light/dark preference

Use `jottr.system_color_scheme.system_color_scheme()` or `system_prefers_dark()`. Do not read `QStyleHints.colorScheme()` to learn what the desktop wants: Qt reports `Light` on native GNOME Wayland when the session is dark, and `Unknown` inside the Flatpak. The resolver asks the desktop portal first, then GTK settings, then Qt.

Only the main window subscribes to desktop changes (`connect_system_color_scheme_changed` in `TextEditorApp.watch_system_color_scheme`). It restyles through `apply_app_style`; new UI should be refreshed from there rather than subscribing on its own.

### Plugins

Plugins never see `ThemeManager`. They get the chrome colors under stable public names from `PluginAPI.theme_colors()` (`ThemeManager.public_colors`, mapped by `ThemeManager.PUBLIC_COLORS`) and hear about changes through `PluginAPI.on_theme_changed()`, which `apply_app_style` fires through `PluginManager.notify_theme_changed()`. Add public names there; never rename one. The rules plugins follow are in [the plugin standard](plugins.md#styling).

## Pick the Right Kind of Widget

### Child widgets

Widgets inside the main window (panels, tabs, bars) inherit the application palette and the chrome stylesheet. Usually nothing is needed.

If the widget paints colors itself, read them at paint time from `ThemeManager.get_ui_theme` or from its own `palette()`. Never cache colors in `__init__`; they go stale on the next theme change.

### Short-lived dialogs

Modal dialogs (`QMessageBox`, font picker, snippet editor, search site) are fine as long as you:

- Pass the main window (or another themed widget) as `parent`.
- Set the window icon with `apply_dialog_window_icon(dialog, "icon-name", settings_manager)`.
- Do not build a separate Light/Dark palette. Inherit the app or parent palette (see `FontSelectionDialog`).
- For message boxes, use `ask_themed_question` / `apply_message_box_icons` so the role icon is a bundled, tinted glyph.

They open and close within one theme, so they never need refreshing.

### Long-lived top-level windows

A non-modal window that can stay open while the theme changes (the Settings window is the reference) needs all of the following. A top-level window does **not** inherit its parent's palette, even when it has a parent.

1. **Set its palette explicitly**, the same way the main window does:

   ```python
   def _apply_palette(self):
       theme = ThemeManager.get_ui_theme(self.settings_manager.get_ui_theme())
       ThemeManager.apply_app_palette(self, theme)
   ```

2. **Reapply it on every `StyleChange` and `Polish`.** Qt's stylesheet style restores the palette a widget had when it was *first* polished on every repolish: a new app stylesheet, the widget's own `setStyleSheet`, or the repolish Qt queues after a Light/Dark request (that one arrives as `Polish` with no `StyleChange`; handle it in `event()`). Without this, the window snaps back to the theme it was opened with.

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

   Skip it until construction finishes, and guard against re-entrancy, because reapplying can repolish again. A refresh triggered by a repolish must only repaint this window; it must not call `apply_qt_color_scheme`, which changes the whole application (the Settings window passes `pin_app_scheme=False` for this).

3. **Let the main window refresh it.** `TextEditorApp.apply_app_style` ends by refreshing the open Settings window. Register a new long-lived window the same way, after the main window's own palette is set.

4. **Resolve from saved settings, not from your own controls.** Menus change settings and restyle before an open window's combo boxes are synced, so reading a combo gives the previous value. Every control saves to `SettingsManager` before it notifies the host, so saved settings are always current.

5. **Order matters when you apply everything yourself:** set the stylesheet first, then the palette, then rebuild icons.

## Stylesheets

- Style Jottr chrome by object name through `ThemeManager.build_app_stylesheet`; do not add app-wide color rules elsewhere.
- A widget-level stylesheet repolishes that widget and triggers the palette restore described above. Keep it font-only where possible (`ThemeManager.build_font_stylesheet`), and set the palette after it.
- Never hard-code light or dark colors in QSS. Take them from the theme dict.
- The Organic look is the one place the app stylesheet carries colors: `build_app_stylesheet(theme=...)` appends `build_organic_stylesheet` when the theme has `organic` tokens. Style new chrome for it there, by object name. Keep every `border-radius` at or below half the control's smallest height, or Qt ignores it and draws square corners.
- Layout and painting a stylesheet cannot express (pane insets, the toolbar group pills drawn by `GroupedToolBar`, the tab bar base line) belong in `TextEditorApp.apply_interface_look_chrome`, which runs on every `apply_app_style`.

## Icons

- Use `themed_symbolic_icon(name, settings_manager, palette=...)` for dialogs and lists, or the main window's `build_themed_icon(name)` for chrome. They tint bundled SVGs from `resolve_icon_color`, which follows the effective chrome theme and the Icon Contrast setting.
- Provide Selected and Disabled modes (the helpers do). Otherwise the style invents its own tint.
- Rebuild icons after a theme change; tints are baked into pixmaps. `apply_app_style` clears `_themed_icon_cache` and refreshes actions and tabs; do the same for icons you own (see `SettingsDialog.refresh_settings_nav_icons`).
- **Dialog buttons never have icons.** OK, Cancel, Save, Discard, Close and every other button in a dialog's button row is text only, in `QDialogButtonBox`, `QMessageBox`, and hand-built button rows alike. `JottrStyle` answers no to `SH_DialogButtonBox_ButtonsHaveIcons`, so standard buttons stay bare even on platform themes (KDE) that add icons; never `setIcon` on one yourself. Icons are for chrome: toolbar, pane header and tab buttons.

## Checklist

Before merging a new widget, dialog, or window:

- [ ] Colors come from `ThemeManager.get_ui_theme` or the widget's palette at paint time, never from constants or `QStyleHints`.
- [ ] Desktop light/dark comes from `system_color_scheme()`, not `QStyleHints`.
- [ ] Dialogs have a themed parent and `apply_dialog_window_icon`.
- [ ] Long-lived top-level windows set their palette, reapply it on `StyleChange` and `Polish`, are refreshed from `apply_app_style`, and read saved settings.
- [ ] Palette is set after any stylesheet on the same widget.
- [ ] Icons are tinted through the helpers and rebuilt on theme change.
- [ ] Dialog buttons are text only.
- [ ] Tested under a theme switch in both directions (below).

## Testing

Tests run on Qt's `offscreen` platform. `tests/conftest.py` deletes the windows and dialogs each test leaves behind; without it the suite slows down quadratically and stale windows react to later tests' theme changes. Run the whole suite with `pytest -n auto`.

A useful theming test for a window:

1. Build it under an explicit theme (`settings.save_ui_theme("Light")` before construction), so a fallback to its first palette is detectable whatever the test machine's desktop prefers.
2. `show()` it. Hidden widgets are not repolished like the running app, and hidden resizes deliver no resize event.
3. Switch the theme the way the app does (`set_color_scheme`, or `save_ui_theme` + `apply_app_style`) and assert on `palette().color(QPalette.ColorRole.Window).lightnessF()`.
4. Switch back, call `QApplication.processEvents()` for any queued repolish, and assert again.
5. Confirm the test fails without your fix. Several palette tests in this suite passed on broken code until they showed the window and started from the opposite theme.

`test_main_window_palette_follows_later_ui_theme_switches`, `test_settings_window_palette_follows_menu_scheme_and_widget_style` and `test_color_scheme_switch_survives_refused_pin_and_repolish` in `tests/test_editor_and_main.py` are working examples.
