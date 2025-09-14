"""
Database services for venue-related persistence.
"""

from __future__ import annotations

from ..manager import DatabaseManager
from src.domain.models import Venue


async def upsert_venues(db: DatabaseManager, data: list[dict]):
    """Validiert und upsertet Venue-Objekte in die 'venues'-Tabelle.
    Erwartet eine Liste von dicts, die mit dem Venue-Pydantic-Modell kompatibel sind.
    """
    if not data:
        return

    venues = [Venue(**item) for item in data]
    processed = [
        {
            "id": v.id if hasattr(v, "id") else None,
            "name": v.name,
            "city": v.city,
            "country_id": v.country_id,
            "capacity": v.capacity,
            "surface": v.surface,
            "indoor": v.indoor,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "image_url": str(v.image_url) if v.image_url else None,
            "external_ids": v.external_ids,
            "created_at": None,  # Optional: aus v übernehmen, falls vorhanden
            "updated_at": None,
        }
        for v in venues
    ]

    if processed:
        await db.bulk_insert(
            "venues",
            processed,
            "(id) DO UPDATE SET capacity = EXCLUDED.capacity, updated_at = CURRENT_TIMESTAMP",
        )
