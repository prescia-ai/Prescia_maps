#!/usr/bin/env python3
"""
Download and optimize USGS historical aerial imagery for the entire
continental United States for a given year (default: 1955).

Usage
-----
# Preferred: supply the token via environment variable (avoids credentials on
# the command line)
export USGS_M2M_TOKEN=YOUR_APPLICATION_TOKEN
python scripts/download_us_aerials.py \
  --year 1955 \
  --username YOUR_USGS_USERNAME \
  --output ./tiles \
  --workers 8

# Alternatively, pass the token directly:
python scripts/download_us_aerials.py \
  --year 1955 \
  --username YOUR_USGS_USERNAME \
  --token YOUR_APPLICATION_TOKEN \
  --output ./tiles \
  --workers 8

Resume an interrupted run by adding --resume.

The --token value can also be supplied via the USGS_M2M_TOKEN environment
variable so you avoid putting credentials on the command line.

To generate an Application Token:
  1. Log in at https://ers.cr.usgs.gov/
  2. Go to Profile → Application Tokens (https://ers.cr.usgs.gov/profile/access)
  3. Create a new token with the "M2M API" scope
  4. Copy the token within the 60-second display window

System dependencies
-------------------
  sudo apt-get install gdal-bin python3-gdal webp
  pip install requests pillow tqdm

USGS M2M API requires a free account:
  https://ers.cr.usgs.gov/register/
"""

import argparse
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ── Optional progress bar ──────────────────────────────────────────────────────
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[assignment]

# ── Constants ──────────────────────────────────────────────────────────────────

# Resolved at startup by _preflight_check_tools(); falls back to "gdal2tiles.py"
# so the module can be imported in tests without GDAL installed.
GDAL2TILES_CMD: str = "gdal2tiles.py"

# M2M session refresh thresholds
SESSION_TTL_SECONDS = 90 * 60      # 5400 s — proactive re-login in _post
GRID_RELOGIN_SECONDS = 60 * 60     # 3600 s — proactive re-login between grids

CONUS_BBOX = (-125.0, 24.0, -66.0, 49.0)  # (west, south, east, north)
GRID_STEP = 10.0  # degrees per grid tile

M2M_BASE_URL = "https://m2m.cr.usgs.gov/api/api/json/stable"

# Candidate dataset names for historical aerial coverage (API names).
# AERIAL_COMBIN is the primary collection for all historical single-frame
# aerials (USGS, USDA, and other agencies, all decades).  NHAP and NAPP cover
# dedicated national programmes from the late 1970s-1990s.  All candidates are
# tried and results merged so coverage is maximised.  Do not include AERIAL
# (not a valid M2M datasetName) or HRP (modern orthoimagery only).
CANDIDATE_DATASETS = [
    "AERIAL_COMBIN",   # Aerial Photo Single Frames (primary historical collection, all decades)
    "NHAP",            # National High Altitude Photography (late 1970s-80s)
    "NAPP",            # National Aerial Photography Program (1980s-90s)
]

OPTIMIZATION_SETTINGS: dict[str, Any] = {
    "resolution_meters": 10,   # 10 m/pixel (down from 1 m)
    "zoom_min": 8,
    "zoom_max": 12,            # skip 13-16 to save space
    "webp_quality": 65,        # aggressive but usable
    "webp_method": 6,          # maximum WebP compression effort
    "compression": "JPEG",     # compression inside GeoTIFF
    "jpeg_quality": 75,
    "color_mode": "grayscale",
    "resampling": "average",
    "tar_compression": 9,      # gzip level 9
    "workers": 8,
}

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _add_file_handler(log_path: Path) -> None:
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(fh)


# ── Helper: run shell command ──────────────────────────────────────────────────

