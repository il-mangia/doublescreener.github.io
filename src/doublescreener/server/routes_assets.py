"""Rotte REST degli asset: upload, download, import PDF."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

from ..core.errors import AssetError
from .routes_projects import state_of

router = APIRouter(prefix="/api", tags=["assets"])


def _asset_payload(meta: Any) -> dict[str, Any]:
    payload = meta.model_dump(mode="json")
    payload["url"] = f"/api/assets/{meta.id}"
    return payload


@router.get("/assets")
async def list_assets(request: Request) -> list[dict[str, Any]]:
    state = state_of(request)
    return [_asset_payload(meta) for meta in state.assets.list()]


@router.post("/projects/{project_id}/assets", status_code=201)
async def upload_asset(
    project_id: str, request: Request, file: Annotated[UploadFile, File()]
) -> dict[str, Any]:
    state = state_of(request)
    state.store.get(project_id)  # 404 se il progetto non esiste
    meta = state.assets.save_upload(file.file, file.filename or "file")
    return _asset_payload(meta)


@router.post("/projects/{project_id}/pdf", status_code=201)
async def upload_pdf(
    project_id: str, request: Request, file: Annotated[UploadFile, File()]
) -> dict[str, Any]:
    state = state_of(request)
    state.store.get(project_id)
    meta = state.assets.save_upload(file.file, file.filename or "document.pdf")
    if meta.kind != "pdf":
        raise AssetError("il file caricato non è un PDF")
    return {
        "asset_id": meta.id,
        "pages": meta.pages,
        "source_name": meta.original_name,
        "url": f"/api/assets/{meta.id}",
    }


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str, request: Request) -> FileResponse:
    state = state_of(request)
    meta = state.assets.meta(asset_id)
    path = state.assets.path(asset_id)
    headers = {
        "Cache-Control": "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    }
    if meta.mime == "image/svg+xml":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        )
    return FileResponse(path, media_type=meta.mime, headers=headers)
