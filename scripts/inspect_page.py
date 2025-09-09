"""
Simple script to inspect the structure of the Courtside1891 games page
"""

import asyncio
import os

from playwright.async_api import async_playwright


async def inspect_page():
    """Inspect the Courtside1891 games page structure"""
    async with async_playwright() as p:
        # Launch browser in non-headless mode
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("Navigating to Courtside1891...")
            await page.goto("https://www.courtside1891.basketball/games", timeout=60000)

            # Wait for content to load
            print("Waiting for content to load...")
            await page.wait_for_load_state("networkidle")

            # Take a screenshot
            print("Taking screenshot...")
            out_dir = os.path.join("reports", "courtside")
            os.makedirs(out_dir, exist_ok=True)
            await page.screenshot(
                path=os.path.join(out_dir, "courtside_screenshot.png"), full_page=True
            )

            # Get all elements with data-testid
            print("\nElements with data-testid:")
            test_ids = await page.evaluate(
                """() => {
                const elements = Array.from(document.querySelectorAll('[data-testid]'));
                return elements.map(el => ({
                    tag: el.tagName,
                    testid: el.getAttribute('data-testid'),
                    text: el.textContent.trim().replace(/\\s+/g, ' ').substring(0, 50),
                    id: el.id || null,
                    classes: el.className || null
                }));
            }"""
            )

            # Print first 10 elements with data-testid
            for i, item in enumerate(test_ids[:10]):
                print(f"{i+1}. <{item['tag']} data-testid=\"{item['testid']}\">")
                print(f"   Text: {item['text']}")
                print(f"   ID: {item['id']}")
                print(f"   Classes: {item['classes']}")

            # Look for common fixture/game elements
            print("\nLooking for potential fixture elements...")

            # Common selectors to try
            selectors = [
                '[data-testid*="fixture"]',
                '[class*="fixture"]',
                '[data-testid*="game"]',
                '[class*="game"]',
                "article",
                "section",
                'div[role="listitem"]',
                ".MuiCard-root",
                "div > div > div",
                'a[href*="/game/"]',
            ]

            for selector in selectors:
                try:
                    count = await page.evaluate(
                        f"""() => {{
                        return document.querySelectorAll('{selector}').length;
                    }}"""
                    )
                    print(f"Found {count} elements with selector: {selector}")

                    # If we found elements, show a sample
                    if count > 0:
                        sample = await page.evaluate(
                            f"""() => {{
                            const el = document.querySelector('{selector}');
                            return {{
                                tag: el.tagName,
                                id: el.id || null,
                                classes: el.className || null,
                                text: el.textContent.trim().replace(/\\s+/g, ' ').substring(0, 100) + '...',
                                html: el.outerHTML.substring(0, 200) + (el.outerHTML.length > 200 ? '...' : '')
                            }};
                        }}"""
                        )
                        print(f"  Sample: {sample['tag']}")
                        print(f"  ID: {sample['id'] or 'None'}")
                        print(f"  Classes: {sample['classes'] or 'None'}")
                        print(f"  Text: {sample['text']}")
                        print(f"  HTML: {sample['html']}")

                except Exception as e:
                    print(f"  Error with selector '{selector}': {str(e)}")

            # Look for any visible text that might indicate fixtures
            print("\nLooking for fixture-related text...")
            fixture_text = await page.evaluate(
                """() => {
                const elements = Array.from(document.querySelectorAll('*'));
                const fixtureElements = elements.filter(el => {
                    const text = el.textContent.trim().toLowerCase();
                    return text.includes('vs') || 
                           text.includes('vs.') ||
                           text.includes('home') ||
                           text.includes('away') ||
                           text.includes('score');
                });
                
                return fixtureElements.map(el => ({
                    tag: el.tagName,
                    id: el.id || null,
                    classes: el.className || null,
                    text: el.textContent.trim().replace(/\\s+/g, ' ').substring(0, 100) + '...'
                }));
            }"""
            )

            print(f"\nFound {len(fixture_text)} elements with fixture-related text")
            if fixture_text:
                print("\nSample elements with fixture text:")
                for i, item in enumerate(fixture_text[:5]):
                    print(f"{i+1}. <{item['tag']}>")
                    print(f"   ID: {item['id'] or 'None'}")
                    print(f"   Classes: {item['classes'] or 'None'}")
                    print(f"   Text: {item['text']}")

            print(
                "\nInspection complete. Check 'reports/courtside/courtside_screenshot.png' for a visual reference."
            )

        except Exception as e:
            print(f"Error during inspection: {str(e)}")
            import traceback

            traceback.print_exc()
        finally:
            # Keep browser open for manual inspection
            input("Press Enter to close the browser...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_page())
