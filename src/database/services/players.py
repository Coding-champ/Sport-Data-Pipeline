"""
Database services for player-related persistence.
"""

from __future__ import annotations

import json

from ..manager import DatabaseManager


async def upsert_players(db: DatabaseManager, data: list[dict]):
    """Transform and upsert player-like dicts into 'players' table.

    Expects items with keys (provider-agnostic after scraping):
    - name (full), market_value, position, age, scraped_at, profile_url
    """
    if not data:
        return

    processed = []
    for item in data:
        name = (item.get("name") or "").strip()
        first, *rest = name.split()
        processed.append(
            {
                "first_name": first or "",
                "last_name": " ".join(rest) if rest else "",
                "external_ids": json.dumps(
                    {"transfermarkt": item.get("profile_url", "")}, ensure_ascii=False
                ),
                "market_value": _parse_market_value(item.get("market_value")),
                "position": item.get("position", ""),
                "age": _parse_age(item.get("age")),
                "created_at": item.get("scraped_at"),
            }
        )

    if processed:
        await db.bulk_insert(
            "players",
            processed,
            "(first_name,last_name) DO UPDATE SET market_value = EXCLUDED.market_value, updated_at = CURRENT_TIMESTAMP",
        )


def _parse_market_value(value):
    if not value:
        return None
    s = str(value)
    try:
        s = s.replace("€", "").replace("$", "").replace(",", "").strip()
        if "Mio" in s or "M" in s:
            return float(s.replace("Mio", "").replace("M", "").strip()) * 1_000_000
        if "Tsd" in s or "K" in s:
            return float(s.replace("Tsd", "").replace("K", "").strip()) * 1_000
        return float(s)
    except Exception:
        return None


def _parse_age(value):
    if value is None:
        return None
    try:
        import re

        m = re.search(r"\d+", str(value))
        return int(m.group(0)) if m else None
    except Exception:
        return None
