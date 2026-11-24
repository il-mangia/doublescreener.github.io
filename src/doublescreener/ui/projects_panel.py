"""Pannello dei progetti: elenco e operazioni di base."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.store import ProjectStore
from .i18n import Translator

_ID_ROLE = Qt.ItemDataRole.UserRole


class ProjectsPanel(QWidget):
    project_selected = pyqtSignal(str)
    project_deleted = pyqtSignal(str)
    project_renamed = pyqtSignal(str)

    def __init__(
        self,
        store: ProjectStore,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._t = translator
        self._current_id: str | None = None
        self._build()
        translator.language_changed.connect(self.retranslate)
        self.retranslate()
        self.refresh()

    # -- costruzione ------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(False)
        self.list.itemActivated.connect(lambda _item: self._open_current())
        self.list.itemDoubleClicked.connect(lambda _item: self._open_current())
        self.list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list, 1)

        self.new_button = QPushButton("+")
        self.rename_button = QPushButton("✎")
        self.duplicate_button = QPushButton("⧉")
        self.delete_button = QPushButton("🗑")
        for button in (
            self.new_button,
            self.rename_button,
            self.duplicate_button,
            self.delete_button,
        ):
            button.setFixedWidth(34)
            layout.addWidget(button)

        self.new_button.clicked.connect(self.create_project)
        self.rename_button.clicked.connect(self.rename_current)
        self.duplicate_button.clicked.connect(self.duplicate_current)
        self.delete_button.clicked.connect(self.delete_current)

    # -- testi ------------------------------------------------------------

    def retranslate(self) -> None:
        self.title.setText(self._t.t("projects.title"))
        self.new_button.setToolTip(self._t.t("projects.new.tooltip"))
        self.rename_button.setToolTip(self._t.t("projects.rename.tooltip"))
        self.duplicate_button.setToolTip(self._t.t("projects.duplicate.tooltip"))
        self.delete_button.setToolTip(self._t.t("projects.delete.tooltip"))
        self._update_buttons()

    # -- stato ------------------------------------------------------------

    def refresh(self) -> None:
        selected = self._current_id
        self.list.blockSignals(True)
        self.list.clear()
        summaries = self._store.list()
        for summary in summaries:
            item = QListWidgetItem(f"{summary.name}  ·  {summary.slide_count}")
            item.setData(_ID_ROLE, summary.id)
            item.setToolTip(summary.name)
            self.list.addItem(item)
            if summary.id == selected:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self._update_buttons()

    def set_current(self, project_id: str | None) -> None:
        self._current_id = project_id
        self.list.blockSignals(True)
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(_ID_ROLE) == project_id:
                self.list.setCurrentRow(row)
                break
        else:
            self.list.clearSelection()
        self.list.blockSignals(False)
        self._update_buttons()

    def current_project_id(self) -> str | None:
        item = self.list.currentItem()
        return str(item.data(_ID_ROLE)) if item else None

    def focus_list(self) -> None:
        self.list.setFocus()

    def _update_buttons(self) -> None:
        has_selection = self.list.currentItem() is not None
        for button in (
            self.rename_button,
            self.duplicate_button,
            self.delete_button,
        ):
            button.setEnabled(has_selection)

    def _on_current_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is not None:
            self._current_id = str(current.data(_ID_ROLE))
        self._update_buttons()

    def _open_current(self) -> None:
        project_id = self.current_project_id()
        if project_id:
            self._current_id = project_id
            self.project_selected.emit(project_id)

    # -- azioni -----------------------------------------------------------

    def create_project(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            self._t.t("projects.new.title"),
            self._t.t("projects.new.label"),
            text=self._t.t("projects.new.default"),
        )
        if not ok or not name.strip():
            return
        try:
            project = self._store.create(name.strip())
        except Exception as exc:
            QMessageBox.warning(self, self._t.t("dialog.error"), str(exc))
            return
        self.refresh()
        self.set_current(project.id)
        self.project_selected.emit(project.id)

    def rename_current(self) -> None:
        project_id = self.current_project_id()
        if not project_id:
            return
        try:
            project = self._store.get(project_id)
        except Exception as exc:
            QMessageBox.warning(self, self._t.t("dialog.error"), str(exc))
            return
        name, ok = QInputDialog.getText(
            self,
            self._t.t("projects.rename.title"),
            self._t.t("projects.rename.label"),
            text=project.name,
        )
        if not ok or not name.strip() or name.strip() == project.name:
            return
        project.name = name.strip()
        try:
            self._store.save(project)
        except Exception as exc:
            QMessageBox.warning(self, self._t.t("dialog.error"), str(exc))
            return
        self.refresh()
        self.set_current(project.id)
        self.project_renamed.emit(project.id)

    def duplicate_current(self) -> None:
        project_id = self.current_project_id()
        if not project_id:
            return
        try:
            copy = self._store.duplicate(
                project_id, self._t.t("projects.duplicate.suffix")
            )
        except Exception as exc:
            QMessageBox.warning(self, self._t.t("dialog.error"), str(exc))
            return
        self.refresh()
        self.set_current(copy.id)
        self.project_selected.emit(copy.id)

    def delete_current(self) -> None:
        project_id = self.current_project_id()
        if not project_id:
            return
        try:
            name = self._store.get(project_id).name
        except Exception:
            name = project_id
        answer = QMessageBox.question(
            self,
            self._t.t("projects.delete.title"),
            self._t.t("projects.delete.text", name=name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._store.delete(project_id)
        except Exception as exc:
            QMessageBox.warning(self, self._t.t("dialog.error"), str(exc))
            return
        self._current_id = None
        self.refresh()
        self.project_deleted.emit(project_id)
