"""
Simple debug script to explore Courtside1891 page structure
"""

import asyncio

from playwright.async_api import async_playwright


async def debug_page():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navigate to the page
            print("Navigating to Courtside1891...")
            await page.goto("https://www.courtside1891.basketball/games", timeout=60000)

            # Wait for content to load
            print("Waiting for content...")
            await page.wait_for_load_state("networkidle")

            # Get page title
            title = await page.title()
            print(f"\nPage title: {title}")

            # Get all text content
            print("\nPage content (first 1000 chars):")
            content = await page.content()
            print(content[:1000] + ("..." if len(content) > 1000 else ""))

            # Find all links
            print("\nAll links on page:")
            links = await page.evaluate(
                """() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({
                        text: a.textContent.trim().replace(/\s+/g, ' ').substring(0, 50),
                        href: a.href
                    }))
                    .filter(link => link.text);
            }"""
            )

            for i, link in enumerate(links[:20], 1):  # Show first 20 links
                print(f"{i}. {link['text']} - {link['href']}")

            # Look for common data attributes
            print("\nElements with data-testid:")
            testids = await page.evaluate(
                """() => {
                return Array.from(document.querySelectorAll('[data-testid]'))
                    .map(el => ({
                        tag: el.tagName,
                        testid: el.getAttribute('data-testid'),
                        text: el.textContent.trim().replace(/\s+/g, ' ').substring(0, 50)
                    }));
            }"""
            )

            for item in testids[:20]:  # Show first 20
                print(f"- {item['tag']} [data-testid=\"{item['testid']}\"]: {item['text']}")

            # Look for JSON data
            print("\nLooking for JSON data...")
            json_data = await page.evaluate(
                """() => {
                const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                return scripts.map(s => {
                    try { return JSON.parse(s.textContent); } 
                    catch (e) { return null; }
                }).filter(Boolean);
            }"""
            )

            if json_data:
                print(f"Found {len(json_data)} JSON-LD scripts")
                for i, data in enumerate(json_data[:2], 1):  # Show first 2
                    print(f"\nJSON-LD {i} (first 200 chars):")
                    print(str(data)[:200] + "...")

            # Look for common game/fixture elements
            print("\nLooking for game/fixture elements...")
            games = await page.evaluate(
                """() => {
                const elements = [];
                // Common selectors for game/fixture elements
                const selectors = [
                    '[class*="fixture"]',
                    '[class*="game"]',
                    '[role="listitem"]',
                    'article',
                    'section',
                    '.MuiCard-root'
                ];
                
                for (const sel of selectors) {
                    const matches = document.querySelectorAll(sel);
                    if (matches.length > 0) {
                        console.log(`Found ${matches.length} elements with selector: ${sel}`);
                        Array.from(matches).forEach(el => {
                            elements.push({
                                selector: sel,
                                tag: el.tagName,
                                id: el.id,
                                className: el.className,
                                text: el.textContent.trim().replace(/\s+/g, ' ').substring(0, 100)
                            });
                        });
                    }
                }
                return elements;
            }"""
            )

            print(f"\nFound {len(games)} potential game/fixture elements:")
            for i, game in enumerate(games[:10], 1):  # Show first 10
                print(f"\n--- Game {i} ---")
                print(f"Selector: {game['selector']}")
                print(f"Tag: {game['tag']}")
                print(f"ID: {game['id']}")
                print(f"Classes: {game['className']}")
                print(f"Text: {game['text']}")

            print("\nDebug complete. Check the browser window for the loaded page.")

            # Keep browser open for inspection
            input("Press Enter to close the browser...")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_page())
