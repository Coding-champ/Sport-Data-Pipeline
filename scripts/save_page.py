"""
Simple script to save the HTML of a webpage for analysis
"""

import asyncio
import os
from datetime import datetime

from playwright.async_api import async_playwright


async def save_page():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "logs"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"courtside_snapshot_{timestamp}.html")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("Loading page...")
            await page.goto("https://www.courtside1891.basketball/games", timeout=60000)

            # Wait for content to load
            await page.wait_for_load_state("networkidle")

            # Save the HTML content
            content = await page.content()
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"\nPage saved to: {output_file}")

            # Also save a screenshot
            screenshot_path = os.path.join(output_dir, f"courtside_snapshot_{timestamp}.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(save_page())
