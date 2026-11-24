from __future__ import annotations

import json
import re
from pathlib import Path

from doublescreener.ui.i18n import LOCALES_DIR

WEB_PLAYER_LOCALES_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "doublescreener"
    / "web"
    / "player"
    / "locales"
)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _load_locale(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_pair(directory: Path) -> None:
    it = _load_locale(directory / "it.json")
    en = _load_locale(directory / "en.json")

    assert set(it) == set(en), (
        f"Disallineamento chiavi in {directory}: "
        f"solo it={sorted(set(it) - set(en))}, solo en={sorted(set(en) - set(it))}"
    )

    for key in it:
        assert isinstance(it[key], str) and it[key].strip(), f"Valore vuoto it[{key}]"
        assert isinstance(en[key], str) and en[key].strip(), f"Valore vuoto en[{key}]"
        it_ph = set(_PLACEHOLDER_RE.findall(it[key]))
        en_ph = set(_PLACEHOLDER_RE.findall(en[key]))
        assert it_ph == en_ph, f"Placeholder diversi per {key}: it={it_ph}, en={en_ph}"


def test_ui_locales_parity() -> None:
    _assert_pair(LOCALES_DIR)


def test_web_player_locales_parity() -> None:
    _assert_pair(WEB_PLAYER_LOCALES_DIR)
