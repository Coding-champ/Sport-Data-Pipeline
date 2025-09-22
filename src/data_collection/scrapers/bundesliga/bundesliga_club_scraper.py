"""
Unified Bundesliga Club / Squad / Player Scraper
================================================

Goals:
 - Single canonical implementation located under `scrapers/bundesliga/`
 - Preserve existing public class name `BundesligaClubScraper` so external imports keep working after
   updating their import path (compat shim can be left temporarily in old location if needed)
 - Add robust fallback strategies without losing Pydantic data models for downstream usage.
 - robust overview & detail fallbacks, LD/NUXT JSON parsing, optional Playwright rendering, JSON hydration parsing, profile/stat extraction helpers
"""

from __future__ import annotations

import os
import re
import json
import asyncio
import logging
import unicodedata
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
from ....common.term_mapper import (
    map_position,
    map_nationality,
    map_footedness,
)  # centralised synonym -> canonical mapping (positions, nationalities, footedness)
from ....common.lexicon_config import get_lexicon_config

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
    headers: dict[str, str] = field(default_factory=lambda: {
        # Emulate a modern desktop browser to encourage server to embed more SSR/hydration data
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache'
    })
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
    goals: Optional[int] = None
    assists: Optional[int] = None
    penalties_taken: Optional[int] = None
    penalties_scored: Optional[int] = None
    woodwork: Optional[int] = None  # Pfosten / Latte
    shots_on_target: Optional[int] = None
    crosses: Optional[int] = None
    fouls_committed: Optional[int] = None
    yellow_cards: Optional[int] = None
    duels_won: Optional[int] = None
    aerial_duels_won: Optional[int] = None
    possession_phases: Optional[int] = None
    sprints: Optional[int] = None
    intensive_runs: Optional[int] = None
    distance_km: Optional[float] = None
    top_speed_kmh: Optional[float] = None
    clean_sheets: Optional[int] = None
    saves: Optional[int] = None
    own_goals: Optional[int] = None
    source_url: Optional[str] = None


