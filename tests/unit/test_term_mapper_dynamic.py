import os
import time
import sys
from pathlib import Path

# Ensure project root (contains src/) on path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.common.term_mapper import DynamicPositionMapper


def write_temp_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "term_mappings.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_dynamic_mapper_initial_load(tmp_path):
    yaml_content = """
positions:
  GK:
    canonical_long: Goalkeeper
    synonyms: [Torwart, TW]
  FW:
    canonical_long: Forward
    synonyms: [Stürmer, Stuermer]
""".strip()
    config_file = write_temp_yaml(tmp_path, yaml_content)
    mapper = DynamicPositionMapper(path=str(config_file), poll_interval=0)
    assert mapper.map_position("Torwart") == "GK"
    assert mapper.map_position("Stuermer") == "FW"
    assert mapper.map_position("Stürmer", return_long=True) == "Forward"


def test_dynamic_mapper_hot_reload(tmp_path):
    yaml_content_v1 = """
positions:
  GK:
    canonical_long: Goalkeeper
    synonyms: [Torwart]
""".strip()
    yaml_content_v2 = """
positions:
  GK:
    canonical_long: Goalkeeper
    synonyms: [Torwart, Keeper]
  MF:
    canonical_long: Midfielder
    synonyms: [Mittelfeld]
""".strip()
    config_file = write_temp_yaml(tmp_path, yaml_content_v1)
    mapper = DynamicPositionMapper(path=str(config_file), poll_interval=0.5)
    # initial
    assert mapper.map_position("Torwart") == "GK"
    assert mapper.map_position("Keeper") is None
    # update file
    time.sleep(0.2)
    config_file.write_text(yaml_content_v2, encoding="utf-8")
    # allow watcher to detect
    time.sleep(0.7)
    assert mapper.map_position("Keeper") == "GK"
    assert mapper.map_position("Mittelfeld") == "MF"
    mapper.stop()
