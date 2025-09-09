import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

TABLE = sys.argv[1] if len(sys.argv) > 1 else "live_scores"


def get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set in environment")
    # asyncpg expects postgresql:// (no +asyncpg)
    return dsn.replace("+asyncpg", "")


async def main():
    dsn = get_dsn()
    attempts = 10
    delay = 2
    last_err = None
    for i in range(1, attempts + 1):
        try:
            conn = await asyncpg.connect(dsn)
            try:
                # health check
                await conn.fetchval("SELECT 1")
                query = f"SELECT COUNT(*) FROM {TABLE}"
                cnt = await conn.fetchval(query)
                print(f"{TABLE} count:", cnt)
                return
            finally:
                await conn.close()
        except Exception as e:
            last_err = e
            if i < attempts:
                await asyncio.sleep(delay)
            else:
                break
    print("Error:", type(last_err).__name__, str(last_err))


if __name__ == "__main__":
    # Windows event loop policy compatibility
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    # Load .env from project root
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    asyncio.run(main())
