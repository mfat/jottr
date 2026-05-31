# Jottr Plugin Standard

This document defines how Jottr plugins are structured, how plugin authors should write them, and how the app should integrate plugin contributions.

The first supported plugin runtime is Python. Plugins may also be manifest-only when they only need declarative UI contributions.

Jottr does not use built-in plugin folders for optional features. Default optional features are listed in the plugin index and resolved through the same registry path as third-party plugins.

## Goals

Plugins should extend Jottr without forcing optional features into the core app. A plugin can add panels, commands, editor extensions, sidebar items, toolbar actions, and background services. The core app owns discovery, settings, permissions, trust prompts, and UI placement.

Plugins must not receive the main window object directly. They interact with Jottr through the plugin manifest and the narrow `PluginAPI` object passed to Python entry files.


## Starting a New Plugin

Start from the template repository:

```bash
git clone git@github.com:Jottrhq/template-plugin.git my-plugin
```

Then rename the plugin id, package folder, command ids, panel ids, and release-please package name. Keep first plugin releases at `0.1.0`, validate `plugin.json`, and publish both the zip and `.zip.sha256` release assets before adding the plugin to `Jottrhq/plugins`.

## Repository Layout

Jottr reads plugin availability from a checksummed plugin index. The default public index lives in the `Jottrhq/plugins` repository:

