#!/usr/bin/env python3
"""
Script to run the enhanced Bundesliga Club & Squad Scraper

This script demonstrates how to use the BundesligaClubScraper to scrape:
1. Club overviews from https://www.bundesliga.com/de/bundesliga/clubs  
2. Squad listings for each club
3. Individual player data including career statistics

Usage:
    python scripts/run_bundesliga_club_scraper.py [--clubs-only] [--clubs-format json|csv] [--max-clubs N] [--output FILE]
  
Examples:
  # Scrape all clubs and squads
  python scripts/run_bundesliga_club_scraper.py
  
    # Just scrape club info (no players) to JSON
    python scripts/run_bundesliga_club_scraper.py --clubs-only -o clubs.json

    # Only clubs as CSV
    python scripts/run_bundesliga_club_scraper.py --clubs-only --clubs-format csv -o clubs.csv
  
  # Limit to first 3 clubs for testing
  python scripts/run_bundesliga_club_scraper.py --max-clubs 3
  
  # Save results to JSON file
  python scripts/run_bundesliga_club_scraper.py --output bundesliga_data.json
"""

import asyncio
import os
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper


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
    parser.add_argument("--clubs-format", choices=["json","csv"], default="json",
                       help="Output format when using --clubs-only (default json)")
    parser.add_argument("--max-players", type=int, default=None,
                       help="Maximum number of players to scrape per club (for testing)")
    parser.add_argument("--output", "-o", type=str, default=None,
                       help="Output JSON file path")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    parser.add_argument("--player-url", type=str, default=None,
                       help="Direct player profile URL to scrape (bypasses clubs & squads)")
    
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
        results = {
            'clubs': [],
            'squads': {},
            'players': {},
            'scraping_stats': {
                'total_clubs': 0,
                'total_players': 0,
                'start_time': start_time.isoformat(),
                'clubs_only': args.clubs_only,
                'direct_player': bool(args.player_url)
            }
        }

        if not args.player_url:
            logger.info("Stage 1: Scraping club overviews...")
            clubs = await scraper.scrape_clubs()
            if args.max_clubs:
                clubs = clubs[:args.max_clubs]
                logger.info(f"Limited to {len(clubs)} clubs for testing")
            logger.info(f"Found {len(clubs)} clubs")
            results['clubs'] = [club.model_dump() for club in clubs]
            results['scraping_stats']['total_clubs'] = len(clubs)
            if args.clubs_only:
                if args.output:
                    out_path = Path(args.output)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    if args.clubs_format == 'json':
                        payload = {
                            'scraped_at': datetime.utcnow().isoformat(),
                            'count': len(clubs),
                            'clubs': [c.model_dump() for c in clubs]
                        }
                        with out_path.open('w', encoding='utf-8') as f:
                            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
                        logger.info(f"Clubs JSON written: {out_path}")
                    else:
                        import csv as _csv
                        rows = [c.model_dump() for c in clubs]
                        header = sorted({k for r in rows for k in r.keys()})
                        with out_path.open('w', newline='', encoding='utf-8') as f:
                            writer = _csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
                            writer.writeheader()
                            for r in rows:
                                writer.writerow(r)
                        logger.info(f"Clubs CSV written: {out_path}")
                else:
                    print("\nCLUBS (first 10 shown)")
                    print("-"*40)
                    for c in clubs[:10]:
                        print(f"- {c.name} | Stadium: {c.stadium or 'n/a'} | Founded: {c.founded_year or 'n/a'}")
                    print(f"Total clubs: {len(clubs)}")
                end_time = datetime.now()
                duration = end_time - start_time
                results['scraping_stats'].update({
                    'end_time': end_time.isoformat(),
                    'duration_seconds': duration.total_seconds(),
                    'duration_formatted': str(duration)
                })
                logger.info("Clubs-only mode complete")
                return
        
        if args.player_url:
            # Direct single player scrape path
            logger.info(f"Direct player scrape: {args.player_url}")
            player = await scraper.scrape_player(args.player_url)
            if player:
                # Use pseudo club bucket 'direct'
                results['players']['direct'] = [player.model_dump()]
                results['scraping_stats']['total_players'] = 1
            else:
                logger.error("Failed to scrape direct player URL")
        elif not args.clubs_only:
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
                        # Show current season stats summary if available
                        season_stats = player.get('current_season_stats') or {}
                        if season_stats:
                            # Filter out empty / null values
                            filtered = {k: v for k, v in season_stats.items() if v not in (None, '', 0)}
                            if filtered:
                                # Limit to a few key metrics for brevity
                                important_keys = [
                                    'appearances','goals','assists','minutes_played',
                                    'distance_km','sprints','intensive_runs','duels_won'
                                ]
                                display_pairs = []
                                for key in important_keys:
                                    if key in filtered:
                                        display_pairs.append(f"{key}={filtered[key]}")
                                # Fallback: if none of the important keys present, show first 6 items
                                if not display_pairs:
                                    for k, v in list(filtered.items())[:6]:
                                        display_pairs.append(f"{k}={v}")
                                print("  Current Season Stats: " + ", ".join(display_pairs))
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
    # Windows-specific event loop policy selection.
    # Playwright requires subprocess support which is not implemented for the WindowsSelectorEventLoop.
    # If dynamic rendering is requested via BUNDESLIGA_USE_PLAYWRIGHT, prefer Proactor; otherwise keep Selector
    # (Selector can be marginally more compatible with some legacy libs, but here Proactor is fine for most cases).
    if sys.platform.startswith("win"):
        use_playwright = os.getenv("BUNDESLIGA_USE_PLAYWRIGHT") in ("1", "true", "True")
        try:
            if use_playwright and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]
            elif not use_playwright and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
        except Exception:
            # Fallback silently; asyncio.run will use default policy
            pass

    asyncio.run(main())