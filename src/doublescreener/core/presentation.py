"""Stato della presentazione e comandi della regia.

Il controller è thread-safe: può essere comandato dalla GUI Qt o dalle rotte
HTTP. Non conosce WebSocket: emette eventi a cui l'hub si sottoscrive.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from .. import __version__
from .errors import NotFoundError
from .models import Project, Slide
from .store import ProjectStore

log = logging.getLogger(__name__)

EventKind = Literal["open", "close", "slide", "state"]

PDF_PAGE_URL = "/api/assets/{asset_id}/pages/{page}?width={width}"
ASSET_URL = "/api/assets/{asset_id}"


@dataclass(frozen=True, slots=True)
class PresentationSnapshot:
    project_id: str | None
    project_name: str | None
    index: int
    slide_count: int
    playing: bool
    black: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "index": self.index,
            "slide_count": self.slide_count,
            "playing": self.playing,
            "black": self.black,
        }


Listener = Callable[[EventKind, PresentationSnapshot], None]


class PresentationController:
    def __init__(
        self,
        store: ProjectStore,
        *,
        lang: str = "it",
        pdf_width: int = 1920,
    ) -> None:
        self._store = store
        self._lang = lang
        self._pdf_width = pdf_width
        self._project: Project | None = None
        self._index = 0
        self._playing = False
        self._black = False
        self._listeners: list[Listener] = []
        self._lock = threading.RLock()

    # -- sottoscrizioni ---------------------------------------------------

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def _notify(self, kind: EventKind) -> None:
        with self._lock:
            listeners = list(self._listeners)
            snapshot = self._snapshot_unlocked()
        for listener in listeners:
            try:
                listener(kind, snapshot)
            except Exception:  # pragma: no cover - un listener non deve fermare gli altri
                log.exception("errore in un listener della presentazione")

    # -- interroghiamo lo stato ------------------------------------------

    def _snapshot_unlocked(self) -> PresentationSnapshot:
        project = self._project
        return PresentationSnapshot(
            project_id=project.id if project else None,
            project_name=project.name if project else None,
            index=self._index,
            slide_count=len(project.slides) if project else 0,
            playing=self._playing,
            black=self._black,
        )

    def snapshot(self) -> PresentationSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def state_dict(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "type": "state",
            "index": snapshot.index,
            "playing": snapshot.playing,
            "black": snapshot.black,
            "slide_count": snapshot.slide_count,
            "project_id": snapshot.project_id,
        }

    # -- comandi ----------------------------------------------------------

    def open(self, project_id: str, index: int = 0) -> PresentationSnapshot:
        project = self._store.get(project_id)
        if not 0 <= index < len(project.slides):
            raise ValueError(f"indice slide non valido: {index}")
        with self._lock:
            self._project = project
            self._index = index
            self._playing = True
            self._black = False
        self._notify("open")
        return self.snapshot()

    def close(self) -> PresentationSnapshot:
        with self._lock:
            self._project = None
            self._index = 0
            self._playing = False
            self._black = False
        self._notify("close")
        return self.snapshot()

    def goto(self, index: int) -> PresentationSnapshot:
        with self._lock:
            project = self._project
            if project is None:
                raise ValueError("nessuna presentazione attiva")
            if not 0 <= index < len(project.slides):
                raise ValueError(f"indice slide non valido: {index}")
            if index == self._index:
                return self._snapshot_unlocked()
            self._index = index
        self._notify("slide")
        return self.snapshot()

    def step(self, delta: int) -> PresentationSnapshot:
        with self._lock:
            project = self._project
            if project is None:
                raise ValueError("nessuna presentazione attiva")
            target = max(0, min(self._index + delta, len(project.slides) - 1))
            if target == self._index:
                return self._snapshot_unlocked()
            self._index = target
        self._notify("slide")
        return self.snapshot()

    def set_black(self, on: bool) -> PresentationSnapshot:
        with self._lock:
            if self._project is None:
                raise ValueError("nessuna presentazione attiva")
            if self._black == on:
                return self._snapshot_unlocked()
            self._black = on
        self._notify("state")
        return self.snapshot()

    def set_lang(self, lang: str) -> None:
        with self._lock:
            self._lang = lang

    def set_pdf_width(self, width: int) -> None:
        with self._lock:
            self._pdf_width = width

    # -- payload ----------------------------------------------------------

    def _current_project_unlocked(self) -> Project:
        project = self._project
        if project is None:
            raise NotFoundError("nessuna presentazione attiva")
        return project

    def _slide_payload_unlocked(self, index: int) -> dict[str, Any]:
        project = self._current_project_unlocked()
        slide = project.slides[index]
        payload: dict[str, Any] = {
            "index": index,
            "id": slide.id,
            "kind": slide.kind,
            "name": slide.name,
            "notes": slide.notes,
            "background": slide.background or project.canvas.background,
            "canvas": project.canvas.model_dump(mode="json"),
            "transition": (slide.transition or project.default_transition).model_dump(mode="json"),
            "elements": [element.model_dump(mode="json") for element in slide.elements],
            "pdf": None,
        }
        if slide.kind == "pdf_page" and slide.pdf is not None:
            payload["pdf"] = {
                "asset_id": slide.pdf.asset_id,
                "page": slide.pdf.page,
                "source_name": slide.pdf.source_name,
                "image_url": PDF_PAGE_URL.format(
                    asset_id=slide.pdf.asset_id,
                    page=slide.pdf.page,
                    width=self._pdf_width,
                ),
            }
        return payload

    def slide_payload(self, index: int | None = None) -> dict[str, Any] | None:
        with self._lock:
            if self._project is None:
                return None
            return self._slide_payload_unlocked(self._index if index is None else index)

    def _prefetch_unlocked(self, index: int) -> list[str]:
        project = self._current_project_unlocked()
        urls: list[str] = []
        for candidate in (index + 1,):
            if not 0 <= candidate < len(project.slides):
                continue
            slide: Slide = project.slides[candidate]
            if slide.kind == "pdf_page" and slide.pdf is not None:
                urls.append(
                    PDF_PAGE_URL.format(
                        asset_id=slide.pdf.asset_id,
                        page=slide.pdf.page,
                        width=self._pdf_width,
                    )
                )
            for element in slide.elements:
                if element.content.asset_id:
                    urls.append(ASSET_URL.format(asset_id=element.content.asset_id))
        return urls

    def prefetch(self, index: int | None = None) -> list[str]:
        with self._lock:
            if self._project is None:
                return []
            return self._prefetch_unlocked(self._index if index is None else index)

    def slide_message(self) -> dict[str, Any] | None:
        with self._lock:
            if self._project is None:
                return None
            index = self._index
            payload = self._slide_payload_unlocked(index)
            return {
                "type": "slide",
                "index": index,
                "slide": payload,
                "transition": payload["transition"],
                "prefetch": self._prefetch_unlocked(index),
            }

    def session_dict(self) -> dict[str, Any]:
        with self._lock:
            project = self._project
            if project is None:
                return {
                    "type": "session",
                    "protocol": 1,
                    "server": {"version": __version__},
                    "lang": self._lang,
                    "state": {
                        "index": 0,
                        "playing": False,
                        "black": False,
                        "slide_count": 0,
                        "project_id": None,
                    },
                    "project": None,
                    "deck": {"count": 0},
                    "canvas": None,
                    "slide": None,
                    "index": 0,
                }
            return {
                "type": "session",
                "protocol": 1,
                "server": {"version": __version__},
                "lang": self._lang,
                "state": {
                    "index": self._index,
                    "playing": self._playing,
                    "black": self._black,
                    "slide_count": len(project.slides),
                    "project_id": project.id,
                },
                "project": {"id": project.id, "name": project.name},
                "deck": {"count": len(project.slides)},
                "canvas": project.canvas.model_dump(mode="json"),
                "slide": self._slide_payload_unlocked(self._index),
                "index": self._index,
            }
