"""Apertura del player a schermo intero sui monitor collegati."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QScreen
from PyQt6.QtWidgets import QMainWindow

log = logging.getLogger(__name__)


class PlayerWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, url: str) -> None:
        super().__init__()
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self.setWindowTitle("DoubleScreener")
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.load(QUrl(url))

    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        self.closed.emit()
        super().closeEvent(event)


class DisplayManager(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._windows: list[PlayerWindow] = []

    @staticmethod
    def screens() -> list[QScreen]:
        return QGuiApplication.screens()

    @staticmethod
    def screen_label(screen: QScreen, index: int) -> str:
        geometry = screen.geometry()
        name = screen.name() or f"Screen {index + 1}"
        label = f"{index + 1}. {name} — {geometry.width()}×{geometry.height()}"
        if screen == QGuiApplication.primaryScreen():
            label += " ★"
        return label

    def open_on_screen(self, url: str, screen: QScreen | None) -> PlayerWindow:
        window = PlayerWindow(url)
        self._windows.append(window)
        window.closed.connect(lambda: self._forget(window))
        if screen is not None:
            window.setScreen(screen)
            window.setGeometry(screen.geometry())
        window.showFullScreen()
        window.raise_()
        window.activateWindow()
        return window

    def open_in_browser(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def close_all(self) -> None:
        for window in list(self._windows):
            window.close()
        self._windows.clear()

    def _forget(self, window: PlayerWindow) -> None:
        if window in self._windows:
            self._windows.remove(window)
