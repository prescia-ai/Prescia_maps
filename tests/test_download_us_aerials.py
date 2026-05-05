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
import requests

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
        client._username = "testuser"
        client._token = "testtoken"
        client.login_time = time.monotonic()
    return client


def _make_downloader() -> m.USAerialDownloader:
    """Return a USAerialDownloader whose inner USGSClient is fully mocked."""
    downloader = m.USAerialDownloader.__new__(m.USAerialDownloader)
    client = _make_client()
    downloader._client = client
    return downloader


# ── CANDIDATE_DATASETS ────────────────────────────────────────────────────────

class TestCandidateDatasets:
    def test_includes_aerial_combin(self):
        assert "AERIAL_COMBIN" in m.CANDIDATE_DATASETS

    def test_includes_nhap(self):
        assert "NHAP" in m.CANDIDATE_DATASETS

    def test_includes_napp(self):
        assert "NAPP" in m.CANDIDATE_DATASETS

    def test_excludes_aerial(self):
        assert "AERIAL" not in m.CANDIDATE_DATASETS

    def test_excludes_hrp(self):
        assert "HRP" not in m.CANDIDATE_DATASETS

    def test_aerial_combin_is_first(self):
        assert m.CANDIDATE_DATASETS[0] == "AERIAL_COMBIN"


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
            if dataset == "AERIAL_COMBIN":
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
            if dataset in ("AERIAL_COMBIN", "NHAP"):
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

    def test_no_double_nesting_when_output_already_ends_in_year(self, tmp_path):
        """When --output already ends in the year, do NOT append /<year> again."""
        downloader = _make_downloader()

        downloader._download_grid         = MagicMock(return_value=[])
        downloader.optimize_geotiff       = MagicMock(return_value=True)
        downloader.create_optimized_tiles = MagicMock()
        downloader.compress_tiles         = MagicMock(return_value=None)
        downloader._write_metadata        = MagicMock()
        downloader._client.logout         = MagicMock()

        # Simulate: user passed --output ./tiles/1955
        year_dir_input = tmp_path / "1955"
        year_dir_input.mkdir()

        downloader.download_full_us(year=1955, output_dir=year_dir_input, workers=1)

        # Output must live directly under year_dir_input, NOT year_dir_input/1955
        double_nested = year_dir_input / "1955"
        assert not double_nested.exists(), (
            "download_full_us must NOT create 1955/1955 when output already ends in year"
        )

    def test_tile_dir_is_not_double_year(self, tmp_path):
        """tile_dir must be <year_dir>/tiles, not <year_dir>/tiles/<year>."""
        downloader = _make_downloader()

        captured: dict = {}

        def _capture_compress(tile_dir, year, output_dir):
            captured["tile_dir"] = tile_dir
            return None

        downloader._download_grid         = MagicMock(return_value=[])
        downloader.optimize_geotiff       = MagicMock(return_value=True)
        downloader.create_optimized_tiles = MagicMock()
        downloader.compress_tiles         = MagicMock(side_effect=_capture_compress)
        downloader._write_metadata        = MagicMock()
        downloader._client.logout         = MagicMock()

        downloader.download_full_us(year=1955, output_dir=tmp_path, workers=1)

        tile_dir = captured.get("tile_dir")
        assert tile_dir is not None
        # The tile_dir should end with "tiles", not "tiles/1955"
        assert tile_dir.name == "tiles", (
            f"tile_dir should be <year_dir>/tiles, got {tile_dir}"
        )


# ── request_download_urls — one product per entityId ─────────────────────────

