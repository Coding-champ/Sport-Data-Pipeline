"""
Enhanced Bundesliga Club & Squad Scraper

Implements comprehensive workflow for scraping:
1. Club overviews from https://www.bundesliga.com/de/bundesliga/clubs
2. Squad listings for each club 
3. Individual player data including career statistics

Usage:
    scraper = BundesligaClubScraper(db_manager)
    await scraper.initialize()
    try:
        clubs = await scraper.scrape_clubs()
        squads = await scraper.scrape_squads(clubs)
        players = await scraper.scrape_players(squads)
    finally:
        await scraper.cleanup()
"""

from __future__ import annotations

import asyncio
import json
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Any, Optional, List, Dict, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, field_validator

from .base import BaseScraper, ScrapingConfig
from ...domain.models import Club, Player, Position, Footedness


# =============================================================================
# 1. CONFIGURATION & DATA MODELS
# =============================================================================

@dataclass
class BundesligaClubScraperConfig(ScrapingConfig):
    """Configuration for Bundesliga club scraper"""
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
    """Model for player career statistics"""
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
    """Model for current season player statistics"""
    appearances: Optional[int] = None
    starts: Optional[int] = None
    minutes_played: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    clean_sheets: Optional[int] = None  # for goalkeepers
    saves: Optional[int] = None  # for goalkeepers
    pass_accuracy: Optional[float] = None
    shots_on_target: Optional[int] = None
    tackles: Optional[int] = None
    interceptions: Optional[int] = None
    aerial_duels_won: Optional[int] = None
    source_url: Optional[str] = None


