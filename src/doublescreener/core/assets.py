"""Archivio degli asset (immagini e PDF) con deduplica per hash.

Layout: ``<data>/assets/<asset_id><ext>`` + ``<asset_id>.json`` con i metadati.
Il nome originale è conservato solo come informazione, mai usato come path.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from ..config import Paths
from .errors import AssetError, NotFoundError
from .ids import new_id
from .jsonio import atomic_write_bytes, atomic_write_json, read_json
from .models import ID_PATTERN

log = logging.getLogger(__name__)

MAX_ASSET_BYTES = 200 * 1024 * 1024
_CHUNK = 1024 * 1024
_ID_RE = re.compile(ID_PATTERN)

AssetKind = Literal["image", "pdf"]


class AssetMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    kind: AssetKind
    mime: str
    ext: str
    original_name: str
    size: int
    sha256: str
    width: int | None = None
    height: int | None = None
    pages: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_SVG_PREFIXES = (b"<svg", b"<?xml")


def _sniff(data: bytes) -> tuple[AssetKind, str, str]:
    """Riconosce il tipo dal contenuto, non dall'estensione."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg", ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image", "image/gif", ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image", "image/webp", ".webp"
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf", ".pdf"
    head = data[:2048].lstrip().lower()
    if head.startswith(_SVG_PREFIXES) and b"<svg" in head:
        return "image", "image/svg+xml", ".svg"
    raise AssetError(
        "formato non supportato: ammessi PNG, JPEG, GIF, WebP, SVG e PDF"
    )


def _probe_image(data: bytes) -> tuple[int | None, int | None]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.width, image.height
    except UnidentifiedImageError:
        # SVG e formati non gestiti da Pillow: dimensioni non note.
        return None, None


def _probe_pdf(data: bytes) -> tuple[int | None, int | None, int | None]:
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - dipendenza installata
        return None, None, None
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass:
                raise AssetError("il PDF è protetto da password")
            width = height = None
            if document.page_count:
                rect = document[0].rect
                width, height = round(rect.width), round(rect.height)
            return document.page_count, width, height
    except AssetError:
        raise
    except Exception as exc:  # PyMuPDF solleva eccezioni proprie
        raise AssetError(f"PDF non valido: {exc}") from exc


def _clean_name(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[:255] or "file"


class AssetStore:
    def __init__(self, paths: Paths) -> None:
        self._root = paths.assets
        self._root.mkdir(parents=True, exist_ok=True)

    # -- percorsi ---------------------------------------------------------

    def _meta_path(self, asset_id: str) -> Path:
        self._validate_id(asset_id)
        return self._root / f"{asset_id}.json"

    def _file_path(self, asset_id: str, ext: str) -> Path:
        self._validate_id(asset_id)
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", ext):
            raise ValueError(f"estensione non valida: {ext!r}")
        return self._root / f"{asset_id}{ext}"

    @staticmethod
    def _validate_id(asset_id: str) -> str:
        if not isinstance(asset_id, str) or not _ID_RE.match(asset_id):
            raise ValueError(f"id asset non valido: {asset_id!r}")
        return asset_id

    # -- salvataggio ------------------------------------------------------

    def save_bytes(self, data: bytes, original_name: str) -> AssetMeta:
        if not data:
            raise AssetError("file vuoto")
        if len(data) > MAX_ASSET_BYTES:
            raise AssetError(
                f"file troppo grande: massimo {MAX_ASSET_BYTES // (1024 * 1024)} MB"
            )
        kind, mime, ext = _sniff(data)
        digest = hashlib.sha256(data).hexdigest()
        existing = self._find_by_hash(digest)
        if existing is not None:
            return existing

        asset_id = new_id("asset")
        width = height = pages = None
        if kind == "image":
            width, height = _probe_image(data)
        elif kind == "pdf":
            pages, width, height = _probe_pdf(data)

        meta = AssetMeta(
            id=asset_id,
            kind=kind,
            mime=mime,
            ext=ext,
            original_name=_clean_name(original_name),
            size=len(data),
            sha256=digest,
            width=width,
            height=height,
            pages=pages,
        )
        atomic_write_bytes(self._file_path(asset_id, ext), data)
        atomic_write_json(self._meta_path(asset_id), meta.model_dump(mode="json"))
        log.info("asset salvato %s (%s, %d byte)", asset_id, kind, len(data))
        return meta

    def save_upload(self, stream: BinaryIO, original_name: str) -> AssetMeta:
        buffer = bytearray()
        while chunk := stream.read(_CHUNK):
            buffer.extend(chunk)
            if len(buffer) > MAX_ASSET_BYTES:
                raise AssetError(
                    f"file troppo grande: massimo {MAX_ASSET_BYTES // (1024 * 1024)} MB"
                )
        return self.save_bytes(bytes(buffer), original_name)

    # -- lettura ----------------------------------------------------------

    def meta(self, asset_id: str) -> AssetMeta:
        path = self._meta_path(asset_id)
        try:
            return AssetMeta.model_validate(read_json(path))
        except FileNotFoundError:
            raise NotFoundError(f"asset non trovato: {asset_id}") from None

    def path(self, asset_id: str) -> Path:
        meta = self.meta(asset_id)
        path = self._file_path(asset_id, meta.ext)
        if not path.is_file():
            raise NotFoundError(f"file dell'asset mancante: {asset_id}")
        return path

    def read_bytes(self, asset_id: str) -> bytes:
        return self.path(asset_id).read_bytes()

    def exists(self, asset_id: str) -> bool:
        return self._meta_path(asset_id).is_file()

    def list(self) -> list[AssetMeta]:
        metas: list[AssetMeta] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                metas.append(AssetMeta.model_validate(read_json(path)))
            except (OSError, ValueError) as exc:
                log.warning("metadati asset ignorati %s: %s", path.name, exc)
        return metas

    # -- manutenzione -----------------------------------------------------

    def delete(self, asset_id: str) -> None:
        meta = self.meta(asset_id)
        self._file_path(asset_id, meta.ext).unlink(missing_ok=True)
        self._meta_path(asset_id).unlink(missing_ok=True)

    def _find_by_hash(self, digest: str) -> AssetMeta | None:
        for meta in self.list():
            if meta.sha256 == digest:
                return meta
        return None
