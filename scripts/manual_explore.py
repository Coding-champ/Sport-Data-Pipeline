"""
Manual exploration of the Courtside1891 page structure
"""

import asyncio
import os

from playwright.async_api import async_playwright


async def explore_page():
    """Manually explore the page structure"""
    async with async_playwright() as p:
        # Launch browser with devtools open
        browser = await p.chromium.launch(headless=False, devtools=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("Navigating to Courtside1891...")
            await page.goto("https://www.courtside1891.basketball/games", timeout=60000)

            # Wait for content to load
            print("Waiting for content to load...")
            await page.wait_for_load_state("networkidle")

            # Take a screenshot
            out_dir = os.path.join("reports", "courtside")
            os.makedirs(out_dir, exist_ok=True)
            await page.screenshot(path=os.path.join(out_dir, "courtside_page.png"), full_page=True)

            # Let the user know what to do next
            print("\nBrowser window opened with DevTools.")
            print("1. Use the Elements panel to inspect the page")
            print("2. Look for elements containing fixture data")
            print("3. Note any relevant classes, IDs, or data attributes")
            print("4. Press Enter in this terminal when done")

            # Keep the browser open for manual inspection
            input("Press Enter to close the browser...")

        except Exception as e:
            print(f"Error: {str(e)}")
            import traceback

            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(explore_page())
