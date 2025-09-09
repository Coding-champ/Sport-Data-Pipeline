"""
Command-line interface for running scraping and scheduling jobs.
Usage examples:
  python -m src.apps.cli run-once --jobs flashscore odds
  python -m src.apps.cli run-once --jobs all
  python -m src.apps.cli schedule --duration-minutes 10
"""

import argparse
import asyncio
import logging
from typing import Any

import click

from src.core.config import Settings, settings
from src.data_collection.scrapers.courtside_scraper import CourtsideScraper
from src.data_collection.scrapers.fbref_scraper import FbrefScraper
from src.data_collection.scrapers.flashscore_scraper import FlashscoreScraper
from src.data_collection.scrapers.bet365_scraper import Bet365Scraper
from src.data_collection.scrapers.scraping_orchestrator import (
    ScrapingOrchestrator,
    ScrapingScheduler,
)
from src.data_collection.scrapers.transfermarkt_scraper import TransfermarktScraper
from src.database.manager import DatabaseManager


def _build_orchestrator(db: DatabaseManager, cfg: Settings) -> ScrapingOrchestrator:
    orch = ScrapingOrchestrator(db, cfg)
    # Register scrapers
    orch.register_scraper(TransfermarktScraper(db, cfg))
    orch.register_scraper(FlashscoreScraper(db, cfg))
    orch.register_scraper(Bet365Scraper(db, cfg))
    orch.register_scraper(FbrefScraper(db, cfg))
    orch.register_scraper(CourtsideScraper(db, cfg))
    return orch


async def _init_db(db: DatabaseManager) -> None:
    # Initialize both engines; tolerate failures in local/dev
    try:
        db.initialize_sync()
    except Exception:
        pass
    try:
        await db.initialize_async()
    except Exception:
        pass


async def cmd_run_once(jobs: list[str]) -> int:
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    db = DatabaseManager()
    await _init_db(db)

    orch = _build_orchestrator(db, settings)
    await orch.initialize_all()

    # Normalize jobs
    if not jobs or jobs == ["all"]:
        targets = None  # run all registered
    else:
        targets = jobs

    results = await orch.run_scraping_job(targets)
    await orch.cleanup_all()
    await db.close()

    # Simple exit code convention: 0 if no errors
    any_error = any(v.get("status") == "error" for v in results.values())
    return 1 if any_error else 0


async def cmd_schedule(duration_minutes: int) -> int:
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    db = DatabaseManager()
    await _init_db(db)

    orch = _build_orchestrator(db, settings)
    await orch.initialize_all()

    scheduler = ScrapingScheduler(orch)

    async def _run_for_duration():
        try:
            asyncio.create_task(scheduler.start_schedule())
            await asyncio.sleep(max(duration_minutes, 1) * 60)
        finally:
            scheduler.stop()
            await orch.cleanup_all()
            await db.close()

    await _run_for_duration()
    return 0


def _collect_scrapers_info(orch: ScrapingOrchestrator) -> list[dict[str, Any]]:
    # Access the internal registry after build; avoid initialization
    infos: list[dict[str, Any]] = []
    for name, scraper in getattr(orch, "scrapers", {}).items():
        desc = getattr(scraper, "DESCRIPTION", None)
        if not desc:
            # Fallback to class docstring or empty
            desc = (scraper.__class__.__doc__ or "").strip()
        infos.append(
            {
                "name": name,
                "class": scraper.__class__.__name__,
                "description": desc,
            }
        )
    return sorted(infos, key=lambda x: x["name"])


def cmd_list_scrapers() -> int:
    db = DatabaseManager()
    orch = _build_orchestrator(db, settings)
    infos = _collect_scrapers_info(orch)
    print("Available scrapers:\n")
    for it in infos:
        line = f"- {it['name']} ({it['class']})"
        print(line)
        if it["description"]:
            print(f"  {it['description']}")
    return 0


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--leagues",
    multiple=True,
    type=int,
    help="FBref competition IDs (e.g. 9 12 11). Overrides settings.fbref_league_ids for this run.",
)
def test_fbref(leagues: tuple[int, ...] = ()):
    """Test the FBref scraper"""
    import asyncio

    from src.core.config import Settings
    from src.database.manager import DatabaseManager

    async def run_test():
        db_manager = DatabaseManager()
        settings = Settings(fbref_league_ids=list(leagues)) if leagues else Settings()
        try:
            # Ensure DB pools are available for the scraper's queries
            try:
                db_manager.initialize_sync()
            except Exception:
                pass
            try:
                await db_manager.initialize_async()
            except Exception:
                pass

            scraper = FbrefScraper(db_manager, settings)
            return await scraper.test_scraper()
        finally:
            try:
                await db_manager.close()
            except Exception:
                pass

    success = asyncio.run(run_test())

    if success:
        click.echo("FBref scraper test passed!")
    else:
        click.echo("FBref scraper test failed - check logs for details")


