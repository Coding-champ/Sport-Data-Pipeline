"""
FastAPI ASGI entry point for Uvicorn
Creates the FastAPI app with required dependencies
"""
# TODO: This entry point duplicates logic from src/api/main.py and imports a non-existent DataCollectionOrchestrator.
# TODO: Consider removing this file or delegating entirely to main.py to avoid drift and circular imports.

from src.core.config import Settings
from src.analytics.engine import AnalyticsEngine
from src.data_collection.orchestrator import DataCollectionOrchestrator  # TODO: This module does not exist; use SportsDataApp or ScrapingOrchestrator.
from src.api.main import create_fastapi_app

settings = Settings()
data_app = DataCollectionOrchestrator()
# TODO: Align AnalyticsEngine signature with main.py (it expects a db_manager). Pass a proper DatabaseManager if required.
analytics_app = AnalyticsEngine()

app = create_fastapi_app(settings, data_app, analytics_app)