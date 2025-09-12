-- PostgreSQL schema for Sports Data Pipeline
-- Target: PostgreSQL
-- Sports: Football (Soccer), Basketball, American Football
-- Features:
-- - Multi-sport support with sport-specific entities
-- - Supports club and national teams via team_type
-- - Seasons support both cross-year (e.g., 2024/2025) and calendar-year via season_type + label
-- - Comprehensive odds tracking (pre-match, live, closing)
-- - Lineups/Events support field/court coordinates (x,y in percent)
-- - Extended staff model (medical, technical, administrative)
-- - SCD2-style historization for Club and Venue names
-- - Enhanced JSONB usage for flexible statistics storage
-- - Technology integration (VAR, Goal-line technology, GPS tracking)
-- - Medical and injury tracking system
-- - Youth development and academy support
-- - Audit fields: source_url, scraped_at, created_at, updated_at

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================
-- Enums
-- =========================
-- Core sport types
CREATE TYPE sport_enum AS ENUM ('football', 'basketball', 'american_football');

-- Team classification
CREATE TYPE team_type AS ENUM ('club', 'national', 'youth', 'women', 'academy');
CREATE TYPE strong_foot AS ENUM ('left', 'right', 'both');
CREATE TYPE surface_type AS ENUM ('grass', 'hybrid', 'artificial', 'indoor', 'hardwood', 'turf');

-- Officials and staff
CREATE TYPE official_role AS ENUM ('referee', 'ar1', 'ar2', 'fourth', 'var', 'avar', 'umpire', 'line_judge', 'field_judge');
CREATE TYPE staff_role AS ENUM ('head_coach', 'assistant_coach', 'gk_coach', 'fitness_coach', 'analyst', 'physio', 'medical', 'team_manager', 'nutritionist', 'psychologist', 'equipment_manager', 'video_analyst', 'scout');

-- Betting and odds
CREATE TYPE price_type AS ENUM ('open', 'close', 'live');
CREATE TYPE season_type AS ENUM ('cross_year', 'calendar_year');

-- Medical and health
CREATE TYPE nationality_type AS ENUM ('nationality', 'citizenship');
CREATE TYPE injury_type AS ENUM ('muscle', 'bone', 'joint', 'ligament', 'concussion', 'illness', 'other');
CREATE TYPE absence_reason AS ENUM ('injury', 'suspension', 'illness', 'national_duty', 'personal', 'coach_decision');

-- Technology integration
CREATE TYPE technology_type AS ENUM ('var', 'goal_line', 'offside', 'gps', 'heart_rate', 'player_tracking');

-- Youth development
CREATE TYPE academy_level AS ENUM ('u8', 'u10', 'u12', 'u14', 'u16', 'u18', 'u21', 'reserve');

-- Basketball specific
CREATE TYPE basketball_position AS ENUM ('point_guard', 'shooting_guard', 'small_forward', 'power_forward', 'center');

-- American Football specific  
CREATE TYPE american_football_position AS ENUM ('quarterback', 'running_back', 'wide_receiver', 'tight_end', 'offensive_line', 'defensive_line', 'linebacker', 'defensive_back', 'kicker', 'punter');

-- =========================
-- Core Lookups
-- =========================
-- Sports definition table
CREATE TABLE sport (
    sport_id SERIAL PRIMARY KEY,
    sport_type sport_enum NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    rules_url TEXT,
    governing_body TEXT
);

