from __future__ import annotations

import pytest

from doublescreener.core.models import Canvas, Element, ElementStyle, Project, Slide
from doublescreener.core.templates import (
    TEMPLATE_IDS,
    TEMPLATES,
    build_slide,
    element_defaults,
    get_template,
)
from doublescreener.core.themes import (
    DEFAULT_THEME,
    THEME_IDS,
    THEMES,
    apply_to_project,
    get_theme,
)


def test_templates_build_all_five_and_scale() -> None:
    assert len(TEMPLATES) == 5
    canvas_hd = Canvas(width=1920, height=1080)
    canvas_half = Canvas(width=960, height=540)

    for template_id in TEMPLATE_IDS:
        assert get_template(template_id).id == template_id
        slide = build_slide(template_id, canvas_hd, name="Slide")
        assert slide.name == "Slide"
        assert slide.elements

        scaled = build_slide(template_id, canvas_half, name="Half")
        assert len(scaled.elements) == len(slide.elements)
        for full_el, half_el in zip(slide.elements, scaled.elements, strict=True):
            assert half_el.rect.w == pytest.approx(full_el.rect.w / 2)
            assert half_el.rect.h == pytest.approx(full_el.rect.h / 2)


def test_element_defaults_for_all_kinds() -> None:
    canvas = Canvas(width=1920, height=1080)
    theme = get_theme("ocean")
    for kind in ("text", "image", "button", "box", "line"):
        element = element_defaults(kind, canvas, theme=theme)
        assert element.type == kind
        assert element.rect.w > 0
        assert element.rect.h > 0
        assert 0 <= element.rect.x < canvas.width
        assert 0 <= element.rect.y < canvas.height

    with pytest.raises(ValueError):
        element_defaults("unknown", canvas)  # type: ignore[arg-type]


def test_apply_theme_updates_palette_and_keeps_custom_colors() -> None:
    assert len(THEMES) >= 4
    assert DEFAULT_THEME in THEME_IDS
    dark = get_theme("dark")
    light = get_theme("light")

    matched_text = Element(type="text", style=ElementStyle(color=dark.text))
    custom_text = Element(type="text", style=ElementStyle(color="#123456"))
    matched_box = Element(
        type="box",
        style=ElementStyle(background=dark.surface, border_color=dark.accent),
    )

    project = Project(
        name="Test",
        theme="dark",
        canvas=Canvas(width=1920, height=1080, background=dark.background),
        slides=[Slide(name="S1", elements=[matched_text, custom_text, matched_box])],
    )

    apply_to_project(project, "light")

    assert project.theme == "light"
    assert project.canvas.background == light.background
    assert matched_text.style.color == light.text
    assert custom_text.style.color == "#123456"
    assert matched_box.style.background == light.surface
    assert matched_box.style.border_color == light.accent
