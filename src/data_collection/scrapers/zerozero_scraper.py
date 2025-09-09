import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter
from typing import Dict, Optional, Any
import re
from urllib.parse import urlparse

from common.http import DEFAULT_UAS, fetch_html

# ZeroZero (fussballzz.de) provides matches, referees, stadiums, players, coaches.
# Using shared HTTP utilities from common/http.py; parsing will be implemented later.


def determine_entity_type(url: str) -> str:
    """Determine the entity type from the ZeroZero URL."""
    # Parse URL path to determine entity type
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    if '/match/' in path or '/spiel/' in path:
        return 'match'
    elif '/referee/' in path or '/schiedsrichter/' in path:
        return 'referee'
    elif '/stadium/' in path or '/stadion/' in path:
        return 'stadium'
    elif '/player/' in path or '/spieler/' in path:
        return 'player'
    elif '/coach/' in path or '/trainer/' in path:
        return 'coach'
    elif '/team/' in path or '/verein/' in path:
        return 'team'
    else:
        return 'unknown'


def parse_zerozero_entity(html_content: str, url: str) -> Dict[str, Any]:
    """Parse ZeroZero page based on entity type."""
    from bs4 import BeautifulSoup
    
    entity_type = determine_entity_type(url)
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Entity-specific parsing
    if entity_type == 'match':
        return _parse_match_entity(soup, url)
    elif entity_type == 'player':
        return _parse_player_entity(soup, url)
    elif entity_type == 'coach':
        return _parse_coach_entity(soup, url)
    elif entity_type == 'referee':
        return _parse_referee_entity(soup, url)
    elif entity_type == 'stadium':
        return _parse_stadium_entity(soup, url)
    elif entity_type == 'team':
        return _parse_team_entity(soup, url)
    else:
        return _parse_generic_entity(soup, url)


def _parse_match_entity(soup, url: str) -> Dict[str, Any]:
    """Parse match information from ZeroZero."""
    data = {'entity_type': 'match', 'url': url}
    
    try:
        # Extract match title/teams
        title = soup.find('title')
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Look for score elements
        score_elements = soup.find_all(['span', 'div'], class_=re.compile(r'score|result', re.I))
        for elem in score_elements:
            text = elem.get_text(strip=True)
            if re.match(r'\d+:\d+|\d+-\d+', text):
                data['score'] = text
                break
        
        # Find team names
        team_links = soup.find_all('a', href=re.compile(r'/team|/verein', re.I))
        teams = []
        for link in team_links[:2]:  # Usually first 2 are the playing teams
            teams.append(link.get_text(strip=True))
        
        if len(teams) >= 2:
            data['home_team'] = teams[0]
            data['away_team'] = teams[1]
        
        # Find date information
        date_patterns = [r'\d{2}\.\d{2}\.\d{4}', r'\d{4}-\d{2}-\d{2}']
        for pattern in date_patterns:
            date_match = re.search(pattern, soup.get_text())
            if date_match:
                data['date'] = date_match.group()
                break
                
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_player_entity(soup, url: str) -> Dict[str, Any]:
    """Parse player information from ZeroZero."""
    data = {'entity_type': 'player', 'url': url}
    
    try:
        # Player name (usually in h1 or title)
        name_elem = soup.find('h1') or soup.find('title')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)
        
        # Find player details table
        details_table = soup.find('table') or soup.find('div', class_=re.compile(r'player|info', re.I))
        if details_table:
            rows = details_table.find_all('tr') if details_table.name == 'table' else details_table.find_all(['div', 'p'])
            
            for row in rows:
                text = row.get_text().lower()
                if 'position' in text or 'pos.' in text:
                    data['position'] = row.get_text(strip=True)
                elif 'birth' in text or 'geboren' in text or 'geb.' in text:
                    date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', row.get_text())
                    if date_match:
                        data['birth_date'] = date_match.group()
                elif 'nationality' in text or 'nation' in text:
                    data['nationality'] = row.get_text(strip=True)
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_coach_entity(soup, url: str) -> Dict[str, Any]:
    """Parse coach information from ZeroZero."""
    data = {'entity_type': 'coach', 'url': url}
    
    try:
        # Coach name
        name_elem = soup.find('h1') or soup.find('title')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)
        
        # Find teams coached
        team_links = soup.find_all('a', href=re.compile(r'/team|/verein', re.I))
        teams = [link.get_text(strip=True) for link in team_links[:3]]
        if teams:
            data['teams'] = teams
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_referee_entity(soup, url: str) -> Dict[str, Any]:
    """Parse referee information from ZeroZero."""
    data = {'entity_type': 'referee', 'url': url}
    
    try:
        # Referee name
        name_elem = soup.find('h1') or soup.find('title')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)
        
        # Find matches refereed
        match_links = soup.find_all('a', href=re.compile(r'/match|/spiel', re.I))
        data['recent_matches_count'] = len(match_links)
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_stadium_entity(soup, url: str) -> Dict[str, Any]:
    """Parse stadium information from ZeroZero."""
    data = {'entity_type': 'stadium', 'url': url}
    
    try:
        # Stadium name
        name_elem = soup.find('h1') or soup.find('title')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)
        
        # Find capacity if mentioned
        capacity_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*(?:capacity|plätze|zuschauer)', soup.get_text().lower())
        if capacity_match:
            data['capacity'] = capacity_match.group(1)
        
        # Find location/city
        location_keywords = ['city', 'stadt', 'ort', 'location']
        for keyword in location_keywords:
            if keyword in soup.get_text().lower():
                # Try to extract location context
                break
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_team_entity(soup, url: str) -> Dict[str, Any]:
    """Parse team information from ZeroZero."""
    data = {'entity_type': 'team', 'url': url}
    
    try:
        # Team name
        name_elem = soup.find('h1') or soup.find('title')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)
        
        # Find recent matches
        match_links = soup.find_all('a', href=re.compile(r'/match|/spiel', re.I))
        data['recent_matches_count'] = len(match_links[:10])  # Limit to reasonable number
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def _parse_generic_entity(soup, url: str) -> Dict[str, Any]:
    """Parse generic information when entity type is unknown."""
    data = {'entity_type': 'unknown', 'url': url}
    
    try:
        # Extract basic page info
        title = soup.find('title')
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Count different types of links to infer content type
        match_links = len(soup.find_all('a', href=re.compile(r'/match|/spiel', re.I)))
        player_links = len(soup.find_all('a', href=re.compile(r'/player|/spieler', re.I)))
        team_links = len(soup.find_all('a', href=re.compile(r'/team|/verein', re.I)))
        
        data['content_hints'] = {
            'match_links': match_links,
            'player_links': player_links,
            'team_links': team_links
        }
        
    except Exception as e:
        data['parse_error'] = str(e)
    
    return data


