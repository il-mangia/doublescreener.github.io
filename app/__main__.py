"""Punto di ingresso CLI: ``python -m app`` (oppure ``python app/main.py``)."""

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
        description="Regia desktop e second screen per presentazioni HTML e PDF."
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
        "--mode",
        choices=["presentation", "custom", "tournament", "tombola", "idle"],
        help="Modalità di avvio dell'app",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"DoubleScreener {__version__}",
    )
    return parser
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
    # Mode selection will be handled in the GUI if not provided via CLI
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
            'pip install -e "[gui]"'
        )
        return 2
    # Pass the selected mode (may be None) to the GUI
    return run_gui(paths, host=args.bind, port=args.port, debug=args.debug, mode=getattr(args, "mode", None))
    args = build_parser().parse_args(argv)
    # If mode not provided, ask user via console prompt
    if not getattr(args, "mode", None):
        print("Seleziona modalità di avvio:")
        print("  1) presentation  – carica .pptx o .pdf per slide-only")
        print("  2) custom        – editor tradizionale")
        print("  3) tournament    – classifiche, ecc.")
        print("  4) tombola       – grande tabellone numeri")
        print("  5) idle          – video o musica in loop")
        choice = input("Inserisci numero (default 2): ").strip()
        mode_map = {
            "1": "presentation",
            "2": "custom",
            "3": "tournament",
            "4": "tombola",
            "5": "idle",
        }
        args.mode = mode_map.get(choice, "custom")
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
            'pip install -e "[gui]"'
        )
        return 2
    # Pass the selected mode to the GUI
    return run_gui(paths, host=args.bind, port=args.port, debug=args.debug, mode=args.mode)
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
