from typing import Optional
"""
Betfair Odds Collector für die Sport Data Pipeline

Implementiert die Betfair Exchange API Integration für Wett-Quoten Sammlung.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from ...database.manager import DatabaseManager
from .base import DataCollector, RateLimiter
from src.domain.models import Team, Player, Match


@dataclass
class BetfairConfig:
    """Konfiguration für Betfair API"""

    app_key: str
    username: str
    password: str
    cert_file: str
    key_file: str
    base_url: str = "https://api.betfair.com/exchange"
    login_url: str = "https://identitysso.betfair.com/api/login"
    rate_limit: int = 5  # Requests pro Sekunde


class BetfairOddsCollector(DataCollector):
    """Datensammler für Betfair Exchange API"""

    def __init__(self, db_manager: DatabaseManager, config: BetfairConfig):
        super().__init__("betfair_odds", db_manager)
        self.config = config
        self.session_token = None  # type: Optional[str]
        self.session = None  # type: Optional[aiohttp.ClientSession]
        self.logger = logging.getLogger("betfair_collector")

    async def initialize(self):
        """Initialisiert die Betfair API Verbindung"""
        try:
            # SSL Context für Zertifikat-basierte Authentifizierung
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(self.config.cert_file, self.config.key_file)

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)

            # Login und Session Token erhalten
            await self._authenticate()
            self.logger.info("Betfair API initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Betfair API: {e}")
            raise

    async def cleanup(self):
        """Räumt Ressourcen auf"""
        if self.session:
            await self.session.close()
        self.session_token = None

    async def _authenticate(self):
        """Authentifiziert sich bei der Betfair API"""
        login_data = {"username": self.config.username, "password": self.config.password}

        headers = {
            "X-Application": self.config.app_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with self.session.post(
                self.config.login_url, data=login_data, headers=headers
            ) as response:

                if response.status == 200:
                    result = await response.json()

                    if result.get("status") == "SUCCESS":
                        self.session_token = result.get("token")
                        self.logger.info("Betfair authentication successful")
                    else:
                        raise Exception(f"Authentication failed: {result.get('error')}")
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")

        except Exception as e:
            self.logger.error(f"Betfair authentication failed: {e}")
            raise

    async def _make_api_request(self, method: str, params: dict = None) -> dict[str, Any]:
        """Macht einen API Request zur Betfair Exchange API"""
        if not self.session_token:
            await self._authenticate()

        url = f"{self.config.base_url}/betting/json-rpc/v1"

        payload = {
            "jsonrpc": "2.0",
            "method": f"SportsAPING/v1.0/{method}",
            "params": params or {},
            "id": 1,
        }

        headers = {
            "X-Application": self.config.app_key,
            "X-Authentication": self.session_token,
            "Content-Type": "application/json",
        }

        try:
            # Rate Limiting
            await self.rate_limiter.acquire()

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()

                    if "error" in result:
                        raise Exception(f"API Error: {result['error']}")

                    return result.get("result", {})
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")

        except Exception as e:
            self.logger.error(f"Betfair API request failed: {e}")
            raise

    async def collect_odds(self, match_id: str = None) -> list[dict]:
        """Sammelt Odds von Betfair für Fußball-Märkte"""
        try:
            # 1. Hole verfügbare Fußball-Events
            events = await self._get_football_events()

            odds_data = []
            for event in events[:10]:  # Limit für Demo
                try:
                    # 2. Hole Markt-Daten für jedes Event
                    markets = await self._get_event_markets(event["event"]["id"])

                    for market in markets:
                        if market["marketName"] == "Match Odds":  # 1X2 Markt
                            # 3. Hole aktuelle Odds
                            market_book = await self._get_market_book(market["marketId"])

                            odds_item = self._extract_odds_data(event, market, market_book)
                            if odds_item:
                                odds_data.append(odds_item)

                except Exception as e:
                    self.logger.warning(
                        f"Failed to collect odds for event {event.get('event', {}).get('id')}: {e}"
                    )
                    continue

            self.logger.info(f"Collected {len(odds_data)} odds from Betfair")
            return odds_data

        except Exception as e:
            self.logger.error(f"Betfair odds collection failed: {e}")
            return []

    async def _get_football_events(self) -> list[dict]:
        """Holt verfügbare Fußball-Events"""
        params = {
            "filter": {
                "eventTypeIds": ["1"],  # Fußball Event Type ID
                "marketCountries": ["GB", "DE", "ES", "IT", "FR"],  # Hauptligen
                "marketTypeCodes": ["MATCH_ODDS"],
                "inPlayOnly": False,
                "turnInPlayEnabled": True,
            },
            "maxResults": 50,
            "sort": "FIRST_TO_START",
        }

        result = await self._make_api_request("listEvents", params)
        return result

    async def _get_event_markets(self, event_id: str) -> list[dict]:
        """Holt verfügbare Märkte für ein Event"""
        params = {
            "filter": {
                "eventIds": [event_id],
                "marketTypeCodes": ["MATCH_ODDS", "OVER_UNDER_25", "BOTH_TEAMS_TO_SCORE"],
            }
        }

        result = await self._make_api_request("listMarketCatalogue", params)
        return result

    async def _get_market_book(self, market_id: str) -> dict:
        """Holt aktuelle Odds für einen Markt"""
        params = {
            "marketIds": [market_id],
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"],
                "exBestOffersOverrides": {
                    "bestPricesDepth": 3,
                    "rollupModel": "STAKE",
                    "rollupLimit": 20,
                },
            },
        }

        result = await self._make_api_request("listMarketBook", params)
        return result[0] if result else {}

    def _extract_odds_data(self, event: dict, market: dict, market_book: dict) -> Optional[dict]:
        """Extrahiert Odds-Daten aus Betfair Response"""
        try:
            event_info = event.get("event", {})

            # Team-Namen aus Event extrahieren
            home_team = (
                event_info.get("name", "").split(" v ")[0]
                if " v " in event_info.get("name", "")
                else ""
            )
            away_team = (
                event_info.get("name", "").split(" v ")[1]
                if " v " in event_info.get("name", "")
                else ""
            )

            if not home_team or not away_team:
                return None

            # Odds aus Market Book extrahieren
            runners = market_book.get("runners", [])
            odds_data = {
                "event_id": event_info.get("id"),
                "market_id": market.get("marketId"),
                "home_team": home_team.strip(),
                "away_team": away_team.strip(),
                "event_date": datetime.fromisoformat(
                    event_info.get("openDate", "").replace("Z", "+00:00")
                ),
                "market_name": market.get("marketName"),
                "odds_home": None,
                "odds_draw": None,
                "odds_away": None,
                "total_matched": market_book.get("totalMatched", 0),
                "source": "betfair",
                "scraped_at": datetime.now(),
            }

            # Odds zuordnen (basierend auf Runner-Namen)
            for runner in runners:
                runner_name = runner.get("runnerName", "").lower()
                best_prices = runner.get("ex", {}).get("availableToBack", [])

                if best_prices:
                    price = best_prices[0].get("price")

                    if home_team.lower() in runner_name or runner_name == "1":
                        odds_data["odds_home"] = price
                    elif away_team.lower() in runner_name or runner_name == "2":
                        odds_data["odds_away"] = price
                    elif "draw" in runner_name or runner_name == "x":
                        odds_data["odds_draw"] = price

            return odds_data

        except Exception as e:
            self.logger.debug(f"Failed to extract odds data: {e}")
            return None

    # Implementiere abstrakte Methoden (nicht verwendet für Odds Collector)
    async def collect_teams(self, league_id: str = None) -> list[Team]:
        """Betfair sammelt keine Team-Daten"""
        return []

    async def collect_players(self, team_id: str = None) -> list[Player]:
        """Betfair sammelt keine Spieler-Daten"""
        return []

    async def collect_matches(self, league_id: str, season: str) -> list[Match]:
        """Betfair sammelt keine Match-Daten (nur Odds)"""
        return []

    async def save_odds_to_database(self, odds_data: list[dict]):
        """Speichert Odds-Daten in die Datenbank"""
        if not odds_data:
            return

        try:
            # Transformiere Daten für DB-Schema
            db_data = []
            for odds in odds_data:
                db_data.append(
                    {
                        "external_id": odds["event_id"],
                        "bookmaker": "betfair",
                        "market_type": odds["market_name"],
                        "odds_home": odds["odds_home"],
                        "odds_draw": odds["odds_draw"],
                        "odds_away": odds["odds_away"],
                        "total_volume": odds["total_matched"],
                        "created_at": odds["scraped_at"],
                    }
                )

            # Bulk Insert in odds Tabelle
            await self.db_manager.bulk_insert(
                "odds",
                db_data,
                "ON CONFLICT (external_id, bookmaker) DO UPDATE SET "
                "odds_home = EXCLUDED.odds_home, "
                "odds_draw = EXCLUDED.odds_draw, "
                "odds_away = EXCLUDED.odds_away, "
                "updated_at = CURRENT_TIMESTAMP",
            )

            self.logger.info(f"Saved {len(db_data)} odds records to database")

        except Exception as e:
            self.logger.error(f"Failed to save odds to database: {e}")
            raise
