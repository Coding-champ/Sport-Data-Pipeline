"""Dynamic lexical configuration loader for scraper label/indicator mappings.

Loads additional (non-term-mapper) domain vocab from the same YAML file used by
`term_mapper` (default: config/term_mappings.yaml). Sections supported (optional):

indicators:
  squad_page: [squad, kader, team, mannschaft, spieler, players]
  player_link_context: [position, pos, torwart, ...]

player_stats_labels:
  appearances: [Appearances, Games, Matches, Spiele, Einsätze]
  goals: [Goals, Tore]
  ...

field_labels:
  position: [Position, Pos.]
  number: [Number, Nummer, Nr., '#']
  birth_date: [Born, Birth, Geboren, Date of Birth]
  ...

All lookups are normalised (casefold, strip accents, collapse whitespace).
Hot-reload is delegated to the term mapper watcher logic: we simply re-read the
file on explicit refresh() calls (cheap) to avoid duplicate threads.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Any
import os
import json
import threading
import unicodedata
import re
from .term_mapper import normalize_text as _tm_normalize  # reuse shared normalization

try:  # optional yaml
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

_WS_RE = re.compile(r"\s+")  # retained only for backwards compatibility if needed

def _norm(v: str) -> str:  # thin adapter
    return _tm_normalize(v)

@dataclass
class LexiconConfig:
    path: Path
    indicators: Dict[str, List[str]]
    player_stats_labels: Dict[str, List[str]]
    field_labels: Dict[str, List[str]]
    label_lookup: Dict[str, str]  # normalised label -> stat field

    def get_indicator_list(self, key: str) -> List[str]:
        return self.indicators.get(key, [])

    def get_field_labels(self, field: str) -> List[str]:
        return self.field_labels.get(field, [])

    def resolve_stat_field(self, raw_label: str) -> Optional[str]:
        if not raw_label:
            return None
        return self.label_lookup.get(_norm(raw_label))

_lock = threading.RLock()
_LEXICON_INSTANCE: Optional[LexiconConfig] = None


def _load_file(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    if path.suffix.lower() in ('.yaml', '.yml'):
        if not yaml:
            raise ImportError("PyYAML not installed but YAML file provided for lexicon config.")
        return yaml.safe_load(text) or {}
    return json.loads(text)

def _build_from_data(path: Path, data: dict) -> LexiconConfig:
    indicators = data.get('indicators') if isinstance(data.get('indicators'), dict) else {}
    player_stats_labels = data.get('player_stats_labels') if isinstance(data.get('player_stats_labels'), dict) else {}
    field_labels = data.get('field_labels') if isinstance(data.get('field_labels'), dict) else {}

    # Build normalised label lookup for stats
    label_lookup: Dict[str, str] = {}
    for field, labels in player_stats_labels.items():
        if not isinstance(labels, list):
            continue
        for lab in labels:
            if isinstance(lab, str):
                label_lookup[_norm(lab)] = field
    return LexiconConfig(path=path,
                         indicators={k: list(v) for k,v in indicators.items()},
                         player_stats_labels={k: list(v) for k,v in player_stats_labels.items()},
                         field_labels={k: list(v) for k,v in field_labels.items()},
                         label_lookup=label_lookup)

def get_lexicon_config(force_reload: bool = False) -> LexiconConfig:
    global _LEXICON_INSTANCE
    with _lock:
        if _LEXICON_INSTANCE is not None and not force_reload:
            return _LEXICON_INSTANCE
        path = Path(os.getenv('TERM_MAPPINGS_PATH', 'config/term_mappings.yaml'))
        if not path.exists():
            raise FileNotFoundError(f"Lexicon config file not found at {path}")
        data = _load_file(path)
        _LEXICON_INSTANCE = _build_from_data(path, data)
        return _LEXICON_INSTANCE

__all__ = [
    'LexiconConfig',
    'get_lexicon_config'
]