CREATE TABLE country (
    country_id SERIAL PRIMARY KEY,
    iso2 CHAR(2) UNIQUE,
    iso3 CHAR(3) UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE city (
    city_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    country_id INT REFERENCES country(country_id) ON DELETE RESTRICT,
    state_region TEXT
);

CREATE TABLE association (
    association_id SERIAL PRIMARY KEY,
    association_name TEXT NOT NULL,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    is_national BOOLEAN DEFAULT TRUE,
    parent_association_id INT REFERENCES association(association_id) ON DELETE SET NULL
);

-- Enhanced position lookup with sport-specific positions
CREATE TABLE position_lookup (
    position_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    code TEXT NOT NULL, -- e.g., GK, RB, CB, PG, QB, etc.
    name TEXT NOT NULL,
    position_group TEXT, -- e.g., 'defense', 'midfield', 'attack', 'guard', 'forward', 'offense'
    sport_specific_data JSONB, -- Flexible data for sport-specific attributes
    UNIQUE(sport_id, code)
);

CREATE TABLE weather_lookup (
    weather_id SERIAL PRIMARY KEY,
    condition TEXT NOT NULL -- e.g., Clear, Rain, Snow, Cloudy
);

CREATE TABLE bookmaker (
    bookmaker_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE betting_market (
    market_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    name TEXT NOT NULL,      -- e.g., 1X2, Over/Under, Asian Handicap, Moneyline, Point Spread
    UNIQUE(sport_id, name)
);

CREATE TABLE betting_outcome (
    outcome_id SERIAL PRIMARY KEY,
    market_id INT NOT NULL REFERENCES betting_market(market_id) ON DELETE CASCADE,
    name TEXT NOT NULL,      -- e.g., Home, Draw, Away, Over, Under, +0.5, -1.0
    UNIQUE(market_id, name)
);

-- =========================
-- Organizations and Venues
-- =========================
CREATE TABLE club (
    club_id SERIAL PRIMARY KEY,
    sport_id INT REFERENCES sport(sport_id) ON DELETE RESTRICT,
    code TEXT UNIQUE,                -- optional short code like FCB, BVB, LAL (Lakers)
    founding_year INT,
    colors TEXT,
    association_id INT REFERENCES association(association_id) ON DELETE SET NULL,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    members INT,                     -- membership count
    address_street TEXT,
    address_postal_code TEXT,
    address_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    -- Commercial information
    market_value NUMERIC(15,2),
    market_value_currency TEXT DEFAULT 'EUR',
    main_sponsor TEXT,
    kit_supplier TEXT,
    -- Multi-sport club support
    parent_club_id INT REFERENCES club(club_id) ON DELETE SET NULL, -- for multi-sport organizations
    -- Social media and web presence
    website_url TEXT,
    social_media JSONB, -- {twitter:"", instagram:"", tiktok:"", youtube:"", facebook:""}
    -- Audit fields
    source_url TEXT,
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
    city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    address_street TEXT,
    address_postal_code TEXT,
    operator TEXT,
    owner TEXT,
    construction_date DATE,
    opening_date DATE,
    surface surface_type NOT NULL,
    -- Multi-sport venue support
    supported_sports JSONB, -- Array of sport types this venue supports
    -- Sport-specific dimensions
    field_dimensions JSONB, -- {football: {length: 105, width: 68}, basketball: {length: 28, width: 15}}
    capacity_national INT,
    capacity_international INT,
    capacity_details JSONB, -- {total: 75000, seated: 65000, standing: 10000, vip: 2000}
    -- Technology and facilities
    has_var BOOLEAN DEFAULT FALSE,
    has_goal_line_tech BOOLEAN DEFAULT FALSE,
    has_player_tracking BOOLEAN DEFAULT FALSE,
    facilities JSONB, -- {parking_spaces: 5000, restaurants: 12, shops: 8, conference_rooms: 20}
    -- Environmental
    indoor BOOLEAN DEFAULT FALSE,
    retractable_roof BOOLEAN DEFAULT FALSE,
    climate_controlled BOOLEAN DEFAULT FALSE,
    -- Commercial
    naming_rights_sponsor TEXT,
    naming_rights_until DATE,
    official_website TEXT,
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SCD2: Venue name history
CREATE TABLE venue_name_history (
    venue_name_history_id SERIAL PRIMARY KEY,
    venue_id INT NOT NULL REFERENCES venue(venue_id) ON DELETE CASCADE,
    venue_name TEXT NOT NULL,
    former_names TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN GENERATED ALWAYS AS (valid_to IS NULL) STORED
);

-- Club ↔ Venue tenancy periods (M:N)
CREATE TABLE club_venue_tenancy (
    tenancy_id SERIAL PRIMARY KEY,
    club_id INT NOT NULL REFERENCES club(club_id) ON DELETE CASCADE,
    venue_id INT NOT NULL REFERENCES venue(venue_id) ON DELETE CASCADE,
    main_tenant BOOLEAN DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    UNIQUE (club_id, venue_id, start_date)
);

-- =========================
-- Teams and People
-- =========================
CREATE TABLE team (
    team_id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    club_id INT REFERENCES club(club_id) ON DELETE SET NULL,  -- null for national teams
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL, -- set for national teams
    team_type team_type NOT NULL,
    market_value NUMERIC(14,2),
    market_value_currency TEXT DEFAULT 'EUR',
    social_media JSONB, -- {twitter:"", instagram:"", tiktok:"", youtube:""}
    is_senior BOOLEAN DEFAULT TRUE,
    is_male BOOLEAN,
    -- Youth development
    academy_level academy_level,
    parent_team_id INT REFERENCES team(team_id) ON DELETE SET NULL, -- link to senior team
    -- Commercial
    main_sponsor TEXT,
    kit_supplier TEXT,
    -- Performance tracking
    current_form JSONB, -- Last 5-10 games performance summary
    season_objectives JSONB, -- {league_position: 4, cup_progress: "quarter_finals"}
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT team_club_or_country CHECK (
        (team_type = 'club' AND club_id IS NOT NULL) OR
        (team_type IN ('national','youth','women') AND (club_id IS NULL OR team_type IN ('youth','academy')) )
    )
);

-- Agents (player representatives)
CREATE TABLE agent (
    agent_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name)
);

-- Equipment suppliers (kit/boot providers)
CREATE TABLE equipment_supplier (
    equipment_supplier_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    official_website TEXT,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE player (
    player_id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    nickname TEXT,
    birthdate DATE,
    birth_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    -- Physical attributes
    height_cm INT,
    weight_kg INT,
    strong_foot strong_foot,
    -- Sport-specific attributes stored as JSONB
    sport_attributes JSONB, -- {shooting_range: "3pt", vertical_leap: 85, sprint_speed: 32.5}
    -- Career information
    is_active BOOLEAN DEFAULT TRUE,
    professional_debut DATE,
    retirement_date DATE,
    -- Youth development
    youth_career JSONB, -- [{club: "Barcelona", from: "2015", to: "2018", level: "u18"}]
    -- Commercial relationships
    agent_id INT REFERENCES agent(agent_id) ON DELETE SET NULL,
    equipment_supplier_id INT REFERENCES equipment_supplier(equipment_supplier_id) ON DELETE SET NULL,
    -- Medical and fitness
    medical_clearance BOOLEAN DEFAULT TRUE,
    medical_clearance_date DATE,
    fitness_level JSONB, -- Latest fitness test results
    -- Social and digital presence
    social_media JSONB, -- {instagram: "@player", twitter: "@player", tiktok: "@player"}
    -- Performance analytics
    career_stats JSONB, -- Aggregated career statistics
    current_market_value NUMERIC(12,2),
    current_market_value_currency TEXT DEFAULT 'EUR',
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player multiple nationalities/citizenships
CREATE TABLE player_country (
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    country_id INT NOT NULL REFERENCES country(country_id) ON DELETE RESTRICT,
    type nationality_type NOT NULL,
    PRIMARY KEY (player_id, country_id, type)
);

CREATE TABLE coach (
    coach_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    birthdate DATE,
    birth_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Broader staff entity (includes head/assistant, GK coach, analysts, etc.)
CREATE TABLE staff_member (
    staff_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    birthdate DATE,
    birth_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
    -- Qualifications and certifications
    qualifications JSONB, -- {uefa_pro_license: true, medical_degree: true, certifications: ["FIFA", "UEFA"]}
    specializations JSONB, -- {areas: ["youth_development", "injury_prevention"], languages: ["en", "de", "es"]}
    experience_years INT,
    -- Contact and social media
    social_media JSONB,
    -- Audit fields
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Medical staff specifically
CREATE TABLE medical_staff (
    medical_staff_id SERIAL PRIMARY KEY,
    staff_id INT REFERENCES staff_member(staff_id) ON DELETE CASCADE,
    medical_license_number TEXT,
    medical_license_country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    specialization TEXT, -- e.g., 'sports_medicine', 'physiotherapy', 'nutrition', 'psychology'
    can_prescribe_medication BOOLEAN DEFAULT FALSE,
    emergency_certified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- Competitions / Seasons
-- =========================
CREATE TABLE competition (
    competition_id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sport(sport_id) ON DELETE RESTRICT,
    competition_name TEXT NOT NULL,
    association_id INT REFERENCES association(association_id) ON DELETE SET NULL,
    country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
    since_year INT,
    is_cup BOOLEAN DEFAULT FALSE,
    is_youth BOOLEAN DEFAULT FALSE,
    is_women BOOLEAN DEFAULT FALSE,
    is_national BOOLEAN,
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
    name TEXT NOT NULL,       -- e.g., Regular Season, Group A, Round of 16
    round_number INT,
    leg INT,
    stage_format JSONB, -- {type: "group", teams_per_group: 4, advance_count: 2}
    UNIQUE(competition_id, season_id, name, COALESCE(round_number, -1), COALESCE(leg, -1))
);

-- =========================
-- Medical and Health Tracking
-- =========================
CREATE TABLE player_injury (
    injury_id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    injury_type injury_type NOT NULL,
    injury_description TEXT,
    body_part TEXT, -- e.g., 'left_knee', 'right_shoulder', 'head'
    severity TEXT, -- e.g., 'minor', 'moderate', 'severe', 'career_threatening'
    injury_date DATE,
    expected_return_date DATE,
    actual_return_date DATE,
    medical_staff_id INT REFERENCES medical_staff(medical_staff_id) ON DELETE SET NULL,
    treatment_plan JSONB, -- Detailed treatment and recovery plan
    medical_reports JSONB, -- Array of medical report URLs and summaries
    caused_by_match_id INT REFERENCES match(match_id) ON DELETE SET NULL,
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player fitness and health monitoring
CREATE TABLE player_fitness_record (
    fitness_record_id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    test_date DATE NOT NULL,
    test_type TEXT, -- e.g., 'preseason', 'monthly', 'return_from_injury'
    fitness_data JSONB, -- {vo2_max: 65, sprint_speed: 32.1, endurance: 85, flexibility: 78}
    medical_staff_id INT REFERENCES medical_staff(medical_staff_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- Technology Integration
-- =========================
CREATE TABLE match_technology_data (
    technology_data_id SERIAL PRIMARY KEY,
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    technology_type technology_type NOT NULL,
    event_minute INT,
    event_second INT,
    decision_result JSONB, -- VAR decision, goal-line technology result, etc.
    technology_provider TEXT,
    confidence_level NUMERIC(5,2), -- 0-100 confidence in the technology decision
    human_override BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player tracking data (GPS, performance metrics)
CREATE TABLE player_tracking_data (
    tracking_id SERIAL PRIMARY KEY,
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    timestamp_seconds INT, -- Second in match when data was recorded
    -- Physical metrics
    distance_covered NUMERIC(8,2), -- Total distance in meters
    top_speed NUMERIC(5,2), -- km/h
    sprint_count INT,
    heart_rate INT,
    -- Positional data
    x_position NUMERIC(6,2), -- Field position coordinates
    y_position NUMERIC(6,2),
    -- Sport-specific metrics stored flexibly
    performance_metrics JSONB, -- {acceleration: 8.5, deceleration: 7.2, jump_height: 65}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- Team Seasons, Squads, Contracts, Staff Assignments
-- =========================
CREATE TABLE team_season (
    team_season_id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    coach_id INT REFERENCES coach(coach_id) ON DELETE SET NULL,
    league_position INT,
    group_name TEXT,
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

CREATE TABLE contract (
    contract_id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    start_date DATE,
    end_date DATE,
    transfer_fee NUMERIC(14,2),
    bonus_fees_sum NUMERIC(14,2),
    transfer_type TEXT, -- lookup optional
    source_url TEXT,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE staff_assignment (
    staff_assignment_id SERIAL PRIMARY KEY,
    staff_id INT NOT NULL REFERENCES staff_member(staff_id) ON DELETE CASCADE,
    team_season_id INT NOT NULL REFERENCES team_season(team_season_id) ON DELETE CASCADE,
    role staff_role NOT NULL,
    start_date DATE,
    end_date DATE,
    UNIQUE (staff_id, team_season_id, role, COALESCE(start_date, '0001-01-01'::date))
);

-- =========================
-- Matches and Results
-- =========================
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
    referee_country_id INT REFERENCES country(country_id) ON DELETE SET NULL,
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
    birthdate DATE,
    birth_city_id INT REFERENCES city(city_id) ON DELETE SET NULL,
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
    reason_off TEXT,
    rating NUMERIC(4,2), -- optional source ratings
    PRIMARY KEY (match_id, team_id, player_id)
);

CREATE TABLE event_type_lookup (
    event_type_id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- goal, shot, foul, card, sub, offside, corner, free_kick, penalty, save, block
    name TEXT
);

CREATE TABLE event_qualifier_lookup (
    qualifier_id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- e.g., header, left_foot, right_foot, inside_box, outside_box
    name TEXT
);

CREATE TABLE match_event (
    event_id SERIAL PRIMARY KEY,
    match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    event_type_id INT NOT NULL REFERENCES event_type_lookup(event_type_id) ON DELETE RESTRICT,
    qualifier_id INT REFERENCES event_qualifier_lookup(qualifier_id) ON DELETE SET NULL,
    minute INT,
    second INT,
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
    -- Live betting specific fields
    match_minute INT, -- Minute in match when odds were recorded (for live odds)
    match_second INT,
    current_score JSONB, -- Score at time of odds recording for live betting
    -- Market metadata
    market_status TEXT DEFAULT 'open', -- open, suspended, closed
    max_bet_amount NUMERIC(12,2),
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
    club_id INT REFERENCES club(club_id) ON DELETE SET NULL,
    player_id INT REFERENCES player(player_id) ON DELETE SET NULL,
    UNIQUE (trophy_id, COALESCE(season_id, -1), COALESCE(team_id, -1), COALESCE(club_id, -1), COALESCE(player_id, -1))
);

-- =========================
-- Indexes (FK columns and common filters)
-- =========================
-- Core entity indexes
CREATE INDEX idx_club_sport ON club(sport_id);
CREATE INDEX idx_team_sport ON team(sport_id);
CREATE INDEX idx_team_club_id ON team(club_id);
CREATE INDEX idx_team_country_id ON team(country_id);
CREATE INDEX idx_player_sport ON player(sport_id);
CREATE INDEX idx_player_birth_city_id ON player(birth_city_id);
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
CREATE INDEX idx_contract_player ON contract(player_id);
CREATE INDEX idx_contract_team ON contract(team_id);
CREATE INDEX idx_team_season_team ON team_season(team_id);
CREATE INDEX idx_team_season_season ON team_season(season_id);
CREATE INDEX idx_squad_member_player ON squad_member(player_id);

-- Stats and performance indexes
CREATE INDEX idx_match_event_match ON match_event(match_id);
CREATE INDEX idx_match_event_player ON match_event(player_id);
CREATE INDEX idx_team_match_stats_match_team ON team_match_stats(match_id, team_id);
CREATE INDEX idx_player_match_stats_match_player ON player_match_stats(match_id, player_id);
CREATE INDEX idx_player_match_stats_provider ON player_match_stats(provider);

-- Betting and odds indexes
CREATE INDEX idx_betting_market_sport ON betting_market(sport_id);
CREATE INDEX idx_match_odd_match ON match_odd(match_id);
CREATE INDEX idx_match_odd_bookmaker ON match_odd(bookmaker_id);
CREATE INDEX idx_match_odd_timestamp ON match_odd(timestamp);
CREATE INDEX idx_match_odd_price_type ON match_odd(price_type);

-- Medical and technology indexes
CREATE INDEX idx_player_injury_player ON player_injury(player_id);
CREATE INDEX idx_player_injury_date ON player_injury(injury_date);
CREATE INDEX idx_player_fitness_player ON player_fitness_record(player_id);
CREATE INDEX idx_player_fitness_date ON player_fitness_record(test_date);
CREATE INDEX idx_match_technology_match ON match_technology_data(match_id);
CREATE INDEX idx_player_tracking_match ON player_tracking_data(match_id);
CREATE INDEX idx_player_tracking_player ON player_tracking_data(player_id);

-- Staff and organizational indexes
CREATE INDEX idx_medical_staff_staff ON medical_staff(staff_id);
CREATE INDEX idx_staff_assignment_staff ON staff_assignment(staff_id);
CREATE INDEX idx_staff_assignment_team_season ON staff_assignment(team_season_id);

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

-- =============================================
-- Flattened migrations appended for greenfield
-- Order: 0002 -> 0003 -> 0004 -> 0005 -> 0006
-- =============================================

-- Migration 0002_seed.sql
-- Seed data for core lookups (idempotent)

-- Sports
INSERT INTO sport (sport_type, name, description, governing_body) VALUES
  ('football', 'Football (Soccer)', 'Association football played with feet', 'FIFA'),
  ('basketball', 'Basketball', 'Team sport played on a court with baskets', 'FIBA'),
  ('american_football', 'American Football', 'Gridiron football played primarily in North America', 'NFL')
ON CONFLICT (sport_type) DO NOTHING;

-- Positions (Football)
INSERT INTO position_lookup (sport_id, code, name, position_group) 
SELECT s.sport_id, p.code, p.name, p.position_group FROM sport s
CROSS JOIN (VALUES
  ('GK','Goalkeeper','goalkeeper'),
  ('RB','Right Back','defense'),
  ('RCB','Right Center Back','defense'),
  ('CB','Center Back','defense'),
  ('LCB','Left Center Back','defense'),
  ('LB','Left Back','defense'),
  ('RWB','Right Wing Back','defense'),
  ('LWB','Left Wing Back','defense'),
  ('DM','Defensive Midfielder','midfield'),
  ('CM','Central Midfielder','midfield'),
  ('AM','Attacking Midfielder','midfield'),
  ('RW','Right Winger','attack'),
  ('LW','Left Winger','attack'),
  ('CF','Center Forward','attack'),
  ('ST','Striker','attack')
) AS p(code, name, position_group)
WHERE s.sport_type = 'football'
ON CONFLICT (sport_id, code) DO NOTHING;

-- Positions (Basketball)
INSERT INTO position_lookup (sport_id, code, name, position_group) 
SELECT s.sport_id, p.code, p.name, p.position_group FROM sport s
CROSS JOIN (VALUES
  ('PG','Point Guard','guard'),
  ('SG','Shooting Guard','guard'),
  ('SF','Small Forward','forward'),
  ('PF','Power Forward','forward'),
  ('C','Center','center')
) AS p(code, name, position_group)
WHERE s.sport_type = 'basketball'
ON CONFLICT (sport_id, code) DO NOTHING;

-- Positions (American Football)
INSERT INTO position_lookup (sport_id, code, name, position_group) 
SELECT s.sport_id, p.code, p.name, p.position_group FROM sport s
CROSS JOIN (VALUES
  ('QB','Quarterback','offense'),
  ('RB','Running Back','offense'),
  ('WR','Wide Receiver','offense'),
  ('TE','Tight End','offense'),
  ('OL','Offensive Line','offense'),
  ('DL','Defensive Line','defense'),
  ('LB','Linebacker','defense'),
  ('DB','Defensive Back','defense'),
  ('K','Kicker','special_teams'),
  ('P','Punter','special_teams')
) AS p(code, name, position_group)
WHERE s.sport_type = 'american_football'
ON CONFLICT (sport_id, code) DO NOTHING;

-- Event types
INSERT INTO event_type_lookup (code, name) VALUES
  ('goal','Goal'),
  ('own_goal','Own Goal'),
  ('penalty_goal','Penalty Goal'),
  ('shot_on','Shot On Target'),
  ('shot_off','Shot Off Target'),
  ('big_chance_missed','Big Chance Missed'),
  ('foul','Foul'),
  ('yellow_card','Yellow Card'),
  ('second_yellow','Second Yellow'),
  ('red_card','Red Card'),
  ('substitution','Substitution'),
  ('offside','Offside'),
  ('corner','Corner'),
  ('free_kick','Free Kick'),
  ('penalty_awarded','Penalty Awarded'),
  ('save','Save'),
  ('block','Block'),
  ('clearance','Clearance')
ON CONFLICT (code) DO NOTHING;

-- Event qualifiers
INSERT INTO event_qualifier_lookup (code, name) VALUES
  ('header','Header'),
  ('left_foot','Left Foot'),
  ('right_foot','Right Foot'),
  ('inside_box','Inside Box'),
  ('outside_box','Outside Box'),
  ('counter_attack','Counter Attack'),
  ('fast_break','Fast Break'),
  ('set_piece','Set Piece'),
  ('open_play','Open Play')
ON CONFLICT (code) DO NOTHING;

-- Weather
INSERT INTO weather_lookup (condition) VALUES
  ('Clear'), ('Cloudy'), ('Rain'), ('Snow'), ('Windy'), ('Fog')
ON CONFLICT DO NOTHING;

-- Bookmakers
INSERT INTO bookmaker (name) VALUES
  ('Bet365'), ('Pinnacle'), ('William Hill'), ('Betfair')
ON CONFLICT (name) DO NOTHING;

-- Markets (Sport-specific)
INSERT INTO betting_market (sport_id, name)
SELECT s.sport_id, m.name FROM sport s
CROSS JOIN (VALUES
  ('1X2'),
  ('Over/Under Goals'),
  ('Asian Handicap'),
  ('Both Teams To Score'),
  ('Correct Score')
) AS m(name)
WHERE s.sport_type = 'football'
ON CONFLICT (sport_id, name) DO NOTHING;

INSERT INTO betting_market (sport_id, name)
SELECT s.sport_id, m.name FROM sport s
CROSS JOIN (VALUES
  ('Moneyline'),
  ('Point Spread'),
  ('Total Points'),
  ('Player Props')
) AS m(name)
WHERE s.sport_type = 'basketball'
ON CONFLICT (sport_id, name) DO NOTHING;

INSERT INTO betting_market (sport_id, name)
SELECT s.sport_id, m.name FROM sport s
CROSS JOIN (VALUES
  ('Moneyline'),
  ('Point Spread'),
  ('Total Points'),
  ('Player Props')
) AS m(name)
WHERE s.sport_type = 'american_football'
ON CONFLICT (sport_id, name) DO NOTHING;

-- Outcomes for Football 1X2
INSERT INTO betting_outcome (market_id, name)
SELECT m.market_id, v.name FROM (
  SELECT 'Home' AS name UNION ALL SELECT 'Draw' UNION ALL SELECT 'Away'
) v
JOIN betting_market m ON m.name = '1X2'
JOIN sport s ON s.sport_id = m.sport_id AND s.sport_type = 'football'
ON CONFLICT (market_id, name) DO NOTHING;

-- Outcomes for Football Over/Under Goals
INSERT INTO betting_outcome (market_id, name)
SELECT m.market_id, v.name FROM (
  SELECT 'Over' AS name UNION ALL SELECT 'Under'
) v
JOIN betting_market m ON m.name = 'Over/Under Goals'
JOIN sport s ON s.sport_id = m.sport_id AND s.sport_type = 'football'
ON CONFLICT (market_id, name) DO NOTHING;

-- Outcomes for Basketball/American Football Moneyline
INSERT INTO betting_outcome (market_id, name)
SELECT m.market_id, v.name FROM (
  SELECT 'Home' AS name UNION ALL SELECT 'Away'
) v
JOIN betting_market m ON m.name = 'Moneyline'
JOIN sport s ON s.sport_id = m.sport_id AND s.sport_type IN ('basketball', 'american_football')
ON CONFLICT (market_id, name) DO NOTHING;

-- Outcomes for Point Spread
INSERT INTO betting_outcome (market_id, name)
SELECT m.market_id, v.name FROM (
  SELECT 'Home' AS name UNION ALL SELECT 'Away'
) v
JOIN betting_market m ON m.name = 'Point Spread'
JOIN sport s ON s.sport_id = m.sport_id AND s.sport_type IN ('basketball', 'american_football')
ON CONFLICT (market_id, name) DO NOTHING;
ON CONFLICT (market_id, name) DO NOTHING;

-- Migration 0003_seed_geo_assoc.sql
-- Seed countries and associations (idempotent)

-- Minimal country seed (extend as needed)
INSERT INTO country (iso2, iso3, name) VALUES
  -- Europe (incl. Home Nations as custom codes)
  ('DE','DEU','Germany'),
  ('GB','GBR','United Kingdom'),
  ('EN','ENG','England'),
  ('SC','SCO','Scotland'),
  ('WA','WAL','Wales'),
  ('NI','NIR','Northern Ireland'),
  ('ES','ESP','Spain'),
  ('IT','ITA','Italy'),
  ('FR','FRA','France'),
  ('NL','NLD','Netherlands'),
  ('PT','PRT','Portugal'),
  ('BE','BEL','Belgium'),
  ('CH','CHE','Switzerland'),
  ('AT','AUT','Austria'),
  ('DK','DNK','Denmark'),
  ('NO','NOR','Norway'),
  ('SE','SWE','Sweden'),
  ('FI','FIN','Finland'),
  ('IE','IRL','Ireland'),
  ('PL','POL','Poland'),
  ('CZ','CZE','Czechia'),
  ('SK','SVK','Slovakia'),
  ('HU','HUN','Hungary'),
  ('RO','ROU','Romania'),
  ('BG','BGR','Bulgaria'),
  ('GR','GRC','Greece'),
  ('TR','TUR','Türkiye'),
  ('HR','HRV','Croatia'),
  ('RS','SRB','Serbia'),
  ('SI','SVN','Slovenia'),
  ('UA','UKR','Ukraine'),
  ('RU','RUS','Russia'),
  ('IS','ISL','Iceland'),
  ('LU','LUX','Luxembourg'),
  ('LT','LTU','Lithuania'),
  ('LV','LVA','Latvia'),
  ('EE','EST','Estonia'),
  -- Americas
  ('US','USA','United States'),
  ('CA','CAN','Canada'),
  ('MX','MEX','Mexico'),
  ('BR','BRA','Brazil'),
  ('AR','ARG','Argentina'),
  ('CL','CHL','Chile'),
  ('CO','COL','Colombia'),
  ('UY','URY','Uruguay'),
  ('PE','PER','Peru'),
  ('EC','ECU','Ecuador'),
  -- Asia
  ('CN','CHN','China'),
  ('JP','JPN','Japan'),
  ('KR','KOR','South Korea'),
  ('SA','SAU','Saudi Arabia'),
  ('QA','QAT','Qatar'),
  ('AE','ARE','United Arab Emirates'),
  ('IR','IRN','Iran'),
  ('IN','IND','India'),
  ('ID','IDN','Indonesia'),
  ('TH','THA','Thailand'),
  ('VN','VNM','Vietnam'),
  ('MY','MYS','Malaysia'),
  -- Africa
  ('MA','MAR','Morocco'),
  ('DZ','DZA','Algeria'),
  ('TN','TUN','Tunisia'),
  ('EG','EGY','Egypt'),
  ('NG','NGA','Nigeria'),
  ('GH','GHA','Ghana'),
  ('CI','CIV','Côte d''Ivoire'),
  ('SN','SEN','Senegal'),
  ('CM','CMR','Cameroon'),
  ('ZA','ZAF','South Africa'),
  -- Oceania
  ('AU','AUS','Australia'),
  ('NZ','NZL','New Zealand')
ON CONFLICT (iso2) DO NOTHING;

-- Global and European associations
-- FIFA (no parent)
INSERT INTO association (association_name, is_national, parent_association_id)
VALUES ('FIFA', FALSE, NULL)
ON CONFLICT DO NOTHING;

-- UEFA (parent = FIFA)
INSERT INTO association (association_name, is_national, parent_association_id)
SELECT 'UEFA', FALSE, a.association_id
FROM association a
WHERE a.association_name = 'FIFA'
ON CONFLICT DO NOTHING;

-- National associations (parents = UEFA)
INSERT INTO association (association_name, is_national, parent_association_id) (
  SELECT v.name, TRUE, u.association_id
  FROM (VALUES
    ('DFB'),              -- Germany
    ('DFL'),              -- German League (operator, not strictly a FA)
    ('The FA'),           -- England
    ('RFEF'),             -- Spain
    ('FIGC'),             -- Italy
    ('FFF'),              -- France
    ('KNVB'),             -- Netherlands
    ('FPF')               -- Portugal
  ) AS v(name)
  CROSS JOIN (SELECT association_id FROM association WHERE association_name = 'UEFA') u
)
ON CONFLICT DO NOTHING;

-- Leagues as associations/operators (optional)
INSERT INTO association (association_name, is_national, parent_association_id)
SELECT 'Premier League', TRUE, u.association_id
FROM association u WHERE u.association_name = 'The FA'
ON CONFLICT DO NOTHING;

-- Equipment suppliers (brands)
INSERT INTO equipment_supplier (name, official_website) VALUES
  ('Adidas','https://www.adidas.com'),
  ('Nike','https://www.nike.com'),
  ('Puma','https://eu.puma.com'),
  ('Under Armour','https://www.underarmour.com'),
  ('New Balance','https://www.newbalance.com'),
  ('Umbro','https://www.umbro.com'),
  ('Kappa','https://www.kappa.com'),
  ('Joma','https://www.joma-sport.com'),
  ('Hummel','https://www.hummel.net'),
  ('Macron','https://www.macron.com'),
  ('Mizuno','https://www.mizunousa.com'),
  ('Diadora','https://www.diadora.com'),
  ('Lotto','https://www.lotto.it'),
  ('Erreà','https://www.errea.com'),
  ('Kelme','https://www.kelme.com'),
  ('Le Coq Sportif','https://www.lecoqsportif.com'),
  ('Castore','https://castore.com'),
  ('Warrior','https://www.warrior.com'),
  ('Uhlsport','https://www.uhlsport.com'),
  ('Reebok','https://www.reebok.com'),
  ('ASICS','https://www.asics.com'),
  ('Li-Ning','https://store.lining.com'),
  ('PEAK','https://www.peak.com'),
  ('ANTA','https://www.anta.com')
ON CONFLICT (name) DO NOTHING;

-- Migration 0004_stats_ratings_absences_external_ids.sql
-- Enums
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'provider_enum') THEN
    CREATE TYPE provider_enum AS ENUM (
      'fbref','transfermarkt','whoscored','sofascore','oddsportal','premierleague','fussballzz','fussballtransfers'
    );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'absence_type_enum') THEN
    CREATE TYPE absence_type_enum AS ENUM ('injury','suspension','illness','national_duty');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_enum') THEN
    CREATE TYPE entity_type_enum AS ENUM (
      'club','team','player','coach','staff_member','referee','match','competition','season','venue','association','trophy'
    );
  END IF;
END $$;

-- External ID Mapping
CREATE TABLE IF NOT EXISTS external_id_map (
  external_id_map_id SERIAL PRIMARY KEY,
  entity_type entity_type_enum NOT NULL,
  entity_id INT NOT NULL,
  provider provider_enum NOT NULL,
  external_id TEXT NOT NULL,
  external_url TEXT,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (provider, entity_type, external_id)
);
CREATE INDEX IF NOT EXISTS idx_external_id_map_entity ON external_id_map(entity_type, entity_id);

-- Team/Player Stats (Enhanced with JSONB for flexible storage)
CREATE TABLE IF NOT EXISTS team_match_stats (
  team_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  provider provider_enum NOT NULL,
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
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, team_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_team_match_stats_match_team ON team_match_stats(match_id, team_id);

CREATE TABLE IF NOT EXISTS player_match_stats (
  player_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  provider provider_enum NOT NULL,
  -- Basic performance data
  minutes INT,
  position_played TEXT, -- Position actually played during the match
  -- Football/Soccer specific stats
  shots_total INT,
  shots_on_target INT,
  goals INT DEFAULT 0,
  assists INT DEFAULT 0,
  xg NUMERIC(6,3),
  xa NUMERIC(6,3),
  passes INT,
  passes_completed INT,
  key_passes INT,
  progressive_passes INT,
  tackles INT,
  interceptions INT,
  clearances INT,
  dribbles_completed INT,
  duels_won INT,
  yellows INT DEFAULT 0,
  reds INT DEFAULT 0,
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
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, player_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_player_match_stats_match_player ON player_match_stats(match_id, player_id);

-- Ratings & Formations
CREATE TABLE IF NOT EXISTS player_match_rating (
  player_match_rating_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  provider provider_enum NOT NULL,
  rating NUMERIC(4,2),
  minutes INT,
  motm BOOLEAN,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, player_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_player_match_rating_match_player ON player_match_rating(match_id, player_id);

CREATE TABLE IF NOT EXISTS team_match_formation (
  team_match_formation_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  provider provider_enum NOT NULL,
  formation TEXT,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, team_id, provider)
);

-- Absences
CREATE TABLE IF NOT EXISTS player_absence (
  absence_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  absence_type absence_type_enum NOT NULL,
  reason TEXT,
  start_date DATE,
  end_date DATE,
  expected_return_date DATE,
  missed_games INT,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_player_absence_player ON player_absence(player_id);
CREATE INDEX IF NOT EXISTS idx_player_absence_dates ON player_absence(start_date, end_date);

-- Lineup start position coords additions
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='match_lineup_entry' AND column_name='x_percent'
  ) THEN
    ALTER TABLE match_lineup_entry ADD COLUMN x_percent NUMERIC(5,2);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='match_lineup_entry' AND column_name='y_percent'
  ) THEN
    ALTER TABLE match_lineup_entry ADD COLUMN y_percent NUMERIC(5,2);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_match_lineup_x_percent_range'
  ) THEN
    ALTER TABLE match_lineup_entry
    ADD CONSTRAINT chk_match_lineup_x_percent_range CHECK (
      x_percent IS NULL OR (x_percent >= 0 AND x_percent <= 100)
    );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_match_lineup_y_percent_range'
  ) THEN
    ALTER TABLE match_lineup_entry
    ADD CONSTRAINT chk_match_lineup_y_percent_range CHECK (
      y_percent IS NULL OR (y_percent >= 0 AND y_percent <= 100)
    );
  END IF;
END $$;

-- Migration 0005_enhancements.sql
-- Enhanced tables are now part of the main schema definition
-- This section is kept for migration compatibility

-- Goalkeeper match stats
CREATE TABLE IF NOT EXISTS goalkeeper_match_stats (
  goalkeeper_match_stats_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
  provider provider_enum NOT NULL,
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
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, player_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_gk_match_stats_match_player ON goalkeeper_match_stats(match_id, player_id);

-- Team tactical style
CREATE TABLE IF NOT EXISTS team_match_style (
  team_match_style_id SERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  provider provider_enum NOT NULL,
  directness NUMERIC(6,3),
  press_intensity NUMERIC(6,3),
  width NUMERIC(6,3),
  line_height NUMERIC(6,3),
  metrics_extra JSONB,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (match_id, team_id, provider)
);

-- Team season kit
CREATE TYPE IF NOT EXISTS kit_type_enum AS ENUM ('home','away','third','gk');
CREATE TABLE IF NOT EXISTS team_season_kit (
  team_season_kit_id SERIAL PRIMARY KEY,
  team_season_id INT NOT NULL REFERENCES team_season(team_season_id) ON DELETE CASCADE,
  equipment_supplier_id INT REFERENCES equipment_supplier(equipment_supplier_id) ON DELETE SET NULL,
  kit_type kit_type_enum NOT NULL,
  colors TEXT,
  sponsor TEXT,
  image_url TEXT,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (team_season_id, kit_type)
);

-- Shot events
CREATE TYPE IF NOT EXISTS shot_body_part_enum AS ENUM ('left_foot','right_foot','head','other');
CREATE TYPE IF NOT EXISTS shot_situation_enum AS ENUM ('open_play','set_piece','penalty','counter','fast_break');
CREATE TABLE IF NOT EXISTS shot_event (
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
  provider provider_enum,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_shot_x_range CHECK (x_percent IS NULL OR (x_percent>=0 AND x_percent<=100)),
  CONSTRAINT chk_shot_y_range CHECK (y_percent IS NULL OR (y_percent>=0 AND y_percent<=100))
);
CREATE INDEX IF NOT EXISTS idx_shot_event_match ON shot_event(match_id);

-- Referee season stats
CREATE TABLE IF NOT EXISTS referee_season_stats (
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

-- Migration 0006_agents_market_values_national_teams.sql
-- Agent table intentionally not redefined here because base schema already defines it.

-- player_agent_assignment
CREATE TABLE IF NOT EXISTS player_agent_assignment (
  player_agent_assignment_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  agent_id INT NOT NULL REFERENCES agent(agent_id) ON DELETE CASCADE,
  from_date DATE,
  to_date DATE,
  source_url TEXT,
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, agent_id, COALESCE(from_date, DATE '0001-01-01'))
);

-- player_market_value (time series)
CREATE TABLE IF NOT EXISTS player_market_value (
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

-- team: national team flag
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='team' AND column_name='is_national_team'
  ) THEN
    ALTER TABLE team ADD COLUMN is_national_team BOOLEAN DEFAULT FALSE;
  END IF;
END $$;

-- player_national_team_summary
CREATE TABLE IF NOT EXISTS player_national_team_summary (
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
