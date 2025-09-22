"""Unified Courtside1891 debug & analysis CLI.

Modi (via --mode):
  minimal  - schneller Check: wartet auf Fixtures, Screenshot + HTML Dump
  fixtures - extrahiert strukturierte Fixture Daten als JSON
  analyze  - tiefe Analyse (Container, Fixture-Elemente, data-testid, Ressourcen)
  inspect  - Kurz-Inspektion (erste Elemente & Selektor Counts)
  snapshot - Nur Screenshot + HTML
  raw      - reiner HTML Dump

Beispiele:
  python scripts/courtside_debug.py --mode minimal --headless
  python scripts/courtside_debug.py --mode fixtures --json > fixtures.json
  python scripts/courtside_debug.py --mode analyze --out-dir reports/courtside
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from src.common.playwright_utils import browser_page

URL = "https://www.courtside1891.basketball/games"


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


async def _ensure_out_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


async def _wait(page, selector: str | None, timeout: int):
    if selector:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            pass


async def mode_minimal(page, args):
    await page.goto(URL, timeout=args.timeout, wait_until="domcontentloaded")
    await _wait(page, args.wait_selector, args.timeout)
    out = await _ensure_out_dir(args.out_dir)
    sc = os.path.join(out, f"courtside_minimal_{_ts()}.png")
    await page.screenshot(path=sc, full_page=True)
    html_path = os.path.join(out, f"courtside_minimal_{_ts()}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(await page.content())
    return {"screenshot": sc, "html": html_path}


async def mode_snapshot(page, args):
    await page.goto(URL, timeout=args.timeout, wait_until="networkidle")
    out = await _ensure_out_dir(args.out_dir)
    sc = os.path.join(out, f"courtside_snapshot_{_ts()}.png")
    await page.screenshot(path=sc, full_page=True)
    html_path = os.path.join(out, f"courtside_snapshot_{_ts()}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(await page.content())
    return {"screenshot": sc, "html": html_path}


async def mode_raw(page, args):
    await page.goto(URL, timeout=args.timeout)
    html = await page.content()
    out = await _ensure_out_dir(args.out_dir)
    path = os.path.join(out, f"courtside_raw_{_ts()}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"html": path}


async def _extract_fixtures(page):
    return await page.evaluate(
        """() => {
        return Array.from(document.querySelectorAll('[data-testid="fixture-row"]')).map(row => ({
            home: row.querySelector('[data-testid="team-home"]')?.textContent?.trim() || null,
            away: row.querySelector('[data-testid="team-away"]')?.textContent?.trim() || null,
            score: row.querySelector('[data-testid="fixture-score"]')?.textContent?.trim() || null,
            competition: row.closest('[data-testid="competition-fixtures"]')?.querySelector('[data-testid="competition-name"]')?.textContent?.trim() || null
        }));
    }"""
    )


async def mode_fixtures(page, args):
    await page.goto(URL, timeout=args.timeout, wait_until="networkidle")
    await _wait(page, args.wait_selector, args.timeout)
    fixtures = await _extract_fixtures(page)
    return {"count": len(fixtures), "fixtures": fixtures}


async def mode_inspect(page, args):
    await page.goto(URL, timeout=args.timeout, wait_until="domcontentloaded")
    await _wait(page, args.wait_selector, args.timeout)
    test_ids = await page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-testid]')).slice(0,50).map(el => ({
            tag: el.tagName,
            testid: el.getAttribute('data-testid'),
            text: el.textContent.trim().replace(/\s+/g,' ').substring(0,80)
        }))"""
    )
    selectors = [
        '[data-testid*="fixture"]','[class*="fixture"]','[data-testid*="game"]','a[href*="/game/"]'
    ]
    selector_counts = {}
    for sel in selectors:
        try:
            c = await page.evaluate(f"() => document.querySelectorAll('{sel}').length")
            selector_counts[sel] = c
        except Exception:
            selector_counts[sel] = 0
    return {"test_ids": test_ids, "selector_counts": selector_counts}


async def mode_analyze(page, args):
    await page.goto(URL, timeout=args.timeout, wait_until="networkidle")
    await _wait(page, args.wait_selector, args.timeout)
    containers = await page.evaluate(
        """() => {
        const sels = ['main','body','div[role="main"]','.MuiContainer-root','div#root'];
        return sels.map(s => { const els = Array.from(document.querySelectorAll(s)); return {selector:s,count:els.length,sample:els[0]?{tag:els[0].tagName,text:els[0].textContent.trim().substring(0,120)}:null};});
    }"""
    )
    fixtures = await _extract_fixtures(page)
    resources = await page.evaluate(
        """() => Array.from(performance.getEntriesByType('resource')).filter(r=>r.initiatorType==='xmlhttprequest'||/api|graphql|fixture|game/i.test(r.name)).slice(0,40).map(r=>({name:r.name,type:r.initiatorType,duration:r.duration,transfer:r.transferSize}))"""
    )
    test_ids_sample = await page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-testid]')).slice(0,30).map(el=>({testid:el.getAttribute('data-testid'),tag:el.tagName,text:el.textContent.trim().substring(0,80)}))"""
    )
    out_dir = await _ensure_out_dir(args.out_dir)
    report_path = os.path.join(out_dir, f"courtside_analysis_{_ts()}.json")
    payload = {
        "mode": "analyze",
        "fixtures_found": len(fixtures),
        "fixtures_sample": fixtures[:5],
        "containers": containers,
        "resources": resources,
        "test_ids": test_ids_sample,
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"analysis_file": report_path, "summary": {k: payload[k] for k in ("fixtures_found","containers")}}


MODES: dict[str, Any] = {
    "minimal": mode_minimal,
    "snapshot": mode_snapshot,
    "raw": mode_raw,
    "fixtures": mode_fixtures,
    "inspect": mode_inspect,
    "analyze": mode_analyze,
}


async def run(args):
    mode_fn = MODES[args.mode]
    viewport = None
    if args.viewport is not None:
        viewport = {"width": args.viewport[0], "height": args.viewport[1]}
    async with browser_page(headless=args.headless, viewport=viewport) as page:
        result = await mode_fn(page, args)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Mode '{args.mode}' finished -> {result}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unified Courtside1891 debug tool")
    p.add_argument("--mode", choices=sorted(MODES.keys()), default="minimal")
    p.add_argument("--headless", action="store_true", help="Run headless")
    p.add_argument("--timeout", type=int, default=90000)
    p.add_argument("--wait-selector", dest="wait_selector", default='[data-testid="fixture-row"]')
    p.add_argument("--out-dir", default="reports/courtside")
    p.add_argument("--json", action="store_true", help="Print JSON only")
    p.add_argument("--viewport", type=str, default="1366x768", help="WIDTHxHEIGHT or 'none'")
    args = p.parse_args(argv)
    if args.viewport.lower() == "none":
        args.viewport = None
    else:
        try:
            w, h = args.viewport.lower().split("x")
            args.viewport = (int(w), int(h))
        except Exception:
            print("Invalid --viewport, using default 1366x768", file=sys.stderr)
            args.viewport = (1366, 768)
    return args


def main(argv: list[str] | None = None):
    args = parse_args(argv or sys.argv[1:])
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
