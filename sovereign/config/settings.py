"""Pydantic settings for Sovereign Cricket Analytics."""

from __future__ import annotations

import sys
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Structured log level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class FormatType(str, Enum):
    """Cricket match format."""

    T20I = "T20I"
    ODI = "ODI"
    TEST = "TEST"


class SPIWeights:
    """SPI weight profile for a single cricket format.

    Weights correspond to the five SPI components:
    - ``run_pressure`` (RP)
    - ``wicket_criticality`` (WC)
    - ``match_phase`` (MP)
    - ``tournament_stage`` (TS)
    - ``opposition_quality`` (OQ)

    All five weights must sum to 1.0.
    """

    def __init__(
        self,
        run_pressure: float,
        wicket_criticality: float,
        match_phase: float,
        tournament_stage: float,
        opposition_quality: float,
    ) -> None:
        """Initialise weight profile."""
        self.run_pressure = run_pressure
        self.wicket_criticality = wicket_criticality
        self.match_phase = match_phase
        self.tournament_stage = tournament_stage
        self.opposition_quality = opposition_quality
        total = (
            run_pressure
            + wicket_criticality
            + match_phase
            + tournament_stage
            + opposition_quality
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"SPI weights must sum to 1.0, got {total:.6f}"
            )

    def as_dict(self) -> dict[str, float]:
        """Return weights as a plain dictionary."""
        return {
            "run_pressure": self.run_pressure,
            "wicket_criticality": self.wicket_criticality,
            "match_phase": self.match_phase,
            "tournament_stage": self.tournament_stage,
            "opposition_quality": self.opposition_quality,
        }


# Default SPI weight profiles per format
DEFAULT_SPI_WEIGHTS: dict[str, dict[str, float]] = {
    FormatType.T20I: {
        "run_pressure": 0.30,
        "wicket_criticality": 0.25,
        "match_phase": 0.20,
        "tournament_stage": 0.15,
        "opposition_quality": 0.10,
    },
    FormatType.ODI: {
        "run_pressure": 0.28,
        "wicket_criticality": 0.27,
        "match_phase": 0.18,
        "tournament_stage": 0.15,
        "opposition_quality": 0.12,
    },
    FormatType.TEST: {
        "run_pressure": 0.20,
        "wicket_criticality": 0.30,
        "match_phase": 0.15,
        "tournament_stage": 0.20,
        "opposition_quality": 0.15,
    },
}


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="cricketanalytics", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="postgres", description="Database password")
    pool_min: int = Field(default=5, description="Minimum pool connections")
    pool_max: int = Field(default=20, description="Maximum pool connections")
    pool_timeout: int = Field(default=30, description="Pool checkout timeout (s)")
    echo_sql: bool = Field(default=False, description="Log all SQL statements")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Ensure port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v

    @field_validator("pool_min", "pool_max")
    @classmethod
    def validate_pool(cls, v: int) -> int:
        """Ensure pool sizes are positive."""
        if v < 1:
            raise ValueError(f"Pool size must be >= 1, got {v}")
        return v

    @model_validator(mode="after")
    def validate_pool_order(self) -> "DatabaseSettings":
        """Ensure pool_min <= pool_max."""
        if self.pool_min > self.pool_max:
            raise ValueError(
                f"pool_min ({self.pool_min}) must be <= pool_max ({self.pool_max})"
            )
        return self

    @property
    def sync_url(self) -> str:
        """Synchronous psycopg2 connection URL."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        """Asynchronous asyncpg connection URL."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def alembic_url(self) -> str:
        """Plain psycopg2 URL for Alembic migrations."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database index")
    password: str | None = Field(default=None, description="Redis password")
    pool_min: int = Field(default=5, description="Minimum pool connections")
    pool_max: int = Field(default=20, description="Maximum pool connections")
    auction_ttl: int = Field(
        default=14400, description="Auction session TTL in seconds (4 hours)"
    )
    score_cache_ttl: int = Field(
        default=3600, description="Player score cache TTL in seconds"
    )

    @property
    def url(self) -> str:
        """Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    host: str = Field(default="0.0.0.0", description="API bind host")
    port: int = Field(default=8000, description="API bind port")
    workers: int = Field(default=4, description="Uvicorn worker count")
    debug: bool = Field(default=False, description="Enable debug mode")
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for token signing",
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="CORS allowed origins",
    )


