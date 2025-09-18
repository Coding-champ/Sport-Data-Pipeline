#!/usr/bin/env python3
"""
Script to run the enhanced Bundesliga Club & Squad Scraper

This script demonstrates how to use the BundesligaClubScraper to scrape:
1. Club overviews from https://www.bundesliga.com/de/bundesliga/clubs  
2. Squad listings for each club
3. Individual player data including career statistics

Usage:
  python scripts/run_bundesliga_club_scraper.py [--clubs-only] [--max-clubs N] [--output FILE]
  
Examples:
  # Scrape all clubs and squads
  python scripts/run_bundesliga_club_scraper.py
  
  # Just scrape club info (no players)
  python scripts/run_bundesliga_club_scraper.py --clubs-only
  
  # Limit to first 3 clubs for testing
  python scripts/run_bundesliga_club_scraper.py --max-clubs 3
  
  # Save results to JSON file
  python scripts/run_bundesliga_club_scraper.py --output bundesliga_data.json
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper


class MockDatabaseManager:
    """Mock database manager for standalone operation"""
    
    async def bulk_insert(self, table: str, data: list, conflict_resolution: str = ""):
        """Mock bulk insert - just log what would be inserted"""
        logging.info(f"Would insert {len(data)} records into table '{table}' with resolution: {conflict_resolution}")
        
        # Show sample data
        if data:
            sample = data[0]
            logging.info(f"Sample record: {json.dumps(sample, indent=2, default=str)[:200]}...")


async def main():
    """Main scraping function"""
    parser = argparse.ArgumentParser(description="Enhanced Bundesliga Club & Squad Scraper")
    parser.add_argument("--clubs-only", action="store_true", 
                       help="Only scrape club information, skip squads and players")
    parser.add_argument("--max-clubs", type=int, default=None,
                       help="Maximum number of clubs to scrape (for testing)")  
    parser.add_argument("--max-players", type=int, default=None,
                       help="Maximum number of players to scrape per club (for testing)")
    parser.add_argument("--output", "-o", type=str, default=None,
                       help="Output JSON file path")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Enhanced Bundesliga Club & Squad Scraper")
    
    # Create scraper with mock database
    db_manager = MockDatabaseManager()
    scraper = BundesligaClubScraper(db_manager)
    
    try:
        await scraper.initialize()
        
        start_time = datetime.now()
        
        # Stage 1: Scrape clubs
        logger.info("Stage 1: Scraping club overviews...")
        clubs = await scraper.scrape_clubs()
        
        if args.max_clubs:
            clubs = clubs[:args.max_clubs]
            logger.info(f"Limited to {len(clubs)} clubs for testing")
        
        logger.info(f"Found {len(clubs)} clubs")
        
        results = {
            'clubs': [club.model_dump() for club in clubs],
            'squads': {},
            'players': {},
            'scraping_stats': {
                'total_clubs': len(clubs),
                'total_players': 0,
                'start_time': start_time.isoformat(),
                'clubs_only': args.clubs_only
            }
        }
        
        if not args.clubs_only:
            # Stage 2: Scrape squads
            logger.info("Stage 2: Scraping squad listings...")
            all_squads = {}
            
            for i, club in enumerate(clubs, 1):
                if club.squad_url:
                    try:
                        logger.info(f"Scraping squad {i}/{len(clubs)}: {club.name}")
                        squad_urls = await scraper.scrape_squad(club.squad_url, club.name)
                        
                        if args.max_players:
                            squad_urls = squad_urls[:args.max_players]
                            
                        all_squads[club.name] = squad_urls
                        logger.info(f"Found {len(squad_urls)} players for {club.name}")
                        
                        # Rate limiting
                        await scraper.anti_detection.random_delay(scraper.config.delay_range)
                        
                    except Exception as e:
                        logger.error(f"Failed to scrape squad for {club.name}: {e}")
                        all_squads[club.name] = []
            
            results['squads'] = all_squads
            
            # Stage 3: Scrape individual players
            logger.info("Stage 3: Scraping individual player data...")
            all_players = {}
            total_players = sum(len(squad) for squad in all_squads.values())
            
            logger.info(f"Will scrape {total_players} individual players")
            
            player_count = 0
            for club_name, player_urls in all_squads.items():
                club_players = []
                
                for j, player_url in enumerate(player_urls, 1):
                    try:
                        logger.debug(f"Scraping player {j}/{len(player_urls)} for {club_name}: {player_url}")
                        player = await scraper.scrape_player(player_url)
                        
                        if player:
                            club_players.append(player.model_dump())
                            player_count += 1
                            
                            # Log progress every 10 players
                            if player_count % 10 == 0:
                                logger.info(f"Scraped {player_count}/{total_players} players")
                        
                        # Rate limiting
                        await scraper.anti_detection.random_delay(scraper.config.delay_range)
                        
                    except Exception as e:
                        logger.error(f"Failed to scrape player {player_url}: {e}")
                        continue
                
                all_players[club_name] = club_players
                logger.info(f"Scraped {len(club_players)} players for {club_name}")
            
            results['players'] = all_players
            results['scraping_stats']['total_players'] = player_count
        
        # Add completion stats
        end_time = datetime.now()
        duration = end_time - start_time
        
        results['scraping_stats'].update({
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'duration_formatted': str(duration)
        })
        
        # Output results
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Results saved to: {output_path}")
        else:
            # Print summary to stdout
            print("\n" + "="*60)
            print("SCRAPING SUMMARY")
            print("="*60)
            print(f"Clubs scraped: {results['scraping_stats']['total_clubs']}")
            if not args.clubs_only:
                print(f"Players scraped: {results['scraping_stats']['total_players']}")
            print(f"Duration: {results['scraping_stats']['duration_formatted']}")
            print("="*60)
            
            # Show sample club data
            if clubs:
                print(f"\nSample club: {clubs[0].name}")
                print(f"  Stadium: {clubs[0].stadium}")
                print(f"  Founded: {clubs[0].founded_year}")
                print(f"  Squad URL: {clubs[0].squad_url}")
            
            # Show sample player data
            if not args.clubs_only and results['players']:
                for club_name, players in results['players'].items():
                    if players:
                        player = players[0]
                        print(f"\nSample player from {club_name}:")
                        print(f"  Name: {player.get('first_name', '')} {player.get('last_name', '')}")
                        print(f"  Position: {player.get('position', 'N/A')}")
                        print(f"  Nationality: {player.get('nationality', 'N/A')}")
                        break
        
        logger.info("Scraping completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    # Windows-specific event loop policy
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())