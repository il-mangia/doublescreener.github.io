"""Inspector nativo Qt: geometria, stile, contenuto e animazione dell'elemento."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Element
from .i18n import Translator

WEIGHTS = (
    ("inspector.weight.light", 300),
    ("inspector.weight.regular", 400),
    ("inspector.weight.medium", 500),
    ("inspector.weight.semibold", 600),
    ("inspector.weight.bold", 700),
    ("inspector.weight.black", 900),
)
ALIGNS = (
    ("inspector.align.left", "left"),
    ("inspector.align.center", "center"),
    ("inspector.align.right", "right"),
    ("inspector.align.justify", "justify"),
)
FITS = (
    ("inspector.fit.cover", "cover"),
    ("inspector.fit.contain", "contain"),
    ("inspector.fit.fill", "fill"),
)
ANIMATIONS = (
    ("inspector.anim.none", "none"),
    ("inspector.anim.fadeIn", "fadeIn"),
    ("inspector.anim.slideUp", "slideUp"),
    ("inspector.anim.slideDown", "slideDown"),
    ("inspector.anim.slideLeft", "slideLeft"),
    ("inspector.anim.slideRight", "slideRight"),
    ("inspector.anim.zoomIn", "zoomIn"),
    ("inspector.anim.bounce", "bounce"),
)


class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#ffffff"
        self.dialog_title = "Color"
        self.set_color("#ffffff")
        self.clicked.connect(self._choose)

    def set_color(self, color: str) -> None:
        self._color = color or "transparent"
        if self._color.lower() == "transparent":
            self.setText("—")
            self.setStyleSheet("background: #0e1015; color: #7b8aa5;")
            return
        self.setText(self._color.upper())
        self.setStyleSheet(
            f"background: {self._color}; color: #0b0d12; border: 1px solid #2c3346;"
        )

    def _choose(self) -> None:
        initial = QColor(self._color) if QColor.isValidColor(self._color) else QColor("#ffffff")
        color = QColorDialog.getColor(initial, self, self.dialog_title)
        if not color.isValid():
            return
        self.set_color(color.name())
        self.color_changed.emit(color.name())


def _double(
    minimum: float,
    maximum: float,
    *,
    decimals: int = 0,
    step: float = 1,
    suffix: str = "",
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    if suffix:
        spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


def _int(minimum: int, maximum: int, *, step: int = 1, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    if suffix:
        spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


class InspectorPanel(QWidget):
    element_changed = pyqtSignal(str, dict, str)
    image_requested = pyqtSignal(str)
    preview_requested = pyqtSignal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._element: Element | None = None
        self._count = 0
        self._updating = False
        self._labels: list[tuple[QLabel, str]] = []
        self._groups: list[tuple[QGroupBox, str]] = []
        self._bg_key = "background"
        self._build()
        translator.language_changed.connect(self.retranslate)
        self.retranslate()
        self.set_selection([])

    # -- costruzione -------------------------------------------------------

    def _group(self, key: str) -> tuple[QGroupBox, QFormLayout]:
        box = QGroupBox()
        form = QFormLayout(box)
        form.setContentsMargins(10, 8, 10, 10)
        form.setSpacing(6)
        self._groups.append((box, key))
        return box, form

    def _label(self, key: str) -> QLabel:
        label = QLabel()
        self._labels.append((label, key))
        return label

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self.scroll)

        body = QWidget()
        self.scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.header = QLabel()
        self.header.setObjectName("sectionTitle")
        layout.addWidget(self.header)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #7b8aa5;")
        layout.addWidget(self.message)

        self._build_geometry(layout)
        self._build_text(layout)
        self._build_box(layout)
        self._build_content(layout)
        self._build_animation(layout)
        layout.addStretch(1)

    def _build_geometry(self, layout: QVBoxLayout) -> None:
        box, form = self._group("inspector.section.geometry")
        layout.addWidget(box)

        self.x_spin = _double(-16384, 16384, decimals=1, suffix=" px")
        self.y_spin = _double(-16384, 16384, decimals=1, suffix=" px")
        position = QWidget()
        position_row = QHBoxLayout(position)
        position_row.setContentsMargins(0, 0, 0, 0)
        position_row.addWidget(self.x_spin)
        position_row.addWidget(self.y_spin)
        form.addRow(self._label("inspector.x"), position)

        self.w_spin = _double(1, 16384, decimals=1, suffix=" px")
        self.h_spin = _double(1, 16384, decimals=1, suffix=" px")
        size = QWidget()
        size_row = QHBoxLayout(size)
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.addWidget(self.w_spin)
        size_row.addWidget(self.h_spin)
        form.addRow(self._label("inspector.w"), size)

        self.rotation_spin = _double(-180, 180, decimals=1, suffix="°")
        form.addRow(self._label("inspector.rotation"), self.rotation_spin)

        self.opacity_spin = _double(0, 100, decimals=0, suffix=" %")
        form.addRow(self._label("inspector.opacity"), self.opacity_spin)

        self.z_spin = _int(-9999, 9999)
        form.addRow(self._label("inspector.z"), self.z_spin)

        for widget in (self.x_spin, self.y_spin, self.w_spin, self.h_spin):
            widget.valueChanged.connect(self._on_rect)
        self.rotation_spin.valueChanged.connect(self._on_rotation)
        self.opacity_spin.valueChanged.connect(self._on_opacity)
        self.z_spin.valueChanged.connect(self._on_z)

    def _build_text(self, layout: QVBoxLayout) -> None:
        box, form = self._group("inspector.section.text")
        self.text_group = box
        layout.addWidget(box)

        self.font_combo = QFontComboBox()
        form.addRow(self._label("inspector.font"), self.font_combo)

        self.size_spin = _double(1, 1000, decimals=1, step=1, suffix=" px")
        form.addRow(self._label("inspector.size"), self.size_spin)

        self.weight_combo = QComboBox()
        form.addRow(self._label("inspector.weight"), self.weight_combo)

        self.line_height_spin = _double(0.5, 5, decimals=2, step=0.05)
        form.addRow(self._label("inspector.line_height"), self.line_height_spin)

        self.spacing_spin = _double(-20, 200, decimals=1, step=0.5, suffix=" px")
        form.addRow(self._label("inspector.letter_spacing"), self.spacing_spin)

        self.text_color = ColorButton()
        form.addRow(self._label("inspector.color"), self.text_color)

        self.align_combo = QComboBox()
        form.addRow(self._label("inspector.align"), self.align_combo)

        self.font_combo.currentFontChanged.connect(self._on_font)
        self.size_spin.valueChanged.connect(
            lambda value: self._on_style("font_size", float(value))
        )
        self.weight_combo.currentIndexChanged.connect(self._on_weight)
        self.line_height_spin.valueChanged.connect(
            lambda value: self._on_style("line_height", float(value))
        )
        self.spacing_spin.valueChanged.connect(
            lambda value: self._on_style("letter_spacing", float(value))
        )
        self.text_color.color_changed.connect(lambda value: self._on_style("color", value))
        self.align_combo.currentIndexChanged.connect(self._on_align)

    def _build_box(self, layout: QVBoxLayout) -> None:
        box, form = self._group("inspector.section.box")
        self.box_group = box
        layout.addWidget(box)

        self.background_color = ColorButton()
        form.addRow(self._label("inspector.background"), self.background_color)

        self.padding_spin = _double(0, 1000, decimals=1, suffix=" px")
        form.addRow(self._label("inspector.padding"), self.padding_spin)

        self.radius_spin = _double(0, 2000, decimals=1, suffix=" px")
        form.addRow(self._label("inspector.radius"), self.radius_spin)

        self.border_width_spin = _double(0, 100, decimals=1, suffix=" px")
        form.addRow(self._label("inspector.border_width"), self.border_width_spin)

        self.border_color = ColorButton()
        form.addRow(self._label("inspector.border_color"), self.border_color)

        self.shadow_edit = QLineEdit()
        self.shadow_edit.setPlaceholderText("0 8px 24px rgba(0,0,0,.4)")
        form.addRow(self._label("inspector.shadow"), self.shadow_edit)

        self.background_color.color_changed.connect(self._on_background)
        self.padding_spin.valueChanged.connect(
            lambda value: self._on_style("padding", float(value))
        )
        self.radius_spin.valueChanged.connect(
            lambda value: self._on_style("border_radius", float(value))
        )
        self.border_width_spin.valueChanged.connect(
            lambda value: self._on_style("border_width", float(value))
        )
        self.border_color.color_changed.connect(
            lambda value: self._on_style("border_color", value)
        )
        self.shadow_edit.textChanged.connect(self._on_shadow)

    def _build_content(self, layout: QVBoxLayout) -> None:
        box, form = self._group("inspector.section.content")
        self.content_group = box
        self.content_form = form
        layout.addWidget(box)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setFixedHeight(72)
        form.addRow(self._label("inspector.content.text"), self.text_edit)

        self.href_edit = QLineEdit()
        form.addRow(self._label("inspector.content.href"), self.href_edit)

        image_row = QWidget()
        image_layout = QHBoxLayout(image_row)
        image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel()
        image_layout.addWidget(self.image_label, 1)
        self.image_button = QPushButton()
        image_layout.addWidget(self.image_button)
        self.image_row_widget = image_row
        form.addRow(self._label("inspector.content.image"), image_row)

        self.alt_edit = QLineEdit()
        form.addRow(self._label("inspector.content.alt"), self.alt_edit)

        self.fit_combo = QComboBox()
        form.addRow(self._label("inspector.content.fit"), self.fit_combo)

        self.text_edit.textChanged.connect(self._on_text)
        self.href_edit.textChanged.connect(self._on_href)
        self.image_button.clicked.connect(self._on_image)
        self.alt_edit.textChanged.connect(self._on_alt)
        self.fit_combo.currentIndexChanged.connect(self._on_fit)

    def _build_animation(self, layout: QVBoxLayout) -> None:
        box, form = self._group("inspector.section.animation")
        self.animation_group = box
        layout.addWidget(box)

        self.enter_combo = QComboBox()
        form.addRow(self._label("inspector.anim.enter"), self.enter_combo)

        self.duration_spin = _int(0, 60000, step=50, suffix=" ms")
        form.addRow(self._label("inspector.anim.duration"), self.duration_spin)

        self.delay_spin = _int(0, 60000, step=50, suffix=" ms")
        form.addRow(self._label("inspector.anim.delay"), self.delay_spin)

        self.easing_edit = QLineEdit()
        form.addRow(self._label("inspector.anim.easing"), self.easing_edit)

        self.preview_button = QPushButton()
        form.addRow(self._label("inspector.anim.preview"), self.preview_button)

        self.enter_combo.currentIndexChanged.connect(self._on_animation)
        self.duration_spin.valueChanged.connect(self._on_animation)
        self.delay_spin.valueChanged.connect(self._on_animation)
        self.easing_edit.textChanged.connect(self._on_animation)
        self.preview_button.clicked.connect(self._on_preview)

    # -- testi -------------------------------------------------------------

    def retranslate(self) -> None:
        self.header.setText(self._t.t("inspector.title"))
        for label, key in self._labels:
            label.setText(self._t.t(key))
        for box, key in self._groups:
            box.setTitle(self._t.t(key))
        self.image_button.setText(self._t.t("inspector.content.replace"))
        self.preview_button.setText(self._t.t("inspector.anim.preview.button"))
        dialog_title = self._t.t("inspector.color.choose")
        for button in (self.text_color, self.background_color, self.border_color):
            button.dialog_title = dialog_title
        self._fill_combo(self.weight_combo, WEIGHTS)
        self._fill_combo(self.align_combo, ALIGNS)
        self._fill_combo(self.fit_combo, FITS)
        self._fill_combo(self.enter_combo, ANIMATIONS)
        self._refresh_message()
        if self._element is not None:
            self._populate(self._element)

    def _fill_combo(self, combo: QComboBox, items: tuple[tuple[str, Any], ...]) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for key, value in items:
            combo.addItem(self._t.t(key), value)
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _refresh_message(self) -> None:
        if self._count == 0:
            self.message.setText(self._t.t("inspector.empty"))
        elif self._count > 1:
            self.message.setText(self._t.t("inspector.multi", n=self._count))
        else:
            self.message.setText("")

    # -- dati --------------------------------------------------------------

    def set_selection(self, elements: list[Element]) -> None:
        self._count = len(elements)
        self._element = elements[0].model_copy(deep=True) if self._count == 1 else None
        self._refresh_message()
        visible = self._element is not None
        for box, _key in self._groups:
            box.setVisible(visible)
        if self._element is None:
            self.header.setText(self._t.t("inspector.title"))
            return
        element = self._element
        label = element.name or self._t.t(f"element.{element.type}")
        self.header.setText(f"{label} · {self._t.t(f'element.{element.type}')}")
        self._populate(element)
        self._apply_visibility(element)

    def _apply_visibility(self, element: Element) -> None:
        kind = element.type
        self.text_group.setVisible(kind in ("text", "button"))
        self.box_group.setVisible(kind in ("box", "line", "image", "button"))
        self.content_group.setVisible(kind in ("text", "button", "image"))
        self.animation_group.setVisible(True)
        self.content_form.setRowVisible(self.text_edit, kind in ("text", "button"))
        self.content_form.setRowVisible(self.href_edit, kind == "button")
        self.content_form.setRowVisible(self.image_row_widget, kind == "image")
        self.content_form.setRowVisible(self.alt_edit, kind == "image")
        self.content_form.setRowVisible(self.fit_combo, kind == "image")
        self._bg_key = "color" if kind == "line" else "background"

    def _populate(self, element: Element) -> None:
        style = element.style
        content = element.content
        animation = element.animation
        self._updating = True
        try:
            self.x_spin.setValue(element.rect.x)
            self.y_spin.setValue(element.rect.y)
            self.w_spin.setValue(element.rect.w)
            self.h_spin.setValue(element.rect.h)
            self.rotation_spin.setValue(element.rotation)
            self.opacity_spin.setValue(element.opacity * 100)
            self.z_spin.setValue(element.z)

            self.font_combo.setCurrentFont(QFont(style.font_family))
            self.size_spin.setValue(style.font_size)
            index = self.weight_combo.findData(style.font_weight)
            self.weight_combo.setCurrentIndex(max(0, index))
            self.line_height_spin.setValue(style.line_height)
            self.spacing_spin.setValue(style.letter_spacing)
            self.text_color.set_color(style.color)
            index = self.align_combo.findData(style.text_align)
            self.align_combo.setCurrentIndex(max(0, index))

            background = style.color if element.type == "line" else style.background
            self.background_color.set_color(background)
            self.padding_spin.setValue(style.padding)
            self.radius_spin.setValue(style.border_radius)
            self.border_width_spin.setValue(style.border_width)
            self.border_color.set_color(style.border_color)
            self.shadow_edit.setText(style.shadow or "")

            self.text_edit.setPlainText(content.text)
            self.href_edit.setText(content.href or "")
            self.image_label.setText(
                self._t.t("inspector.content.image.set") if content.asset_id else "—"
            )
            self.alt_edit.setText(content.alt or "")
            index = self.fit_combo.findData(style.object_fit)
            self.fit_combo.setCurrentIndex(max(0, index))

            index = self.enter_combo.findData(animation.enter)
            self.enter_combo.setCurrentIndex(max(0, index))
            self.duration_spin.setValue(animation.duration_ms)
            self.delay_spin.setValue(animation.delay_ms)
            self.easing_edit.setText(animation.easing)
        finally:
            self._updating = False

    # -- emissione ---------------------------------------------------------

    def _emit(self, changes: dict[str, Any], key: str) -> None:
        if self._updating or self._element is None:
            return
        self.element_changed.emit(
            self._element.id, changes, f"inspector:{self._element.id}:{key}"
        )

    def _on_rect(self) -> None:
        self._emit(
            {
                "rect": {
                    "x": self.x_spin.value(),
                    "y": self.y_spin.value(),
                    "w": self.w_spin.value(),
                    "h": self.h_spin.value(),
                }
            },
            "rect",
        )

    def _on_rotation(self, value: float) -> None:
        self._emit({"rotation": float(value)}, "rotation")

    def _on_opacity(self, value: float) -> None:
        self._emit({"opacity": float(value) / 100.0}, "opacity")

    def _on_z(self, value: int) -> None:
        self._emit({"z": int(value)}, "z")

    def _style_payload(self) -> dict[str, Any] | None:
        return self._element.style.model_dump() if self._element else None

    def _on_style(self, key: str, value: Any) -> None:
        style = self._style_payload()
        if style is None:
            return
        style[key] = value
        self._emit({"style": style}, f"style.{key}")

    def _on_font(self, font: QFont) -> None:
        self._on_style("font_family", font.family())

    def _on_weight(self) -> None:
        value = self.weight_combo.currentData()
        if value is not None:
            self._on_style("font_weight", int(value))

    def _on_align(self) -> None:
        value = self.align_combo.currentData()
        if value is not None:
            self._on_style("text_align", str(value))

    def _on_background(self, value: str) -> None:
        self._on_style(self._bg_key, value)

    def _on_shadow(self, text: str) -> None:
        self._on_style("shadow", text.strip() or None)

    def _content_payload(self) -> dict[str, Any] | None:
        return self._element.content.model_dump() if self._element else None

    def _on_text(self) -> None:
        content = self._content_payload()
        if content is None:
            return
        content["text"] = self.text_edit.toPlainText()
        self._emit({"content": content}, "content.text")

    def _on_href(self, text: str) -> None:
        content = self._content_payload()
        if content is None:
            return
        content["href"] = text.strip() or None
        self._emit({"content": content}, "content.href")

    def _on_alt(self, text: str) -> None:
        content = self._content_payload()
        if content is None:
            return
        content["alt"] = text
        self._emit({"content": content}, "content.alt")

    def _on_fit(self) -> None:
        value = self.fit_combo.currentData()
        if value is not None:
            self._on_style("object_fit", str(value))

    def _on_image(self) -> None:
        if self._element is not None:
            self.image_requested.emit(self._element.id)

    def _on_animation(self) -> None:
        if self._updating or self._element is None:
            return
        animation = self._element.animation.model_dump()
        animation["enter"] = self.enter_combo.currentData() or "none"
        animation["duration_ms"] = self.duration_spin.value()
        animation["delay_ms"] = self.delay_spin.value()
        animation["easing"] = self.easing_edit.text().strip() or "ease-out"
        self._emit({"animation": animation}, "animation")

    def _on_preview(self) -> None:
        if self._element is not None:
            self.preview_requested.emit(self._element.id)
