"""Stato condiviso del backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import Paths, Settings, SettingsManager
from ..core.assets import AssetStore
from ..core.store import ProjectStore

if TYPE_CHECKING:
    from ..core.presentation import PresentationController
    from ..pdf.renderer import PdfRenderer
    from .ws import WebSocketHub


@dataclass(slots=True)
class AppState:
    paths: Paths
    settings: Settings
    settings_manager: SettingsManager
    store: ProjectStore
    assets: AssetStore
    controller: PresentationController
    hub: WebSocketHub
    pdf: PdfRenderer
    port: int
    lan_ip: str
