"""
Data Collection Collectors Package

Enthält verschiedene Datensammler für APIs und externe Datenquellen.
"""

from .betfair_odds_collector import BetfairOddsCollector
from .football_data_api_collector import FootballDataCollector

__all__ = ["FootballDataCollector", "BetfairOddsCollector"]
