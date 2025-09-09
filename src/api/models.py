"""
API Models
Pydantic Models für API Requests und Responses
"""

from datetime import datetime
from typing import Any, Optional, List

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard API Response Model"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class MatchPredictionRequest(BaseModel):
    """Request model for match prediction"""

    home_team_id: int
    away_team_id: int
    match_date: Optional[datetime] = None
    season: Optional[str] = None


class PlayerAnalysisRequest(BaseModel):
    """Request model for player analysis"""

    player_id: int
    season: Optional[str] = None
    include_predictions: bool = False


class TeamStatsRequest(BaseModel):
    """Request model for team statistics"""

    team_id: int
    season: str
    include_players: bool = False


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    timestamp: datetime
    database: Optional[str] = None
    redis: Optional[str] = None
    services: Optional[dict[str, str]] = None


class DataCollectionRequest(BaseModel):
    """Request model for data collection"""

    league_id: str
    season: str
    collectors: Optional[List[str]] = None
    force_refresh: bool = False
