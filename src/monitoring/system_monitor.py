"""
System Monitor für die Sport Data Pipeline

Implementiert System-Monitoring und Alerting Funktionalitäten.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import aiofiles
import psutil

from ..core.config import Settings


class SystemMonitor:
    """System Monitor für Performance und Resource Tracking"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger("system_monitor")
        self.alerts = []
        self.alert_handlers: list[Callable] = []

        # Thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "response_time_ms": 5000.0,
        }

    def add_alert_handler(self, handler: Callable):
        """Fügt Alert Handler hinzu"""
        self.alert_handlers.append(handler)

    async def collect_system_metrics(self) -> dict[str, Any]:
        """Sammelt System-Metriken"""
        try:
            # CPU Metriken
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memory Metriken
            memory = psutil.virtual_memory()

            # Disk Metriken
            disk = psutil.disk_usage("/")

            # Network Metriken
            network = psutil.net_io_counters()

            # Process Metriken
            process = psutil.Process()
            process_memory = process.memory_info()

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "load_avg": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "percent": round((disk.used / disk.total) * 100, 2),
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 2),
                    "cpu_percent": process.cpu_percent(),
                },
            }

            # Prüfe Thresholds
            await self._check_thresholds(metrics)

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def _check_thresholds(self, metrics: dict[str, Any]):
        """Prüft Threshold-Überschreitungen"""
        alerts = []

        # CPU Check
        if metrics["cpu"]["percent"] > self.thresholds["cpu_percent"]:
            alerts.append(
                {
                    "type": "cpu_high",
                    "severity": "warning",
                    "message": f"High CPU usage: {metrics['cpu']['percent']}%",
                    "value": metrics["cpu"]["percent"],
                    "threshold": self.thresholds["cpu_percent"],
                }
            )

        # Memory Check
        if metrics["memory"]["percent"] > self.thresholds["memory_percent"]:
            alerts.append(
                {
                    "type": "memory_high",
                    "severity": "warning",
                    "message": f"High memory usage: {metrics['memory']['percent']}%",
                    "value": metrics["memory"]["percent"],
                    "threshold": self.thresholds["memory_percent"],
                }
            )

        # Disk Check
        if metrics["disk"]["percent"] > self.thresholds["disk_percent"]:
            alerts.append(
                {
                    "type": "disk_high",
                    "severity": "critical",
                    "message": f"High disk usage: {metrics['disk']['percent']}%",
                    "value": metrics["disk"]["percent"],
                    "threshold": self.thresholds["disk_percent"],
                }
            )

        # Sende Alerts
        for alert in alerts:
            await self._send_alert(alert)

    async def _send_alert(self, alert: dict[str, Any]):
        """Sendet Alert an alle Handler"""
        alert["timestamp"] = datetime.now().isoformat()
        self.alerts.append(alert)

        # Behalte nur letzte 100 Alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        self.logger.warning(f"ALERT: {alert['message']}")

        # Rufe Alert Handler auf
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")

    async def get_performance_summary(self, hours: int = 24) -> dict[str, Any]:
        """Holt Performance Summary der letzten Stunden"""
        try:
            # Sammle aktuelle Metriken
            current_metrics = await self.collect_system_metrics()

            # Berechne Trends (vereinfacht - würde normalerweise historische Daten verwenden)
            summary = {
                "current_status": {
                    "cpu_percent": current_metrics["cpu"]["percent"],
                    "memory_percent": current_metrics["memory"]["percent"],
                    "disk_percent": current_metrics["disk"]["percent"],
                },
                "thresholds": self.thresholds,
                "recent_alerts": self.alerts[-10:],  # Letzte 10 Alerts
                "alert_count_24h": len([a for a in self.alerts if self._is_recent_alert(a, hours)]),
                "system_health": self._calculate_health_score(current_metrics),
            }

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}

    def _is_recent_alert(self, alert: dict[str, Any], hours: int) -> bool:
        """Prüft ob Alert in den letzten X Stunden war"""
        try:
            alert_time = datetime.fromisoformat(alert["timestamp"])
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return alert_time > cutoff_time
        except:
            return False

    def _calculate_health_score(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Berechnet System Health Score"""
        try:
            # Einfacher Health Score basierend auf Metriken
            cpu_score = max(0, 100 - metrics["cpu"]["percent"])
            memory_score = max(0, 100 - metrics["memory"]["percent"])
            disk_score = max(0, 100 - metrics["disk"]["percent"])

            overall_score = (cpu_score + memory_score + disk_score) / 3

            if overall_score >= 80:
                status = "excellent"
            elif overall_score >= 60:
                status = "good"
            elif overall_score >= 40:
                status = "fair"
            else:
                status = "poor"

            return {
                "overall_score": round(overall_score, 1),
                "status": status,
                "component_scores": {
                    "cpu": round(cpu_score, 1),
                    "memory": round(memory_score, 1),
                    "disk": round(disk_score, 1),
                },
            }

        except Exception as e:
            return {"error": str(e)}

    async def save_metrics_to_file(self, metrics: dict[str, Any], filepath: str):
        """Speichert Metriken in Datei"""
        try:
            async with aiofiles.open(filepath, "a") as f:
                await f.write(json.dumps(metrics) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to save metrics to file: {e}")

    async def start_monitoring(self, interval: int = 60):
        """Startet kontinuierliches System Monitoring"""
        self.logger.info(f"Starting system monitoring with {interval}s interval")

        while True:
            try:
                metrics = await self.collect_system_metrics()

                # Optional: Speichere Metriken
                if self.settings.monitoring_log_file:
                    await self.save_metrics_to_file(metrics, self.settings.monitoring_log_file)

                await asyncio.sleep(interval)

            except Exception as e:
                self.logger.error(f"System monitoring error: {e}")
                await asyncio.sleep(interval)


class AlertManager:
    """Alert Management System"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger("alert_manager")
        self.alert_channels = []

    def add_channel(self, channel):
        """Fügt Alert Channel hinzu"""
        self.alert_channels.append(channel)

    async def send_alert(self, alert: dict[str, Any]):
        """Sendet Alert über alle Channels"""
        for channel in self.alert_channels:
            try:
                await channel.send(alert)
            except Exception as e:
                self.logger.error(f"Failed to send alert via {channel.__class__.__name__}: {e}")


class EmailAlertChannel:
    """E-Mail Alert Channel"""

    def __init__(self, smtp_config: dict[str, Any]):
        self.smtp_config = smtp_config
        self.logger = logging.getLogger("email_alerts")

    async def send(self, alert: dict[str, Any]):
        """Sendet Alert per E-Mail"""
        # Vereinfachte E-Mail Implementation
        # In echter Anwendung würde aiosmtplib oder ähnliches verwendet
        self.logger.info(f"EMAIL ALERT: {alert['message']}")


class SlackAlertChannel:
    """Slack Alert Channel"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.logger = logging.getLogger("slack_alerts")

    async def send(self, alert: dict[str, Any]):
        """Sendet Alert an Slack"""
        try:
            import aiohttp

            payload = {
                "text": f"🚨 {alert['message']}",
                "attachments": [
                    {
                        "color": "danger" if alert["severity"] == "critical" else "warning",
                        "fields": [
                            {"title": "Severity", "value": alert["severity"], "short": True},
                            {"title": "Timestamp", "value": alert["timestamp"], "short": True},
                        ],
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        self.logger.info("Alert sent to Slack successfully")
                    else:
                        self.logger.error(f"Failed to send Slack alert: {response.status}")

        except Exception as e:
            self.logger.error(f"Slack alert failed: {e}")


class LogAlertChannel:
    """Log Alert Channel"""

    def __init__(self):
        self.logger = logging.getLogger("log_alerts")

    async def send(self, alert: dict[str, Any]):
        """Loggt Alert"""
        level = logging.CRITICAL if alert["severity"] == "critical" else logging.WARNING
        self.logger.log(level, f"ALERT: {alert['message']} | {alert}")
