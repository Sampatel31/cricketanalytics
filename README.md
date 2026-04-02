# Sovereign Cricket Analytics

## Phase 0: Foundation — Database + Config Setup

This repository contains the complete foundation layer for Sovereign Cricket Analytics.

### Project Structure

```
cricketanalytics/
├── alembic/                          # Database migrations
│   ├── versions/
│   │   ├── 001_initial_schema.py     # Core tables
│   │   ├── 002_enriched_balls.py     # Enriched balls table
│   │   └── 003_features_archetypes.py # Features & archetype tables
│   ├── env.py
│   └── script.py.mako
├── sovereign/
│   ├── config/
│   │   ├── settings.py               # Pydantic v2 settings
│   │   ├── weights.toml              # SPI weights per format
│   │   └── player_overrides.json
│   ├── db/
│   │   ├── connection.py             # Async SQLAlchemy engine
│   │   ├── models.py                 # 15 ORM tables
│   │   └── migrations.py             # Alembic wrappers
│   ├── registry/
│   │   └── models.py                 # Player registry Pydantic models
│   └── utils/
│       └── logger.py                 # structlog setup
├── scripts/
│   ├── init_db.sql                   # PostgreSQL initialisation
│   └── setup_redis.sh                # Redis setup
├── tests/
│   ├── conftest.py
│   ├── test_config/test_settings.py
│   ├── test_db/test_models.py
│   └── test_registry/test_models.py
├── .env.example                      # Environment template
├── .env.test                         # Test environment
├── alembic.ini
├── docker-compose.yml                # PostgreSQL 16 + Redis 7
├── Dockerfile
└── pyproject.toml
```

### Quick Start

```bash
# 1. Start services
docker-compose up -d

# 2. Install dependencies
pip install pydantic pydantic-settings sqlalchemy[asyncio] asyncpg alembic redis structlog

# 3. Run migrations
alembic upgrade head

# 4. Run tests
pytest
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `cricketanalytics` | Database name |
| `REDIS_HOST` | `localhost` | Redis host |
| `ENVIRONMENT` | `development` | `development` / `testing` / `production` |

### Database Tables (15 total)

| Table | Description |
|---|---|
| `players` | Master player registry |
| `matches` | Match metadata |
| `deliveries` | Ball-by-ball records |
| `enriched_balls` | Context-enriched delivery features |
| `player_features` | Season-level feature vectors (JSONB) |
| `player_archetypes` | Season-level archetype assignments |
| `archetypes` | Archetype reference table |
| `archetype_transitions` | Player archetype evolution |
| `sovereign_alerts` | Automated performance alerts |
| `franchise_dna_sessions` | Franchise DNA analysis sessions |
| `auction_picks` | Player auction picks |
| `squad_balance` | Squad balance metrics |
| `umap_models` | Serialised UMAP reducers |
| `hdbscan_clusters` | Serialised HDBSCAN results |
| `processed_files` | Ingestion tracking |