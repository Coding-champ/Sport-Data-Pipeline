"""
API Module
FastAPI Anwendung, Endpoints und Models
"""

from .dependencies import get_analytics_engine, get_db_manager
from .main import create_fastapi_app
from .models import APIResponse, MatchPredictionRequest, PlayerAnalysisRequest

__all__ = [
    "create_fastapi_app",
    "APIResponse",
    "MatchPredictionRequest",
    "PlayerAnalysisRequest",
    "get_db_manager",
    "get_analytics_engine",
]
