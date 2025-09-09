"""
Standalone Courtside scraper test with terminal output
"""

import asyncio
import json

from playwright.async_api import async_playwright


async def scrape_courtside():
    """Scrape Courtside1891 and print results"""
    async with async_playwright() as p:
        # Simplified browser launch without extra config
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            print("Loading Courtside1891 website...")
            await page.goto(
                "https://www.courtside1891.basketball/games",
                timeout=60000,
                wait_until="domcontentloaded",
            )

            # Wait for and extract data
            await page.wait_for_selector('[data-testid="fixture-row"]', timeout=30000)
            fixtures = await page.evaluate(
                """() => {
                return Array.from(document.querySelectorAll('[data-testid="fixture-row"]')).map(row => ({
                    home: row.querySelector('[data-testid="team-home"]')?.textContent.trim(),
                    away: row.querySelector('[data-testid="team-away"]')?.textContent.trim(),
                    score: row.querySelector('[data-testid="fixture-score"]')?.textContent.trim(),
                    competition: row.closest('[data-testid="competition-fixtures"]')?.querySelector('[data-testid="competition-name"]')?.textContent.trim()
                }));
            }"""
            )

            print("\nScraped fixtures:")
            print(json.dumps(fixtures, indent=2))
            print(f"\nTotal fixtures found: {len(fixtures)}")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_courtside())
