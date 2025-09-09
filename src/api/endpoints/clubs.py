"""
Clubs API Endpoints
- Serves Bundesliga clubs stats scraped into reports/bundesliga_clubs.json
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models import APIResponse
from src.domain.models import Club

router = APIRouter()

# Default location can be overridden by env var
_DEFAULT_JSON = Path(__file__).resolve().parents[3] / "reports" / "bundesliga_clubs.json"
_JSON_PATH = Path(os.getenv("BUNDESLIGA_CLUBS_JSON", str(_DEFAULT_JSON)))


def _load_clubs() -> list[dict[str, Any]]:
    if not _JSON_PATH.exists():
        raise FileNotFoundError(f"Not found: {_JSON_PATH}")
    with open(_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Invalid data format: expected a list of clubs")
        # Validate each item via Pydantic Club model
        validated: list[dict[str, Any]] = []
        for item in data:
            try:
                club = Club(**item)
                validated.append(club.model_dump())
            except Exception as e:
                raise ValueError(f"Invalid club entry: {e}")
        return validated


@router.get("/clubs/bundesliga", response_model=APIResponse)
async def list_bundesliga_clubs(
    matchday: Optional[int] = Query(default=None, ge=1, description="Optional filter by matchday"),
):
    """List all Bundesliga clubs with optional matchday filter."""
    t0 = time.time()
    try:
        clubs = _load_clubs()
        if matchday is not None:
            clubs = [c for c in clubs if (c or {}).get("matchday") == matchday]
        return APIResponse(success=True, data=clubs, execution_time_ms=(time.time() - t0) * 1000)
    except Exception as e:
        return APIResponse(success=False, error=str(e), execution_time_ms=(time.time() - t0) * 1000)


@router.get("/clubs/bundesliga/{club}", response_model=APIResponse)
async def get_bundesliga_club(
    club: str,
):
    """Get a single club by name (case-insensitive substring) or exact URL slug.
    Examples:
    - club=\"bayern\" matches \"FC Bayern München\"
    - club=\"fc-bayern-muenchen\" also matches via URL slug
    """
    t0 = time.time()
    try:
        clubs = _load_clubs()
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
