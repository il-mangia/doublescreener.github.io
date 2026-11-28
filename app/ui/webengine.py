"""Bootstrap di QtWebEngine, da eseguire prima di creare ``QApplication``.

Qt richiede che ``QtWebEngineWidgets`` sia importato (oppure che
``AA_ShareOpenGLContexts`` sia impostato) prima che esista una
``QCoreApplication``. Questo modulo centralizza l'operazione ed è idempotente:
importarlo più volte non ha effetti collaterali.
"""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, Qt

AVAILABLE = True

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

try:
    from PyQt6 import QtWebEngineWidgets  # noqa: E402, F401
except ImportError:  # pragma: no cover - dipende dall'extra gui
    AVAILABLE = False
