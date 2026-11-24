"""Temi colore applicabili a un progetto.

Un tema è solo un insieme di colori: il progetto salva il suo id e i template
usano la palette al momento della creazione. Applicare un tema aggiorna lo
sfondo del canvas e i colori degli elementi che corrispondevano alla vecchia
palette, lasciando intatti i colori personalizzati.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Project

DEFAULT_THEME = "dark"


@dataclass(frozen=True, slots=True)
class Theme:
    id: str
    name_key: str
    background: str
    surface: str
    text: str
    muted: str
    accent: str


THEMES: tuple[Theme, ...] = (
    Theme(
        id="dark",
        name_key="theme.dark",
        background="#101014",
        surface="#1b2030",
        text="#f5f7fb",
        muted="#9fb0cc",
        accent="#4cc9f0",
    ),
    Theme(
        id="light",
        name_key="theme.light",
        background="#f7f8fb",
        surface="#ffffff",
        text="#10131a",
        muted="#5b6472",
        accent="#2563eb",
    ),
    Theme(
        id="ocean",
        name_key="theme.ocean",
        background="#06202b",
        surface="#0d3446",
        text="#e6fbff",
        muted="#8ec7d8",
        accent="#22d3ee",
    ),
    Theme(
        id="sunset",
        name_key="theme.sunset",
        background="#1d1020",
        surface="#3a1c2e",
        text="#fff1e6",
        muted="#e0b0a0",
        accent="#ff7a59",
    ),
)

THEME_IDS = tuple(theme.id for theme in THEMES)
_BY_ID = {theme.id: theme for theme in THEMES}


def get_theme(theme_id: str | None) -> Theme:
    return _BY_ID.get(theme_id or DEFAULT_THEME, _BY_ID[DEFAULT_THEME])


def apply_to_project(project: Project, theme_id: str) -> None:
    """Imposta il tema e riallinea i colori derivati dalla palette precedente."""
    previous = get_theme(project.theme)
    theme = get_theme(theme_id)
    project.theme = theme.id
    project.canvas.background = theme.background

    for slide in project.slides:
        if slide.background in (None, "", previous.background):
            slide.background = None
        for element in slide.elements:
            style = element.style
            if style.color == previous.text:
                style.color = theme.text
            elif style.color == previous.muted:
                style.color = theme.muted
            if style.background == previous.surface:
                style.background = theme.surface
            elif style.background == previous.accent:
                style.background = theme.accent
            if style.border_color == previous.accent:
                style.border_color = theme.accent
