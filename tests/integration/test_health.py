import httpx
import pytest

from src.api.main import create_fastapi_app
from src.core.config import Settings


@pytest.mark.asyncio
async def test_health_endpoint():
    settings = Settings()
    app = create_fastapi_app(settings, data_app=None, analytics_app=None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
