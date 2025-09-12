-- Sample Data for Schema Demonstration
-- This script provides example data to demonstrate the enhanced schema

-- Sample countries (already partially seeded in main schema)
INSERT INTO country (iso2, iso3, name) VALUES
  ('US', 'USA', 'United States'),
  ('CA', 'CAN', 'Canada'),
  ('UK', 'GBR', 'United Kingdom'),
  ('DE', 'DEU', 'Germany'),
  ('ES', 'ESP', 'Spain')
ON CONFLICT (iso2) DO NOTHING;

-- Sample cities
INSERT INTO city (name, country_id, state_region) 
SELECT 'Los Angeles', c.country_id, 'California' FROM country c WHERE c.iso2 = 'US'
UNION ALL
SELECT 'New York', c.country_id, 'New York' FROM country c WHERE c.iso2 = 'US'
UNION ALL
SELECT 'Munich', c.country_id, 'Bavaria' FROM country c WHERE c.iso2 = 'DE'
UNION ALL
SELECT 'Madrid', c.country_id, 'Madrid' FROM country c WHERE c.iso2 = 'ES';

-- Sample associations
INSERT INTO association (association_name, sport_id, is_national, parent_association_id)
SELECT 'NBA', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'basketball'
UNION ALL
SELECT 'NFL', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'american_football'
UNION ALL
SELECT 'La Liga', s.sport_id, TRUE, NULL FROM sport s WHERE s.sport_type = 'football';

-- Sample clubs
INSERT INTO club (sport_id, code, founding_year, colors, country_id, city_id, market_value, market_value_currency, main_sponsor, kit_supplier, social_media)
SELECT 
  s.sport_id, 
  'LAL', 
  1947, 
  'Purple and Gold',
  c.country_id,
  ci.city_id,
  5500000000,
  'USD',
  'Crypto.com',
  'Nike',
  '{"twitter": "@Lakers", "instagram": "@lakers", "youtube": "Lakers"}'
FROM sport s, country c, city ci 
WHERE s.sport_type = 'basketball' AND c.iso2 = 'US' AND ci.name = 'Los Angeles'

UNION ALL

SELECT 
  s.sport_id,
  'RMA',
  1902,
  'White',
  c.country_id,
  ci.city_id,
  1200000000,
  'EUR',
  'Emirates',
  'Adidas',
  '{"twitter": "@realmadrid", "instagram": "@realmadrid", "youtube": "RealMadrid"}'
FROM sport s, country c, city ci
WHERE s.sport_type = 'football' AND c.iso2 = 'ES' AND ci.name = 'Madrid';

-- Sample venues with multi-sport support
INSERT INTO venue (city_id, surface, supported_sports, field_dimensions, capacity_national, has_var, has_player_tracking, facilities, indoor, climate_controlled)
SELECT 
  ci.city_id,
  'hardwood',
  '["basketball"]',
  '{"basketball": {"length": 28.7, "width": 15.2}}',
  18997,
  FALSE,
  TRUE,
  '{"parking_spaces": 3100, "restaurants": 8, "shops": 4}',
  TRUE,
  TRUE
FROM city ci WHERE ci.name = 'Los Angeles'

UNION ALL

SELECT
  ci.city_id,
  'grass',
  '["football"]',
  '{"football": {"length": 105, "width": 68}}',
  81044,
  TRUE,
  TRUE,
  '{"parking_spaces": 5000, "restaurants": 12, "shops": 6}',
  FALSE,
  FALSE
FROM city ci WHERE ci.name = 'Madrid';

-- Add venue names
INSERT INTO venue_name_history (venue_id, venue_name, valid_from, valid_to)
SELECT v.venue_id, 'Crypto.com Arena', '2021-12-01', NULL
FROM venue v 
JOIN city ci ON v.city_id = ci.city_id
WHERE ci.name = 'Los Angeles'

UNION ALL

SELECT v.venue_id, 'Santiago Bernabéu', '1947-12-14', NULL
FROM venue v
JOIN city ci ON v.city_id = ci.city_id
WHERE ci.name = 'Madrid';

-- Sample teams
INSERT INTO team (sport_id, club_id, team_type, market_value, market_value_currency, is_senior, is_male, social_media)
SELECT 
  c.sport_id,
  c.club_id,
  'club',
  c.market_value,
  c.market_value_currency,
  TRUE,
  TRUE,
  c.social_media
FROM club c;

-- Add team names through club_name_history
INSERT INTO club_name_history (club_id, name_official, name_short, nickname, valid_from, valid_to)
SELECT c.club_id, 'Los Angeles Lakers', 'Lakers', 'LAL', '1947-01-01', NULL
FROM club c WHERE c.code = 'LAL'

UNION ALL

SELECT c.club_id, 'Real Madrid Club de Fútbol', 'Real Madrid', 'Los Blancos', '1902-03-06', NULL
FROM club c WHERE c.code = 'RMA';

-- Sample players with sport-specific attributes
INSERT INTO player (sport_id, first_name, last_name, birthdate, height_cm, weight_kg, sport_attributes, is_active, career_stats, current_market_value, current_market_value_currency, social_media)
SELECT 
  s.sport_id,
  'LeBron',
  'James',
  '1984-12-30',
  206,
  113,
  '{"position": "SF", "vertical_leap": 44, "wingspan": 213}',
  TRUE,
  '{"career_points": 38652, "career_rebounds": 10210, "career_assists": 10420}',
  44000000,
  'USD',
  '{"twitter": "@KingJames", "instagram": "@kingjames"}'
FROM sport s WHERE s.sport_type = 'basketball'

UNION ALL

SELECT
  s.sport_id,
  'Karim',
  'Benzema',
  '1987-12-19',
  185,
  81,
  '{"preferred_position": "ST", "weak_foot": 4, "skill_moves": 4}',
  FALSE,
  '{"career_goals": 354, "career_assists": 165, "career_appearances": 648}',
  25000000,
  'EUR',
  '{"twitter": "@Benzema", "instagram": "@karimbenzema"}'
FROM sport s WHERE s.sport_type = 'football';

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

-- This demonstrates the key improvements:
-- 1. Multi-sport support through sport_id references
-- 2. JSONB usage for flexible data (sport_attributes, social_media, etc.)
-- 3. Enhanced venue support with multi-sport capabilities
-- 4. Comprehensive competition and season rules
-- 5. Sport-specific player attributes and career statistics