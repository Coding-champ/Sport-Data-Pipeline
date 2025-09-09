from typing import Optional
from typing import Optional
"""
Flashscore Live-Scores Scraper für die Sport Data Pipeline

Implementiert Web Scraping für Live-Scores von Flashscore.
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from src.core.config import Settings
from src.data_collection.scrapers.base import BaseScraper, ScrapingConfig
from src.database.manager import DatabaseManager


class FlashscoreScraper(BaseScraper):
    """Scraper für Flashscore Live-Scores"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        config = ScrapingConfig(
            base_url="https://www.flashscore.de",
            selectors={
                "match_row": ".event__match",
                "home_team": ".event__participant--home",
                "away_team": ".event__participant--away",
                "score": ".event__score",
                "time": ".event__time",
                "status": ".event__stage",
            },
            headers=None,
            delay_range=(1, 2),
            anti_detection=True,
        )
        super().__init__(config, db_manager, "flashscore")
        self.settings = settings

    async def scrape_data(self) -> list[dict]:
        """Scrapt Live-Scores von Flashscore"""
        matches_data = []

        football_url = f"{self.config.base_url}/fussball/"

        try:
            html = await self.fetch_page(football_url, use_cloudscraper=True)
            soup = self.parse_html(html)

            # Match-Container robust finden (verschiedene Varianten)
            match_rows = soup.select(
                "div.event__match, div.event__match--live, div.event__match--scheduled, div.event__match--static, div.event__match__row, a.event__match__row--link, div[class*='event__match']"
            )
            self.logger.debug(
                f"flashscore: found {len(match_rows)} potential match rows on /fussball/"
            )

            seen, with_teams, with_score, extracted = 0, 0, 0, 0
            for match_row in match_rows:
                try:
                    seen += 1
                    match_data = self._extract_match_data(match_row)
                    if match_data:
                        with_teams += 1
                        if (
                            match_data.get("home_score") is not None
                            or match_data.get("away_score") is not None
                        ):
                            with_score += 1
                        matches_data.append(match_data)
                        extracted += 1
                except Exception as e:
                    self.logger.warning(f"Failed to extract match: {e}")
                    continue

            await self.anti_detection.random_delay()
            self.logger.debug(
                f"flashscore extraction stats: seen={seen}, with_teams={with_teams}, with_score={with_score}, extracted={extracted}"
            )
            if not matches_data:
                # Snapshot sichern zur Analyse
                try:
                    logs_dir = Path(self.settings.log_file_path)
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    snapshot_path = (
                        logs_dir
                        / f"flashscore_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    )
                    snapshot_path.write_text(html, encoding="utf-8")
                    self.logger.info(
                        f"No matches parsed on /fussball/. Saved HTML snapshot to {snapshot_path}"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to save HTML snapshot: {e}")
            return matches_data

        except Exception as e:
            self.logger.error(f"Flashscore scraping failed: {e}")
            raise

    async def fetch_page(self, url: str, use_cloudscraper: bool = False) -> str:
        """Holt eine Webseite via Playwright (immer), klickt Consent und rendert HTML.
        Der Parameter use_cloudscraper ist aus Kompatibilitätsgründen vorhanden und wird ignoriert.
        """
        try:
            return await self.fetch_with_playwright(url)
        except Exception as e:
            self.logger.error(f"Failed to fetch page {url} with Playwright: {e}")
            raise

    async def fetch_with_playwright(self, url: str) -> str:
        """Verwendet Playwright mit Retries, akzeptiert Consent und rendert HTML."""
        timeout = 45000
        # Use centralized anti-detection headers (common.http)
        headers = (
            getattr(self, "anti_detection", None).session_headers
            if getattr(self, "anti_detection", None)
            else {}
        )
        user_agent = headers.get("User-Agent", "Mozilla/5.0")
        accept_lang = headers.get("Accept-Language", "de-DE,de;q=0.9")

        retries = 3
        backoff = 1.0
        last_err = None

        for attempt in range(1, retries + 1):
            try:
                self.logger.debug(f"Playwright fetch attempt {attempt}/{retries} for {url}")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=user_agent,
                        locale="de-DE",
                        timezone_id="Europe/Berlin",
                        viewport={"width": 1280, "height": 1800},
                        device_scale_factor=1.0,
                        extra_http_headers={"Accept-Language": accept_lang},
                    )
                    page = await context.new_page()
                    html = ""
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            pass

                        # Consent-Buttons
                        consent_selectors = [
                            "#onetrust-accept-btn-handler",
                            "button:has-text('Akzeptieren')",
                            "button:has-text('Alle akzeptieren')",
                            "button:has-text('Agree')",
                            "button:has-text('I agree')",
                            "#didomi-notice-agree-button",
                            "button[data-qa='consent-accept-all']",
                            "#qc-cmp2-ui button:has-text('Zustimmen')",
                            "#qc-cmp2-ui button:has-text('Einverstanden')",
                        ]
                        for sel in consent_selectors:
                            try:
                                if await page.locator(sel).first.is_visible(timeout=1000):
                                    await page.locator(sel).first.click(timeout=2000)
                                    await page.wait_for_timeout(500)
                                    break
                            except Exception:
                                continue

                        # Live-Filter aktivieren
                        live_selectors = [
                            "a[role='tab']:has-text('Live')",
                            "a:has-text('LIVE')",
                            "button:has-text('Live')",
                            "[data-testid='live']",
                        ]
                        for lsel in live_selectors:
                            try:
                                if await page.locator(lsel).first.is_visible(timeout=1000):
                                    await page.locator(lsel).first.click(timeout=1500)
                                    await page.wait_for_timeout(500)
                                    break
                            except Exception:
                                continue

                        # Lazy-Loading anstoßen
                        try:
                            for _ in range(3):
                                await page.mouse.wheel(0, 1200)
                                await page.wait_for_timeout(400)
                        except Exception:
                            pass

                        # Auf Match-Container warten (best effort)
                        try:
                            await page.wait_for_selector("div[class*='event__match']", timeout=8000)
                        except Exception:
                            pass

                        html = await page.content()
                    finally:
                        await context.close()
                        await browser.close()

                    if html:
                        return html

            except Exception as e:
                last_err = e
                self.logger.warning(
                    f"Playwright fetch failed (attempt {attempt}/{retries}) for {url}: {e}"
                )
                if attempt < retries:
                    sleep_for = backoff + random.uniform(0, 0.5)
                    await asyncio.sleep(sleep_for)
                    backoff = min(backoff * 2, 8.0)
                else:
                    break

        raise RuntimeError(f"Playwright failed after {retries} attempts: {last_err}")

    def _extract_match_data(self, match_element) -> Optional[dict]:
        """Extrahiert Match-Daten"""
        try:
            # Tag-agnostische Auswahl via CSS (neue und alte Struktur)
            home_team_el = match_element.select_one(
                '.event__participant--home, .event__homeParticipant .wcl-name_jjfMf, .event__homeParticipant [data-testid="wcl-scores-simpleText-01"]'
            )
            away_team_el = match_element.select_one(
                '.event__participant--away, .event__awayParticipant .wcl-name_jjfMf, .event__awayParticipant [data-testid="wcl-scores-simpleText-01"]'
            )
            # Scores: getrennte Spans (home/away) oder kombinierter Block
            score_home_el = match_element.select_one(
                '.event__score--home, [data-testid="wcl-matchRowScore"][data-side="1"]'
            )
            score_away_el = match_element.select_one(
                '.event__score--away, [data-testid="wcl-matchRowScore"][data-side="2"]'
            )
            score_combined_el = match_element.select_one(
                ".event__score"
            ) or match_element.select_one(".event__scores")
            time_elem = match_element.select_one(".event__time")
            status_elem = match_element.select_one(".event__stage")

            if not all([home_team_el, away_team_el]):
                return None

            # Status bestimmen
            status = "scheduled"
            text_time = time_elem.text.strip() if time_elem else ""
            # Direkter Live-Hinweis über Klassen
            classes = match_element.get("class", [])
            is_live_class = (
                any("event__match--live" in c for c in classes)
                if isinstance(classes, list)
                else False
            )
            # Zeit-/Status-Heuristiken
            live_tokens = ["'", "HT", "1. HZ", "2. HZ", "ET", "PEN"]
            is_live_time = any(tok in text_time for tok in live_tokens)
            is_finished_time = any(tok in text_time for tok in ["FT", "AET"])  # End of match tokens

            if is_live_class or is_live_time:
                status = "live"
            else:
                # Decide based on presence of score elements
                has_any_score_el = (
                    (score_home_el and (score_home_el.text or "").strip())
                    or (score_away_el and (score_away_el.text or "").strip())
                    or (score_combined_el and (score_combined_el.text or "").strip())
                )
                if has_any_score_el:
                    status = "finished" if (is_finished_time or not is_live_time) else "live"

            # Score parsen
            def _to_int_safe(s: str) -> Optional[int]:
                s = (s or "").strip()
                if not s or s == "-" or s.lower() == "vs":
                    return None
                try:
                    return int(s)
                except Exception:
                    return None

            home_score, away_score = None, None
            if score_home_el or score_away_el:
                home_score = _to_int_safe(score_home_el.text if score_home_el else None)
                away_score = _to_int_safe(score_away_el.text if score_away_el else None)
            elif score_combined_el and score_combined_el.text and " - " in score_combined_el.text:
                parts = [p.strip() for p in score_combined_el.text.strip().split(" - ", 1)]
                if len(parts) == 2:
                    home_score = _to_int_safe(parts[0])
                    away_score = _to_int_safe(parts[1])

            return {
                "home_team": home_team_el.text.strip(),
                "away_team": away_team_el.text.strip(),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "match_time": time_elem.text.strip() if time_elem else "",
                "stage": status_elem.text.strip() if status_elem else "",
                "source": "flashscore",
                "scraped_at": datetime.now(),
            }

        except Exception as e:
            self.logger.debug(f"Failed to extract match data: {e}")
            return None

    async def scrape_league_matches(self, league_url: str) -> list[dict]:
        """Scrapt Matches einer spezifischen Liga"""
        matches_data = []

        try:
            html = await self.fetch_page(league_url, use_cloudscraper=True)
            soup = self.parse_html(html)

            # Liga-spezifische Match-Container
            match_containers = soup.find_all("div", class_=["event__match", "event__match--static"])

            for container in match_containers:
                match_data = self._extract_match_data(container)
                if match_data:
                    matches_data.append(match_data)

            self.logger.info(f"Scraped {len(matches_data)} matches from league")
            return matches_data

        except Exception as e:
            self.logger.error(f"League scraping failed for {league_url}: {e}")
            return []

    async def scrape_live_scores(self) -> list[dict]:
        """Scrapt nur Live-Matches"""
        live_url = f"{self.config.base_url}/live/"
        try:
            # Erster Versuch: dedizierte Live-Seite
            html = await self.fetch_page(live_url, use_cloudscraper=True)
            soup = self.parse_html(html)
        except Exception as e:
            # Fallback: Haupt-Fußballseite und dort live filtern
            self.logger.warning(f"Live page failed ({e}), falling back to /fussball/")
            try:
                html = await self.fetch_page(
                    f"{self.config.base_url}/fussball/", use_cloudscraper=True
                )
                soup = self.parse_html(html)
            except Exception as e2:
                self.logger.error(f"Live scores scraping failed: {e2}")
                return []

        # Live-Matches parsen und filtern
        live_matches = []
        # Breitere Auswahl an Match-Containern (inkl. scheduled/static Varianten)
        match_rows = soup.select(
            "div.event__match, div.event__match--live, div.event__match--scheduled, div.event__match--static, div.event__match__row, a.event__match__row--link, div[class*='event__match']"
        )
        self.logger.debug(
            f"flashscore: found {len(match_rows)} potential match rows on page {live_url if 'soup' in locals() else ''}"
        )
        for match_row in match_rows:
            match_data = self._extract_match_data(match_row)
            if match_data and match_data.get("status") == "live":
                live_matches.append(match_data)

        # Wenn keine Live-Matches gefunden: optional geplante Spiele zurückgeben
        if not live_matches and getattr(self.settings, "include_scheduled_on_empty", False):
            scheduled_matches = []
            for match_row in match_rows:
                match_data = self._extract_match_data(match_row)
                if match_data and match_data.get("status") == "scheduled":
                    scheduled_matches.append(match_data)
            if scheduled_matches:
                self.logger.info(
                    f"No live matches found. Returning {len(scheduled_matches)} scheduled matches (include_scheduled_on_empty=True)"
                )
                return scheduled_matches

        # Wenn weiterhin keine Matches gefunden wurden: HTML Snapshot speichern zur Analyse
        if not live_matches:
            try:
                logs_dir = Path(self.settings.log_file_path)
                logs_dir.mkdir(parents=True, exist_ok=True)
                snapshot_path = (
                    logs_dir
                    / f"flashscore_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                snapshot_path.write_text(html, encoding="utf-8")
                self.logger.info(f"No live matches found. Saved HTML snapshot to {snapshot_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save HTML snapshot: {e}")

        self.logger.info(f"Found {len(live_matches)} live matches (after fallback if needed)")
        return live_matches

    async def save_matches_to_database(self, matches_data: list[dict]):
        """Speichert Match-Daten in die Datenbank"""
        if not matches_data:
            return

        try:
            # Transformiere Daten für DB-Schema
            db_data = []
            for match in matches_data:
                db_data.append(
                    {
                        "external_id": f"flashscore_{hash('_'.join([str(match['home_team']), str(match['away_team']), str(match['scraped_at'])]))}",
                        "home_team_name": match["home_team"],
                        "away_team_name": match["away_team"],
                        "home_score": match["home_score"],
                        "away_score": match["away_score"],
                        "status": match["status"],
                        "match_time": match["match_time"],
                        "source": "flashscore",
                        "created_at": match["scraped_at"],
                    }
                )

            # Bulk Insert in live_scores Tabelle (oder ähnlich)
            await self.db_manager.bulk_insert(
                "live_scores",
                db_data,
                "ON CONFLICT (external_id) DO UPDATE SET "
                "home_score = EXCLUDED.home_score, "
                "away_score = EXCLUDED.away_score, "
                "status = EXCLUDED.status, "
                "updated_at = CURRENT_TIMESTAMP",
            )

            self.logger.info(f"Saved {len(db_data)} match records to database")

        except Exception as e:
            self.logger.error(f"Failed to save matches to database: {e}")
            raise
