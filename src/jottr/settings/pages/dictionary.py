"""Spellcheck page: spell checking, detected dictionaries, and the user dictionary."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QWidget, QCheckBox, QGroupBox, QFormLayout, QInputDialog,
)

from jottr.editor.spellcheck import list_available_spell_languages
from jottr.translation_manager import _, format_language_label


class DictionaryPageMixin:
    """Builds the Spellcheck page and its helpers. Expects SettingsDialog host."""

    def build_dictionary_page(self):
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)
        dict_layout.setContentsMargins(12, 12, 12, 12)
        dict_layout.setSpacing(10)

        spell_box = QGroupBox(_("Spell Checking"))
        spell_form = QFormLayout(spell_box)
        spell_form.setContentsMargins(12, 10, 12, 12)
        spell_form.setSpacing(8)
        self.spell_check_enabled = QCheckBox(_("Enable spell checking"))
        self.spell_check_enabled.toggled.connect(self._on_spell_toggled)
        spell_form.addRow(self.spell_check_enabled)

        spell_langs_hint = QLabel(
            _("Set the document language from Tools → Document Language "
              "or the status bar.")
        )
        spell_langs_hint.setWordWrap(True)
        spell_form.addRow(spell_langs_hint)
        dict_layout.addWidget(spell_box)

        user_box = QGroupBox(_("User Dictionary"))
        user_layout = QVBoxLayout(user_box)
        user_layout.setContentsMargins(12, 10, 12, 12)
        user_layout.setSpacing(8)
        self.dict_list = QListWidget()
        self.dict_list.setMinimumHeight(120)
        self.dict_list.itemSelectionChanged.connect(self._update_dict_buttons)
        user_layout.addWidget(self.dict_list)
        dict_buttons = QHBoxLayout()
        add_word = QPushButton(_("Add Word"))
        self.delete_word_button = QPushButton(_("Delete Word"))
        add_word.clicked.connect(self.add_dict_word)
        self.delete_word_button.clicked.connect(self.delete_dict_word)
        dict_buttons.addWidget(add_word)
        dict_buttons.addWidget(self.delete_word_button)
        dict_buttons.addStretch()
        user_layout.addLayout(dict_buttons)
        dict_layout.addWidget(user_box)

        detected_box = QGroupBox(_("Detected dictionaries"))
        detected_layout = QVBoxLayout(detected_box)
        detected_layout.setContentsMargins(12, 10, 12, 12)
        detected_layout.setSpacing(8)
        detected_hint = QLabel(
            _("Spell dictionaries found on this system via Enchant. "
              "Install hunspell/myspell packages to add more languages.")
        )
        detected_hint.setWordWrap(True)
        detected_layout.addWidget(detected_hint)
        self.detected_dictionaries_list = QListWidget()
        self.detected_dictionaries_list.setMinimumHeight(100)
        self.detected_dictionaries_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        self.detected_dictionaries_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.load_detected_dictionaries()
        detected_layout.addWidget(self.detected_dictionaries_list)
        dict_layout.addWidget(detected_box)
        dict_layout.addStretch()

        self.sync_dictionary_page()
        return dict_tab

    def sync_dictionary_page(self):
        self.spell_check_enabled.setChecked(
            bool(self.settings_manager.get_setting("spell_check", True))
        )
        self.load_user_dict()

    def _save_spell_settings(self):
        self.settings_manager.save_setting('spell_check', self.spell_check_enabled.isChecked())

    def _on_spell_toggled(self):
        self._commit("spell", self._save_spell_settings)

    def _save_user_dictionary(self):
        self._save_only(
            lambda: self.settings_manager.save_setting(
                'user_dictionary', self.get_user_dictionary()
            )
        )

    def load_detected_dictionaries(self):
        """List Enchant dictionaries installed on this system."""
        self.detected_dictionaries_list.clear()
        languages = list_available_spell_languages()
        if not languages:
            self.detected_dictionaries_list.addItem(_("No dictionaries detected."))
            return
        for language in languages:
            self.detected_dictionaries_list.addItem(
                f"{format_language_label(language)} ({language})"
            )

    def load_user_dict(self):
        """Load user dictionary words, keeping the current selection."""
        current = self.dict_list.currentItem()
        current_word = current.text() if current is not None else None
        self.dict_list.clear()
        words = self.settings_manager.get_setting('user_dictionary', [])
        for word in words if isinstance(words, list) else []:
            self.dict_list.addItem(word)
            if word == current_word:
                self.dict_list.setCurrentRow(self.dict_list.count() - 1)
        self._update_dict_buttons()

    def get_user_dictionary(self):
        """Get words from dictionary list widget"""
        return [self.dict_list.item(i).text() for i in range(self.dict_list.count())]

    def _update_dict_buttons(self):
        self.delete_word_button.setEnabled(self.dict_list.currentItem() is not None)

    def add_dict_word(self, word=None):
        """Add a word to the user dictionary (prompts when no word is given)."""
        if word is None:
            word, ok = QInputDialog.getText(self, _("Add Word"), _("Enter word:"))
            if not ok:
                return
        word = (word or "").strip()
        if not word:
            return
        existing = self.dict_list.findItems(word, Qt.MatchFlag.MatchExactly)
        if existing:
            self.dict_list.setCurrentItem(existing[0])
            return
        self.dict_list.addItem(word)
        self.dict_list.setCurrentRow(self.dict_list.count() - 1)
        self._save_user_dictionary()
        # A new word changes highlighting, so refresh spell state live.
        self._notify("spell")

    def delete_dict_word(self):
        """Delete word from user dictionary"""
        current = self.dict_list.currentRow()
        if current >= 0:
            self.dict_list.takeItem(current)
            self._save_user_dictionary()
            self._update_dict_buttons()
            self._notify("spell")
