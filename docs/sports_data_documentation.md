# Sports Data Analytics Platform

## 🏟️ Overview

A comprehensive, production-ready sports data collection and analytics platform built with Python, PostgreSQL, and modern web technologies. Supports football, basketball, and American football with extensible architecture for additional sports.

## 🚀 Key Features

### Data Collection
- **Multi-source API Integration**: Football-data.org, Betfair, and other sports APIs
- **Advanced Web Scraping**: Transfermarkt, Flashscore, betting sites
- **Anti-detection Mechanisms**: Undetected Chrome, proxy rotation, header randomization
- **Rate Limiting & Error Handling**: Automatic retry logic with exponential backoff
- **Real-time & Scheduled Collection**: Live scores, periodic player/team updates

### Database & Storage
- **Sport-agnostic Schema**: Unified structure for football, basketball, American football
- **Historical Data Tracking**: Transfers, contracts, season statistics, match history
- **Flexible Data Storage**: JSONB fields for custom attributes and external API IDs
- **Performance Optimized**: Strategic indexing and query optimization
- **Data Validation**: Pydantic models for type safety and validation

### Analytics & Machine Learning
- **Player Performance Analysis**: 
  - Individual performance metrics and trends
  - Peer comparison within age groups and positions
  - Market value predictions
  - Career trajectory forecasting
- **Match Prediction Models**:
  - Team form analysis (last 5-10 games)
  - Head-to-head historical performance
  - Home/away advantage calculations
  - ML-powered outcome predictions
- **League Analytics**:
  - Comprehensive standings analysis
  - Goal scoring patterns and trends
  - Team efficiency metrics
  - Competitive balance indicators
- **Transfer Market Analysis**:
  - Fee trends by position and age
  - Market inflation tracking
  - Transfer success rate analysis

### Reporting & Visualization
- **Automated Report Generation**: HTML/PDF player and league reports
- **Interactive Dashboards**: Plotly-powered visualizations
- **Performance Metrics**: Real-time KPIs and statistics
- **Export Capabilities**: CSV, JSON, and structured data exports

### API & Integration
- **RESTful API**: FastAPI with automatic OpenAPI documentation
- **Real-time Endpoints**: Live match data and predictions
- **Webhook Support**: Event-driven data updates
- **Authentication & Rate Limiting**: Secure API access controls
- **CORS Support**: Cross-origin resource sharing for web clients

### Production Features
- **Containerized Deployment**: Docker and Docker Compose setup
- **Monitoring & Metrics**: Prometheus metrics with Grafana dashboards
- **Health Checks**: Comprehensive system health monitoring
- **Background Jobs**: Celery task queue for async processing
- **Structured Logging**: JSON logging with correlation IDs
- **Auto-scaling Ready**: Horizontal scaling capabilities

## 🛠️ Technology Stack

### Backend
- **Python 3.09**: Core application language
- **FastAPI**: Modern, fast web framework
- **PostgreSQL 15**: Primary database with JSONB support
- **Redis**: Caching and message broker
- **Celery**: Background task processing

### Data Collection
- **aiohttp**: Async HTTP client for API calls
- **Selenium**: Web browser automation
- **Playwright**: Modern browser automation
- **BeautifulSoup**: HTML parsing
- **CloudScraper**: Cloudflare bypass

### Analytics & ML
- **pandas**: Data manipulation and analysis
- **scikit-learn**: Machine learning algorithms
- **statsmodels**: Statistical modeling
- **numpy**: Numerical computations

### Monitoring & Deployment
- **Docker**: Containerization
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Supervisor**: Process management

## 📦 Installation & Setup

### Prerequisites
- Python 3.09
- Docker & Docker Compose
- PostgreSQL 15 (if not using Docker)
- Redis (if not using Docker)

### Quick Start with Docker

1. **Clone the repository and setup environment:**
```bash
git clone <repository-url>
cd sports-data-platform
cp .env.example .env
# Edit .env with your API keys and configuration
```

