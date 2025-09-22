import json
import sys
import sys as _sys
import argparse
from pathlib import Path

# Ensure project root and src on path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in _sys.path:
    _sys.path.insert(0, str(ROOT))
if str(SRC) not in _sys.path:
    _sys.path.insert(0, str(SRC))

from src.data_collection.scrapers.transfermarkt_injuries_scraper import _parse_injuries  # type: ignore
from src.common.http import DEFAULT_UAS, fetch_html  # type: ignore
from src.common.parsing import extract_tm_player_id_from_href  # type: ignore


def build_url(club_id: int) -> str:
    return f"https://www.transfermarkt.de/-/sperrenundverletzungen/verein/{club_id}/plus/1"


def main():
    parser = argparse.ArgumentParser(description="Preview Transfermarkt injuries (HTML scrape)")
    parser.add_argument("club_id", type=int, nargs="?", default=27, help="Transfermarkt club id")
    parser.add_argument(
        "--mode",
        choices=["json", "min"],
        default="json",
        help="Output mode: json (detailed) or min (CSV minimal)",
    )
    parser.add_argument("--quiet", action="store_true", help="Silence HTTP verbose output")
    args = parser.parse_args()

    url = build_url(args.club_id)
    html = fetch_html(
        url,
        timeout=45.0,
        retries=3,
        backoff=1.5,
        proxy=None,
        verbose=not args.quiet and args.mode == "json",
        user_agents=DEFAULT_UAS,
        rotate_ua=False,
        force_ua_on_429=False,
        header_randomize=True,
        pre_jitter=0.0,
    )
    rows = _parse_injuries(html)

    if args.mode == "min":
        print("tm_player_id,player_name,reason,start_date,expected")
        for r in rows:
            tm_id = extract_tm_player_id_from_href(r.get("player_href"))
            name = (r.get("player_name") or "").replace(",", " ")
            reason = (r.get("reason") or "").replace(",", " ")
            start_date = r.get("start_date") or ""
            expected = r.get("end_or_expected") or ""
            print(f"{tm_id},{name},{reason},{start_date},{expected}")
        return

    # json mode
    for r in rows:
        r["tm_player_id"] = extract_tm_player_id_from_href(r.get("player_href"))
    print(
        json.dumps(
            {
                "source": "transfermarkt",
                "collector": "injuries-preview",
                "url": url,
                "count": len(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
