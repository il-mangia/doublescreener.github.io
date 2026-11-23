"""Cronologia undo/redo basata su comandi."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from .models import Project


@dataclass(slots=True)
class Command:
    label: str
    apply: Callable[[Project], None]
    revert: Callable[[Project], None]
    merge_key: str | None = None
    timestamp: float = field(default_factory=time.monotonic)

    def merged_with(self, newer: Command) -> Command:
        """Fonde due comandi consecutivi mantenendo il revert del primo."""
        return Command(
            label=newer.label,
            apply=newer.apply,
            revert=self.revert,
            merge_key=newer.merge_key or self.merge_key,
            timestamp=newer.timestamp,
        )


class History:
    def __init__(self, limit: int = 200, merge_window: float = 0.6) -> None:
        if limit < 1:
            raise ValueError("limit deve essere almeno 1")
        self._limit = limit
        self._merge_window = merge_window
        self._undo: deque[Command] = deque(maxlen=limit)
        self._redo: list[Command] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str | None:
        return self._undo[-1].label if self._undo else None

    @property
    def redo_label(self) -> str | None:
        return self._redo[-1].label if self._redo else None

    def execute(self, project: Project, command: Command) -> Command:
        command.apply(project)
        self.record(command)
        return command

    def record(self, command: Command) -> None:
        self._redo.clear()
        if (
            self._undo
            and command.merge_key is not None
            and self._undo[-1].merge_key == command.merge_key
            and command.timestamp - self._undo[-1].timestamp <= self._merge_window
        ):
            self._undo[-1] = self._undo[-1].merged_with(command)
        else:
            self._undo.append(command)

    def undo(self, project: Project) -> Command | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        command.revert(project)
        self._redo.append(command)
        return command

    def redo(self, project: Project) -> Command | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        command.apply(project)
        self._undo.append(command)
        return command

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def __len__(self) -> int:
        return len(self._undo)
