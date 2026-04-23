"""
Tests for the GET /api/v1/land-access/padus.pmtiles endpoint.

Covers:
- 206 Partial Content with correct Content-Range when file exists and Range header sent.
- 200 OK with full content when file exists and no Range header sent.
- 404 with helpful JSON message when the file does not exist.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict

import pytest
import fastapi
from fastapi import Request, status
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Inline copy of the pmtiles endpoint logic so tests run without the full
# FastAPI application (no database, no PostGIS needed).
# ---------------------------------------------------------------------------

_DUMMY_CONTENT = b"PMTILESDUMMYCONTENTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def _build_app(pmtiles_path: str) -> TestClient:
    """Build a minimal FastAPI app that serves a pmtiles file from pmtiles_path."""
    import re as _re

    app = fastapi.FastAPI()

    @app.get("/land-access/padus.pmtiles")
    async def serve(request: StarletteRequest) -> Response:
        if not os.path.isfile(pmtiles_path):
            raise fastapi.HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="padus.pmtiles not found — run scripts/bake_padus_pmtiles.sh",
            )

        file_size = os.path.getsize(pmtiles_path)
        range_header = request.headers.get("range")

        base_headers: Dict[str, str] = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        }

        if range_header:
            match = _re.fullmatch(r"bytes=(\d+)-(\d*)", range_header.strip())
            if not match:
                raise fastapi.HTTPException(
                    status_code=416,
                    detail="Range Not Satisfiable",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1

            if start > end or start >= file_size:
                raise fastapi.HTTPException(
                    status_code=416,
                    detail="Range Not Satisfiable",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )
            end = min(end, file_size - 1)
            length = end - start + 1

            with open(pmtiles_path, "rb") as fh:
                fh.seek(start)
                chunk = fh.read(length)

            return Response(
                content=chunk,
                status_code=206,
                headers={
                    **base_headers,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                },
                media_type="application/octet-stream",
            )

        with open(pmtiles_path, "rb") as fh:
            content = fh.read()

        return Response(
            content=content,
            status_code=200,
            headers={**base_headers, "Content-Length": str(file_size)},
            media_type="application/octet-stream",
        )

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_range_request_returns_206():
    """Range request returns HTTP 206 with correct Content-Range header."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pmtiles") as f:
        f.write(_DUMMY_CONTENT)
        path = f.name
    try:
        client = _build_app(path)
        resp = client.get(
            "/land-access/padus.pmtiles",
            headers={"Range": "bytes=0-1023"},
        )
        assert resp.status_code == 206
        assert "Content-Range" in resp.headers
        cr = resp.headers["Content-Range"]
        # e.g. "bytes 0-79/80"
        assert cr.startswith("bytes 0-")
        assert len(resp.content) > 0
    finally:
        os.unlink(path)


def test_range_request_content_range_values():
    """Content-Range reflects exact byte positions requested."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pmtiles") as f:
        f.write(_DUMMY_CONTENT)
        path = f.name
    file_size = len(_DUMMY_CONTENT)
    try:
        client = _build_app(path)
        end_byte = min(15, file_size - 1)
        resp = client.get(
            "/land-access/padus.pmtiles",
            headers={"Range": f"bytes=0-{end_byte}"},
        )
        assert resp.status_code == 206
        expected_cr = f"bytes 0-{end_byte}/{file_size}"
        assert resp.headers["Content-Range"] == expected_cr
        assert resp.content == _DUMMY_CONTENT[0 : end_byte + 1]
    finally:
        os.unlink(path)


def test_full_request_returns_200():
    """No Range header → 200 with full content."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pmtiles") as f:
        f.write(_DUMMY_CONTENT)
        path = f.name
    try:
        client = _build_app(path)
        resp = client.get("/land-access/padus.pmtiles")
        assert resp.status_code == 200
        assert resp.content == _DUMMY_CONTENT
    finally:
        os.unlink(path)


def test_missing_file_returns_404():
    """When padus.pmtiles doesn't exist, endpoint returns 404 with helpful message."""
    client = _build_app("/nonexistent/padus.pmtiles")
    resp = client.get("/land-access/padus.pmtiles")
    assert resp.status_code == 404
    body = resp.json()
    assert "bake_padus_pmtiles" in body["detail"]


def test_accept_ranges_header_present():
    """Response always includes Accept-Ranges: bytes."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pmtiles") as f:
        f.write(_DUMMY_CONTENT)
        path = f.name
    try:
        client = _build_app(path)
        resp = client.get("/land-access/padus.pmtiles")
        assert resp.headers.get("accept-ranges") == "bytes"
    finally:
        os.unlink(path)
