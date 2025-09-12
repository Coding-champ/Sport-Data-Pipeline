# Sport Data Pipeline - Setup Guide

## 📋 Systemvoraussetzungen und Installation

### Mindestanforderungen

#### Hardware
- **CPU**: 4 Cores (empfohlen: 8+ Cores für Produktionsumgebung)
- **RAM**: 8 GB (empfohlen: 16+ GB für Analytics-Workloads)
- **Storage**: 50 GB freier Speicherplatz (SSD empfohlen)
- **Netzwerk**: Stabile Internetverbindung (min. 10 Mbit/s)

#### Software-Voraussetzungen
- **Python**: 3.09+ (empfohlen: 3.10+)
- **PostgreSQL**: 15+ mit JSONB-Support
- **Redis**: 6.0+ für Caching und Message Broker
- **Docker**: 20.10+ (optional, aber empfohlen)
- **Docker Compose**: 2.0+ (für Container-Setup)
- **Git**: Für Repository-Verwaltung

#### Betriebssystem-Support
- ✅ **Linux**: Ubuntu 20.04+, CentOS 8+, Debian 11+
- ✅ **macOS**: macOS 11+ (Intel/Apple Silicon)
- ✅ **Windows**: Windows 10/11 mit WSL2 empfohlen

## 🐋 Setup-Szenario 1: Docker Compose (Empfohlen für Entwicklung)

### Schnellstart mit Docker
Dies ist der einfachste Weg, um die gesamte Infrastruktur zu starten.

#### Schritt 1: Repository klonen
```bash
git clone https://github.com/Coding-champ/Sport-Data-Pipeline.git
cd Sport-Data-Pipeline
```

#### Schritt 2: Umgebungsvariablen konfigurieren
```bash
# Beispiel .env Datei erstellen
cp .env.example .env

# .env bearbeiten (siehe Konfigurationsabschnitt)
nano .env
```

#### Schritt 3: Services starten
```bash
# Alle Services im Hintergrund starten
docker-compose up -d

# Services mit Logs verfolgen
docker-compose up
```

#### Schritt 4: Datenbank initialisieren
```bash
# Datenbank-Schema erstellen
docker-compose exec api python -c "
import asyncio
from src.database.manager import DatabaseManager
from src.core.config import Settings

async def init_db():
    settings = Settings()
    db = DatabaseManager(settings)
    await db.initialize()
    print('Database initialized successfully')

asyncio.run(init_db())
"
```

#### Schritt 5: Zugriff auf Services
- **API Dokumentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Prometheus Metriken**: http://localhost:9090
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Redis Commander**: http://localhost:8081

### Docker Services im Detail

#### docker-compose.yml Überblick
```yaml
version: '3.8'
services:
  # PostgreSQL Datenbank
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: sportsdata
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis für Caching
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # FastAPI Application
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/sportsdata
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # Celery Worker für Background Tasks
  worker:
    build: .
    command: celery -A main.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/sportsdata
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # Celery Beat für Scheduled Tasks
  scheduler:
    build: .
    command: celery -A main.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/sportsdata
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # Prometheus für Monitoring
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  # Grafana für Dashboards
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
```

### Docker-spezifische Befehle
```bash
# Services stoppen
docker-compose down

# Services neu builden
docker-compose build

# Logs anzeigen
docker-compose logs -f api
docker-compose logs -f worker

# In Container einsteigen
docker-compose exec api bash
docker-compose exec postgres psql -U postgres -d sportsdata

# Einzelne Services starten/stoppen
docker-compose start api
docker-compose stop worker

# Volumes löschen (Daten gehen verloren!)
docker-compose down -v
```

## 🔧 Setup-Szenario 2: Manuelle Installation (Produktionsumgebung)

### Schritt 1: System-Dependencies installieren

#### Ubuntu/Debian
```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Python 3.09+ installieren
sudo apt install python3.10 python3.10-venv python3.10-dev python3-pip -y

# PostgreSQL installieren
sudo apt install postgresql-15 postgresql-contrib-15 -y

# Redis installieren
sudo apt install redis-server -y

# Weitere Dependencies
sudo apt install git curl wget build-essential libpq-dev -y

# Chrome für Web Scraping (optional)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable -y
```

