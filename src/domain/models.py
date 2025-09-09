"""
Domain models for validated sports data using Pydantic.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Union, Optional

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, field_validator

Number = Union[int, float]


class Club(BaseModel):
    """Validated Bundesliga club item.

    Notes:
    - stats is a free-form dict with German metric names as keys.
    - Values are coerced to numbers when possible (e.g., "85.1" -> 85.1).
    - url validated as HttpUrl.
    """

    club_id: Optional[int] = Field(default=None)
    club_name: str
    url: HttpUrl
    matchday: int = Field(ge=1)
    stats: dict[str, Number]

    @field_validator("stats", mode="before")
    @classmethod
    def coerce_stats_numbers(cls, v: Any) -> dict[str, Number]:
        # TODO: Use a tolerant coercion path for None/"" values instead of raising to avoid rejecting partial rows.
        if not isinstance(v, dict):
            raise ValueError("stats must be a dict")
        out: dict[str, Number] = {}
        for k, val in v.items():
            # Already numeric
            # FIX: isinstance does not accept union types (int | float) here; using tuple form instead.
            if isinstance(val, (int, float)):
                out[k] = val
                continue
            # Try to coerce numeric strings like "85.1" or "111"
            if isinstance(val, str):
                sval = val.strip().replace(",", ".")
                try:
                    if "." in sval:
                        out[k] = float(sval)
                    else:
                        out[k] = int(sval)
                    continue
                except Exception:
                    pass
            # Fallback: raise for unsupported types
            raise ValueError(f"Unsupported stats value for '{k}': {type(val).__name__}")
        return out


class ClubsBundle(BaseModel):
    """Helper model for lists of clubs."""

    items: list[Club]


# --- Common / Shared Types ---

ID = Union[int, str]


class Venue(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    capacity: Optional[int] = None


class Team(BaseModel):
    team_id: ID
    name: str
    country: Optional[str] = None
    league: Optional[str] = None
    season: Optional[str] = None
    founded: Optional[int] = Field(default=None, ge=1800, le=2100)
    venue: Optional[Venue] = None
    # TODO: Consider adding external_ids: dict[str,str] to align with DB schema.external_ids and scrapers.


class Position(str, Enum):
    GK = "GK"
    DF = "DF"
    MF = "MF"
    FW = "FW"


class Footedness(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class Player(BaseModel):
    player_id: ID
    name: str
    team_id: Optional[ID] = None
    nationality: Optional[str] = None
    position: Optional[Position] = None
    birth_date: Optional[date] = None
    height_cm: Optional[int] = Field(default=None, ge=120, le=230)
    weight_kg: Optional[float] = Field(default=None, ge=40, le=130)
    foot: Optional[Footedness] = None
    # TODO: Many collectors/scrapers produce first_name/last_name and external_ids; consider extending the model or adding a mapping layer.


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELED = "canceled"


class MatchResult(BaseModel):
    home_goals: Optional[int] = Field(default=None, ge=0)
    away_goals: Optional[int] = Field(default=None, ge=0)
    winner: Optional[str] = Field(default=None, description="home/away/draw")

    @field_validator("winner")
    @classmethod
    def validate_winner(cls, v: Optional[str], info):
        if v is None:
            return v
        if v not in {"home", "away", "draw"}:
            raise ValueError("winner must be one of home/away/draw")
        return v


class Match(BaseModel):
    match_id: ID
    competition: Optional[str] = None
    season: Optional[str] = None
    round: Optional[str] = None
    utc_datetime: Optional[AwareDatetime] = None
    home_team_id: ID
    away_team_id: ID
    venue: Optional[Venue] = None
    status: MatchStatus = MatchStatus.SCHEDULED
    result: Optional[MatchResult] = None
    # TODO: Consider adding external_ids and source_url to align with ingestion scripts.


class InjuryStatus(str, Enum):
    INJURED = "injured"
    DOUBTFUL = "doubtful"
    SUSPENDED = "suspended"
    RECOVERED = "recovered"


class Injury(BaseModel):
    player_id: ID
    team_id: Optional[ID] = None
    description: Optional[str] = None
    status: InjuryStatus
    start_date: Optional[date] = None
    expected_return: Optional[date] = None


class TransferType(str, Enum):
    PERMANENT = "permanent"
    LOAN = "loan"
    FREE = "free"


class Transfer(BaseModel):
    player_id: ID
    from_team_id: Optional[ID] = None
    to_team_id: Optional[ID] = None
    date: Optional[date] = None
    fee_eur: Optional[float] = Field(default=None, ge=0)
    type: Optional[TransferType] = None


class OddsProvider(BaseModel):
    name: str
    key: Optional[str] = None


class Market(str, Enum):
    MATCH_ODDS = "match_odds"
    OVER_UNDER = "over_under"
    BOTH_TEAMS_TO_SCORE = "btts"


class Selection(BaseModel):
    name: str  # e.g., "Home", "Draw", "Away", "Over 2.5"
    price: float = Field(ge=1.01)
    implied_prob: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("implied_prob", mode="before")
    @classmethod
    def calc_implied(cls, v, values):
        if v is not None:
            return v
        price = values.get("price")
        if isinstance(price, (int, float)) and price > 0:
            return 1.0 / float(price)
        return None


class Odds(BaseModel):
    match_id: ID
    provider: OddsProvider
    market: Market
    selections: list[Selection]
    ts: Optional[AwareDatetime] = None


class EventType(str, Enum):
    GOAL = "goal"
    CARD = "card"
    SUBSTITUTION = "substitution"
    VAR = "var"
    OTHER = "other"


class Event(BaseModel):
    match_id: ID
    minute: Optional[int] = Field(default=None, ge=0, le=130)
    type: EventType
    team_id: Optional[ID] = None
    player_id: Optional[ID] = None
    description: Optional[str] = None