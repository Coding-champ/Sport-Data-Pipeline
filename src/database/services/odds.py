"""
Database services for odds-related persistence.
"""

from __future__ import annotations

from ..manager import DatabaseManager
from src.domain.models import Odds


async def upsert_odds(db: DatabaseManager, data: list[dict]):
    """Validiert und upsertet Odds-Objekte in die 'odds'-Tabelle.
    Erwartet eine Liste von dicts, die mit dem Odds-Pydantic-Modell kompatibel sind.
    """
    if not data:
        return

    odds_list = [Odds(**item) for item in data]
    processed = [
        {
            "match_id": o.match_id,
            "provider": o.provider,
            "market": o.market,
            "selections": [s.dict() for s in o.selections],
            "ts": o.ts,
        }
        for o in odds_list
    ]

    if processed:
        await db.bulk_insert(
            "odds",
            processed,
            "(match_id, provider, market) DO UPDATE SET selections = EXCLUDED.selections, ts = EXCLUDED.ts, updated_at = CURRENT_TIMESTAMP",
        )