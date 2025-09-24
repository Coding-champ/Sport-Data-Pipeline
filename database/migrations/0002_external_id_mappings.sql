-- Migration: 0002_external_id_mappings.sql
-- Creates mapping tables for external IDs for core master data entities.
-- Safe to run multiple times; uses existence checks.

-- Helper DO block to create a mapping table if base table exists
-- Params:
--   base_table:   name of base table
--   mapping_table: name of mapping table to create
--   entity_col:   foreign key column name in mapping table
CREATE OR REPLACE FUNCTION create_mapping_if_base_exists(
    base_table TEXT,
    mapping_table TEXT,
    entity_col TEXT
) RETURNS VOID AS $$
BEGIN
    IF to_regclass('public.' || base_table) IS NULL THEN
        RETURN; -- base table missing, skip
    END IF;

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS public.%I (
            source      TEXT NOT NULL,
            external_id TEXT NOT NULL,
            %I          BIGINT NOT NULL REFERENCES public.%I(%I) ON DELETE CASCADE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_%I PRIMARY KEY (source, external_id)
        );',
        mapping_table, entity_col, base_table, entity_col, mapping_table
    );

    -- unique (source, entity_id)
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = ('uq_' || mapping_table || '_source_' || entity_col)
    ) THEN
        EXECUTE format(
            'ALTER TABLE public.%I ADD CONSTRAINT %I UNIQUE (source, %I);',
            mapping_table, ('uq_' || mapping_table || '_source_' || entity_col), entity_col
        );
    END IF;

    -- index on source
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'i'
          AND c.relname = ('ix_' || mapping_table || '_source')
          AND n.nspname = 'public'
    ) THEN
        EXECUTE format(
            'CREATE INDEX %I ON public.%I(source);',
            ('ix_' || mapping_table || '_source'), mapping_table
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create mapping tables for agreed entities
SELECT create_mapping_if_base_exists('player', 'player_external_ids', 'player_id');
SELECT create_mapping_if_base_exists('team', 'team_external_ids', 'team_id');
SELECT create_mapping_if_base_exists('club', 'club_external_ids', 'club_id');
SELECT create_mapping_if_base_exists('match', 'match_external_ids', 'match_id');
SELECT create_mapping_if_base_exists('venue', 'venue_external_ids', 'venue_id');
-- Stadiums table may not exist; skip if missing
SELECT create_mapping_if_base_exists('stadium', 'stadium_external_ids', 'stadium_id');
-- Leagues may be modeled as competitions; create competition mapping
SELECT create_mapping_if_base_exists('competition', 'competition_external_ids', 'competition_id');
SELECT create_mapping_if_base_exists('tournament', 'tournament_external_ids', 'tournament_id');
SELECT create_mapping_if_base_exists('referee', 'referee_external_ids', 'referee_id');
SELECT create_mapping_if_base_exists('coach', 'coach_external_ids', 'coach_id');
SELECT create_mapping_if_base_exists('country', 'country_external_ids', 'country_id');
SELECT create_mapping_if_base_exists('city', 'city_external_ids', 'city_id');

-- Cleanup helper (optional): keep function for future migrations
-- DROP FUNCTION IF EXISTS create_mapping_if_base_exists(TEXT, TEXT, TEXT);
