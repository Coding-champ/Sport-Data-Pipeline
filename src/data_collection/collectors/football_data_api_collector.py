"""
Football-data.org API Collector
Sammelt Daten von der Football-data.org API
"""

from datetime import datetime

from src.core.config import APIConfig
from .base import DataCollector, RateLimiter
from src.domain.models import Team, Player, Match


class FootballDataCollector(DataCollector):
    """Datensammler für Football-data.org API"""

    def __init__(self, db_manager, api_config: APIConfig):
        super().__init__("football_data", db_manager)
        self.api_config = api_config
        self.rate_limiter = RateLimiter(api_config.rate_limit)

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Macht einen API Request mit Rate Limiting"""
        await self.rate_limiter.acquire()

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
            team = Team(
                external_id=str(team_data["id"]),
                name=team_data["name"],
                short_name=team_data.get("shortName"),
                city=team_data.get("area", {}).get("name"),
                founded_year=team_data.get("founded"),
                logo_url=team_data.get("crest"),
            )
            teams.append(team)

        return teams

    async def collect_players(self, team_id: str = None) -> list[Player]:
        """Sammelt Spieler von Football-data.org"""
        endpoint = f"/teams/{team_id}"
        data = await self._make_request(endpoint)

        players = []
        for player_data in data.get("squad", []):
            player = Player(
                external_id=str(player_data["id"]),
                first_name=player_data.get("name", "").split()[0],
                last_name=" ".join(player_data.get("name", "").split()[1:]),
                birth_date=(
                    datetime.fromisoformat(player_data["dateOfBirth"])
                    if player_data.get("dateOfBirth")
                    else None
                ),
                nationality=player_data.get("nationality"),
                position=player_data.get("position"),
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
            match = Match(
                external_id=str(match_data["id"]),
                home_team_id=str(match_data["homeTeam"]["id"]),
                away_team_id=str(match_data["awayTeam"]["id"]),
                match_date=datetime.fromisoformat(match_data["utcDate"].replace("Z", "+00:00")),
                status=match_data["status"],
                home_score=match_data["score"]["fullTime"]["home"],
                away_score=match_data["score"]["fullTime"]["away"],
                league_id=league_id,
                season=season,
            )
            matches.append(match)

        return matches

    async def collect_odds(self, match_id: str) -> list[dict]:
        """Football-data.org hat keine Odds - Placeholder"""
        return []
