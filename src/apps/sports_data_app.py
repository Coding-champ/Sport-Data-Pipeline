"""
Sports Data App - Hauptanwendungsklasse für Data Collection

Koordiniert alle Data Collection Komponenten und bietet einheitliche API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..core.config import Settings
from ..data_collection.collectors import BetfairOddsCollector, FootballDataCollector
## from ..data_collection.orchestrator import DataCollectionOrchestrator  # Removed: file does not exist
from ..data_collection.scrapers.flashscore_scraper import FlashscoreScraper
from ..data_collection.scrapers.scraping_orchestrator import ScrapingOrchestrator, ScrapingScheduler
from ..data_collection.scrapers.transfermarkt_scraper import TransfermarktScraper
from ..data_collection.scrapers.bet365_scraper import Bet365Scraper
from ..database.manager import DatabaseManager
from ..monitoring import HealthChecker, PrometheusMetrics, SystemMonitor


class SportsDataApp:
    """Hauptanwendung für Sport Data Collection"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.db_manager = DatabaseManager()
    # self.data_orchestrator = DataCollectionOrchestrator(self.db_manager, self.settings)  # Disabled: class not defined
        self.scraping_orchestrator = ScrapingOrchestrator(self.db_manager, self.settings)
        self.scraping_scheduler = ScrapingScheduler(self.scraping_orchestrator)

        # Monitoring
        self.metrics = PrometheusMetrics(self.settings, self.db_manager)
        self.health_checker = HealthChecker(self.settings, self.db_manager)
        self.system_monitor = SystemMonitor(self.settings)

        # Logger (configured globally in main.py)
        self.logger = logging.getLogger("sports_data_app")

    # Per-app logging is configured centrally; no local setup here

    async def initialize(self):
        """Initialisiert die Anwendung"""
        try:
            self.logger.info("Initializing Sports Data App...")

            # Database initialisieren
            await self.db_manager.initialize()

            # Collectors registrieren
            await self._register_collectors()

            # Scrapers registrieren
            await self._register_scrapers()

            # Monitoring server is started centrally in main.py; do not start here

            self.logger.info("Sports Data App initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Sports Data App: {e}")
            raise

    async def _register_collectors(self):
        """Registriert Data Collectors"""
        try:
            # Football Data API Collector
            if self.settings.football_data_api_key:
                football_collector = FootballDataCollector(self.db_manager, self.settings)
                self.data_orchestrator.register_collector(football_collector)
                self.logger.info("Registered FootballDataCollector")

            # Betfair Odds Collector
            if self.settings.betfair_app_key:
                from ..data_collection.collectors.betfair_odds_collector import BetfairConfig

                betfair_config = BetfairConfig(
                    app_key=self.settings.betfair_app_key,
                    username=self.settings.betfair_username,
                    password=self.settings.betfair_password,
                    cert_file=self.settings.betfair_cert_file,
                    key_file=self.settings.betfair_key_file,
                )

                betfair_collector = BetfairOddsCollector(self.db_manager, betfair_config)
                self.data_orchestrator.register_collector(betfair_collector)
                self.logger.info("Registered BetfairOddsCollector")

            # Initialisiere alle Collectors
            await self.data_orchestrator.initialize_all()

        except Exception as e:
            self.logger.error(f"Failed to register collectors: {e}")
            raise

    async def _register_scrapers(self):
        """Registriert Web Scrapers"""
        try:
            # Transfermarkt Scraper
            transfermarkt_scraper = TransfermarktScraper(self.db_manager, self.settings)
            self.scraping_orchestrator.register_scraper(transfermarkt_scraper)

            # Flashscore Scraper
            flashscore_scraper = FlashscoreScraper(self.db_manager, self.settings)
            self.scraping_orchestrator.register_scraper(flashscore_scraper)

            # Odds Scraper (optional in collection_once)
            if not (
                self.settings.run_mode == "collection_once"
                and not getattr(self.settings, "enable_odds_in_collection_once", False)
            ):
                odds_scraper = Bet365Scraper(self.db_manager, self.settings)
                self.scraping_orchestrator.register_scraper(odds_scraper)
            else:
                self.logger.info(
                    "Skipping OddsScraper registration for collection_once (disabled by setting)"
                )

            # Initialisiere alle Scrapers
            await self.scraping_orchestrator.initialize_all()

            self.logger.info("Registered and initialized all scrapers")

        except Exception as e:
            self.logger.error(f"Failed to register scrapers: {e}")
            raise

    async def run_data_collection(self, collectors: list[str] = None) -> dict[str, Any]:
        """Führt Data Collection aus"""
        try:
            self.logger.info("Starting data collection...")
            start_time = datetime.now()

            # Sammle Daten von API Collectors
            collection_results = await self.data_orchestrator.collect_all_data(collectors)

            # Sammle Daten von Scrapers
            scraping_results = await self.scraping_orchestrator.run_scraping_job()

            duration = (datetime.now() - start_time).total_seconds()

            results = {
                "status": "completed",
                "duration_seconds": duration,
                "collection_results": collection_results,
                "scraping_results": scraping_results,
                "timestamp": datetime.now().isoformat(),
            }

            # Metriken aufzeichnen (robust gegen Listen/Dictionaries)
            if self.settings.enable_metrics:

                def iter_result_items(res):
                    if isinstance(res, dict):
                        return list(res.values())
                    if isinstance(res, list):
                        return res
                    return []

                total_items = 0
                for r in iter_result_items(collection_results):
                    if isinstance(r, dict):
                        total_items += int(r.get("items_collected", 0))
                for r in iter_result_items(scraping_results):
                    if isinstance(r, dict):
                        total_items += int(r.get("items_scraped", 0))

                self.metrics.record_data_collection(
                    "all_collectors", "success", duration, total_items
                )

            self.logger.info(f"Data collection completed in {duration:.2f}s")
            return results

        except Exception as e:
            self.logger.error(f"Data collection failed: {e}")

            if self.settings.enable_metrics:
                self.metrics.record_data_collection("all_collectors", "error", 0)

            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    async def run_scheduled_collection(self):
        """Führt geplante Data Collection aus"""
        try:
            # Verwende einen einzigen, zentralen Scheduler für Scraping-Jobs
            await self.scraping_scheduler.start_schedule()
        except Exception as e:
            self.logger.error(f"Scheduled collection failed: {e}")

    async def get_system_status(self) -> dict[str, Any]:
        """Holt System Status"""
        try:
            # Health Checks
            health_status = await self.health_checker.check_all_components()

            # System Metriken
            system_metrics = await self.system_monitor.collect_system_metrics()

            # Data Collection Status
            collection_stats = await self.data_orchestrator.get_collection_statistics()

            # Scraping Status
            scraping_stats = await self.scraping_orchestrator.get_scraping_statistics()

            return {
                "overall_status": health_status["overall_status"],
                "health": health_status,
                "system": system_metrics,
                "data_collection": collection_stats,
                "scraping": scraping_stats,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    async def cleanup(self):
        """Räumt Ressourcen auf"""
        try:
            self.logger.info("Cleaning up Sports Data App...")

            # Stoppe Scheduler
            self.scraping_scheduler.stop()

            # Räume Orchestrators auf
            await self.data_orchestrator.cleanup_all()
            await self.scraping_orchestrator.cleanup_all()

            # Schließe Database
            if self.db_manager.pool:
                await self.db_manager.pool.close()

            self.logger.info("Sports Data App cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Convenience Functions
async def create_sports_data_app(settings: Settings = None) -> SportsDataApp:
    """Erstellt und initialisiert SportsDataApp"""
    app = SportsDataApp(settings)
    await app.initialize()
    return app


async def run_data_collection_once(settings: Settings = None) -> dict[str, Any]:
    """Führt einmalige Data Collection aus"""
    app = await create_sports_data_app(settings)

    try:
        results = await app.run_data_collection()
        return results
    finally:
        await app.cleanup()


# Removed standalone __main__ entry point; use project-level main.py
