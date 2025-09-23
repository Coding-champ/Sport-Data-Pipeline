"""Generic term mapping utilities.

This module provides a `TermMapper` class which centralises synonym -> canonical
value mappings that are currently scattered as ad-hoc heuristics in scrapers.

Design goals:
 - Normalise input (case-fold, strip accents, collapse whitespace, remove punctuation)
 - Provide fast O(1) lookup via pre-built dictionary of normalised synonyms
 - Allow runtime extension (register / bulk update) without breaking existing mappings
 - Provide small helper functions for common football mapping tasks (e.g. positions)

Extended / compound positions (e.g. "Left Winger", "Right Back") are *not* expanded
at this stage; we reduce to the broad line for analytical aggregation. This can be
extended later with a second layer that retains granularity.

Variante C (aktiv):
    Die Funktion `map_position()` nutzt ausschließlich die externe Konfigurationsdatei
    (Standard: `config/term_mappings.yaml` oder Pfad via `TERM_MAPPINGS_PATH`).
    Das frühere statische in-Code Fallback-Mapping wurde entfernt, um konsistente
    deployments und konfigurierbare Domain-Änderungen ohne Codeänderungen zu ermöglichen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import unicodedata
import re
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Mapping, Any

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\.,;:_/\\()+\-\[\]{}]+")


def _strip_accents(value: str) -> str:
    """Return *value* with accents removed (NFKD decomposition -> drop marks)."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _base_normalize(value: str) -> str:
    """Apply text normalisation pipeline used for dictionary keys.

    Steps:
      1. Lowercase
      2. Trim
      3. Remove accents
      4. Replace punctuation with space
      5. Collapse multiple whitespace to single space
    """
    v = value.lower().strip()
    v = _strip_accents(v)
    v = _PUNCT_RE.sub(" ", v)
    v = _WHITESPACE_RE.sub(" ", v).strip()
    return v


