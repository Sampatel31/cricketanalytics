"""Schema validation and duplicate detection for parsed match data.

Usage::

    from sovereign.ingestion.validator import MatchValidator, compute_file_hash

    validator = MatchValidator()
    is_valid, errors = validator.validate_match(parsed_match)
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import structlog

from sovereign.ingestion.models import MatchInfo, ParsedMatch, RawDelivery

log = structlog.get_logger(__name__)

# Format-specific maximum overs
_MAX_OVERS: dict[str, Optional[int]] = {
    "T20I": 20,
    "T20": 20,
    "WOMENS_T20I": 20,
    "U19_T20I": 20,
    "ODI": 50,
    "WOMENS_ODI": 50,
    "U19_ODI": 50,
    "LIST_A": 50,
    "TEST": None,
    "WOMENS_TEST": None,
    "FIRST_CLASS": None,
}

_MIN_DELIVERIES = 20


def compute_file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*."""
    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class MatchValidator:
    """Validate a :class:`ParsedMatch` for completeness and consistency."""

    def validate_match(self, match: ParsedMatch) -> tuple[bool, list[str]]:
        """Run all validation checks and return ``(is_valid, errors)``.

        All checks are performed before returning (non-fail-fast).
        """
        errors: list[str] = []

        # 1. MatchInfo required fields
        info = match.match_info
        if not info.match_id:
            errors.append("match_info.match_id is missing")
        if info.date is None:
            errors.append("match_info.date is missing")
        if not info.format:
            errors.append("match_info.format is missing")
        if not info.team1 or not info.team2:
            errors.append("match_info.teams incomplete (need team1 and team2)")

        # 2. Minimum deliveries
        if len(match.deliveries) < _MIN_DELIVERIES:
            errors.append(
                f"Too few deliveries: {len(match.deliveries)} < {_MIN_DELIVERIES}"
            )

        # 3. Per-delivery checks
        format_upper = (info.format or "").upper()
        max_overs = _MAX_OVERS.get(format_upper)

        for i, d in enumerate(match.deliveries):
            prefix = f"delivery[{i}]"

            if not d.batter_id:
                errors.append(f"{prefix}: batter_id is missing")
            if not d.bowler_id:
                errors.append(f"{prefix}: bowler_id is missing")

            if d.over_number < 0:
                errors.append(f"{prefix}: over_number {d.over_number} < 0")
            elif max_overs is not None and d.over_number >= max_overs:
                errors.append(
                    f"{prefix}: over_number {d.over_number} >= max {max_overs}"
                )

            if not (0 <= d.ball_number <= 9):
                errors.append(
                    f"{prefix}: ball_number {d.ball_number} out of range [0, 9]"
                )

            if d.runs_batter < 0:
                errors.append(f"{prefix}: runs_batter {d.runs_batter} is negative")
            if d.runs_extras < 0:
                errors.append(f"{prefix}: runs_extras {d.runs_extras} is negative")
            if d.runs_total < 0:
                errors.append(f"{prefix}: runs_total {d.runs_total} is negative")

        is_valid = len(errors) == 0
        if not is_valid:
            log.debug(
                "match_validation_failed",
                match_id=info.match_id,
                error_count=len(errors),
            )
        return is_valid, errors


class DuplicateDetector:
    """Detect duplicate files by tracking SHA-256 hashes in memory.

    In production this would check against a ``processed_files`` database
    table.  For now it keeps an in-process set of already-seen hashes and
    accepts an optional pre-populated set for testing.
    """

    def __init__(self, seen_hashes: Optional[set[str]] = None) -> None:
        self._seen: set[str] = seen_hashes or set()

    def is_duplicate(self, file_path: Path) -> bool:
        """Return ``True`` if *file_path* has already been processed.

        The first call for a given file records its hash; subsequent calls
        return ``True``.
        """
        h = compute_file_hash(file_path)
        if h in self._seen:
            log.debug("duplicate_file_skipped", path=str(file_path))
            return True
        self._seen.add(h)
        return False

    def mark_processed(self, file_path: Path) -> str:
        """Record *file_path* as processed and return its hash."""
        h = compute_file_hash(file_path)
        self._seen.add(h)
        return h
