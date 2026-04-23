# Scripts

Utility scripts for data preparation and maintenance.

---

## `bake_padus_pmtiles.sh` — Bake the PAD-US land-access overlay

The land-access overlay is served as a self-hosted [PMTiles](https://protomaps.com/docs/pmtiles)
vector tile archive. Run this script **once** after cloning (and again when USGS publishes a new
PAD-US version, roughly annually).

### Prerequisites

| Platform | Command |
|----------|---------|
| macOS    | `brew install gdal tippecanoe` |
| Ubuntu   | `sudo apt install gdal-bin` + [build tippecanoe from source](https://github.com/felt/tippecanoe) |

Verify the tools are available:

```bash
ogr2ogr --version    # GDAL 3.x
tippecanoe --version # tippecanoe 2.x
curl --version
```

### Usage

```bash
# From the repo root:
bash scripts/bake_padus_pmtiles.sh
```

This produces `backend/data/padus.pmtiles` (~80–150 MB after filtering).
The file is gitignored — bake it locally and never commit it.

If the default USGS ScienceBase download URL ever drifts, override it:

```bash
PADUS_URL=https://your-mirror.example.com/PADUS4_1Combined_GDB.zip \
  bash scripts/bake_padus_pmtiles.sh
```

### What the script does

1. Downloads the PAD-US 4.1 Combined GeoPackage from USGS ScienceBase.
2. Uses `ogr2ogr` to:
   - Reproject to EPSG:4326.
   - Clip to CONUS (`-125 24 -66 50`).
   - Keep only the four columns the overlay uses: `Mang_Name`, `GAP_Sts`, `Des_Tp`, `Unit_Nm`.
   - Output as line-delimited GeoJSON (GeoJSONSeq) for tippecanoe.
3. Runs `tippecanoe` with flags tuned for compact output:
   - Zoom range 4–12 (overlay only visible at zoom ≥ 9).
   - `--drop-densest-as-needed` + `--coalesce-smallest-as-needed` to merge tiny slivers.
   - Simplification=10 to drop redundant vertices.
4. Cleans up the intermediate GeoJSONSeq.

---

## Other scripts

| Script | Purpose |
|--------|---------|
| `Ghosttownsscraper.py` | Scrape ghost town locations from GNIS / other sources |
| `Historicscraper.py` | Scrape historic sites |
| `USminesscraper.py` | Scrape US mine locations |
| `enrich_locations.py` | Enrich existing locations with additional metadata |
| `stitch_routes.py` | Convert point clusters into rendered map lines |
| `seed_badges.py` | Seed the badge definitions into the database |
| `reset_db.py` | Drop and recreate all tables (destructive!) |