#### CentOS/RHEL
```bash
# System aktualisieren
sudo dnf update -y

# Python 3.09+ installieren
sudo dnf install python3.10 python3.10-pip python3.10-devel -y

# PostgreSQL installieren
sudo dnf install postgresql15-server postgresql15 -y
sudo postgresql-15-setup initdb
sudo systemctl enable postgresql-15
sudo systemctl start postgresql-15

# Redis installieren
sudo dnf install redis -y
sudo systemctl enable redis
sudo systemctl start redis

# Development Tools
sudo dnf groupinstall "Development Tools" -y
sudo dnf install libpq-devel -y
```

#### macOS
```bash
# Homebrew installieren (falls nicht vorhanden)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Dependencies installieren
brew install python@3.10 postgresql@15 redis git

# Services starten
brew services start postgresql@15
brew services start redis

# Chrome installieren
brew install --cask google-chrome
```

### Schritt 2: Datenbanken konfigurieren

#### PostgreSQL Setup
```bash
# PostgreSQL Service starten
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Datenbank und User erstellen
sudo -u postgres psql -c "CREATE DATABASE sportsdata;"
sudo -u postgres psql -c "CREATE USER sportsuser WITH PASSWORD 'securepassword';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sportsdata TO sportsuser;"

# PostgreSQL für Netzwerk-Verbindungen konfigurieren
sudo nano /etc/postgresql/15/main/postgresql.conf
# Ändern: listen_addresses = 'localhost'

sudo nano /etc/postgresql/15/main/pg_hba.conf
# Hinzufügen: host    sportsdata    sportsuser    127.0.0.1/32    md5

# PostgreSQL neu starten
sudo systemctl restart postgresql
```

#### Redis Setup
```bash
# Redis Service starten
sudo systemctl start redis
sudo systemctl enable redis

# Redis Konfiguration anpassen (optional)
sudo nano /etc/redis/redis.conf
# Empfohlene Änderungen:
# maxmemory 2gb
# maxmemory-policy allkeys-lru

# Redis neu starten
sudo systemctl restart redis
```

### Schritt 3: Python-Umgebung einrichten
```bash
# Repository klonen
git clone https://github.com/Coding-champ/Sport-Data-Pipeline.git
cd Sport-Data-Pipeline

# Virtual Environment erstellen
python3.10 -m venv venv
source venv/bin/activate  # Linux/macOS
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install --upgrade pip
pip install -r requirements.txt

# Development Dependencies (optional)
pip install -r requirements-dev.txt
```

### Schritt 4: Umgebungsvariablen konfigurieren
```bash
# .env Datei erstellen
cp .env.example .env

# .env bearbeiten
nano .env
```

### Schritt 5: Datenbank-Schema einrichten
```bash
# Schema-Dateien ausführen
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -f schema.sql
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -f sports_database_schema.sql

# Oder über Python
python -c "
import asyncio
from src.database.manager import DatabaseManager
from src.core.config import Settings

async def init_db():
    settings = Settings()
    db = DatabaseManager(settings)
    await db.initialize()
    print('Database initialized')

asyncio.run(init_db())
"
```

### Schritt 6: Services starten

#### API Server
```bash
# Development Server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production Server
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Background Workers (separate Terminals)
```bash
# Terminal 1: Celery Worker
celery -A main.celery_app worker --loglevel=info --concurrency=4

# Terminal 2: Celery Beat Scheduler
celery -A main.celery_app beat --loglevel=info

# Terminal 3: Flower für Celery Monitoring (optional)
celery -A main.celery_app flower --port=5555
```

## 🛠️ Setup-Szenario 3: Entwicklungsumgebung

### IDE-Setup

#### VS Code Empfohlene Extensions
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "ms-python.mypy-type-checker",
    "bradlc.vscode-tailwindcss",
    "ms-vscode.vscode-json",
    "redhat.vscode-yaml"
  ]
}
```

#### VS Code Settings (.vscode/settings.json)
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "python.sortImports.args": ["--profile", "black"]
}
```

### Pre-commit Hooks Setup
```bash
# Pre-commit installieren
pip install pre-commit

# Hooks installieren
pre-commit install

# Hooks manuell ausführen
pre-commit run --all-files
```

### Development Tools Configuration (pyproject.toml)
```toml
[tool.black]
line-length = 100
target-version = ["py310"]

