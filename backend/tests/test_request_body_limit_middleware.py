from __future__ import annotations

import fastapi
from fastapi.testclient import TestClient

import main as backend_main


def _build_app(max_body_size: int = backend_main.MAX_BODY_SIZE) -> TestClient:
    app = fastapi.FastAPI()
    app.add_middleware(backend_main.LimitRequestBodyMiddleware, max_body_size=max_body_size)

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    return TestClient(app)


def test_request_body_middleware_allows_small_payload():
    client = _build_app(max_body_size=1024)

    response = client.post("/echo", json={"name": "ghost town"})

    assert response.status_code == 200
    assert response.json() == {"name": "ghost town"}


def test_request_body_middleware_rejects_large_payload():
    client = _build_app(max_body_size=10)

    response = client.post("/echo", json={"name": "ghost town"})

    assert response.status_code == 413
    assert response.text == "Request body too large"
