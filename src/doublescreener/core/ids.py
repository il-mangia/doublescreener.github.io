"""Generazione di identificatori ULID con prefisso di dominio.

Formato: ``<prefix>_<ulid>`` dove ``prefix`` è uno tra ``prj``, ``sld``, ``el``,
``ast`` e ``ulid`` è un ULID canonico di 26 caratteri (Crockford base32).
Gli id sono ordinabili per tempo di creazione e leggibili nei file JSON.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
_TIMESTAMP_CHARS = 10
_RANDOM_BYTES = 10

PREFIXES = {
    "project": "prj",
    "slide": "sld",
    "element": "el",
    "asset": "ast",
}


def _encode(value: int, length: int) -> str:
    chars = [""] * length
    for index in range(length - 1, -1, -1):
        chars[index] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def ulid(timestamp_ms: int | None = None, randomness: bytes | None = None) -> str:
    """Restituisce un ULID. Parametri opzionali per test deterministici."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if randomness is None:
        randomness = os.urandom(_RANDOM_BYTES)
    if len(randomness) != _RANDOM_BYTES:
        raise ValueError(f"randomness deve essere di {_RANDOM_BYTES} byte")
    timestamp = timestamp_ms & ((1 << 48) - 1)
    value = int.from_bytes(randomness, "big")
    return _encode(timestamp, _TIMESTAMP_CHARS) + _encode(value, _ULID_LENGTH - _TIMESTAMP_CHARS)


def new_id(kind: str) -> str:
    """Genera un id con prefisso, es. ``new_id("project") -> prj_01...``."""
    try:
        prefix = PREFIXES[kind]
    except KeyError as exc:
        raise ValueError(f"tipo id sconosciuto: {kind!r}") from exc
    return f"{prefix}_{ulid()}"
