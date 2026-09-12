# Jottr Help

## Themes
Jottr separates chrome and editor colors:

- **Color Scheme** (View → Color Scheme, or Settings → Appearance): **Follow system**, **Light**, or **Dark**. This sets Qt's [`ColorScheme`](https://doc.qt.io/qt-6/qt.html#ColorScheme-enum) via `QStyleHints` (`Unknown` follows the platform appearance).
- **Editor Theme** (View → Editor Theme, or Settings → Appearance): White, Black, Sepia, Dracula, Monokai, Monaspace, Tokyo Night, Matcha, Darkly, or a custom theme — applied to the writing surface and syntax colors only. The View menu shows a palette grid of preview cards for each theme.
- **Custom Editor Themes**: User-defined editor and syntax colors (they do not change Color Scheme).

## Widget styles
In Settings > Appearance, **Widget Style** lists every Qt style available on your system, including:
- System: Keep the platform default style
- Built-in styles such as Fusion and Windows
- Platform styles such as WindowsVista, windows11, or macos when provided by Qt
- Desktop or plugin styles installed on your system (for example Breeze, Oxygen, or [Darkly](https://github.com/Bali10050/Darkly))

The dropdown is filled from Qt's style factory, so everything your Qt build can create is offered. Color Scheme drives Qt's application palette hint; Jottr still styles its own chrome (toolbar, tabs, workspace) to match the effective light or dark appearance. Paired light/dark styles (when both are installed) automatically follow Color Scheme.

To create a custom editor theme:
1. Open Settings > Appearance
2. Edit the theme JSON under Custom Editor Themes
3. Put the theme name in the top-level `name` field
4. Save the theme, then choose it as **Editor Theme**

Theme standard (editor themes may still include an `app` block for compatibility; Color Scheme ignores it and stays Follow system, Light, or Dark):
```json
{
  "name": "My Theme",
  "app": {
    "background": "#282a36",
    "surface": "#343746",
    "surface_alt": "#424450",
    "surface_hover": "#44475a",
    "surface_active": "#6272a4",
    "text": "#f8f8f2",
    "muted": "#c6c8d1",
    "border": "#6272a4",
    "border_active": "#815cd6",
    "accent": "#bd93f9",
    "accent_text": "#f8f8f2",
    "danger": "#ff5555"
  },
  "editor": {
    "background": "#282a36",
    "foreground": "#f8f8f2",
    "selection": "#44475a",
    "current_line": "#353747",
    "border": "#6272a4"
  },
  "syntax": {
    "comment": "#6272a4",
    "keyword": "#ff79c6",
    "string": "#f1fa8c",
    "number": "#ffb86c",
    "function": "#50fa7b",
    "type": "#8be9fd",
    "constant": "#bd93f9",
    "error": "#ff5555"
  }
}
```

To change the editor theme:
1. Click the Theme button in the toolbar, open View → Editor Theme (palette grid), or use Settings → Appearance
2. Select your preferred theme
3. Changes are applied immediately

To change the color scheme:
1. Open View → Color Scheme or Settings → Appearance
2. Choose Follow system, Light, or Dark

## Font Customization
Customize the editor font to your preference:

1. Click the Font button in the toolbar
2. Select your preferred:
   - Font family
   - Font size
   - Font style
3. Changes are applied immediately

## Focus Mode
Enter distraction-free writing mode:

- Click the Focus Mode button in the toolbar or press Ctrl+Shift+D (or Cmd+Shift+D on Mac)
- Hides side panels for distraction-free writing
- Click exit button, Escape key or Ctrl+Shift+D (or Cmd+Shift+D on Mac) to exit focus mode

## Spell Checking
Jottr underlines misspelled words while you type:

- Toggle from Tools > Automatic Spell Checking (Ctrl+Shift+O), or in Settings > Dictionary
- Set the document language under Tools > Document Language, or in Settings > Dictionary
- Choose a specific language, or Auto-detect (uses `langdetect` on the document text)
- Jottr loads the matching installed Enchant/hunspell dictionary; if none is installed it shows a warning instead of guessing
- For Persian/Farsi, install `myspell-fa` (Debian/Ubuntu) or `hunspell-fa` (Fedora)
- Changing the document language rechecks open documents immediately

## User Dictionary
The editor maintains a custom dictionary for your frequently used words:

- Words you add to the dictionary won't be marked as misspelled
- These words will also appear as autocomplete suggestions
- Manage your dictionary in Settings > Dictionary

To add words:
1. Right-click on a word
2. Select "Add to Dictionary"

## Word Completion
The editor suggests completions from your user dictionary as you type:

- Start typing a word (at least 2 characters)
- If a matching word exists in your dictionary, it appears in grey
- Press Tab or Enter to accept the suggestion
- The suggestion disappears if you continue typing

## Snippets
Snippets are reusable text blocks that can be quickly inserted with mouse or keyboard:

- Create snippets for frequently used text
- Access snippets from the side panel
- Insert a snippet by double-clicking it or using typing the snippet name. 


To create a snippet:
1. Select text you want to save
2. Right-click and choose "Save as Snippet"
3. Enter a name for your snippet

To use snippets:
1. Click the Snippets button to show the panel
2. Double-click a snippet to insert it
3. Or start typing the snippet name for auto-completion

## Browser Panel
The integrated browser panel allows quick web access:

- Toggle the browser with the Browser button
- Enter URLs directly in the address bar
- Use for quick reference while writing
- Default homepage can be set in Settings

## Site-Specific Searches
Quickly search selected text on specific news sites. You can add any website frm Settings, and Google-search inside that site from the context menu.

1. Select text in the editor
2. Right-click and choose "Search in..."
3. Select a news site:
   - AP News
   - Reuters
   - BBC News
   - Or use regular Google search

Configure search sites:
1. Open Settings
2. Add or modify sites in the Search Sites section

## Keyboard Shortcuts
Common operations:
- Ctrl+N: New document
- Ctrl+O: Open file
- Ctrl+S: Save file
- Ctrl+Z: Undo
- Ctrl+Shift+Z: Redo
- Ctrl++: Zoom in
- Ctrl+-: Zoom out
- Ctrl+0: Reset zoom 
- Ctrl+Shift+D: Toggle focus mode (cmd+shift+d on mac)
- Escape: Exit focus mode
- Ctrl+F: Find
