"""Tests for sovereign/db/models.py and sovereign/db/connection.py."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine


class TestOrmModels:
    """Validate ORM model definitions without a live database."""

    def test_all_tables_registered(self) -> None:
        """All 15 expected tables are registered in Base.metadata."""
        from sovereign.db.models import Base

        expected = {
            "players",
            "matches",
            "deliveries",
            "enriched_balls",
            "player_features",
            "player_archetypes",
            "archetypes",
            "archetype_transitions",
            "sovereign_alerts",
            "franchise_dna_sessions",
            "auction_picks",
            "squad_balance",
            "umap_models",
            "hdbscan_clusters",
            "processed_files",
        }
        actual = set(Base.metadata.tables.keys())
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_players_table_columns(self) -> None:
        """Players table has the expected columns."""
        from sovereign.db.models import Base

        table = Base.metadata.tables["players"]
        column_names = {c.name for c in table.columns}
        assert {"player_id", "name", "country", "role", "dob", "created_at", "updated_at"} <= column_names

    def test_deliveries_foreign_keys(self) -> None:
        """Deliveries table references players and matches via foreign keys."""
        from sovereign.db.models import Base

        table = Base.metadata.tables["deliveries"]
        fk_targets = {fk.target_fullname for fk in table.foreign_keys}
        assert "matches.match_id" in fk_targets
        assert "players.player_id" in fk_targets

    def test_player_features_unique_constraint(self) -> None:
        """PlayerFeature table has a unique constraint on (player_id, format, season)."""
        from sovereign.db.models import Base

        table = Base.metadata.tables["player_features"]
        uc_names = {uc.name for uc in table.constraints if hasattr(uc, "columns")}
        assert "uq_player_features" in uc_names

    def test_player_archetypes_unique_constraint(self) -> None:
        """PlayerArchetype table has a unique constraint on (player_id, format, season)."""
        from sovereign.db.models import Base

        table = Base.metadata.tables["player_archetypes"]
        uc_names = {uc.name for uc in table.constraints if hasattr(uc, "columns")}
        assert "uq_player_archetypes" in uc_names

    def test_indexes_on_deliveries(self) -> None:
        """Deliveries table has indexes on match_id, batter_id, bowler_id, wicket."""
        from sovereign.db.models import Base

        table = Base.metadata.tables["deliveries"]
        index_names = {idx.name for idx in table.indexes}
        for expected in [
            "ix_deliveries_match_id",
            "ix_deliveries_batter_id",
            "ix_deliveries_bowler_id",
            "ix_deliveries_wicket",
        ]:
            assert expected in index_names, f"Missing index: {expected}"

    def test_player_model_repr(self) -> None:
        """Player model can be instantiated without a database."""
        from sovereign.db.models import Player

        p = Player(player_id="virat-kohli-ind", name="Virat Kohli", country="India")
        assert p.player_id == "virat-kohli-ind"
        assert p.name == "Virat Kohli"

    def test_match_model(self) -> None:
        """Match model instantiation."""
        from sovereign.db.models import Match

        m = Match(match_id="test-001", format="T20I", team1="India", team2="Australia")
        assert m.match_id == "test-001"

    def test_processed_file_model(self) -> None:
        """ProcessedFile model instantiation."""
        from sovereign.db.models import ProcessedFile

        pf = ProcessedFile(filename="test.yaml", file_hash="abc123")
        assert pf.filename == "test.yaml"


class TestDatabaseManager:
    """Tests for DatabaseManager (without a real database)."""

    def test_engine_uninitialised_raises(self) -> None:
        """Accessing engine before initialise raises DatabaseError."""
        from sovereign.db.connection import DatabaseError, DatabaseManager

        mgr = DatabaseManager()
        with pytest.raises(DatabaseError, match="not initialised"):
            _ = mgr.engine

    def test_session_uninitialised_raises(self) -> None:
        """Using session before initialise raises DatabaseError."""
        import asyncio

        from sovereign.db.connection import DatabaseError, DatabaseManager

        mgr = DatabaseManager()

        async def _run() -> None:
            async with mgr.session():
                pass

        with pytest.raises(DatabaseError, match="not initialised"):
            asyncio.run(_run())

    def test_initialise_creates_engine(self) -> None:
        """initialise() creates an async engine."""
        from sovereign.db.connection import DatabaseManager

        mgr = DatabaseManager()
        url = "postgresql+asyncpg://postgres:postgres@localhost:5432/cricketanalytics_test"
        mgr.initialise(async_url=url, pool_min=2, pool_max=5)
        assert mgr._engine is not None
        assert mgr._session_factory is not None


class TestSQLiteInMemory:
    """Smoke tests using SQLite in-memory (no PostgreSQL required)."""

    @pytest.mark.asyncio
    async def test_create_all_sqlite(self) -> None:
        """Core non-JSONB tables can be created in SQLite in-memory."""
        from sqlalchemy import Column, DateTime, Integer, String
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import DeclarativeBase

        class _Base(DeclarativeBase):
            pass

        class _Player(_Base):
            __tablename__ = "players"
            player_id = Column(String(100), primary_key=True)
            name = Column(String(200), nullable=False)
            country = Column(String(100))

        class _Match(_Base):
            __tablename__ = "matches"
            match_id = Column(String(100), primary_key=True)
            format = Column(String(20))

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)

        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result.fetchall()}

        await engine.dispose()

        assert "players" in tables
        assert "matches" in tables

    def test_all_tables_in_metadata(self) -> None:
        """All 15 expected tables are present in Base.metadata (no DB required)."""
        from sovereign.db.models import Base

        expected = {
            "players", "matches", "deliveries", "enriched_balls",
            "player_features", "player_archetypes", "archetypes",
            "archetype_transitions", "sovereign_alerts",
            "franchise_dna_sessions", "auction_picks", "squad_balance",
            "umap_models", "hdbscan_clusters", "processed_files",
        }
        actual = set(Base.metadata.tables.keys())
        assert expected == actual
