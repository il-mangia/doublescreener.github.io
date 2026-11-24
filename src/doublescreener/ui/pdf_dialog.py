"""Dialogo di importazione di un PDF nel deck."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.assets import AssetMeta
from ..pdf.importer import parse_pages
from ..pdf.renderer import PdfRenderer
from .i18n import Translator


class PdfImportDialog(QDialog):
    def __init__(
        self,
        meta: AssetMeta,
        renderer: PdfRenderer,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._meta = meta
        self._renderer = renderer
        self._t = translator
        self._pages: list[int] = list(range(1, (meta.pages or 1) + 1))
        self._build()
        self.retranslate()

    def _build(self) -> None:
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        form = QFormLayout()
        self.pages_edit = QLineEdit(f"1-{self._meta.pages or 1}")
        self.pages_label = QLabel()
        form.addRow(self.pages_label, self.pages_edit)
        self.name_edit = QLineEdit("Pagina {page}")
        self.name_label = QLabel()
        form.addRow(self.name_label, self.name_edit)
        layout.addLayout(form)

        self.pages_hint = QLabel()
        self.pages_hint.setWordWrap(True)
        self.pages_hint.setStyleSheet("color: #7b8aa5;")
        layout.addWidget(self.pages_hint)

        self.preview_button = QPushButton()
        self.preview_button.clicked.connect(self._preview)
        layout.addWidget(self.preview_button)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setStyleSheet(
            "background: #0b0d12; border: 1px solid #232733; border-radius: 8px;"
        )
        layout.addWidget(self.preview_label, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def retranslate(self) -> None:
        self.setWindowTitle(self._t.t("pdf.dialog.title", name=self._meta.original_name))
        self.info_label.setText(
            self._t.t(
                "pdf.dialog.total",
                pages=self._meta.pages or 1,
                name=self._meta.original_name,
            )
        )
        self.pages_label.setText(self._t.t("pdf.dialog.pages"))
        self.pages_hint.setText(self._t.t("pdf.dialog.pages.hint"))
        self.name_label.setText(self._t.t("pdf.dialog.name"))
        self.preview_button.setText(self._t.t("pdf.dialog.preview"))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t.t("pdf.dialog.import")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t.t("common.cancel")
        )

    # -- dati -------------------------------------------------------------

    def pages(self) -> list[int]:
        return list(self._pages)

    def name_template(self) -> str:
        return self.name_edit.text().strip() or "Pagina {page}"

    def accept(self) -> None:
        total = self._meta.pages or 1
        try:
            self._pages = parse_pages(self.pages_edit.text(), total)
        except ValueError as exc:
            self.pages_hint.setText(str(exc))
            self.pages_hint.setStyleSheet("color: #f08a8a;")
            return
        try:
            self.name_template().format(page=1, total=total)
        except (KeyError, IndexError, ValueError):
            self.pages_hint.setText(self._t.t("pdf.dialog.name.invalid"))
            self.pages_hint.setStyleSheet("color: #f08a8a;")
            return
        super().accept()

    # -- anteprima --------------------------------------------------------

    def _preview(self) -> None:
        total = self._meta.pages or 1
        try:
            pages = parse_pages(self.pages_edit.text(), total)
        except ValueError as exc:
            self.preview_label.setText(str(exc))
            return
        try:
            path = self._renderer.render(self._meta.id, pages[0], 960)
            pixmap = QPixmap(str(path))
        except Exception as exc:  # il renderer riporta errori leggibili
            self.preview_label.setText(str(exc))
            return
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.width() - 16,
                self.preview_label.height() - 16,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
