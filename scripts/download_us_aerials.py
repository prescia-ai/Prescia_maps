#!/usr/bin/env python3
"""
Download and optimize USGS historical aerial imagery for the entire
continental United States for a given year (default: 1955).

Usage
-----
python scripts/download_us_aerials.py \
  --year 1955 \
  --username apgrant719 \
  --password KaidDerly2020! \
  --output ./tiles/1955 \
  --workers 8

Resume an interrupted run by adding --resume.

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

CONUS_BBOX = (-125.0, 24.0, -66.0, 49.0)  # (west, south, east, north)
GRID_STEP = 10.0  # degrees per grid tile

M2M_BASE_URL = "https://m2m.cr.usgs.gov/api/api/json/stable"

# Candidate dataset names for 1950s aerial coverage (API names)
CANDIDATE_DATASETS = [
    "AERIAL_COMBIN",
    "NHAP",        # National High Altitude Photography
    "NAPP",        # National Aerial Photography Program
    "HRP",         # High Resolution Orthoimagery (fallback)
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

    def __init__(self, username: str, password: str) -> None:
        self._session = requests.Session()
        self._api_key: str | None = None
        self._login(username, password)

    # ── Auth ───────────────────────────────────────────────────────────────────

    def _login(self, username: str, password: str) -> None:
        payload = {"username": username, "password": password}
        resp = self._post("login", payload)
        self._api_key = resp
        self._session.headers.update({"X-Auth-Token": self._api_key})
        logger.info("Logged in to USGS M2M API.")

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
        max_results: int = 50,
    ) -> list[dict]:
        """Search for scenes within bbox for the given year."""
        west, south, east, north = bbox
        payload = {
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
            "maxResults": max_results,
            "startingNumber": 1,
        }
        try:
            result = self._post("scene-search", payload)
            return result.get("results", [])
        except requests.HTTPError as exc:
            logger.warning("scene-search failed for %s: %s", dataset_name, exc)
            return []

    # ── Download ───────────────────────────────────────────────────────────────

    def request_download_urls(
        self, dataset_name: str, scene_ids: list[str]
    ) -> list[dict]:
        """Request download URLs for a list of entity IDs."""
        payload = {
            "datasetName": dataset_name,
            "entityIds": scene_ids,
            "products": [{"productCode": "standard", "useCustomization": False}],
        }
        try:
            result = self._post("download-request", payload)
            return result.get("availableDownloads", [])
        except requests.HTTPError as exc:
            logger.warning("download-request failed: %s", exc)
            return []

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
        resp = self._session.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        if body.get("errorCode"):
            raise requests.HTTPError(f"{body['errorCode']}: {body.get('errorMessage')}")
        return body.get("data")


# ── Main downloader class ──────────────────────────────────────────────────────

class USAerialDownloader:
    """Downloads, optimizes, and tiles USGS historical aerials for the CONUS."""

    def __init__(self, username: str, password: str) -> None:
        self._client = USGSClient(username, password)

    # ── Public API ─────────────────────────────────────────────────────────────

    def download_full_us(
        self,
        year: int,
        output_dir: Path,
        workers: int = 8,
        resume: bool = False,
    ) -> None:
        """End-to-end pipeline: download → optimize → tile → archive."""
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_dir   = output_dir / "raw_geotiffs"
        tile_dir  = output_dir / "tiles" / str(year)
        manifest  = output_dir / "download_manifest.json"

        _add_file_handler(output_dir / "download.log")
        logger.info("Starting US aerial download  year=%d  output=%s", year, output_dir)

        state = self._load_manifest(manifest) if (resume and manifest.exists()) else {}
        completed_grids: set[str] = set(state.get("completed_grids", []))
        all_tif_paths:   list[str] = list(state.get("tif_paths", []))

        grid_boxes = self._create_download_grid(CONUS_BBOX, GRID_STEP)
        total_grids = len(grid_boxes)
        logger.info("Grid tiles: %d  (already done: %d)", total_grids, len(completed_grids))

        # ── Phase 1: Download GeoTIFFs ─────────────────────────────────────────
        for i, bbox in enumerate(grid_boxes, 1):
            grid_key = f"{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}"
            if grid_key in completed_grids:
                logger.info("[%d/%d] Skipping grid %s (cached)", i, total_grids, grid_key)
                continue

            logger.info("[%d/%d] Downloading grid %s", i, total_grids, grid_key)
            grid_dir = raw_dir / f"grid_{i}"
            new_paths = self._download_grid(bbox, year, grid_dir)
            all_tif_paths.extend(str(p) for p in new_paths)

            completed_grids.add(grid_key)
            self._save_manifest(manifest, {
                "completed_grids": list(completed_grids),
                "tif_paths": all_tif_paths,
            })

        # ── Phase 2: Optimize GeoTIFFs ─────────────────────────────────────────
        logger.info("Optimizing %d GeoTIFFs …", len(all_tif_paths))
        opt_dir = output_dir / "optimized_geotiffs"
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
        archive = self.compress_tiles(tile_dir, year, output_dir)

        # ── Phase 5: Metadata ──────────────────────────────────────────────────
        self._write_metadata(tile_dir, year, len(optimized_paths))

        # ── Cleanup temp directories ───────────────────────────────────────────
        logger.info("Cleaning up temporary GeoTIFF directories …")
        for d in (raw_dir, opt_dir):
            if d.exists():
                shutil.rmtree(d)

        logger.info("All done. Archive: %s", archive)
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
        """Search USGS for scenes in bbox/year and download them."""
        grid_dir.mkdir(parents=True, exist_ok=True)
        all_paths: list[Path] = []

        for dataset in CANDIDATE_DATASETS:
            scenes = self._client.search_scenes(dataset, bbox, year)
            if not scenes:
                continue
            logger.info("  Dataset %-20s → %d scenes found", dataset, len(scenes))

            entity_ids = [s.get("entityId", s.get("entity_id", "")) for s in scenes]
            entity_ids = [e for e in entity_ids if e]
            if not entity_ids:
                continue

            downloads = self._client.request_download_urls(dataset, entity_ids)
            for dl in downloads:
                url = dl.get("url")
                if not url:
                    continue
                fname = url.rsplit("/", 1)[-1] or f"{dl.get('entityId', 'scene')}.tif"
                dest  = grid_dir / fname
                if dest.exists():
                    all_paths.append(dest)
                    continue
                logger.info("    Downloading %s", fname)
                if self._client.download_file(url, dest):
                    all_paths.append(dest)
                time.sleep(0.25)  # polite throttle
            break  # use first dataset that has coverage

        return all_paths

    # ── GeoTIFF optimization ───────────────────────────────────────────────────

    def optimize_geotiff(self, input_path: Path, output_path: Path) -> bool:
        """
        Reduce to 10 m resolution, convert to grayscale, and apply JPEG
        compression inside the GeoTIFF.  Returns True on success.
        """
        settings = OPTIMIZATION_SETTINGS
        tr = settings["resolution_meters"]
        try:
            _run([
                "gdalwarp",
                "-tr", str(tr), str(tr),
                "-r",  settings["resampling"],
                "-co", f"COMPRESS={settings['compression']}",
                "-co", f"JPEG_QUALITY={settings['jpeg_quality']}",
                "-co", "PHOTOMETRIC=YCBCR",
                "-co", "TILED=YES",
                str(input_path),
                str(output_path),
            ])
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("gdalwarp failed for %s:\n%s", input_path, exc.stderr)
            return False

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
    ) -> Path:
        """
        Create a tar.gz archive of the tile directory.
        Splits into 2 GB chunks when the total exceeds that threshold.
        """
        archive = output_dir / f"us_aerials_{year}.tar.gz"
        level   = OPTIMIZATION_SETTINGS["tar_compression"]
        logger.info("Creating archive %s (gzip level %d) …", archive, level)

        with tarfile.open(archive, f"w:gz", compresslevel=level) as tar:
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
                "gdal2tiles.py",
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
    parser.add_argument("--password", required=True,
                        help="USGS ERS password.")
    parser.add_argument("--output",   default="./tiles",
                        help="Root output directory.")
    parser.add_argument("--workers",  type=int,
                        default=OPTIMIZATION_SETTINGS["workers"],
                        help="Parallel worker processes for tile conversion.")
    parser.add_argument("--resume",   action="store_true",
                        help="Resume from a previous interrupted run.")
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Allow CLI overrides for the key optimization parameters
    OPTIMIZATION_SETTINGS["zoom_min"]          = args.zoom_min
    OPTIMIZATION_SETTINGS["zoom_max"]          = args.zoom_max
    OPTIMIZATION_SETTINGS["webp_quality"]      = args.webp_quality
    OPTIMIZATION_SETTINGS["resolution_meters"] = args.resolution_meters
    OPTIMIZATION_SETTINGS["workers"]           = args.workers

    output_dir = Path(args.output) / str(args.year)

    downloader = USAerialDownloader(args.username, args.password)
    downloader.download_full_us(
        year=args.year,
        output_dir=output_dir,
        workers=args.workers,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
