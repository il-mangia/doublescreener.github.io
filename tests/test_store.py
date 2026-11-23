from __future__ import annotations

import time

import pytest

from doublescreener.core.errors import ConflictError, NotFoundError, StoreError
from doublescreener.core.jsonio import read_json
from doublescreener.core.models import Element, Project


def test_create_list_get(store) -> None:
    project = store.create("Lezione 1")
    store.create("Lezione 2")

    summaries = store.list()
    assert [summary.name for summary in summaries] == ["Lezione 1", "Lezione 2"] or {
        summary.name for summary in summaries
    } == {"Lezione 1", "Lezione 2"}

    loaded = store.get(project.id)
    assert loaded.name == "Lezione 1"
    assert loaded.id == project.id


def test_get_missing(store) -> None:
    with pytest.raises(NotFoundError):
        store.get("prj_" + "A" * 26)


def test_invalid_id_rejected(store) -> None:
    with pytest.raises(ValueError):
        store.get("../../etc/passwd")


def test_save_updates_timestamp_and_creates_backup(store) -> None:
    project = store.create("A")
    first = project.model_copy(deep=True)

    project.name = "B"
    store.save(project)

    backup = store.backup_path(project.id)
    assert backup.is_file()
    assert Project.model_validate(read_json(backup)).name == "A"
    assert store.get(project.id).name == "B"
    assert store.get(project.id).updated_at >= first.updated_at


def test_save_requires_fresh_version(store) -> None:
    project = store.create("A")
    stale = project.model_copy(deep=True)
    time.sleep(0.002)
    store.save(project)

    with pytest.raises(ConflictError):
        store.save(stale, expected_updated_at=stale.updated_at)


def test_save_accepts_current_version(store) -> None:
    project = store.create("A")
    project.name = "B"
    store.save(project, expected_updated_at=project.updated_at)
    assert store.get(project.id).name == "B"


def test_no_temporary_files_left(store, paths) -> None:
    project = store.create("A")
    project.name = "B"
    store.save(project)
    assert list(paths.projects.glob("*.tmp")) == []
    assert list(paths.projects.glob(".*.tmp")) == []


def test_duplicate_regenerates_ids(store) -> None:
    project = store.create("Originale")
    slide = project.slides[0]
    slide.elements.append(Element(type="text"))
    store.save(project)

    copy = store.duplicate(project.id)

    assert copy.id != project.id
    assert copy.name.startswith("Originale")
    assert copy.slides[0].id != slide.id
    assert copy.slides[0].elements[0].id != slide.elements[0].id
    assert store.get(project.id).slides[0].elements[0].id == slide.elements[0].id


def test_delete(store) -> None:
    project = store.create("Da eliminare")
    store.delete(project.id)
    assert not store.exists(project.id)
    with pytest.raises(NotFoundError):
        store.get(project.id)


def test_delete_missing(store) -> None:
    with pytest.raises(NotFoundError):
        store.delete("prj_" + "B" * 26)


def test_corrupt_main_file_recovers_from_backup(store) -> None:
    project = store.create("Buono")
    project.name = "Buono due"
    store.save(project)

    store.path(project.id).write_text("{ non json", encoding="utf-8")
    loaded, warning = store.load(project.id)

    assert warning is not None
    assert "recuperato" in warning
    assert loaded.name == "Buono"


def test_list_skips_corrupt_files(store, paths) -> None:
    store.create("Valido")
    (paths.projects / "rotto.json").write_text("{ nope", encoding="utf-8")

    summaries = store.list()
    assert len(summaries) == 1
    assert summaries[0].name == "Valido"


def test_snapshot_backup_prunes_old(store) -> None:
    project = store.create("Backup")
    for _ in range(5):
        store.snapshot_backup(project.id, keep=2)
        time.sleep(0.002)

    files = list(store._paths.backups.glob(f"{project.id}-*.json"))
    assert len(files) == 2


def test_save_detects_unreadable_existing_file(store) -> None:
    project = store.create("A")
    store.path(project.id).write_text("{ rotto", encoding="utf-8")
    with pytest.raises(StoreError):
        store.save(project)
