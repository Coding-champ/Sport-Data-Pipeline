"""
Diagnostic & exploratory runner for Courtside1891 scraper.

Combines previous ad-hoc scripts (test_scraper.py, test_courtside_scraper.py) into a single
maintainable utility. No database writes – runs scraper logic and provides:
  * Execution timing
  * Sample fixture preview
  * Competition distribution summary
  * Data quality checks for missing team names
  * Debug export of problematic fixtures
  * Optional page diagnostics when zero results are returned

Usage (PowerShell):
  python scripts/diagnose/courtside_scraper_diagnose.py [--limit N] [--debug]

Environment:
  Relies on Settings() for configuration; ensures local `src/` is on sys.path.

NOTE: This script intentionally performs live network & browser automation calls and is
NOT meant for automated CI. Use manually for investigation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, List

from playwright.async_api import async_playwright

# --- Path setup -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent  # project root
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.core.config import Settings  # type: ignore  # noqa: E402
from src.data_collection.scrapers.courtside_scraper import (  # type: ignore  # noqa: E402
    CourtsideScraper,
)

# --- Logging --------------------------------------------------------------------
LOG_FILE = "courtside_scraper_diagnose.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("courtside.diagnose")


# --- Core diagnostic routine ----------------------------------------------------
async def run_diagnostics(limit: int | None, enable_debug: bool) -> None:
    settings = Settings()
    scraper = CourtsideScraper(None, settings)  # No DB usage here

    if enable_debug:
        logger.setLevel(logging.DEBUG)

    logger.info("Starting Courtside scraper diagnostic run ...")
    start_time = time.time()

    try:
        results: List[dict[str, Any]] = await scraper.scrape_data()
    except Exception as e:  # pragma: no cover - diagnostic path
        logger.exception("Scraper raised an exception: %s", e)
        await scraper.close()
        return

    elapsed = time.time() - start_time
    logger.info("Scraping completed in %.2f seconds (%d fixtures)", elapsed, len(results))

    if limit and results:
        results = results[:limit]
        logger.info("Limiting in-memory results to first %d fixtures for reporting", limit)

    if not results:
        logger.warning("No fixtures returned – invoking page diagnostics")
        await _page_diagnostics()
        await scraper.close()
        return

    # Sample fixture
    logger.info("Sample fixture:\n%s", json.dumps(results[0], indent=2, ensure_ascii=False))

    # Competition distribution
    comp_counts: dict[str, int] = defaultdict(int)
    for fx in results:
        comp_counts[fx.get("competition", "Unknown")] += 1
    logger.info("Competition distribution:")
    for comp, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info("  %s: %d", comp, count)

    # Data quality check
    missing = [fx for fx in results if not (fx.get("home_team") and fx.get("away_team"))]
    completeness = (len(results) - len(missing)) / len(results) * 100 if results else 0
    logger.info(
        "Data quality: %d total | %d missing teams | %.1f%% complete",
        len(results),
        len(missing),
        completeness,
    )

    if missing:
        sample_missing = missing[:3]
        logger.info("Sample problematic fixtures (max 3):")
        for i, fx in enumerate(sample_missing, start=1):
            logger.info(
                "Problem %d: comp=%s home=%s away=%s score=%s",
                i,
                fx.get("competition"),
                fx.get("home_team"),
                fx.get("away_team"),
                fx.get("score"),
            )
            dbg = fx.get("_debug")
            if isinstance(dbg, dict):
                selector = dbg.get("selector")
                outer = (dbg.get("outerHTML") or "")[:400].replace("\n", " ")
                logger.debug("  selector=%s outerHTML[0:400]=%s...", selector, outer)

        with open("problematic_fixtures.json", "w", encoding="utf-8") as f:
            json.dump(missing, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d problematic fixtures to problematic_fixtures.json", len(missing))

    # Persist full results
    with open("scraped_fixtures.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Saved all scraped fixtures to scraped_fixtures.json")

    await scraper.close()


# --- Page diagnostics when scraper returns nothing ------------------------------
async def _page_diagnostics():  # pragma: no cover - side-channel
    logger.info("Running low-level page diagnostics ...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            target_url = "https://www.courtside1891.basketball/games"
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            ready = await page.evaluate("document.readyState")
            counts = await page.evaluate(
                """() => ({
                    fixture_row: document.querySelectorAll('[data-testid=\\"fixture-row\\"]').length,
                    fixture_card: document.querySelectorAll('[data-testid*=\\"fixture\\"][role]').length,
                    any_fixture_testid: document.querySelectorAll('[data-testid*=\\"fixture\\"]').length,
                    listitems: document.querySelectorAll('li').length,
                    sections: document.querySelectorAll('section').length,
                })"""
            )
            text_sample = (await page.inner_text("body"))[:1000]
            logger.info("document.readyState=%s selector_counts=%s", ready, counts)
            logger.debug("Body sample: %s", text_sample.replace("\n", " ")[:300])
            await browser.close()
    except Exception:
        logger.exception("Page diagnostics failed")


# --- CLI ------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Courtside scraper diagnostic tool")
    parser.add_argument("--limit", type=int, help="Limit number of fixtures processed for summary")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main():  # pragma: no cover - CLI entry
    args = parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_diagnostics(args.limit, args.debug))
    finally:
        loop.close()


if __name__ == "__main__":  # pragma: no cover
    main()
