#!/usr/bin/env python3
"""
Demo script for BundesligaClubScraper with mock data

This demonstrates the scraper functionality using mock HTML responses
instead of actual network requests.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper


# Mock HTML responses
MOCK_CLUBS_HTML = """
<html>
<body>
    <div class="clubs-overview">
        <a href="/de/bundesliga/clubs/fc-bayern-muenchen">FC Bayern München</a>
        <a href="/de/bundesliga/clubs/borussia-dortmund">Borussia Dortmund</a>
        <a href="/de/bundesliga/clubs/rb-leipzig">RB Leipzig</a>
        <a href="/de/bundesliga/clubs/bayer-leverkusen">Bayer 04 Leverkusen</a>
    </div>
</body>
</html>
"""

MOCK_CLUB_HTML = """
<html>
<head>
    <title>{club_name} - Bundesliga</title>
    <meta property="og:title" content="{club_name}" />
</head>
<body>
    <h1 class="club-name">{club_name}</h1>
    <div class="club-info">
        <dl>
            <dt>Stadium</dt><dd>{stadium}</dd>
            <dt>Founded</dt><dd>{founded}</dd>
            <dt>Coach</dt><dd>{coach}</dd>
            <dt>City</dt><dd>{city}</dd>
        </dl>
    </div>
    <a href="/de/bundesliga/clubs/{club_id}/squad">Squad</a>
    <img src="/images/{club_id}_logo.png" alt="{club_name} logo" class="club-logo">
</body>
</html>
"""

MOCK_SQUAD_HTML = """
<html>
<body>
    <div class="squad-list">
        {player_links}
    </div>
</body>
</html>
"""

MOCK_PLAYER_HTML = """
<html>
<head>
    <title>{player_name} - Bundesliga</title>
</head>
<body>
    <h1 class="player-name">{player_name}</h1>
    <div class="player-info">
        <dl>
            <dt>Position</dt><dd>{position}</dd>
            <dt>Number</dt><dd>{number}</dd>
            <dt>Born</dt><dd>{birth_date}</dd>
            <dt>Birthplace</dt><dd>{birth_place}</dd>
            <dt>Nationality</dt><dd>{nationality}</dd>
            <dt>Height</dt><dd>{height} cm</dd>
            <dt>Weight</dt><dd>{weight} kg</dd>
            <dt>Foot</dt><dd>{foot}</dd>
        </dl>
    </div>
    <section class="season-stats">
        <h3>Current Season</h3>
        <dl>
            <dt>Appearances</dt><dd>{appearances}</dd>
            <dt>Goals</dt><dd>{goals}</dd>
            <dt>Assists</dt><dd>{assists}</dd>
            <dt>Minutes</dt><dd>{minutes}</dd>
        </dl>
    </section>
    <img src="/images/{player_id}_photo.jpg" alt="{player_name}" class="player-photo">
