#!/usr/bin/env bash
# download_padus_pmtiles.sh
#
# Downloads the latest pre-baked padus.pmtiles from the project's GitHub
# Releases into backend/data/.
#
# Usage:
#   bash scripts/download_padus_pmtiles.sh
#
# Optional: set GITHUB_TOKEN to avoid unauthenticated rate limits (60 req/hr).
#   export GITHUB_TOKEN=ghp_...
#   bash scripts/download_padus_pmtiles.sh
#
# Prerequisites: curl, jq
#   macOS:  brew install jq
#   Ubuntu: sudo apt install jq

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO="prescia-ai/Prescia_maps"
ASSET="padus.pmtiles"
API_BASE="https://api.github.com/repos/${REPO}"

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------
if ! command -v curl &>/dev/null; then
  echo "ERROR: 'curl' is not installed." >&2
  echo "  macOS:  it ships with the OS; if missing: brew install curl" >&2
  echo "  Ubuntu: sudo apt install curl" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: 'jq' is not installed." >&2
  echo "  macOS:  brew install jq" >&2
  echo "  Ubuntu: sudo apt install jq" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Auth header (optional)
# ---------------------------------------------------------------------------
AUTH_HEADER=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH_HEADER="Authorization: Bearer ${GITHUB_TOKEN}"
fi

# ---------------------------------------------------------------------------
# Helper: call GitHub API
# ---------------------------------------------------------------------------
gh_api() {
  local url="$1"
  local http_code
  local response

  if [ -n "${AUTH_HEADER}" ]; then
    response=$(curl -fsSL -w "\n%{http_code}" -H "${AUTH_HEADER}" -H "User-Agent: download_padus_pmtiles.sh" "${url}" 2>&1) || true
  else
    response=$(curl -fsSL -w "\n%{http_code}" -H "User-Agent: download_padus_pmtiles.sh" "${url}" 2>&1) || true
  fi

  http_code=$(echo "${response}" | tail -1)
  body=$(echo "${response}" | head -n -1)

  if [ "${http_code}" = "403" ]; then
    echo "ERROR: GitHub API rate limit exceeded (HTTP 403)." >&2
    echo "       Set GITHUB_TOKEN to a personal access token and try again." >&2
    exit 1
  fi

  if [ "${http_code}" = "404" ]; then
    echo "ERROR: GitHub API returned 404 for ${url}." >&2
    echo "       The repository or release may not exist yet." >&2
    exit 1
  fi

  if [ "${http_code}" != "200" ]; then
    echo "ERROR: GitHub API returned HTTP ${http_code} for ${url}." >&2
    exit 1
  fi

  echo "${body}"
}

# ---------------------------------------------------------------------------
# Find the latest padus-* release
# ---------------------------------------------------------------------------
echo "==> Checking GitHub Releases for ${REPO} ..."

RELEASE=""

# First try /releases/latest — cheap single call.
LATEST=$(gh_api "${API_BASE}/releases/latest")
LATEST_TAG=$(echo "${LATEST}" | jq -r '.tag_name // ""')

if [[ "${LATEST_TAG}" == padus-* ]]; then
  RELEASE="${LATEST}"
fi

# If latest is a non-padus release, page through /releases to find the first
# padus-* one.
if [ -z "${RELEASE}" ]; then
  echo "    Latest release is '${LATEST_TAG}' — searching for a padus-* release..."
  PAGE=1
  while true; do
    PAGE_DATA=$(gh_api "${API_BASE}/releases?per_page=100&page=${PAGE}")
    COUNT=$(echo "${PAGE_DATA}" | jq 'length')
    if [ "${COUNT}" -eq 0 ]; then
      break
    fi
    MATCH=$(echo "${PAGE_DATA}" | jq -c 'map(select(.tag_name | startswith("padus-"))) | first // empty')
    if [ -n "${MATCH}" ]; then
      RELEASE="${MATCH}"
      break
    fi
    PAGE=$((PAGE + 1))
  done
fi

if [ -z "${RELEASE}" ]; then
  cat >&2 <<EOF
ERROR: No padus-* release found in ${REPO}.

The pre-baked file has not been published yet. A project maintainer needs to
trigger the "Bake PAD-US PMTiles" workflow from the Actions tab, or you can
bake the file locally:

    bash scripts/bake_padus_pmtiles.sh   # requires GDAL + tippecanoe

EOF
  exit 1
fi

RELEASE_TAG=$(echo "${RELEASE}" | jq -r '.tag_name')
echo "    Found release: ${RELEASE_TAG}"

# ---------------------------------------------------------------------------
# Find the padus.pmtiles asset in the release
# ---------------------------------------------------------------------------
DOWNLOAD_URL=$(echo "${RELEASE}" | jq -r --arg name "${ASSET}" '.assets[] | select(.name == $name) | .browser_download_url // empty' | head -1)

if [ -z "${DOWNLOAD_URL}" ]; then
  cat >&2 <<EOF
ERROR: Release '${RELEASE_TAG}' does not contain an asset named '${ASSET}'.

This should not happen for a properly-baked release. Check the Actions run
that produced this release for errors, or ask a maintainer to re-run the
"Bake PAD-US PMTiles" workflow.
EOF
  exit 1
fi

echo "    Asset URL: ${DOWNLOAD_URL}"

# ---------------------------------------------------------------------------
# Determine target path
# ---------------------------------------------------------------------------
# The script lives at <repo>/scripts/download_padus_pmtiles.sh
# Parent of parent of the script = repo root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/backend/data"
TARGET="${DATA_DIR}/${ASSET}"

# Create backend/data/ if it doesn't exist.
if [ ! -d "${DATA_DIR}" ]; then
  echo "==> Creating directory: ${DATA_DIR}"
  mkdir -p "${DATA_DIR}" || {
    echo "ERROR: Cannot create directory '${DATA_DIR}'." >&2
    echo "       Check that you have write permission to the backend/data/ folder." >&2
    exit 1
  }
fi

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
echo "==> Downloading ${ASSET} to ${TARGET} ..."
echo "    (this may take a few minutes — the file is ~100 MB)"

CURL_ARGS=(-L --progress-bar -o "${TARGET}")
if [ -n "${AUTH_HEADER}" ]; then
  CURL_ARGS+=(-H "${AUTH_HEADER}")
fi

if ! curl "${CURL_ARGS[@]}" "${DOWNLOAD_URL}"; then
  echo "" >&2
  echo "ERROR: Download failed." >&2
  echo "       Check your internet connection and try again." >&2
  # Remove partial file if it exists.
  [ -f "${TARGET}" ] && rm -f "${TARGET}"
  exit 1
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
SIZE_BYTES=$(wc -c < "${TARGET}" | tr -d ' ')
SIZE_MB=$(awk "BEGIN {printf \"%.1f\", ${SIZE_BYTES}/1048576}")

echo ""
echo "✅  Done!"
echo "    File : ${TARGET}"
echo "    Size : ${SIZE_MB} MB"
echo ""
echo "Restart the backend to pick up the new file."
