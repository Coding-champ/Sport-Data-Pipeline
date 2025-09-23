"""Central logging utilities for the Sport Data Pipeline.

Goals:
- Single place to configure logging for scripts, CLI tools, services.
- Provide structured JSON logging option (LOG_FORMAT=json) and colored human-readable output (default).
- Respect environment variables:
    LOG_LEVEL=INFO|DEBUG|... (default: INFO)
    LOG_FORMAT=console|json (default: console)
    LOG_NO_COLOR=1 to disable color output even on console format.
    LOG_TIMEZONE=utc|local (default: local)
- Allow reusable per-module loggers via get_logger(name) without re-configuring root handlers.

Usage in scripts:
    from src.common.logging_utils import configure_logging, get_logger
    configure_logging(service="scraper")  # idempotent
    logger = get_logger(__name__)
    logger.info("Hello")

Calling configure_logging() multiple times is safe – subsequent calls become no-ops unless
`force=True` is passed.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_CONFIG_LOCK = threading.Lock()
_ALREADY_CONFIGURED = False

# --------------------------------------------------------------------------------------
# Formatters
# --------------------------------------------------------------------------------------

class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\x1b[38;5;245m",  # grey
        "INFO": "\x1b[38;5;39m",  # blue
        "WARNING": "\x1b[38;5;214m",  # orange
        "ERROR": "\x1b[38;5;196m",  # red
        "CRITICAL": "\x1b[48;5;196m\x1b[38;5;231m",  # white on red
    }
    RESET = "\x1b[0m"

    def __init__(self, tz_local: bool):
        super().__init__()
        self.tz_local = tz_local

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        level_color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if self.tz_local:
            ts = ts.astimezone()
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        base = f"{ts_str} | {record.levelname:<8} | {record.name} | {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        if level_color:
            return f"{level_color}{base}{self.RESET}"
        return base


class JsonFormatter(logging.Formatter):
    def __init__(self, tz_local: bool):
        super().__init__()
        self.tz_local = tz_local

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if self.tz_local:
            ts = ts.astimezone()
        payload: Dict[str, Any] = {
            "ts": ts.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Include extra attributes (non-standard) if present
        for k, v in record.__dict__.items():
            if k not in logging.LogRecord.__dict__ and k not in payload and not k.startswith("_"):
                # Filter built-ins
                if k in {"args", "name", "msg", "levelno", "levelname", "pathname", "filename", "module", "exc_text", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "stack_info"}:
                    continue
                try:
                    json.dumps({k: v})  # type check
                    payload[k] = v
                except Exception:
                    payload[k] = repr(v)
        return json.dumps(payload, ensure_ascii=False)


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------

def configure_logging(service: str | None = None, *, force: bool = False) -> None:
    """Configure root logging once.

    Parameters
    ----------
    service: Optional logical service/app name (added as logger 'context' field in JSON mode)
    force: If True, reconfigure even if already configured.
    """
    global _ALREADY_CONFIGURED
    with _CONFIG_LOCK:
        if _ALREADY_CONFIGURED and not force:
            return

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "console").lower()
        tz_mode = os.getenv("LOG_TIMEZONE", "local").lower()
        no_color = os.getenv("LOG_NO_COLOR") == "1"

        tz_local = tz_mode != "utc"

        # Clear existing handlers if reconfiguring
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

        if log_format == "json":
            formatter: logging.Formatter = JsonFormatter(tz_local=tz_local)
        else:
            if sys.stderr.isatty() and not no_color:
                formatter = ColorFormatter(tz_local=tz_local)
            else:
                formatter = logging.Formatter(
                    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
        root.setLevel(getattr(logging, log_level, logging.INFO))

        if service:
            # Attach service name via LoggerAdapter mechanism when retrieved
            _ServiceLoggerAdapter.BASE_SERVICE = service  # type: ignore[attr-defined]

        _ALREADY_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    base = logging.getLogger(name)
    # If a service context exists, wrap in adapter; else return raw logger
    base_service = getattr(_ServiceLoggerAdapter, "BASE_SERVICE", None)
    if base_service:
        return _ServiceLoggerAdapter(base, {"service": base_service})
    return base


class _ServiceLoggerAdapter(logging.LoggerAdapter):
    # Dynamically set by configure_logging if service specified
    BASE_SERVICE: Optional[str] = None

    def process(self, msg: Any, kwargs: Dict[str, Any]):  # noqa: D401
        extra = kwargs.get("extra") or {}
        if "service" not in extra and self.extra.get("service"):
            extra["service"] = self.extra["service"]
        kwargs["extra"] = extra
        return msg, kwargs


__all__ = [
    "configure_logging",
    "get_logger",
]
