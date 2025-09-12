-- Schema Validation and Example Queries
-- This file demonstrates the enhanced schema capabilities

-- Test 1: Multi-sport support
-- Show all sports and their associated competitions
SELECT 
    s.name as sport_name,
    COUNT(c.competition_id) as competition_count,
    COUNT(DISTINCT cl.club_id) as club_count
FROM sport s
LEFT JOIN competition c ON s.sport_id = c.sport_id
LEFT JOIN club cl ON s.sport_id = cl.sport_id
GROUP BY s.sport_id, s.name;

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
JOIN sport s ON p.sport_id = s.sport_id
WHERE s.sport_type = 'basketball'
    AND pms.basketball_stats IS NOT NULL;

-- Test 3: Advanced team analytics with JSONB
-- Football team tactical analysis
SELECT 
    t.name as team_name,
    tms.tactical_analysis->>'pressing_intensity' as pressing_intensity,
    tms.tactical_analysis->>'defensive_line' as defensive_line,
    tms.advanced_metrics->>'expected_possession' as expected_possession,
    tms.formation
FROM team_match_stats tms
JOIN team t ON tms.team_id = t.team_id
JOIN sport s ON t.sport_id = s.sport_id
WHERE s.sport_type = 'football'
    AND tms.tactical_analysis IS NOT NULL;

-- Test 4: Technology integration tracking
-- VAR decisions in matches
SELECT 
    m.match_id,
    m.match_date_time,
    mtd.event_minute,
    mtd.decision_result->>'var_decision' as var_decision,
    mtd.decision_result->>'review_duration_seconds' as review_duration,
    mtd.confidence_level
FROM match_technology_data mtd
JOIN match m ON mtd.match_id = m.match_id
WHERE mtd.technology_type = 'var';

-- Test 5: Medical and injury tracking
-- Player injury analysis with treatment plans
SELECT 
    p.first_name || ' ' || p.last_name as player_name,
    pi.injury_type,
    pi.body_part,
    pi.severity,
    pi.injury_date,
    pi.expected_return_date,
    pi.treatment_plan->>'rehabilitation_weeks' as rehab_weeks,
    ms.first_name || ' ' || ms.last_name as medical_staff
FROM player_injury pi
JOIN player p ON pi.player_id = p.player_id
LEFT JOIN medical_staff med ON pi.medical_staff_id = med.medical_staff_id
LEFT JOIN staff_member ms ON med.staff_id = ms.staff_id;

-- Test 6: Multi-venue support with sport-specific dimensions
SELECT 
    v.venue_name_history.venue_name,
    v.supported_sports,
    v.field_dimensions->>'football' as football_dimensions,
    v.field_dimensions->>'basketball' as basketball_dimensions,
    v.capacity_details->>'total' as total_capacity,
    v.has_var,
    v.has_player_tracking
FROM venue v
JOIN venue_name_history vnh ON v.venue_id = vnh.venue_id
WHERE vnh.is_current = true;

-- Test 7: Sport-specific betting markets
SELECT 
    s.name as sport_name,
    bm.name as market_name,
    COUNT(bo.outcome_id) as outcome_count
FROM sport s
JOIN betting_market bm ON s.sport_id = bm.sport_id
LEFT JOIN betting_outcome bo ON bm.market_id = bo.market_id
GROUP BY s.sport_id, s.name, bm.market_id, bm.name
ORDER BY s.name, bm.name;

-- Test 8: Player tracking and performance data
SELECT 
    p.first_name || ' ' || p.last_name as player_name,
    AVG(ptd.distance_covered) as avg_distance_covered,
    MAX(ptd.top_speed) as max_speed,
    AVG(CAST(ptd.performance_metrics->>'acceleration' AS NUMERIC)) as avg_acceleration
FROM player_tracking_data ptd
JOIN player p ON ptd.player_id = p.player_id
GROUP BY p.player_id, p.first_name, p.last_name
HAVING COUNT(*) >= 5; -- Players with at least 5 tracking records

-- Test 9: Youth development tracking
SELECT 
    senior_team.name as senior_team,
    youth_team.name as youth_team,
    youth_team.academy_level,
    COUNT(DISTINCT p.player_id) as player_count
FROM team senior_team
JOIN team youth_team ON senior_team.team_id = youth_team.parent_team_id
LEFT JOIN contract c ON youth_team.team_id = c.team_id
LEFT JOIN player p ON c.player_id = p.player_id
WHERE youth_team.team_type = 'youth'
GROUP BY senior_team.team_id, senior_team.name, youth_team.team_id, youth_team.name, youth_team.academy_level;

-- Test 10: Live betting odds tracking
SELECT 
    m.match_date_time,
    ht.name as home_team,
    at.name as away_team,
    mo.match_minute,
    mo.current_score,
    bm.name as market_name,
    bo.name as outcome_name,
    mo.price as odds
FROM match_odd mo
JOIN match m ON mo.match_id = m.match_id
JOIN team ht ON m.home_team_id = ht.team_id
JOIN team at ON m.away_team_id = at.team_id
JOIN betting_market bm ON mo.market_id = bm.market_id
JOIN betting_outcome bo ON mo.outcome_id = bo.outcome_id
WHERE mo.price_type = 'live'
    AND mo.match_minute IS NOT NULL
ORDER BY m.match_date_time, mo.match_minute;