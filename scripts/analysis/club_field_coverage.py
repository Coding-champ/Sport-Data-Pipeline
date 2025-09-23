"""Generate coverage report for club fields (moved from report_club_field_coverage.py).

Purpose: quick insight into which fields are populated across scraped Bundesliga clubs.

Usage:
  python scripts/analysis/club_field_coverage.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.common.paths import REPORTS_DIR  # type: ignore  # noqa: E402


def load_clubs():
    # Heuristic: prefer enriched report, fallback to base
    candidates = [REPORTS_DIR / "clubs_enriched.json", REPORTS_DIR / "clubs.json"]
    for c in candidates:
        if c.exists():
            with c.open("r", encoding="utf-8") as f:
                return json.load(f)
    raise SystemExit("No clubs*.json file found in reports directory")


def compute_field_coverage(clubs):
    field_counts = defaultdict(int)
    total = len(clubs)
    for club in clubs:
        for k, v in club.items():
            if v not in (None, "", [], {}):
                field_counts[k] += 1
    coverage = {k: round(v / total * 100, 1) for k, v in field_counts.items()}
    return coverage, total


def main():  # pragma: no cover - CLI
    clubs = load_clubs()
    coverage, total = compute_field_coverage(clubs)
    print(f"Total clubs: {total}")
    for field, pct in sorted(coverage.items(), key=lambda x: x[1], reverse=True):
        print(f"{field:30} {pct:5.1f}%")


if __name__ == "__main__":  # pragma: no cover
    main()
