"""
Database services for match-related persistence.
"""

from __future__ import annotations

import hashlib

from ..manager import DatabaseManager


async def upsert_matches(db: DatabaseManager, data: list[dict]):
    """Transform and upsert match-like dicts into 'live_scores' table.

    Expects items with keys: home_team, away_team, scraped_at, and optional
    home_score, away_score, status, match_time.
    """
    if not data:
        return

    processed = []
    for item in data:
        # TODO: Normalize field names. Some scrapers use 'home'/'away' or 'home_team_name'/'away_team_name'.
        home = item.get("home_team") or item.get("home") or item.get("home_team_name")
        away = item.get("away_team") or item.get("away") or item.get("away_team_name")
        if not (home and away and item.get("scraped_at")):
            # TODO: Consider logging/metrics for dropped records.
            continue
        # Stable external id: sha1 of home|away|date
        id_src = f"{home}|{away}|{item['scraped_at'].date()}".encode()
        external_id = hashlib.sha1(id_src).hexdigest()
        processed.append(
            {
                "external_id": external_id,
                "home_team_name": home,
                "away_team_name": away,
                "home_score": item.get("home_score"),
                "away_score": item.get("away_score"),
                "status": item.get("status", "scheduled"),
                "match_time": item.get("match_time", ""),
                "source": item.get("source", "flashscore"),
                "created_at": item["scraped_at"],
            }
        )

    if processed:
        await db.bulk_insert(
            "live_scores",
            processed,
            "(external_id) DO UPDATE SET home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score, status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP",
        )