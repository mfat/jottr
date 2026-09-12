"""Plugins tab: manage sources/plugins and notify the host on changes."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QComboBox, QGroupBox,
    QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize

from jottr.file_dialogs import get_existing_directory
from jottr.plugin_manager import REMOTE_WARNING
from jottr.translation_manager import _


class PluginsTabMixin:
    """Builds the Plugins tab and its helpers. Expects SettingsDialog host."""

    def create_plugins_tab(self):
        plugins_tab = QWidget()
        plugins_tab.setObjectName("pluginsSettingsTab")
        layout = QVBoxLayout(plugins_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        source_box = QGroupBox(_("Plugin Sources"))
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(12, 10, 12, 12)
        source_layout.setSpacing(8)
        local_layout = QHBoxLayout()
        local_layout.addWidget(QLabel(_("Local plugins folder:")))
        self.plugins_directory_edit = QLineEdit(
            self.settings_manager.get_setting("plugins_directory", self.plugin_manager.plugins_dir)
        )
        self.plugins_directory_edit.editingFinished.connect(self._on_plugins_directory_edited)
        browse_plugins = QPushButton(_("Browse"))
        browse_plugins.clicked.connect(self.browse_plugins_directory)
        local_layout.addWidget(self.plugins_directory_edit, 1)
        local_layout.addWidget(browse_plugins)
        source_layout.addLayout(local_layout)

        self.plugin_channels = self.plugin_manager.plugin_channels()
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(_("Show channel:")))
        self.plugin_channel_filter_combo = QComboBox()
        self.populate_plugin_channel_filter()
        self.plugin_channel_filter_combo.currentIndexChanged.connect(self.change_plugin_channel_filter)
        filter_layout.addWidget(self.plugin_channel_filter_combo, 1)
        update_registry = QPushButton(_("Update Channel(s)"))
        update_registry.clicked.connect(self.update_plugin_registry)
        self.remove_plugin_channel_button = QPushButton(_("Remove Channel"))
        self.remove_plugin_channel_button.clicked.connect(self.remove_plugin_channel)
        filter_layout.addWidget(update_registry)
        filter_layout.addWidget(self.remove_plugin_channel_button)
        source_layout.addLayout(filter_layout)

        registry_layout = QHBoxLayout()
        registry_layout.addWidget(QLabel(_("Add channel:")))
        self.plugin_channel_name_edit = QLineEdit()
        self.plugin_channel_name_edit.setPlaceholderText(_("Name"))
        self.plugin_registry_url_edit = QLineEdit()
        self.plugin_registry_url_edit.setPlaceholderText(self.plugin_manager.registry_url() or _("Channel URL"))
        self.plugin_registry_checksum_url_edit = QLineEdit()
        self.plugin_registry_checksum_url_edit.setPlaceholderText(
            self.plugin_manager.registry_checksum_url() or _("Checksum URL")
        )
        add_channel = QPushButton(_("Add Channel"))
        add_channel.clicked.connect(self.add_plugin_channel)
        registry_layout.addWidget(self.plugin_channel_name_edit, 1)
        registry_layout.addWidget(self.plugin_registry_url_edit, 2)
        registry_layout.addWidget(self.plugin_registry_checksum_url_edit, 2)
        registry_layout.addWidget(add_channel)
        source_layout.addLayout(registry_layout)
        layout.addWidget(source_box)

        manager_frame = QFrame()
        manager_frame.setObjectName("pluginManagerSurface")
        manager_layout = QHBoxLayout(manager_frame)
        manager_layout.setContentsMargins(0, 0, 0, 0)
        manager_layout.setSpacing(12)

        list_panel = QFrame()
        list_panel.setObjectName("pluginListPanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_header = QLabel(_("Plugins"))
        list_header.setObjectName("pluginPanelTitle")
        list_layout.addWidget(list_header)
        self.plugin_list = QListWidget()
        self.plugin_list.setObjectName("pluginCardList")
        self.plugin_list.setSpacing(8)
        self.plugin_list.setUniformItemSizes(False)
        self.plugin_list.currentItemChanged.connect(self.show_plugin_details)
        list_layout.addWidget(self.plugin_list, 1)
        manager_layout.addWidget(list_panel, 2)

        detail_panel = QFrame()
        detail_panel.setObjectName("pluginDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        detail_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.plugin_detail_title = QLabel(_("Select a plugin"))
        self.plugin_detail_title.setObjectName("pluginDetailTitle")
        self.plugin_detail_subtitle = QLabel("")
        self.plugin_detail_subtitle.setObjectName("pluginDetailSubtitle")
        title_stack.addWidget(self.plugin_detail_title)
        title_stack.addWidget(self.plugin_detail_subtitle)
        self.plugin_status_badge = QLabel("")
        self.plugin_status_badge.setObjectName("pluginStatusBadge")
        self.plugin_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addLayout(title_stack, 1)
        title_row.addWidget(self.plugin_status_badge)
        detail_layout.addLayout(title_row)

        self.plugin_details = QLabel()
        self.plugin_details.setObjectName("pluginDetailText")
        self.plugin_details.setWordWrap(True)
        self.plugin_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.plugin_details)

        version_layout = QHBoxLayout()
        version_label = QLabel(_("Version"))
        version_label.setObjectName("pluginFieldLabel")
        self.plugin_version_combo = QComboBox()
        self.plugin_version_combo.currentTextChanged.connect(self.change_selected_plugin_version)
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.plugin_version_combo, 1)
        detail_layout.addLayout(version_layout)

        self.plugin_permissions_label = QLabel()
        self.plugin_permissions_label.setObjectName("pluginPermissions")
        self.plugin_permissions_label.setWordWrap(True)
        self.plugin_permissions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.plugin_permissions_label)
        detail_layout.addStretch()

        plugin_buttons = QHBoxLayout()
        self.toggle_plugin_button = QPushButton(_("Enable"))
        self.update_plugin_button = QPushButton(_("Update"))
        self.remove_plugin_button = QPushButton(_("Remove"))
        self.toggle_plugin_button.clicked.connect(self.toggle_selected_plugin)
        self.update_plugin_button.clicked.connect(self.update_selected_plugin)
        self.remove_plugin_button.clicked.connect(self.remove_selected_plugin)
        plugin_buttons.addWidget(self.toggle_plugin_button)
        plugin_buttons.addWidget(self.update_plugin_button)
        plugin_buttons.addWidget(self.remove_plugin_button)
        detail_layout.addLayout(plugin_buttons)
        manager_layout.addWidget(detail_panel, 3)
        layout.addWidget(manager_frame, 1)

        warning = QLabel(_("Remote plugins require permission review before they can run code."))
        warning.setObjectName("pluginWarningText")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.refresh_plugin_list()
        return plugins_tab

    def _host_plugins_changed(self):
        """Ask the main window to reload plugins from SettingsManager."""
        self._notify("plugins")

    def populate_plugin_channel_filter(self):
        if not hasattr(self, "plugin_channel_filter_combo"):
            return
        current = self.plugin_manager.plugin_channel_filter()
        self.plugin_channel_filter_combo.blockSignals(True)
        self.plugin_channel_filter_combo.clear()
        self.plugin_channel_filter_combo.addItem(_("All channels"), "all")
        for channel in self.plugin_channels:
            label = channel.get("name", "")
            if channel.get("verified"):
                label = f"{label} ✓"
            self.plugin_channel_filter_combo.addItem(label, channel.get("name", ""))
        index = self.plugin_channel_filter_combo.findData(current)
        self.plugin_channel_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.plugin_channel_filter_combo.blockSignals(False)
        self.update_plugin_channel_action_state()

    def selected_plugin_channel(self):
        selected = self.plugin_channel_filter_combo.currentData() if hasattr(self, "plugin_channel_filter_combo") else "all"
        if selected == "all":
            return None
        return next((channel for channel in self.plugin_channels if channel.get("name") == selected), None)

    def update_plugin_channel_action_state(self):
        if not hasattr(self, "remove_plugin_channel_button"):
            return
        channel = self.selected_plugin_channel()
        can_remove = bool(channel and not channel.get("verified"))
        self.remove_plugin_channel_button.setEnabled(can_remove)

    def add_plugin_channel(self):
        url = self.plugin_registry_url_edit.text().strip()
        if not url:
            return
        name = self.plugin_channel_name_edit.text().strip() or url
        channel = self.plugin_manager.normalize_plugin_channel({
            "name": name,
            "url": url,
            "checksumUrl": self.plugin_registry_checksum_url_edit.text().strip(),
            "enabled": True,
        })
        existing = [item for item in self.plugin_channels if item.get("url") != channel["url"]]
        existing.append(channel)
        self.plugin_channels = existing
        self.plugin_manager.save_plugin_channels(self.plugin_channels)
        self.populate_plugin_channel_filter()
        channel_index = self.plugin_channel_filter_combo.findData(channel["name"])
        if channel_index >= 0:
            self.plugin_channel_filter_combo.setCurrentIndex(channel_index)
        self.plugin_manager.refresh()
        self.refresh_plugin_list()
        self._host_plugins_changed()

    def remove_plugin_channel(self):
        channel = self.selected_plugin_channel()
        if not channel or channel.get("verified"):
            self.update_plugin_channel_action_state()
            return
        self.plugin_channels = [
            item for item in self.plugin_channels
            if item.get("name") != channel.get("name") or item.get("url") != channel.get("url")
        ]
        self.plugin_manager.save_plugin_channels(self.plugin_channels)
        self.plugin_manager.set_plugin_channel_filter("all")
        self.populate_plugin_channel_filter()
        self.plugin_manager.refresh()
        self.refresh_plugin_list()
        self._host_plugins_changed()

    def change_plugin_channel_filter(self):
        if not hasattr(self, "plugin_channel_filter_combo"):
            return
        self.plugin_manager.set_plugin_channel_filter(self.plugin_channel_filter_combo.currentData() or "all")
        self.update_plugin_channel_action_state()
        self.plugin_manager.refresh()
        self.refresh_plugin_list()
        # Filter is UI-only for the settings list; host plugin set is unchanged.

    def plugin_source_label(self, plugin):
        if plugin.source == "remote":
            return _("Remote")
        if plugin.source == "registry":
            channel = plugin.channel_name or _("Registry")
            return f"{channel} ✓" if plugin.channel_verified else channel
        return _("Local")

    def plugin_status_label(self, plugin):
        return _("Enabled") if plugin.enabled else _("Disabled")

    def create_plugin_list_card(self, plugin):
        card = QFrame()
        card.setObjectName("pluginCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setProperty("selected", False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(5)

        top_row = QHBoxLayout()
        title = QLabel(plugin.display_name)
        title.setObjectName("pluginCardTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        channel_label = QLabel(self.plugin_source_label(plugin))
        channel_label.setObjectName("pluginCardChannel")
        channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        channel_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        badge = QLabel(self.plugin_status_label(plugin))
        badge.setObjectName("pluginBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top_row.addWidget(title, 1)
        top_row.addWidget(channel_label)
        top_row.addWidget(badge)
        card_layout.addLayout(top_row)

        description = QLabel(plugin.description or plugin.name)
        description.setObjectName("pluginCardDescription")
        description.setWordWrap(True)
        description.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(description)

        meta = QLabel(plugin.version)
        meta.setObjectName("pluginCardMeta")
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(meta)
        card.mousePressEvent = lambda event, name=plugin.name: self.select_plugin_by_name(name)
        return card

    def browse_plugins_directory(self):
        directory = get_existing_directory(
            self,
            _("Choose Plugins Folder"),
            self.plugins_directory_edit.text()
        )
        if directory:
            self.plugins_directory_edit.setText(directory)
            self._apply_plugins_directory(directory)

    def _on_plugins_directory_edited(self):
        directory = self.plugins_directory_edit.text().strip()
        if not directory:
            return
        if str(self.plugin_manager.plugins_dir) == directory:
            return
        self._apply_plugins_directory(directory)

    def _apply_plugins_directory(self, directory):
        self.plugin_manager.set_plugins_directory(directory)
        self.plugin_manager.refresh()
        self.refresh_plugin_list()
        self._host_plugins_changed()

    def update_plugin_registry(self):
        try:
            selected_channel = self.plugin_channel_filter_combo.currentData() or "all"
            self.plugin_manager.save_plugin_channels(self.plugin_channels)
            self.settings_manager.save_setting("plugin_registry_url", self.plugin_registry_url_edit.text().strip())
            self.settings_manager.save_setting("plugin_registry_checksum_url", self.plugin_registry_checksum_url_edit.text().strip())
            self.plugin_manager.update_plugin_registry(channel_name=selected_channel)
            self.plugin_manager.refresh()
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not update plugin index: {error}").format(error=exc))

    def selected_plugin(self):
        current = self.plugin_list.currentItem()
        if not current:
            return None
        return self.plugin_manager.plugins.get(current.data(Qt.ItemDataRole.UserRole))

    def select_plugin_by_name(self, plugin_name):
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == plugin_name:
                self.plugin_list.setCurrentItem(item)
                return

    def update_plugin_card_states(self):
        current_item = self.plugin_list.currentItem()
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            card = self.plugin_list.itemWidget(item)
            if not card:
                continue
            card.setProperty("selected", item is current_item)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()

    def set_plugin_action_state(self, plugin):
        has_plugin = plugin is not None
        self.toggle_plugin_button.setEnabled(has_plugin)
        self.toggle_plugin_button.setText(_("Disable") if has_plugin and plugin.enabled else _("Enable"))
        self.update_plugin_button.setEnabled(has_plugin)
        self.remove_plugin_button.setEnabled(has_plugin)

    def refresh_plugin_list(self):
        current = self.selected_plugin()
        current_name = current.name if current else None
        self.plugin_list.clear()
        for plugin in self.plugin_manager.plugins.values():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            item.setSizeHint(QSize(240, 92))
            self.plugin_list.addItem(item)
            self.plugin_list.setItemWidget(item, self.create_plugin_list_card(plugin))
            if plugin.name == current_name:
                self.plugin_list.setCurrentItem(item)
        if self.plugin_list.count() and not self.plugin_list.currentItem():
            self.plugin_list.setCurrentRow(0)
        self.show_plugin_details(self.plugin_list.currentItem())

    def show_plugin_details(self, current, previous=None):
        self.update_plugin_card_states()
        plugin = self.selected_plugin()
        if not plugin:
            self.plugin_detail_title.setText(_("Select a plugin"))
            self.plugin_detail_subtitle.clear()
            self.plugin_status_badge.clear()
            self.plugin_details.clear()
            self.plugin_permissions_label.clear()
            self.plugin_version_combo.blockSignals(True)
            self.plugin_version_combo.clear()
            self.plugin_version_combo.setEnabled(False)
            self.plugin_version_combo.blockSignals(False)
            self.set_plugin_action_state(None)
            return

        self.plugin_detail_title.setText(plugin.display_name)
        self.plugin_detail_subtitle.setText(f"{self.plugin_source_label(plugin)} · {plugin.name}")
        self.plugin_status_badge.setText(self.plugin_status_label(plugin))
        self.plugin_version_combo.blockSignals(True)
        self.plugin_version_combo.clear()
        versions = self.plugin_manager.plugin_versions(plugin.name)
        self.plugin_version_combo.addItems(versions)
        selected_version = self.plugin_manager.selected_plugin_version(plugin.name) or plugin.version
        if selected_version and selected_version in versions:
            self.plugin_version_combo.setCurrentText(selected_version)
        self.plugin_version_combo.setEnabled(bool(versions))
        self.plugin_version_combo.blockSignals(False)

        source = plugin.source_url or plugin.path
        details = (
            f"{plugin.description}\n"
            f"{_('Installed')}: {plugin.version}\n"
            f"{_('Source')}: {source}"
        )
        if plugin.error:
            details = f"{details}\n{_('Error')}: {plugin.error}"
        self.plugin_details.setText(details)

        permissions = ", ".join(plugin.permissions) if plugin.permissions else _("None")
        remote_note = f"\n{REMOTE_WARNING}" if plugin.source in {"remote", "registry"} and not plugin.trusted else ""
        self.plugin_permissions_label.setText(f"{_('Permissions')}: {permissions}{remote_note}")
        self.set_plugin_action_state(plugin)

    def enable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        trusted = plugin.source in {"local", "registry"}
        if plugin.source == "remote":
            permissions = ", ".join(plugin.permissions) if plugin.permissions else _("None")
            reply = QMessageBox.warning(
                self,
                _("Enable Remote Plugin"),
                _("Enable this remote plugin?\n\nPermissions: {permissions}\n\n{warning}").format(
                    permissions=permissions,
                    warning=REMOTE_WARNING
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            trusted = True
        try:
            self.plugin_manager.set_enabled(plugin.name, True, trusted=trusted)
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except PermissionError as exc:
            QMessageBox.warning(self, _("Plugins"), str(exc))

    def toggle_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        if plugin.enabled:
            self.disable_selected_plugin()
        else:
            self.enable_selected_plugin()

    def change_selected_plugin_version(self, version):
        plugin = self.selected_plugin()
        if not plugin or not version:
            return
        if self.plugin_manager.set_plugin_version(plugin.name, version):
            try:
                self.plugin_manager.install_plugin_from_registry(plugin.name)
            except Exception as exc:
                QMessageBox.warning(self, _("Plugins"), _("Could not install plugin version: {error}").format(error=exc))
            self.refresh_plugin_list()
            self._host_plugins_changed()

    def disable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        self.plugin_manager.set_enabled(plugin.name, False)
        self.sync_plugin_dependent_settings_pages()
        self.refresh_plugin_list()
        self._host_plugins_changed()

    def update_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        try:
            if plugin.source in {"remote", "registry"}:
                self.plugin_manager.update_plugin(plugin.name)
            else:
                self.plugin_manager.refresh()
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not update plugin: {error}").format(error=exc))

    def remove_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        reply = QMessageBox.question(
            self,
            _("Remove Plugin"),
            _("Remove {plugin}?").format(plugin=plugin.display_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.plugin_manager.remove_plugin(plugin.name)
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not remove plugin: {error}").format(error=exc))