def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    logger.debug("CMD: %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


# ── USGS M2M API client ────────────────────────────────────────────────────────

class USGSClient:
    """Thin wrapper around the USGS Machine-to-Machine (M2M) JSON API."""

    def __init__(
        self,
        username: str,
        token: str,
        api_timeout: int = 300,
        api_retries: int = 5,
    ) -> None:
        self._session = requests.Session()
        self._api_key: str | None = None
        self._api_timeout = api_timeout
        self._api_retries = api_retries
        self._username = username
        self._token = token
        self.login_time: float = 0.0
        self._login(username, token)

    # ── Auth ───────────────────────────────────────────────────────────────────

    def _login(self, username: str, token: str) -> None:
        payload = {"username": username, "token": token}
        resp = self._post("login-token", payload)
        self._api_key = resp
        self._session.headers.update({"X-Auth-Token": self._api_key})
        self.login_time = time.monotonic()
        logger.info("Logged in to USGS M2M API.")

    def relogin(self) -> None:
        """Refresh the M2M auth token by re-running login-token."""
        logger.warning("USGS auth appears expired — re-logging in …")
        self._session.headers.pop("X-Auth-Token", None)
        self._login(self._username, self._token)

    def logout(self) -> None:
        try:
            self._post("logout", {})
        except Exception:
            pass
        logger.info("Logged out of USGS M2M API.")

    # ── Scene search ───────────────────────────────────────────────────────────

    def search_scenes(
        self,
        dataset_name: str,
        bbox: tuple[float, float, float, float],
        year: int,
        max_results: int = 10_000,
        page_size: int = 100,
    ) -> list[dict]:
        """Search for scenes within bbox for the given year.

        Paginates through all results using ``startingNumber`` so grids with
        more than *page_size* scenes are fully retrieved.  At most *max_results*
        scenes are returned across all pages.
        """
        west, south, east, north = bbox
        base_payload = {
            "datasetName": dataset_name,
            "spatialFilter": {
                "filterType": "mbr",
                "lowerLeft":  {"latitude": south, "longitude": west},
                "upperRight": {"latitude": north, "longitude": east},
            },
            "temporalFilter": {
                "startDate": f"{year}-01-01",
                "endDate":   f"{year}-12-31",
            },
        }
        all_scenes: list[dict] = []
        starting = 1
        pages = 0
        try:
            while len(all_scenes) < max_results:
                payload = dict(base_payload)
                payload["maxResults"]     = min(page_size, max_results - len(all_scenes))
                payload["startingNumber"] = starting
                result = self._post("scene-search", payload)
                page_results = result.get("results", []) if result else []
                if not page_results:
                    break
                all_scenes.extend(page_results)
                pages += 1
                total_hits = result.get("totalHits", len(all_scenes))
                starting += len(page_results)
                if starting > total_hits:
                    break
        except requests.HTTPError as exc:
            logger.warning("scene-search failed for %s: %s", dataset_name, exc)
            return []
        if pages > 1:
            logger.debug(
                "scene-search %s: total scenes found across %d pages: %d",
                dataset_name, pages, len(all_scenes),
            )
        return all_scenes

    # ── Download ───────────────────────────────────────────────────────────────

    def get_download_options(
        self, dataset_name: str, entity_ids: list[str]
    ) -> list[dict]:
        """Return available download products for *entity_ids* in *dataset_name*.

        Calls the M2M ``download-options`` endpoint.  Each item in the returned
        list has at least ``entityId``, ``id`` (the product ID), ``available``,
        and ``bulkAvailable`` keys.
        """
        payload = {"datasetName": dataset_name, "entityIds": entity_ids}
        try:
            result = self._post("download-options", payload)
            return result if isinstance(result, list) else []
        except requests.HTTPError as exc:
            logger.warning("download-options failed for %s: %s", dataset_name, exc)
            return []

    def request_download_urls(
        self, dataset_name: str, scene_ids: list[str]
    ) -> list[dict]:
        """Request download URLs for a list of entity IDs.

        Correct M2M flow:

        1. ``download-options``  → per-scene product catalogue
        2. ``download-request``  → submit ``{downloads:[{entityId,productId}], label}``
        3. ``download-retrieve`` → poll for items that are still "preparing"

        Exactly one product is selected per ``entityId`` to avoid downloading
        the same scene multiple times.  Preference order (first match wins):

        1. Product whose ``productCode`` or ``productName`` matches
           ``(?i)standard|geotiff|tiff|full.?res|high.?res`` **and** is
           ``available`` or ``bulkAvailable``.
        2. The product with the largest ``filesize``/``productSize`` that is
           ``available`` or ``bulkAvailable``.
        3. The first product that is ``available`` or ``bulkAvailable``.

        Returns combined list of download dicts (each has a ``url`` key).
        """
        import re
        _PREFERRED = re.compile(r"(?i)standard|geotiff|tiff|full.?res|high.?res")

        # Step 1: get real {entityId, productId} pairs from the catalogue
        options = self.get_download_options(dataset_name, scene_ids)

        # Group options by entityId
        by_entity: dict[str, list[dict]] = {}
        for opt in options:
            eid = opt.get("entityId")
            if eid:
                by_entity.setdefault(eid, []).append(opt)

        downloads_to_request: list[dict] = []

        def _size(p: dict) -> int:
            return int(p.get("filesize") or p.get("productSize") or 0)

        for eid, products in by_entity.items():
            available = [
                p for p in products
                if p.get("available") or p.get("bulkAvailable")
            ]
            if not available:
                continue

            # Preference 1: name matches preferred pattern
            chosen = next(
                (
                    p for p in available
                    if _PREFERRED.search(str(p.get("productCode", "")))
                    or _PREFERRED.search(str(p.get("productName", "")))
                ),
                None,
            )
            if chosen is None:
                # Preference 2: largest filesize / productSize
                largest = max(available, key=_size, default=None)
                if largest is not None and _size(largest) > 0:
                    chosen = largest
                else:
                    # Preference 3: first available product
                    chosen = available[0]

            product_id = chosen.get("id")
            if product_id:
                downloads_to_request.append({"entityId": eid, "productId": product_id})

        logger.debug(
            "download-options: %d/%d scenes have a downloadable product",
            len(downloads_to_request), len(scene_ids),
        )
        if not downloads_to_request:
            return []

        # Step 2: submit download request with proper payload shape
        label = f"prescia_{dataset_name}_{int(time.time())}"
        payload = {"downloads": downloads_to_request, "label": label}
        try:
            result = self._post("download-request", payload)
        except requests.HTTPError as exc:
            logger.warning("download-request failed: %s", exc)
            return []

        available_dl: list[dict] = result.get("availableDownloads", []) if result else []
        preparing: list[dict]    = result.get("preparingDownloads", []) if result else []
        logger.debug(
            "download-request: %d available, %d preparing",
            len(available_dl), len(preparing),
        )

        # Step 3: poll for items that are still being prepared
        if preparing:
            retrieved = self._poll_download_retrieve(label)
            available_dl.extend(retrieved)

        return available_dl

    def _poll_download_retrieve(
        self, label: str, max_wait: int = 300
    ) -> list[dict]:
        """Poll ``download-retrieve`` until all items are ready or *max_wait* expires."""
        collected: list[dict] = []
        deadline = time.time() + max_wait
        delay = 5
        while time.time() < deadline:
            time.sleep(delay)
            delay = min(delay * 2, 60)  # exponential back-off, cap at 60 s
            try:
                result = self._post("download-retrieve", {"label": label})
            except requests.HTTPError as exc:
                logger.warning("download-retrieve failed: %s", exc)
                break
            if not result:
                continue
            ready         = result.get("available", [])
            still_waiting = result.get("requested", [])
            collected.extend(ready)
            if ready:
                logger.debug(
                    "download-retrieve: +%d ready, %d still preparing",
                    len(ready), len(still_waiting),
                )
            if not still_waiting:
                break
        return collected

    def download_file(self, url: str, dest_path: Path) -> bool:
        """Stream download to dest_path. Returns True on success."""
        try:
            with self._session.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            return True
        except Exception as exc:
            logger.error("Download failed (%s): %s", url, exc)
            if dest_path.exists():
                dest_path.unlink()
            return False

    # ── Internal ───────────────────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> Any:
        url = f"{M2M_BASE_URL}/{endpoint}"
        timeout = (30, self._api_timeout)
        last_exc: Exception = RuntimeError("Retry loop failed without capturing exception")

        # Proactively re-login if the session is older than 90 minutes, but not
        # while executing login-token itself (that would recurse infinitely).
        if endpoint != "login-token" and time.monotonic() - self.login_time > SESSION_TTL_SECONDS:
            self.relogin()

        auth_retried = False
        attempt = 0
        # attempt=0 is the initial try; 1..api_retries are regular retries.
        # Auth retries (401/403) do NOT increment attempt so they don't consume a slot.
        while attempt <= self._api_retries:
            try:
                resp = self._session.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                body = resp.json()
                if body.get("errorCode"):
                    raise requests.HTTPError(
                        f"{body['errorCode']}: {body.get('errorMessage')}"
                    )
                return body.get("data")
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < self._api_retries:
                    wait = 2 ** (attempt + 1)  # 2s, 4s, 8s, 16s, 32s
                    logger.warning(
                        "USGS /%s timed out, retrying in %ds (attempt %d/%d)",
                        endpoint, wait, attempt + 1, self._api_retries,
                    )
                    time.sleep(wait)
                attempt += 1
            except requests.exceptions.HTTPError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else 0
                if status in (401, 403) and not auth_retried:
                    auth_retried = True
                    self.relogin()
                    # Do NOT increment attempt — retry the same slot immediately
                    continue
                # Only retry transient server/rate-limit errors
                if status == 429 or status >= 500:
                    if attempt < self._api_retries:
                        wait = 2 ** (attempt + 1)  # 2s, 4s, 8s, 16s, 32s
                        logger.warning(
                            "USGS /%s returned %d, retrying in %ds (attempt %d/%d)",
                            endpoint, status, wait, attempt + 1, self._api_retries,
                        )
                        time.sleep(wait)
                    attempt += 1
                else:
                    # 4xx (except 401/403 first-time and 429) — don't retry, fail fast
                    raise
        raise last_exc


# ── Main downloader class ──────────────────────────────────────────────────────

class USAerialDownloader:
    """Downloads, optimizes, and tiles USGS historical aerials for the CONUS."""

    def __init__(
        self,
        username: str,
        token: str,
        api_timeout: int = 300,
        api_retries: int = 5,
    ) -> None:
        self._client = USGSClient(username, token, api_timeout=api_timeout, api_retries=api_retries)

    # ── Public API ─────────────────────────────────────────────────────────────

    def download_full_us(
        self,
        year: int,
        output_dir: Path,
        workers: int = 8,
        resume: bool = False,
    ) -> None:
        """End-to-end pipeline: download → optimize → tile → archive.

        ``output_dir`` should be the root output directory, e.g. ``./tiles``.
        A ``<year>/`` sub-directory is created automatically::

            python scripts/download_us_aerials.py --year 1955 --output ./tiles

        Passing ``--output ./tiles/1955`` also works — the script detects that
        the directory already ends in the year and does **not** append it again.
        """
        # Make year_dir idempotent: don't double-append if output_dir already ends
        # in the year (e.g. the user passed --output ./tiles/1955).
        if output_dir.name == str(year):
            logger.warning(
                "Output directory '%s' already ends in %d; using it directly "
                "without creating a nested year subdirectory.",
                output_dir, year,
            )
            year_dir = output_dir
        else:
            year_dir = output_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        raw_dir   = year_dir / "raw_geotiffs"
        tile_dir  = year_dir / "tiles"
        manifest  = year_dir / "download_manifest.json"

        _add_file_handler(year_dir / "download.log")
        logger.info("Starting US aerial download  year=%d  output=%s", year, year_dir)

        state = self._load_manifest(manifest) if (resume and manifest.exists()) else {}
        completed_grids: set[str] = set(state.get("completed_grids", []))
        all_tif_paths:   list[str] = list(state.get("tif_paths", []))
        # On resume, previously failed grids are retried; start fresh otherwise
        failed_grids: list[str] = list(state.get("failed_grids", [])) if resume else []

        grid_boxes = self._create_download_grid(CONUS_BBOX, GRID_STEP)
        total_grids = len(grid_boxes)

        # On resume, also collect grid boxes for previously failed grids
        if resume and failed_grids:
            retry_keys = set(failed_grids)
            failed_grids.clear()  # Will re-populate as they fail again
            # Remove previously failed grids from completed so they get retried
            for key in retry_keys:
                completed_grids.discard(key)

        logger.info("Grid tiles: %d  (already done: %d)", total_grids, len(completed_grids))

        # ── Phase 1: Download GeoTIFFs ─────────────────────────────────────────
        for i, bbox in enumerate(grid_boxes, 1):
            grid_key = f"{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}"
            if grid_key in completed_grids:
                logger.info("[%d/%d] Skipping grid %s (cached)", i, total_grids, grid_key)
                continue

            logger.info("[%d/%d] Downloading grid %s", i, total_grids, grid_key)
            grid_dir = raw_dir / f"grid_{i}"

            # Proactively re-login between grids if the session is older than 60 minutes.
            if time.monotonic() - self._client.login_time > GRID_RELOGIN_SECONDS:
                self._client.relogin()

            try:
                new_paths = self._download_grid(bbox, year, grid_dir)
            except Exception as exc:
                logger.warning(
                    "[%d/%d] Grid %s failed: %s — skipping and recording for retry",
                    i, total_grids, grid_key, exc,
                )
                if grid_key not in failed_grids:
                    failed_grids.append(grid_key)
                self._save_manifest(manifest, {
                    "completed_grids": list(completed_grids),
                    "tif_paths": all_tif_paths,
                    "failed_grids": failed_grids,
                })
                continue
            all_tif_paths.extend(str(p) for p in new_paths)

            completed_grids.add(grid_key)
            self._save_manifest(manifest, {
                "completed_grids": list(completed_grids),
                "tif_paths": all_tif_paths,
                "failed_grids": failed_grids,
            })

        completed_count = len(completed_grids)
        failed_count = len(failed_grids)
        logger.info(
            "Completed: %d/%d grids. Failed: %d%s",
            completed_count, total_grids, failed_count,
            " (see download_manifest.json `failed_grids` for retry)" if failed_count else "",
        )

        # ── Phase 2: Optimize GeoTIFFs ─────────────────────────────────────────
        logger.info("Optimizing %d GeoTIFFs …", len(all_tif_paths))
        opt_dir = year_dir / "optimized_geotiffs"
        opt_dir.mkdir(parents=True, exist_ok=True)
        optimized_paths = []
        for tif in all_tif_paths:
            src = Path(tif)
            dst = opt_dir / src.name
            if dst.exists():
                optimized_paths.append(dst)
                continue
            ok = self.optimize_geotiff(src, dst)
            if ok:
                optimized_paths.append(dst)
            else:
                logger.warning("Skipping corrupted file: %s", src)

        # ── Phase 3: Generate tiles ────────────────────────────────────────────
        logger.info("Generating tiles …")
        self.create_optimized_tiles(optimized_paths, tile_dir, workers=workers)

        # ── Phase 4: Archive ───────────────────────────────────────────────────
        logger.info("Compressing tiles …")
        archive = self.compress_tiles(tile_dir, year, year_dir)

        # ── Phase 5: Metadata ──────────────────────────────────────────────────
        if archive is not None:
            self._write_metadata(tile_dir, year, len(optimized_paths))

        # ── Cleanup temp directories ───────────────────────────────────────────
        logger.info("Cleaning up temporary GeoTIFF directories …")
        for d in (raw_dir, opt_dir):
            if d.exists():
                shutil.rmtree(d)

        if archive is not None:
            logger.info("All done. Archive: %s", archive)
        else:
            logger.error("All done. No archive was created — no tiles were generated.")
        self._client.logout()

    # ── Grid creation ──────────────────────────────────────────────────────────

    def _create_download_grid(
        self,
        bbox: tuple[float, float, float, float],
        grid_size: float = 10.0,
    ) -> list[tuple[float, float, float, float]]:
        """Divide bbox into grid_size×grid_size degree tiles."""
        west, south, east, north = bbox
        boxes: list[tuple[float, float, float, float]] = []
        lat = south
        while lat < north:
            lon = west
            while lon < east:
                boxes.append((
                    round(lon, 4),
                    round(lat, 4),
                    round(min(lon + grid_size, east),  4),
                    round(min(lat + grid_size, north), 4),
                ))
                lon += grid_size
            lat += grid_size
        return boxes

    # ── Per-grid download ──────────────────────────────────────────────────────

    def _download_grid(
        self,
        bbox: tuple[float, float, float, float],
        year: int,
        grid_dir: Path,
    ) -> list[Path]:
        """Search USGS for scenes in bbox/year and download them.

        Tries every candidate dataset, accumulates results, and deduplicates by
        entity ID so the same scene is never downloaded twice.  Raises
        ``RuntimeError`` when no download URLs are returned across all datasets.
        """
        grid_dir.mkdir(parents=True, exist_ok=True)
        all_paths:    list[Path] = []
        all_downloads: list[dict] = []
        seen_entity_ids: set[str] = set()

        for dataset in CANDIDATE_DATASETS:
            scenes = self._client.search_scenes(dataset, bbox, year)
            if not scenes:
                continue

            # Deduplicate entity IDs: skip any already seen in a prior dataset
            entity_ids = [
                eid
                for eid in (
                    s.get("entityId", s.get("entity_id", "")) for s in scenes
                )
                if eid and eid not in seen_entity_ids
            ]
            if not entity_ids:
                continue
            seen_entity_ids.update(entity_ids)
            logger.info("  Dataset %-20s → %d scenes found", dataset, len(entity_ids))

            downloads = self._client.request_download_urls(dataset, entity_ids)
            if not downloads:
                logger.warning(
                    "  Dataset %s: 0/%d scenes returned download URLs",
                    dataset, len(entity_ids),
                )
                continue

            unique_scenes = len({dl.get("entityId") for dl in downloads if dl.get("entityId")})
            logger.info(
                "  Dataset %-20s → %d/%d scenes have download URLs",
                dataset, unique_scenes, len(entity_ids),
            )
            if unique_scenes < len(entity_ids) * 0.5:
                logger.warning(
                    "  Dataset %s: fewer than half of scenes have download URLs "
                    "(%d/%d) — some scenes may be unavailable.",
                    dataset, unique_scenes, len(entity_ids),
                )
            all_downloads.extend(downloads)

        if not all_downloads:
            raise RuntimeError(
                f"No download URLs were returned by any dataset for this grid "
                f"(tried: {', '.join(CANDIDATE_DATASETS)})"
            )

        # Deduplicate downloads by URL before fetching
        seen_urls: set[str] = set()
        for dl in all_downloads:
            url = dl.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            fname = url.rsplit("/", 1)[-1] or f"{dl.get('entityId', 'scene')}.tif"
            dest  = grid_dir / fname
            if dest.exists():
                all_paths.append(dest)
                continue
            logger.info("    Downloading %s", fname)
            if self._client.download_file(url, dest):
                all_paths.append(dest)
            time.sleep(0.25)  # polite throttle

        return all_paths

    # ── GeoTIFF optimization ───────────────────────────────────────────────────

    def optimize_geotiff(self, input_path: Path, output_path: Path) -> bool:
        """
        Reduce to 10 m resolution, convert to grayscale, and apply JPEG
        compression inside the GeoTIFF.  Returns True on success.

        ``PHOTOMETRIC=YCBCR`` is only added for RGB (≥ 3-band) inputs; it is
        invalid for single-band grayscale scans and would cause gdalwarp to fail.
        """
        settings = OPTIMIZATION_SETTINGS
        tr = settings["resolution_meters"]
        band_count = self._get_band_count(input_path)
        cmd = [
            "gdalwarp",
            "-tr", str(tr), str(tr),
            "-r",  settings["resampling"],
            "-co", f"COMPRESS={settings['compression']}",
            "-co", f"JPEG_QUALITY={settings['jpeg_quality']}",
            "-co", "TILED=YES",
        ]
        if band_count >= 3:
            cmd += ["-co", "PHOTOMETRIC=YCBCR"]
        cmd += [str(input_path), str(output_path)]
        try:
            _run(cmd)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("gdalwarp failed for %s:\n%s", input_path, exc.stderr)
            return False

    @staticmethod
    def _get_band_count(path: Path) -> int:
        """Return the number of raster bands in *path* (0 on error)."""
        try:
            result = subprocess.run(
                ["gdalinfo", "-json", str(path)],
                check=True, capture_output=True, text=True,
            )
            info = json.loads(result.stdout)
            return len(info.get("bands", []))
        except Exception:
            return 0

    # ── Tiling ────────────────────────────────────────────────────────────────

    def create_optimized_tiles(
        self,
        geotiff_paths: list[Path],
        tile_dir: Path,
        workers: int = 8,
    ) -> None:
        """Convert each optimized GeoTIFF to WebP tiles in tile_dir."""
        tile_dir.mkdir(parents=True, exist_ok=True)
        args = [(p, tile_dir) for p in geotiff_paths]

        if not args:
            logger.warning("No GeoTIFFs to tile.")
            return

        logger.info("Tiling %d files with %d workers …", len(args), workers)
        done = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_single_geotiff_worker, a): a for a in args}
            for future in as_completed(futures):
                tif, _ = futures[future]
                try:
                    future.result()
                    done += 1
                    logger.info("  [%d/%d] Tiled %s", done, len(args), tif.name)
                except Exception as exc:
                    logger.error("  Tiling failed for %s: %s", tif.name, exc)

    # ── Compression ───────────────────────────────────────────────────────────

    def compress_tiles(
        self, tile_dir: Path, year: int, output_dir: Path
    ) -> Path | None:
        """
        Create a tar.gz archive of the tile directory.
        Splits into 2 GB chunks when the total exceeds that threshold.
        Returns ``None`` (and logs an error) when *tile_dir* contains no
        ``*.webp`` files — the pipeline should not create an empty archive.
        """
        webp_files = list(tile_dir.rglob("*.webp")) if tile_dir.exists() else []
        if not webp_files:
            logger.error(
                "compress_tiles: %s contains no *.webp files — skipping archive creation.",
                tile_dir,
            )
            return None

        archive = output_dir / f"us_aerials_{year}.tar.gz"
        level   = OPTIMIZATION_SETTINGS["tar_compression"]
        logger.info("Creating archive %s (gzip level %d) …", archive, level)

        with tarfile.open(archive, "w:gz", compresslevel=level) as tar:
            tar.add(tile_dir, arcname=str(year))

        size_gb = archive.stat().st_size / (1 << 30)
        logger.info("Archive size: %.2f GB", size_gb)

        chunk_size = 2 * (1 << 30)  # 2 GB
        if archive.stat().st_size > chunk_size:
            logger.info("Archive exceeds 2 GB — splitting into chunks …")
            self._split_archive(archive, chunk_size)

        return archive

    def _split_archive(self, archive: Path, chunk_size: int) -> None:
        """Split archive into chunk_size byte parts (archive.part00, .part01, …)."""
        with open(archive, "rb") as src:
            part = 0
            while True:
                data = src.read(chunk_size)
                if not data:
                    break
                part_path = archive.with_suffix(f".part{part:02d}")
                with open(part_path, "wb") as dst:
                    dst.write(data)
                logger.info("  Chunk: %s (%.2f GB)", part_path.name, len(data) / (1 << 30))
                part += 1
        archive.unlink()
        logger.info("Split into %d chunks.", part)

    # ── Metadata ───────────────────────────────────────────────────────────────

    def _write_metadata(
        self, tile_dir: Path, year: int, scenes_downloaded: int
    ) -> None:
        webp_files = list(tile_dir.rglob("*.webp"))
        total_tiles = len(webp_files)
        total_bytes = sum(f.stat().st_size for f in webp_files)

        meta = {
            "year": year,
            "bbox": list(CONUS_BBOX),
            "resolution_meters": OPTIMIZATION_SETTINGS["resolution_meters"],
            "zoom_levels": list(range(
                OPTIMIZATION_SETTINGS["zoom_min"],
                OPTIMIZATION_SETTINGS["zoom_max"] + 1,
            )),
            "total_tiles": total_tiles,
            "total_size_gb": round(total_bytes / (1 << 30), 3),
            "format": "webp",
            "quality": OPTIMIZATION_SETTINGS["webp_quality"],
            "download_date": datetime.now(timezone.utc).date().isoformat(),
            "scenes_downloaded": scenes_downloaded,
            "coverage": "Continental United States",
        }
        meta_path = tile_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        logger.info("Metadata written to %s", meta_path)

    # ── Manifest helpers ───────────────────────────────────────────────────────

    def _save_manifest(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2))

    def _load_manifest(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}


