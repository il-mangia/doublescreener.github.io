from __future__ import annotations

import pytest

from doublescreener.core.ids import new_id, ulid


def test_ulid_zero_is_deterministic() -> None:
    assert ulid(0, b"\x00" * 10) == "0" * 26


def test_ulid_length_and_alphabet() -> None:
    value = ulid()
    assert len(value) == 26
    assert set(value) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_ulid_is_lexicographically_ordered_by_time() -> None:
    first = ulid(1_700_000_000_000, b"\x00" * 10)
    second = ulid(1_700_000_001_000, b"\x00" * 10)
    assert first < second


def test_new_id_prefixes() -> None:
    assert new_id("project").startswith("prj_")
    assert new_id("slide").startswith("sld_")
    assert new_id("element").startswith("el_")
    assert new_id("asset").startswith("ast_")


def test_new_id_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        new_id("banana")


def test_ulid_rejects_wrong_randomness() -> None:
    with pytest.raises(ValueError):
        ulid(0, b"\x00")