class EnhancedPlayer(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    nationality: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    photo_url: Optional[HttpUrl] = None
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    current_season_stats: Optional[PlayerSeasonStats] = None
    career_stats: Optional[List[PlayerCareerStats]] = None
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None

    @field_validator('birth_date', mode='before')
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
    # Newly added enriched fields parsed from club detail page fact table / header
    official_name: Optional[str] = None
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    stadium_image_url: Optional[HttpUrl] = None
    map_url: Optional[HttpUrl] = None
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
    
    
class BundesligaClubScraper(BaseScraper):
    """Unified scraper orchestrating club, squad, and player enrichment for Bundesliga.

    This class was accidentally partially removed in a prior patch; reintroducing explicit
    class header and __init__ so that downstream imports and unit tests function again.

    NOTE: Player positions are now normalised through `map_position` (see `src/common/term_mapper.py`).
          The scraper stores broad canonical codes (GK/DF/MF/FW) to simplify downstream analytics.
    """

    OVERVIEW_URL_DE = "https://www.bundesliga.com/de/bundesliga/clubs"
    OVERVIEW_URL_EN = "https://www.bundesliga.com/en/bundesliga/clubs"

    def __init__(self, config: Optional[BundesligaClubScraperConfig] = None, *args, use_playwright: Optional[bool] = None, **kwargs):
        """Initialize BundesligaClubScraper.

        Accepts additional keyword arguments (e.g. db_manager, save_html) for backward
        compatibility with previous constructor signatures used in tests. Unknown kwargs
        are stored on the instance to avoid breaking older code paths but are otherwise
        ignored here.
        """
        # If the first positional value was a db_manager passed positionally into the 'config' slot,
        # detect and shift it. (Script usage: BundesligaClubScraper(MockDatabaseManager()))
        if config is not None and not isinstance(config, BundesligaClubScraperConfig):
            args = (config,) + args  # treat provided object as first positional arg (db_manager)
            config = None
        cfg = config or BundesligaClubScraperConfig()
        # Backward compatibility: if first positional arg provided and not a ScrapingConfig treat as db_manager
        db_manager = kwargs.pop('db_manager', None)
        if db_manager is None and args:
            # Only treat first arg as db_manager if it does not look like a config instance
            potential = args[0]
            if not isinstance(potential, BundesligaClubScraperConfig):
                db_manager = potential
        if db_manager is None:
            # Provide a lightweight no-op db manager to prevent attribute errors in standalone usage
            class _NullDB:
                async def bulk_insert(self, *a, **k):
                    return None
            db_manager = _NullDB()
        # BaseScraper requires a name argument
        super().__init__(cfg, db_manager=db_manager, name='bundesliga_club_scraper')
        # Preserve arbitrary kwargs for potential legacy use
        self._extra_init_kwargs = kwargs
        # Decide if we attempt dynamic rendering
        env_flag = os.getenv('BUNDESLIGA_USE_PLAYWRIGHT') in ('1','true','True')
        self._use_playwright = use_playwright if use_playwright is not None else env_flag
        # Playwright runtime handles
        self._pw = None
        self._pw_browser = None
        self._pw_page = None
        # Buffers populated during dynamic fetch
        self._captured_club_json: list[dict] = []
        self._captured_club_json_pairs: list[tuple[str, dict]] = []

    # -------------------- Utility Normalizers --------------------

    # -------------------- Utility Normalizers --------------------
    def _normalize_website(self, url_val: Optional[str]) -> Optional[str]:
        """Ensure website/homepage has a scheme. Accept bare domains.

        Examples:
          'www.fcaugsburg.de' -> 'https://www.fcaugsburg.de'
          'http://bvb.de' stays as-is.
        """
        if not url_val:
            return None
        u = url_val.strip()
        if not u:
            return None
        # Sometimes value may be like 'www.domain.tld' or 'domain.tld'
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', u):
            # Prepend https://
            u = f"https://{u.lstrip('/')}"
        # Remove accidental double schemes
        u = re.sub(r'^(https?://)+(https?://)', r'\1', u, flags=re.I)
        return u

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
        html = await self._fetch_page_dynamic(self.OVERVIEW_URL_DE)
        soup = self.parse_html(html)
        overview_items = self._extract_clubs_overview(soup, raw_html=html)
        if not overview_items:
            # fallback: English page
            try:
                html_en = await self._fetch_page_dynamic(self.OVERVIEW_URL_EN)
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
                detail_html = await self._fetch_page_dynamic(url)
                soup_detail = self.parse_html(detail_html)
                club_data = self._extract_club_data(soup_detail, url)
                # Enrich via hydration JSON if dynamic content withheld from static HTML
                try:
                    self._enrich_club_from_hydration(detail_html, club_data)
                except Exception:
                    pass
                # Regex fallback if still critical fields missing
                core_missing = not club_data.get('official_name') or not club_data.get('founded_year') or not club_data.get('colors') or not club_data.get('street_address')
                if core_missing:
                    try:
                        self._regex_fact_table_fallback(detail_html, club_data)
                    except Exception:
                        pass
                # Additional broad div-based regex fallback
                core_missing = not club_data.get('official_name') or not club_data.get('founded_year') or not club_data.get('colors') or not club_data.get('street_address')
                if core_missing:
                    try:
                        self._regex_div_fact_table_fallback(detail_html, club_data)
                    except Exception:
                        pass
                # Debug dump of raw HTML (first problematic case) if still missing after all attempts
                if core_missing and os.getenv('BUNDESLIGA_SCRAPER_DEBUG') in ('1','true','True'):
                    # Simple one-time dump mechanism
                    dump_dir = os.path.join(os.getcwd(), 'reports', 'debug_html')
                    os.makedirs(dump_dir, exist_ok=True)
                    slug = url.rstrip('/').rsplit('/',1)[-1]
                    dump_path = os.path.join(dump_dir, f'club_raw_{slug}.html')
                    if not os.path.exists(dump_path):
                        try:
                            with open(dump_path, 'w', encoding='utf-8') as f:
                                f.write(detail_html)
                            logger.info("Dumped club HTML for debugging: %s", dump_path)
                        except Exception as e:
                            logger.debug("Failed to write debug dump %s: %s", dump_path, e)
                if not club_data.get('name'):
                    continue
                squad_url = self._find_squad_url(soup_detail, url)
                # Final sanitation: discard obviously invalid city tokens (pure 2-3 digit numbers)
                if club_data.get('city') and isinstance(club_data['city'], str) and re.fullmatch(r'\d{2,3}', club_data['city']):
                    club_data['city'] = None
                club = EnhancedClub(
                    name=club_data['name'],
                    short_name=club_data.get('short_name'),
                    city=club_data.get('city'),
                    founded_year=club_data.get('founded_year'),
                    logo_url=club_data.get('logo_url'),
                    website=self._normalize_website(club_data.get('website') or item.get('website')),
                    stadium=club_data.get('stadium') or item.get('stadium'),
                    stadium_capacity=club_data.get('stadium_capacity'),
                    coach=club_data.get('coach'),
                    colors=club_data.get('colors'),
                    official_name=club_data.get('official_name'),
                    street_address=club_data.get('street_address'),
                    postal_code=club_data.get('postal_code'),
                    phone=club_data.get('phone'),
                    fax=club_data.get('fax'),
                    email=club_data.get('email'),
                    stadium_image_url=club_data.get('stadium_image_url'),
                    map_url=club_data.get('map_url'),
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
        player = self._parse_player_data(soup, player_url)
        # Augment with hydration / ld+json fallback if key fields missing
        if player and (not player.position or not player.nationality or not player.preferred_foot or not player.shirt_number):
            try:
                enriched = self._player_hydration_fallback(html, player)
                if enriched:
                    player = enriched
            except Exception:
                pass
        if player:
            self._augment_player_postprocess(player, soup)
        return player

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
        # Attempt explicit new layout extraction (fact table + stadium header block)
        try:
            # Stadium image & name / capacity block
            stadium_container = soup.find('div', class_=re.compile(r'stadiumImage'))
            if stadium_container:
                img_el = stadium_container.find('img')
                if img_el and img_el.get('src'):
                    data['stadium_image_url'] = urljoin(url, img_el['src'])
            footer_block = soup.find('div', class_=re.compile(r'footer'))
            if footer_block:
                # Stadium name
                name_wrapper = footer_block.find('div', class_=re.compile(r'stadium-name-wrapper'))
                if name_wrapper:
                    label_el = name_wrapper.find(class_=re.compile(r'label'))
                    value_el = name_wrapper.find(class_=re.compile(r'value'))
                    if value_el:
                        stadium_name = value_el.get_text(strip=True)
                        if stadium_name:
                            data['stadium'] = stadium_name
                # Capacity sibling
                cap_div = footer_block.find_next('div', class_=re.compile(r'capac'))  # matches 'capacity' variant
                if cap_div:
                    value_span = cap_div.find(class_=re.compile(r'value'))
                    if value_span:
                        cap_txt = value_span.get_text(strip=True)
                        cap_num = re.sub(r'[^0-9]', '', cap_txt)
                        if cap_num.isdigit():
                            try:
                                data['stadium_capacity'] = int(cap_num)
                            except ValueError:
                                pass
            # Fact table parsing
            fact_container = soup.find('div', class_=re.compile(r'factTable'))
            if fact_container:
                for row in fact_container.find_all('div', class_=re.compile(r'col')):
                    label_el = row.find(class_=re.compile(r'label'))
                    value_el = row.find(class_=re.compile(r'value'))
                    if not label_el or not value_el:
                        continue
                    label = label_el.get_text(' ', strip=True).strip()
                    # For colors value is a container of color divs
                    if re.search(r'Clubfarben|Club colors', label, re.I):
                        color_divs = value_el.find_all('div', class_=re.compile(r'clubColor'))
                        colors: Dict[str, str] = {}
                        ordered_colors: list[str] = []
                        for cdiv in color_divs:
                            style = cdiv.get('style') or ''
                            mcol = re.search(r'background-color:\s*([^;]+);?', style)
                            if not mcol:
                                continue
                            raw_col = mcol.group(1).strip()
                            ordered_colors.append(self._normalize_color(raw_col))
                        if ordered_colors:
                            data['colors'] = self._standardize_colors(ordered_colors)
                        continue
                    val_text = value_el.get_text(' ', strip=True).strip()
                    if not val_text:
                        continue
                    if re.search(r'Offizieller Clubname|Official club name', label, re.I):
                        data['official_name'] = val_text
                    elif re.search(r'Gegründet|Founded', label, re.I):
                        year_m = re.search(r'(19|20)\d{2}', val_text)
                        if year_m:
                            try:
                                data['founded_year'] = int(year_m.group())
                            except ValueError:
                                pass
                    elif re.search(r'Straße|Strasse|Address|Adresse', label, re.I):
                        data['street_address'] = val_text
                        # attempt postal code & city split (e.g. 86199 Augsburg)
                        pc_city = re.match(r'(\d{4,5})\s+(.+)', val_text)
                        if pc_city and not data.get('postal_code') and not data.get('city'):
                            data['postal_code'] = pc_city.group(1)
                            data['city'] = pc_city.group(2)
                    elif re.search(r'Stadt|City|Ort', label, re.I):
                        # Often contains postal code + city
                        pc_city = re.match(r'(\d{4,5})\s+(.+)', val_text)
                        if pc_city:
                            data['postal_code'] = pc_city.group(1)
                            data['city'] = pc_city.group(2)
                        else:
                            data['city'] = val_text
                    elif re.search(r'Telefon|Phone', label, re.I):
                        data['phone'] = val_text
                    elif re.search(r'Fax', label, re.I):
                        data['fax'] = val_text
                    elif re.search(r'Website', label, re.I):
                        # Might contain an <a>
                        a = value_el.find('a', href=True)
                        if a and a['href']:
                            data['website'] = a['href']
                        else:
                            data['website'] = val_text
                    elif re.search(r'Email|E-Mail', label, re.I):
                        data['email'] = val_text
                    elif re.search(r'Anfahrt|Map', label, re.I):
                        a = value_el.find('a', href=True)
                        if a:
                            data['map_url'] = a['href']
        except Exception as e:
            logger.debug("Enhanced club fact table parse failed: %s", e)

        # Fallback legacy extraction if some core fields still missing
        if 'stadium' not in data or not data.get('stadium'):
            data['stadium'] = self._find_labeled_value(soup, ['Stadium', 'Stadion', 'Venue'])
        if 'coach' not in data or not data.get('coach'):
            data['coach'] = self._find_labeled_value(soup, ['Coach', 'Trainer', 'Head Coach'])
        if 'founded_year' not in data or data.get('founded_year') is None:
            founded_text = self._find_labeled_value(soup, ['Founded', 'Gegründet', 'Est.', 'Since'])
            if founded_text:
                m = re.search(r'\b(19|20)\d{2}\b', founded_text)
                if m:
                    try:
                        data['founded_year'] = int(m.group())
                    except ValueError:
                        pass
        if 'city' not in data or not data.get('city'):
            data['city'] = self._find_labeled_value(soup, ['City', 'Stadt', 'Location', 'Ort'])
        if 'logo_url' not in data or not data.get('logo_url'):
            logo = soup.find('img', {'alt': re.compile(r'logo|emblem', re.I)}) or soup.find('img', class_=re.compile(r'logo|emblem'))
            if logo and logo.get('src'):
                data['logo_url'] = urljoin(url, logo['src'])
        if 'stadium_capacity' not in data or data.get('stadium_capacity') is None:
            capacity_text = self._find_labeled_value(soup, ['Capacity', 'Kapazität', 'Seats'])
            if capacity_text:
                m2 = re.search(r'(\d{1,3}(?:[,\.]\d{3})*)', capacity_text.replace('.', '').replace(',', ''))
                if m2:
                    try:
                        data['stadium_capacity'] = int(m2.group().replace(',', '').replace('.', ''))
                    except ValueError:
                        pass
        return data

    def _enrich_club_from_hydration(self, html: str, data: Dict[str, Any]):
        """Parse window.__NUXT__ JSON to fill missing club fields.

        Targets: official_name, founded_year, stadium_capacity, colors, phone, fax, email, website, stadium.
        """
        try:
            # Broaden regex: allow trailing semicolon, spaces and attributes before </script>
            m = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
            raw_json = None
            if m:
                raw_json = m.group(1)
            else:
                marker = 'window.__NUXT__'
                idx = html.find(marker)
                if idx != -1:
                    eq = html.find('=', idx)
                    if eq != -1:
                        bstart = html.find('{', eq)
                        if bstart != -1:
                            depth = 0
                            for j in range(bstart, len(html)):
                                ch = html[j]
                                if ch == '{': depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        raw_json = html[bstart:j+1]
                                        break
            if not raw_json:
                if os.getenv('BUNDESLIGA_SCRAPER_DEBUG') in ('1','true','True'):
                    snippet = html[:5000]
                    logger.info("No window.__NUXT__ hydration JSON found for club page (first 5KB snippet logged)")
                    logger.debug("HTML snippet (truncated): %s", snippet)
                return
            nuxt = json.loads(raw_json)
            debug_enabled = os.getenv('BUNDESLIGA_SCRAPER_DEBUG') in ('1','true','True')
            debug_hits: dict[str, list[str]] = {}
            def record(field: str, source: str):
                if not debug_enabled:
                    return
                debug_hits.setdefault(field, []).append(source)
            def walk(o):
                if isinstance(o, dict):
                    club_name_keys = ['officialName','official_name','officialClubName','clubNameLong']
                    founded_keys = ['founded','foundationYear','foundedYear','yearFounded']
                    stadium_keys = ['stadium']
                    # Additional nested name structures (observed in captured API blob wapp.bapi.bundesliga.com/club)
                    if not data.get('official_name'):
                        # Structure: name: { full: ..., withFormOfCompany: ... }
                        name_block = o.get('name')
                        if isinstance(name_block, dict):
                            for cand_key in ['withFormOfCompany','official','full','long']:
                                cand_val = name_block.get(cand_key)
                                if isinstance(cand_val, str) and len(cand_val) > 3:
                                    data['official_name'] = cand_val.strip(); record('official_name', f'nuxt.name.{cand_key}')
                                    break
                    for k in club_name_keys:
                        if not data.get('official_name') and isinstance(o.get(k), str):
                            data['official_name'] = o[k].strip(); record('official_name', f'nuxt.{k}')
                            break
                    for k in founded_keys:
                        if not data.get('founded_year') and o.get(k) is not None:
                            fv = o.get(k)
                            if isinstance(fv, (str,int)) and re.match(r'^(19|20)\d{2}$', str(fv)):
                                try:
                                    data['founded_year'] = int(fv); record('founded_year', f'nuxt.{k}')
                                except ValueError:
                                    pass
                            if data.get('founded_year'):
                                break
                    for k in stadium_keys:
                        if k in o and isinstance(o[k], dict):
                            stad = o[k]
                            if not data.get('stadium') and isinstance(stad.get('name'), str):
                                data['stadium'] = stad['name'].strip(); record('stadium', f'nuxt.{k}.name')
                            if not data.get('stadium_capacity') and stad.get('capacity'):
                                cap_raw = str(stad.get('capacity'))
                                cap_num = re.sub(r'[^0-9]', '', cap_raw)
                                if cap_num.isdigit():
                                    try:
                                        data['stadium_capacity'] = int(cap_num); record('stadium_capacity', f'nuxt.{k}.capacity')
                                    except ValueError:
                                        pass
                    color_keys_pattern = re.compile(r'(color(P|S|T|Primary|Secondary|Tertiary)|primaryColorHex|secondaryColorHex|tertiaryColorHex)', re.I)
                    collected_colors: list[str] = []
                    # Handle structured colors seen in club endpoint: colors: { club: { primary: {hex:#...}, secondary: {...}} }
                    if 'colors' in o and isinstance(o.get('colors'), dict):
                        def extract_color_hex(block):
                            if isinstance(block, dict):
                                hx = block.get('hex') or block.get('Hex') or block.get('HEX')
                                if isinstance(hx, str):
                                    return self._normalize_color(hx)
                            if isinstance(block, str):
                                return self._normalize_color(block)
                            return None
                        colors_block = o['colors']
                        for path in [
                            ('colors','club','primary'),('colors','club','secondary'),('colors','club','tertiary'),
                            ('colors','jersey','home','primary'),('colors','jersey','home','secondary'),
                            ('colors','jersey','away','primary'),('colors','jersey','away','secondary'),
                        ]:
                            try:
                                ref = colors_block
                                for seg in path[1:]:  # skip leading 'colors'
                                    if isinstance(ref, dict):
                                        ref = ref.get(seg)
                                    else:
                                        ref = None
                                        break
                                col = extract_color_hex(ref)
                                if col:
                                    collected_colors.append(col)
                            except Exception:
                                continue
                    for ck, val in o.items():
                        if color_keys_pattern.match(ck) and isinstance(val, str) and len(val) < 40:
                            collected_colors.append(self._normalize_color(val))
                        if ck in ('clubColors','colors','brandColors') and isinstance(val, list):
                            for c in val:
                                if isinstance(c, str):
                                    collected_colors.append(self._normalize_color(c))
                    if collected_colors and not data.get('colors'):
                        data['colors'] = self._standardize_colors(collected_colors); record('colors','nuxt.color*')
                    contact_blocks = [o.get('contact'), o.get('communication')]
                    for block in [b for b in contact_blocks if isinstance(b, dict)]:
                        if not data.get('phone') and isinstance(block.get('phone'), str):
                            data['phone'] = block['phone']; record('phone','nuxt.contact.phone')
                        if not data.get('fax') and isinstance(block.get('fax'), str):
                            data['fax'] = block['fax']; record('fax','nuxt.contact.fax')
                        if not data.get('email') and isinstance(block.get('email'), str):
                            data['email'] = block['email']; record('email','nuxt.contact.email')
                        if not data.get('website') and isinstance(block.get('website'), str):
                            data['website'] = block['website']; record('website','nuxt.contact.website')
                    if not data.get('phone') and isinstance(o.get('phone'), str):
                        data['phone'] = o['phone']; record('phone','nuxt.phone')
                    if not data.get('fax') and isinstance(o.get('fax'), str):
                        data['fax'] = o['fax']; record('fax','nuxt.fax')
                    if not data.get('email') and isinstance(o.get('email'), str):
                        data['email'] = o['email']; record('email','nuxt.email')
                    for w_key in ['website','homepage','url']:
                        if not data.get('website') and isinstance(o.get(w_key), str) and 'http' in o.get(w_key):
                            data['website'] = o[w_key]; record('website', f'nuxt.{w_key}')
                            break
                    # Normalize website if present without scheme
                    if data.get('website'):
                        data['website'] = self._normalize_website(data['website'])
                    address_candidates = []
                    for a_key in ['address','clubAddress','location','venueAddress']:
                        if isinstance(o.get(a_key), dict):
                            address_candidates.append(o[a_key])
                    for addr in address_candidates:
                        if not isinstance(addr, dict):
                            continue
                        street = addr.get('street') or addr.get('streetAddress') or addr.get('addressLine1')
                        city = addr.get('city') or addr.get('town') or addr.get('locality')
                        postal = addr.get('zip') or addr.get('postalCode') or addr.get('postcode')
                        if street and not data.get('street_address'):
                            house_no = addr.get('houseNumber') or addr.get('house_number')
                            street_full = f"{street} {house_no}".strip() if house_no and house_no not in str(street) else str(street)
                            data['street_address'] = str(street_full).strip(); record('street_address','nuxt.address.street')
                        if city and not data.get('city'):
                            data['city'] = str(city).strip(); record('city','nuxt.address.city')
                        if postal and not data.get('postal_code'):
                            data['postal_code'] = re.sub(r'[^0-9A-Za-z]', '', str(postal)); record('postal_code','nuxt.address.postal')
                    for mk in ['mapUrl','mapURL','mapsLink','mapLink']:
                        if not data.get('map_url') and isinstance(o.get(mk), str) and o.get(mk).startswith('http'):
                            data['map_url'] = o[mk]; record('map_url', f'nuxt.{mk}')
                            break
                    if not data.get('coach'):
                        coach_obj = o.get('coach') or o.get('trainer')
                        if isinstance(coach_obj, dict):
                            cname = coach_obj.get('name') or coach_obj.get('fullName')
                            if isinstance(cname, str):
                                data['coach'] = cname.strip(); record('coach','nuxt.coach.name')
                        elif isinstance(coach_obj, str):
                            data['coach'] = coach_obj.strip(); record('coach','nuxt.coach')
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for it in o:
                        walk(it)
            walk(nuxt)
            # Post-process: avoid bogus numeric-only city values (e.g., '50') captured from malformed DOM artifacts
            if data.get('city') and isinstance(data['city'], str) and re.fullmatch(r'\d{2,3}', data['city']):
                def _seek_city(o):
                    if isinstance(o, dict):
                        for k,v in o.items():
                            if k.lower() in ('city','town','location') and isinstance(v, str) and not re.fullmatch(r'\d{2,3}', v):
                                return v
                            r = _seek_city(v)
                            if r: return r
                    elif isinstance(o, list):
                        for it in o:
                            r = _seek_city(it)
                            if r: return r
                    return None
                candidate_city = _seek_city(nuxt)
                if candidate_city:
                    data['city'] = candidate_city
            if debug_enabled and debug_hits:
                logger.info("Club hydration debug: %s", {k: list(set(v)) for k,v in debug_hits.items()})
        except Exception as e:
            logger.debug("Club hydration enrichment failed: %s", e)

    def _regex_fact_table_fallback(self, html: str, data: Dict[str, Any]):  # pragma: no cover
        """Regex-based extraction of label/value club fact entries when DOM parsing failed.

        Only fills fields still missing in data.
        """
        try:
            pattern = re.compile(r'<span[^>]*class="[^"]*label[^"]*"[^>]*>(?P<label>.*?)</span>\s*<span[^>]*class="[^"]*value[^"]*"[^>]*>(?P<value>.*?)</span>', re.I|re.DOTALL)
            for m in pattern.finditer(html):
                label_raw = re.sub(r'<[^>]+>', '', m.group('label')).strip()
                value_raw = re.sub(r'<[^>]+>', '', m.group('value')).strip()
                if not label_raw or not value_raw:
                    continue
                if re.search(r'Offizieller Clubname|Official club name', label_raw, re.I) and not data.get('official_name'):
                    data['official_name'] = value_raw
                elif re.search(r'Gegründet|Founded', label_raw, re.I) and not data.get('founded_year'):
                    ym = re.search(r'(19|20)\d{2}', value_raw)
                    if ym:
                        try:
                            data['founded_year'] = int(ym.group())
                        except ValueError:
                            pass
                elif re.search(r'Clubfarben|Club colors', label_raw, re.I) and not data.get('colors'):
                    color_divs = re.findall(r'background-color:\s*([^;]+);?', m.group(0))
                    ordered = [self._normalize_color(c.strip()) for c in color_divs]
                    if ordered:
                        data['colors'] = self._standardize_colors(ordered)
                elif re.search(r'Straße|Strasse|Address|Adresse', label_raw, re.I) and not data.get('street_address'):
                    data['street_address'] = value_raw
                elif re.search(r'Stadt|City|Ort', label_raw, re.I) and not data.get('city'):
                    pc_city = re.match(r'(\d{4,5})\s+(.+)', value_raw)
                    if pc_city:
                        data['postal_code'] = pc_city.group(1)
                        data['city'] = pc_city.group(2)
                    else:
                        # Avoid assigning lone numeric token as city (observed artifact '50','48', etc.)
                        if not re.fullmatch(r'\d{2,3}', value_raw):
                            data['city'] = value_raw
                elif re.search(r'Telefon|Phone', label_raw, re.I) and not data.get('phone'):
                    data['phone'] = value_raw
                elif re.search(r'Fax', label_raw, re.I) and not data.get('fax'):
                    data['fax'] = value_raw
                elif re.search(r'Website', label_raw, re.I) and not data.get('website'):
                    data['website'] = value_raw
                elif re.search(r'Email|E-Mail', label_raw, re.I) and not data.get('email'):
                    data['email'] = value_raw
        except Exception:
            pass
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
        """Attempt to discover a club-specific squad page URL.

        Previous logic sometimes returned the generic Bundesliga player hub
        (e.g. /de/bundesliga/spieler) which aggregates ALL players, causing
        the scraper to attribute unrelated players to a single club.

        Strategy:
        1. Collect candidate anchors whose text/href contains squad indicators.
        2. Prefer URLs that include the club slug (derived from base_url after /clubs/).
        3. Exclude known generic aggregate pages (*/bundesliga/spieler, */en/bundesliga/players, etc.).
        4. Fallback: append '/squad' to club base if pattern looks plausible.
        """
        try:
            parsed = urlparse(base_url)
            path = parsed.path.rstrip('/').lower()
            club_slug = None
            m = re.search(r'/clubs/([^/]+)$', path)
            if m:
                club_slug = m.group(1)
        except Exception:
            club_slug = None

        cfg = get_lexicon_config()
        indicators = [w.lower() for w in (cfg.get_indicator_list('squad_page') or ['squad'])]
        generic_disallowed = [
            '/bundesliga/spieler', '/en/bundesliga/players', '/de/bundesliga/spieler'
        ]  # could move to YAML later

        candidates: list[str] = []
        for a in soup.find_all('a', href=True):
            href_raw = a['href']
            href_l = href_raw.lower()
            txt = a.get_text(strip=True).lower()
            if any(tok in href_l or tok in txt for tok in indicators):
                abs_url = urljoin(base_url, href_raw)
                # Skip obvious generic collections
                if any(abs_url.lower().endswith(g) for g in generic_disallowed):
                    continue
                candidates.append(abs_url)

        # Rank candidates: club slug presence > shorter path length
        if candidates:
            def score(u: str) -> tuple[int, int]:
                contains_slug = 1 if (club_slug and club_slug in u.lower()) else 0
                path_len = len(urlparse(u).path)
                # higher contains_slug first, then shorter path
                return (-contains_slug, path_len)
            candidates.sort(key=score)
            chosen = candidates[0]
            if club_slug and club_slug not in chosen.lower() and self.logger:
                self.logger.debug("Squad URL selected without club slug: %s (slug=%s)", chosen, club_slug)
            return chosen

        # Fallback: synthesize /squad if base_url is a club detail
        if club_slug and '/clubs/' in base_url:
            fallback = base_url.rstrip('/') + '/squad'
            if self.logger:
                self.logger.debug("Fallback squad URL synthesized: %s", fallback)
            return fallback
        return None

    # =============================================================================
    # Player parsing
    # =============================================================================
    def _extract_player_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        cfg = get_lexicon_config()
        links: set[str] = set()
        page_text = soup.get_text().lower()
        squad_indicators = [w.lower() for w in cfg.get_indicator_list('squad_page')]
        if squad_indicators and not any(i in page_text for i in squad_indicators):
            return []

        def row_has_position(text: str) -> bool:
            tokens = set(re.split(r'[^a-zA-Zäöüß]+', text.lower()))
            if any(t in {'position', 'pos'} for t in tokens):
                return True
            for t in tokens:
                if not t:
                    continue
                if map_position(t):
                    return True
            return False

        # Prefer structured containers (table rows, article blocks)
        for container in soup.find_all(['tr', 'article']):
            c_text = container.get_text(" ", strip=True)
            if not row_has_position(c_text):
                continue
            for a in container.find_all('a', href=True):
                href = a['href']
                if re.search(r'/de/bundesliga/spieler/[a-z0-9\-]+', href):
                    link_text = a.get_text(strip=True)
                    if link_text and len(link_text.split()) >= 2:
                        links.add(urljoin(base_url, href))

        # Fallback: anchors inside tables referencing player pages (context tokens optional here)
        if not links:
            for a in soup.find_all('a', href=re.compile(r'/de/bundesliga/spieler/[a-z0-9\-]+')):
                parent_tr = a.find_parent('tr')
                if not parent_tr:
                    continue
                ctx = parent_tr.get_text(' ', strip=True)
                if row_has_position(ctx) or any(tok in ctx.lower() for tok in ['gk', 'fw', 'mf', 'df']):
                    link_text = a.get_text(strip=True)
                    if link_text and len(link_text.split()) >= 2:
                        links.add(urljoin(base_url, a['href']))

        # Ultra-permissive final fallback (mainly for unit-test synthetic HTML)
        if not links:
            for a in soup.find_all('a', href=re.compile(r'/de/bundesliga/spieler/[a-z0-9\-]+')):
                if a.find_parent(['nav', 'footer']):
                    continue
                link_text = a.get_text(strip=True)
                if link_text and len(link_text.split()) >= 2 and a.find_parent('table'):
                    links.add(urljoin(base_url, a['href']))

        result = sorted(links)
        if len(result) > 100:  # safety cap
            result = result[:50]
        return result

    def _parse_player_data(self, soup: BeautifulSoup, url: str) -> Optional[EnhancedPlayer]:
        pdata = self._extract_player_basic_info(soup)
        if not (pdata.get('first_name') or pdata.get('last_name')):
            return None
        # Basic stats first
        season_stats = self._extract_player_season_stats(soup)
        # Enhanced extraction attempts dynamic key/value tables
        enhanced = self._extract_player_season_stats_enhanced(soup)
        if enhanced:
            if season_stats:
                # merge: do not overwrite existing non-null
                for field, value in enhanced.model_dump().items():
                    if field == 'source_url':
                        continue
                    if value is not None and getattr(season_stats, field) in (None, []):
                        setattr(season_stats, field, value)
            else:
                season_stats = enhanced
        career_stats = self._extract_player_career_stats(soup)
        return EnhancedPlayer(
            first_name=pdata.get('first_name'), last_name=pdata.get('last_name'), birth_date=pdata.get('birth_date'),
            birth_place=pdata.get('birth_place'), nationality=pdata.get('nationality'), height_cm=pdata.get('height_cm'),
            weight_kg=pdata.get('weight_kg'), preferred_foot=pdata.get('preferred_foot'), photo_url=pdata.get('photo_url'),
            position=pdata.get('position'), shirt_number=pdata.get('shirt_number'), market_value=pdata.get('market_value'),
            previous_clubs=pdata.get('previous_clubs'),
            current_season_stats=season_stats, career_stats=career_stats, source_url=url,
            scraped_at=datetime.now(timezone.utc), external_ids={'bundesliga_url': url}
        )

    def _extract_player_basic_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        cfg = get_lexicon_config()
        fl = cfg.field_labels  # dict of canonical -> list
        name_text = (
            self._get_text_by_selector(soup, 'h1.player-name, h1, .player-header h1') or
            self._get_meta_content(soup, 'og:title') or ''
        )
        if name_text:
            # Normalize to NFC to ensure composed Unicode characters (e.g. 'é')
            raw = unicodedata.normalize('NFC', name_text.strip())
            # Remove common suffix fragments like '- Spielerprofil - Bundesliga'
            raw = re.sub(r'\b(spielerprofil|player profile)\b.*$', '', raw, flags=re.I).strip()
            # Detect specialized fused pattern only (NameShirtNumber) without spaces
            m = re.match(r'^([A-Za-zÀ-ÖØ-öø-ÿ\-]+?)(\d{1,3})$', raw)
            if m:
                name_core, num = m.groups()
                # Split first capital sequence vs rest if possible; else treat entire as last name after first token
                parts = re.findall(r'[A-ZÀ-ÖØ-Þ][^A-ZÀ-ÖØ-Þ]+', name_core) or [name_core]
                data['first_name'] = parts[0]
                if len(parts) > 1:
                    data['last_name'] = ' '.join(p.strip() for p in parts[1:] if p.strip())
                try:
                    sn = int(num)
                    if 1 <= sn <= 99:
                        data['shirt_number'] = sn
                except ValueError:
                    pass
            else:
                # Simple split preserves accents reliably
                if ' ' in raw:
                    first, rest = raw.split(' ', 1)
                    data['first_name'] = first
                    data['last_name'] = rest.strip()
                else:
                    data['first_name'] = raw
                    data['last_name'] = ''
        data['position'] = self._find_labeled_value(soup, fl.get('position', ['Position']))
        # Normalise position early (broad band)
        if data.get('position'):
            mapped = map_position(data['position'])
            if mapped:
                data['position'] = mapped
        number_text = self._find_labeled_value(soup, fl.get('number', ['Number']))
        if number_text:
            m = re.search(r'\d+', number_text)
            if m:
                try:
                    data['shirt_number'] = int(m.group())
                except ValueError:
                    pass
        birth_text = self._find_labeled_value(soup, fl.get('birth_date', ['Birth']))
        if birth_text:
            data['birth_date'] = self._parse_date_string(birth_text)
        data['birth_place'] = self._find_labeled_value(soup, fl.get('birth_place', ['Birthplace']))
        data['nationality'] = self._find_labeled_value(soup, fl.get('nationality', ['Nationality']))
        # Structured info items for height/weight
        if (data.get('height_cm') is None or data.get('weight_kg') is None):
            try:
                for info in soup.find_all('div', class_=re.compile(r'info-item')):
                    label_el = info.find(['span','div'], class_=re.compile(r'label'))
                    value_el = info.find(['span','div'], class_=re.compile(r'value'))
                    if not label_el or not value_el:
                        continue
                    label_txt = label_el.get_text(' ', strip=True).lower()
                    value_txt = value_el.get_text(' ', strip=True)
                    if data.get('height_cm') is None and any(k in label_txt for k in ['größe','grösse','height']):
                        m_h = re.search(r'(\d{2,3})\s*cm', value_txt)
                        if m_h:
                            try:
                                data['height_cm'] = int(m_h.group(1))
                                logger.debug("Parsed height_cm from info-item: %s", data['height_cm'])
                            except ValueError:
                                pass
                    if data.get('weight_kg') is None and any(k in label_txt for k in ['gewicht','weight']):
                        m_w = re.search(r'(\d{2,3})\s*kg', value_txt)
                        if m_w:
                            try:
                                data['weight_kg'] = int(m_w.group(1))
                                logger.debug("Parsed weight_kg from info-item: %s", data['weight_kg'])
                            except ValueError:
                                pass
            except Exception:
                pass
        height_text = self._find_labeled_value(soup, fl.get('height', ['Height']))
        if height_text and (m := re.search(r'(\d+)\s*cm', height_text)):
            try:
                data['height_cm'] = int(m.group(1))
            except ValueError:
                pass
        weight_text = self._find_labeled_value(soup, fl.get('weight', ['Weight']))
        if weight_text and (m := re.search(r'(\d+)\s*kg', weight_text)):
            try:
                data['weight_kg'] = int(m.group(1))
            except ValueError:
                pass
        foot_text = self._find_labeled_value(soup, fl.get('preferred_foot', ['Foot']))
        if foot_text and foot_text.lower() in ['left', 'right', 'both']:
            try:
                data['preferred_foot'] = Footedness(foot_text.lower())
            except Exception:
                pass
        data['market_value'] = self._find_labeled_value(soup, fl.get('market_value', ['Market Value']))
        photo = soup.find('img', {'alt': re.compile(r'player|spieler', re.I)}) or soup.find('img', class_=re.compile(r'player|portrait'))
        if photo and photo.get('src'):
            src = photo['src']
            if src.startswith('/'):
                data['photo_url'] = f"https://www.bundesliga.com{src}".replace('///','/').replace('//www','//www')
            else:
                data['photo_url'] = src
        return data

    def _player_hydration_fallback(self, html: str, player: EnhancedPlayer) -> Optional[EnhancedPlayer]:
        """Extract missing player attributes from hydration or ld+json blocks.

        We look for window.__NUXT__ or <script type="application/ld+json"> objects containing
        fields like nationality, position, height, birthDate, image, identifier, etc.
        """
        try:
            # Collect JSON blobs
            blobs: list[str] = []
            # window.__NUXT__ brace extraction (reuse logic from club parsing simplified)
            m = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
            if m:
                blobs.append(m.group(1))
            else:
                if 'window.__NUXT__' in html:
                    idx = html.find('window.__NUXT__')
                    eq = html.find('=', idx)
                    if eq != -1:
                        bstart = html.find('{', eq)
                        if bstart != -1:
                            depth = 0
                            for j in range(bstart, len(html)):
                                ch = html[j]
                                if ch == '{': depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        blobs.append(html[bstart:j+1])
                                        break
            # ld+json blocks
            for m2 in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL|re.I):
                blobs.append(m2.group(1))

            extracted: dict[str, Any] = {}
            for raw in blobs:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                self._walk_player_json(data, extracted)
            # Apply extracted values if player fields missing
            updated = False
            def set_if_missing(attr, value):
                nonlocal updated
                if value is None:
                    return
                if getattr(player, attr) in (None, [], ''):
                    try:
                        setattr(player, attr, value)
                        updated = True
                    except Exception:
                        pass
            set_if_missing('nationality', extracted.get('nationality'))
            set_if_missing('position', extracted.get('position'))
            set_if_missing('height_cm', extracted.get('height_cm'))
            set_if_missing('weight_kg', extracted.get('weight_kg'))
            set_if_missing('shirt_number', extracted.get('shirt_number'))
            set_if_missing('preferred_foot', extracted.get('preferred_foot'))
            set_if_missing('birth_date', extracted.get('birth_date'))
            set_if_missing('photo_url', extracted.get('photo_url'))
            if updated and self.logger:
                self.logger.debug("Hydration fallback enriched player %s %s (fields: %s)", player.first_name, player.last_name, [k for k,v in extracted.items() if v is not None])
            if updated:
                player.external_ids = (player.external_ids or {})
                if extracted.get('id'):
                    player.external_ids['bundesliga_player_id'] = extracted['id']
                return player
        except Exception:
            return None
        return None

    def _walk_player_json(self, obj: Any, out: dict[str, Any]):  # pragma: no cover - JSON traversal utility
        if isinstance(obj, dict):
            # Common LD-JSON schema.org Person / Athlete
            if obj.get('@type') in ('Person', 'Athlete'):
                if 'height' in obj and isinstance(obj['height'], str):
                    m = re.search(r'(\d{2,3})\s*cm', obj['height'])
                    if m:
                        out.setdefault('height_cm', int(m.group(1)))
                if 'weight' in obj and isinstance(obj['weight'], str):
                    m = re.search(r'(\d{2,3})\s*kg', obj['weight'])
                    if m:
                        out.setdefault('weight_kg', int(m.group(1)))
                if 'birthDate' in obj and isinstance(obj['birthDate'], str):
                    try:
                        out.setdefault('birth_date', datetime.fromisoformat(obj['birthDate'].replace('Z','+00:00')).date())
                    except Exception:
                        pass
                if 'nationality' in obj:
                    nat = obj['nationality']
                    if isinstance(nat, dict):
                        nat_name = nat.get('name') or nat.get('@id')
                        if isinstance(nat_name, str):
                            out.setdefault('nationality', nat_name)
                    elif isinstance(nat, str):
                        out.setdefault('nationality', nat)
                if 'image' in obj and isinstance(obj['image'], str):
                    out.setdefault('photo_url', obj['image'])
                if 'identifier' in obj and isinstance(obj['identifier'], (str, int)):
                    out.setdefault('id', str(obj['identifier']))
            # Hydration style nested data
            if 'position' in obj and isinstance(obj['position'], (str, dict)):
                pos_val = obj['position'] if isinstance(obj['position'], str) else obj['position'].get('name')
                if isinstance(pos_val, str):
                    out.setdefault('position', pos_val)
            if 'shirtNumber' in obj and isinstance(obj['shirtNumber'], (str, int)):
                try:
                    sn = int(str(obj['shirtNumber']).strip())
                    if 0 < sn < 100:
                        out.setdefault('shirt_number', sn)
                except Exception:
                    pass
            if 'foot' in obj and isinstance(obj['foot'], str):
                mapped_foot = map_footedness(obj['foot'])
                if mapped_foot:
                    try:
                        out.setdefault('preferred_foot', Footedness(mapped_foot))
                    except Exception:
                        pass
            for v in obj.values():
                self._walk_player_json(v, out)
        elif isinstance(obj, list):
            for it in obj:
                self._walk_player_json(it, out)

    # ------------------------------------------------------------------
    # Post-process augmentation heuristics (position inference, nationality mapping)
    # ------------------------------------------------------------------
    def _augment_player_postprocess(self, player: EnhancedPlayer, soup: BeautifulSoup):  # pragma: no cover - heuristic utility
        try:
            # Nationality canonicalisation via dynamic mappings (short codes or synonyms -> long form)
            if player.nationality:
                mapped_nat = map_nationality(player.nationality, return_long=True)
                if mapped_nat:
                    player.nationality = mapped_nat
            # Preferred foot canonicalisation (if accidentally captured as raw string earlier) - ensure enum assignment
            if isinstance(getattr(player, 'preferred_foot', None), str):
                mapped_pf = map_footedness(player.preferred_foot)  # type: ignore[arg-type]
                if mapped_pf:
                    try:
                        player.preferred_foot = Footedness(mapped_pf)  # type: ignore[assignment]
                    except Exception:
                        pass
            # Position heuristic if still missing
            if not player.position:
                # 1) Structured scan for Angular injected position labels (e.g. <div class="ng-star-inserted">Angriff</div>)
                structured = self._infer_position_from_structure(soup)
                if structured:
                    player.position = structured
                if not player.position:
                    text = soup.get_text(' ', strip=True).lower()
                    # 2) Richer mapping including abbreviations
                    pos_map = [
                        # Goalkeeper
                        ('torwart', 'Goalkeeper'), ('torhüter', 'Goalkeeper'), ('tw', 'Goalkeeper'), ('goalkeeper', 'Goalkeeper'), ('keeper', 'Goalkeeper'),
                        # Defender / defense
                        ('abwehr', 'Defender'), ('innenverteidiger', 'Defender'), ('aussenverteidiger', 'Defender'), ('verteidiger', 'Defender'),
                        ('iv', 'Defender'), ('rv', 'Defender'), ('lv', 'Defender'), ('defender', 'Defender'), ('full-back', 'Defender'),
                        # Midfield
                        ('mittelfeld', 'Midfielder'), ('zentrale mittelfeld', 'Midfielder'), ('dm', 'Midfielder'), ('om', 'Midfielder'),
                        ('zm', 'Midfielder'), ('am', 'Midfielder'), ('cm', 'Midfielder'), ('lm', 'Midfielder'), ('rm', 'Midfielder'),
                        ('midfielder', 'Midfielder'),
                        # Forward / attack
                        ('angriff', 'Forward'), ('stürmer', 'Forward'), ('stuermer', 'Forward'), ('angreifer', 'Forward'),
                        ('st', 'Forward'), ('ms', 'Forward'), ('fw', 'Forward'), ('striker', 'Forward'), ('forward', 'Forward'),
                    ]
                    for needle, label in pos_map:
                        if f' {needle} ' in f' {text} ':
                            player.position = label
                            break
            # After any heuristic mapping, unify to canonical code if a long form detected
            if player.position:
                # If we have full English words we still convert to code for consistency
                mapped = map_position(player.position)
                if mapped:
                    player.position = mapped
            # Normalize photo URL to https absolute
            if player.photo_url and isinstance(player.photo_url, str):
                if player.photo_url.startswith('//'):
                    player.photo_url = 'https:' + player.photo_url
                elif player.photo_url.startswith('/'):  # should already have been handled but double-ensure
                    player.photo_url = 'https://www.bundesliga.com' + player.photo_url
        except Exception:
            pass

    def _infer_position_from_structure(self, soup: BeautifulSoup) -> Optional[str]:  # pragma: no cover - heuristic utility
        candidates: list[str] = []
        for div in soup.find_all(['div', 'span'], class_=re.compile(r'ng-star-inserted')):
            txt = div.get_text(strip=True)
            if not txt or len(txt) > 30:
                continue
            candidates.append(txt)
        for raw in candidates:
            mapped = map_position(raw)
            if mapped:
                return mapped
        # Last resort: token split
        for raw in candidates:
            for token in re.split(r'\s+', raw):
                mapped = map_position(token)
                if mapped:
                    return mapped
        return None

    def _extract_player_season_stats(self, soup: BeautifulSoup) -> Optional[PlayerSeasonStats]:
        stats: Dict[str, Any] = {}
        stats_section = soup.find(['section', 'div'], class_=re.compile(r'stats|statistics|season'))
        if not stats_section:
            return None
        cfg = get_lexicon_config()
        stat_labels = cfg.player_stats_labels or {}
        for key, labels in stat_labels.items():
            txt = self._find_labeled_value(stats_section, labels)
            if txt and (m := re.search(r'\d+', txt.replace(',', ''))):
                try:
                    stats[key] = int(m.group())
                except ValueError:
                    pass
        return PlayerSeasonStats(**stats) if stats else None

    def _extract_player_season_stats_enhanced(self, soup: BeautifulSoup) -> Optional[PlayerSeasonStats]:
        """Parse richer season stats from dynamic key-value grid rows (German + English labels).

        Looks for rows with classes like 'row' containing two columns 'key' and 'value' as seen in the
        provided HTML snippet. Maps localized labels to standardized field names.
        """
        rows = soup.find_all('div', class_=re.compile(r'\brow\b'))
        if not rows:
            return None
        mapping: list[tuple[re.Pattern, str, str]] = [
            (re.compile(r'einsätze|appearances', re.I), 'appearances', 'int'),
            (re.compile(r'tore|goals', re.I), 'goals', 'int'),
            (re.compile(r'vorlagen|assists', re.I), 'assists', 'int'),
            (re.compile(r'gelbe karten|yellow', re.I), 'yellow_cards', 'int'),
            (re.compile(r'rote karten|red', re.I), 'red_cards', 'int'),
            (re.compile(r'gew\.? zweikämpfe|duels won', re.I), 'duels_won', 'int'),
            (re.compile(r'gew\.? kopfduelle|aerial duels won', re.I), 'aerial_duels_won', 'int'),
            (re.compile(r'sprints', re.I), 'sprints', 'int'),
            (re.compile(r'intensive läufe|intensive runs', re.I), 'intensive_runs', 'int'),
            (re.compile(r'laufdistanz', re.I), 'distance_km', 'float'),
            (re.compile(r'speed|km/h', re.I), 'top_speed_kmh', 'float'),
            (re.compile(r'flanken|crosses', re.I), 'crosses', 'int'),
            (re.compile(r'fouls|begangene fouls', re.I), 'fouls_committed', 'int'),
            (re.compile(r'ballbesitzphasen|possession phases', re.I), 'possession_phases', 'int'),
            (re.compile(r'shots on goal|shots on target|Torschüsse|torschüsse aufs? tor', re.I), 'shots_on_target', 'int'),
            (re.compile(r'abgewehrte schüsse|paraden|saves', re.I), 'saves', 'int'),
            (re.compile(r'eigentore|own goals?', re.I), 'own_goals', 'int'),
            # Differentiate penalties taken vs scored
            (re.compile(r'^elfmeter-tore|penalties scored', re.I), 'penalties_scored', 'int'),
            (re.compile(r'^elfmeter(?!-tore)|penalties$', re.I), 'penalties_taken', 'int'),
            (re.compile(r'minuten|minutes', re.I), 'minutes_played', 'int'),
            (re.compile(r'pfosten\s*/\s*latte|woodwork', re.I), 'woodwork', 'int'),
        ]
        collected: Dict[str, Any] = {}
        matched_fields: list[str] = []
        # Pass 1: structured row/key/value layout
        for r in rows:
            key_el = r.find('div', class_=re.compile(r'\bkey\b'))
            val_el = r.find('div', class_=re.compile(r'\bvalue\b'))
            if not key_el or not val_el:
                continue
            key_text = key_el.get_text(' ', strip=True)
            val_text = val_el.get_text(' ', strip=True)
            if not key_text or not val_text:
                continue
            for pattern, field, ftype in mapping:
                if pattern.search(key_text):
                    if ftype == 'int':
                        m = re.search(r'-?\d+', val_text.replace('.', '').replace(',', '.'))
                        if m:
                            try:
                                collected[field] = int(m.group())
                                matched_fields.append(field)
                                logger.debug("Enhanced stats (row) matched %s=%s (label='%s', raw='%s')", field, collected[field], key_text, val_text)
                            except ValueError:
                                pass
                    elif ftype == 'float':
                        m = re.search(r'-?\d+[\.,]?\d*', val_text)
                        if m:
                            try:
                                collected[field] = float(m.group().replace(',', '.'))
                                matched_fields.append(field)
                                logger.debug("Enhanced stats (row) matched %s=%s (label='%s', raw='%s')", field, collected[field], key_text, val_text)
                            except ValueError:
                                pass
                    break
        # Pass 2: stat-box layout (label/value)
        stat_boxes = soup.find_all('div', class_=re.compile(r'stat-box'))
        for box in stat_boxes:
            label_el = box.find('div', class_=re.compile(r'label'))
            value_el = box.find('div', class_=re.compile(r'value'))
            if not label_el or not value_el:
                continue
            key_text = label_el.get_text(' ', strip=True)
            val_text = value_el.get_text(' ', strip=True)
            if not key_text or not val_text:
                continue
            for pattern, field, ftype in mapping:
                if pattern.search(key_text) and field not in collected:
                    if ftype == 'int':
                        m = re.search(r'-?\d+', val_text.replace('.', '').replace(',', '.'))
                        if m:
                            try:
                                collected[field] = int(m.group())
                                matched_fields.append(field)
                                logger.debug("Enhanced stats (stat-box) matched %s=%s (label='%s', raw='%s')", field, collected[field], key_text, val_text)
                            except ValueError:
                                pass
                    elif ftype == 'float':
                        m = re.search(r'-?\d+[\.,]?\d*', val_text)
                        if m:
                            try:
                                collected[field] = float(m.group().replace(',', '.'))
                                matched_fields.append(field)
                                logger.debug("Enhanced stats (stat-box) matched %s=%s (label='%s', raw='%s')", field, collected[field], key_text, val_text)
                            except ValueError:
                                pass
                    break
        if not collected:
            logger.debug("No enhanced season stats extracted (rows=%d, stat_boxes=%d)", len(rows), len(stat_boxes))
            return None
        # Backfill legacy penalties field if only taken found
        if 'penalties' not in collected and 'penalties_taken' in collected:
            collected['penalties'] = collected['penalties_taken']
        logger.debug("Enhanced season stats aggregated fields=%s", sorted(matched_fields))
        return PlayerSeasonStats(**collected) if collected else None

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

    cfg = get_lexicon_config()
    indicators = [w.lower() for w in cfg.get_indicator_list('squad_page')] or ['squad']
    # Keep previous disallow list inline for now (könnte später in YAML url_filters rein)
    generic_disallowed = ['/bundesliga/spieler', '/en/bundesliga/players', '/de/bundesliga/spieler']
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

    def _normalize_color(self, raw: str) -> str:
        """Normalize CSS color definitions to hex if possible.

        Supports:
          - rgb(r, g, b)
          - #hex (returned lowercased)
          - plain color names (returned as-is)
        """
        raw = raw.strip()
        if raw.startswith('#'):
            return raw.lower()
        m = re.match(r'rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', raw, re.I)
        if m:
            r, g, b = (min(255, int(m.group(i))) for i in range(1,4))
            return f"#{r:02x}{g:02x}{b:02x}"
        return raw

    def _standardize_colors(self, ordered: list[str]) -> Dict[str, str]:
        """Assign semantic keys primary, secondary, tertiary based on order.

        Deduplicates while preserving order. If fewer than 3 colors present,
        only populate available keys. Ignores placeholders like 'transparent'.
        """
        result: Dict[str, str] = {}
        seen: set[str] = set()
        clean = [c for c in ordered if c and c.lower() not in ('transparent',)]
        for c in clean:
            if c in seen:
                continue
            seen.add(c)
        clean = [c for c in clean if c in seen]
        keys = ['primary', 'secondary', 'tertiary']
        for idx, c in enumerate(clean[:3]):
            result[keys[idx]] = c
        return result

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
            headless_env = os.getenv('BUNDESLIGA_PW_HEADLESS', '1')
            headless = headless_env not in ('0','false','False')
            self._pw = await async_playwright().start()
            self._pw_browser = await self._pw.chromium.launch(headless=headless, args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox', '--disable-dev-shm-usage'
            ])
            self._pw_page = await self._pw_browser.new_page()
            # Attach response listener once
            self._captured_club_json: list[dict] = []  # raw blobs only (legacy)
            self._captured_club_json_pairs: list[tuple[str, dict]] = []  # (url, blob) pairs for richer heuristics
            async def _on_response(resp):  # type: ignore
                try:
                    url = resp.url
                    ctype = resp.headers.get('content-type','')
                    if 'application/json' not in ctype:
                        return
                    # Fetch body (guard size)
                    text = await resp.text()
                    if not text or len(text) > 800_000:
                        return
                    txt = text.strip()
                    if not (txt.startswith('{') or txt.startswith('[')):
                        return
                    # Broaden capture: keep most JSON (site often calls indirect endpoints without /api/ pattern)
                    try:
                        data = json.loads(txt)
                    except Exception:
                        return
                    self._captured_club_json.append(data)
                    self._captured_club_json_pairs.append((url, data))
                except Exception:
                    pass
            self._pw_page.on('response', _on_response)  # type: ignore
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

    async def _fetch_page_dynamic(self, url: str) -> str:
        """Fetch page using Playwright (if enabled) else fallback to aiohttp.

        Uses full JS rendering when self._use_playwright is True. Includes a short wait for
        network idle attempts (best effort) and retries falling back to static fetch on failure.
        """
        if not self._use_playwright:
            return await self.fetch_page(url)
        # Ensure playwright started
        started = await self._ensure_playwright()
        if not started or not self._pw_page:
            return await self.fetch_page(url)
        try:
            # Reset captured JSON buffers for each navigation to avoid cross-club contamination
            try:
                self._captured_club_json.clear()
                self._captured_club_json_pairs.clear()
            except Exception:
                pass
            await self._pw_page.goto(url, wait_until='domcontentloaded', timeout=self.config.timeout * 1000)
            # Attempt cookie consent auto-accept (common patterns)
            try:
                for sel in ["button:has-text('Akzeptieren')", "button:has-text('Alle akzeptieren')", "button:has-text('Accept')", "#onetrust-accept-btn-handler", "button[title*='akzept']"]:
                    btn = await self._pw_page.query_selector(sel)  # type: ignore
                    if btn:
                        await btn.click()  # type: ignore
                        await asyncio.sleep(0.2)
                        break
            except Exception:
                pass
            # Try staged waits to allow Angular hydration: first small delay, then wait for either
            # window.__NUXT__ injection or .factTable labels to appear.
            # Initial small delay then scroll attempts for lazy content
            await asyncio.sleep(0.5)
            try:
                # Incremental scroll to bottom to trigger lazy-loaded API calls
                scroll_script = """
                let total=0; let step=window.innerHeight*0.6; let h=document.body.scrollHeight;
                window.scrollBy(0, step); total+=step; h=document.body.scrollHeight;
                return {height:h, scrolled:total};
                """
                for _ in range(5):
                    await self._pw_page.evaluate(scroll_script)  # type: ignore
                    await asyncio.sleep(0.35)
            except Exception:
                pass
            debug = os.getenv('BUNDESLIGA_SCRAPER_DEBUG') in ('1','true','True')
            # Poll for dynamic selectors / hydration up to ~3 seconds total
            wanted_selectors = ['.factTable .label', '.factTable .value', '.club-detail .profile .factTable']
            max_attempts = 8
            for attempt in range(max_attempts):
                content = await self._pw_page.content()
                # Broaden hydration detection patterns
                if any(marker in content for marker in ['window.__NUXT__','window.__INITIAL_STATE__','window.__DATA__','window.__STORE__']):
                    break
                if any(sel in content for sel in ['factTable', 'clubColor']):
                    # Quick DOM based heuristic: see if at least one label/value pair present
                    if re.search(r'class="[^"]*label[^"]*"', content) and re.search(r'class="[^"]*value[^"]*"', content):
                        break
                await asyncio.sleep(0.4)
            # Final content grab (after polling)
            content = await self._pw_page.content()
            if debug and not any(x in content for x in ['window.__NUXT__','window.__INITIAL_STATE__','window.__DATA__']):
                logger.info("Playwright fetch (post-wait): no hydration marker in %s (len=%d)", url, len(content))
            # If still missing core hydration, attempt enrichment from captured network JSON blobs
            hydration_present = any(x in content for x in ['window.__NUXT__','window.__INITIAL_STATE__','window.__DATA__'])
            if not hydration_present and getattr(self, '_captured_club_json', None):
                try:
                    # Prefer targeted search across (url, blob) pairs for structures containing club identity markers.
                    candidate: Optional[dict] = None
                    keys_interest = {'stadium','founded','foundationYear','officialName','clubColors','contact','address','venue'}
                    # Derive slug tokens from URL for heuristic filtering
                    slug = url.rstrip('/').rsplit('/',1)[-1].lower()
                    slug_tokens = [t for t in re.split(r'[-_]+', slug) if t and t not in {'de','clubs','club'}]
                    def walk(obj):  # nested search
                        nonlocal candidate
                        if candidate is not None:
                            return
                        if isinstance(obj, dict):
                            if keys_interest.intersection(obj.keys()) and any(k in obj for k in ('officialName','clubColors','venue','stadium')):
                                candidate = obj
                                return
                            for v in obj.values():
                                walk(v)
                        elif isinstance(obj, list):
                            for it in obj:
                                walk(it)
                    # First pass: prefer blobs whose JSON string contains slug tokens
                    pairs = list(getattr(self, '_captured_club_json_pairs', []))
                    for prefer_slug in (True, False):
                        for _u, blob in reversed(pairs):
                            if prefer_slug:
                                try:
                                    blob_str_low = json.dumps(blob, ensure_ascii=False).lower()
                                    if not all(tok in blob_str_low for tok in slug_tokens[:1]):  # require at least first token
                                        continue
                                except Exception:
                                    continue
                            walk(blob)
                            if candidate is not None:
                                break
                        if candidate is not None:
                            break
                    if candidate is None:
                        # fallback to previous broad heuristic
                        for blob in self._captured_club_json:
                            blob_str = json.dumps(blob, ensure_ascii=False)
                            if any(k in blob_str for k in keys_interest):
                                try:
                                    candidate = blob
                                    break
                                except Exception:
                                    continue
                    if candidate is not None:
                        # Validate candidate actually corresponds to this club slug to avoid Augsburg duplication leak.
                        def cand_matches(slug_tokens: list[str], cand: dict) -> bool:
                            try:
                                name_val = ''
                                # Possible name sources
                                if isinstance(cand.get('name'), dict):
                                    # choose longest textual field
                                    name_candidates = [v for v in cand['name'].values() if isinstance(v, str)]
                                    if name_candidates:
                                        name_val = max(name_candidates, key=len).lower()
                                elif isinstance(cand.get('name'), str):
                                    name_val = cand['name'].lower()
                                tlc = str(cand.get('threeLetterCode','')).lower()
                                # Heuristic: at least one slug token must appear in name OR tlc starts with first token letters
                                if slug_tokens:
                                    token_hit = any(tok in name_val for tok in slug_tokens if len(tok) > 2)
                                else:
                                    token_hit = True
                                if not token_hit and slug_tokens and tlc:
                                    token_hit = tlc.startswith(slug_tokens[0][:3])
                                return bool(token_hit)
                            except Exception:
                                return False
                        if not cand_matches(slug_tokens, candidate):
                            if debug:
                                logger.info("Discarded synthetic candidate for %s due to slug mismatch", url)
                        else:
                            # Avoid reusing the exact same candidate object across multiple clubs (track by id if available)
                            cand_id = candidate.get('id') or candidate.get('clubId') or candidate.get('externalId')
                            reuse_ok = True
                            if getattr(self, '_last_synthetic_ids', None) is None:
                                self._last_synthetic_ids = set()
                            if cand_id and cand_id in self._last_synthetic_ids:
                                reuse_ok = False
                            if reuse_ok:
                                if cand_id:
                                    self._last_synthetic_ids.add(cand_id)
                                synth = json.dumps({'data': {'club': candidate}}, ensure_ascii=False)
                                content += f"\n<script>window.__NUXT__={synth}</script>"
                                if debug:
                                    # Log a shallow summary of keys present in candidate for transparency
                                    logger.info("Injected synthetic hydration for %s using captured JSON (top-level keys: %s)", url, list(candidate.keys())[:12])
                            else:
                                if debug:
                                    logger.info("Skipped candidate reuse for %s (id=%s)", url, cand_id)
                    else:
                        # Direct JSON extraction fallback: append small script with extracted micro-fields for parser
                        try:
                            extracted: dict[str, Any] = {}
                            seen_objs: set[int] = set()

                            def assign_address(addr: dict):
                                # Accept common address schema variants
                                street = addr.get('street') or addr.get('streetName')
                                house_no = addr.get('houseNumber') or addr.get('number')
                                if street and isinstance(street, str):
                                    full_street = street.strip()
                                    if house_no and isinstance(house_no, (str,int)):
                                        full_street = f"{full_street} {house_no}".strip()
                                    if full_street and 'street_address' not in extracted:
                                        extracted['street_address'] = full_street
                                pc = addr.get('postalCode') or addr.get('zip') or addr.get('zipCode')
                                if pc and isinstance(pc, (str,int)) and 'postal_code' not in extracted:
                                    pc_s = str(pc).strip()
                                    if re.match(r'^\d{4,5}$', pc_s):
                                        extracted['postal_code'] = pc_s
                                city = addr.get('city') or addr.get('town') or addr.get('locality')
                                if city and isinstance(city, str) and 'city' not in extracted:
                                    extracted['city'] = city.strip()

                            def walk_assign(o):
                                oid = id(o)
                                if oid in seen_objs:
                                    return
                                seen_objs.add(oid)
                                if isinstance(o, dict):
                                    # Gather directly if keys exist
                                    if 'founded' in o and 'founded_year' not in extracted:
                                        fv = o['founded']
                                        if isinstance(fv,(int,str)) and re.match(r'^(19|20)\d{2}$', str(fv)):
                                            try:
                                                extracted['founded_year'] = int(str(fv))
                                            except ValueError:
                                                pass
                                    if 'stadium' in o and isinstance(o['stadium'], dict):
                                        st = o['stadium']
                                        if 'name' in st and 'stadium' not in extracted and isinstance(st['name'], str):
                                            extracted['stadium'] = st['name']
                                        if 'capacity' in st and 'stadium_capacity' not in extracted:
                                            cap_raw = re.sub(r'[^0-9]','', str(st['capacity']))
                                            if cap_raw.isdigit():
                                                extracted['stadium_capacity'] = int(cap_raw)
                                        # Address nested inside stadium
                                        if 'address' in st and isinstance(st['address'], dict):
                                            assign_address(st['address'])
                                    # Venue variant
                                    if 'venue' in o and isinstance(o['venue'], dict):
                                        ven = o['venue']
                                        if 'address' in ven and isinstance(ven['address'], dict):
                                            assign_address(ven['address'])
                                    # Generic address key
                                    if 'address' in o and isinstance(o['address'], dict):
                                        assign_address(o['address'])
                                    if 'contact' in o and isinstance(o['contact'], dict):
                                        for ck in ['phone','fax','email','website']:
                                            if ck in o['contact'] and ck not in extracted and isinstance(o['contact'][ck], str):
                                                val = o['contact'][ck].strip()
                                                if ck == 'website':
                                                    val = self._normalize_website(val)
                                                extracted[ck] = val
                                    # officialName fallback
                                    if 'officialName' in o and 'official_name' not in extracted and isinstance(o['officialName'], str):
                                        extracted['official_name'] = o['officialName'].strip()
                                    # Colors minimal variant (array of hex codes)
                                    if 'clubColors' in o and 'colors' not in extracted:
                                        cc = o['clubColors']
                                        if isinstance(cc, (list, tuple)):
                                            ordered = [self._normalize_color(str(c)) for c in cc if isinstance(c,(str,int))]
                                            if ordered:
                                                extracted['colors'] = self._standardize_colors(ordered)
                                    for v in o.values():
                                        walk_assign(v)
                                elif isinstance(o, list):
                                    for it in o:
                                        walk_assign(it)

                            # Only inspect a limited tail of captured blobs for performance
                            for _, blob in getattr(self, '_captured_club_json_pairs', [])[-8:]:
                                walk_assign(blob)
                                # Early break if we already have a decent set of fields
                                if len(extracted) >= 7:
                                    break
                            if extracted:
                                extracted_json = json.dumps(extracted, ensure_ascii=False)
                                content += "\n<script>window.__NUXT__={" + f"\"data\":{{\"club\":{extracted_json}}}" + "</script>"
                                if debug:
                                    logger.info("Injected minimal synthetic hydration (direct extraction) for %s: %s", url, sorted(extracted.keys()))
                        except Exception:
                            if debug:
                                logger.info("Minimal synthetic extraction failed for %s", url)
                            pass
                    # Optional raw dump for diagnostics
                    if os.getenv('BUNDESLIGA_DUMP_JSON') in ('1','true','True') and self._captured_club_json_pairs:
                        try:
                            from pathlib import Path
                            slug = url.rstrip('/').rsplit('/',1)[-1]
                            dump_dir = Path('reports/debug_json') / slug
                            dump_dir.mkdir(parents=True, exist_ok=True)
                            for idx,(u, blob) in enumerate(self._captured_club_json_pairs[-10:]):  # last 10
                                with (dump_dir / f"blob_{idx}.json").open('w', encoding='utf-8') as f:
                                    json.dump({'url': u, 'data': blob}, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                except Exception:
                    pass
            return content
        except Exception as e:
            logger.warning("Playwright navigation failed for %s (%s) - falling back to static fetch", url, e)
            try:
                return await self.fetch_page(url)
            except Exception:
                raise

    # -------------------- Extra broad regex fallback for div-based fact table (no spans) --------------------
    def _regex_div_fact_table_fallback(self, html: str, data: Dict[str, Any]):  # pragma: no cover
        """Capture label/value pairs where structure uses generic <div class="label"> and <div class="value"> blocks.

        This complements _regex_fact_table_fallback which targets span pairs. We iterate sequentially through
        occurrences to approximate row grouping.
        """
        try:
            # Find all label/value occurrences in order
            pattern = re.compile(r'<div[^>]*class="[^"]*label[^"]*"[^>]*>(?P<label>.*?)</div>\s*<div[^>]*class="[^"]*value[^"]*"[^>]*>(?P<value>.*?)</div>', re.I|re.DOTALL)
            for m in pattern.finditer(html):
                label_raw = re.sub(r'<[^>]+>', '', m.group('label')).strip()
                value_raw = re.sub(r'<[^>]+>', '', m.group('value')).strip()
                if not label_raw or not value_raw:
                    continue
                # Reuse same mapping logic as span fallback
                if re.search(r'Offizieller Clubname|Official club name', label_raw, re.I) and not data.get('official_name'):
                    data['official_name'] = value_raw
                elif re.search(r'Gegründet|Founded', label_raw, re.I) and not data.get('founded_year'):
                    ym = re.search(r'(19|20)\d{2}', value_raw)
                    if ym:
                        try:
                            data['founded_year'] = int(ym.group())
                        except ValueError:
                            pass
                elif re.search(r'Clubfarben|Club colors', label_raw, re.I) and not data.get('colors'):
                    color_divs = re.findall(r'background-color:\s*([^;]+);?', m.group(0))
                    ordered = [self._normalize_color(c.strip()) for c in color_divs]
                    if ordered:
                        data['colors'] = self._standardize_colors(ordered)
                elif re.search(r'Straße|Strasse|Address|Adresse', label_raw, re.I) and not data.get('street_address'):
                    data['street_address'] = value_raw
                elif re.search(r'Stadt|City|Ort', label_raw, re.I) and not data.get('city'):
                    pc_city = re.match(r'(\d{4,5})\s+(.+)', value_raw)
                    if pc_city:
                        data['postal_code'] = pc_city.group(1)
                        data['city'] = pc_city.group(2)
                    else:
                        data['city'] = value_raw
                elif re.search(r'Telefon|Phone', label_raw, re.I) and not data.get('phone'):
                    data['phone'] = value_raw
                elif re.search(r'Fax', label_raw, re.I) and not data.get('fax'):
                    data['fax'] = value_raw
                elif re.search(r'Website', label_raw, re.I) and not data.get('website'):
                    data['website'] = value_raw
                elif re.search(r'Email|E-Mail', label_raw, re.I) and not data.get('email'):
                    data['email'] = value_raw
                elif re.search(r'Anfahrt|Map', label_raw, re.I) and not data.get('map_url'):
                    # Extract potential link inside the value block
                    href_m = re.search(r'href="(.*?)"', m.group(0))
                    if href_m:
                        data['map_url'] = href_m.group(1)
        except Exception:
            pass


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
    import sys, os
    # Align event loop policy choice with run script: Proactor when Playwright requested.
    if sys.platform.startswith('win'):
        use_playwright = os.getenv('BUNDESLIGA_USE_PLAYWRIGHT') in ('1','true','True')
        try:
            if use_playwright and hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]
            elif not use_playwright and hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
        except Exception:
            pass
    asyncio.run(_test())
