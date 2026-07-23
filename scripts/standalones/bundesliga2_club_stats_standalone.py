#!/usr/bin/env python3
"""Standalone 2. Bundesliga club stats scraper.

The script fetches the 2. Bundesliga club overview page, extracts the club
slugs from the overview cards, then visits each club detail page and reads the
current matchday and season statistics into a compact JSON structure.

It intentionally depends only on the Python standard library so it can later be
packaged as a standalone executable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://www.bundesliga.com"
OVERVIEW_URL = "https://www.bundesliga.com/de/2bundesliga/clubs"
SEASON_CODE = "2627"
LEAGUE_CODE = "2bundesliga"


STAT_LABELS = [
    ("Torschüsse", re.compile(r"torschusse")),
    ("Eigentore", re.compile(r"eigentore")),
    ("Elfmeter", re.compile(r"elfmeter(?![-\s]*tore)")),
    ("Elfmetertore", re.compile(r"elfmeter[-\s]*tore")),
    ("Tore", re.compile(r"(?<!elfmeter[-\s])tore")),
    ("Pfosten / Latte", re.compile(r"pfosten\s*/\s*latte")),
    ("gew. Zweikämpfe", re.compile(r"gew\.\s*zweikampfe")),
    ("gew. Kopfduelle", re.compile(r"gew\.\s*kopfduelle")),
    ("Ballbesitz (%)", re.compile(r"ballbesitz\s*\(%\)")),
    ("Karten", re.compile(r"(?<!gelbe\s)karten")),
    ("Gelbe Karten", re.compile(r"gelbe\s*karten")),
    ("Flanken aus dem Spiel", re.compile(r"flanken\s+aus\s+dem\s+spiel")),
    ("Laufdistanz (km)", re.compile(r"laufdistanz\s*\(km\)")),
    ("Fouls am Gegner", re.compile(r"fouls\s+am\s+gegner")),
    ("Intensive Läufe", re.compile(r"intensive\s+laufe")),
    ("Passquote (%)", re.compile(r"passquote\s*\(%\)")),
    ("Sprints", re.compile(r"sprints")),
]


@dataclass(frozen=True)
class ClubEntry:
    club_id: str
    club_name: str
    url: str


class VisibleHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip_depth = 0
        self._current_href: str | None = None
        self._current_link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            attr_map = {key: value for key, value in attrs}
            self._current_href = attr_map.get("href")
            self._current_link_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "a" and self._current_href is not None:
            anchor_text = normalize_whitespace(" ".join(self._current_link_parts))
            self.links.append((self._current_href, anchor_text))
            self._current_href = None
            self._current_link_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self.text_parts.append(data)
            if self._current_href is not None:
                self._current_link_parts.append(data)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def fetch_html(url: str, timeout: int, user_agent: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        raw = response.read()
        return raw.decode(content_type, errors="replace")


def slug_to_club_name(slug: str) -> str:
    special = {
        "dsc-arminia-bielefeld": "DSC Arminia Bielefeld",
        "vfl-bochum-1848": "VfL Bochum 1848",
        "eintracht-braunschweig": "Eintracht Braunschweig",
        "fc-energie-cottbus": "FC Energie Cottbus",
        "sv-darmstadt-98": "SV Darmstadt 98",
        "fortuna-duesseldorf": "Fortuna Düsseldorf",
        "1-fc-kaiserslautern": "1. FC Kaiserslautern",
        "hertha-bsc": "Hertha BSC",
        "hannover-96": "Hannover 96",
        "karlsruher-sc": "Karlsruher SC",
        "1-fc-magdeburg": "1. FC Magdeburg",
        "spvgg-greuther-fuerth": "SpVgg Greuther Fürth",
        "preussen-muenster": "Preußen Münster",
        "1-fc-nuernberg": "1. FC Nürnberg",
        "sc-paderborn-07": "SC Paderborn 07",
        "holstein-kiel": "Holstein Kiel",
        "ssv-jahn-regensburg": "SSV Jahn Regensburg",
    }
    slug_l = slug.lower().strip("/")
    if slug_l in special:
        return special[slug_l]

    tokens = slug_l.split("-")
    parts: list[str] = []
    abbreviations = {
        "fc": "FC",
        "sv": "SV",
        "tsg": "TSG",
        "rb": "RB",
        "vfb": "VfB",
        "vfl": "VfL",
        "dsc": "DSC",
        "spvgg": "SpVgg",
        "ssv": "SSV",
        "bsc": "BSC",
        "sc": "SC",
        "fsv": "FSV",
    }
    transliterations = {
        "muenchen": "München",
        "koeln": "Köln",
        "duesseldorf": "Düsseldorf",
        "nuernberg": "Nürnberg",
        "cottbus": "Cottbus",
        "braunschweig": "Braunschweig",
        "kaiserslautern": "Kaiserslautern",
        "paderborn": "Paderborn",
        "regensburg": "Regensburg",
        "muenster": "Münster",
        "moenchengladbach": "Mönchengladbach",
        "fuerth": "Fürth",
        "st": "St.",
    }

    for index, token in enumerate(tokens):
        if index == 0 and token == "1":
            parts.append("1.")
            continue
        if token in transliterations:
            parts.append(transliterations[token])
            continue
        if token in abbreviations:
            parts.append(abbreviations[token])
            continue
        if token.isdigit() and len(token) <= 4:
            parts.append(token)
            continue
        if token == "sport" and len(tokens) > index + 1 and tokens[index + 1] == "club":
            parts.append("Sport-Club")
            continue
        if token == "club" and parts and parts[-1] == "Sport-Club":
            continue
        parts.append(token.capitalize())

    return " ".join(parts)


def extract_club_overview(html: str) -> list[ClubEntry]:
    parser = VisibleHtmlParser()
    parser.feed(html)

    clubs: dict[str, ClubEntry] = {}
    link_pattern = re.compile(rf"^/(?:de|en)/{LEAGUE_CODE}/clubs/([^/?#]+)$")

    for href, anchor_text in parser.links:
        resolved = urljoin(BASE_URL, href)
        parsed = urlparse(resolved)
        match = link_pattern.match(parsed.path)
        if not match:
            continue
        slug = match.group(1).strip()
        if not slug or slug in {"clubs", "club", LEAGUE_CODE}:
            continue
        if slug not in clubs:
            clubs[slug] = ClubEntry(
                club_id=slug,
                club_name=slug_to_club_name(slug),
                url=resolved,
            )

    if clubs:
        return list(clubs.values())

    fallback_slugs = re.findall(rf"/de/{LEAGUE_CODE}/clubs/([^/?#\"]+)", html)
    for slug in fallback_slugs:
        slug = slug.strip()
        if slug and slug not in clubs and slug not in {"clubs", "club"}:
            clubs[slug] = ClubEntry(
                club_id=slug,
                club_name=slug_to_club_name(slug),
                url=f"{BASE_URL}/de/{LEAGUE_CODE}/clubs/{slug}",
            )
    return list(clubs.values())


def extract_stats_section(text: str) -> str:
    normalized = normalize_whitespace(strip_accents(text).lower())
    marker = "saison-statistiken"
    marker_index = normalized.find(marker)
    if marker_index == -1:
        marker_index = normalized.find("statistik")
    if marker_index == -1:
        return normalized

    tail = normalized[marker_index:]
    end_marker = tail.find("news")
    if end_marker != -1:
        tail = tail[:end_marker]
    return tail[:4000]


def parse_stat_value(raw_value: str) -> int | float | None:
    candidate = raw_value.strip().replace(".", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", candidate)
    if not match:
        return None
    number = match.group(0)
    if "." in number:
        try:
            return float(number)
        except ValueError:
            return None
    try:
        return int(number)
    except ValueError:
        return None


def strip_html_tags(fragment: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", fragment))


def extract_current_sp(html: str, club_name: str) -> int | None:
    club_norm = normalize_whitespace(strip_accents(club_name).lower())
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.I | re.S):
        row_text = strip_html_tags(row_html)
        if not row_text:
            continue
        row_norm = normalize_whitespace(strip_accents(row_text).lower())
        if club_norm not in row_norm:
            continue
        name_index = row_norm.rfind(club_norm)
        suffix = row_text
        if name_index != -1:
            suffix = row_text[name_index + len(club_name):]
        numbers = re.findall(r"\b\d+\b", suffix)
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                continue
    return None


def extract_club_stats(html: str) -> dict[str, int | float]:
    parser = VisibleHtmlParser()
    parser.feed(html)
    visible_text = normalize_whitespace(" ".join(parser.text_parts))
    stats_text = extract_stats_section(visible_text)

    stats: dict[str, int | float] = {}
    cursor = 0
    for label, pattern in STAT_LABELS:
        match = pattern.search(stats_text[cursor:])
        if not match:
            continue
        after = stats_text[cursor + match.end():]
        number_match = re.search(r"-?\d+(?:[\.,]\d+)?", after)
        if not number_match:
            cursor += match.end()
            continue
        value = parse_stat_value(number_match.group(0))
        if value is not None:
            stats[label] = value
        cursor += match.end() + number_match.end()

    return stats


def scrape_clubs(
    overview_url: str,
    timeout: int,
    delay: float,
    user_agent: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    overview_html = fetch_html(overview_url, timeout=timeout, user_agent=user_agent)
    clubs = extract_club_overview(overview_html)
    if limit is not None:
        clubs = clubs[:limit]

    results: list[dict[str, Any]] = []
    for index, club in enumerate(clubs, start=1):
        print(f"[{index}/{len(clubs)}] Scraping {club.club_name}", flush=True)
        try:
            detail_html = fetch_html(club.url, timeout=timeout, user_agent=user_agent)
            current_sp = extract_current_sp(detail_html, club.club_name)
            stats = extract_club_stats(detail_html)
        except Exception as exc:
            print(f"[WARN] Skipping {club.club_name}: {exc}", file=sys.stderr)
            if delay > 0 and index < len(clubs):
                time.sleep(delay)
            continue

        results.append(
            {
                "club_id": club.club_id,
                "club_name": club.club_name,
                "url": club.url,
                "matchday": current_sp,
                "stats": stats,
            }
        )
        if delay > 0 and index < len(clubs):
            time.sleep(delay)

    return results


def resolve_output_path(output: str) -> Path:
    path = Path(output)
    if path.suffix:
        return path
    return path.with_suffix(".json")


def build_default_output_path(matchday: int | None) -> Path:
    safe_matchday = 0 if matchday is None else matchday
    return Path(f"bundesliga2_{SEASON_CODE}_matchday_{safe_matchday}.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape 2. Bundesliga club overview links and season statistics into JSON.",
    )
    parser.add_argument("--overview-url", default=OVERVIEW_URL, help="Club overview URL to scrape.")
    parser.add_argument(
        "--output",
        default=None,
        help=f"Output JSON file path. Defaults to {LEAGUE_CODE}_{SEASON_CODE}_matchday_[matchday].json in the current directory.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
    parser.add_argument("--delay", type=float, default=0.75, help="Delay between club detail requests in seconds.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for the number of clubs to scrape.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level.")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON without indentation.")
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        help="User agent string for HTTP requests.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        results = scrape_clubs(
            overview_url=args.overview_url,
            timeout=args.timeout,
            delay=args.delay,
            user_agent=args.user_agent,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1

    matchday_values = [item.get("matchday") for item in results if isinstance(item.get("matchday"), int)]
    current_matchday = max(matchday_values) if matchday_values else None

    if args.output:
        output_path = resolve_output_path(args.output)
    else:
        output_path = build_default_output_path(current_matchday)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.compact:
        payload = json.dumps(results, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(results, ensure_ascii=False, indent=args.indent)

    output_path.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(results)} clubs to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())