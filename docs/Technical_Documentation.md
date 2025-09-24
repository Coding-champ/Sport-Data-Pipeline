# Sport Data Pipeline - Technische Dokumentation

## 🏗️ Softwarearchitektur und Modulstruktur

### Überblick

Die Sport Data Pipeline ist eine Plattform für die Sammlung, Analyse und Bereitstellung von Sportdaten. Das System folgt einer modularen Architektur mit klarer Trennung der Verantwortlichkeiten.

### Architektur-Diagramm

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Clients   │    │   Mobile Apps   │    │  External APIs  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      FastAPI Layer      │
                    │    (API Endpoints)      │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          └─────────────────────┼─────────────────────┘
                    ┌────────────▼────────────┐
                    │   Database Manager      │
                    │   (PostgreSQL + Redis)  │
                    └─────────────────────────┘
```

### Modulstruktur

```text
src/                   # Haupt-Package
├── api/                          # FastAPI Anwendungsschicht
│   ├── main.py                   # FastAPI App Configuration
│   ├── dependencies.py           # Dependency Injection
│   ├── models.py                 # Pydantic Request/Response Models
│   ├── router.py                 # Router Aggregation
│   └── endpoints/                # API Endpoints (modulare Router)
│       ├── players.py            # Spieler-Endpoints
│       ├── matches.py            # Spiel-Endpoints
│       ├── teams.py              # Team-Endpoints
│       ├── odds.py               # Wett-Endpoints
│       ├── analytics.py          # Analytics-Endpoints
│       └── system.py             # System/Health-Endpoints
├── core/                         # Zentrale Konfiguration
│   └── config.py                 # Pydantic Settings mit Env-Variablen
├── data_collection/              # Datensammlung
│   ├── orchestrator.py           # Koordiniert alle Datensammler
│   ├── collectors/              # API-basierte Datensammler
│   │   ├── base.py              # Abstract Base Collector
│   │   ├── football_data_api_collector.py  # Football-data.org
│   │   └── betfair_odds_collector.py       # Betfair Exchange
│   └── scrapers/                # Web-Scraping Module
│   │   ├── match_prediction.py
│   │   └── market_analysis.py
│   └── reports/                 # Report Generation
│       ├── player_reports.py
│       └── league_reports.py
├── database/                    # Datenbankschicht
│   ├── manager.py               # Database Manager
│   ├── schema.py                # SQLAlchemy Models
│   └── services/                # Data Access Layer
│       ├── __init__.py
│       ├── players.py           # Spieler-Services
│       ├── matches.py           # Spiel-Services
│       ├── teams.py             # Team-Services
├── domain/                      # Domain Models
│   ├── entities/                # Business Entities
│   └── value_objects/           # Value Objects
├── common/                      # Gemeinsame Utilities
│   ├── http.py                  # HTTP Client mit Anti-Detection
│   ├── logging.py               # Strukturiertes Logging
└── monitoring/                  # Monitoring & Metriken
    ├── metrics.py               # Prometheus Metriken
    └── health.py                # Health Checks
### Zentrale Konfiguration

Alle Einstellungen werden über `src/core/config.py` mit Pydantic Settings verwaltet und können über Umgebungsvariablen überschrieben werden.

### Wichtige Konfigurationsbereiche

- **Database**: PostgreSQL-Verbindung, Pool-Größe
- **Redis**: Caching und Message Broker
- **API**: Host, Port, CORS, Authentifizierung
- **Scraping**: Intervalle, Anti-Detection, Timeouts
- **Analytics**: Model-Updates, Cache-Strategien
- **Monitoring**: Metriken, Health Checks, Logging

---

## 🔗 Externe ID-Mappings (Quelle → interne IDs)

Ziel: Externe Anbieter-IDs (z. B. FBref, Transfermarkt, Flashscore) stabil den internen Entitäten zuordnen. Dadurch werden Idempotenz beim Import, Deduplizierung und quellübergreifendes Linking gewährleistet.

### Schema-Pattern

- Für jede Entität mit externen IDs gibt es eine Mapping-Tabelle mit folgendem Muster:
    - Primärschlüssel: `(source, external_id)` (Composite)
    - Fremdschlüssel: `<entity_id_col>` → Basistabelle, `ON DELETE CASCADE`
    - Eindeutigkeit: `UNIQUE (source, <entity_id_col>)` verhindert doppelte Mappings derselben Quelle auf verschiedene externe IDs

