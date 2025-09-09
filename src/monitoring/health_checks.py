"""
Health Checks für die Sport Data Pipeline

Implementiert Health Check Funktionalitäten für verschiedene Systemkomponenten.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import aiohttp
import redis.asyncio as redis

from ..core.config import Settings
from ..database.manager import DatabaseManager


class HealthChecker:
    """Health Check System für alle Komponenten"""

    def __init__(self, settings: Settings, db_manager: DatabaseManager):
        self.settings = settings
        self.db_manager = db_manager
        self.logger = logging.getLogger("health_checker")

    async def check_all_components(self) -> dict[str, Any]:
        """Führt Health Checks für alle Komponenten durch"""

        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
        }

        # Liste der Health Checks
        checks = [
            ("database", self._check_database),
            ("redis", self._check_redis),
            ("external_apis", self._check_external_apis),
            ("disk_space", self._check_disk_space),
            ("memory", self._check_memory),
            ("background_tasks", self._check_background_tasks),
        ]

        # Führe alle Checks parallel aus
        tasks = []
        for component_name, check_func in checks:
            task = asyncio.create_task(self._run_single_check(component_name, check_func))
            tasks.append(task)

        # Warte auf alle Ergebnisse
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sammle Ergebnisse
        for i, (component_name, _) in enumerate(checks):
            result = results[i]

            if isinstance(result, Exception):
                health_status["components"][component_name] = {
                    "status": "unhealthy",
                    "error": str(result),
                    "timestamp": datetime.now().isoformat(),
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["components"][component_name] = result
                if result["status"] != "healthy":
                    health_status["overall_status"] = (
                        "degraded" if health_status["overall_status"] == "healthy" else "unhealthy"
                    )

        return health_status

    async def _run_single_check(self, component_name: str, check_func) -> dict[str, Any]:
        """Führt einen einzelnen Health Check aus"""
        start_time = time.time()

        try:
            result = await check_func()
            result["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
            result["timestamp"] = datetime.now().isoformat()
            return result

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": datetime.now().isoformat(),
            }

    async def _check_database(self) -> dict[str, Any]:
        """Prüft Database Health"""
        try:
            # Test Connection
            result = await self.db_manager.execute_query("SELECT 1 as test")

            if result and len(result) > 0:
                # Zusätzliche DB-Metriken
                pool_info = {}
                if self.db_manager.pool:
                    pool_info = {
                        "pool_size": self.db_manager.pool.get_size(),
                        "pool_min_size": self.db_manager.pool.get_min_size(),
                        "pool_max_size": self.db_manager.pool.get_max_size(),
                    }

                return {
                    "status": "healthy",
                    "details": {"connection": "ok", "query_test": "passed", **pool_info},
                }
            else:
                return {"status": "unhealthy", "error": "Database query returned no results"}

        except Exception as e:
            return {"status": "unhealthy", "error": f"Database connection failed: {str(e)}"}

    async def _check_redis(self) -> dict[str, Any]:
        """Prüft Redis Health"""
        try:
            redis_client = redis.from_url(self.settings.redis_url)

            # Test Connection
            await redis_client.ping()

            # Test Set/Get
            test_key = "health_check_test"
            await redis_client.set(test_key, "test_value", ex=10)
            value = await redis_client.get(test_key)

            await redis_client.close()

            if value == b"test_value":
                return {
                    "status": "healthy",
                    "details": {"connection": "ok", "read_write_test": "passed"},
                }
            else:
                return {"status": "unhealthy", "error": "Redis read/write test failed"}

        except Exception as e:
            return {"status": "unhealthy", "error": f"Redis connection failed: {str(e)}"}

    async def _check_external_apis(self) -> dict[str, Any]:
        """Prüft externe API Health"""
        apis_to_check = [
            {
                "name": "football_data_org",
                "url": "https://api.football-data.org/v4/competitions",
                "headers": {"X-Auth-Token": "test"},  # Würde echten Token verwenden
            }
        ]

        api_results = {}
        overall_status = "healthy"

        for api in apis_to_check:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(api["url"], headers=api.get("headers", {})) as response:
                        if response.status < 500:  # 4xx ist ok für Health Check
                            api_results[api["name"]] = {
                                "status": "healthy",
                                "http_status": response.status,
                            }
                        else:
                            api_results[api["name"]] = {
                                "status": "unhealthy",
                                "http_status": response.status,
                            }
                            overall_status = "degraded"

            except Exception as e:
                api_results[api["name"]] = {"status": "unhealthy", "error": str(e)}
                overall_status = "degraded"

        return {"status": overall_status, "details": api_results}

    async def _check_disk_space(self) -> dict[str, Any]:
        """Prüft Disk Space"""
        try:
            import psutil

            disk_usage = psutil.disk_usage("/")
            usage_percent = (disk_usage.used / disk_usage.total) * 100

            if usage_percent > 90:
                status = "unhealthy"
            elif usage_percent > 80:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "details": {
                    "usage_percent": round(usage_percent, 2),
                    "free_gb": round(disk_usage.free / (1024**3), 2),
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                },
            }

        except Exception as e:
            return {"status": "unhealthy", "error": f"Disk space check failed: {str(e)}"}

    async def _check_memory(self) -> dict[str, Any]:
        """Prüft Memory Usage"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_percent = memory.percent

            if usage_percent > 90:
                status = "unhealthy"
            elif usage_percent > 80:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "details": {
                    "usage_percent": usage_percent,
                    "available_gb": round(memory.available / (1024**3), 2),
                    "total_gb": round(memory.total / (1024**3), 2),
                },
            }

        except Exception as e:
            return {"status": "unhealthy", "error": f"Memory check failed: {str(e)}"}

    async def _check_background_tasks(self) -> dict[str, Any]:
        """Prüft Background Tasks Health"""
        try:
            # Prüfe Celery Worker Status (falls verfügbar)
            redis_client = redis.from_url(self.settings.redis_url)

            # Prüfe aktive Tasks
            active_tasks = await redis_client.llen("celery")

            await redis_client.close()

            return {
                "status": "healthy",
                "details": {"active_tasks": active_tasks, "queue_status": "ok"},
            }

        except Exception as e:
            return {"status": "degraded", "error": f"Background tasks check failed: {str(e)}"}

    async def check_component(self, component_name: str) -> dict[str, Any]:
        """Prüft einen spezifischen Komponenten"""

        check_mapping = {
            "database": self._check_database,
            "redis": self._check_redis,
            "external_apis": self._check_external_apis,
            "disk_space": self._check_disk_space,
            "memory": self._check_memory,
            "background_tasks": self._check_background_tasks,
        }

        if component_name not in check_mapping:
            return {
                "status": "unknown",
                "error": f"Unknown component: {component_name}",
                "timestamp": datetime.now().isoformat(),
            }

        return await self._run_single_check(component_name, check_mapping[component_name])

    async def get_health_summary(self) -> dict[str, Any]:
        """Holt Health Summary"""
        health_status = await self.check_all_components()

        # Zähle Status
        status_counts = {}
        for component, details in health_status["components"].items():
            status = details["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        # Berechne Uptime (vereinfacht)
        uptime_info = self._get_uptime_info()

        return {
            "overall_status": health_status["overall_status"],
            "components_total": len(health_status["components"]),
            "status_counts": status_counts,
            "uptime": uptime_info,
            "last_check": health_status["timestamp"],
        }

    def _get_uptime_info(self) -> dict[str, Any]:
        """Holt Uptime Informationen"""
        try:
            import psutil

            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time

            return {
                "system_boot_time": boot_time.isoformat(),
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime).split(".")[0],  # Ohne Mikrosekunden
            }

        except Exception as e:
            return {"error": f"Failed to get uptime: {str(e)}"}


