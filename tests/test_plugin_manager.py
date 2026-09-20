import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtWidgets import QApplication, QLabel

from jottr.plugin_manager import PluginManager
from jottr.settings_manager import SettingsManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


def seed_official_plugin_registry(manager):
    registry = {
        "schemaVersion": 1,
        "plugins": [
            {
                "id": "rss-feed",
                "displayName": "RSS Feed Reader",
                "description": "Adds the RSS feed reader tab.",
                "latestVersion": "0.3.1",
                "defaultEnabled": True,
                "versions": [
                    {"version": "0.3.1", "package": {"downloadUrl": "https://example.test/rss-0.3.1.zip", "sha256": "abc"}},
                    {"version": "0.1.0", "package": {"downloadUrl": "https://example.test/rss-0.1.0.zip", "sha256": "abc"}},
                ],
            },
        ],
    }
    channel = manager.official_plugin_channel()
    registry_path = manager.cached_registry_file(channel)
    checksum_path = manager.cached_registry_checksum_file(channel)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    checksum_path.write_text(f"{manager.sha256_file(registry_path)}  plugins.json\n", encoding="utf-8")


class PluginManagerTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        seed_official_plugin_registry(PluginManager(self.settings))

    def write_plugin(self, base, name, manifest=None, entry=None):
        plugin_dir = Path(base) / name
        plugin_dir.mkdir(parents=True)
        data = {
            "name": name,
            "displayName": name.title(),
            "version": "1.0.0",
            "description": "Test plugin",
            "permissions": ["ui.sidebar"],
            "contributes": {
                "uiPanels": [{"id": f"{name}.panel", "title": "Panel", "type": "text"}],
                "commands": [{"id": f"{name}.command", "title": "Command", "message": "Hello"}],
                "toolbarActions": [{"id": f"{name}.toolbar", "title": "Toolbar", "panel": f"{name}.panel"}],
            },
        }
        if manifest:
            data.update(manifest)
        (plugin_dir / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
        if entry:
            (plugin_dir / data["entry"]).write_text(entry, encoding="utf-8")
        return plugin_dir

    def test_discovers_local_manifest_and_registers_enabled_contributions(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        self.write_plugin(plugins_dir, "custom-feed")
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()

        self.assertIn("custom-feed", manager.plugins)
        self.assertFalse(manager.plugins["custom-feed"].enabled)

        manager.set_enabled("custom-feed", True)
        registry = manager.activate_enabled_plugins()

        self.assertEqual(registry.panels[0]["id"], "custom-feed.panel")
        self.assertTrue(any(command["id"] == "custom-feed.command" for command in registry.commands))
        self.assertTrue(any(action.get("panel") == "custom-feed.panel" for action in registry.toolbar_actions))


    def test_plugin_channels_merge_and_filter_registry_entries(self):
        manager = PluginManager(self.settings)
        community = {
            "name": "Community",
            "url": "https://example.test/community/plugins.json",
            "checksumUrl": "",
            "enabled": True,
        }
        self.settings.save_setting("plugin_channels", [manager.official_plugin_channel(), community])

        community_registry = {
            "schemaVersion": 1,
            "plugins": [
                {
                    "id": "community-tool",
                    "displayName": "Community Tool",
                    "description": "From community",
                    "latestVersion": "0.1.0",
                    "versions": [{"version": "0.1.0", "package": {"downloadUrl": "https://example.test/community.zip", "sha256": "abc"}}],
                }
            ],
        }
        channel = manager.normalize_plugin_channel(community)
        registry_file = manager.cached_registry_file(channel)
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        registry_file.write_text(json.dumps(community_registry), encoding="utf-8")

        manager.refresh()

        self.assertIn("rss-feed", manager.plugins)
        self.assertTrue(manager.plugins["rss-feed"].channel_verified)
        self.assertEqual(manager.plugins["rss-feed"].channel_name, "Official")
        self.assertIn("community-tool", manager.plugins)
        self.assertEqual(manager.plugins["community-tool"].channel_name, "Community")
        self.assertFalse(manager.plugins["community-tool"].channel_verified)

        manager.set_plugin_channel_filter("Community")
        manager.refresh()

        # The filter narrows the settings list only; discovery keeps every channel.
        self.assertIn("rss-feed", manager.plugins)
        visible = [plugin.name for plugin in manager.visible_plugins()]
        self.assertIn("community-tool", visible)
        self.assertNotIn("rss-feed", visible)
        self.assertIn("rss-feed", [plugin.name for plugin in manager.visible_plugins("all")])

    def test_refresh_keeps_python_registrations_without_rerunning_entries(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        exec_log = Path(self.temp_dir.name) / "exec.log"
        plugin_dir = self.write_plugin(
            plugins_dir,
            "counter-tool",
            manifest={"entry": "index.py", "contributes": {}},
            entry=(
                f"with open({str(exec_log)!r}, 'a') as log:\n"
                "    log.write('x')\n"
                "def register(api):\n"
                "    api.register_command('counter-tool.run', 'Run', lambda: None)\n"
            ),
        )
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()
        manager.set_enabled("counter-tool", True)
        manager.activate_enabled_plugins()
        self.assertIn("counter-tool.run", manager.registry.command_callbacks)

        manager.refresh()
        self.assertIn("counter-tool.run", manager.registry.command_callbacks)
        manager.activate_enabled_plugins()
        self.assertEqual(exec_log.read_text(encoding="utf-8"), "x")

        # A changed entry file runs again.
        entry = plugin_dir / "index.py"
        stat = entry.stat()
        os.utime(entry, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        manager.activate_enabled_plugins()
        self.assertEqual(exec_log.read_text(encoding="utf-8"), "xx")

        manager.set_enabled("counter-tool", False)
        self.assertNotIn("counter-tool.run", manager.registry.command_callbacks)
        self.assertNotIn("counter-tool", manager.loaded_modules)

    def test_failing_plugin_entry_records_error_without_raising(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        self.write_plugin(
            plugins_dir,
            "broken-tool",
            manifest={"entry": "index.py", "contributes": {}},
            entry="import module_that_does_not_exist\n",
        )
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()
        with patch("traceback.print_exc"):
            manager.set_enabled("broken-tool", True)
            manager.activate_enabled_plugins()

        self.assertIn("module_that_does_not_exist", manager.plugins["broken-tool"].error)
        self.assertNotIn("broken-tool", manager.loaded_modules)

    def test_registry_catalog_entries_are_lightweight_until_manifest_is_available(self):
        manager = PluginManager(self.settings)
        manager.refresh()
        registry = manager.activate_enabled_plugins()

        self.assertEqual(manager.plugins["rss-feed"].source, "registry")
        # defaultEnabled alone does not enable a plugin that is not installed.
        self.assertFalse(manager.plugins["rss-feed"].enabled)
        self.assertEqual(manager.plugins["rss-feed"].permissions, [])
        self.assertEqual(manager.plugins["rss-feed"].contributes, {})
        self.assertFalse(any(action.get("id") == "rss-feed.toolbar" for action in registry.toolbar_actions))
        self.assertEqual(manager.plugin_versions("rss-feed"), ["0.3.1", "0.1.0"])

    def test_registry_plugin_exposes_and_selects_multiple_versions(self):
        plugin_source_v1 = Path(self.temp_dir.name) / "plugin-source-v1"
        plugin_source_v2 = Path(self.temp_dir.name) / "plugin-source-v2"
        self.write_plugin(plugin_source_v1, "versioned-tool", manifest={"version": "0.1.0"})
        self.write_plugin(plugin_source_v2, "versioned-tool", manifest={"version": "0.2.0"})
        registry_file = Path(self.temp_dir.name) / "plugins.json"
        registry = {
            "schemaVersion": 1,
            "plugins": [
                {
                    "id": "versioned-tool",
                    "displayName": "Versioned Tool",
                    "description": "Listed in the catalog",
                    "repository": "https://example.test/versioned-tool",
                    "latestVersion": "0.2.0",
                    "defaultEnabled": False,
                    "versions": [
                        {
                            "version": "0.2.0",
                            "source": {"type": "path", "path": str(plugin_source_v2 / "versioned-tool")},
                        },
                        {
                            "version": "0.1.0",
                            "source": {"type": "path", "path": str(plugin_source_v1 / "versioned-tool")},
                        },
                    ],
                }
            ],
        }
        registry_file.write_text(json.dumps(registry), encoding="utf-8")

        manager = PluginManager(self.settings)
        manager.load_plugin_registry = lambda registry_file_override=None: {**registry, "_registry_file": str(registry_file)}
        manager.refresh()

        self.assertEqual(manager.plugin_versions("versioned-tool"), ["0.2.0", "0.1.0"])
        self.assertEqual(manager.selected_plugin_version("versioned-tool"), "0.2.0")
        self.assertEqual(manager.plugins["versioned-tool"].version, "0.2.0")

        self.assertTrue(manager.set_plugin_version("versioned-tool", "0.1.0"))
        self.assertEqual(manager.selected_plugin_version("versioned-tool"), "0.1.0")
        self.assertEqual(manager.plugins["versioned-tool"].version, "0.1.0")

        # Installing pins 0.1.0; Update moves to the latest release.
        self.assertTrue(manager.install_plugin_from_registry("versioned-tool", "0.1.0"))
        installed = manager.plugins["versioned-tool"]
        self.assertEqual(installed.path, str(manager.plugins_dir / "versioned-tool"))
        # The plugins folder scan must not re-label an installed registry plugin as local.
        self.assertEqual(installed.source, "registry")
        self.assertEqual(manager.installed_registry_version(installed), "0.1.0")
        self.assertEqual([plugin.name for plugin in manager.available_updates()], ["versioned-tool"])
        self.assertFalse(manager.needs_registry_install(installed))

        self.assertTrue(manager.update_plugin("versioned-tool"))
        self.assertEqual(manager.plugins["versioned-tool"].version, "0.2.0")
        self.assertEqual(manager.selected_plugin_version("versioned-tool"), "0.2.0")
        self.assertEqual(manager.available_updates(), [])
        self.assertFalse(manager.update_plugin("versioned-tool"))

        # A failed staging leaves the installed plugin and no staging dirs behind.
        with self.assertRaises(FileNotFoundError):
            manager.stage_plugin_package("versioned-tool", {
                "version": "9.9.9",
                "source": {"type": "path", "path": str(Path(self.temp_dir.name) / "missing")},
            })
        self.assertEqual(manager.plugins["versioned-tool"].version, "0.2.0")
        self.assertEqual(list(manager.download_cache_dir.glob(".versioned-tool-*")), [])

    def test_installed_registry_version_uses_recorded_release_not_manifest(self):
        # The package's plugin.json says 0.0.1 while the registry
        # release is 0.1.0; that must not look outdated forever.
        plugin_source = Path(self.temp_dir.name) / "plugin-source"
        self.write_plugin(plugin_source, "drifting-tool", manifest={"version": "0.0.1"})
        registry_file = Path(self.temp_dir.name) / "plugins.json"
        registry = {
            "schemaVersion": 1,
            "plugins": [{
                "id": "drifting-tool",
                "displayName": "Drifting Tool",
                "latestVersion": "0.1.0",
                "versions": [{
                    "version": "0.1.0",
                    "source": {"type": "path", "path": str(plugin_source / "drifting-tool")},
                }],
            }],
        }
        registry_file.write_text(json.dumps(registry), encoding="utf-8")
        manager = PluginManager(self.settings)
        manager.load_plugin_registry = lambda registry_file_override=None: {**registry, "_registry_file": str(registry_file)}
        manager.refresh()

        self.assertTrue(manager.install_plugin_from_registry("drifting-tool"))
        plugin = manager.plugins["drifting-tool"]
        self.assertEqual(plugin.version, "0.0.1")
        self.assertEqual(manager.installed_registry_version(plugin), "0.1.0")
        self.assertFalse(manager.needs_registry_install(plugin))
        self.assertEqual(manager.available_updates(), [])
        self.assertFalse(manager.update_plugin("drifting-tool"))

    def test_download_file_uses_timeout_and_never_leaves_partial_files(self):
        import io
        import jottr.plugin_manager as plugin_manager_module

        target = Path(self.temp_dir.name) / "cache" / "plugins.json"
        target.parent.mkdir()
        target.write_text("old", encoding="utf-8")

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        with patch("urllib.request.urlopen", return_value=Response(b"new")) as urlopen:
            plugin_manager_module.download_file("https://example.test/plugins.json", target)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], plugin_manager_module.NETWORK_TIMEOUT_SECONDS)
        # Without CA roots every download dies with CERTIFICATE_VERIFY_FAILED.
        self.assertTrue(urlopen.call_args.kwargs["context"].get_ca_certs())
        self.assertEqual(target.read_text(encoding="utf-8"), "new")

        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                plugin_manager_module.download_file("https://example.test/plugins.json", target)
        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        self.assertEqual([path.name for path in target.parent.iterdir()], ["plugins.json"])

    def test_ca_ssl_context_falls_back_to_certifi_when_the_system_store_is_empty(self):
        import ssl
        import certifi
        import jottr.plugin_manager as plugin_manager_module

        # A frozen macOS .app ships no system CA store, so the default context
        # comes up empty; certifi's bundle has to fill in.
        empty = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(empty.get_ca_certs(), [])
        with patch("ssl.create_default_context", return_value=empty):
            context = plugin_manager_module.ca_ssl_context()
        self.assertIs(context, empty)
        self.assertTrue(context.get_ca_certs())

        # A system store with roots is left alone, so SSL_CERT_FILE and
        # distro or corporate CAs keep working.
        loaded = ssl.create_default_context(cafile=certifi.where())
        with patch("ssl.create_default_context", return_value=loaded) as create:
            self.assertIs(plugin_manager_module.ca_ssl_context(), loaded)
        create.assert_called_once_with()

    def test_registry_source_reads_permissions_and_contributions_from_plugin_json(self):
        plugin_source = Path(self.temp_dir.name) / "plugin-source"
        self.write_plugin(plugin_source, "catalog-tool")
        registry_file = Path(self.temp_dir.name) / "plugins.json"
        registry = {
            "schemaVersion": 1,
            "plugins": [
                {
                    "id": "catalog-tool",
                    "displayName": "Catalog Tool",
                    "description": "Listed in the catalog",
                    "repository": "https://example.test/catalog-tool",
                    "latestVersion": "1.0.0",
                    "defaultEnabled": True,
                    "versions": [
                        {
                            "version": "1.0.0",
                            "source": {"type": "path", "path": str(plugin_source / "catalog-tool")},
                        }
                    ],
                }
            ],
        }
        registry_file.write_text(json.dumps(registry), encoding="utf-8")

        manager = PluginManager(self.settings)
        manager.load_plugin_registry = lambda registry_file_override=None: {**registry, "_registry_file": str(registry_file)}
        manager.refresh()
        active = manager.plugins["catalog-tool"]

        self.assertEqual(active.permissions, ["ui.sidebar"])
        self.assertEqual(active.description, "Test plugin")
        self.assertTrue(active.enabled)
        self.assertTrue(any(panel["id"] == "catalog-tool.panel" for panel in manager.registry.panels))

    def test_remote_plugins_require_trust_before_enable(self):
        manager = PluginManager(self.settings)
        remote_url = "https://example.test/jottr-plugins.git"
        cache_plugins = manager.source_cache_path(remote_url) / "plugins"
        self.write_plugin(cache_plugins, "remote-tool")
        manager.add_remote_source(remote_url)
        manager.refresh()

        with self.assertRaises(PermissionError):
            manager.set_enabled("remote-tool", True)

        plugin = manager.set_enabled("remote-tool", True, trusted=True)

        self.assertTrue(plugin.enabled)
        self.assertTrue(plugin.trusted)
        self.assertEqual(plugin.source, "remote")

    def test_runtime_contributions_replace_manifest_contributions_by_id(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        self.write_plugin(
            plugins_dir,
            "duplicate-tool",
            manifest={
                "entry": "index.py",
                "contributes": {
                    "uiPanels": [{"id": "duplicate-tool.panel", "title": "Manifest Panel", "type": "python"}],
                    "commands": [{"id": "duplicate-tool.command", "title": "Manifest Command"}],
                    "toolbarActions": [{"id": "duplicate-tool.toolbar", "title": "Manifest Toolbar"}],
                },
            },
            entry=(
                "from PyQt6.QtWidgets import QLabel\n"
                "def register(api):\n"
                "    api.register_panel('duplicate-tool.panel', 'Runtime Panel', lambda: QLabel('runtime'))\n"
                "    api.register_command('duplicate-tool.command', 'Runtime Command', lambda: None)\n"
                "    api.register_toolbar_action({'id': 'duplicate-tool.toolbar', 'title': 'Runtime Toolbar'})\n"
            ),
        )
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()
        manager.set_enabled("duplicate-tool", True)
        registry = manager.activate_enabled_plugins()

        self.assertEqual([panel["id"] for panel in registry.panels], ["duplicate-tool.panel"])
        self.assertEqual(registry.panels[0]["title"], "Runtime Panel")
        self.assertEqual([command["id"] for command in registry.commands], ["duplicate-tool.command"])
        self.assertEqual(registry.commands[0]["title"], "Runtime Command")
        self.assertEqual([action["id"] for action in registry.toolbar_actions], ["duplicate-tool.toolbar"])
        self.assertEqual(registry.toolbar_actions[0]["title"], "Runtime Toolbar")
        self.assertIn("duplicate-tool.command", registry.command_callbacks)

    def test_python_entry_can_import_package_from_plugin_root(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        plugin_dir = self.write_plugin(
            plugins_dir,
            "package-tool",
            manifest={
                "entry": "index.py",
                "permissions": ["ui.panel"],
                "contributes": {},
            },
            entry=(
                "from package_tool.panel import make_label\n"
                "def register(api):\n"
                "    api.register_panel('package-tool.panel', 'Package Panel', make_label)\n"
            ),
        )
        package_dir = plugin_dir / "package_tool"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "panel.py").write_text(
            "from PyQt6.QtWidgets import QLabel\n"
            "def make_label():\n"
            "    return QLabel('from package')\n",
            encoding="utf-8",
        )
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()
        manager.set_enabled("package-tool", True)
        registry = manager.activate_enabled_plugins()

        self.assertIsInstance(registry.panel_factories["package-tool.panel"](), QLabel)
        self.assertFalse(any(str(plugin_dir) == item for item in sys.path))

    def test_python_entry_uses_narrow_plugin_api(self):
        plugins_dir = Path(self.temp_dir.name) / "plugins"
        self.write_plugin(
            plugins_dir,
            "python-tool",
            manifest={
                "entry": "index.py",
                "permissions": ["ui.panel"],
                "contributes": {},
            },
            entry=(
                "from PyQt6.QtWidgets import QLabel\n"
                "def register(api):\n"
                "    api.register_command('python-tool.hello', 'Hello', lambda: None)\n"
                "    api.register_panel('python-tool.panel', 'Python Panel', lambda: QLabel('plugin'))\n"
                "    api.register_toolbar_action({'id': 'python-tool.toolbar', 'title': 'Tool'})\n"
                "    api.register_sidebar_item({'id': 'python-tool.sidebar', 'title': 'Side'})\n"
                "    api.register_editor_extension({'id': 'python-tool.editor'})\n"
                "    api.register_background_service({'id': 'python-tool.service'})\n"
            ),
        )
        self.settings.save_setting("plugins_directory", str(plugins_dir))

        manager = PluginManager(self.settings)
        manager.refresh()
        manager.set_enabled("python-tool", True)
        registry = manager.activate_enabled_plugins()

        self.assertIn("python-tool.hello", registry.command_callbacks)
        self.assertIsInstance(registry.panel_factories["python-tool.panel"](), QLabel)
        self.assertTrue(any(action["id"] == "python-tool.toolbar" for action in registry.toolbar_actions))
        self.assertTrue(any(item["id"] == "python-tool.sidebar" for item in registry.sidebar_items))
        self.assertTrue(any(extension["id"] == "python-tool.editor" for extension in registry.editor_extensions))
        self.assertTrue(any(service["id"] == "python-tool.service" for service in registry.background_services))


if __name__ == "__main__":
    unittest.main()
