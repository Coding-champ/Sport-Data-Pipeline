from alembic import op
import sqlalchemy as sa

# IDs
revision = "d1a7c3e2f9ab"
down_revision = None  # TODO: set to current head
branch_labels = None
depends_on = None

# Basistabellen -> Mappingtabellen
ENTITIES = [
    # Kern
    ("players", "player_external_ids", "player_id"),
    ("teams", "team_external_ids", "team_id"),
    ("clubs", "club_external_ids", "club_id"),
    ("matches", "match_external_ids", "match_id"),
    ("venues", "venue_external_ids", "venue_id"),
    ("stadiums", "stadium_external_ids", "stadium_id"),
    # Wettbewerb/Organisation
    ("leagues", "league_external_ids", "league_id"),
    ("competitions", "competition_external_ids", "competition_id"),
    ("tournaments", "tournament_external_ids", "tournament_id"),
    # Personen
    ("referees", "referee_external_ids", "referee_id"),
    ("coaches", "coach_external_ids", "coach_id"),
    # Geo
    ("countries", "country_external_ids", "country_id"),
    ("cities", "city_external_ids", "city_id"),
]


def upgrade():
    for base, mapping, entity_col in ENTITIES:
        op.execute(
            f"""
        DO $$
        BEGIN
            IF to_regclass('public.{base}') IS NOT NULL THEN
                CREATE TABLE IF NOT EXISTS public.{mapping} (
                    source      TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    {entity_col} BIGINT NOT NULL REFERENCES public.{base}(id) ON DELETE CASCADE,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT pk_{mapping} PRIMARY KEY (source, external_id)
                );
                -- UNIQUE(source, entity_id)
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_{mapping}_source_{entity_col}'
                ) THEN
                    ALTER TABLE public.{mapping}
                    ADD CONSTRAINT uq_{mapping}_source_{entity_col} UNIQUE (source, {entity_col});
                END IF;
                -- Index auf source
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'i'
                      AND c.relname = 'ix_{mapping}_source'
                      AND n.nspname = 'public'
                ) THEN
                    CREATE INDEX ix_{mapping}_source ON public.{mapping}(source);
                END IF;
            END IF;
        END $$;
        """
        )


def downgrade():
    for _, mapping, entity_col in reversed(ENTITIES):
        op.execute(
            f"""
        DO $$
        BEGIN
            IF to_regclass('public.{mapping}') IS NOT NULL THEN
                DROP INDEX IF EXISTS public.ix_{mapping}_source;
                ALTER TABLE public.{mapping} DROP CONSTRAINT IF EXISTS uq_{mapping}_source_{entity_col};
                DROP TABLE IF EXISTS public.{mapping};
            END IF;
        END $$;
        """
        )
