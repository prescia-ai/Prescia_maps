#!/usr/bin/env bash
# bake_padus_pmtiles.sh
#
# One-time script to download PAD-US 4.1 from USGS ScienceBase, filter it to
# the CONUS bounding box with only the columns needed by the land-access overlay,
# and bake a compact PMTiles archive at backend/data/padus.pmtiles.
#
# Usage:
#   bash scripts/bake_padus_pmtiles.sh
#
# Override the download URL if it drifts:
#   PADUS_URL=https://... bash scripts/bake_padus_pmtiles.sh
#
# Prerequisites:
#   macOS:  brew install gdal tippecanoe
#   Ubuntu: sudo apt install gdal-bin   (tippecanoe must be built from source —
#           see https://github.com/felt/tippecanoe)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# PAD-US 4.1 Combined GeoPackage from USGS ScienceBase.
# This is the Combined (Fee + Designation + Easement) CONUS layer.
# If the URL drifts, set PADUS_URL in the environment.
DEFAULT_PADUS_URL="https://www.sciencebase.gov/catalog/file/get/652d4ebbd34e44db0e2ee45c?name=PADUS4_1Combined_GDB.zip"
PADUS_URL="${PADUS_URL:-$DEFAULT_PADUS_URL}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/backend/data"
TMP_DIR="$(mktemp -d)"

OUTPUT="${DATA_DIR}/padus.pmtiles"

echo "==> Output: ${OUTPUT}"
echo "==> Temp dir: ${TMP_DIR}"

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERROR: '$1' not found."
    echo ""
    echo "Install hints:"
    echo "  macOS:  brew install gdal tippecanoe"
    echo "  Ubuntu: sudo apt install gdal-bin"
    echo "          (tippecanoe: build from source — https://github.com/felt/tippecanoe)"
    exit 1
  fi
}

check_cmd ogr2ogr
check_cmd tippecanoe
check_cmd curl

echo "==> Prerequisites OK"

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

ZIP="${TMP_DIR}/padus.zip"
echo "==> Downloading PAD-US 4.1..."
echo "    URL: ${PADUS_URL}"
curl -L --progress-bar -o "${ZIP}" "${PADUS_URL}"
echo "==> Download complete: $(du -sh "${ZIP}" | cut -f1)"

# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

echo "==> Extracting archive..."
cd "${TMP_DIR}"
unzip -q "${ZIP}"

# Find the GeoPackage (or shapefile) in the extracted content.
GPKG=$(find "${TMP_DIR}" -name "*.gpkg" | head -1)
if [ -z "${GPKG}" ]; then
  # Try GDB
  GDB=$(find "${TMP_DIR}" -name "*.gdb" -type d | head -1)
  if [ -z "${GDB}" ]; then
    echo "ERROR: Could not find a .gpkg or .gdb in the downloaded archive."
    echo "       Files found:"
    find "${TMP_DIR}" -maxdepth 3 | head -30
    exit 1
  fi
  GPKG="${GDB}"
fi
echo "==> Using source: ${GPKG}"

# ---------------------------------------------------------------------------
# Convert with ogr2ogr → GeoJSONSeq
# ---------------------------------------------------------------------------

GEOJSONSEQ="${TMP_DIR}/padus.geojsonl"

echo "==> Converting to GeoJSONSeq (CONUS only, 4 columns, EPSG:4326)..."
ogr2ogr \
  -f GeoJSONSeq \
  "${GEOJSONSEQ}" \
  "${GPKG}" \
  -t_srs EPSG:4326 \
  -clipsrc -125 24 -66 50 \
  -select "Mang_Name,GAP_Sts,Des_Tp,Unit_Nm" \
  -lco RFC7946=YES

echo "==> GeoJSONSeq size: $(du -sh "${GEOJSONSEQ}" | cut -f1)"

# ---------------------------------------------------------------------------
# Bake with tippecanoe
# ---------------------------------------------------------------------------

mkdir -p "${DATA_DIR}"

echo "==> Running tippecanoe..."
tippecanoe \
  -o "${OUTPUT}" \
  --force \
  -l padus \
  -z 12 -Z 4 \
  --drop-densest-as-needed \
  --coalesce-smallest-as-needed \
  --extend-zooms-if-still-dropping \
  --no-tile-size-limit \
  --simplification=10 \
  "${GEOJSONSEQ}"

# ---------------------------------------------------------------------------
# Cleanup & report
# ---------------------------------------------------------------------------

echo "==> Cleaning up temp files..."
rm -rf "${TMP_DIR}"

FINAL_SIZE=$(du -sh "${OUTPUT}" | cut -f1)
echo ""
echo "✅  Done!"
echo "    ${OUTPUT}  (${FINAL_SIZE})"
echo ""
echo "The file is gitignored. Commit the bake script but not the .pmtiles file."
echo "Re-bake annually when USGS publishes a new PAD-US version."
