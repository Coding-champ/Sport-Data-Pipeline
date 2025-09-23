import pytest
from src.common.scraper_utils import (
    parse_score_text,
    classify_match_status,
    is_incomplete_fixture,
    looks_like_fixture_json_url,
    extract_game_anchor_records,
    unify_fixture_records,
)


def test_parse_score_text_basic():
    assert parse_score_text("2-1") == (2,1)
    assert parse_score_text(" 3 : 0 ") == (3,0)
    assert parse_score_text("foo") == (None, None)


def test_classify_match_status():
    assert classify_match_status("12'", []) == "live"
    assert classify_match_status("FT", []) == "finished"
    assert classify_match_status("", []) == "scheduled"
    assert classify_match_status("45'", ["event__match--live"]) == "live"


def test_is_incomplete_fixture():
    assert is_incomplete_fixture({}) is True
    assert is_incomplete_fixture({"home":"A","away":"B"}) is True  # missing scores
    assert is_incomplete_fixture({"home":"A","away":"B","home_score":1}) is True
    assert is_incomplete_fixture({"home":"A","away":"B","home_score":1,"away_score":2}) is False


def test_looks_like_fixture_json_url():
    assert looks_like_fixture_json_url("https://api/x/game/123")
    assert looks_like_fixture_json_url("/fixtures/list")
    assert not looks_like_fixture_json_url("/static/css/app.css")


def test_extract_game_anchor_records():
    anchors = [
        {"url":"/game/abc?x=1"},
        {"id":"/match/xyz"},
        {"foo":"bar"},
    ]
    out = extract_game_anchor_records(anchors)
    assert len(out) == 2
    assert out[0]["id"] == "/game/abc"


def test_unify_fixture_records():
    raw = [
        {"id":"/game/1","home":"A","away":"B","home_score":2,"away_score":1},
        {"fixture_id":"2","home_team_name":"C","away_team_name":"D","score":"0-0"},
    ]
    unified = unify_fixture_records(raw)
    assert len(unified) == 2
    ids = {u["fixture_id"] for u in unified}
    assert ids == {"/game/1","2"}
    sc_map = {u["fixture_id"]: u["score"] for u in unified}
    assert sc_map["/game/1"] == "2-1"
    assert sc_map["2"] == "0-0"
