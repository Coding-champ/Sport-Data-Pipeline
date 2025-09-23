"""Backward compatibility shim for BundesligaClubScraper.

Historically the Bundesliga club scraper lived at
`src.data_collection.scrapers.bundesliga_club_scraper`.
It was refactored into the package subdirectory `bundesliga/`.

Older imports (tests, docs, runner scripts) still reference the old path.
This shim re-exports the public classes to avoid breaking those imports
while allowing new code to use the consolidated package location.
"""

from .bundesliga.bundesliga_club_scraper import (  # type: ignore
    BundesligaClubScraper,
)

__all__ = ["BundesligaClubScraper"]
