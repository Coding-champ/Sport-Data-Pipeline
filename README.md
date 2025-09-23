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

## Courtside Debug & Analysis CLI

Mehrere frühere separate Debug/Analyse Skripte für Courtside1891 wurden zu einem einzigen Tool vereinheitlicht: `scripts/courtside_debug.py`.

Modi (`--mode`):

- `minimal`  – schneller Reachability-Check (Screenshot + HTML Dump)
- `fixtures` – extrahiert strukturierte Fixture Daten (JSON Ausgabe mit `--json`)
- `analyze`  – tiefe Analyse (Container, Ressourcen, Test-ID Sample, Fixture Sample) → schreibt JSON Report
- `inspect`  – leichte Inspektion (erste `data-testid` Elemente + Selektor Counts)
- `snapshot` – nur Screenshot + HTML nach vollständigem Laden (networkidle)
- `raw`      – reiner HTML Dump

Beispiele:

```bash
python scripts/courtside_debug.py --mode minimal --headless
python scripts/courtside_debug.py --mode fixtures --json > fixtures.json
python scripts/courtside_debug.py --mode analyze --out-dir reports/courtside
```

Ausgabe Verzeichnis (default): `reports/courtside`.

Optionen:

- `--wait-selector` (default `[data-testid="fixture-row"]`) – optionales Warten auf primäres Content-Element
- `--viewport 1920x1080` – Anpassung der Auflösung (oder `--viewport none` für default)
- `--headless` – Headless Browser
- `--json` – Rohdaten JSON (für `fixtures`, `minimal`, `inspect`, `analyze` Zusammenfassungen)

Die alten Skripte (`analyze_page.py`, `inspect_page.py`, `courtside_minimal_test.py`, `courtside_standalone_test.py`, `debug_courtside.py`) wurden entfernt.

## Unified Scraper CLI

Mehrere einzelne Runner (`run_bundesliga_club_scraper.py`, `scrape_bundesliga_clubs.py`, `run_flashscore_once.py`, `run_courtside_scrape_preview.py`, `preview_transfermarkt_injuries_min.py`) wurden zusammengeführt in: `scripts/run_scraper.py`.

Quellen (`--source`):

- `bundesliga_overview`  – nur Club-Übersichten (zuvor `scrape_bundesliga_clubs.py`)
- `bundesliga_deep`      – Clubs + Squads + Player Details (zuvor `run_bundesliga_club_scraper.py`)
- `flashscore_once`      – orchestrierter Flashscore Run
- `courtside_preview`    – Courtside Fixtures Preview (leichtgewichtiger Dump)
- `tm_injuries`          – Transfermarkt Verletzungen (JSON)
- `tm_injuries_csv`      – Transfermarkt Verletzungen (CSV direkt auf stdout oder `--out`)

Globale Optionen:

- `--out PATH`          – JSON Output-Datei (CSV bei `*_csv` Quellmodus)
- `--limit N`           – generisches Limit (Clubs / Fixtures / Items abhängig vom Modus)
- `--limit-players N`   – Limit Spieler pro Club (nur `bundesliga_deep`)
- `--club-id ID`        – Transfermarkt Club-ID (Default 27)
- `--verbose`           – mehr Logging

Beispiele:

```bash
python scripts/run_scraper.py --source bundesliga_overview --out reports/bundesliga_clubs.json
python scripts/run_scraper.py --source bundesliga_deep --limit 3 --limit-players 5 --out reports/bundesliga_deep.json
python scripts/run_scraper.py --source flashscore_once
python scripts/run_scraper.py --source courtside_preview --limit 5 --out reports/courtside/preview.json
python scripts/run_scraper.py --source tm_injuries --club-id 27 --out reports/tm_injuries.json
python scripts/run_scraper.py --source tm_injuries_csv --club-id 27 > injuries.csv
```

Entfernte Skripte: `run_bundesliga_club_scraper.py`, `scrape_bundesliga_clubs.py`, `run_flashscore_once.py`, `run_courtside_scrape_preview.py`, `preview_transfermarkt_injuries_min.py`.

## Zentrales Logging

Zentrale Utilities: `src/common/logging_utils.py`

Environment Variablen:

- `LOG_LEVEL` (Default: `INFO`) – z.B. `DEBUG`, `WARNING`.
- `LOG_FORMAT` (`console` | `json`, Default: `console`).
- `LOG_NO_COLOR=1` – deaktiviert Farben im Konsolenformat.
- `LOG_TIMEZONE` (`local` | `utc`, Default: `local`).

Verwendung:

```python
from src.common.logging_utils import configure_logging, get_logger

configure_logging(service="scraper")  # idempotent
logger = get_logger(__name__)
logger.info("Starting job", extra={"job": "flashscore_batch"})
```

JSON Beispiel (`LOG_FORMAT=json`):

```json
{"ts": "2025-09-23T19:20:11.123456+02:00", "level": "INFO", "logger": "scripts.run_scraper", "message": "Starting scraper", "service": "scraper"}
```

Lokale Entwicklung (verbose):

```bash
export LOG_LEVEL=DEBUG
python scripts/run_scraper.py --source bundesliga_overview --limit 2
```

Batch/Prod (strukturierte Logs):

```bash
LOG_FORMAT=json LOG_LEVEL=INFO python scripts/run_scraper.py --source flashscore_once > logs/flashscore.jsonl
```

Alle konsolidierten Skripte nutzen bereits dieses zentrale Logging.
