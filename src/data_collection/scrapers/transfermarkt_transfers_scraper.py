import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter
from typing import List, Dict, Optional
import re

from common.http import DEFAULT_UAS, fetch_html

# Using shared HTTP utilities from common/http.py


def parse_transfer_tables(html_content: str) -> Dict[str, List[Dict]]:
    """Parse Transfermarkt transfers page for inbound and outbound transfers.
    
    Args:
        html_content: HTML content of the Transfermarkt transfers page
        
    Returns:
        Dictionary with parsed transfers data for in/out transfers
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    transfers_data = {
        "inbound": [],
        "outbound": []
    }
    
    try:
        # Find transfer tables - they usually have specific classes
        tables = soup.find_all('table', {'class': lambda x: x and 'items' in x})
        
        for table in tables:
            # Determine if this is inbound or outbound based on context
            table_type = _determine_table_type(table)
            if not table_type:
                continue
                
            # Parse rows
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                transfer_data = _parse_transfer_row(row)
                if transfer_data:
                    transfers_data[table_type].append(transfer_data)
                    
    except Exception as e:
        print(f"Error parsing transfer tables: {e}", file=sys.stderr)
    
    return transfers_data


def _determine_table_type(table) -> Optional[str]:
    """Determine if table contains inbound or outbound transfers."""
    # Look for context clues in the table or surrounding elements
    prev_element = table.find_previous(['h2', 'h3', 'div'])
    if prev_element:
        text = prev_element.get_text().lower()
        if 'zugang' in text or 'arrivals' in text or 'in' in text:
            return 'inbound'
        elif 'abgang' in text or 'departures' in text or 'out' in text:
            return 'outbound'
    
    # Check table headers for clues
    headers = table.find_all('th')
    for header in headers:
        text = header.get_text().lower()
        if 'von' in text or 'from' in text:
            return 'inbound'
        elif 'zu' in text or 'to' in text:
            return 'outbound'
            
    return None


def _parse_transfer_row(row) -> Optional[Dict]:
    """Parse a single transfer row."""
    try:
        cells = row.find_all('td')
        if len(cells) < 4:
            return None
            
        transfer_data = {}
        
        # Player name (usually first or second cell)
        player_cell = cells[0] if cells[0].find('a') else cells[1] if len(cells) > 1 else None
        if player_cell:
            player_link = player_cell.find('a')
            if player_link:
                transfer_data['player_name'] = player_link.get_text(strip=True)
                transfer_data['player_url'] = player_link.get('href', '')
        
        # Position
        position_cell = next((cell for cell in cells if cell.get_text(strip=True) in 
                             ['GK', 'DF', 'MF', 'FW', 'CB', 'RB', 'LB', 'CM', 'CAM', 'CDM', 'RW', 'LW']), None)
        if position_cell:
            transfer_data['position'] = position_cell.get_text(strip=True)
        
        # Age
        age_text = ''
        for cell in cells:
            text = cell.get_text(strip=True)
            if re.match(r'^\d{1,2}$', text) and int(text) > 15 and int(text) < 50:
                age_text = text
                break
        if age_text:
            transfer_data['age'] = int(age_text)
        
        # Market value
        value_cell = next((cell for cell in cells if '€' in cell.get_text()), None)
        if value_cell:
            transfer_data['market_value'] = _parse_market_value(value_cell.get_text(strip=True))
        
        # Transfer fee
        fee_cell = next((cell for cell in cells if 
                        any(keyword in cell.get_text().lower() for keyword in ['fee', 'ablöse', '€', 'free', 'loan'])), None)
        if fee_cell:
            transfer_data['transfer_fee'] = _parse_transfer_fee(fee_cell.get_text(strip=True))
        
        # Club (from/to depending on table type)
        club_cells = [cell for cell in cells if cell.find('a') and '/verein/' in str(cell)]
        for club_cell in club_cells:
            club_link = club_cell.find('a')
            if club_link and '/verein/' in club_link.get('href', ''):
                transfer_data['club_name'] = club_link.get_text(strip=True)
                transfer_data['club_url'] = club_link.get('href', '')
                break
        
        # Date
        date_cell = next((cell for cell in cells if re.search(r'\d{2}\.\d{2}\.\d{4}', cell.get_text())), None)
        if date_cell:
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_cell.get_text())
            if date_match:
                transfer_data['transfer_date'] = date_match.group(1)
        
        return transfer_data if transfer_data else None
        
    except Exception as e:
        print(f"Error parsing transfer row: {e}", file=sys.stderr)
        return None


def _parse_market_value(value_text: str) -> Optional[float]:
    """Parse market value from text like '€15.00m' or '€500k'."""
    try:
        # Remove currency symbol and whitespace
        cleaned = re.sub(r'[€$£,\s]', '', value_text.lower())
        
        if 'm' in cleaned:
            # Million
            number = float(cleaned.replace('m', ''))
            return number * 1000000
        elif 'k' in cleaned:
            # Thousand
            number = float(cleaned.replace('k', ''))
            return number * 1000
        else:
            # Direct number
            return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_transfer_fee(fee_text: str) -> Dict[str, str]:
    """Parse transfer fee information."""
    fee_info = {
        'type': 'unknown',
        'amount': None,
        'raw_text': fee_text
    }
    
    text_lower = fee_text.lower()
    
    if 'free' in text_lower or 'ablösefrei' in text_lower:
        fee_info['type'] = 'free'
    elif 'loan' in text_lower or 'leihe' in text_lower:
        fee_info['type'] = 'loan'
    elif '€' in fee_text:
        fee_info['type'] = 'transfer_fee'
        fee_info['amount'] = _parse_market_value(fee_text)
    
    return fee_info


def create_transfers_report(url: str, club_id: str, season: str, transfers_data: Dict[str, List[Dict]]) -> Dict:
    """Create standardized transfers report."""
    return {
        "source": "transfermarkt",
        "collector": "transfers",
        "input": {
            "url": url,
            "club_id": club_id,
            "season": season
        },
        "data": transfers_data,
        "summary": {
            "inbound_count": len(transfers_data.get("inbound", [])),
            "outbound_count": len(transfers_data.get("outbound", [])),
            "total_transfers": len(transfers_data.get("inbound", [])) + len(transfers_data.get("outbound", []))
        },
        "timestamp": time.time(),
        "status": "parsed"
    }


def process_one(args):
    # Example: https://www.transfermarkt.de/{club}/transfers/verein/{club_id}/saison_id/{year}/...
    if not args.url and not (args.club_id and args.season):
        raise ValueError("Provide --url or --club-id and --season")
    url = args.url or (
        f"https://www.transfermarkt.de/-/transfers/verein/{args.club_id}/saison_id/{args.season}/pos//detailpos/0/w_s//plus/1"
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
        print(f"Fetched transfers page in {dt*1000:.0f} ms -> {url}")
    
    # Parse inbound/outbound tables with fees, types, dates, bonuses
    try:
        transfers_data = parse_transfer_tables(html_content)
        report = create_transfers_report(url, args.club_id, args.season, transfers_data)
        
        print(json.dumps(report, ensure_ascii=False, indent=2 if args.verbose else None))
        
    except Exception as e:
        error_result = {
            "source": "transfermarkt",
            "collector": "transfers",
            "input": {"url": url, "club_id": args.club_id, "season": args.season},
            "status": "error",
            "message": f"Failed to parse transfers: {str(e)}",
        }
        print(json.dumps(error_result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Transfermarkt Transfers Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="Transfers URL")
    p.add_argument("--club-id", type=str, default=None, help="Club id")
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
