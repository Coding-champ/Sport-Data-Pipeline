"""
Database services for odds-related persistence.
"""

from __future__ import annotations

import hashlib

from ..manager import DatabaseManager


def _stable_odds_id(item: dict) -> str:
    # Stable external id: sha1 of bookmaker|home|away|date|market
    market = item.get("market_type", "1X2")
    date_part = str(item["scraped_at"].date())
    src = (
        f"{item['bookmaker']}|{item['home_team']}|{item['away_team']}|{date_part}|{market}".encode()
    )
    return hashlib.sha1(src).hexdigest()


async def upsert_odds(db: DatabaseManager, data: list[dict]):
    """Transform and upsert odds-like dicts into 'odds' table.

    Expects items with keys: bookmaker, home_team, away_team, scraped_at, and
    odds_home, odds_draw, odds_away; optional: is_live, market_type.
    """
    if not data:
        return

    processed = []
    for item in data:
        external_id = _stable_odds_id(item)
        processed.append(
            {
                "external_id": external_id,
                "bookmaker": item["bookmaker"],
                "home_team_name": item["home_team"],
                "away_team_name": item["away_team"],
                "odds_home": item.get("odds_home"),
                "odds_draw": item.get("odds_draw"),
                "odds_away": item.get("odds_away"),
                "market_type": item.get("market_type", "1X2"),
                "is_live": item.get("is_live", False),
                "created_at": item["scraped_at"],
            }
        )

    if processed:
        await db.bulk_insert(
            "odds",
            processed,
            "(external_id) DO UPDATE SET odds_home = EXCLUDED.odds_home, odds_draw = EXCLUDED.odds_draw, odds_away = EXCLUDED.odds_away, updated_at = CURRENT_TIMESTAMP",
        )
