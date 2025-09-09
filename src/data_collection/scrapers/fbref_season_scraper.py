import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin

from src.common.http import DEFAULT_UAS, fetch_html

# Using shared HTTP utilities from common/http.py


def parse_match_links(html_content: str, base_url: str) -> List[Dict[str, str]]:
    """Parse FBref season page for all match links.
    
    Args:
        html_content: HTML content of the FBref season page
        base_url: Base URL for resolving relative links
        
    Returns:
        List of match dictionaries with URLs and metadata
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    matches = []
    
    try:
        # Look for fixture tables - FBref typically has a "Scores & Fixtures" section
        fixture_tables = soup.find_all('table', {'id': re.compile(r'.*fixture.*|.*scores.*', re.I)})
        
        for table in fixture_tables:
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
            
            for row in rows:
                match_data = _parse_match_row(row, base_url)
                if match_data:
                    matches.append(match_data)
        
        # Also look for match links in the general structure
        match_links = soup.find_all('a', href=re.compile(r'/en/matches/.*/'))
        for link in match_links:
            href = link.get('href', '')
            if href and '/en/matches/' in href:
                # Extract match info from the link context
                match_info = _extract_match_info_from_link(link, base_url)
                if match_info and match_info not in matches:
                    matches.append(match_info)
        
    except Exception as e:
        print(f"Error parsing match links: {e}", file=sys.stderr)
    
    return matches


def _parse_match_row(row, base_url: str) -> Optional[Dict[str, str]]:
    """Parse a single match row from fixtures table."""
    try:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 3:
            return None
            
        match_data = {}
        
        # Look for match report link
        match_link = None
        for cell in cells:
            link = cell.find('a', href=re.compile(r'/en/matches/'))
            if link:
                match_link = link
                break
        
        if not match_link:
            return None
            
        href = match_link.get('href', '')
        match_data['url'] = urljoin(base_url, href)
        
        # Extract match ID from URL
        match_id_match = re.search(r'/en/matches/([^/]+)/', href)
        if match_id_match:
            match_data['match_id'] = match_id_match.group(1)
        
        # Try to extract date and teams from the row
        for i, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            
            # Date pattern
            if re.match(r'\d{4}-\d{2}-\d{2}', cell_text):
                match_data['date'] = cell_text
            
            # Score pattern (e.g., "2-1", "0-0")
            if re.match(r'\d+-\d+', cell_text):
                match_data['score'] = cell_text
            
            # Team names (look for team links)
            team_link = cell.find('a', href=re.compile(r'/en/squads/'))
            if team_link:
                team_name = team_link.get_text(strip=True)
                if 'home_team' not in match_data:
                    match_data['home_team'] = team_name
                elif 'away_team' not in match_data:
                    match_data['away_team'] = team_name
        
        return match_data if match_data.get('url') else None
        
    except Exception as e:
        print(f"Error parsing match row: {e}", file=sys.stderr)
        return None


def _extract_match_info_from_link(link, base_url: str) -> Optional[Dict[str, str]]:
    """Extract match info from a standalone match link."""
    try:
        href = link.get('href', '')
        if not href or '/en/matches/' not in href:
            return None
            
        match_data = {
            'url': urljoin(base_url, href)
        }
        
        # Extract match ID
        match_id_match = re.search(r'/en/matches/([^/]+)/', href)
        if match_id_match:
            match_data['match_id'] = match_id_match.group(1)
        
        # Try to get info from link text or context
        link_text = link.get_text(strip=True)
        if link_text:
            match_data['description'] = link_text
        
        return match_data
        
    except Exception:
        return None


def write_matches_csv(matches: List[Dict[str, str]], output_file: str):
    """Write match data to CSV file for batch processing."""
    if not matches:
        print("No matches found to write to CSV")
        return
        
    # Define CSV columns
    fieldnames = ['url', 'match_id', 'date', 'home_team', 'away_team', 'score', 'description']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for match in matches:
            # Ensure all fields exist
            row = {field: match.get(field, '') for field in fieldnames}
            writer.writerow(row)
    
    print(f"Written {len(matches)} matches to {output_file}")


def process_one(args):
    # Expected inputs: comp_id and season path to list all matches and enqueue to batch
    if not args.url and not (args.comp_id and args.season):
        raise ValueError("Provide --url to a competition season page or --comp-id and --season")
    url = args.url or f"https://fbref.com/en/comps/{args.comp_id}/{args.season}/"
    t0 = perf_counter()
    html_content = fetch_html(
        url,
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
        print(f"Fetched season page in {dt*1000:.0f} ms -> {url}")
    
    # Parse all match links for the season and emit a CSV for fbref_match_collector --batch-file
    try:
        matches = parse_match_links(html_content, "https://fbref.com")
        
        # Generate output filename based on inputs
        if args.output_csv:
            output_file = args.output_csv
        else:
            season_safe = (args.season or "season").replace("/", "-")
            comp_safe = (args.comp_id or "comp").replace("/", "-") 
            output_file = f"fbref_matches_{comp_safe}_{season_safe}.csv"
        
        # Write matches to CSV
        write_matches_csv(matches, output_file)
        
        # Output JSON summary
        result = {
            "source": "fbref",
            "collector": "season",
            "input": {
                "url": url,
                "comp_id": args.comp_id,
                "season": args.season,
            },
            "output": {
                "csv_file": output_file,
                "matches_found": len(matches),
            },
            "status": "completed",
            "message": f"Extracted {len(matches)} match links and wrote to {output_file}",
        }
        
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.verbose else None))
        
    except Exception as e:
        error_result = {
            "source": "fbref",
            "collector": "season",
            "input": {"url": url, "comp_id": args.comp_id, "season": args.season},
            "status": "error",
            "message": f"Failed to parse match links: {str(e)}",
        }
        print(json.dumps(error_result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="FBref Season Collector (skeleton)")
    p.add_argument("--url", type=str, help="FBref competition season URL", default=None)
    p.add_argument("--comp-id", type=str, help="Competition ID (e.g., 9 for Premier League)")
    p.add_argument(
        "--season", type=str, help="Season segment (e.g., 2024-2025-Premier-League-Stats)"
    )
    p.add_argument(
        "--output-csv", type=str, help="Output CSV file for matches (auto-generated if not provided)", default=None
    )
    p.add_argument(
        "--batch-file",
        type=str,
        help="CSV with headers depending on source (url, ...) for batch processing",
        default=None,
    )
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
                local.url = row.get("url") or None
                local.comp_id = row.get("comp_id") or args.comp_id
                local.season = row.get("season") or args.season
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