```sql
CREATE TABLE <entity>_external_ids (
    PRIMARY KEY (source, external_id),
    UNIQUE (source, <entity_id>)
);
CREATE INDEX ix_<entity>_external_ids_source ON <entity>_external_ids(source);
```

### Angelegte Mapping-Tabellen (Migration 0002)

Die SQL-Migration `database/migrations/0002_external_id_mappings.sql` legt die Tabellen nur an, wenn die jeweilige Basistabelle existiert (`to_regclass`-Check):

- `player_external_ids (player_id → player.player_id)`
- `team_external_ids (team_id → team.team_id)`
- `club_external_ids (club_id → club.club_id)`
- `match_external_ids (match_id → match.match_id)`
- `venue_external_ids (venue_id → venue.venue_id)`
- `stadium_external_ids (stadium_id → stadium.stadium_id)` (optional, falls vorhanden)
- `competition_external_ids (competition_id → competition.competition_id)`
- `tournament_external_ids (tournament_id → tournament.tournament_id)` (optional)
- `referee_external_ids (referee_id → referee.referee_id)`
- `coach_external_ids (coach_id → coach.coach_id)`
- `country_external_ids (country_id → country.country_id)`
- `city_external_ids (city_id → city.city_id)`

Die Migration nutzt eine Helper-Funktion `create_mapping_if_base_exists(base_table, mapping_table, entity_col)`, um Wiederholbarkeit und robuste Checks sicherzustellen.

Ausführung (PowerShell):

```powershell
psql "postgresql://user:pass@localhost:5432/yourdb" -f "database\migrations\0002_external_id_mappings.sql"
```

### Async Mapping Service (strict, idempotent)

Implementiert unter `src/database/services/external_id_mapping_service_async.py` mit `asyncpg`:

- Klasse: `ExternalIdMappingServiceAsync`
    - `ensure(entity, source, external_id, internal_id)`
        - Fügt neues Mapping ein (`ON CONFLICT (source, external_id) DO NOTHING`).
        - Ist bereits ein Mapping vorhanden:
            - identische `internal_id` → OK (idempotent)
            - abweichende `internal_id` → `MappingConflictError` (Remapping wird nicht automatisch vorgenommen)
    - `find(entity, source, external_id)` → liefert `internal_id` oder `None`
- Bequeme Wrapper für gängige Entitäten, z. B. `ensure_player`, `find_team`, `ensure_club`, `ensure_match`, `ensure_competition`, …

Vertrag/Fehlermodi:

- Eingaben: `entity: str` (z. B. "player"), `source: str | Source`, `external_id: str`, `internal_id: int`
- Rückgabe: `internal_id: int` (existierende oder neu angelegte Zuordnung)
- Fehler: `MappingConflictError` falls (source, external_id) bereits auf eine andere `internal_id` zeigt
- Nebenläufigkeit: Transaktionale Absicherung, zweiter Insert-Versuch bei seltenen Races

Beispiel (vereinfacht):

```python
from src.database.manager import DatabaseManager
from src.database.services.external_id_mapping_service_async import ExternalIdMappingServiceAsync, MappingConflictError
from src.common.constants import Source

db = DatabaseManager()
svc = ExternalIdMappingServiceAsync()

async def demo(conn):
        try:
                await svc.ensure_player(conn, source=Source.FBREF, external_id="p_42", player_id=123)
        except MappingConflictError as e:
                # Konflikt bewusst behandeln (loggen, manuell prüfen)
                raise
```

Vollständiges, lauffähiges Beispiel: `scripts/demo_external_id_mapping.py` (erst die Migration ausführen).

### Source-Konstanten und Normalisierung

Zentrale Definition unter `src/common/constants.py`:

- `Source` Enum: `fbref`, `sofascore`, `transfermarkt`, `bundesliga`, `bet365`, `flashscore`, `courtside1891`, `odds`
- `normalize_source(value: str | Source) -> str` canonicalisiert und validiert Eingaben; gängige Aliasse (`tm`, `fs`, `fb`) werden aufgelöst
- Der Mapping-Service akzeptiert `str | Source` und normalisiert vor dem DB-Zugriff → konsistente Speicherung/Abfragen

