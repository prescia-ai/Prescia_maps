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
# Optional environment variable overrides:
#   PADUS_URL       — Skip JSON resolution and download from this URL directly.
#   PADUS_ITEM_ID   — ScienceBase item ID (default: 652d4ebbd34e44db0e2ee45c).
#   PADUS_FILE_NAME — Filename to match in the ScienceBase files list
#                     (default: PADUS4_1Combined_GDB.zip).
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
# Resolved at runtime from the ScienceBase item JSON API.
# Override with PADUS_URL to bypass resolution entirely.
PADUS_ITEM_ID="${PADUS_ITEM_ID:-652d4ebbd34e44db0e2ee45c}"
PADUS_FILE_NAME="${PADUS_FILE_NAME:-PADUS4_1Combined_GDB.zip}"

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
check_cmd python3

echo "==> Prerequisites OK"

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

ZIP="${TMP_DIR}/padus.zip"

if [ -n "${PADUS_URL:-}" ]; then
  RESOLVED_URL="${PADUS_URL}"
  echo "==> Using PADUS_URL override: ${RESOLVED_URL}"
else
  echo "==> Resolving ScienceBase download URL for ${PADUS_FILE_NAME}..."
  ITEM_JSON_URL="https://www.sciencebase.gov/catalog/item/${PADUS_ITEM_ID}?format=json&fields=files,webLinks"
  RESOLVED_URL=$(curl -fsSL "${ITEM_JSON_URL}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = '${PADUS_FILE_NAME}'
for f in data.get('files', []) or []:
    if f.get('name') == target and f.get('downloadUri'):
        print(f['downloadUri']); sys.exit(0)
for w in data.get('webLinks', []) or []:
    uri = w.get('uri', '')
    if uri.endswith(target) or ('name=' + target) in uri:
        print(uri); sys.exit(0)
print('Could not find ' + target + ' in ScienceBase item ${PADUS_ITEM_ID}', file=sys.stderr); sys.exit(1)
")
fi

echo "==> Downloading PAD-US 4.1..."
echo "    URL: ${RESOLVED_URL}"
curl -L --fail --progress-bar -o "${ZIP}" "${RESOLVED_URL}"

SIZE_BYTES=$(stat -c%s "${ZIP}" 2>/dev/null || stat -f%z "${ZIP}" 2>/dev/null)
if [ -z "${SIZE_BYTES}" ]; then
  echo "ERROR: Could not determine size of downloaded file: ${ZIP}"
  exit 1
fi
if [ "${SIZE_BYTES}" -lt 10000000 ]; then
  echo "ERROR: Downloaded file is only ${SIZE_BYTES} bytes — ScienceBase likely returned an HTML page."
  echo "       First 200 bytes of response:"
  head -c 200 "${ZIP}"; echo
  exit 1
fi
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
