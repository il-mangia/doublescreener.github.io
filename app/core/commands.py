"""Comandi concreti per l'editor.

Ogni funzione restituisce un :class:`~.history.Command` con ``apply`` e
``revert`` simmetrici. Le modifiche sono sempre assolute: l'``apply`` imposta il
nuovo stato, il ``revert`` ripristina lo stato catturato alla prima esecuzione.
"""

from __future__ import annotations

from typing import Any

from .history import Command
from .models import Element, Project, Slide


def _slide(project: Project, slide_id: str) -> Slide:
    return project.slide(slide_id)


def _element_index(slide: Slide, element_id: str) -> int:
    for index, element in enumerate(slide.elements):
        if element.id == element_id:
            return index
    raise KeyError(f"elemento non trovato: {element_id}")


def add_element(slide_id: str, element: Element) -> Command:
    snapshot = element.model_copy(deep=True)

    def apply(project: Project) -> None:
        slide = _slide(project, slide_id)
        if any(existing.id == snapshot.id for existing in slide.elements):
            raise ValueError(f"elemento già presente: {snapshot.id}")
        slide.elements = [*slide.elements, snapshot.model_copy(deep=True)]

    def revert(project: Project) -> None:
        slide = _slide(project, slide_id)
        slide.elements = [e for e in slide.elements if e.id != snapshot.id]

    return Command("Aggiungi elemento", apply, revert)


def update_element(
    slide_id: str,
    element_id: str,
    changes: dict[str, Any],
    *,
    merge_key: str | None = None,
) -> Command:
    holder: dict[str, Element] = {}

    def apply(project: Project) -> None:
        slide = _slide(project, slide_id)
        index = _element_index(slide, element_id)
        current = slide.elements[index]
        if "before" not in holder:
            holder["before"] = current.model_copy(deep=True)
        payload = current.model_dump()
        payload.update(changes)
        payload["id"] = element_id
        updated = Element.model_validate(payload)
        slide.elements = [
            updated if position == index else element
            for position, element in enumerate(slide.elements)
        ]

    def revert(project: Project) -> None:
        slide = _slide(project, slide_id)
        index = _element_index(slide, element_id)
        original = holder["before"].model_copy(deep=True)
        slide.elements = [
            original if position == index else element
            for position, element in enumerate(slide.elements)
        ]

    return Command(
        "Modifica elemento",
        apply,
        revert,
        merge_key=merge_key or f"element:{element_id}",
    )


def delete_element(slide_id: str, element_id: str) -> Command:
    holder: dict[str, tuple[int, Element]] = {}

    def apply(project: Project) -> None:
        slide = _slide(project, slide_id)
        index = _element_index(slide, element_id)
        if "item" not in holder:
            holder["item"] = (index, slide.elements[index].model_copy(deep=True))
        slide.elements = [
            element for position, element in enumerate(slide.elements) if position != index
        ]

    def revert(project: Project) -> None:
        slide = _slide(project, slide_id)
        index, element = holder["item"]
        index = min(index, len(slide.elements))
        slide.elements = [
            *slide.elements[:index],
            element.model_copy(deep=True),
            *slide.elements[index:],
        ]

    return Command("Elimina elemento", apply, revert)


def add_slide(slide: Slide, index: int | None = None) -> Command:
    snapshot = slide.model_copy(deep=True)

    def apply(project: Project) -> None:
        if any(existing.id == snapshot.id for existing in project.slides):
            raise ValueError(f"slide già presente: {snapshot.id}")
        position = len(project.slides) if index is None else max(0, min(index, len(project.slides)))
        project.slides = [
            *project.slides[:position],
            snapshot.model_copy(deep=True),
            *project.slides[position:],
        ]

    def revert(project: Project) -> None:
        project.slides = [s for s in project.slides if s.id != snapshot.id]

    return Command("Aggiungi slide", apply, revert)


def delete_slide(slide_id: str) -> Command:
    holder: dict[str, tuple[int, Slide]] = {}

    def apply(project: Project) -> None:
        if len(project.slides) <= 1:
            raise ValueError("non puoi eliminare l'unica slide del progetto")
        index = project.slide_index(slide_id)
        if "item" not in holder:
            holder["item"] = (index, project.slides[index].model_copy(deep=True))
        project.slides = [s for position, s in enumerate(project.slides) if position != index]

    def revert(project: Project) -> None:
        index, slide = holder["item"]
        index = min(index, len(project.slides))
        project.slides = [
            *project.slides[:index],
            slide.model_copy(deep=True),
            *project.slides[index:],
        ]

    return Command("Elimina slide", apply, revert)


def reorder_slide(from_index: int, to_index: int) -> Command:
    def apply(project: Project) -> None:
        slides = list(project.slides)
        if not 0 <= from_index < len(slides) or not 0 <= to_index < len(slides):
            raise IndexError("indice slide fuori intervallo")
        item = slides.pop(from_index)
        slides.insert(to_index, item)
        project.slides = slides

    def revert(project: Project) -> None:
        slides = list(project.slides)
        item = slides.pop(to_index)
        slides.insert(from_index, item)
        project.slides = slides

    return Command("Riordina slide", apply, revert)


def update_slide(
    slide_id: str,
    changes: dict[str, Any],
    *,
    merge_key: str | None = None,
) -> Command:
    holder: dict[str, Slide] = {}

    def apply(project: Project) -> None:
        index = project.slide_index(slide_id)
        current = project.slides[index]
        if "before" not in holder:
            holder["before"] = current.model_copy(deep=True)
        payload = current.model_dump()
        payload.update(changes)
        payload["id"] = slide_id
        updated = Slide.model_validate(payload)
        project.slides = [
            updated if position == index else slide
            for position, slide in enumerate(project.slides)
        ]

    def revert(project: Project) -> None:
        index = project.slide_index(slide_id)
        original = holder["before"].model_copy(deep=True)
        project.slides = [
            original if position == index else slide
            for position, slide in enumerate(project.slides)
        ]

    return Command(
        "Modifica slide",
        apply,
        revert,
        merge_key=merge_key or f"slide:{slide_id}",
    )


def update_project(
    changes: dict[str, Any],
    *,
    merge_key: str | None = None,
) -> Command:
    holder: dict[str, dict[str, Any]] = {}

    def apply(project: Project) -> None:
        if "before" not in holder:
            holder["before"] = {key: getattr(project, key) for key in changes}
        for key, value in changes.items():
            setattr(project, key, value)

    def revert(project: Project) -> None:
        for key, value in holder["before"].items():
            setattr(project, key, value)

    return Command("Modifica progetto", apply, revert, merge_key=merge_key)
