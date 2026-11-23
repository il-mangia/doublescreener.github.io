"""Handler uniformi per gli errori dell'API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..core.errors import (
    AssetError,
    ConflictError,
    DoubleScreenerError,
    NotFoundError,
    SchemaError,
    StoreError,
)

log = logging.getLogger(__name__)


def error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_body("not_found", str(exc)))

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content=error_body("conflict", str(exc)))

    @app.exception_handler(AssetError)
    async def _asset(_: Request, exc: AssetError) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_body("invalid_asset", str(exc)))

    @app.exception_handler(SchemaError)
    async def _schema(_: Request, exc: SchemaError) -> JSONResponse:
        return JSONResponse(status_code=422, content=error_body("invalid_schema", str(exc)))

    @app.exception_handler(StoreError)
    async def _store(_: Request, exc: StoreError) -> JSONResponse:
        log.exception("errore di persistenza")
        return JSONResponse(status_code=500, content=error_body("store_error", str(exc)))

    @app.exception_handler(ValidationError)
    async def _validation(_: Request, exc: ValidationError) -> JSONResponse:
        details = [
            {"loc": list(item.get("loc", [])), "msg": item.get("msg"), "type": item.get("type")}
            for item in exc.errors(include_context=False, include_url=False)
        ]
        return JSONResponse(
            status_code=422, content=error_body("validation_error", "dati non validi", details)
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": list(item.get("loc", [])),
                "msg": item.get("msg"),
                "type": item.get("type"),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content=error_body("validation_error", "richiesta non valida", details)
        )

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_body("bad_request", str(exc)))

    @app.exception_handler(DoubleScreenerError)
    async def _generic(_: Request, exc: DoubleScreenerError) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_body("error", str(exc)))