### Betriebs- und Datenqualitätsregeln

- Remapping-Policy: Automatisches Umhängen wird nicht durchgeführt (Konflikt wird gemeldet). Anpassungen erfolgen bewusst/manuell.
- Idempotenz: Wiederholte `ensure(...)`-Aufrufe mit derselben Zuordnung sind No-Ops.
- Integrität: `UNIQUE (source, <entity_id>)` verhindert widersprüchliche Mappings je Quelle.
- Performance: PK `(source, external_id)` + Index auf `source` sichern schnelle Suchen/Upserts. Batch-APIs sind aktuell nicht erforderlich, können später ergänzt werden.

## ��️ CLI und Verwaltung

### Modulare CLI-Schnittstelle

Das System bietet eine einheitliche CLI für verschiedene Operationen:

```bash
# Einmalige Scraping-Läufe
python -m src.apps.cli run-once --jobs all
python -m src.apps.cli run-once --jobs flashscore
python -m src.apps.cli run-once --jobs odds transfermarkt
python -m src.apps.cli run-once --jobs fbref

# Scheduler für begrenzte Zeit
python -m src.apps.cli schedule --duration-minutes 10

# Verfügbare Scraper anzeigen
python -m src.apps.cli scrapers
```

### Run-Modi Konfiguration

Über die Umgebungsvariable `RUN_MODE` oder `Settings.run_mode`:

- **`interactive`**: CLI-Menü im Prozess
- **`api_only`**: Nur FastAPI starten
- **`collection_once`**: Ein Datensammlungszyklus und beenden
- **`analytics_once`**: Einmalige Analytics-Routine
- **`full_service`**: API und Background-Scheduler starten

### Operative Scripts

```bash
# Database Diagnostics
python -m scripts.db_diagnostics

# API Health Smoke Test
python scripts/api_health_smoke.py

# Scraper Testing
python scripts/test_scraper.py

# Development Debugging
python scripts/simple_debug.py
```

## 🛠️ Verwendete Software und Frameworks

### Backend-Framework

| Framework | Version | Zweck |
|-----------|---------|-------|
| **FastAPI** | 0.104.1 | Moderne, schnelle Web-API mit automatischer OpenAPI-Dokumentation |
| **Uvicorn** | 0.24.0 | ASGI-Server für High-Performance |
| **Pydantic** | 2.4.2 | Datenvalidierung und Settings-Management |

### Datenbank-Stack

| Technologie | Version | Zweck |
|-------------|---------|-------|
| **PostgreSQL** | 15+ | Primäre relationale Datenbank mit JSONB-Support |
| **SQLAlchemy** | 2.0.23 | ORM mit Async-Support |
| **Asyncpg** | 0.29.0 | Async PostgreSQL-Treiber |
| **Alembic** | 1.12.1 | Datenbank-Migrations |
| **Redis** | 4.0.1+ | Caching und Message Broker |

### Web-Scraping-Stack

| Tool | Version | Einsatzzweck |
|------|---------|-------------|
| **Selenium** | 4.15.2 | Browser-Automatisierung für JS-heavy Sites |
| **Playwright** | 1.40.0 | Moderne Browser-Automatisierung |
| **Undetected Chrome** | 3.5.4 | Anti-Detection Browser |
| **BeautifulSoup** | 4.12.2 | HTML-Parsing |
| **CloudScraper** | 1.2.71 | Cloudflare-Bypass |
| **aiohttp** | 3.8.6 | Async HTTP-Client |

### Machine Learning & Analytics

| Bibliothek | Version | Anwendung |
|------------|---------|-----------|
| **scikit-learn** | 1.3.2 | Machine Learning Algorithmen |
| **pandas** | 2.1.3 | Datenmanipulation und -analyse |
| **numpy** | 1.24.3 | Numerische Berechnungen |
| **statsmodels** | 0.14.0 | Statistische Modellierung |
| **matplotlib** | 3.8.1 | Basis-Visualisierung |
| **plotly** | 5.17.0 | Interaktive Dashboards |
| **seaborn** | 0.13.0 | Statistische Visualisierung |

### Background Processing

