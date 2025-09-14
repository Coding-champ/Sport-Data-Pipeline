from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Dict, List

from src.domain.models import GenericRecord

def is_pydantic_model(obj: Any) -> bool:
    try:
        from pydantic import BaseModel
        return isinstance(obj, BaseModel)
    except Exception:
        return False

def serialize_item(item: Any) -> dict:
    """Convert a Pydantic model or plain dict to a serializable dict (for JSON or DB persistence)."""
    if is_pydantic_model(item):
        return item.dict()
    if isinstance(item, dict):
        return item
    return {"value": str(item)}

def to_scraped_data_rows(scraper_name: str, items: Sequence[Any]) -> List[Dict[str, Any]]:
    """Standardize generic persistence rows for 'scraped_data' table."""
    rows: List[Dict[str, Any]] = []
    now = datetime.utcnow()
    for it in items:
        if isinstance(it, GenericRecord):
            rows.append({
                "scraper_name": it.scraper_name or scraper_name,
                "data": json_dumps_safe(serialize_item(it.data)),
                "created_at": it.created_at or now,
            })
        else:
            rows.append({
                "scraper_name": scraper_name,
                "data": json_dumps_safe(serialize_item(it)),
                "created_at": now,
            })
    return rows

def json_dumps_safe(obj: Any) -> str:
    import json
    from datetime import date, datetime
    def default(o: Any):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if is_pydantic_model(o):
            return o.dict()
        return str(o)
    return json.dumps(obj, default=default, ensure_ascii=False)