class EnhancedPlayer(BaseModel):
    """Enhanced player model with additional scraped data"""
    # Basic player info (matches domain Player model)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    nationality: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: Optional[Footedness] = None
    photo_url: Optional[HttpUrl] = None
    
    # Additional scraped fields
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    market_value: Optional[str] = None
    contract_until: Optional[date] = None
    previous_clubs: Optional[List[str]] = None
    
    # Statistics
    current_season_stats: Optional[PlayerSeasonStats] = None
    career_stats: Optional[List[PlayerCareerStats]] = None
    
    # Source information
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None

    @field_validator('birth_date', 'contract_until', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Parse date from string if needed"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
            except:
                return None
        return v


class EnhancedClub(BaseModel):
    """Enhanced club model with additional scraped data"""
    # Basic club info (matches domain Club model) 
    name: str
    short_name: Optional[str] = None
    city: Optional[str] = None
    founded_year: Optional[int] = None
    logo_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    
    # Additional scraped fields
    stadium: Optional[str] = None
    stadium_capacity: Optional[int] = None
    coach: Optional[str] = None
    colors: Optional[Dict[str, str]] = None
    
    # Source information
    source_url: Optional[str] = None
    squad_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None


# =============================================================================
# 2. MAIN SCRAPER CLASS
# =============================================================================

class BundesligaClubScraper(BaseScraper):
    """Enhanced Bundesliga scraper for clubs, squads, and players"""
    
    name = "bundesliga_club"
    
    def __init__(self, db_manager):
        config = BundesligaClubScraperConfig()
        super().__init__(config, db_manager, self.name)
        
    async def scrape_data(self) -> dict[str, Any]:
        """Main method to scrape all data (clubs, squads, players)"""
        self.logger.info("Starting comprehensive Bundesliga scraping")
        
        # Stage 1: Scrape club overviews
        clubs = await self.scrape_clubs()
        self.logger.info(f"Found {len(clubs)} clubs")
        
        # Stage 2: Scrape squad data for each club
        all_squads = {}
        for club in clubs:
            if club.squad_url:
                try:
                    squad = await self.scrape_squad(club.squad_url, club.name)
                    all_squads[club.name] = squad
                    await self.anti_detection.random_delay(self.config.delay_range)
                except Exception as e:
                    self.logger.error(f"Failed to scrape squad for {club.name}: {e}")
                    continue
        
        # Stage 3: Scrape individual player data
        all_players = {}
        total_players = sum(len(squad) for squad in all_squads.values())
        self.logger.info(f"Scraping {total_players} individual players")
        
        player_count = 0
        for club_name, player_urls in all_squads.items():
            club_players = []
            for player_url in player_urls:
                try:
                    player = await self.scrape_player(player_url)
                    if player:
                        club_players.append(player)
                        player_count += 1
                        
                        # Log progress every 10 players
                        if player_count % 10 == 0:
                            self.logger.info(f"Scraped {player_count}/{total_players} players")
                    
                    await self.anti_detection.random_delay(self.config.delay_range)
                except Exception as e:
                    self.logger.error(f"Failed to scrape player {player_url}: {e}")
                    continue
            
            all_players[club_name] = club_players
            
        return {
            'clubs': clubs,
            'squads': all_squads, 
            'players': all_players,
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'total_clubs': len(clubs),
            'total_players': player_count
        }
    
    async def scrape_clubs(self) -> List[EnhancedClub]:
        """Stage 1: Scrape club overview from main clubs page"""
        clubs_url = "https://www.bundesliga.com/de/bundesliga/clubs"
        
        self.logger.info(f"Fetching clubs from: {clubs_url}")
        html = await self.fetch_page(clubs_url)
        soup = self.parse_html(html)
        
        club_links = self._extract_club_links(soup, clubs_url)
        self.logger.info(f"Found {len(club_links)} club links")
        
        clubs = []
        for i, club_url in enumerate(club_links, 1):
            try:
                self.logger.debug(f"Scraping club {i}/{len(club_links)}: {club_url}")
                club = await self._scrape_single_club(club_url)
                if club:
                    clubs.append(club)
                
                await self.anti_detection.random_delay(self.config.delay_range)
                
            except Exception as e:
                self.logger.error(f"Failed to scrape club {club_url}: {e}")
                continue
                
        return clubs
    
    async def scrape_squad(self, squad_url: str, club_name: str) -> List[str]:
        """Stage 2: Scrape squad page to get player URLs"""
        self.logger.debug(f"Fetching squad for {club_name}: {squad_url}")
        
        html = await self.fetch_page(squad_url)
        soup = self.parse_html(html)
        
        return self._extract_player_links(soup, squad_url)
    
    async def scrape_player(self, player_url: str) -> Optional[EnhancedPlayer]:
        """Stage 3: Scrape individual player data"""
        try:
            html = await self.fetch_page(player_url)
            soup = self.parse_html(html)
            
            return self._parse_player_data(soup, player_url)
            
        except Exception as e:
            self.logger.error(f"Failed to scrape player {player_url}: {e}")
            return None

    # =============================================================================
    # 3. HELPER METHODS FOR DATA EXTRACTION
    # =============================================================================
    
    def _extract_club_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract club page URLs from main clubs page"""
        links = set()
        
        # Pattern for Bundesliga club URLs
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Match club URLs like /de/bundesliga/clubs/fc-augsburg
            if re.search(r"/de/(?:bundesliga|2-bundesliga)/(?:clubs|vereine)/[a-z0-9\-]+", href):
                full_url = urljoin(base_url, href)
                # Avoid overview pages
                if not re.search(r"/(clubs|vereine)/?$", urlparse(full_url).path):
                    links.add(full_url)
        
        return sorted(list(links))
    
    async def _scrape_single_club(self, club_url: str) -> Optional[EnhancedClub]:
        """Scrape data for a single club page"""
        try:
            html = await self.fetch_page(club_url)
            soup = self.parse_html(html)
            
            # Extract basic club information
            club_data = self._extract_club_data(soup, club_url)
            if not club_data.get('name'):
                return None
                
            # Look for squad/team page URL
            squad_url = self._find_squad_url(soup, club_url)
            
            return EnhancedClub(
                name=club_data['name'],
                short_name=club_data.get('short_name'),
                city=club_data.get('city'),
                founded_year=club_data.get('founded_year'),
                logo_url=club_data.get('logo_url'),
                website=club_data.get('website'),
                stadium=club_data.get('stadium'),
                stadium_capacity=club_data.get('stadium_capacity'),
                coach=club_data.get('coach'),
                colors=club_data.get('colors'),
                source_url=club_url,
                squad_url=squad_url,
                scraped_at=datetime.now(timezone.utc),
                external_ids={'bundesliga_url': club_url}
            )
            
        except Exception as e:
            self.logger.error(f"Error scraping club {club_url}: {e}")
            return None

    def _extract_club_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract club information from club page"""
        data = {}
        
        # Club name - try multiple sources
        data['name'] = (
            self._get_text_by_selector(soup, 'h1.club-name, h1, .club-header h1') or
            self._get_meta_content(soup, 'og:title') or
            self._extract_from_title(soup)
        )
        
        # Stadium info
        data['stadium'] = self._find_labeled_value(soup, ['Stadium', 'Stadion', 'Venue'])
        
        # Coach info
        data['coach'] = self._find_labeled_value(soup, ['Coach', 'Trainer', 'Head Coach'])
        
        # Founded year
        founded_text = self._find_labeled_value(soup, ['Founded', 'Gegründet', 'Est.', 'Since'])
        if founded_text:
            match = re.search(r'\b(19|20)\d{2}\b', founded_text)
            if match:
                try:
                    data['founded_year'] = int(match.group())
                except ValueError:
                    pass
        
        # City (often in address or location info)
        data['city'] = self._find_labeled_value(soup, ['City', 'Stadt', 'Location', 'Ort'])
        
        # Logo URL
        logo = soup.find('img', {'alt': re.compile(r'logo|emblem', re.I)}) or soup.find('img', class_=re.compile(r'logo|emblem'))
        if logo and logo.get('src'):
            data['logo_url'] = urljoin(url, logo['src'])
        
        # Stadium capacity
        capacity_text = self._find_labeled_value(soup, ['Capacity', 'Kapazität', 'Seats'])
        if capacity_text:
            match = re.search(r'(\d{1,3}(?:[,\.]\d{3})*)', capacity_text.replace('.', '').replace(',', ''))
            if match:
                try:
                    data['stadium_capacity'] = int(match.group().replace(',', '').replace('.', ''))
                except ValueError:
                    pass
        
        return data
    
    def _find_squad_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find squad/team page URL from club page"""
        # Look for links containing squad, team, kader, etc.
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            text = a.get_text().lower()
            
            if any(term in href or term in text for term in ['squad', 'kader', 'team', 'mannschaft', 'spieler']):
                return urljoin(base_url, a['href'])
        
        # Fallback: construct likely squad URL
        if '/clubs/' in base_url:
            return base_url.rstrip('/') + '/squad' 
        return None
    
    def _extract_player_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract player profile URLs from squad page"""
        links = set()
        
        # First, try to find player links within specific squad/roster containers
        squad_containers = soup.find_all(['div', 'section', 'ul', 'table'], 
                                       class_=re.compile(r'(squad|roster|player|team|lineup|kader|mannschaft)', re.I))
        
        if squad_containers:
            # Look within squad containers first
            for container in squad_containers:
                for a in container.find_all('a', href=True):
                    href = a['href']
                    if re.search(r'/de/bundesliga/spieler/[a-z0-9\-]+', href):
                        full_url = urljoin(base_url, href)
                        links.add(full_url)
        
        # If no squad containers found or no links within them, fall back to a more targeted approach
        if not links:
            # Look for player links that are likely to be in squad context
            # This includes links with player names in nearby text or within list items
            for a in soup.find_all('a', href=True):
                href = a['href']
                
                if re.search(r'/de/bundesliga/spieler/[a-z0-9\-]+', href):
                    # Check if the link is within a list item, table row, or card-like structure
                    parent = a.find_parent(['li', 'tr', 'div'])
                    if parent:
                        # Check if parent contains player-like info (name, number, position indicators)
                        parent_text = parent.get_text().lower()
                        # Look for indicators this is actually a player listing
                        if any(indicator in parent_text for indicator in ['#', 'position', 'pos', 'age', 'nationality']):
                            full_url = urljoin(base_url, href)
                            links.add(full_url)
        
        # If still no links found, use the original broad approach but with a warning
        if not links:
            self.logger.warning(f"No squad-specific containers found, using broad search for {base_url}")
            for a in soup.find_all('a', href=True):
                href = a['href']
                if re.search(r'/de/bundesliga/spieler/[a-z0-9\-]+', href):
                    full_url = urljoin(base_url, href)
                    links.add(full_url)
        
        # Log if we found an unusually high number of players (likely indicates over-broad matching)
        if len(links) > 50:
            self.logger.warning(f"Found {len(links)} player links for squad page - this seems too high and may indicate over-broad matching")
        
        return sorted(list(links))
    
    def _parse_player_data(self, soup: BeautifulSoup, url: str) -> Optional[EnhancedPlayer]:
        """Parse player data from individual player page"""
        try:
            # Extract basic player info
            player_data = self._extract_player_basic_info(soup)
            
            # Extract current season stats
            season_stats = self._extract_player_season_stats(soup)
            
            # Extract career history
            career_stats = self._extract_player_career_stats(soup)
            
            if not player_data.get('first_name') and not player_data.get('last_name'):
                return None
                
            return EnhancedPlayer(
                first_name=player_data.get('first_name'),
                last_name=player_data.get('last_name'),
                birth_date=player_data.get('birth_date'),
                birth_place=player_data.get('birth_place'),
                nationality=player_data.get('nationality'),
                height_cm=player_data.get('height_cm'),
                weight_kg=player_data.get('weight_kg'),
                preferred_foot=player_data.get('preferred_foot'),
                photo_url=player_data.get('photo_url'),
                position=player_data.get('position'),
                shirt_number=player_data.get('shirt_number'),
                market_value=player_data.get('market_value'),
                contract_until=player_data.get('contract_until'),
                previous_clubs=player_data.get('previous_clubs'),
                current_season_stats=season_stats,
                career_stats=career_stats,
                source_url=url,
                scraped_at=datetime.now(timezone.utc),
                external_ids={'bundesliga_url': url}
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing player data from {url}: {e}")
            return None

    def _extract_player_basic_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic player information"""
        data = {}
        
        # Player name
        name_text = (
            self._get_text_by_selector(soup, 'h1.player-name, h1, .player-header h1') or
            self._get_meta_content(soup, 'og:title') or
            ''
        )
        
        if name_text:
            # Split first and last name
            parts = name_text.strip().split()
            if parts:
                data['first_name'] = parts[0]
                if len(parts) > 1:
                    data['last_name'] = ' '.join(parts[1:])
        
        # Position
        data['position'] = self._find_labeled_value(soup, ['Position', 'Pos.'])
        
        # Shirt number
        number_text = self._find_labeled_value(soup, ['Number', 'Nummer', 'Nr.', '#'])
        if number_text:
            match = re.search(r'\d+', number_text)
            if match:
                try:
                    data['shirt_number'] = int(match.group())
                except ValueError:
                    pass
        
        # Birth date
        birth_text = self._find_labeled_value(soup, ['Born', 'Birth', 'Geboren', 'Date of Birth'])
        if birth_text:
            data['birth_date'] = self._parse_date_string(birth_text)
        
        # Birth place
        data['birth_place'] = self._find_labeled_value(soup, ['Birthplace', 'Geburtsort', 'Place of Birth'])
        
        # Nationality
        data['nationality'] = self._find_labeled_value(soup, ['Nationality', 'Nationalität', 'Country'])
        
        # Height
        height_text = self._find_labeled_value(soup, ['Height', 'Größe', 'Size'])
        if height_text:
            match = re.search(r'(\d+)\s*cm', height_text)
            if match:
                try:
                    data['height_cm'] = int(match.group(1))
                except ValueError:
                    pass
        
        # Weight  
        weight_text = self._find_labeled_value(soup, ['Weight', 'Gewicht'])
        if weight_text:
            match = re.search(r'(\d+)\s*kg', weight_text)
            if match:
                try:
                    data['weight_kg'] = int(match.group(1))
                except ValueError:
                    pass
        
        # Preferred foot
        foot_text = self._find_labeled_value(soup, ['Foot', 'Fuß', 'Preferred Foot'])
        if foot_text and foot_text.lower() in ['left', 'right', 'both']:
            data['preferred_foot'] = Footedness(foot_text.lower())
        
        # Market value
        data['market_value'] = self._find_labeled_value(soup, ['Market Value', 'Marktwert', 'Value'])
        
        # Contract until
        contract_text = self._find_labeled_value(soup, ['Contract', 'Vertrag', 'Contract until'])
        if contract_text:
            data['contract_until'] = self._parse_date_string(contract_text)
        
        # Photo URL
        photo = soup.find('img', {'alt': re.compile(r'player|spieler', re.I)}) or soup.find('img', class_=re.compile(r'player|portrait'))
        if photo and photo.get('src'):
            photo_src = photo['src']
            # Convert relative URLs to absolute URLs
            if photo_src.startswith('/'):
                data['photo_url'] = f"https://www.bundesliga.com{photo_src}"
            else:
                data['photo_url'] = photo_src
        
        return data
    
    def _extract_player_season_stats(self, soup: BeautifulSoup) -> Optional[PlayerSeasonStats]:
        """Extract current season statistics"""
        stats = {}
        
        # Look for statistics section
        stats_section = soup.find(['section', 'div'], class_=re.compile(r'stats|statistics|season'))
        if not stats_section:
            return None
            
        # Extract common statistics
        stat_mapping = {
            'appearances': ['Appearances', 'Games', 'Matches', 'Spiele', 'Einsätze'],
            'goals': ['Goals', 'Tore'],
            'assists': ['Assists', 'Vorlagen'],
            'minutes_played': ['Minutes', 'Minuten'],
            'yellow_cards': ['Yellow Cards', 'Gelbe Karten', 'YC'],
            'red_cards': ['Red Cards', 'Rote Karten', 'RC'],
        }
        
        for stat_key, labels in stat_mapping.items():
            value_text = self._find_labeled_value(stats_section, labels)
            if value_text:
                match = re.search(r'\d+', value_text.replace(',', ''))
                if match:
                    try:
                        stats[stat_key] = int(match.group())
                    except ValueError:
                        pass
        
        return PlayerSeasonStats(**stats) if stats else None
    
    def _extract_player_career_stats(self, soup: BeautifulSoup) -> List[PlayerCareerStats]:
        """Extract career history statistics"""
        career_stats = []
        
        # Look for career/history table
        career_table = soup.find('table', class_=re.compile(r'career|history|statistik'))
        if not career_table:
            return []
            
        # Parse table rows
        for row in career_table.find_all('tr')[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue
                
            try:
                season_stats = PlayerCareerStats(
                    season=cells[0].get_text(strip=True),
                    team=cells[1].get_text(strip=True) if len(cells) > 1 else None,
                    league=cells[2].get_text(strip=True) if len(cells) > 2 else None,
                )
                
                # Extract numeric stats from remaining cells
                for i, cell in enumerate(cells[3:], 3):
                    text = cell.get_text(strip=True)
                    if text.isdigit():
                        value = int(text)
                        # Map to appropriate field based on position
                        if i == 3:
                            season_stats.appearances = value
                        elif i == 4:
                            season_stats.goals = value
                        elif i == 5:
                            season_stats.assists = value
                        
                career_stats.append(season_stats)
                
            except Exception as e:
                self.logger.debug(f"Failed to parse career row: {e}")
                continue
                
        return career_stats
    
    # =============================================================================
    # 4. UTILITY METHODS
    # =============================================================================
    
    def _get_text_by_selector(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Get text content by CSS selector"""
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else None
    
    def _get_meta_content(self, soup: BeautifulSoup, property_name: str) -> Optional[str]:
        """Get meta tag content"""
        meta = soup.find('meta', {'property': property_name}) or soup.find('meta', {'name': property_name})
        return meta.get('content') if meta else None
    
    def _extract_from_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract club name from page title"""
        title = soup.title
        if title:
            title_text = title.get_text()
            # Remove common suffixes
            for suffix in [' - Bundesliga', ' | Bundesliga', ' - Official Website']:
                title_text = title_text.replace(suffix, '')
            return title_text.strip()
        return None
    
    def _find_labeled_value(self, soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
        """Find value by label using various patterns"""
        # Try definition lists first
        for label in labels:
            dt = soup.find('dt', string=re.compile(rf'^{re.escape(label)}\s*:?\s*$', re.I))
            if dt:
                dd = dt.find_next_sibling('dd')
                if dd:
                    return dd.get_text(strip=True)
        
        # Try label:value patterns in text
        text = soup.get_text()
        for label in labels:
            pattern = rf'{re.escape(label)}\s*:\s*([^\n\r]+)'
            match = re.search(pattern, text, re.I)
            if match:
                value = match.group(1).strip()
                # Clean up common trailing text
                for delimiter in [' |', '©', 'Watch', 'Privacy']:
                    if delimiter in value:
                        value = value.split(delimiter)[0].strip()
                return value
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """Parse date from various string formats"""
        if not date_str:
            return None
            
        # Common date patterns
        patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{4})',  # DD/MM/YYYY or DD.MM.YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',        # YYYY-MM-DD
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',        # DD Month YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if '/' in date_str or '.' in date_str:
                        day, month, year = match.groups()
                        return date(int(year), int(month), int(day))
                    elif '-' in date_str:
                        year, month, day = match.groups()
                        return date(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    continue
                    
        return None


# =============================================================================
# 5. CLI FOR TESTING
# =============================================================================

async def _test_scraper():
    """Simple test function"""
    from src.database.manager import DatabaseManager
    
    # Create mock database manager for testing
    class MockDB:
        async def bulk_insert(self, table, data, conflict_resolution):
            print(f"Would insert {len(data)} records into {table}")
    
    db = MockDB()
    scraper = BundesligaClubScraper(db_manager=db)
    
    await scraper.initialize()
    try:
        # Test club scraping only
        clubs = await scraper.scrape_clubs()
        print(f"\nFound {len(clubs)} clubs:")
        for club in clubs[:3]:  # Show first 3
            print(f"- {club.name} ({club.source_url})")
            if club.squad_url:
                print(f"  Squad URL: {club.squad_url}")
        
        # Test squad scraping for first club
        if clubs and clubs[0].squad_url:
            print(f"\nTesting squad scraping for {clubs[0].name}...")
            players = await scraper.scrape_squad(clubs[0].squad_url, clubs[0].name)
            print(f"Found {len(players)} player URLs")
            
            # Test player scraping for first few players
            if players:
                print(f"\nTesting player scraping...")
                for i, player_url in enumerate(players[:2]):  # Just test 2 players
                    player = await scraper.scrape_player(player_url)
                    if player:
                        print(f"- {player.first_name} {player.last_name} ({player.position})")
                    
    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    import sys
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_test_scraper())