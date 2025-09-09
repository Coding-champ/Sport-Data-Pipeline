from typing import Optional, Any
import argparse
import csv
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from time import perf_counter
from typing import Any

import psycopg2
import requests
from bs4 import BeautifulSoup, Comment

from src.domain.models import Event, EventType, Match, MatchStatus

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# A small default pool for UA rotation. Can be overridden by --ua-file
DEFAULT_UAS: list[str] = [
    UA,
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# Language pools for randomized headers
ACCEPT_LANGUAGES: list[str] = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.7",
    "es-ES,es;q=0.9,en;q=0.7",
]
ACCEPT_HEADERS: list[str] = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xml;q=0.9,*/*;q=0.8",
]

CORE_MAP = {
    "minutes": "minutes",
    "shots": "shots_total",
    "shots_on_target": "shots_on_target",
    "xg": "xg",
    "xa": "xa",
    "passes": "passes",
    "passes_completed": "passes_completed",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "dribbles_completed": "dribbles_completed",
    # extras added in 0005
    "key_passes": "key_passes",
    "progressive_passes": "progressive_passes",
    "cards_yellow": "yellows",
    "cards_red": "reds",
    "fouls": "fouls_committed",
    "fouled": "fouls_drawn",
}

# Team-level keys: FBref uses short codes; handle multiple aliases
TEAM_CORE_KEYS = {
    "possession": "possession",  # percent
    "sh": "shots_total",
    "shots": "shots_total",
    "sot": "shots_on_target",
    "shots_on_target": "shots_on_target",
    "c": "corners",
    "corners": "corners",
    "crs": "corners",
    "fouls": "fouls",
    "offsides": "offsides",
    "passes": "passes",
    "passes_completed": "passes_completed",
    "xg": "xg",
    "xa": "xa",
}


def get_db_conn():
    host = os.getenv("PGHOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = int(os.getenv("PGPORT", os.getenv("POSTGRES_PORT", "6543")))
    user = os.getenv("PGUSER", os.getenv("POSTGRES_USER", "sports_user"))
    password = os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD", "sports_password"))
    dbname = os.getenv("PGDATABASE", os.getenv("POSTGRES_DB", "sports_data"))
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)


def fetch_html(
    url: str,
    *,
    timeout: float = 45.0,
    retries: int = 3,
    backoff: float = 1.5,
    proxy: str | None = None,
    verbose: bool = False,
    user_agents: list[str] | None = None,
    rotate_ua: bool = False,
    force_ua_on_429: bool = False,
    header_randomize: bool = True,
    pre_jitter: float = 0.0,
) -> str:
    session = requests.Session()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    last_err = None
    prev_ua: str | None = None
    last_status: int | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            # Optional jitter before attempt
            if pre_jitter and pre_jitter > 0:
                delay = random.uniform(0, pre_jitter)
                if verbose:
                    print(f"pre-jitter sleep: {delay:.2f}s")
                time.sleep(delay)

            # choose UA
            if user_agents and len(user_agents) > 0:
                if rotate_ua:
                    ua = random.choice(user_agents)
                else:
                    # normal: first UA; but if last status was 429 and forced change: pick a different one
                    if force_ua_on_429 and last_status == 429 and len(user_agents) > 1:
                        candidates = [u for u in user_agents if u != prev_ua]
                        ua = random.choice(candidates) if candidates else user_agents[0]
                    else:
                        ua = user_agents[0]
            else:
                ua = UA
            prev_ua = ua

            # randomized headers
            headers = {"User-Agent": ua}
            if header_randomize:
                headers["Accept-Language"] = random.choice(ACCEPT_LANGUAGES)
                headers["Accept"] = random.choice(ACCEPT_HEADERS)
                # Avoid setting Accept-Encoding explicitly; requests will handle compression.

            if verbose:
                al = headers.get("Accept-Language")
                print(f"HTTP attempt {attempt} UA: {ua[:60]}... Accept-Language: {al}")

            resp = session.get(url, headers=headers, timeout=timeout, proxies=proxies)
            # Treat common transient statuses as retryable
            if resp.status_code in (429, 502, 503, 504):
                last_status = resp.status_code
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            return resp.text
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_err = e
            if attempt >= max(1, retries):
                if verbose:
                    print(f"fetch_html failed after {attempt} attempt(s): {e}")
                raise
            # Exponential backoff with jitter
            sleep_s = (backoff ** (attempt - 1)) + random.uniform(0.2, 0.6)
            if verbose:
                print(f"fetch_html attempt {attempt} failed: {e} -> retrying in {sleep_s:.2f}s")
            time.sleep(sleep_s)
    # Should not reach here
    raise last_err if last_err else RuntimeError("fetch_html failed without exception")


def _to_number(text: str) -> Optional[float]:
    if text is None:
        return None
    t = text.strip()
    if t in ("", "—", "-"):
        return None
    # handle added time like 90+2 -> 92
    if "+" in t and all(p.isdigit() for p in t.split("+")):
        try:
            parts = [int(p) for p in t.split("+")]
            return float(sum(parts))
        except Exception:
            pass
    try:
        if t.endswith("%"):
            return float(t[:-1].replace(",", "."))
        if re.match(r"^-?\d+$", t):
            return float(int(t))
        # normalize comma decimals
        return float(t.replace(",", "."))
    except ValueError:
        return None


def parse_player_tables(
    html: str, extra_ids: list | None = None, dump_keys: bool = False, dump_sink: list | None = None
) -> dict[str, dict[str, Any]]:
    """Return dict keyed by fbref_player_id with merged stats across tables.
    Uses thead data-stat names as keys.
    """
    soup = BeautifulSoup(html, "html.parser")

    # FBref embeds some tables within HTML comments. Parse comments, too.
    def extract_tables(parent):
        # target common FBref match player tables explicitly
        ids = [
            "stats_player_summary",
            "stats_shooting",
            "stats_passing",
            "stats_defense",
            "stats_possession",
            "stats_passing_types",
            "stats_misc",
            "stats_keeper_summary",
        ]
        if extra_ids:
            ids.extend([i for i in extra_ids if isinstance(i, str)])
        sel = ", ".join([f"table#{i}" for i in ids])
        for table in parent.select(sel + ", table[id^='stats_']"):
            yield table
        for c in parent.find_all(string=lambda text: isinstance(text, Comment)):
            try:
                frag = BeautifulSoup(c, "html.parser")
                for table in frag.select(sel + ", table[id^='stats_']"):
                    yield table
            except Exception:
                continue

    players: dict[str, dict[str, Any]] = defaultdict(dict)

    for table in extract_tables(soup):
        # header defines available data-stat names
        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.select("tr th[data-stat]"):
                headers.append(th.get("data-stat"))
        if dump_keys:
            table_id = table.get("id")
            # collect body keys as well
            body_keys = {td.get("data-stat") for td in table.select("tbody td[data-stat]")}
            print(
                f"TABLE[player] id={table_id} head_keys={sorted([h for h in headers if h])} body_keys={sorted([k for k in body_keys if k])}"
            )
            if dump_sink is not None:
                dump_sink.append(
                    {
                        "type": "player",
                        "table_id": table_id,
                        "head_keys": sorted([h for h in headers if h]),
                        "body_keys": sorted([k for k in body_keys if k]),
                    }
                )
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.select("tr"):
            # skip summary or separators
            if tr.get("class") and ("thead" in tr.get("class") or "summary" in tr.get("class")):
                continue
            th = tr.find("th", attrs={"data-stat": "player"})
            if not th:
                continue
            fbref_player_id = th.get("data-append-csv")  # FBref player id
            if not fbref_player_id:
                continue
            # collect stats
            row_stats: dict[str, Any] = {}
            for td in tr.select("td[data-stat]"):
                key = td.get("data-stat")
                val = td.get_text(strip=True)
                num = _to_number(val)
                row_stats[key] = num if num is not None else val
            # also include minutes from th if present
            if "minutes" not in row_stats:
                td_min = tr.find("td", attrs={"data-stat": "minutes"})
                if td_min:
                    row_stats["minutes"] = _to_number(td_min.get_text(strip=True))
            # merge into player's dict (latest table wins if duplicate)
            players[fbref_player_id].update(row_stats)
    return players


def parse_team_stats(
    html: str, extra_ids: list | None = None, dump_keys: bool = False, dump_sink: list | None = None
) -> dict[str, dict[str, Any]]:
    """Return dict keyed by fbref_team_id with merged team stats across tables."""
    soup = BeautifulSoup(html, "html.parser")

    def tables(parent):
        # heuristic: try common ids first, then fall back
        base_selector = (
            "table#team_stats, table#team_summary, table[id*='team_stats'], table[id*='summary']"
        )
        sel = base_selector
        if extra_ids:
            sel = ", ".join([base_selector] + [f"table#{i}" for i in extra_ids])
        for table in parent.select(sel):
            yield table
        for c in parent.find_all(string=lambda text: isinstance(text, Comment)):
            try:
                frag = BeautifulSoup(c, "html.parser")
                for table in frag.select(sel):
                    yield table
            except Exception:
                continue

    by_team: dict[str, dict[str, Any]] = defaultdict(dict)
    for table in tables(soup):
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.select("tr"):
            th = tr.find("th")
            if not th:
                continue
            a = th.find("a", href=re.compile(r"/en/squads/"))
            if not a:
                continue
            team_href = a.get("href", "")
            fb_team_id = team_href.split("/")[-2] if "/en/squads/" in team_href else None
            if not fb_team_id:
                continue
            row_stats: dict[str, Any] = {}
            for td in tr.select("td[data-stat]"):
                key = td.get("data-stat")
                val = td.get_text(strip=True)
                num = _to_number(val)
                row_stats[key] = num if num is not None else val
            by_team[fb_team_id].update(row_stats)
        if dump_keys:
            tid = table.get("id")
            keys = {td.get("data-stat") for td in table.select("tbody td[data-stat]")}
            print(f"TABLE[team] id={tid} keys={sorted([k for k in keys if k])}")
            if dump_sink is not None:
                dump_sink.append(
                    {
                        "type": "team",
                        "table_id": tid,
                        "keys": sorted([k for k in keys if k]),
                    }
                )
    return by_team


def parse_gk_tables(
    html: str, extra_ids: list | None = None, dump_keys: bool = False, dump_sink: list | None = None
) -> dict[str, dict[str, Any]]:
    """Return dict keyed by fbref_player_id for goalkeeper-specific stats."""
    soup = BeautifulSoup(html, "html.parser")

    def tables(parent):
        # explicit common GK table ids
        base_selector = "table#stats_keeper_summary, table[id*='keeper'], table[id*='goalkeeper']"
        sel = base_selector
        if extra_ids:
            sel = ", ".join([base_selector] + [f"table#{i}" for i in extra_ids])
        for table in parent.select(sel):
            yield table
        for c in parent.find_all(string=lambda text: isinstance(text, Comment)):
            try:
                frag = BeautifulSoup(c, "html.parser")
                for table in frag.select(sel):
                    yield table
            except Exception:
                continue

    gk: dict[str, dict[str, Any]] = defaultdict(dict)
    for table in tables(soup):
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.select("tr"):
            th = tr.find("th", attrs={"data-stat": "player"})
            if not th:
                continue
            fb_pid = th.get("data-append-csv")
            if not fb_pid:
                continue
            row_stats: dict[str, Any] = {}
            for td in tr.select("td[data-stat]"):
                key = td.get("data-stat")
                val = td.get_text(strip=True)
                num = _to_number(val)
                row_stats[key] = num if num is not None else val
            gk[fb_pid].update(row_stats)
        if dump_keys:
            tid = table.get("id")
            keys = {td.get("data-stat") for td in table.select("tbody td[data-stat]")}
            print(f"TABLE[gk] id={tid} keys={sorted([k for k in keys if k])}")
            if dump_sink is not None:
                dump_sink.append(
                    {
                        "type": "gk",
                        "table_id": tid,
                        "keys": sorted([k for k in keys if k]),
                    }
                )
    return gk


def parse_formations(html: str) -> dict[str, str]:
    """Try to parse team formations keyed by fbref team id.
    Returns mapping {fbref_team_id: formation}
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, str] = {}

    def scan(parent):
        for div in parent.select("div#lineups div div"):  # fairly permissive
            # FBref team link contains data-append-csv team id in anchor
            a = div.find("a", href=re.compile(r"/en/squads/"))
            if not a:
                continue
            team_id = (
                a.get("href", "").split("/")[-2] if "/en/squads/" in a.get("href", "") else None
            )
            if not team_id:
                continue
            text = div.get_text(" ", strip=True)
            m = re.search(r"Formation:\s*([0-9\-]+)", text)
            if m:
                result[team_id] = m.group(1)

    scan(soup)
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        try:
            frag = BeautifulSoup(c, "html.parser")
            scan(frag)
        except Exception:
            continue
    return result


def parse_match_header(html: str) -> Optional[dict]:
    """Best-effort parse of FBref match header to identify home/away team FBref IDs
    and kickoff datetime (UTC or local as provided by page). Returns a dict with keys:
      { 'home_fb_team_id', 'away_fb_team_id', 'utc_datetime', 'status' }
    All keys are optional and may be None if not discovered.
    """
    soup = BeautifulSoup(html, "html.parser")
    home_id: str | None = None
    away_id: str | None = None
    dt_iso: str | None = None
    status: str | None = None

    # Try scorebox team anchors in order (home first, away second on FBref)
    scorebox = soup.select_one("div.scorebox")
    if scorebox:
        team_anchors = scorebox.select("div.scorebox-team a[href*='/en/squads/']")
        if len(team_anchors) >= 2:
            try:
                home_href = team_anchors[0].get("href", "")
                away_href = team_anchors[1].get("href", "")
                if "/en/squads/" in home_href:
                    home_id = home_href.split("/")[-2]
                if "/en/squads/" in away_href:
                    away_id = away_href.split("/")[-2]
            except Exception:
                pass
        # status heuristic
        sb_meta = scorebox.select_one("div.scorebox_meta")
        if sb_meta:
            meta_text = sb_meta.get_text(" ", strip=True).lower()
            if any(k in meta_text for k in ["postponed", "abandoned", "cancelled", "canceled"]):
                status = "postponed"
            elif any(k in meta_text for k in ["ft", "full time", "final"]):
                status = "finished"

    # Kickoff datetime: FBref often includes time tags or meta elements
    # Try <span class="venuetime"> or time[datetime]
    time_el = soup.find("time")
    if time_el and time_el.get("datetime"):
        dt_iso = time_el.get("datetime")

    return {
        "home_fb_team_id": home_id,
        "away_fb_team_id": away_id,
        "utc_datetime": dt_iso,
        "status": status,
    }


def _parse_minute(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.strip().lower()
    m = re.match(r"^(\d+)(?:\+(\d+))?\'?$", t)
    if m:
        base = int(m.group(1))
        extra = int(m.group(2)) if m.group(2) else 0
        return base + extra
    # fallback: any leading integer
    m2 = re.match(r"^(\d+)", t)
    return int(m2.group(1)) if m2 else None


def parse_basic_events(html: str) -> list[dict[str, Any]]:
    """Very lightweight event parser for FBref pages.
    Returns a list of dicts with keys: minute, type, team_fb_id (optional), description.
    This is heuristic and may not capture all events; intended for validation only.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, Any]] = []

    def scan(parent):
        # Look for list items that often contain event text around lineups/scorebox
        for li in parent.select("li"):  # permissive
            text = li.get_text(" ", strip=True)
            if not text:
                continue
            ltext = text.lower()
            etype: EventType | None = None
            if any(k in ltext for k in ["goal", "own goal", "penalty"]):
                etype = EventType.GOAL
            elif any(k in ltext for k in ["yellow card", "red card", "second yellow", "card"]):
                etype = EventType.CARD
            elif "substitution" in ltext or "subbed" in ltext:
                etype = EventType.SUBSTITUTION
            elif "var" in ltext:
                etype = EventType.VAR
            if not etype:
                continue
            # minute often appears at start like "45'+2"
            minute = None
            # try any child with class minute
            min_el = li.find(class_=re.compile("minute|min"))
            if min_el:
                minute = _parse_minute(min_el.get_text(strip=True))
            if minute is None:
                minute = _parse_minute(text.split(" ")[0])

            # Try to associate team via nearest '/en/squads/' link
            team_fb_id = None
            a_team = li.find("a", href=re.compile(r"/en/squads/"))
            if a_team and "/en/squads/" in a_team.get("href", ""):
                team_fb_id = a_team.get("href").split("/")[-2]

            out.append(
                {
                    "minute": minute,
                    "type": etype,
                    "team_fb_id": team_fb_id,
                    "description": text,
                }
            )

    scan(soup)
    # Also parse commented fragments
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        try:
            frag = BeautifulSoup(c, "html.parser")
            scan(frag)
        except Exception:
            continue
    return out


def _map_event_to_lookup_code(ev: dict) -> Optional[str]:
    """Map our coarse EventType plus description to schema.sql event_type_lookup.code.
    Returns None if no reasonable mapping exists (skip).
    """
    et = ev.get("type")  # type: Optional[Any]
    desc = (ev.get("description") or "").lower()
    if et == EventType.GOAL:
        if "own goal" in desc:
            return "own_goal"
        if "pen" in desc and "goal" in desc:
            return "penalty_goal"
        return "goal"
    if et == EventType.CARD:
        if "second yellow" in desc:
            return "second_yellow"
        if "red" in desc:
            return "red_card"
        if "yellow" in desc:
            return "yellow_card"
        return None
    if et == EventType.SUBSTITUTION:
        return "substitution"
    # No VAR/OTHER mapping in lookup -> skip
    return None


def upsert_match_metadata(
    cur,
    match_id: int,
    args_single,
    header: dict[str, Any],
    team_map: dict[str, int],
    source_url: str,
) -> None:
    """Insert or update match row using minimal available data.
    Requires --competition-id and --season-id for inserts. Updates will touch date, teams, venue_id if provided, and source_url.
    """
    # Resolve teams
    home_fb = header.get("home_fb_team_id")
    away_fb = header.get("away_fb_team_id")
    if not (home_fb and away_fb and home_fb in team_map and away_fb in team_map):
        return
    home_team_id = int(team_map[home_fb])
    away_team_id = int(team_map[away_fb])
    # Parse datetime
    dt_str = header.get("utc_datetime")
    dt_val = None
    if dt_str:
        try:
            dt_val = datetime.fromisoformat(dt_str)
        except Exception:
            dt_val = None

    # Check if match exists
    cur.execute("SELECT 1 FROM match WHERE match_id = %s", (match_id,))
    exists = cur.fetchone() is not None

    if exists:
        cur.execute(
            """
            UPDATE match
            SET match_date_time = COALESCE(%s, match_date_time),
                home_team_id = %s,
                away_team_id = %s,
                venue_id = COALESCE(%s, venue_id),
                source_url = %s,
                scraped_at = NOW()
            WHERE match_id = %s
            """,
            (
                dt_val,
                home_team_id,
                away_team_id,
                getattr(args_single, "venue_id", None),
                source_url,
                match_id,
            ),
        )
    else:
        # Need competition and season for insert
        comp_id = getattr(args_single, "competition_id", None)
        season_id = getattr(args_single, "season_id", None)
        if comp_id is None or season_id is None:
            return
        cur.execute(
            """
            INSERT INTO match (match_id, season_id, competition_id, stage_id, match_date_time, venue_id,
                               home_team_id, away_team_id, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (match_id) DO UPDATE SET
              match_date_time = EXCLUDED.match_date_time,
              home_team_id = EXCLUDED.home_team_id,
              away_team_id = EXCLUDED.away_team_id,
              venue_id = COALESCE(EXCLUDED.venue_id, match.venue_id),
              source_url = EXCLUDED.source_url,
              scraped_at = NOW()
            """,
            (
                match_id,
                int(season_id),
                int(comp_id),
                getattr(args_single, "stage_id", None),
                dt_val,
                getattr(args_single, "venue_id", None),
                home_team_id,
                away_team_id,
                source_url,
            ),
        )


def upsert_basic_events(
    cur, match_id: int, events: list[dict[str, Any]], team_map: dict[str, int]
) -> tuple[int, int]:
    """Insert basic events into match_event. Returns (inserted, skipped).
    Only inserts events that can be mapped to a known event_type_lookup.code.
    """
    # Cache event_type code -> id
    type_cache: dict[str, int] = {}

    def get_type_id(code: str) -> Optional[int]:
        if code in type_cache:
            return type_cache[code]
        cur.execute("SELECT event_type_id FROM event_type_lookup WHERE code = %s", (code,))
        row = cur.fetchone()
        if not row:
            return None
        type_cache[code] = int(row[0])
        return type_cache[code]

    ins = 0
    skip = 0
    for ev in events:
        code = _map_event_to_lookup_code(ev)
        if not code:
            skip += 1
            continue
        etid = get_type_id(code)
        if not etid:
            skip += 1
            continue
        minute = ev.get("minute")
        team_id = None
        if ev.get("team_fb_id") and ev["team_fb_id"] in team_map:
            team_id = int(team_map[ev["team_fb_id"]])
        # Minimal insert; duplicates allowed (no natural key). Could be extended with de-duplication.
        cur.execute(
            """
            INSERT INTO match_event (match_id, team_id, event_type_id, minute)
            VALUES (%s, %s, %s, %s)
            """,
            (match_id, team_id, etid, minute),
        )
        ins += 1
    return ins, skip


def upsert_player_match_stats(
    cur, match_id: int, player_id: int, team_id: int | None, stats: dict[str, Any], source_url: str
):
    # Map core columns
    core_values: dict[str, Any] = {k_db: None for k_db in set(CORE_MAP.values())}
    for fb_k, db_k in CORE_MAP.items():
        if fb_k in stats and stats[fb_k] is not None:
            try:
                core_values[db_k] = (
                    int(stats[fb_k]) if db_k not in ("xg", "xa") else float(stats[fb_k])
                )
            except Exception:
                core_values[db_k] = float(stats[fb_k]) if db_k in ("xg", "xa") else None

    cur.execute(
        """
        INSERT INTO player_match_stats(
            match_id, player_id, team_id, provider,
            minutes, shots_total, shots_on_target, xg, xa,
            passes, passes_completed, tackles, interceptions, clearances,
            dribbles_completed, key_passes, progressive_passes, yellows, reds,
            fouls_committed, fouls_drawn, metrics_extra, source_url, scraped_at
        ) VALUES (
            %(match_id)s, %(player_id)s, %(team_id)s, 'fbref',
            %(minutes)s, %(shots_total)s, %(shots_on_target)s, %(xg)s, %(xa)s,
            %(passes)s, %(passes_completed)s, %(tackles)s, %(interceptions)s, %(clearances)s,
            %(dribbles_completed)s, %(key_passes)s, %(progressive_passes)s, %(yellows)s, %(reds)s,
            %(fouls_committed)s, %(fouls_drawn)s, %(metrics_extra)s::jsonb, %(source_url)s, NOW()
        )
        ON CONFLICT (match_id, player_id, provider)
        DO UPDATE SET
            team_id = EXCLUDED.team_id,
            minutes = EXCLUDED.minutes,
            shots_total = EXCLUDED.shots_total,
            shots_on_target = EXCLUDED.shots_on_target,
            xg = EXCLUDED.xg,
            xa = EXCLUDED.xa,
            passes = EXCLUDED.passes,
            passes_completed = EXCLUDED.passes_completed,
            tackles = EXCLUDED.tackles,
            interceptions = EXCLUDED.interceptions,
            clearances = EXCLUDED.clearances,
            dribbles_completed = EXCLUDED.dribbles_completed,
            key_passes = EXCLUDED.key_passes,
            progressive_passes = EXCLUDED.progressive_passes,
            yellows = EXCLUDED.yellows,
            reds = EXCLUDED.reds,
            fouls_committed = EXCLUDED.fouls_committed,
            fouls_drawn = EXCLUDED.fouls_drawn,
            metrics_extra = EXCLUDED.metrics_extra,
            source_url = EXCLUDED.source_url,
            updated_at = NOW()
        """,
        {
            "match_id": match_id,
            "player_id": player_id,
            "team_id": team_id,
            "minutes": core_values.get("minutes"),
            "shots_total": core_values.get("shots_total"),
            "shots_on_target": core_values.get("shots_on_target"),
            "xg": core_values.get("xg"),
            "xa": core_values.get("xa"),
            "passes": core_values.get("passes"),
            "passes_completed": core_values.get("passes_completed"),
            "tackles": core_values.get("tackles"),
            "interceptions": core_values.get("interceptions"),
            "clearances": core_values.get("clearances"),
            "dribbles_completed": core_values.get("dribbles_completed"),
            "key_passes": core_values.get("key_passes"),
            "progressive_passes": core_values.get("progressive_passes"),
            "yellows": core_values.get("yellows"),
            "reds": core_values.get("reds"),
            "fouls_committed": core_values.get("fouls_committed"),
            "fouls_drawn": core_values.get("fouls_drawn"),
            "metrics_extra": json.dumps(stats, default=str),
            "source_url": source_url,
        },
    )


def upsert_team_match_stats(
    cur, match_id: int, team_id: int, stats: dict[str, Any], source_url: str
):
    # Map known keys
    core: dict[str, Any] = {
        "possession": None,
        "shots_total": None,
        "shots_on_target": None,
        "corners": None,
        "fouls": None,
        "offsides": None,
        "passes": None,
        "passes_completed": None,
        "xg": None,
        "xa": None,
    }
    for k_src, k_dst in TEAM_CORE_KEYS.items():
        if k_src in stats and stats[k_src] is not None:
            core[k_dst] = stats[k_src]
    # Normalize possession to numeric percent if string like '55'
    if isinstance(core["possession"], str) and core["possession"].endswith("%"):
        try:
            core["possession"] = float(core["possession"].rstrip("%"))
        except Exception:
            pass

    cur.execute(
        """
        INSERT INTO team_match_stats(
            match_id, team_id, provider,
            possession, shots_total, shots_on_target, corners, fouls, offsides,
            passes, passes_completed, xg, xa, metrics_extra, source_url, scraped_at
        ) VALUES (
            %(match_id)s, %(team_id)s, 'fbref',
            %(possession)s, %(shots_total)s, %(shots_on_target)s, %(corners)s, %(fouls)s, %(offsides)s,
            %(passes)s, %(passes_completed)s, %(xg)s, %(xa)s, %(metrics_extra)s::jsonb, %(source_url)s, NOW()
        )
        ON CONFLICT (match_id, team_id, provider)
        DO UPDATE SET
            possession = EXCLUDED.possession,
            shots_total = EXCLUDED.shots_total,
            shots_on_target = EXCLUDED.shots_on_target,
            corners = EXCLUDED.corners,
            fouls = EXCLUDED.fouls,
            offsides = EXCLUDED.offsides,
            passes = EXCLUDED.passes,
            passes_completed = EXCLUDED.passes_completed,
            xg = EXCLUDED.xg,
            xa = EXCLUDED.xa,
            metrics_extra = EXCLUDED.metrics_extra,
            source_url = EXCLUDED.source_url,
            updated_at = NOW()
        """,
        {
            "match_id": match_id,
            "team_id": team_id,
            **core,
            "metrics_extra": json.dumps(stats, default=str),
            "source_url": source_url,
        },
    )


def upsert_goalkeeper_match_stats(
    cur, match_id: int, player_id: int, team_id: int | None, stats: dict[str, Any], source_url: str
):
    # Map GK keys with fallbacks
    shots_faced = stats.get("sota") or stats.get("shots_on_target_against")
    goals_allowed = stats.get("ga") or stats.get("goals_against")
    saves = stats.get("saves")
    save_pct = stats.get("save_pct") or stats.get("save%")
    sweeper_actions = stats.get("def_actions_outside_pen_area") or stats.get("sweeper")
    launched_passes = stats.get("passes_launched") or stats.get("launched_passes")
    claims = stats.get("claims")
    punches = stats.get("punches")
    minutes = stats.get("minutes")

    cur.execute(
        """
        INSERT INTO goalkeeper_match_stats(
            match_id, player_id, team_id, provider,
            minutes, shots_faced, goals_allowed, saves, save_pct,
            sweeper_actions, launched_passes, claims, punches,
            metrics_extra, source_url, scraped_at
        ) VALUES (
            %(match_id)s, %(player_id)s, %(team_id)s, 'fbref',
            %(minutes)s, %(shots_faced)s, %(goals_allowed)s, %(saves)s, %(save_pct)s,
            %(sweeper_actions)s, %(launched_passes)s, %(claims)s, %(punches)s,
            %(metrics_extra)s::jsonb, %(source_url)s, NOW()
        )
        ON CONFLICT (match_id, player_id, provider)
        DO UPDATE SET
            team_id = EXCLUDED.team_id,
            minutes = EXCLUDED.minutes,
            shots_faced = EXCLUDED.shots_faced,
            goals_allowed = EXCLUDED.goals_allowed,
            saves = EXCLUDED.saves,
            save_pct = EXCLUDED.save_pct,
            sweeper_actions = EXCLUDED.sweeper_actions,
            launched_passes = EXCLUDED.launched_passes,
            claims = EXCLUDED.claims,
            punches = EXCLUDED.punches,
            metrics_extra = EXCLUDED.metrics_extra,
            source_url = EXCLUDED.source_url,
            updated_at = NOW()
        """,
        {
            "match_id": match_id,
            "player_id": player_id,
            "team_id": team_id,
            "minutes": minutes,
            "shots_faced": shots_faced,
            "goals_allowed": goals_allowed,
            "saves": saves,
            "save_pct": save_pct,
            "sweeper_actions": sweeper_actions,
            "launched_passes": launched_passes,
            "claims": claims,
            "punches": punches,
            "metrics_extra": json.dumps(stats, default=str),
            "source_url": source_url,
        },
    )


def upsert_team_formation(cur, match_id: int, team_id: int, formation: str, source_url: str):
    cur.execute(
        """
        INSERT INTO team_match_formation(match_id, team_id, provider, formation, source_url, scraped_at)
        VALUES (%s, %s, 'fbref', %s, %s, NOW())
        ON CONFLICT (match_id, team_id, provider)
        DO UPDATE SET formation = EXCLUDED.formation, source_url = EXCLUDED.source_url, updated_at = NOW()
        """,
        (match_id, team_id, formation, source_url),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ingest FBref match player stats into player_match_stats (hybrid)"
    )
    parser.add_argument("--match-id", type=int, required=True, help="Internal match_id in DB")
    parser.add_argument("--url", type=str, required=True, help="FBref match URL")
    parser.add_argument(
        "--mapping",
        type=str,
        required=True,
        help=(
            "Path to JSON mapping: {\n  'players': { 'fbref_player_id': { 'player_id': int, 'team_id': int } },\n"
            "  'teams': { 'fbref_team_id': int }\n}"
        ),
    )
    parser.add_argument("--no-formation", action="store_true", help="Skip formation ingestion")
    parser.add_argument(
        "--dump-keys", action="store_true", help="Print discovered table ids and data-stat keys"
    )
    parser.add_argument(
        "--dump-keys-file", type=str, default=None, help="Write discovered keys to JSON file"
    )
    parser.add_argument(
        "--generate-mapping-skeleton",
        type=str,
        default=None,
        help="Write a mapping skeleton JSON to this file based on parsed page (players, teams)",
    )
    parser.add_argument(
        "--extra-player-tables",
        type=str,
        help="Comma-separated extra player table IDs",
        default=None,
    )
    parser.add_argument(
        "--extra-team-tables", type=str, help="Comma-separated extra team table IDs", default=None
    )
    parser.add_argument(
        "--extra-gk-tables",
        type=str,
        help="Comma-separated extra goalkeeper table IDs",
        default=None,
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose console output")
    parser.add_argument(
        "--timeout", type=float, default=45.0, help="HTTP timeout in seconds (default: 45)"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="HTTP retries on transient errors (default: 3)"
    )
    parser.add_argument(
        "--backoff", type=float, default=1.5, help="Exponential backoff base (default: 1.5)"
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP/HTTPS proxy URL (e.g. http://user:pass@host:port)",
    )
    parser.add_argument(
        "--ua-file", type=str, default=None, help="Path to file with User-Agents (one per line)"
    )
    parser.add_argument(
        "--ua-rotate",
        action="store_true",
        help="Rotate User-Agent per request (default: use first)",
    )
    parser.add_argument(
        "--force-ua-on-429",
        action="store_true",
        help="Force-change User-Agent when 429 occurs (even without --ua-rotate)",
    )
    parser.add_argument(
        "--no-header-randomize",
        action="store_true",
        help="Disable randomized Accept-Language/Accept headers",
    )
    parser.add_argument(
        "--pre-jitter",
        type=float,
        default=0.0,
        help="Random sleep up to N seconds before each HTTP attempt",
    )
    parser.add_argument(
        "--batch-file",
        type=str,
        default=None,
        help="CSV file with headers: match_id,url,mapping for batch ingestion",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=0.0,
        help="Minimum seconds to wait between batch items",
    )
    parser.add_argument(
        "--validate-match",
        action="store_true",
        help="Validate parsed match header with Pydantic models (no DB upsert)",
    )
    parser.add_argument(
        "--validate-events",
        action="store_true",
        help="Validate parsed basic events with Pydantic models (no DB upsert)",
    )
    parser.add_argument(
        "--upsert-match",
        action="store_true",
        help="Insert/Update match metadata (requires --competition-id and --season-id for inserts)",
    )
    parser.add_argument(
        "--competition-id", type=int, default=None, help="Competition ID for match insert"
    )
    parser.add_argument("--season-id", type=int, default=None, help="Season ID for match insert")
    parser.add_argument("--stage-id", type=int, default=None, help="Stage ID (optional)")
    parser.add_argument("--venue-id", type=int, default=None, help="Venue ID (optional)")
    parser.add_argument(
        "--upsert-events",
        action="store_true",
        help="Insert parsed basic events into match_event table",
    )
    args = parser.parse_args()

    def run_once(conn, args_single):
        with open(args_single.mapping, encoding="utf-8") as f:
            mapping = json.load(f)
        player_map: dict[str, dict[str, Any]] = mapping.get("players", {})
        team_map: dict[str, int] = mapping.get("teams", {})

        # Prepare UA list
        ua_list: list[str] | None = None
        if args_single.ua_file:
            try:
                with open(args_single.ua_file, encoding="utf-8") as f:
                    ua_list = [
                        ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")
                    ]
            except Exception as e:
                if args_single.verbose:
                    print(f"Failed to read --ua-file: {e}. Falling back to defaults.")
                ua_list = DEFAULT_UAS
        else:
            ua_list = DEFAULT_UAS

        t0 = perf_counter()
        html = fetch_html(
            args_single.url,
            timeout=args_single.timeout,
            retries=args_single.retries,
            backoff=args_single.backoff,
            proxy=args_single.proxy,
            verbose=args_single.verbose,
            user_agents=ua_list,
            rotate_ua=args_single.ua_rotate,
            force_ua_on_429=args_single.force_ua_on_429,
            header_randomize=(not args_single.no_header_randomize),
            pre_jitter=args_single.pre_jitter,
        )
        t_fetch = perf_counter() - t0
        extra_player = (
            [s.strip() for s in args_single.extra_player_tables.split(",")]
            if args_single.extra_player_tables
            else None
        )
        extra_team = (
            [s.strip() for s in args_single.extra_team_tables.split(",")]
            if args_single.extra_team_tables
            else None
        )
        extra_gk = (
            [s.strip() for s in args_single.extra_gk_tables.split(",")]
            if args_single.extra_gk_tables
            else None
        )

        discovered: list = []
        players_stats = parse_player_tables(
            html,
            extra_ids=extra_player,
            dump_keys=args_single.dump_keys,
            dump_sink=discovered if (args_single.dump_keys or args_single.dump_keys_file) else None,
        )
        team_stats = parse_team_stats(
            html,
            extra_ids=extra_team,
            dump_keys=args_single.dump_keys,
            dump_sink=discovered if (args_single.dump_keys or args_single.dump_keys_file) else None,
        )
        gk_stats = parse_gk_tables(
            html,
            extra_ids=extra_gk,
            dump_keys=args_single.dump_keys,
            dump_sink=discovered if (args_single.dump_keys or args_single.dump_keys_file) else None,
        )

        if args_single.verbose:
            print(f"fetch_html: {t_fetch*1000:.0f} ms")
            p_tables = sum(1 for d in discovered if d.get("type") == "player")
            t_tables = sum(1 for d in discovered if d.get("type") == "team")
            g_tables = sum(1 for d in discovered if d.get("type") == "gk")
            print(f"tables discovered -> player: {p_tables}, team: {t_tables}, gk: {g_tables}")
            print(
                f"objects parsed -> players: {len(players_stats)}, gk: {len(gk_stats)}, teams: {len(team_stats)}"
            )

        if args_single.dump_keys_file:
            try:
                os.makedirs(os.path.dirname(args_single.dump_keys_file), exist_ok=True)
            except Exception:
                pass
            try:
                with open(args_single.dump_keys_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "url": args_single.url,
                            "discovered": discovered,
                            "players_count": len(players_stats),
                            "gk_count": len(gk_stats),
                            "teams_count": len(team_stats),
                            "fetched_ms": int(t_fetch * 1000),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except Exception as e:
                print(f"Failed to write dump keys file: {e}", file=sys.stderr)

        if args_single.generate_mapping_skeleton:
            try:
                os.makedirs(os.path.dirname(args_single.generate_mapping_skeleton), exist_ok=True)
            except Exception:
                pass
            skeleton = {"players": {}, "teams": {}}
            for pid in set(list(players_stats.keys()) + list(gk_stats.keys())):
                skeleton["players"][pid] = {"player_id": None, "team_id": None}
            for tid in team_stats.keys():
                skeleton["teams"][tid] = None
            try:
                with open(args_single.generate_mapping_skeleton, "w", encoding="utf-8") as f:
                    json.dump(skeleton, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Failed to write mapping skeleton: {e}", file=sys.stderr)

        # Optional: Validate match header and mapping consistency
        if args_single.validate_match:
            header = parse_match_header(html)
            if header and header.get("home_fb_team_id") and header.get("away_fb_team_id"):
                home_fb = header["home_fb_team_id"]
                away_fb = header["away_fb_team_id"]
                if home_fb in team_map and away_fb in team_map:
                    try:
                        match_model = Match(
                            match_id=args_single.match_id,
                            competition=None,
                            season=None,
                            round=None,
                            utc_datetime=header.get("utc_datetime"),
                            home_team_id=int(team_map[home_fb]),
                            away_team_id=int(team_map[away_fb]),
                            venue=None,
                            status=MatchStatus(header.get("status") or "finished"),
                            result=None,
                        )
                        if args_single.verbose:
                            print(
                                f"Validated Match model: home={match_model.home_team_id} away={match_model.away_team_id} status={match_model.status}"
                            )
                    except Exception as e:
                        if args_single.verbose:
                            print(f"Match validation failed: {e}")
                elif args_single.verbose:
                    print("Match validation skipped: team_map missing home/away fbref ids")

        if args_single.validate_events or args_single.upsert_events:
            events = parse_basic_events(html)
            ok = 0
            for ev in events:
                try:
                    team_id = None
                    if ev.get("team_fb_id") and ev["team_fb_id"] in team_map:
                        team_id = int(team_map[ev["team_fb_id"]])
                    model = Event(
                        match_id=args_single.match_id,
                        minute=ev.get("minute"),
                        type=ev.get("type"),
                        team_id=team_id,
                        player_id=None,
                        description=ev.get("description"),
                    )
                    ok += 1
                except Exception as e:
                    if args_single.verbose:
                        print(f"Event validation failed: {e} | data={ev}")
            if args_single.verbose and args_single.validate_events:
                print(f"Validated events: {ok}/{len(events)}")

        # Optional upserts
        with conn:
            with conn.cursor() as cur:
                if args_single.upsert_match:
                    header = parse_match_header(html)
                    if header:
                        upsert_match_metadata(
                            cur, args_single.match_id, args_single, header, team_map, args_single.url
                        )
                        if args_single.verbose:
                            print("Match metadata upsert attempted.")
                if args_single.upsert_events and "events" in locals():
                    ins, skip = upsert_basic_events(cur, args_single.match_id, events, team_map)
                    if args_single.verbose:
                        print(f"Events upserted: inserted={ins} skipped={skip}")

        with conn:
            with conn.cursor() as cur:
                inserted = 0
                skipped = 0
                for fbref_pid, stats in players_stats.items():
                    m = player_map.get(fbref_pid)
                    if not m:
                        skipped += 1
                        continue
                    upsert_player_match_stats(
                        cur,
                        match_id=args_single.match_id,
                        player_id=int(m["player_id"]),
                        team_id=int(m["team_id"]) if m.get("team_id") is not None else None,
                        stats=stats,
                        source_url=args_single.url,
                    )
                    inserted += 1
                if args_single.verbose:
                    print(
                        f"player_match_stats upserts: {inserted}, skipped (no mapping): {skipped}"
                    )

                gk_inserted = 0
                gk_skipped = 0
                for fbref_pid, stats in gk_stats.items():
                    m = player_map.get(fbref_pid)
                    if not m:
                        gk_skipped += 1
                        continue
                    upsert_goalkeeper_match_stats(
                        cur,
                        match_id=args_single.match_id,
                        player_id=int(m["player_id"]),
                        team_id=int(m["team_id"]) if m.get("team_id") is not None else None,
                        stats=stats,
                        source_url=args_single.url,
                    )
                    gk_inserted += 1
                if args_single.verbose:
                    print(
                        f"goalkeeper_match_stats upserts: {gk_inserted}, skipped (no mapping): {gk_skipped}"
                    )

                team_inserted = 0
                for fb_team_id, stats in team_stats.items():
                    if fb_team_id in team_map:
                        upsert_team_match_stats(
                            cur,
                            match_id=args_single.match_id,
                            team_id=int(team_map[fb_team_id]),
                            stats=stats,
                            source_url=args_single.url,
                        )
                        team_inserted += 1
                if team_stats and args_single.verbose:
                    print(
                        f"team_match_stats upserts: {team_inserted} (only those with mapping applied)"
                    )

                if not args_single.no_formation:
                    formations = parse_formations(html)
                    for fb_team_id, formation in formations.items():
                        if fb_team_id in team_map:
                            upsert_team_formation(
                                cur,
                                args_single.match_id,
                                int(team_map[fb_team_id]),
                                formation,
                                args_single.url,
                            )
                    if formations and args_single.verbose:
                        print(
                            f"team_match_formation upserts: {len(formations)} (only those with mapping applied)"
                        )

    # Decide single vs batch
    if args.batch_file:
        conn = get_db_conn()
        try:
            total = 0
            with open(args.batch_file, encoding="utf-8") as bf:
                reader = csv.DictReader(bf)
                required = {"match_id", "url", "mapping"}
                if not required.issubset(set([c.strip() for c in reader.fieldnames or []])):
                    raise ValueError("--batch-file must have headers: match_id,url,mapping")
                for row in reader:
                    local = argparse.Namespace(**vars(args))
                    local.match_id = int(row["match_id"]) if row.get("match_id") else args.match_id
                    local.url = row.get("url") or args.url
                    local.mapping = row.get("mapping") or args.mapping
                    if args.verbose:
                        print(f"Processing match_id={local.match_id} url={local.url}")
                    run_once(conn, local)
                    total += 1
                    if args.min_interval and args.min_interval > 0:
                        time.sleep(args.min_interval)
            if args.verbose:
                print(f"Batch completed: {total} items processed")
        finally:
            conn.close()
    else:
        conn = get_db_conn()
        try:
            run_once(conn, args)
        finally:
            conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
