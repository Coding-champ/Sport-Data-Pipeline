-- PostgreSQL schema for Sports Data Pipeline
-- Target: PostgreSQL
-- Sports: Football (Soccer), Basketball, American Football
-- Features:
-- - Multi-sport support with sport-specific entities
-- - Supports club and national teams via team_type
-- - Supports youth and senior teams via team_maturity
-- - Supports men and women teams via team_gender
-- - Seasons support both cross-year (e.g., 2024/2025) and calendar-year via season_type + label
-- - Comprehensive odds tracking (pre-match)
-- - Lineups/Events support field/court coordinates (x,y in percent)
-- - Extended staff model (medical, technical, administrative)
-- - SCD2-style historization for Club and Venue names
-- - Enhanced JSONB usage for flexible statistics storage
-- - Player Transfer and injury tracking
-- - Audit fields: source_url, scraped_at, created_at, updated_at
-- - Look at seed_data.sql for initial data (Countries, Positions, etc.)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================
-- Enums
-- =========================
-- Core sport types
CREATE TYPE sport_enum AS ENUM ('football', 'basketball', 'american_football');

-- Team classification
CREATE TYPE team_type AS ENUM ('club', 'national');
CREATE TYPE team_maturity AS ENUM ('youth', 'professional');
CREATE TYPE team_gender AS ENUM ('men', 'women');
CREATE TYPE strong_foot AS ENUM ('left', 'right', 'both');
CREATE TYPE surface_type AS ENUM ('grass', 'hybrid', 'artificial', 'indoor');

-- Match and event specifics
CREATE TYPE match_status AS ENUM ('not_started', 'in_progress', 'completed', 'abandoned', 'postponed', 'suspended', 'cancelled');
CREATE TYPE shot_body_part_enum AS ENUM ('left_foot','right_foot','head','other');
CREATE TYPE shot_situation_enum AS ENUM ('open_play','set_piece','penalty','counter','fast_break');

-- Officials and staff
CREATE TYPE official_role AS ENUM ('referee', 'ar1', 'ar2', 'fourth', 'var', 'avar', 'umpire', 'line_judge', 'field_judge');
CREATE TYPE staff_role AS ENUM ('head_coach', 'assistant_coach', 'gk_coach', 'fitness_coach', 'analyst', 'physio', 'medical', 'team_manager', 'nutritionist', 'psychologist', 'equipment_manager', 'video_analyst', 'scout');

-- Betting and odds
CREATE TYPE price_type AS ENUM ('open', 'close', 'live');
CREATE TYPE odd_type AS ENUM ('home', 'draw', 'away');

-- Medical and health
CREATE TYPE nationality_type AS ENUM ('nationality', 'citizenship');
CREATE TYPE injury_type AS ENUM ('muscle', 'bone', 'joint', 'ligament', 'concussion', 'illness', 'hamstring strain', 'other');
CREATE TYPE absence_reason AS ENUM ('injury', 'suspension', 'illness', 'personal', 'coach_decision', 'other');

-- Football specific
CREATE TYPE football_position AS ENUM ('goalkeeper', 'defender', 'midfielder', 'forward');

-- Basketball specific
CREATE TYPE basketball_position AS ENUM ('point_guard', 'shooting_guard', 'small_forward', 'power_forward', 'center');

-- American Football specific  
CREATE TYPE american_football_position AS ENUM ('quarterback', 'running_back', 'wide_receiver', 'tight_end', 'offensive_line', 'defensive_line', 'linebacker', 'defensive_back', 'kicker', 'punter');

-- General
CREATE TYPE season_type AS ENUM ('cross_year', 'calendar_year');
CREATE TYPE venue_type AS ENUM ('stadium', 'arena', 'dome', 'fieldhouse');

-- Metadata
CREATE TYPE entity_type AS ENUM ('player', 'team', 'club', 'coach', 'competition', 'match', 'referee');
CREATE TYPE data_provider AS ENUM ('opta', 'statsbomb', 'wyscout', 'understat', 'fbref', 'transfermarkt', 'sofifa', 'fifa', 'espn', 'other');


-- =========================
-- Stammdaten (Master Data)
-- =========================
-- Sport, Land, Stadt, Verein, Team, Spieler, Positionen, etc.

CREATE TABLE sport (
    sport_id SERIAL PRIMARY KEY,
    sport_type sport_enum NOT NULL UNIQUE,
    is_team_sport BOOLEAN DEFAULT TRUE,
    -- name TEXT NOT NULL,
    -- sport_description TEXT,
    -- rules_url TEXT,
    governing_body TEXT REFERENCES association(association_id) ON DELETE SET NULL,
);

CREATE TABLE country (
    country_id SERIAL PRIMARY KEY,
    iso2 CHAR(2) UNIQUE,
    iso3 CHAR(3) UNIQUE,
    country_name TEXT NOT NULL,
    flag_url TEXT
);

CREATE TABLE city (
    city_id SERIAL PRIMARY KEY,
    city_name TEXT NOT NULL,
    country_id INT REFERENCES country(country_id) ON DELETE RESTRICT,
    state_region TEXT,
    city_population INT
);

