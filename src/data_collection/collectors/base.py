"""
Base classes for data collectors in the Sport Data Pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import asyncio
import logging

class RateLimiter:
    """Simple async rate limiter."""
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self._lock = asyncio.Semaphore(rate_limit)

    async def acquire(self):
        # TODO: This is a concurrency limiter, not a true rate limiter. Replace with a token bucket/leaky bucket to enforce N requests per time window.
        await self._lock.acquire()
        await asyncio.sleep(1 / self.rate_limit)
        self._lock.release()

class DataCollector(ABC):
    """Abstract base class for all data collectors."""
    def __init__(self, name: str, db_manager: Any):
        self.name = name
        self.db_manager = db_manager
        self.logger = logging.getLogger(f'collector.{name}')

    @abstractmethod
    async def collect_teams(self, league_id: Optional[str] = None) -> List[Any]:
        """Collect teams for a league.
        
        Args:
            league_id: Optional league identifier. If None, collect all teams.
            
        Returns:
            List of team objects or dictionaries.
        """
        pass

    @abstractmethod
    async def collect_players(self, team_id: Optional[str] = None) -> List[Any]:
        """Collect players for a team."""
        pass

    @abstractmethod
    async def collect_matches(self, league_id: str, season: str) -> List[Any]:
        """Collect matches for a given league and season."""
        pass

    @abstractmethod
    async def collect_odds(self, match_id: Optional[str] = None) -> List[dict]:
        """Collect odds for a match (if provider supports it)."""
        pass