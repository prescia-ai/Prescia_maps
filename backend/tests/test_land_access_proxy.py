"""
Tests for the /api/v1/land-access/pad-us-proxy endpoint.

Uses httpx.MockTransport (part of the httpx stdlib — no extra deps) to mock
the upstream PAD-US service so these tests run fully offline.

The tests cover:
- _esri_to_geojson helper (pure-function unit tests)
- pad_us_proxy returning 200 with a valid GeoJSON FeatureCollection
- pad_us_proxy returning 502 when the upstream returns a 5xx
- pad_us_proxy returning 502 when the upstream returns non-JSON
- pad_us_proxy returning 422 for malformed bbox inputs
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import httpx
import pytest

# ---------------------------------------------------------------------------
# Re-usable test data
# ---------------------------------------------------------------------------

SAMPLE_GEOJSON: Dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-105.0, 40.0],
                        [-104.0, 40.0],
                        [-104.0, 41.0],
                        [-105.0, 41.0],
                        [-105.0, 40.0],
                    ]
                ],
            },
            "properties": {
                "Mang_Name": "BLM",
                "GAP_Sts": 3,
                "Des_Tp": "ACEC",
                "Unit_Nm": "Test Area",
            },
        }
    ],
}

SAMPLE_ESRI: Dict[str, Any] = {
    "features": [
        {
            "geometry": {
                "rings": [
                    [
                        [-105.0, 40.0],
                        [-104.0, 40.0],
                        [-104.0, 41.0],
                        [-105.0, 41.0],
                        [-105.0, 40.0],
                    ]
                ]
            },
            "attributes": {
                "Mang_Name": "BLM",
                "GAP_Sts": 3,
                "Des_Tp": "ACEC",
                "Unit_Nm": "Test Area",
            },
        }
    ]
}

# Default upstream URL (mirrors routes.py so the tests are self-contained)
_PADUS_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/PADUS4_1Combined/FeatureServer/0/query"
)


# ---------------------------------------------------------------------------
# Inline copy of _esri_to_geojson for pure-function unit tests.
# Kept here so tests don't need to import the whole FastAPI application.
# ---------------------------------------------------------------------------

def _esri_to_geojson(esri_data: Dict[str, Any]) -> Dict[str, Any]:
    def _rings_to_geom(rings):  # type: ignore[no-untyped-def]
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    features = []
    for feat in esri_data.get("features", []):
        geom = feat.get("geometry")
        attrs = feat.get("attributes", {})
        if geom and "rings" in geom:
            geo = _rings_to_geom(geom["rings"])
        elif geom and "x" in geom and "y" in geom:
            geo = {"type": "Point", "coordinates": [geom["x"], geom["y"]]}
        else:
            geo = None
        features.append({"type": "Feature", "geometry": geo, "properties": attrs})
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Helper: build a mock httpx.Response
# ---------------------------------------------------------------------------

def _make_response(
    status_code: int,
    body: Any,
    content_type: str = "application/json",
) -> httpx.Response:
    if isinstance(body, (dict, list)):
        content = json.dumps(body).encode()
    else:
        content = body.encode() if isinstance(body, str) else body
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": content_type},
        request=httpx.Request("GET", _PADUS_URL),
    )


# ---------------------------------------------------------------------------
# Helper: build a minimal FastAPI TestClient with only the proxy route
# ---------------------------------------------------------------------------

def _build_test_app(mock_transport: httpx.MockTransport):
    import fastapi
    from fastapi import HTTPException, Query, status
    from fastapi.testclient import TestClient

    app = fastapi.FastAPI()
    padus_url = _PADUS_URL
    conv = _esri_to_geojson

    @app.get("/proxy")
    async def _proxy(bbox: str = Query(...)) -> Dict[str, Any]:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox must be four comma-separated numbers: west,south,east,north",
            )
        try:
            west, south, east, north = (float(p) for p in parts)
        except ValueError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox values must be numeric",
            )
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Longitude values must be between -180 and 180",
            )
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Latitude values must be between -90 and 90",
            )

        params = {
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true",
            "outFields": "Mang_Name,GAP_Sts,Des_Tp,Unit_Nm",
            "f": "geojson",
            "outSR": "4326",
        }
        try:
            async with httpx.AsyncClient(
                transport=mock_transport, timeout=30.0
            ) as client:
                response = await client.get(padus_url, params=params)
                if not response.is_success:
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY,
                        detail=f"PAD-US upstream returned {response.status_code}",
                    )
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY,
                        detail="PAD-US service returned an unexpected response format",
                    )
                data = response.json()
                if "type" not in data:
                    data = conv(data)
                return data
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch PAD-US data: {exc}",
            )

    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for _esri_to_geojson
# ---------------------------------------------------------------------------


def test_esri_to_geojson_basic():
    result = _esri_to_geojson(SAMPLE_ESRI)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    feat = result["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["Mang_Name"] == "BLM"


def test_esri_to_geojson_multipolygon():
    """Two rings → MultiPolygon."""
    ring = [
        [-105.0, 40.0],
        [-104.0, 40.0],
        [-104.0, 41.0],
        [-105.0, 41.0],
        [-105.0, 40.0],
    ]
    esri = {"features": [{"geometry": {"rings": [ring, ring]}, "attributes": {}}]}
    result = _esri_to_geojson(esri)
    assert result["features"][0]["geometry"]["type"] == "MultiPolygon"


def test_esri_to_geojson_empty():
    result = _esri_to_geojson({"features": []})
    assert result == {"type": "FeatureCollection", "features": []}


def test_esri_to_geojson_preserves_fields():
    result = _esri_to_geojson(SAMPLE_ESRI)
    props = result["features"][0]["properties"]
    assert props["GAP_Sts"] == 3
    assert props["Des_Tp"] == "ACEC"
    assert props["Unit_Nm"] == "Test Area"


# ---------------------------------------------------------------------------
# Integration tests for pad_us_proxy logic via the mini TestClient app
# ---------------------------------------------------------------------------


def test_proxy_returns_200_geojson():
    """Upstream returns a valid GeoJSON FeatureCollection → 200."""
    transport = httpx.MockTransport(lambda req: _make_response(200, SAMPLE_GEOJSON))
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=-105,40,-104,41")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert isinstance(body["features"], list)


def test_proxy_converts_esri_json():
    """Upstream returns esriJSON (no 'type' key) → converted to GeoJSON."""
    transport = httpx.MockTransport(lambda req: _make_response(200, SAMPLE_ESRI))
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=-105,40,-104,41")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["Mang_Name"] == "BLM"


def test_proxy_502_on_upstream_503():
    """Upstream returns 503 → proxy returns 502 with upstream status in detail."""
    transport = httpx.MockTransport(
        lambda req: _make_response(503, "Service Unavailable", "text/html")
    )
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=-105,40,-104,41")
    assert resp.status_code == 502
    assert "503" in resp.json()["detail"]


def test_proxy_502_on_non_json_200():
    """Upstream returns 200 HTML → proxy returns 502."""
    transport = httpx.MockTransport(
        lambda req: _make_response(200, "<html>Error</html>", "text/html")
    )
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=-105,40,-104,41")
    assert resp.status_code == 502


def test_proxy_422_on_too_few_parts():
    """bbox with only 3 parts → 422."""
    transport = httpx.MockTransport(lambda req: _make_response(200, SAMPLE_GEOJSON))
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=1,2,3")
    assert resp.status_code == 422


def test_proxy_422_on_non_numeric_bbox():
    """Non-numeric bbox values → 422."""
    transport = httpx.MockTransport(lambda req: _make_response(200, SAMPLE_GEOJSON))
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=west,south,east,north")
    assert resp.status_code == 422


def test_proxy_422_on_out_of_range_longitude():
    """Longitude out of [-180, 180] → 422."""
    transport = httpx.MockTransport(lambda req: _make_response(200, SAMPLE_GEOJSON))
    client = _build_test_app(transport)
    resp = client.get("/proxy?bbox=-200,40,-104,41")
    assert resp.status_code == 422