2. **Build and start all services:**
```bash
docker-compose up -d
```

3. **Initialize the database:**
```bash
docker-compose exec api python -c "
import asyncio
from your_main_app import DatabaseManager, DatabaseConfig
async def init_db():
    db = DatabaseManager(DatabaseConfig())
    await db.initialize()
    print('Database initialized')
asyncio.run(init_db())
"
```

4. **Access the services:**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Grafana Dashboard: http://localhost:3000 (admin/admin)
- Prometheus Metrics: http://localhost:9090

### Manual Installation

1. **Setup Python environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Setup databases:**
```bash
# PostgreSQL
createdb sportsdata
psql sportsdata < schema.sql

# Redis (start service)
redis-server
```

3. **Environment configuration:**
```bash
export DATABASE_URL="postgresql://user:pass@localhost/sportsdata"
export REDIS_URL="redis://localhost:6379"
export FOOTBALL_DATA_API_KEY="your_api_key_here"
```

4. **Start the application:**
```bash
# API Server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Background Workers (separate terminals)
celery -A main.celery_app worker --loglevel=info
celery -A main.celery_app beat --loglevel=info
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/sportsdata
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
CORS_ORIGINS=["*"]

# External APIs
FOOTBALL_DATA_API_KEY=your_football_data_api_key
BETFAIR_API_KEY=your_betfair_api_key

# Features
SCRAPING_ENABLED=true
SCRAPING_INTERVAL_MINUTES=30
ANALYTICS_ENABLED=true
MODEL_UPDATE_INTERVAL_HOURS=24
METRICS_ENABLED=true

# Logging
LOG_LEVEL=INFO

# Security
API_KEY=your_secure_api_key
```

### Database Schema

The application automatically creates the following main tables:
- `sports`, `countries`, `leagues`, `teams`, `venues`
- `players`, `positions`, `player_contracts`, `transfers`
- `matches`, `match_events`, `match_player_stats`
- `odds`, `bookmakers`, `season_player_stats`

## 📡 API Usage

### Authentication
```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/...
```

### Key Endpoints

#### Player Analysis
```bash
POST /api/v1/players/{player_id}/analyze
{
  "season": "2024-25",
  "include_predictions": true
}
```

#### Match Prediction
```bash
POST /api/v1/matches/predict
{
  "home_team_id": 1,
  "away_team_id": 2,
  "match_date": "2024-12-01T15:00:00Z"
}
```

#### League Analytics
```bash
GET /api/v1/leagues/{league_id}/analytics?season=2024-25
```

#### Trigger Scraping
```bash
POST /api/v1/scraping/trigger?scraper_name=transfermarkt
```

#### System Status
```bash
GET /api/v1/system/status
GET /health
GET /metrics
```

## 🔍 Data Sources

### Supported APIs
- **Football-data.org**: Match data, team info, player stats
- **Betfair Exchange**: Live betting odds and market data
- **Custom APIs**: Extensible for additional sports data providers

### Web Scraping Sources
- **Transfermarkt**: Player valuations, transfers, detailed stats
- **Flashscore**: Live scores and match updates
- **Betting Sites**: Odds comparison and market analysis
- **League Websites**: Official statistics and fixtures

## 📊 Analytics Examples

### Player Performance Report
```python
# Analyze a player's performance
analysis = await analytics_engine.analyze_player_performance(
    player_id=123,
    season="2024-25"
)

# Results include:
# - Performance summary (goals, assists, minutes)
# - Trend analysis (improving/declining form)
# - Peer comparison (percentile ranking)
# - Future predictions (next season forecast)
```

### Match Prediction
```python
# Predict match outcome
prediction = await analytics_engine.predict_match_outcome(
    home_team_id=1,
    away_team_id=2
)

# Results include:
# - Win/draw/loss probabilities
# - Confidence level
# - Key factors (form, h2h, home advantage)
```

### League Dashboard
```python
# Generate league analytics
dashboard = await report_generator.generate_league_dashboard(
    league_id=1,
    season="2024-25"
)

# Creates interactive HTML dashboard with:
# - Current standings visualization
# - Goals analysis charts
# - Team form trends
# - Statistical insights
```