CREATE TABLE association (
    association_id SERIAL PRIMARY KEY,
    association_name TEXT NOT NULL,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT, -- null for multi-sport organizations (football, futsal, beach soccer)
    is_national BOOLEAN DEFAULT TRUE,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL, -- null for international (FIFA, UEFA, etc.)
    parent_association_id INT REFERENCES association(association_id) ON DELETE SET NULL -- Null for top-level (FIFA, UEFA, etc.)
);

-- Enhanced position lookup with sport-specific positions
CREATE TABLE position_lookup (
    position_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    code TEXT NOT NULL, -- e.g., GK, RB, CB, PG, QB, etc.
    position_name TEXT NOT NULL,
    position_group TEXT, -- e.g., 'defense', 'midfield', 'attack', 'guard', 'forward', 'offense'
    sport_specific_data JSONB, -- Flexible data for sport-specific attributes
    UNIQUE(sport_id, code)
);

CREATE TABLE weather_lookup (
    weather_id SERIAL PRIMARY KEY,
    condition TEXT NOT NULL, -- e.g., Clear, Rain, Snow, Cloudy
);

CREATE TABLE bookmaker (
    bookmaker_id SERIAL PRIMARY KEY,
    bookmaker_name TEXT NOT NULL UNIQUE,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    website_url TEXT
);

CREATE TABLE betting_market (
    market_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    market_name TEXT NOT NULL,      -- e.g., 1X2, Over/Under, Asian Handicap, Moneyline, Point Spread
    UNIQUE(sport_id, market_name)
);

CREATE TABLE betting_outcome (
    outcome_id SERIAL PRIMARY KEY,
    market_id INT NOT NULL REFERENCES betting_market(market_id) ON DELETE CASCADE,
    outcome_name TEXT NOT NULL,      -- e.g., Home, Draw, Away, Over, Under, +0.5, -1.0
    UNIQUE(market_id, outcome_name)
);

