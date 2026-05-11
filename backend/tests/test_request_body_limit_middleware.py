from __future__ import annotations

import fastapi
from fastapi.testclient import TestClient

import main as backend_main


def _build_app() -> TestClient:
    app = fastapi.FastAPI()
    app.add_middleware(backend_main.LimitRequestBodyMiddleware)

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    return TestClient(app)


def test_request_body_limit_allows_small_payload(monkeypatch):
    monkeypatch.setattr(backend_main, "MAX_BODY_SIZE", 1024)
    client = _build_app()

    response = client.post("/echo", json={"name": "ghost town"})

    assert response.status_code == 200
    assert response.json() == {"name": "ghost town"}


def test_request_body_limit_rejects_large_payload(monkeypatch):
    monkeypatch.setattr(backend_main, "MAX_BODY_SIZE", 10)
    client = _build_app()

    response = client.post("/echo", json={"name": "ghost town"})

    assert response.status_code == 413
    assert response.text == "Request body too large"
