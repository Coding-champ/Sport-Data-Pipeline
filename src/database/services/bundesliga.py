"""
Service: Persist Bundesliga matchday scraped items into match & match_result tables.
Resolves team, season, competition, venue, referee IDs.
"""

from __future__ import annotations

from typing import Any, Optional

from ..manager import DatabaseManager


async def _get_scalar(conn, query: str, *args) -> Optional[int]:
    val = await conn.fetchval(query, *args)
    return int(val) if val is not None else None


async def _ensure_competition(conn, name_en: str = "Bundesliga") -> int:
    cid = await _get_scalar(conn, "SELECT competition_id FROM competition WHERE competition_name = $1", name_en)
    if cid:
        return cid
    return await _get_scalar(
        conn,
        "INSERT INTO competition(competition_name) VALUES ($1) RETURNING competition_id",
        name_en,
    )


async def _ensure_season(conn, competition_id: int, label: str) -> int:
    sid = await _get_scalar(conn, "SELECT season_id FROM season WHERE competition_id = $1 AND label = $2", competition_id, label)
    if sid:
        return sid
    return await _get_scalar(
        conn,
        "INSERT INTO season(competition_id, label) VALUES ($1,$2) RETURNING season_id",
        competition_id,
        label,
    )


async def _ensure_regular_season_stage(conn, competition_id: int, season_id: int, stage_name: str = "Regular Season") -> Optional[int]:
    """Ensure a generic Regular Season stage exists for the competition/season.
    Returns stage_id or None if creation fails.
    """
    sid = await _get_scalar(
        conn,
        """
        SELECT stage_id FROM competition_stage
        WHERE competition_id = $1 AND season_id = $2 AND stage_name = $3 AND leg IS NULL
        """,
        competition_id,
        season_id,
        stage_name,
    )
    if sid:
        return sid
    return await _get_scalar(
        conn,
        """
        INSERT INTO competition_stage(competition_id, season_id, stage_name, leg, stage_format)
        VALUES ($1, $2, $3, NULL, '{"type":"league"}'::jsonb)
        RETURNING stage_id
        """,
        competition_id,
        season_id,
        stage_name,
    )


async def _resolve_team(conn, name: str) -> Optional[int]:
    # Try exact match in team by name
    q = "SELECT team_id FROM team WHERE team_name = $1"
    return await _get_scalar(conn, q, name)


async def _resolve_venue(conn, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    return await _get_scalar(conn, "SELECT venue_id FROM venue WHERE venue_name = $1", name)


async def _resolve_referee(conn, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    return await _get_scalar(conn, "SELECT referee_id FROM referee WHERE referee_name = $1", name)


async def upsert_bundesliga_matches(db: DatabaseManager, season_label: str, matchday: int, items: list[dict]):
    if not items:
        return

    async with db.get_async_connection() as conn:
        competition_id = await _ensure_competition(conn, "Bundesliga")
        season_id = await _ensure_season(conn, competition_id, season_label)
        sport_id = await _get_scalar(conn, "SELECT sport_id FROM sport WHERE sport_type = 'football'") or 1

        # Ensure a default stage (Regular Season) once per batch
        stage_id = await _ensure_regular_season_stage(conn, competition_id, season_id)

        rows_match = []
        rows_result = []

        for it in items:
            home_id = await _resolve_team(conn, it.get("home_team"))
            away_id = await _resolve_team(conn, it.get("away_team"))
            venue_id = await _resolve_venue(conn, it.get("stadium"))
            referee_id = await _resolve_referee(conn, it.get("referee"))

            kickoff = it.get("kickoff_utc")

            # Pack sport-specific details (store matchday and season label for convenience)
            sport_specific = {"season_label": season_label, "matchday": int(matchday)}

            rows_match.append(
                {
                    "sport_id": sport_id,
                    "season_id": season_id,
                    "competition_id": competition_id,
                    "stage_id": stage_id,
                    "match_date_time": kickoff,
                    "venue_id": venue_id,
                    "attendance": None,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "referee_id": referee_id,
                    "status": "scheduled" if it.get("home_score") is None else "finished",
                    "technology_used": None,
                    "sport_specific_data": sport_specific,
                    "broadcast_info": None,
                    "source_url": it.get("url"),
                    "scraped_at": it.get("scraped_at"),
                }
            )

            rows_result.append(
                {
                    "home_score": it.get("home_score"),
                    "away_score": it.get("away_score"),
                    "home_score_ht": None,
                    "away_score_ht": None,
                    "home_score_et": None,
                    "away_score_et": None,
                    "home_score_pens": None,
                    "away_score_pens": None,
                }
            )

        # Insert matches and collect generated IDs
        match_cols = list(rows_match[0].keys())
        placeholders = ",".join([f"${i+1}" for i in range(len(match_cols))])
        insert_sql = f"""
            INSERT INTO match ({','.join(match_cols)})
            VALUES ({placeholders})
            RETURNING match_id
        """
        match_ids: list[int] = []
        for rm in rows_match:
            mid = await conn.fetchval(insert_sql, *[rm[c] for c in match_cols])
            match_ids.append(int(mid))

        # Insert match_result rows (aligned by order)
        res_cols = list(rows_result[0].keys())
        placeholders_res = ",".join([f"${i+1}" for i in range(len(res_cols)+1)])
        insert_res_sql = f"""
            INSERT INTO match_result (match_id,{','.join(res_cols)})
            VALUES ({placeholders_res})
            ON CONFLICT (match_id) DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                home_score_ht = EXCLUDED.home_score_ht,
                away_score_ht = EXCLUDED.away_score_ht,
                home_score_et = EXCLUDED.home_score_et,
                away_score_et = EXCLUDED.away_score_et,
                home_score_pens = EXCLUDED.home_score_pens,
                away_score_pens = EXCLUDED.away_score_pens
        """
        for mid, rr in zip(match_ids, rows_result):
            await conn.execute(insert_res_sql, *([mid] + [rr[c] for c in res_cols]))
