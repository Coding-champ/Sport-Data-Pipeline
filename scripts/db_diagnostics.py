"""
Unified database diagnostics script using DatabaseManager.

Usage:
  python -m scripts.db_diagnostics
"""

import asyncio
import sys
from typing import Any

from src.database.manager import DatabaseManager
from src.core.config import Settings


async def main() -> int:
    settings = Settings()
    db = DatabaseManager()

    # Results container
    results: dict[str, Any] = {
        "dsn": settings.database_url,
        "sync": {},
        "async": {},
    }

    # Initialize sync + async
    try:
        db.initialize_sync()
        results["sync"] = {"ok": True}
    except Exception as e:  # pragma: no cover
        results["sync"] = {"ok": False, "error": str(e)}

    try:
        await db.initialize_async()
        results["async"] = {"ok": True}
    except Exception as e:  # pragma: no cover
        results["async"] = {"ok": False, "error": str(e)}

    # Simple queries
    try:
        # Sync check
        if db.engine is not None:
            with db.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            results["sync"]["query"] = "ok"
    except Exception as e:  # pragma: no cover
        results["sync"]["query"] = f"error: {e}"

    try:
        # Async check
        if db.pool is not None:
            async with db.get_async_connection() as conn:
                await conn.fetchval("SELECT 1")
            results["async"]["query"] = "ok"
    except Exception as e:  # pragma: no cover
        results["async"]["query"] = f"error: {e}"

    # Print concise outcome
    sync_ok = results["sync"].get("ok") is True and results["sync"].get("query") == "ok"
    async_ok = results["async"].get("ok") is True and results["async"].get("query") == "ok"

    print("Database diagnostics:")
    print(f"  DSN: {results['dsn']}")
    print(f"  Sync: {'OK' if sync_ok else results['sync']}")
    print(f"  Async: {'OK' if async_ok else results['async']}")

    # Close resources
    try:
        if db.pool is not None:
            await db.pool.close()
    except Exception:
        pass

    return 0 if (sync_ok and async_ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


