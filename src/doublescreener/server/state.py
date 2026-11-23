"""Stato condiviso del backend."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Paths, Settings, SettingsManager
from ..core.assets import AssetStore
from ..core.store import ProjectStore


@dataclass(slots=True)
class AppState:
    paths: Paths
    settings: Settings
    settings_manager: SettingsManager
    store: ProjectStore
    assets: AssetStore
    port: int
    lan_ip: str
