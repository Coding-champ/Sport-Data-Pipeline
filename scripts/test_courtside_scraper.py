"""
Test script with direct terminal output (no DB). Adds ./src to sys.path for imports.
"""

import asyncio
import json
import os
import sys

# Ensure local src/ is importable without editable install
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from playwright.async_api import async_playwright

from src.core.config import Settings
from src.data_collection.scrapers.courtside_scraper import CourtsideScraper


async def main():
    """Main async function"""
    settings = Settings()
    scraper = CourtsideScraper(None, settings)  # No database

    print("Starting Courtside1891 scraper test...")
    results = await scraper.scrape_data()
    print("\nScraped data:")
    print(json.dumps(results, indent=2))
    print(f"\nFound {len(results)} fixtures")

    # Diagnostics if empty
    if not results:
        print("\nNo fixtures found by scraper. Running quick page diagnostics...")
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(
                "https://www.courtside1891.basketball/games",
                timeout=60000,
                wait_until="domcontentloaded",
            )
            ready = await page.evaluate("document.readyState")
            counts = await page.evaluate(
                """() => ({
                    fixture_row: document.querySelectorAll('[data-testid=\"fixture-row\"]').length,
                    fixture_card: document.querySelectorAll('[data-testid*=\"fixture\"][role]')?.length || 0,
                    any_fixture_testid: document.querySelectorAll('[data-testid*=\"fixture\"]').length,
                    listitems: document.querySelectorAll('li').length,
                    sections: document.querySelectorAll('section').length,
                })"""
            )
            text_sample = (await page.inner_text("body"))[:1200]
            print(f"document.readyState: {ready}")
            print("Selector counts:")
            print(json.dumps(counts, indent=2))
            print("\nBody text sample:\n" + text_sample)
            await browser.close()


if __name__ == "__main__":
    # Proper event loop handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