```text
plugins/
|-- plugins.json
`-- plugins.json.sha256
```

Each plugin is released from its own repository so plugin versions are independent from the main app version and tag history:

```text
Jottrhq/browser-plugin
Jottrhq/rss-feed-plugin
Jottrhq/mermaid-charts-plugin
```

Installed plugin packages are stored under the configured plugins directory. By default this is:

```text
<Jottr config directory>/plugins/
```

Each installed plugin lives in one directory. The plugin manifest must be named one of:

```text
plugin.json
metadata.json
manifest.json
```

Prefer `plugin.json` for new plugins.

## Plugin Index

Validate the plugin index before release:

```bash
python scripts/validate-plugins-json.py plugins.json --checksum plugins.json.sha256
```

The index is the app-facing catalog. Keep it small: it should list where a plugin lives, what package version can be downloaded, and how to verify that package. Do not duplicate manifest-owned fields such as `permissions`, `entry`, `uiPanels`, `sidebarItems`, `toolbarActions`, or other `contributes` data in `plugins.json`. Jottr reads those from the installed plugin package's `plugin.json`.

```json
{
  "schemaVersion": 1,
  "checksumAlgorithm": "sha256",
  "plugins": [
    {
      "id": "rss-feed",
      "displayName": "RSS Feed Reader",
      "description": "Adds the RSS feed reader tab.",
      "repository": "https://github.com/Jottrhq/rss-feed-plugin",
      "latestVersion": "0.1.0",
      "defaultEnabled": true,
      "versions": [
        {
          "version": "0.1.0",
          "package": {
            "downloadUrl": "https://github.com/Jottrhq/rss-feed-plugin/releases/download/rss-feed-v0.1.0/rss-feed-0.1.0.zip",
            "checksumUrl": "https://github.com/Jottrhq/rss-feed-plugin/releases/download/rss-feed-v0.1.0/rss-feed-0.1.0.zip.sha256"
          },
          "source": {"type": "archive"}
        }
      ]
    }
  ]
}
```

`plugins.json.sha256` contains the SHA-256 of `plugins.json`. Each plugin release uploads both the package zip and a sibling `.zip.sha256` asset generated during the package build. Jottr verifies the index checksum after updating the catalog, downloads the package checksum asset, verifies the zip before extraction, and then reads `plugin.json` from the extracted package for permissions and contributions.

## Manifest

Validate plugin manifests before packaging:

```bash
python scripts/validate-plugin-json.py plugin.json
```

Every plugin must include metadata:

```json
{
  "name": "rss-feed",
  "displayName": "RSS Feed",
  "version": "1.0.0",
  "description": "Adds RSS feed reading support.",
  "entry": "index.py",
  "permissions": ["network", "ui.panel"],
  "contributes": {
    "uiPanels": [
      {
        "id": "rss-feed.reader",
        "title": "RSS Reader",
        "type": "rss"
      }
    ],
    "commands": [
      {
        "id": "rss-feed.open",
        "title": "Open RSS Reader",
        "panel": "rss-feed.reader"
      }
    ],
    "toolbarActions": [
      {
        "id": "rss-feed.toolbar",
        "title": "RSS",
        "panel": "rss-feed.reader"
      }
    ]
  }
}
```

### Required Fields

- `name`: Stable plugin identifier. Use lowercase kebab-case, for example `rss-feed`.
- `displayName`: Human-readable name shown in settings.
- `version`: Plugin version. Use semantic versioning when possible.
- `description`: Short explanation shown in settings.
- `permissions`: List of required capabilities. Use an empty list if none are needed.

### Optional Fields

- `entry`: Python file inside the plugin directory. Only `.py` entries are supported in the first version.
- `contributes`: Declarative contributions Jottr can load without executing plugin code.

## Contribution Points

Manifest contribution keys use plural camelCase names:

```json
{
  "contributes": {
    "uiPanels": [],
    "commands": [],
    "editorExtensions": [],
    "sidebarItems": [],
    "toolbarActions": [],
    "backgroundServices": []
  }
}
```

### UI Panels

Panels open as app tabs.

```json
{
  "id": "browser.docs",
  "title": "Docs Browser",
  "type": "browser",
  "url": "https://example.com/docs"
}
```

Supported manifest panel types:

- `text`: Opens a simple read-only text panel using `content` or `description`.
- `browser` or `web`: Opens a web panel using `url` or `homepage`.
- `rss`: Opens Jottr's RSS reader panel.

### Commands

Commands appear in the Plugins menu.

```json
{
  "id": "docs.open",
  "title": "Open Docs",
  "panel": "browser.docs"
}
```

Command behavior may be declarative:

- `panel`: Opens a contributed panel by ID.
- `message`: Shows an informational message.

Python plugins can register callable commands through `PluginAPI.register_command()`. Markdown plugins can also register runtime processors through `PluginAPI.register_markdown_extension()`; those processors may transform rendered markdown HTML and contribute preview head/style/body HTML from the plugin package.

### Toolbar Actions

Toolbar actions appear in the main toolbar.

```json
{
  "id": "docs.toolbar",
  "title": "Docs",
  "tooltip": "Open Docs",
  "panel": "browser.docs"
}
```

Use short labels because toolbar space is limited. If `icon` matches a built-in Jottr icon name, Jottr may use it.

### Sidebar Items

Sidebar items are collected by the plugin registry and exposed through the Plugins menu in the first implementation. Future app versions may render them in a dedicated sidebar.

```json
{
  "id": "workspace.tools",
  "title": "Workspace Tools",
  "panel": "workspace.tools.panel"
}
```

### Editor Extensions

Editor extensions are declared but not yet executed by the app. Use this key to describe future editor integrations without adding unsupported code paths.

```json
{
  "id": "markdown.templates",
  "title": "Markdown Templates"
}
```

### Background Services

Background services are declared and exposed through the registry. The first implementation records them but does not run long-lived processes automatically.

```json
{
  "id": "rss-feed.refresh",
  "title": "Refresh RSS Feeds"
}
```

## Python Plugin API

If a plugin needs code, set `entry` to a Python file and define a `register(api)` function:

```python
from PyQt6.QtWidgets import QLabel


def register(api):
    api.register_command(
        "hello-world.say-hello",
        "Say Hello",
        lambda: print("Hello from a plugin")
    )

    api.register_panel(
        "hello-world.panel",
        "Hello",
        lambda: QLabel("Hello from a Jottr plugin")
    )

    api.register_toolbar_action({
        "id": "hello-world.toolbar",
        "title": "Hello",
        "panel": "hello-world.panel"
    })