CREATE TABLE club (
    club_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    association_id INT REFERENCES association(association_id) ON DELETE SET NULL,
    -- Club details
    name_official TEXT NOT NULL,
    name_short TEXT,
    nickname TEXT,
      --code TEXT UNIQUE,                -- optional short code like FCB, BVB, LAL (Lakers)
    colors JSONB, -- {"primary": "#FF0000", "secondary": "#FFFFFF"}
    logo_url TEXT,
    founding_year INT,
    membership_count INT,
    -- club address
    address_street TEXT,
    address_postal_code TEXT,
    address_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    -- Commercial information
    main_sponsor TEXT,    -- e.g., "Telekom", "Emirates", "Rakuten"
    kit_supplier TEXT,    -- e.g., "Adidas", "Nike", "Puma"
    -- Multi-sport club support
    parent_club_id INT REFERENCES club(club_id) ON DELETE SET NULL, -- for multi-sport organizations
    -- Social media and web presence
    website_url TEXT,
    social_media JSONB, -- {twitter:"", instagram:"", tiktok:"", youtube:"", facebook:""}
    -- Audit fields
    source_url TEXT,  -- URL from which the data was scraped
    external_ids JSONB, -- API IDs verschiedener Anbieter
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SCD2: Club name history
CREATE TABLE club_name_history (
    club_name_history_id SERIAL PRIMARY KEY,
    club_id INT NOT NULL REFERENCES club(club_id) ON DELETE CASCADE,
    name_official TEXT NOT NULL,
    name_short TEXT,
    nickname TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN GENERATED ALWAYS AS (valid_to IS NULL) STORED
);

CREATE TABLE venue (
    venue_id SERIAL PRIMARY KEY,
    venue_name TEXT NOT NULL,
    address_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    address_street TEXT,
    address_postal_code TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    venue_operator TEXT, -- e.g., "City of Manchester"
    venue_owner TEXT, -- e.g., "Manchester United FC"
    construction_date DATE,
    opening_date DATE,
    renovation_date DATE,
    -- Environmental and structural
    surface surface_type NOT NULL, -- grass, hybrid, artificial, indoor
    venue_type venue_type NOT NULL, -- stadium, arena, dome, fieldhouse
    roof_type TEXT, -- open, closed, retractable
      --climate_controlled BOOLEAN DEFAULT FALSE,
    -- Multi-sport venue support
    supported_sports JSONB, -- Array of sport types this venue supports
    -- Sport-specific dimensions
    field_dimensions JSONB, -- {football: {length: 105, width: 68}, basketball: {length: 28, width: 15}}
    capacity_national INT,
    capacity_international INT,
    capacity_details JSONB, -- {total: 75000, seated: 65000, standing: 10000, vip: 2000}
    -- Technology and facilities
      --has_var BOOLEAN DEFAULT FALSE,
      --has_goal_line_tech BOOLEAN DEFAULT FALSE,
      --has_player_tracking BOOLEAN DEFAULT FALSE,
      --facilities JSONB, -- {parking_spaces: 5000, restaurants: 12, shops: 8, conference_rooms: 20}
    -- Commercial
    naming_rights_sponsor TEXT,
    naming_rights_until DATE,
    official_website TEXT,
    image_url TEXT,
    -- Audit fields
    source_url TEXT,
    external_ids JSONB, -- API IDs verschiedener Anbieter
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SCD2: Venue name history
CREATE TABLE venue_name_history (
    venue_name_history_id SERIAL PRIMARY KEY,
    venue_id INT NOT NULL REFERENCES venue(venue_id) ON DELETE CASCADE,
    venue_name TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN GENERATED ALWAYS AS (valid_to IS NULL) STORED
);

CREATE TABLE club_venue_tenancy (
    tenancy_id SERIAL PRIMARY KEY,
    club_id INT NOT NULL REFERENCES club(club_id) ON DELETE CASCADE,
    venue_id INT NOT NULL REFERENCES venue(venue_id) ON DELETE CASCADE,
    main_tenant BOOLEAN DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    UNIQUE (club_id, venue_id, start_date)
);

CREATE TABLE team (
    team_id SERIAL PRIMARY KEY,
    club_id INT REFERENCES club(club_id) ON DELETE SET NULL,  -- null for national teams
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL, -- set for national teams
    team_type team_type NOT NULL, -- 'club', 'national'
    team_maturity team_maturity NOT NULL, -- 'youth', 'professional'
    team_gender team_gender NOT NULL, -- 'men', 'women'
    market_value NUMERIC(14,2),
    market_value_currency TEXT DEFAULT 'EUR',
    social_media JSONB, -- {twitter:"", instagram:"", tiktok:"", youtube:""}
    -- Commercial
    main_sponsor TEXT,
    kit_supplier TEXT,
    -- Performance tracking
    season_objectives JSONB, -- {league_position: 4, cup_progress: "quarter_finals"}
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT team_club_or_country CHECK (
        team_type = 'club' AND club_id IS NOT NULL    
    )
);

CREATE TABLE player_agent (
    agent_id SERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agency_id INT REFERENCES agency(agency_id) ON DELETE SET NULL,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_name)
);

CREATE TABLE agency (
    agency_id SERIAL PRIMARY KEY,
    agency_name TEXT NOT NULL UNIQUE,
    country_id INT REFERENCES country(country_id) ON DELETE
);

CREATE TABLE equipment_supplier (
    equipment_supplier_id SERIAL PRIMARY KEY,
    supplier_name TEXT NOT NULL UNIQUE, -- e.g., "Nike", "Adidas", "Puma", "Reebok","Under Armour", "New Balance", "ASICS", "Castore"
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    official_website TEXT,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE player (
    player_id SERIAL PRIMARY KEY,
      --sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    nickname TEXT,
    date_of_birth DATE,
    place_of_birth INT REFERENCES city(city_id) ON DELETE SET NULL,
    nationality INT REFERENCES country(country_id) ON DELETE SET NULL,
    -- Physical attributes
    height_cm INT,
    weight_kg INT,
    strong_foot strong_foot,
    -- Sport-specific attributes stored as JSONB
      --sport_attributes JSONB, -- {shooting_range: "3pt", vertical_leap: 85, sprint_speed: 32.5}
    -- Career information
    is_active BOOLEAN DEFAULT TRUE,
    professional_debut DATE,
    retirement_date DATE,
    youth_career JSONB, -- [{club: "Barcelona", from: "2015", to: "2018", level: "u18"}]
    senior_career JSONB, -- [{club: "Barcelona", from: "2018", to: null, appearances: 120, goals: 45}]
    -- Commercial relationships
    agent INT REFERENCES player_agent(agent_id) ON DELETE SET NULL,
    equipment_supplier INT REFERENCES equipment_supplier(equipment_supplier_id) ON DELETE SET NULL,
    -- Medical and fitness
    injury_history JSONB, -- [{type: "hamstring", date: "2023-09-15", duration_days: 30, description: "Grade 2 strain"}]
    is_ready_for_sport BOOLEAN DEFAULT TRUE,
    -- Social and digital presence
    social_media JSONB, -- {instagram: "@player", twitter: "@player", tiktok: "@player"}
    -- Performance analytics
    career_stats JSONB, -- Aggregated career statistics
    current_market_value NUMERIC(12,2),
    current_market_value_currency TEXT DEFAULT 'EUR',
    photo_url TEXT,
    -- Audit fields
    source_url TEXT,
    external_ids JSONB, -- API IDs verschiedener Anbieter
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player multiple nationalities/citizenships
CREATE TABLE player_country (
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    country_id INT NOT NULL REFERENCES country(country_id) ON DELETE RESTRICT,
    nationality_type nationality_type NOT NULL,
    PRIMARY KEY (player_id, country_id, nationality_type)
);

CREATE TABLE coach (
    coach_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth DATE,
    place_of_birth INT REFERENCES city(city_id) ON DELETE SET NULL,
    nationality INT REFERENCES country(country_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Broader staff entity (includes head/assistant, GK coach, analysts, etc.)
--CREATE TABLE staff_member (
--    staff_id SERIAL PRIMARY KEY,
--    first_name TEXT NOT NULL,
--    last_name TEXT NOT NULL,
--    date_of_birth DATE,
--    place_of_birth INT REFERENCES city(city_id) ON DELETE SET NULL,
--    nationality INT REFERENCES country(country_id) ON DELETE SET NULL,
    -- Qualifications and certifications
      --qualifications JSONB, -- {uefa_pro_license: true, medical_degree: true, certifications: ["FIFA", "UEFA"]}
      --specializations JSONB, -- {areas: ["youth_development", "injury_prevention"], languages: ["en", "de", "es"]}
      --experience_years INT,
    -- social media
    --social_media JSONB,
    -- Audit fields
--    source_url TEXT,
--    scraped_at TIMESTAMPTZ,
--    created_at TIMESTAMPTZ DEFAULT NOW(),
--    updated_at TIMESTAMPTZ DEFAULT NOW()
--);

-- Medical staff specifically
--CREATE TABLE medical_staff (
--    medical_staff_id SERIAL PRIMARY KEY,
--    staff_id INT REFERENCES staff_member(staff_id) ON DELETE CASCADE,
--    medical_license_number TEXT,
--    medical_license_country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
--    specialization TEXT, -- e.g., 'sports_medicine', 'physiotherapy', 'nutrition', 'psychology'
--    created_at TIMESTAMPTZ DEFAULT NOW(),
--    updated_at TIMESTAMPTZ DEFAULT NOW()
--);

-- Administrative and non-technical staff (team managers, directors, etc.)
CREATE TABLE administrative_staff (
    administrative_staff_id SERIAL PRIMARY KEY,
    --staff_id INT REFERENCES staff_member(staff_id) ON DELETE CASCADE,
    staff_role TEXT, -- e.g., 'team_manager', 'director_of_football', 'club_secretary'
    department TEXT, -- e.g., 'operations', 'communications', 'marketing'
    from_date DATE,
    to_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE player_position (
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    position_id INT NOT NULL REFERENCES position_lookup(position_id) ON DELETE RESTRICT,
    is_primary_position BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (player_id, position_id)
);

-- Player ↔ Coach relationships for players who have developed into a coaching role
CREATE TABLE player_coach_development (
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    coach_id INT NOT NULL REFERENCES coach(coach_id) ON DELETE CASCADE,
    from_date DATE NOT NULL,
    to_date DATE,
    PRIMARY KEY (player_id, coach_id)
);

-- Player ↔ Player relationships (family, siblings, etc.)
CREATE TABLE person_relations (
    person_id INT REFERENCES player(player_id) ON DELETE CASCADE,
    related_person_id INT REFERENCES player(player_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- e.g., 'sibling', 'parent', 'child', 'spouse', 'cousin'
    PRIMARY KEY (person_id, related_person_id, relation_type)
);

-- =========================
-- Bewegungsdaten (Transactional Data)
-- =========================
-- Matches, Events, Stats, Transfers, Verletzungen, etc.

CREATE TABLE competition (
    competition_id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    competition_name TEXT NOT NULL,
    competition_short_name TEXT,
    association_id INT REFERENCES association(association_id) ON DELETE SET NULL,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    since_year INT,
    is_cup BOOLEAN DEFAULT FALSE,
    is_youth BOOLEAN DEFAULT FALSE,
    is_women BOOLEAN DEFAULT FALSE,
    is_national BOOLEAN,
    tier INTEGER DEFAULT 1, -- 1 = Top-Liga, 2 = Zweite Liga, etc.
    logo_url TEXT,
    -- Competition format and rules
    competition_format JSONB, -- {type: "league", playoff_format: "single_elimination", teams: 20}
    prize_money JSONB, -- {winner: 50000000, runner_up: 25000000, currency: "EUR"}
    UNIQUE (competition_name, COALESCE(country_id, -1), COALESCE(association_id, -1))
);

CREATE TABLE season (
    season_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    season_type season_type NOT NULL,
    label TEXT NOT NULL,      -- e.g., '2024/2025' or '2025'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    number_of_teams INT,
    number_of_games INT,
    -- Season-specific rules and regulations
    rules JSONB, -- {var_usage: true, max_subs: 5, extra_time: 30, playoff_format: "best_of_7"}
    UNIQUE (competition_id, label)
);

CREATE TABLE competition_stage (
    stage_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,       -- e.g., Regular Season, Group Stage, Round of 16
    leg INT,                      -- for multi-leg rounds
    stage_format JSONB, -- {type: "group", teams_per_group: 4, advance_count: 2}
    UNIQUE(competition_id, season_id, stage_name, COALESCE(leg, -1))
);

CREATE TABLE competition_table (
    table_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    position INT,
    played INT,
    won INT,
    drawn INT,
    lost INT,
    goals_for INT,
    goals_against INT,
    goal_difference INT,
    points INT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (competition_id, season_id, team_id)
);

CREATE TABLE competition_group (
    group_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    --stage_id INT REFERENCES competition_stage(stage_id) ON DELETE SET NULL,
    group_name TEXT NOT NULL,       -- e.g., Group A, East Division
    UNIQUE (competition_id, season_id, COALESCE(stage_id, -1), group_name)
);

CREATE TABLE player_injury (
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    injury_type injury_type NOT NULL, -- e.g., 'muscle', 'bone', 'joint', 'ligament', 'concussion', 'illness', 'other'
    body_part TEXT, -- e.g., 'left_knee', 'right_shoulder', 'head'
    severity TEXT, -- e.g., 'minor', 'moderate', 'severe', 'career_threatening'
    injury_date DATE,
    expected_return_date DATE,
    actual_return_date DATE,
    caused_by_match_id INT REFERENCES match(match_id) ON DELETE SET NULL,
    missed_games INT,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE team_season (
    team_season_id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    coach_id INT REFERENCES coach(coach_id) ON DELETE SET NULL,
    league_position INT,
    UNIQUE (team_id, season_id)
);

CREATE TABLE squad_member (
    team_season_id INT NOT NULL REFERENCES team_season(team_season_id) ON DELETE CASCADE,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    shirt_number INT,
    from_date DATE,
    to_date DATE,
    PRIMARY KEY (team_season_id, player_id)
);

CREATE TABLE player_transfer (
    contract_id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    transfer_from_team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    transfer_to_team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    transfer_date DATE,
    transfer_type TEXT, -- e.g., 'permanent', 'loan', 'free_transfer'
    loan_duration INT, -- in months, if applicable
    permanent_transfer_after_loan BOOLEAN DEFAULT FALSE,
    transfer_fee NUMERIC(14,2), -- initial transfer fee or loan fee
    transfer_fee_currency TEXT DEFAULT 'EUR',
    bonus_fees_sum NUMERIC(14,2), -- sum of all bonus fees
    signing_bonus NUMERIC(12,2), -- signing bonus
    total_transfer_cost NUMERIC(14,2), -- transfer_fee + bonus_fees_sum + signing_bonus (if applicable)
    clauses JSONB, -- {release_clause: 100000000, buy_back_clause: 50000000, sell_on_percentage: 10}
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE player_contract (
    contract_id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    start_date DATE,
    end_date DATE,
    annual_salary NUMERIC(12,2),
    salary_currency TEXT DEFAULT 'EUR',
    total_contract_cost NUMERIC(14,2), -- annual_salary * years (if applicable)
    --clauses JSONB, -- {release_clause: 100000000, buy_back_clause: 50000000, sell_on_percentage: 10}
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE team_staff_assignment (
    team_season_id INT NOT NULL REFERENCES team_season(team_season_id) ON DELETE CASCADE,
      --staff_id INT NOT NULL REFERENCES staff_member(staff_id) ON DELETE CASCADE,
    staff_role staff_role NOT NULL,
    from_date DATE,
    to_date DATE,
    PRIMARY KEY (team_season_id, staff_role)
);

CREATE TABLE match (
    match_id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    stage_id INT REFERENCES competition_stage(stage_id) ON DELETE SET NULL,
    match_date_time TIMESTAMPTZ NOT NULL,
    venue_id INT REFERENCES venue(venue_id) ON DELETE SET NULL,
    attendance INT,
    home_team_id INT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
    away_team_id INT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
    referee_id INT REFERENCES referee(referee_id) ON DELETE SET NULL,
    -- Weather conditions
    weather_id INT REFERENCES weather_lookup(weather_id) ON DELETE SET NULL,
    temperature_c NUMERIC(5,2),
    wind_kmh NUMERIC(6,2),
    rain_intensity NUMERIC(5,2), -- 0..1 or mm/h if available
    humidity_percent NUMERIC(5,2),
    -- Match status and timing
    status TEXT DEFAULT 'scheduled', -- scheduled, live, finished, postponed, cancelled
    match_duration_minutes INT, -- Actual match duration including stoppage time
    -- Technology usage
    technology_used JSONB, -- {var: true, goal_line: true, player_tracking: true}
    -- Sport-specific data
    sport_specific_data JSONB, -- Flexible storage for sport-specific match details
    -- Broadcast and media
    broadcast_info JSONB, -- {tv_channels: ["ESPN", "Sky"], streaming: ["Netflix"], commentary_languages: ["en", "es"]}
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE match_result (
    match_id INT PRIMARY KEY REFERENCES match(match_id) ON DELETE CASCADE,
    -- Standard scores
    home_score INT,
    away_score INT,
    home_score_ht INT, -- Half-time (football) or Q2 (basketball) or H1 (american football)
    away_score_ht INT,
    -- Extended time scores (football)
    home_score_et INT,
    away_score_et INT,
    -- Penalty shootout (football)
    home_score_pens INT,
    away_score_pens INT,
    -- Sport-specific scoring breakdown
    score_breakdown JSONB, -- Basketball: quarters, American Football: quarters, detailed scoring
    -- Match outcome
    winner_team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    is_draw BOOLEAN DEFAULT FALSE,
    win_type TEXT -- 'regular', 'overtime', 'penalties', 'forfeit'
);

CREATE TABLE referee (
    referee_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth DATE,
    place_of_birth INT REFERENCES city(city_id) ON DELETE SET NULL,
    nationality INT REFERENCES country(country_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE match_official (
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    referee_id INT NOT NULL REFERENCES referee(referee_id) ON DELETE CASCADE,
    role official_role NOT NULL,
    PRIMARY KEY (match_id, referee_id, role)
);

CREATE TABLE match_lineup_entry (
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    position_id INT REFERENCES position_lookup(position_id) ON DELETE SET NULL,
    is_starter BOOLEAN NOT NULL DEFAULT TRUE,
    is_captain BOOLEAN DEFAULT FALSE,
    minute_on INT,  -- for subs
    minute_off INT, -- for subs
    reason_off TEXT, -- e.g., 'injury', 'tactical', 'yellow_card'
    shirt_number INT,
    rating NUMERIC(4,2), -- optional source ratings
    PRIMARY KEY (match_id, team_id, player_id)
);

CREATE TABLE event_type_lookup (
    event_type_id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL UNIQUE, -- goal, shot, foul, card, sub, offside, corner, free_kick, penalty, save, block
    event_subtype TEXT, -- e.g., for card: yellow, red; for goal: own_goal, penalty, VAR_goal
);

CREATE TABLE event_qualifier_lookup (
    qualifier_id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- e.g., header, left_foot, right_foot, inside_box, outside_box
    name TEXT
);

-- Match events (detailed event logging) (football focus, extendable for other sports)
CREATE TABLE match_event (
    event_id SERIAL PRIMARY KEY,
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    event_type_id INT NOT NULL REFERENCES event_type_lookup(event_type_id) ON DELETE RESTRICT,
    qualifier_id INT REFERENCES event_qualifier_lookup(qualifier_id) ON DELETE SET NULL,
    event_minute INT,
    event_second INT,
    event_injury_time INT, -- for stoppage time
    event_extra_time INT, -- for extra time
    player_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    player_in_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    player_out_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    assist_player_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    x_percent NUMERIC(5,2), -- 0..100
    y_percent NUMERIC(5,2), -- 0..100
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_match_event_x_percent_range CHECK (
      x_percent IS NULL OR (x_percent >= 0 AND x_percent <= 100)
    ),
    CONSTRAINT chk_match_event_y_percent_range CHECK (
      y_percent IS NULL OR (y_percent >= 0 AND y_percent <= 100)
    )
);

-- =========================
-- Odds (pre-match, live, and closing)
-- =========================
CREATE TABLE match_odd (
    odd_id SERIAL PRIMARY KEY,
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    bookmaker_id INT NOT NULL REFERENCES bookmaker(bookmaker_id) ON DELETE RESTRICT,
    market_id INT NOT NULL REFERENCES betting_market(market_id) ON DELETE RESTRICT,
    outcome_id INT NOT NULL REFERENCES betting_outcome(outcome_id) ON DELETE RESTRICT,
    price_type price_type NOT NULL, -- open, close, or live
    price NUMERIC(10,4) NOT NULL,   -- decimal odds
    line NUMERIC(6,2),              -- for totals (e.g., Over/Under 2.5)
    handicap NUMERIC(6,2),          -- for Asian Handicap and Point Spread
    timestamp TIMESTAMPTZ NOT NULL,
    -- Market metadata
    market_status TEXT DEFAULT 'open', -- open, suspended, closed
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (match_id, bookmaker_id, market_id, outcome_id, price_type, timestamp)
);

-- =========================
-- Standings (snapshots)
-- =========================
CREATE TABLE standings_table (
    standings_id SERIAL PRIMARY KEY,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    stage_id INT REFERENCES competition_stage(stage_id) ON DELETE SET NULL,
    matchday INT,                    -- snapshot per matchday
    snapshot_time TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (season_id, COALESCE(stage_id, -1), COALESCE(matchday, -1), snapshot_time)
);

CREATE TABLE standing_row (
    standings_id INT NOT NULL REFERENCES standings_table(standings_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    position INT,
    played INT,
    wins INT,
    draws INT,
    losses INT,
    goals_for INT,
    goals_against INT,
    goal_diff INT,
    points INT,
    xg_for NUMERIC(6,2),
    xg_against NUMERIC(6,2),
    home_points INT,
    away_points INT,
    PRIMARY KEY (standings_id, team_id)
);

-- =========================
-- Trophies
-- =========================
CREATE TABLE trophy (
    trophy_id SERIAL PRIMARY KEY,
    trophy_name TEXT NOT NULL,
    competition_id INT REFERENCES competition(competition_id) ON DELETE SET NULL,
    weight_g NUMERIC(8,2),
    height_cm NUMERIC(8,2),
    established_year INT,
    picture_url TEXT
);

CREATE TABLE trophy_winner (
    trophy_winner_id SERIAL PRIMARY KEY,
    trophy_id INT NOT NULL REFERENCES trophy(trophy_id) ON DELETE CASCADE,
    season_id INT REFERENCES season(season_id) ON DELETE SET NULL,
    team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    --player_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    UNIQUE (trophy_id, COALESCE(season_id, -1), COALESCE(team_id, -1))
);

-- =========================
-- Advanced Stats and Analytics
-- =========================

-- Team/Player Stats (Enhanced with JSONB for flexible storage)
CREATE TABLE team_match_stats (
  team_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  -- Common stats across sports
  possession NUMERIC(5,2),
  -- Football specific stats
  shots_total INT,
  shots_on_target INT,
  corners INT,
  fouls INT,
  offsides INT,
  passes INT,
  passes_completed INT,
  xg NUMERIC(6,3),
  xa NUMERIC(6,3),
  -- Flexible sport-specific metrics
  football_stats JSONB, -- {crosses: 12, tackles: 18, clearances: 25, free_kicks: 8}
  basketball_stats JSONB, -- {field_goals: 45, three_pointers: 12, free_throws: 18, rebounds: 42}
  american_football_stats JSONB, -- {passing_yards: 285, rushing_yards: 142, turnovers: 2, sacks: 3}
  -- Advanced analytics (all sports)
  advanced_metrics JSONB, -- {expected_possession: 52.3, pressure_index: 7.2, tempo: 65}
  -- Formation and tactics
  formation TEXT,
  tactical_analysis JSONB, -- {pressing_intensity: 8.1, defensive_line: 45.2, width: 72}
  -- Audit fields
  source_url TEXT,
  data_provider data_provider NOT NULL,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, team_id, data_provider)
);

CREATE TABLE player_match_stats (
  player_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  -- Basic performance data
  minutes INT,
  position_played TEXT, -- Position actually played during the match
  -- Football/Soccer specific stats
  -- Attacking stats
  shots_total INT,
  shots_on_target INT,
  goals INT DEFAULT 0,
  assists INT DEFAULT 0,
  xg NUMERIC(6,3),
  xa NUMERIC(6,3),
  --- Passing stats
  passes INT,
  passes_completed INT,
  key_passes INT,
  progressive_passes INT,
  -- Defensive stats
  tackles INT,
  interceptions INT,
  clearances INT,
  blocks INT,
  aerials_won INT,
  --- Dribbling and duels
  dribbles_completed INT,
  duels_won INT,
  duels_lost INT,
  --- Disciplinary stats
  yellow_cards INT DEFAULT 0,
  red_cards INT DEFAULT 0,
  fouls_committed INT,
  fouls_drawn INT,
  -- Basketball specific stats (stored in JSONB for flexibility)
  basketball_stats JSONB, -- {points: 24, rebounds: 8, assists: 6, steals: 2, blocks: 1, turnovers: 3, field_goals_made: 9, field_goals_attempted: 15, three_pointers_made: 3, three_pointers_attempted: 7, free_throws_made: 3, free_throws_attempted: 4}
  -- American Football specific stats  
  american_football_stats JSONB, -- {passing_yards: 285, rushing_yards: 45, receiving_yards: 95, touchdowns: 2, interceptions: 1, fumbles: 0, tackles: 8, sacks: 1}
  -- Performance ratings and grades
  rating NUMERIC(4,2), -- Provider's rating (1-10 scale typically)
  grade TEXT, -- Letter grade or performance level
  -- Physical performance data
  distance_covered NUMERIC(8,2),
  top_speed NUMERIC(5,2),
  sprints INT,
  -- Heat map and positioning
  average_position JSONB, -- {x: 45.2, y: 32.8} average position on field/court
  heat_map_data JSONB, -- Detailed positioning data throughout match
  -- Flexible storage for additional metrics
  advanced_metrics JSONB, -- Provider-specific or sport-specific advanced stats
  -- Audit fields
  source_url TEXT,
  data_provider data_provider NOT NULL,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, player_id, data_provider)
);

-- Goalkeeper match stats
CREATE TABLE goalkeeper_match_stats (
  goalkeeper_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  minutes INT,
  shots_faced INT,
  goals_allowed INT,
  saves INT,
  save_pct NUMERIC(5,2),
  sweeper_actions INT,
  launched_passes INT,
  claims INT,
  punches INT,
  metrics_extra JSONB,
  source_url TEXT,
  data_provider data_provider NOT NULL,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, player_id, data_provider)
);

-- Shot events
CREATE TABLE shot_event (
  shot_event_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  player_id INT REFERENCES player(player_id) ON DELETE SET NULL,
  minute INT,
  second INT,
  x_percent NUMERIC(5,2),
  y_percent NUMERIC(5,2),
  xg NUMERIC(6,3),
  body_part shot_body_part_enum,
  situation shot_situation_enum,
  is_big_chance BOOLEAN,
  is_on_target BOOLEAN,
  is_goal BOOLEAN,
  data_provider data_provider NOT NULL,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_shot_x_range CHECK (x_percent IS NULL OR (x_percent>=0 AND x_percent<=100)),
  CONSTRAINT chk_shot_y_range CHECK (y_percent IS NULL OR (y_percent>=0 AND y_percent<=100))
);

-- Saisonstatistiken (aggregiert)
CREATE TABLE season_player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES player(player_id),
    team_id INTEGER REFERENCES team(team_id),
    competition_id INTEGER REFERENCES competition(id),
    season VARCHAR(20),
    matches_played INTEGER DEFAULT 0,
    minutes_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0, -- Basketball
    rebounds INTEGER DEFAULT 0, -- Basketball
    -- Weitere aggregierte Statistiken...
    stats_data JSONB, -- Flexibel für verschiedene Stats
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, team_id, competition_id, season)
);

-- Referee season stats
CREATE TABLE referee_season_stats (
  referee_season_stats_id SERIAL PRIMARY KEY,
  referee_id INT NOT NULL REFERENCES referee(referee_id) ON DELETE CASCADE,
  season_id INT REFERENCES season(season_id) ON DELETE SET NULL,
  competition_id INT REFERENCES competition(competition_id) ON DELETE SET NULL,
  matches INT,
  yellow_cards INT,
  red_cards INT,
  penalties_awarded INT,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (referee_id, COALESCE(season_id, -1), COALESCE(competition_id, -1))
);

-- player_market_value (time series)
CREATE TABLE player_market_value (
  player_market_value_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  valuation_date DATE NOT NULL,
  value_eur NUMERIC(14,2),
  currency TEXT DEFAULT 'EUR',
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, valuation_date)
);

-- player_national_team_summary
CREATE TABLE player_national_team_summary (
  player_national_team_summary_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  caps INT,
  goals INT,
  last_update DATE,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, team_id)
);


-- =========================
-- External Integrations and Mappings
-- =========================

-- External ID Mapping
CREATE TABLE external_id_map (
  external_id_map_id SERIAL PRIMARY KEY,
  entity_type entity_type NOT NULL,
  entity_id INT NOT NULL, -- References the internal ID of the entity (player_id, team_id, etc.)
  data_provider data_provider NOT NULL,
  external_id TEXT NOT NULL,
  external_url TEXT,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (data_provider, entity_type, external_id)
);

-- Tabelle für die manuelle Überprüfung von unsicheren Mappings
CREATE TABLE mapping_review_queue (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'team', 'player', etc.
    source_name VARCHAR(100) NOT NULL,
    new_entity_data JSONB NOT NULL, -- Die kompletten Daten der neuen Quelle
    potential_match_id INTEGER, -- Die ID des gefundenen, möglichen Treffers
    confidence_score REAL, -- Der Score, der die Überprüfung ausgelöst hat
    review_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'resolved', 'discarded'
    notes TEXT, -- Platz für Kommentare des Bearbeiters
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- =========================
-- Indexes (FK columns and common filters)
-- =========================
-- Core entity indexes
CREATE INDEX idx_club_sport ON club(sport_id);
CREATE INDEX idx_team_club_id ON team(club_id);
CREATE INDEX idx_team_country_id ON team(country_id);
CREATE INDEX idx_player_active ON player(is_active);
CREATE INDEX idx_position_lookup_sport ON position_lookup(sport_id);

-- Competition and match indexes
CREATE INDEX idx_competition_sport ON competition(sport_id);
CREATE INDEX idx_match_sport ON match(sport_id);
CREATE INDEX idx_match_season ON match(season_id);
CREATE INDEX idx_match_competition ON match(competition_id);
CREATE INDEX idx_match_date ON match(match_date_time);
CREATE INDEX idx_match_teams ON match(home_team_id, away_team_id);
CREATE INDEX idx_match_venue ON match(venue_id);
CREATE INDEX idx_match_status ON match(status);

-- Contract and team relationship indexes
CREATE INDEX idx_contract_player ON player_contract(player_id);
CREATE INDEX idx_contract_team ON player_contract(team_id);
CREATE INDEX idx_team_season_team ON team_season(team_id);
CREATE INDEX idx_team_season_season ON team_season(season_id);
CREATE INDEX idx_squad_member_player ON squad_member(player_id);

-- Stats and performance indexes
CREATE INDEX idx_match_event_match ON match_event(match_id);
CREATE INDEX idx_match_event_player ON match_event(player_id);
CREATE INDEX idx_team_match_stats_match_team ON team_match_stats(match_id, team_id);
CREATE INDEX idx_player_match_stats_match_player ON player_match_stats(match_id, player_id);
CREATE INDEX idx_player_match_stats_provider ON player_match_stats(data_provider);
CREATE INDEX idx_gk_match_stats_match_player ON goalkeeper_match_stats(match_id, player_id);
CREATE INDEX idx_shot_event_match ON shot_event(match_id);

-- Betting and odds indexes
CREATE INDEX idx_betting_market_sport ON betting_market(sport_id);
CREATE INDEX idx_match_odd_match ON match_odd(match_id);
CREATE INDEX idx_match_odd_bookmaker ON match_odd(bookmaker_id);
CREATE INDEX idx_match_odd_timestamp ON match_odd(timestamp);
CREATE INDEX idx_match_odd_price_type ON match_odd(price_type);

-- Medical and technology indexes
CREATE INDEX idx_player_injury_player ON player_injury(player_id);
CREATE INDEX idx_player_injury_date ON player_injury(injury_date);

-- External ID mapping
CREATE INDEX idx_external_id_map_entity ON external_id_map(entity_type, entity_id);


-- =========================
-- Triggers to keep updated_at
-- =========================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT table_name FROM information_schema.columns 
           WHERE column_name = 'updated_at' AND table_schema = 'public'
  LOOP
    EXECUTE format('CREATE TRIGGER set_updated_at_%I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at();', r.table_name, r.table_name);
  END LOOP;
END $$;
