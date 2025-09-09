"""
FastAPI ASGI entry point for Uvicorn
Creates the FastAPI app with required dependencies
"""

from src.core.config import Settings
from src.analytics.engine import AnalyticsEngine
from src.data_collection.orchestrator import DataCollectionOrchestrator
from src.api.main import create_fastapi_app

settings = Settings()
data_app = DataCollectionOrchestrator()
analytics_app = AnalyticsEngine()

app = create_fastapi_app(settings, data_app, analytics_app)
