"""Rotte REST per comandare la presentazione.

La regia embedded usa il controller direttamente; queste rotte servono a test,
diagnostica e a un futuro pannello remoto.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from .routes_projects import state_of

router = APIRouter(prefix="/api/presentation", tags=["presentation"])

_ID_PATTERN = r"^[a-z]{2,5}_[0-9A-Za-z]{1,32}$"


class OpenRequest(BaseModel):
    project_id: str = Field(pattern=_ID_PATTERN)
    index: int = Field(default=0, ge=0)


class GotoRequest(BaseModel):
    index: int = Field(ge=0)


class StepRequest(BaseModel):
    delta: int


class BlackRequest(BaseModel):
    on: bool


def _snapshot_payload(request: Request) -> dict[str, Any]:
    state = state_of(request)
    return {**state.controller.snapshot().to_dict(), "clients": state.hub.client_count}


@router.get("")
async def get_state(request: Request) -> dict[str, Any]:
    return _snapshot_payload(request)


@router.post("/open")
async def open_presentation(payload: OpenRequest, request: Request) -> dict[str, Any]:
    state = state_of(request)
    state.controller.open(payload.project_id, payload.index)
    return _snapshot_payload(request)


@router.post("/close")
async def close_presentation(request: Request) -> dict[str, Any]:
    state = state_of(request)
    state.controller.close()
    return _snapshot_payload(request)


@router.post("/goto")
async def goto_slide(payload: GotoRequest, request: Request) -> dict[str, Any]:
    state = state_of(request)
    state.controller.goto(payload.index)
    return _snapshot_payload(request)


@router.post("/step")
async def step_slide(payload: StepRequest, request: Request) -> dict[str, Any]:
    state = state_of(request)
    state.controller.step(payload.delta)
    return _snapshot_payload(request)


@router.post("/black")
async def black_screen(payload: BlackRequest, request: Request) -> dict[str, Any]:
    state = state_of(request)
    state.controller.set_black(payload.on)
    return _snapshot_payload(request)


@router.get("/clients")
async def list_clients(request: Request) -> dict[str, Any]:
    state = state_of(request)
    return {"clients": state.hub.clients()}
