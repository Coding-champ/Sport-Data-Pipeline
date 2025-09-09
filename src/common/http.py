import random
import time
from typing import Any, Optional

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
