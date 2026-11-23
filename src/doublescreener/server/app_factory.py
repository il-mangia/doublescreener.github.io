"""Creazione dell'applicazione FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from .. import __version__
from ..config import DEFAULT_PORT, Paths, Settings, SettingsManager
from ..core.assets import AssetStore
from ..core.store import ProjectStore
from . import routes_assets, routes_projects
from .errors import install_error_handlers
from .net import lan_ip
from .state import AppState


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

    app = FastAPI(
        title="DoubleScreener",
        version=__version__,
        description="Regia desktop e second screen per presentazioni HTML e PDF.",
        license_info={"name": "GPL-3.0-only"},
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.ds = AppState(
        paths=paths,
        settings=settings,
        settings_manager=manager,
        store=store or ProjectStore(paths),
        assets=assets or AssetStore(paths),
        port=port,
        lan_ip=lan_ip(),
    )

    install_error_handlers(app)
    app.include_router(routes_projects.router)
    app.include_router(routes_assets.router)

    @app.get("/api/info", tags=["info"])
    async def info(request: Request) -> dict[str, Any]:
        state: AppState = request.app.state.ds
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
            "presentation": None,
        }

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse("/api/info")

    return app
