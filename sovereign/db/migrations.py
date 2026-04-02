"""Database migration helpers.

Thin wrappers around Alembic's scripting API so that application code can
trigger migrations programmatically (e.g. in tests or CLI scripts).
"""

from __future__ import annotations

import pathlib

from alembic import command
from alembic.config import Config


def _alembic_config(ini_path: str | None = None) -> Config:
    """Build an Alembic :class:`Config` pointing at the project root."""
    if ini_path is None:
        ini_path = str(pathlib.Path(__file__).parent.parent.parent / "alembic.ini")
    return Config(ini_path)


def upgrade(revision: str = "head", ini_path: str | None = None) -> None:
    """Run ``alembic upgrade <revision>``."""
    cfg = _alembic_config(ini_path)
    command.upgrade(cfg, revision)


def downgrade(revision: str, ini_path: str | None = None) -> None:
    """Run ``alembic downgrade <revision>``."""
    cfg = _alembic_config(ini_path)
    command.downgrade(cfg, revision)


def current(ini_path: str | None = None) -> None:
    """Print the current migration revision."""
    cfg = _alembic_config(ini_path)
    command.current(cfg)
