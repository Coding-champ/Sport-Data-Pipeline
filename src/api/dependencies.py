"""
API Dependencies
Dependency Injection für FastAPI
"""

from fastapi import Request

from src.analytics.engine import AnalyticsEngine
from src.database.manager import DatabaseManager


async def get_db_manager(request: Request) -> DatabaseManager:
    """Dependency für Database Manager (geteilt über App-Lebenszyklus)"""
    return request.app.state.db


async def get_analytics_engine(request: Request) -> AnalyticsEngine:
    """Dependency für Analytics Engine (nutzt geteilten DB-Manager)"""
    db_manager = request.app.state.db
    return AnalyticsEngine(db_manager)
