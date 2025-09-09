from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

# Shared async Playwright helpers used by multiple scrapers


async def accept_consent(page: Page) -> bool:
    """Attempt to accept cookie/consent banners on the given page or its frames.
    Returns True if any consent element was clicked.
    """
    candidates = [
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button[aria-label*='Accept']",
        "#onetrust-accept-btn-handler",
        "[id*='consent'] button",
        "[data-testid*='consent'] button",
        "button:has-text('I Accept')",
        "button:has-text('Agree')",
        "button:has-text('Zustimmen')",
        "button:has-text('Alle akzeptieren')",
    ]
    frames = [page] + list(page.frames)
    for frame in frames:
        for sel in candidates:
            try:
                el = await frame.query_selector(sel)
                if el:
                    await el.click()
                    await page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
    return False


async def infinite_scroll(page: Page, *, max_time_ms: int = 60000, idle_rounds: int = 2) -> None:
    """Scroll the page down until time or idle rounds elapsed to trigger lazy loading."""
    start = datetime.utcnow().timestamp() * 1000
    last_height = await page.evaluate("() => document.body.scrollHeight")
    idle = 0
    while (datetime.utcnow().timestamp() * 1000 - start) < max_time_ms and idle < idle_rounds:
        try:
            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(800)
            new_height = await page.evaluate("() => document.body.scrollHeight")
            if new_height == last_height:
                idle += 1
            else:
                idle = 0
            last_height = new_height
        except Exception:
            break


