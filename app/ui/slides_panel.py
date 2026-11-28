"""Pannello delle slide: elenco, riordino e azioni."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Project, Slide
from .i18n import Translator

_ID_ROLE = Qt.ItemDataRole.UserRole


class SlidesPanel(QWidget):
    current_changed = pyqtSignal(int)
    add_html_requested = pyqtSignal()
    add_pdf_requested = pyqtSignal()
    duplicate_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    move_requested = pyqtSignal(int, int)
    reorder_requested = pyqtSignal(list)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._slides: list[Slide] = []
        self._updating = False
        self._build()
        translator.language_changed.connect(self.retranslate)
        self.retranslate()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)

        self.list = QListWidget()
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._focus_current())
        self.list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list, 1)

        first_row = QHBoxLayout()
        self.add_html_button = QPushButton("+ HTML")
        self.add_pdf_button = QPushButton("+ PDF")
        first_row.addWidget(self.add_html_button)
        first_row.addWidget(self.add_pdf_button)
        layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self.duplicate_button = QPushButton("⧉")
        self.delete_button = QPushButton("🗑")
        self.up_button = QPushButton("↑")
        self.down_button = QPushButton("↓")
        for button in (
            self.duplicate_button,
            self.delete_button,
            self.up_button,
            self.down_button,
        ):
            button.setFixedWidth(34)
            second_row.addWidget(button)
        layout.addLayout(second_row)

        self.add_html_button.clicked.connect(self.add_html_requested)
        self.add_pdf_button.clicked.connect(self.add_pdf_requested)
        self.duplicate_button.clicked.connect(self._duplicate_current)
        self.delete_button.clicked.connect(self._delete_current)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))

    # -- testi ------------------------------------------------------------

    def retranslate(self) -> None:
        self.title.setText(self._t.t("slides.title"))
        self.add_html_button.setToolTip(self._t.t("slides.add_html.tooltip"))
        self.add_pdf_button.setToolTip(self._t.t("slides.add_pdf.tooltip"))
        self.duplicate_button.setToolTip(self._t.t("slides.duplicate.tooltip"))
        self.delete_button.setToolTip(self._t.t("slides.delete.tooltip"))
        self.up_button.setToolTip(self._t.t("slides.up.tooltip"))
        self.down_button.setToolTip(self._t.t("slides.down.tooltip"))
        self._update_buttons()

    # -- dati -------------------------------------------------------------

    def set_slides(self, project: Project | None, select: int = 0) -> None:
        self._slides = list(project.slides) if project else []
        self._updating = True
        self.list.blockSignals(True)
        self.list.clear()
        for index, slide in enumerate(self._slides):
            suffix = ""
            if slide.kind == "pdf_page":
                suffix = f"  ·  {self._t.t('slides.pdf_badge')}"
            item = QListWidgetItem(f"{index + 1}. {slide.name}{suffix}")
            item.setData(_ID_ROLE, slide.id)
            item.setToolTip(slide.name)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._updating = False
        if self._slides:
            self.set_current_index(max(0, min(select, len(self._slides) - 1)))
        self._update_buttons()

    def set_current_index(self, index: int) -> None:
        if not 0 <= index < self.list.count():
            return
        self._updating = True
        self.list.setCurrentRow(index)
        self._updating = False
        self._update_buttons()

    def current_index(self) -> int:
        return max(0, self.list.currentRow())

    def _update_buttons(self) -> None:
        row = self.list.currentRow()
        count = len(self._slides)
        has_selection = 0 <= row < count
        self.duplicate_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection and count > 1)
        self.up_button.setEnabled(has_selection and row > 0)
        self.down_button.setEnabled(has_selection and row < count - 1)

    def _on_row_changed(self, row: int) -> None:
        self._update_buttons()
        if not self._updating and 0 <= row < len(self._slides):
            self.current_changed.emit(row)

    def _focus_current(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._slides):
            self.current_changed.emit(row)

    def _duplicate_current(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._slides):
            self.duplicate_requested.emit(row)

    def _delete_current(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._slides):
            self.delete_requested.emit(row)

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if 0 <= row < len(self._slides) and 0 <= target < len(self._slides):
            self.move_requested.emit(row, target)

    def _on_rows_moved(self, *_args: object) -> None:
        if self._updating or not self._slides:
            return
        order: list[str] = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            order.append(str(item.data(_ID_ROLE)))
        self.reorder_requested.emit(order)
