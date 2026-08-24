#!/usr/bin/env python3
"""Standalone Premier League club stats API client.

The script fetches the current Premier League teams and season statistics from
the official football API and writes a compact JSON structure.

It intentionally depends only on the Python standard library so it can later be
packaged as a standalone executable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_URL = "https://footballapi.pulselive.com/football"
COMPETITION_ID = 1
SEASON_CODE = "current"


@dataclass(frozen=True)
class ClubEntry:
    club_id: str
    club_name: str
    url: str


def fetch_json(url: str, timeout: int, user_agent: str) -> Any:
    for attempt in range(3):
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 2 ** (attempt + 1)
            print(f"[WARN] API rate limit; retrying in {wait_seconds:g}s", file=sys.stderr)
            time.sleep(wait_seconds)
    raise RuntimeError("Premier League API request failed")


def fetch_current_season_id(timeout: int, user_agent: str) -> tuple[int, str]:
    url = f"{API_URL}/competitions/{COMPETITION_ID}/compseasons?page=0&pageSize=1"
    seasons = fetch_json(url, timeout, user_agent).get("content", [])
    if not seasons:
        raise RuntimeError("Premier League API returned no seasons")
    season = seasons[0]
    return int(season["id"]), str(season["label"])


def fetch_current_matchday(season_id: int, timeout: int, user_agent: str) -> int | None:
    url = (
        f"{API_URL}/fixtures?comps={COMPETITION_ID}&compSeasons={season_id}"
        "&page=0&pageSize=100"
    )
    data = fetch_json(url, timeout, user_agent)
    fixtures = data if isinstance(data, list) else data.get("content", [])
    if not fixtures:
        return None

    started_matchdays: list[int] = []
    scheduled_matchdays: list[int] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        gameweek = fixture.get("gameweek", {})
        value = gameweek.get("gameweek") if isinstance(gameweek, dict) else None
        if not isinstance(value, (int, float)):
            continue
        matchday = int(value)
        scheduled_matchdays.append(matchday)
        if fixture.get("status") in {"C", "L"}:
            started_matchdays.append(matchday)

    if started_matchdays:
        return max(started_matchdays)
    return min(scheduled_matchdays) if scheduled_matchdays else None


def extract_api_clubs(data: Any) -> list[ClubEntry]:
    clubs: dict[str, ClubEntry] = {}
    teams = data if isinstance(data, list) else data.get("content", [])
    for team in teams:
        club_id = team.get("id")
        name = team.get("name") or team.get("shortName")
        if club_id is None or not name or team.get("teamType") != "FIRST":
            continue
        club_id_text = str(int(club_id))
        clubs[club_id_text] = ClubEntry(
            club_id=club_id_text,
            club_name=str(name),
            url=f"{API_URL}/teams/{club_id_text}",
        )
    return list(clubs.values())


def extract_api_stats(data: dict[str, Any]) -> dict[str, int | float]:
    stats: dict[str, int | float] = {}
    for item in data.get("stats", []):
        name = item.get("name")
        value = item.get("value")
        if not name or not isinstance(value, (int, float)):
            continue
        stats[str(name)] = value
    return stats


def scrape_clubs(
    timeout: int,
    delay: float,
    user_agent: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    season_id, season_label = fetch_current_season_id(timeout, user_agent)
    current_matchday = fetch_current_matchday(season_id, timeout, user_agent)
    teams_url = f"{API_URL}/compseasons/{season_id}/teams?page=0&pageSize=100"
    clubs = extract_api_clubs(fetch_json(teams_url, timeout, user_agent))
    if limit is not None:
        clubs = clubs[:limit]

    results: list[dict[str, Any]] = []
    for index, club in enumerate(clubs, start=1):
        print(f"[{index}/{len(clubs)}] Fetching {club.club_name}", flush=True)
        try:
            stats_url = (
                f"{API_URL}/stats/team/{club.club_id}"
                f"?comps={COMPETITION_ID}&compSeasons={season_id}"
            )
            stats = extract_api_stats(fetch_json(stats_url, timeout, user_agent))
        except Exception as exc:
            print(f"[WARN] Skipping {club.club_name}: {exc}", file=sys.stderr)
            if delay > 0 and index < len(clubs):
                time.sleep(delay)
            continue

        results.append(
            {
                "club_id": club.club_id,
                "club_name": club.club_name,
                "url": club.url,
                "stats_url": stats_url,
                "season": season_label,
                "matchday": current_matchday,
                "stats": stats,
            }
        )
        if delay > 0 and index < len(clubs):
            time.sleep(delay)

    return results


def resolve_output_path(output: str) -> Path:
    path = Path(output)
    if path.suffix:
        return path
    return path.with_suffix(".json")


def build_default_output_path(matchday: int | None) -> Path:
    safe_matchday = 0 if matchday is None else matchday
    return Path(f"premierleague_{SEASON_CODE}_matchday_{safe_matchday}.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Premier League teams and season statistics from the official API into JSON.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Defaults to premierleague_current_matchday_[matchday].json in the current directory.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Pause between API requests in seconds (increase if the API returns 429).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for the number of clubs to scrape.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level.")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON without indentation.")
    parser.add_argument(
        "--user-agent",
        default="sport-data-pipeline/1.0",
        help="User agent string for HTTP requests.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        results = scrape_clubs(
            timeout=args.timeout,
            delay=args.delay,
            user_agent=args.user_agent,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1

    matchday_values = [item.get("matchday") for item in results if isinstance(item.get("matchday"), int)]
    current_matchday = max(matchday_values) if matchday_values else None

    if args.output:
        output_path = resolve_output_path(args.output)
    else:
        output_path = build_default_output_path(current_matchday)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.compact:
        payload = json.dumps(results, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(results, ensure_ascii=False, indent=args.indent)

    output_path.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(results)} clubs to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())