"""Preferencias de guardado, apariencia e idioma (se guardan entre sesiones)."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGroupBox, QLabel, QVBoxLayout)

from ..i18n import DEFAULT as DEFAULT_LANGUAGE
from ..i18n import available_languages, tr



class Preferences:
    def __init__(self, settings: QSettings):
        self.settings = settings

    @property
    def id3_version(self) -> int:
        return 4 if str(self.settings.value("id3", 3)) == "4" else 3

    @property
    def info_encoding(self) -> str:
        return "cp1252" if self.settings.value("info_enc", "utf-8") == "cp1252" else "utf-8"

    @property
    def folder_art(self) -> bool:
        return str(self.settings.value("folder_art", "true")).lower() == "true"

    @property
    def language(self) -> str:
        value = str(self.settings.value("language", DEFAULT_LANGUAGE))
        return value if value in available_languages() else DEFAULT_LANGUAGE

    @property
    def theme(self) -> str:
        value = self.settings.value("theme", "system")
        return value if value in ("system", "light", "dark") else "system"

    def save(self, id3_version: int, info_encoding: str, folder_art: bool, theme: str,
             language: str) -> None:
        self.settings.setValue("id3", id3_version)
        self.settings.setValue("info_enc", info_encoding)
        self.settings.setValue("folder_art", "true" if folder_art else "false")
        self.settings.setValue("theme", theme)
        self.settings.setValue("language", language)


def _combo(items, current) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    combo.setCurrentIndex(max(combo.findData(current), 0))
    return combo


class PreferencesDialog(QDialog):
    def __init__(self, prefs: Preferences, parent=None):
        super().__init__(parent)
        self.prefs = prefs
        self.setWindowTitle(tr("Preferences"))
        self.setMinimumWidth(460)

        self.id3 = _combo([(tr("ID3v2.3 (maximum compatibility)"), 3), ("ID3v2.4", 4)],
                          prefs.id3_version)
        self.info = _combo([("UTF-8 (BWF MetaEdit, MediaInfo)", "utf-8"),
                            (tr("Windows-1252 (older software)"), "cp1252")], prefs.info_encoding)
        self.info.setToolTip(tr("Text encoding of LIST-INFO (INAM, IART, IENG…)."))
        self.folder_art = QCheckBox(tr("Also save the cover as folder.jpg"))
        self.folder_art.setChecked(prefs.folder_art)
        note = QLabel(tr("Windows Explorer and the Windows players do not read the cover embedded "
                         "in a WAV, but they do read folder.jpg. The WAV files are not changed."))
        note.setObjectName("muted")
        note.setWordWrap(True)
        self.theme = _combo([(tr("Same as the system"), "system"), (tr("Light"), "light"),
                             (tr("Dark"), "dark")], prefs.theme)
        self.language = _combo([(name, code) for code, name in available_languages().items()],
                               prefs.language)
        lang_note = QLabel(tr("A language change takes effect when Runout is restarted."))
        lang_note.setObjectName("muted")
        lang_note.setWordWrap(True)

        tags = QGroupBox(tr("Tags"))
        f = QFormLayout(tags)
        f.addRow("ID3:", self.id3)
        f.addRow("LIST-INFO:", self.info)
        f.addRow(self.folder_art)
        f.addRow(note)
        look = QGroupBox(tr("Appearance"))
        f2 = QFormLayout(look)
        f2.addRow(tr("Theme:"), self.theme)
        f2.addRow(tr("Language:"), self.language)
        f2.addRow(lang_note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tags)
        lay.addWidget(look)
        lay.addWidget(buttons)

    def accept(self):
        self.language_changed = self.language.currentData() != self.prefs.language
        self.prefs.save(int(self.id3.currentData()), self.info.currentData(),
                        self.folder_art.isChecked(), self.theme.currentData(),
                        self.language.currentData())
        super().accept()
