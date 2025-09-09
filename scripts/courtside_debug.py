"""
Debug script for Courtside1891 scraper
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.config import Settings
from src.database.manager import DatabaseManager


async def debug_courtside():
    """Debug function to explore Courtside1891 page structure"""
    settings = Settings()
    # Initialize with empty config since we're just debugging
    DatabaseManager(settings.database_url)

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await context.new_page()

        try:
            # Navigate to the page
            print("Navigating to Courtside1891...")
            await page.goto(
                "https://www.courtside1891.basketball/games",
                timeout=120000,
                wait_until="domcontentloaded",
            )
            print("Page loaded successfully")

            # Wait for content to load
            print("Waiting for content...")
            await page.wait_for_selector("body", timeout=30000)

            # Get the page content
            content = await page.content()
            print("\nPage content (first 1000 chars):")
            print(content[:1000])

            # Look for common data structures
            print("\nLooking for JSON data...")
            json_data = await page.evaluate(
                """() => {
                // Check for __NEXT_DATA__
                const nextData = document.getElementById('__NEXT_DATA__');
                if (nextData) {
                    console.log("Found __NEXT_DATA__");
                    return { type: '__NEXT_DATA__', data: JSON.parse(nextData.textContent) };
                }
                
                // Check for window.__INITIAL_STATE__ or similar
                if (window.__INITIAL_STATE__) {
                    console.log("Found __INITIAL_STATE__");
                    return { type: '__INITIAL_STATE__', data: window.__INITIAL_STATE__ };
                }
                
                // Look for any script tags with JSON data
                const scripts = Array.from(document.getElementsByTagName('script'));
                for (const script of scripts) {
                    const content = script.textContent || '';
                    if (content.includes('fixtures') || content.includes('games')) {
                        try {
                            const json = JSON.parse(content);
                            return { type: 'script_content', data: json };
                        } catch (e) {
                            // Not valid JSON, continue
                        }
                    }
                }
                
                return { type: 'no_data', data: null };
            }"""
            )

            if json_data["type"] != "no_data":
                print(f"\nFound {json_data['type']} data:")
                print(json.dumps(json_data["data"], indent=2)[:2000] + "...")

            # First, let's get all the text content to see what's visible
            print("\nGetting visible text content...")
            visible_text = await page.evaluate(
                """() => {
                return document.body.innerText;
            }"""
            )
            print("\nVisible text content (first 2000 chars):")
            print(visible_text[:2000] + ("..." if len(visible_text) > 2000 else ""))

            # Check for common API endpoints
            print("\nLooking for API endpoints in network requests...")
            api_endpoints = await page.evaluate(
                """() => {
                return Array.from(performance.getEntriesByType('resource'))
                    .filter(r => 
                        r.initiatorType === 'xmlhttprequest' || 
                        r.name.includes('api') || 
                        r.name.includes('graphql') ||
                        r.name.includes('fixture') ||
                        r.name.includes('game')
                    )
                    .map(r => ({
                        name: r.name,
                        type: r.initiatorType,
                        size: r.transferSize,
                        duration: r.duration
                    }));
            }"""
            )

            if api_endpoints:
                print("\nFound potential API endpoints:")
                for i, endpoint in enumerate(api_endpoints[:10], 1):
                    print(
                        f"{i}. {endpoint['name']} (Type: {endpoint['type']}, Size: {endpoint['size']} bytes)"
                    )

            # Look for fixture elements with more detailed inspection
            print("\nLooking for fixture elements with detailed inspection...")
            fixture_elements = await page.evaluate(
                """() => {
                const elements = [];
                
                // Common fixture selectors
                const selectors = [
                    '[data-testid*="fixture"]',
                    '[class*="fixture"]',
                    '[class*="game"]',
                    'a[href*="/game/"]',
                    'div[role="listitem"]',
                    'li[role="listitem"]'
                ];
                
                // Try each selector and collect matching elements
                for (const sel of selectors) {
                    const matches = Array.from(document.querySelectorAll(sel));
                    if (matches.length > 0) {
                        console.log(`Found ${matches.length} elements with selector: ${sel}`);
                        for (const el of matches) {
                            elements.push({
                                selector: sel,
                                tagName: el.tagName,
                                id: el.id,
                                className: el.className,
                                text: el.textContent.trim().replace(/\\s+/g, ' ').substring(0, 100),
                                attributes: Array.from(el.attributes).map(attr => ({
                                    name: attr.name,
                                    value: attr.value
                                })),
                                html: el.outerHTML.substring(0, 300) + (el.outerHTML.length > 300 ? '...' : '')
                            });
                        }
                    }
                }
                
                return elements;
            }"""
            )

            print(f"\nFound {len(fixture_elements)} potential fixture elements:")
            for i, el in enumerate(fixture_elements[:15]):  # Show first 15
                print(f"\n--- Element {i+1} ---")
                print(f"Selector: {el['selector']}")
                print(f"Tag: {el['tagName']}")
                print(f"ID: {el['id']}")
                print(f"Classes: {el['className']}")
                print(f"Text: {el['text']}")
                print("Attributes:")
                for attr in el["attributes"]:
                    print(f"  {attr['name']}: {attr['value']}")
                print(f"HTML: {el['html']}")

                # If this looks like a game/fixture link, try to extract more details
                if "game" in (el.get("className", "").lower() + " " + el.get("id", "").lower()):
                    print("\nThis element might be a game/fixture. Extracting more details...")
                    try:
                        # Try to find common patterns for teams and scores
                        details = await page.evaluate(
                            """(element) => {
                            const getText = (selector) => {
                                const el = element.querySelector(selector);
                                return el ? el.textContent.trim() : null;
                            };
                            
                            // Common patterns for team names and scores
                            return {
                                home_team: getText('[class*="home"], [class*="team1"], [data-home-team]') || 
                                          (element.getAttribute('data-home-team') || '').trim(),
                                away_team: getText('[class*="away"], [class*="team2"], [data-away-team]') || 
                                          (element.getAttribute('data-away-team') || '').trim(),
                                score: getText('[class*="score"], [class*="result"], [data-score]'),
                                link: element.href || element.getAttribute('href') || null,
                                data_attrs: Object.fromEntries(
                                    Object.entries(element.dataset).map(([k, v]) => [k, v])
                                )
                            };
                        }""",
                            el["element"],
                        )

                        print("Extracted game details:")
                        for k, v in details.items():
                            if v:  # Only show non-empty values
                                print(f"  {k}: {v}")

                    except Exception as e:
                        print(f"  Could not extract details: {str(e)}")

            if len(fixture_elements) > 10:
                print(f"\n... and {len(fixture_elements) - 10} more elements")

        except Exception as e:
            print(f"Error during debugging: {str(e)}")
            import traceback

            traceback.print_exc()

        finally:
            # Keep browser open for inspection
            print("\nDebugging complete. Press Enter to close the browser...")
            input()
            await browser.close()


if __name__ == "__main__":
    import json

    from playwright.async_api import async_playwright

    asyncio.run(debug_courtside())