| Tool | Version | Funktion |
|------|---------|----------|
| **Celery** | 4.0.1+ | Async Task Queue |
| **Redis** | 4.0.1+ | Message Broker für Celery |

### Monitoring & DevOps

| Tool | Version | Zweck |
|------|---------|-------|
| **Prometheus** | Client 0.19.0 | Metriken-Sammlung |
| **Docker** | Latest | Containerisierung |
| **psutil** | 5.9.6 | System-Monitoring |

### Development & Testing

| Tool | Version | Einsatz |
|------|---------|---------|
| **pytest** | 7.4.3 | Testing Framework |
| **black** | 23.10.1 | Code Formatting |
| **isort** | 5.12.0 | Import Sorting |
| **mypy** | 1.7.0 | Type Checking |

## 🏟️ Verfügbare API-Services

### Authentifizierung

- **API-Key basiert**: `X-API-Key` Header erforderlich (außer Development)
- **Rate Limiting**: Konfigurierbare Anfragen pro Minute
- **CORS**: Konfigurierbare Origins

### Kern-Endpoints

#### Spieler-Management (`/api/v1/players`)

```http
GET    /api/v1/players                    # Liste aller Spieler
GET    /api/v1/players/{id}               # Einzelner Spieler
POST   /api/v1/players/{id}/analyze       # Spieleranalyse
GET    /api/v1/players/{id}/stats         # Spielerstatistiken
GET    /api/v1/players/{id}/transfers     # Transfer-Historie
POST   /api/v1/players/{id}/predict       # Performance-Vorhersage
```

#### Team-Management (`/api/v1/teams`)

```http
GET    /api/v1/teams                      # Liste aller Teams
GET    /api/v1/teams/{id}                 # Team-Details
GET    /api/v1/teams/{id}/players         # Team-Kader
GET    /api/v1/teams/{id}/matches         # Team-Spielplan
POST   /api/v1/teams/{id}/analyze         # Team-Analyse
```

#### Spiel-Management (`/api/v1/matches`)

```http
GET    /api/v1/matches                    # Spielliste (mit Filtern)
GET    /api/v1/matches/{id}               # Spiel-Details
POST   /api/v1/matches/predict            # Spielvorhersage
GET    /api/v1/matches/live               # Live-Spiele
GET    /api/v1/matches/{id}/events        # Spielereignisse
GET    /api/v1/matches/{id}/stats         # Spielstatistiken
```

#### Wett-Daten (`/api/v1/odds`)

```http
GET    /api/v1/odds/matches/{id}          # Quoten für Spiel
GET    /api/v1/odds/compare               # Quoten-Vergleich
GET    /api/v1/odds/value                 # Value-Bets
```

#### Analytics (`/api/v1/analytics`)

```http
POST   /api/v1/analytics/player           # Spieler-Analyse
POST   /api/v1/analytics/team             # Team-Analyse
POST   /api/v1/analytics/league           # Liga-Analyse
POST   /api/v1/analytics/market           # Markt-Analyse
GET    /api/v1/analytics/reports/{id}     # Report abrufen
```

#### System-Endpoints (`/api/v1/system`)

```http
GET    /health                           # System Health Check
GET    /metrics                          # Prometheus Metriken
GET    /api/v1/system/status             # Detaillierter System-Status
POST   /api/v1/system/scraping/trigger   # Scraping manuell starten
GET    /api/v1/system/jobs               # Background Job Status
GET    /docs                            # OpenAPI Dokumentation
```

### Request/Response-Formate

Alle Endpoints nutzen JSON für Request/Response mit Pydantic-Validierung:

```python
# Beispiel: Match Prediction Request
{
    "home_team_id": 1,
    "away_team_id": 2,
    "match_date": "2024-12-15T15:00:00Z",
    "venue_id": 3,
    "include_confidence": true,
    "historical_depth_games": 10
}

# Response
{
    "prediction": {
        "home_win_probability": 0.45,
        "draw_probability": 0.30,
        "away_win_probability": 0.25,
        "confidence_level": 0.78
    },
    "factors": {
        "home_advantage": 0.12,
        "form_difference": 0.08,
        "head_to_head": 0.15
    },
    "metadata": {
        "model_version": "v2.1",
        "prediction_timestamp": "2024-12-01T10:30:00Z"
    }
}
```

