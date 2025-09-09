"""
Courtside1891 debug script
"""

import asyncio

from playwright.async_api import async_playwright


async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("Loading Courtside1891 (visible browser will open)...")
            await page.goto("https://www.courtside1891.basketball/games", timeout=60000)

            # Save debug info
            content = await page.content()
            with open("courtside_raw.html", "w", encoding="utf-8") as f:
                f.write(content)

            await page.screenshot(path="courtside_debug.png", full_page=True)
            print("Debug files saved:")
            print("- courtside_raw.html (page HTML)")
            print("- courtside_debug.png (screenshot)")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug())
