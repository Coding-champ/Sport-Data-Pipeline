-- Sportdatenbank Schema für Fußball, Basketball und Football
-- PostgreSQL Datenbank Design

-- Grundlegende Referenztabellen
CREATE TABLE sports (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    code VARCHAR(32) NOT NULL UNIQUE, -- 'football', 'basketball', 'american_football'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE countries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(3) NOT NULL UNIQUE, -- ISO 3166-1 Alpha-3
    flag_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE leagues (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    country_id INTEGER REFERENCES countries(id),
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(50),
    logo_url TEXT,
    tier INTEGER DEFAULT 1, -- 1 = Top-Liga, 2 = Zweite Liga, etc.
    season_format VARCHAR(50), -- 'league', 'playoffs', 'tournament'
    is_active BOOLEAN DEFAULT true,
    external_ids JSONB, -- API IDs verschiedener Anbieter
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams/Vereine
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(50),
    city VARCHAR(100),
    country_id INTEGER REFERENCES countries(id),
    founded_year INTEGER,
    logo_url TEXT,
    colors JSONB, -- {"primary": "#FF0000", "secondary": "#FFFFFF"}
    website TEXT,
    is_active BOOLEAN DEFAULT true,
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stadien/Arenen
CREATE TABLE venues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    country_id INTEGER REFERENCES countries(id),
    capacity INTEGER,
    surface VARCHAR(50), -- 'grass', 'artificial', 'hardwood', etc.
    indoor BOOLEAN DEFAULT false,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    image_url TEXT,
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spieler
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    birth_date DATE,
    birth_place VARCHAR(100),
    nationality VARCHAR(3) REFERENCES countries(code),
    height_cm INTEGER,
    weight_kg INTEGER,
    preferred_foot VARCHAR(10), -- 'left', 'right', 'both'
    photo_url TEXT,
    is_active BOOLEAN DEFAULT true,
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Positionen (sportspezifisch)
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    name VARCHAR(50) NOT NULL,
    short_name VARCHAR(10),
    category VARCHAR(50), -- 'defense', 'midfield', 'attack', 'guard', 'forward', 'center'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team-Liga Zugehörigkeit (historisch)
CREATE TABLE team_league_memberships (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id),
    league_id INTEGER REFERENCES leagues(id),
    season VARCHAR(20), -- '2023-24', '2024'
    points INTEGER DEFAULT 0,
    played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0, -- NULL für Basketball/Football
    losses INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0, -- Points für Basketball/Football
    goals_against INTEGER DEFAULT 0,
    position INTEGER, -- Tabellenplatz
    is_current BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, league_id, season)
);

