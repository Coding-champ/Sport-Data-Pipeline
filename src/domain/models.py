"""
Domain models for validated sports data using Pydantic.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Union, Optional

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, field_validator

Number = Union[int, float]

# --- Spielbetrieb, Ereignisse, Statistiken, Transfers, Odds, Trophäen, Mappings ---

class MatchResultTable(BaseModel):
    match_id: int
    # weitere Felder nach Bedarf

class Referee(BaseModel):
    referee_id: Optional[int] = None
    # weitere Felder nach Bedarf

class MatchOfficial(BaseModel):
    match_id: int
    referee_id: int
    role: str

class MatchLineupEntry(BaseModel):
    match_id: int
    team_id: int
    player_id: int
    # weitere Felder nach Bedarf

class EventTypeLookup(BaseModel):
    event_type_id: Optional[int] = None
    event_type: str
    event_subtype: Optional[str] = None

class EventQualifierLookup(BaseModel):
    qualifier_id: Optional[int] = None
    name: str

class MatchEvent(BaseModel):
    event_id: Optional[int] = None
    match_id: int
    # weitere Felder nach Bedarf

class MatchOdd(BaseModel):
    odd_id: Optional[int] = None
    match_id: int
    bookmaker_id: int
    market_id: int
    outcome_id: int
    price_type: str
    price: float
    timestamp: Optional[AwareDatetime] = None

class StandingsTable(BaseModel):
    standings_id: Optional[int] = None
    # weitere Felder nach Bedarf

class StandingRow(BaseModel):
    standings_id: int
    team_id: int
    # weitere Felder nach Bedarf

class Trophy(BaseModel):
    trophy_id: Optional[int] = None
    trophy_name: str
    picture_url: Optional[HttpUrl] = None

class TrophyWinner(BaseModel):
    trophy_winner_id: Optional[int] = None
    trophy_id: int
    season_id: Optional[int] = None
    team_id: Optional[int] = None

class TeamMatchStats(BaseModel):
    team_match_stats_id: Optional[int] = None
    match_id: int
    team_id: int
    data_provider: Optional[str] = None
    # weitere Felder nach Bedarf

class PlayerMatchStats(BaseModel):
    player_match_stats_id: Optional[int] = None
    match_id: int
    player_id: int
    data_provider: Optional[str] = None
    # weitere Felder nach Bedarf

class GoalkeeperMatchStats(BaseModel):
    goalkeeper_match_stats_id: Optional[int] = None
    match_id: int
    player_id: int
    data_provider: Optional[str] = None
    # weitere Felder nach Bedarf

class ShotEvent(BaseModel):
    shot_event_id: Optional[int] = None
    match_id: int
    # weitere Felder nach Bedarf

class SeasonPlayerStats(BaseModel):
    id: Optional[int] = None
    player_id: int
    team_id: int
    competition_id: Optional[int] = None
    season: Optional[str] = None
    # weitere Felder nach Bedarf

class RefereeSeasonStats(BaseModel):
    referee_season_stats_id: Optional[int] = None
    referee_id: int
    # weitere Felder nach Bedarf

class PlayerMarketValue(BaseModel):
    player_market_value_id: Optional[int] = None
    player_id: int
    valuation_date: date
    # weitere Felder nach Bedarf

class PlayerNationalTeamSummary(BaseModel):
    player_national_team_summary_id: Optional[int] = None
    player_id: int
    team_id: int
    # weitere Felder nach Bedarf

class ExternalIdMap(BaseModel):
    external_id_map_id: Optional[int] = None
    data_provider: str
    entity_type: str
    external_id: str
    # weitere Felder nach Bedarf

class MappingReviewQueue(BaseModel):
    id: Optional[int] = None
    # weitere Felder nach Bedarf
# --- Wettbewerbs- und Saisonstrukturen ---

class Competition(BaseModel):
    competition_id: Optional[int] = None
    competition_name: str
    country_id: Optional[int] = None
    association_id: Optional[int] = None
    # weitere Felder nach Bedarf

class Season(BaseModel):
    season_id: Optional[int] = None
    competition_id: int
    label: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    season_type: Optional[str] = None

class CompetitionStage(BaseModel):
    stage_id: Optional[int] = None
    competition_id: int
    season_id: int
    stage_name: str
    leg: Optional[int] = None

class CompetitionTable(BaseModel):
    table_id: Optional[int] = None
    competition_id: int
    season_id: int
    team_id: int
    # weitere Felder nach Bedarf

class CompetitionGroup(BaseModel):
    group_id: Optional[int] = None
    competition_id: int
    season_id: int
    stage_id: Optional[int] = None
    group_name: str

class TeamSeason(BaseModel):
    team_season_id: Optional[int] = None
    team_id: int
    season_id: int
    # weitere Felder nach Bedarf

class SquadMember(BaseModel):
    team_season_id: int
    player_id: int

class TeamStaffAssignment(BaseModel):
    team_season_id: int
    staff_role: str
# --- Organisation & Personal ---

class PlayerAgent(BaseModel):
    agent_id: Optional[int] = None
    agent_name: str
    agency_id: Optional[int] = None
    country_id: Optional[int] = None
    source_url: Optional[HttpUrl] = None
    scraped_at: Optional[AwareDatetime] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

class Agency(BaseModel):
    agency_id: Optional[int] = None
    agency_name: str
    country_id: Optional[int] = None

class EquipmentSupplier(BaseModel):
    equipment_supplier_id: Optional[int] = None
    supplier_name: str
    country_id: Optional[int] = None
    official_website: Optional[HttpUrl] = None
    source_url: Optional[HttpUrl] = None
    scraped_at: Optional[AwareDatetime] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

class Coach(BaseModel):
    coach_id: Optional[int] = None
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    place_of_birth: Optional[int] = None
    nationality: Optional[int] = None
    source_url: Optional[HttpUrl] = None
    scraped_at: Optional[AwareDatetime] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

class AdministrativeStaff(BaseModel):
    administrative_staff_id: Optional[int] = None
    staff_role: Optional[str] = None
    department: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None
# --- Historisierungs- und Zuordnungsmodelle ---

class ClubNameHistory(BaseModel):
    club_name_history_id: Optional[int] = None
    club_id: int
    name_official: str
    name_short: Optional[str] = None
    nickname: Optional[str] = None
    valid_from: date
    valid_to: Optional[date] = None
    is_current: Optional[bool] = None

class VenueNameHistory(BaseModel):
    venue_name_history_id: Optional[int] = None
    venue_id: int
    venue_name: str
    valid_from: date
    valid_to: Optional[date] = None
    is_current: Optional[bool] = None

class ClubVenueTenancy(BaseModel):
    tenancy_id: Optional[int] = None
    club_id: int
    venue_id: int
    main_tenant: Optional[bool] = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class PlayerCountry(BaseModel):
    player_id: int
    country_id: int
    nationality_type: str

class PlayerPosition(BaseModel):
    player_id: int
    position_id: int
    is_primary_position: Optional[bool] = False

class PlayerCoachDevelopment(BaseModel):
    player_id: int
    coach_id: int

class PersonRelations(BaseModel):
    person_id: int
    related_person_id: int
    relation_type: str
# --- Lookup- und Stammdatenmodelle aus schema.sql ---

class City(BaseModel):
    city_id: Optional[int] = None
    city_name: str
    country_id: Optional[int] = None
    state_region: Optional[str] = None
    city_population: Optional[int] = None

class Association(BaseModel):
    association_id: Optional[int] = None
    association_name: str
    sport_id: Optional[int] = None
    is_national: Optional[bool] = True
    country_id: Optional[int] = None
    parent_association_id: Optional[int] = None

class PositionLookup(BaseModel):
    position_id: Optional[int] = None
    sport_id: Optional[int] = None
    code: str
    position_name: str
    position_group: Optional[str] = None
    sport_specific_data: Optional[dict] = None

class WeatherLookup(BaseModel):
    weather_id: Optional[int] = None
    condition: str

class Bookmaker(BaseModel):
    bookmaker_id: Optional[int] = None
    bookmaker_name: str
    country_id: Optional[int] = None
    website_url: Optional[HttpUrl] = None

class BettingMarket(BaseModel):
    market_id: Optional[int] = None
    sport_id: Optional[int] = None
    market_name: str

class BettingOutcome(BaseModel):
    outcome_id: Optional[int] = None
    market_id: int
    outcome_name: str

# Stammdaten-Modelle gemäß schema.sql
class Sport(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    created_at: Optional[AwareDatetime] = None

class Country(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    flag_url: Optional[HttpUrl] = None
    created_at: Optional[AwareDatetime] = None

class League(BaseModel):
    id: Optional[int] = None
    sport_id: Optional[int] = None
    country_id: Optional[int] = None
    name: str
    short_name: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    tier: Optional[int] = 1
    season_format: Optional[str] = None
    is_active: Optional[bool] = True
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None

class Club(BaseModel):
    id: Optional[int] = None
    sport_id: Optional[int] = None
    name: str
    short_name: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[int] = None
    founded_year: Optional[int] = None
    logo_url: Optional[HttpUrl] = None
    colors: Optional[dict] = None
    website: Optional[HttpUrl] = None
    is_active: Optional[bool] = True
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

class Venue(BaseModel):
    id: Optional[int] = None
    name: str
    city: Optional[str] = None
    country_id: Optional[int] = None
    capacity: Optional[int] = None
    surface: Optional[str] = None
    indoor: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[HttpUrl] = None
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None

class ClubsBundle(BaseModel):
    """Helper model for lists of clubs."""

    items: list[Club]

# --- Common / Shared Types ---

ID = Union[int, str]

# Team entspricht jetzt der Tabelle teams
class Team(BaseModel):
    id: Optional[int] = None
    sport_id: Optional[int] = None
    name: str
    short_name: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[int] = None
    founded_year: Optional[int] = None
    logo_url: Optional[HttpUrl] = None
    colors: Optional[dict] = None
    website: Optional[HttpUrl] = None
    is_active: Optional[bool] = True
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None


class Position(str, Enum):
    GK = "GK"
    DF = "DF"
    MF = "MF"
    FW = "FW"

class Footedness(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"

# Player entspricht jetzt der Tabelle players
class Player(BaseModel):
    id: Optional[int] = None
    sport_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    nationality: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: Optional[Footedness] = None
    photo_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = True
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

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

# Match entspricht jetzt der Tabelle matches
class Match(BaseModel):
    id: Optional[int] = None
    season_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    venue_id: Optional[int] = None
    match_date: Optional[AwareDatetime] = None
    status: Optional[MatchStatus] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    attendance: Optional[int] = None
    referee: Optional[str] = None
    weather_conditions: Optional[dict] = None
    match_stats: Optional[dict] = None
    external_ids: Optional[dict] = None
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

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

# Odds entspricht jetzt der Tabelle betting_odds
class Odds(BaseModel):
    id: Optional[int] = None
    match_id: Optional[int] = None
    bookmaker: str
    market_type: Optional[str] = None
    odds_data: Optional[dict] = None
    timestamp: Optional[AwareDatetime] = None
    created_at: Optional[AwareDatetime] = None

class EventType(str, Enum):
    GOAL = "goal"
    CARD = "card"
    SUBSTITUTION = "substitution"
    VAR = "var"
    OTHER = "other"

# Event (Beispielstruktur, ggf. anpassen)
class Event(BaseModel):
    id: Optional[int] = None
    match_id: Optional[int] = None
    minute: Optional[int] = None
    type: Optional[EventType] = None
    team_id: Optional[int] = None
    player_id: Optional[int] = None
    description: Optional[str] = None

class Fixture(BaseModel):
    id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    competition_id: Optional[int] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: Optional[str] = None
    url: Optional[HttpUrl] = None
    scraped_at: Optional[AwareDatetime] = None

class MatchRef(BaseModel):
    match_id: int
    home_club_id: int
    away_club_id: int
    scraped_at: Optional[AwareDatetime] = None

class ClubDTO(BaseModel):
    id: int
    name: Optional[str] = None
    competition_id: Optional[int] = None
    scraped_at: Optional[AwareDatetime] = None

class OddsQuote(BaseModel):
    bookmaker: str
    home_team_name: str
    away_team_name: str
    market_type: str = "1X2"
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    external_id: Optional[str] = None
    scraped_at: Optional[AwareDatetime] = None

class GenericRecord(BaseModel):
    scraper_name: str
    data: dict
    created_at: Optional[AwareDatetime] = None