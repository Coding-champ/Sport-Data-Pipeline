# --- ASGI app instantiation for Uvicorn ---

from src.core.config import Settings
from src.apps.sports_data_app import SportsDataApp
from src.analytics.engine import AnalyticsEngine
from typing import Optional
from src.database.manager import DatabaseManager
from src.monitoring.prometheus_metrics import MetricsCollector, PrometheusMetrics
from contextlib import asynccontextmanager
from fastapi import FastAPI

"""
FastAPI Application Main
Hauptanwendung für die Sports Data API
"""

import logging
import time
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request, status, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse


from typing import Optional
from src.database.manager import DatabaseManager
from src.monitoring.prometheus_metrics import MetricsCollector, PrometheusMetrics

# TODO: Remove duplicate imports (FastAPI, asynccontextmanager, typing) to adhere to PEP8 and avoid confusion.


def create_fastapi_app(settings, data_app, analytics_app, *, db_manager: Optional[DatabaseManager] = None, metrics: Optional[PrometheusMetrics] = None):
    """Factory function to create the FastAPI app.

    Supports SAFE_MODE (env var FASTAPI_SAFE_MODE=1) to skip external dependencies
    like database/redis initialization for a quick startup check.
    """
    import os
    safe_mode = os.getenv("FASTAPI_SAFE_MODE", "0") == "1"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application Lifespan Management"""
        logger = logging.getLogger(__name__)
        logger.info("Starting Sports Data API")

        if not safe_mode:
            # Initialize Redis
            app.state.redis = redis.from_url(settings.redis_url)

            # Use injected DatabaseManager if provided, else create a local one
            app.state.db = db_manager or DatabaseManager()
            if not db_manager:
                try:
                    await app.state.db.initialize()
                except Exception:
                    logger.exception("Database initialization failed (non-safe mode)")
        else:
            logger.info("SAFE_MODE enabled: skipping Redis and DB initialization")
            app.state.redis = None
            app.state.db = None

        # (Defer scraper registration in SAFE_MODE to admin endpoint to avoid heavy imports.)
        if not safe_mode:
            try:
                orchestrator = getattr(data_app, "scraping_orchestrator", None)
                if orchestrator and not orchestrator.scrapers:
                    from src.data_collection.scrapers.transfermarkt_scraper import TransfermarktScraper
                    from src.data_collection.scrapers.flashscore_scraper import FlashscoreScraper
                    from src.data_collection.scrapers.bet365_scraper import Bet365Scraper
                    # TODO: These imports/modules may not exist in this repo snapshot; consider feature flags to guard registration.
                    orchestrator.register_scraper(TransfermarktScraper(data_app.db_manager, settings))
                    orchestrator.register_scraper(FlashscoreScraper(data_app.db_manager, settings))
                    orchestrator.register_scraper(Bet365Scraper(data_app.db_manager, settings))
                    await orchestrator.initialize_all()
            except Exception:
                logging.getLogger(__name__).exception("Failed non-safe scraper registration during startup")

        # Use injected PrometheusMetrics if provided, else create a local one
        if not safe_mode:
            app.state.metrics = metrics or PrometheusMetrics(settings, app.state.db)
            app.state.metrics_collector = MetricsCollector(app.state.metrics, interval=30)
            # Only start metrics server when this instance owns it (i.e., not injected)
            if not metrics and getattr(settings, "enable_metrics", True):
                try:
                    app.state.metrics.start_metrics_server(getattr(settings, "metrics_port", 8008))
                except Exception:
                    logger.exception("Failed to start Prometheus metrics server")
            # Start background metrics collection
            app.state._metrics_task = None
            try:
                import asyncio
                app.state._metrics_task = asyncio.create_task(
                    app.state.metrics_collector.start_collection()
                )
            except Exception:
                logger.exception("Failed to start metrics collector task")
        else:
            app.state.metrics = None
            app.state.metrics_collector = None

        logger.info("Application startup complete")
        yield

        # Shutdown
        logger.info("Shutting down application")
        # Stop metrics collector
        try:
            if getattr(app.state, "_metrics_task", None):
                app.state.metrics_collector.stop_collection()
                import asyncio

                await asyncio.sleep(0)  # let it exit
        except Exception:
            logger.exception("Failed to stop metrics collector")
        if not safe_mode and hasattr(app.state, "redis") and app.state.redis:
            await app.state.redis.close()

        # Close DatabaseManager only if we created it locally
        if not safe_mode and hasattr(app.state, "db") and app.state.db and not db_manager:
            await app.state.db.close()

    app = FastAPI(
        title="Sports Data Analytics API",
        description="Comprehensive sports data collection and analytics platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Make apps available to endpoints
    app.state.data_app = data_app
    app.state.analytics_app = analytics_app
    app.state.safe_mode = safe_mode
    # Scrapers are now ensured inside lifespan
    # Expose scraping orchestrator for admin endpoint
    if hasattr(data_app, 'scraping_orchestrator'):
        app.state.scraping_orchestrator = data_app.scraping_orchestrator

    # CORS Middleware (tighten in non-development)
    cors_origins = settings.cors_origins
    if getattr(settings, "environment", "development") != "development":
        cors_origins = [o for o in cors_origins if o != "*"] or []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Simple in-memory rate limit (per-IP) if enabled
    rate_limit_enabled = hasattr(settings, "rate_limit_requests_per_minute") and getattr(
        settings, "rate_limit_requests_per_minute", 0
    ) > 0
    if rate_limit_enabled:
        from collections import defaultdict
        from time import monotonic

        window_seconds = 60
        max_requests = int(getattr(settings, "rate_limit_requests_per_minute", 60))
        buckets: dict[str, list[float]] = defaultdict(list)

        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            now = monotonic()
            client_ip = request.client.host if request.client else "unknown"
            times = buckets[client_ip]
            # Drop outdated timestamps
            cutoff = now - window_seconds
            while times and times[0] < cutoff:
                times.pop(0)
            if len(times) >= max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Too many requests"},
                )
            times.append(now)
            return await call_next(request)

    @app.middleware("http")
    async def metrics_http_middleware(request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.time() - start
            try:
                status = str(getattr(response, "status_code", 500))
                method = request.method
                endpoint = request.url.path
                if hasattr(app.state, "metrics") and app.state.metrics:
                    app.state.metrics.record_api_request(
                        method=method, endpoint=endpoint, status=status, duration=duration
                    )
            except Exception:
                # Never break requests due to metrics errors
                pass

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint with API documentation"""
        return """
        <html>
            <head>
                <title>Sports Data API</title>
            </head>
            <body>
                <h1>Sports Data Analytics API</h1>
                <p>Welcome to the comprehensive sports data platform!</p>
                <ul>
                    <li><a href="/docs">API Documentation (Swagger)</a></li>
                    <li><a href="/health">Health Check</a></li>
                    <li><a href="/metrics">Prometheus Metrics</a></li>
                </ul>
            </body>
        </html>
        """

    @app.get("/health")
    async def health_check(x_api_key: Optional[str] = Header(default=None, convert_underscores=False)):
        """Basic health check endpoint"""
        # If an API key is configured, require it even for health in non-development

        if (
            getattr(settings, "api_key", None)
            and getattr(settings, "environment", "development") != "development"
            and x_api_key != settings.api_key
        ):
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        return {"status": "ok"}

    # Include aggregated API router
    from src.api.router import api_router
    app.include_router(api_router, prefix="/api/v1")

    return app

# --- Instantiate app and dependencies at the end, after all definitions ---

settings = Settings()
data_app = SportsDataApp(settings)
# Reuse the data_app's DB manager everywhere to avoid multiple instances
# TODO: Ensure AnalyticsEngine signature matches this usage; pass dependencies explicitly if needed.
analytics_app = AnalyticsEngine(data_app.db_manager)
app = create_fastapi_app(settings, data_app, analytics_app, db_manager=data_app.db_manager)