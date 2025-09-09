"""
Test script to check if we can access the Courtside1891 API directly
"""

import asyncio
import json
import os
from datetime import datetime

import aiohttp


async def test_api():
    """Test accessing the Courtside1891 API"""
    # Common API endpoints for sports data
    api_endpoints = [
        "https://api.courtside1891.basketball/games",
        "https://www.courtside1891.basketball/api/games",
        "https://www.courtside1891.basketball/api/v1/fixtures",
        "https://www.courtside1891.basketball/api/v1/games",
        "https://api.courtside1891.basketball/v1/fixtures",
        "https://api.courtside1891.basketball/v1/games",
        "https://www.courtside1891.basketball/_next/data/__BUILD_ID__/games.json",
    ]

    # Common GraphQL endpoints
    graphql_endpoints = [
        "https://www.courtside1891.basketball/api/graphql",
        "https://api.courtside1891.basketball/graphql",
    ]

    # Common headers to try
    headers_list = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.courtside1891.basketball/",
            "Origin": "https://www.courtside1891.basketball",
        },
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.courtside1891.basketball/games",
            "Origin": "https://www.courtside1891.basketball",
        },
    ]

    async with aiohttp.ClientSession() as session:
        # Test REST API endpoints
        print("Testing REST API endpoints...")
        for url in api_endpoints:
            for headers in headers_list:
                try:
                    print(f"\nTrying: {url}")
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            content_type = response.headers.get("Content-Type", "")
                            print(f"  Status: {response.status}")
                            print(f"  Content-Type: {content_type}")

                            # Try to parse as JSON
                            try:
                                data = await response.json()
                                print(f"  JSON response (first 200 chars): {str(data)[:200]}...")

                                # Save the full response for inspection
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                out_dir = os.path.join("reports", "courtside")
                                os.makedirs(out_dir, exist_ok=True)
                                out_path = os.path.join(out_dir, f"api_response_{timestamp}.json")
                                with open(out_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f, indent=2, ensure_ascii=False)
                                print(f"  Saved full response to {out_path}")

                            except Exception:
                                # If not JSON, try to get text
                                text = await response.text()
                                print(f"  Text response (first 200 chars): {text[:200]}...")

                        else:
                            print(f"  Status: {response.status} - {response.reason}")
                except Exception as e:
                    print(f"  Error: {str(e)}")

        # Test GraphQL endpoints
        print("\nTesting GraphQL endpoints...")
        for url in graphql_endpoints:
            for headers in headers_list:
                try:
                    print(f"\nTrying GraphQL: {url}")

                    # Try a simple query to get fixtures/games
                    query = """
                    query {
                        fixtures {
                            id
                            homeTeam { name }
                            awayTeam { name }
                            score
                            competition { name }
                        }
                    }
                    """

                    # Try with different query formats
                    for query_format in [
                        {"query": query},
                        {"query": query, "variables": "{}"},
                        {"query": query, "operationName": "Fixtures"},
                    ]:
                        try:
                            async with session.post(
                                url,
                                json=query_format,
                                headers={**headers, "Content-Type": "application/json"},
                                timeout=10,
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    print(f"  GraphQL response: {str(data)[:200]}...")

                                    # Save the full response
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    out_dir = os.path.join("reports", "courtside")
                                    os.makedirs(out_dir, exist_ok=True)
                                    out_path = os.path.join(
                                        out_dir, f"graphql_response_{timestamp}.json"
                                    )
                                    with open(out_path, "w", encoding="utf-8") as f:
                                        json.dump(data, f, indent=2, ensure_ascii=False)
                                    print(f"  Saved full response to {out_path}")

                                else:
                                    print(f"  Status: {response.status} - {response.reason}")
                        except Exception as e:
                            print(f"  Error with query format: {str(e)}")

                except Exception as e:
                    print(f"  Error: {str(e)}")

        # Check for any XHR/fetch requests in the page that might contain data
        print("\nChecking for data in page XHR/fetch requests...")
        try:
            # Use Playwright to load the page and monitor network requests
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Collect all responses
                responses = []

                def handle_response(response):
                    url = response.url
                    status = response.status
                    content_type = response.headers.get("content-type", "")

                    # Only process JSON responses
                    if "application/json" in content_type and status == 200:
                        responses.append(
                            {
                                "url": url,
                                "status": status,
                                "content_type": content_type,
                                "method": response.request.method,
                                "request_headers": dict(response.request.headers),
                            }
                        )

                # Attach the response handler
                page.on("response", handle_response)

                # Navigate to the page
                print("Loading Courtside1891 page to monitor network requests...")
                await page.goto(
                    "https://www.courtside1891.basketball/games", wait_until="networkidle"
                )

                # Wait a bit more for any lazy-loaded content
                await asyncio.sleep(5)

                # Print the collected responses
                print(f"\nFound {len(responses)} JSON responses:")
                for i, resp in enumerate(responses, 1):
                    print(f"{i}. {resp['method']} {resp['url']} ({resp['status']})")
                    print(f"   Content-Type: {resp['content_type']}")

                    # Save the response details
                    out_dir = os.path.join("logs", "courtside")
                    os.makedirs(out_dir, exist_ok=True)
                    with open(
                        os.path.join(out_dir, f"network_response_{i}.json"), "w", encoding="utf-8"
                    ) as f:
                        json.dump(resp, f, indent=2, ensure_ascii=False)

                await browser.close()

        except ImportError:
            print("Playwright not available for network monitoring")
        except Exception as e:
            print(f"Error monitoring network: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_api())
