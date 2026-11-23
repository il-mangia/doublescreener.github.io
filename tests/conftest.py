from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from doublescreener.config import Paths


@pytest.fixture()
def paths(tmp_path: Path) -> Paths:
    return Paths(tmp_path / "data").ensure()


@pytest.fixture()
def store(paths: Paths):
    from doublescreener.core.store import ProjectStore

    return ProjectStore(paths)


@pytest.fixture()
def assets(paths: Paths):
    from doublescreener.core.assets import AssetStore

    return AssetStore(paths)


@pytest_asyncio.fixture()
async def client(paths: Paths):
    from doublescreener.server.app_factory import create_app

    app = create_app(paths, port=8765)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
