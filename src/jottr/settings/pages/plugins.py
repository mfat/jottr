"""Plugins tab: manage sources/plugins and notify the host on changes.

Network and disk-heavy work (channel indexes, package downloads, git pulls)
runs on a worker thread so the app stays responsive; results are applied to
the shared PluginManager back on the GUI thread.
"""
import copy
import threading

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QComboBox, QFrame, QMessageBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPalette

from jottr.file_dialogs import get_existing_directory
from jottr.icon_manager import themed_symbolic_icon
from jottr.plugin_manager import REMOTE_WARNING
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _

from ..plugin_widgets import PLUGIN_CARD_ROLE, PluginAvatar, PluginCardDelegate, plugin_initial
from ..widgets import SegmentedControl


class _PluginTaskBridge(QObject):
    """Hands a worker thread's result to a callback on the GUI thread."""

    finished = pyqtSignal(object, object)

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self.finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    @pyqtSlot(object, object)
    def _deliver(self, result, error):
        try:
            self._callback(result, error)
        finally:
            self.deleteLater()


class PluginsTabMixin:
    """Builds the Plugins tab and its helpers. Expects SettingsDialog host."""

    def plugin_chrome_tokens(self):
        """Chrome colors the plugin cards and avatars are painted in."""
        return ThemeManager.chrome_tokens(
            ThemeManager.get_ui_theme(self.settings_manager.get_ui_theme())
        )

    def plugin_icon(self, name):
        return themed_symbolic_icon(name, self.settings_manager, size=16, palette=self.palette())

    def create_plugins_tab(self):
        plugins_tab = QWidget()
        plugins_tab.setObjectName("pluginsSettingsTab")
        layout = QVBoxLayout(plugins_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Beside the page title: the local plugins folder.
        self.plugins_header = QWidget()
        header_layout = QHBoxLayout(self.plugins_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        self.plugins_directory_edit = QLineEdit(
            self.settings_manager.get_setting("plugins_directory", self.plugin_manager.plugins_dir)
        )
        self.plugins_directory_edit.setObjectName("pluginFolderField")
        self.plugins_directory_edit.setToolTip(_("Local plugins folder"))
        self.plugins_directory_edit.setMinimumWidth(220)
        self.plugins_directory_edit.setMaximumWidth(340)
        self.plugins_folder_action = self.plugins_directory_edit.addAction(
            self.plugin_icon("folder"), QLineEdit.ActionPosition.LeadingPosition
        )
        # Long paths show their start, like the design's elided folder pill.
        self.plugins_directory_edit.setCursorPosition(0)
        self.plugins_directory_edit.editingFinished.connect(self._on_plugins_directory_edited)
        self.browse_plugins_button = QPushButton(_("Browse"))
        self.browse_plugins_button.setObjectName("pluginBrowseButton")
        self.browse_plugins_button.clicked.connect(self.browse_plugins_directory)
        header_layout.addWidget(self.plugins_directory_edit)
        header_layout.addWidget(self.browse_plugins_button)

        # Channels: which to show, refresh their indexes, add or remove one.
        self.plugin_channels = self.plugin_manager.plugin_channels()
        channel_row = QHBoxLayout()
        channel_row.setSpacing(8)
        self.plugin_channel_filter_control = SegmentedControl()
        self.populate_plugin_channel_filter()
        self.plugin_channel_filter_control.currentDataChanged.connect(
            self.change_plugin_channel_filter
        )
        channel_row.addWidget(self.plugin_channel_filter_control)
        self.update_registry_button = QPushButton(_("Update channels"))
        self.update_registry_button.setObjectName("pluginChannelAction")
        self.update_registry_button.setIcon(self.plugin_icon("view-refresh"))
        self.update_registry_button.clicked.connect(self.update_plugin_registry)
        self.remove_plugin_channel_button = QPushButton(_("Remove channel"))
        self.remove_plugin_channel_button.setObjectName("pluginChannelAction")
        self.remove_plugin_channel_button.clicked.connect(self.remove_plugin_channel)
        channel_row.addWidget(self.update_registry_button)
        channel_row.addWidget(self.remove_plugin_channel_button)
        channel_row.addStretch(1)
        self.show_add_channel_button = QPushButton(_("Add channel"))
        self.show_add_channel_button.setObjectName("pluginAddChannelButton")
        self.show_add_channel_button.setIcon(self.plugin_icon("list-add"))
        self.show_add_channel_button.setCheckable(True)
        self.show_add_channel_button.toggled.connect(self._on_show_add_channel)
        channel_row.addWidget(self.show_add_channel_button)
        layout.addLayout(channel_row)
        self.update_plugin_channel_action_state()

        # Add channel: revealed by its button.
        self.add_channel_form = QWidget()
        self.add_channel_form.setObjectName("pluginAddChannelForm")
        form_layout = QHBoxLayout(self.add_channel_form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)
        self.plugin_channel_name_edit = QLineEdit()
        self.plugin_channel_name_edit.setPlaceholderText(_("Name"))
        self.plugin_registry_url_edit = QLineEdit()
        self.plugin_registry_url_edit.setPlaceholderText(self.plugin_manager.registry_url() or _("Channel URL"))
        self.plugin_registry_checksum_url_edit = QLineEdit()
        self.plugin_registry_checksum_url_edit.setPlaceholderText(
            self.plugin_manager.registry_checksum_url() or _("Checksum URL")
        )
        self.add_plugin_channel_button = QPushButton(_("Add"))
        self.add_plugin_channel_button.setProperty("primary", True)
        self.add_plugin_channel_button.clicked.connect(self.add_plugin_channel)
        form_layout.addWidget(self.plugin_channel_name_edit, 1)
        form_layout.addWidget(self.plugin_registry_url_edit, 2)
        form_layout.addWidget(self.plugin_registry_checksum_url_edit, 2)
        form_layout.addWidget(self.add_plugin_channel_button)
        self.add_channel_form.hide()
        layout.addWidget(self.add_channel_form)

        body = QHBoxLayout()
        body.setSpacing(14)

        # The plugin list, with a search field above it.
        list_panel = QVBoxLayout()
        list_panel.setSpacing(8)
        self.plugin_search_edit = QLineEdit()
        self.plugin_search_edit.setObjectName("pluginSearchField")
        self.plugin_search_edit.setClearButtonEnabled(True)
        self.plugin_search_action = self.plugin_search_edit.addAction(
            self.plugin_icon("find"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.plugin_search_edit.textChanged.connect(self.filter_plugin_list)
        list_panel.addWidget(self.plugin_search_edit)
        self.plugin_list = QListWidget()
        self.plugin_list.setObjectName("pluginCardList")
        self.plugin_list.setMinimumWidth(220)
        self.plugin_list.setSpacing(2)
        self.plugin_list.setUniformItemSizes(False)
        self.plugin_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.plugin_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plugin_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.plugin_list.setMouseTracking(True)
        self.plugin_list.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.plugin_list.setItemDelegate(
            PluginCardDelegate(self.plugin_list, self.plugin_chrome_tokens)
        )
        self.plugin_list.currentItemChanged.connect(self.show_plugin_details)
        list_panel.addWidget(self.plugin_list, 1)
        body.addLayout(list_panel, 5)

        # The selected plugin.
        detail_panel = QFrame()
        detail_panel.setObjectName("pluginDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(22, 20, 22, 20)
        detail_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        self.plugin_detail_avatar = PluginAvatar(52, self.plugin_chrome_tokens)
        title_row.addWidget(self.plugin_detail_avatar, 0, Qt.AlignmentFlag.AlignTop)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.plugin_detail_title = QLabel(_("Select a plugin"))
        self.plugin_detail_title.setObjectName("pluginDetailTitle")
        self.plugin_detail_title.setWordWrap(True)
        self.plugin_detail_subtitle = QLabel("")
        self.plugin_detail_subtitle.setObjectName("pluginDetailSubtitle")
        self.plugin_detail_subtitle.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        title_stack.addWidget(self.plugin_detail_title)
        title_stack.addWidget(self.plugin_detail_subtitle)
        title_row.addLayout(title_stack, 1)
        self.plugin_status_badge = QLabel("")
        self.plugin_status_badge.setObjectName("pluginStatusBadge")
        self.plugin_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self.plugin_status_badge, 0, Qt.AlignmentFlag.AlignTop)
        detail_layout.addLayout(title_row)

        self.plugin_details = QLabel()
        self.plugin_details.setObjectName("pluginDetailText")
        self.plugin_details.setWordWrap(True)
        self.plugin_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.plugin_details)

        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(10)
        fields.setColumnStretch(1, 1)
        version_row = QHBoxLayout()
        version_row.setSpacing(10)
        self.plugin_version_combo = QComboBox()
        self.plugin_version_combo.setMinimumWidth(120)
        self.plugin_version_combo.currentTextChanged.connect(self.change_selected_plugin_version)
        self.plugin_version_note = QLabel("")
        self.plugin_version_note.setObjectName("pluginFieldLabel")
        self.plugin_version_note.setWordWrap(True)
        self.plugin_version_note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        version_row.addWidget(self.plugin_version_combo)
        version_row.addWidget(self.plugin_version_note, 1)
        self.plugin_source_value = QLabel("")
        self.plugin_source_value.setObjectName("pluginSourceValue")
        self.plugin_source_value.setWordWrap(True)
        self.plugin_source_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.plugin_permission_chips = QHBoxLayout()
        self.plugin_permission_chips.setSpacing(6)
        permissions_widget = QWidget()
        permissions_widget.setLayout(self.plugin_permission_chips)
        self.plugin_permission_chips.setContentsMargins(0, 0, 0, 0)
        for row, (label, field) in enumerate((
            (_("Version"), version_row),
            (_("Source"), self.plugin_source_value),
            (_("Permissions"), permissions_widget),
        )):
            title = QLabel(label)
            title.setObjectName("pluginFieldLabel")
            title.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            fields.addWidget(title, row, 0, Qt.AlignmentFlag.AlignVCenter)
            if isinstance(field, QHBoxLayout):
                fields.addLayout(field, row, 1)
            else:
                fields.addWidget(field, row, 1)
        detail_layout.addLayout(fields)

        # Kept for callers that read one line of permissions and the remote note.
        self.plugin_permissions_label = QLabel()
        self.plugin_permissions_label.setObjectName("pluginPermissions")
        self.plugin_permissions_label.setWordWrap(True)
        self.plugin_permissions_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        detail_layout.addWidget(self.plugin_permissions_label)
        detail_layout.addStretch()

        plugin_buttons = QHBoxLayout()
        plugin_buttons.setSpacing(8)
        self.toggle_plugin_button = QPushButton(_("Enable"))
        self.update_plugin_button = QPushButton(_("Update"))
        self.remove_plugin_button = QPushButton(_("Remove"))
        self.remove_plugin_button.setObjectName("pluginRemoveButton")
        self.remove_plugin_button.setIcon(self.plugin_icon("user-trash"))
        self.toggle_plugin_button.clicked.connect(self.toggle_selected_plugin)
        self.update_plugin_button.clicked.connect(self.update_selected_plugin)
        self.remove_plugin_button.clicked.connect(self.remove_selected_plugin)
        # A row of actions: regular-size buttons, not pills.
        for button in (
            self.toggle_plugin_button, self.update_plugin_button,
            self.show_add_channel_button, self.add_plugin_channel_button,
        ):
            button.setProperty("compact", True)
        plugin_buttons.addWidget(self.update_plugin_button)
        plugin_buttons.addWidget(self.toggle_plugin_button)
        plugin_buttons.addStretch(1)
        plugin_buttons.addWidget(self.remove_plugin_button)
        detail_layout.addLayout(plugin_buttons)
        body.addWidget(detail_panel, 6)
        layout.addLayout(body, 1)

        # Status of the last plugin task, and the remote-code warning.
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.plugin_status_dot = QWidget()
        self.plugin_status_dot.setObjectName("pluginStatusDot")
        self.plugin_status_dot.setFixedSize(8, 8)
        self.plugin_task_progress = QProgressBar()
        self.plugin_task_progress.setObjectName("pluginTaskProgress")
        self.plugin_task_progress.setRange(0, 0)
        self.plugin_task_progress.setTextVisible(False)
        self.plugin_task_progress.setMaximumWidth(120)
        self.plugin_task_progress.hide()
        self.plugin_task_status = QLabel("")
        self.plugin_task_status.setObjectName("pluginTaskStatus")
        self.plugin_task_status.setWordWrap(True)
        self.plugin_task_status.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        warning = QLabel(_("Remote plugins require permission review before they can run code."))
        warning.setObjectName("pluginWarningText")
        warning.setWordWrap(True)
        warning.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        status_row.addWidget(self.plugin_status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.plugin_task_progress)
        status_row.addWidget(self.plugin_task_status, 1)
        status_row.addWidget(warning, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(status_row)
        self.plugin_task_status_changed()
        self.refresh_plugin_list()
        return plugins_tab

    def refresh_plugin_page_colors(self):
        """Repaint the painted parts and retint icons after a theme change."""
        self.plugin_list.viewport().update()
        self.plugin_detail_avatar.update()
        self.plugins_folder_action.setIcon(self.plugin_icon("folder"))
        self.plugin_search_action.setIcon(self.plugin_icon("find"))
        self.update_registry_button.setIcon(self.plugin_icon("view-refresh"))
        self.show_add_channel_button.setIcon(self.plugin_icon("list-add"))
        self.remove_plugin_button.setIcon(self.plugin_icon("user-trash"))

    def _on_show_add_channel(self, shown):
        self.add_channel_form.setVisible(shown)
        if shown:
            self.plugin_channel_name_edit.setFocus()

    def _host_plugins_changed(self):
        """Ask the main window to reload plugins from SettingsManager."""
        self._notify("plugins")

    # Background plugin tasks.

    def plugin_task_running(self):
        return getattr(self, "_plugin_task", None) is not None

    def run_plugin_task(self, busy_text, work, apply, error_text):
        """Run ``work`` on a worker thread, then ``apply`` its result here.

        ``work`` may only do network/disk I/O: no widgets and no shared
        PluginManager state. ``apply(result)`` runs on the GUI thread, even if
        Settings was closed meanwhile, and returns ``(message, changed)``.
        ``error_text`` is formatted with ``{error}`` when either step fails.
        """
        if self.plugin_task_running():
            return False
        host = self.host
        bridge = _PluginTaskBridge(
            lambda result, error: self._finish_plugin_task(host, apply, error_text, result, error),
            host if host is not None else self,
        )
        self._plugin_task = bridge
        self.set_plugin_busy(True, busy_text)

        def run():
            result = error = None
            try:
                result = work()
            except Exception as exc:
                error = exc
            try:
                bridge.finished.emit(result, error)
            except RuntimeError:
                pass  # The owning window was destroyed.

        threading.Thread(target=run, name="jottr-plugin-task", daemon=True).start()
        return True

    def _finish_plugin_task(self, host, apply, error_text, result, error):
        self._plugin_task = None
        message, changed = "", False
        if error is None:
            try:
                message, changed = apply(result)
            except Exception as exc:
                error = exc
        if error is not None:
            message = error_text.format(error=error)

        if sip.isdeleted(self):
            # Settings closed mid-task: still apply to the app and report there.
            if changed and host is not None:
                host.apply_settings_domain("plugins")
            status_bar = getattr(host, "statusBar", None)
            if message and hasattr(status_bar, "showMessage"):
                status_bar.showMessage(message, 8000)
            return

        self.set_plugin_busy(False)
        self.refresh_plugin_list()
        if changed:
            self._host_plugins_changed()
        if error is not None:
            self.plugin_task_status.clear()
            QMessageBox.warning(self, _("Plugins"), message)
        else:
            self.plugin_task_status.setText(message)
        self.plugin_task_status_changed()

    def plugin_task_status_changed(self):
        # The dot marks a status line with something in it.
        self.plugin_status_dot.setVisible(bool(self.plugin_task_status.text()))

    def set_plugin_busy(self, busy, text=""):
        for widget in (
            self.plugins_directory_edit,
            self.browse_plugins_button,
            self.plugin_channel_filter_control,
            self.update_registry_button,
            self.show_add_channel_button,
            self.plugin_channel_name_edit,
            self.plugin_registry_url_edit,
            self.plugin_registry_checksum_url_edit,
            self.add_plugin_channel_button,
        ):
            widget.setEnabled(not busy)
        self.plugin_task_progress.setVisible(busy)
        self.plugin_task_status.setText(text)
        self.plugin_task_status_changed()
        self.update_plugin_channel_action_state()
        self.set_plugin_action_state(self.selected_plugin())
        self.plugin_version_combo.setEnabled(not busy and self.plugin_version_combo.count() > 0)

    def populate_plugin_channel_filter(self):
        if not hasattr(self, "plugin_channel_filter_control"):
            return
        current = self.plugin_manager.plugin_channel_filter()
        control = self.plugin_channel_filter_control
        control.blockSignals(True)
        control.clear()
        control.addOption(_("All channels"), "all")
        for channel in self.plugin_channels:
            label = channel.get("name", "")
            if channel.get("verified"):
                label = f"{label} ✓"
            control.addOption(label, channel.get("name", ""))
        index = control.findData(current)
        control.setCurrentIndex(index if index >= 0 else 0)
        control.blockSignals(False)
        self.update_plugin_channel_action_state()

    def selected_plugin_channel(self):
        selected = (
            self.plugin_channel_filter_control.currentData()
            if hasattr(self, "plugin_channel_filter_control") else "all"
        )
        if selected == "all":
            return None
        return next((channel for channel in self.plugin_channels if channel.get("name") == selected), None)

    def update_plugin_channel_action_state(self):
        if not hasattr(self, "remove_plugin_channel_button"):
            return
        channel = self.selected_plugin_channel()
        can_remove = bool(channel and not channel.get("verified")) and not self.plugin_task_running()
        self.remove_plugin_channel_button.setEnabled(can_remove)
        # Only a removable channel offers removal at all.
        self.remove_plugin_channel_button.setVisible(bool(channel and not channel.get("verified")))

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
        control = self.plugin_channel_filter_control
        channel_index = control.findData(channel["name"])
        if channel_index >= 0:
            control.blockSignals(True)
            control.setCurrentIndex(channel_index)
            control.blockSignals(False)
            self.plugin_manager.set_plugin_channel_filter(channel["name"])
            self.update_plugin_channel_action_state()
        self.show_add_channel_button.setChecked(False)
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
        if not hasattr(self, "plugin_channel_filter_control"):
            return
        self.plugin_manager.set_plugin_channel_filter(
            self.plugin_channel_filter_control.currentData() or "all"
        )
        self.update_plugin_channel_action_state()
        # The filter only narrows this list; the app's plugin set is unchanged.
        self.refresh_plugin_list()

    def plugin_source_label(self, plugin):
        if plugin.source == "remote":
            return _("Remote")
        if plugin.source == "registry":
            channel = plugin.channel_name or _("Registry")
            return f"{channel} ✓" if plugin.channel_verified else channel
        return _("Local")

    def plugin_status_label(self, plugin):
        if plugin.error:
            return _("Error")
        if plugin.enabled:
            return _("Enabled")
        if not self.plugin_manager.is_installed(plugin):
            return _("Not installed")
        return _("Disabled")

    def plugin_card_data(self, plugin):
        """What a plugin's card in the list shows."""
        if plugin.error:
            kind = "error"
        elif plugin.enabled:
            kind = "enabled"
        else:
            kind = "idle"
        meta = " · ".join(
            part for part in (plugin.version, self.plugin_source_label(plugin)) if part
        )
        return {
            "title": plugin.display_name,
            "status": self.plugin_status_label(plugin),
            "status_kind": kind,
            "description": plugin.description or plugin.name,
            "meta": meta,
            "initial": plugin_initial(plugin.display_name),
        }

    def filter_plugin_list(self, query=None):
        """Show only plugins whose name or description contains the search text."""
        query = (self.plugin_search_edit.text() if query is None else query).strip().casefold()
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            card = item.data(PLUGIN_CARD_ROLE) or {}
            haystack = f"{card.get('title', '')} {card.get('description', '')}".casefold()
            item.setHidden(bool(query) and query not in haystack)

    def browse_plugins_directory(self):
        directory = get_existing_directory(
            self,
            _("Choose Plugins Folder"),
            self.plugins_directory_edit.text()
        )
        if directory:
            self.plugins_directory_edit.setText(directory)
            self.plugins_directory_edit.setCursorPosition(0)
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
        if self.plugin_task_running():
            return
        manager = self.plugin_manager
        selected_channel = self.plugin_channel_filter_control.currentData() or "all"
        manager.save_plugin_channels(self.plugin_channels)
        self.settings_manager.save_setting("plugin_registry_url", self.plugin_registry_url_edit.text().strip())
        self.settings_manager.save_setting("plugin_registry_checksum_url", self.plugin_registry_checksum_url_edit.text().strip())
        channels = manager.plugin_channels_to_update(channel_name=selected_channel)
        if not channels:
            self.plugin_task_status.setText(_("No plugin channels to update."))
            self.plugin_task_status_changed()
            return
        legacy_url = manager.registry_url()

        def apply(_result):
            manager.refresh()
            updates = manager.available_updates()
            if updates:
                names = ", ".join(plugin.display_name for plugin in updates)
                return _("Plugin index updated. Updates available: {plugins}.").format(plugins=names), True
            return _("Plugin index updated. All installed plugins are up to date."), True

        self.run_plugin_task(
            _("Updating plugin channels…"),
            lambda: manager.download_plugin_registries(channels, legacy_url=legacy_url),
            apply,
            _("Could not update plugin index: {error}"),
        )

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

    def plugin_has_update(self, plugin):
        try:
            return any(item.name == plugin.name for item in self.plugin_manager.available_updates())
        except Exception:
            return False

    def set_plugin_action_state(self, plugin):
        has_plugin = plugin is not None
        actionable = has_plugin and not self.plugin_task_running()
        installed = has_plugin and self.plugin_manager.is_installed(plugin)
        self.toggle_plugin_button.setEnabled(actionable)
        if has_plugin and plugin.enabled:
            self.toggle_plugin_button.setText(_("Disable"))
        elif has_plugin and not installed:
            self.toggle_plugin_button.setText(_("Install"))
        else:
            self.toggle_plugin_button.setText(_("Enable"))
        # Nothing to update or remove until the plugin is installed.
        self.update_plugin_button.setEnabled(actionable and installed)
        self.remove_plugin_button.setEnabled(actionable and installed)
        # The action the plugin most likely needs next is the filled one: an
        # available update, else installing or enabling it.
        update_first = installed and self.plugin_has_update(plugin)
        self.update_plugin_button.setVisible(installed)
        self._set_primary(self.update_plugin_button, update_first)
        self._set_primary(
            self.toggle_plugin_button,
            has_plugin and not update_first and not plugin.enabled,
        )

    def _set_primary(self, button, primary):
        if bool(button.property("primary")) == bool(primary):
            return
        button.setProperty("primary", bool(primary))
        button.style().unpolish(button)
        button.style().polish(button)

    def refresh_plugin_list(self):
        current = self.selected_plugin()
        current_name = current.name if current else None
        self.plugin_list.clear()
        plugins = self.plugin_manager.visible_plugins()
        for plugin in plugins:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            item.setData(PLUGIN_CARD_ROLE, self.plugin_card_data(plugin))
            item.setToolTip(plugin.display_name)
            self.plugin_list.addItem(item)
            if plugin.name == current_name:
                self.plugin_list.setCurrentItem(item)
        self.plugin_search_edit.setPlaceholderText(
            _("Search {count} plugins").format(count=len(plugins))
        )
        self.filter_plugin_list()
        if self.plugin_list.count() and not self.plugin_list.currentItem():
            self.plugin_list.setCurrentRow(0)
        self.show_plugin_details(self.plugin_list.currentItem())

    def set_plugin_permission_chips(self, permissions, none_label=True):
        """One chip per permission; *none_label* says "None" when there are none."""
        while self.plugin_permission_chips.count():
            widget = self.plugin_permission_chips.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for permission in permissions or ([_("None")] if none_label else []):
            chip = QLabel(permission)
            chip.setObjectName("pluginPermissionChip" if permissions else "pluginSourceValue")
            chip.setFont(self.font())
            self.plugin_permission_chips.addWidget(chip)
        self.plugin_permission_chips.addStretch(1)

    def show_plugin_details(self, current, previous=None):
        plugin = self.selected_plugin()
        if not plugin:
            self.plugin_detail_avatar.set_initial("")
            self.plugin_detail_title.setText(_("Select a plugin"))
            self.plugin_detail_subtitle.clear()
            self.plugin_status_badge.clear()
            self.plugin_status_badge.hide()
            self.plugin_details.clear()
            self.plugin_version_note.clear()
            self.plugin_source_value.clear()
            # No plugin, no permissions to report.
            self.set_plugin_permission_chips([], none_label=False)
            self.plugin_permissions_label.clear()
            self.plugin_permissions_label.hide()
            self.plugin_version_combo.blockSignals(True)
            self.plugin_version_combo.clear()
            self.plugin_version_combo.setEnabled(False)
            self.plugin_version_combo.blockSignals(False)
            self.set_plugin_action_state(None)
            return

        self.plugin_detail_avatar.set_initial(plugin_initial(plugin.display_name))
        self.plugin_detail_title.setText(plugin.display_name)
        self.plugin_detail_subtitle.setText(f"{self.plugin_source_label(plugin)} · {plugin.name}")
        self.plugin_status_badge.setText(self.plugin_status_label(plugin))
        self.plugin_status_badge.setProperty("kind", self.plugin_card_data(plugin)["status_kind"])
        self.plugin_status_badge.style().unpolish(self.plugin_status_badge)
        self.plugin_status_badge.style().polish(self.plugin_status_badge)
        self.plugin_status_badge.show()
        self.plugin_version_combo.blockSignals(True)
        self.plugin_version_combo.clear()
        versions = self.plugin_manager.plugin_versions(plugin.name)
        self.plugin_version_combo.addItems(versions)
        selected_version = self.plugin_manager.selected_plugin_version(plugin.name) or plugin.version
        if selected_version and selected_version in versions:
            self.plugin_version_combo.setCurrentText(selected_version)
        self.plugin_version_combo.setEnabled(bool(versions) and not self.plugin_task_running())
        self.plugin_version_combo.blockSignals(False)

        version_label = _("Installed") if self.plugin_manager.is_installed(plugin) else _("Available")
        self.plugin_version_note.setText(f"{version_label}: {plugin.version}")
        self.plugin_source_value.setText(str(plugin.source_url or plugin.path or ""))
        details = plugin.description or ""
        if plugin.error:
            details = f"{details}\n{_('Error')}: {plugin.error}".strip()
        self.plugin_details.setText(details)

        self.set_plugin_permission_chips(list(plugin.permissions or []))
        remote = plugin.source in {"remote", "registry"} and not plugin.trusted
        self.plugin_permissions_label.setText(REMOTE_WARNING if remote else "")
        self.plugin_permissions_label.setVisible(remote)
        self.set_plugin_action_state(plugin)

    def enable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin or self.plugin_task_running():
            return
        if self.plugin_manager.needs_registry_install(plugin):
            self._install_and_enable_registry_plugin(plugin)
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
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except PermissionError as exc:
            QMessageBox.warning(self, _("Plugins"), str(exc))

    def _install_and_enable_registry_plugin(self, plugin):
        manager = self.plugin_manager
        name, display_name = plugin.name, plugin.display_name
        entry = copy.deepcopy(manager.available_plugins.get(name))
        if not entry:
            QMessageBox.warning(
                self, _("Plugins"),
                _("{plugin} has no downloadable package.").format(plugin=display_name),
            )
            return
        version = entry.get("version", "")

        def work():
            staging = manager.stage_plugin_package(name, entry)
            if staging is None:
                raise ValueError(_("{plugin} has no downloadable package.").format(plugin=display_name))
            return staging

        def apply(staging):
            manager.install_staged_plugin(name, version, staging)
            manager.set_enabled(name, True, trusted=True)
            return _("{plugin} {version} installed and enabled.").format(
                plugin=display_name, version=version
            ), True

        self.run_plugin_task(
            _("Installing {plugin} {version}…").format(plugin=display_name, version=version),
            work,
            apply,
            _("Could not install plugin: {error}"),
        )

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
        if not plugin or not version or self.plugin_task_running():
            return
        manager = self.plugin_manager
        if version == manager.installed_registry_version(plugin):
            return
        entry = copy.deepcopy(manager.registry_entry_for_version(plugin.name, version))
        if not entry:
            return
        name, display_name, enabled = plugin.name, plugin.display_name, plugin.enabled

        def work():
            staging = manager.stage_plugin_package(name, entry)
            if staging is None:
                raise ValueError(_("{plugin} has no downloadable package.").format(plugin=display_name))
            return staging

        def apply(staging):
            manager.install_staged_plugin(name, version, staging, enable=enabled)
            return _("{plugin} switched to {version}.").format(plugin=display_name, version=version), True

        self.run_plugin_task(
            _("Installing {plugin} {version}…").format(plugin=display_name, version=version),
            work,
            apply,
            _("Could not install plugin version: {error}"),
        )

    def disable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        self.plugin_manager.set_enabled(plugin.name, False)
        self.refresh_plugin_list()
        self._host_plugins_changed()

    def update_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin or self.plugin_task_running():
            return
        manager = self.plugin_manager
        display_name = plugin.display_name
        if plugin.source == "registry":
            self._update_registry_plugin(plugin)
        elif plugin.source == "remote":
            source_url = plugin.source_url

            def apply(changed):
                manager.refresh()
                if changed:
                    return _("{plugin} updated.").format(plugin=display_name), True
                return _("{plugin} is up to date.").format(plugin=display_name), False

            self.run_plugin_task(
                _("Updating {plugin}…").format(plugin=display_name),
                lambda: manager.pull_remote_plugin_source(source_url),
                apply,
                _("Could not update plugin: {error}"),
            )
        else:
            manager.refresh()
            self.refresh_plugin_list()
            self._host_plugins_changed()
            self.plugin_task_status.setText(
                _("Reloaded {plugin} from disk.").format(plugin=display_name)
            )
            self.plugin_task_status_changed()

    def _update_registry_plugin(self, plugin):
        """Refresh the plugin's channel index, then install its latest release."""
        manager = self.plugin_manager
        name, display_name, enabled = plugin.name, plugin.display_name, plugin.enabled
        installed_version = manager.installed_registry_version(plugin)
        channel = next(
            (
                item for item in manager.plugin_channels()
                if item.get("name") == plugin.channel_name and item.get("url")
            ),
            None,
        )
        legacy_url = manager.registry_url()
        plugin_entry = copy.deepcopy(manager.registry_plugins.get(name, {}))

        def work():
            entry = plugin_entry
            if channel is not None:
                manager.download_plugin_registries([channel], legacy_url=legacy_url)
                entry = manager.registry_plugin_entry(name, channel) or entry
            latest = manager.latest_registry_entry(entry)
            if not latest:
                raise ValueError(
                    _("{plugin} is no longer listed in its channel.").format(plugin=display_name)
                )
            version = latest.get("version", "")
            if version and version == installed_version:
                return version, None
            staging = manager.stage_plugin_package(name, latest)
            if staging is None:
                raise ValueError(_("{plugin} has no downloadable package.").format(plugin=display_name))
            return version, staging

        def apply(result):
            version, staging = result
            manager.refresh()
            if staging is None:
                return _("{plugin} is up to date ({version}).").format(
                    plugin=display_name, version=version
                ), False
            manager.install_staged_plugin(name, version, staging, enable=enabled)
            return _("{plugin} updated to {version}.").format(
                plugin=display_name, version=version
            ), True

        self.run_plugin_task(
            _("Updating {plugin}…").format(plugin=display_name),
            work,
            apply,
            _("Could not update plugin: {error}"),
        )

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
            self.refresh_plugin_list()
            self._host_plugins_changed()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not remove plugin: {error}").format(error=exc))
