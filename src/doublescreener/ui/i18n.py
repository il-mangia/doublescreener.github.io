"""Traduzioni della regia: dizionari JSON, nessuna toolchain ``.qm``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SUPPORTED = ("it", "en")
DEFAULT_LANGUAGE = "it"


class Translator(QObject):
    language_changed = pyqtSignal(str)

    def __init__(self, lang: str = DEFAULT_LANGUAGE) -> None:
        super().__init__()
        self._lang = DEFAULT_LANGUAGE
        self._strings: dict[str, str] = {}
        self.set_language(lang if lang in SUPPORTED else DEFAULT_LANGUAGE, force=True)

    @property
    def language(self) -> str:
        return self._lang

    def set_language(self, lang: str, *, force: bool = False) -> None:
        if lang not in SUPPORTED:
            lang = DEFAULT_LANGUAGE
        if not force and lang == self._lang and self._strings:
            return
        self._strings = self._load(lang)
        self._lang = lang
        self.language_changed.emit(lang)

    @staticmethod
    def _load(lang: str) -> dict[str, str]:
        path = LOCALES_DIR / f"{lang}.json"
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            log.warning("locale %s non caricata: %s", lang, exc)
            return {}
        if not isinstance(data, dict):
            log.warning("locale %s non è un dizionario", lang)
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def t(self, key: str, **kwargs: object) -> str:
        text = self._strings.get(key) or key
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