async def extract_next_data(page: Page) -> List[Dict[str, Any]]:
    """Extract items from Next.js __NEXT_DATA__ as a normalized list of fixture-like dicts."""
    try:
        try:
            await page.wait_for_selector("#__NEXT_DATA__", timeout=1500)
        except Exception:
            pass
        payload = await page.evaluate(
            """() => {
            const el = document.getElementById('__NEXT_DATA__');
            return el ? el.textContent : null;
        }"""
        )
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except Exception:
            return []

        results: List[Dict[str, Any]] = []

        def walk(node: Any):
            if isinstance(node, dict):
                norm = normalize_game_node(node)
                if norm:
                    results.append(norm)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)

        seen = set()
        unique: List[Dict[str, Any]] = []
        for r in results:
            key = (r.get("id"), r.get("home"), r.get("away"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)
        return unique
    except Exception:
        return []


def extract_from_ld_json(json_texts: List[Dict[str, Any] | str]) -> Dict[str, Any]:
    """Parse schema.org SportsEvent from LD+JSON blocks and normalize."""
    for txt in json_texts:
        try:
            data = json.loads(txt) if isinstance(txt, str) else txt
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            typ = (node.get("@type") or "").lower()
            if "sportsevent" in typ or "event" in typ:
                home = None
                away = None
                home_id = None
                away_id = None

                def team_from(obj):
                    if isinstance(obj, dict):
                        name = obj.get("name") or obj.get("alternateName")
                        tid = obj.get("@id") or obj.get("identifier")
                        return name, tid
                    return None, None

                if node.get("homeTeam"):
                    home, home_id = team_from(node.get("homeTeam"))
                if node.get("awayTeam"):
                    away, away_id = team_from(node.get("awayTeam"))
                comps = node.get("competitor")
                if isinstance(comps, list) and (home is None or away is None):
                    if len(comps) >= 2:
                        hname, hid = team_from(comps[0])
                        aname, aid = team_from(comps[1])
                        home = home or hname
                        away = away or aname
                        home_id = home_id or hid
                        away_id = away_id or aid
                home_score = None
                away_score = None
                agg = node.get("aggregateScore") or node.get("result")
                if isinstance(agg, dict):
                    home_score = agg.get("home") or agg.get("homeScore")
                    away_score = agg.get("away") or agg.get("awayScore")
                if home or away:
                    return {
                        "id": node.get("@id") or node.get("identifier") or None,
                        "home": home,
                        "away": away,
                        "home_id": home_id,
                        "away_id": away_id,
                        "home_score": home_score,
                        "away_score": away_score,
                        "competition": (
                            (node.get("superEvent") or {}).get("name")
                            if isinstance(node.get("superEvent"), dict)
                            else None
                        ),
                        "competition_id": (
                            (node.get("superEvent") or {}).get("identifier")
                            if isinstance(node.get("superEvent"), dict)
                            else None
                        ),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
    return {}


def parse_captured_json(captured_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse fixture/game data structures from captured network JSON with normalization."""
    results: List[Dict[str, Any]] = []

    def walk(node: Any):
        if isinstance(node, dict):
            norm = normalize_game_node(node)
            if norm:
                results.append(norm)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for item in captured_json:
        walk(item.get("data"))

    seen = set()
    unique: List[Dict[str, Any]] = []
    for r in results:
        key = (r.get("id"), r.get("home"), r.get("away"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def normalize_game_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize various game/fixture node shapes into a flat record with names/ids and scores."""
    if not isinstance(node, dict):
        return {}

    keys = set(node.keys())
    looks_like_game = (
        (
            ("home" in keys or "homeTeam" in keys or "teams" in keys or "participants" in keys)
            and ("away" in keys or "awayTeam" in keys or "teams" in keys or "participants" in keys)
        )
        or ({"id", "score"} <= keys)
        or ({"homeScore", "awayScore"} <= keys)
    )
    if not looks_like_game:
        return {}

    def first(*vals):
        for v in vals:
            if v is not None:
                return v
        return None

    home_obj = first(
        node.get("home"),
        node.get("homeTeam"),
        (node.get("teams") or {}).get("home") if isinstance(node.get("teams"), dict) else None,
    )
    away_obj = first(
        node.get("away"),
        node.get("awayTeam"),
        (node.get("teams") or {}).get("away") if isinstance(node.get("teams"), dict) else None,
    )
    parts = node.get("participants") if isinstance(node.get("participants"), list) else []
    if not home_obj or not away_obj:
        for p in parts:
            side = (p.get("side") or p.get("homeAway") or p.get("alignment") or "").lower()
            if side in ("home", "h") and not home_obj:
                home_obj = p
            if side in ("away", "a") and not away_obj:
                away_obj = p

    def team_name(obj):
        if not obj:
            return None
        if isinstance(obj, str):
            return obj
        return first(
            obj.get("name"), obj.get("shortName"), obj.get("abbr"), obj.get("code"), obj.get("slug")
        )

    def team_id(obj):
        if not obj:
            return None
        if isinstance(obj, str):
            return None
        return first(
            obj.get("id"),
            obj.get("teamId"),
            obj.get("externalId"),
            obj.get("slug"),
            obj.get("code"),
        )

    score_val = first(node.get("score"), node.get("result"))
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    if isinstance(score_val, str):
        try:
            parts = [int(x) for x in score_val.replace(":", "-").split("-") if x.strip().isdigit()]
            if len(parts) >= 2:
                home_score, away_score = parts[0], parts[1]
        except Exception:
            pass
    elif isinstance(score_val, dict):
        home_score = first(score_val.get("home"), score_val.get("h"))
        away_score = first(score_val.get("away"), score_val.get("a"))
    home_score = first(home_score, node.get("homeScore"), node.get("scoreHome"))
    away_score = first(away_score, node.get("awayScore"), node.get("scoreAway"))
    scores = node.get("scores") if isinstance(node.get("scores"), dict) else None
    if scores:
        ft = scores.get("ft") if isinstance(scores.get("ft"), dict) else scores
        home_score = first(home_score, ft.get("home") if isinstance(ft, dict) else None)
        away_score = first(away_score, ft.get("away") if isinstance(ft, dict) else None)

    return {
        "id": first(
            node.get("id"),
            node.get("externalId"),
            node.get("fixtureId"),
            node.get("slug"),
            node.get("code"),
        ),
        "home": team_name(home_obj),
        "away": team_name(away_obj),
        "home_id": team_id(home_obj),
        "away_id": team_id(away_obj),
        "home_score": home_score,
        "away_score": away_score,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def list_data_testids(page: Page, limit: int = 20) -> List[Dict[str, Any]]:
    """Small helper useful for diagnostics to list elements with data-testid."""
    return await page.evaluate(
        r"""(limit) => {
        return Array.from(document.querySelectorAll('[data-testid]'))
            .slice(0, limit)
            .map(el => ({
                tag: el.tagName,
                testid: el.getAttribute('data-testid'),
                text: (el.textContent||'').trim().replace(/\s+/g,' ').substring(0, 50),
                id: el.id || null,
                class: el.className || null
            }));
        }""",
        limit,
    )

import contextlib
from dataclasses import dataclass

try:
    from playwright.sync_api import TimeoutError as PWTimeoutError  # type: ignore
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None  # type: ignore
    PWTimeoutError = Exception  # type: ignore


@dataclass
class RenderWait:
    selectors: list[str] | None = None
    text_contains: list[str] | None = None
    network_idle: bool = False


class BrowserSession:
    """
    Thin convenience wrapper for Playwright sync API.

    Usage:
        with BrowserSession(headless=True, user_agent=..., proxy=...) as bs:
            html = bs.render_page(url, wait=RenderWait(selectors=[".stats"]))
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        user_agent: str | None = None,
        proxy: str | None = None,
        default_timeout_s: float = 30.0,
    ) -> None:
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = headless
        self._user_agent = user_agent
        self._proxy = proxy
        self._default_timeout_ms = int(default_timeout_s * 1000)

    def __enter__(self):
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not available. Install the package and browsers: 'pip install playwright' and 'python -m playwright install'"
            )
        self._pw = sync_playwright().start()
        launch_args = {"headless": self._headless}
        if self._proxy:
            launch_args["proxy"] = {"server": self._proxy}
        self._browser = self._pw.chromium.launch(**launch_args)
        context_args = {}
        if self._user_agent:
            context_args["user_agent"] = self._user_agent
        self._context = self._browser.new_context(**context_args)
        self._page = self._context.new_page()
        self._page.set_default_timeout(self._default_timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb):
        with contextlib.suppress(Exception):
            if self._page:
                self._page.close()
        with contextlib.suppress(Exception):
            if self._context:
                self._context.close()
        with contextlib.suppress(Exception):
            if self._browser:
                self._browser.close()
        with contextlib.suppress(Exception):
            if self._pw:
                self._pw.stop()

    def render_page(
        self,
        url: str,
        *,
        wait: RenderWait | None = None,
        timeout_s: float | None = None,
        wait_until: str = "domcontentloaded",
    ) -> str:
        if not self._page:
            raise RuntimeError("BrowserSession not started")
        if timeout_s is not None:
            self._page.set_default_timeout(int(timeout_s * 1000))
        self._page.goto(url, wait_until=wait_until)

        # Apply waits in order: selectors -> text -> network idle
        if wait and wait.selectors:
            for sel in wait.selectors:
                try:
                    self._page.wait_for_selector(sel, state="attached")
                except PWTimeoutError:
                    # continue; we still return HTML to allow parsing fallbacks
                    pass
        if wait and wait.text_contains:
            for t in wait.text_contains:
                try:
                    self._page.wait_for_selector(f':has-text("{t}")')
                except PWTimeoutError:
                    pass
        if wait and wait.network_idle:
            with contextlib.suppress(Exception):
                self._page.wait_for_load_state("networkidle")

        return self._page.content()

    def screenshot(self, path: str) -> None:
        if not self._page:
            raise RuntimeError("BrowserSession not started")
        self._page.screenshot(path=path, full_page=True)
