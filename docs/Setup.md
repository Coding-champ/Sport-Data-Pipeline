## Ausführen (CLI)

Nutze die modulare CLI, um Scraping-Jobs konsistent zu starten. `sitecustomize.py` sorgt dafür, dass `src/` automatisch im `PYTHONPATH` ist.

Beispiele:

```bash
# Einmalige Läufe
python -m src.apps.cli run-once --jobs all
python -m src.apps.cli run-once --jobs flashscore
python -m src.apps.cli run-once --jobs odds transfermarkt
python -m src.apps.cli run-once --jobs fbref

# Scheduler für begrenzte Zeit (Live-Scores ~30s, Odds ~5min)
python -m src.apps.cli schedule --duration-minutes 10

# Verfügbare Scraper anzeigen
python -m src.apps.cli scrapers
```

Hinweise:

- Einheitliche HTTP-Header & User-Agent Rotation erfolgen zentral in `src/common/http.py` und werden in allen Scrapers über `AntiDetectionManager` genutzt.
- Datenpersistenz ist in Services in `src/database/services/` zentralisiert (`players.py`, `matches.py`, `odds.py`).

### Datenmodelle (Pydantic)

- Unsere Data Classes sind mit Pydantic implementiert, z. B. API-Modelle in `src/api/models.py` (erben von `pydantic.BaseModel`).
- Vorteile: Validierung, Defaults, Typ-Sicherheit und klare Schemas für Requests/Responses.
- Beispiel: `APIResponse`, `MatchPredictionRequest`, `PlayerAnalysisRequest`, `TeamStatsRequest` in `src/api/models.py`.