# ── Worker function (must be top-level for multiprocessing) ───────────────────

def _process_single_geotiff_worker(args: tuple[Path, Path]) -> None:
    """
    Convert one optimized GeoTIFF into WebP map tiles.

    Steps:
      1. gdal2tiles.py  →  PNG tiles  (zoom 8-12)
      2. cwebp          →  WebP tiles (quality 65, method 6)
      3. Delete PNG tiles
    """
    tif_path, tile_dir = args
    settings = OPTIMIZATION_SETTINGS
    zoom_min = settings["zoom_min"]
    zoom_max = settings["zoom_max"]
    quality  = settings["webp_quality"]
    method   = settings["webp_method"]

    tmp_png_dir = tile_dir / f"_tmp_png_{tif_path.stem}"
    tmp_png_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Raster → PNG tiles ─────────────────────────────────────────────────
        subprocess.run(
            [
                GDAL2TILES_CMD,
                "--zoom", f"{zoom_min}-{zoom_max}",
                "--resampling", settings["resampling"],
                "--webviewer", "none",
                str(tif_path),
                str(tmp_png_dir),
            ],
            check=True,
            capture_output=True,
        )

        # ── PNG → WebP ─────────────────────────────────────────────────────────
        for png in tmp_png_dir.rglob("*.png"):
            rel   = png.relative_to(tmp_png_dir)
            webp  = tile_dir / rel.with_suffix(".webp")
            webp.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "cwebp",
                    "-q",  str(quality),
                    "-m",  str(method),
                    str(png),
                    "-o", str(webp),
                ],
                check=True,
                capture_output=True,
            )

    finally:
        # Always remove temp PNGs to keep disk usage low
        if tmp_png_dir.exists():
            shutil.rmtree(tmp_png_dir)


