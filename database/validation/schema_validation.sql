-- Schema Validation and Example Queries
-- This file demonstrates the enhanced schema capabilities

-- Test 1: Multi-sport support
-- Show all sports and their associated competitions
SELECT 
    s.sport_type as sport_name,
    COUNT(c.competition_id) as competition_count,
    COUNT(DISTINCT cl.club_id) as club_count
FROM sport s
LEFT JOIN competition c ON s.sport_id = c.sport_id
LEFT JOIN club cl ON s.sport_id = cl.sport_id
GROUP BY s.sport_id, s.sport_type;

-- Test 2: JSONB usage for flexible player statistics
-- Example basketball player stats query
SELECT 
    p.first_name || ' ' || p.last_name as player_name,
    pms.basketball_stats->>'points' as points,
    pms.basketball_stats->>'rebounds' as rebounds,
    pms.basketball_stats->>'assists' as assists,
    pms.basketball_stats->>'field_goals_made' as field_goals_made,
    pms.basketball_stats->>'three_pointers_made' as three_pointers_made
FROM player_match_stats pms
JOIN player p ON pms.player_id = p.player_id
WHERE pms.basketball_stats IS NOT NULL;

-- Test 5: Medical and injury tracking
-- Player injury analysis with treatment plans
SELECT 
    p.first_name || ' ' || p.last_name as player_name,
    pi.injury_type,
    pi.body_part,
    pi.severity,
    pi.injury_date,
    pi.expected_return_date
    --, ms.first_name || ' ' || ms.last_name as medical_staff -- Uncomment if staff_member/medical_staff implemented
FROM player_injury pi
JOIN player p ON pi.player_id = p.player_id;

-- Test 6: Multi-venue support with sport-specific dimensions
SELECT 
    vnh.venue_name,
    v.supported_sports,
    v.field_dimensions->>'football' as football_dimensions,
    v.field_dimensions->>'basketball' as basketball_dimensions,
    v.capacity_national as total_capacity
FROM venue v
JOIN venue_name_history vnh ON v.venue_id = vnh.venue_id
WHERE vnh.is_current = true;

-- Test 7: Sport-specific betting markets
SELECT 
    s.sport_type as sport_name,
    bm.market_name as market_name,
    COUNT(bo.outcome_id) as outcome_count
FROM sport s
JOIN betting_market bm ON s.sport_id = bm.sport_id
LEFT JOIN betting_outcome bo ON bm.market_id = bo.market_id
GROUP BY s.sport_id, s.sport_type, bm.market_id, bm.market_name
ORDER BY s.sport_type, bm.market_name;

-- Test: Vereine mit den meisten Trophäen
SELECT 
    c.name_official AS club_name,
    COUNT(tw.trophy_winner_id) AS trophies_won
FROM club c
JOIN team t ON t.club_id = c.club_id
JOIN trophy_winner tw ON tw.team_id = t.team_id
GROUP BY c.club_id, c.name_official
ORDER BY trophies_won DESC, club_name;

-- Test: Aktive Spieler pro Team und Sportart
SELECT
    s.sport_type,
    t.team_id,
    t.team_gender,
    t.team_maturity,
    COUNT(p.player_id) AS active_players
FROM team t
JOIN club c ON t.club_id = c.club_id
JOIN sport s ON c.sport_id = s.sport_id
JOIN squad_member sm ON sm.team_season_id IS NOT NULL -- Annahme: aktuelle Saison
JOIN player p ON sm.player_id = p.player_id
WHERE p.is_active = TRUE
GROUP BY s.sport_type, t.team_id, t.team_gender, t.team_maturity
ORDER BY s.sport_type, t.team_id;

-- Test: Clubs und ihre aktuellen Venues
SELECT
    c.name_official AS club_name,
    vnh.venue_name AS current_venue
FROM club c
JOIN club_venue_tenancy cvt ON c.club_id = cvt.club_id
JOIN venue v ON cvt.venue_id = v.venue_id
JOIN venue_name_history vnh ON v.venue_id = vnh.venue_id
WHERE vnh.is_current = TRUE AND (cvt.end_date IS NULL OR cvt.end_date > NOW());

-- Test: Teams mit ihren aktuellen Trainern
SELECT
    t.team_id,
    t.team_gender,
    t.team_maturity,
    ts.season_id,
    c.first_name || ' ' || c.last_name AS coach_name
FROM team_season ts
JOIN team t ON ts.team_id = t.team_id
LEFT JOIN coach c ON ts.coach_id = c.coach_id
WHERE ts.season_id = (SELECT MAX(season_id) FROM team_season WHERE team_id = t.team_id);

-- Test: Top-Scorer einer Competition/Saison
SELECT
    p.first_name || ' ' || p.last_name AS player_name,
    SUM(pms.goals) AS total_goals,
    t.team_id,
    s.season_id,
    c.competition_id
FROM player_match_stats pms
JOIN player p ON pms.player_id = p.player_id
JOIN match m ON pms.match_id = m.match_id
JOIN team t ON pms.team_id = t.team_id
JOIN season s ON m.season_id = s.season_id
JOIN competition c ON m.competition_id = c.competition_id
GROUP BY p.player_id, t.team_id, s.season_id, c.competition_id
ORDER BY total_goals DESC, player_name
LIMIT 10;

-- Test: Verletzte Spieler und deren Rückkehrdatum
SELECT
    p.first_name || ' ' || p.last_name AS player_name,
    pi.injury_type,
    pi.body_part,
    pi.severity,
    pi.injury_date,
    pi.expected_return_date
FROM player_injury pi
JOIN player p ON pi.player_id = p.player_id
WHERE pi.expected_return_date IS NOT NULL AND (pi.actual_return_date IS NULL OR pi.actual_return_date > NOW());