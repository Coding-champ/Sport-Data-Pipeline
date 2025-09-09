"""
Sport Data Pipeline - Hauptanwendung

Zentraler Einstiegspunkt für die gesamte Sport Data Pipeline.
Koordiniert Data Collection, Analytics und API Services.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Windows-specific asyncio policy to avoid 'Event loop is closed' and transport warnings
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import uvicorn

from src.api.main import create_fastapi_app
from src.apps import SportsAnalyticsApp, SportsDataApp
from src.core.config import Settings
from src.monitoring import HealthChecker, PrometheusMetrics, SystemMonitor


class SportDataPipeline:
    """Hauptklasse für die gesamte Sport Data Pipeline"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.logger = logging.getLogger("sport_data_pipeline")

        # Apps
        self.data_app: SportsDataApp | None = None
        self.analytics_app: SportsAnalyticsApp | None = None
        self.fastapi_app = None

        # Monitoring
        self.metrics: PrometheusMetrics | None = None
        self.health_checker: HealthChecker | None = None
        self.system_monitor: SystemMonitor | None = None

        # Tasks
        self.background_tasks = []
        self.shutdown_event = asyncio.Event()

        self._setup_logging()
        self._setup_signal_handlers()

    def _setup_logging(self):
        """Konfiguriert Logging"""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))

        # File Handler
        log_file = Path(self.settings.log_file_path) / "sport_data_pipeline.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Root Logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.settings.log_level.upper()))
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    def _setup_signal_handlers(self):
        """Konfiguriert Signal Handlers für graceful shutdown"""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def initialize(self):
        """Initialisiert alle Komponenten"""
        try:
            self.logger.info("Initializing Sport Data Pipeline...")

            # Data Collection App
            if self.settings.enable_data_collection:
                self.data_app = SportsDataApp(self.settings)
                await self.data_app.initialize()
                self.logger.info("Data Collection App initialized")

            # Analytics App
            if self.settings.enable_analytics:
                self.analytics_app = SportsAnalyticsApp(self.settings)
                await self.analytics_app.initialize()
                self.logger.info("Analytics App initialized")

            # Monitoring (shared across apps)
            from src.database.manager import DatabaseManager
            db_manager: DatabaseManager | None = None
            if self.settings.enable_monitoring:
                db_manager = DatabaseManager()
                await db_manager.initialize()

                self.metrics = PrometheusMetrics(self.settings, db_manager)
                self.health_checker = HealthChecker(self.settings, db_manager)
                self.system_monitor = SystemMonitor(self.settings)

                # Start metrics server once, here
                if self.settings.enable_metrics:
                    self.metrics.start_metrics_server(self.settings.metrics_port)

                self.logger.info("Monitoring initialized")

            # FastAPI App (inject shared db/metrics)
            if self.settings.enable_api:
                self.fastapi_app = create_fastapi_app(
                    self.settings,
                    self.data_app,
                    self.analytics_app,
                    db_manager=db_manager,
                    metrics=self.metrics,
                )
                self.logger.info("FastAPI App initialized")

            self.logger.info("Sport Data Pipeline initialization completed")

        except Exception as e:
            self.logger.error(f"Failed to initialize Sport Data Pipeline: {e}")
            raise

    async def start_background_tasks(self):
        """Startet Background Tasks"""
        try:
            # Data Collection Scheduler
            if self.data_app and self.settings.enable_scheduled_collection:
                task = asyncio.create_task(self.data_app.run_scheduled_collection())
                self.background_tasks.append(task)
                self.logger.info("Data collection scheduler started")

            # Analytics Scheduler
            if self.analytics_app and self.settings.enable_scheduled_analytics:
                task = asyncio.create_task(self._run_analytics_scheduler())
                self.background_tasks.append(task)
                self.logger.info("Analytics scheduler started")

            # System Monitoring
            if self.system_monitor and self.settings.enable_system_monitoring:
                task = asyncio.create_task(self.system_monitor.start_monitoring(60))
                self.background_tasks.append(task)
                self.logger.info("System monitoring started")

            # Health Check Scheduler
            if self.health_checker and self.settings.enable_health_checks:
                from src.monitoring.health_checks import HealthCheckScheduler

                health_scheduler = HealthCheckScheduler(self.health_checker, 300)  # 5 min
                task = asyncio.create_task(health_scheduler.start_monitoring())
                self.background_tasks.append(task)
                self.logger.info("Health check scheduler started")

        except Exception as e:
            self.logger.error(f"Failed to start background tasks: {e}")
            raise

    async def _run_analytics_scheduler(self):
        """Analytics Scheduler - läuft täglich"""
        while not self.shutdown_event.is_set():
            try:
                # Warte bis zur nächsten geplanten Zeit (z.B. 2:00 AM)
                await self._wait_until_scheduled_time(2, 0)  # 2:00 AM

                if not self.shutdown_event.is_set():
                    self.logger.info("Running scheduled analytics...")
                    await self.analytics_app.run_daily_analytics()

            except Exception as e:
                self.logger.error(f"Analytics scheduler error: {e}")
                # Warte 1 Stunde bei Fehler
                await asyncio.sleep(3600)

    async def _wait_until_scheduled_time(self, hour: int, minute: int):
        """Wartet bis zur geplanten Zeit"""
        from datetime import datetime, timedelta

        now = datetime.now()
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Wenn die Zeit heute schon vorbei ist, plane für morgen
        if scheduled <= now:
            scheduled += timedelta(days=1)

        wait_seconds = (scheduled - now).total_seconds()

        try:
            await asyncio.wait_for(self.shutdown_event.wait(), timeout=wait_seconds)
        except asyncio.TimeoutError:
            pass  # Timeout ist erwünscht

    async def run_api_server(self):
        """Startet den API Server"""
        if not self.fastapi_app:
            self.logger.warning("FastAPI app not initialized, skipping API server")
            return

        config = uvicorn.Config(
            self.fastapi_app,
            host=self.settings.api_host,
            port=self.settings.api_port,
            log_level=self.settings.log_level.lower(),
            access_log=True,
        )

        server = uvicorn.Server(config)

        self.logger.info(
            f"Starting API server on {self.settings.api_host}:{self.settings.api_port}"
        )

        # Starte Server in separatem Task
        server_task = asyncio.create_task(server.serve())
        self.background_tasks.append(server_task)

        # Warte auf Shutdown
        await self.shutdown_event.wait()

        # Stoppe Server gracefully
        server.should_exit = True
        await server_task

    async def run(self):
        """Hauptausführung der Pipeline"""
        try:
            await self.initialize()

            # Starte Background Tasks
            await self.start_background_tasks()

            # Bestimme Run Mode
            if self.settings.run_mode == "api_only":
                # Nur API Server
                await self.run_api_server()

            elif self.settings.run_mode == "collection_once":
                # Einmalige Data Collection
                if self.data_app:
                    results = await self.data_app.run_data_collection()
                    self.logger.info(f"Data collection completed: {results}")
                else:
                    self.logger.error("Data app not initialized")

            elif self.settings.run_mode == "analytics_once":
                # Einmalige Analytics
                if self.analytics_app:
                    results = await self.analytics_app.run_daily_analytics()
                    self.logger.info(f"Analytics completed: {results}")
                else:
                    self.logger.error("Analytics app not initialized")

            elif self.settings.run_mode == "full_service":
                # Vollständiger Service-Modus
                tasks = []

                # API Server
                if self.fastapi_app:
                    tasks.append(asyncio.create_task(self.run_api_server()))

                # Warte auf alle Tasks oder Shutdown
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    await self.shutdown_event.wait()

            else:
                # Interactive Mode
                await self._run_interactive_mode()

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}")
            raise
        finally:
            await self.cleanup()

    async def _run_interactive_mode(self):
        """Interaktiver Modus"""
        print("\n🏈 Sport Data Pipeline - Interactive Mode")
        print("=" * 50)
        print("Available commands:")
        print("  collect     - Run data collection")
        print("  flashscore  - Run Flashscore scraper once")
        print("  analytics   - Run analytics")
        print("  status      - Show system status")
        print("  health      - Show health status")
        print("  metrics     - Show metrics summary")
        print("  quit        - Exit application")
        print("=" * 50)

        while not self.shutdown_event.is_set():
            try:
                command = input("\n> ").strip().lower()

                if command == "collect":
                    if self.data_app:
                        results = await self.data_app.run_data_collection()
                        print(f"✅ Collection completed: {results.get('status', 'unknown')}")
                    else:
                        print("❌ Data collection not enabled")

                elif command == "flashscore":
                    if self.data_app and getattr(self.data_app, "scraping_orchestrator", None):
                        results = await self.data_app.scraping_orchestrator.run_scraping_job(
                            ["flashscore"]
                        )
                        count = 0
                        try:
                            fs_res = results.get("flashscore") or {}
                            count = int(fs_res.get("items_scraped", 0))
                        except Exception:
                            pass
                        print(f"✅ Flashscore run completed. Items scraped: {count}")
                    else:
                        print("❌ Flashscore orchestrator not available")

                elif command == "analytics":
                    if self.analytics_app:
                        results = await self.analytics_app.run_daily_analytics()
                        print(f"✅ Analytics completed: {results.get('status', 'unknown')}")
                    else:
                        print("❌ Analytics not enabled")

                elif command == "status":
                    await self._show_system_status()

                elif command == "health":
                    await self._show_health_status()

                elif command == "metrics":
                    await self._show_metrics_summary()

                elif command == "quit":
                    break

                elif command == "help":
                    print(
                        "Available commands: collect, flashscore, analytics, status, health, metrics, quit"
                    )

                else:
                    print(f"❌ Unknown command: {command}. Type 'help' for available commands.")

            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ Command failed: {e}")

    async def _show_system_status(self):
        """Zeigt System Status"""
        print("\n📊 System Status:")
        print("-" * 30)

        if self.data_app:
            status = await self.data_app.get_system_status()
            print(f"Data Collection: {status.get('overall_status', 'unknown')}")

        if self.analytics_app:
            summary = await self.analytics_app.get_analytics_summary()
            print(f"Analytics: {'healthy' if 'error' not in summary else 'error'}")

        if self.system_monitor:
            metrics = await self.system_monitor.collect_system_metrics()
            if "error" not in metrics:
                print(f"CPU: {metrics['cpu']['percent']:.1f}%")
                print(f"Memory: {metrics['memory']['percent']:.1f}%")
                print(f"Disk: {metrics['disk']['percent']:.1f}%")

    async def _show_health_status(self):
        """Zeigt Health Status"""
        if not self.health_checker:
            print("❌ Health checking not enabled")
            return

        print("\n🏥 Health Status:")
        print("-" * 30)

        health = await self.health_checker.check_all_components()
        print(f"Overall: {health['overall_status']}")

        for component, details in health["components"].items():
            status_emoji = (
                "✅"
                if details["status"] == "healthy"
                else "⚠️" if details["status"] == "degraded" else "❌"
            )
            print(f"{status_emoji} {component}: {details['status']}")

    async def _show_metrics_summary(self):
        """Zeigt Metrics Summary"""
        if not self.metrics:
            print("❌ Metrics not enabled")
            return

        print("\n📈 Metrics Summary:")
        print("-" * 30)
        print("Metrics server running on port", self.settings.metrics_port)
        print(f"Visit http://localhost:{self.settings.metrics_port}/metrics for Prometheus metrics")

    async def shutdown(self):
        """Graceful Shutdown"""
        self.logger.info("Initiating graceful shutdown...")

        # Signal shutdown to all components
        self.shutdown_event.set()

        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        self.logger.info("Graceful shutdown completed")

    async def cleanup(self):
        """Räumt alle Ressourcen auf"""
        try:
            self.logger.info("Cleaning up resources...")

            # Cleanup Apps
            if self.data_app:
                await self.data_app.cleanup()

            if self.analytics_app:
                await self.analytics_app.cleanup()

            self.logger.info("Resource cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


async def main():
    """Haupteinstiegspunkt"""
    try:
        # Load settings
        settings = Settings()

        # Create and run pipeline
        pipeline = SportDataPipeline(settings)
        await pipeline.run()

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
