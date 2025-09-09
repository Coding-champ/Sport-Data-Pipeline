"""
Data Collection Scrapers Package

This package contains various scraper implementations.

Note: avoid importing scraper modules at package import time to keep imports
lightweight (important for unit tests that only need 'utils'). Import concrete
scrapers from their modules directly, e.g.:

    from src.data_collection.scrapers.flashscore_scraper import FlashscoreScraper
"""

__all__ = []
