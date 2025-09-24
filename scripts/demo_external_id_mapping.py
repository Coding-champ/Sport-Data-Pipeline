import asyncio
from src.database.manager import DatabaseManager
from src.database.services.external_id_mapping_service_async import (
    ExternalIdMappingServiceAsync,
    MappingConflictError,
)
from src.common.constants import Source

# Minimal demo that:
# 1) Ensures base dummy rows exist (player, team) and captures their IDs
# 2) Applies mapping for fbref external IDs
# 3) Reads mappings back
# 4) Demonstrates conflict handling

CREATE_PLAYER_SQL = """
INSERT INTO player (first_name, last_name)
VALUES ($1, $2)
RETURNING player_id
"""

CREATE_TEAM_SQL = """
INSERT INTO team (team_type, team_maturity, team_gender)
VALUES ('club', 'professional', 'men')
RETURNING team_id
"""

async def main():
    db = DatabaseManager()
    await db.initialize_async()
    svc = ExternalIdMappingServiceAsync()

    async with db.get_async_connection() as conn:
        # Create minimal dummy rows (idempotent-like via try except on unique not present; we just insert new rows)
        player_id = await conn.fetchval(CREATE_PLAYER_SQL, "Demo", "Player")
        team_id = await conn.fetchval(CREATE_TEAM_SQL)

        # External IDs (examples)
        ext_player_id = "p_demo_1"
        ext_team_id = "t_demo_1"
        source = Source.FBREF

        # Ensure mappings (idempotent)
        pid = await svc.ensure_player(conn, source=source, external_id=ext_player_id, player_id=player_id)
        tid = await svc.ensure_team(conn, source=source, external_id=ext_team_id, team_id=team_id)
        print(f"Player mapped: {ext_player_id} -> {pid}")
        print(f"Team mapped:   {ext_team_id} -> {tid}")

        # Read back
        pid2 = await svc.find_player(conn, source=source, external_id=ext_player_id)
        tid2 = await svc.find_team(conn, source=source, external_id=ext_team_id)
        print(f"Found player mapping: {ext_player_id} -> {pid2}")
        print(f"Found team mapping:   {ext_team_id} -> {tid2}")

        # Conflict demo
        try:
            await svc.ensure_player(conn, source=source, external_id=ext_player_id, player_id=player_id + 1)
        except MappingConflictError as e:
            print(f"Conflict detected (as expected): {e}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
