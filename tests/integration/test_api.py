from typing import Any

from fastapi.testclient import TestClient

from src.api.main import create_fastapi_app
from src.core.config import Settings


class _DummyDB:
    async def initialize(self) -> None:  # pragma: no cover
        return None

    async def close(self) -> None:  # pragma: no cover
        return None


class _DummyMetrics:
    def __init__(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        pass

    def start_metrics_server(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        pass

    def export_metrics(self) -> str:  # pragma: no cover
        return ""

    def record_api_request(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        pass


def _build_test_app():
    settings = Settings(enable_metrics=False)
    app = create_fastapi_app(
        settings,
        data_app=None,
        analytics_app=None,
        db_manager=_DummyDB(),
        metrics=_DummyMetrics(),
    )
    return app


def test_health_and_openapi_routes_present():
    app = _build_test_app()
    with TestClient(app) as client:
        # Health endpoint
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

        # OpenAPI contains aggregated routers with expected tags
        s = client.get("/openapi.json")
        assert s.status_code == 200
        schema = s.json()
        # Collect tags used in paths
        tags_in_paths = set()
        for _, path_item in schema.get("paths", {}).items():
            for method_spec in path_item.values():
                for tag in method_spec.get("tags", []):
                    tags_in_paths.add(tag)
        for expected in {"players", "matches", "teams", "clubs"}:
            assert expected in tags_in_paths


