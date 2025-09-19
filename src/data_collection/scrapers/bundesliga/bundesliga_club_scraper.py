"""
Unified Bundesliga Club / Squad / Player Scraper
================================================

Merged functionality from:
 - root-level `bundesliga_club_scraper.py` (enhanced multi-stage clubs -> squads -> players)
 - folder-level `bundesliga/club_scraper.py` (robust overview & detail fallbacks, LD/NUXT JSON parsing,
   optional Playwright rendering, JSON hydration parsing, profile/stat extraction helpers)

Goals:
 - Single canonical implementation located under `scrapers/bundesliga/`
 - Preserve existing public class name `BundesligaClubScraper` so external imports keep working after
   updating their import path (compat shim can be left temporarily in old location if needed)
 - Add robust fallback strategies without losing Pydantic data models for downstream usage.

Import Path Migration:
   OLD: from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper
   NEW: from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper

Temporary backwards compatibility can be achieved by leaving a thin stub in the old file importing this class
until all call sites are updated (handled in a later step in this refactor process).
"""

from __future__ import annotations

import os
import re
import json
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Any, Optional, List, Dict, TypedDict, Protocol, runtime_checkable, Awaitable, TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
try:
    from playwright.async_api import async_playwright  # optional
except ImportError:  # pragma: no cover - playwright optional
    async_playwright = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from playwright.async_api import Playwright, Browser, Page

from pydantic import BaseModel, HttpUrl, field_validator

from ..base import BaseScraper, ScrapingConfig
from ....domain.models import Footedness  # adjusted relative import path

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# 1. CONFIGURATION & DATA MODELS
# =============================================================================

@dataclass
class BundesligaClubScraperConfig(ScrapingConfig):
    base_url: str = "https://www.bundesliga.com"
    selectors: dict[str, str] = field(default_factory=lambda: {
        'club_links': 'a[href*="/clubs/"], a[href*="/vereine/"]',
        'player_links': 'a[href*="/spieler/"]',
        'squad_container': '.squad-overview, .team-squad, .player-list',
        'player_stats': '.player-stats, .statistics, .career-stats'
    })
    headers: dict[str, str] = field(default_factory=dict)
    delay_range: tuple = (1, 3)
    max_retries: int = 3
    timeout: int = 30
    use_proxy: bool = False
    proxy_list: Optional[list[str]] = None
    anti_detection: bool = True
    screenshot_on_error: bool = True


class PlayerCareerStats(BaseModel):
    season: str
    team: Optional[str] = None
    league: Optional[str] = None
    appearances: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    minutes_played: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    source_url: Optional[str] = None


class PlayerSeasonStats(BaseModel):
    appearances: Optional[int] = None
    starts: Optional[int] = None
    minutes_played: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    clean_sheets: Optional[int] = None
    saves: Optional[int] = None
    pass_accuracy: Optional[float] = None
    shots_on_target: Optional[int] = None
    tackles: Optional[int] = None
    interceptions: Optional[int] = None
    aerial_duels_won: Optional[int] = None
    source_url: Optional[str] = None


