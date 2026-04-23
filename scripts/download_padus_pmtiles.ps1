#Requires -Version 5.1
<#
.SYNOPSIS
    Downloads the latest pre-baked padus.pmtiles from the project's GitHub Releases.

.DESCRIPTION
    Fetches the most recent release tagged padus-* from the prescia-ai/Prescia_maps
    repository and downloads the padus.pmtiles asset into backend/data/.

    No GDAL, tippecanoe, WSL, or Docker required.

.EXAMPLE
    # From the repo root:
    ./scripts/download_padus_pmtiles.ps1

    # With a GitHub token to avoid rate limits:
    $env:GITHUB_TOKEN = "ghp_..."
    ./scripts/download_padus_pmtiles.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
$Repo    = "prescia-ai/Prescia_maps"
$Asset   = "padus.pmtiles"
$ApiBase = "https://api.github.com/repos/$Repo"

# ---------------------------------------------------------------------------
# Optional auth header (avoids 60 req/hr unauthenticated rate limit)
# ---------------------------------------------------------------------------
$Headers = @{ "User-Agent" = "download_padus_pmtiles.ps1" }
if ($env:GITHUB_TOKEN) {
    $Headers["Authorization"] = "Bearer $env:GITHUB_TOKEN"
}

# ---------------------------------------------------------------------------
# Helper: invoke GitHub API with friendly error messages
# ---------------------------------------------------------------------------
function Invoke-GitHubApi {
    param([string]$Uri)
    try {
        return Invoke-RestMethod -Uri $Uri -Headers $Headers -UseBasicParsing
    }
    catch [System.Net.WebException] {
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -eq 403) {
            Write-Error "GitHub API rate limit exceeded (HTTP 403). Set `$env:GITHUB_TOKEN to a personal access token and try again."
        }
        elseif ($status -eq 404) {
            Write-Error "GitHub API returned 404 for $Uri — the repository or release may not exist yet."
        }
        else {
            Write-Error "Network error calling GitHub API ($Uri): $_"
        }
        exit 1
    }
    catch {
        Write-Error "Unexpected error calling GitHub API ($Uri): $_"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Find the latest padus-* release
# ---------------------------------------------------------------------------
Write-Host "==> Checking GitHub Releases for $Repo ..."

$release = $null

# First try /releases/latest — cheap single call.
$latest = Invoke-GitHubApi "$ApiBase/releases/latest"
if ($latest.tag_name -like "padus-*") {
    $release = $latest
}

# If latest is a non-padus release, page through /releases to find the first
# one whose tag starts with padus-.
if (-not $release) {
    Write-Host "    Latest release is '$($latest.tag_name)' — searching for a padus-* release..."
    $page = 1
    while ($true) {
        $releases = Invoke-GitHubApi "$ApiBase/releases?per_page=100&page=$page"
        if ($releases.Count -eq 0) { break }
        foreach ($r in $releases) {
            if ($r.tag_name -like "padus-*") {
                $release = $r
                break
            }
        }
        if ($release) { break }
        $page++
    }
}

if (-not $release) {
    Write-Error @"
No padus-* release found in $Repo.

The pre-baked file has not been published yet. A project maintainer needs to
trigger the "Bake PAD-US PMTiles" workflow from the Actions tab, or you can
bake the file locally:

    bash scripts/bake_padus_pmtiles.sh   # requires GDAL + tippecanoe (Linux/macOS/WSL2)
"@
    exit 1
}

Write-Host "    Found release: $($release.tag_name)"

# ---------------------------------------------------------------------------
# Find the padus.pmtiles asset in the release
# ---------------------------------------------------------------------------
$assetObj = $release.assets | Where-Object { $_.name -eq $Asset } | Select-Object -First 1

if (-not $assetObj) {
    Write-Error @"
Release '$($release.tag_name)' does not contain an asset named '$Asset'.

This should not happen for a properly-baked release. Check the Actions run
that produced this release for errors, or ask a maintainer to re-run the
"Bake PAD-US PMTiles" workflow.
"@
    exit 1
}

$DownloadUrl = $assetObj.browser_download_url
Write-Host "    Asset URL: $DownloadUrl"

# ---------------------------------------------------------------------------
# Determine target path
# ---------------------------------------------------------------------------
# The script lives at <repo>/scripts/download_padus_pmtiles.ps1
# Parent of parent of the script = repo root.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$DataDir   = Join-Path $RepoRoot "backend\data"
$Target    = Join-Path $DataDir $Asset

# Create backend/data/ if it doesn't exist.
if (-not (Test-Path $DataDir)) {
    Write-Host "==> Creating directory: $DataDir"
    try {
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    }
    catch {
        Write-Error "Cannot create directory '$DataDir': $_`nCheck that you have write permission to the backend/data/ folder."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
Write-Host "==> Downloading $Asset to $Target ..."
Write-Host "    (this may take a few minutes — the file is ~100 MB)"

try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $Target -UseBasicParsing -Headers $Headers
}
catch [System.Net.WebException] {
    Write-Error "Network error downloading $Asset`: $_`nCheck your internet connection and try again."
    exit 1
}
catch [System.UnauthorizedAccessException] {
    Write-Error "Write permission denied for '$Target'.`nRun PowerShell as Administrator or check folder permissions."
    exit 1
}
catch {
    Write-Error "Unexpected error downloading $Asset`: $_"
    exit 1
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
$SizeBytes = (Get-Item $Target).Length
$SizeMB    = [math]::Round($SizeBytes / 1MB, 1)

Write-Host ""
Write-Host "✅  Done!"
Write-Host "    File : $Target"
Write-Host "    Size : ${SizeMB} MB"
Write-Host ""
Write-Host "Restart the backend to pick up the new file."