## 📊 Datenmodell und Schema

### Datenbank-Architektur

Das System nutzt PostgreSQL mit strategischem Einsatz von JSONB für flexible, sportspezifische Daten.

#### Kern-Entitäten

##### Sports & Hierarchie

```sql
sports                  -- Unterstützte Sportarten (Football, Basketball, American Football)
├── countries           -- Länder
├── leagues            -- Ligen/Wettbewerbe
├── teams              -- Teams/Vereine
├── venues             -- Spielstätten
└── players            -- Spieler
```

##### Spieler & Personal

```sql
players                 -- Spieler-Stammdaten
├── player_contracts    -- Verträge
├── player_positions    -- Spielerpositionen (sportspezifisch)
├── transfers          -- Transfer-Historie
├── player_injuries    -- Verletzungsdaten
└── season_player_stats -- Saisonstatistiken (JSONB für sportspezifische Stats)
```

##### Spiele & Events

```sql
matches                -- Spiele
├── match_events       -- Spielereignisse (Tore, Karten, etc.)
├── match_player_stats -- Spieler-Leistung pro Spiel
├── match_officials    -- Schiedsrichter-Einsätze
└── match_technology_data -- VAR/Technologie-Entscheidungen
```

##### Wett-System

```sql
bookmakers            -- Wettanbieter
├── betting_markets   -- Wettmärkte (sportspezifisch)
├── odds             -- Quoten mit Live-Updates
└── bet_results      -- Wett-Ergebnisse
```

### JSONB-Felder für Flexibilität

#### Sportspezifische Statistiken

```sql
-- In season_player_stats Tabelle
football_stats JSONB    -- Fußball: goals, assists, passes, tackles...
basketball_stats JSONB  -- Basketball: points, rebounds, assists, steals...
american_football_stats JSONB -- Am. Football: yards, touchdowns, sacks...

-- Beispiel Football Stats
{
    "goals": 15,
    "assists": 8,
    "shots": 45,
    "shots_on_target": 28,
    "pass_accuracy": 0.87,
    "tackles_won": 23,
    "dribbles_completed": 12,
    "aerial_duels_won": 18,
    "distance_covered_km": 10.5
}
```

#### Match Events (sportspezifisch)

```sql
event_data JSONB  -- Flexible Event-Daten pro Sportart

-- Football Event
{
    "event_type": "goal",
    "minute": 67,
    "assist_player_id": 456,
    "body_part": "right_foot",
    "position": {"x": 16, "y": 8}
}

-- Basketball Event  
{
    "event_type": "three_pointer",
    "quarter": 3,
    "time_remaining": "05:23",
    "assist_player_id": 789,
    "position": {"x": 24.5, "y": 6.1}
}
```

#### Team & Venue Metadata

```sql
-- Teams
metadata JSONB  -- Social Media, Sponsoren, Ausstattung
facility_features JSONB  -- Stadium-Features, Technologie

-- Venues  
technology_features JSONB  -- VAR, Torlinientechnik, etc.
```

## 📡 Datenquellen-Übersicht

| Datenquelle | Typ | URL/Basis-URL | Kategorie | Sportarten | Status |
|-------------|-----|---------------|-----------|------------|---------|
| **FBref** | Web Scraping | https://fbref.com | Statistiken, Spieleranalyse | Football | ✅ Aktiv |
| **Transfermarkt** | Web Scraping | https://transfermarkt.com | Transfers, Marktwerte, Kader | Football | ✅ Aktiv |
| **Football-data.org** | REST API | https://api.football-data.org | Spiele, Teams, Ligen | Football | ✅ Aktiv |
| **Betfair Exchange** | REST API | https://api.betfair.com | Live-Quoten, Wettmärkte | Football, Basketball | ✅ Aktiv |
| **Flashscore** | Web Scraping | https://flashscore.com | Live-Scores, Spielergebnisse | Football, Basketball | ✅ Aktiv |
| **Courtside** | Web Scraping | https://courtside.com | Spieleranalyse, Statistiken | Basketball | ✅ Aktiv |
| **Bet365** | Web Scraping | https://bet365.com | Wettquoten, Live-Betting | Football, Basketball, Am. Football | ✅ Aktiv |
| **BetExplorer** | Web Scraping | https://betexplorer.com | Historische Quoten, Quotenvergleich | Football, Basketball | ✅ Aktiv |
| **Premier League** | Web Scraping | https://premierleague.com | Offizielle Liga-Daten | Football | ✅ Aktiv |
| **SofaScore** | Web Scraping | https://sofascore.com | Live-Scores, Statistiken | Football, Basketball | ✅ Aktiv |
| **WhoScored** | Web Scraping | https://whoscored.com | Detaillierte Spieleranalyse | Football | ✅ Aktiv |
| **ZeroZero** | Web Scraping | https://zerozero.pt | Portugiesische Liga-Daten | Football | ✅ Aktiv |

