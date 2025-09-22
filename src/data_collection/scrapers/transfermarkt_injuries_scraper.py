from typing import Optional
import argparse
import csv
import json
import os
import random
import sys
import time
from pathlib import Path
from time import perf_counter

# Ensure project root and src are on sys.path so `from src.*` imports work
_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parents[1]  # .../src
_PROJECT_ROOT = _THIS_FILE.parents[2]  # project root
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Proactively load .env so DATABASE_URL is set for DB helpers
try:
    from dotenv import find_dotenv, load_dotenv  # type: ignore

    _ENV = find_dotenv(usecwd=True)
    if _ENV:
        load_dotenv(_ENV)
except Exception:
    pass

from pydantic import ValidationError

from src.common.db import (
    find_player_id_by_transfermarkt,
    get_conn,
    upsert_player_absence,
)
from src.common.http import DEFAULT_UAS, fetch_html
from src.common.parsing import (
    clean_text,
    extract_tm_player_id_from_href,
    parse_date,
    parse_int,
    soup_from_html,
)
from src.common.playwright_utils import BrowserSession, RenderWait, fetch_page, FetchOptions  # type: ignore
from src.domain.models import Injury, InjuryStatus

# Using shared HTTP utilities from common/http.py


def _guess_absence_type(reason: Optional[str]) -> str:
    r = (reason or "").lower()
    if any(k in r for k in ["sperre", "gesperrt", "suspension", "gelb", "rot"]):
        return "suspension"
    if any(k in r for k in ["illness", "ill", "krank"]):
        return "illness"
    if any(k in r for k in ["national", "landes", "länderspiel", "laenderspiel", "country duty"]):
        return "national_duty"
    return "injury"


def _map_absence_to_status(absence_type: str) -> InjuryStatus:
    at = (absence_type or "").lower()
    if at == "suspension":
        return InjuryStatus.SUSPENDED
    # Map both illness and injury to INJURED
    if at in {"injury", "illness"}:
        return InjuryStatus.INJURED
    # National team duty behaves like unavailable; use SUSPENDED as neutral unavailability
    if at == "national_duty":
        return InjuryStatus.SUSPENDED
    return InjuryStatus.INJURED


def _parse_injuries(html: str) -> list[dict]:
    soup = soup_from_html(html)
    results: list[dict] = []
    # Generic: find the main table with rows
    table = soup.select_one("table.items, table") or soup.find("table")
    if not table:
        return results
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all(["td", "th"])  # TM sometimes uses th for first cell
        if len(tds) < 4:
            continue
        # Player cell usually contains <a href="/spieler/ID...">Name</a>
        player_link = tr.select_one("a[href*='/spieler/'], a[href*='/player/']")
        player_href = player_link["href"] if player_link else None
        player_name = clean_text(player_link.get_text()) if player_link else None

        # Reason / Type cell
        # Strategy: select the cell immediately after the one that contains the player link
        reason = None
        player_td_idx = None
        for idx, td in enumerate(tds):
            if td.select_one("a[href*='/spieler/'], a[href*='/player/']"):
                player_td_idx = idx
                break
        if player_td_idx is not None and player_td_idx + 1 < len(tds):
            reason = clean_text(tds[player_td_idx + 1].get_text())
        # Secondary heuristic: a 'hauptlink' td without a player link
        if not reason:
            for rc in tr.select("td.hauptlink"):
                if not rc.select_one("a[href*='/spieler/'], a[href*='/player/']"):
                    reason = clean_text(rc.get_text())
                    break
        # Positional fallbacks
        if not reason:
            pos_cell = tr.select_one("td:nth-of-type(2)")
            if pos_cell:
                reason = clean_text(pos_cell.get_text())
            elif len(tds) > 1:
                reason = clean_text(tds[1].get_text())
        # Safety: if reason equals player_name due to page quirks, try another adjacent cell
        if reason and player_name and reason == player_name and player_td_idx is not None:
            # Try next-next cell if available
            if player_td_idx + 2 < len(tds):
                alt = clean_text(tds[player_td_idx + 2].get_text())
                if alt and alt != player_name:
                    reason = alt

        # Dates - Transfermarkt typically shows 'seit' and 'bis vorauss.'
        since_cell = tr.select_one("td.zentriert:nth-of-type(4)") or (
            tds[3] if len(tds) > 3 else None
        )
        until_cell = tr.select_one("td.zentriert:nth-of-type(5)") or (
            tds[4] if len(tds) > 4 else None
        )
        start_date = parse_date(since_cell.get_text()) if since_cell else None
        end_or_expected = parse_date(until_cell.get_text()) if until_cell else None

        # Missed games often near the end columns
        missed_cell = tr.select_one("td.zentriert:nth-of-type(7)") or (
            tds[6] if len(tds) > 6 else None
        )
        missed_games = parse_int(missed_cell.get_text()) if missed_cell else None

        results.append(
            {
                "player_href": player_href,
                "player_name": player_name,
                "reason": reason,
                "start_date": start_date.isoformat() if start_date else None,
                "end_or_expected": end_or_expected.isoformat() if end_or_expected else None,
                "missed_games": missed_games,
            }
        )
    return results