class HealthCheckScheduler:
    """Scheduler für regelmäßige Health Checks"""

    def __init__(self, health_checker: HealthChecker, interval: int = 60):
        self.health_checker = health_checker
        self.interval = interval
        self.logger = logging.getLogger("health_check_scheduler")
        self.running = False
        self.last_results = {}

    async def start_monitoring(self):
        """Startet kontinuierliches Health Monitoring"""
        self.running = True

        while self.running:
            try:
                # Führe Health Checks durch
                results = await self.health_checker.check_all_components()
                self.last_results = results

                # Log kritische Probleme
                if results["overall_status"] == "unhealthy":
                    self.logger.error(f"System unhealthy: {results}")
                elif results["overall_status"] == "degraded":
                    self.logger.warning(f"System degraded: {results}")

                await asyncio.sleep(self.interval)

            except Exception as e:
                self.logger.error(f"Health check monitoring error: {e}")
                await asyncio.sleep(self.interval)

    def stop_monitoring(self):
        """Stoppt Health Monitoring"""
        self.running = False
        self.logger.info("Health check monitoring stopped")

    def get_last_results(self) -> dict[str, Any]:
        """Holt letzte Health Check Ergebnisse"""
        return self.last_results or {
            "status": "no_data",
            "message": "No health checks performed yet",
        }
