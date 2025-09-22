import random
import time
import os
from typing import Any, Optional, Iterable, Sequence, Callable

try:  # Optional playwright dependency isolation
    from common.playwright_utils import BrowserSession, RenderWait  # type: ignore
except Exception:  # pragma: no cover - optional path
    BrowserSession = None  # type: ignore
    RenderWait = None  # type: ignore

import requests

# Shared defaults
DEFAULT_UAS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "de-DE,de;q=0.9,en;q=0.8",
]
ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
]


def build_headers(
    user_agent: str, *, header_randomize: bool, accept_json: bool = False
) -> dict[str, str]:
    headers = {"User-Agent": user_agent}
    if accept_json:
        headers["Accept"] = "application/json, text/plain, */*"
    elif header_randomize:
        headers["Accept-Language"] = random.choice(ACCEPT_LANGUAGES)
        headers["Accept"] = random.choice(ACCEPT_HEADERS)
    return headers


def _pick_user_agent(
    ua_pool: list[str], *, rotate_ua: bool, force_ua_on_429: bool, last_status: Optional[int]
) -> str:
    if rotate_ua:
        return random.choice(ua_pool)
    if force_ua_on_429 and last_status == 429 and len(ua_pool) > 1:
        # pick a different UA than the first default
        return random.choice([u for u in ua_pool if u != ua_pool[0]])
    return ua_pool[0]


def fetch_html(
    url: str,
    *,
    timeout: float,
    retries: int,
    backoff: float,
    proxy: Optional[str],
    verbose: bool,
    user_agents: Optional[list[str]],
    rotate_ua: bool,
    force_ua_on_429: bool,
    header_randomize: bool,
    pre_jitter: float,
) -> str:
    session = requests.Session()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    last_status: Optional[int] = None
    ua_pool = user_agents or DEFAULT_UAS

    for attempt in range(1, max(1, retries) + 1):
        try:
            if pre_jitter and pre_jitter > 0:
                d = random.uniform(0, pre_jitter)
                if verbose:
                    print(f"pre-jitter: {d:.2f}s")
                time.sleep(d)

            ua = _pick_user_agent(
                ua_pool,
                rotate_ua=rotate_ua,
                force_ua_on_429=force_ua_on_429,
                last_status=last_status,
            )
            headers = build_headers(ua, header_randomize=header_randomize, accept_json=False)
            if verbose:
                print(f"GET {url} [attempt {attempt}] UA={ua[:50]}...")

            r = session.get(url, timeout=timeout, proxies=proxies, headers=headers)
            if r.status_code in (429, 502, 503, 504):
                last_status = r.status_code
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.text
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            if attempt >= retries:
                raise
            sleep_s = (backoff ** (attempt - 1)) + random.uniform(0.2, 0.6)
            if verbose:
                print(f"Attempt {attempt} failed: {e} -> sleep {sleep_s:.2f}s")
            time.sleep(sleep_s)
    raise RuntimeError("unreachable")


def fetch_json(
    url: str,
    *,
    timeout: float,
    retries: int,
    backoff: float,
    proxy: Optional[str],
    verbose: bool,
    user_agents: Optional[list[str]],
    rotate_ua: bool,
    force_ua_on_429: bool,
    pre_jitter: float,
) -> Any:
    session = requests.Session()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    last_status: Optional[int] = None
    ua_pool = user_agents or DEFAULT_UAS

    for attempt in range(1, max(1, retries) + 1):
        try:
            if pre_jitter and pre_jitter > 0:
                d = random.uniform(0, pre_jitter)
                if verbose:
                    print(f"pre-jitter: {d:.2f}s")
                time.sleep(d)

            ua = _pick_user_agent(
                ua_pool,
                rotate_ua=rotate_ua,
                force_ua_on_429=force_ua_on_429,
                last_status=last_status,
            )
            headers = build_headers(ua, header_randomize=False, accept_json=True)
            if verbose:
                print(f"GET {url} [attempt {attempt}] UA={ua[:50]}... (json)")

            r = session.get(url, timeout=timeout, proxies=proxies, headers=headers)
            if r.status_code in (429, 502, 503, 504):
                last_status = r.status_code
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError) as e:
            if attempt >= retries:
                raise
            sleep_s = (backoff ** (attempt - 1)) + random.uniform(0.2, 0.6)
            if verbose:
                print(f"Attempt {attempt} failed (json): {e} -> sleep {sleep_s:.2f}s")
            time.sleep(sleep_s)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# Unified helper for conditional Playwright render with graceful fallback
