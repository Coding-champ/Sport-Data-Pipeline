#!/usr/bin/env python3
"""
Scrape Bundesliga clubs overview and per-club pages from:
  https://www.bundesliga.com/de/bundesliga/clubs

Outputs JSON with entries per club containing:
- club_id (best-effort, from JSON-LD or data attributes)
- club_name
- url (club page)
- matchday (Spieltag) if detectable on the club page
- stats (best-effort dictionary parsed from embedded JSON or visible key/value blocks)

Usage:
  python -u scripts/scrape_bundesliga_clubs.py \
    --out reports/bundesliga_clubs.json \
    --delay 0.8 --timeout 25 --retries 2 --verbose
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup  # type: ignore

try:
    # Optional: used when --render is passed
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:
    sync_playwright = None  # type: ignore

MAIN_URL = "https://www.bundesliga.com/de/bundesliga/clubs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class ClubData:
    club_id: str | None
    club_name: str | None
    url: str
    matchday: int | None
    stats: dict[str, Any]


def fetch(
    url: str, timeout: float = 25.0, retries: int = 2, backoff: float = 1.6, verbose: bool = False
) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            if verbose:
                print(f"WARN: {url} -> HTTP {resp.status_code}")
        except Exception as e:
            last_exc = e
            if verbose:
                print(f"ERROR fetching {url}: {e}")
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch {url}")


def parse_club_links(html: str, base_url: str = MAIN_URL, verbose: bool = False) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Heuristic: Bundesliga club pages usually under /de/bundesliga/vereine or /de/bundesliga/clubs
        if re.search(r"/de/(?:bundesliga|2-bundesliga)/(?:clubs|vereine)/", href):
            url = urljoin(base_url, href)
            links.add(url)
        # Fallback: some links may be under /de/vereine/
        elif re.search(r"/de/.*vereine/", href):
            url = urljoin(base_url, href)
            # Require domain match to avoid external
            if urlparse(url).netloc.endswith("bundesliga.com"):
                links.add(url)
    # Remove overview-like links (ending with '/clubs' etc.)
    filtered = [u for u in links if not re.search(r"/(clubs|vereine)/?$", urlparse(u).path)]
    if verbose:
        print(f"Found {len(filtered)} club links")
    return sorted(filtered)


def _json_from_ld_scripts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            txt = s.string or s.get_text() or ""
            txt = txt.strip()
            if not txt:
                continue
            data = json.loads(txt)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                for d in data:
                    if isinstance(d, dict):
                        out.append(d)
        except Exception:
            continue
    return out


def extract_club_id(soup: BeautifulSoup, page_text: str) -> str | None:
    # 1) JSON-LD SportsTeam identifier
    for d in _json_from_ld_scripts(soup):
        t = d.get("@type") or d.get("type")
        if isinstance(t, str) and t.lower() in {"sportsteam", "organization"}:
            # Common fields: identifier, id, clubId
            for key in ("identifier", "id", "clubId"):
                val = d.get(key)
                if isinstance(val, str | int):
                    return str(val)
            # Sometimes identifier is nested
            ident = d.get("identifier")
            if isinstance(ident, dict):
                val = ident.get("value") or ident.get("@id")
                if val:
                    return str(val)
    # 2) data attributes on container
    container = soup.find(attrs={"data-club-id": True})
    if container:
        return str(container.get("data-club-id"))
    # 3) Raw JSON in page
    m = re.search(r"\bclubId\"?\s*[:=]\s*\"?(\d+)\"?", page_text)
    if m:
        return m.group(1)
    return None


def extract_matchday(soup: BeautifulSoup, page_text: str) -> int | None:
    # Try explicit labels near 'Spieltag' or 'Matchday'
    txt = soup.get_text(" ", strip=True)
    m = re.search(r"(?:Spieltag|Matchday)\s*(\d{1,2})", txt, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    # Look for JSON with current matchday
    m = re.search(
        r"\b(matchday|currentMatchday)\"?\s*[:=]\s*\"?(\d{1,2})\"?", page_text, flags=re.IGNORECASE
    )
    if m:
        try:
            return int(m.group(2))
        except Exception:
            pass
    return None


def extract_stats(soup: BeautifulSoup, page_text: str) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    # 1) Try to parse embedded JSON objects containing 'stats'
    for m in re.finditer(r"\{[^{}]*\bstats\b[^{}]*\}", page_text):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and isinstance(obj.get("stats"), dict | list):
                stats_key = obj.get("stats")
                if isinstance(stats_key, dict):
                    stats.update(stats_key)
                elif isinstance(stats_key, list):
                    # normalize list of {name: , value: }
                    for item in stats_key:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("label")
                            value = item.get("value")
                            if name is not None:
                                stats[str(name)] = value
        except Exception:
            continue

    # 2) Parse Angular-rendered club stats grids, e.g. .club-stats -> .stat-box .label/.value
    #    and the right-hand .club-stats-table with rows containing .key/.value
    def _cast_value(v: str) -> Any:
        v = v.strip()
        # try int
        if re.fullmatch(r"[-+]?\d+", v.replace("\u202f", "").replace(" ", "")):
            try:
                return int(v.replace("\u202f", "").replace(" ", ""))
            except Exception:
                pass
        # try float with comma or dot
        vv = v.replace("\u202f", "").replace(" ", "").replace(",", ".")
        if re.fullmatch(r"[-+]?\d*(?:\.\d+)?", vv) and vv not in ("", "."):
            try:
                return float(vv)
            except Exception:
                pass
        return v

    # Left panel tiles
    for box in soup.select(".club-stats .stat-box"):
        label_el = box.select_one(".label")
        value_el = box.select_one(".value")
        if not label_el or not value_el:
            continue
        key = label_el.get_text(strip=True)
        val = value_el.get_text(strip=True)
        if key:
            stats[key] = _cast_value(val)

    # Right panel table rows
    for row in soup.select(
        ".club-stats-table .row.element, .club-stats-table .row.element.even-row"
    ):
        key_el = row.select_one(".key")
        val_el = row.select_one(".value")
        if not key_el or not val_el:
            continue
        key = key_el.get_text(strip=True)
        val = val_el.get_text(strip=True)
        if key:
            # normalize extra spaces within parentheses labels, e.g., "Ballbesitz (%)"
            key = re.sub(r"\s+", " ", key)
            stats[key] = _cast_value(val)

    # 3) Fallback: generic visible key-value pairs near headings mentioning Statistik
    for section in soup.find_all(
        lambda tag: tag.name in ("section", "div") and tag.get_text(strip=True)
    ):
        heading = section.find(["h2", "h3", "h4", "strong"]) or section
        if heading and re.search(r"statistik", heading.get_text(strip=True), flags=re.IGNORECASE):
            for row in section.find_all(["li", "div", "p"]):
                text = row.get_text(" ", strip=True)
                m = re.match(r"(.+?):\s*(.+)$", text)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    if key and key.lower() not in ("statistik", "statistiken") and key not in stats:
                        stats[key] = _cast_value(val)
    return stats


def scrape(
    out_path: str, delay: float, timeout: float, retries: int, verbose: bool, render: bool = False
) -> list[ClubData]:
    main_html = fetch(MAIN_URL, timeout=timeout, retries=retries, verbose=verbose)
    club_links = parse_club_links(main_html, base_url=MAIN_URL, verbose=verbose)

    results: list[ClubData] = []
    pw = None
    browser = None
    context = None
    page = None
    try:
        if render:
            if sync_playwright is None:
                raise RuntimeError(
                    "Playwright not available. Install browsers: 'python -m playwright install' or run without --render."
                )
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS.get("User-Agent"))
            page = context.new_page()

        for i, url in enumerate(club_links, 1):
            if verbose:
                print(f"[{i}/{len(club_links)}] {url}")
            if render and page is not None:
                page.set_default_timeout(int(timeout * 1000))
                page.goto(url, wait_until="domcontentloaded")
                # wait for either of the stats containers to appear, but don't fail hard if missing
                try:
                    page.wait_for_selector(
                        ".club-stats, .club-stats-table", timeout=int(0.6 * timeout * 1000)
                    )
                except Exception:
                    pass
                html = page.content()
            else:
                html = fetch(url, timeout=timeout, retries=retries, verbose=verbose)
            soup = BeautifulSoup(html, "html.parser")

            # club name
            club_name = None
            title = soup.find("title")
            if title and title.get_text():
                club_name = re.sub(r"\s*[|].*$", "", title.get_text()).strip()
            if not club_name:
                h1 = soup.find(["h1", "h2"])
                if h1:
                    club_name = h1.get_text(strip=True)

            club_id = extract_club_id(soup, html)
            matchday = extract_matchday(soup, html)
            stats = extract_stats(soup, html)

            results.append(
                ClubData(
                    club_id=club_id,
                    club_name=club_name,
                    url=url,
                    matchday=matchday,
                    stats=stats,
                )
            )

            if delay > 0:
                time.sleep(delay)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass

    # write JSON
    payload = [asdict(r) for r in results]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"Saved {len(results)} clubs -> {out_path}")
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="Scrape Bundesliga clubs and stats")
    p.add_argument("--out", type=str, default="reports/bundesliga_clubs.json")
    p.add_argument("--delay", type=float, default=0.8)
    p.add_argument("--timeout", type=float, default=25.0)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--render",
        action="store_true",
        help="Render pages with Playwright to extract JS-inserted stats",
    )
    args = p.parse_args()

    scrape(
        out_path=args.out,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        verbose=args.verbose,
        render=args.render,
    )


if __name__ == "__main__":
    main()
