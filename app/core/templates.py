"""Template di slide e valori iniziali per la palette elementi.

Le coordinate sono pensate su un canvas 1920×1080 e vengono riscalate sulle
dimensioni reali del progetto. I colori arrivano dal tema attivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Canvas, Element, ElementContent, ElementStyle, Rect, Slide
from .themes import Theme, get_theme

ElementKind = Literal["text", "image", "button", "box", "line"]


@dataclass(frozen=True, slots=True)
class SlideTemplate:
    id: str
    name_key: str


TEMPLATES: tuple[SlideTemplate, ...] = (
    SlideTemplate("title", "template.title"),
    SlideTemplate("title_subtitle", "template.title_subtitle"),
    SlideTemplate("bullets", "template.bullets"),
    SlideTemplate("image_full", "template.image_full"),
    SlideTemplate("two_columns", "template.two_columns"),
)

TEMPLATE_IDS = tuple(template.id for template in TEMPLATES)
_BY_ID = {template.id: template for template in TEMPLATES}


def get_template(template_id: str) -> SlideTemplate:
    return _BY_ID[template_id]


def _scale(canvas: Canvas) -> tuple[float, float, float]:
    sx = canvas.width / 1920
    sy = canvas.height / 1080
    return sx, sy, min(sx, sy)


def _rect(canvas: Canvas, x: float, y: float, w: float, h: float) -> Rect:
    sx, sy, _ = _scale(canvas)
    return Rect(x=x * sx, y=y * sy, w=w * sx, h=h * sy)


def _text(
    canvas: Canvas,
    name: str,
    text: str,
    box: tuple[float, float, float, float],
    *,
    size: float,
    weight: int = 400,
    color: str,
    align: Literal["left", "center", "right", "justify"] = "left",
    line_height: float = 1.2,
) -> Element:
    _, _, font_scale = _scale(canvas)
    return Element(
        type="text",
        name=name,
        rect=_rect(canvas, *box),
        content=ElementContent(text=text),
        style=ElementStyle(
            font_size=max(8.0, size * font_scale),
            font_weight=weight,
            color=color,
            text_align=align,
            line_height=line_height,
        ),
    )


def _box(
    canvas: Canvas,
    name: str,
    box: tuple[float, float, float, float],
    *,
    background: str,
    radius: float = 0,
    border_color: str | None = None,
    border_width: float = 0,
) -> Element:
    _, _, font_scale = _scale(canvas)
    return Element(
        type="box",
        name=name,
        rect=_rect(canvas, *box),
        style=ElementStyle(
            background=background,
            border_radius=radius * font_scale,
            border_color=border_color or "#000000",
            border_width=border_width,
        ),
    )


def build_slide(
    template_id: str,
    canvas: Canvas,
    *,
    name: str,
    theme: Theme | None = None,
) -> Slide:
    """Crea una slide HTML con gli elementi del template richiesto."""
    palette = theme or get_theme("dark")
    elements: list[Element] = []

    if template_id == "title":
        elements.append(
            _text(
                canvas,
                "Titolo",
                "Titolo della presentazione",
                (140, 380, 1640, 320),
                size=104,
                weight=700,
                color=palette.text,
                align="center",
            )
        )
    elif template_id == "title_subtitle":
        elements.append(
            _text(
                canvas,
                "Titolo",
                "Titolo",
                (140, 330, 1640, 220),
                size=88,
                weight=700,
                color=palette.text,
                align="center",
            )
        )
        elements.append(
            _text(
                canvas,
                "Sottotitolo",
                "Un sottotitolo chiaro e sintetico",
                (140, 570, 1640, 140),
                size=40,
                color=palette.muted,
                align="center",
            )
        )
    elif template_id == "bullets":
        elements.append(
            _text(
                canvas,
                "Titolo",
                "Punti principali",
                (140, 120, 1640, 140),
                size=64,
                weight=700,
                color=palette.text,
            )
        )
        elements.append(
            _text(
                canvas,
                "Elenco",
                "• Primo punto\n• Secondo punto\n• Terzo punto\n• Quarto punto",
                (180, 320, 1560, 620),
                size=44,
                color=palette.text,
                line_height=1.55,
            )
        )
    elif template_id == "image_full":
        elements.append(
            Element(
                type="image",
                name="Immagine",
                rect=_rect(canvas, 0, 0, 1920, 1080),
                content=ElementContent(alt="Immagine di sfondo"),
                style=ElementStyle(object_fit="cover"),
            )
        )
        elements.append(
            _text(
                canvas,
                "Titolo",
                "Titolo sopra l'immagine",
                (120, 760, 1680, 240),
                size=76,
                weight=700,
                color="#ffffff",
            )
        )
    elif template_id == "two_columns":
        elements.append(
            _text(
                canvas,
                "Titolo",
                "Due colonne",
                (140, 110, 1640, 130),
                size=60,
                weight=700,
                color=palette.text,
            )
        )
        for index, (x, heading) in enumerate(
            ((140, "Prima colonna"), (1000, "Seconda colonna"))
        ):
            elements.append(
                _box(
                    canvas,
                    f"Riquadro {index + 1}",
                    (x, 300, 780, 600),
                    background=palette.surface,
                    radius=28,
                )
            )
            elements.append(
                _text(
                    canvas,
                    f"Titolo {index + 1}",
                    heading,
                    (x + 50, 350, 680, 110),
                    size=44,
                    weight=600,
                    color=palette.accent,
                )
            )
            elements.append(
                _text(
                    canvas,
                    f"Testo {index + 1}",
                    "Scrivi qui il contenuto della colonna.",
                    (x + 50, 480, 680, 380),
                    size=32,
                    color=palette.text,
                    line_height=1.4,
                )
            )
    else:  # pragma: no cover - id sconosciuto
        raise ValueError(f"template sconosciuto: {template_id}")

    return Slide(name=name, elements=elements, background=None)


def element_defaults(
    kind: ElementKind,
    canvas: Canvas,
    *,
    theme: Theme | None = None,
) -> Element:
    """Elemento iniziale inserito dalla palette, centrato sul canvas."""
    palette = theme or get_theme("dark")
    _, _, font_scale = _scale(canvas)
    width = canvas.width
    height = canvas.height

    def centered(w: float, h: float, y: float) -> Rect:
        return Rect(x=(width - w) / 2, y=y, w=w, h=h)

    if kind == "text":
        return Element(
            type="text",
            name="Testo",
            rect=centered(width * 0.5, height * 0.2, height * 0.4),
            content=ElementContent(text="Testo"),
            style=ElementStyle(
                font_size=max(8.0, 48 * font_scale),
                color=palette.text,
            ),
        )
    if kind == "button":
        return Element(
            type="button",
            name="Pulsante",
            rect=centered(width * 0.22, height * 0.1, height * 0.45),
            content=ElementContent(text="Pulsante"),
            style=ElementStyle(
                font_size=max(8.0, 32 * font_scale),
                font_weight=600,
                color=palette.background,
                background=palette.accent,
                border_radius=14 * font_scale,
                text_align="center",
            ),
        )
    if kind == "image":
        return Element(
            type="image",
            name="Immagine",
            rect=centered(width * 0.34, height * 0.4, height * 0.3),
            content=ElementContent(alt="Immagine"),
            style=ElementStyle(object_fit="cover"),
        )
    if kind == "box":
        return Element(
            type="box",
            name="Riquadro",
            rect=centered(width * 0.3, height * 0.3, height * 0.35),
            style=ElementStyle(
                background=palette.surface,
                border_radius=24 * font_scale,
                border_color=palette.accent,
                border_width=1,
            ),
        )
    if kind == "line":
        return Element(
            type="line",
            name="Linea",
            rect=centered(width * 0.34, max(2.0, 4 * font_scale), height * 0.5),
            style=ElementStyle(color=palette.accent),
        )
    raise ValueError(f"tipo di elemento sconosciuto: {kind}")
