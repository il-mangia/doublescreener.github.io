"""Rendering delle pagine PDF in immagini, con cache su disco.

Le pagine sono renderizzate con PyMuPDF e codificate in WebP con Pillow (la
build di PyMuPDF può non includere il codec WebP). La cache vive in
``<data>/cache/pdf`` e la chiave è ``asset + pagina + larghezza``: gli asset
sono immutabili, quindi non serve invalidare se non alla cancellazione.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from pathlib import Path

from PIL import Image

from ..config import Paths
from ..core.assets import AssetStore
from ..core.errors import AssetError, NotFoundError

log = logging.getLogger(__name__)

MIN_WIDTH = 320
MAX_WIDTH = 3840
DEFAULT_QUALITY = 82
_CACHE_RE = re.compile(r"^(?P<asset>ast_[0-9A-Za-z]{1,32})-p(?P<page>\d+)-w(?P<width>\d+)\.webp$")


def clamp_width(width: int) -> int:
    try:
        value = int(width)
    except (TypeError, ValueError):
        value = MIN_WIDTH
    return max(MIN_WIDTH, min(value, MAX_WIDTH))


class PdfRenderer:
    def __init__(
        self,
        paths: Paths,
        assets: AssetStore,
        *,
        quality: int = DEFAULT_QUALITY,
    ) -> None:
        self._assets = assets
        self._root = paths.pdf_cache
        self._root.mkdir(parents=True, exist_ok=True)
        self._quality = max(30, min(int(quality), 95))
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # -- cache ------------------------------------------------------------

    def _cache_path(self, asset_id: str, page: int, width: int) -> Path:
        return self._root / f"{asset_id}-p{page}-w{width}.webp"

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def purge(self, asset_id: str) -> int:
        """Rimuove dalla cache tutte le pagine di un asset. Ritorna quante ne ha tolte."""
        removed = 0
        for path in self._root.glob(f"{asset_id}-p*.webp"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    # -- rendering --------------------------------------------------------

    def render(self, asset_id: str, page: int, width: int) -> Path:
        """Ritorna il percorso dell'immagine, renderizzandola se non in cache."""
        width = clamp_width(width)
        meta = self._assets.meta(asset_id)
        if meta.kind != "pdf":
            raise AssetError(f"l'asset {asset_id} non è un PDF")
        if page < 1:
            raise NotFoundError(f"pagina non valida: {page}")
        if meta.pages is not None and page > meta.pages:
            raise NotFoundError(
                f"pagina {page} fuori intervallo (1–{meta.pages}) per {asset_id}"
            )

        target = self._cache_path(asset_id, page, width)
        if self._is_ready(target):
            return target

        with self._lock_for(target.name):
            if self._is_ready(target):
                return target
            data = self._render_page(self._assets.path(asset_id), page, width)
            tmp = target.with_name(f"{target.name}.{threading.get_ident()}.tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
            log.debug("pagina PDF renderizzata %s (%d byte)", target.name, len(data))
        return target

    @staticmethod
    def _is_ready(path: Path) -> bool:
        try:
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    def _render_page(self, source: Path, page: int, width: int) -> bytes:
        try:
            import pymupdf
        except ImportError as exc:  # pragma: no cover - dipendenza installata
            raise AssetError("PyMuPDF non disponibile") from exc
        try:
            with pymupdf.open(source) as document:
                if document.needs_pass:
                    raise AssetError("il PDF è protetto da password")
                if not 1 <= page <= document.page_count:
                    raise NotFoundError(
                        f"pagina {page} fuori intervallo (1–{document.page_count})"
                    )
                pdf_page = document[page - 1]
                zoom = width / max(1.0, float(pdf_page.rect.width))
                pixmap = pdf_page.get_pixmap(
                    matrix=pymupdf.Matrix(zoom, zoom), alpha=False
                )
                image = Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
                buffer = io.BytesIO()
                image.save(buffer, format="WEBP", quality=self._quality, method=4)
                return buffer.getvalue()
        except (AssetError, NotFoundError):
            raise
        except Exception as exc:  # PyMuPDF solleva eccezioni proprie
            raise AssetError(f"impossibile renderizzare la pagina: {exc}") from exc
