"""
Script to analyze the structure of the Courtside1891 games page
"""

import asyncio
import json
import os

from playwright.async_api import async_playwright


async def analyze_page():
    """Analyze the structure of the Courtside1891 games page"""
    async with async_playwright() as p:
        # Launch browser
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
            os.makedirs("reports/courtside", exist_ok=True)
            await page.screenshot(
                path=os.path.join("reports", "courtside", "courtside_page.png"), full_page=True
            )

            # Save page content
            print("Saving page content...")
            content = await page.content()
            with open(
                os.path.join("reports", "courtside", "courtside_page.html"), "w", encoding="utf-8"
            ) as f:
                f.write(content)

            # Extract and save all data-testid attributes
            print("Extracting data-testid attributes...")
            test_ids = await page.evaluate(
                """() => {
                const elements = Array.from(document.querySelectorAll('[data-testid]'));
                return elements.map(el => ({
                    tag: el.tagName,
                    testid: el.getAttribute('data-testid'),
                    text: el.textContent.trim().replace(/\s+/g, ' ').substring(0, 100),
                    id: el.id || null,
                    classes: el.className || null,
                    html: el.outerHTML.substring(0, 200) + (el.outerHTML.length > 200 ? '...' : '')
                }));
            }"""
            )

            with open(
                os.path.join("reports", "courtside", "test_ids.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(test_ids, f, indent=2, ensure_ascii=False)

            # Look for potential fixture containers
            print("\nLooking for potential fixture containers...")
            containers = await page.evaluate(
                """() => {
                const selectors = [
                    '.MuiContainer-root',
                    '.fixtures-container',
                    '.games-container',
                    'main',
                    'div[role="main"]',
                    'div.container',
                    'div#root',
                    'body'
                ];
                
                return selectors.map(selector => {
                    const elements = Array.from(document.querySelectorAll(selector));
                    return {
                        selector,
                        count: elements.length,
                        sample: elements.length > 0 ? {
                            tagName: elements[0].tagName,
                            id: elements[0].id || null,
                            classes: elements[0].className || null,
                            text: elements[0].textContent.trim().replace(/\s+/g, ' ').substring(0, 100) + '...',
                            children: elements[0].children.length
                        } : null
                    };
                });
            }"""
            )

            print("\nPotential container elements:")
            for container in containers:
                print(f"\nSelector: {container['selector']}")
                print(f"  Found: {container['count']} elements")
                if container["sample"]:
                    print(f"  Sample: {container['sample']['tagName']}")
                    print(f"  ID: {container['sample']['id'] or 'None'}")
                    print(f"  Classes: {container['sample']['classes'] or 'None'}")
                    print(f"  Text: {container['sample']['text']}")
                    print(f"  Children: {container['sample']['children']}")

            # Look for potential fixture elements
            print("\nLooking for potential fixture elements...")
            fixture_elements = await page.evaluate(
                """() => {
                const selectors = [
                    '[data-testid*="fixture"]',
                    '[class*="fixture"]',
                    '[data-testid*="game"]',
                    '[class*="game"]',
                    'article',
                    'section',
                    'div[role="listitem"]',
                    'div[role="article"]',
                    '.MuiCard-root',
                    'div > div > div',
                    'a[href*="/game/"]',
                    'a[href*="/fixture/"]'
                ];
                
                const results = [];
                
                for (const selector of selectors) {
                    try {
                        const elements = Array.from(document.querySelectorAll(selector));
                        if (elements.length > 0) {
                            const sample = elements[0];
                            results.push({
                                selector,
                                count: elements.length,
                                sample: {
                                    tagName: sample.tagName,
                                    id: sample.id || null,
                                    classes: sample.className || null,
                                    text: sample.textContent.trim().replace(/\s+/g, ' ').substring(0, 100) + '...',
                                    html: sample.outerHTML.substring(0, 200) + (sample.outerHTML.length > 200 ? '...' : '')
                                }
                            });
                        }
                    } catch (e) {
                        console.error(`Error with selector ${selector}:`, e);
                    }
                }
                
                return results;
            }"""
            )

            print("\nPotential fixture elements:")
            for element in fixture_elements:
                print(f"\nSelector: {element['selector']}")
                print(f"  Found: {element['count']} elements")
                print(f"  Sample HTML: {element['sample']['html']}")

            # Save all results to a file
            results = {
                "containers": containers,
                "fixture_elements": fixture_elements,
                "test_ids": test_ids[:20],  # First 20 test IDs for reference
            }

            with open(
                os.path.join("reports", "courtside", "page_analysis.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print("\nAnalysis complete. Check the following files under reports/courtside/:")
            print("- courtside_page.png: Screenshot of the page")
            print("- courtside_page.html: Full HTML content")
            print("- test_ids.json: All elements with data-testid attributes")
            print("- page_analysis.json: Complete analysis results")

        except Exception as e:
            print(f"Error during analysis: {str(e)}")
            import traceback

            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(analyze_page())
