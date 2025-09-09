"""
Base classes for data collectors in the Sport Data Pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import asyncio

class RateLimiter:
    """Simple async rate limiter."""
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self._lock = asyncio.Semaphore(rate_limit)

    async def acquire(self):
        await self._lock.acquire()
        await asyncio.sleep(1 / self.rate_limit)
        self._lock.release()

class DataCollector(ABC):
    """Abstract base class for all data collectors."""
    def __init__(self, name: str, db_manager: Any):
        self.name = name
        self.db_manager = db_manager

    @abstractmethod
    async def collect_teams(self, league_id: Optional[str] = None) -> List[Any]:
        pass

    @abstractmethod
    async def collect_players(self, team_id: Optional[str] = None) -> List[Any]:
        pass

    @abstractmethod
    async def collect_matches(self, league_id: str, season: str) -> List[Any]:
        pass

    @abstractmethod
    async def collect_odds(self, match_id: Optional[str] = None) -> List[dict]:
        pass
