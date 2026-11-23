"""Avvio e arresto di Uvicorn dentro il processo della regia."""

from __future__ import annotations

import logging
import threading
import time

import uvicorn
from fastapi import FastAPI

from ..config import DEFAULT_BIND, DEFAULT_PORT, Paths
from .app_factory import create_app

log = logging.getLogger(__name__)


class ServerRuntime:
    """Uvicorn in un thread dedicato, avviabile e fermabile dalla GUI."""

    def __init__(
        self,
        paths: Paths,
        host: str = DEFAULT_BIND,
        port: int = DEFAULT_PORT,
        *,
        app: FastAPI | None = None,
    ) -> None:
        self._app = app or create_app(paths, port=port)
        self._host = host
        self._requested_port = port
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        config = uvicorn.Config(
            self._app,
            host=host,
            port=port,
            log_config=None,
            access_log=False,
            lifespan="on",
        )
        self._server = uvicorn.Server(config)
        # I signal handler funzionano solo nel thread principale.
        self._server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    @property
    def app(self) -> FastAPI:
        return self._app

    @property
    def port(self) -> int:
        if self._requested_port == 0 and self._server.servers:
            sockets = self._server.servers[0].sockets
            if sockets:
                return int(sockets[0].getsockname()[1])
        return self._requested_port

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self._host in ("0.0.0.0", "::") else self._host
        return f"http://{host}:{self.port}"

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server.started)

    def start(self, timeout: float = 10.0) -> None:
        if self.running:
            return
        self._error = None
        self._thread = threading.Thread(
            target=self._run, name="doublescreener-server", daemon=True
        )
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                log.info("server avviato su %s", self.url)
                return
            if not self._thread.is_alive():
                raise RuntimeError("il server si è fermato durante l'avvio") from self._error
            time.sleep(0.05)
        raise TimeoutError("timeout durante l'avvio del server")

    def _run(self) -> None:
        try:
            self._server.run()
        except BaseException as exc:  # pragma: no cover - dipende da uvicorn
            self._error = exc
            log.exception("errore fatale del server")

    def stop(self, timeout: float = 5.0) -> None:
        if self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout)
        if self._thread.is_alive():
            log.warning("il server non si è fermato entro %.1fs", timeout)
        else:
            log.info("server fermato")
        self._thread = None


def run_blocking(
    paths: Paths,
    host: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    *,
    debug: bool = False,
) -> None:
    app = create_app(paths, port=port)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="debug" if debug else "info",
        log_config=None,
        access_log=debug,
    )
