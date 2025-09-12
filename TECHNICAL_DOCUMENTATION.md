# Sport Data Pipeline - Technische Dokumentation

## 🏗️ Softwarearchitektur und Modulstruktur

### Überblick
Die Sport Data Pipeline ist eine skalierbare, produktionstaugliche Plattform für die Sammlung, Analyse und Bereitstellung von Sportdaten. Das System folgt einer modularen Architektur mit klarer Trennung der Verantwortlichkeiten.

### Architektur-Diagramm
```
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
          │                      │                      │
    ┌─────▼─────┐        ┌──────▼──────┐        ┌─────▼─────┐
    │Analytics  │        │Data Collection│       │Background │
    │  Engine   │        │ Orchestrator │       │   Tasks   │
    └─────┬─────┘        └──────┬──────┘        └─────┬─────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                    ┌────────────▼────────────┐
                    │   Database Manager      │
                    │   (PostgreSQL + Redis)  │
                    └─────────────────────────┘
```

### Modulstruktur

```
src/
├── __init__.py                    # Haupt-Package
├── api/                          # FastAPI Anwendungsschicht
│   ├── __init__.py
│   ├── main.py                   # FastAPI App Configuration
│   ├── dependencies.py           # Dependency Injection
│   ├── models.py                 # Pydantic Request/Response Models
│   ├── router.py                 # Router Aggregation
│   └── endpoints/                # API Endpoints (modulare Router)
│       ├── __init__.py
│       ├── players.py            # Spieler-Endpoints
│       ├── matches.py            # Spiel-Endpoints
│       ├── teams.py              # Team-Endpoints
│       ├── odds.py               # Wett-Endpoints
│       ├── analytics.py          # Analytics-Endpoints
│       └── system.py             # System/Health-Endpoints
├── core/                         # Zentrale Konfiguration
│   ├── __init__.py
│   └── config.py                 # Pydantic Settings mit Env-Variablen
├── data_collection/              # Datensammlung
│   ├── __init__.py
│   ├── orchestrator.py          # Koordiniert alle Datensammler
│   ├── collectors/              # API-basierte Datensammler
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract Base Collector
│   │   ├── football_data_api_collector.py  # Football-data.org
│   │   └── betfair_odds_collector.py       # Betfair Exchange
│   └── scrapers/                # Web-Scraping Module
│       ├── __init__.py
│       ├── base.py              # Abstract Base Scraper
│       ├── scraping_orchestrator.py       # Scraper Koordination
│       ├── transfermarkt_scraper.py       # Transfermarkt
│       ├── fbref_scraper.py               # FBref Stats
│       ├── flashscore_scraper.py          # Flashscore Live
│       ├── bet365_scraper.py              # Bet365 Odds
│       ├── courtside_scraper.py           # Courtside Basketball
│       └── [weitere Scraper...]
├── analytics/                    # Machine Learning & Analytics
│   ├── __init__.py
│   ├── engine.py                # Analytics Engine
│   ├── models/                  # ML-Modelle
│   │   ├── __init__.py
│   │   ├── player_performance.py
│   │   ├── match_prediction.py
│   │   └── market_analysis.py
│   └── reports/                 # Report Generation
│       ├── __init__.py
│       ├── player_reports.py
│       └── league_reports.py
├── database/                     # Datenbankschicht
│   ├── __init__.py
│   ├── manager.py               # Database Manager
│   ├── schema.py                # SQLAlchemy Models
│   └── services/                # Data Access Layer
│       ├── __init__.py
│       ├── players.py           # Spieler-Services
│       ├── matches.py           # Spiel-Services
│       ├── teams.py             # Team-Services
│       └── odds.py              # Wett-Services
├── domain/                       # Domain Models
│   ├── __init__.py
│   ├── entities/                # Business Entities
│   └── value_objects/           # Value Objects
├── common/                       # Gemeinsame Utilities
│   ├── __init__.py
│   ├── http.py                  # HTTP Client mit Anti-Detection
│   ├── logging.py               # Strukturiertes Logging
│   └── exceptions.py            # Custom Exceptions
└── monitoring/                   # Monitoring & Metriken
    ├── __init__.py
    ├── metrics.py               # Prometheus Metriken
    └── health.py                # Health Checks
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
GET    /api/v1/odds/live                  # Live-Quoten
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
| **Live-Quoten** | 5 Minuten | Bet365, Betfair, BetExplorer |
| **Spielerstatistiken** | Täglich (2:00 AM) | FBref, Transfermarkt, WhoScored |
| **Transfers** | Alle 6 Stunden | Transfermarkt |
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
- ✅ **Live-Daten**: Echtzeit-Scores und Live-Quoten
- ✅ **Automatisierte Sammlung**: Celery-basierte Background Jobs
- ✅ **Fehlerbehandlung**: Retry-Logic mit exponential Backoff

#### Analytics & Machine Learning
- ✅ **Spieleranalyse**: Performance-Trends, Peer-Vergleiche
- ✅ **Spielvorhersagen**: ML-basierte Outcome-Prediction
- ✅ **Liga-Analytics**: Tabellenstände, Form-Analyse
- ✅ **Transfer-Analyse**: Marktwert-Entwicklung, Transfer-Erfolg
- ✅ **Report-Generation**: Automatisierte HTML/PDF-Reports

#### API & Integration
- ✅ **RESTful API**: FastAPI mit OpenAPI-Dokumentation
- ✅ **Echtzeit-Endpoints**: Live-Match-Daten und Predictions
- ✅ **Authentifizierung**: API-Key basierte Sicherheit
- ✅ **Rate Limiting**: Schutz vor Überlastung
- ✅ **CORS Support**: Web-Client Integration

#### Produktion & Monitoring
- ✅ **Containerisierung**: Docker & Docker Compose
- ✅ **Monitoring**: Prometheus Metriken
- ✅ **Health Checks**: Umfassendes System-Monitoring
- ✅ **Strukturiertes Logging**: JSON-Logs mit Korrelations-IDs

### 🔄 Aktuell in Entwicklung (nächste 3 Monate)

#### Erweiterte ML-Modelle
- 🔄 **Neural Networks**: Deep Learning für präzisere Vorhersagen
- 🔄 **Ensemble Methods**: Kombination mehrerer Modelle
- 🔄 **Feature Engineering**: Erweiterte statistische Features
- 🔄 **Model Versioning**: MLflow Integration

#### Real-time Streaming
- 🔄 **WebSocket API**: Echtzeit-Daten für Web-Clients
- 🔄 **Event Streaming**: Kafka für Event-driven Architecture
- 🔄 **Live Notifications**: Push-Benachrichtigungen
- 🔄 **Stream Processing**: Apache Kafka Streams

#### Enhanced Visualisation
- 🔄 **Interactive Dashboards**: Erweiterte Plotly-Dashboards
- 🔄 **Mobile-Responsive UI**: Progressive Web App
- 🔄 **Custom Report Builder**: Drag & Drop Report-Erstellung
- 🔄 **Data Export**: Erweiterte Export-Optionen (Excel, PowerBI)

#### Performance Optimierungen
- 🔄 **Database Sharding**: Horizontale Skalierung
- 🔄 **Caching Strategy**: Redis Cluster, CDN Integration
- 🔄 **Query Optimization**: Index-Optimierung, Query-Tuning
- 🔄 **API Gateway**: Load Balancing, API-Versionierung

### 📋 Geplante Features (6-12 Monate)

#### Zusätzliche Sportarten
- 📋 **Tennis**: ATP/WTA Tour Integration
- 📋 **Hockey**: NHL/European Hockey Integration
- 📋 **Baseball**: MLB Statistics Integration
- 📋 **eSports**: Gaming Tournament Data

#### Fantasy Sports Integration
- 📋 **Fantasy API**: Draft Kings/FanDuel Integration
- 📋 **Lineup Optimization**: ML-optimierte Team-Aufstellungen
- 📋 **Player Projections**: Fantasy Points Predictions
- 📋 **Contest Analysis**: ROI-Optimierung

#### Social Features
- 📋 **User Accounts**: Personalisierte Dashboards
- 📋 **Community Features**: Tipps, Kommentare, Bewertungen
- 📋 **Following System**: Experten und Teams folgen
- 📋 **Achievement System**: Gamification-Elemente

#### Advanced Betting Analytics
- 📋 **Arbitrage Detection**: Surebet-Finder
- 📋 **Value Bet Algorithm**: Mathematical Edge Detection
- 📋 **Bankroll Management**: Portfolio-Optimierung
- 📋 **Live Betting Signals**: Real-time Opportunity Alerts

#### AI-Powered Insights
- 📋 **Natural Language Generation**: Automated Match Reports
- 📋 **Computer Vision**: Video Analysis Integration
- 📋 **Sentiment Analysis**: Social Media Impact auf Quoten
- 📋 **Predictive Maintenance**: System-Health Vorhersagen

### 💡 Zukünftige Innovationen (12+ Monate)

#### Blockchain Integration
- 💡 **Smart Contracts**: Automatisierte Wett-Abwicklung
- 💡 **NFT Integration**: Digitale Sammelkarten/Momente
- 💡 **Decentralized Data**: Blockchain-basierte Datenverifizierung

#### Advanced AI
- 💡 **Large Language Models**: ChatGPT-Integration für Queries
- 💡 **Computer Vision**: Automatische Video-Analyse
- 💡 **Reinforcement Learning**: Adaptive Betting-Strategien

#### Mobile & IoT
- 💡 **Native Mobile Apps**: iOS/Android Apps
- 📋 **Wearable Integration**: Apple Watch/Fitness Tracker
- 💡 **Stadium IoT**: Direkte Venue-Datenintegration

#### Enterprise Features
- 💡 **White-Label Solutions**: Anpassbare Platform für Kunden
- 💡 **B2B API Marketplace**: Daten-as-a-Service
- 💡 **Regulatory Compliance**: GDPR, CCPA, Gaming-Regulierung

## 🔧 Konfiguration und Umgebungsvariablen

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

*Diese technische Dokumentation wird kontinuierlich aktualisiert und erweitert.*