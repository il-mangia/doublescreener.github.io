from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from PIL import Image

from doublescreener.config import Paths
from doublescreener.core.errors import SchemaError
from doublescreener.core.models import Element, ElementContent, PdfRef, Slide
from doublescreener.export import (
    estimate_export_bytes,
    export_single_file,
    export_static_site,
)
from doublescreener.pdf.renderer import PdfRenderer
from doublescreener.server.app_factory import create_app


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (40, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Export PDF", fontsize=24)
    data = document.tobytes()
    document.close()
    return data


def _build_mixed_project(store, assets):
    img_meta = assets.save_bytes(_png_bytes(), "photo.png")
    pdf_meta = assets.save_bytes(_pdf_bytes(), "slides.pdf")

    project = store.create("Corso Reti")
    project.slides = [
        Slide(
            name="Intro",
            elements=[
                Element(type="text", content=ElementContent(text="Benvenuti </script>")),
                Element(
                    type="image",
                    content=ElementContent(asset_id=img_meta.id, alt="Foto"),
                ),
            ],
        ),
        Slide(
            name="PDF p.1",
            kind="pdf_page",
            pdf=PdfRef(asset_id=pdf_meta.id, page=1, source_name="slides.pdf"),
        ),
    ]
    return store.save(project), img_meta, pdf_meta


def test_export_static_site_folder(paths: Paths, store, assets, tmp_path: Path) -> None:
    project, img_meta, pdf_meta = _build_mixed_project(store, assets)
    pdf_renderer = PdfRenderer(paths, assets)
    target = tmp_path / "export-folder"

    result = export_static_site(project, target, assets, pdf_renderer, pdf_width=640)

    assert result.format == "folder"
    assert result.warning is None
    assert (target / "index.html").is_file()
    assert (target / "project.json").is_file()
    assert (target / "deck.js").is_file()
    assert (target / "renderer.js").is_file()
    assert (target / "renderer.css").is_file()
    assert (target / "transitions.css").is_file()
    assert (target / "player.css").is_file()
    assert (target / "standalone.js").is_file()
    assert (target / "assets" / f"{img_meta.id}.png").is_file()
    assert (target / "assets" / f"{pdf_meta.id}_p1.webp").is_file()

    index_html = (target / "index.html").read_text(encoding="utf-8")
    assert 'src="renderer.js"' in index_html
    assert 'src="deck.js"' in index_html
    assert 'src="standalone.js"' in index_html
    assert "/api/" not in index_html

    deck = json.loads((target / "project.json").read_text(encoding="utf-8"))
    assert deck["project"]["name"] == "Corso Reti"
    assert deck["assets"][img_meta.id] == f"assets/{img_meta.id}.png"
    assert deck["slides"][1]["pdf"]["image_url"] == f"assets/{pdf_meta.id}_p1.webp"


def test_export_single_file_and_warning(
    paths: Paths, store, assets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _img_meta, _pdf_meta = _build_mixed_project(store, assets)
    pdf_renderer = PdfRenderer(paths, assets)
    out_file = tmp_path / "deck.html"

    result = export_single_file(project, out_file, assets, pdf_renderer, pdf_width=640)

    assert result.format == "single_file"
    assert result.file_count == 1
    assert out_file.is_file()
    html_text = out_file.read_text(encoding="utf-8")
    assert "data:image/png;base64," in html_text
    assert "data:image/webp;base64," in html_text
    assert "\\u003c/script>" in html_text
    assert '<script src="' not in html_text
    assert '<link rel="stylesheet"' not in html_text

    # Verifica warning oltre soglia
    from doublescreener.export import single_file as sf_mod

    monkeypatch.setattr(sf_mod, "SINGLE_FILE_WARNING_BYTES", 1024)
    warn_result = export_single_file(
        project, tmp_path / "warn.html", assets, pdf_renderer, pdf_width=640
    )
    assert warn_result.warning == "size_exceeded"

    est = estimate_export_bytes(project, assets, pdf_renderer, pdf_width=640, inline=True)
    assert est > 0


def test_import_project_json_validates_and_avoids_collision(store, tmp_path: Path) -> None:
    original = store.create("Originale")
    exported_json = tmp_path / "project.json"
    exported_json.write_text(
        json.dumps(original.model_dump(mode="json")), encoding="utf-8"
    )

    imported = store.import_file(exported_json)
    assert imported.id != original.id
    assert imported.name == "Originale"
    assert store.exists(original.id)
    assert store.exists(imported.id)

    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"schema_version": 999}', encoding="utf-8")
    with pytest.raises(SchemaError):
        store.import_file(bad_file)


async def test_export_api_folder_and_single_file(paths: Paths) -> None:
    app = create_app(paths)
    state = app.state.ds
    project, _img, _pdf = _build_mixed_project(state.store, state.assets)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/projects/{project.id}/export", json={"format": "folder"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "folder"
        dl = await client.get(body["download_url"])
        assert dl.status_code == 200
        with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
            names = set(zf.namelist())
            assert "index.html" in names
            assert "project.json" in names
            assert "renderer.js" in names

        resp2 = await client.post(
            f"/api/projects/{project.id}/export", json={"format": "single_file"}
        )
        assert resp2.status_code == 200
        dl2 = await client.get(resp2.json()["download_url"])
        assert dl2.status_code == 200
        assert b"window.__DS_DECK__" in dl2.content

        missing = await client.get("/api/exports/invalid_id/download")
        assert missing.status_code == 404
