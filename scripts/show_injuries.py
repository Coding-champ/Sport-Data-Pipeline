import json
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Load .env if present
try:
    from dotenv import find_dotenv, load_dotenv  # type: ignore

    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
except Exception:
    pass

from src.common.db import get_conn  # noqa: E402


def fetch_injuries_for_club_verein_id(club_id: int, limit: int = 50):
    like_pattern = f"%/verein/{club_id}/%"
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
                (like_pattern, limit),
            )
            cols = [d.name for d in cur.description]
            for r in cur.fetchall():
                rows.append(dict(zip(cols, r)))
    return rows


if __name__ == "__main__":
    club_id = int(sys.argv[1]) if len(sys.argv) > 1 else 27
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    data = fetch_injuries_for_club_verein_id(club_id, limit)
    print(
        json.dumps(
            {"club_id": club_id, "count": len(data), "items": data}, ensure_ascii=False, default=str
        )
    )
