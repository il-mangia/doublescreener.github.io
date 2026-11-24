"""Palette degli elementi: inserimento rapido nel canvas."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .i18n import Translator

KINDS = ("text", "image", "button", "box", "line")


class PalettePanel(QWidget):
    element_requested = pyqtSignal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)

        for kind in KINDS:
            button = QPushButton()
            button.setObjectName("paletteButton")
            button.clicked.connect(lambda _=False, value=kind: self.element_requested.emit(value))
            layout.addWidget(button)
            self._buttons[kind] = button

        layout.addStretch(1)
        translator.language_changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(self._t.t("palette.title"))
        for kind, button in self._buttons.items():
            button.setText(self._t.t(f"palette.{kind}"))
            button.setToolTip(self._t.t(f"palette.{kind}.tooltip"))