[tool.isort]
profile = "black"
line_length = 100
known_first_party = ["src"]

[tool.ruff]
line-length = 100
target-version = "py310"
select = [
  "E",   # pycodestyle errors
  "F",   # pyflakes
  "I",   # isort
  "UP",  # pyupgrade
]
```

### Windows PowerShell Setup
Für Windows-Entwickler gibt es einen automatisierten Setup-Script:
```powershell
# Automatisiertes Setup (empfohlen)
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1

# Was das Script macht:
# - Virtual Environment erstellen
# - Dependencies installieren
# - Playwright Browser installieren
# - Development Tools konfigurieren
# - Pre-commit Hooks einrichten
```

### Nützliche Development Scripts
Das Repository enthält hilfreiche Scripts im `scripts/` Verzeichnis:
```bash
# Database Diagnostics
python scripts/db_diagnostics.py

# API Health Check
python scripts/api_health_smoke.py

# Scraper Testing
python scripts/test_scraper.py
python scripts/test_courtside_scraper.py

# Development Debugging
python scripts/simple_debug.py
python scripts/courtside_debug.py
```

### Testing Setup
```bash
# Tests ausführen
pytest

# Mit Coverage
pytest --cov=src tests/

# Spezifische Test-Kategorie
pytest tests/unit/
pytest tests/integration/

# Einzelnen Test ausführen
pytest tests/unit/test_analytics.py::test_player_analysis
```

### Debugging Setup
```bash
# Debug-Modus für API
export DEBUG=true
uvicorn main:app --reload --log-level debug

# Interaktive Python-Session mit App-Context
python -c "
from main import app
from src.database.manager import DatabaseManager
# Debugging-Code hier...
"
```

## 🔧 Konfiguration und Umgebungsvariablen

### Vollständige .env Datei-Vorlage
```bash
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
DATABASE_URL=postgresql://sportsuser:securepassword@localhost:5432/sportsdata
DATABASE_POOL_SIZE=20
DATABASE_POOL_MIN_SIZE=10
DATABASE_POOL_MAX_SIZE=20

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================
REDIS_URL=redis://localhost:6379
REDIS_CACHE_TTL=3600

# =============================================================================
# API CONFIGURATION
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Security
API_KEY=your_secure_api_key_here_min_32_chars
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# =============================================================================
# EXTERNAL API KEYS
# =============================================================================
FOOTBALL_DATA_API_KEY=your_football_data_org_api_key
BETFAIR_APPLICATION_KEY=your_betfair_app_key
BETFAIR_USERNAME=your_betfair_username
BETFAIR_PASSWORD=your_betfair_password

# =============================================================================
# SCRAPING CONFIGURATION
# =============================================================================
SCRAPING_ENABLED=true
SCRAPING_INTERVAL_MINUTES=30
SCRAPING_DELAY_RANGE_MIN=1
SCRAPING_DELAY_RANGE_MAX=3
SCRAPING_MAX_RETRIES=3
SCRAPING_TIMEOUT=30
SCRAPING_USE_PROXY=false
SCRAPING_ANTI_DETECTION=true
SCRAPING_SCREENSHOT_ON_ERROR=true

# Specific Scraping Intervals (seconds)
LIVE_UPDATE_INTERVAL_SECONDS=30
REGULAR_UPDATE_INTERVAL_SECONDS=300
DAILY_UPDATE_INTERVAL_SECONDS=86400
SCRAPING_LIVE_SCORES_INTERVAL_SECONDS=30
SCRAPING_ODDS_INTERVAL_SECONDS=300
SCRAPING_PLAYER_DAILY_CHECK_INTERVAL_SECONDS=3600

# =============================================================================
# ANALYTICS & ML CONFIGURATION
# =============================================================================
ANALYTICS_ENABLED=true
MODEL_UPDATE_INTERVAL_HOURS=24
ANALYTICS_CACHE_TTL=1800
ML_MODEL_PATH=./models/
FEATURE_ENGINEERING_ENABLED=true

