import json

from src.common.playwright_utils import extract_from_ld_json, normalize_game_node


def test_normalize_game_node_basic():
    node = {
        "id": "game-123",
        "home": {"name": "Team A", "id": "A"},
        "away": {"name": "Team B", "id": "B"},
        "score": {"home": 2, "away": 1},
    }
    res = normalize_game_node(node)
    assert res["id"] == "game-123"
    assert res["home"] == "Team A"
    assert res["away"] == "Team B"
    assert res["home_score"] == 2
    assert res["away_score"] == 1


def test_normalize_game_node_participants_list():
    node = {
        "participants": [
            {"name": "Team X", "teamId": "X", "side": "home"},
            {"name": "Team Y", "teamId": "Y", "side": "away"},
        ],
        "scores": {"ft": {"home": 0, "away": 0}},
    }
    res = normalize_game_node(node)
    assert res["home"] == "Team X"
    assert res["away"] == "Team Y"
    assert res["home_score"] == 0
    assert res["away_score"] == 0


def test_extract_from_ld_json_sportsevent():
    ld = [
        json.dumps(
            {
                "@type": "SportsEvent",
                "homeTeam": {"name": "Home FC", "@id": "H1"},
                "awayTeam": {"name": "Away FC", "@id": "A1"},
                "aggregateScore": {"home": 3, "away": 2},
                "superEvent": {"name": "Cup", "identifier": "CUP"},
                "identifier": "EVT1",
            }
        )
    ]
    res = extract_from_ld_json(ld)
    assert res["id"] == "EVT1"
    assert res["home"] == "Home FC"
    assert res["away"] == "Away FC"
    assert res["home_score"] == 3
    assert res["away_score"] == 2
    assert res["competition"] == "Cup"
    assert res["competition_id"] == "CUP"
