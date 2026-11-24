"""Dialogo per esportare un progetto in cartella standalone o file HTML singolo."""

from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.assets import AssetStore
from ..core.models import Project
from ..export import SINGLE_FILE_WARNING_BYTES, ExportFormat, estimate_export_bytes
from ..pdf.renderer import PdfRenderer
from .i18n import Translator


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.strip())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "doublescreener-export"


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class ExportDialog(QDialog):
    def __init__(
        self,
        project: Project,
        assets: AssetStore,
        pdf_renderer: PdfRenderer,
        translator: Translator,
        *,
        pdf_width: int = 1920,
        default_dir: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._assets = assets
        self._pdf = pdf_renderer
        self._t = translator
        self._pdf_width = pdf_width
        self._base_dir = default_dir or Path.home()
        self._slug = _safe_slug(project.name)
        self._build()
        self.retranslate()
        self._update_default_path()
        self._refresh_estimate()

    def _build(self) -> None:
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItem("", "folder")
        self.format_combo.addItem("", "single_file")
        self.format_label = QLabel()
        form.addRow(self.format_label, self.format_combo)

        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        self.browse_button = QPushButton()
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.browse_button)
        self.path_label = QLabel()
        form.addRow(self.path_label, path_row)

        self.size_label = QLabel()
        self.size_value = QLabel()
        form.addRow(self.size_label, self.size_value)
        layout.addLayout(form)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #f59e0b;")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.buttons)

        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.browse_button.clicked.connect(self._browse)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def retranslate(self) -> None:
        self.setWindowTitle(self._t.t("export.title"))
        self.format_label.setText(self._t.t("export.format"))
        self.format_combo.setItemText(0, self._t.t("export.format.folder"))
        self.format_combo.setItemText(1, self._t.t("export.format.single_file"))
        self.path_label.setText(self._t.t("export.path"))
        self.browse_button.setText(self._t.t("export.browse"))
        self.size_label.setText(self._t.t("export.size"))
        self.warning_label.setText(self._t.t("export.warning.size"))
        ok_btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText(self._t.t("export.confirm"))
        cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText(self._t.t("common.cancel"))
        self._refresh_estimate()

    def selected_format(self) -> ExportFormat:
        value = self.format_combo.currentData()
        return "single_file" if value == "single_file" else "folder"

    def target_path(self) -> Path:
        return Path(self.path_edit.text().strip())

    def _on_format_changed(self) -> None:
        self._update_default_path()
        self._refresh_estimate()

    def _update_default_path(self) -> None:
        if self.selected_format() == "single_file":
            self.path_edit.setText(str(self._base_dir / f"{self._slug}.html"))
        else:
            self.path_edit.setText(str(self._base_dir / self._slug))

    def _refresh_estimate(self) -> None:
        inline = self.selected_format() == "single_file"
        size = estimate_export_bytes(
            self._project,
            self._assets,
            self._pdf,
            pdf_width=self._pdf_width,
            inline=inline,
        )
        self.size_value.setText(_format_bytes(size))
        self.warning_label.setVisible(inline and size > SINGLE_FILE_WARNING_BYTES)

    def _browse(self) -> None:
        if self.selected_format() == "single_file":
            path, _ = QFileDialog.getSaveFileName(
                self,
                self._t.t("export.title"),
                self.path_edit.text(),
                self._t.t("export.filter.html"),
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                self._t.t("export.title"),
                str(self._base_dir),
            )
            if path:
                path = str(Path(path) / self._slug)
        if path:
            self.path_edit.setText(path)
