"""Eccezioni di dominio di DoubleScreener."""

from __future__ import annotations


class DoubleScreenerError(Exception):
    """Errore applicativo con messaggio destinato all'utente."""


class NotFoundError(DoubleScreenerError):
    """Risorsa richiesta inesistente."""


class ConflictError(DoubleScreenerError):
    """Modifica concorrente rilevata (versione non aggiornata)."""


class AssetError(DoubleScreenerError):
    """File caricato non valido o non supportato."""


class SchemaError(DoubleScreenerError):
    """Versione del formato dati non supportata."""


class StoreError(DoubleScreenerError):
    """Errore di lettura/scrittura sulla directory dati."""
