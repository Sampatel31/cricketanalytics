"""Sovereign Pressure Index (SPI) calculator.

Formula:
    SPI = α·RP + β·WC + γ·MP + δ·TS + ε·OQ

where:
    RP = Run Pressure      [0, 10]
    WC = Wicket Criticality [0, 10]
    MP = Match Phase        [0, 10]
    TS = Tournament Stage   [0, 10]
    OQ = Opposition Quality [0, 10]

All component values and the total are clamped to [0, 10].

Usage::

    from sovereign.enrichment.spi import spi_calculator

    components = spi_calculator.compute(enriched_delivery)
    print(components.total, components.tier)
"""

from __future__ import annotations

from typing import Optional

import structlog

from sovereign.config.settings import FormatType, Settings, settings as _settings
from sovereign.enrichment.models import EnrichedDelivery, SPIComponents

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ELO constants for opposition quality
# ---------------------------------------------------------------------------
_ELO_MIN = 1200.0
_ELO_MAX = 1800.0

# ---------------------------------------------------------------------------
# Tournament stage scores
# ---------------------------------------------------------------------------
_STAGE_SCORES: dict[str, float] = {
    "final": 10.0,
    "semi-final": 8.0,
    "semi final": 8.0,
    "semifinal": 8.0,
    "quarter-final": 7.0,
    "quarter final": 7.0,
    "quarterfinal": 7.0,
    "super 12": 6.0,
    "super 8": 6.0,
    "super 4": 6.0,
    "super six": 5.5,
    "group": 5.0,
    "group stage": 5.0,
    "league": 5.0,
    "preliminary": 4.0,
    "qualifier": 4.0,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    """Clamp *value* to [*lo*, *hi*]."""
    return max(lo, min(hi, value))


def phase_label(format_type: str, over_number: int) -> str:
    """Return 'powerplay', 'middle' or 'death' for a given over.

    This is a module-level convenience function that mirrors the logic in
    ``sovereign.enrichment.context``.
    """
    from sovereign.enrichment.context import _phase_label

    return _phase_label(format_type, over_number)


def _tournament_stage_score(event_stage: Optional[str]) -> float:
    """Map event stage string to a [0, 10] score."""
    if not event_stage:
        return 5.0  # default group stage
    lower = event_stage.lower().strip()

    # Check longer/more specific patterns first to avoid substring false matches
    # (e.g. "semi-final" must not match "final")
    ordered_checks = [
        ("semifinal", 8.0),
        ("semi-final", 8.0),
        ("semi final", 8.0),
        ("quarterfinal", 7.0),
        ("quarter-final", 7.0),
        ("quarter final", 7.0),
        ("super 12", 6.0),
        ("super 8", 6.0),
        ("super 4", 6.0),
        ("super six", 5.5),
        ("group stage", 5.0),
        ("group", 5.0),
        ("league", 5.0),
        ("preliminary", 4.0),
        ("qualifier", 4.0),
        # "final" must come AFTER semi-final / quarter-final checks
        ("final", 10.0),
    ]
    for key, score in ordered_checks:
        if key in lower:
            return score

    # Try direct numeric match (e.g. match number late in tournament)
    try:
        num = int(lower.split()[-1])
        # Higher match numbers tend to be later in tournaments
        return min(10.0, 4.0 + num * 0.05)
    except (ValueError, IndexError):
        pass
    return 5.0


def _elo_to_oq(elo: Optional[float]) -> float:
    """Normalise *elo* to [0, 10].  Unknown ELO defaults to 5.0."""
    if elo is None:
        return 5.0
    normalised = (elo - _ELO_MIN) / (_ELO_MAX - _ELO_MIN) * 10.0
    return _clamp(normalised)


def _run_pressure(ctx: EnrichedDelivery, format_upper: str) -> float:
    """Compute the Run Pressure component.

    Second innings: based on RRR − CRR gap.
    First innings: uses a projected shortfall proxy.
    Test/FC: uses a simpler proxy (low RP by default).
    """
    if ctx.required_run_rate is None:
        # First innings or format without RRR
        if format_upper in ("TEST", "WOMENS_TEST", "FIRST_CLASS"):
            return 3.0  # low default for Test
        # First innings projection: use current run rate vs a nominal target rate
        crr = ctx.current_run_rate or 0.0
        # If scoring slowly vs typical T20 (8 rpo) / ODI (5 rpo)
        nominal = 8.0 if "T20" in format_upper else 5.0
        gap = nominal - crr
        return _clamp(5.0 + gap)

    rrr = ctx.required_run_rate
    crr = ctx.current_run_rate or 0.0
    gap = rrr - crr
    # Map gap to [0, 10]: gap of 0 → 5, gap of 6 → 10 (extreme), gap of -6 → 0
    score = 5.0 + gap * (5.0 / 6.0)
    return _clamp(score)


def _wicket_criticality(ctx: EnrichedDelivery) -> float:
    """Non-linear wicket criticality score.

    Later wickets and chasing positions carry higher weight.
    """
    wickets = ctx.wickets_fallen
    wih = max(0, 11 - wickets)

    # Base score: more wickets fallen = more critical
    # Wickets 0-3 → low, 4-6 → medium, 7-9 → high, 10 → extreme
    base = _clamp((wickets / 10.0) * 8.0 + 1.0)

    # Chase multiplier: higher when chasing with fewer resources
    if ctx.innings_number == 2:
        chase_factor = 1.2
    else:
        chase_factor = 1.0

    score = base * chase_factor * (1.0 + (10 - wih) / 20.0)
    return _clamp(score)


def _match_phase_score(ctx: EnrichedDelivery) -> float:
    """Map phase label to a pressure score."""
    label = ctx.phase_label
    if label == "death":
        return 8.5
    if label == "middle":
        return 5.0
    if label == "powerplay":
        return 6.0  # powerplay has its own pressure dynamic
    return 5.0


class SPICalculator:
    """Compute the Sovereign Pressure Index for a single enriched delivery."""

    def __init__(self, settings_obj: Optional[Settings] = None) -> None:
        self._settings = settings_obj or _settings

    def compute(self, ctx: EnrichedDelivery) -> SPIComponents:
        """Compute and return all SPI components for *ctx*."""
        format_str = (
            ctx.batting_team  # not the format — need it from match_info context
        )
        # We don't have match_info directly on EnrichedDelivery; infer from
        # phase_label and other available info.  The caller should set
        # EnrichedDelivery.phase_label correctly via ContextBuilder.
        format_upper = "T20I"  # sensible default; override via _infer_format

        # Determine format for weight lookup
        format_upper = self._infer_format(ctx)

        try:
            format_type = FormatType(format_upper)
        except ValueError:
            # Fall back to T20I weights for unknown formats
            format_type = FormatType.T20I

        weights = self._settings.spi_weights(format_type)

        # Component scores
        rp = _run_pressure(ctx, format_upper)
        wc = _wicket_criticality(ctx)
        mp = _match_phase_score(ctx)

        # Tournament stage – we embed stage hint in the phase_label extension
        # field when available; otherwise default to group stage (5.0).
        ts = _tournament_stage_score(None)

        # Opposition quality – default 5.0 unless caller sets elo on ctx
        elo: Optional[float] = getattr(ctx, "opposition_elo", None)
        oq = _elo_to_oq(elo)

        total = (
            weights.run_pressure * rp
            + weights.wicket_criticality * wc
            + weights.match_phase * mp
            + weights.tournament_stage * ts
            + weights.opposition_quality * oq
        )

        return SPIComponents(
            run_pressure=_clamp(rp),
            wicket_criticality=_clamp(wc),
            match_phase=_clamp(mp),
            tournament_stage=_clamp(ts),
            opposition_quality=_clamp(oq),
            total=_clamp(total),
        )

    def compute_with_stage(
        self,
        ctx: EnrichedDelivery,
        event_stage: Optional[str] = None,
        opposition_elo: Optional[float] = None,
    ) -> SPIComponents:
        """Full computation with optional tournament stage and ELO."""
        format_upper = self._infer_format(ctx)
        try:
            format_type = FormatType(format_upper)
        except ValueError:
            format_type = FormatType.T20I

        weights = self._settings.spi_weights(format_type)

        rp = _run_pressure(ctx, format_upper)
        wc = _wicket_criticality(ctx)
        mp = _match_phase_score(ctx)
        ts = _tournament_stage_score(event_stage)
        oq = _elo_to_oq(opposition_elo)

        total = (
            weights.run_pressure * rp
            + weights.wicket_criticality * wc
            + weights.match_phase * mp
            + weights.tournament_stage * ts
            + weights.opposition_quality * oq
        )

        return SPIComponents(
            run_pressure=_clamp(rp),
            wicket_criticality=_clamp(wc),
            match_phase=_clamp(mp),
            tournament_stage=_clamp(ts),
            opposition_quality=_clamp(oq),
            total=_clamp(total),
        )

    @staticmethod
    def _infer_format(ctx: EnrichedDelivery) -> str:
        """Infer match format from available context fields."""
        # EnrichedDelivery doesn't carry match format directly; we use
        # phase_label boundaries as a proxy.
        # Callers may also attach a ``_format`` attribute.
        fmt: Optional[str] = getattr(ctx, "_format", None)
        if fmt:
            return fmt.upper()
        # Fallback: unknown → T20I (most common in datasets)
        return "T20I"


# Module-level singleton
spi_calculator = SPICalculator()