def _pick_ua(args) -> str:
    try:
        pool = (
            open(args.ua_file, encoding="utf-8").read().splitlines()
            if args.ua_file and os.path.exists(args.ua_file)
            else DEFAULT_UAS
        )
        return random.choice(pool) if getattr(args, "ua_rotate", False) else pool[0]
    except Exception:
        return DEFAULT_UAS[0]


def _render_or_fetch(url: str, args) -> str:
    if getattr(args, "render", False):
        ua = _pick_ua(args)
        wait_selectors = [s.strip() for s in (args.render_wait_selector or "").split(",") if s.strip()] or None
        wait_texts = [t.strip() for t in (args.render_wait_text or "").split(",") if t.strip()] or None
        if args.verbose:
            print(f"[render] {url} wait selectors={wait_selectors} text={wait_texts} network_idle={args.render_wait_network_idle}")
        try:
            # Use unified async fetch (convert to sync via event loop run)
            import asyncio
            html = asyncio.run(fetch_page(FetchOptions(
                url=url,
                headless=not args.render_headful,
                user_agent=ua,
                wait_selectors=wait_selectors,
                wait_text=wait_texts,
                network_idle=args.render_wait_network_idle,
                timeout_ms=int(args.render_timeout * 1000),
                retries=args.retries,
            )))
            return html
        except Exception as e:
            if args.verbose:
                print(f"[render->fallback] {e}")
    # HTTP fallback/default
    return fetch_html(
        url,
        timeout=args.timeout,
        retries=args.retries,
        backoff=args.backoff,
        proxy=args.proxy,
        verbose=args.verbose,
        user_agents=(
            open(args.ua_file, encoding="utf-8").read().splitlines()
            if args.ua_file and os.path.exists(args.ua_file)
            else DEFAULT_UAS
        ),
        rotate_ua=args.ua_rotate,
        force_ua_on_429=args.force_ua_on_429,
        header_randomize=(not args.no_header_randomize),
        pre_jitter=args.pre_jitter,
    )


