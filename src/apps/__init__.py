"""
Applications Package für die Sport Data Pipeline

Enthält Hauptanwendungsklassen für verschiedene Komponenten.
"""

from .analytics_app import SportsAnalyticsApp
from .sports_data_app import SportsDataApp

__all__ = ["SportsDataApp", "SportsAnalyticsApp"]