-- Spieler-Team Zugehörigkeit (Verträge/Transfers)
CREATE TABLE player_contracts (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    team_id INTEGER REFERENCES teams(id),
    position_id INTEGER REFERENCES positions(id),
    jersey_number INTEGER,
    contract_start DATE,
    contract_end DATE,
    salary_amount DECIMAL(15,2),
    salary_currency VARCHAR(3),
    loan BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transfers
CREATE TABLE transfers (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    from_team_id INTEGER REFERENCES teams(id),
    to_team_id INTEGER REFERENCES teams(id),
    transfer_date DATE,
    transfer_fee DECIMAL(15,2),
    transfer_fee_currency VARCHAR(3),
    transfer_type VARCHAR(20), -- 'permanent', 'loan', 'free', 'end_of_contract'
    season VARCHAR(20),
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Matches/Spiele
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    league_id INTEGER REFERENCES leagues(id),
    season VARCHAR(20),
    matchday INTEGER,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    venue_id INTEGER REFERENCES venues(id),
    match_date TIMESTAMP,
    status VARCHAR(20), -- 'scheduled', 'live', 'finished', 'postponed', 'cancelled'
    home_score INTEGER,
    away_score INTEGER,
    home_score_ht INTEGER, -- Halbzeit
    away_score_ht INTEGER,
    home_score_periods JSONB, -- Für Basketball/Football Quarters/Periods
    away_score_periods JSONB,
    attendance INTEGER,
    referee VARCHAR(200),
    weather JSONB, -- {"temperature": 15, "condition": "sunny", "wind": "light"}
    external_ids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spieler-Statistiken pro Match
CREATE TABLE match_player_stats (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    player_id INTEGER REFERENCES players(id),
    team_id INTEGER REFERENCES teams(id),
    position_id INTEGER REFERENCES positions(id),
    jersey_number INTEGER,
    starter BOOLEAN DEFAULT false,
    minutes_played INTEGER,
    -- Fußball-spezifische Stats
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    shots_on_target INTEGER DEFAULT 0,
    passes INTEGER DEFAULT 0,
    passes_successful INTEGER DEFAULT 0,
    tackles INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    fouls INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    -- Basketball-spezifische Stats  
    points INTEGER DEFAULT 0,
    rebounds INTEGER DEFAULT 0,
    steals INTEGER DEFAULT 0,
    blocks INTEGER DEFAULT 0,
    turnovers INTEGER DEFAULT 0,
    -- Zusätzliche flexible Stats als JSON
    additional_stats JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events während des Spiels
CREATE TABLE match_events (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    player_id INTEGER REFERENCES players(id),
    team_id INTEGER REFERENCES teams(id),
    minute INTEGER,
    second INTEGER DEFAULT 0,
    event_type VARCHAR(50), -- 'goal', 'card', 'substitution', 'timeout', etc.
    event_subtype VARCHAR(50), -- 'penalty', 'own_goal', 'yellow_card', etc.
    description TEXT,
    coordinates JSONB, -- Feldkoordinaten wenn verfügbar
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quoten
CREATE TABLE bookmakers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    website TEXT,
    country_id INTEGER REFERENCES countries(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE odds (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    bookmaker_id INTEGER REFERENCES bookmakers(id),
    market_type VARCHAR(50), -- '1x2', 'over_under', 'handicap', 'moneyline'
    selection VARCHAR(50), -- 'home', 'draw', 'away', 'over_2.5', etc.
    odds_decimal DECIMAL(8,4),
    odds_fractional VARCHAR(20),
    odds_american INTEGER,
    timestamp TIMESTAMP,
    is_latest BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saisonstatistiken (aggregiert)
CREATE TABLE season_player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    team_id INTEGER REFERENCES teams(id),
    league_id INTEGER REFERENCES leagues(id),
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
    UNIQUE(player_id, team_id, league_id, season)
);

-- Tabelle für die manuelle Überprüfung von unsicheren Mappings
CREATE TABLE mapping_review_queue (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'team', 'player', etc.
    source_name VARCHAR(100) NOT NULL,
    new_entity_data JSONB NOT NULL, -- Die kompletten Daten der neuen Quelle
    potential_match_id INTEGER, -- Die ID des gefundenen, möglichen Treffers
    confidence_score REAL, -- Der Score, der die Überprüfung ausgelöst hat
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'resolved', 'discarded'
    notes TEXT, -- Platz für Kommentare des Bearbeiters
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Indizes für Performance
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id);
CREATE INDEX idx_matches_league_season ON matches(league_id, season);
CREATE INDEX idx_players_name ON players(last_name, first_name);
CREATE INDEX idx_transfers_player ON transfers(player_id);
CREATE INDEX idx_transfers_date ON transfers(transfer_date);
CREATE INDEX idx_odds_match ON odds(match_id);
CREATE INDEX idx_odds_bookmaker ON odds(bookmaker_id);
CREATE INDEX idx_external_ids ON teams USING gin(external_ids);
CREATE INDEX idx_player_contracts_active ON player_contracts(player_id) WHERE is_active = true;
CREATE INDEX idx_mapping_review_queue_pending ON mapping_review_queue(status) WHERE status = 'pending';

-- Trigger für updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_players_updated_at BEFORE UPDATE ON players FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contracts_updated_at BEFORE UPDATE ON player_contracts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Beispieldaten einfügen
INSERT INTO sports (name, code) VALUES 
('Fußball', 'football'),
('Basketball', 'basketball'),
('American Football', 'american_football');

INSERT INTO countries (name, code) VALUES 
('Deutschland', 'DEU'),
('England', 'ENG'),
('Spanien', 'ESP'),
('USA', 'USA');

INSERT INTO positions (sport_id, name, short_name, category) 
SELECT s.id, pos.name, pos.short_name, pos.category
FROM sports s
CROSS JOIN (VALUES 
    ('football', 'Torwart', 'TW', 'goalkeeper'),
    ('football', 'Innenverteidiger', 'IV', 'defense'),
    ('football', 'Mittelfeld', 'MF', 'midfield'),
    ('football', 'Stürmer', 'ST', 'attack'),
    ('basketball', 'Point Guard', 'PG', 'guard'),
    ('basketball', 'Center', 'C', 'center'),
    ('american_football', 'Quarterback', 'QB', 'offense')
) AS pos(sport_code, name, short_name, category)
WHERE s.code = pos.sport_code;