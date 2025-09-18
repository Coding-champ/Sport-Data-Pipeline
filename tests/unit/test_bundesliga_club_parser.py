import os
import sys
from pathlib import Path
import json

# Ensure project root is on sys.path so 'import src.*' works
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_collection.scrapers.bundesliga.club_scraper import BundesligaClubScraper


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
    data = scraper._parse_detail(html, "https://www.bundesliga.com/en/bundesliga/clubs/fc-bayern-muenchen")

    # Assert basics
    assert data is not None
    assert data.get("name"), "Club name should be detected"
    profile = data.get("profile_info") or {}
    assert isinstance(profile, dict) and profile, "profile_info should be populated"

    # Expect at least some of these keys via hydration/ld-json mapping
    expected_any = [
        "full_name",
        "founded",
        "club_colors",
        "stadium",
        "capacity",
        "street",
        "city",
        "address",
        "phone",
        "fax",
        "email",
        "website",
    ]
    assert any(k in profile for k in expected_any), f"Expected any of {expected_any} in profile_info"

    # Flattened fields should mirror profile when present
    for key in ("full_name","founded","capacity","club_colors","address","street","city","phone","fax","email","website","stadium"):
        if key in profile:
            assert data.get(key) == profile.get(key)
