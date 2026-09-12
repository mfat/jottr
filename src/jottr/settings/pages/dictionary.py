"""Spellcheck settings page (moved from settings_dialog, plus instant wiring)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QWidget, QCheckBox, QComboBox, QGroupBox, QFormLayout, QInputDialog,
)

from jottr.editor.spellcheck import (
    DOCUMENT_LANGUAGE_AUTO,
    get_document_language,
    list_available_spell_languages,
    list_document_language_choices,
    match_dictionary_for_language,
    missing_dictionary_message,
)
from jottr.translation_manager import _, format_language_label


class DictionaryPageMixin:
    """Builds the Spellcheck tab and its helpers. Expects SettingsDialog host."""

    def build_dictionary_page(self):
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)
        dict_layout.setSpacing(10)

        spell_box = QGroupBox(_("Spell Checking"))
        spell_form = QFormLayout(spell_box)
        spell_form.setContentsMargins(12, 10, 12, 12)
        spell_form.setSpacing(8)
        self.spell_check_enabled = QCheckBox(_("Enable spell checking"))
        self.spell_check_enabled.setChecked(
            bool(self.settings_manager.get_setting("spell_check", True))
        )
        self.spell_check_enabled.toggled.connect(self._on_spell_toggled)
        spell_form.addRow(self.spell_check_enabled)

        self.document_language_combo = QComboBox()
        self.document_language_combo.setMinimumContentsLength(28)
        self.load_document_languages()
        self.document_language_combo.currentIndexChanged.connect(
            self._on_document_language_changed
        )
        self.document_language_combo.currentIndexChanged.connect(
            self.update_document_language_status
        )
        spell_form.addRow(_("Document language:"), self.document_language_combo)

        self.document_language_status = QLabel()
        self.document_language_status.setWordWrap(True)
        spell_form.addRow(self.document_language_status)
        self.update_document_language_status()

        spell_langs_hint = QLabel(
            _("Choose a language, or Auto-detect from the text. "
              "Jottr loads a matching installed dictionary and warns if none is available. "
              "Also available from Tools → Document Language and the status bar.")
        )
        spell_langs_hint.setWordWrap(True)
        spell_form.addRow(spell_langs_hint)
        dict_layout.addWidget(spell_box)

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

        dict_label = QLabel(_("User Dictionary:"))
        dict_layout.addWidget(dict_label)

        self.dict_list = QListWidget()
        self.load_user_dict()
        dict_layout.addWidget(self.dict_list)

        # Dictionary buttons
        dict_buttons = QHBoxLayout()
        add_word = QPushButton(_("Add Word"))
        delete_word = QPushButton(_("Delete Word"))
        add_word.clicked.connect(self.add_dict_word)
        delete_word.clicked.connect(self.delete_dict_word)
        dict_buttons.addWidget(add_word)
        dict_buttons.addWidget(delete_word)
        dict_layout.addLayout(dict_buttons)
        return dict_tab

    def _save_spell_settings(self):
        sm = self.settings_manager
        sm.save_setting('spell_check', self.spell_check_enabled.isChecked())
        document_language = self.get_document_language()
        sm.save_setting('document_language', document_language)
        sm.save_setting('spell_languages', self._spell_languages_for_document())

    def _on_spell_toggled(self):
        self._commit("spell", self._save_spell_settings)

    def _on_document_language_changed(self):
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
        """Load user dictionary words"""
        words = self.settings_manager.get_setting('user_dictionary', [])
        self.dict_list.addItems(words)

    def get_user_dictionary(self):
        """Get words from dictionary list widget"""
        words = []
        for i in range(self.dict_list.count()):
            words.append(self.dict_list.item(i).text())
        return words

    def load_document_languages(self):
        """Populate the document-language combo, including languages without dictionaries."""
        current = get_document_language(self.settings_manager)
        self.document_language_combo.blockSignals(True)
        self.document_language_combo.clear()
        for language in list_document_language_choices(extra=[current]):
            self.document_language_combo.addItem(format_language_label(language), language)
        index = self.document_language_combo.findData(current)
        if index < 0:
            self.document_language_combo.addItem(format_language_label(current), current)
            index = self.document_language_combo.findData(current)
        self.document_language_combo.setCurrentIndex(max(0, index))
        self.document_language_combo.blockSignals(False)

    def update_document_language_status(self, *args):
        """Show whether a dictionary is installed for the selected document language."""
        from jottr.editor.spellcheck import USE_LANGDETECT

        language = (
            self.document_language_combo.currentData()
            or self.document_language_combo.currentText()
            or get_document_language(self.settings_manager)
        )
        if language == DOCUMENT_LANGUAGE_AUTO:
            if USE_LANGDETECT:
                self.document_language_status.setText(
                    _("Auto-detects language from the document, then loads a matching "
                      "installed dictionary. Short text may be unreliable.")
                )
            else:
                self.document_language_status.setText(
                    _("Auto-detect requires the langdetect package.")
                )
            return

        matched = match_dictionary_for_language(language)
        if matched:
            self.document_language_status.setText(
                _("Dictionary ready: {dictionary}").format(dictionary=matched)
            )
        else:
            self.document_language_status.setText(missing_dictionary_message(language))

    def get_document_language(self):
        """Return the selected document language tag."""
        return (
            self.document_language_combo.currentData()
            or self.document_language_combo.currentText()
            or "en_US"
        )

    def _spell_languages_for_document(self):
        language = self.get_document_language()
        if language == DOCUMENT_LANGUAGE_AUTO:
            return []
        matched = match_dictionary_for_language(language)
        return [matched] if matched else []

    def add_dict_word(self):
        """Add word to user dictionary"""
        word, ok = QInputDialog.getText(self, _("Add Word"), _("Enter word:"))
        if ok and word:
            self.dict_list.addItem(word)
            self._save_user_dictionary()
            # A new word changes highlighting, so refresh spell state live.
            self._notify("spell")

    def delete_dict_word(self):
        """Delete word from user dictionary"""
        current = self.dict_list.currentRow()
        if current >= 0:
            self.dict_list.takeItem(current)
            self._save_user_dictionary()
            self._notify("spell")
