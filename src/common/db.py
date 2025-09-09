"""
DEPRECATED: Use src.database.manager.DatabaseManager instead.

This module remains for backward compatibility with older scripts. New code should
import and use `DatabaseManager` for both sync and async access.
"""

import os
import re
from contextlib import contextmanager
from typing import Any

import psycopg2

# Load .env if present to populate DATABASE_URL for scripts
try:
    from dotenv import find_dotenv, load_dotenv  # type: ignore

    _ENV_PATH = find_dotenv(usecwd=True)
    if _ENV_PATH:
        load_dotenv(_ENV_PATH)
except Exception:
    # Safe to ignore if python-dotenv is not available
    pass


def _build_psycopg2_dsn_from_env() -> str:
    # Accept DATABASE_URL like postgresql+asyncpg://user:pass@host:port/db?params
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL env var not set")
    # Normalize driver to psycopg2-compatible
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
    return url


@contextmanager
def get_conn():
    print(
        "WARNING: src/common/db.py is deprecated. Use src.database.manager.DatabaseManager instead.",
        flush=True,
    )
    dsn = _build_psycopg2_dsn_from_env()
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def query_one(conn, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        if not row:
            return None
        # Build dict using cursor description
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))


def execute(conn, sql: str, params: tuple[Any, ...] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def find_player_id_by_transfermarkt(conn, tm_player_id: str) -> int | None:
    row = query_one(
        conn,
        """
        SELECT entity_id AS player_id
        FROM external_id_map
        WHERE provider = 'transfermarkt'
          AND entity_type = 'player'
          AND external_id = %s
        """,
        (tm_player_id,),
    )
    return int(row["player_id"]) if row else None


def upsert_player_absence(
    conn,
    *,
    player_id: int,
    absence_type: str,
    reason: str | None,
    start_date: str | None,  # ISO date string 'YYYY-MM-DD'
    end_date: str | None,  # ISO date string
    expected_return_date: str | None,  # ISO
    missed_games: int | None,
    source_url: str | None,
) -> None:
    # No UNIQUE in schema; emulate by merging on (player_id, absence_type, start_date, reason)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT absence_id FROM player_absence
            WHERE player_id = %s
              AND absence_type = %s
              AND COALESCE(start_date::text,'') = COALESCE(%s,'')
              AND COALESCE(reason,'') = COALESCE(%s,'')
            LIMIT 1
            """,
            (player_id, absence_type, start_date, reason),
        )
        row = cur.fetchone()
        if row:
            absence_id = row[0]
            cur.execute(
                """
                UPDATE player_absence
                SET end_date = COALESCE(%s, end_date),
                    expected_return_date = COALESCE(%s, expected_return_date),
                    missed_games = COALESCE(%s, missed_games),
                    source_url = COALESCE(%s, source_url),
                    scraped_at = NOW(),
                    updated_at = NOW()
                WHERE absence_id = %s
                """,
                (end_date, expected_return_date, missed_games, source_url, absence_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO player_absence(
                    player_id, absence_type, reason, start_date, end_date,
                    expected_return_date, missed_games, source_url, scraped_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                """,
                (
                    player_id,
                    absence_type,
                    reason,
                    start_date,
                    end_date,
                    expected_return_date,
                    missed_games,
                    source_url,
                ),
            )
    conn.commit()
