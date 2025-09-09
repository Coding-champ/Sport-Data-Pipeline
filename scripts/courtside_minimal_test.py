"""
Enhanced minimal Courtside test
"""

import asyncio
from datetime import datetime

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visible browser
        page = await browser.new_page()

        try:
            print("Loading page (visible browser will open)...")
            await page.goto(
                "https://www.courtside1891.basketball/games",
                timeout=90000,  # Longer timeout
                wait_until="networkidle",
            )

            print("Waiting for fixtures (90s timeout)...")
            await page.wait_for_selector('[data-testid="fixture-row"]', timeout=90000)

            # Save debug info
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"courtside_success_{timestamp}.png", full_page=True)
            print(f"Saved screenshot: courtside_success_{timestamp}.png")

            # Output sample content
            content = await page.content()
            print("\nFirst 1000 characters of page:")
            print(content[:1000])

        except Exception as e:
            print(f"\nError: {e}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"courtside_error_{timestamp}.png", full_page=True)
            print(f"Saved error screenshot: courtside_error_{timestamp}.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