class Settings(BaseSettings):
    """Top-level application settings.

    All values can be overridden by environment variables.
    Nested settings are read via their own prefixes.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # General                                                              #
    # ------------------------------------------------------------------ #
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO, description="Logging verbosity"
    )
    log_json: bool = Field(
        default=False, description="Emit logs as JSON (True in production)"
    )

    # ------------------------------------------------------------------ #
    # Ingestion                                                            #
    # ------------------------------------------------------------------ #
    ingest_sample_mode: bool = Field(
        default=False,
        description="Only process first 500 files when True",
    )
    ingest_batch_size: int = Field(
        default=500, description="Files per ingestion batch"
    )
    ingest_workers: int = Field(
        default=4, description="Number of parallel workers for ingestion"
    )

    # ------------------------------------------------------------------ #
    # Feature engineering                                                  #
    # ------------------------------------------------------------------ #
    feature_dimensions: int = Field(
        default=54, description="Dimensionality of player feature vectors"
    )
    feature_min_innings: int = Field(
        default=5, description="Minimum innings for stability features"
    )
    feature_confidence_innings: int = Field(
        default=30, description="Innings count for full confidence weight (1.0)"
    )
    rolling_window_size: int = Field(
        default=5, description="Rolling window size for tactical features"
    )
    hmm_n_states: int = Field(
        default=3, description="Number of HMM hidden states for form regime"
    )
    feature_min_deliveries_per_tier: int = Field(
        default=10, description="Minimum deliveries per SPI tier for pressure features"
    )
    feature_min_deliveries_per_phase: int = Field(
        default=5, description="Minimum deliveries per phase for phase features"
    )
    feature_n_workers: int = Field(
        default=4, description="Parallel workers for feature computation"
    )
    feature_batch_size: int = Field(
        default=100, description="Players per batch in feature builder"
    )
    batch_size: int = Field(
        default=256, description="Processing batch size for ingestion"
    )
    umap_n_components: int = Field(
        default=2, description="UMAP output dimensions"
    )
    hdbscan_min_cluster_size: int = Field(
        default=10, description="HDBSCAN minimum cluster size"
    )
    umap_n_neighbors_cluster: int = Field(default=15, description="UMAP n_neighbors for clustering reduction")
    umap_min_dist_cluster: float = Field(default=0.1, description="UMAP min_dist for clustering reduction")
    umap_n_neighbors_viz: int = Field(default=50, description="UMAP n_neighbors for visualization reduction")
    umap_min_dist_viz: float = Field(default=0.05, description="UMAP min_dist for visualization reduction")
    hdbscan_min_samples: int | None = Field(default=None, description="HDBSCAN min_samples (None = use min_cluster_size)")
    bootstrap_runs: int = Field(default=1000, description="Number of bootstrap runs for stability validation")
    bootstrap_subsample_ratio: float = Field(default=0.8, description="Subsample ratio for bootstrap validation")
    ari_stability_threshold: float = Field(default=0.85, description="Minimum ARI for stable clustering")

    # ------------------------------------------------------------------ #
    # Matching engine                                                       #
    # ------------------------------------------------------------------ #
    base_value_t20i: float = Field(
        default=50.0, description="Base crore value for T20I players"
    )
    base_value_odi: float = Field(
        default=25.0, description="Base crore value for ODI players"
    )
    base_value_test: float = Field(
        default=15.0, description="Base crore value for TEST players"
    )
    format_multiplier_t20i: float = Field(
        default=1.2, description="Format valuation multiplier for T20I"
    )
    format_multiplier_odi: float = Field(
        default=0.9, description="Format valuation multiplier for ODI"
    )
    format_multiplier_test: float = Field(
        default=0.6, description="Format valuation multiplier for TEST"
    )
    age_young_threshold: int = Field(
        default=28, description="Age at or below which a player is 'young'"
    )
    age_peak_range: tuple[int, int] = Field(
        default=(29, 32), description="Inclusive age range for peak players"
    )
    age_factor_young: float = Field(
        default=1.0, description="Valuation multiplier for young players"
    )
    age_factor_peak: float = Field(
        default=0.95, description="Valuation multiplier for peaked players"
    )
    age_factor_veteran: float = Field(
        default=0.85, description="Valuation multiplier for veteran players"
    )
    arbitrage_strong_bid: float = Field(
        default=0.20,
        description="Arbitrage pct threshold above which to recommend BID",
    )
    arbitrage_wait: float = Field(
        default=0.05,
        description="Arbitrage pct threshold above which to recommend WAIT",
    )
    arbitrage_avoid: float = Field(
        default=-0.05,
        description="Arbitrage pct threshold below which to recommend AVOID",
    )
    overbid_threshold: float = Field(
        default=1.2,
        description="Multiplier above fair value that triggers an overbid alert",
    )
    gap_alert_auction_progress_pct: float = Field(
        default=0.6,
        description="Auction progress fraction at which gap alerts are triggered",
    )

    # ------------------------------------------------------------------ #
    # Sub-settings (instantiated lazily)                                   #
    # ------------------------------------------------------------------ #
    _db: DatabaseSettings | None = None
    _redis: RedisSettings | None = None
    _api: APISettings | None = None

    @property
    def db(self) -> DatabaseSettings:
        """Return (cached) database settings."""
        if self._db is None:
            self._db = DatabaseSettings()
        return self._db

    @property
    def redis(self) -> RedisSettings:
        """Return (cached) Redis settings."""
        if self._redis is None:
            self._redis = RedisSettings()
        return self._redis

    @property
    def api(self) -> APISettings:
        """Return (cached) API settings."""
        if self._api is None:
            self._api = APISettings()
        return self._api

    @property
    def is_production(self) -> bool:
        """True when running in production mode."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """True when running in test mode."""
        return self.environment == Environment.TESTING

    def spi_weights(self, format_type: FormatType) -> SPIWeights:
        """Return SPI weight profile for the given format.

        Weights are loaded from ``sovereign/config/weights.toml`` when present,
        falling back to the built-in defaults.
        """
        weights_dict = self._load_weights_toml().get(
            format_type.value, DEFAULT_SPI_WEIGHTS[format_type]
        )
        return SPIWeights(**weights_dict)

    @staticmethod
    def _load_weights_toml() -> dict[str, Any]:
        """Load SPI weight profiles from weights.toml if the file exists."""
        import pathlib

        toml_path = pathlib.Path(__file__).parent / "weights.toml"
        if not toml_path.exists():
            return {}
        with toml_path.open("rb") as fh:
            data = tomllib.load(fh)
        return data.get("weights", {})


# Module-level singleton for convenience
settings = Settings()
