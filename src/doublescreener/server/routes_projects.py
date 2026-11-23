"""Rotte REST dei progetti."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, Field

from ..core.models import Canvas, Project, Slide
from .state import AppState

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    canvas: Canvas | None = None
    slides: list[Slide] | None = None


class DuplicateRequest(BaseModel):
    name_suffix: str = Field(default=" copy", max_length=40)


def state_of(request: Request) -> AppState:
    return request.app.state.ds


def _etag(project: Project) -> str:
    return f'"{project.model_dump(mode="json")["updated_at"]}"'


def _parse_if_match(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip().strip('"')
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("If-Match non valido: atteso un timestamp ISO 8601") from exc


@router.get("/projects")
async def list_projects(request: Request) -> list[dict[str, Any]]:
    state = state_of(request)
    return [summary.model_dump(mode="json") for summary in state.store.list()]


@router.post("/projects", status_code=201)
async def create_project(
    payload: ProjectCreate, request: Request, response: Response
) -> dict[str, Any]:
    state = state_of(request)
    project = state.store.create(
        payload.name, canvas=payload.canvas, slides=payload.slides
    )
    response.headers["ETag"] = _etag(project)
    return project.model_dump(mode="json")


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str, request: Request, response: Response
) -> dict[str, Any]:
    state = state_of(request)
    project = state.store.get(project_id)
    response.headers["ETag"] = _etag(project)
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    payload: Project,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    if payload.id != project_id:
        raise ValueError(f"id del corpo ({payload.id}) diverso da quello dell'URL")
    state = state_of(request)
    project = state.store.save(payload, expected_updated_at=_parse_if_match(if_match))
    response.headers["ETag"] = _etag(project)
    return project.model_dump(mode="json")


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request) -> Response:
    state = state_of(request)
    state.store.delete(project_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/duplicate", status_code=201)
async def duplicate_project(
    project_id: str,
    request: Request,
    response: Response,
    payload: DuplicateRequest | None = None,
) -> dict[str, Any]:
    state = state_of(request)
    suffix = payload.name_suffix if payload is not None else " copy"
    project = state.store.duplicate(project_id, name_suffix=suffix)
    response.headers["ETag"] = _etag(project)
    return project.model_dump(mode="json")
