# Bundesliga Club & Squad Scraper

## Overview

The `BundesligaClubScraper` is a comprehensive web scraper that implements a three-stage workflow for collecting Bundesliga data:

1. **Club Overview Scraping**: Extracts all club URLs from the main clubs page
2. **Squad Scraping**: For each club, scrapes the squad listing to get all player URLs  
3. **Player Data Scraping**: For each player, scrapes detailed information including career statistics

## Features

- ✅ **Comprehensive Club Data**: Name, stadium, coach, founding year, logo, etc.
- ✅ **Detailed Player Information**: Personal details, physical attributes, position, etc.  
- ✅ **Current Season Statistics**: Appearances, goals, assists, minutes played, cards
- ✅ **Career History**: Multi-season statistics and club history
- ✅ **Anti-Detection Measures**: Rate limiting, random delays, realistic headers
- ✅ **Robust Error Handling**: Retry logic, graceful failure handling, progress logging
- ✅ **Data Validation**: Pydantic models ensure data quality and type safety
- ✅ **Extensible Architecture**: Built on `BaseScraper` following established patterns

## Usage

### Basic Usage

```python
import asyncio
from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper
from src.database.manager import DatabaseManager

async def scrape_bundesliga():
    db_manager = DatabaseManager()
    scraper = BundesligaClubScraper(db_manager)
    
    await scraper.initialize()
    try:
        # Scrape all data (clubs, squads, players)
        results = await scraper.scrape_data()
        
        print(f"Scraped {results['total_clubs']} clubs")
        print(f"Scraped {results['total_players']} players")
        
    finally:
        await scraper.cleanup()

asyncio.run(scrape_bundesliga())
```

### Stage-by-Stage Usage

```python
# Stage 1: Scrape club overviews only
clubs = await scraper.scrape_clubs()

# Stage 2: Scrape squad for specific club
squad_urls = await scraper.scrape_squad(club.squad_url, club.name)

# Stage 3: Scrape individual player
player = await scraper.scrape_player(player_url)
```

### Using the CLI Script

```bash
# Scrape all clubs and players
python scripts/run_bundesliga_club_scraper.py

# Scrape only club information
python scripts/run_bundesliga_club_scraper.py --clubs-only

# Limit to first 3 clubs for testing
python scripts/run_bundesliga_club_scraper.py --max-clubs 3

# Save results to JSON file
python scripts/run_bundesliga_club_scraper.py --output bundesliga_data.json
```

## Data Models

### EnhancedClub

```python
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
```

### EnhancedPlayer

```python
class EnhancedPlayer(BaseModel):
    # Basic info
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    nationality: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: Optional[Footedness] = None
    photo_url: Optional[HttpUrl] = None
    
    # Football-specific
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    market_value: Optional[str] = None
    contract_until: Optional[date] = None
    
    # Statistics
    current_season_stats: Optional[PlayerSeasonStats] = None
    career_stats: Optional[List[PlayerCareerStats]] = None
    
    # Metadata
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    external_ids: Optional[dict] = None
```

### PlayerSeasonStats

```python
class PlayerSeasonStats(BaseModel):
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
```

## Configuration

The scraper uses `BundesligaClubScraperConfig` which extends `ScrapingConfig`:

```python
@dataclass
class BundesligaClubScraperConfig(ScrapingConfig):
    base_url: str = "https://www.bundesliga.com"
    delay_range: tuple = (1, 3)  # Random delay between requests
    max_retries: int = 3
    timeout: int = 30
    anti_detection: bool = True
    screenshot_on_error: bool = True
```

## Error Handling

The scraper implements comprehensive error handling:

- **Retry Logic**: Failed requests are retried up to `max_retries` times
- **Rate Limiting**: Random delays between requests to avoid being blocked
- **Graceful Failures**: Individual failures don't stop the entire scraping process
- **Progress Logging**: Detailed logging shows scraping progress and any issues
- **Data Validation**: Pydantic models validate all scraped data

## Integration with Orchestrator

The scraper can be integrated with the existing `ScrapingOrchestrator`:

```python
from src.data_collection.scrapers.scraping_orchestrator import ScrapingOrchestrator
from src.data_collection.scrapers.bundesliga_club_scraper import BundesligaClubScraper

orchestrator = ScrapingOrchestrator(db_manager, settings)
bundesliga_scraper = BundesligaClubScraper(db_manager)

orchestrator.register_scraper(bundesliga_scraper)
await orchestrator.initialize_all()

# Run scraping job
results = await orchestrator.run_scraping_job(['bundesliga_club'])
```

## Testing

Run the unit tests:

```bash
python -m pytest tests/unit/test_bundesliga_club_scraper.py -v
```

Run the demo with mock data:

```bash
python scripts/test_bundesliga_scraper_demo.py
```

## Data Storage

The scraper is compatible with existing domain models:

- Club data can be saved to the `clubs` table using the `Club` model
- Player data can be saved to the `players` table using the `Player` model  
- Additional statistics can be stored in appropriate stats tables
- The scraper supports bulk insert operations for efficient data storage

## Performance Considerations

- **Rate Limiting**: Built-in delays prevent overwhelming the target server
- **Batch Processing**: Players are scraped in batches with progress logging
- **Memory Efficient**: Data is processed incrementally, not loaded all at once
- **Concurrent-Safe**: Async/await pattern allows for concurrent operations
- **Resumable**: Can be stopped and restarted without losing progress

## Future Enhancements

Potential areas for improvement:

- [ ] Add support for historical season data
- [ ] Implement match performance statistics
- [ ] Add injury and suspension data
- [ ] Support for multiple leagues (2. Bundesliga, etc.)
- [ ] Integration with transfer market data
- [ ] Real-time data updates
- [ ] Data change detection and incremental updates

## Example Output

The scraper produces structured data like this:

```json
{
  "clubs": [
    {
      "name": "FC Bayern München",
      "stadium": "Allianz Arena", 
      "founded_year": 1900,
      "coach": "Thomas Tuchel",
      "city": "München",
      "squad_url": "https://www.bundesliga.com/de/bundesliga/clubs/fc-bayern-muenchen/squad"
    }
  ],
  "players": {
    "FC Bayern München": [
      {
        "first_name": "Manuel",
        "last_name": "Neuer",
        "position": "Goalkeeper",
        "shirt_number": 1,
        "nationality": "Germany",
        "birth_date": "1986-03-27",
        "height_cm": 193,
        "weight_kg": 92,
        "current_season_stats": {
          "appearances": 34,
          "goals": 0,
          "assists": 2
        }
      }
    ]
  },
  "total_clubs": 18,
  "total_players": 450
}
```