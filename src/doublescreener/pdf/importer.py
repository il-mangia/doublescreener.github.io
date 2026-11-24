"""Importazione di PDF: ispezione, intervalli di pagine, creazione slide."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..core.assets import AssetMeta
from ..core.errors import AssetError
from ..core.models import PdfRef, Slide

_ALL = {"all", "*", "tutte", "tutti", "tutto"}
_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


@dataclass(frozen=True, slots=True)
class PdfInfo:
    pages: int
    width: float
    height: float
    title: str


def inspect(path: Path) -> PdfInfo:
    """Legge numero di pagine, dimensioni della prima pagina e titolo."""
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dipendenza installata
        raise AssetError("PyMuPDF non disponibile") from exc
    try:
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise AssetError("il PDF è protetto da password")
            if document.page_count == 0:
                raise AssetError("il PDF non contiene pagine")
            rect = document[0].rect
            return PdfInfo(
                pages=document.page_count,
                width=float(rect.width),
                height=float(rect.height),
                title=(document.metadata or {}).get("title") or path.stem,
            )
    except AssetError:
        raise
    except Exception as exc:  # PyMuPDF solleva eccezioni proprie
        raise AssetError(f"PDF non valido: {exc}") from exc


def parse_pages(spec: str | None, total: int) -> list[int]:
    """Converte ``"1-3,5"`` (o ``"all"``) in una lista di pagine 1-based.

    I duplicati vengono rimossi mantenendo l'ordine di scrittura.
    """
    if total < 1:
        raise ValueError("il PDF non contiene pagine")
    text = (spec or "").strip().lower()
    if not text or text in _ALL:
        return list(range(1, total + 1))

    pages: list[int] = []
    seen: set[int] = set()
    for chunk in text.split(","):
        if not chunk.strip():
            continue
        match = _RANGE_RE.match(chunk)
        if not match:
            raise ValueError(f"intervallo di pagine non valido: {chunk.strip()!r}")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end:
            raise ValueError(f"intervallo invertito: {chunk.strip()!r}")
        if start < 1 or end > total:
            raise ValueError(f"pagine fuori intervallo 1–{total}: {chunk.strip()!r}")
        for page in range(start, end + 1):
            if page not in seen:
                seen.add(page)
                pages.append(page)
    if not pages:
        raise ValueError("nessuna pagina selezionata")
    return pages


def build_slides(
    meta: AssetMeta,
    pages: list[int],
    *,
    name_template: str = "Pagina {page}",
) -> list[Slide]:
    """Crea una slide ``pdf_page`` per ogni pagina richiesta."""
    if meta.kind != "pdf":
        raise AssetError(f"l'asset {meta.id} non è un PDF")
    total = meta.pages or 0
    slides: list[Slide] = []
    for page in pages:
        if page < 1 or (total and page > total):
            raise ValueError(f"pagina fuori intervallo: {page}")
        slides.append(
            Slide(
                kind="pdf_page",
                name=name_template.format(page=page, total=total),
                pdf=PdfRef(
                    asset_id=meta.id,
                    page=page,
                    source_name=meta.original_name,
                ),
            )
        )
    return slides
