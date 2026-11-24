from __future__ import annotations

import pytest

from doublescreener.core.models import (
    Element,
    ElementContent,
    PdfRef,
    Project,
    Slide,
)
from doublescreener.core.presentation import PresentationController


def _project_with_slides(store, count: int = 2) -> Project:
    project = store.create("Demo")
    for index in range(1, count):
        project.slides.append(Slide(name=f"Slide {index + 1}"))
    return store.save(project)


def test_initial_state(store) -> None:
    controller = PresentationController(store)
    snapshot = controller.snapshot()
    assert snapshot.project_id is None
    assert snapshot.slide_count == 0
    assert controller.session_dict()["project"] is None
    assert controller.slide_payload() is None


def test_open_goto_step_black_close(store) -> None:
    project = _project_with_slides(store)
    controller = PresentationController(store)
    events: list[tuple[str, int]] = []
    unsubscribe = controller.subscribe(lambda kind, snap: events.append((kind, snap.index)))

    snapshot = controller.open(project.id)
    assert snapshot.project_id == project.id
    assert snapshot.index == 0
    assert snapshot.playing is True
    assert events == [("open", 0)]

    controller.goto(1)
    assert events[-1] == ("slide", 1)
    controller.goto(1)
    assert events[-1] == ("slide", 1)
    assert len(events) == 2

    controller.step(1)  # già all'ultima
    assert len(events) == 2
    controller.step(-1)
    assert events[-1] == ("slide", 0)

    controller.set_black(True)
    assert events[-1] == ("state", 0)
    assert controller.snapshot().black is True
    controller.set_black(True)
    assert len(events) == 4

    controller.close()
    assert events[-1][0] == "close"
    assert controller.snapshot().project_id is None
    unsubscribe()


def test_open_validates_index(store) -> None:
    project = _project_with_slides(store)
    controller = PresentationController(store)
    with pytest.raises(ValueError):
        controller.open(project.id, index=5)


def test_commands_require_active_presentation(store) -> None:
    controller = PresentationController(store)
    with pytest.raises(ValueError):
        controller.goto(0)
    with pytest.raises(ValueError):
        controller.step(1)
    with pytest.raises(ValueError):
        controller.set_black(True)


def test_slide_payload_contains_elements(store) -> None:
    project = _project_with_slides(store)
    project.slides[0].elements.append(
        Element(type="text", content=ElementContent(text="Ciao"))
    )
    store.save(project)

    controller = PresentationController(store)
    controller.open(project.id)
    payload = controller.slide_payload()

    assert payload is not None
    assert payload["kind"] == "html"
    assert payload["canvas"]["width"] == 1920
    assert payload["background"] == "#101014"
    assert payload["elements"][0]["content"]["text"] == "Ciao"
    assert payload["pdf"] is None


def test_pdf_payload_and_prefetch(store) -> None:
    project = store.create("PDF")
    project.slides = [
        Slide(
            kind="pdf_page",
            name="Pagina 2",
            pdf=PdfRef(asset_id="ast_" + "A" * 26, page=2, source_name="doc.pdf"),
        )
    ]
    store.save(project)

    controller = PresentationController(store, pdf_width=1280)
    controller.open(project.id)
    payload = controller.slide_payload()

    assert payload is not None
    assert payload["kind"] == "pdf_page"
    assert payload["pdf"]["page"] == 2
    assert payload["pdf"]["image_url"] == (
        f"/api/assets/ast_{'A' * 26}/pages/2?width=1280"
    )

    project.slides.append(
        Slide(
            kind="pdf_page",
            name="Pagina 3",
            pdf=PdfRef(asset_id="ast_" + "B" * 26, page=3),
        )
    )
    store.save(project)
    controller.open(project.id, index=0)
    assert controller.prefetch() == [
        f"/api/assets/ast_{'B' * 26}/pages/3?width=1280"
    ]


def test_session_dict(store) -> None:
    project = _project_with_slides(store)
    controller = PresentationController(store, lang="en")
    controller.open(project.id)

    session = controller.session_dict()
    assert session["type"] == "session"
    assert session["protocol"] == 1
    assert session["lang"] == "en"
    assert session["project"]["id"] == project.id
    assert session["deck"]["count"] == 2
    assert session["slide"]["index"] == 0
    assert session["state"]["playing"] is True


def test_listener_errors_do_not_break_others(store) -> None:
    project = _project_with_slides(store)
    controller = PresentationController(store)
    received: list[str] = []

    def broken(_kind, _snapshot):
        raise RuntimeError("boom")

    controller.subscribe(broken)
    controller.subscribe(lambda kind, _snap: received.append(kind))
    controller.open(project.id)
    assert received == ["open"]
