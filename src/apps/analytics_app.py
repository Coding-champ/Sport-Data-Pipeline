"""
Sports Analytics App - Hauptanwendungsklasse für Analytics

Koordiniert alle Analytics Komponenten und bietet einheitliche API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine, TypeVar, cast, Optional

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

from ..analytics import AnalyticsEngine, ReportGenerator
from ..core.config import Settings
from ..database.manager import DatabaseManager
from ..monitoring import HealthChecker, PrometheusMetrics, SystemMonitor


class SportsAnalyticsApp:
    """Hauptanwendung für Sport Analytics"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.db_manager = DatabaseManager()
        self.analytics_engine = AnalyticsEngine(self.db_manager, self.settings)
        self.report_generator = ReportGenerator(self.analytics_engine, self.settings)

        # Monitoring
        self.metrics = PrometheusMetrics(self.settings, self.db_manager)
        self.health_checker = HealthChecker(self.settings, self.db_manager)
        self.system_monitor = SystemMonitor(self.settings)

        # Logger (configured globally in main.py)
        self.logger = logging.getLogger("analytics_app")

    # Per-app logging is configured centrally; no local setup here

    async def initialize(self):
        """Initialisiert die Analytics App"""
        try:
            self.logger.info("Initializing Sports Analytics App...")

            # Database initialisieren
            await self.db_manager.initialize()

            # Analytics Engine initialisieren
            await self.analytics_engine.initialize()

            # Monitoring server is started centrally in main.py; do not start here

            self.logger.info("Sports Analytics App initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Analytics App: {e}")
            raise

    # ------------------------- Internal helpers -------------------------
    def _timed(
        self,
    operation: str,
    log_success: Optional[str] = None,
    log_error: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator factory for timing + metrics around async operations.

        Parameters
        ----------
        operation: str
            Metric / operation key (e.g. "player_analysis").
        log_success: str | None
            Optional format string for success log. Can contain placeholders consumed via .format(**locals()).
        log_error: str | None
            Optional format string for error log.
        """

        def wrapper(fn: F) -> F:
            async def inner(*args, **kwargs):  # type: ignore[override]
                start_time = datetime.now()
                try:
                    result = await fn(*args, **kwargs)
                    duration = (datetime.now() - start_time).total_seconds()
                    if self.settings.enable_metrics:
                        self.metrics.record_analytics_operation(operation, "success", duration)
                    if log_success:
                        # Provide common locals
                        try:
                            self.logger.info(log_success.format(duration=duration, args=args, kwargs=kwargs))
                        except Exception:
                            self.logger.info(f"{operation} completed in {duration:.2f}s")
                    return result
                except Exception as e:  # noqa: BLE001
                    if self.settings.enable_metrics:
                        self.metrics.record_analytics_operation(operation, "error", 0)
                    if log_error:
                        try:
                            self.logger.error(log_error.format(error=e, args=args, kwargs=kwargs))
                        except Exception:
                            self.logger.error(f"{operation} failed: {e}")
                    else:
                        self.logger.error(f"{operation} failed: {e}")
                    return {"error": str(e)}

            return cast(F, inner)

        return wrapper

    async def analyze_player_performance(self, player_id: int, season: Optional[str] = None) -> dict[str, Any]:  # type: ignore[override]
        """Analyze single player performance (simplified, not using timing decorator for Py3.9 compat)."""
        return await self.analytics_engine.analyze_player_performance(player_id, season)

    @_timed("match_prediction", log_success="Match prediction completed in {duration:.2f}s")
    async def predict_match_outcome(
    self, home_team_id: int, away_team_id: int, match_date: Optional[datetime] = None
    ) -> dict[str, Any]:  # type: ignore[override]
        return await self.analytics_engine.predict_match_outcome(
            home_team_id, away_team_id, match_date
        )

    @_timed(
        "league_analytics", log_success="League analytics completed in {duration:.2f}s"
    )
    async def generate_league_analytics(self, league_id: int, season: str) -> dict[str, Any]:  # type: ignore[override]
        return await self.analytics_engine.generate_league_analytics(league_id, season)

    @_timed("player_report")
    async def generate_player_report(self, player_id: int, season: Optional[str] = None) -> dict[str, Any]:  # type: ignore[override]
        report = await self.report_generator.generate_player_report(player_id, season)
        return {
            "status": "success",
            "report_content": report,
        }

    @_timed("league_dashboard")
    async def generate_league_dashboard(self, league_id: int, season: str) -> dict[str, Any]:  # type: ignore[override]
        dashboard = await self.report_generator.generate_league_dashboard(league_id, season)
        return {
            "status": "success",
            "dashboard": dashboard,
        }

    @_timed("transfer_analysis")
    async def generate_transfer_analysis(self) -> dict[str, Any]:  # type: ignore[override]
        analysis = await self.report_generator.generate_transfer_analysis()
        return {"status": "success", "analysis": analysis}

    async def run_daily_analytics(self) -> dict[str, Any]:
        """Führt tägliche Analytics-Routine aus"""
        try:
            self.logger.info("Starting daily analytics routine...")
            start_time = datetime.now()

            results = {
                "status": "completed",
                "operations": {},
                "timestamp": datetime.now().isoformat(),
            }

            # 1. Model Updates
            try:
                await self._update_models()
                results["operations"]["model_update"] = "success"
            except Exception as e:
                results["operations"]["model_update"] = f"error: {str(e)}"

            # 2. Generate Reports
            try:
                await self._generate_daily_reports()
                results["operations"]["report_generation"] = "success"
            except Exception as e:
                results["operations"]["report_generation"] = f"error: {str(e)}"

            # 3. Transfer Analysis
            try:
                transfer_result = await self.generate_transfer_analysis()
                results["operations"]["transfer_analysis"] = (
                    "success"
                    if "error" not in transfer_result
                    else f"error: {transfer_result['error']}"
                )
            except Exception as e:
                results["operations"]["transfer_analysis"] = f"error: {str(e)}"

            # 4. Weekly Summary
            try:
                weekly_summary = await self.report_generator.generate_weekly_summary()
                results["operations"]["weekly_summary"] = (
                    "success"
                    if "error" not in weekly_summary
                    else f"error: {weekly_summary['error']}"
                )
            except Exception as e:
                results["operations"]["weekly_summary"] = f"error: {str(e)}"

            duration = (datetime.now() - start_time).total_seconds()
            results["duration_seconds"] = duration

            self.logger.info(f"Daily analytics routine completed in {duration:.2f}s")
            return results

        except Exception as e:
            self.logger.error(f"Daily analytics routine failed: {e}")
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    async def _update_models(self):
        """Aktualisiert ML-Modelle"""
        # Player Performance Model Training
        query = """
        SELECT 
            p.*,
            sps.*,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age
        FROM players p
        JOIN season_player_stats sps ON p.id = sps.player_id
        WHERE sps.matches_played >= 10
        """

        training_data = await self.analytics_engine.load_data(query, cache_key="training_data")

        if not training_data.empty:
            # Model trainieren
            result = self.analytics_engine.player_model.train(training_data, "goals")
            self.logger.info(f"Player model retrained with MSE: {result['mse']}")

            # Model speichern (vereinfacht)
            # In echter Anwendung würde joblib.dump verwendet
            self.logger.info("Player model saved")

    async def _generate_daily_reports(self):
        """Generiert tägliche Reports"""
        season = getattr(self.settings, "current_season", None) or datetime.now().strftime("%Y-%Y")
        await self.report_generator.generate_top_performers_report(season)
        self.logger.info("Daily reports generated successfully")

    async def get_analytics_summary(self) -> dict[str, Any]:
        """Holt Analytics Summary"""
        try:
            # Sammle verschiedene Statistiken
            summary = {
                "timestamp": datetime.now().isoformat(),
                "cache_stats": (
                    self.analytics_engine.cache.get_stats()
                    if hasattr(self.analytics_engine.cache, "get_stats")
                    else {}
                ),
                "model_info": {
                    "player_model_trained": hasattr(self.analytics_engine.player_model, "model")
                    and self.analytics_engine.player_model.model is not None,
                    "match_model_trained": hasattr(self.analytics_engine.match_model, "model")
                    and self.analytics_engine.match_model.model is not None,
                },
                "recent_operations": [],  # Würde aus Metriken geholt
            }

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get analytics summary: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """Räumt Ressourcen auf"""
        try:
            self.logger.info("Cleaning up Analytics App...")

            # Schließe Database
            if self.db_manager.pool:
                await self.db_manager.pool.close()

            self.logger.info("Analytics App cleanup completed")

        except Exception as e:
            self.logger.error(f"Analytics cleanup failed: {e}")


# Convenience Functions
async def create_analytics_app(settings: Settings = None) -> SportsAnalyticsApp:
    """Erstellt und initialisiert SportsAnalyticsApp"""
    app = SportsAnalyticsApp(settings)
    await app.initialize()
    return app


async def analyze_player_once(
    player_id: int, season: str = None, settings: Settings = None
) -> dict[str, Any]:
    """Führt einmalige Spieler-Analyse aus"""
    app = await create_analytics_app(settings)

    try:
        results = await app.analyze_player_performance(player_id, season)
        return results
    finally:
        await app.cleanup()


async def predict_match_once(
    home_team_id: int, away_team_id: int, match_date: datetime = None, settings: Settings = None
) -> dict[str, Any]:
    """Führt einmalige Match-Vorhersage aus"""
    app = await create_analytics_app(settings)

    try:
        results = await app.predict_match_outcome(home_team_id, away_team_id, match_date)
        return results
    finally:
        await app.cleanup()


# Removed standalone __main__ entry point; use project-level main.py
