"""Canvas Qt: QWebEngineView + bridge QWebChannel verso il renderer condiviso."""

from __future__ import annotations

import json
import logging
from typing import Any

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ..core.models import Project, Slide
from ..core.presentation import slide_payload

# Bootstrap di QtWebEngine: deve avvenire prima di creare QApplication.
from . import webengine  # noqa: F401

log = logging.getLogger(__name__)


class CanvasBridge(QObject):
    """Oggetto esposto a JavaScript come ``bridge``."""

    intent_received = pyqtSignal(str)
    stateChanged = pyqtSignal(str)  # noqa: N815 - nome usato dal client JS

    @pyqtSlot(str)
    def intent(self, payload_json: str) -> None:
        self.intent_received.emit(payload_json)


class CanvasView(QWidget):
    intent = pyqtSignal(dict)
    ready = pyqtSignal()

    def __init__(
        self,
        url: str,
        parent: QWidget | None = None,
        *,
        profile_path: str | None = None,
    ) -> None:
        super().__init__(parent)
        from PyQt6.QtWebChannel import QWebChannel
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self._ready = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.view.setStyleSheet("background: #0b0d12;")
        layout.addWidget(self.view)

        profile = QWebEngineProfile("doublescreener-canvas", self)
        if profile_path:
            profile.setPersistentStoragePath(profile_path)
            profile.setCachePath(f"{profile_path}/cache")
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.profile = profile
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)

        self.channel = QWebChannel(self)
        self.bridge = CanvasBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.page.setWebChannel(self.channel)
        self.bridge.intent_received.connect(self._on_intent_raw)
        self.view.load(QUrl(url))
        self.view.loadFinished.connect(self._on_load_finished)

    # -- invio verso JS ----------------------------------------------------

    def send(self, message: dict[str, Any]) -> None:
        self.bridge.stateChanged.emit(json.dumps(message, ensure_ascii=False))

    def set_slide(
        self,
        project: Project,
        slide: Slide,
        index: int,
        *,
        selection: list[str] | None = None,
        zoom: float = 1.0,
        grid: bool = False,
        lang: str = "it",
        pdf_width: int = 1920,
    ) -> None:
        self.send(
            {
                "type": "render_slide",
                "index": index,
                "slide": slide_payload(project, slide, index, pdf_width=pdf_width),
                "canvas": project.canvas.model_dump(mode="json"),
                "selection": selection or [],
                "zoom": zoom,
                "grid": grid,
                "lang": lang,
            }
        )

    def patch_element(self, element: Any) -> None:
        self.send(
            {
                "type": "patch_element",
                "id": element.id,
                "element": element.model_dump(mode="json"),
            }
        )

    def set_selection(self, ids: list[str]) -> None:
        self.send({"type": "selection", "ids": ids})

    def set_zoom(self, zoom: float) -> None:
        self.send({"type": "zoom", "zoom": zoom})

    def set_grid(self, on: bool) -> None:
        self.send({"type": "grid", "on": on})

    # -- ricezione da JS ---------------------------------------------------

    def _on_intent_raw(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except ValueError:
            log.warning("intento canvas non valido: %r", payload_json[:200])
            return
        if not isinstance(payload, dict):
            return
        if payload.get("action") == "ready":
            self._ready = True
            self.ready.emit()
            return
        self.intent.emit(payload)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            log.warning("caricamento del canvas fallito")
            return
        self._ready = False
