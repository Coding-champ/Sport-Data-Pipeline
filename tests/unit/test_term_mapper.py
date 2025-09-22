import pytest
import sys
from pathlib import Path

# Ensure project root (containing src/) is on sys.path when tests executed directly
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.term_mapper import TermMapper, map_position


def test_default_position_mapper_basic_synonyms():
    mapper = TermMapper.default_position_mapper()
    # Goalkeeper synonyms
    for term in ["Torwart", "Torhüter", "Keeper", "Goalkeeper", "TW", "gk"]:
        assert mapper.lookup(term) == "GK"
    # Defender synonyms
    for term in ["Defender", "Verteidiger", "Abwehr", "CB", "IV", "LV", "RV", "Full-Back", "Wing Back"]:
        assert mapper.lookup(term) == "DF"
    # Midfielder synonyms
    for term in ["Mittelfeld", "Midfielder", "DM", "OM", "ZM", "AM", "CM", "LM", "RM"]:
        assert mapper.lookup(term) == "MF"
    # Forward synonyms
    for term in ["Stürmer", "Stuermer", "Angriff", "Angreifer", "Striker", "FW", "MS", "ST", "CF"]:
        assert mapper.lookup(term) == "FW"


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
    mapper.register("MF", "playmaker")  # new synonym
    assert mapper.lookup("PlayMaker") == "MF"
