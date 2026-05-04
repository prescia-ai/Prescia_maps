"""
Unit tests for scripts/download_us_aerials.py

All network calls are mocked; no real USGS credentials are required.
Run with:
    pip install pytest
    pytest tests/test_download_us_aerials.py -v
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow importing the script directly without installing it as a package
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import download_us_aerials as m  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_client() -> m.USGSClient:
    """Return a USGSClient with the login step mocked out."""
    with patch.object(m.USGSClient, "_login"):
        client = m.USGSClient.__new__(m.USGSClient)
        client._session = MagicMock()
        client._api_key = "fake-key"
        client._api_timeout = 30
        client._api_retries = 0
    return client


def _make_downloader() -> m.USAerialDownloader:
    """Return a USAerialDownloader whose inner USGSClient is fully mocked."""
    downloader = m.USAerialDownloader.__new__(m.USAerialDownloader)
    client = _make_client()
    downloader._client = client
    return downloader


# ── CANDIDATE_DATASETS ────────────────────────────────────────────────────────

class TestCandidateDatasets:
    def test_includes_aerial(self):
        assert "AERIAL" in m.CANDIDATE_DATASETS

    def test_includes_nhap(self):
        assert "NHAP" in m.CANDIDATE_DATASETS

    def test_includes_napp(self):
        assert "NAPP" in m.CANDIDATE_DATASETS

    def test_excludes_aerial_combin(self):
        assert "AERIAL_COMBIN" not in m.CANDIDATE_DATASETS

    def test_excludes_hrp(self):
        assert "HRP" not in m.CANDIDATE_DATASETS

    def test_aerial_is_first(self):
        assert m.CANDIDATE_DATASETS[0] == "AERIAL"


# ── USGSClient.request_download_urls — payload construction ───────────────────

class TestRequestDownloadUrls:
    def test_calls_download_options_first(self):
        """download-options must be called before download-request."""
        client = _make_client()
        options_resp = [
            {"entityId": "E1", "id": 101, "available": True, "bulkAvailable": True},
            {"entityId": "E2", "id": 102, "available": False, "bulkAvailable": False},
        ]
        request_resp = {
            "availableDownloads": [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ],
            "preparingDownloads": [],
        }

        call_order: list[str] = []

        def _side(endpoint, payload):
            call_order.append(endpoint)
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                return request_resp
            return {}

        with patch.object(client, "_post", side_effect=_side):
            result = client.request_download_urls("AERIAL", ["E1", "E2"])

        assert call_order[0] == "download-options", (
            "download-options must be called before download-request"
        )

    def test_download_request_uses_entity_product_pairs(self):
        """download-request payload must use {downloads:[{entityId,productId}]}."""
        client = _make_client()
        options_resp = [
            {"entityId": "E1", "id": 101, "available": True, "bulkAvailable": False},
        ]
        request_resp = {
            "availableDownloads": [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ],
            "preparingDownloads": [],
        }
        captured: dict = {}

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                captured["payload"] = payload
                return request_resp
            return {}

        with patch.object(client, "_post", side_effect=_side):
            client.request_download_urls("AERIAL", ["E1"])

        assert "downloads" in captured["payload"], "Payload must have 'downloads' key"
        assert "label" in captured["payload"],     "Payload must have 'label' key"
        dl = captured["payload"]["downloads"][0]
        assert dl == {"entityId": "E1", "productId": 101}

    def test_only_available_products_are_requested(self):
        """Products where available==False and bulkAvailable==False are skipped."""
        client = _make_client()
        options_resp = [
            {"entityId": "E1", "id": 101, "available": True},
            {"entityId": "E2", "id": 102, "available": False, "bulkAvailable": False},
        ]
        request_resp = {
            "availableDownloads": [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ],
            "preparingDownloads": [],
        }
        captured: dict = {}

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                captured["payload"] = payload
                return request_resp
            return {}

        with patch.object(client, "_post", side_effect=_side):
            client.request_download_urls("AERIAL", ["E1", "E2"])

        assert len(captured["payload"]["downloads"]) == 1
        assert captured["payload"]["downloads"][0]["entityId"] == "E1"

    def test_returns_available_downloads(self):
        """Result combines availableDownloads from download-request."""
        client = _make_client()
        options_resp = [{"entityId": "E1", "id": 101, "available": True}]
        request_resp = {
            "availableDownloads": [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ],
            "preparingDownloads": [],
        }

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                return request_resp
            return {}

        with patch.object(client, "_post", side_effect=_side):
            result = client.request_download_urls("AERIAL", ["E1"])

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/E1.tif"

    def test_polls_preparing_downloads(self):
        """Items in preparingDownloads are collected via download-retrieve."""
        client = _make_client()
        options_resp  = [{"entityId": "E1", "id": 101, "available": True}]
        request_resp  = {
            "availableDownloads": [],
            "preparingDownloads": [{"entityId": "E1", "productId": 101}],
        }
        retrieve_resp = {
            "available": [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ],
            "requested": [],
        }

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                return request_resp
            if endpoint == "download-retrieve":
                return retrieve_resp
            return {}

        with patch.object(client, "_post", side_effect=_side), \
             patch("time.sleep"):
            result = client.request_download_urls("AERIAL", ["E1"])

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/E1.tif"

    def test_empty_options_returns_empty_list(self):
        """When download-options returns nothing, return an empty list immediately."""
        client = _make_client()
        with patch.object(client, "_post", return_value=[]):
            result = client.request_download_urls("AERIAL", ["E1"])
        assert result == []


# ── USAerialDownloader._download_grid — accumulation and dedup ────────────────

class TestDownloadGrid:
    def test_tries_all_candidate_datasets(self, tmp_path):
        """Every CANDIDATE_DATASET is searched even when the first has results."""
        downloader = _make_downloader()
        downloader._client.search_scenes = MagicMock(
            side_effect=lambda ds, b, y, **kw: [{"entityId": f"{ds}_E1"}]
        )
        downloader._client.request_download_urls = MagicMock(
            side_effect=lambda ds, eids: [
                {"url": f"https://example.com/{eid}.tif", "entityId": eid}
                for eid in eids
            ]
        )
        downloader._client.download_file = MagicMock(return_value=True)

        with patch("time.sleep"):
            paths = downloader._download_grid(
                (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
            )

        assert downloader._client.search_scenes.call_count == len(m.CANDIDATE_DATASETS)
        # One file per dataset (each has a unique entityId)
        assert len(paths) == len(m.CANDIDATE_DATASETS)

    def test_accumulates_across_datasets(self, tmp_path):
        """Results from multiple datasets are combined."""
        downloader = _make_downloader()

        def _search(dataset, b, y, **kw):
            if dataset == "AERIAL":
                return [{"entityId": "E1"}]
            if dataset == "NHAP":
                return [{"entityId": "E2"}]
            return []

        def _request_urls(dataset, entity_ids):
            return [
                {"url": f"https://example.com/{eid}.tif", "entityId": eid}
                for eid in entity_ids
            ]

        downloader._client.search_scenes    = MagicMock(side_effect=_search)
        downloader._client.request_download_urls = MagicMock(side_effect=_request_urls)
        downloader._client.download_file    = MagicMock(return_value=True)

        with patch("time.sleep"):
            paths = downloader._download_grid(
                (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
            )

        assert len(paths) == 2

    def test_deduplicates_entity_ids_across_datasets(self, tmp_path):
        """Same entityId returned by multiple datasets is only requested once."""
        downloader = _make_downloader()
        # All datasets return the same entityId
        downloader._client.search_scenes = MagicMock(
            return_value=[{"entityId": "E1"}]
        )
        requested_entity_ids: list[str] = []

        def _request_urls(dataset, entity_ids):
            requested_entity_ids.extend(entity_ids)
            return [
                {"url": "https://example.com/E1.tif", "entityId": "E1"}
            ]

        downloader._client.request_download_urls = MagicMock(
            side_effect=_request_urls
        )
        downloader._client.download_file = MagicMock(return_value=True)

        with patch("time.sleep"):
            paths = downloader._download_grid(
                (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
            )

        # E1 should only have been requested once, regardless of how many
        # datasets returned it
        assert requested_entity_ids.count("E1") == 1
        # And only one file should have been downloaded
        assert len(paths) == 1

    def test_raises_when_no_download_urls_returned(self, tmp_path):
        """RuntimeError is raised when every dataset returns 0 download URLs."""
        downloader = _make_downloader()
        downloader._client.search_scenes = MagicMock(
            return_value=[{"entityId": "E1"}]
        )
        downloader._client.request_download_urls = MagicMock(return_value=[])

        with pytest.raises(RuntimeError, match="No download URLs"):
            with patch("time.sleep"):
                downloader._download_grid(
                    (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
                )

    def test_raises_when_all_datasets_have_no_scenes(self, tmp_path):
        """RuntimeError is raised when scene-search returns nothing for all datasets."""
        downloader = _make_downloader()
        downloader._client.search_scenes = MagicMock(return_value=[])

        with pytest.raises(RuntimeError, match="No download URLs"):
            with patch("time.sleep"):
                downloader._download_grid(
                    (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
                )

    def test_skips_duplicate_urls(self, tmp_path):
        """The same URL returned by two different datasets is downloaded only once."""
        downloader = _make_downloader()

        def _search(dataset, b, y, **kw):
            if dataset in ("AERIAL", "NHAP"):
                return [{"entityId": f"{dataset}_E1"}]
            return []

        def _request_urls(dataset, entity_ids):
            # Both datasets return the same URL
            return [{"url": "https://example.com/shared.tif", "entityId": entity_ids[0]}]

        downloader._client.search_scenes         = MagicMock(side_effect=_search)
        downloader._client.request_download_urls = MagicMock(side_effect=_request_urls)
        downloader._client.download_file         = MagicMock(return_value=True)

        with patch("time.sleep"):
            paths = downloader._download_grid(
                (-125.0, 24.0, -115.0, 34.0), 1955, tmp_path
            )

        # The URL is identical so it should be downloaded exactly once
        assert downloader._client.download_file.call_count == 1
        assert len(paths) == 1


# ── compress_tiles — empty-directory bail-out ─────────────────────────────────

class TestCompressTiles:
    def test_returns_none_when_no_webp_files(self, tmp_path):
        """compress_tiles returns None when tile_dir has no *.webp files."""
        downloader = _make_downloader()
        tile_dir   = tmp_path / "tiles" / "1955"
        tile_dir.mkdir(parents=True)

        result = downloader.compress_tiles(tile_dir, 1955, tmp_path)

        assert result is None

    def test_returns_none_when_tile_dir_missing(self, tmp_path):
        """compress_tiles returns None when tile_dir does not exist."""
        downloader = _make_downloader()
        tile_dir   = tmp_path / "nonexistent"

        result = downloader.compress_tiles(tile_dir, 1955, tmp_path)

        assert result is None

    def test_creates_archive_when_webp_files_exist(self, tmp_path):
        """compress_tiles creates the tar.gz when *.webp files are present."""
        downloader = _make_downloader()
        tile_dir   = tmp_path / "tiles" / "1955"
        tile_dir.mkdir(parents=True)
        (tile_dir / "tile.webp").write_bytes(b"FAKE_WEBP")

        archive = downloader.compress_tiles(tile_dir, 1955, tmp_path)

        assert archive is not None
        assert archive.exists()
        assert archive.suffix == ".gz"


# ── Output path — no double-nesting ──────────────────────────────────────────

class TestOutputPath:
    def test_download_full_us_creates_year_subdir(self, tmp_path):
        """download_full_us creates <output_dir>/<year>/ when called."""
        downloader = _make_downloader()

        # Short-circuit every phase so nothing real happens
        downloader._download_grid       = MagicMock(return_value=[])
        downloader.optimize_geotiff     = MagicMock(return_value=True)
        downloader.create_optimized_tiles = MagicMock()
        downloader.compress_tiles       = MagicMock(return_value=None)
        downloader._write_metadata      = MagicMock()
        downloader._client.logout       = MagicMock()

        downloader.download_full_us(year=1955, output_dir=tmp_path, workers=1)

        year_dir = tmp_path / "1955"
        assert year_dir.is_dir(), (
            "download_full_us must create <output_dir>/1955/ automatically"
        )
