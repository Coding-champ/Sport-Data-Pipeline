"""
Database services for match-related persistence.
"""

from __future__ import annotations

from ..manager import DatabaseManager
from src.domain.models import Match


async def upsert_matches(db: DatabaseManager, data: list[dict]):
    """Validiert und upsertet Match-Objekte in die 'matches'-Tabelle.
    Erwartet eine Liste von dicts, die mit dem Match-Pydantic-Modell kompatibel sind.
    """
    if not data:
        return

    matches = [Match(**item) for item in data]
    processed = [
        {
            "id": m.match_id if hasattr(m, "match_id") else None,
            "season": m.season,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "venue": m.venue.id if m.venue else None,
            "status": m.status.value if hasattr(m.status, "value") else m.status,
            "result": m.result.dict() if m.result else None,
            "external_ids": m.external_ids,
            "source_url": str(m.source_url) if m.source_url else None,
            "created_at": None,
            "updated_at": None,
        }
        for m in matches
    ]

    if processed:
        await db.bulk_insert(
            "matches",
            processed,
            "(id) DO UPDATE SET status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP",
        )