# =============================================================================
# MONITORING & METRICS
# =============================================================================
ENABLE_MONITORING=true
ENABLE_METRICS=true
METRICS_PORT=8008
PROMETHEUS_ENABLED=true

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=./logs/app.log
LOG_ROTATION_SIZE=100MB
LOG_RETENTION_DAYS=30

# =============================================================================
# ENVIRONMENT & DEPLOYMENT
# =============================================================================
ENVIRONMENT=development  # development | staging | production
DEBUG=false
TESTING=false

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_ALWAYS_EAGER=false

# =============================================================================
# FEATURE FLAGS
# =============================================================================
ENABLE_API=true
ENABLE_DATA_COLLECTION=true
ENABLE_ANALYTICS=true
ENABLE_BACKGROUND_TASKS=true
ENABLE_WEB_UI=false

# =============================================================================
# CHROME/SELENIUM CONFIGURATION
# =============================================================================
CHROME_BINARY_PATH=/usr/bin/google-chrome
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
HEADLESS_BROWSER=true
BROWSER_WINDOW_SIZE=1920,1080
```

### Umgebungsspezifische Konfigurationen

#### Development (.env.development)
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ORIGINS=["*"]
API_KEY=""  # Keine Authentifizierung in Development
SCRAPING_DELAY_RANGE_MIN=0.5
SCRAPING_DELAY_RANGE_MAX=1.5
CELERY_TASK_ALWAYS_EAGER=true  # Synchrone Ausführung für Tests
```

#### Staging (.env.staging)
```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
API_KEY=staging_api_key_here
CORS_ORIGINS=["https://staging.yourdomain.com"]
DATABASE_URL=postgresql://user:pass@staging-db:5432/sportsdata
SCRAPING_ENABLED=true
ANALYTICS_ENABLED=true
```

#### Production (.env.production)
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
API_KEY=super_secure_production_key
CORS_ORIGINS=["https://yourdomain.com"]
DATABASE_URL=postgresql://user:pass@prod-db:5432/sportsdata
DATABASE_POOL_SIZE=50
API_WORKERS=8
CELERY_WORKER_CONCURRENCY=8
RATE_LIMIT_REQUESTS_PER_MINUTE=30
```

## 🚀 Produktions-Deployment

### Setup-Szenario 4: Produktions-Deployment mit Docker

#### docker-compose.prod.yml
```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - --api.dashboard=true
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik/certificates:/certificates

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 512M

  api:
    build: 
      context: .
      dockerfile: Dockerfile.prod
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    labels:
      - traefik.enable=true
      - traefik.http.routers.api.rule=Host(`api.yourdomain.com`)
      - traefik.http.routers.api.tls=true
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  worker:
    build: 
      context: .
      dockerfile: Dockerfile.prod
    command: celery -A main.celery_app worker --loglevel=warning --concurrency=4
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G

volumes:
  postgres_data:
  redis_data:
```

#### Dockerfile.prod
```dockerfile
FROM python:3.10-slim

# System-Dependencies installieren
RUN apt-get update && apt-get install -y \
    postgresql-client \
    wget \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Chrome installieren
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Working Directory
WORKDIR /app

# Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application Code
COPY . .

# Non-root User
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health Check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Deployment-Befehle
```bash
# Production Build & Deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Database Migration
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Monitoring
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml ps
```

## 🏥 Setup-Szenario 5: Kubernetes Deployment

### Kubernetes Manifests

#### deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sport-data-api
  labels:
    app: sport-data-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sport-data-api
  template:
    metadata:
      labels:
        app: sport-data-api
    spec:
      containers:
      - name: api
        image: sport-data-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: sport-data-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: sport-data-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: sport-data-api-service
spec:
  selector:
    app: sport-data-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

#### configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sport-data-config
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  SCRAPING_ENABLED: "true"
  ANALYTICS_ENABLED: "true"
```

### Deployment-Befehle
```bash
# Secrets erstellen
kubectl create secret generic sport-data-secrets \
  --from-literal=database-url="postgresql://user:pass@postgres:5432/db" \
  --from-literal=redis-url="redis://redis:6379"

# Deployment erstellen
kubectl apply -f k8s/

# Status prüfen
kubectl get pods -l app=sport-data-api
kubectl get services
kubectl logs -l app=sport-data-api -f
```

## 🔍 Troubleshooting

### Häufige Probleme und Lösungen

#### Database Connection Issues
```bash
# PostgreSQL-Verbindung testen
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "SELECT 1;"

