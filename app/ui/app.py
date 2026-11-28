"""Avvio della regia desktop e istanza singola."""

from __future__ import annotations

import hashlib
import logging
import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox

from .. import __version__
from ..config import DEFAULT_BIND, DEFAULT_PORT, Paths, SettingsManager
from ..server.runtime import ServerRuntime

# Bootstrap di QtWebEngine: deve avvenire prima di creare QApplication.
from . import webengine  # noqa: F401
from .main_window import MainWindow
from .theme import stylesheet_for

log = logging.getLogger(__name__)


def _server_name(paths: Paths) -> str:
    digest = hashlib.sha1(str(paths.root).encode("utf-8")).hexdigest()[:16]
    return f"doublescreener-{digest}"


def _notify_existing(name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(600):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(600)
    socket.disconnectFromServer()
    return True


def _accept_connections(server: QLocalServer, window: MainWindow) -> None:
    while server.hasPendingConnections():
        connection = server.nextPendingConnection()
        if connection is None:
            continue

        def activate(socket: QLocalSocket = connection) -> None:
            socket.readAll()
            window.activate()
            socket.disconnectFromServer()

        connection.readyRead.connect(activate)
        connection.disconnected.connect(connection.deleteLater)


def run_gui(
    paths: Paths,
    host: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    *,
    debug: bool = False,
    mode: str = "custom",
) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DoubleScreener")
    app.setApplicationDisplayName("DoubleScreener")
    app.setOrganizationName("il-mangia")
    app.setOrganizationDomain("doublescreener.github.io")
    app.setStyle("Fusion")
    settings_manager = SettingsManager(paths)
    settings = settings_manager.load()
    app.setStyleSheet(stylesheet_for(settings.theme))
    effective_port = port
    if port == DEFAULT_PORT and settings.port != DEFAULT_PORT:
        effective_port = settings.port
    # Resolve effective host/port, falling back to a free port if the default is already in use
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind((effective_host, effective_port))
    except OSError:
        # Port already in use – let the OS pick a free one
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
            test_sock.bind((effective_host, 0))
            effective_port = test_sock.getsockname()[1]
    log.info(f"Using server port {effective_port}")
    if host == DEFAULT_BIND and settings.bind != DEFAULT_BIND:
        effective_host = settings.bind

    name = _server_name(paths)
    local_server = QLocalServer()
    if not local_server.listen(name):
        if _notify_existing(name):
            log.info("istanza già attiva: portata in primo piano")
            return 0
        local_server.removeServer(name)
        if not local_server.listen(name):
            QMessageBox.critical(
                None,
                "DoubleScreener",
                f"Impossibile creare il canale locale: {local_server.errorString()}",
            )
            return 1

    runtime = ServerRuntime(paths, host=effective_host, port=effective_port)
    try:
        runtime.start()
    except Exception as exc:
        log.exception("avvio del server fallito")
        QMessageBox.critical(
            None,
            "DoubleScreener",
            f"Impossibile avviare il server su {effective_host}:{effective_port}\n\n{exc}",
        )
        return 1

    log.info("DoubleScreener %s — regia su %s", __version__, runtime.url)
    # Pass mode to MainWindow
    window = MainWindow(paths, runtime, settings_manager, settings, mode=mode)
    window.local_server = local_server  # type: ignore[attr-defined]
    local_server.newConnection.connect(lambda: _accept_connections(local_server, window))
    app.aboutToQuit.connect(runtime.stop)
    window.show()
    return app.exec()

    app = QApplication(sys.argv)
    app.setApplicationName("DoubleScreener")
    app.setApplicationDisplayName("DoubleScreener")
    app.setOrganizationName("il-mangia")
    app.setOrganizationDomain("doublescreener.github.io")
    app.setStyle("Fusion")
    settings_manager = SettingsManager(paths)
    settings = settings_manager.load()
    app.setStyleSheet(stylesheet_for(settings.theme))
    effective_port = port
    if port == DEFAULT_PORT and settings.port != DEFAULT_PORT:
        effective_port = settings.port
    # Resolve effective host/port, falling back to a free port if the default is already in use
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind((effective_host, effective_port))
    except OSError:
        # Port already in use – let the OS pick a free one
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
            test_sock.bind((effective_host, 0))
            effective_port = test_sock.getsockname()[1]
    log.info(f"Using server port {effective_port}")
    if host == DEFAULT_BIND and settings.bind != DEFAULT_BIND:
        effective_host = settings.bind

    name = _server_name(paths)
    local_server = QLocalServer()
    if not local_server.listen(name):
        if _notify_existing(name):
            log.info("istanza già attiva: portata in primo piano")
            return 0
        local_server.removeServer(name)
        if not local_server.listen(name):
            QMessageBox.critical(
                None,
                "DoubleScreener",
                f"Impossibile creare il canale locale: {local_server.errorString()}",
            )
            return 1

    runtime = ServerRuntime(paths, host=effective_host, port=effective_port)
    try:
        runtime.start()
    except Exception as exc:
        log.exception("avvio del server fallito")
        QMessageBox.critical(
            None,
            "DoubleScreener",
            f"Impossibile avviare il server su {effective_host}:{effective_port}\n\n{exc}",
        )
        return 1

    log.info("DoubleScreener %s — regia su %s", __version__, runtime.url)
    window = MainWindow(paths, runtime, settings_manager, settings)
    window.local_server = local_server  # type: ignore[attr-defined]
    local_server.newConnection.connect(lambda: _accept_connections(local_server, window))
    app.aboutToQuit.connect(runtime.stop)
    window.show()
    return app.exec()
