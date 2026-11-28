"""Pannello presentazione: stato, client, URL e QR del second screen."""

from __future__ import annotations

import io
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Project
from ..core.presentation import PresentationSnapshot
from .i18n import Translator

QR_SIZE = 148


class PresenterPanel(QWidget):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    next_requested = pyqtSignal()
    black_toggled = pyqtSignal(bool)
    display_requested = pyqtSignal()
    browser_requested = pyqtSignal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._url = ""
        self._snapshot: PresentationSnapshot | None = None
        self._clients: list[dict[str, Any]] = []
        self._build()
        translator.language_changed.connect(self.retranslate)
        self.retranslate()
        self.update_presentation(None)
        self.set_clients([])

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)

        self.project_label = QLabel()
        self.project_label.setWordWrap(True)
        layout.addWidget(self.project_label)

        self.state_label = QLabel()
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)

        start_row = QHBoxLayout()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        start_row.addWidget(self.start_button)
        start_row.addWidget(self.stop_button)
        layout.addLayout(start_row)

        nav_row = QHBoxLayout()
        self.prev_button = QPushButton()
        self.next_button = QPushButton()
        self.black_button = QPushButton()
        self.black_button.setCheckable(True)
        nav_row.addWidget(self.prev_button)
        nav_row.addWidget(self.next_button)
        nav_row.addWidget(self.black_button)
        layout.addLayout(nav_row)

        self.clients_title = QLabel()
        self.clients_title.setObjectName("sectionTitle")
        layout.addWidget(self.clients_title)

        self.clients_list = QListWidget()
        self.clients_list.setMaximumHeight(110)
        layout.addWidget(self.clients_list)

        self.url_label = QLabel()
        self.url_label.setObjectName("urlLabel")
        self.url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.url_label.setWordWrap(True)
        layout.addWidget(self.url_label)

        copy_row = QHBoxLayout()
        self.copy_button = QPushButton()
        copy_row.addWidget(self.copy_button)
        self.display_button = QPushButton()
        copy_row.addWidget(self.display_button)
        layout.addLayout(copy_row)

        self.browser_button = QPushButton()
        layout.addWidget(self.browser_button)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedHeight(QR_SIZE + 12)
        layout.addWidget(self.qr_label)
        layout.addStretch(1)

        self.start_button.clicked.connect(self.start_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.prev_button.clicked.connect(self.prev_requested)
        self.next_button.clicked.connect(self.next_requested)
        self.black_button.toggled.connect(self.black_toggled)
        self.copy_button.clicked.connect(self._copy_url)
        self.display_button.clicked.connect(self.display_requested)
        self.browser_button.clicked.connect(self.browser_requested)

    # -- testi ------------------------------------------------------------

    def retranslate(self) -> None:
        self.title.setText(self._t.t("presenter.title"))
        self.start_button.setText(self._t.t("presenter.start"))
        self.stop_button.setText(self._t.t("presenter.stop"))
        self.prev_button.setText(self._t.t("presenter.prev"))
        self.next_button.setText(self._t.t("presenter.next"))
        self.black_button.setText(self._t.t("presenter.black"))
        self.clients_title.setText(self._t.t("presenter.clients"))
        self.copy_button.setText(self._t.t("presenter.copy"))
        self.display_button.setText(self._t.t("presenter.display"))
        self.browser_button.setText(self._t.t("presenter.browser"))
        self.copy_button.setToolTip(self._t.t("presenter.copy.tooltip"))
        self.update_presentation(self._snapshot)
        self.set_clients(self._clients)
        if self._url:
            self._set_qr(self._url)
        else:
            self.qr_label.setText(self._t.t("presenter.qr.empty"))

    # -- dati -------------------------------------------------------------

    def set_project(self, project: Project | None) -> None:
        if project is None:
            self.project_label.setText(self._t.t("presenter.project.none"))
        else:
            self.project_label.setText(
                self._t.t("presenter.project.name", name=project.name)
            )

    def set_url(self, url: str) -> None:
        self._url = url
        self.url_label.setText(url)
        self._set_qr(url)

    def set_clients(self, clients: list[dict[str, Any]]) -> None:
        self._clients = list(clients)
        self.clients_list.clear()
        if not clients:
            self.clients_list.addItem(self._t.t("presenter.clients.none"))
            self.clients_list.setEnabled(False)
            return
        self.clients_list.setEnabled(True)
        for client in clients:
            ip = client.get("ip") or "?"
            client_id = str(client.get("client_id") or "")[:8]
            age = client.get("last_pong_age_s")
            text = f"{ip}  ·  {client_id}"
            if age is not None:
                text += f"  ·  {age}s"
            self.clients_list.addItem(text)

    def update_presentation(self, snapshot: PresentationSnapshot | None) -> None:
        self._snapshot = snapshot
        active = snapshot is not None and snapshot.project_id is not None
        playing = active and snapshot.playing
        if not active:
            self.state_label.setText(self._t.t("presenter.state.idle"))
            self.state_label.setStyleSheet("color: #96a3b8;")
        elif snapshot.black:
            self.state_label.setText(
                self._t.t(
                    "presenter.state.black",
                    index=snapshot.index + 1,
                    total=snapshot.slide_count,
                )
            )
            self.state_label.setStyleSheet("color: #f0b35c;")
        else:
            self.state_label.setText(
                self._t.t(
                    "presenter.state.playing",
                    index=snapshot.index + 1,
                    total=snapshot.slide_count,
                )
            )
            self.state_label.setStyleSheet("color: #6fd3a8;")

        self.stop_button.setEnabled(playing)
        self.prev_button.setEnabled(playing)
        self.next_button.setEnabled(playing)
        self.black_button.setEnabled(active)
        if self.black_button.isChecked() != (active and snapshot.black):
            self.black_button.blockSignals(True)
            self.black_button.setChecked(bool(active and snapshot.black))
            self.black_button.blockSignals(False)

    # -- QR ---------------------------------------------------------------

    def _set_qr(self, url: str) -> None:
        try:
            import segno

            qr = segno.make(url, micro=False)
            buffer = io.BytesIO()
            qr.save(buffer, kind="png", scale=4, border=1, dark="#0e1015", light="#ffffff")
            pixmap = QPixmap()
            if not pixmap.loadFromData(buffer.getvalue()):
                raise ValueError("immagine QR non valida")
            self.qr_label.setPixmap(
                pixmap.scaled(
                    QR_SIZE,
                    QR_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception:
            self.qr_label.setText(self._t.t("presenter.qr.error"))

    def _copy_url(self) -> None:
        if not self._url:
            return
        QApplication.clipboard().setText(self._url)
        self.copy_button.setText(self._t.t("presenter.copied"))
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(1500, lambda: self.copy_button.setText(self._t.t("presenter.copy")))