def process_one(args):
    if not args.url:
        raise ValueError(
            "Provide --url to ZeroZero entity (match, referee, stadium, player, coach)"
        )
    t0 = perf_counter()
    html_content = fetch_html(
        args.url,
        timeout=args.timeout,
        retries=args.retries,
        backoff=args.backoff,
        proxy=args.proxy,
        verbose=args.verbose,
        user_agents=(
            open(args.ua_file, encoding="utf-8").read().splitlines()
            if args.ua_file and os.path.exists(args.ua_file)
            else DEFAULT_UAS
        ),
        rotate_ua=args.ua_rotate,
        force_ua_on_429=args.force_ua_on_429,
        header_randomize=(not args.no_header_randomize),
        pre_jitter=args.pre_jitter,
    )
    dt = perf_counter() - t0
    if args.verbose:
        print(f"Fetched ZeroZero page in {dt*1000:.0f} ms -> {args.url}")
    
    # Parse depending on entity (match, referee, stadium, player, coach)
    try:
        entity_data = parse_zerozero_entity(html_content, args.url)
        
        result = {
            "source": "zerozero",
            "collector": entity_data.get('entity_type', 'generic'),
            "input": {"url": args.url},
            "data": entity_data,
            "status": "parsed",
            "timestamp": time.time(),
            "message": f"Successfully parsed {entity_data.get('entity_type', 'unknown')} entity",
        }
        
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.verbose else None))
        
    except Exception as e:
        error_result = {
            "source": "zerozero",
            "collector": "generic", 
            "input": {"url": args.url},
            "status": "error",
            "message": f"Failed to parse entity: {str(e)}",
        }
        print(json.dumps(error_result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="ZeroZero (fussballzz) Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="ZeroZero URL")
    p.add_argument("--batch-file", type=str, default=None, help="CSV with column: url")
    p.add_argument("--min-interval", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--backoff", type=float, default=1.5)
    p.add_argument("--proxy", type=str, default=None)
    p.add_argument("--ua-file", type=str, default=None)
    p.add_argument("--ua-rotate", action="store_true")
    p.add_argument("--force-ua-on-429", action="store_true")
    p.add_argument("--no-header-randomize", action="store_true")
    p.add_argument("--pre-jitter", type=float, default=0.0)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.batch_file:
        with open(args.batch_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            total = 0
            for row in reader:
                local = argparse.Namespace(**vars(args))
                local.url = row.get("url")
                process_one(local)
                total += 1
                if args.min_interval and args.min_interval > 0:
                    time.sleep(args.min_interval)
        if args.verbose:
            print(f"Batch finished, items={total}")
    else:
        process_one(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
