# Code Review Summary — 2025-09-09

This review focuses on correctness, modularity, PEP 8/typing compliance, and alignment between layers (scrapers/collectors, domain models, DB services, API). I added inline TODO comments to the most relevant files. Below is a high-level summary and prioritized action list.

## Critical Issues (Fix First)

1) SportsDataApp wiring is broken
- Problem: `self.data_orchestrator` is referenced but never initialized (class import/instantiation commented out).
- Impact: Data collection paths and status endpoints will raise AttributeError.
- Action: Re-introduce a DataCollectionOrchestrator or refactor to rely solely on `ScrapingOrchestrator`. Update all references in `SportsDataApp`.
- Files: src/apps/sports_data_app.py (TODOs added)

2) Inconsistent/invalid imports and entrypoints
- src/api/app.py imports `DataCollectionOrchestrator` from a non-existent module.
- Duplicate/overlapping bootstrap logic with src/api/main.py.
- Action: Remove or deprecate src/api/app.py and standardize on src/api/main.py. Guard optional scrapers with feature flags.
- Files: src/api/app.py, src/api/main.py (TODOs added)

3) Domain model vs collector mismatches
- FootballDataCollector uses fields not present in Pydantic models (e.g., external_id/short_name/city) and relies on undefined `self.session` and `self.logger`.
- Action: Introduce an async HTTP client for collectors and map fields properly to `src/domain/models.py`.
- Files: src/data_collection/collectors/football_data_api_collector.py (TODOs added)

4) Scraper/Collector class architecture mismatch
- TransfermarktScraper extends DataCollector but is registered in ScrapingOrchestrator (expects BaseScraper). Logger usage without definition.
- Action: Refactor TransfermarktScraper to extend BaseScraper (or register it via a collector orchestrator if one exists).
- Files: src/data_collection/scrapers/transfermarkt_scraper.py (TODOs)

5) DB schema vs service SQL mismatches
- Services reference columns like `external_id` in tables `matches`/`clubs`, but the SQLAlchemy schema uses `external_ids` JSON and different structures.
- Action: Align `database/services/*` SQL with actual schema or provide dedicated ingestion tables (live_scores/odds) only.
- Files: src/database/services/matches.py, src/database/services/odds.py, src/data_collection/scrapers/fbref_scraper.py (TODOs)

## High-Value Fixes

- Domain models bug
  - Fixed `isinstance(val, int | float)` to `isinstance(val, (int, float))` in `Club.coerce_stats_numbers`.
  - Additional TODO to soften coercion for partial/None values.

- Import path consistency for CLI scrapers
  - Switched `common.http` to `src.common.http` in `fbref_season_scraper.py` and `premierleague_scraper.py`. Added TODO to align playwright utils import.

- RateLimiter semantics
  - Current semaphore approach limits concurrency, not rate. Add a token-bucket-style limiter in `collectors/base.py`.

## Consistency and Cleanliness

- Duplicate imports and potentially missing modules in `api/main.py`: TODOs to streamline imports and guard optional scrapers with feature flags to prevent ImportError on startup.

- ScrapingOrchestrator routing is hard-coded to "transfermarkt", "flashscore", "odds".
  - TODO: Make routing configurable in Settings and support additional scrapers like "fbref" or "courtside1891".

- Logging
  - Several classes reference `self.logger` without defining it. Add standard logger initialization in base classes.

## Typing & Docstrings

- Added TODOs to ensure functions and abstract methods include parameter and return descriptions and type hints where missing (per your standards).
- Suggested model extensions (e.g., external_ids, source_url) for better cross-layer alignment.

## Suggested Next Steps (in order)

1) Wire-up and de-duplicate application bootstrap
   - Decide on a single entrypoint (src/api/main.py) and remove src/api/app.py.
   - Fix SportsDataApp by either reintroducing a proper DataCollectionOrchestrator or refactoring to only use ScrapingOrchestrator.
   - Put optional scrapers behind Settings flags to avoid startup errors in minimal environments.

2) Fix collectors/scrapers
   - FootballDataCollector: add async HTTP client; align with domain models.
   - TransfermarktScraper: inherit BaseScraper or adjust orchestrator usage.
   - Normalize naming in services (home/away vs home_team_name/away_team_name).

3) DB services alignment
   - Confirm actual tables/columns for matches/clubs. If `live_scores` and `odds` are the ingestion outputs, keep services focused there and remove direct `matches/clubs` accesses or implement via ORM.

4) QA and Tests
   - Add integration tests for orchestration paths (SAFE_MODE on/off).
   - Add unit tests for parsing/coercion (Club.stats), and service normalization.

5) Tooling
   - Add ruff/black/mypy to CI; run against src/.

## Quick Commands

- Run API in SAFE_MODE to validate startup without external deps:
  - FASTAPI_SAFE_MODE=1 uvicorn src.api.main:app --reload

- Mypy type-check (example):
  - mypy src/domain src/api src/data_collection --ignore-missing-imports

---

If you want, I can follow up with a PR to:
- Remove/deprecate src/api/app.py
- Patch SportsDataApp to remove the broken data_orchestrator references
- Add basic httpx client and logging to FootballDataCollector
- Normalize database service field names