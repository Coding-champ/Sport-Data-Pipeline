# Sport Data Pipeline

Python-only sports data pipeline with data collection, analytics, and a FastAPI server.

## Metrics & Monitoring

- Prometheus metrics server is started once from `main.py` if `ENABLE_METRICS=true`.
- Default port: `METRICS_PORT` (default `8008`).
- Example: visit `http://localhost:8008/metrics`.

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
