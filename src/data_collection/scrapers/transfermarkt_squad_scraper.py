import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter

from common.http import DEFAULT_UAS, fetch_html

# Using shared HTTP utilities from common/http.py


def process_one(args):
    if not args.url and not (args.club_id and args.season):
        raise ValueError("Provide --url or --club-id and --season (e.g., 27 and 2025)")
    url = (
        args.url
        or f"https://www.transfermarkt.de/-/kader/verein/{args.club_id}/saison_id/{args.season}/plus/1"
    )
    t0 = perf_counter()
    fetch_html(
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
    # TODO: Parse squad table (number, player, position, age, nationality, market value, contract)
    print(
        json.dumps(
            {
                "source": "transfermarkt",
                "collector": "squad",
                "input": {"url": url, "club_id": args.club_id, "season": args.season},
                "status": "fetched",
                "message": "placeholder - extract squad rows and upsert players/squad",
            },
            ensure_ascii=False,
        )
    )


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
