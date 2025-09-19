# Bundesliga Scraper Refactor Migration Guide

Date: 2025-09-19 (Updated – Shims Removed, Typing Enhancements Added)

## Overview

The Bundesliga club / squad / player scraping logic has been consolidated into a single canonical module:

`from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper`

Previously duplicated / legacy modules existed at:
`scrapers/bundesliga_club_scraper.py` (root), `scrapers/bundesliga/club_scraper.py`, and `scrapers/bundesliga_scraper.py`.

These deprecation shims have now been REMOVED. Any remaining imports pointing to them must be updated; otherwise imports will fail.

## Key Changes

- Unified feature set: overview extraction, squad link discovery, player parsing, JSON hydration fallback, LD‑JSON fallback (simplified) now coexist in one class.
- (Removed) legacy adapter method `_parse_detail(html, url)`; replaced with public `parse_club_html(html, url)` returning a normalized lightweight dict (`ClubParseResult`).
- Added explicit helper methods that tests call directly: `_extract_club_links`, `_extract_player_links`, `_extract_detail_url`, `_extract_name`, `_extract_stadium`, `_dedupe`.
- Player link extraction tightened to filter navigation/footer noise while still supporting synthetic unit test fixtures.

## Backward Compatibility

All shim modules have been excised. The only remaining transitional artifact is the private adapter method `_parse_detail(html, url)`—retain it until no external callers rely on the legacy dict shape, then remove.

## Migration Steps for Callers

1. Update imports:

   ```python
   # OLD
   from src.data_collection.scrapers.bundesliga.club_scraper import BundesligaClubScraper
   # or
   from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper

   # NEW
   from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper
   ```

2. Stop calling private legacy helpers (e.g. `_parse_detail`) and instead rely on:
   - `scrape_clubs()` for structured `EnhancedClub` objects
   - `scrape_squad(squad_url, club_name)` for player link lists
   - `scrape_player(player_url)` for `EnhancedPlayer` objects

3. Remove any custom JSON hydration parsing you had externally; it is handled internally.

4. Handle `EnhancedClub` / `EnhancedPlayer` pydantic models directly instead of dict munging.

## Data Model & Typing Notes

- `EnhancedPlayer.preferred_foot` now uses the shared enum `Footedness` from `domain.models`.
- Dates are parsed opportunistically; unparseable values become `None` instead of raising.
- New `ClubParseResult` `TypedDict` documents the lightweight shape returned by `parse_club_html` (only `name` guaranteed when present, others optional).
- Introduced `DatabaseManagerProtocol` (async `bulk_insert`) to formalize dependency injection for persistence and improve static analysis.
- Playwright runtime attributes now explicitly typed behind a `TYPE_CHECKING` guard for clearer editor support.

## Test Updates

- Unit tests now import only the canonical module path (no shim usage remains).
- All current unit tests pass (19 passed, 0 warnings related to deprecated imports).

## Future Follow-ups (Optional)

- Add richer club profile extraction (social links, colors, address) if still required.
- Expand career stats parsing to include defensive/keeper metrics.
- Consider deprecating `parse_club_html` if higher-level orchestration fully replaces ad‑hoc parsing use cases (retain while tests or tooling rely on `ClubParseResult`).
- Add integration test for matchday scraper after relocation.

## Changelog Summary

- Added: `bundesliga/bundesliga_club_scraper.py`, `bundesliga/bundesliga_matchday_scraper.py`.
- Removed: legacy shim files `bundesliga_club_scraper.py` (root), `bundesliga_scraper.py`, and `bundesliga/club_scraper.py`.
- Updated: migration guide to reflect final state (no shims).

## Contact

For questions about this refactor or migration, refer to the technical documentation or open an issue referencing this guide.
