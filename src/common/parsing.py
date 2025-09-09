import re
from datetime import datetime

from bs4 import BeautifulSoup

# Date formats seen commonly across sources
DATE_FORMATS = [
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%d %b %Y",
]


def clean_text(s: str | None) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s.strip())
    return s or None


def parse_int(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"-?\d+", s.replace(".", ""))
    return int(m.group(0)) if m else None


def parse_decimal(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_date(s: str | None) -> datetime.date | None:
    if not s:
        return None
    s = clean_text(s)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def extract_tm_player_id_from_href(href: str | None) -> str | None:
    # Examples: /spieler/35616/..., /profile/player/35616
    if not href:
        return None
    m = re.search(r"/(spieler|player)/([0-9]+)", href)
    if m:
        return m.group(2)
    m = re.search(r"/(profil|profile)/(spieler|player)/([0-9]+)", href)
    if m:
        return m.group(3)
    m = re.search(r"/(\d+)(?:[^\d]|$)", href)
    return m.group(1) if m else None
