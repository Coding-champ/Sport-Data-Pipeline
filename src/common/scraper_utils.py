"""Shared pure scraper helper functions (fixture parsing & normalization).

These utilities consolidate duplicated logic across multiple scraper modules:
- Score parsing / normalization
- Fixture completeness heuristics
- Status classification heuristics
- Game anchor normalization
- Unified fixture record shaping

All functions are intentionally side-effect free to ease testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Any
from datetime import datetime

# Keywords used to heuristically detect fixture/game related JSON endpoints
FIXTURE_KEYWORDS: tuple[str, ...] = ("fixture", "game", "match", "schedule")


def looks_like_fixture_json_url(url: str) -> bool:
    """Return True if url likely points to fixture/game JSON (heuristic)."""
    u = (url or "").lower()
    return any(k in u for k in FIXTURE_KEYWORDS)


def parse_score_text(raw: str | None) -> tuple[Optional[int], Optional[int]]:
    """Parse a score like '2-1', '2:1', ' 2 - 1 ' into (home, away).
    Returns (None, None) if not parseable.
    """
    if not raw:
        return None, None
    t = raw.strip().replace(":", "-")
    # remove whitespace
    t = "".join(t.split())
    parts = t.split("-")
    if len(parts) != 2:
        return None, None
    def to_int(s: str) -> Optional[int]:
        try:
            return int(s)
        except Exception:
            return None
    return to_int(parts[0]), to_int(parts[1])


def classify_match_status(text_time: str | None, css_classes: Sequence[str] | None) -> str:
    """Heuristic classification for match status (scheduled/live/finished).
    Mirrors logic used in Flashscore scraper; can be tuned per site.
    """
    time = (text_time or "").strip()
    classes = css_classes or []
    live_tokens = ["'", "HT", "1. HZ", "2. HZ", "ET", "PEN"]
    finished_tokens = ["FT", "AET"]
    if any("event__match--live" in c for c in classes) or any(tok in time for tok in live_tokens):
        return "live"
    if any(tok in time for tok in finished_tokens):
        return "finished"
    return "scheduled"


def is_incomplete_fixture(d: dict) -> bool:
    """Return True if fixture dict lacks essential team or score fields."""
    if not isinstance(d, dict):
        return True
    k = d.keys()
    # Need both team identifiers
    if not (("home" in k or "home_id" in k) and ("away" in k or "away_id" in k)):
        return True
    # If unified string score present -> OK
    if "score" in k and isinstance(d.get("score"), str):
        return False
    # If either individual score key present, require both
    if ("home_score" in k) ^ ("away_score" in k):  # xor -> only one present
        return True
    # If both present they are fine (even if None, caller can validate)
    if ("home_score" in k) and ("away_score" in k):
        return False
    # No score information at all
    return True


def extract_game_anchor_records(anchors: Iterable[dict]) -> list[dict]:
    """Normalize anchor-like dicts with id/url fields into consistent shape.
    Expected input items have 'url' and/or 'id'.
    """
    out: list[dict] = []
    for a in anchors:
        if not isinstance(a, dict):
            continue
        href = a.get("url") or a.get("id")
        if not href:
            continue
        clean = href.split("?")[0]
        out.append({
            "id": clean,
            "url": href,
            "timestamp": a.get("timestamp") or datetime.utcnow().isoformat(),
        })
    return out


def _to_score_string(home_score: Optional[int], away_score: Optional[int]) -> Optional[str]:
    try:
        if home_score is None or away_score is None:
            return None
        return f"{int(home_score)}-{int(away_score)}"
    except Exception:
        return None


def unify_fixture_records(items: list[dict]) -> list[dict]:
    """Convert mixed-shape fixture dicts into unified normalized structure.

    Output keys:
    - fixture_id
    - competition_id
    - competition_name
    - home_team_id
    - away_team_id
    - home_team_name
    - away_team_name
    - score (string or None)
    - url
    - timestamp (ISO)
    """
    unified: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        fixture_id = it.get("fixture_id") or it.get("id") or it.get("url")
        competition_id = it.get("competition_id")
        competition_name = it.get("competition_name") or it.get("competition")
        home_team_id = it.get("home_team_id") or it.get("home_id")
        away_team_id = it.get("away_team_id") or it.get("away_id")
        home_team_name = it.get("home_team_name") or it.get("home")
        away_team_name = it.get("away_team_name") or it.get("away")
        score = it.get("score")
        if not score:
            score = _to_score_string(it.get("home_score"), it.get("away_score"))
        url = it.get("url") or None
        timestamp = it.get("timestamp") or datetime.utcnow().isoformat()
        unified.append({
            "fixture_id": fixture_id,
            "competition_id": competition_id,
            "competition_name": competition_name,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "score": score,
            "url": url,
            "timestamp": timestamp,
        })
    return unified

__all__ = [
    "looks_like_fixture_json_url",
    "parse_score_text",
    "classify_match_status",
    "is_incomplete_fixture",
    "extract_game_anchor_records",
    "unify_fixture_records",
]
