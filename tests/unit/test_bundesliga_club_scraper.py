"""
Unit tests for BundesligaClubScraper
"""

import pytest
import asyncio
from datetime import date, datetime
from unittest.mock import Mock, AsyncMock, patch
from bs4 import BeautifulSoup

from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import (
    BundesligaClubScraper,
    EnhancedClub,
    EnhancedPlayer,
    PlayerSeasonStats,
    PlayerCareerStats
)


class TestBundesligaClubScraper:
    """Test cases for BundesligaClubScraper"""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager"""
        db = Mock()
        db.bulk_insert = AsyncMock()
        return db
    
    @pytest.fixture
    def scraper(self, mock_db_manager):
        """Create scraper instance with mock database"""
        return BundesligaClubScraper(mock_db_manager)
        

    def test_extract_club_links(self, scraper, sample_clubs_html):
        """Test extraction of club links from clubs overview page"""
        soup = BeautifulSoup(sample_clubs_html, 'html.parser')
        base_url = "https://www.bundesliga.com/de/bundesliga/clubs"
        
        links = scraper._extract_club_links(soup, base_url)
        
        assert len(links) == 3
        assert "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen" in links
        assert "https://www.bundesliga.com/de/bundesliga/clubs/borussia-dortmund" in links
        assert "https://www.bundesliga.com/de/bundesliga/clubs/rb-leipzig" in links

    def test_extract_club_data(self, scraper, sample_club_html):
        """Test extraction of club data from individual club page"""
        soup = BeautifulSoup(sample_club_html, 'html.parser')
        url = "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen"
        
        data = scraper._extract_club_data(soup, url)
        
        assert data['name'] == "FC Bayern München"
        assert data['stadium'] == "Allianz Arena"
        assert data['founded_year'] == 1900
        assert data['coach'] == "Thomas Tuchel"
        assert data['city'] == "München"

    def test_find_squad_url(self, scraper, sample_club_html):
        """Test finding squad URL from club page"""
        soup = BeautifulSoup(sample_club_html, 'html.parser')
        base_url = "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen"
        
        squad_url = scraper._find_squad_url(soup, base_url)
        
        assert squad_url == "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen/squad"

    def test_extract_player_links(self, scraper, sample_squad_html):
        """Test extraction of player links from squad page"""
        soup = BeautifulSoup(sample_squad_html, 'html.parser')
        base_url = "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen/squad"
        
        links = scraper._extract_player_links(soup, base_url)
        
        assert len(links) == 3
        assert "https://www.bundesliga.com/de/bundesliga/spieler/manuel-neuer" in links
        assert "https://www.bundesliga.com/de/bundesliga/spieler/thomas-mueller" in links  
        assert "https://www.bundesliga.com/de/bundesliga/spieler/joshua-kimmich" in links

    def test_extract_player_links_filters_noise(self, scraper, sample_squad_html_with_noise):
        """Test that player link extraction filters out extraneous links and focuses on squad"""
        soup = BeautifulSoup(sample_squad_html_with_noise, 'html.parser')
        base_url = "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen/squad"
        
        links = scraper._extract_player_links(soup, base_url)
        
        # Should only find the 3 actual squad members, not the navigation links
        assert len(links) == 3
        assert "https://www.bundesliga.com/de/bundesliga/spieler/manuel-neuer" in links
        assert "https://www.bundesliga.com/de/bundesliga/spieler/thomas-mueller" in links
        assert "https://www.bundesliga.com/de/bundesliga/spieler/joshua-kimmich" in links
        
        # Should NOT include navigation or footer links
        assert "https://www.bundesliga.com/de/bundesliga/spieler/random-player-1" not in links
        assert "https://www.bundesliga.com/de/bundesliga/spieler/another-random" not in links

    def test_extract_player_basic_info(self, scraper, sample_player_html):
        """Test extraction of basic player information"""
        soup = BeautifulSoup(sample_player_html, 'html.parser')
        
        data = scraper._extract_player_basic_info(soup)
        
        assert data['first_name'] == "Manuel"
        assert data['last_name'] == "Neuer"
        assert data['position'] == "Goalkeeper"
        assert data['shirt_number'] == 1
        assert data['nationality'] == "Germany"
        assert data['height_cm'] == 193
        assert data['weight_kg'] == 92
        assert data['birth_date'] == date(1986, 3, 27)

    def test_extract_player_season_stats(self, scraper, sample_player_html):
        """Test extraction of player season statistics"""
        soup = BeautifulSoup(sample_player_html, 'html.parser')
        
        stats = scraper._extract_player_season_stats(soup)
        
        assert stats is not None
        assert stats.appearances == 25
        assert stats.goals == 0
        assert stats.assists == 1

    def test_parse_date_string(self, scraper):
        """Test date parsing from various formats"""
        # Test DD.MM.YYYY format
        date1 = scraper._parse_date_string("27.03.1986")
        assert date1 == date(1986, 3, 27)
        
        # Test YYYY-MM-DD format
        date2 = scraper._parse_date_string("1986-03-27")
        assert date2 == date(1986, 3, 27)
        
        # Test invalid date
        date3 = scraper._parse_date_string("invalid date")
        assert date3 is None

    def test_find_labeled_value(self, scraper):
        """Test finding labeled values in HTML"""
        html = """
        <div>
            <dt>Position</dt><dd>Midfielder</dd>
            <p>Height: 180 cm</p>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Test definition list
        position = scraper._find_labeled_value(soup, ['Position'])
        assert position == "Midfielder"
        
        # Test text pattern
        height = scraper._find_labeled_value(soup, ['Height'])
        assert height == "180 cm"

    @pytest.mark.asyncio
    async def test_scrape_clubs_integration(self, scraper, sample_clubs_html, sample_club_html):
        """Test full club scraping workflow"""
        with patch.object(scraper, 'fetch_page') as mock_fetch:
            # Mock responses
            mock_fetch.side_effect = [sample_clubs_html, sample_club_html, sample_club_html, sample_club_html]
            
            clubs = await scraper.scrape_clubs()
            
            assert len(clubs) == 3
            assert all(isinstance(club, EnhancedClub) for club in clubs)
            assert clubs[0].name == "FC Bayern München"

    @pytest.mark.asyncio
    async def test_scrape_player_integration(self, scraper, sample_player_html):
        """Test full player scraping workflow"""
        with patch.object(scraper, 'fetch_page', return_value=sample_player_html):
            player_url = "https://www.bundesliga.com/de/bundesliga/spieler/manuel-neuer"
            
            player = await scraper.scrape_player(player_url)
            
            assert player is not None
            assert isinstance(player, EnhancedPlayer)
            assert player.first_name == "Manuel"
            assert player.last_name == "Neuer"
            assert player.position == "Goalkeeper"
            assert player.source_url == player_url

    def test_enhanced_player_model_validation(self):
        """Test EnhancedPlayer model validation"""
        # Test valid player
        player_data = {
            'first_name': 'Manuel',
            'last_name': 'Neuer',
            'position': 'Goalkeeper',
            'birth_date': '1986-03-27',
            'nationality': 'Germany'
        }
        
        player = EnhancedPlayer(**player_data)
        assert player.first_name == 'Manuel'
        assert player.birth_date == date(1986, 3, 27)

    def test_enhanced_club_model_validation(self):
        """Test EnhancedClub model validation"""
        # Test valid club
        club_data = {
            'name': 'FC Bayern München',
            'city': 'München',
            'founded_year': 1900,
            'stadium': 'Allianz Arena'
        }
        
        club = EnhancedClub(**club_data)
        assert club.name == 'FC Bayern München'
        assert club.founded_year == 1900

    def test_player_season_stats_model(self):
        """Test PlayerSeasonStats model"""
        stats_data = {
            'appearances': 25,
            'goals': 0,
            'assists': 1,
            'minutes_played': 2250
        }
        
        stats = PlayerSeasonStats(**stats_data)
        assert stats.appearances == 25
        assert stats.goals == 0

    def test_player_career_stats_model(self):
        """Test PlayerCareerStats model"""
        career_data = {
            'season': '2023-24',
            'team': 'FC Bayern München',
            'league': 'Bundesliga',
            'appearances': 34,
            'goals': 0
        }
        
        career = PlayerCareerStats(**career_data)
        assert career.season == '2023-24'
        assert career.team == 'FC Bayern München'


if __name__ == "__main__":
    pytest.main([__file__])