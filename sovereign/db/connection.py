"""Database connection manager using async SQLAlchemy + asyncpg.

Usage::

    from sovereign.db.connection import db_manager

    async with db_manager.session() as session:
        result = await session.execute(select(Player))
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sovereign.db.models import Base

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class DatabaseManager:
    """Manages the async SQLAlchemy engine and session factory.

    Call :meth:`initialise` once at application startup and
    :meth:`close` during shutdown.
    """

    def __init__(self) -> None:
        """Create an uninitialised manager."""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def initialise(
        self,
        async_url: str,
        pool_min: int = 5,
        pool_max: int = 20,
        pool_timeout: int = 30,
        echo: bool = False,
    ) -> None:
        """Create the async engine and session factory.

        Args:
            async_url: asyncpg connection URL
                (``postgresql+asyncpg://user:pass@host/db``).
            pool_min: Minimum number of pooled connections.
            pool_max: Maximum number of pooled connections.
            pool_timeout: Seconds to wait for a connection before raising.
            echo: Log every SQL statement when *True*.
        """
        self._engine = create_async_engine(
            async_url,
            pool_size=pool_min,
            max_overflow=pool_max - pool_min,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
            echo=echo,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Database engine initialised", extra={"url": async_url})

    @property
    def engine(self) -> AsyncEngine:
        """Return the async engine, raising if uninitialised."""
        if self._engine is None:
            raise DatabaseError(
                "DatabaseManager is not initialised. Call .initialise() first."
            )
        return self._engine

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield an :class:`AsyncSession` with automatic rollback on error.

        Example::

            async with db_manager.session() as s:
                s.add(player)
                await s.commit()
        """
        if self._session_factory is None:
            raise DatabaseError(
                "DatabaseManager is not initialised. Call .initialise() first."
            )
        async with self._session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    async def create_all(self) -> None:
        """Create all tables defined in ``Base.metadata`` (for tests/dev)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self) -> None:
        """Drop all tables (destructive – test environments only)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def health_check(self) -> bool:
        """Execute a simple ``SELECT 1`` to verify database connectivity.

        Returns:
            *True* if the database is reachable, *False* otherwise.
        """
        try:
            from sqlalchemy import text

            async with self.session() as s:
                await s.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("Database health check failed: %s", exc)
            return False

    async def close(self) -> None:
        """Dispose of the connection pool and release all resources."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database engine closed")


# Module-level singleton
db_manager = DatabaseManager()
