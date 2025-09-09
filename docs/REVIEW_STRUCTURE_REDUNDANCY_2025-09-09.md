# Structural & Redundancy Review (2025-09-09)

Scope: src/common, src/data_collection/scrapers, src/database/services, src/api, src/apps

Summary
- The codebase shows solid modular direction (shared http and parsing utils, orchestrators, DTOs).
- Main structural gaps: duplicated HTTP/UA logic, dual implementations of infinite scroll, scraper/collector class mismatch, and DB-service vs schema mismatch.
- Introduced TODOs in files to guide refactors with minimal churn.

Redundancy Highlights
- HTTP fetching logic duplicated:
  - Duplicate fetch_html and UA/header pools in src/data_collection/scrapers/fbref_match_scraper.py versus src/common/http.py.
  - TODOs added to refactor scrapers to import from src.common.http.
- Playwright infinite scroll:
  - courtside_scraper implements a local _infinite_scroll while already importing infinite_scroll from src.common.playwright_utils.
  - TODO to standardize on shared utility.
- Parsing helpers:
  - fbref_match_scraper implements _to_number-style parsing heuristics duplicating functionality that fits src/common/parsing.py.
  - TODO to extract and reuse parsing utils.
- UA picking:
  - premierleague_scraper defines _pick_ua duplicating selection logic; TODO to reuse src.common.http DEFAULT_UAS and header builder.
- Age/market value parsing:
  - Duplicated across scraping_orchestrator and database/services/players; TODO to DRY via shared util.

Structural Observations
- Scraper/Collector mismatch:
  - TransfermarktScraper inherits DataCollector but is registered in ScrapingOrchestrator that expects BaseScraper.
  - TODO (already present elsewhere) to align inheritance or registration path.
- DB alignment:
  - Services reference columns like external_id for matches/clubs, while ORM uses external_ids (JSON).
  - TODOs (in services and scrapers) to limit services to ingestion tables (live_scores, odds) or align schema.
- API bootstrap:
  - api/main.py already has TODO to clean duplicate imports and guard optional scrapers; good direction.

Prioritized Actions
1) Deduplicate HTTP/UA logic
   - Remove local fetch_html and UA/header constants in scrapers; import from src.common.http.
2) Standardize on shared Playwright utilities
   - Remove _infinite_scroll from courtside_scraper and use src.common.playwright_utils.infinite_scroll.
3) Centralize parsing helpers
   - Move numeric/text/“minute” parsing helpers from fbref_match_scraper to src/common/parsing, then reuse.
4) Resolve scraper/collector mismatch
   - Make TransfermarktScraper extend BaseScraper or register it under a collector orchestrator.
5) DB service/schema alignment
   - Keep services targeting ingestion tables (live_scores, odds) or adjust schema; avoid direct matches/clubs writes unless schema updated.

Notes
- Keep SAFE_MODE startup path in api/main.py and admin to avoid heavy imports for dev.
- Introduce a shared utility module (e.g., src/common/normalization.py) for age/market value parsing to be reused across services and orchestrator.

If helpful, I can follow up with a PR that:
- Refactors scrapers to use src.common.http and src.common.parsing.
- Removes local infinite scrolling in courtside_scraper.
- Introduces a shared normalization helper for age/market value.