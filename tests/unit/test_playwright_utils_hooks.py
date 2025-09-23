import asyncio
import types
import pytest

from src.common.playwright_utils import FetchOptions, FetchHooks, fetch_page_with_hooks, PlaywrightFetchError

# Reuse Dummy structures conceptually similar to earlier test, but adjusted for hook paths.

class DummyResponse:
    def __init__(self, url, status=200, json_data=None, headers=None):
        self.url = url
        self._json = json_data
        self.status = status
        self.headers = headers or {"content-type": "application/json"}
    async def json(self):
        await asyncio.sleep(0)
        return self._json

class DummyConsoleMsg:
    def __init__(self, typ, text):
        self.type = typ
        self.text = text

class DummyPage:
    def __init__(self, *, fail_first=False):
        self.fail_first = fail_first
        self.goto_calls = 0
        self._responses = []
        self._console = []
        self._handlers = {"response": [], "console": [], "request": []}
        self.mouse = types.SimpleNamespace(wheel=lambda *_: None)
    def on(self, evt, cb):
        self._handlers[evt].append(cb)
    async def goto(self, url, wait_until="domcontentloaded", timeout=0):  # noqa: ARG002
        self.goto_calls += 1
        if self.fail_first and self.goto_calls == 1:
            raise RuntimeError("boom")
        # simulate events
        for rcb in self._handlers["response"]:
            rcb(DummyResponse(url+"/api/fixture", json_data={"key": "value"}))
        for ccb in self._handlers["console"]:
            ccb(DummyConsoleMsg("log", "hello"))
    async def wait_for_selector(self, selector, timeout=0):  # noqa: ARG002
        return None
    async def wait_for_load_state(self, state):  # noqa: ARG002
        return None
    async def content(self):
        return "<html><body>OK</body></html>"
    async def wait_for_timeout(self, ms):  # noqa: ARG002
        return None

class DummyContext:
    def __init__(self, page):
        self._page = page
    async def new_page(self):
        return self._page
    async def close(self):
        return None

class DummyBrowser:
    def __init__(self, page):
        self._page = page
    async def new_context(self, **kwargs):  # noqa: ARG002
        return DummyContext(self._page)
    async def close(self):
        return None

class DummyP:
    def __init__(self, page):
        async def launch(headless=True):  # noqa: ARG002
            return DummyBrowser(page)
        self.chromium = types.SimpleNamespace(launch=launch)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False

@pytest.mark.asyncio
async def test_fetch_page_with_hooks_success(monkeypatch):
    page = DummyPage()
    def fake_async_playwright():
        class Ctx:
            async def __aenter__(self_inner):
                return DummyP(page)
            async def __aexit__(self_inner, exc_type, exc, tb):  # noqa: ARG002
                return False
        return Ctx()
    monkeypatch.setattr("src.common.playwright_utils.async_playwright", fake_async_playwright)

    received = {"responses":0, "console":0, "ready":False, "before":False}

    def on_resp(resp, p, acc):  # noqa: ARG002
        received["responses"] += 1
    def on_console(msg, p, acc):  # noqa: ARG002
        received["console"] += 1
    def on_ready(p):  # noqa: ARG002
        received["ready"] = True
    def before_return(p, meta):  # noqa: ARG002
        meta["marker"] = True
        received["before"] = True

    hooks = FetchHooks(
        on_response=on_resp,
        on_console=on_console,
        on_page_ready=on_ready,
        before_return=before_return,
    )
    res = await fetch_page_with_hooks(FetchOptions(url="https://example.org"), hooks)
    assert "OK" in res.html
    assert received["responses"] >= 1
    assert received["console"] >= 1
    assert received["ready"] is True
    assert received["before"] is True
    assert res.meta.get("marker") is True

@pytest.mark.asyncio
async def test_fetch_page_with_hooks_retry(monkeypatch):
    page = DummyPage(fail_first=True)
    def fake_async_playwright():
        class Ctx:
            async def __aenter__(self_inner):
                return DummyP(page)
            async def __aexit__(self_inner, exc_type, exc, tb):  # noqa: ARG002
                return False
        return Ctx()
    monkeypatch.setattr("src.common.playwright_utils.async_playwright", fake_async_playwright)

    attempts = []
    def on_error(exc, attempt):
        attempts.append(attempt)

    hooks = FetchHooks(on_error=on_error)
    res = await fetch_page_with_hooks(FetchOptions(url="https://retry.example", retries=2, backoff_base=0.01), hooks)
    assert res.meta["attempt"] == 2  # second attempt succeeded
    assert 1 in attempts
