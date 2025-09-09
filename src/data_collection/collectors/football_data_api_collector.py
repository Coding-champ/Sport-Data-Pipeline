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
        # TODO: Add an async HTTP client (e.g., aiohttp.ClientSession or httpx.AsyncClient) as self.session, and initialize/cleanup lifecycle.
        # TODO: Add a logger: self.logger = logging.getLogger('collector.football_data')

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Macht einen API Request mit Rate Limiting"""
        await self.rate_limiter.acquire()

        url = f"{self.api_config.base_url}{endpoint}"
        headers = self.api_config.headers.copy()

        try:
            # TODO: self.session is undefined. Initialize an async client (e.g., in an initialize() method) and close it on cleanup.
            async with self.session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            # TODO: self.logger is undefined. Add a logger to the base class or here.
            self.logger.error(f"API request failed: {url} - {e}")
            raise

    async def collect_teams(self, league_id: str = None) -> list[Team]:
        """Sammelt Teams von Football-data.org"""
        endpoint = f"/competitions/{league_id}/teams" if league_id else "/teams"
        data = await self._make_request(endpoint)

        teams = []
        for team_data in data.get("teams", []):
            # TODO: The Team model expects `team_id` and `name`, not external_id/short_name/city/founded_year.
            # TODO: Map fields accordingly and add external_ids if needed.
            team = Team(
                team_id=str(team_data["id"]),
                name=team_data["name"],
                country=team_data.get("area", {}).get("name"),
                founded=team_data.get("founded"),
            )
            teams.append(team)

        return teams

    async def collect_players(self, team_id: str = None) -> list[Player]:
        """Sammelt Spieler von Football-data.org"""
        endpoint = f"/teams/{team_id}"
        data = await self._make_request(endpoint)

        players = []
        for player_data in data.get("squad", []):
            # TODO: Player model has `name` not first/last name fields. Compose full name accordingly or extend the model.
            full_name = player_data.get("name") or ""
            player = Player(
                player_id=str(player_data["id"]),
                name=full_name,
                birth_date=(
                    datetime.fromisoformat(player_data["dateOfBirth"])
                    if player_data.get("dateOfBirth")
                    else None
                ),
                nationality=player_data.get("nationality"),
                # TODO: Map position to enum Position if possible.
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
            # TODO: Domain Match expects match_id, utc_datetime (aware), home/away team IDs, and status mapped to MatchStatus enum.
            match = Match(
                match_id=str(match_data["id"]),
                home_team_id=str(match_data["homeTeam"]["id"]),
                away_team_id=str(match_data["awayTeam"]["id"]),
                utc_datetime=datetime.fromisoformat(match_data["utcDate"].replace("Z", "+00:00")),
                status="finished" if match_data["status"] == "FINISHED" else "scheduled",
                competition=str(league_id),
                season=season,
            )
            matches.append(match)

        return matches

    async def collect_odds(self, match_id: str) -> list[dict]:
        """Football-data.org hat keine Odds - Placeholder"""
        return []