"""
Test script for Courtside1891 scraper
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.config import Settings
from src.data_collection.scrapers.courtside_scraper import CourtsideScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("scraper_test.log")],
)


async def test_scraper():
    """Test the Courtside scraper"""
    print("Initializing test...")

    # Initialize with test settings
    settings = Settings()

    # Create a simple mock database manager since we're not using the DB
    class MockDBManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def fetch_all(self, *args, **kwargs):
            return []

    # Create scraper instance with mock DB manager
    scraper = CourtsideScraper(MockDBManager(), settings)

    try:
        print("Starting scraper test...")

        # Enable debug logging
        import logging

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(), logging.FileHandler("scraper_debug.log")],
        )

        # Run the scraper with timing
        import time

        start_time = time.time()

        print("\n=== Starting scraper execution ===")
        results = await scraper.scrape_data()

        elapsed = time.time() - start_time
        print(f"\n=== Scraping completed in {elapsed:.2f} seconds ===")

        # Print summary
        print(f"\nScraping complete. Found {len(results)} fixtures.")

        if results:
            print("\n=== Sample fixture ===")
            import json

            print(json.dumps(results[0], indent=2))

            # Count fixtures by competition
            from collections import defaultdict

            comp_counts = defaultdict(int)
            for f in results:
                comp = f.get("competition", "Unknown")
                comp_counts[comp] += 1

            print("\n=== Fixtures by competition ===")
            for comp, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"{comp}: {count} fixtures")

            # Analyze data quality
            missing_data = []
            for f in results:
                if not (f.get("home_team") and f.get("away_team")):
                    missing_data.append(f)

            print("\n=== Data Quality Report ===")
            print(f"Total fixtures: {len(results)}")
            print(f"Fixtures with missing team names: {len(missing_data)}")
            print(
                f"Data quality: {((len(results) - len(missing_data)) / len(results) * 100):.1f}% complete"
            )

            if missing_data:
                print("\n=== Sample problematic fixtures ===")
                for i, f in enumerate(missing_data[:3]):
                    print(f"\nProblematic Fixture {i+1}:")
                    print(f"- Competition: {f.get('competition', 'N/A')}")
                    print(
                        f"- Home: {f.get('home_team', 'MISSING')} (ID: {f.get('home_team_id', 'N/A')})"
                    )
                    print(
                        f"- Away: {f.get('away_team', 'MISSING')} (ID: {f.get('away_team_id', 'N/A')})"
                    )
                    print(f"- Score: {f.get('score', 'N/A')}")

                    if "_debug" in f:
                        debug = f["_debug"]
                        print("\nDebug Info:")
                        print(f"- Selector: {debug.get('selector', 'unknown')}")
                        print("\nHTML Snippet:")
                        print(debug.get("outerHTML", "No HTML available")[:500] + "...")

                        if "parentHTML" in debug and debug["parentHTML"] != "No parent":
                            print("\nParent HTML Snippet:")
                            print(debug["parentHTML"][:500] + "...")

                # Save full debug info to file
                with open("problematic_fixtures.json", "w", encoding="utf-8") as f:
                    json.dump(missing_data, f, indent=2, ensure_ascii=False)
                print("\nSaved full debug info to 'problematic_fixtures.json'")

            # Save all results to a file for further analysis
            with open("scraped_fixtures.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print("\nSaved all scraped data to 'scraped_fixtures.json'")

    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        await scraper.close()
        print("\nTest complete.")


if __name__ == "__main__":
    asyncio.run(test_scraper())
