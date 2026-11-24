"""Dialogo delle impostazioni della regia."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings
from .i18n import SUPPORTED, Translator


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._t = translator
        self._build()
        self.retranslate()

    def _build(self) -> None:
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.language_combo = QComboBox()
        for code in SUPPORTED:
            self.language_combo.addItem(code.upper(), code)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(self._settings.lang))
        )
        self.language_label = QLabel()
        form.addRow(self.language_label, self.language_combo)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self._settings.port)
        self.port_label = QLabel()
        form.addRow(self.port_label, self.port_spin)

        self.bind_edit = QLineEdit(self._settings.bind)
        self.bind_label = QLabel()
        form.addRow(self.bind_label, self.bind_edit)

        self.pdf_width_spin = QSpinBox()
        self.pdf_width_spin.setRange(320, 3840)
        self.pdf_width_spin.setSingleStep(160)
        self.pdf_width_spin.setValue(self._settings.pdf_render_width)
        self.pdf_width_label = QLabel()
        form.addRow(self.pdf_width_label, self.pdf_width_spin)

        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(200, 60000)
        self.autosave_spin.setSingleStep(100)
        self.autosave_spin.setValue(self._settings.autosave_ms)
        self.autosave_label = QLabel()
        form.addRow(self.autosave_label, self.autosave_spin)

        layout.addLayout(form)

        self.restart_hint = QLabel()
        self.restart_hint.setWordWrap(True)
        self.restart_hint.setStyleSheet("color: #7b8aa5;")
        layout.addWidget(self.restart_hint)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def retranslate(self) -> None:
        self.setWindowTitle(self._t.t("settings.title"))
        self.language_label.setText(self._t.t("settings.language"))
        self.port_label.setText(self._t.t("settings.port"))
        self.bind_label.setText(self._t.t("settings.bind"))
        self.pdf_width_label.setText(self._t.t("settings.pdf_width"))
        self.autosave_label.setText(self._t.t("settings.autosave"))
        self.restart_hint.setText(self._t.t("settings.restart_hint"))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t.t("settings.save")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t.t("common.cancel")
        )

    def result_settings(self) -> Settings:
        return self._settings.model_copy(
            update={
                "lang": str(self.language_combo.currentData()),
                "port": self.port_spin.value(),
                "bind": self.bind_edit.text().strip() or "0.0.0.0",
                "pdf_render_width": self.pdf_width_spin.value(),
                "autosave_ms": self.autosave_spin.value(),
            }
        )
