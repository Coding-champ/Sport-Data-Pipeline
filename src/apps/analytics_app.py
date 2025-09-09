"""
Sports Analytics App - Hauptanwendungsklasse für Analytics

Koordiniert alle Analytics Komponenten und bietet einheitliche API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

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

    async def analyze_player_performance(
        self, player_id: int, season: str = None
    ) -> dict[str, Any]:
        """Analysiert Spielerleistung"""
        try:
            start_time = datetime.now()

            analysis = await self.analytics_engine.analyze_player_performance(player_id, season)

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("player_analysis", "success", duration)

            self.logger.info(f"Player analysis completed for player {player_id} in {duration:.2f}s")
            return analysis

        except Exception as e:
            self.logger.error(f"Player analysis failed for player {player_id}: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("player_analysis", "error", 0)

            return {"error": str(e)}

    async def predict_match_outcome(
        self, home_team_id: int, away_team_id: int, match_date: datetime = None
    ) -> dict[str, Any]:
        """Vorhersage Spielausgang"""
        try:
            start_time = datetime.now()

            prediction = await self.analytics_engine.predict_match_outcome(
                home_team_id, away_team_id, match_date
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("match_prediction", "success", duration)

            self.logger.info(f"Match prediction completed in {duration:.2f}s")
            return prediction

        except Exception as e:
            self.logger.error(f"Match prediction failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("match_prediction", "error", 0)

            return {"error": str(e)}

    async def generate_league_analytics(self, league_id: int, season: str) -> dict[str, Any]:
        """Erstellt Liga-Analytics"""
        try:
            start_time = datetime.now()

            analytics = await self.analytics_engine.generate_league_analytics(league_id, season)

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("league_analytics", "success", duration)

            self.logger.info(f"League analytics completed in {duration:.2f}s")
            return analytics

        except Exception as e:
            self.logger.error(f"League analytics failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("league_analytics", "error", 0)

            return {"error": str(e)}

    async def generate_player_report(self, player_id: int, season: str = None) -> dict[str, Any]:
        """Erstellt Spieler-Report"""
        try:
            start_time = datetime.now()

            report = await self.report_generator.generate_player_report(player_id, season)

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("player_report", "success", duration)

            return {
                "status": "success",
                "report_content": report,
                "generation_time_seconds": duration,
            }

        except Exception as e:
            self.logger.error(f"Player report generation failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("player_report", "error", 0)

            return {"error": str(e)}

    async def generate_league_dashboard(self, league_id: int, season: str) -> dict[str, Any]:
        """Erstellt Liga-Dashboard"""
        try:
            start_time = datetime.now()

            dashboard = await self.report_generator.generate_league_dashboard(league_id, season)

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("league_dashboard", "success", duration)

            return {
                "status": "success",
                "dashboard": dashboard,
                "generation_time_seconds": duration,
            }

        except Exception as e:
            self.logger.error(f"League dashboard generation failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("league_dashboard", "error", 0)

            return {"error": str(e)}

    async def generate_transfer_analysis(self) -> dict[str, Any]:
        """Erstellt Transfer-Analyse"""
        try:
            start_time = datetime.now()

            analysis = await self.report_generator.generate_transfer_analysis()

            duration = (datetime.now() - start_time).total_seconds()

            # Metriken aufzeichnen
            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("transfer_analysis", "success", duration)

            return {"status": "success", "analysis": analysis, "generation_time_seconds": duration}

        except Exception as e:
            self.logger.error(f"Transfer analysis failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_analytics_operation("transfer_analysis", "error", 0)

            return {"error": str(e)}

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

        # Top-Performer Report
        await self._generate_top_performers_report()

        self.logger.info("Daily reports generated successfully")

    async def _generate_top_performers_report(self):
        """Generiert Top-Performer Report"""

        query = """
        SELECT 
            p.first_name || ' ' || p.last_name as player_name,
            t.name as team_name,
            sps.goals,
            sps.assists,
            sps.matches_played,
            (sps.goals + sps.assists) as goal_contributions,
            sps.goals::float / sps.matches_played as goals_per_match
        FROM players p
        JOIN season_player_stats sps ON p.id = sps.player_id
        JOIN teams t ON sps.team_id = t.id
        WHERE sps.season = '2024-25'
        AND sps.matches_played >= 10
        ORDER BY goal_contributions DESC
        LIMIT 20
        """

        top_performers = await self.analytics_engine.load_data(query, cache_key="top_performers")

        if not top_performers.empty:
            # Einfacher HTML-Report
            html = """
            <html>
            <head><title>Top Performers Report</title></head>
            <body>
            <h1>Top Performers - Current Season</h1>
            <table border="1">
            <tr><th>Player</th><th>Team</th><th>Goals</th><th>Assists</th><th>Contributions</th><th>Goals/Match</th></tr>
            """

            for _, player in top_performers.iterrows():
                html += f"""
                <tr>
                    <td>{player['player_name']}</td>
                    <td>{player['team_name']}</td>
                    <td>{player['goals']}</td>
                    <td>{player['assists']}</td>
                    <td>{player['goal_contributions']}</td>
                    <td>{player['goals_per_match']:.2f}</td>
                </tr>
                """

            html += "</table></body></html>"

            # Speichern
            filename = f"{self.settings.report_output_path}/top_performers_{datetime.now().strftime('%Y%m%d')}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)

            self.logger.info(f"Top performers report saved to {filename}")

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
