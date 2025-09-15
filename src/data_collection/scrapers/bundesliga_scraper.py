"""
Bundesliga.com matchday scraper

Usage: instantiate with season label (e.g. "2025-2026") and matchday (int), then call scrape_data().
Collects per-match data: teams, score, season, matchday, kickoff (UTC), stadium, referee, source URL.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapingConfig


@dataclass
class BundesligaScraperConfig(ScrapingConfig):
    # Provide defaults for all base fields to satisfy dataclass ordering rules
    base_url: str = "https://www.bundesliga.com"
    selectors: dict[str, str] = field(default_factory=dict)  # rely on JSON-LD and href patterns
    headers: dict[str, str] = field(default_factory=dict)
    delay_range: tuple = (1, 3)
    max_retries: int = 3
    timeout: int = 30
    use_proxy: bool = False
    proxy_list: Optional[list[str]] = None
    anti_detection: bool = True
    screenshot_on_error: bool = True


def _extract_ld_json(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            txt = (s.string or s.get_text() or "").strip()
            if not txt:
                continue
            data = json.loads(txt)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend([d for d in data if isinstance(d, dict)])
        except Exception:
            continue
    return out


def _pick_event(ld_objs: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for d in ld_objs:
        t = d.get("@type") or d.get("type")
        if not t:
            continue
        t_l = t if isinstance(t, str) else (t[0] if isinstance(t, list) and t else None)
        if not isinstance(t_l, str):
            continue
        if t_l.lower() in {"sportsevent", "soccer", "soccerseasongame", "event"}:
            return d
    return None


def _find_labeled_value(soup: BeautifulSoup, labels: list[str]) -> str | None:
    """Finds a value on the page by looking for label:value pairs or definition lists.
    Tries patterns like <dt>Label</dt><dd>Value</dd> or <span>Label:</span> Value.
    """
    # 1) Definition list dt/dd
    lbl_re = re.compile(rf"^({'|'.join(map(re.escape, labels))})\s*:?$", flags=re.I)
    dt = soup.find(lambda tag: tag.name in {"dt", "strong", "span"} and tag.get_text(strip=True) and lbl_re.match(tag.get_text(strip=True) or ""))
    if dt:
        # Prefer dd sibling for dt
        if dt.name == "dt":
            dd = dt.find_next_sibling("dd")
            if dd:
                val = dd.get_text(" ", strip=True)
                if val:
                    return val
        # Otherwise try immediate next sibling text
        sib_text = (dt.next_sibling.get_text(" ", strip=True) if hasattr(dt.next_sibling, "get_text") else (str(dt.next_sibling).strip() if dt.next_sibling else ""))
        if sib_text:
            return sib_text

    # 2) Generic label: value text search within small blocks
    # Search small containers to limit spillover
    for container in soup.find_all(["p", "li", "div", "section"], limit=200):
        txt = container.get_text(" ", strip=True)
        if not txt or len(txt) > 500:
            continue
        m = re.search(rf"({'|'.join(map(re.escape, labels))})\s*:\s*(.+)$", txt, flags=re.I)
        if m:
            val = m.group(2).strip()
            # Truncate at common delimiters
            for delim in ["  ", " | ", " |", "|", " ©", "©", " Watch", " Hello", " Our Apps", " Privacy", " Cookie", " Terms", " Imprint"]:
                cut = val.find(delim)
                if cut != -1:
                    val = val[:cut].strip()
                    break
            # Cap length to avoid runaway captures
            if len(val) > 80:
                val = val[:80].rstrip()
            if val:
                return val
    return None


def _clean_person_name(val: str) -> str:
    val = re.sub(r"\s+", " ", val or "").strip(" :-|•\t\r\n")
    # Truncate at common delimiters
    for delim in ["  ", " | ", " |", "|", " - ", " — ", " – ", " • ", " ©", "©", " Watch", " Hello", " Our Apps", " Privacy", " Cookie", " Terms", " Imprint"]:
        cut = val.find(delim)
        if cut != -1:
            val = val[:cut].strip()
            break
    # Limit to a few tokens
    tokens = [t for t in val.split() if t]
    if len(tokens) > 5:
        tokens = tokens[:5]
    return " ".join(tokens)


def _extract_referee_from_ld(ld_objs: Iterable[dict[str, Any]]) -> str | None:
    """Extract referee name from JSON-LD by matching roles like Referee/Schiedsrichter.
    Looks into keys: 'referee', 'officiatingCrew' and variants.
    """
    # Helper to pick from a container (dict or list)
    def pick_from_container(container) -> str | None:
        items: list[dict[str, Any]] = []
        if isinstance(container, dict):
            items = [container]
        elif isinstance(container, list):
            items = [x for x in container if isinstance(x, dict)]
        for it in items:
            # Build role meta
            meta = " ".join(
                str(it.get(k, "")) for k in ("roleName", "jobTitle", "description", "@type", "role")
            ).lower()
            name = it.get("name") or (" ".join(filter(None, [it.get("givenName"), it.get("familyName")])).strip())
            if ("referee" in meta or "schiedsrichter" in meta) and name:
                return _clean_person_name(name)
        return None

    for d in ld_objs:
        # Direct referee key
        val = d.get("referee")
        if isinstance(val, dict) and val.get("name"):
            return _clean_person_name(val.get("name"))
        if isinstance(val, str) and val.strip():
            return _clean_person_name(val)
        # Officiating crew containers
        for key in ("officiatingCrew", "officiatingcrew"):
            crew = d.get(key)
            picked = pick_from_container(crew)
            if picked:
                return picked
    return None


class BundesligaMatchdayScraper(BaseScraper):
    name = "bundesliga"

    def __init__(self, db_manager, season_label: str, matchday: int):
        cfg = BundesligaScraperConfig(delay_range=(1, 2), timeout=30, max_retries=3)
        super().__init__(cfg, db_manager, self.name)
        self.season_label = season_label
        self.matchday = int(matchday)

    def _matchday_url(self) -> str:
        return f"https://www.bundesliga.com/en/bundesliga/matchday/{self.season_label}/{self.matchday}"

    async def scrape_data(self) -> list[dict]:
        url = self._matchday_url()
        html = await self.fetch_page(url)
        soup = self.parse_html(html)
        links = self._extract_match_links(soup, base=url)
        results: list[dict] = []
        for link in links:
            try:
                match_html = await self.fetch_page(link)
                item = self._parse_match_page(match_html, link)
                if item:
                    item.update(
                        {
                            "season": self.season_label,
                            "matchday": self.matchday,
                            "url": link,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    results.append(item)
            except Exception:
                # ignore single-match failures
                continue
        return results

    def _extract_match_links(self, soup: BeautifulSoup, base: str) -> list[str]:
        hrefs: set[str] = set()
        # Prefer English path; fall back to any matchday link containing the current season and matchday
        season = re.escape(self.season_label)
        md = re.escape(str(self.matchday))
        pat = re.compile(rf"/(en|de)/bundesliga/matchday/{season}/{md}/[a-z0-9\-]+", re.I)
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0]
            if pat.search(href):
                hrefs.add(urljoin(base, href))
        # Deduplicate and return
        return sorted(hrefs)

    def _parse_match_page(self, html: str, url: str) -> dict | None:
        soup = self.parse_html(html)
        ld = _extract_ld_json(soup)
        ev = _pick_event(ld) or {}

        # Teams
        home_name = None
        away_name = None
        for key in ("homeTeam", "home", "competitor", "performer"):
            v = ev.get(key)
            if isinstance(v, list):
                # Try to infer teams from list of performers/competitors
                names = [x.get("name") for x in v if isinstance(x, dict) and x.get("name")]
                if len(names) >= 2:
                    home_name, away_name = names[0], names[1]
                    break
            elif isinstance(v, dict):
                # some LDs have homeTeam/awayTeam directly
                home_name = v.get("name") if not home_name else home_name
        if not home_name:
            # Try meta or page title heuristics
            ttl = soup.title.get_text(strip=True) if soup.title else ""
            m = re.search(r"^(.*?)\s+vs\s+(.*?)(?:\s+|$)", ttl, flags=re.I)
            if m:
                home_name, away_name = m.group(1), m.group(2)

        away_from_ev = ev.get("awayTeam") if isinstance(ev.get("awayTeam"), dict) else None
        if isinstance(away_from_ev, dict) and away_from_ev.get("name"):
            away_name = away_from_ev.get("name")

        # Score
        home_score = None
        away_score = None
        for k in ("homeScore", "awayScore"):
            if k in ev and isinstance(ev[k], (int, float, str)):
                try:
                    if k == "homeScore":
                        home_score = int(str(ev[k]))
                    else:
                        away_score = int(str(ev[k]))
                except Exception:
                    pass
        if home_score is None or away_score is None:
            txt = soup.get_text(" ", strip=True)
            m = re.search(r"(\d{1,2})\s*[-:\u2013]\s*(\d{1,2})", txt)
            if m:
                try:
                    home_score = int(m.group(1))
                    away_score = int(m.group(2))
                except Exception:
                    pass

        # Kickoff
        kickoff_iso = ev.get("startDate") if isinstance(ev.get("startDate"), str) else None
        # Stadium
        stadium = None
        loc = ev.get("location")
        if isinstance(loc, dict):
            # Common LD patterns
            stadium = (
                loc.get("name")
                or ((loc.get("address") or {}).get("name") if isinstance(loc.get("address"), dict) else None)
                or ((loc.get("containedInPlace") or {}).get("name") if isinstance(loc.get("containedInPlace"), dict) else None)
            )
        if not stadium:
            # Structured label-value search
            stadium = _find_labeled_value(soup, ["Stadium", "Stadion", "Venue", "Spielort"])
        if not stadium:
            # Microdata/meta tags
            venue_meta = soup.find(attrs={"itemprop": "location"})
            if venue_meta:
                vn = venue_meta.get("content") or venue_meta.get("aria-label") or venue_meta.get_text(strip=True)
                stadium = vn or stadium
        # Referee
        referee = _extract_referee_from_ld(ld) or None
        if not referee:
            # Look for explicit HTML block e.g., div.matchInfoReferee
            ref_div = soup.find(
                lambda tag: tag and tag.get("class") and any(
                    isinstance(c, str) and "matchInfoReferee" in c for c in tag.get("class", [])
                )
            )
            if ref_div:
                block_txt = ref_div.get_text(" ", strip=True)
                m = re.search(r"(?:Referee|Schiedsrichter)\s*[:\-–—]?\s*(.+)$", block_txt, flags=re.I)
                if m:
                    referee = _clean_person_name(m.group(1))
                if not referee:
                    # Try to pick value from child spans/divs
                    parts = [
                        el.get_text(" ", strip=True)
                        for el in ref_div.find_all(["span", "div", "p"], recursive=True)
                    ]
                    parts = [p for p in parts if p]
                    # remove label tokens
                    parts = [p for p in parts if not re.match(r"^(Referee|Schiedsrichter)\b", p, flags=re.I)]
                    if parts:
                        referee = _clean_person_name(parts[0])
        if not referee:
            referee = _find_labeled_value(soup, ["Referee", "Schiedsrichter"]) or None
        if not referee:
            # Heuristic in page text (limit to typical name token patterns)
            for container in soup.find_all(["p", "li", "div", "section" ], limit=300):
                txt = container.get_text(" ", strip=True)
                if not txt or len(txt) > 400:
                    continue
                m = re.search(r"(?:Referee|Schiedsrichter)\s*[:\-–—]?\s*([A-Za-zÄÖÜäöüß'\-\.]+(?:\s+[A-Za-zÄÖÜäöüß'\-\.]+){0,4})", txt, flags=re.I)
                if m:
                    referee = _clean_person_name(m.group(1))
                    if referee:
                        break

        # Normalize and return
        if not (home_name and away_name):
            return None
        return {
            "home_team": home_name,
            "away_team": away_name,
            "home_score": home_score,
            "away_score": away_score,
            "kickoff_utc": kickoff_iso,
            "stadium": stadium,
            "referee": referee,
            "source": "bundesliga",
        }


# Simple CLI runner for ad-hoc testing
async def _run_once(season: str, matchday: int):
    from src.database.manager import DatabaseManager

    db = DatabaseManager()
    # Optional: only initialize async pool if available
    try:
        # Many usages rely on db.pool for orchestrator saves; if not, we just print results
        conn_url = getattr(db, "pool", None)
    except Exception:
        conn_url = None
    scraper = BundesligaMatchdayScraper(db_manager=db, season_label=season, matchday=matchday)
    await scraper.initialize()
    try:
        items = await scraper.scrape_data()
        print(json.dumps({"count": len(items), "items": items[:3]}, ensure_ascii=False))
    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Bundesliga matchday scraper")
    p.add_argument("season", help="Season label, e.g. 2025-2026")
    p.add_argument("matchday", type=int, help="Matchday number, e.g. 1")
    args = p.parse_args()
    # Windows-specific: use SelectorEventLoop to avoid 'Event loop is closed' warnings
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run_once(args.season, args.matchday))
