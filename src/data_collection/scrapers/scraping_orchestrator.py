from typing import Optional
"""
Scraping Orchestrator für die Sport Data Pipeline

Koordiniert alle Web Scraping Aktivitäten und Scheduler.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from src.core.config import Settings
from src.domain.utils import to_scraped_data_rows
from src.data_collection.scrapers.base import BaseScraper
from src.database.manager import DatabaseManager
from src.database.services.matches import upsert_matches
from src.database.services.odds import upsert_odds
from src.database.services.players import upsert_players


class ScrapingOrchestrator:
    """Orchestriert alle Web Scraping Aktivitäten"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        self.db_manager = db_manager
        self.settings = settings
        self.scrapers = {}
        self.logger = logging.getLogger("scraping_orchestrator")

    def register_scraper(self, scraper: BaseScraper):
        """Registriert einen neuen Scraper"""
        self.scrapers[scraper.name] = scraper
        self.logger.info(f"Registered scraper: {scraper.name}")

    async def initialize_all(self):
        """Initialisiert alle Scraper"""
        for scraper in self.scrapers.values():
            try:
                await scraper.initialize()
                self.logger.info(f"Initialized scraper: {scraper.name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {scraper.name}: {e}")

    async def cleanup_all(self):
        """Räumt alle Scraper auf"""
        for scraper in self.scrapers.values():
            try:
                await scraper.cleanup()
            except Exception as e:
                self.logger.error(f"Cleanup failed for {scraper.name}: {e}")

    async def run_scraping_job(self, scraper_names: list[str] = None) -> dict[str, Any]:
        """Führt Scraping-Job aus"""
        scrapers_to_run = scraper_names or list(self.scrapers.keys())

        results = {}

        for scraper_name in scrapers_to_run:
            if scraper_name not in self.scrapers:
                self.logger.warning(f"Scraper {scraper_name} not found")
                continue

            scraper = self.scrapers[scraper_name]

            try:
                self.logger.info(f"Running scraper: {scraper_name}")
                start_time = datetime.now()

                data = await scraper.scrape_data()

                # Daten in DB speichern
                if data:
                    await self._save_scraped_data(scraper_name, data)
                    results[scraper_name] = {
                        "status": "success",
                        "items_scraped": len(data),
                        "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    }
                    self.logger.info(f"Scraped {len(data)} items from {scraper_name}")
                else:
                    results[scraper_name] = {
                        "status": "no_data",
                        "items_scraped": 0,
                        "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    }
                    self.logger.warning(f"No data scraped from {scraper_name}")

            except Exception as e:
                results[scraper_name] = {"status": "error", "error": str(e), "items_scraped": 0}
                self.logger.error(f"Scraping failed for {scraper_name}: {e}")

        return results

    async def _save_scraped_data(self, scraper_name: str, data: list[dict]):
        """Speichert gescrapte Daten"""
        # If database pool is not initialized, skip persistence gracefully
        if not getattr(self.db_manager, "pool", None):
            self.logger.info(
                "DB pool not initialized; skipping persistence for %s (%d items)",
                scraper_name,
                len(data) if data else 0,
            )
            return
        
        # Use configurable scraper routing from settings
        routing_type = self.settings.scraper_routing.get(scraper_name, "generic")
        
        if routing_type == "players":
            # Delegate to centralized DB service for players
            await upsert_players(self.db_manager, data)
        elif routing_type == "matches":
            # Delegate to centralized DB service for matches
            await upsert_matches(self.db_manager, data)
        elif routing_type == "odds":
            # Delegate to centralized DB service for odds
            await upsert_odds(self.db_manager, data)
        else:
            # Generic storage for new scrapers like 'fbref', 'courtside1891'
            await self._save_generic_data(scraper_name, data)

    async def _save_generic_data(self, scraper_name: str, data: list[dict]):
        """Speichert generische Scraper-Daten via typed DTO serializer"""
        if not data:
            return
        rows = to_scraped_data_rows(scraper_name, data)
        if rows:
            await self.db_manager.bulk_insert("scraped_data", rows)

    def _parse_market_value(self, value_str: str) -> Optional[float]:
        """Parst Marktwert-String zu Float"""
        if not value_str:
            return None

        try:
            # Entferne Währungssymbole und Einheiten
            clean_value = value_str.replace("€", "").replace("$", "").replace(",", "").strip()

            # Handle Millionen/Tausend Notationen
            if "Mio" in clean_value or "M" in clean_value:
                number = float(clean_value.replace("Mio", "").replace("M", "").strip())
                return number * 1000000
            elif "Tsd" in clean_value or "K" in clean_value:
                number = float(clean_value.replace("Tsd", "").replace("K", "").strip())
                return number * 1000
            else:
                return float(clean_value)

        except (ValueError, AttributeError):
            return None

    def _parse_age(self, age_str: str) -> Optional[int]:
        """Parst Alter-String zu Integer"""
        if not age_str:
            return None

        try:
            # Extrahiere Zahl aus String
            import re

            numbers = re.findall(r"\d+", age_str)
            if numbers:
                return int(numbers[0])
        except (ValueError, AttributeError):
            pass

        return None

    async def run_parallel_scraping(self, scraper_configs: list[dict]) -> dict[str, Any]:
        """Führt mehrere Scraper parallel aus"""
        tasks = []

        for config in scraper_configs:
            scraper_name = config["name"]
            if scraper_name in self.scrapers:
                task = asyncio.create_task(
                    self._run_single_scraper(scraper_name, config.get("params", {}))
                )
                tasks.append((scraper_name, task))

        results = {}

        # Warte auf alle Tasks
        for scraper_name, task in tasks:
            try:
                result = await task
                results[scraper_name] = result
            except Exception as e:
                results[scraper_name] = {"status": "error", "error": str(e)}
                self.logger.error(f"Parallel scraping failed for {scraper_name}: {e}")

        return results

    async def _run_single_scraper(self, scraper_name: str, params: dict) -> dict[str, Any]:
        """Führt einen einzelnen Scraper aus"""
        scraper = self.scrapers[scraper_name]
        start_time = datetime.now()

        try:
            # Spezielle Methoden je nach Scraper und Parametern
            if params.get("method") == "live_scores" and hasattr(scraper, "scrape_live_scores"):
                data = await scraper.scrape_live_scores()
            elif params.get("method") == "live_odds" and hasattr(scraper, "scrape_live_odds"):
                data = await scraper.scrape_live_odds()
            else:
                data = await scraper.scrape_data()

            if data:
                await self._save_scraped_data(scraper_name, data)

            return {
                "status": "success",
                "items_scraped": len(data) if data else 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

    async def get_scraping_statistics(self) -> dict[str, Any]:
        """Holt Scraping-Statistiken"""
        try:
            # Statistiken aus der Datenbank
            stats_query = """
            SELECT 
                'players' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM players
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            
            UNION ALL
            
            SELECT 
                'live_scores' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM live_scores
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            
            UNION ALL
            
            SELECT 
                'odds' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM odds
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """

            stats_data = await self.db_manager.execute_query(stats_query)

            statistics = {
                "scraper_count": len(self.scrapers),
                "active_scrapers": list(self.scrapers.keys()),
                "data_statistics": {},
            }

            for row in stats_data:
                statistics["data_statistics"][row["table_name"]] = {
                    "records_last_7_days": row["total_records"],
                    "last_update": row["last_update"].isoformat() if row["last_update"] else None,
                }

            return statistics

        except Exception as e:
            self.logger.error(f"Failed to get scraping statistics: {e}")
            return {"error": str(e)}


class ScrapingScheduler:
    """Scheduler für regelmäßige Scraping-Jobs"""

    def __init__(self, orchestrator: ScrapingOrchestrator):
        self.orchestrator = orchestrator
        self.logger = logging.getLogger("scraping_scheduler")
        self.running = False
        self.tasks = []

    async def start_schedule(self):
        """Startet den Scheduler"""
        self.running = True

        # Verschiedene Scheduling-Intervalle
        self.tasks = [
            asyncio.create_task(self._live_scores_loop()),
            asyncio.create_task(self._odds_loop()),
            asyncio.create_task(self._player_data_loop()),
        ]

        try:
            await asyncio.gather(*self.tasks)
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")
        finally:
            self.running = False

    async def _live_scores_loop(self):
        """Live-Score Updates"""
        while self.running:
            try:
                result = await self.orchestrator.run_scraping_job(["flashscore"])
                self.logger.debug(f"Live scores update: {result}")
                await asyncio.sleep(self.orchestrator.settings.scraping_live_scores_interval_seconds)
            except Exception as e:
                self.logger.error(f"Live scores loop error: {e}")
                await asyncio.sleep(self.orchestrator.settings.live_error_backoff_seconds)

    async def _odds_loop(self):
        """Odds Updates"""
        while self.running:
            try:
                result = await self.orchestrator.run_scraping_job(["odds"])
                self.logger.debug(f"Odds update: {result}")
                await asyncio.sleep(self.orchestrator.settings.scraping_odds_interval_seconds)
            except Exception as e:
                self.logger.error(f"Odds loop error: {e}")
                await asyncio.sleep(self.orchestrator.settings.regular_error_backoff_seconds)

    async def _player_data_loop(self):
        """Tägliche Player Updates"""
        while self.running:
            try:
                # Nur einmal täglich um 2:00 Uhr
                now = datetime.now()
                if (
                    now.hour == self.orchestrator.settings.player_daily_hour
                    and now.minute < self.orchestrator.settings.player_daily_window_minutes
                ):
                    result = await self.orchestrator.run_scraping_job(["transfermarkt"])
                    self.logger.info(f"Daily player update: {result}")
                await asyncio.sleep(
                    self.orchestrator.settings.scraping_player_daily_check_interval_seconds
                )
            except Exception as e:
                self.logger.error(f"Player data loop error: {e}")
                await asyncio.sleep(
                    self.orchestrator.settings.scraping_player_daily_check_interval_seconds
                )

    def stop(self):
        """Stoppt den Scheduler"""
        self.running = False
        for task in self.tasks:
            if not task.done():
                task.cancel()
        self.logger.info("Scraping scheduler stopped")

    async def run_manual_job(self, job_type: str, params: dict = None) -> dict[str, Any]:
        """Führt manuellen Scraping-Job aus"""
        params = params or {}

        if job_type == "live_scores":
            return await self.orchestrator.run_scraping_job(["flashscore"])
        elif job_type == "odds":
            return await self.orchestrator.run_scraping_job(["odds"])
        elif job_type == "player_data":
            return await self.orchestrator.run_scraping_job(["transfermarkt"])
        elif job_type == "all":
            return await self.orchestrator.run_scraping_job()
        else:
            return {"error": f"Unknown job type: {job_type}"}