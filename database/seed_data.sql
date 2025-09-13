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

-- Sample cities
INSERT INTO city (city_name, country_id, state_region, city_population)
SELECT 'Los Angeles', c.country_id, 'California', NULL FROM country c WHERE c.iso2 = 'US'
UNION ALL
SELECT 'New York', c.country_id, 'New York', NULL FROM country c WHERE c.iso2 = 'US'
UNION ALL
SELECT 'Munich', c.country_id, 'Bavaria', NULL FROM country c WHERE c.iso2 = 'DE'
UNION ALL
SELECT 'Madrid', c.country_id, 'Madrid', NULL FROM country c WHERE c.iso2 = 'ES';

-- Sample associations
INSERT INTO association (association_name, sport_id, is_national, parent_association_id)
SELECT 'NBA', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'basketball'
UNION ALL
SELECT 'NFL', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'american_football'
UNION ALL
SELECT 'La Liga', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'football';

-- Sample clubs
INSERT INTO club (sport_id, name_official, founding_year, colors, country_id, address_city_id, market_value, market_value_currency, main_sponsor, kit_supplier, social_media)
SELECT 
  s.sport_id, 
  'Los Angeles Lakers',
  1947, 
  '{"primary": "#552583", "secondary": "#FDB927"}',
  c.country_id,
  ci.city_id,
  5500000000,
  'USD',
  'Crypto.com',
  'Nike',
  '{"twitter": "@Lakers", "instagram": "@lakers", "youtube": "Lakers"}'
FROM sport s, country c, city ci 
WHERE s.sport_type = 'basketball' AND c.iso2 = 'US' AND ci.city_name = 'Los Angeles'
UNION ALL
SELECT 
  s.sport_id,
  'Real Madrid Club de Fútbol',
  1902,
  '{"primary": "#FFFFFF", "secondary": "#00529F"}',
  c.country_id,
  ci.city_id,
  1200000000,
  'EUR',
  'Emirates',
  'Adidas',
  '{"twitter": "@realmadrid", "instagram": "@realmadrid", "youtube": "RealMadrid"}'
FROM sport s, country c, city ci
WHERE s.sport_type = 'football' AND c.iso2 = 'ES' AND ci.city_name = 'Madrid';

-- Sample venues with multi-sport support
INSERT INTO venue (venue_name, address_city_id, surface, supported_sports, field_dimensions, capacity_national)
SELECT 
  'Crypto.com Arena',
  ci.city_id,
  'indoor',
  '["basketball"]',
  '{"basketball": {"length": 28.7, "width": 15.2}}',
  18997
FROM city ci WHERE ci.city_name = 'Los Angeles'
UNION ALL
SELECT
  'Santiago Bernabéu',
  ci.city_id,
  'grass',
  '["football"]',
  '{"football": {"length": 105, "width": 68}}',
  81044
FROM city ci WHERE ci.city_name = 'Madrid';

-- Sample teams
INSERT INTO team (club_id, team_type, team_maturity, team_gender, market_value, market_value_currency, social_media)
SELECT 
  c.club_id,
  'club',
  'professional',
  'men',
  c.market_value,
  c.market_value_currency,
  c.social_media
FROM club c;

-- Sample players with sport-specific attributes
INSERT INTO player (first_name, last_name, date_of_birth, height_cm, weight_kg, strong_foot, is_active, career_stats, current_market_value, current_market_value_currency, social_media)
SELECT 
  'LeBron',
  'James',
  '1984-12-30',
  206,
  113,
  NULL,
  TRUE,
  '{"career_points": 38652, "career_rebounds": 10210, "career_assists": 10420}',
  44000000,
  'USD',
  '{"twitter": "@KingJames", "instagram": "@kingjames"}'
UNION ALL
SELECT
  'Karim',
  'Benzema',
  '1987-12-19',
  185,
  81,
  NULL,
  FALSE,
  '{"career_goals": 354, "career_assists": 165, "career_appearances": 648}',
  25000000,
  'EUR',
  '{"twitter": "@Benzema", "instagram": "@karimbenzema"}';

-- Sample competitions
INSERT INTO competition (sport_id, competition_name, association_id, since_year, is_cup, competition_format, prize_money)
SELECT 
  s.sport_id,
  'NBA Regular Season',
  a.association_id,
  1946,
  FALSE,
  '{"type": "league", "teams": 30, "games_per_team": 82}',
  '{"total_salary_cap": 136000000, "currency": "USD"}'
FROM sport s
JOIN association a ON s.sport_id = a.sport_id
WHERE s.sport_type = 'basketball' AND a.association_name = 'NBA'
UNION ALL
SELECT
  s.sport_id,
  'La Liga',
  a.association_id,
  1929,
  FALSE,
  '{"type": "league", "teams": 20, "games_per_team": 38}',
  '{"total_prize_pool": 140000000, "currency": "EUR"}'
FROM sport s
JOIN association a ON s.sport_id = a.sport_id
WHERE s.sport_type = 'football' AND a.association_name = 'La Liga';

-- Sample seasons
INSERT INTO season (competition_id, season_type, label, start_date, end_date, is_active, number_of_teams, number_of_games, rules)
SELECT 
  co.competition_id,
  'cross_year',
  '2023-24',
  '2023-10-17',
  '2024-04-14',
  FALSE,
  30,
  1230,
  '{"playoff_format": "best_of_7", "play_in_tournament": true}'
FROM competition co WHERE co.competition_name = 'NBA Regular Season'
UNION ALL
SELECT
  co.competition_id,
  'cross_year',
  '2023-24',
  '2023-08-18',
  '2024-05-26',
  FALSE,
  20,
  380,
  '{"var_usage": true, "max_subs": 5, "extra_time": 30}'
FROM competition co WHERE co.competition_name = 'La Liga';

-- Sample club name history
INSERT INTO club_name_history (club_id, name_official, name_short, nickname, valid_from, valid_to)
SELECT c.club_id, 'Los Angeles Lakers', 'Lakers', 'LAL', '1947-01-01', NULL
FROM club c WHERE c.name_official = 'Los Angeles Lakers'
UNION ALL
SELECT c.club_id, 'Real Madrid Club de Fútbol', 'Real Madrid', 'Los Blancos', '1902-03-06', NULL
FROM club c WHERE c.name_official = 'Real Madrid Club de Fútbol';

-- Sample venue name history
INSERT INTO venue_name_history (venue_id, venue_name, valid_from, valid_to)
SELECT v.venue_id, 'Crypto.com Arena', '2021-12-01', NULL
FROM venue v 
JOIN city ci ON v.address_city_id = ci.city_id
WHERE ci.city_name = 'Los Angeles'
UNION ALL
SELECT v.venue_id, 'Santiago Bernabéu', '1947-12-14', NULL
FROM venue v
JOIN city ci ON v.address_city_id = ci.city_id
WHERE ci.city_name = 'Madrid';
