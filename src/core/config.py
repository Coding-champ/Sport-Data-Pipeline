"""
Zentrale Konfiguration für die Sport Data Pipeline
Basiert auf Pydantic Settings mit Environment Variable Support
"""



from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application Settings mit Environment Variable Support"""

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/sportsdata"
    database_pool_size: int = 20
    database_pool_min_size: int = 10
    database_pool_max_size: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Scraping
    scraping_enabled: bool = True
    scraping_interval_minutes: int = 30
    scraping_delay_range_min: int = 1
    scraping_delay_range_max: int = 3
    scraping_max_retries: int = 3
    scraping_timeout: int = 30
    scraping_use_proxy: bool = False
    scraping_anti_detection: bool = True
    scraping_screenshot_on_error: bool = True
    # Scraping/Scheduling Intervals (seconds)
    live_update_interval_seconds: int = 30
    live_error_backoff_seconds: int = 60
    regular_update_interval_seconds: int = 300
    regular_error_backoff_seconds: int = 300
    daily_update_interval_seconds: int = 86400
    daily_error_backoff_seconds: int = 3600
    scraping_live_scores_interval_seconds: int = 30
    scraping_odds_interval_seconds: int = 300
    scraping_player_daily_check_interval_seconds: int = 3600
    player_daily_hour: int = 2
    player_daily_window_minutes: int = 30
    # FBref specific
    fbref_league_ids: list[int] = [
        9
    ]  # default: Premier League (9); can include others e.g. [9, 12, 11]

    # Orchestrator Configuration
    # Configurable scraper routing (addresses TODO in scraping_orchestrator.py)
    scraper_routing: dict[str, str] = {
        "transfermarkt": "players",  # Use upsert_players service
        "flashscore": "matches",     # Use upsert_matches service  
        "odds": "odds",              # Use upsert_odds service
        "fbref": "generic",          # Use generic scraped_data table
        "courtside1891": "generic",  # Use generic scraped_data table
        "bet365": "odds",            # Use upsert_odds service
    }
    
    # Feature flags for optional scrapers (addresses startup ImportError issues)
    enable_transfermarkt_scraper: bool = True
    enable_flashscore_scraper: bool = True
    enable_bet365_scraper: bool = True
    enable_fbref_scraper: bool = True
    enable_courtside1891_scraper: bool = False
    
    # Feature flags for collectors
    enable_football_data_collector: bool = True
    enable_betfair_collector: bool = True

    # Analytics
    analytics_enabled: bool = True
    model_update_interval_hours: int = 24
    model_storage_path: str = "./models/"
    report_output_path: str = "./reports/"
    cache_duration_hours: int = 24
    min_matches_for_prediction: int = 10
    feature_importance_threshold: float = 0.01

    # Monitoring
    log_level: str = "INFO"
    log_file_path: str = "./logs"
    enable_monitoring: bool = True
    enable_metrics: bool = True
    metrics_port: int = 8008
    enable_system_monitoring: bool = True
    enable_health_checks: bool = True
    monitoring_log_file: Optional[str] = "./logs/system_monitor.log"

    # Feature Flags
    enable_data_collection: bool = True
    enable_analytics: bool = True
    enable_api: bool = True
    enable_scheduled_collection: bool = True
    enable_scheduled_analytics: bool = True

    # Application
    run_mode: str = (
        "interactive"  # Modes: interactive, api_only, collection_once, analytics_once, full_service
    )
    environment: str = "development"  # Environment: development, staging, production
    enable_odds_in_collection_once: bool = False
    include_scheduled_on_empty: bool = True

    # Security
    api_key: Optional[str] = None
    cors_origins: list[str] = ["*"]
    # API rate limiting (requests per minute per IP); 0 disables
    rate_limit_requests_per_minute: int = 0

    # External APIs
    football_data_api_key: Optional[str] = None

    # Betfair API Configuration
    betfair_app_key: Optional[str] = None
    betfair_username: Optional[str] = None
    betfair_password: Optional[str] = None
    betfair_cert_file: Optional[str] = None
    betfair_key_file: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "protected_namespaces": ("settings_",),
    }


class APIConfig:
    """Konfiguration für externe APIs"""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        rate_limit: int,
        headers: dict[str, str],
        endpoints: dict[str, str],
    ):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.headers = headers
        self.endpoints = endpoints


# Global Settings Instance
settings = Settings()