```

Supported API methods:

```python
api.register_command(command_id, title, callback)
api.register_panel(panel_id, title, factory)
api.register_toolbar_action(action)
api.register_sidebar_item(item)
api.register_editor_extension(extension)
api.register_background_service(service)
```

The `factory` passed to `register_panel()` must return a Qt widget.

## Permissions

Plugins must declare every capability they require. Permission names are strings so the app can add new capabilities without changing the manifest format.

Use these first-version permissions:

```text
network
filesystem.read
filesystem.write
ui.panel
ui.sidebar
ui.toolbar
commands
editor.read
editor.write
background
settings.read
settings.write
ai.local
ai.remote
```

Jottr currently displays permissions and blocks untrusted remote plugin execution. Future versions should enforce capabilities more deeply in the runtime.

## Security Rules

Remote plugins are discovered from configured Git repositories, but remote plugin code must not run until the user enables the plugin and accepts the trust warning.

Plugin authors should:

- Keep permissions minimal.
- Avoid hidden network calls.
- Avoid modifying user files without explicit user action.
- Avoid storing secrets in plugin directories.
- Keep background work cancellable and visible.

App maintainers should:

- Continue to show permissions before enabling remote plugins.
- Keep plugin APIs narrow.
- Prefer manifest-only contributions when code execution is not needed.
- Add signing or checksum verification before enabling automatic remote updates.
- Avoid giving plugins direct access to `TextEditorApp`.

## Remote Sources

Users configure remote repositories in Settings, then choose Update Sources. Jottr clones or pulls repositories into its config cache and scans the configured `plugins/` subdirectory.

Remote source records use this shape in settings:

```json
{
  "plugin_registry_url": "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json",
  "plugin_registry_checksum_url": "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json.sha256"
}
```

Index updates are manual in the first version. Jottr verifies `plugins.json.sha256` after fetching the index, downloads each package `.zip.sha256` release asset, and verifies the package before extracting it into the app config directory.

## App Integration Checklist

When adding a new plugin contribution type to Jottr:

1. Add the contribution list to `PluginContributionRegistry`.
2. Add manifest loading in `add_manifest_contributions()`.
3. Add a `PluginAPI` method if Python plugins need to register it at runtime.
4. Render the contribution in `TextEditorApp` or the appropriate UI component.
5. Add permissions to this document.
6. Add tests for local discovery, remote trust behavior, and UI registration.

When changing plugin settings:

1. Keep the canonical settings in `SettingsManager`.
2. Surface user controls in the Plugins settings tab.
3. Persist changes through `SettingsDialog.get_data()`.
4. Rebuild `PluginManager` and app UI after settings are accepted.

When moving an existing app feature into a registry plugin:

1. Create a plugin repository under `Jottrhq/<plugin-name>-plugin`.
2. Put the manifest and optional plugin entry code in that repository.
3. Release plugin zips from that repository and publish the SHA-256 checksum.
4. Add the version entry to `Jottrhq/plugins/plugins.json`.
5. Gate optional host behavior with `SettingsManager.is_plugin_enabled("<plugin-name>")` when the host still owns the low-level implementation.
6. Keep the app packaging pointed at plugin runtime code only; plugin indexes are fetched from configured remote channels, not bundled in the app.

## Minimal Manifest-Only Plugin

```text
plugins/
`-- notes-tools/
    `-- plugin.json
```

```json
{
  "name": "notes-tools",
  "displayName": "Notes Tools",
  "version": "1.0.0",
  "description": "Adds a small notes utility panel.",
  "permissions": ["ui.panel"],
  "contributes": {
    "uiPanels": [
      {
        "id": "notes-tools.panel",
        "title": "Notes Tools",
        "type": "text",
        "content": "Notes plugin loaded."
      }
    ],
    "commands": [
      {
        "id": "notes-tools.open",
        "title": "Open Notes Tools",
        "panel": "notes-tools.panel"
      }
    ]
  }
}
```

## Minimal Python Plugin

```text
plugins/
`-- hello-world/
    |-- plugin.json
    `-- index.py
```

```json
{
  "name": "hello-world",
  "displayName": "Hello World",
  "version": "1.0.0",
  "description": "Example Python plugin.",
  "entry": "index.py",
  "permissions": ["ui.panel", "commands"]
}
```

```python
from PyQt6.QtWidgets import QLabel


def register(api):
    api.register_panel(
        "hello-world.panel",
        "Hello World",
        lambda: QLabel("Hello from a plugin")
    )
    api.register_command(
        "hello-world.open",
        "Open Hello World",
        lambda: None
    )
```
