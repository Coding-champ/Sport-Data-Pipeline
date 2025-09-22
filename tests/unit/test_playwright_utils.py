import asyncio
import types
import pytest

from src.common.playwright_utils import FetchOptions, fetch_page, PlaywrightFetchError


class DummyLocator:
    def __init__(self, visible=True):
        self._visible = visible
    async def is_visible(self, timeout=None):  # noqa: ARG002
        return self._visible
    async def click(self, timeout=None):  # noqa: ARG002
        return None
    @property
    def first(self):
        return self


class DummyPage:
    def __init__(self, *, fail=False, html="<html><body><div id='ok'>OK</div></body></html>"):
        self.fail = fail
        self._html = html
        self.goto_calls = 0
        self.wait_for_selector_calls = []
        self.mouse = types.SimpleNamespace(wheel=lambda *_: None)
    async def goto(self, url, wait_until="domcontentloaded", timeout=0):  # noqa: ARG002
        self.goto_calls += 1
        if self.fail:
            raise RuntimeError("goto failed")
    async def wait_for_selector(self, selector, timeout=0):  # noqa: ARG002
        self.wait_for_selector_calls.append(selector)
        return None
    async def wait_for_load_state(self, state):  # noqa: ARG002
        return None
    async def content(self):
        return self._html
    async def wait_for_timeout(self, ms):  # noqa: ARG002
        return None
    def locator(self, sel):
        return DummyLocator()


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
        self.chromium = types.SimpleNamespace(launch=lambda headless=True: DummyBrowser(page))
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False


@pytest.mark.asyncio
async def test_fetch_page_success(monkeypatch):
    page = DummyPage()

    async def fake_async_playwright():
        class Ctx:
            async def __aenter__(self_inner):
                return DummyP(page)
            async def __aexit__(self_inner, exc_type, exc, tb):  # noqa: ARG002
                return False
        return Ctx()

    monkeypatch.setattr("src.common.playwright_utils.async_playwright", fake_async_playwright)

    html = await fetch_page(FetchOptions(url="https://example.org", wait_selectors=["#ok"]))
    assert "OK" in html


@pytest.mark.asyncio
async def test_fetch_page_retry_and_fail(monkeypatch):
    failing_page = DummyPage(fail=True)

    async def fake_async_playwright():
        class Ctx:
            async def __aenter__(self_inner):
                return DummyP(failing_page)
            async def __aexit__(self_inner, exc_type, exc, tb):  # noqa: ARG002
                return False
        return Ctx()

    monkeypatch.setattr("src.common.playwright_utils.async_playwright", fake_async_playwright)

    opts = FetchOptions(url="https://fail.example", retries=2, backoff_base=0.01)
    with pytest.raises(PlaywrightFetchError):
        await fetch_page(opts)
