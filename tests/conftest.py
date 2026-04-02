"""Pytest fixtures shared across all test modules."""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Override env vars for tests BEFORE importing application code
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DB_NAME", "cricketanalytics_test")
os.environ.setdefault("DB_POOL_MIN", "2")
os.environ.setdefault("DB_POOL_MAX", "5")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio as the AnyIO backend for async tests."""
    return "asyncio"
