"""Hub WebSocket per i second screen.

Un client = una connessione. Il server è autoritario: i client ricevono slide
e stato e possono solo chiedere il session completo (riconnessione).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.presentation import PresentationController, PresentationSnapshot

log = logging.getLogger(__name__)

router = APIRouter()


@dataclass(slots=True)
class PlayerConnection:
    key: str
    client_id: str
    websocket: WebSocket
    user_agent: str
    ip: str
    connected_at: float = field(default_factory=time.time)
    last_pong: float = field(default_factory=time.monotonic)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def info(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "connected_at": self.connected_at,
            "last_pong_age_s": round(time.monotonic() - self.last_pong, 1),
        }


class WebSocketHub:
    def __init__(
        self,
        controller: PresentationController,
        *,
        ping_interval: float = 20.0,
        timeout: float = 60.0,
    ) -> None:
        self._controller = controller
        self._ping_interval = ping_interval
        self._timeout = timeout
        self._connections: dict[str, PlayerConnection] = {}
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unsubscribe = None
        self._keepalive: asyncio.Task[None] | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    # -- ciclo di vita ----------------------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._unsubscribe = self._controller.subscribe(self._on_event)
        self._keepalive = loop.create_task(self._keepalive_loop())

    async def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._keepalive is not None:
            self._keepalive.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._keepalive
            self._keepalive = None
        with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            with contextlib.suppress(Exception):
                await connection.websocket.close(code=1001)
        self._loop = None

    # -- registro ---------------------------------------------------------

    def register(
        self,
        websocket: WebSocket,
        client_id: str,
        *,
        user_agent: str = "",
        ip: str = "",
    ) -> PlayerConnection:
        connection = PlayerConnection(
            key=uuid4().hex,
            client_id=client_id,
            websocket=websocket,
            user_agent=user_agent[:200],
            ip=ip,
        )
        with self._lock:
            self._connections[connection.key] = connection
        log.info("player connesso %s da %s", client_id, ip)
        return connection

    def unregister(self, connection: PlayerConnection) -> None:
        with self._lock:
            self._connections.pop(connection.key, None)
        log.info("player disconnesso %s", connection.client_id)

    def clients(self) -> list[dict[str, Any]]:
        with self._lock:
            connections = sorted(
                self._connections.values(), key=lambda item: item.connected_at
            )
        return [connection.info() for connection in connections]

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._connections)

    # -- invio ------------------------------------------------------------

    async def send(self, connection: PlayerConnection, message: dict[str, Any]) -> bool:
        async with connection.send_lock:
            try:
                await connection.websocket.send_json(message)
                return True
            except Exception as exc:
                log.debug("invio fallito a %s: %s", connection.client_id, exc)
                self.unregister(connection)
                return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        with self._lock:
            connections = list(self._connections.values())
        if not connections:
            return
        await asyncio.gather(
            *(self.send(connection, message) for connection in connections),
            return_exceptions=True,
        )

    async def send_session(self, connection: PlayerConnection) -> None:
        await self.send(connection, self._controller.session_dict())

    # -- eventi dalla regia ----------------------------------------------

    def _on_event(self, kind: str, _snapshot: PresentationSnapshot) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._schedule, kind)

    def _schedule(self, kind: str) -> None:
        task = asyncio.create_task(self._dispatch(kind))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _dispatch(self, kind: str) -> None:
        try:
            messages = self._messages_for(kind)
        except Exception:
            log.exception("errore nel costruire i messaggi di presentazione")
            return
        for message in messages:
            await self.broadcast(message)

    def _messages_for(self, kind: str) -> list[dict[str, Any]]:
        if kind == "open":
            return [self._controller.session_dict()]
        if kind == "close":
            return [self._controller.session_dict()]
        if kind == "slide":
            slide = self._controller.slide_message()
            return [slide, self._controller.state_dict()] if slide else []
        if kind == "state":
            return [self._controller.state_dict()]
        return []

    # -- keepalive --------------------------------------------------------

    async def _keepalive_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._ping_interval)
                now = time.monotonic()
                with self._lock:
                    connections = list(self._connections.values())
                for connection in connections:
                    if now - connection.last_pong > self._timeout:
                        log.warning("client %s silenzioso, chiudo", connection.client_id)
                        with contextlib.suppress(Exception):
                            await connection.websocket.close(code=1001)
                        self.unregister(connection)
                    else:
                        await self.send(
                            connection,
                            {"type": "ping", "t": int(time.time() * 1000)},
                        )
        except asyncio.CancelledError:
            raise

    # -- messaggi dai client ---------------------------------------------

    async def handle_message(
        self, connection: PlayerConnection, message: dict[str, Any]
    ) -> None:
        kind = message.get("type")
        if kind == "pong":
            connection.last_pong = time.monotonic()
        elif kind == "request_state":
            await self.send_session(connection)
        elif kind == "ack":
            log.debug(
                "ack da %s: slide %s",
                connection.client_id,
                message.get("index"),
            )
        elif kind == "error":
            log.warning("errore player %s: %s", connection.client_id, message.get("message"))
        elif kind == "hello":
            connection.last_pong = time.monotonic()


@router.websocket("/ws/player")
async def player_socket(websocket: WebSocket) -> None:
    app = websocket.scope["app"]
    hub: WebSocketHub = app.state.ds.hub

    await websocket.accept()
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        await websocket.close(code=1008)
        return

    if hello.get("type") != "hello":
        await websocket.close(code=1008)
        return

    client_id = str(hello.get("client_id") or uuid4().hex)[:64]
    user_agent = websocket.headers.get("user-agent", "")
    ip = websocket.client.host if websocket.client else ""
    connection = hub.register(websocket, client_id, user_agent=user_agent, ip=ip)

    try:
        await hub.send_session(connection)
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            await hub.handle_message(connection, message)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("errore nel canale player %s", client_id)
    finally:
        hub.unregister(connection)
