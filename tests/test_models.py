from __future__ import annotations

import pytest
from pydantic import ValidationError

from doublescreener.core.errors import SchemaError
from doublescreener.core.models import (
    SCHEMA_VERSION,
    Element,
    ElementContent,
    PdfRef,
    Project,
    Rect,
    Slide,
    migrate,
)


def test_project_defaults() -> None:
    project = Project(name="  Demo  ")
    assert project.name == "Demo"
    assert project.schema_version == SCHEMA_VERSION
    assert len(project.slides) == 1
    assert project.canvas.width == 1920
    assert project.canvas.height == 1080


def test_project_name_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        Project(name="   ")


def test_project_requires_at_least_one_slide() -> None:
    with pytest.raises(ValidationError):
        Project(name="Vuoto", slides=[])


def test_duplicate_slide_ids_rejected() -> None:
    slide = Slide(name="A")
    with pytest.raises(ValidationError):
        Project(name="P", slides=[slide, slide.model_copy(deep=True)])


def test_duplicate_element_ids_rejected() -> None:
    element = Element(type="text")
    with pytest.raises(ValidationError):
        Slide(name="S", elements=[element, element.model_copy(deep=True)])


def test_pdf_slide_requires_reference() -> None:
    with pytest.raises(ValidationError):
        Slide(kind="pdf_page", name="PDF")


def test_html_slide_rejects_pdf_reference() -> None:
    ref = PdfRef(asset_id="ast_" + "A" * 26, page=1)
    with pytest.raises(ValidationError):
        Slide(kind="html", name="HTML", pdf=ref)


def test_pdf_slide_valid() -> None:
    ref = PdfRef(asset_id="ast_" + "A" * 26, page=3, source_name="reti.pdf")
    slide = Slide(kind="pdf_page", name="PDF p3", pdf=ref)
    assert slide.pdf is not None
    assert slide.pdf.page == 3


def test_pdf_page_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        PdfRef(asset_id="ast_" + "A" * 26, page=0)


def test_serialization_round_trip() -> None:
    project = Project(name="Round trip")
    project.slides[0].elements.append(
        Element(type="text", rect=Rect(x=10, y=20, w=300, h=80), content=ElementContent(text="x"))
    )
    data = project.model_dump(mode="json")
    assert data["created_at"].endswith("Z")
    restored = Project.model_validate(data)
    assert restored == project


def test_slide_helpers() -> None:
    project = Project(name="P")
    slide = project.slides[0]
    assert project.slide(slide.id) is slide
    assert project.slide_index(slide.id) == 0
    with pytest.raises(KeyError):
        project.slide("sld_" + "Z" * 26)


def test_element_lookup() -> None:
    element = Element(type="text")
    slide = Slide(name="S", elements=[element])
    assert slide.element(element.id) is element
    with pytest.raises(KeyError):
        slide.element("el_" + "Z" * 26)


def test_migrate_future_schema_rejected() -> None:
    with pytest.raises(SchemaError):
        migrate({"schema_version": SCHEMA_VERSION + 1, "name": "x"})


def test_migrate_sets_current_version() -> None:
    migrated = migrate({"name": "x"})
    assert migrated["schema_version"] == SCHEMA_VERSION


def test_migrate_rejects_invalid_version() -> None:
    with pytest.raises(SchemaError):
        migrate({"schema_version": "uno"})


def test_opacity_bounds() -> None:
    with pytest.raises(ValidationError):
        Element(type="text", opacity=1.5)
