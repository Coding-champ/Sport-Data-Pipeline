"""
Database services for player-related persistence.
"""

from __future__ import annotations

from ..manager import DatabaseManager
from src.domain.models import Player


async def upsert_players(db: DatabaseManager, data: list[dict]):
    """Validiert und upsertet Player-Objekte in die 'players'-Tabelle.
    Erwartet eine Liste von dicts, die mit dem Player-Pydantic-Modell kompatibel sind.
    """
    if not data:
        return

    players = [Player(**item) for item in data]
    processed = [
        {
            "id": p.player_id if hasattr(p, "player_id") else None,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "birth_date": p.birth_date,
            "nationality": p.nationality,
            "height_cm": p.height_cm,
            "weight_kg": p.weight_kg,
            "preferred_foot": p.foot,
            "is_active": True,
            "external_ids": p.external_ids,
            "created_at": None,  # Optional: aus p übernehmen, falls vorhanden
            "updated_at": None,
        }
        for p in players
    ]

    if processed:
        await db.bulk_insert(
            "players",
            processed,
            "(first_name,last_name) DO UPDATE SET height_cm = EXCLUDED.height_cm, weight_kg = EXCLUDED.weight_kg, updated_at = CURRENT_TIMESTAMP",
        )



