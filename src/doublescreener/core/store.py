"""Repository dei progetti su file JSON, con scritture atomiche e backup."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..config import Paths
from .errors import ConflictError, NotFoundError, SchemaError, StoreError
from .ids import new_id
from .jsonio import atomic_write_json, copy_atomic, read_json
from .models import Canvas, Element, Project, ProjectSummary, Slide, migrate, utcnow

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-z]{2,5}_[0-9A-Za-z]{1,32}$")


def _validate_id(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"id non valido: {value!r}")
    return value


def _same_moment(left: datetime, right: datetime) -> bool:
    return left.astimezone(UTC) == right.astimezone(UTC)


class ProjectStore:
    """Gestisce i progetti in ``<data>/projects/<id>.json``.

    Thread-safe nel processo: ogni progetto ha un lock dedicato. Una seconda
    istanza dell'applicazione è impedita a livello di UI (QLocalServer).
    """

    def __init__(self, paths: Paths) -> None:
        self._paths = paths
        self._paths.projects.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    # -- percorsi ---------------------------------------------------------

    def path(self, project_id: str) -> Path:
        return self._paths.projects / f"{_validate_id(project_id)}.json"

    def backup_path(self, project_id: str) -> Path:
        return self._paths.projects / f"{_validate_id(project_id)}.bak.json"

    def _lock(self, project_id: str) -> threading.RLock:
        with self._locks_guard:
            lock = self._locks.get(project_id)
            if lock is None:
                lock = self._locks[project_id] = threading.RLock()
            return lock

    # -- lettura ----------------------------------------------------------

    def _load_path(self, path: Path, project_id: str) -> Project:
        data = read_json(path)
        project = Project.model_validate(migrate(data))
        if project.id != project_id:
            raise StoreError(
                f"il file {path.name} contiene il progetto {project.id}, atteso {project_id}"
            )
        return project

    def list(self) -> list[ProjectSummary]:
        summaries: list[ProjectSummary] = []
        for path in sorted(self._paths.projects.glob("*.json")):
            if path.name.endswith(".bak.json"):
                continue
            try:
                data = read_json(path)
                project = Project.model_validate(migrate(data))
            except (OSError, ValueError, SchemaError, ValidationError) as exc:
                log.warning("progetto ignorato %s: %s", path.name, exc)
                continue
            summaries.append(
                ProjectSummary(
                    id=project.id,
                    name=project.name,
                    slide_count=len(project.slides),
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                )
            )
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return summaries

    def exists(self, project_id: str) -> bool:
        return self.path(project_id).is_file()

    def get(self, project_id: str) -> Project:
        project, _ = self.load(project_id)
        return project

    def load(self, project_id: str) -> tuple[Project, str | None]:
        """Carica un progetto; se il file principale è corrotto, prova il backup.

        Restituisce ``(progetto, avviso)``: ``avviso`` è ``None`` quando la
        lettura è pulita.
        """
        path = self.path(project_id)
        try:
            return self._load_path(path, project_id), None
        except FileNotFoundError:
            backup = self.backup_path(project_id)
            if backup.is_file():
                log.warning("progetto %s assente, recupero dal backup", project_id)
                return self._load_path(backup, project_id), "recuperato dal backup"
            raise NotFoundError(f"progetto non trovato: {project_id}") from None
        except (OSError, ValueError, SchemaError, ValidationError) as exc:
            backup = self.backup_path(project_id)
            if backup.is_file():
                try:
                    project = self._load_path(backup, project_id)
                except (OSError, ValueError, SchemaError, ValidationError):
                    pass
                else:
                    log.error("progetto %s corrotto (%s), recupero dal backup", project_id, exc)
                    return project, "file principale corrotto: recuperato dal backup"
            raise StoreError(f"progetto illeggibile: {project_id}") from exc

    # -- scrittura --------------------------------------------------------

    def create(
        self,
        name: str,
        *,
        canvas: Canvas | None = None,
        slides: list[Slide] | None = None,
    ) -> Project:
        project = Project(
            name=name,
            canvas=canvas or Canvas(),
            slides=slides or [Slide(name="Slide 1")],
        )
        return self.save(project)

    def save(
        self,
        project: Project,
        *,
        expected_updated_at: datetime | None = None,
    ) -> Project:
        path = self.path(project.id)
        with self._lock(project.id):
            if path.is_file():
                try:
                    current = self._load_path(path, project.id)
                except (OSError, ValueError, SchemaError, ValidationError) as exc:
                    raise StoreError(
                        f"impossibile salvare: il progetto esistente è illeggibile ({exc})"
                    ) from exc
                if expected_updated_at is not None and not _same_moment(
                    current.updated_at, expected_updated_at
                ):
                    raise ConflictError(
                        "il progetto è stato modificato da un'altra sessione: ricaricalo"
                    )
                copy_atomic(path, self.backup_path(project.id))
            project.touch()
            atomic_write_json(path, project.model_dump(mode="json"))
        return project

    def delete(self, project_id: str) -> None:
        path = self.path(project_id)
        backup = self.backup_path(project_id)
        with self._lock(project_id):
            if not path.is_file() and not backup.is_file():
                raise NotFoundError(f"progetto non trovato: {project_id}")
            path.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
        with self._locks_guard:
            self._locks.pop(project_id, None)

    def duplicate(self, project_id: str, name_suffix: str = " copy") -> Project:
        original = self.get(project_id)
        new_id_value = new_id("project")
        new_name = f"{original.name}{name_suffix}"[:200]
        copy = original.model_copy(deep=True)
        copy.id = new_id_value
        copy.name = new_name
        copy.created_at = utcnow()
        copy.updated_at = utcnow()
        copy.slides = [
            self._clone_slide(slide) for slide in copy.slides
        ]
        return self.save(copy)

    @staticmethod
    def _clone_slide(slide: Slide) -> Slide:
        clone = slide.model_copy(deep=True)
        clone.id = new_id("slide")
        clone.elements = [ProjectStore._clone_element(element) for element in clone.elements]
        return clone

    @staticmethod
    def _clone_element(element: Element) -> Element:
        clone = element.model_copy(deep=True)
        clone.id = new_id("element")
        return clone

    # -- manutenzione -----------------------------------------------------

    def snapshot_backup(self, project_id: str, keep: int = 10) -> Path:
        """Copia datata del progetto in ``backups/`` e pota le più vecchie."""
        source = self.path(project_id)
        if not source.is_file():
            raise NotFoundError(f"progetto non trovato: {project_id}")
        stamp = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        target = self._paths.backups / f"{project_id}-{stamp}.json"
        copy_atomic(source, target)
        self._prune_backups(project_id, keep)
        return target

    def _prune_backups(self, project_id: str, keep: int) -> None:
        backups = sorted(self._paths.backups.glob(f"{project_id}-*.json"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)


def project_to_dict(project: Project) -> dict[str, Any]:
    return project.model_dump(mode="json")
