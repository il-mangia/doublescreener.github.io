"""Rotte REST per export e download standalone."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core.errors import NotFoundError
from ..core.ids import ulid
from ..export import ExportFormat, export_single_file, export_static_site
from .routes_projects import state_of

router = APIRouter(prefix="/api", tags=["export"])

_JOB_RE = re.compile(r"^[a-zA-Z0-9_]{6,48}$")


class ExportRequest(BaseModel):
    format: ExportFormat = "folder"
    pdf_width: int | None = None


def _exports_dir(root_cache: Path) -> Path:
    directory = root_cache / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _zip_directory(source: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(source.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(source))


@router.post("/projects/{project_id}/export")
async def create_export(
    project_id: str, payload: ExportRequest, request: Request
) -> dict[str, Any]:
    state = state_of(request)
    project = state.store.get(project_id)
    pdf_width = payload.pdf_width or state.settings.pdf_render_width
    job_id = f"exp_{ulid()}"
    exports_dir = _exports_dir(state.paths.cache)

    if payload.format == "single_file":
        target = exports_dir / f"{job_id}.html"
        result = export_single_file(
            project,
            target,
            state.assets,
            state.pdf,
            pdf_width=pdf_width,
        )
        size_bytes = result.total_bytes
    else:
        staging = exports_dir / job_id
        result = export_static_site(
            project,
            staging,
            state.assets,
            state.pdf,
            pdf_width=pdf_width,
        )
        archive_path = exports_dir / f"{job_id}.zip"
        _zip_directory(staging, archive_path)
        size_bytes = archive_path.stat().st_size

    return {
        "job_id": job_id,
        "format": result.format,
        "size_bytes": size_bytes,
        "file_count": result.file_count,
        "warning": result.warning,
        "download_url": f"/api/exports/{job_id}/download",
    }


@router.get("/exports/{job_id}/download")
async def download_export(job_id: str, request: Request) -> FileResponse:
    if not _JOB_RE.match(job_id):
        raise NotFoundError(f"export non trovato: {job_id}")
    state = state_of(request)
    exports_dir = _exports_dir(state.paths.cache)

    zip_path = exports_dir / f"{job_id}.zip"
    if zip_path.is_file():
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{job_id}.zip",
        )
    html_path = exports_dir / f"{job_id}.html"
    if html_path.is_file():
        return FileResponse(
            html_path,
            media_type="text/html",
            filename=f"{job_id}.html",
        )
    raise NotFoundError(f"export non trovato: {job_id}")