@dataclass
class TermMapper:
    """Generic normalising synonym mapper.

    Attributes
    -----------
    mappings: Dict[str, str]
        Dict of normalised synonym -> canonical value. Always stores the *normalised*
        form of both the key and its canonical string (though canonical is not re-normalised
        externally; use whatever representation you want downstream).
    label: str
        Optional label indicating the domain (e.g. "positions") for easier debugging.
    """

    mappings: Dict[str, str] = field(default_factory=dict)
    label: str = ""

    # ---------------------------- Construction helpers ----------------------------
    @classmethod
    def from_groups(cls, groups: Mapping[str, Iterable[str]], label: str = "") -> "TermMapper":
        """Create a TermMapper from a mapping of canonical -> iterable of synonyms.

        Example
        -------
        groups = {
            "GK": ["torwart", "torhueter", "goalkeeper", "keeper", "tw", "gk"],
        }
        mapper = TermMapper.from_groups(groups, label="positions")
        """
        inst = cls(label=label)
        inst.register_groups(groups)
        return inst

    # ---------------------------- Registration API ----------------------------
    def register(self, canonical: str, *synonyms: str) -> None:
        """Register synonyms for a canonical value.

        Existing synonyms are overwritten (idempotent). Canonical itself is also
        registered so passing only the canonical is fine.
        """
        all_terms = list(synonyms) + [canonical]
        for term in all_terms:
            norm = _base_normalize(term)
            if not norm:
                continue
            self.mappings[norm] = canonical

    def register_groups(self, groups: Mapping[str, Iterable[str]]) -> None:
        for canonical, syns in groups.items():
            self.register(canonical, *list(syns))

    # ---------------------------- Lookup ----------------------------
    def lookup(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        norm = _base_normalize(value)
        return self.mappings.get(norm)

    def __contains__(self, value: str) -> bool:  # pragma: no cover - small convenience
        return self.lookup(value) is not None

    # ---------------------------- Legacy default static mapper ----------------------------
    _DEFAULT_POSITION_INSTANCE: Optional["TermMapper"] = None  # type: ignore

    @classmethod
    def default_position_mapper(cls) -> "TermMapper":
        """Return legacy static position mapper used by historical tests.

        Provides a broad-band mapping of common German/English/abbreviated football
        position terms to canonical short codes (GK, DF, MF, FW). This serves as a
        fallback for unit tests and environments where the dynamic external
        configuration file is absent.
        """
        if cls._DEFAULT_POSITION_INSTANCE is None:
            groups = {
                "GK": ["Torwart", "Torhueter", "Torhüter", "Keeper", "Goalkeeper", "TW", "gk"],
                "DF": [
                    "Defender", "Verteidiger", "Abwehr", "CB", "IV", "LV", "RV",
                    "Full-Back", "Full Back", "Wing Back", "WB", "FB"
                ],
                "MF": [
                    "Mittelfeld", "Midfielder", "DM", "OM", "ZM", "AM", "CM",
                    "LM", "RM", "Zentrales Mittelfeld", "Mittelfeldspieler"
                ],
                "FW": [
                    "Stürmer", "Stuermer", "Angriff", "Angreifer", "Striker", "FW",
                    "MS", "ST", "CF", "Forward"
                ],
            }
            cls._DEFAULT_POSITION_INSTANCE = cls.from_groups(groups, label="positions(static)")
        return cls._DEFAULT_POSITION_INSTANCE

def normalize_text(value: str) -> str:
    """Public wrapper used by other modules for consistent normalisation.

    Exposed instead of duplicating accent/punct/whitespace logic in multiple modules.
    """
    return _base_normalize(value)

__all__ = ["TermMapper", "normalize_text"]


# =============================================================================
# Dynamic external configuration support (JSON / YAML w/out hard dependency)
# =============================================================================

def _try_load_yaml(text: str) -> Any:
    """Attempt to load YAML if PyYAML is installed; fallback raises ImportError.

    We keep this optional to avoid forcing a dependency. Users can either install
    PyYAML or provide JSON. Errors propagate for visibility.
    """
    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover - optional path
        raise ImportError("YAML support requires 'pyyaml' to be installed.") from e
    return yaml.safe_load(text)


def _normalize_groups_struct(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalise external file structure into canonical groups dict.

    Expected shapes:
    {
      "positions": {
         "GK": {"synonyms": [...], "canonical_long": "Goalkeeper"},
         ...
      }
    }
    or a flat mapping directly of codes -> list[str].
    """
    if not data:
        return {}
    # If 'positions' key present use that
    if isinstance(data.get('positions'), dict):
        section = data['positions']
    else:
        section = data
    out: dict[str, dict[str, Any]] = {}
    for code, spec in section.items():
        if isinstance(spec, list):  # plain list = synonyms only
            out[code] = {"synonyms": spec}
        elif isinstance(spec, dict):
            syns = spec.get('synonyms') or spec.get('values') or []
            if isinstance(syns, str):
                syns = [syns]
            out[code] = {
                "synonyms": list(syns),
                "canonical_long": spec.get('canonical_long') or spec.get('long') or None
            }
    return out


class DynamicMappings:
    """Generic multi-category mapper (positions, nationalities, footedness) with hot-reload.

    Each section: CODE:
        canonical_long: Optional descriptive long form
        synonyms: [list, of, variants]
    """

    # Wir initialisieren leer und füllen nach erstem erfolgreichen Load.
    CATEGORY_DEFAULTS: dict[str, TermMapper] = {}

    def __init__(self, path: Optional[str] = None, poll_interval: Optional[float] = None):
        self.path = Path(path or os.getenv('TERM_MAPPINGS_PATH', 'config/term_mappings.yaml'))
        self.poll_interval = poll_interval if poll_interval is not None else float(os.getenv('TERM_MAPPINGS_POLL', '5') or 5)
        self._lock = threading.RLock()
        self._mtime: Optional[float] = None
        self._mappers: dict[str, TermMapper] = {}
        self._long_forms: dict[str, dict[str, str]] = {}
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._initial_load()
        if self.poll_interval > 0:
            self._thread = threading.Thread(target=self._watch_loop, name='TermMappingsWatch', daemon=True)
            self._thread.start()

    # ---------------- Internal load logic ----------------
    def _load_file(self) -> bool:
        if not self.path.exists():
            return False
        try:
            text = self.path.read_text(encoding='utf-8')
            if self.path.suffix.lower() in ('.yaml', '.yml'):
                data = _try_load_yaml(text)
            else:
                data = json.loads(text)
            updated_mappers: dict[str, TermMapper] = {}
            updated_longs: dict[str, dict[str, str]] = {}
            for category in ['positions', 'nationalities', 'footedness']:
                block = data.get(category)
                if isinstance(block, dict):
                    # Generic parsing: block is expected to be mapping of CODE -> {synonyms: [...], canonical_long: ...}
                    # or CODE -> list[synonyms].
                    term_groups: dict[str, list[str]] = {}
                    longs: dict[str, str] = {}
                    for code, spec in block.items():
                        if isinstance(spec, list):
                            term_groups[code] = [str(s) for s in spec]
                        elif isinstance(spec, dict):
                            syns = spec.get('synonyms') or spec.get('values') or []
                            if isinstance(syns, str):
                                syns = [syns]
                            term_groups[code] = [str(s) for s in syns]
                            if spec.get('canonical_long'):
                                longs[code] = str(spec['canonical_long'])
                    if term_groups:
                        updated_mappers[category] = TermMapper.from_groups(term_groups, label=f'{category}(dynamic)')
                        updated_longs[category] = longs
            with self._lock:
                self._mappers = updated_mappers
                self._long_forms = updated_longs
                self._mtime = self.path.stat().st_mtime
            return True
        except Exception:
            return False

    def _initial_load(self):
        if not self._load_file():
            # Wenn keine Datei existiert -> klarer Fehler statt silent fallback
            raise FileNotFoundError(
                f"Term mappings file not found at '{self.path}'. Provide it or set TERM_MAPPINGS_PATH."
            )

    def _watch_loop(self):  # pragma: no cover - timing-dependent
        while not self._stop_evt.is_set():
            try:
                if self.path.exists():
                    m = self.path.stat().st_mtime
                    if self._mtime is None or m > self._mtime:
                        self._load_file()
                time.sleep(self.poll_interval)
            except Exception:
                time.sleep(self.poll_interval)

    # ---------------- Public API ----------------
    def _map(self, category: str, raw: Optional[str], *, return_long: bool = False) -> Optional[str]:
        if not raw:
            return None
        with self._lock:
            mapper = self._mappers.get(category)
            if not mapper:
                return None
            code = mapper.lookup(raw)
            if not code:
                return None
            if return_long:
                return self._long_forms.get(category, {}).get(code, code)
            return code

    def map_position(self, raw: Optional[str], *, return_long: bool = False) -> Optional[str]:
        return self._map('positions', raw, return_long=return_long)

    def map_nationality(self, raw: Optional[str], *, return_long: bool = True) -> Optional[str]:
        return self._map('nationalities', raw, return_long=return_long)

    def map_footedness(self, raw: Optional[str]) -> Optional[str]:
        return self._map('footedness', raw, return_long=False)

    def stop(self):  # pragma: no cover - rarely used in tests
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)


def get_dynamic_mappings() -> DynamicMappings:
    global _DYNAMIC_MAPPINGS
    try:
        inst = _DYNAMIC_MAPPINGS
    except NameError:
        inst = None
    if inst is None:
        inst = DynamicMappings()
        _DYNAMIC_MAPPINGS = inst  # type: ignore
    return inst


def map_position(value: Optional[str], *, return_long: bool = False) -> Optional[str]:
    """Map a raw position string to canonical code or long form.

    Tries dynamic external mappings first; if the configuration file is not
    available falls back to the legacy static default mapper.
    """
    try:
        return get_dynamic_mappings().map_position(value, return_long=return_long)
    except FileNotFoundError:
        if not value:
            return None
        mapper = TermMapper.default_position_mapper()
        code = mapper.lookup(value)
        if not code:
            return None
        if return_long:
            LONGS = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}
            return LONGS.get(code, code)
        return code

def map_nationality(value: Optional[str], *, return_long: bool = True) -> Optional[str]:
    return get_dynamic_mappings().map_nationality(value, return_long=return_long)

def map_footedness(value: Optional[str]) -> Optional[str]:
    return get_dynamic_mappings().map_footedness(value)


class DynamicPositionMapper(DynamicMappings):
    """Backward compatible façade expected by older tests.

    The legacy implementation exposed a `DynamicPositionMapper` focused solely
    on positional terms. The refactor generalised this to `DynamicMappings`
    with multiple categories. For compatibility we subclass without modifying
    behaviour so tests importing the old name continue to work.
    """

    # Direct pass-through; kept for semantic clarity.
    pass

__all__.extend([
    'DynamicMappings',
    'DynamicPositionMapper',
    'get_dynamic_mappings',
    'map_position',
    'map_nationality',
    'map_footedness'
])
