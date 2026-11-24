from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from doublescreener.core.models import Slide
from doublescreener.server.app_factory import create_app


@pytest.fixture()
def app(paths):
    return create_app(paths, port=8765)


def _hello(client_id: str = "test-client") -> dict:
    return {"type": "hello", "protocol": 1, "client_id": client_id, "role": "player"}


def _add_slide(app, project: dict) -> None:
    store = app.state.ds.store
    loaded = store.get(project["id"])
    loaded.slides.append(Slide(name="Seconda"))
    store.save(loaded)


def test_session_without_presentation(app) -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/player") as ws,
    ):
        ws.send_json(_hello())
        message = ws.receive_json()
        assert message["type"] == "session"
        assert message["protocol"] == 1
        assert message["project"] is None
        assert message["slide"] is None
        assert message["deck"]["count"] == 0


def test_presentation_broadcast_flow(app) -> None:
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Demo"}).json()
        _add_slide(app, project)

        with client.websocket_connect("/ws/player") as ws:
            ws.send_json(_hello())
            assert ws.receive_json()["type"] == "session"

            opened = client.post(
                "/api/presentation/open", json={"project_id": project["id"]}
            )
            assert opened.status_code == 200, opened.text

            session = ws.receive_json()
            assert session["type"] == "session"
            assert session["project"]["id"] == project["id"]
            assert session["deck"]["count"] == 2
            assert session["slide"]["index"] == 0
            assert session["state"]["playing"] is True

            assert client.post("/api/presentation/step", json={"delta": 1}).status_code == 200
            slide = ws.receive_json()
            state = ws.receive_json()
            assert slide["type"] == "slide"
            assert slide["index"] == 1
            assert slide["slide"]["name"] == "Seconda"
            assert state["type"] == "state"
            assert state["index"] == 1

            assert client.post("/api/presentation/black", json={"on": True}).status_code == 200
            black = ws.receive_json()
            assert black["type"] == "state"
            assert black["black"] is True

            assert client.post("/api/presentation/black", json={"on": False}).status_code == 200
            assert ws.receive_json()["black"] is False

            assert client.post("/api/presentation/goto", json={"index": 0}).status_code == 200
            assert ws.receive_json()["type"] == "slide"
            assert ws.receive_json()["type"] == "state"


def test_clients_endpoint_and_info(app) -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/player") as ws,
    ):
        ws.send_json(_hello("tv-1"))
        ws.receive_json()

        clients = client.get("/api/presentation/clients").json()["clients"]
        assert len(clients) == 1
        assert clients[0]["client_id"] == "tv-1"

        info = client.get("/api/info").json()
        assert info["clients"] == 1
def test_request_state(app) -> None:
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Demo"}).json()
        client.post("/api/presentation/open", json={"project_id": project["id"]})

        with client.websocket_connect("/ws/player") as ws:
            ws.send_json(_hello())
            assert ws.receive_json()["type"] == "session"
            ws.send_json({"type": "request_state"})
            message = ws.receive_json()
            assert message["type"] == "session"
            assert message["project"]["id"] == project["id"]


def test_presentation_errors(app) -> None:
    with TestClient(app) as client:
        response = client.post("/api/presentation/open", json={"project_id": "prj_" + "Z" * 26})
        assert response.status_code == 404

        response = client.post("/api/presentation/step", json={"delta": 1})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"

        project = client.post("/api/projects", json={"name": "Demo"}).json()
        client.post("/api/presentation/open", json={"project_id": project["id"]})
        response = client.post("/api/presentation/goto", json={"index": 9})
        assert response.status_code == 400


def test_player_page_and_static_assets(app) -> None:
    with TestClient(app) as client:
        page = client.get("/p")
        assert page.status_code == 200
        assert "DoubleScreener" in page.text
        assert page.headers["cache-control"] == "no-cache"

        renderer = client.get("/static/shared/renderer.js")
        assert renderer.status_code == 200
        assert "DS" in renderer.text

        locale = client.get("/static/player/locales/it.json")
        assert locale.status_code == 200
        assert locale.json()["retry"] == "Riprova ora"
