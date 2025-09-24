from __future__ import annotations
from typing import Optional, Tuple
import asyncpg

class MappingConflictError(RuntimeError):
    """Konflikt: vorhandenes Mapping zeigt auf eine andere interne ID."""

# Entität -> (Mapping-Tabelle, FK-Spalte)
ENTITY_TABLES = {
    "player": ("player_external_ids", "player_id"),
    "team": ("team_external_ids", "team_id"),
    "club": ("club_external_ids", "club_id"),
    "match": ("match_external_ids", "match_id"),
    "league": ("league_external_ids", "league_id"),
    "competition": ("competition_external_ids", "competition_id"),
    "tournament": ("tournament_external_ids", "tournament_id"),
    "venue": ("venue_external_ids", "venue_id"),
    "stadium": ("stadium_external_ids", "stadium_id"),
    "referee": ("referee_external_ids", "referee_id"),
    "coach": ("coach_external_ids", "coach_id"),
    "country": ("country_external_ids", "country_id"),
    "city": ("city_external_ids", "city_id"),
}


class ExternalIdMappingServiceAsync:
    def __init__(self, schema: str = "public"):
        self.schema = schema

    def _resolve(self, entity: str) -> Tuple[str, str]:
        try:
            table, col = ENTITY_TABLES[entity]
            return f"{self.schema}.{table}", col
        except KeyError:
            raise ValueError(
                f"Unknown entity '{entity}'. Supported: {', '.join(sorted(ENTITY_TABLES))}"
            )

    async def ensure(
        self,
        conn: asyncpg.Connection,
        *,
        entity: str,
        source: str,
        external_id: str,
        internal_id: int,
    ) -> int:
        """
        Strikt und idempotent:
        - Insert, falls nicht vorhanden (ON CONFLICT DO NOTHING).
        - Falls vorhanden: identisch -> OK, abweichend -> MappingConflictError.
        """
        table, col = self._resolve(entity)
        insert_sql = (
            f"INSERT INTO {table} (source, external_id, {col}) "
            "VALUES ($1, $2, $3) ON CONFLICT (source, external_id) DO NOTHING"
        )
        select_sql = f"SELECT {col} FROM {table} WHERE source=$1 AND external_id=$2"

        async with conn.transaction():
            status = await conn.execute(insert_sql, source, external_id, internal_id)
            # asyncpg Status wie "INSERT 0 1" bei Erfolg
            if status.endswith("1"):
                return internal_id

            row = await conn.fetchrow(select_sql, source, external_id)
            if row is None:
                # Seltener Race: zweiter Versuch
                status = await conn.execute(insert_sql, source, external_id, internal_id)
                if status.endswith("1"):
                    return internal_id
                row = await conn.fetchrow(select_sql, source, external_id)
                if row is None:
                    raise RuntimeError("Mapping insert/select race could not be resolved")

            existing = int(row[0])
            if existing != internal_id:
                raise MappingConflictError(
                    f"{entity}: ({source}, {external_id}) already mapped to {existing}, not {internal_id}"
                )
            return existing

    async def find(
        self,
        conn: asyncpg.Connection,
        *,
        entity: str,
        source: str,
        external_id: str,
    ) -> Optional[int]:
        table, col = self._resolve(entity)
        row = await conn.fetchrow(
            f"SELECT {col} FROM {table} WHERE source=$1 AND external_id=$2",
            source,
            external_id,
        )
        return int(row[0]) if row else None

    # Bequeme Wrapper
    async def ensure_player(self, conn, *, source: str, external_id: str, player_id: int) -> int:
        return await self.ensure(
            conn, entity="player", source=source, external_id=external_id, internal_id=player_id
        )

    async def find_player(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="player", source=source, external_id=external_id)

    async def ensure_team(self, conn, *, source: str, external_id: str, team_id: int) -> int:
        return await self.ensure(
            conn, entity="team", source=source, external_id=external_id, internal_id=team_id
        )

    async def find_team(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="team", source=source, external_id=external_id)

    async def ensure_club(self, conn, *, source: str, external_id: str, club_id: int) -> int:
        return await self.ensure(
            conn, entity="club", source=source, external_id=external_id, internal_id=club_id
        )

    async def find_club(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="club", source=source, external_id=external_id)

    async def ensure_match(self, conn, *, source: str, external_id: str, match_id: int) -> int:
        return await self.ensure(
            conn, entity="match", source=source, external_id=external_id, internal_id=match_id
        )

    async def find_match(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="match", source=source, external_id=external_id)

    async def ensure_league(self, conn, *, source: str, external_id: str, league_id: int) -> int:
        return await self.ensure(
            conn, entity="league", source=source, external_id=external_id, internal_id=league_id
        )

    async def find_league(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="league", source=source, external_id=external_id)

    async def ensure_competition(
        self, conn, *, source: str, external_id: str, competition_id: int
    ) -> int:
        return await self.ensure(
            conn,
            entity="competition",
            source=source,
            external_id=external_id,
            internal_id=competition_id,
        )

    async def find_competition(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="competition", source=source, external_id=external_id)

    async def ensure_tournament(
        self, conn, *, source: str, external_id: str, tournament_id: int
    ) -> int:
        return await self.ensure(
            conn,
            entity="tournament",
            source=source,
            external_id=external_id,
            internal_id=tournament_id,
        )

    async def find_tournament(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="tournament", source=source, external_id=external_id)

    async def ensure_venue(self, conn, *, source: str, external_id: str, venue_id: int) -> int:
        return await self.ensure(
            conn, entity="venue", source=source, external_id=external_id, internal_id=venue_id
        )

    async def find_venue(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="venue", source=source, external_id=external_id)

    async def ensure_stadium(self, conn, *, source: str, external_id: str, stadium_id: int) -> int:
        return await self.ensure(
            conn, entity="stadium", source=source, external_id=external_id, internal_id=stadium_id
        )

    async def find_stadium(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="stadium", source=source, external_id=external_id)

    async def ensure_referee(self, conn, *, source: str, external_id: str, referee_id: int) -> int:
        return await self.ensure(
            conn, entity="referee", source=source, external_id=external_id, internal_id=referee_id
        )

    async def find_referee(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="referee", source=source, external_id=external_id)

    async def ensure_coach(self, conn, *, source: str, external_id: str, coach_id: int) -> int:
        return await self.ensure(
            conn, entity="coach", source=source, external_id=external_id, internal_id=coach_id
        )

    async def find_coach(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="coach", source=source, external_id=external_id)

    async def ensure_country(self, conn, *, source: str, external_id: str, country_id: int) -> int:
        return await self.ensure(
            conn, entity="country", source=source, external_id=external_id, internal_id=country_id
        )

    async def find_country(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="country", source=source, external_id=external_id)

    async def ensure_city(self, conn, *, source: str, external_id: str, city_id: int) -> int:
        return await self.ensure(
            conn, entity="city", source=source, external_id=external_id, internal_id=city_id
        )

    async def find_city(self, conn, *, source: str, external_id: str) -> Optional[int]:
        return await self.find(conn, entity="city", source=source, external_id=external_id)
