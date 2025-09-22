import pytest

from src.common.term_mapper import TermMapper, map_position


@pytest.mark.parametrize(
    "term,expected",
    [
        # Goalkeeper
        ("Torwart", "GK"), ("Torhüter", "GK"), ("Keeper", "GK"), ("Goalkeeper", "GK"), ("TW", "GK"), ("gk", "GK"),
        # Defender
        ("Defender", "DF"), ("Verteidiger", "DF"), ("Abwehr", "DF"), ("CB", "DF"), ("IV", "DF"), ("LV", "DF"), ("RV", "DF"), ("Full-Back", "DF"), ("Wing Back", "DF"),
        # Midfielder
        ("Mittelfeld", "MF"), ("Midfielder", "MF"), ("DM", "MF"), ("OM", "MF"), ("ZM", "MF"), ("AM", "MF"), ("CM", "MF"), ("LM", "MF"), ("RM", "MF"),
        # Forward
        ("Stürmer", "FW"), ("Stuermer", "FW"), ("Angriff", "FW"), ("Angreifer", "FW"), ("Striker", "FW"), ("FW", "FW"), ("MS", "FW"), ("ST", "FW"), ("CF", "FW"),
    ],
)
def test_default_position_mapper_synonyms(term, expected):
    mapper = TermMapper.default_position_mapper()
    assert mapper.lookup(term) == expected


def test_map_position_convenience():
    assert map_position("Torwart") == "GK"
    assert map_position("Verteidiger") == "DF"
    assert map_position("Mittelfeld") == "MF"
    assert map_position("Stürmer") == "FW"
    assert map_position("Goalkeeper", return_long=True) == "Goalkeeper"


def test_unknown_returns_none():
    assert map_position("Physiotherapeut") is None
    mapper = TermMapper.default_position_mapper()
    assert mapper.lookup("irgendwas_unbekanntes") is None


def test_runtime_registration():
    mapper = TermMapper.default_position_mapper()
    mapper.register("MF", "playmaker")
    assert mapper.lookup("PlayMaker") == "MF"