# PostgreSQL-Status prüfen
sudo systemctl status postgresql

# PostgreSQL-Logs prüfen
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

#### Redis Connection Issues
```bash
# Redis-Verbindung testen
redis-cli ping

# Redis-Status prüfen
sudo systemctl status redis

# Redis-Memory prüfen
redis-cli info memory
```

#### Web Scraping Issues
```bash
# Chrome Installation prüfen
google-chrome --version

# ChromeDriver Installation
which chromedriver
chromedriver --version

# Selenium Test
python -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get('https://google.com')
print('Selenium working:', driver.title)
driver.quit()
"
```

#### API Issues
```bash
# API Health Check
curl -X GET http://localhost:8000/health

# API Logs mit Debug Level
uvicorn main:app --log-level debug

# Dependency Check
pip check

# Requirements aktualisieren
pip install -r requirements.txt --upgrade
```

#### Performance Issues
```bash
# Database Performance
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "
SELECT schemaname, tablename, attname, n_distinct, correlation 
FROM pg_stats 
WHERE schemaname = 'public' 
ORDER BY n_distinct DESC;
"

# Redis Performance
redis-cli --latency -h localhost -p 6379

# System Resources
htop
free -h
df -h
```

### Logging und Debugging

#### Log-Locations
```bash
# Application Logs
tail -f logs/app.log

# PostgreSQL Logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log

# Redis Logs
sudo tail -f /var/log/redis/redis-server.log

# Nginx Logs (wenn verwendet)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

#### Debug Commands
```bash
# Database Diagnostics
python -m scripts.db_diagnostics

# Scraper Test
python -c "
from src.data_collection.scrapers.flashscore_scraper import FlashscoreScraper
scraper = FlashscoreScraper()
# Test scraper functionality
"

# Analytics Test
python -c "
from src.analytics.engine import AnalyticsEngine
# Test analytics functionality
"
```

### Backup und Recovery

#### Database Backup
```bash
# Backup erstellen
pg_dump postgresql://sportsuser:securepassword@localhost:5432/sportsdata > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup wiederherstellen
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata < backup_20241201_120000.sql

# Automated Backup Script
cat > backup_script.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/sportsdata"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump postgresql://sportsuser:securepassword@localhost:5432/sportsdata | gzip > $BACKUP_DIR/backup_$DATE.sql.gz
# Alte Backups löschen (älter als 7 Tage)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete
EOF

chmod +x backup_script.sh

# Cronjob für tägliche Backups
echo "0 2 * * * /path/to/backup_script.sh" | crontab -
```

## 📊 Monitoring und Wartung

### System Health Monitoring
```bash
# System-Status prüfen
curl http://localhost:8000/health

# Detaillierte System-Metriken
curl http://localhost:8008/metrics

# Database Connection Pool Status
python -c "
from src.database.manager import DatabaseManager
from src.core.config import Settings
import asyncio

async def check_pool():
    settings = Settings()
    db = DatabaseManager(settings)
    await db.initialize()
    print(f'Pool size: {db.pool.get_size()}')
    print(f'Pool available: {db.pool.get_available_size()}')

asyncio.run(check_pool())
"
```

### Performance Monitoring
```bash
# API Response Times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/v1/players

# Database Query Performance
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "
SELECT query, calls, total_time, mean_time, rows 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
"

# Redis Performance
redis-cli --latency-history -i 1
```

### Wartungs-Scripts
```bash
# Database Maintenance
cat > maintenance.sh << 'EOF'
#!/bin/bash
echo "Starting database maintenance..."

# Vacuum und Analyze
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "VACUUM ANALYZE;"

# Reindex
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "REINDEX DATABASE sportsdata;"

# Update Statistics
psql postgresql://sportsuser:securepassword@localhost:5432/sportsdata -c "ANALYZE;"

echo "Database maintenance completed."
EOF

chmod +x maintenance.sh

# Weekly Maintenance Cronjob
echo "0 3 * * 0 /path/to/maintenance.sh" | crontab -
```

---

*Dieser Setup Guide wird kontinuierlich erweitert und aktualisiert basierend auf Community-Feedback und neuen Features.*