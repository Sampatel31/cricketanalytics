"""Tests for sovereign/config/settings.py."""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestDatabaseSettings:
    """Tests for DatabaseSettings."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default database settings are sensible (env vars cleared)."""
        monkeypatch.delenv("DB_POOL_MIN", raising=False)
        monkeypatch.delenv("DB_POOL_MAX", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        from sovereign.config.settings import DatabaseSettings

        db = DatabaseSettings()
        assert db.host == "localhost"
        assert db.port == 5432
        assert db.pool_min == 5
        assert db.pool_max == 20

    def test_sync_url(self) -> None:
        """sync_url is a valid psycopg2 URL."""
        from sovereign.config.settings import DatabaseSettings

        db = DatabaseSettings(host="dbhost", port=5433, name="mydb", user="u", password="p")
        assert db.sync_url == "postgresql+psycopg2://u:p@dbhost:5433/mydb"

    def test_async_url(self) -> None:
        """async_url is a valid asyncpg URL."""
        from sovereign.config.settings import DatabaseSettings

        db = DatabaseSettings(host="dbhost", port=5433, name="mydb", user="u", password="p")
        assert db.async_url == "postgresql+asyncpg://u:p@dbhost:5433/mydb"

    def test_alembic_url(self) -> None:
        """alembic_url is a plain postgresql:// URL."""
        from sovereign.config.settings import DatabaseSettings

        db = DatabaseSettings(host="h", port=5432, name="n", user="u", password="p")
        assert db.alembic_url.startswith("postgresql://")

    def test_invalid_port(self) -> None:
        """Invalid port raises ValueError."""
        from sovereign.config.settings import DatabaseSettings

        with pytest.raises(Exception):
            DatabaseSettings(port=0)

    def test_pool_min_gt_max_raises(self) -> None:
        """pool_min > pool_max raises ValueError."""
        from sovereign.config.settings import DatabaseSettings

        with pytest.raises(Exception):
            DatabaseSettings(pool_min=10, pool_max=5)


class TestRedisSettings:
    """Tests for RedisSettings."""

    def test_url_no_password(self) -> None:
        """URL without password is correct."""
        from sovereign.config.settings import RedisSettings

        r = RedisSettings(host="localhost", port=6379, db=0)
        assert r.url == "redis://localhost:6379/0"

    def test_url_with_password(self) -> None:
        """URL with password includes credentials."""
        from sovereign.config.settings import RedisSettings

        r = RedisSettings(host="localhost", port=6379, db=0, password="secret")
        assert r.url == "redis://:secret@localhost:6379/0"


class TestSPIWeights:
    """Tests for SPIWeights."""

    def test_valid_weights_sum_to_one(self) -> None:
        """Weights that sum to 1.0 are accepted."""
        from sovereign.config.settings import SPIWeights

        w = SPIWeights(batting=0.4, bowling=0.35, fielding=0.1, impact=0.15)
        assert abs(sum(w.as_dict().values()) - 1.0) < 1e-9

    def test_invalid_weights_raise(self) -> None:
        """Weights that do not sum to 1.0 raise ValueError."""
        from sovereign.config.settings import SPIWeights

        with pytest.raises(ValueError, match="sum to 1.0"):
            SPIWeights(batting=0.5, bowling=0.5, fielding=0.1, impact=0.1)

    def test_as_dict_keys(self) -> None:
        """as_dict contains the expected keys."""
        from sovereign.config.settings import SPIWeights

        w = SPIWeights(batting=0.4, bowling=0.4, fielding=0.1, impact=0.1)
        keys = set(w.as_dict().keys())
        assert keys == {"batting", "bowling", "fielding", "impact"}


class TestSettings:
    """Tests for the top-level Settings class."""

    def test_environment_default(self) -> None:
        """Environment defaults to 'testing' (set by conftest)."""
        from sovereign.config.settings import Environment, Settings

        s = Settings()
        # conftest sets ENVIRONMENT=testing
        assert s.environment == Environment.TESTING

    def test_is_testing(self) -> None:
        """is_testing returns True in testing environment."""
        from sovereign.config.settings import Settings

        s = Settings()
        assert s.is_testing is True
        assert s.is_production is False

    def test_spi_weights_t20i(self) -> None:
        """SPI weights for T20I can be retrieved."""
        from sovereign.config.settings import FormatType, Settings

        s = Settings()
        w = s.spi_weights(FormatType.T20I)
        assert abs(sum(w.as_dict().values()) - 1.0) < 1e-9

    def test_spi_weights_all_formats(self) -> None:
        """SPI weights are available for all three formats."""
        from sovereign.config.settings import FormatType, Settings

        s = Settings()
        for fmt in FormatType:
            w = s.spi_weights(fmt)
            assert abs(sum(w.as_dict().values()) - 1.0) < 1e-9

    def test_db_sub_settings(self) -> None:
        """db property returns a DatabaseSettings instance."""
        from sovereign.config.settings import DatabaseSettings, Settings

        s = Settings()
        assert isinstance(s.db, DatabaseSettings)

    def test_redis_sub_settings(self) -> None:
        """redis property returns a RedisSettings instance."""
        from sovereign.config.settings import RedisSettings, Settings

        s = Settings()
        assert isinstance(s.redis, RedisSettings)

    def test_api_sub_settings(self) -> None:
        """api property returns an APISettings instance."""
        from sovereign.config.settings import APISettings, Settings

        s = Settings()
        assert isinstance(s.api, APISettings)

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables override default values."""
        monkeypatch.setenv("DB_HOST", "custom-host")
        from sovereign.config.settings import DatabaseSettings

        db = DatabaseSettings()
        assert db.host == "custom-host"
