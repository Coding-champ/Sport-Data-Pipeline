"""
Base classes for data collectors in the Sport Data Pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import asyncio
import logging

class RateLimiter:
    """Token bucket rate limiter for API requests."""
    
    def __init__(self, rate_limit: int, time_window: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            rate_limit: Maximum number of requests per time window
            time_window: Time window in seconds (default 1.0 for per-second limiting)
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = rate_limit
        self.last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            # Refill tokens based on elapsed time
            time_passed = now - self.last_refill
            self.tokens = min(
                self.rate_limit,
                self.tokens + time_passed * (self.rate_limit / self.time_window)
            )
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            # Wait until we can get a token
            wait_time = (1 - self.tokens) * (self.time_window / self.rate_limit)
            await asyncio.sleep(wait_time)
            self.tokens = 0  # We'll consume the token we waited for

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