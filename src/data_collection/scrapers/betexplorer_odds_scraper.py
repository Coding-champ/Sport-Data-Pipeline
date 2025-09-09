import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter
from typing import Dict, List, Optional, Tuple

from common.http import DEFAULT_UAS, fetch_html

# NOTE: Odds providers often block scraping. Use responsibly and consider legal aspects.
# Using shared HTTP utilities from common/http.py. In practice, normalize markets and snapshot odds over time.


def parse_odds_tables(html_content: str) -> Dict[str, List[Dict]]:
    """Parse BetExplorer odds tables for various markets.
    
    Args:
        html_content: HTML content of the BetExplorer page
        
    Returns:
        Dictionary with parsed odds for different markets (1X2, AH, O/U)
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    odds_data = {
        "1x2": [],
        "asian_handicap": [],
        "over_under": []
    }
    
    try:
        # Parse 1X2 odds table
        x12_table = soup.find('table', {'class': lambda x: x and 'odds-table' in x})
        if x12_table:
            for row in x12_table.find_all('tr')[1:]:  # Skip header
                cells = row.find_all('td')
                if len(cells) >= 4:  # Bookmaker, 1, X, 2
                    bookmaker = cells[0].get_text(strip=True)
                    home_odds = cells[1].get_text(strip=True)
                    draw_odds = cells[2].get_text(strip=True)
                    away_odds = cells[3].get_text(strip=True)
                    
                    odds_data["1x2"].append({
                        "bookmaker": bookmaker,
                        "home": _parse_odds_value(home_odds),
                        "draw": _parse_odds_value(draw_odds),
                        "away": _parse_odds_value(away_odds),
                        "market_type": "1x2"
                    })
        
        # Parse Asian Handicap odds
        ah_table = soup.find('table', {'id': 'handicap-table'}) or soup.find('div', {'class': 'handicap-odds'})
        if ah_table:
            for row in ah_table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    bookmaker = cells[0].get_text(strip=True)
                    handicap = cells[1].get_text(strip=True)
                    home_odds = cells[2].get_text(strip=True)
                    away_odds = cells[3].get_text(strip=True)
                    
                    odds_data["asian_handicap"].append({
                        "bookmaker": bookmaker,
                        "handicap": handicap,
                        "home": _parse_odds_value(home_odds),
                        "away": _parse_odds_value(away_odds),
                        "market_type": "asian_handicap"
                    })
        
        # Parse Over/Under odds
        ou_table = soup.find('table', {'id': 'ou-table'}) or soup.find('div', {'class': 'over-under-odds'})
        if ou_table:
            for row in ou_table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    bookmaker = cells[0].get_text(strip=True)
                    total = cells[1].get_text(strip=True)
                    over_odds = cells[2].get_text(strip=True)
                    under_odds = cells[3].get_text(strip=True)
                    
                    odds_data["over_under"].append({
                        "bookmaker": bookmaker,
                        "total": total,
                        "over": _parse_odds_value(over_odds),
                        "under": _parse_odds_value(under_odds),
                        "market_type": "over_under"
                    })
                    
    except Exception as e:
        print(f"Error parsing odds tables: {e}", file=sys.stderr)
    
    return odds_data


def _parse_odds_value(odds_text: str) -> Optional[float]:
    """Parse odds value from text, handling various formats."""
    try:
        # Remove any extra whitespace and common prefixes/suffixes
        cleaned = odds_text.strip().replace(',', '.')
        
        # Handle different formats: 1.50, 3/2, +150, etc.
        if '/' in cleaned:
            # Fractional odds like 3/2
            parts = cleaned.split('/')
            if len(parts) == 2:
                return (float(parts[0]) / float(parts[1])) + 1.0
        elif cleaned.startswith(('+', '-')):
            # American odds like +150, -110
            value = float(cleaned[1:])
            if cleaned.startswith('+'):
                return (value / 100) + 1.0
            else:
                return (100 / value) + 1.0
        else:
            # Decimal odds like 1.50
            return float(cleaned)
    except (ValueError, ZeroDivisionError):
        return None
    
    return None


def create_odds_snapshot(url: str, odds_data: Dict[str, List[Dict]]) -> Dict:
    """Create a standardized odds snapshot."""
    snapshot = {
        "source": "betexplorer",
        "url": url,
        "timestamp": time.time(),
        "markets": odds_data,
        "total_bookmakers": len(set(
            item.get("bookmaker", "") 
            for market in odds_data.values() 
            for item in market
        )),
        "status": "parsed"
    }
    
    return snapshot


def process_one(args):
    if not args.url:
        raise ValueError("Provide --url to a BetExplorer match page or odds page")
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
        print(f"Fetched BetExplorer odds page in {dt*1000:.0f} ms -> {args.url}")
    
    # Parse odds tables (1X2, AH, O/U) and create snapshot
    try:
        odds_data = parse_odds_tables(html_content)
        snapshot = create_odds_snapshot(args.url, odds_data)
        
        print(json.dumps(snapshot, ensure_ascii=False, indent=2 if args.verbose else None))
        
    except Exception as e:
        error_result = {
            "source": "betexplorer",
            "collector": "odds",
            "input": {"url": args.url},
            "status": "error",
            "message": f"Failed to parse odds: {str(e)}",
        }
        print(json.dumps(error_result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="BetExplorer Odds Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="BetExplorer match/odds URL")
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