@cli.command()
def test_fbref_sync():
    """Sync wrapper for FBref test command"""
    import asyncio

    asyncio.run(test_fbref())


@cli.command()
async def run_once():
    """Run one-off scraping jobs"""
    parser = argparse.ArgumentParser(description="Sport Data Pipeline CLI")
    parser.add_argument(
        "--jobs",
        nargs="+",
        default=["all"],
        choices=["flashscore", "odds", "transfermarkt", "fbref", "courtside", "all"],
        help="Which scrapers to run (default: all)",
    )
    args = parser.parse_args()
    exit_code = await cmd_run_once(args.jobs)
    raise SystemExit(exit_code)


@cli.command()
async def schedule():
    """Run scheduler for a limited time"""
    parser = argparse.ArgumentParser(description="Sport Data Pipeline CLI")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=10,
        help="How long to keep the scheduler running (default: 10)",
    )
    args = parser.parse_args()
    exit_code = await cmd_schedule(args.duration_minutes)
    raise SystemExit(exit_code)


@cli.command(name="import-fbref-ids")
def import_fbref_ids():
    """Importiert die zuletzt exportierten FBref-IDs (JSON) in eine Staging-Tabelle.

    Quelle: reports/fbref/fbref_latest.json
    Zieltabelle: external_id_staging (wird bei Bedarf angelegt)
    """
    import asyncio
    import json
    import os

    from src.database.manager import DatabaseManager

    async def _run():
        db = DatabaseManager()
        try:
            # init DB (tolerate partial failures)
            try:
                db.initialize_sync()
            except Exception:
                pass
            try:
                await db.initialize_async()
            except Exception:
                pass

            # Ensure staging table exists
            await db.execute_query(
                """
                CREATE TABLE IF NOT EXISTS external_id_staging (
                  staging_id SERIAL PRIMARY KEY,
                  provider TEXT NOT NULL,
                  entity_type TEXT NOT NULL,
                  external_id TEXT NOT NULL,
                  external_url TEXT,
                  payload JSONB,
                  last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                  created_at TIMESTAMPTZ DEFAULT NOW(),
                  UNIQUE (provider, entity_type, external_id)
                )
                """
            )

            # Load latest file
            latest_path = os.path.join("reports", "fbref", "fbref_latest.json")
            if not os.path.exists(latest_path):
                click.echo(
                    f"File not found: {latest_path}. Bitte zuerst den FBref-Scraper laufen lassen."
                )
                return 1

            with open(latest_path, encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("items", [])
            if not items:
                click.echo("No items in latest JSON.")
                return 0

            # Prepare rows for staging: both clubs and matches
            rows = []
            for it in items:
                match_id = it.get("match_id")
                home_id = it.get("home_club_id")
                away_id = it.get("away_club_id")
                # match row
                if match_id:
                    rows.append(
                        (
                            "fbref",
                            "match",
                            match_id,
                            f"https://fbref.com/en/matches/{match_id}/",
                            json.dumps(it),
                        )
                    )
                # club rows
                if home_id:
                    rows.append(
                        (
                            "fbref",
                            "club",
                            home_id,
                            f"https://fbref.com/en/squads/{home_id}/",
                            json.dumps({"club_id": home_id, "name": it.get("home_club_name")}),
                        )
                    )
                if away_id:
                    rows.append(
                        (
                            "fbref",
                            "club",
                            away_id,
                            f"https://fbref.com/en/squads/{away_id}/",
                            json.dumps({"club_id": away_id, "name": it.get("away_club_name")}),
                        )
                    )

            # Upsert into staging
            if rows:
                await db.execute_many(
                    """
                    INSERT INTO external_id_staging
                      (provider, entity_type, external_id, external_url, payload, last_seen_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                    ON CONFLICT (provider, entity_type, external_id)
                    DO UPDATE SET external_url = EXCLUDED.external_url,
                                  payload = EXCLUDED.payload,
                                  last_seen_at = NOW()
                    """,
                    rows,
                )
            click.echo(f"Imported/updated {len(rows)} rows into external_id_staging.")
            return 0
        finally:
            try:
                await db.close()
            except Exception:
                pass

    exit_code = asyncio.run(_run())
    raise SystemExit(exit_code)


@cli.command()
def scrapers():
    """List available scrapers with descriptions"""
    exit_code = cmd_list_scrapers()
    raise SystemExit(exit_code)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
