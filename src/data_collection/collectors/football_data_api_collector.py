"""
Football-data.org API Collector
Sammelt Daten von der Football-data.org API
"""

from datetime import datetime
import aiohttp
from typing import Optional

from src.core.config import APIConfig
from .base import DataCollector, RateLimiter
from src.domain.models import Team, Player, Match


class FootballDataCollector(DataCollector):
    """Datensammler für Football-data.org API"""

    def __init__(self, db_manager, api_config: APIConfig):
        super().__init__("football_data", db_manager)
        self.api_config = api_config
        self.rate_limiter = RateLimiter(api_config.rate_limit)
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize async HTTP client."""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30.0)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def cleanup(self):
        """Cleanup async HTTP client."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Macht einen API Request mit Rate Limiting"""
        await self.rate_limiter.acquire()

        # Ensure session is initialized
        if not self.session or self.session.closed:
            await self.initialize()

        url = f"{self.api_config.base_url}{endpoint}"
        headers = self.api_config.headers.copy()

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            self.logger.error(f"API request failed: {url} - {e}")
            raise

    async def collect_teams(self, league_id: str = None) -> list[Team]:
        """Sammelt Teams von Football-data.org"""
        endpoint = f"/competitions/{league_id}/teams" if league_id else "/teams"
        data = await self._make_request(endpoint)

        teams = []
        for team_data in data.get("teams", []):
            # Map Football-data.org fields to Team model
            team = Team(
                team_id=str(team_data["id"]),
                name=team_data["name"],
                country=team_data.get("area", {}).get("name"),
                founded=team_data.get("founded"),
                # Add external_ids mapping for cross-reference
                external_ids={
                    "football_data": str(team_data["id"]),
                    "short_name": team_data.get("shortName", ""),
                    "tla": team_data.get("tla", "")  # Three Letter Acronym
                } if hasattr(Team, 'external_ids') else None
            )
            teams.append(team)

        return teams

    async def collect_players(self, team_id: str = None) -> list[Player]:
        """Sammelt Spieler von Football-data.org"""
        endpoint = f"/teams/{team_id}"
        data = await self._make_request(endpoint)

        players = []
        for player_data in data.get("squad", []):
            # Compose full name from available fields
            name_parts = []
            if player_data.get("name"):
                name_parts.append(player_data["name"])
            elif player_data.get("firstName") and player_data.get("lastName"):
                name_parts.extend([player_data["firstName"], player_data["lastName"]])
            
            full_name = " ".join(name_parts) if name_parts else "Unknown"
            
            # Map position if available
            position = player_data.get("position", "")
            
            player = Player(
                player_id=str(player_data["id"]),
                name=full_name,
                birth_date=(
                    datetime.fromisoformat(player_data["dateOfBirth"])
                    if player_data.get("dateOfBirth")
                    else None
                ),
                nationality=player_data.get("nationality"),
                position=position if position else None,
            )
            players.append(player)

        return players

    async def collect_matches(self, league_id: str, season: str) -> list[Match]:
        """Sammelt Matches von Football-data.org"""
        endpoint = f"/competitions/{league_id}/matches"
        params = {"season": season}
        data = await self._make_request(endpoint, params)

        matches = []
        for match_data in data.get("matches", []):
            # Map status to MatchStatus enum values
            status_mapping = {
                "SCHEDULED": "scheduled",
                "LIVE": "live", 
                "IN_PLAY": "live",
                "PAUSED": "live",
                "FINISHED": "finished",
                "POSTPONED": "postponed",
                "CANCELLED": "cancelled",
                "SUSPENDED": "suspended"
            }
            
            api_status = match_data.get("status", "SCHEDULED")
            mapped_status = status_mapping.get(api_status, "scheduled")
            
            match = Match(
                match_id=str(match_data["id"]),
                home_team_id=str(match_data["homeTeam"]["id"]),
                away_team_id=str(match_data["awayTeam"]["id"]),
                utc_datetime=datetime.fromisoformat(match_data["utcDate"].replace("Z", "+00:00")),
                status=mapped_status,
                competition=str(league_id),
                season=season,
                # Add venue and round if available
                venue=match_data.get("venue", {}).get("name") if match_data.get("venue") else None,
                round=match_data.get("matchday") or match_data.get("round", {}).get("name"),
            )
            matches.append(match)

        return matches

    async def collect_odds(self, match_id: str) -> list[dict]:
        """Football-data.org hat keine Odds - Placeholder"""
        return []