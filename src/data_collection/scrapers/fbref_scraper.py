"""
FBref Scraper for match and club IDs across configurable leagues
"""

import asyncio
import csv
import json
import os
import random
from datetime import datetime

from playwright.async_api import async_playwright

from src.core.config import Settings
from src.data_collection.scrapers.base import BaseScraper, ScrapingConfig
from src.common.playwright_utils import accept_consent
from src.database.manager import DatabaseManager
from src.domain.contracts import MatchRef

class FbrefScraper(BaseScraper):
    """Scraper for FBref match and club IDs from Premier League"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        cfg = ScrapingConfig(
            base_url="https://fbref.com",
            selectors={
                "scores_fixtures_tab": "a[href*='/schedule/']",
                "match_rows": "table[id^='sched'] tbody tr[id^='match']",
                "match_id_attr": "data-stat",
                "home_club_attr": "data-stat",
                "away_club_attr": "data-stat",
            },
            headers=None,
            delay_range=(5, 10),  # Longer delays
            max_retries=5,
            timeout=120,  # 2 minute timeout
            use_proxy=True,  # Enable proxy rotation
            proxy_list=getattr(settings, "PROXY_LIST", []),
            anti_detection=True,
            screenshot_on_error=True,
        )
        super().__init__(cfg, db_manager, name="fbref")
        self.settings = settings

    async def scrape_data(self) -> list[MatchRef]:
        """Enhanced version with detailed logging and human patterns"""
        self.logger.info("Starting FBref scraping with enhanced debugging")

        for attempt in range(self.config.max_retries):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{self.config.max_retries}")

                async with async_playwright() as p:
                    # Configure proxy if available
                    proxy = None
                    if self.config.use_proxy and self.config.proxy_list:
                        proxy = {
                            "server": random.choice(self.config.proxy_list),
                            "username": self.settings.PROXY_USER,
                            "password": self.settings.PROXY_PASS,
                        }
                        self.logger.debug(f"Using proxy: {proxy['server']}")

                    # Launch browser with proxy if configured
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--start-maximized",
                        ],
                        proxy=proxy,
                        slow_mo=random.randint(100, 500),
                    )

                    # Human-like context
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=self.anti_detection.session_headers.get("User-Agent"),
                        locale="en-US",
                        timezone_id="Europe/Berlin",
                    )

                    page = await context.new_page()

                    # Random mouse movement pattern
                    for _ in range(3):
                        await page.mouse.move(random.randint(0, 500), random.randint(0, 500))
                        await asyncio.sleep(random.uniform(0.1, 0.3))

                    matches_all = []
                    leagues = getattr(self.settings, "fbref_league_ids", [9]) or [9]
                    for league_id in leagues:
                        # Navigate to league schedule overview
                        self.logger.debug(
                            f"Navigating to FBref schedule page for league {league_id}..."
                        )
                        await page.goto(
                            f"{self.config.base_url}/en/comps/{league_id}/schedule/",
                            timeout=self.config.timeout * 1000,
                            wait_until="networkidle",
                        )
                        # Best-effort consent dismissal if any banner appears
                        try:
                            await accept_consent(page)
                        except Exception:
                            pass

                        # Wait for core elements with multiple fallbacks
                        try:
                            await page.wait_for_selector("#meta", state="attached", timeout=15000)
                            await page.wait_for_selector(
                                "table.stats_table", state="attached", timeout=15000
                            )
                        except:
                            await page.wait_for_selector(
                                "body", state="attached", timeout=5000
                            )  # Fallback

                        # Scroll to ensure elements are visible
                        await page.evaluate(
                            """
                            document.querySelector('table.stats_table')?.scrollIntoView()
                        """
                        )

                        # Human-like delay with activity
                        await asyncio.sleep(random.uniform(3, 6))
                        await page.mouse.move(random.randint(100, 300), random.randint(100, 300))

                        # Take debug screenshot to logs/fbref (or configured log dir)
                        try:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            out_dir = os.path.join(self.settings.log_file_path, 'fbref')
                            os.makedirs(out_dir, exist_ok=True)
                            await page.screenshot(path=os.path.join(out_dir, f"fbref_debug_{ts}_attempt{attempt}_comp{league_id}.png"))
                        except Exception:
                            pass

                        # Ensure DOM is ready
                        await page.wait_for_load_state("domcontentloaded")

                        # Wait for presence of at least one match link; if not, scroll a bit and retry
                        try:
                            await page.wait_for_selector("a[href^='/en/matches/']", timeout=60000)
                        except Exception:
                            for _ in range(5):
                                try:
                                    await page.evaluate(
                                        "window.scrollBy(0, Math.floor(window.innerHeight * 0.9))"
                                    )
                                    await asyncio.sleep(1.0)
                                    if await page.query_selector("a[href^='/en/matches/']"):
                                        break
                                except Exception:
                                    pass
                            # Final attempt to wait a short time
                            await page.wait_for_selector("a[href^='/en/matches/']", timeout=5000)

                        # Extract match and club IDs for this league
                        matches = await page.evaluate(
                            """() => {
                        // Collect rows that contain a match link
                        const rows = Array.from(document.querySelectorAll('table.stats_table tbody tr'))
                          .filter(r => !r.classList.contains('spacer') && !r.classList.contains('thead'));

                        const out = [];
                        for (const row of rows) {
                            const matchLink = row.querySelector('a[href^="/en/matches/"]');
                            const homeA = row.querySelector('[data-stat="home_team"] a[href*="/en/squads/"]');
                            const awayA = row.querySelector('[data-stat="away_team"] a[href*="/en/squads/"]');
                            if (!matchLink || !homeA || !awayA) continue;

                            const matchHrefParts = (matchLink.getAttribute('href') || '').split('/');
                            const homeHrefParts = (homeA.getAttribute('href') || '').split('/');
                            const awayHrefParts = (awayA.getAttribute('href') || '').split('/');

                            // Expected: /en/matches/{match_id}/...
                            //           ['', 'en', 'matches', '{id}', ...] => index 3
                            const match_id = matchHrefParts.length > 3 ? matchHrefParts[3] : null;
                            // Expected: /en/squads/{club_id}/...
                            //           ['', 'en', 'squads', '{id}', ...] => index 3
                            const home_club_id = homeHrefParts.length > 3 ? homeHrefParts[3] : null;
                            const away_club_id = awayHrefParts.length > 3 ? awayHrefParts[3] : null;

                            if (match_id && home_club_id && away_club_id) {
                                out.push({
                                    match_id,
                                    home_club_id,
                                    away_club_id,
                                    home_club_name: (homeA.textContent || '').trim() || null,
                                    away_club_name: (awayA.textContent || '').trim() || null,
                                });
                            }
                        }
                        return out;
                    }"""
                        )
                        matches_all.extend(matches)

                    if not matches_all:
                        raise ValueError("No matches found on any selected league page")

                    # Save local snapshots regardless of DB state
                    try:
                        await self._save_snapshot(matches_all)
                    except Exception as snap_err:
                        self.logger.warning(f"Failed to save local fbref snapshot: {snap_err}")

                    # Try DB processing; if DB not available, return scraped IDs
                    try:
                        # TODO: _process_matches returns dicts; function signature says list[dict]. Unify return type to list[MatchRef] for consistency or adjust annotations.
                        return await self._process_matches(matches_all)
                    except Exception as db_err:
                        self.logger.error(
                            f"DB processing failed, returning scraped IDs only: {db_err}"
                        )
                        # Return DTOs upstream
                        return [
                            MatchRef(
                                match_id=m.get('match_id'),
                                home_club_id=m.get('home_club_id'),
                                away_club_id=m.get('away_club_id'),
                                home_club_name=m.get('home_club_name'),
                                away_club_name=m.get('away_club_name'),
                            )
                            for m in matches_all
                        ]

            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")

                # Save detailed debug info
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                if self.config.screenshot_on_error and 'page' in locals():
                    try:
                        out_dir = os.path.join(self.settings.log_file_path, 'fbref')
                        os.makedirs(out_dir, exist_ok=True)
                        dest = os.path.join(out_dir, f"fbref_error_{timestamp}.png")
                        await page.screenshot(path=dest, full_page=True)
                        self.logger.info(f"Saved screenshot: {dest}")
                    except Exception as screenshot_error:
                        self.logger.error(f"Failed to save screenshot: {screenshot_error}")

                if attempt < self.config.max_retries - 1:
                    retry_delay = min(30, 5 * (attempt + 1))  # Exponential backoff max 30s
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue

                self.logger.error(f"FBref scraping failed after {self.config.max_retries} attempts")
                return []
            finally:
                if "browser" in locals():
                    await browser.close()

    async def _process_matches(self, matches: list[dict]) -> list[dict]:
        """Filter and prepare matches for DB insertion"""
        if not matches:
            return []

        # Filter out matches already in DB (guard against empty IN clause)
        match_ids = [m["match_id"] for m in matches]
        existing_match_ids: set = set()
        if match_ids:
            # TODO: Verify table/column names. Current DB schema uses matches.id and matches.external_ids(JSON), not matches.external_id (text).
            existing_matches = await self.db_manager.execute_query(
                "SELECT external_id FROM matches WHERE external_id = ANY($1::text[])", match_ids
            )
            existing_match_ids = {row["external_id"] for row in existing_matches}

        # Filter out clubs already in DB
        all_club_ids = list(
            {m["home_club_id"] for m in matches} | {m["away_club_id"] for m in matches}
        )
        existing_club_ids: set = set()
        if all_club_ids:
            # TODO: Same mismatch as above: ensure clubs table and external_id column actually exist.
            existing_clubs = await self.db_manager.execute_query(
                "SELECT external_id FROM clubs WHERE external_id = ANY($1::text[])", all_club_ids
            )
            existing_club_ids = {row["external_id"] for row in existing_clubs}

        # Prepare data for insertion
        new_matches = []
        new_clubs = set()

        for match in matches:
            if match["match_id"] not in existing_match_ids:
                new_matches.append(
                    {
                        "external_id": match["match_id"],
                        "home_club_id": match["home_club_id"],
                        "away_club_id": match["away_club_id"],
                    }
                )

            if match["home_club_id"] not in existing_club_ids:
                new_clubs.add((match["home_club_id"], match["home_club_name"]))

            if match["away_club_id"] not in existing_club_ids:
                new_clubs.add((match["away_club_id"], match["away_club_name"]))

        # Insert new data
        if new_clubs:
            await self.db_manager.execute_many(
                """
                INSERT INTO clubs (external_id, name, competition_id, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (external_id) DO NOTHING
                """,
                [(club_id, name, "premier_league") for club_id, name in new_clubs],
            )

        if new_matches:
            await self.db_manager.execute_many(
                """
                INSERT INTO matches (external_id, home_club_id, away_club_id, competition_id, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (external_id) DO NOTHING
                """,
                [
                    (m["external_id"], m["home_club_id"], m["away_club_id"], "premier_league")
                    for m in new_matches
                ],
            )

        return new_matches

    async def _save_snapshot(self, matches: list[dict]) -> None:
        """Save scraped match and club IDs to JSON and CSV under reports/fbref/.
        Additionally, write a separate club list (id + name) as JSON/CSV.
        """
        if not matches:
            return
        # Prepare output directory
        out_dir = os.path.join("reports", "fbref")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_path = os.path.join(out_dir, f"fbref_ids_{ts}.json")
        csv_path = os.path.join(out_dir, f"fbref_ids_{ts}.csv")
        latest_json = os.path.join(out_dir, "fbref_latest.json")
        latest_csv = os.path.join(out_dir, "fbref_latest.csv")
        clubs_json_path = os.path.join(out_dir, f"fbref_clubs_{ts}.json")
        clubs_csv_path = os.path.join(out_dir, f"fbref_clubs_{ts}.csv")
        clubs_latest_json = os.path.join(out_dir, "fbref_clubs_latest.json")
        clubs_latest_csv = os.path.join(out_dir, "fbref_clubs_latest.csv")

        # Normalize records
        records = [
            {
                "match_id": m.get("match_id") or m.get("external_id"),
                "home_club_id": m.get("home_club_id"),
                "away_club_id": m.get("away_club_id"),
                "home_club_name": m.get("home_club_name"),
                "away_club_name": m.get("away_club_name"),
            }
            for m in matches
        ]

        # Write JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"generated_at": ts, "count": len(records), "items": records},
                f,
                ensure_ascii=False,
                indent=2,
            )
        # Copy to latest
        try:
            with open(latest_json, "w", encoding="utf-8") as f:
                json.dump(
                    {"generated_at": ts, "count": len(records), "items": records},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

        # Write CSV
        fieldnames = [
            "match_id",
            "home_club_id",
            "away_club_id",
            "home_club_name",
            "away_club_name",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        # Copy to latest
        try:
            with open(latest_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
        except Exception:
            pass

        # Build unique club list
        club_map = {}
        for r in records:
            if r.get("home_club_id"):
                club_map[r["home_club_id"]] = r.get("home_club_name")
            if r.get("away_club_id"):
                club_map[r["away_club_id"]] = r.get("away_club_name")
        club_items = [
            {"club_id": cid, "club_name": cname}
            for cid, cname in sorted(club_map.items(), key=lambda x: x[0])
        ]

        # Write clubs JSON
        with open(clubs_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"generated_at": ts, "count": len(club_items), "items": club_items},
                f,
                ensure_ascii=False,
                indent=2,
            )
        try:
            with open(clubs_latest_json, "w", encoding="utf-8") as f:
                json.dump(
                    {"generated_at": ts, "count": len(club_items), "items": club_items},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

        # Write clubs CSV
        club_fields = ["club_id", "club_name"]
        with open(clubs_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=club_fields)
            writer.writeheader()
            writer.writerows(club_items)
        try:
            with open(clubs_latest_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=club_fields)
                writer.writeheader()
                writer.writerows(club_items)
        except Exception:
            pass

    async def test_scraper(self) -> bool:
        """Test function to verify the FBref scraper works"""
        try:
            test_results = await self.scrape_data()

            if not test_results:
                self.logger.warning("Test completed but no new data found")
                return True  # Consider empty results valid (may just mean no new matches)

            required_keys = {"match_id", "home_club_id", "away_club_id"}
            for result in test_results:
                # TODO: If scrape_data returns MatchRef objects, adjust this validation accordingly.
                if not all(key in result for key in required_keys):
                    self.logger.error(f"Test failed - missing keys in result: {result}")
                    return False

            self.logger.info(f"Test passed - found {len(test_results)} matches")
            return True

        except Exception as e:
            self.logger.error(f"Test failed with error: {str(e)}")
            return False