### Datensammlung-Frequenzen

| Kategorie | Frequenz | Datenquellen |
|-----------|----------|--------------|
| **Live-Scores** | 30 Sekunden | Flashscore, SofaScore |
| **Wett-Quoten** | Täglich (2:00 AM) | Bet365, Betfair, BetExplorer |
| **Spielerstatistiken** | Täglich (2:00 AM) | FBref, Transfermarkt, WhoScored |
| **Transfers** | Montags (20:00 PM) | Transfermarkt |
| **Liga-Updates** | Täglich | Premier League, Football-data.org |
| **Team-Daten** | Wöchentlich | Alle Quellen |

### Anti-Detection-Maßnahmen

- **Undetected Chrome**: Für schwer zu scrapende Sites
- **Header-Rotation**: Zufällige User-Agents und Headers
- **Proxy-Rotation**: Bei Bedarf konfigurierbar
- **Rate-Limiting**: Respektvolle Request-Intervalle
- **Retry-Logic**: Exponential Backoff bei Fehlern

## 🛣️ Roadmap und Features

### ✅ Aktuell verfügbare Key Features

#### Datensammlung & -verarbeitung

- ✅ **Multi-Source Integration**: 12 aktive Datenquellen
- ✅ **Anti-Detection Web Scraping**: Undetected Chrome, Header-Rotation
- ✅ **API Integration**: Football-data.org, Betfair Exchange
- ✅ **Live-Daten**: Echtzeit-Scores
- ✅ **Automatisierte Sammlung**: Celery-basierte Background Jobs
- ✅ **Fehlerbehandlung**: Retry-Logic mit exponential Backoff

#### API & Integration

- ✅ **RESTful API**: FastAPI mit OpenAPI-Dokumentation
- ✅ **Authentifizierung**: API-Key basierte Sicherheit
- ✅ **Rate Limiting**: Schutz vor Überlastung
- ✅ **CORS Support**: Web-Client Integration

#### Produktion & Monitoring

- ✅ **Containerisierung**: Docker & Docker Compose
- ✅ **Monitoring**: Prometheus Metriken
- ✅ **Health Checks**: Umfassendes System-Monitoring
- ✅ **Strukturiertes Logging**: JSON-Logs mit Korrelations-IDs

### 🔄 Aktuell in Entwicklung (nächste 3 Monate)

#### Performance Optimierungen

- 🔄 **Database Sharding**: Horizontale Skalierung
- 🔄 **Caching Strategy**: Redis Cluster, CDN Integration
- 🔄 **Query Optimization**: Index-Optimierung, Query-Tuning
- 🔄 **API Gateway**: Load Balancing, API-Versionierung

### 📋 Geplante Features (6-12 Monate)

#### Erweiterte ML-Modelle

- 📋 **Neural Networks**: Deep Learning für präzisere Vorhersagen
- 📋 **Ensemble Methods**: Kombination mehrerer Modelle
- 📋 **Feature Engineering**: Erweiterte statistische Features
- 📋 **Model Versioning**: MLflow Integration

#### Real-time Streaming

- 📋 **WebSocket API**: Echtzeit-Daten für Web-Clients
- 📋 **Live Notifications**: Push-Benachrichtigungen

#### Enhanced Visualisation

- 📋 **Interactive Dashboards**: Erweiterte Plotly-Dashboards
- 📋 **Mobile-Responsive UI**: Progressive Web App
- 📋 **Custom Report Builder**: Report-Erstellung
- 📋 **Data Export**: Erweiterte Export-Optionen (Excel, PowerBI)

