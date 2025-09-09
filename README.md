# Sport Data Pipeline

Python-only sports data pipeline with data collection, analytics, and a FastAPI server.

## Quick start

Install Python dependencies:

- `pip install -r requirements.txt`

Run the pipeline (defaults to interactive mode):

- `python main.py`

## Run modes

Configure via environment variable `RUN_MODE` or `Settings.run_mode`:

- `interactive`: CLI menu inside the process.
- `api_only`: start FastAPI only.
- `collection_once`: run one data collection cycle and exit.
- `analytics_once`: run daily analytics routine once and exit.
- `full_service`: start API and background schedulers.

## API

Host/port:

- `API_HOST` (default `0.0.0.0`), `API_PORT` (default `8000`)

Useful endpoints:

- Health: `GET /health`
- Docs: `GET /docs`
- Metrics proxy: see Metrics below

Routers are aggregated under `/api/v1`.

## Configuration

All settings are defined in `src/core/config.py` (Pydantic BaseSettings) and can be overridden via environment variables. Key variables:

- `DATABASE_URL`: Postgres DSN (supports `postgresql+asyncpg://...`).
- `ENABLE_API`, `ENABLE_DATA_COLLECTION`, `ENABLE_ANALYTICS` (true/false)
- `ENABLE_MONITORING`, `ENABLE_METRICS`, `METRICS_PORT`
- `ENVIRONMENT`: `development` | `staging` | `production`
- `CORS_ORIGINS`: JSON list (e.g. `["https://example.com"]`). `*` allowed only in development.
- `API_KEY`: optional; if set and `ENVIRONMENT != development`, `/health` requires header `x-api-key`.
- `RATE_LIMIT_REQUESTS_PER_MINUTE`: per-IP rate limit (0 disables)

Scraping/Scheduling intervals are configurable in settings (e.g., `live_update_interval_seconds`).

## Metrics & Monitoring

- Prometheus metrics server is started once from `main.py` if `ENABLE_METRICS=true`.
- Default port: `METRICS_PORT` (default `8008`).
- Example: visit `http://localhost:8008/metrics`.

## Database diagnostics

Use the unified script to validate connectivity and basic queries:

```bash
python -m scripts.db_diagnostics
```

It checks both sync and async connections derived from `DATABASE_URL`.

## Development

Tests:

- `pytest`

Linting:

- follow the repository style; CI checks can be added (see TODO)

## Repository layout

- `src/` – application source
  - `api/` – FastAPI app and endpoints
  - `apps/` – orchestration apps (data, analytics)
  - `core/` – configuration and base utilities
  - `data_collection/` – scrapers and scheduler
  - `database/` – DB manager, schema, services
  - `monitoring/` – metrics and health checks
- `scripts/` – operational scripts (`db_diagnostics.py`)
- `tests/` – unit/integration tests and fixtures
