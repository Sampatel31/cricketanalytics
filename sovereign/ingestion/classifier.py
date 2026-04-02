"""Match format classifier with franchise league gate.

Usage::

    from sovereign.ingestion.classifier import classifier
    result = classifier.classify(info_dict)
    if result.is_rejected:
        ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import structlog

from sovereign.ingestion.models import MatchClassification

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Franchise league patterns (case-insensitive) – REJECT
# ---------------------------------------------------------------------------
_FRANCHISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bIPL\b",
        r"\bBBL\b",
        r"\bPSL\b",
        r"\bCPL\b",
        r"\bSA20\b",
        r"\bThe Hundred\b",
        r"\bLPL\b",
        r"\bILT20\b",
        r"\bMLC\b",
        r"\bBPL\b",
        r"\bT10\b",
        r"Indian Premier League",
        r"Big Bash",
        r"Pakistan Super League",
        r"Caribbean Premier",
        r"Lanka Premier",
        r"Major League Cricket",
        r"Bangladesh Premier",
        r"International League T20",
        r"Abu Dhabi T10",
        r"Global T20",
        r"Mzansi Super League",
        r"MSL",
    ]
]

# ---------------------------------------------------------------------------
# Domestic accepted tournament patterns
# ---------------------------------------------------------------------------
_DOMESTIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Syed Mushtaq Ali", re.IGNORECASE), "T20"),
    (re.compile(r"SMAT", re.IGNORECASE), "T20"),
    (re.compile(r"Vijay Hazare", re.IGNORECASE), "LIST_A"),
    (re.compile(r"Ranji", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"County Championship", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"Sheffield Shield", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"Duleep Trophy", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"Deodhar Trophy", re.IGNORECASE), "LIST_A"),
    (re.compile(r"Irani Cup", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"National T20 Cup", re.IGNORECASE), "T20"),
    (re.compile(r"Super Smash", re.IGNORECASE), "T20"),
    (re.compile(r"Plunket Shield", re.IGNORECASE), "FIRST_CLASS"),
    (re.compile(r"Marsh Cup", re.IGNORECASE), "LIST_A"),
    (re.compile(r"Marsh One-Day", re.IGNORECASE), "LIST_A"),
]

# Women's event keywords
_WOMENS_KEYWORDS = re.compile(
    r"\bwomen\b|\bwomens\b|\bwoman\b|\bfemale\b|\bwt20\b|\bwodi\b|\bwtest\b",
    re.IGNORECASE,
)

# U19 event keywords
_U19_KEYWORDS = re.compile(
    r"\bu19\b|\bunder.?19\b|\bunder nineteen\b|\byouth\b",
    re.IGNORECASE,
)


def _is_franchise(event_name: str) -> bool:
    """Return True when *event_name* matches a known franchise league."""
    for pattern in _FRANCHISE_PATTERNS:
        if pattern.search(event_name):
            return True
    return False


def _detect_gender(info: dict) -> str:
    """Detect 'female' / 'male' from info dict."""
    gender = info.get("gender", "").lower()
    if gender in ("female", "women"):
        return "female"
    event = str(info.get("event", {}) or info.get("competition", "") or "")
    if _WOMENS_KEYWORDS.search(event):
        return "female"
    return "male"


def _detect_schema_version(info: dict) -> int:
    """Return 1 or 2 based on presence of event dict (v2) vs simple string (v1)."""
    event = info.get("event")
    if isinstance(event, dict):
        return 2
    return 1


class MatchClassifier:
    """Classify a Cricsheet match ``info`` block into a format and filter flags."""

    def classify(self, info: dict) -> MatchClassification:
        """Classify *info* block and return a :class:`MatchClassification`.

        Parameters
        ----------
        info:
            The ``info`` section of a Cricsheet YAML/JSON file.

        Returns
        -------
        MatchClassification
        """
        schema_version = _detect_schema_version(info)

        # Resolve event name from v1/v2 schemas
        event = info.get("event") or info.get("competition") or {}
        if isinstance(event, dict):
            event_name = event.get("name", "")
        else:
            event_name = str(event)

        match_type: str = (info.get("match_type") or "").upper()
        gender = _detect_gender(info)
        is_female = gender == "female"

        # Franchise gate ---------------------------------------------------
        if _is_franchise(event_name):
            log.info(
                "franchise_rejected",
                event_name=event_name,
                match_type=match_type,
            )
            return MatchClassification(
                format_type="UNKNOWN",
                is_rejected=True,
                rejection_reason=f"Franchise league: {event_name!r}",
                schema_version=schema_version,
            )

        # Determine format type --------------------------------------------
        format_type = self._resolve_format(
            match_type, event_name, is_female, info
        )

        return MatchClassification(
            format_type=format_type,
            is_rejected=False,
            rejection_reason=None,
            schema_version=schema_version,
        )

    # ------------------------------------------------------------------
    def _resolve_format(
        self,
        match_type: str,
        event_name: str,
        is_female: bool,
        info: dict,
    ) -> str:
        """Map match_type + event metadata to an internal format label."""
        # U19 detection
        is_u19 = bool(_U19_KEYWORDS.search(event_name))

        if match_type in ("T20I", "T20"):
            if is_u19:
                return "U19_T20I"
            if is_female:
                return "WOMENS_T20I"
            if match_type == "T20I":
                return "T20I"
            # Domestic T20 – check if event is a known domestic tournament
            return self._domestic_t20_format(event_name)

        if match_type in ("ODI", "MDMN"):
            if is_u19:
                return "U19_ODI"
            if is_female:
                return "WOMENS_ODI"
            # Check list-A domestic
            for pattern, fmt in _DOMESTIC_PATTERNS:
                if pattern.search(event_name) and fmt == "LIST_A":
                    return "LIST_A"
            return "ODI"

        if match_type in ("TEST", "MDM"):
            if is_female:
                return "WOMENS_TEST"
            return "TEST"

        if match_type in ("FC", "FIRST_CLASS", "FIRST CLASS"):
            return "FIRST_CLASS"

        if match_type in ("LIST_A", "LISTA"):
            return "LIST_A"

        # Fallback: infer from event name
        for pattern, fmt in _DOMESTIC_PATTERNS:
            if pattern.search(event_name):
                return fmt

        return match_type or "UNKNOWN"

    def _domestic_t20_format(self, event_name: str) -> str:
        """Return 'T20' (domestic) for domestic T20 tournaments."""
        for pattern, fmt in _DOMESTIC_PATTERNS:
            if pattern.search(event_name) and fmt == "T20":
                return "T20"
        return "T20"


# Module-level singleton
classifier = MatchClassifier()
