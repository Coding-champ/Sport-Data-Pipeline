"""
Database services for competition-related persistence.
"""

from __future__ import annotations

from ..manager import DatabaseManager
from src.domain.models import Competition


async def upsert_competitions(db: DatabaseManager, data: list[dict]):
    """Validiert und upsertet Competition-Objekte in die 'competitions'-Tabelle.
    Erwartet eine Liste von dicts, die mit dem Competition-Pydantic-Modell kompatibel sind.
    """
    if not data:
        return

    competitions = [Competition(**item) for item in data]
    processed = [
        {
            "competition_id": c.competition_id if hasattr(c, "competition_id") else None,
            "competition_name": c.competition_name,
            "country_id": c.country_id,
            "association_id": c.association_id,
            # weitere Felder nach Bedarf
        }
        for c in competitions
    ]

    if processed:
        await db.bulk_insert(
            "competitions",
            processed,
            "(competition_id) DO UPDATE SET competition_name = EXCLUDED.competition_name, updated_at = CURRENT_TIMESTAMP",
        )
