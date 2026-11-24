"""Creazione dell'applicazione FastAPI."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import DEFAULT_PORT, Paths, Settings, SettingsManager
from ..core.assets import AssetStore
from ..core.presentation import PresentationController
from ..core.store import ProjectStore
from . import routes_assets, routes_presentation, routes_projects, ws
from .errors import install_error_handlers
from .net import lan_ip
from .state import AppState
from .ws import WebSocketHub

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    state: AppState = app.state.ds
    state.hub.start(asyncio.get_running_loop())
    try:
        yield
    finally:
        await state.hub.stop()


def create_app(
    paths: Paths,
    *,
    port: int = DEFAULT_PORT,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    assets: AssetStore | None = None,
) -> FastAPI:
    paths.ensure()
    manager = SettingsManager(paths)
    settings = settings or manager.load()
    project_store = store or ProjectStore(paths)
    controller = PresentationController(
        project_store, lang=settings.lang, pdf_width=settings.pdf_render_width
    )

    app = FastAPI(
        title="DoubleScreener",
        version=__version__,
        description="Regia desktop e second screen per presentazioni HTML e PDF.",
        license_info={"name": "GPL-3.0-only"},
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.state.ds = AppState(
        paths=paths,
        settings=settings,
        settings_manager=manager,
        store=project_store,
        assets=assets or AssetStore(paths),
        controller=controller,
        hub=WebSocketHub(controller),
        port=port,
        lan_ip=lan_ip(),
    )

    install_error_handlers(app)
    app.include_router(routes_projects.router)
    app.include_router(routes_assets.router)
    app.include_router(routes_presentation.router)
    app.include_router(ws.router)

    shared = WEB_ROOT / "shared"
    player = WEB_ROOT / "player"
    if shared.is_dir():
        app.mount("/static/shared", StaticFiles(directory=shared), name="shared")
    if player.is_dir():
        app.mount("/static/player", StaticFiles(directory=player), name="player")

    @app.get("/p", include_in_schema=False)
    @app.get("/player", include_in_schema=False)
    async def player_page() -> FileResponse:
        return FileResponse(
            player / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/api/info", tags=["info"])
    async def info(request: Request) -> dict[str, Any]:
        state: AppState = request.app.state.ds
        snapshot = state.controller.snapshot()
        return {
            "name": "DoubleScreener",
            "version": __version__,
            "data_dir": str(state.paths.root),
            "port": state.port,
            "lan_ip": state.lan_ip,
            "urls": {
                "local": f"http://127.0.0.1:{state.port}/p",
                "lan": f"http://{state.lan_ip}:{state.port}/p",
            },
            "presentation": snapshot.to_dict() if snapshot.project_id else None,
            "clients": state.hub.client_count,
        }

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse("/api/info")

    return app