# (used by multiple lightweight CLI scrapers). Kept here to avoid another
# small utility module; depends only on existing imports.
# ---------------------------------------------------------------------------
def render_or_fetch(
    url: str,
    *,
    args: Any,
    default_wait_selectors: Optional[Sequence[str]] = None,
) -> str:
    """Render a page with Playwright if args.render is true, otherwise plain HTTP.

    Falls back to HTTP fetch on any rendering exception. Keeps side‑effects and
    argument names consistent across small scraper entry points. The *args*
    object is an argparse Namespace (duck-typed) providing the following fields:
        - render, render_wait_selector, render_wait_text, render_wait_network_idle,
          render_headful, render_timeout, proxy, timeout, retries, backoff,
          verbose, ua_file, ua_rotate, force_ua_on_429, no_header_randomize,
          pre_jitter
    """
    if getattr(args, "render", False) and BrowserSession and RenderWait:
        try:
            # Build wait conditions
            raw_selectors = getattr(args, "render_wait_selector", "") or ""
            wait_selectors = [s.strip() for s in raw_selectors.split(",") if s.strip()] or list(
                default_wait_selectors or []
            )
            raw_texts = getattr(args, "render_wait_text", "") or ""
            wait_texts = [t.strip() for t in raw_texts.split(",") if t.strip()]
            wait = RenderWait(
                selectors=wait_selectors or None,
                text_contains=wait_texts or None,
                network_idle=getattr(args, "render_wait_network_idle", False),
            )
            if getattr(args, "verbose", False):
                print(
                    f"[render] {url} wait selectors={wait_selectors} text={wait_texts} network_idle={getattr(args,'render_wait_network_idle', False)}"
                )
            ua_pool = (
                open(args.ua_file, encoding="utf-8").read().splitlines()
                if getattr(args, "ua_file", None) and getattr(args, "ua_file") and os.path.exists(args.ua_file)
                else DEFAULT_UAS
            )
            ua = random.choice(ua_pool) if getattr(args, "ua_rotate", False) else ua_pool[0]
            with BrowserSession(
                headless=not getattr(args, "render_headful", False),
                user_agent=ua,
                proxy=getattr(args, "proxy", None),
                default_timeout_s=getattr(args, "render_timeout", 35.0),
            ) as bs:  # type: ignore
                return bs.render_page(url, wait=wait, timeout_s=getattr(args, "render_timeout", 35.0))
        except Exception as e:  # noqa: BLE001
            if getattr(args, "verbose", False):
                print(f"[render->fallback] {e}")
            # fall through to plain fetch
    # Plain HTTP
    return fetch_html(
        url,
        timeout=getattr(args, "timeout", 45.0),
        retries=getattr(args, "retries", 3),
        backoff=getattr(args, "backoff", 1.5),
        proxy=getattr(args, "proxy", None),
        verbose=getattr(args, "verbose", False),
        user_agents=(
            open(args.ua_file, encoding="utf-8").read().splitlines()
            if getattr(args, "ua_file", None) and getattr(args, "ua_file") and os.path.exists(args.ua_file)
            else DEFAULT_UAS
        ),
        rotate_ua=getattr(args, "ua_rotate", False),
        force_ua_on_429=getattr(args, "force_ua_on_429", False),
        header_randomize=not getattr(args, "no_header_randomize", False),
        pre_jitter=getattr(args, "pre_jitter", 0.0),
    )