#### Zusätzliche Sportarten

- 📋 **Hockey**: NHL/European Hockey Integration
- 📋 **Baseball**: MLB Statistics Integration
- 📋 **eSports**: Gaming Tournament Data

#### Fantasy Sports Integration

- 📋 **Fantasy API**: Draft Kings/FanDuel Integration
- 📋 **Lineup Optimization**: ML-optimierte Team-Aufstellungen
- 📋 **Player Projections**: Fantasy Points Predictions
- 📋 **Contest Analysis**: ROI-Optimierung

#### Advanced Betting Analytics

- 📋 **Arbitrage Detection**: Surebet-Finder
- 📋 **Value Bet Algorithm**: Mathematical Edge Detection
- 📋 **Bankroll Management**: Portfolio-Optimierung
- 📋 **Live Betting Signals**: Real-time Opportunity Alerts

#### AI-Powered Insights

- 📋 **Natural Language Generation**: Automated Match Reports
- 📋 **Computer Vision**: Video Analysis Integration
- 📋 **Sentiment Analysis**: Social Media Impact auf Quoten

### 💡 Zukünftige Innovationen (12+ Monate)

#### Blockchain Integration

- 💡 **Smart Contracts**: Automatisierte Wett-Abwicklung
- 💡 **NFT Integration**: Digitale Sammelkarten/Momente
- 💡 **Decentralized Data**: Blockchain-basierte Datenverifizierung

#### Advanced AI

- 💡 **Large Language Models**: ChatGPT-Integration für Queries

#### Mobile & IoT

- 💡 **Stadium IoT**: Direkte Venue-Datenintegration

#### Enterprise Features

- 💡 **White-Label Solutions**: Anpassbare Platform für Kunden
- 💡 **B2B API Marketplace**: Daten-as-a-Service
- 💡 **Regulatory Compliance**: GDPR, CCPA, Gaming-Regulierung

*Diese technische Dokumentation wird kontinuierlich aktualisiert und erweitert.*

---

## 🌐 Unified Playwright Rendering & Hook System

### Motivation

Vor der Konsolidierung enthielten mehrere Scraper (Flashscore, Premier League, Transfermarkt Injuries, Courtside) duplizierte Playwright-Logik: Browserstart, Consent Handling, Scrolling, Retry, Event-Capture. Diese wurde zentralisiert in `src/common/playwright_utils.py` um:

- Boilerplate zu reduzieren
- Einheitliche Retry/Backoff Strategien durchzusetzen
- Wiederverwendbare Event-Hooks bereitzustellen (Netzwerk JSON / Console / Requests)
- Vereinheitlichte Consent- & Lazy-Load Handhabung (Scrolling)

### Kern-Bausteine

```python
@dataclass
class FetchOptions:
    url: str
    wait_until: str = "domcontentloaded"
    wait_selectors: Sequence[str] | None = None
    wait_text: Sequence[str] | None = None
    network_idle: bool = False
    timeout_ms: int = 45000
    retries: int = 3
    backoff_base: float = 1.0
    headless: bool = True
    user_agent: str | None = None
    viewport: dict[str, int] | None = None
    extra_headers: dict[str,str] | None = None
    consent: bool = True
    scroll_rounds: int = 0

async def fetch_page(opts: FetchOptions) -> str
async def fetch_page_with_hooks(opts: FetchOptions, hooks: FetchHooks) -> FetchResult
```

```python
@dataclass
class FetchHooks:
    on_response: Callable[[Response, Page, list[dict]], None] | None = None
    on_console: Callable[[ConsoleMessage, Page, list[dict]], None] | None = None
    on_request: Callable[[Request], None] | None = None
    on_page_ready: Callable[[Page], None] | None = None
    before_return: Callable[[Page, dict], None] | None = None
    on_error: Callable[[Exception, int], None] | None = None

@dataclass
class FetchResult:
    html: str
    responses: list[dict]
    console: list[dict]
    meta: dict[str, Any]
```

### Standard Fetch (HTML only)

```python
html = await fetch_page(FetchOptions(
    url="https://www.flashscore.com/football/",
    wait_selectors=[".event__match"],
    scroll_rounds=2,
))
```

