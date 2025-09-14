
"""
Clubs API Endpoints
- Liefert Clubs aus verschiedenen Ligen (z.B. Bundesliga, Premier League, etc.)
"""

import json
import os
import time

from pathlib import Path
from typing import Any, Optional, Literal

from fastapi import APIRouter, HTTPException, Query

from src.api.models import APIResponse
from src.domain.models import Club

router = APIRouter()

# Default location can be overridden by env var

# Mapping von Liga zu JSON-Datei
_CLUBS_JSON_MAP = {
    "bundesliga": Path(__file__).resolve().parents[3] / "reports" / "bundesliga_clubs.json",
    "premierleague": Path(__file__).resolve().parents[3] / "reports" / "fbref" / "fbref_clubs_latest.json",
    # Weitere Ligen können hier ergänzt werden
}

def _get_json_path(league: str) -> Path:
    if league not in _CLUBS_JSON_MAP:
        raise ValueError(f"Unsupported league: {league}")
    return _CLUBS_JSON_MAP[league]



def _load_clubs(league: str) -> list[dict[str, Any]]:
    path = _get_json_path(league)
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        # fbref: clubs liegen unter "items"
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if not isinstance(data, list):
            raise ValueError("Invalid data format: expected a list of clubs")
        validated: list[dict[str, Any]] = []
        for item in data:
            try:
                club = Club(**item)
                validated.append(club.model_dump())
            except Exception as e:
                raise ValueError(f"Invalid club entry: {e}")
        return validated



@router.get("/clubs/{league}", response_model=APIResponse)
async def list_clubs(
    league: Literal["bundesliga", "premierleague"] = Query(..., description="Liga-Name, z.B. 'bundesliga', 'premierleague'"),
    matchday: Optional[int] = Query(default=None, ge=1, description="Optional filter by matchday"),
):
    """Listet alle Clubs einer Liga (z.B. Bundesliga, Premier League) mit optionalem Matchday-Filter."""
    t0 = time.time()
    try:
        clubs = _load_clubs(league)
        if matchday is not None:
            clubs = [c for c in clubs if (c or {}).get("matchday") == matchday]
        return APIResponse(success=True, data=clubs, execution_time_ms=(time.time() - t0) * 1000)
    except Exception as e:
        return APIResponse(success=False, error=str(e), execution_time_ms=(time.time() - t0) * 1000)



@router.get("/clubs/{league}/{club}", response_model=APIResponse)
async def get_club(
    league: Literal["bundesliga", "premierleague"] = Query(..., description="Liga-Name, z.B. 'bundesliga', 'premierleague'"),
    club: str = Query(..., description="Name oder Slug des Clubs"),
):
    """Gibt einen einzelnen Club einer Liga zurück (Name oder Slug, case-insensitive)."""
    t0 = time.time()
    try:
        clubs = _load_clubs(league)
        key = club.strip().lower()

        def slug(s: str) -> str:
            return (
                s.lower()
                .replace(" ", "-")
                .replace("ü", "ue")
                .replace("ö", "oe")
                .replace("ä", "ae")
                .replace("ß", "ss")
            )

        matches = [
            c
            for c in clubs
            if key in (c.get("club_name", "").lower()) or key in slug(c.get("club_name", ""))
        ]
        if not matches:
            # Try by url path
            matches = [c for c in clubs if key in (c.get("url", "").split("/")[-1].lower())]
        if not matches:
            raise HTTPException(status_code=404, detail=f"Club not found: {club}")
        return APIResponse(
            success=True, data=matches[0], execution_time_ms=(time.time() - t0) * 1000
        )
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(success=False, error=str(e), execution_time_ms=(time.time() - t0) * 1000)
