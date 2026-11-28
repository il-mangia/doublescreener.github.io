"""Configurazione: percorsi dati, impostazioni applicative, default."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .core.jsonio import atomic_write_json, read_json

log = logging.getLogger(__name__)

APP_NAME = "DoubleScreener"
APP_SLUG = "doublescreener"
DEFAULT_PORT = 8765
DEFAULT_BIND = "0.0.0.0"


def default_data_dir() -> Path:
    override = os.environ.get("DOUBLESCREENER_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path(user_data_dir(APP_NAME, "il-mangia"))


def resolve_paths(data_dir: str | Path | None) -> Paths:
    if data_dir is not None:
        return Paths(Path(data_dir))
    return Paths(default_data_dir())


@dataclass(frozen=True, slots=True)
class Paths:
    root: Path

    @property
    def projects(self) -> Path:
        return self.root / "projects"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def pdf_cache(self) -> Path:
        return self.cache / "pdf"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.json"

    @property
    def log_file(self) -> Path:
        return self.root / "app.log"

    @property
    def single_instance_file(self) -> Path:
        return self.root / "instance.lock"

    def ensure(self) -> Paths:
        for directory in (self.root, self.projects, self.assets, self.pdf_cache, self.backups):
            directory.mkdir(parents=True, exist_ok=True)
        return self


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lang: str = "it"
    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)
    bind: str = DEFAULT_BIND
    theme: str = "dark"
    last_project_id: str | None = None
    pdf_render_width: int = Field(default=1920, ge=320, le=7680)
    autosave_ms: int = Field(default=1000, ge=200, le=60000)
    canvas_width: int = Field(default=1920, ge=64, le=16384)
    canvas_height: int = Field(default=1080, ge=64, le=16384)


class SettingsManager:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    @property
    def path(self) -> Path:
        return self._paths.settings_file

    def load(self) -> Settings:
        try:
            raw = read_json(self.path)
        except FileNotFoundError:
            return Settings()
        except (OSError, ValueError) as exc:
            log.warning("impostazioni illeggibili (%s), uso i default", exc)
            return Settings()
        try:
            return Settings.model_validate(raw)
        except ValidationError as exc:
            log.warning("impostazioni non valide (%s), uso i default", exc)
            return Settings()

    def save(self, settings: Settings) -> None:
        atomic_write_json(self.path, settings.model_dump(mode="json"))
