from __future__ import annotations

from pathlib import Path

import pytest

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