### Erweiterte Fetch mit Hooks

```python
responses_capture: list[dict] = []

def on_resp(resp, page, acc):
    if "application/json" in (resp.headers.get("content-type") or "").lower():
        acc.append({"url": resp.url, "status": resp.status})

hooks = FetchHooks(on_response=on_resp)
result = await fetch_page_with_hooks(
    FetchOptions(url="https://www.courtside1891.basketball/games", timeout_ms=120_000, retries=2),
    hooks
)
print(len(result.responses), "JSON/other responses erfasst")
```

### Retry & Backoff

Beide Fetch-Varianten verwenden exponentielles Backoff (`backoff_base`, Verdopplung bis max 8s + Jitter). Fehler nach Ausschöpfung → `PlaywrightFetchError`.

### Consent Handling

`accept_consent(page)` versucht mehrere gängige Button-Muster (Internationalisierung berücksichtigt: *Accept*, *Agree*, *Alle akzeptieren*). Fehler werden unterdrückt, Skript läuft weiter.

### Scroll / Lazy Load

Einfacher Mechanismus via `scroll_rounds` (mehrfaches `mouse.wheel`). Komplexeres Infinite-Scrolling für spezielle Seiten steht als Utility `infinite_scroll(page, max_time_ms=..., idle_rounds=...)` zur Verfügung.

### Courtside Migration Beispiel

Der frühere `courtside_scraper` enthielt ~250 Zeilen Playwright-Steuerlogik. Er nutzt jetzt:

1. Hooks zum Erfassen relevanter JSON-Endpunkte (`fixture`, `game`, `schedule`).
2. Post-Verarbeitung (DOM + `__NEXT_DATA__` + Netzwerk JSON Fallback) auf Basis des resultierenden HTML & Response-Payloads.

### Hook Rezepte (Patterns)

| Ziel | Hook Kombination | Notizen |
|------|------------------|---------|
| Netzwerk JSON sammeln | `on_response` | Filter auf `content-type` + Keyword im URL |
| Console Fehler Monitoring | `on_console` | Logging-Level anpassbar |
| Selektive Request Blockade | `on_request` | `if any(ad in req.url for ad in ["analytics","ads"]) : req.abort()` |
| Später DOM-Mutate vor Rückgabe | `before_return` | Meta erweitern (`meta['extracted']=...`) |
| Schritt nach Navigation (Scrolling, Click) | `on_page_ready` | Kann `asyncio.create_task(...)` nutzen |
| Metriken bei Fehlern | `on_error` | Retry Versuch & Ausnahme-Typ taggen |

### Testabdeckung

Unit Tests (`tests/unit/test_playwright_utils*.py`) mocken `async_playwright` und prüfen:

- Erfolgreiche HTML Rückgabe
- Retry Verhalten bei Fehlern
- Hook-Akkumulation (Responses + Console)

### Empfehlungen

| Use Case | Funktion |
|----------|----------|
| Schneller statischer HTML Snapshot | `fetch_page` |
| Event-getriebene dynamische Seite | `fetch_page_with_hooks` |
| Netzwerk JSON extrahieren | Hooks (`on_response`) + Parser (`parse_captured_json`) |
| Komplexes zweistufiges Enrichment (Detailseiten) | Erst Hooks + DOM, dann manuell `_enrich_from_game_pages` |

### Erweiterungspotenzial

- Headless Mode Toggle via global Settings
- Persistente Browser-Reuse (Pooling) um Startup-Kosten zu senken
- Structured Tracing (Span pro Attempt) in `meta`
- Adaptive Wait Strategie (wenn Selektoren nicht erscheinen → dynamische Backoff Verlängerung)

---

## 🧪 Teststruktur Konsolidierung

Die Tests wurden refaktoriert:

- Zentrale Fixtures in `tests/conftest.py` (Pfad-Setup, HTML Samples, Mapper)
- Parametrisierte Tests statt manueller Loops
- Playwright Utility Tests isolieren Retry/Hook Logik mit Mocks

Konventionen:

- Unit Tests: reine Logik / Parsing / Utilities
- Integration Tests: End-to-End Pfade (Datenfluss, Orchestrator)
- Keine realen Netzwerkaufrufe in Unit Ebene – Playwright & HTTP via Mocks

---
