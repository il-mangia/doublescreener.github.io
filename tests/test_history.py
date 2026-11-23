from __future__ import annotations

import pytest

from doublescreener.core.commands import (
    add_element,
    add_slide,
    delete_element,
    delete_slide,
    reorder_slide,
    update_element,
    update_project,
    update_slide,
)
from doublescreener.core.history import History
from doublescreener.core.models import Element, ElementContent, Project, Rect, Slide


@pytest.fixture()
def project() -> Project:
    return Project(name="Test")


def _slide_id(project: Project) -> str:
    return project.slides[0].id


def test_add_element_undo_redo(project) -> None:
    history = History()
    element = Element(type="text", content=ElementContent(text="ciao"))

    history.execute(project, add_element(_slide_id(project), element))
    assert len(project.slides[0].elements) == 1

    history.undo(project)
    assert project.slides[0].elements == []

    history.redo(project)
    assert project.slides[0].elements[0].content.text == "ciao"


def test_update_element_merges_within_window(project) -> None:
    history = History(merge_window=10)
    element = Element(type="text")
    history.execute(project, add_element(_slide_id(project), element))

    first = update_element(_slide_id(project), element.id, {"rect": Rect(x=10)})
    history.execute(project, first)

    second = update_element(_slide_id(project), element.id, {"rect": Rect(x=20)})
    second.timestamp = first.timestamp + 0.05
    history.execute(project, second)

    # add_element + update fuso = 2 voci
    assert len(history) == 2
    assert project.slides[0].elements[0].rect.x == 20

    history.undo(project)
    assert project.slides[0].elements[0].rect.x == 0


def test_update_element_outside_window_not_merged(project) -> None:
    history = History(merge_window=0.1)
    element = Element(type="text")
    history.execute(project, add_element(_slide_id(project), element))

    first = update_element(_slide_id(project), element.id, {"rect": Rect(x=10)})
    history.execute(project, first)
    second = update_element(_slide_id(project), element.id, {"rect": Rect(x=20)})
    second.timestamp = first.timestamp + 5
    history.execute(project, second)

    # add_element, update, update: nessuna fusione
    assert len(history) == 3


def test_new_command_clears_redo(project) -> None:
    history = History()
    history.execute(project, update_project({"name": "A"}))
    history.undo(project)
    assert history.can_redo

    history.execute(project, update_project({"name": "B"}))
    assert not history.can_redo


def test_history_limit(project) -> None:
    history = History(limit=2)
    for name in ("A", "B", "C"):
        history.execute(project, update_project({"name": name}, merge_key=name))

    assert len(history) == 2
    history.undo(project)
    history.undo(project)
    assert history.undo(project) is None


def test_delete_element_restores_position(project) -> None:
    history = History()
    first = Element(type="text", name="uno")
    second = Element(type="text", name="due")
    history.execute(project, add_element(_slide_id(project), first))
    history.execute(project, add_element(_slide_id(project), second))
    history.execute(project, delete_element(_slide_id(project), first.id))

    assert [e.name for e in project.slides[0].elements] == ["due"]
    history.undo(project)
    assert [e.name for e in project.slides[0].elements] == ["uno", "due"]


def test_delete_slide_protects_last(project) -> None:
    history = History()
    with pytest.raises(ValueError):
        history.execute(project, delete_slide(_slide_id(project)))


def test_add_and_reorder_slides(project) -> None:
    history = History()
    extra = Slide(name="Seconda")
    history.execute(project, add_slide(extra))
    assert [s.name for s in project.slides] == ["Slide 1", "Seconda"]

    history.execute(project, reorder_slide(1, 0))
    assert [s.name for s in project.slides] == ["Seconda", "Slide 1"]

    history.undo(project)
    assert [s.name for s in project.slides] == ["Slide 1", "Seconda"]


def test_update_slide(project) -> None:
    history = History()
    history.execute(project, update_slide(_slide_id(project), {"background": "#000000"}))
    assert project.slides[0].background == "#000000"
    history.undo(project)
    assert project.slides[0].background is None


def test_update_project(project) -> None:
    history = History()
    history.execute(project, update_project({"name": "Nuovo"}))
    assert project.name == "Nuovo"
    history.undo(project)
    assert project.name == "Test"
