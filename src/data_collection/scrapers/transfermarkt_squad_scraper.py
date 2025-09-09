import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter
from typing import List, Dict, Optional
import re
from datetime import datetime

from common.http import DEFAULT_UAS, fetch_html

# Using shared HTTP utilities from common/http.py


def parse_squad_table(html_content: str) -> List[Dict[str, str]]:
    """Parse Transfermarkt squad page for player details.
    
    Args:
        html_content: HTML content of the Transfermarkt squad page
        
    Returns:
        List of player dictionaries with squad information
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    players = []
    
    try:
        # Find the main squad table - usually has 'items' class
        squad_table = soup.find('table', {'class': lambda x: x and 'items' in x})
        
        if not squad_table:
            print("Squad table not found", file=sys.stderr)
            return players
            
        # Parse each player row
        rows = squad_table.find('tbody').find_all('tr') if squad_table.find('tbody') else squad_table.find_all('tr')[1:]
        
        for row in rows:
            player_data = _parse_player_row(row)
            if player_data:
                players.append(player_data)
                
    except Exception as e:
        print(f"Error parsing squad table: {e}", file=sys.stderr)
    
    return players


def _parse_player_row(row) -> Optional[Dict[str, str]]:
    """Parse a single player row from the squad table."""
    try:
        cells = row.find_all('td')
        if len(cells) < 5:  # Minimum expected columns
            return None
            
        player_data = {}
        
        # Squad number (usually first meaningful cell)
        for i, cell in enumerate(cells[:3]):  # Check first few cells
            text = cell.get_text(strip=True)
            if text.isdigit() and 1 <= int(text) <= 99:
                player_data['number'] = int(text)
                break
        
        # Player name and link
        name_cell = None
        for cell in cells:
            player_link = cell.find('a', href=re.compile(r'/profil/spieler/'))
            if player_link:
                name_cell = cell
                break
                
        if name_cell:
            player_link = name_cell.find('a', href=re.compile(r'/profil/spieler/'))
            player_data['name'] = player_link.get_text(strip=True)
            player_data['profile_url'] = player_link.get('href', '')
            
            # Extract player ID from URL
            player_id_match = re.search(r'/profil/spieler/(\d+)', player_data['profile_url'])
            if player_id_match:
                player_data['transfermarkt_id'] = player_id_match.group(1)
        
        # Position
        position_cell = next((cell for cell in cells if 
                             _is_position_cell(cell.get_text(strip=True))), None)
        if position_cell:
            player_data['position'] = position_cell.get_text(strip=True)
        
        # Age (birth date)
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            # Look for date pattern or age
            if re.search(r'\d{2}\.\d{2}\.\d{4}', cell_text):
                player_data['birth_date'] = cell_text
                # Calculate age
                try:
                    birth_date = datetime.strptime(cell_text, '%d.%m.%Y')
                    age = (datetime.now() - birth_date).days // 365
                    player_data['age'] = age
                except:
                    pass
            elif re.match(r'^\d{2}$', cell_text) and int(cell_text) > 15 and int(cell_text) < 50:
                player_data['age'] = int(cell_text)
        
        # Nationality (look for flag images)
        for cell in cells:
            flag_img = cell.find('img', {'class': lambda x: x and 'flaggenrahmen' in x})
            if flag_img:
                nationality = flag_img.get('alt', '') or flag_img.get('title', '')
                if nationality:
                    player_data['nationality'] = nationality
                break
        
        # Market value
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if '€' in cell_text and ('m' in cell_text.lower() or 'k' in cell_text.lower() or 'Th.' in cell_text):
                player_data['market_value'] = _parse_market_value(cell_text)
                player_data['market_value_text'] = cell_text
                break
        
        # Contract expiry
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if re.search(r'\d{2}\.\d{2}\.\d{4}', cell_text) and 'birth_date' in player_data and cell_text != player_data['birth_date']:
                player_data['contract_expiry'] = cell_text
                break
        
        return player_data if player_data.get('name') else None
        
    except Exception as e:
        print(f"Error parsing player row: {e}", file=sys.stderr)
        return None


def _is_position_cell(text: str) -> bool:
    """Check if text represents a football position."""
    positions = {
        'GK', 'TW',  # Goalkeeper
        'CB', 'CD', 'SW', 'LB', 'RB', 'LWB', 'RWB', 'DF',  # Defenders
        'CM', 'CDM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'MF',  # Midfielders
        'CF', 'ST', 'LF', 'RF', 'SS', 'FW'  # Forwards
    }
    return text.upper() in positions


def _parse_market_value(value_text: str) -> Optional[float]:
    """Parse market value from Transfermarkt format."""
    try:
        # Remove currency symbols and spaces
        cleaned = re.sub(r'[€$£,\s]', '', value_text.lower())
        
        if 'm' in cleaned:
            # Million (e.g., "50.00m")
            number = float(cleaned.replace('m', ''))
            return number * 1000000
        elif 'k' in cleaned:
            # Thousand (e.g., "500k")
            number = float(cleaned.replace('k', ''))
            return number * 1000
        elif 'th.' in cleaned:
            # Thousand German format (e.g., "500Th.")
            number = float(cleaned.replace('th.', ''))
            return number * 1000
        else:
            # Try direct conversion
            return float(cleaned) if cleaned else None
            
    except (ValueError, AttributeError):
        return None


def create_squad_report(url: str, club_id: str, season: str, players: List[Dict]) -> Dict:
    """Create standardized squad report."""
    return {
        "source": "transfermarkt",
        "collector": "squad",
        "input": {
            "url": url,
            "club_id": club_id,
            "season": season
        },
        "data": {
            "players": players,
            "summary": {
                "total_players": len(players),
                "positions": list(set(p.get('position', 'Unknown') for p in players)),
                "avg_age": sum(p.get('age', 0) for p in players if p.get('age', 0) > 0) / max(1, len([p for p in players if p.get('age', 0) > 0])),
                "total_market_value": sum(p.get('market_value', 0) for p in players if p.get('market_value')),
            }
        },
        "timestamp": time.time(),
        "status": "parsed"
    }


def process_one(args):
    if not args.url and not (args.club_id and args.season):
        raise ValueError("Provide --url or --club-id and --season (e.g., 27 and 2025)")
    url = (
        args.url
        or f"https://www.transfermarkt.de/-/kader/verein/{args.club_id}/saison_id/{args.season}/plus/1"
    )
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
        print(f"Fetched squad page in {dt*1000:.0f} ms -> {url}")
    
    # Parse squad table (number, player, position, age, nationality, market value, contract)
    try:
        players = parse_squad_table(html_content)
        report = create_squad_report(url, args.club_id, args.season, players)
        
        print(json.dumps(report, ensure_ascii=False, indent=2 if args.verbose else None))
        
    except Exception as e:
        error_result = {
            "source": "transfermarkt",
            "collector": "squad",
            "input": {"url": url, "club_id": args.club_id, "season": args.season},
            "status": "error",
            "message": f"Failed to parse squad: {str(e)}",
        }
        print(json.dumps(error_result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Transfermarkt Squad Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="Transfermarkt squad URL")
    p.add_argument("--club-id", type=str, default=None, help="Transfermarkt club id")
    p.add_argument("--season", type=str, default=None, help="Season year, e.g. 2025")
    p.add_argument(
        "--batch-file", type=str, default=None, help="CSV with columns: url|club_id,season"
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
                local.club_id = row.get("club_id") or args.club_id
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
