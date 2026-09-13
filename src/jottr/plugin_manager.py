import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from jottr.settings_manager import DEFAULT_ENABLED_PLUGIN_NAMES

PLUGIN_MANIFEST_NAMES = ("plugin.json", "metadata.json", "manifest.json")
REMOTE_WARNING = "Remote plugins can run code only after you review their permissions and trust the source."
OFFICIAL_PLUGIN_CHANNEL_NAME = "Official"
OFFICIAL_PLUGIN_REGISTRY_URL = "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json"
OFFICIAL_PLUGIN_REGISTRY_CHECKSUM_URL = "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json.sha256"
NETWORK_TIMEOUT_SECONDS = 30
GIT_TIMEOUT_SECONDS = 120


def download_file(url, target, timeout=NETWORK_TIMEOUT_SECONDS):
    """Download url to target via a temp file, so a failure never leaves a partial file."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(handle, "wb") as output, urllib.request.urlopen(url, timeout=timeout) as response:
            shutil.copyfileobj(response, output)
        os.replace(temp_name, target)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return target


def run_git(*args):
    """Run git without ever waiting on a credentials prompt."""
    try:
        return subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError((exc.stderr or "").strip() or str(exc)) from exc


@dataclass
class PluginMetadata:
    name: str
    display_name: str
    version: str
    description: str
    entry: str = ""
    permissions: list[str] = field(default_factory=list)
    path: str = ""
    source: str = "local"
    source_url: str = ""
    contributes: dict = field(default_factory=dict)
    enabled: bool = False
    trusted: bool = False
    error: str = ""
    registry_version: str = ""
    download_url: str = ""
    package_sha256: str = ""
    channel_name: str = ""
    channel_verified: bool = False

    @classmethod
    def from_manifest(cls, manifest, plugin_path, source="local", source_url="", state=None, registry_entry=None):
        state = state or {}
        registry_entry = registry_entry or {}
        name = str(manifest.get("name", "")).strip()
        if not name:
            raise ValueError("Plugin metadata must include a name.")
        package = registry_entry.get("package", {})
        registry_version = registry_entry.get("version", "")
        return cls(
            name=name,
            display_name=str(manifest.get("displayName") or manifest.get("display_name") or registry_entry.get("displayName") or name),
            version=str(manifest.get("version") or registry_version or "0.0.0"),
            description=str(manifest.get("description", registry_entry.get("description", ""))),
            entry=str(manifest.get("entry", "")),
            permissions=list(manifest.get("permissions", [])),
            path=str(plugin_path),
            source=source,
            source_url=source_url,
            contributes=dict(manifest.get("contributes", {})),
            enabled=bool(state.get("enabled", registry_entry.get("defaultEnabled", False))),
            trusted=bool(state.get("trusted", source in {"registry", "local"})),
            registry_version=str(registry_version),
            download_url=str(package.get("downloadUrl", "")),
            package_sha256=str(package.get("sha256", "")),
            channel_name=str(registry_entry.get("channelName", "")),
            channel_verified=bool(registry_entry.get("channelVerified", False)),
        )

    def as_dict(self):
        return {
            "name": self.name,
            "displayName": self.display_name,
            "version": self.version,
            "description": self.description,
            "entry": self.entry,
            "permissions": list(self.permissions),
            "path": self.path,
            "source": self.source,
            "sourceUrl": self.source_url,
            "contributes": self.contributes,
            "enabled": self.enabled,
            "trusted": self.trusted,
            "error": self.error,
            "registryVersion": self.registry_version,
            "downloadUrl": self.download_url,
            "packageSha256": self.package_sha256,
            "channelName": self.channel_name,
            "channelVerified": self.channel_verified,
        }


class PluginContributionRegistry:
    """Collects contributions provided by manifests and activated plugin entries."""

    def __init__(self):
        self.panels = []
        self.commands = []
        self.editor_extensions = []
        self.sidebar_items = []
        self.toolbar_actions = []
        self.background_services = []
        self.markdown_extensions = []
        self.command_callbacks = {}
        self.panel_factories = {}

    def clear(self):
        self.__init__()

    def upsert_contribution(self, target, contribution):
        contribution_id = contribution.get("id")
        if contribution_id:
            for index, existing in enumerate(target):
                if existing.get("id") == contribution_id:
                    target[index] = {**existing, **contribution}
                    return
        target.append(contribution)

    def add_manifest_contributions(self, plugin, contributes):
        mapping = {
            "uiPanels": self.panels,
            "commands": self.commands,
            "editorExtensions": self.editor_extensions,
            "sidebarItems": self.sidebar_items,
            "toolbarActions": self.toolbar_actions,
            "backgroundServices": self.background_services,
        }
        for key, target in mapping.items():
            for contribution in contributes.get(key, []):
                item = dict(contribution)
                item.setdefault("plugin", plugin.name)
                item.setdefault("permissions", list(plugin.permissions))
                self.upsert_contribution(target, item)

    def register_command(self, plugin, command_id, title, callback):
        command = {"id": command_id, "title": title, "plugin": plugin.name}
        self.upsert_contribution(self.commands, command)
        self.command_callbacks[command_id] = callback

    def register_panel_factory(self, plugin, panel_id, title, factory):
        panel = {"id": panel_id, "title": title, "plugin": plugin.name, "type": "python"}
        self.upsert_contribution(self.panels, panel)
        self.panel_factories[panel_id] = factory

    def register_toolbar_action(self, plugin, action):
        item = dict(action)
        item.setdefault("plugin", plugin.name)
        self.upsert_contribution(self.toolbar_actions, item)

    def register_sidebar_item(self, plugin, item):
        contribution = dict(item)
        contribution.setdefault("plugin", plugin.name)
        self.upsert_contribution(self.sidebar_items, contribution)

    def register_editor_extension(self, plugin, extension):
        contribution = dict(extension)
        contribution.setdefault("plugin", plugin.name)
        self.upsert_contribution(self.editor_extensions, contribution)

    def register_background_service(self, plugin, service):
        contribution = dict(service)
        contribution.setdefault("plugin", plugin.name)
        self.upsert_contribution(self.background_services, contribution)

    def register_markdown_extension(self, plugin, extension):
        contribution = dict(extension)
        contribution.setdefault("plugin", plugin.name)
        self.upsert_contribution(self.markdown_extensions, contribution)


class PluginAPI:
    """Narrow API passed to Python plugins instead of the main window object."""

    def __init__(self, plugin, registry):
        self.plugin = plugin
        self.registry = registry

    def register_command(self, command_id, title, callback):
        self.registry.register_command(self.plugin, command_id, title, callback)

    def register_panel(self, panel_id, title, factory):
        self.registry.register_panel_factory(self.plugin, panel_id, title, factory)

    def register_toolbar_action(self, action):
        self.registry.register_toolbar_action(self.plugin, action)

    def register_sidebar_item(self, item):
        self.registry.register_sidebar_item(self.plugin, item)

    def register_editor_extension(self, extension):
        self.registry.register_editor_extension(self.plugin, extension)

    def register_background_service(self, service):
        self.registry.register_background_service(self.plugin, service)

    def register_markdown_extension(self, extension):
        self.registry.register_markdown_extension(self.plugin, extension)


class PluginManager:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.plugins_dir = Path(
            self.settings_manager.get_setting(
                "plugins_directory",
                os.path.join(self.settings_manager.config_dir, "plugins")
            )
        )
        self.source_cache_dir = Path(self.settings_manager.config_dir) / "plugin_sources"
        self.registry_cache_dir = Path(self.settings_manager.config_dir) / "plugin_registry"
        self.download_cache_dir = Path(self.settings_manager.config_dir) / "plugin_downloads"
        self.plugins = {}
        self.available_plugins = {}
        self.registry_plugins = {}
        self.registry = PluginContributionRegistry()
        self.loaded_modules = {}
        # plugin name -> entry fingerprint the loaded module was executed from.
        self._module_fingerprints = {}

    def plugin_state(self):
        return self.settings_manager.get_setting("plugin_state", {})

    def save_plugin_state(self, state):
        self.settings_manager.save_setting("plugin_state", state)

    def remote_sources(self):
        return list(self.settings_manager.get_setting("plugin_remote_sources", []))

    def official_plugin_channel(self):
        return {
            "name": OFFICIAL_PLUGIN_CHANNEL_NAME,
            "url": OFFICIAL_PLUGIN_REGISTRY_URL,
            "checksumUrl": OFFICIAL_PLUGIN_REGISTRY_CHECKSUM_URL,
            "enabled": True,
            "verified": True,
        }

    def normalize_plugin_channel(self, channel):
        channel = dict(channel or {})
        url = str(channel.get("url") or "").strip()
        checksum_url = str(channel.get("checksumUrl") or channel.get("checksum_url") or "").strip()
        name = str(channel.get("name") or channel.get("displayName") or url or "Plugin Channel").strip()
        is_official = url == OFFICIAL_PLUGIN_REGISTRY_URL
        return {
            "name": OFFICIAL_PLUGIN_CHANNEL_NAME if is_official else name,
            "url": url,
            "checksumUrl": OFFICIAL_PLUGIN_REGISTRY_CHECKSUM_URL if is_official and not checksum_url else checksum_url,
            "enabled": bool(channel.get("enabled", True)),
            "verified": bool(channel.get("verified", False) or is_official),
        }

    def plugin_channels(self):
        channels = self.settings_manager.get_setting("plugin_channels", [])
        if not channels:
            channels = [self.official_plugin_channel()]
        normalized = []
        seen = set()
        for channel in channels:
            item = self.normalize_plugin_channel(channel)
            if not item["url"] or item["url"] in seen:
                continue
            seen.add(item["url"])
            normalized.append(item)
        if not any(channel["url"] == OFFICIAL_PLUGIN_REGISTRY_URL for channel in normalized):
            normalized.insert(0, self.official_plugin_channel())
        return normalized

    def save_plugin_channels(self, channels):
        self.settings_manager.save_setting("plugin_channels", [self.normalize_plugin_channel(channel) for channel in channels])

    def plugin_channel_filter(self):
        return self.settings_manager.get_setting("plugin_channel_filter", "all")

    def set_plugin_channel_filter(self, channel_name):
        self.settings_manager.save_setting("plugin_channel_filter", channel_name or "all")

    def registry_url(self):
        channels = self.plugin_channels()
        return channels[0]["url"] if channels else self.settings_manager.get_setting("plugin_registry_url", "")

    def registry_checksum_url(self):
        channels = self.plugin_channels()
        return channels[0].get("checksumUrl", "") if channels else self.settings_manager.get_setting("plugin_registry_checksum_url", "")

    def set_plugins_directory(self, path):
        self.plugins_dir = Path(path).expanduser()
        self.settings_manager.save_setting("plugins_directory", str(self.plugins_dir))

    def add_remote_source(self, url, directory="plugins"):
        url = url.strip()
        if not url:
            return
        sources = self.remote_sources()
        if not any(source.get("url") == url for source in sources):
            sources.append({"url": url, "directory": directory or "plugins"})
            self.settings_manager.save_setting("plugin_remote_sources", sources)

    def remove_remote_source(self, url):
        sources = [source for source in self.remote_sources() if source.get("url") != url]
        self.settings_manager.save_setting("plugin_remote_sources", sources)

    def source_cache_path(self, url):
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        return self.source_cache_dir / digest

    def channel_cache_key(self, channel):
        return hashlib.sha256(channel.get("url", "").encode("utf-8")).hexdigest()[:16]

    def cached_registry_file(self, channel=None):
        if channel is None:
            return self.registry_cache_dir / "plugins.json"
        return self.registry_cache_dir / self.channel_cache_key(channel) / "plugins.json"

    def cached_registry_checksum_file(self, channel=None):
        if channel is None:
            return self.registry_cache_dir / "plugins.json.sha256"
        return self.registry_cache_dir / self.channel_cache_key(channel) / "plugins.json.sha256"

    def active_registry_file(self, channel=None):
        if channel is not None:
            cached_registry = self.cached_registry_file(channel)
            cached_checksum = self.cached_registry_checksum_file(channel)
            if cached_registry.exists() and self.verify_checksum_file(cached_registry, cached_checksum):
                return cached_registry
            return cached_registry
        cached_registry = self.cached_registry_file()
        cached_checksum = self.cached_registry_checksum_file()
        if cached_registry.exists() and self.verify_checksum_file(cached_registry, cached_checksum):
            return cached_registry
        return cached_registry

    def load_plugin_registry(self, registry_file=None, channel=None):
        registry_file = Path(registry_file or self.active_registry_file(channel))
        if not registry_file.exists():
            return {"schemaVersion": 1, "plugins": [], "_registry_file": str(registry_file)}
        with open(registry_file, "r", encoding="utf-8") as handle:
            registry = json.load(handle)
        registry.setdefault("plugins", [])
        registry["_registry_file"] = str(registry_file)
        return registry

    def load_plugin_registries(self):
        if "load_plugin_registry" in self.__dict__:
            return [self.load_plugin_registry()]
        registries = []
        # Every enabled channel is loaded; the channel filter only narrows
        # what the Plugins settings page lists (see visible_plugins).
        for channel in self.plugin_channels():
            if not channel.get("enabled", True):
                continue
            registry = self.load_plugin_registry(channel=channel)
            registry["_channel"] = channel
            registries.append(registry)
        return registries

    def verify_checksum_file(self, path, checksum_file):
        path = Path(path)
        checksum_file = Path(checksum_file)
        if not path.exists() or not checksum_file.exists():
            return False
        expected = checksum_file.read_text(encoding="utf-8").strip().split()[0]
        return self.sha256_file(path) == expected

    def sha256_file(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


    def flatten_registry_entry(self, plugin_entry, version_entry=None):
        version_entry = version_entry or {}
        merged = dict(version_entry)
        merged["id"] = plugin_entry.get("id", version_entry.get("id", ""))
        merged["displayName"] = plugin_entry.get("displayName", merged["id"])
        merged["description"] = plugin_entry.get("description", "")
        merged["repository"] = plugin_entry.get("repository", "")
        merged["defaultEnabled"] = plugin_entry.get("defaultEnabled", False)
        for key in ("channelName", "channelUrl", "channelVerified", "_registry_file"):
            if key in plugin_entry:
                merged[key] = plugin_entry[key]
        return merged

    def select_registry_version(self, plugin_entry):
        versions = plugin_entry.get("versions", [])
        if not versions:
            return self.flatten_registry_entry(plugin_entry, plugin_entry)
        plugin_id = plugin_entry.get("id", "")
        state = self.plugin_state().get(plugin_id, {})
        selected_version = state.get("version") or plugin_entry.get("latestVersion") or versions[0].get("version")
        selected = next((item for item in versions if item.get("version") == selected_version), versions[0])
        return self.flatten_registry_entry(plugin_entry, selected)

    def plugin_versions(self, plugin_name):
        entry = self.registry_plugins.get(plugin_name, {})
        return [item.get("version", "") for item in entry.get("versions", []) if item.get("version")]

    def selected_plugin_version(self, plugin_name):
        state_version = self.plugin_state().get(plugin_name, {}).get("version")
        if state_version:
            return state_version
        entry = self.registry_plugins.get(plugin_name, {})
        return entry.get("latestVersion", "")

    def set_plugin_version(self, plugin_name, version):
        if plugin_name not in self.registry_plugins:
            return False
        versions = self.plugin_versions(plugin_name)
        if version not in versions:
            return False
        state = self.plugin_state()
        plugin_state = dict(state.get(plugin_name, {}))
        plugin_state["version"] = version
        state[plugin_name] = plugin_state
        self.save_plugin_state(state)
        self.refresh()
        return True

    def plugin_channels_to_update(self, registry_url=None, checksum_url=None, channel_name=None):
        channels = self.plugin_channels()
        if registry_url:
            channels = [{"name": channel_name or "Plugin Channel", "url": registry_url, "checksumUrl": checksum_url or "", "enabled": True}]
        elif channel_name and channel_name != "all":
            channels = [channel for channel in channels if channel.get("name") == channel_name]
        else:
            channels = [channel for channel in channels if channel.get("enabled", True)]
        return [channel for channel in channels if channel.get("url")]

    def download_plugin_registries(self, channels, legacy_url=None):
        """Fetch channel indexes into the cache.

        Network and cache files only; it does not touch plugin state, so it
        can run off the GUI thread. A failed or unverified download keeps the
        previously cached index.
        """
        self.registry_cache_dir.mkdir(parents=True, exist_ok=True)
        for channel in channels:
            if not channel.get("url"):
                continue
            target = self.cached_registry_file(channel)
            checksum_target = self.cached_registry_checksum_file(channel)
            channel_checksum_url = channel.get("checksumUrl", "")
            if channel_checksum_url:
                staged = target.with_name(target.name + ".download")
                staged_checksum = checksum_target.with_name(checksum_target.name + ".download")
                try:
                    download_file(channel["url"], staged)
                    download_file(channel_checksum_url, staged_checksum)
                    if not self.verify_checksum_file(staged, staged_checksum):
                        raise ValueError("Plugin registry checksum verification failed.")
                    os.replace(staged, target)
                    os.replace(staged_checksum, checksum_target)
                finally:
                    staged.unlink(missing_ok=True)
                    staged_checksum.unlink(missing_ok=True)
            else:
                download_file(channel["url"], target)
            if legacy_url and channel.get("url") == legacy_url:
                shutil.copyfile(target, self.cached_registry_file())
                if checksum_target.exists():
                    shutil.copyfile(checksum_target, self.cached_registry_checksum_file())
        return channels

    def update_plugin_registry(self, registry_url=None, checksum_url=None, channel_name=None):
        channels = self.plugin_channels_to_update(registry_url, checksum_url, channel_name)
        if not channels:
            return False
        self.download_plugin_registries(channels, legacy_url=self.registry_url())
        self.refresh()
        return True

    def sync_remote_sources(self):
        self.source_cache_dir.mkdir(parents=True, exist_ok=True)
        synced = []
        for source in self.remote_sources():
            url = source.get("url", "")
            if not url:
                continue
            cache_path = self.source_cache_path(url)
            if cache_path.exists():
                run_git("-C", str(cache_path), "pull", "--ff-only")
            else:
                run_git("clone", "--depth", "1", url, str(cache_path))
            synced.append(cache_path)
        return synced

    def pull_remote_plugin_source(self, source_url):
        """git pull a remote plugin source; True when new commits arrived.

        Runs git only, so it can run off the GUI thread.
        """
        cache_path = str(self.source_cache_path(source_url))
        before = run_git("-C", cache_path, "rev-parse", "HEAD").stdout.strip()
        run_git("-C", cache_path, "pull", "--ff-only")
        return run_git("-C", cache_path, "rev-parse", "HEAD").stdout.strip() != before

    def update_plugin(self, plugin_name):
        """Update a plugin to the newest version its source offers.

        Returns False when there was nothing to update.
        """
        plugin = self.plugins.get(plugin_name)
        if plugin and plugin.source == "registry":
            latest = self.latest_plugin_version(plugin_name)
            if latest and latest == self.installed_registry_version(plugin):
                return False
            return self.install_plugin_from_registry(
                plugin_name, latest or None, enable=plugin.enabled
            )
        if not plugin or plugin.source != "remote":
            return False
        changed = self.pull_remote_plugin_source(plugin.source_url)
        self.refresh()
        return changed

    def remove_plugin(self, plugin_name):
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return False
        if plugin.source == "local":
            shutil.rmtree(plugin.path)
        elif plugin.source == "registry":
            installed_path = self.plugins_dir / plugin.name
            if installed_path.exists() and Path(plugin.path).resolve() == installed_path.resolve():
                shutil.rmtree(installed_path)
            state = self.plugin_state()
            state.pop(plugin.name, None)
            self.save_plugin_state(state)
        else:
            state = self.plugin_state()
            state.pop(plugin.name, None)
            self.save_plugin_state(state)
        self.refresh()
        return True

    def discover_plugin_dirs(self):
        locations = []
        self.registry_plugins = {}
        for registry in self.load_plugin_registries():
            registry_file = Path(registry.get("_registry_file", self.cached_registry_file()))
            channel = registry.get("_channel", {})
            channel_name = channel.get("name", "")
            channel_url = channel.get("url", "")
            channel_verified = bool(channel.get("verified", False))
            for raw_entry in registry.get("plugins", []):
                plugin_id = raw_entry.get("id")
                if not plugin_id or plugin_id in self.registry_plugins:
                    continue
                entry = dict(raw_entry)
                entry["channelName"] = channel_name
                entry["channelUrl"] = channel_url
                entry["channelVerified"] = channel_verified
                entry["_registry_file"] = str(registry_file)
                self.registry_plugins[plugin_id] = entry
        self.available_plugins = {
            plugin_id: self.select_registry_version(entry)
            for plugin_id, entry in self.registry_plugins.items()
        }
        for plugin_id, entry in self.available_plugins.items():
            source = entry.get("source", {})
            registry_file = Path(entry.get("_registry_file", self.cached_registry_file()))
            installed_path = self.plugins_dir / plugin_id
            source_url = entry.get("channelUrl") or entry.get("repository", "")
            if installed_path.exists():
                locations.append((installed_path, "registry", source_url))
                continue
            if source.get("type") == "path":
                plugin_path = Path(source.get("path", ""))
                if not plugin_path.is_absolute():
                    plugin_path = (registry_file.parent / plugin_path).resolve()
                locations.append((plugin_path, "registry", source_url or source.get("path", "")))

        locations.append((self.plugins_dir, "local", ""))
        for source in self.remote_sources():
            url = source.get("url", "")
            directory = source.get("directory", "plugins")
            cache_path = self.source_cache_path(url)
            locations.append((cache_path / directory, "remote", url))

        # Installed registry plugins live inside the local plugins folder; the
        # first source that finds a directory owns it, so they stay "registry".
        seen = set()
        for base_path, source, url in locations:
            if not base_path.exists():
                continue
            candidates = [base_path] if self.find_manifest(base_path) else sorted(base_path.iterdir())
            for child in candidates:
                if not child.is_dir() or not self.find_manifest(child):
                    continue
                resolved = child.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield child, source, url

    def find_manifest(self, plugin_dir):
        for name in PLUGIN_MANIFEST_NAMES:
            manifest = plugin_dir / name
            if manifest.exists():
                return manifest
        return None

    def load_manifest(self, manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def refresh(self, sync_remote=False):
        if sync_remote:
            self.sync_remote_sources()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        state = self.plugin_state()
        plugins = {}
        for plugin_dir, source, url in self.discover_plugin_dirs():
            try:
                manifest = self.load_manifest(self.find_manifest(plugin_dir))
                name = manifest.get("name", "")
                plugin_state = state.get(name, {})
                registry_entry = self.available_plugins.get(name, {})
                plugin = PluginMetadata.from_manifest(
                    manifest,
                    plugin_dir,
                    source=source,
                    source_url=url,
                    state=plugin_state,
                    registry_entry=registry_entry,
                )
            except Exception as exc:
                plugin = PluginMetadata(
                    name=plugin_dir.name,
                    display_name=plugin_dir.name,
                    version="0.0.0",
                    description="",
                    path=str(plugin_dir),
                    source=source,
                    source_url=url,
                    error=str(exc),
                    channel_name=registry_entry.get("channelName", "") if "registry_entry" in locals() else "",
                    channel_verified=bool(registry_entry.get("channelVerified", False)) if "registry_entry" in locals() else False,
                )
            plugins[plugin.name] = plugin
        for plugin_id, entry in self.available_plugins.items():
            if plugin_id in plugins:
                continue
            state_entry = state.get(plugin_id, {})
            manifest = {
                "name": plugin_id,
                "displayName": entry.get("displayName", plugin_id),
                "version": entry.get("version", "0.0.0"),
                "description": entry.get("description", ""),
                "permissions": [],
                "contributes": {},
            }
            plugin = PluginMetadata.from_manifest(
                manifest,
                "",
                source="registry",
                source_url=entry.get("channelUrl") or entry.get("repository", ""),
                state=state_entry,
                registry_entry=entry,
            )
            # Not installed: only plugins backed by built-in code (the browser
            # pane) can be active; the rest stay off until Enable installs them.
            plugin.enabled = (
                plugin_id in DEFAULT_ENABLED_PLUGIN_NAMES
                and bool(state_entry.get("enabled", True))
            )
            plugins[plugin_id] = plugin
        self.plugins = plugins
        self.rebuild_registry(include_entries=False)
        return list(self.plugins.values())

    def set_enabled(self, plugin_name, enabled, trusted=False):
        plugin = self.plugins[plugin_name]
        if enabled and self.needs_registry_install(plugin):
            self.install_plugin_from_registry(plugin_name)
            plugin = self.plugins[plugin_name]
        if enabled and plugin.source == "remote" and not trusted and not plugin.trusted:
            raise PermissionError(REMOTE_WARNING)
        state = self.plugin_state()
        plugin_state = dict(state.get(plugin.name, {}))
        plugin_state.update({
            "enabled": bool(enabled),
            "trusted": bool(trusted or plugin.trusted or plugin.source in {"registry", "local"}),
        })
        if plugin.source == "registry" and plugin.registry_version:
            plugin_state.setdefault("version", plugin.registry_version)
        state[plugin.name] = plugin_state
        self.save_plugin_state(state)
        self.refresh()
        return self.plugins[plugin_name]


    def read_checksum_text(self, checksum_text):
        return checksum_text.strip().split()[0] if checksum_text.strip() else ""

    def fetch_package_checksum(self, package, archive_path):
        if package.get("sha256"):
            return str(package.get("sha256", "")).strip()
        checksum_url = package.get("checksumUrl")
        if not checksum_url:
            return ""
        checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
        download_file(checksum_url, checksum_path)
        return self.read_checksum_text(checksum_path.read_text(encoding="utf-8"))

    def stage_plugin_package(self, plugin_name, entry):
        """Download (or copy) and unpack a registry package into a staging dir.

        Network and disk only; it does not touch plugin state, so it can run
        off the GUI thread. Returns the staging directory, or None when the
        entry has nothing to install.
        """
        source = entry.get("source", {})
        package = entry.get("package", {})
        version = entry.get("version", "latest")
        download_url = package.get("downloadUrl") or source.get("downloadUrl")
        if source.get("type") != "path" and not download_url:
            return None
        self.download_cache_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{plugin_name}-{version}-", dir=self.download_cache_dir))
        try:
            if source.get("type") == "path":
                source_path = Path(source.get("path", ""))
                registry_file = Path(entry.get("_registry_file") or self.cached_registry_file())
                if not source_path.is_absolute():
                    source_path = (registry_file.parent / source_path).resolve()
                shutil.copytree(
                    source_path,
                    staging,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "dist", "__pycache__"),
                )
            else:
                archive_path = self.download_cache_dir / f"{plugin_name}-{version}.zip"
                download_file(download_url, archive_path)
                expected_sha256 = self.fetch_package_checksum(package, archive_path)
                if not expected_sha256:
                    archive_path.unlink(missing_ok=True)
                    raise ValueError(f"Missing checksum for {plugin_name}.")
                if self.sha256_file(archive_path) != expected_sha256:
                    archive_path.unlink(missing_ok=True)
                    raise ValueError(f"Checksum verification failed for {plugin_name}.")
                with zipfile.ZipFile(archive_path, "r") as archive:
                    archive.extractall(staging)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return staging

    def install_staged_plugin(self, plugin_name, version, staging_dir, enable=True):
        """Swap a staged package into the plugins folder and record its version."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        target = self.plugins_dir / plugin_name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(staging_dir), str(target))
        state = self.plugin_state()
        plugin_state = dict(state.get(plugin_name, {}))
        plugin_state.update({"enabled": bool(enable), "trusted": True, "version": version})
        state[plugin_name] = plugin_state
        self.save_plugin_state(state)
        self.refresh()
        return True

    def install_plugin_from_registry(self, plugin_name, version=None, enable=True):
        entry = self.registry_entry_for_version(plugin_name, version)
        if not entry:
            return False
        staging = self.stage_plugin_package(plugin_name, entry)
        if staging is None:
            return False
        return self.install_staged_plugin(
            plugin_name, entry.get("version", "latest"), staging, enable=enable
        )

    def rebuild_registry(self, include_entries=True):
        """Rebuild contributions from enabled plugins.

        Python entries that already ran register again from their loaded
        module, so a refresh never drops their commands or panels. With
        include_entries, enabled plugins whose entry has not run yet (or
        changed on disk) are executed.
        """
        self.registry.clear()
        enabled = set()
        for plugin in self.plugins.values():
            if not plugin.enabled:
                continue
            enabled.add(plugin.name)
            self.registry.add_manifest_contributions(plugin, plugin.contributes)
            if include_entries:
                self.activate_plugin(plugin)
            elif self.is_plugin_loaded(plugin):
                self.register_loaded_plugin(plugin)
        for name in list(self.loaded_modules):
            if name not in enabled:
                self.loaded_modules.pop(name, None)
                self._module_fingerprints.pop(name, None)
        return self.registry

    def plugin_entry_fingerprint(self, plugin):
        entry_path = Path(plugin.path) / plugin.entry
        try:
            modified = entry_path.stat().st_mtime_ns
        except OSError:
            modified = None
        return (str(entry_path), plugin.version, modified)

    def is_plugin_loaded(self, plugin):
        return (
            plugin.name in self.loaded_modules
            and self._module_fingerprints.get(plugin.name) == self.plugin_entry_fingerprint(plugin)
        )

    def register_loaded_plugin(self, plugin):
        register = getattr(self.loaded_modules[plugin.name], "register", None)
        if not callable(register):
            return
        try:
            register(PluginAPI(plugin, self.registry))
        except Exception as exc:
            plugin.error = str(exc)

    def activate_enabled_plugins(self):
        return self.rebuild_registry(include_entries=True)

    def activate_plugin(self, plugin):
        if not plugin.entry:
            return
        if plugin.source == "remote" and not plugin.trusted:
            plugin.error = REMOTE_WARNING
            return
        entry_path = Path(plugin.path) / plugin.entry
        if entry_path.suffix != ".py" or not entry_path.exists():
            plugin.error = "Only Python plugin entry files are supported in this version."
            return
        if self.is_plugin_loaded(plugin):
            self.register_loaded_plugin(plugin)
            return
        module_name = f"jottr_plugin_{plugin.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, entry_path)
        if not spec or not spec.loader:
            plugin.error = "Could not load plugin entry."
            return
        module = importlib.util.module_from_spec(spec)
        plugin_root = str(Path(plugin.path).resolve())
        added_plugin_root = plugin_root not in sys.path
        if added_plugin_root:
            sys.path.insert(0, plugin_root)
        try:
            spec.loader.exec_module(module)
            self.loaded_modules[plugin.name] = module
            self._module_fingerprints[plugin.name] = self.plugin_entry_fingerprint(plugin)
            register = getattr(module, "register", None)
            if callable(register):
                register(PluginAPI(plugin, self.registry))
        except Exception as exc:
            plugin.error = str(exc)
            raise
        finally:
            if added_plugin_root:
                try:
                    sys.path.remove(plugin_root)
                except ValueError:
                    pass

    def get_enabled_plugins(self):
        return [plugin for plugin in self.plugins.values() if plugin.enabled]

    def visible_plugins(self, channel_filter=None):
        """Plugins to list for a channel filter; non-registry plugins always show."""
        if channel_filter is None:
            channel_filter = self.plugin_channel_filter()
        return [
            plugin for plugin in self.plugins.values()
            if channel_filter in ("", "all")
            or plugin.source != "registry"
            or plugin.channel_name == channel_filter
        ]

    def is_installed(self, plugin):
        return bool(plugin.path) and self.find_manifest(Path(plugin.path)) is not None

    def is_builtin(self, plugin):
        """Jottr ships this plugin's feature itself, so it works without installing."""
        return plugin.name in DEFAULT_ENABLED_PLUGIN_NAMES

    def installed_registry_version(self, plugin):
        """Registry version installed for a plugin ("" when not installed).

        Uses the version recorded at install time: a package's plugin.json
        version can differ from the registry release it was published as.
        """
        if not self.is_installed(plugin):
            return ""
        return self.plugin_state().get(plugin.name, {}).get("version") or plugin.version

    def needs_registry_install(self, plugin):
        if plugin.source != "registry":
            return False
        if not self.is_installed(plugin):
            return True
        return self.installed_registry_version(plugin) != self.selected_plugin_version(plugin.name)

    def latest_registry_entry(self, plugin_entry):
        """Flattened entry for a catalog entry's latest version (no I/O)."""
        if not plugin_entry:
            return None
        versions = plugin_entry.get("versions", [])
        if not versions:
            return self.flatten_registry_entry(plugin_entry, plugin_entry)
        latest = plugin_entry.get("latestVersion")
        selected = next((item for item in versions if item.get("version") == latest), versions[0])
        return self.flatten_registry_entry(plugin_entry, selected)

    def latest_plugin_version(self, plugin_name):
        entry = self.latest_registry_entry(self.registry_plugins.get(plugin_name))
        return entry.get("version", "") if entry else ""

    def registry_entry_for_version(self, plugin_name, version=None):
        """Flattened entry for a version; None means the selected version."""
        if version is None:
            return self.available_plugins.get(plugin_name)
        plugin_entry = self.registry_plugins.get(plugin_name)
        if not plugin_entry:
            return None
        versions = plugin_entry.get("versions", [])
        if not versions:
            if plugin_entry.get("version") == version:
                return self.flatten_registry_entry(plugin_entry, plugin_entry)
            return None
        selected = next((item for item in versions if item.get("version") == version), None)
        return self.flatten_registry_entry(plugin_entry, selected) if selected else None

    def registry_plugin_entry(self, plugin_name, channel):
        """Catalog entry for a plugin from a channel's cached index (file read only)."""
        registry = self.load_plugin_registry(channel=channel)
        for raw_entry in registry.get("plugins", []):
            if raw_entry.get("id") == plugin_name:
                entry = dict(raw_entry)
                entry["channelName"] = channel.get("name", "")
                entry["channelUrl"] = channel.get("url", "")
                entry["channelVerified"] = bool(channel.get("verified", False))
                entry["_registry_file"] = registry.get("_registry_file", "")
                return entry
        return None

    def available_updates(self):
        """Installed registry plugins whose channel lists a newer release."""
        updates = []
        for plugin in self.plugins.values():
            if plugin.source != "registry" or not self.is_installed(plugin):
                continue
            latest = self.latest_plugin_version(plugin.name)
            if latest and latest != self.installed_registry_version(plugin):
                updates.append(plugin)
        return updates
