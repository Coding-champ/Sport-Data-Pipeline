import os
import sys
from pathlib import Path
import json

# Ensure project root is on sys.path so 'import src.*' works
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_collection.scrapers.bundesliga.bundesliga_club_scraper import BundesligaClubScraper


class DummyDB:
    async def bulk_insert(self, *a, **kw):
        return None


def test_parse_bayern_profile_from_saved_html_or_hydration(monkeypatch):
    # Arrange
    db = DummyDB()
    scraper = BundesligaClubScraper(db_manager=db, save_html=False)

    # Load saved Bayern page
    base = os.path.join(os.getcwd(), "reports", "bundesliga", "clubs")
    candidates = [
        os.path.join(base, "fc-bayern-muenchen__rendered.html"),
        os.path.join(base, "fc-bayern-muenchen.html"),
    ]
    html = None
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                html = f.read()
            break
    # If no saved page or saved page has no data-hydration, build a minimal synthetic hydration page
    if not html or ("__NUXT__" not in html and "application/ld+json" not in html and "section id=\"profile\"" not in html.lower()):
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>FC Bayern München - Clubs - Bundesliga</title></head>"
            "<body>"
            "<h1>FC Bayern München</h1>"
            "<script>window.__NUXT__ = {\"data\":[{\"club\": {\"slug\": \"fc-bayern-muenchen\", \"name\": \"FC Bayern München\"," 
            "\"fullName\": \"FC Bayern München e.V.\", \"founded\": \"1900\", \"contact\": {\"street\": \"Säbener Straße\","
            "\"houseNumber\": \"51-57\", \"postalCode\": \"81547\", \"city\": \"München\", \"phone\": \"+49 89 699 31-0\","
            "\"fax\": \"+49 89 699 31-813\", \"email\": \"service@fcb.de\", \"homepage\": \"www.fcbayern.com\"},"
            "\"colors\": {\"club\": {\"primary\": {\"hex\": \"#DC052D\"}, \"secondary\": {\"hex\": \"#0066B2\"}},"
            "\"jersey\": {\"home\": {\"primary\": {\"hex\": \"#DC052D\"}, \"secondary\": {\"hex\": \"#FFFFFF\"}, \"number\": {\"hex\": \"#FFFFFF\"}}}},"
            "\"stadium\": {\"name\": \"Allianz Arena\", \"capacity\": \"75,024\"}}}]};</script>"
            "</body></html>"
        )

    # Act
    data = scraper.parse_club_html(html, "https://www.bundesliga.com/en/bundesliga/clubs/fc-bayern-muenchen")

    # Assert basics
    assert data is not None
    assert data.get("name"), "Club name should be detected"
    # New simplified dict shape asserts
    assert 'stadium' in data
    assert 'founded_year' in data or 'founded' in data  # depending on parse success
    assert 'city' in data
    assert data.get('source_url')
