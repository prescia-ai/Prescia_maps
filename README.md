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

# 3. Load seed datasets (in a second terminal)
docker compose exec backend python /scripts/load_datasets.py

# 4. Open the API docs
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

### Load seed datasets (trails, battles, forts, mines)

```bash
# From project root
python scripts/load_datasets.py
```

Inserts approximately 60 pre-defined historical locations and 4 linear features (Oregon Trail, Trail of Tears, Santa Fe Trail, Transcontinental Railroad) directly from hardcoded coordinates — no external files required.

### Scrape Wikipedia

```bash
# From project root
python scripts/scrape_wikipedia.py
```

Fetches Civil War battle lists, ghost town lists, and other historical Wikipedia pages. Geocodes any records missing coordinates via Nominatim, then inserts them into the database.

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

`battle` · `camp` · `railroad_stop` · `trail` · `town` · `mine` · `structure` · `event`

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
| `SCORE_SEARCH_RADIUS_KM` | `10.0` | Default radius for scoring queries |
| `SCRAPER_TIMEOUT` | `30.0` | HTTP timeout for Wikipedia scraper (seconds) |

---

## Screenshots

> *(Coming soon — map view with heatmap overlay and scoring panel)*

---

## License

MIT