class TestRequestDownloadUrlsOneProductPerScene:
    def test_selects_exactly_one_product_per_entity(self):
        """When download-options returns 3 products for the same entity, only
        one entry is included in the download-request payload."""
        client = _make_client()

        options_resp = [
            # Three products for the same entityId E1
            {"entityId": "E1", "id": 201, "available": True,  "bulkAvailable": False,
             "productCode": "BROWSE", "productName": "Browse Image", "filesize": 500_000},
            {"entityId": "E1", "id": 202, "available": True,  "bulkAvailable": False,
             "productCode": "STANDARD", "productName": "Standard Download", "filesize": 5_000_000},
            {"entityId": "E1", "id": 203, "available": False, "bulkAvailable": False,
             "productCode": "TIFF_HR", "productName": "High Res TIFF", "filesize": 50_000_000},
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
            result = client.request_download_urls("AERIAL_COMBIN", ["E1"])

        downloads = captured["payload"]["downloads"]
        assert len(downloads) == 1, (
            f"Expected exactly 1 product in download-request, got {len(downloads)}"
        )
        assert downloads[0]["entityId"] == "E1"

    def test_prefers_preferred_product_name(self):
        """Product matching 'standard|geotiff|tiff' is chosen over larger browse image."""
        client = _make_client()

        options_resp = [
            {"entityId": "E1", "id": 301, "available": True,
             "productCode": "BROWSE", "productName": "Browse Image", "filesize": 10_000_000},
            {"entityId": "E1", "id": 302, "available": True,
             "productCode": "STANDARD", "productName": "Standard GeoTIFF", "filesize": 1_000_000},
        ]
        captured: dict = {}

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                captured["payload"] = payload
                return {"availableDownloads": [], "preparingDownloads": []}
            return {}

        with patch.object(client, "_post", side_effect=_side):
            client.request_download_urls("AERIAL_COMBIN", ["E1"])

        downloads = captured["payload"]["downloads"]
        assert downloads[0]["productId"] == 302, (
            "Standard GeoTIFF product should be preferred over browse image"
        )

    def test_falls_back_to_largest_when_no_preferred_name(self):
        """When no product matches the preferred pattern, largest filesize wins."""
        client = _make_client()

        options_resp = [
            {"entityId": "E1", "id": 401, "available": True,
             "productCode": "JPEG", "productName": "JPEG Preview", "filesize": 200_000},
            {"entityId": "E1", "id": 402, "available": True,
             "productCode": "FULL", "productName": "Full Resolution", "filesize": 8_000_000},
        ]
        captured: dict = {}

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                captured["payload"] = payload
                return {"availableDownloads": [], "preparingDownloads": []}
            return {}

        with patch.object(client, "_post", side_effect=_side):
            client.request_download_urls("AERIAL_COMBIN", ["E1"])

        downloads = captured["payload"]["downloads"]
        assert downloads[0]["productId"] == 402, (
            "Largest-filesize product should be chosen when no preferred name matches"
        )

    def test_skips_entity_with_no_available_product(self):
        """Entities where all products are unavailable are omitted entirely."""
        client = _make_client()

        options_resp = [
            {"entityId": "E1", "id": 501, "available": False, "bulkAvailable": False,
             "productCode": "STANDARD", "productName": "Standard"},
            {"entityId": "E2", "id": 502, "available": True,  "bulkAvailable": False,
             "productCode": "STANDARD", "productName": "Standard"},
        ]
        captured: dict = {}

        def _side(endpoint, payload):
            if endpoint == "download-options":
                return options_resp
            if endpoint == "download-request":
                captured["payload"] = payload
                return {"availableDownloads": [], "preparingDownloads": []}
            return {}

        with patch.object(client, "_post", side_effect=_side):
            client.request_download_urls("AERIAL_COMBIN", ["E1", "E2"])

        downloads = captured["payload"]["downloads"]
        assert len(downloads) == 1
        assert downloads[0]["entityId"] == "E2"


# ── search_scenes — pagination ────────────────────────────────────────────────

class TestSearchScenesPagination:
    def test_paginates_when_total_hits_exceeds_page_size(self):
        """search_scenes should keep fetching pages until totalHits is exhausted."""
        client = _make_client()

        # Simulate 150 scenes spread over 2 pages of 100
        page1 = [{"entityId": f"E{i}"} for i in range(100)]
        page2 = [{"entityId": f"E{i}"} for i in range(100, 150)]

        call_count = 0

        def _side(endpoint, payload):
            nonlocal call_count
            if endpoint != "scene-search":
                return {}
            call_count += 1
            starting = payload.get("startingNumber", 1)
            if starting == 1:
                return {"results": page1, "totalHits": 150}
            else:
                return {"results": page2, "totalHits": 150}

        with patch.object(client, "_post", side_effect=_side):
            scenes = client.search_scenes(
                "AERIAL_COMBIN",
                (-125.0, 24.0, -115.0, 34.0),
                1955,
                max_results=10_000,
                page_size=100,
            )

        assert len(scenes) == 150, f"Expected 150 scenes, got {len(scenes)}"
        assert call_count == 2, f"Expected 2 API calls, got {call_count}"

    def test_stops_when_results_empty(self):
        """search_scenes stops when the API returns an empty results list."""
        client = _make_client()

        page1 = [{"entityId": "E1"}, {"entityId": "E2"}]

        call_count = 0

        def _side(endpoint, payload):
            nonlocal call_count
            if endpoint != "scene-search":
                return {}
            call_count += 1
            starting = payload.get("startingNumber", 1)
            if starting == 1:
                return {"results": page1, "totalHits": 2}
            return {"results": [], "totalHits": 2}

        with patch.object(client, "_post", side_effect=_side):
            scenes = client.search_scenes(
                "NHAP",
                (-125.0, 24.0, -115.0, 34.0),
                1955,
            )

        assert len(scenes) == 2
        # After fetching page 1 (2 results, totalHits=2), starting becomes 3 > 2 → stop.
        # Only 1 API call is needed; the empty-results guard is an extra safety net.
        assert call_count >= 1

    def test_respects_max_results_cap(self):
        """search_scenes never returns more than max_results scenes."""
        client = _make_client()

        # Mock respects maxResults from the payload so we simulate a realistic API
        def _side(endpoint, payload):
            if endpoint != "scene-search":
                return {}
            count = payload.get("maxResults", 100)
            start = payload.get("startingNumber", 1)
            return {
                "results": [{"entityId": f"E{start + i}"} for i in range(count)],
                "totalHits": 10_000,
            }

        with patch.object(client, "_post", side_effect=_side):
            scenes = client.search_scenes(
                "AERIAL_COMBIN",
                (-125.0, 24.0, -115.0, 34.0),
                1955,
                max_results=150,
                page_size=100,
            )

        assert len(scenes) == 150


# ── _preflight_check_tools ────────────────────────────────────────────────────

class TestPreflightCheckTools:
    def test_exits_with_code_2_when_gdalwarp_missing(self, capsys):
        """_preflight_check_tools exits with code 2 when gdalwarp is absent."""
        def _which(name):
            if name == "gdalwarp":
                return None
            # Everything else is present
            return f"/usr/bin/{name}"

        with patch("shutil.which", side_effect=_which):
            with pytest.raises(SystemExit) as exc_info:
                m._preflight_check_tools()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "gdalwarp" in captured.err
        assert "install GDAL" in captured.err

    def test_exits_with_code_2_when_cwebp_missing(self, capsys):
        """_preflight_check_tools exits with code 2 when cwebp is absent."""
        def _which(name):
            if name == "cwebp":
                return None
            return f"/usr/bin/{name}"

        with patch("shutil.which", side_effect=_which):
            with pytest.raises(SystemExit) as exc_info:
                m._preflight_check_tools()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "cwebp" in captured.err

    def test_exits_with_code_2_when_gdal2tiles_missing(self, capsys):
        """_preflight_check_tools exits with code 2 when neither gdal2tiles variant is found."""
        def _which(name):
            if name in ("gdal2tiles", "gdal2tiles.py"):
                return None
            return f"/usr/bin/{name}"

        with patch("shutil.which", side_effect=_which):
            with pytest.raises(SystemExit) as exc_info:
                m._preflight_check_tools()

        assert exc_info.value.code == 2

    def test_all_tools_present_does_not_exit(self):
        """_preflight_check_tools does not exit when all tools are found."""
        with patch("shutil.which", return_value="/usr/bin/tool"):
            # Should complete without raising SystemExit
            m._preflight_check_tools()

    def test_sets_gdal2tiles_cmd_to_resolved_path(self):
        """GDAL2TILES_CMD is updated to the resolved path of gdal2tiles."""
        def _which(name):
            if name == "gdal2tiles":
                return "/usr/bin/gdal2tiles"
            return f"/usr/bin/{name}"

        with patch("shutil.which", side_effect=_which):
            m._preflight_check_tools()

        assert m.GDAL2TILES_CMD == "/usr/bin/gdal2tiles"

    def test_error_message_contains_install_instructions(self, capsys):
        """The error message includes OS-specific install instructions."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit):
                m._preflight_check_tools()

        captured = capsys.readouterr()
        assert "apt-get" in captured.err or "OSGeo4W" in captured.err


# ── USGSClient._post — 401/403 auth retry ────────────────────────────────────

class TestPostAuthRetry:
    def _make_http_error(self, status_code: int) -> requests.exceptions.HTTPError:
        """Return a mock HTTPError for the given status code."""
        resp = MagicMock()
        resp.status_code = status_code
        exc = requests.exceptions.HTTPError(response=resp)
        return exc

    def test_retries_once_on_403_then_succeeds(self):
        """_post calls relogin() once on 403 and retries; succeeds on second attempt."""
        client = _make_client()
        client._api_retries = 0  # no transient retries; only auth retry

        call_count = [0]

        def _post_side(url, json, timeout):
            call_count[0] += 1
            resp = MagicMock()
            if call_count[0] == 1:
                resp.status_code = 403
                resp.raise_for_status.side_effect = self._make_http_error(403)
            else:
                resp.status_code = 200
                resp.raise_for_status.return_value = None
                resp.json.return_value = {"data": "ok", "errorCode": None}
            return resp

        client._session.post.side_effect = _post_side
        relogin_calls = [0]

        def _relogin():
            relogin_calls[0] += 1
            client.login_time = time.monotonic()

        with patch.object(client, "relogin", side_effect=_relogin):
            result = client._post("scene-search", {})

        assert result == "ok"
        assert relogin_calls[0] == 1, "relogin() should be called exactly once"

    def test_retries_once_on_401_then_succeeds(self):
        """_post calls relogin() once on 401 and retries; succeeds on second attempt."""
        client = _make_client()
        client._api_retries = 0

        call_count = [0]

        def _post_side(url, json, timeout):
            call_count[0] += 1
            resp = MagicMock()
            if call_count[0] == 1:
                resp.status_code = 401
                resp.raise_for_status.side_effect = self._make_http_error(401)
            else:
                resp.status_code = 200
                resp.raise_for_status.return_value = None
                resp.json.return_value = {"data": "ok", "errorCode": None}
            return resp

        client._session.post.side_effect = _post_side

        with patch.object(client, "relogin"):
            result = client._post("scene-search", {})

        assert result == "ok"

    def test_does_not_retry_403_twice(self):
        """_post raises after a single auth retry — does not loop on repeated 403."""
        client = _make_client()
        client._api_retries = 0

        def _post_side(url, json, timeout):
            resp = MagicMock()
            resp.status_code = 403
            resp.raise_for_status.side_effect = self._make_http_error(403)
            return resp

        client._session.post.side_effect = _post_side
        relogin_calls = [0]

        def _relogin():
            relogin_calls[0] += 1
            client.login_time = time.monotonic()

        with patch.object(client, "relogin", side_effect=_relogin):
            with pytest.raises(requests.exceptions.HTTPError):
                client._post("scene-search", {})

        assert relogin_calls[0] == 1, (
            "relogin() should be called exactly once, then the error is raised"
        )

    def test_proactive_relogin_when_session_expired(self):
        """_post calls relogin() proactively when login_time is older than 90 min."""
        client = _make_client()
        client._api_retries = 0
        # Simulate session that is 91 minutes old (SESSION_TTL_SECONDS is 90 min)
        client.login_time = time.monotonic() - (91 * 60)

        def _post_side(url, json, timeout):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"data": "ok", "errorCode": None}
            return resp

        client._session.post.side_effect = _post_side
        relogin_calls = [0]

        def _relogin():
            relogin_calls[0] += 1
            client.login_time = time.monotonic()

        with patch.object(client, "relogin", side_effect=_relogin):
            result = client._post("scene-search", {})

        assert result == "ok"
        assert relogin_calls[0] == 1, "relogin() should be called proactively"

    def test_no_proactive_relogin_for_fresh_session(self):
        """_post does not proactively call relogin() when the session is fresh."""
        client = _make_client()
        client._api_retries = 0
        client.login_time = time.monotonic()  # just logged in

        def _post_side(url, json, timeout):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"data": "ok", "errorCode": None}
            return resp

        client._session.post.side_effect = _post_side

        with patch.object(client, "relogin") as mock_relogin:
            client._post("scene-search", {})

        mock_relogin.assert_not_called()

