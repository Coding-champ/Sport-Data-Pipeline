from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Typed data transfer objects shared across layers


@dataclass
class Fixture:
    fixture_id: Optional[str]
    home_team_name: Optional[str]
    away_team_name: Optional[str]
    home_team_id: Optional[str] = None
    away_team_id: Optional[str] = None
    competition_name: Optional[str] = None
    competition_id: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: Optional[str] = None
    url: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MatchRef:
    match_id: str
    home_club_id: str
    away_club_id: str
    home_club_name: Optional[str] = None
    away_club_name: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Club:
    club_id: str
    name: Optional[str] = None
    competition_id: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OddsQuote:
    bookmaker: str
    home_team_name: str
    away_team_name: str
    market_type: str = "1X2"
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    external_id: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GenericRecord:
    scraper_name: str
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


def is_dataclass_instance(obj: Any) -> bool:
    try:
        return hasattr(obj, "__dataclass_fields__")
    except Exception:
        return False


def serialize_item(
    item: Union[Dict[str, Any], Fixture, MatchRef, Club, OddsQuote, GenericRecord],
) -> Dict[str, Any]:
    """Convert a DTO or plain dict to a serializable dict (for JSON or DB persistence)."""
    if is_dataclass_instance(item):
        return asdict(item)  # type: ignore[arg-type]
    if isinstance(item, dict):
        return item
    # Fallback: best-effort string conversion
    return {"value": str(item)}


def to_scraped_data_rows(
    scraper_name: str,
    items: Sequence[Union[Dict[str, Any], Fixture, MatchRef, Club, OddsQuote, GenericRecord]],
) -> List[Dict[str, Any]]:
    """Standardize generic persistence rows for 'scraped_data' table.

    Output schema:
    - scraper_name: str
    - data: JSON (as string)
    - created_at: timestamp
    """
    rows: List[Dict[str, Any]] = []
    now = datetime.utcnow()
    for it in items:
        if isinstance(it, GenericRecord):
            rows.append(
                {
                    "scraper_name": it.scraper_name or scraper_name,
                    "data": json_dumps_safe(serialize_item(it.data)),
                    "created_at": it.created_at or now,
                }
            )
        else:
            rows.append(
                {
                    "scraper_name": scraper_name,
                    "data": json_dumps_safe(serialize_item(it)),
                    "created_at": now,
                }
            )
    return rows


def json_dumps_safe(obj: Any) -> str:
    import json
    from datetime import date, datetime

    def default(o: Any):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if is_dataclass_instance(o):
            return asdict(o)
        return str(o)

    return json.dumps(obj, default=default, ensure_ascii=False)


