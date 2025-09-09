import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter

from src.common.http import DEFAULT_UAS, fetch_html  # TODO: Fixed import path to `src.common.http` for package consistency.

# Using shared HTTP utilities from common/http.py


def process_one(args):
    # Expected inputs: comp_id and season path to list all matches and enqueue to batch
    if not args.url and not (args.comp_id and args.season):
        raise ValueError("Provide --url to a competition season page or --comp-id and --season")
    url = args.url or f"https://fbref.com/en/comps/{args.comp_id}/{args.season}/"
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
        print(f"Fetched season page in {dt*1000:.0f} ms -> {url}")
    # TODO: Parse all match links for the season and emit a CSV for fbref_match_collector --batch-file
    # Placeholder normalized JSON output
    print(
        json.dumps(
            {
                "source": "fbref",
                "collector": "season",
                "input": {
                    "url": url,
                    "comp_id": args.comp_id,
                    "season": args.season,
                },
                "status": "fetched",
                "message": "placeholder - extract match links and write batch CSV",
            },
            ensure_ascii=False,
        )
    )


def main():
    p = argparse.ArgumentParser(description="FBref Season Collector (skeleton)")
    p.add_argument("--url", type=str, help="FBref competition season URL", default=None)
    p.add_argument("--comp-id", type=str, help="Competition ID (e.g., 9 for Premier League)")
    p.add_argument(
        "--season", type=str, help="Season segment (e.g., 2024-2025-Premier-League-Stats)"
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