def process_one(args):
    # Example: https://www.transfermarkt.de/{club}/sperrenundverletzungen/verein/{club_id}/plus/1
    if not args.url and not args.club_id:
        raise ValueError("Provide --url or --club-id")
    url = (
        args.url
        or f"https://www.transfermarkt.de/-/sperrenundverletzungen/verein/{args.club_id}/plus/1"
    )
    t0 = perf_counter()
    html = _render_or_fetch(url, args)
    dt = perf_counter() - t0
    if args.verbose:
        print(f"Fetched injuries page in {dt*1000:.0f} ms -> {url}")
    rows = _parse_injuries(html)
    if args.verbose:
        print(f"Parsed rows: {len(rows)}")

    upserted = 0
    unresolved = 0
    with get_conn() as conn:
        for r in rows:
            tm_pid = extract_tm_player_id_from_href(r.get("player_href"))
            if not tm_pid:
                unresolved += 1
                if args.verbose:
                    print(f"Skip: no TM player id for '{r.get('player_name')}'")
                continue
            player_id = find_player_id_by_transfermarkt(conn, tm_pid)
            if not player_id:
                unresolved += 1
                if args.verbose:
                    print(f"Skip: TM player {tm_pid} not mapped in external_id_map")
                continue
            absence_type = _guess_absence_type(r.get("reason"))
            status = _map_absence_to_status(absence_type)
            try:
                injury = Injury(
                    player_id=player_id,
                    team_id=None,
                    description=r.get("reason"),
                    status=status,
                    start_date=r.get("start_date"),
                    expected_return=r.get("end_or_expected"),
                )
            except ValidationError as ve:
                unresolved += 1
                if args.verbose:
                    print(f"ValidationError for player {player_id}: {ve}")
                continue

            # Heuristic: put parsed end date into expected_return_date
            upsert_player_absence(
                conn,
                player_id=player_id,
                absence_type=absence_type,
                reason=injury.description,
                start_date=(injury.start_date.isoformat() if injury.start_date else None),
                end_date=None,
                expected_return_date=(
                    injury.expected_return.isoformat() if injury.expected_return else None
                ),
                missed_games=r.get("missed_games"),
                source_url=url,
            )
            upserted += 1

    print(
        json.dumps(
            {
                "source": "transfermarkt",
                "collector": "injuries",
                "input": {"url": url, "club_id": args.club_id},
                "status": "ok",
                "upserted": upserted,
                "unresolved": unresolved,
            },
            ensure_ascii=False,
        )
    )


def main():
    p = argparse.ArgumentParser(description="Transfermarkt Injuries Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="Injuries URL")
    p.add_argument("--club-id", type=str, default=None, help="Club id")
    p.add_argument("--batch-file", type=str, default=None, help="CSV with columns: url|club_id")
    p.add_argument("--min-interval", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--backoff", type=float, default=1.5)
    p.add_argument("--proxy", type=str, default=None)
    p.add_argument("--ua-file", type=str, default=None)
    p.add_argument("--ua-rotate", action="store_true")
    p.add_argument("--force-ua-on-429", action="store_true")
    p.add_argument("--no-header-randomize", action="store_true")
    p.add_argument("--pre-jitter", type=float, default=0.0)
    p.add_argument("--verbose", action="store_true")
    # Rendering options (Playwright)
    p.add_argument(
        "--render", action="store_true", help="Render page via Playwright before parsing"
    )
    p.add_argument(
        "--render-timeout",
        type=float,
        default=35.0,
        help="Default timeout in seconds for rendering",
    )
    p.add_argument(
        "--render-wait-selector",
        type=str,
        default="table.items, .items, .responsive-table",
        help="Comma-separated CSS selectors to wait for",
    )
    p.add_argument(
        "--render-wait-text",
        type=str,
        default="",
        help="Comma-separated text snippets to wait for",
    )
    p.add_argument(
        "--render-wait-network-idle", action="store_true", help="Additionally wait for network idle"
    )
    p.add_argument(
        "--render-headful", action="store_true", help="Run browser non-headless for debugging"
    )
    args = p.parse_args()

    if args.batch_file:
        with open(args.batch_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            total = 0
            for row in reader:
                local = argparse.Namespace(**vars(args))
                local.url = row.get("url") or None
                local.club_id = row.get("club_id") or args.club_id
                process_one(local)
                total += 1
                if args.min_interval and args.min_interval > 0:
                    time.sleep(args.min_interval)
        if args.verbose:
            print(f"Batch finished, items={total}")
    else:
        process_one(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
