# Jottr Help

## Themes
Jottr separates chrome and editor colors:

- **Window Color Scheme** (View → Window Color Scheme, or Settings → Appearance): Kate-style chrome palette from installed KDE `.colors` schemes. **Default** follows the system (Breeze Light/Dark when available); picking a named scheme installs that palette.
- **Editor Theme** (View → Editor Theme, or Settings → Appearance): White, Black, Sepia, Dracula, Monokai, Monaspace, Tokyo Night, Matcha, or Darkly — applied to the writing surface and syntax colors only. The View menu shows a palette grid of preview cards for each theme.

## Widget styles
In Settings > Appearance, **Widget Style** lists every Qt style available on your system, including:
- System: Keep the platform default style
- Built-in styles such as Fusion and Windows
- Platform styles such as WindowsVista, windows11, or macos when provided by Qt
- Desktop or plugin styles installed on your system (for example Breeze, Oxygen, or [Darkly](https://github.com/Bali10050/Darkly))

The dropdown is filled from Qt's style factory, so everything your Qt build can create is offered. Window Color Scheme drives the application palette; menus, toolbar, tabs and panels are drawn by the widget style in those colors, with no extra Jottr styling. Paired light/dark styles (when both are installed) automatically follow the active scheme.


To change the editor theme:
1. Click the Theme button in the toolbar, open View → Editor Theme (palette grid), or use Settings → Appearance
2. Select your preferred theme
3. Changes are applied immediately

To change the window color scheme:
1. Open View → Window Color Scheme or Settings → Appearance
2. Choose Default (follow system) or a named KDE color scheme

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

- Toggle from Tools > Automatic Spell Checking (Ctrl+Shift+O), or in Settings > Spellcheck
- Set the document language under Tools > Document Language, or from the status bar
- Choose a specific language, or Auto-detect (uses `langdetect` on the document text)
- Jottr loads the matching installed Enchant/hunspell dictionary; if none is installed it shows a warning instead of guessing
- Settings > Spellcheck lists dictionaries detected on this system
- For Persian/Farsi, install `myspell-fa` (Debian/Ubuntu) or `hunspell-fa` (Fedora)
- Changing the document language rechecks open documents immediately

## User Dictionary
The editor maintains a custom dictionary for your frequently used words:

- Words you add to the dictionary won't be marked as misspelled
- These words will also appear as autocomplete suggestions
- Manage your dictionary in Settings > Spellcheck

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

- Toggle the browser with the Browser button, View > Toggle Browser Pane, or Ctrl+Shift+B
- Enter URLs directly in the address bar
- Click ↗ next to the address bar to open the page in your default browser
- Use for quick reference while writing
- Default homepage can be set in Settings > Browser and Search
- Choose whether searches open in the built-in browser or your default browser in Settings > Browser and Search
- Cookies and logins are forgotten when Jottr closes. To stay signed in, turn on "Remember cookies and logins" under Privacy in Settings > Browser and Search. Remembered cookies are stored unencrypted in Jottr's config folder. "Clear Cookies and Cache" or turning remembering off deletes all saved browsing data, including site storage, when Jottr closes; Jottr offers to restart right away.

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
1. Open Settings > Browser and Search
2. Add, edit, or delete sites under Site-Specific Searches
3. Optionally pick a timeframe (past hour, 24 hours, week, month, or year) to limit a site's results

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
