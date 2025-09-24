from __future__ import annotations
from enum import Enum

class Source(str, Enum):
    FBREF = "fbref"
    SOFASCORE = "sofascore"
    TRANSFERMARKT = "transfermarkt"
    BUNDESLIGA = "bundesliga"
    BET365 = "bet365"
    FLASHCORE = "flashscore"
    COURTSIDE1891 = "courtside1891"
    ODDS = "odds"

ALL_SOURCES: set[str] = {s.value for s in Source}

ALIASES: dict[str, str] = {
    # common short-hands
    "tm": Source.TRANSFERMARKT.value,
    "fs": Source.FLASHCORE.value,
    "fb": Source.FBREF.value,
}

def normalize_source(value: str | Source) -> str:
    """
    Normalize a source identifier to the canonical lowercase value.
    Raises ValueError for unknown sources.
    """
    if isinstance(value, Source):
        return value.value
    v = (value or "").strip().lower()
    v = ALIASES.get(v, v)
    if v not in ALL_SOURCES:
        allowed = ", ".join(sorted(ALL_SOURCES))
        raise ValueError(f"Unknown source '{value}'. Allowed: {allowed}")
    return v