# ── Preflight tool check ───────────────────────────────────────────────────────

_INSTALL_INSTRUCTIONS = """\
Windows install:
  1. Download OSGeo4W: https://download.osgeo.org/osgeo4w/osgeo4w-setup.exe
     Express Install → check "GDAL"
  2. Download libwebp: https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.4.0-windows-x64.zip
     Extract and copy bin\\cwebp.exe to C:\\OSGeo4W\\bin\\
  3. Add C:\\OSGeo4W\\bin to PATH

Linux install:
  sudo apt-get install gdal-bin python3-gdal webp

Verify:
  gdalwarp --version
  gdal2tiles --help
  cwebp -version"""


def _preflight_check_tools() -> None:
    """Verify that all required external tools are on PATH.

    Resolves ``gdal2tiles`` / ``gdal2tiles.py`` and sets the module-level
    ``GDAL2TILES_CMD`` constant so the worker can use whichever form is
    available (OSGeo4W on Windows ships ``gdal2tiles.bat``; Linux ships
    ``gdal2tiles.py``).

    Exits with code 2 and a helpful install message if any tool is missing.
    """
    global GDAL2TILES_CMD

    missing: list[tuple[str, str]] = []

    if not shutil.which("gdalwarp"):
        missing.append(("gdalwarp", "install GDAL"))

    # Accept either name: gdal2tiles (OSGeo4W / newer distros) or gdal2tiles.py
    gdal2tiles_path = shutil.which("gdal2tiles") or shutil.which("gdal2tiles.py")
    if gdal2tiles_path is None:
        missing.append(("gdal2tiles / gdal2tiles.py", "install GDAL"))
    else:
        GDAL2TILES_CMD = gdal2tiles_path

    if not shutil.which("cwebp"):
        missing.append(("cwebp", "install libwebp"))

    if missing:
        lines = ["ERROR: Required external tools missing from PATH:"]
        for tool, hint in missing:
            lines.append(f"  - {tool:<30} ({hint})")
        lines.append("")
        lines.append(_INSTALL_INSTRUCTIONS)
        print("\n".join(lines), file=sys.stderr)
        sys.exit(2)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and optimize USGS historical aerials for the continental US.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--year",     type=int, default=1955,
                        help="Target year for aerial imagery.")
    parser.add_argument("--username", required=True,
                        help="USGS ERS username.")
    parser.add_argument("--token", default=None,
                        help=(
                            "USGS Application Token (M2M API scope). "
                            "May also be supplied via the USGS_M2M_TOKEN env var. "
                            "Generate one at https://ers.cr.usgs.gov/profile/access "
                            "(Profile → Application Tokens)"
                        ))
    parser.add_argument("--output",   default="./tiles",
                        help="Root output directory.")
    parser.add_argument("--workers",  type=int,
                        default=OPTIMIZATION_SETTINGS["workers"],
                        help="Parallel worker processes for tile conversion.")
    parser.add_argument("--resume",   action="store_true",
                        help="Resume from a previous interrupted run.")
    parser.add_argument("--skip-preflight", action="store_true",
                        dest="skip_preflight",
                        help="Skip preflight check for external tools (useful in CI/testing).")
    parser.add_argument("--zoom-min", type=int,
                        default=OPTIMIZATION_SETTINGS["zoom_min"],
                        dest="zoom_min",
                        help="Minimum zoom level to generate.")
    parser.add_argument("--zoom-max", type=int,
                        default=OPTIMIZATION_SETTINGS["zoom_max"],
                        dest="zoom_max",
                        help="Maximum zoom level to generate.")
    parser.add_argument("--webp-quality", type=int,
                        default=OPTIMIZATION_SETTINGS["webp_quality"],
                        dest="webp_quality",
                        help="WebP quality (1-100, lower = smaller file).")
    parser.add_argument("--resolution", type=int,
                        default=OPTIMIZATION_SETTINGS["resolution_meters"],
                        dest="resolution_meters",
                        help="Target GeoTIFF resolution in metres.")
    parser.add_argument("--api-timeout", type=int, default=300,
                        dest="api_timeout",
                        help="Read timeout in seconds for USGS M2M API calls.")
    parser.add_argument("--api-retries", type=int, default=5,
                        dest="api_retries",
                        help="Maximum number of retries for transient USGS API errors.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.skip_preflight:
        _preflight_check_tools()

    # Resolve token: CLI flag → env var → error
    token = args.token or os.environ.get("USGS_M2M_TOKEN")
    if not token:
        print(
            "Error: a USGS Application Token is required.\n"
            "Pass it with --token or set the USGS_M2M_TOKEN environment variable.\n"
            "Generate a token at: https://ers.cr.usgs.gov/profile/access",
            file=sys.stderr,
        )
        sys.exit(1)

    # Allow CLI overrides for the key optimization parameters
    OPTIMIZATION_SETTINGS["zoom_min"]          = args.zoom_min
    OPTIMIZATION_SETTINGS["zoom_max"]          = args.zoom_max
    OPTIMIZATION_SETTINGS["webp_quality"]      = args.webp_quality
    OPTIMIZATION_SETTINGS["resolution_meters"] = args.resolution_meters
    OPTIMIZATION_SETTINGS["workers"]           = args.workers

    output_dir = Path(args.output)  # year sub-directory is created by download_full_us

    downloader = USAerialDownloader(
        args.username, token,
        api_timeout=args.api_timeout,
        api_retries=args.api_retries,
    )
    downloader.download_full_us(
        year=args.year,
        output_dir=output_dir,
        workers=args.workers,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
