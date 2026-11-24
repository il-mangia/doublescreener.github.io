from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest

from doublescreener.core.assets import AssetStore
from doublescreener.core.errors import AssetError, NotFoundError
from doublescreener.pdf.importer import build_slides, inspect, parse_pages
from doublescreener.pdf.renderer import PdfRenderer, clamp_width


def pdf_bytes(pages: int = 3, width: float = 595, height: float = 842) -> bytes:
    import pymupdf

    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page(width=width, height=height)
        page.draw_rect(
            pymupdf.Rect(40, 40, width - 40, height - 40),
            color=(0.1, 0.3, 0.7),
            fill=(0.92, 0.95, 1.0),
        )
        page.insert_text((72, 120), f"Pagina {number}", fontsize=28)
    data = document.tobytes()
    document.close()
    return data


def png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), "red").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("spec", "total", "expected"),
    [
        (None, 3, [1, 2, 3]),
        ("", 2, [1, 2]),
        ("all", 2, [1, 2]),
        ("tutte", 2, [1, 2]),
        ("1-2,4", 5, [1, 2, 4]),
        ("3", 5, [3]),
        ("1-2,2-3", 3, [1, 2, 3]),
        (" 2 - 3 ", 4, [2, 3]),
    ],
)
def test_parse_pages(spec: str | None, total: int, expected: list[int]) -> None:
    assert parse_pages(spec, total) == expected


@pytest.mark.parametrize("spec", ["0", "4", "3-2", "a", "1-", "10-12"])
def test_parse_pages_rejects_invalid(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_pages(spec, 3)


def test_inspect_and_build_slides(assets: AssetStore, tmp_path: Path) -> None:
    meta = assets.save_bytes(pdf_bytes(4), "lezione.pdf")
    assert meta.kind == "pdf"
    assert meta.pages == 4

    info = inspect(assets.path(meta.id))
    assert info.pages == 4
    assert round(info.width) == 595
    assert round(info.height) == 842

    slides = build_slides(meta, [2, 4])
    assert [slide.name for slide in slides] == ["Pagina 2", "Pagina 4"]
    assert all(slide.kind == "pdf_page" for slide in slides)
    assert slides[0].pdf is not None
    assert slides[0].pdf.asset_id == meta.id
    assert slides[0].pdf.page == 2
    assert slides[0].pdf.source_name == "lezione.pdf"


def test_build_slides_validates_pages(assets: AssetStore) -> None:
    meta = assets.save_bytes(pdf_bytes(2), "doc.pdf")
    with pytest.raises(ValueError):
        build_slides(meta, [3])

    image = assets.save_bytes(png_bytes(), "foto.png")
    with pytest.raises(AssetError):
        build_slides(image, [1])


def test_renderer_cache_and_purge(paths, assets: AssetStore) -> None:
    meta = assets.save_bytes(pdf_bytes(2), "doc.pdf")
    renderer = PdfRenderer(paths, assets)

    target = renderer.render(meta.id, 2, 800)
    assert target.is_file()
    first_mtime = target.stat().st_mtime_ns

    from PIL import Image

    with Image.open(target) as image:
        assert image.format == "WEBP"
        assert image.width == 800

    assert renderer.render(meta.id, 2, 800) == target
    assert target.stat().st_mtime_ns == first_mtime

    assert renderer.purge(meta.id) == 1
    assert not target.exists()
    assert renderer.render(meta.id, 2, 800).is_file()


def test_renderer_rejects_bad_requests(paths, assets: AssetStore) -> None:
    meta = assets.save_bytes(pdf_bytes(2), "doc.pdf")
    renderer = PdfRenderer(paths, assets)

    with pytest.raises(NotFoundError):
        renderer.render(meta.id, 3, 800)
    with pytest.raises(NotFoundError):
        renderer.render(meta.id, 0, 800)

    image = assets.save_bytes(png_bytes(), "foto.png")
    with pytest.raises(AssetError):
        renderer.render(image.id, 1, 800)


def test_clamp_width() -> None:
    assert clamp_width(1) == 320
    assert clamp_width(1000) == 1000
    assert clamp_width(99999) == 3840


async def _create_project(client: httpx.AsyncClient) -> dict:
    response = await client.post("/api/projects", json={"name": "PDF"})
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_pdf(client: httpx.AsyncClient, project_id: str, data: bytes) -> dict:
    response = await client.post(
        f"/api/projects/{project_id}/pdf",
        files={"file": ("lezione.pdf", data, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_pdf_upload_and_page_endpoint(client: httpx.AsyncClient) -> None:
    project = await _create_project(client)
    uploaded = await _upload_pdf(client, project["id"], pdf_bytes(3))
    assert uploaded["pages"] == 3
    assert uploaded["source_name"] == "lezione.pdf"

    page = await client.get(f"/api/assets/{uploaded['asset_id']}/pages/2?width=640")
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/webp"
    assert page.headers["cache-control"].startswith("public")
    assert page.content.startswith(b"RIFF")
    assert b"WEBP" in page.content[:16]
    assert page.headers["etag"] == f'"{uploaded["asset_id"]}-p2-w640"'

    cached = await client.get(f"/api/assets/{uploaded['asset_id']}/pages/2?width=640")
    assert cached.status_code == 200
    assert cached.content == page.content


async def test_pdf_page_errors(client: httpx.AsyncClient) -> None:
    project = await _create_project(client)
    uploaded = await _upload_pdf(client, project["id"], pdf_bytes(2))

    missing = await client.get(f"/api/assets/{uploaded['asset_id']}/pages/9")
    assert missing.status_code == 404

    zero = await client.get(f"/api/assets/{uploaded['asset_id']}/pages/0")
    assert zero.status_code == 404

    image = await client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("foto.png", png_bytes(), "image/png")},
    )
    assert image.status_code == 201
    not_pdf = await client.get(f"/api/assets/{image.json()['id']}/pages/1")
    assert not_pdf.status_code == 400
    assert not_pdf.json()["error"]["code"] == "invalid_asset"


async def test_pdf_upload_rejects_corrupt_file(client: httpx.AsyncClient) -> None:
    project = await _create_project(client)
    response = await client.post(
        f"/api/projects/{project['id']}/pdf",
        files={"file": ("rotto.pdf", b"%PDF-1.7 non davvero un pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_asset"


async def test_pdf_page_width_is_clamped(client: httpx.AsyncClient) -> None:
    from PIL import Image

    project = await _create_project(client)
    uploaded = await _upload_pdf(client, project["id"], pdf_bytes(1))
    response = await client.get(
        f"/api/assets/{uploaded['asset_id']}/pages/1?width=99999"
    )
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.width == 3840
