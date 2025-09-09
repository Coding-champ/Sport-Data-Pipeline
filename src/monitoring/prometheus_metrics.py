"""
Prometheus Metrics für die Sport Data Pipeline

Implementiert Metriken-Sammlung und -Export für Monitoring.
"""

import asyncio
import logging
import time
from typing import Any

import psutil
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
)

from ..core.config import Settings
from ..database.manager import DatabaseManager


class PrometheusMetrics:
    """Prometheus Metriken für die Sport Data Pipeline"""

    def __init__(self, settings: Settings, db_manager: DatabaseManager):
        self.settings = settings
        self.db_manager = db_manager
        self.logger = logging.getLogger("prometheus_metrics")

        # Custom Registry für bessere Kontrolle
        self.registry = CollectorRegistry()

        # API Metriken
        self.api_requests_total = Counter(
            "api_requests_total",
            "Total number of API requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.api_request_duration = Histogram(
            "api_request_duration_seconds",
            "API request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Data Collection Metriken
        self.data_collection_total = Counter(
            "data_collection_total",
            "Total number of data collection operations",
            ["collector", "status"],
            registry=self.registry,
        )

        self.data_collection_duration = Histogram(
            "data_collection_duration_seconds",
            "Data collection duration in seconds",
            ["collector"],
            registry=self.registry,
        )

        self.data_items_collected = Counter(
            "data_items_collected_total",
            "Total number of data items collected",
            ["collector", "data_type"],
            registry=self.registry,
        )

        # Scraping Metriken
        self.scraping_operations_total = Counter(
            "scraping_operations_total",
            "Total number of scraping operations",
            ["scraper", "status"],
            registry=self.registry,
        )

        self.scraping_duration = Histogram(
            "scraping_duration_seconds",
            "Scraping operation duration in seconds",
            ["scraper"],
            registry=self.registry,
        )

        # Analytics Metriken
        self.analytics_operations_total = Counter(
            "analytics_operations_total",
            "Total number of analytics operations",
            ["operation_type", "status"],
            registry=self.registry,
        )

        self.analytics_duration = Histogram(
            "analytics_duration_seconds",
            "Analytics operation duration in seconds",
            ["operation_type"],
            registry=self.registry,
        )

        # Background Tasks Metriken
        self.background_tasks_total = Counter(
            "background_tasks_total",
            "Total number of background tasks",
            ["task_name", "status"],
            registry=self.registry,
        )

        self.background_task_duration = Histogram(
            "background_task_duration_seconds",
            "Background task duration in seconds",
            ["task_name"],
            registry=self.registry,
        )

        # System Metriken
        self.system_cpu_usage = Gauge(
            "system_cpu_usage_percent", "System CPU usage percentage", registry=self.registry
        )

        self.system_memory_usage = Gauge(
            "system_memory_usage_bytes", "System memory usage in bytes", registry=self.registry
        )

        self.system_disk_usage = Gauge(
            "system_disk_usage_bytes", "System disk usage in bytes", registry=self.registry
        )

        # Database Metriken
        self.database_connections_active = Gauge(
            "database_connections_active",
            "Number of active database connections",
            registry=self.registry,
        )

        self.database_query_duration = Histogram(
            "database_query_duration_seconds",
            "Database query duration in seconds",
            ["query_type"],
            registry=self.registry,
        )

        self.database_operations_total = Counter(
            "database_operations_total",
            "Total number of database operations",
            ["operation", "status"],
            registry=self.registry,
        )

        # Application Info
        self.app_info = Info(
            "sport_data_pipeline_info",
            "Sport Data Pipeline application info",
            registry=self.registry,
        )

        # Setze App Info
        self.app_info.info(
            {
                "version": "1.0.0",
                "environment": self.settings.environment,
                "database_url": (
                    self.settings.database_url.split("@")[1]
                    if "@" in self.settings.database_url
                    else "hidden"
                ),
            }
        )

    def start_metrics_server(self, port: int = 8001):
        """Startet Prometheus Metrics HTTP Server"""
        try:
            start_http_server(port, registry=self.registry)
            self.logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
            raise

    def record_api_request(self, method: str, endpoint: str, status: str, duration: float):
        """Zeichnet API Request auf"""
        self.api_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.api_request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_data_collection(
        self,
        collector: str,
        status: str,
        duration: float,
        items_count: int = 0,
        data_type: str = "unknown",
    ):
        """Zeichnet Data Collection Operation auf"""
        self.data_collection_total.labels(collector=collector, status=status).inc()
        self.data_collection_duration.labels(collector=collector).observe(duration)

        if items_count > 0:
            self.data_items_collected.labels(collector=collector, data_type=data_type).inc(
                items_count
            )

    def record_scraping_operation(self, scraper: str, status: str, duration: float):
        """Zeichnet Scraping Operation auf"""
        self.scraping_operations_total.labels(scraper=scraper, status=status).inc()
        self.scraping_duration.labels(scraper=scraper).observe(duration)

    def record_analytics_operation(self, operation_type: str, status: str, duration: float):
        """Zeichnet Analytics Operation auf"""
        self.analytics_operations_total.labels(operation_type=operation_type, status=status).inc()
        self.analytics_duration.labels(operation_type=operation_type).observe(duration)

    def record_background_task(self, task_name: str, status: str, duration: float):
        """Zeichnet Background Task auf"""
        self.background_tasks_total.labels(task_name=task_name, status=status).inc()
        self.background_task_duration.labels(task_name=task_name).observe(duration)

    def record_database_operation(
        self, operation: str, status: str, duration: float, query_type: str = "unknown"
    ):
        """Zeichnet Database Operation auf"""
        self.database_operations_total.labels(operation=operation, status=status).inc()
        self.database_query_duration.labels(query_type=query_type).observe(duration)

    def update_system_metrics(self):
        """Aktualisiert System-Metriken"""
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent()
            self.system_cpu_usage.set(cpu_percent)

            # Memory Usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.used)

            # Disk Usage
            disk = psutil.disk_usage("/")
            self.system_disk_usage.set(disk.used)

        except Exception as e:
            self.logger.warning(f"Failed to update system metrics: {e}")

    async def update_database_metrics(self):
        """Aktualisiert Database-Metriken"""
        try:
            if self.db_manager.pool:
                # Aktive Verbindungen (approximation)
                active_connections = (
                    len(self.db_manager.pool._holders)
                    if hasattr(self.db_manager.pool, "_holders")
                    else 0
                )
                self.database_connections_active.set(active_connections)

        except Exception as e:
            self.logger.warning(f"Failed to update database metrics: {e}")

    def get_metrics_summary(self) -> dict[str, Any]:
        """Holt Metriken-Zusammenfassung"""
        try:
            # Sammle aktuelle Metriken-Werte
            summary = {
                "system": {
                    "cpu_usage_percent": psutil.cpu_percent(),
                    "memory_usage_percent": psutil.virtual_memory().percent,
                    "disk_usage_percent": psutil.disk_usage("/").percent,
                },
                "database": {
                    "active_connections": (
                        len(self.db_manager.pool._holders)
                        if self.db_manager.pool and hasattr(self.db_manager.pool, "_holders")
                        else 0
                    )
                },
                "metrics_endpoint": "http://localhost:8001/metrics",
            }

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {e}")
            return {"error": str(e)}

    def export_metrics(self) -> str:
        """Exportiert Metriken im Prometheus Format"""
        try:
            return generate_latest(self.registry).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
            return f"# Error exporting metrics: {e}\n"


class MetricsMiddleware:
    """Middleware für automatische Metriken-Sammlung"""

    def __init__(self, metrics: PrometheusMetrics):
        self.metrics = metrics

    def __call__(self, func):
        """Decorator für Funktionen"""

        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                func_name = func.__name__

                # Bestimme Metriken-Typ basierend auf Funktionsname
                if "collect" in func_name:
                    self.metrics.record_data_collection("unknown", status, duration)
                elif "scrape" in func_name:
                    self.metrics.record_scraping_operation("unknown", status, duration)
                elif "analyze" in func_name or "predict" in func_name:
                    self.metrics.record_analytics_operation("unknown", status, duration)

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                func_name = func.__name__

                if "collect" in func_name:
                    self.metrics.record_data_collection("unknown", status, duration)
                elif "scrape" in func_name:
                    self.metrics.record_scraping_operation("unknown", status, duration)

        # Wähle Wrapper basierend auf Funktion
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


class MetricsCollector:
    """Sammelt Metriken periodisch"""

    def __init__(self, metrics: PrometheusMetrics, interval: int = 30):
        self.metrics = metrics
        self.interval = interval
        self.logger = logging.getLogger("metrics_collector")
        self.running = False

    async def start_collection(self):
        """Startet periodische Metriken-Sammlung"""
        self.running = True

        while self.running:
            try:
                # System-Metriken aktualisieren
                self.metrics.update_system_metrics()

                # Database-Metriken aktualisieren
                await self.metrics.update_database_metrics()

                await asyncio.sleep(self.interval)

            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.interval)

    def stop_collection(self):
        """Stoppt Metriken-Sammlung"""
        self.running = False
        self.logger.info("Metrics collection stopped")
