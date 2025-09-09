import asyncio
import sys
from pathlib import Path

# Ensure project root and src on path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

import traceback

import httpx

from src.api.main import create_fastapi_app
from src.core.config import Settings


async def main():
    # Minimize feature set to focus on API only
    settings = Settings()
    try:
        app = create_fastapi_app(settings, data_app=None, analytics_app=None)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            print("/health status:", resp.status_code, flush=True)
            print("/health body:", resp.json(), flush=True)
    except Exception as e:
        print("API health smoke failed:", e, flush=True)
        print(traceback.format_exc(), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
