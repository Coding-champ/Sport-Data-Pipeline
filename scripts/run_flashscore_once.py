import asyncio
import sys
from pathlib import Path

# Ensure project root (parent of 'src') is on sys.path so 'src' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows-specific: use Selector loop to avoid shutdown warnings on Windows
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from src.apps.sports_data_app import SportsDataApp
from src.core.config import Settings


async def main():
    settings = Settings()
    app = SportsDataApp(settings)
    try:
        await app.initialize()
        res = await app.scraping_orchestrator.run_scraping_job(["flashscore"])
        print(res)
    finally:
        await app.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
