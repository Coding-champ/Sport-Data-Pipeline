"""Check row count of a given DB table with retries.

Moved into maintenance utilities folder.
Usage:
  python scripts/maintenance/check_table_count.py <table_name>
Defaults to 'live_scores' when not provided.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg  # type: ignore
from dotenv import load_dotenv  # type: ignore

TABLE = sys.argv[1] if len(sys.argv) > 1 else "live_scores"


def get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set in environment")
    return dsn.replace("+asyncpg", "")


async def check():
    dsn = get_dsn()
    attempts = 10
    delay = 2
    last_err = None
    for i in range(1, attempts + 1):
        try:
            conn = await asyncpg.connect(dsn)
            try:
                await conn.fetchval("SELECT 1")
                cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {TABLE}")
                print(f"{TABLE} count: {cnt}")
                return
            finally:
                await conn.close()
        except Exception as e:  # pragma: no cover - network/db path
            last_err = e
            if i < attempts:
                await asyncio.sleep(delay)
            else:
                break
    print("Error:", type(last_err).__name__, str(last_err))


def main():  # pragma: no cover - CLI entry
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    asyncio.run(check())


if __name__ == "__main__":  # pragma: no cover
    main()
