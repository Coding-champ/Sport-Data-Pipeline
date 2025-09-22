"""Unified scraping entrypoint for multiple data sources.

Sources (pass via --source):
  bundesliga_overview   - Overview clubs only (legacy scrape_bundesliga_clubs subset)
  bundesliga_deep       - Clubs + squads + players (legacy run_bundesliga_club_scraper)
  flashscore_once       - Single Flashscore orchestration run
  courtside_preview     - Lightweight Courtside scraper preview (first fixtures)
  tm_injuries           - Transfermarkt injuries (JSON)
  tm_injuries_csv       - Transfermarkt injuries (CSV minimal format)

Common options:
  --out OUT.json        Output file (JSON unless *_csv mode)
  --limit N             Limit items (if supported by the source)
  --verbose             Verbose logging

Examples:
  python scripts/run_scraper.py --source bundesliga_overview --out reports/bundesliga_clubs.json
  python scripts/run_scraper.py --source bundesliga_deep --limit 3 --out reports/bundesliga_deep.json
  python scripts/run_scraper.py --source flashscore_once
  python scripts/run_scraper.py --source courtside_preview --out reports/courtside/preview.json
  python scripts/run_scraper.py --source tm_injuries --club-id 27 --out reports/tm_injuries.json
  python scripts/run_scraper.py --source tm_injuries_csv --club-id 27 > injuries.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

# Ensure project root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- Transfermarkt Injuries minimal helpers (adapted from preview scripts) ---
from src.common.http import DEFAULT_UAS, fetch_html  # type: ignore
from src.common.parsing import extract_tm_player_id_from_href  # type: ignore
from src.data_collection.scrapers.transfermarkt_injuries_scraper import _parse_injuries  # type: ignore


def _tm_injuries_url(club_id: int) -> str:
    return f"https://www.transfermarkt.de/-/sperrenundverletzungen/verein/{club_id}/plus/1"


async def run_tm_injuries(club_id: int, csv_mode: bool, out: Path | None) -> dict[str, Any] | None:
    html = fetch_html(
        _tm_injuries_url(club_id),
        timeout=45.0,
        retries=3,
        backoff=1.5,
        proxy=None,
        verbose=False,
        user_agents=DEFAULT_UAS,
        rotate_ua=False,
        force_ua_on_429=False,
        header_randomize=True,
        pre_jitter=0.0,
    )
    rows = _parse_injuries(html)
    if csv_mode:
        writer = csv.writer(sys.stdout if out is None else out.open("w", newline="", encoding="utf-8"))
        writer.writerow(["tm_player_id", "player_name", "reason", "start_date", "expected"])
        for r in rows:
            writer.writerow([
                extract_tm_player_id_from_href(r.get("player_href")),
                (r.get("player_name") or "").replace(",", " "),
                (r.get("reason") or "").replace(",", " "),
                r.get("start_date") or "",
                r.get("end_or_expected") or "",
            ])
        return None
    payload = {"club_id": club_id, "count": len(rows), "items": rows}
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


# --- Flashscore orchestrated run ---
async def run_flashscore_once(limit: int | None) -> dict[str, Any]:
    from src.apps.sports_data_app import SportsDataApp  # type: ignore
    from src.core.config import Settings  # type: ignore
    settings = Settings()
    app = SportsDataApp(settings)
    try:
        await app.initialize()
        res = await app.scraping_orchestrator.run_scraping_job(["flashscore"])
        if limit and isinstance(res, dict) and "items" in res:
            res["items"] = res["items"][:limit]
        return {"source": "flashscore", "result": res}
    finally:
        await app.cleanup()


# --- Courtside preview (adapt from run_courtside_scrape_preview) ---
class _DummyDBManager:
    async def bulk_insert(self, *args, **kwargs):
        return None


class _DummySettings:
    pass


async def run_courtside_preview(limit: int | None) -> dict[str, Any]:
    from src.data_collection.scrapers.courtside_scraper import CourtsideScraper  # local import

    scraper = CourtsideScraper(db_manager=_DummyDBManager(), settings=_DummySettings())
    items: list[dict[str, Any]] = await scraper.scrape_data()
    if limit:
        items = items[:limit]
    preview = [{
        "fixture_id": it.get("fixture_id"),
        "competition_id": it.get("competition_id"),
        "home_team_id": it.get("home_team_id"),
        "away_team_id": it.get("away_team_id"),
        "home_team_name": it.get("home_team_name"),
        "away_team_name": it.get("away_team_name"),
        "score": it.get("score"),
        "url": it.get("url"),
    } for it in items]
    return {"source": "courtside", "count": len(preview), "items": preview}


# --- Bundesliga overview & deep ---
from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper  # type: ignore


class _MockDB:
    async def bulk_insert(self, table: str, data: list, conflict_resolution: str = ""):
        return None


async def run_bundesliga_deep(limit_clubs: int | None, limit_players: int | None) -> dict[str, Any]:
    scraper = BundesligaClubScraper(_MockDB())
    await scraper.initialize()
    clubs = await scraper.scrape_clubs()
    if limit_clubs:
        clubs = clubs[:limit_clubs]
    results: dict[str, Any] = {"clubs": [c.model_dump() for c in clubs], "players": {}, "squads": {}}
    if limit_players is not None and limit_players <= 0:
        return results
    for club in clubs:
        squad = await scraper.scrape_squad(club)
        if limit_players:
            squad = squad[:limit_players]
        results["squads"][club.slug] = [p.model_dump() for p in squad]
        for p in squad:
            pdata = await scraper.scrape_player(p, club)
            results["players"][p.slug] = pdata.model_dump()
    return results


# For overview we reuse separate script logic? If that script has custom heuristics, consider importing.
# Here we call only the scraper's clubs method; the older script did parsing without dynamic player detail.
async def run_bundesliga_overview(limit: int | None) -> dict[str, Any]:
    scraper = BundesligaClubScraper(_MockDB())
    await scraper.initialize()
    clubs = await scraper.scrape_clubs()
    if limit:
        clubs = clubs[:limit]
    return {"count": len(clubs), "clubs": [c.model_dump() for c in clubs]}


# --- Argument parsing & orchestration ---
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified multi-source scraping CLI")
    p.add_argument("--source", required=True, choices=[
        "bundesliga_overview","bundesliga_deep","flashscore_once","courtside_preview","tm_injuries","tm_injuries_csv"
    ])
    p.add_argument("--out", type=str, default=None, help="Output file (JSON unless *_csv)")
    p.add_argument("--limit", type=int, default=None, help="Generic limit (clubs, fixtures, etc.)")
    p.add_argument("--limit-players", type=int, default=None, help="Limit players per club (deep mode)")
    p.add_argument("--club-id", type=int, default=27, help="Transfermarkt club id for injuries")
    p.add_argument("--verbose", action="store_true")
    return p


async def dispatch(args: argparse.Namespace) -> Any:
    if args.source.startswith("tm_injuries"):
        return await run_tm_injuries(args.club_id, csv_mode=args.source.endswith("_csv"), out=(Path(args.out) if args.out else None))
    if args.source == "flashscore_once":
        return await run_flashscore_once(args.limit)
    if args.source == "courtside_preview":
        return await run_courtside_preview(args.limit)
    if args.source == "bundesliga_deep":
        return await run_bundesliga_deep(args.limit, args.limit_players)
    if args.source == "bundesliga_overview":
        return await run_bundesliga_overview(args.limit)
    raise SystemExit("Unknown source")


def maybe_write_json(result: Any, out: str | None):
    if out is None or result is None:
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def configure_logging(verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    result = asyncio.run(dispatch(args))
    if args.out and not (args.source.endswith("_csv")):
        maybe_write_json(result, args.out)
    if result is not None and not args.out:
        # Print summary to stdout
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
