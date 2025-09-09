import argparse
import csv
import json
import os
import sys
import time
from time import perf_counter

from common.http import DEFAULT_UAS, fetch_html

# ZeroZero (fussballzz.de) provides matches, referees, stadiums, players, coaches.
# Using shared HTTP utilities from common/http.py; parsing will be implemented later.


def process_one(args):
    if not args.url:
        raise ValueError(
            "Provide --url to ZeroZero entity (match, referee, stadium, player, coach)"
        )
    t0 = perf_counter()
    fetch_html(
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
    # TODO: Parse depending on entity (match, referee, stadium, player, coach)
    print(
        json.dumps(
            {
                "source": "zerozero",
                "collector": "generic",
                "input": {"url": args.url},
                "status": "fetched",
                "message": "placeholder - implement entity-specific parsing",
            },
            ensure_ascii=False,
        )
    )


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
