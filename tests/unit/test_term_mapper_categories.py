import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.common.term_mapper import map_nationality, map_footedness, map_position, get_dynamic_mappings


def _ensure_loaded():
    # Force instantiation and allow brief time for initial file load (non-blocking thread)
    inst = get_dynamic_mappings()
    # The loader is synchronous for first load, but be safe if file access delayed
    for _ in range(5):
        if map_nationality('de') is not None:
            break
        import time; time.sleep(0.1)


def test_map_nationality_basic():
    _ensure_loaded()
    assert map_nationality('de') == 'Germany'
    assert map_nationality('GER') == 'Germany'
    assert map_nationality('Deutschland') == 'Germany'
    assert map_nationality('xx') is None


def test_map_footedness_basic():
    _ensure_loaded()
    assert map_footedness('Left') == 'L'
    assert map_footedness('right') == 'R'
    assert map_footedness('both') == 'B'
    assert map_footedness('unknown-foot') is None


def test_position_still_works():
    assert map_position('Goalkeeper') == 'GK'
    assert map_position('Torwart') == 'GK'
