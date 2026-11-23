"""Punto di ingresso CLI: ``python -m doublescreener``."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .config import DEFAULT_BIND, DEFAULT_PORT, resolve_paths
from .logging_setup import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doublescreener",
        description="Regia desktop e second screen per presentazioni HTML e PDF.",
    )
    parser.add_argument(
        "--data-dir",
        metavar="PATH",
        default=None,
        help="directory dati (default: cartella utente dell'app)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="porta del server")
    parser.add_argument("--bind", default=DEFAULT_BIND, help="indirizzo di ascolto del server")
    parser.add_argument("--debug", action="store_true", help="log dettagliato")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="avvia solo il backend, senza la regia desktop",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"DoubleScreener {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = resolve_paths(args.data_dir).ensure()
    configure_logging(paths, debug=args.debug)
    log = logging.getLogger("doublescreener")
    log.info("DoubleScreener %s — dati in %s", __version__, paths.root)

    if args.headless:
        try:
            from .server.runtime import run_blocking
        except ImportError:
            log.error("backend non ancora disponibile in questa build")
            return 3
        run_blocking(paths, host=args.bind, port=args.port, debug=args.debug)
        return 0

    try:
        from .ui.app import run_gui
    except ImportError:
        log.error(
            "regia non disponibile: installa le dipendenze GUI con "
            'pip install -e ".[gui]"'
        )
        return 2
    return run_gui(paths, host=args.bind, port=args.port, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
