# Jottr Help

## Themes
Jottr separates chrome and editor colors:

- **Style** (View → Style, or Settings → Appearance): **Follow System**, **Light**, or **Dark** menus, toolbars and panels. Follow System matches the desktop.
- **Interface Look** (Settings → Appearance): **Native** is a plain, familiar look; **Organic** is Jottr's own rounded, warm look.
- **Editor Theme** (View → Editor Theme, or Settings → Appearance): White, Sepia, Matcha, Latte, Black, Dracula, Monokai, Monaspace, Tokyo Night, or Nord — applied to the writing surface and syntax colors only. Both show the same palette of swatches, drawn in each theme's page, heading, link and code colors.

Jottr draws its menus, toolbars and panels with Qt's Fusion style on every platform, so they look the same everywhere and follow your light or dark choice exactly.

To change the editor theme:
1. Click the Theme button in the toolbar, open View → Editor Theme (palette grid), or use Settings → Appearance
2. Select your preferred theme
3. Changes are applied immediately

To switch between light and dark:
1. Open View → Style or Settings → Appearance
2. Choose Follow System, Light, or Dark

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

## Formatting Toolbar
Markdown commands for the text you are writing, laid out like GitHub's editor.

- Turn it on with View → Formatting Toolbar (it is hidden until you ask for it), or from the right-click menu on either toolbar
- Buttons: heading (click for H1/H2/H3), bold, italic, strikethrough, inline code, link, image, blockquote, bulleted list, numbered list, task list, code block, and Clear Formatting
- Inline commands act on the selection, or on the word under the cursor; line commands act on the selected lines, or the current line
- The same commands live in the editor's right-click menu under Formatting
- **Clear Formatting** removes Markdown markers — headings, quotes, list markers, bold/italic/strikethrough, inline code, links and code fences — from the selection, or from the current line

## Images
Markdown documents link images the way Typora and VS Code do:

- Paste a screenshot or copied image, drop image files onto the editor, or use Insert Image… on the formatting toolbar or under Formatting in the right-click menu
- Pasted images are saved as PNG files (pasted-date-time.png) in an **images** folder beside the document, and dropped or chosen files are copied there; the link is relative, so the document and its images can move together
- Files already inside the document's folder are linked where they are, not copied
- In an untitled document, images wait in Jottr's settings folder and move beside the document when you first save it
- In the Flatpak, Jottr sees only the document you opened, not its folder. The first time it needs to save an image there, it asks you to choose that folder (or one above it, such as your home folder) and remembers the choice across sessions; the preview then shows the document's images too
- Settings > Editor > Markdown changes the folder name (leave it empty for the document's own folder) or links dropped files where they are instead of copying them

## Spell Checking
Jottr underlines misspelled words while you type:

- Toggle from Tools > Automatic Spell Checking (Ctrl+Shift+O), or in Settings > Spellcheck
- Set the document language under Tools > Document Language, or from the status bar
- Choose a specific language, or Auto-detect (uses `langdetect` on the document text)
- Jottr loads the matching Enchant dictionary (hunspell/aspell on Linux; AppleSpell / macOS system languages in the macOS app); if none is installed it shows a warning instead of guessing
- Settings > Spellcheck lists dictionaries detected on this system
- For Persian/Farsi on Linux, install `myspell-fa` (Debian/Ubuntu) or `hunspell-fa` (Fedora). The macOS app uses Apple’s dictionaries; languages they lack fall back to the built-in checker
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
- Ctrl+B: Bold
- Ctrl+I: Italic
- Ctrl+K: Link
- Ctrl+E: Inline code
- Ctrl+Shift+X: Strikethrough
- Ctrl+\\: Clear formatting