class EnhancedPlayer(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    nationality: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: Optional[Footedness] = None
    photo_url: Optional[HttpUrl] = None
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    market_value: Optional[str] = None
    contract_until: Optional[date] = None
    previous_clubs: Optional[List[str]] = None
    current_season_stats: Optional[PlayerSeasonStats] = None
    career_stats: Optional[List[PlayerCareerStats]] = None
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None

    @field_validator('birth_date', 'contract_until', mode='before')
    @classmethod
    def parse_date(cls, v):  # type: ignore[override]
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
            except Exception:
                return None
        return v


class EnhancedClub(BaseModel):
    name: str
    short_name: Optional[str] = None
    city: Optional[str] = None
    founded_year: Optional[int] = None
    logo_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    stadium: Optional[str] = None
    stadium_capacity: Optional[int] = None
    coach: Optional[str] = None
    colors: Optional[Dict[str, str]] = None
    source_url: Optional[str] = None
    squad_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None


class ClubParseResult(TypedDict, total=False):
    """Lightweight parsed club detail structure returned by parse_club_html.

    Mirrors a subset of EnhancedClub fields but keeps them primitive for
    downstream lenient usage (e.g. directly serialisable / JSON dump without
    Pydantic instantiation). Only 'name' is required at runtime; others are
    optional and populated if detected either from static DOM or hydration
    JSON fallbacks.
    """
    name: str
    stadium: Optional[str]
    founded_year: Optional[int]
    city: Optional[str]
    coach: Optional[str]
    stadium_capacity: Optional[int]
    logo_url: Optional[str]
    source_url: str


@runtime_checkable
class DatabaseManagerProtocol(Protocol):  # pragma: no cover - typing only
    async def bulk_insert(self, table: str, rows: List[Dict[str, Any]], on_conflict: str) -> Any: ...


# =============================================================================
# 2. MAIN SCRAPER CLASS
# =============================================================================

class BundesligaClubScraper(BaseScraper):
    """Unified Bundesliga scraper for clubs, squads, and players.

    Combines robust overview/detail fallback logic (JSON hydration, LD-JSON, optional Playwright)
    with multi-stage squad & player scraping from the enhanced version.
    """

    name = "bundesliga_club"
    OVERVIEW_URL_DE = "https://www.bundesliga.com/de/bundesliga/clubs"
    OVERVIEW_URL_EN = "https://www.bundesliga.com/en/bundesliga/clubs"

    # Instance attribute type declarations (for static type checkers)
    _pw: Optional["Playwright"]
    _pw_browser: Optional["Browser"]
    _pw_page: Optional["Page"]

    def __init__(self, db_manager: DatabaseManagerProtocol, *, use_playwright: Optional[bool] = None, save_html: bool = False):
        config = BundesligaClubScraperConfig()
        super().__init__(config, db_manager, self.name)
        # Feature toggles
        env_pw = os.getenv("BUNDESLIGA_USE_PLAYWRIGHT", "0") in ("1", "true", "True")
        self._use_playwright = (use_playwright if use_playwright is not None else env_pw) and async_playwright is not None
        self.save_html = save_html or bool(os.getenv("BUNDESLIGA_SCRAPER_SAVE_HTML"))
        # Playwright runtime objects (assigned lazily in _ensure_playwright)
        self._pw = None
        self._pw_browser = None
        self._pw_page = None

    # -------------------- Public Orchestrator --------------------
    async def scrape_data(self) -> dict[str, Any]:  # type: ignore[override]
        self.logger.info("Starting Bundesliga club -> squad -> player scrape")
        clubs = await self.scrape_clubs()
        all_squads: dict[str, list[str]] = {}
        for club in clubs:
            if not club.squad_url:
                continue
            try:
                squad_links = await self.scrape_squad(club.squad_url, club.name)
                all_squads[club.name] = squad_links
            except Exception as e:
                self.logger.warning(f"Squad scrape failed for {club.name}: {e}")
            await self.anti_detection.random_delay(self.config.delay_range)

        players_by_club: dict[str, list[EnhancedPlayer]] = {}
        total_links = sum(len(v) for v in all_squads.values())
        processed = 0
        for club_name, links in all_squads.items():
            club_players: list[EnhancedPlayer] = []
            for link in links:
                try:
                    player = await self.scrape_player(link)
                    if player:
                        club_players.append(player)
                except Exception as e:
                    self.logger.debug(f"Player scrape failed {link}: {e}")
                processed += 1
                if processed % 10 == 0:
                    self.logger.info("Players scraped %d/%d", processed, total_links)
                await self.anti_detection.random_delay(self.config.delay_range)
            players_by_club[club_name] = club_players

        return {
            'clubs': clubs,
            'squads': all_squads,
            'players': players_by_club,
            'total_clubs': len(clubs),
            'total_players': sum(len(v) for v in players_by_club.values()),
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }

    async def cleanup(self):
        await super().cleanup()
        await self._close_playwright()

    # -------------------- Stage 1: Clubs --------------------
    async def scrape_clubs(self) -> List[EnhancedClub]:
        # Try DE first (contains richer localized info sometimes)
        html = await self.fetch_page(self.OVERVIEW_URL_DE)
        soup = self.parse_html(html)
        overview_items = self._extract_clubs_overview(soup, raw_html=html)
        if not overview_items:
            # fallback: English page
            try:
                html_en = await self.fetch_page(self.OVERVIEW_URL_EN)
                soup_en = self.parse_html(html_en)
                overview_items = self._extract_clubs_overview(soup_en, raw_html=html_en)
            except Exception:
                pass

        clubs: list[EnhancedClub] = []
        for item in overview_items:
            url = item.get('url')
            if not url:
                continue
            try:
                detail_html = await self.fetch_page(url)
                soup_detail = self.parse_html(detail_html)
                club_data = self._extract_club_data(soup_detail, url)
                if not club_data.get('name'):
                    continue
                squad_url = self._find_squad_url(soup_detail, url)
                club = EnhancedClub(
                    name=club_data['name'],
                    short_name=club_data.get('short_name'),
                    city=club_data.get('city'),
                    founded_year=club_data.get('founded_year'),
                    logo_url=club_data.get('logo_url'),
                    website=club_data.get('website') or item.get('website'),
                    stadium=club_data.get('stadium') or item.get('stadium'),
                    stadium_capacity=club_data.get('stadium_capacity'),
                    coach=club_data.get('coach'),
                    colors=club_data.get('colors'),
                    source_url=url,
                    squad_url=squad_url,
                    scraped_at=datetime.now(timezone.utc),
                    external_ids={'bundesliga_url': url}
                )
                clubs.append(club)
            except Exception as e:
                self.logger.debug(f"Club detail failed {url}: {e}")
            await self.anti_detection.random_delay(self.config.delay_range)
        return clubs

    # -------------------- Stage 2: Squad (player link extraction) --------------------
    async def scrape_squad(self, squad_url: str, club_name: str) -> List[str]:
        html = await self.fetch_page(squad_url)
        soup = self.parse_html(html)
        return self._extract_player_links(soup, squad_url)

    # -------------------- Stage 3: Player --------------------
    async def scrape_player(self, player_url: str) -> Optional[EnhancedPlayer]:
        html = await self.fetch_page(player_url)
        soup = self.parse_html(html)
        return self._parse_player_data(soup, player_url)

    # =============================================================================
    # Overview & Detail Fallback Logic (ported / simplified)
    # =============================================================================
    def _extract_clubs_overview(self, soup: BeautifulSoup, raw_html: str) -> List[Dict[str, Any]]:
        clubs: list[dict] = []
        tried_selectors = [
            '.club-card', '[data-component="ClubCard"]', 'a[href*="/en/bundesliga/clubs/"]', 'a[href*="/de/bundesliga/clubs/"]'
        ]
        for sel in tried_selectors:
            els = soup.select(sel)
            if not els:
                continue
            for el in els:
                url = self._extract_detail_url(el)
                if not url:
                    continue
                name = self._extract_name(el)
                if not name and getattr(el, 'name', None) == 'a':
                    t = el.get_text(strip=True)
                    if t and len(t) < 70 and '/' not in t:
                        name = t
                if not name:
                    continue
                stadium = self._extract_stadium(el)
                clubs.append({'name': name, 'stadium': stadium, 'url': url})
            if clubs:
                break
        if clubs:
            return self._dedupe(clubs)
        self.logger.warning("Static overview selectors empty – trying hydration JSON fallback")
        return self._json_overview_fallback(raw_html)

    def _json_overview_fallback(self, html: str) -> List[Dict[str, Any]]:
        pattern = re.compile(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*</script>', re.DOTALL)
        m = pattern.search(html)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except Exception:
            return []
        found: list[dict] = []

        def walk(obj):
            if isinstance(obj, dict):
                if {'slug', 'name'} <= obj.keys():
                    slug = obj.get('slug')
                    if isinstance(slug, str):
                        if slug.startswith(('/en/bundesliga/clubs/', '/de/bundesliga/clubs/')):
                            url = f"https://www.bundesliga.com{slug}" if slug.startswith('/') else slug
                        else:
                            url = None
                        if url:
                            found.append({'name': str(obj.get('name', '')).strip(), 'stadium': str(obj.get('stadium', '') or '').strip(), 'url': url})
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for it in obj:
                    walk(it)
        walk(data)
        deduped = self._dedupe(found)
        if deduped:
            self.logger.info("JSON fallback extracted %d clubs", len(deduped))
        return deduped

    # =============================================================================
    # Club detail parsing (kept simple; advanced profile extraction could be re-added later)
    # =============================================================================
    def _extract_club_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        data['name'] = (
            self._get_text_by_selector(soup, 'h1.club-name, h1, .club-header h1') or
            self._get_meta_content(soup, 'og:title') or
            self._extract_from_title(soup)
        )
        data['stadium'] = self._find_labeled_value(soup, ['Stadium', 'Stadion', 'Venue'])
        data['coach'] = self._find_labeled_value(soup, ['Coach', 'Trainer', 'Head Coach'])
        founded_text = self._find_labeled_value(soup, ['Founded', 'Gegründet', 'Est.', 'Since'])
        if founded_text:
            m = re.search(r'\b(19|20)\d{2}\b', founded_text)
            if m:
                try:
                    data['founded_year'] = int(m.group())
                except ValueError:
                    pass
        data['city'] = self._find_labeled_value(soup, ['City', 'Stadt', 'Location', 'Ort'])
        logo = soup.find('img', {'alt': re.compile(r'logo|emblem', re.I)}) or soup.find('img', class_=re.compile(r'logo|emblem'))
        if logo and logo.get('src'):
            data['logo_url'] = urljoin(url, logo['src'])
        capacity_text = self._find_labeled_value(soup, ['Capacity', 'Kapazität', 'Seats'])
        if capacity_text:
            m2 = re.search(r'(\d{1,3}(?:[,\.]\d{3})*)', capacity_text.replace('.', '').replace(',', ''))
            if m2:
                try:
                    data['stadium_capacity'] = int(m2.group().replace(',', '').replace('.', ''))
                except ValueError:
                    pass
        return data
    # ------------------------------------------------------------------
    # Public helper: parse raw club HTML into a normalized dict (successor to legacy _parse_detail)
    # ------------------------------------------------------------------
    def parse_club_html(self, html: str, url: str) -> Optional[ClubParseResult]:  # pragma: no cover - thin wrapper
        """Parse a single club page's HTML into a lightweight dict.

        Returns None if the club name cannot be detected.
        Keys:
          name, stadium, founded_year, city, coach, stadium_capacity, logo_url, source_url
        """
        try:
            soup = self.parse_html(html)
            data = self._extract_club_data(soup, url)
            if not data.get('name'):
                return None
            # Hydration JSON fallback for founded year / capacity if still missing
            if ('founded_year' not in data or data.get('founded_year') is None) or ('stadium_capacity' not in data or data.get('stadium_capacity') is None):
                raw_json = None
                m = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
                if m:
                    raw_json = m.group(1)
                else:
                    marker = 'window.__NUXT__'
                    idx = html.find(marker)
                    if idx != -1:
                        eq_idx = html.find('=', idx)
                        if eq_idx != -1:
                            brace_start = html.find('{', eq_idx)
                            if brace_start != -1:
                                depth = 0
                                for j in range(brace_start, len(html)):
                                    ch = html[j]
                                    if ch == '{':
                                        depth += 1
                                    elif ch == '}':
                                        depth -= 1
                                        if depth == 0:
                                            raw_json = html[brace_start:j+1]
                                            break
                if raw_json:
                    try:
                        nuxt = json.loads(raw_json)
                        def walk(o):
                            if isinstance(o, dict):
                                # descend first to allow nested 'club'
                                for v in o.values():
                                    walk(v)
                                if 'founded' in o and not data.get('founded_year'):
                                    fv = o.get('founded')
                                    if isinstance(fv, (str, int)) and re.match(r'^(19|20)\d{2}$', str(fv)):
                                        try:
                                            data['founded_year'] = int(fv)
                                        except ValueError:
                                            pass
                                if 'stadium' in o and isinstance(o['stadium'], dict) and not data.get('stadium_capacity'):
                                    cap = o['stadium'].get('capacity')
                                    if isinstance(cap, str):
                                        cap_num = re.sub(r'[^0-9]', '', cap)
                                        if cap_num.isdigit():
                                            try:
                                                data['stadium_capacity'] = int(cap_num)
                                            except ValueError:
                                                pass
                            elif isinstance(o, list):
                                for it in o:
                                    walk(it)
                        walk(nuxt)
                    except Exception:
                        pass
            data['source_url'] = url
            return data
        except Exception:
            return None

    def _find_squad_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for a in soup.find_all('a', href=True):
            href_l = a['href'].lower()
            txt = a.get_text().lower()
            if any(t in href_l or t in txt for t in ['squad', 'kader', 'team', 'mannschaft', 'spieler']):
                return urljoin(base_url, a['href'])
        if '/clubs/' in base_url:
            return base_url.rstrip('/') + '/squad'
        return None

    # =============================================================================
    # Player parsing
    # =============================================================================
    def _extract_player_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links: set[str] = set()
        page_text = soup.get_text().lower()
        if not any(i in page_text for i in ['squad', 'team', 'kader', 'mannschaft', 'spieler']):
            return []
        # Restrict to structural elements likely representing squad rows to reduce noise
        for container in soup.find_all(['tr', 'article']):
            c_text = container.get_text().lower()
            if not any(ind in c_text for ind in ['position', 'pos', 'torwart', 'verteidiger', 'mittelfeld', 'stürmer', 'goalkeeper', 'defender', 'midfielder', 'forward']):
                continue
            for a in container.find_all('a', href=True):
                href = a['href']
                if re.search(r'/de/bundesliga/spieler/[a-z0-9\-]+', href):
                    link_text = a.get_text(strip=True)
                    if link_text and len(link_text.split()) >= 2:
                        links.add(urljoin(base_url, href))
        if not links:
            for a in soup.find_all('a', href=re.compile(r'/de/bundesliga/spieler/[a-z0-9\-]+')):
                # Only accept links within tables (squad listings)
                if not a.find_parent('table'):
                    continue
                ctx = a.find_parent('tr').get_text(' ', strip=True).lower() if a.find_parent('tr') else ''
                if any(ind in ctx for ind in ['gk', 'torwart', 'fw', 'mf', 'df', 'verteidiger', 'mittelfeld', 'stürmer']):
                    links.add(urljoin(base_url, a['href']))
        # Final very permissive fallback for unit-test synthetic HTML lacking context labels
        if not links:
            for a in soup.find_all('a', href=re.compile(r'/de/bundesliga/spieler/[a-z0-9\-]+')):
                link_text = a.get_text(strip=True)
                # Exclude navigation/footer sections explicitly
                if a.find_parent(['nav', 'footer']):
                    continue
                if link_text and len(link_text.split()) >= 2 and a.find_parent('table'):
                    links.add(urljoin(base_url, a['href']))
        result = sorted(links)
        if len(result) > 100:
            result = result[:50]
        return result

    def _parse_player_data(self, soup: BeautifulSoup, url: str) -> Optional[EnhancedPlayer]:
        pdata = self._extract_player_basic_info(soup)
        if not (pdata.get('first_name') or pdata.get('last_name')):
            return None
        season_stats = self._extract_player_season_stats(soup)
        career_stats = self._extract_player_career_stats(soup)
        return EnhancedPlayer(
            first_name=pdata.get('first_name'), last_name=pdata.get('last_name'), birth_date=pdata.get('birth_date'),
            birth_place=pdata.get('birth_place'), nationality=pdata.get('nationality'), height_cm=pdata.get('height_cm'),
            weight_kg=pdata.get('weight_kg'), preferred_foot=pdata.get('preferred_foot'), photo_url=pdata.get('photo_url'),
            position=pdata.get('position'), shirt_number=pdata.get('shirt_number'), market_value=pdata.get('market_value'),
            contract_until=pdata.get('contract_until'), previous_clubs=pdata.get('previous_clubs'),
            current_season_stats=season_stats, career_stats=career_stats, source_url=url,
            scraped_at=datetime.now(timezone.utc), external_ids={'bundesliga_url': url}
        )

    def _extract_player_basic_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        name_text = (
            self._get_text_by_selector(soup, 'h1.player-name, h1, .player-header h1') or
            self._get_meta_content(soup, 'og:title') or ''
        )
        if name_text:
            parts = name_text.strip().split()
            if parts:
                data['first_name'] = parts[0]
                if len(parts) > 1:
                    data['last_name'] = ' '.join(parts[1:])
        data['position'] = self._find_labeled_value(soup, ['Position', 'Pos.'])
        number_text = self._find_labeled_value(soup, ['Number', 'Nummer', 'Nr.', '#'])
        if number_text:
            m = re.search(r'\d+', number_text)
            if m:
                try:
                    data['shirt_number'] = int(m.group())
                except ValueError:
                    pass
        birth_text = self._find_labeled_value(soup, ['Born', 'Birth', 'Geboren', 'Date of Birth'])
        if birth_text:
            data['birth_date'] = self._parse_date_string(birth_text)
        data['birth_place'] = self._find_labeled_value(soup, ['Birthplace', 'Geburtsort', 'Place of Birth'])
        data['nationality'] = self._find_labeled_value(soup, ['Nationality', 'Nationalität', 'Country'])
        height_text = self._find_labeled_value(soup, ['Height', 'Größe', 'Size'])
        if height_text and (m := re.search(r'(\d+)\s*cm', height_text)):
            try:
                data['height_cm'] = int(m.group(1))
            except ValueError:
                pass
        weight_text = self._find_labeled_value(soup, ['Weight', 'Gewicht'])
        if weight_text and (m := re.search(r'(\d+)\s*kg', weight_text)):
            try:
                data['weight_kg'] = int(m.group(1))
            except ValueError:
                pass
        foot_text = self._find_labeled_value(soup, ['Foot', 'Fuß', 'Preferred Foot'])
        if foot_text and foot_text.lower() in ['left', 'right', 'both']:
            try:
                data['preferred_foot'] = Footedness(foot_text.lower())
            except Exception:
                pass
        data['market_value'] = self._find_labeled_value(soup, ['Market Value', 'Marktwert', 'Value'])
        contract_text = self._find_labeled_value(soup, ['Contract', 'Vertrag', 'Contract until'])
        if contract_text:
            data['contract_until'] = self._parse_date_string(contract_text)
        photo = soup.find('img', {'alt': re.compile(r'player|spieler', re.I)}) or soup.find('img', class_=re.compile(r'player|portrait'))
        if photo and photo.get('src'):
            src = photo['src']
            if src.startswith('/'):
                data['photo_url'] = f"https://www.bundesliga.com{src}"
            else:
                data['photo_url'] = src
        return data

    def _extract_player_season_stats(self, soup: BeautifulSoup) -> Optional[PlayerSeasonStats]:
        stats: Dict[str, Any] = {}
        stats_section = soup.find(['section', 'div'], class_=re.compile(r'stats|statistics|season'))
        if not stats_section:
            return None
        mapping = {
            'appearances': ['Appearances', 'Games', 'Matches', 'Spiele', 'Einsätze'],
            'goals': ['Goals', 'Tore'],
            'assists': ['Assists', 'Vorlagen'],
            'minutes_played': ['Minutes', 'Minuten'],
            'yellow_cards': ['Yellow Cards', 'Gelbe Karten', 'YC'],
            'red_cards': ['Red Cards', 'Rote Karten', 'RC'],
        }
        for key, labels in mapping.items():
            txt = self._find_labeled_value(stats_section, labels)
            if txt and (m := re.search(r'\d+', txt.replace(',', ''))):
                try:
                    stats[key] = int(m.group())
                except ValueError:
                    pass
        return PlayerSeasonStats(**stats) if stats else None

    def _extract_player_career_stats(self, soup: BeautifulSoup) -> List[PlayerCareerStats]:
        out: List[PlayerCareerStats] = []
        table = soup.find('table', class_=re.compile(r'career|history|statistik'))
        if not table:
            return out
        rows = table.find_all('tr')[1:]
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue
            try:
                pcs = PlayerCareerStats(
                    season=cells[0].get_text(strip=True),
                    team=cells[1].get_text(strip=True) if len(cells) > 1 else None,
                    league=cells[2].get_text(strip=True) if len(cells) > 2 else None,
                )
                for idx, cell in enumerate(cells[3:], 3):
                    txt = cell.get_text(strip=True)
                    if txt.isdigit():
                        val = int(txt)
                        if idx == 3:
                            pcs.appearances = val
                        elif idx == 4:
                            pcs.goals = val
                        elif idx == 5:
                            pcs.assists = val
                out.append(pcs)
            except Exception:
                continue
        return out

    # =============================================================================
    # Utility helpers (copied / adapted)
    # =============================================================================
    def _get_text_by_selector(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    def _get_meta_content(self, soup: BeautifulSoup, prop: str) -> Optional[str]:
        meta = soup.find('meta', {'property': prop}) or soup.find('meta', {'name': prop})
        return meta.get('content') if meta else None

    def _extract_from_title(self, soup: BeautifulSoup) -> Optional[str]:
        if not soup.title:
            return None
        txt = soup.title.get_text(strip=True)
        for suf in [' - Bundesliga', ' | Bundesliga', ' - Official Website']:
            txt = txt.replace(suf, '')
        return txt.strip() or None

    def _find_labeled_value(self, soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
        for label in labels:
            dt = soup.find('dt', string=re.compile(rf'^{re.escape(label)}\s*:?', re.I))
            if dt:
                dd = dt.find_next_sibling('dd')
                if dd:
                    return dd.get_text(strip=True)
        text = soup.get_text()
        for label in labels:
            pattern = rf'{re.escape(label)}\s*:\s*([^\n\r]+)'
            m = re.search(pattern, text, re.I)
            if m:
                value = m.group(1).strip()
                for delim in [' |', '©', 'Watch', 'Privacy']:
                    if delim in value:
                        value = value.split(delim)[0].strip()
                return value
        return None

    # ------------------------------------------------------------------
    # Additional helper methods ported / reconstructed from legacy scraper
    # to satisfy direct unit test access and internal calls.
    # ------------------------------------------------------------------
    def _extract_club_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:  # pragma: no cover - simple utility exercised by tests
        """Extract absolute club detail URLs from an overview page.

        Unit tests provide simplified HTML with a wrapping container and <a> tags.
        We accept both /de/ and /en/ paths and normalise to absolute URLs.
        """
        links: list[str] = []
        for a in soup.select('a[href*="/bundesliga/clubs/"]'):
            href = a.get('href')
            if not href:
                continue
            if not href.startswith('http'):
                # ensure leading slash for urljoin behaviour
                if not href.startswith('/'):
                    href = '/' + href
                abs_url = urljoin(self.config.base_url, href)
            else:
                abs_url = href
            # basic sanity filter
            if '/bundesliga/clubs/' in abs_url:
                links.append(abs_url.rstrip('/'))
        # de-dupe while preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for u in links:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered

    def _extract_detail_url(self, el) -> Optional[str]:  # pragma: no cover - deterministic
        # Accept element itself if anchor, else find first anchor descendant
        anchor = el if getattr(el, 'name', None) == 'a' else el.find('a', href=True)
        if not anchor:
            return None
        href = anchor.get('href')
        if not href:
            return None
        # normalise
        if href.startswith('javascript:'):
            return None
        if not href.startswith('http'):
            if not href.startswith('/'):
                href = '/' + href
            href = urljoin(self.config.base_url, href)
        # constrain to club detail pages
        if '/bundesliga/clubs/' not in href:
            return None
        return href.rstrip('/')

    def _extract_name(self, el) -> Optional[str]:  # pragma: no cover
        # Try common class / heading patterns
        for sel in ['.club-name', 'h3', 'h2', 'h4']:
            found = el.select_one(sel) if hasattr(el, 'select_one') else None
            if found and (txt := found.get_text(strip=True)):
                return txt
        # Fallback: direct text
        if getattr(el, 'name', None) == 'a':
            txt = el.get_text(strip=True)
            return txt if txt else None
        # Any child anchor
        a = el.find('a') if hasattr(el, 'find') else None
        if a and (txt := a.get_text(strip=True)):
            return txt
        return None

    def _extract_stadium(self, el) -> Optional[str]:  # pragma: no cover
        text = el.get_text(" ", strip=True) if hasattr(el, 'get_text') else ''
        m = re.search(r'(Stadium|Stadion)[:\s]+([^|\n\r]+)', text, re.I)
        if m:
            candidate = m.group(2).strip()
            # strip trailing decorations
            for delim in [' |', ' - ', ' • ']:
                if delim in candidate:
                    candidate = candidate.split(delim)[0].strip()
            return candidate
        return None

    def _dedupe(self, items: List[dict]) -> List[dict]:  # pragma: no cover
        seen: set[str] = set()
        out: list[dict] = []
        for it in items:
            url = it.get('url')
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(it)
        return out

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        if not date_str:
            return None
        patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',
        ]
        months = {m.lower(): i for i, m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}
        for p in patterns:
            m = re.search(p, date_str)
            if not m:
                continue
            try:
                if p.startswith('('):  # dd.mm.yyyy or yyyy-mm-dd
                    parts = m.groups()
                    if p == patterns[0]:
                        d, mo, y = parts
                        return date(int(y), int(mo), int(d))
                    elif p == patterns[1]:
                        y, mo, d = parts
                        return date(int(y), int(mo), int(d))
                else:  # dd Month YYYY
                    d, mon, y = m.groups()
                    mi = months.get(mon.lower())
                    if mi:
                        return date(int(y), mi, int(d))
            except Exception:
                continue
        return None

    # -------------------- Playwright support --------------------
    async def _ensure_playwright(self):
        if not self._use_playwright or not async_playwright:
            return False
        if self._pw_page is not None:
            return True
        try:  # pragma: no cover (runtime only)
            self._pw = await async_playwright().start()
            self._pw_browser = await self._pw.chromium.launch(headless=True)
            self._pw_page = await self._pw_browser.new_page()
            return True
        except Exception as e:
            self.logger.warning(f"Playwright init failed: {e}")
            return False

    async def _close_playwright(self):  # pragma: no cover
        try:
            if self._pw_page:
                await self._pw_page.close()
            if self._pw_browser:
                await self._pw_browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        finally:
            self._pw = self._pw_browser = self._pw_page = None


# =============================================================================
# 5. Simple CLI test entry
# =============================================================================
async def _test():  # pragma: no cover
    from src.database.manager import DatabaseManager
    db = DatabaseManager()
    scraper = BundesligaClubScraper(db_manager=db)
    await scraper.initialize()
    try:
        data = await scraper.scrape_data()
        print(f"Scraped clubs={len(data['clubs'])} players={data['total_players']}")
    finally:
        await scraper.cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys
    if sys.platform.startswith('win') and hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_test())
