from __future__ import annotations

import io

import httpx
import pytest

from doublescreener import __version__
from doublescreener.server.runtime import ServerRuntime


def png_bytes(width: int = 4, height: int = 3) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


async def _create(client: httpx.AsyncClient, name: str = "Lezione") -> dict:
    response = await client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def test_info(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DoubleScreener"
    assert data["version"] == __version__
    assert data["port"] == 8765
    assert data["urls"]["local"].endswith(":8765/p")
    assert data["presentation"] is None


async def test_root_redirects_to_info(client: httpx.AsyncClient) -> None:
    response = await client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/api/info"


async def test_canvas_page_and_qwebchannel(client: httpx.AsyncClient) -> None:
    pytest.importorskip("PyQt6.QtWebChannel")

    page = await client.get("/editor-canvas")
    assert page.status_code == 200
    assert "canvas.js" in page.text

    script = await client.get("/qtwebchannel.js")
    assert script.status_code == 200
    assert "QWebChannel" in script.text
    assert script.headers["content-type"].startswith("application/javascript")


async def test_create_list_get(client: httpx.AsyncClient) -> None:
    created = await _create(client, "Lezione 1")
    assert created["id"].startswith("prj_")
    assert created["schema_version"] == 1
    assert len(created["slides"]) == 1
    assert created["slides"][0]["kind"] == "html"

    listed = (await client.get("/api/projects")).json()
    assert [item["name"] for item in listed] == ["Lezione 1"]
    assert listed[0]["slide_count"] == 1

    response = await client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.headers["etag"]
    assert response.json()["name"] == "Lezione 1"


async def test_get_missing_project(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/projects/prj_" + "A" * 26)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_update_project_with_etag(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    etag = (await client.get(f"/api/projects/{project['id']}")).headers["etag"]

    project["name"] = "Rinominato"
    response = await client.put(
        f"/api/projects/{project['id']}", json=project, headers={"If-Match": etag}
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Rinominato"


async def test_update_conflict(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    original = await client.get(f"/api/projects/{project['id']}")
    etag = original.headers["etag"]

    project["name"] = "Prima modifica"
    assert (
        await client.put(
            f"/api/projects/{project['id']}", json=project, headers={"If-Match": etag}
        )
    ).status_code == 200

    project["name"] = "Seconda modifica"
    response = await client.put(
        f"/api/projects/{project['id']}", json=project, headers={"If-Match": etag}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_update_rejects_id_mismatch(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    original_id = project["id"]
    project["id"] = "prj_" + "B" * 26
    response = await client.put(f"/api/projects/{original_id}", json=project)
    assert response.status_code == 400


async def test_delete_project(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    response = await client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 204
    assert (await client.get(f"/api/projects/{project['id']}")).status_code == 404


async def test_duplicate_project(client: httpx.AsyncClient) -> None:
    project = await _create(client, "Originale")
    response = await client.post(
        f"/api/projects/{project['id']}/duplicate", json={"name_suffix": " (copia)"}
    )
    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != project["id"]
    assert copy["name"] == "Originale (copia)"
    assert copy["slides"][0]["id"] != project["slides"][0]["id"]


async def test_create_validation_error(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/projects", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_upload_and_download_asset(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    data = png_bytes(4, 3)

    response = await client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("foto.png", data, "image/png")},
    )
    assert response.status_code == 201, response.text
    meta = response.json()
    assert meta["kind"] == "image"
    assert meta["width"] == 4
    assert meta["height"] == 3
    assert meta["url"] == f"/api/assets/{meta['id']}"

    download = await client.get(meta["url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.content == data


async def test_asset_dedupe(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    data = png_bytes()
    first = (
        await client.post(
            f"/api/projects/{project['id']}/assets",
            files={"file": ("a.png", data, "image/png")},
        )
    ).json()
    second = (
        await client.post(
            f"/api/projects/{project['id']}/assets",
            files={"file": ("b.png", data, "image/png")},
        )
    ).json()
    assert first["id"] == second["id"]
    assert len((await client.get("/api/assets")).json()) == 1


async def test_upload_invalid_asset(client: httpx.AsyncClient) -> None:
    project = await _create(client)
    response = await client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("nota.txt", b"testo", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_asset"


async def test_upload_to_missing_project(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/projects/prj_" + "C" * 26 + "/assets",
        files={"file": ("x.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 404


async def test_upload_pdf(client: httpx.AsyncClient) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    document.new_page(width=595, height=842)
    data = document.tobytes()
    document.close()

    project = await _create(client)
    response = await client.post(
        f"/api/projects/{project['id']}/pdf",
        files={"file": ("slide.pdf", data, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["pages"] == 1
    assert body["source_name"] == "slide.pdf"
    assert body["asset_id"].startswith("ast_")


def test_embedded_server_starts_and_stops(paths) -> None:
    runtime = ServerRuntime(paths, host="127.0.0.1", port=0)
    runtime.start()
    try:
        assert runtime.port > 0
        response = httpx.get(f"{runtime.url}/api/info", timeout=5)
        assert response.status_code == 200
        assert response.json()["version"] == __version__
    finally:
        runtime.stop()
    assert not runtime.running
