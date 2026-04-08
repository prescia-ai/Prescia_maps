# Prescia Maps — Historical Activity Mapping & Metal Detecting Intelligence

An interactive mapping system that aggregates historical location data (Civil War battles, ghost towns, historic trails, mines, forts) and computes interest scores to assist metal-detecting research.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Leaflet / react-leaflet |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2 (async), asyncpg |
| **Database** | PostgreSQL 16 + PostGIS 3.4 |
| **Containerisation** | Docker, Docker Compose |
| **Data scraping** | httpx, BeautifulSoup4, Nominatim (geopy) |

---

## Quick Start (Docker)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/install/) v2

```bash
# 1. Clone the repository
git clone https://github.com/your-org/Prescia_maps.git
cd Prescia_maps

# 2. Start all services (database + backend)
docker compose up --build

# 3. Import data (in a second terminal — run one or more scrapers)
docker compose exec backend python /scripts/USminesscraper.py --limit 1000
docker compose exec backend python /scripts/Ghosttownsscraper.py --gnis-only --limit 1000
docker compose exec backend python /scripts/Historicscraper.py --skip-ohm --limit 1000

# 4. Stitch routes — turns point clusters into rendered map lines
docker compose exec backend python /scripts/stitch_routes.py

# 5. Open the API docs
open http://localhost:8000/docs
```

---

## Local Development Setup

### Backend

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy and configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env → set DATABASE_URL to your local PostgreSQL instance

# Start a local PostGIS instance (or use Docker just for the DB)
docker compose up db -d

# Run the development server
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # Starts Vite dev server on http://localhost:5173
```

---

## Populating Data

The database is populated by three purpose-built scrapers that each own a single domain of historical data. Each scraper downloads bulk authoritative datasets, deduplicates records, and inserts them with proper geometry and confidence scoring.

### 1. US Mines — `USminesscraper.py`

```bash
# Full import (downloads USGS MRDS bulk CSV — 800,000+ mine sites)
python scripts/USminesscraper.py

# Filter by state
python scripts/USminesscraper.py --state CO

# Limit records (useful for testing)
python scripts/USminesscraper.py --limit 1000

# Dry-run: parse without inserting
python scripts/USminesscraper.py --dry-run
```

Downloads the USGS Mineral Resources Data System (MRDS) bulk CSV and imports mine site records with coordinates, commodity tags, and status. Replaces all previous mine-related data sources.

### 2. Ghost Towns & Abandoned Places — `Ghosttownsscraper.py`

```bash
# Full import (GNIS + web sources)
python scripts/Ghosttownsscraper.py

# GNIS only (skip web scraping)
python scripts/Ghosttownsscraper.py --gnis-only

# Filter by state
python scripts/Ghosttownsscraper.py --state CO

# Limit records
python scripts/Ghosttownsscraper.py --limit 5000
```

Downloads the USGS GNIS National File and scrapes Legends of America and ghosttowns.com for ghost towns, churches, cemeteries, schools, springs, camps, and other abandoned places. Replaces all previous ghost town and GNIS data sources.

### 3. Historic Places, Routes & Features — `Historicscraper.py`

```bash
# Full import (NRHP + NPS + OpenHistoricalMap)
python scripts/Historicscraper.py

# Skip NPS (if no API key)
python scripts/Historicscraper.py --skip-nps

# Skip OpenHistoricalMap
python scripts/Historicscraper.py --skip-ohm

# Specific state
python scripts/Historicscraper.py --state TX

# Dry-run
python scripts/Historicscraper.py --dry-run
```

Imports from the National Register of Historic Places (NRHP), NPS API (requires `NPS_API_KEY`), and OpenHistoricalMap Overpass API. Handles both point features (battles, forts, stations) and linear features (abandoned railways, historic trails). Replaces all previous NRHP, NPS, and Wikipedia battle/trail/fort data sources.

### 4. Route Stitcher — `stitch_routes.py`

Run **after** the three scrapers to convert point-stop clusters into rendered route lines.

```bash
# Full run (NPS trail geometry + stitch from point clusters)
python scripts/stitch_routes.py

# Preview what would be created (no DB writes)
python scripts/stitch_routes.py --dry-run

# Skip NPS National Trails download (only stitch from DB points)
python scripts/stitch_routes.py --skip-nps-trails

# Require at least 5 stops to form a route
python scripts/stitch_routes.py --min-points 5
```

Downloads actual polyline geometry for National Historic Trails from the NPS ArcGIS open-data portal, then groups existing `Location` point records by route-name pattern (Pony Express, Butterfield Overland Mail, Oregon/Santa Fe/Mormon/California Trails, named railroads, etc.) and stitches them into `LinearFeature` LINESTRING records using nearest-neighbour geographic ordering. The result is that named routes appear as **lines** on the map with their individual stops as **dots**.

### Post-import enrichment

```bash
# Enrich records with Wikipedia descriptions, corrected types, and years
python scripts/enrich_locations.py

# Reclassify location types using source-label-first logic
python scripts/reclassify.py
```

All scrapers support crash-safe checkpointing (`--checkpoint`, `--fresh`) and can resume interrupted imports.

---

## API Endpoints

All routes are prefixed with `/api/v1`. Interactive docs: `http://localhost:8000/docs`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness / database connectivity probe |
| `GET` | `/locations` | All point locations as GeoJSON FeatureCollection |
| `GET` | `/locations?type=battle` | Filter by location type |
| `GET` | `/locations?min_confidence=0.8` | Filter by confidence threshold |
| `POST` | `/locations` | Insert a new historical location |
| `GET` | `/features` | All linear features (trails, railroads) as GeoJSON |
| `GET` | `/features?type=trail` | Filter linear features by type |
| `GET` | `/heatmap` | Weighted density array for heatmap overlay |
| `GET` | `/score?lat=39.81&lon=-77.22` | Metal-detecting interest score for a coordinate |
| `GET` | `/score?lat=…&lon=…&radius_km=5` | Score with custom search radius |
| `POST` | `/scrape` | Trigger a live Wikipedia scrape (admin) |

### Location types

`battle` · `camp` · `railroad_stop` · `trail` · `town` · `mine` · `structure` · `event` · `church` · `school` · `cemetery` · `fairground` · `ferry` · `stagecoach_stop` · `spring` · `locale`

### Score response

```json
{
  "lat": 39.81,
  "lon": -77.22,
  "score": 87.4,
  "breakdown": { "battle": 60, "proximity_bonus": 15, "age_bonus": 12.4 },
  "nearby_count": 3
}
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5432/prescia_maps` | Async SQLAlchemy connection string |
| `MAPBOX_TOKEN` | *(empty)* | Optional Mapbox token for tile layers |
| `NPS_API_KEY` | *(empty)* | API key for the NPS developer API ([get one free](https://www.nps.gov/subjects/developer/get-started.htm)) |
| `SCORE_SEARCH_RADIUS_KM` | `10.0` | Default radius for scoring queries |
| `SCRAPER_TIMEOUT` | `30.0` | HTTP timeout for Wikipedia scraper (seconds) |

---

## Screenshots

> *(Coming soon — map view with heatmap overlay and scoring panel)*

---

## License

MIT