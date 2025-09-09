import asyncio
import json
import os
import sys
from typing import Any

# Ensure project root is on sys.path so 'src' package is importable when running directly
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Minimal dummy implementations to avoid touching the real DB or settings
class DummyDBManager:
    async def bulk_insert(self, *args, **kwargs):
        return None


class DummySettings:
    pass


async def main() -> None:
    from src.data_collection.scrapers.courtside_scraper import CourtsideScraper

    scraper = CourtsideScraper(db_manager=DummyDBManager(), settings=DummySettings())
    items: list[dict[str, Any]] = await scraper.scrape_data()

    # Print a concise preview of the first few unified items
    print(f"Total fixtures scraped: {len(items)}")
    for i, it in enumerate(items[:10]):
        preview = {
            "fixture_id": it.get("fixture_id"),
            "competition_id": it.get("competition_id"),
            "home_team_id": it.get("home_team_id"),
            "away_team_id": it.get("away_team_id"),
            "home_team_name": it.get("home_team_name"),
            "away_team_name": it.get("away_team_name"),
            "score": it.get("score"),
            "url": it.get("url"),
        }
        print(json.dumps(preview, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
