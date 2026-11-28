"""Avvio rapido di DoubleScreener.

Uso, dalla radice del repository:

    python app/main.py            # regia desktop
    python app/main.py --headless # solo server + player
    python -m app                 # equivalente

Lo script aggiunge la radice del repository a ``sys.path`` quando viene
eseguito per percorso, così il pacchetto ``app`` resta importabile anche
senza installazione editabile.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    if __package__:
        return
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_bootstrap()

from app.__main__ import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
