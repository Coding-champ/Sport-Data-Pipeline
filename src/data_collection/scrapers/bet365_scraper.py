from typing import Optional
"""
Bet365 Odds Scraper für die Sport Data Pipeline

Implementiert Web Scraping für Wett-Quoten von verschiedenen Buchmachern.
"""

import asyncio
from datetime import datetime

from src.core.config import Settings
from src.data_collection.scrapers.base import PlaywrightScraper, ScrapingConfig
from src.database.manager import DatabaseManager


class Bet365Scraper(PlaywrightScraper):
    """Scraper für Wett-Quoten"""

    def __init__(self, db_manager: DatabaseManager, settings: Settings):
        config = ScrapingConfig(
            base_url="https://www.bet365.com",  # Beispiel
            selectors={
                "match_row": ".gl-Market_General",
                "odds_home": ".gl-Participant_General:first-child .gl-ParticipantOddsOnly_Odds",
                "odds_draw": ".gl-Participant_General:nth-child(2) .gl-ParticipantOddsOnly_Odds",
                "odds_away": ".gl-Participant_General:last-child .gl-ParticipantOddsOnly_Odds",
            },
            headers=None,
            delay_range=(3, 6),
            anti_detection=True,
        )
        super().__init__(config, db_manager, "odds")
        self.settings = settings

    async def initialize(self):
        """Initialize Playwright unless in FASTAPI_SAFE_MODE.

        Skips heavy browser startup for quick health checks.
        """
        import os
        if os.getenv("FASTAPI_SAFE_MODE", "0") == "1":
            self.logger.info("SAFE_MODE: skipping Bet365Scraper Playwright initialization")
            return
        await super().initialize()

    async def scrape_data(self) -> list[dict]:
        """Scrapt Wett-Quoten (Beispiel-Implementierung)"""
        odds_data = []
        try:
            # Wenn Page nicht initialisiert (SAFE_MODE), gib leere Liste zurück
            if not getattr(self, "page", None):
                self.logger.info("SAFE_MODE or uninitialized Playwright page: returning no odds data")
                return []

            # Robuste Navigation mit networkidle und Retry
            for attempt in range(3):
                try:
                    await self.goto_page(f"{self.config.base_url}/soccer", wait_until="networkidle")
                    await self.page.wait_for_selector(".gl-Market_General", timeout=45000)
                    break
                except Exception as e:
                    self.logger.warning(f"Navigation/wait attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(3)

            # Matches mit Quoten sammeln
            match_elements = await self.page.query_selector_all(".gl-Market_General")
            for match_elem in match_elements[:10]:  # Limit für Demo
                try:
                    odds_data_item = await self._extract_odds_data(match_elem)
                    if odds_data_item:
                        odds_data.append(odds_data_item)
                except Exception as e:
                    self.logger.warning(f"Failed to extract odds: {e}")
                    continue
            return odds_data
        except Exception as e:
            self.logger.error(f"Odds scraping failed: {e}")
            raise

    async def _extract_odds_data(self, match_element) -> Optional[dict]:
        """Extrahiert Odds-Daten"""
        try:
            # Teams extrahieren
            teams = await match_element.query_selector_all(
                ".gl-ParticipantFixtureDetails_TeamNames"
            )
            if len(teams) < 2:
                return None

            home_team = await teams[0].text_content()
            away_team = await teams[1].text_content()

            # Odds extrahieren
            odds_elements = await match_element.query_selector_all(".gl-ParticipantOddsOnly_Odds")

            if len(odds_elements) >= 3:
                odds_home = await odds_elements[0].text_content()
                odds_draw = await odds_elements[1].text_content()
                odds_away = await odds_elements[2].text_content()
            else:
                return None

            return {
                "home_team": home_team.strip(),
                "away_team": away_team.strip(),
                "odds_home": float(odds_home) if odds_home.replace(".", "").isdigit() else None,
                "odds_draw": float(odds_draw) if odds_draw.replace(".", "").isdigit() else None,
                "odds_away": float(odds_away) if odds_away.replace(".", "").isdigit() else None,
                "bookmaker": "bet365",
                "scraped_at": datetime.now(),
            }

        except Exception as e:
            self.logger.debug(f"Failed to extract odds data: {e}")
            return None

    async def scrape_multiple_bookmakers(self) -> list[dict]:
        """Scrapt Odds von mehreren Buchmachern"""
        all_odds = []

        bookmakers = [
            {
                "name": "bet365",
                "url": "https://www.bet365.com/soccer",
                "selectors": {
                    "match_row": ".gl-Market_General",
                    "teams": ".gl-ParticipantFixtureDetails_TeamNames",
                    "odds": ".gl-ParticipantOddsOnly_Odds",
                },
            },
            {
                "name": "bwin",
                "url": "https://sports.bwin.com/de/sports/fussball-4",
                "selectors": {
                    "match_row": ".grid-event-wrapper",
                    "teams": ".participants",
                    "odds": ".option-value",
                },
            },
        ]

        for bookmaker in bookmakers:
            try:
                self.logger.info(f"Scraping odds from {bookmaker['name']}")
                odds = await self._scrape_bookmaker_odds(bookmaker)
                all_odds.extend(odds)

                # Pause zwischen Buchmachern
                await asyncio.sleep(5)

            except Exception as e:
                self.logger.error(f"Failed to scrape {bookmaker['name']}: {e}")
                continue

        return all_odds

    async def _scrape_bookmaker_odds(self, bookmaker: dict) -> list[dict]:
        """Scrapt Odds von einem spezifischen Buchmacher"""
        odds_data = []

        try:
            # Robust navigieren und warten
            for attempt in range(3):
                try:
                    await self.goto_page(bookmaker["url"], wait_until="networkidle")
                    await self.page.wait_for_selector(
                        bookmaker["selectors"]["match_row"], timeout=45000
                    )
                    break
                except Exception as e:
                    self.logger.warning(f"{bookmaker['name']} wait attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(3)

            # Matches finden
            match_elements = await self.page.query_selector_all(bookmaker["selectors"]["match_row"])

            for match_elem in match_elements[:5]:  # Limit pro Buchmacher
                try:
                    odds_item = await self._extract_bookmaker_odds(match_elem, bookmaker)
                    if odds_item:
                        odds_data.append(odds_item)
                except Exception as e:
                    self.logger.debug(f"Failed to extract odds from {bookmaker['name']}: {e}")
                    continue

            self.logger.info(f"Extracted {len(odds_data)} odds from {bookmaker['name']}")
            return odds_data

        except Exception as e:
            self.logger.error(f"Bookmaker scraping failed for {bookmaker['name']}: {e}")
            return []

    async def _extract_bookmaker_odds(self, match_element, bookmaker: dict) -> Optional[dict]:
        """Extrahiert Odds von einem spezifischen Buchmacher"""
        try:
            # Teams extrahieren (bookmaker-spezifisch)
            if bookmaker["name"] == "bet365":
                teams = await match_element.query_selector_all(
                    ".gl-ParticipantFixtureDetails_TeamNames"
                )
                if len(teams) >= 2:
                    home_team = await teams[0].text_content()
                    away_team = await teams[1].text_content()
                else:
                    return None

            elif bookmaker["name"] == "bwin":
                participants = await match_element.query_selector(".participants")
                if participants:
                    teams_text = await participants.text_content()
                    team_parts = teams_text.split(" - ")
                    if len(team_parts) >= 2:
                        home_team = team_parts[0].strip()
                        away_team = team_parts[1].strip()
                    else:
                        return None
                else:
                    return None

            else:
                return None

            # Odds extrahieren
            odds_elements = await match_element.query_selector_all(bookmaker["selectors"]["odds"])

            odds_home = odds_draw = odds_away = None

            if len(odds_elements) >= 3:
                try:
                    odds_home_text = await odds_elements[0].text_content()
                    odds_draw_text = await odds_elements[1].text_content()
                    odds_away_text = await odds_elements[2].text_content()

                    odds_home = (
                        float(odds_home_text)
                        if odds_home_text.replace(".", "").replace(",", "").isdigit()
                        else None
                    )
                    odds_draw = (
                        float(odds_draw_text)
                        if odds_draw_text.replace(".", "").replace(",", "").isdigit()
                        else None
                    )
                    odds_away = (
                        float(odds_away_text)
                        if odds_away_text.replace(".", "").replace(",", "").isdigit()
                        else None
                    )

                except (ValueError, AttributeError):
                    pass

            return {
                "home_team": home_team.strip() if home_team else "",
                "away_team": away_team.strip() if away_team else "",
                "odds_home": odds_home,
                "odds_draw": odds_draw,
                "odds_away": odds_away,
                "bookmaker": bookmaker["name"],
                "scraped_at": datetime.now(),
            }

        except Exception as e:
            self.logger.debug(f"Failed to extract odds from {bookmaker['name']}: {e}")
            return None

    async def save_odds_to_database(self, odds_data: list[dict]):
        """Speichert Odds-Daten in die Datenbank"""
        if not odds_data:
            return

        try:
            # Transformiere Daten für DB-Schema
            db_data = []
            for odds in odds_data:
                # Erstelle eindeutige ID basierend auf Teams und Buchmacher
                team_hash_str = f"{odds['home_team']}_{odds['away_team']}"
                external_id = (
                    f"{odds['bookmaker']}_{hash(team_hash_str)}_{odds['scraped_at'].date()}"
                )

                db_data.append(
                    {
                        "external_id": external_id,
                        "bookmaker": odds["bookmaker"],
                        "home_team_name": odds["home_team"],
                        "away_team_name": odds["away_team"],
                        "odds_home": odds["odds_home"],
                        "odds_draw": odds["odds_draw"],
                        "odds_away": odds["odds_away"],
                        "market_type": "1X2",  # Standard Match Odds
                        "created_at": odds["scraped_at"],
                    }
                )

            # Bulk Insert in odds Tabelle
            await self.db_manager.bulk_insert(
                "odds",
                db_data,
                "ON CONFLICT (external_id) DO UPDATE SET "
                "odds_home = EXCLUDED.odds_home, "
                "odds_draw = EXCLUDED.odds_draw, "
                "odds_away = EXCLUDED.odds_away, "
                "updated_at = CURRENT_TIMESTAMP",
            )

            self.logger.info(f"Saved {len(db_data)} odds records to database")

        except Exception as e:
            self.logger.error(f"Failed to save odds to database: {e}")
            raise

    async def scrape_live_odds(self) -> list[dict]:
        """Scrapt Live-Odds für laufende Spiele"""
        live_odds = []

        try:
            # Navigiere zu Live-Bereich
            for attempt in range(3):
                try:
                    await self.goto_page(
                        f"{self.config.base_url}/inplay/1", wait_until="networkidle"
                    )
                    await self.page.wait_for_selector(".ipo-Fixture", timeout=45000)
                    break
                except Exception as e:
                    self.logger.warning(f"Live odds wait attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(3)

            # Live-Matches sammeln
            live_matches = await self.page.query_selector_all(".ipo-Fixture")

            for match in live_matches[:5]:  # Limit für Live-Matches
                try:
                    odds_item = await self._extract_live_odds(match)
                    if odds_item:
                        live_odds.append(odds_item)
                except Exception as e:
                    self.logger.warning(f"Failed to extract live odds: {e}")
                    continue

            self.logger.info(f"Scraped {len(live_odds)} live odds")
            return live_odds

        except Exception as e:
            self.logger.error(f"Live odds scraping failed: {e}")
            return []

    async def _extract_live_odds(self, match_element) -> Optional[dict]:
        """Extrahiert Live-Odds"""
        try:
            # Teams aus Live-Match
            teams = await match_element.query_selector_all(".ipo-Participant")
            if len(teams) < 2:
                return None

            home_team = await teams[0].text_content()
            away_team = await teams[1].text_content()

            # Live-Odds
            odds_elements = await match_element.query_selector_all(".ipo-ParticipantOddsOnly_Odds")

            odds_home = odds_draw = odds_away = None
            if len(odds_elements) >= 3:
                try:
                    odds_home = float(await odds_elements[0].text_content())
                    odds_draw = float(await odds_elements[1].text_content())
                    odds_away = float(await odds_elements[2].text_content())
                except (ValueError, AttributeError):
                    pass

            # Live-Status
            status_elem = await match_element.query_selector(".ipo-InPlayIndicator_Time")
            match_time = await status_elem.text_content() if status_elem else "LIVE"

            return {
                "home_team": home_team.strip(),
                "away_team": away_team.strip(),
                "odds_home": odds_home,
                "odds_draw": odds_draw,
                "odds_away": odds_away,
                "match_time": match_time,
                "is_live": True,
                "bookmaker": "bet365",
                "scraped_at": datetime.now(),
            }

        except Exception as e:
            self.logger.debug(f"Failed to extract live odds: {e}")
            return None
