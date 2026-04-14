# Historical Aerials Setup Guide

This guide explains how to download, optimize, and serve 1955 USGS historical
aerial imagery as a tile overlay on the Prescia Maps Leaflet map.

---

## 1. Prerequisites

### USGS Account

The downloader uses the USGS Machine-to-Machine (M2M) JSON API, which requires
a free USGS Earth Resources Observation and Science (EROS) account.

1. Register at <https://ers.cr.usgs.gov/register/>
2. Log in and request M2M API access (usually approved within a day)

### Storage

| Stage                        | Disk space needed |
|------------------------------|-------------------|
| Downloaded raw GeoTIFFs      | ~80–120 GB (temp) |
| Optimized GeoTIFFs           | ~15–25 GB (temp)  |
| Final WebP tiles (zoom 8-12) | ~8–12 GB          |
| Compressed archive           | ~5–7 GB           |

Temporary files are automatically deleted once tiling is complete.  
Plan for at least **~30 GB** of free space on the processing machine.

---

## 2. Installation

### System packages

```bash
# Debian / Ubuntu
sudo apt-get update
sudo apt-get install -y gdal-bin python3-gdal webp

# macOS (Homebrew)
brew install gdal webp
```

Verify that `gdalwarp`, `gdal2tiles.py`, and `cwebp` are all on your `PATH`:

```bash
gdalwarp --version
gdal2tiles.py --version
cwebp -version
```

### Python packages

```bash
pip install requests pillow tqdm
```

---

## 3. Running the Download Script

### Basic usage

```bash
python scripts/download_us_aerials.py \
  --year 1955 \
  --username YOUR_USGS_USERNAME \
  --password YOUR_USGS_PASSWORD \
  --output ./tiles \
  --workers 8
```

The script writes output to `./tiles/1955/` by default.

### Resuming an interrupted run

```bash
python scripts/download_us_aerials.py \
  --year 1955 \
  --username YOUR_USGS_USERNAME \
  --password YOUR_USGS_PASSWORD \
  --output ./tiles \
  --resume
```

Progress is tracked in `./tiles/1955/download_manifest.json`.  
Each completed 10° × 10° grid square is recorded so you never re-download it.

### All options

| Flag | Default | Description |
|------|---------|-------------|
| `--year` | `1955` | Target year for aerial imagery |
| `--username` | *(required)* | USGS ERS username |
| `--password` | *(required)* | USGS ERS password |
| `--output` | `./tiles` | Root output directory |
| `--workers` | `8` | Parallel processes for tile conversion |
| `--resume` | `false` | Resume from a previous interrupted run |
| `--zoom-min` | `8` | Minimum zoom level to generate |
| `--zoom-max` | `12` | Maximum zoom level to generate |
| `--webp-quality` | `65` | WebP quality (1-100, lower = smaller) |
| `--resolution` | `10` | GeoTIFF target resolution in metres |

### Alternative sizes (if 10 GB is still too large)

```bash
# ~6 GB — skip zoom 12
--zoom-max 11

# ~5 GB — lower WebP quality
--webp-quality 55

# ~4 GB — coarser resolution
--resolution 15
```

---

## 4. Estimated Run Time

| Phase | Estimated duration |
|-------|--------------------|
| Download raw GeoTIFFs | 12–36 hours (internet-speed dependent) |
| Optimize GeoTIFFs | 2–6 hours (CPU-bound, uses all cores) |
| Tile generation | 4–12 hours (CPU-bound) |
| Archiving | 30–90 minutes |
| **Total** | **~24–72 hours** |

Run it on a server or leave it overnight on a workstation.

---

## 5. Output Directory Layout

```
tiles/
  1955/
    8/               ← zoom level 8
      0/
        0.webp
        1.webp
    9/
    10/
    11/
    12/
    metadata.json    ← stats (scenes, size, zoom levels, …)

us_aerials_1955.tar.gz   ← compressed archive (~5-7 GB)
download_manifest.json   ← resume checkpoint
download.log             ← full processing log
```

### metadata.json example

```json
{
  "year": 1955,
  "bbox": [-125.0, 24.0, -66.0, 49.0],
  "resolution_meters": 10,
  "zoom_levels": [8, 9, 10, 11, 12],
  "total_tiles": 456789,
  "total_size_gb": 9.2,
  "format": "webp",
  "quality": 65,
  "download_date": "2026-04-14",
  "scenes_downloaded": 1234,
  "coverage": "Continental United States"
}
```

---

## 6. Deploying Tiles to Production

### Option A — Serve from frontend public directory

Copy (or symlink) the tiles into the frontend public directory so they are
available at the path the map expects:

```bash
cp -r tiles/1955 frontend/public/tiles/1955
```

The Leaflet tile layer is already configured in `MapView.tsx` to load:

```
/tiles/1955/{z}/{x}/{y}.webp
```

### Option B — External object storage (recommended for production)

1. Upload `tiles/1955/` to an S3 bucket (or compatible CDN).
2. Update the tile URL in `frontend/src/components/MapView.tsx`:

```typescript
url="https://your-cdn.example.com/tiles/1955/{z}/{x}/{y}.webp"
```

WebP is supported by all modern browsers (Chrome, Firefox, Safari 14+, Edge).

---

## 7. Enabling the Layer in the Map

The "1955 Historical Aerials" toggle appears in the **Overlays** section of the
Layer Controls panel (left side of the map).  It is off by default.

Turning it on overlays the grayscale 1955 aerials at 70% opacity on top of the
current base map, making it easy to compare old vs modern imagery — ideal for
spotting old foundations, ghost towns, fairgrounds, and other buried structures.

---

## 8. Troubleshooting

### `gdalwarp` not found

Make sure `gdal-bin` is installed and `gdalwarp` is on your `PATH`.  
On macOS: `brew install gdal`.

### `gdal2tiles.py` not found

On some systems it is installed as `gdal2tiles` (without `.py`).  
Update the command in `_process_single_geotiff_worker()` in the script if needed.

### `cwebp` not found

Install the `webp` package:

```bash
sudo apt-get install webp     # Debian/Ubuntu
brew install webp             # macOS
```

### USGS API returns no scenes

- Double-check that your account has M2M API access enabled.
- Some grid tiles (open ocean, very remote areas) may have zero 1955 coverage.
  The script logs a warning and moves on automatically.
- Try dataset names `NHAP` or `NAPP` — coverage varies by region.

### Download interrupted / disk full

Run again with `--resume`.  The script picks up from the last completed grid
square and skips all already-downloaded files.

### Tiles look shifted or misaligned

Ensure that `gdal2tiles.py` is using the `--profile mercator` option (the
default) so tiles align with the OpenStreetMap/Google tile grid that Leaflet
expects.
