"""Sorgente di ``qwebchannel.js`` prelevata dalle risorse Qt.

QtWebEngine sa caricare ``qrc:///qtwebchannel/qwebchannel.js``, ma affidarsi a
uno schema personalizzato da una pagina HTTP è fragile (CSP, origini). Il canvas
serve quindi una copia same-origin letta dalle risorse della libreria Qt già
installata: nessun file aggiuntivo nel pacchetto e versione sempre allineata.
"""

from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)

RESOURCE_PATH = ":/qtwebchannel/qwebchannel.js"


@lru_cache(maxsize=1)
def qwebchannel_source() -> str | None:
    """Restituisce il sorgente JS, oppure ``None`` se PyQt6 non è installato."""
    try:
        from PyQt6 import QtWebChannel  # noqa: F401 - registra la risorsa qrc
        from PyQt6.QtCore import QFile, QIODevice
    except ImportError:
        return None

    handle = QFile(RESOURCE_PATH)
    if not handle.exists() or not handle.open(QIODevice.OpenModeFlag.ReadOnly):
        log.warning("qwebchannel.js assente dalle risorse Qt")
        return None
    try:
        data = bytes(handle.readAll())
    finally:
        handle.close()
    return data.decode("utf-8")
