"""
Data Collection Orchestrator für die Sport Data Pipeline

Koordiniert alle API-basierten Data Collection Aktivitäten.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from src.core.config import Settings
from src.data_collection.collectors.base import DataCollector
from src.database.manager import DatabaseManager


class DataCollectionOrchestrator:
    """Orchestriert alle API-basierten Data Collection Aktivitäten"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        self.db_manager = db_manager
        self.settings = settings
        self.collectors = {}
        self.logger = logging.getLogger("data_collection_orchestrator")

    def register_collector(self, collector: DataCollector):
        """Registriert einen neuen Collector"""
        self.collectors[collector.name] = collector
        self.logger.info(f"Registered collector: {collector.name}")

    async def initialize_all(self):
        """Initialisiert alle Collectors"""
        for collector in self.collectors.values():
            try:
                if hasattr(collector, 'initialize'):
                    await collector.initialize()
                self.logger.info(f"Initialized collector: {collector.name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {collector.name}: {e}")

    async def cleanup_all(self):
        """Räumt alle Collectors auf"""
        for collector in self.collectors.values():
            try:
                if hasattr(collector, 'cleanup'):
                    await collector.cleanup()
            except Exception as e:
                self.logger.error(f"Cleanup failed for {collector.name}: {e}")

    async def collect_all_data(self, collector_names: list[str] = None) -> dict[str, Any]:
        """Führt Data Collection für alle oder spezifische Collectors aus"""
        collectors_to_run = collector_names or list(self.collectors.keys())

        results = {}

        for collector_name in collectors_to_run:
            if collector_name not in self.collectors:
                self.logger.warning(f"Collector {collector_name} not found")
                continue

            collector = self.collectors[collector_name]

            try:
                self.logger.info(f"Running collector: {collector_name}")
                start_time = datetime.now()

                # Collect different types of data based on collector capabilities
                collected_data = {
                    "teams": [],
                    "players": [],
                    "matches": [],
                    "odds": []
                }

                # Collect teams
                try:
                    teams = await collector.collect_teams()
                    collected_data["teams"] = teams
                except Exception as e:
                    self.logger.warning(f"Failed to collect teams from {collector_name}: {e}")

                # Collect players  
                try:
                    players = await collector.collect_players()
                    collected_data["players"] = players
                except Exception as e:
                    self.logger.warning(f"Failed to collect players from {collector_name}: {e}")

                # Collect odds (if supported)
                try:
                    odds = await collector.collect_odds()
                    collected_data["odds"] = odds
                except Exception as e:
                    self.logger.warning(f"Failed to collect odds from {collector_name}: {e}")

                # Save data to database
                total_items = sum(len(data) for data in collected_data.values())
                if total_items > 0:
                    await self._save_collected_data(collector_name, collected_data)

                results[collector_name] = {
                    "status": "success",
                    "items_collected": total_items,
                    "breakdown": {k: len(v) for k, v in collected_data.items()},
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                }
                self.logger.info(f"Collected {total_items} items from {collector_name}")

            except Exception as e:
                results[collector_name] = {
                    "status": "error",
                    "error": str(e),
                    "items_collected": 0
                }
                self.logger.error(f"Data collection failed for {collector_name}: {e}")

        return results

    async def _save_collected_data(self, collector_name: str, data: dict[str, list]):
        """Speichert gesammelte Daten in die Datenbank"""
        # If database pool is not initialized, skip persistence gracefully
        if not getattr(self.db_manager, "pool", None):
            self.logger.info(
                "DB pool not initialized; skipping persistence for %s",
                collector_name
            )
            return

        try:
            # Save teams
            if data.get("teams"):
                await self._save_teams(data["teams"])

            # Save players
            if data.get("players"):
                await self._save_players(data["players"])

            # Save matches
            if data.get("matches"):
                await self._save_matches(data["matches"])

            # Save odds
            if data.get("odds"):
                await self._save_odds(collector_name, data["odds"])

        except Exception as e:
            self.logger.error(f"Failed to save data from {collector_name}: {e}")
            raise

    async def _save_teams(self, teams: list):
        """Speichert Team-Daten"""
        if not teams:
            return

        # Convert domain models to dict if needed
        team_data = []
        for team in teams:
            if hasattr(team, '__dict__'):
                team_data.append(team.__dict__)
            else:
                team_data.append(team)

        # Use domain service or direct DB operations
        # For now, use generic table insert
        await self.db_manager.bulk_insert("teams", team_data)

    async def _save_players(self, players: list):
        """Speichert Spieler-Daten"""
        if not players:
            return

        # Convert domain models to dict if needed
        player_data = []
        for player in players:
            if hasattr(player, '__dict__'):
                player_data.append(player.__dict__)
            else:
                player_data.append(player)

        await self.db_manager.bulk_insert("players", player_data)

    async def _save_matches(self, matches: list):
        """Speichert Match-Daten"""
        if not matches:
            return

        # Use the existing matches service
        from src.database.services.matches import upsert_matches

        match_data = []
        for match in matches:
            if hasattr(match, '__dict__'):
                match_data.append(match.__dict__)
            else:
                match_data.append(match)

        await upsert_matches(self.db_manager, match_data)

    async def _save_odds(self, collector_name: str, odds: list):
        """Speichert Odds-Daten"""
        if not odds:
            return

        # Use the existing odds service
        from src.database.services.odds import upsert_odds

        await upsert_odds(self.db_manager, odds)

    async def get_collection_statistics(self) -> dict[str, Any]:
        """Holt Collection-Statistiken"""
        try:
            # Statistiken aus der Datenbank
            stats_query = """
            SELECT 
                'teams' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM teams
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            
            UNION ALL
            
            SELECT 
                'players' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM players
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            
            UNION ALL
            
            SELECT 
                'matches' as table_name,
                COUNT(*) as total_records,
                MAX(created_at) as last_update
            FROM matches
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """

            stats_data = await self.db_manager.execute_query(stats_query)

            statistics = {
                "collector_count": len(self.collectors),
                "active_collectors": list(self.collectors.keys()),
                "data_statistics": {},
            }

            for row in stats_data:
                statistics["data_statistics"][row["table_name"]] = {
                    "records_last_7_days": row["total_records"],
                    "last_update": row["last_update"].isoformat() if row["last_update"] else None,
                }

            return statistics

        except Exception as e:
            self.logger.error(f"Failed to get collection statistics: {e}")
            return {"error": str(e)}

    async def run_collection_job(self, collector_names: list[str] = None, job_type: str = "full") -> dict[str, Any]:
        """Führt einen Collection-Job aus"""
        try:
            self.logger.info(f"Starting collection job: {job_type}")
            start_time = datetime.now()

            if job_type == "teams_only":
                # Nur Team-Daten sammeln
                results = {}
                for name in (collector_names or self.collectors.keys()):
                    if name not in self.collectors:
                        continue
                    
                    collector = self.collectors[name]
                    try:
                        teams = await collector.collect_teams()
                        if teams:
                            await self._save_teams(teams)
                        results[name] = {
                            "status": "success",
                            "teams_collected": len(teams) if teams else 0
                        }
                    except Exception as e:
                        results[name] = {"status": "error", "error": str(e)}

            elif job_type == "odds_only":
                # Nur Odds sammeln
                results = {}
                for name in (collector_names or self.collectors.keys()):
                    if name not in self.collectors:
                        continue
                    
                    collector = self.collectors[name]
                    try:
                        odds = await collector.collect_odds()
                        if odds:
                            await self._save_odds(name, odds)
                        results[name] = {
                            "status": "success", 
                            "odds_collected": len(odds) if odds else 0
                        }
                    except Exception as e:
                        results[name] = {"status": "error", "error": str(e)}

            else:
                # Full collection
                results = await self.collect_all_data(collector_names)

            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "status": "completed",
                "job_type": job_type,
                "duration_seconds": duration,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Collection job failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }