from __future__ import annotations

import io

import pytest
from PIL import Image

from doublescreener.core import assets as assets_module
from doublescreener.core.errors import AssetError, NotFoundError


def _png_bytes(width: int = 12, height: int = 8) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def test_save_image_and_probe(assets) -> None:
    meta = assets.save_bytes(_png_bytes(12, 8), "foto.png")

    assert meta.kind == "image"
    assert meta.mime == "image/png"
    assert meta.ext == ".png"
    assert meta.width == 12
    assert meta.height == 8
    assert meta.original_name == "foto.png"
    assert assets.path(meta.id).read_bytes() == _png_bytes(12, 8)


def test_dedupe_by_hash(assets) -> None:
    data = _png_bytes()
    first = assets.save_bytes(data, "a.png")
    second = assets.save_bytes(data, "b.png")
    assert first.id == second.id
    assert len(assets.list()) == 1


def test_reject_unknown_format(assets) -> None:
    with pytest.raises(AssetError):
        assets.save_bytes(b"ciao mondo", "nota.txt")


def test_reject_empty(assets) -> None:
    with pytest.raises(AssetError):
        assets.save_bytes(b"", "vuoto.png")


def test_sanitize_original_name(assets) -> None:
    meta = assets.save_bytes(_png_bytes(), "..\\..\\cartella\\foto.png")
    assert meta.original_name == "foto.png"


def test_delete_asset(assets) -> None:
    meta = assets.save_bytes(_png_bytes(), "x.png")
    assets.delete(meta.id)
    with pytest.raises(NotFoundError):
        assets.meta(meta.id)


def test_missing_asset(assets) -> None:
    with pytest.raises(NotFoundError):
        assets.meta("ast_" + "Z" * 26)


def test_pdf_metadata(assets) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    document.new_page(width=595, height=842)
    data = document.tobytes()
    document.close()

    meta = assets.save_bytes(data, "slide.pdf")
    assert meta.kind == "pdf"
    assert meta.mime == "application/pdf"
    assert meta.pages == 1
    assert meta.width == 595
    assert meta.height == 842


def test_size_limit(assets, monkeypatch) -> None:
    monkeypatch.setattr(assets_module, "MAX_ASSET_BYTES", 10)
    with pytest.raises(AssetError):
        assets.save_bytes(b"x" * 11, "grande.png")


def test_save_upload(assets) -> None:
    stream = io.BytesIO(_png_bytes())
    meta = assets.save_upload(stream, "upload.png")
    assert meta.kind == "image"
    assert assets.path(meta.id).is_file()
