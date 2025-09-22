import argparse
import csv
import json
import os
import random
import sys
import time
from time import perf_counter

from common.http import DEFAULT_UAS, fetch_json, render_or_fetch

# NOTE: SofaScore exposes JSON endpoints behind the app; prefer JSON when possible.
# Using shared HTTP utilities from common/http.py.


def _pick_ua(args) -> str:
    try:
        pool = (
            open(args.ua_file, encoding="utf-8").read().splitlines()
            if args.ua_file and os.path.exists(args.ua_file)
            else DEFAULT_UAS
        )
        return random.choice(pool) if getattr(args, "ua_rotate", False) else pool[0]
    except Exception:
        return DEFAULT_UAS[0]


def _render_or_fetch(url: str, args) -> str:  # backward shim; delegates
    return render_or_fetch(url, args=args)


def process_one(args):
    if args.api_url:
        t0 = perf_counter()
        payload = fetch_json(
            args.api_url,
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
            print(f"Fetched SofaScore JSON in {dt*1000:.0f} ms -> {args.api_url}")
        print(
            json.dumps(
                {
                    "source": "sofascore",
                    "collector": "generic",
                    "input": {"api_url": args.api_url},
                    "status": "ok",
                    "json_keys": list(payload.keys()) if isinstance(payload, dict) else None,
                    "items": len(payload) if isinstance(payload, list) else None,
                },
                ensure_ascii=False,
            )
        )
        return

    if not args.url:
        raise ValueError("Provide --url or --api-url")
    t0 = perf_counter()
    html = _render_or_fetch(args.url, args)
    dt = perf_counter() - t0
    if args.verbose:
        print(f"Fetched SofaScore page in {dt*1000:.0f} ms -> {args.url}")
    print(
        json.dumps(
            {
                "source": "sofascore",
                "collector": "generic",
                "input": {"url": args.url},
                "status": "ok",
                "html_len": len(html),
            },
            ensure_ascii=False,
        )
    )


def main():
    p = argparse.ArgumentParser(description="SofaScore Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="SofaScore page URL (fallback)")
    p.add_argument("--api-url", type=str, default=None, help="Direct JSON API endpoint URL")
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
    # Rendering options (Playwright)
    p.add_argument(
        "--render", action="store_true", help="Render page via Playwright before parsing"
    )
    p.add_argument(
        "--render-timeout",
        type=float,
        default=35.0,
        help="Default timeout in seconds for rendering",
    )
    p.add_argument(
        "--render-wait-selector",
        type=str,
        default=".event,.team,.match,.stats",
        help="Comma-separated CSS selectors to wait for",
    )
    p.add_argument(
        "--render-wait-text",
        type=str,
        default="",
        help="Comma-separated text snippets to wait for",
    )
    p.add_argument(
        "--render-wait-network-idle", action="store_true", help="Additionally wait for network idle"
    )
    p.add_argument(
        "--render-headful", action="store_true", help="Run browser non-headless for debugging"
    )
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
