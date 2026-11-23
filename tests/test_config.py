from __future__ import annotations

from pathlib import Path

from doublescreener.config import Paths, Settings, SettingsManager, resolve_paths


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.lang == "it"
    assert settings.port == 8765
    assert settings.autosave_ms == 1000


def test_settings_round_trip(paths: Paths) -> None:
    manager = SettingsManager(paths)
    manager.save(Settings(lang="en", port=9000))

    loaded = manager.load()
    assert loaded.lang == "en"
    assert loaded.port == 9000
    assert manager.path.is_file()


def test_corrupt_settings_fall_back_to_defaults(paths: Paths) -> None:
    manager = SettingsManager(paths)
    manager.path.write_text("{ non json", encoding="utf-8")

    settings = manager.load()
    assert settings.lang == "it"
    assert settings.port == 8765


def test_invalid_settings_fall_back_to_defaults(paths: Paths) -> None:
    manager = SettingsManager(paths)
    manager.path.write_text('{"port": 999999}', encoding="utf-8")
    assert manager.load().port == 8765


def test_paths_creation(tmp_path: Path) -> None:
    paths = Paths(tmp_path / "data").ensure()
    assert paths.projects.is_dir()
    assert paths.assets.is_dir()
    assert paths.pdf_cache.is_dir()
    assert paths.backups.is_dir()


def test_resolve_paths_explicit(tmp_path: Path) -> None:
    paths = resolve_paths(tmp_path / "custom")
    assert paths.root == tmp_path / "custom"


def test_resolve_paths_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOUBLESCREENER_DATA_DIR", str(tmp_path / "env"))
    assert resolve_paths(None).root == tmp_path / "env"