</body>
</html>
"""

# Sample data
CLUB_DATA = {
    'fc-bayern-muenchen': {
        'name': 'FC Bayern München',
        'stadium': 'Allianz Arena',
        'founded': '1900', 
        'coach': 'Thomas Tuchel',
        'city': 'München',
        'players': [
            ('manuel-neuer', 'Manuel Neuer', 'Goalkeeper', 1, '27.03.1986', 'Gelsenkirchen', 'Germany', 193, 92, 'right', 34, 0, 2, 3060),
            ('thomas-mueller', 'Thomas Müller', 'Forward', 25, '13.09.1989', 'Weilheim', 'Germany', 186, 75, 'right', 31, 12, 8, 2450),
            ('joshua-kimmich', 'Joshua Kimmich', 'Midfielder', 6, '08.02.1995', 'Rottweil', 'Germany', 177, 75, 'right', 33, 4, 11, 2890),
        ]
    },
    'borussia-dortmund': { 
        'name': 'Borussia Dortmund',
        'stadium': 'Signal Iduna Park',
        'founded': '1909',
        'coach': 'Edin Terzić', 
        'city': 'Dortmund',
        'players': [
            ('erling-haaland', 'Erling Haaland', 'Forward', 9, '21.07.2000', 'Leeds', 'Norway', 194, 88, 'left', 28, 22, 7, 2240),
            ('marco-reus', 'Marco Reus', 'Midfielder', 11, '31.05.1989', 'Dortmund', 'Germany', 180, 71, 'right', 24, 8, 5, 1890),
        ]
    },
    'rb-leipzig': {
        'name': 'RB Leipzig',
        'stadium': 'Red Bull Arena',
        'founded': '2009',
        'coach': 'Marco Rose',
        'city': 'Leipzig', 
        'players': [
            ('timo-werner', 'Timo Werner', 'Forward', 11, '06.03.1996', 'Stuttgart', 'Germany', 180, 75, 'right', 29, 14, 6, 2310),
        ]
    },
    'bayer-leverkusen': {
        'name': 'Bayer 04 Leverkusen',
        'stadium': 'BayArena',
        'founded': '1904',
        'coach': 'Xabi Alonso',
        'city': 'Leverkusen',
        'players': [
            ('florian-wirtz', 'Florian Wirtz', 'Midfielder', 10, '03.05.2003', 'Pulheim', 'Germany', 176, 70, 'right', 32, 11, 13, 2650),
        ]
    }
}


class MockDatabaseManager:
    """Mock database manager that logs operations"""
    
    async def bulk_insert(self, table: str, data: list, conflict_resolution: str = ""):
        logging.info(f"MockDB: Would insert {len(data)} records into '{table}'")
        if data:
            sample = data[0]
            logging.debug(f"Sample record: {json.dumps(sample, indent=2, default=str)[:300]}...")


async def mock_fetch_page(url: str, method: str = "GET", data: dict = None, use_cloudscraper: bool = False) -> str:
    """Mock fetch_page method that returns appropriate HTML based on URL"""
    
    await asyncio.sleep(0.1)  # Simulate network delay
    
    if '/clubs' in url and not any(club in url for club in CLUB_DATA.keys()):
        # Main clubs page
        return MOCK_CLUBS_HTML
    
    # Individual club pages
    for club_id, club_info in CLUB_DATA.items():
        if club_id in url:
            if '/squad' in url:
                # Squad page
                player_links = '\n'.join([
                    f'<a href="/de/bundesliga/spieler/{player[0]}">{player[1]}</a>'
                    for player in club_info['players']
                ])
                return MOCK_SQUAD_HTML.format(player_links=player_links)
            else:
                # Club page  
                return MOCK_CLUB_HTML.format(
                    club_name=club_info['name'],
                    club_id=club_id,
                    stadium=club_info['stadium'],
                    founded=club_info['founded'],
                    coach=club_info['coach'],
                    city=club_info['city']
                )
    
    # Player pages
    if '/spieler/' in url:
        player_id = url.split('/spieler/')[-1]
        
        # Find player in data
        for club_info in CLUB_DATA.values():
            for player in club_info['players']:
                if player[0] == player_id:
                    return MOCK_PLAYER_HTML.format(
                        player_name=player[1],
                        player_id=player[0],
                        position=player[2],
                        number=player[3],
                        birth_date=player[4],
                        birth_place=player[5],
                        nationality=player[6],
                        height=player[7],
                        weight=player[8],
                        foot=player[9],
                        appearances=player[10],
                        goals=player[11],
                        assists=player[12],
                        minutes=player[13]
                    )
    
    return "<html><body><h1>Page not found</h1></body></html>"


async def main():
    """Demo the scraper with mock data"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Bundesliga Club Scraper Demo with Mock Data")
    
    # Create scraper with mock database
    db_manager = MockDatabaseManager() 
    scraper = BundesligaClubScraper(db_manager)
    
    # Patch the fetch_page method to use mock data
    with patch.object(scraper, 'fetch_page', new=mock_fetch_page):
        
        try:
            await scraper.initialize()
            
            logger.info("=== Stage 1: Scraping Club Overviews ===")
            clubs = await scraper.scrape_clubs()
            
            logger.info(f"Found {len(clubs)} clubs:")
            for club in clubs:
                logger.info(f"  - {club.name} (Founded: {club.founded_year}, Stadium: {club.stadium})")
            
            logger.info("\n=== Stage 2: Scraping Squad Listings ===")
            all_squads = {}
            
            for club in clubs[:2]:  # Limit to first 2 clubs for demo
                if club.squad_url:
                    squad_urls = await scraper.scrape_squad(club.squad_url, club.name)
                    all_squads[club.name] = squad_urls
                    logger.info(f"  {club.name}: {len(squad_urls)} players")
            
            logger.info("\n=== Stage 3: Scraping Individual Players ===")
            all_players = {}
            
            for club_name, player_urls in all_squads.items():
                club_players = []
                
                for player_url in player_urls[:2]:  # Limit to 2 players per club for demo
                    player = await scraper.scrape_player(player_url)
                    if player:
                        club_players.append(player)
                        logger.info(f"  {player.first_name} {player.last_name} ({player.position}, #{player.shirt_number})")
                
                all_players[club_name] = club_players
            
            # Create comprehensive results
            results = {
                'clubs': [club.model_dump() for club in clubs],
                'squads': all_squads,
                'players': {name: [p.model_dump() for p in players] for name, players in all_players.items()},
                'demo_stats': {
                    'total_clubs': len(clubs),
                    'total_players': sum(len(players) for players in all_players.values()),
                    'data_source': 'mock_data_for_demo'
                }
            }
            
            logger.info("\n=== Demo Results Summary ===")
            logger.info(f"Clubs scraped: {results['demo_stats']['total_clubs']}")
            logger.info(f"Players scraped: {results['demo_stats']['total_players']}")
            
            # Show detailed sample
            if clubs:
                sample_club = clubs[0]
                logger.info(f"\n=== Sample Club Data ===")
                logger.info(f"Name: {sample_club.name}")
                logger.info(f"Stadium: {sample_club.stadium} (Founded: {sample_club.founded_year})")
                logger.info(f"Coach: {sample_club.coach}")
                logger.info(f"City: {sample_club.city}")
                logger.info(f"Squad URL: {sample_club.squad_url}")
            
            if all_players:
                for club_name, players in all_players.items():
                    if players:
                        sample_player = players[0]
                        logger.info(f"\n=== Sample Player from {club_name} ===")
                        logger.info(f"Name: {sample_player.first_name} {sample_player.last_name}")
                        logger.info(f"Position: {sample_player.position} (#{sample_player.shirt_number})")
                        logger.info(f"Born: {sample_player.birth_date} in {sample_player.birth_place}")
                        logger.info(f"Nationality: {sample_player.nationality}")
                        logger.info(f"Physical: {sample_player.height_cm}cm, {sample_player.weight_kg}kg")
                        if sample_player.current_season_stats:
                            stats = sample_player.current_season_stats
                            logger.info(f"Season Stats: {stats.appearances} apps, {stats.goals} goals, {stats.assists} assists")
                        break
            
            # Save results
            output_file = Path("demo_bundesliga_results.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"\n=== Demo completed successfully! ===")
            logger.info(f"Full results saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Demo failed: {e}", exc_info=True)
        finally:
            await scraper.cleanup()


if __name__ == "__main__":
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())