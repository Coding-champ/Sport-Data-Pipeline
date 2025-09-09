import argparse
import csv
import json
import os
import random
import sys
import time
from time import perf_counter

from src.common.http import DEFAULT_UAS, fetch_html, fetch_json  # TODO: Fixed import path to `src.common.http`.
from common.playwright_utils import BrowserSession, RenderWait  # type: ignore

# Official Premier League site is highly dynamic; many resources are loaded via JSON APIs.
# Using shared HTTP utilities from common/http.py.

# TODO: Align import for playwright utils to `src.common.playwright_utils` for consistency if available.


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


def _render_or_fetch(url: str, args) -> str:
    if getattr(args, "render", False):
        ua = _pick_ua(args)
        wait_selectors = [
            s.strip() for s in (args.render_wait_selector or "").split(",") if s.strip()
        ]
        wait_texts = [t.strip() for t in (args.render_wait_text or "").split(",") if t.strip()]
        wait = RenderWait(
            selectors=wait_selectors or None,
            text_contains=wait_texts or None,
            network_idle=args.render_wait_network_idle,
        )
        if args.verbose:
            print(
                f"[render] {url} wait selectors={wait_selectors} text={wait_texts} network_idle={args.render_wait_network_idle}"
            )
        try:
            with BrowserSession(
                headless=not args.render_headful,
                user_agent=ua,
                proxy=args.proxy,
                default_timeout_s=args.render_timeout,
            ) as bs:
                return bs.render_page(url, wait=wait, timeout_s=args.render_timeout)
        except Exception as e:
            if args.verbose:
                print(f"[render->fallback] {e}")
            # fall back to HTTP fetch
    return fetch_html(
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
            print(f"Fetched Premier League JSON in {dt*1000:.0f} ms -> {args.api_url}")
        print(
            json.dumps(
                {
                    "source": "premierleague",
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
        print(f"Fetched Premier League page in {dt*1000:.0f} ms -> {args.url}")
    print(
        json.dumps(
            {
                "source": "premierleague",
                "collector": "generic",
                "input": {"url": args.url},
                "status": "fetched",
                "message": "placeholder - discover official JSON APIs and extract data",
                "html_len": len(html),
            },
            ensure_ascii=False,
        )
    )


def main():
    p = argparse.ArgumentParser(description="Premier League Collector (skeleton)")
    p.add_argument("--url", type=str, default=None, help="Premier League page URL (fallback)")
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
        default=".pageContainer,.wrapper,.mainContent,.matchCentre",
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