## 🔄 Background Tasks

The platform runs several background processes:

### Scraping Jobs
- **Live Scores**: Every 30 seconds during match days
- **Player Data**: Daily at 2:00 AM
- **Transfer Updates**: Every 6 hours
- **Odds Updates**: Every 5 minutes

### Analytics Jobs
- **Model Training**: Daily model updates
- **Report Generation**: Automated daily/weekly reports
- **Cache Refresh**: Performance metric updates

### System Maintenance
- **Health Checks**: Continuous system monitoring
- **Log Rotation**: Automated log management
- **Metric Collection**: Real-time system metrics

## 📈 Monitoring & Metrics

### Prometheus Metrics
- `api_requests_total`: API request counter
- `scraping_jobs_total`: Scraping job counter
- `database_connections_active`: DB connection gauge
- `api_response_time_seconds`: Response time histogram
- `prediction_accuracy_percentage`: ML model accuracy

### Health Checks
- Database connectivity
- Redis connectivity
- External API availability
- System resource usage
- Background task status

### Grafana Dashboards
- API Performance Dashboard
- System Resource Dashboard
- Data Collection Dashboard
- ML Model Performance Dashboard

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=src tests/
```

### Test Data
```bash
# Load test fixtures
python scripts/load_test_data.py

# Run scraping tests
python scripts/test_scrapers.py
```

## 🔒 Security Considerations

### API Security
- API key authentication
- Rate limiting per endpoint
- Input validation and sanitization
- CORS configuration

### Data Protection
- No personal data storage beyond public sports info
- Secure external API key storage
- Database connection encryption
- Audit logging for data access

### Scraping Ethics
- Respect robots.txt files
- Implement reasonable delays
- Monitor for IP blocking
- Use official APIs when available

## 🚀 Deployment

### Docker Production Deployment
```bash
# Build production image
docker build -t sports-data-api:latest .

# Deploy with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment
```yaml
# Basic k8s deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sports-data-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sports-data-api
  template:
    metadata:
      labels:
        app: sports-data-api
    spec:
      containers:
      - name: api
        image: sports-data-api:latest
        ports:
        - containerPort: 8000
```

### Scaling Considerations
- **Horizontal Scaling**: Multiple API instances behind load balancer
- **Database Scaling**: Read replicas for analytics queries
- **Cache Scaling**: Redis clustering for high availability
- **Background Jobs**: Multiple Celery workers

## 🛣️ Roadmap

### Phase 1 (Current)
- ✅ Core database schema
- ✅ API integration framework
- ✅ Web scraping pipeline
- ✅ Basic analytics engine
- ✅ REST API endpoints

### Phase 2 (Next 3 months)
- 🔄 Advanced ML models (neural networks)
- 🔄 Real-time data streaming
- 🔄 Mobile app API
- 🔄 Enhanced visualization dashboard
- 🔄 Multi-language support

### Phase 3 (6-12 months)
- 📋 Additional sports (tennis, hockey)
- 📋 Fantasy sports integration
- 📋 Social features and user accounts
- 📋 Advanced betting analytics
- 📋 AI-powered insights

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Run code formatting
black src/
isort src/

# Type checking
mypy src/
```

### Code Style
- Use Black for code formatting
- Follow PEP 8 guidelines
- Add type hints for all functions
- Write docstrings for public APIs
- Maintain test coverage >90%

### Pull Request Process
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

### Documentation
- API Documentation: `/docs` endpoint
- Architecture Overview: `docs/architecture.md`
- Deployment Guide: `docs/deployment.md`

### Community
- GitHub Issues: Bug reports and feature requests
- Discussions: Architecture and implementation questions
- Wiki: Community-contributed guides and examples

### Commercial Support
For commercial licensing, enterprise features, or professional support, contact: [your-email@domain.com]

---

**Built with ❤️ for the sports analytics community**