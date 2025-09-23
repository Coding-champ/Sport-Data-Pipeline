"""Display recent injury records for a given Transfermarkt club (verein) id.

Moved from former scripts/show_injuries.py. This version lives in maintenance tools
category (DB read-only helpers).

Usage:
  python scripts/maintenance/injuries_show_db.py <club_id> [limit]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:  # optional dotenv
    from dotenv import find_dotenv, load_dotenv  # type: ignore

    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
except Exception:  # pragma: no cover - optional
    pass

from src.common.db import get_conn  # type: ignore  # noqa: E402


def fetch_injuries_for_club_verein_id(club_id: int, limit: int = 50):
    pattern = f"%/verein/{club_id}/%"
    rows = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT player_id, absence_type, reason, start_date, end_date,
                       expected_return_date, missed_games, source_url, scraped_at
                FROM player_absence
                WHERE source_url LIKE %s
                ORDER BY scraped_at DESC NULLS LAST
                LIMIT %s
                """,
                (pattern, limit),
            )
            cols = [d.name for d in cur.description]
            for r in cur.fetchall():
                rows.append(dict(zip(cols, r)))
    return rows


def main():  # pragma: no cover - CLI
    club_id = int(sys.argv[1]) if len(sys.argv) > 1 else 27
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    data = fetch_injuries_for_club_verein_id(club_id, limit)
    print(
        json.dumps(
            {"club_id": club_id, "count": len(data), "items": data},
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
