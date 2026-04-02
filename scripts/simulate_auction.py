"""CLI script: Simulate an IPL-style auction against franchise DNA.

Usage
-----
::

    python scripts/simulate_auction.py \\
        --dna-json data/models/franchise_dna_MI.json \\
        --auction-lots data/auction_lots_2024.json \\
        --budget 100 \\
        --format T20I \\
        --output-dir data/simulations \\
        --verbose

Auction lots JSON format
------------------------
A list of player lot objects::

    [
        {
            "player_id": "rohit-123",
            "player_name": "Rohit Sharma",
            "base_price": 2.0,
            "market_price": 15.0,
            "archetype_code": "ARC_001",
            "archetype_label": "Aggressive Opener",
            "age": 36
        },
        ...
    ]

Outputs
-------
- ``squad_report_<franchise>.json`` — Final squad composition
- ``scorecard_<franchise>.json``   — All player scores
- ``overbid_alerts_<franchise>.json`` — Overbid warnings
- ``gap_alerts_<franchise>.json``  — Archetype gap warnings
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

import polars as pl

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import structlog

from sovereign.features.models import FeatureVector
from sovereign.matching.dna import _FEATURE_NAMES
from sovereign.matching.homology import HomologyScorer
from sovereign.matching.models import FranchiseDNA, OverbidAlert
from sovereign.matching.squad import SquadManager
from sovereign.matching.valuation import ValuationModel
from sovereign.config.settings import settings

log = structlog.get_logger()

FEATURE_NAMES: list[str] = list(FeatureVector.model_fields.keys())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate an auction using franchise DNA and player lots.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dna-json",
        required=True,
        help="Path to franchise DNA JSON produced by build_franchise_dna.py",
    )
    parser.add_argument(
        "--auction-lots",
        required=True,
        help="Path to auction lots JSON (list of player objects)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=100.0,
        help="Total auction budget in crores (default: 100)",
    )
    parser.add_argument(
        "--format",
        dest="format_type",
        default="T20I",
        choices=["T20I", "ODI", "TEST"],
        help="Cricket format for valuation (default: T20I)",
    )
    parser.add_argument(
        "--overbid-threshold",
        type=float,
        default=None,
        help="Overbid alert threshold multiplier (default: from settings)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/simulations",
        help="Output directory for simulation reports",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def _load_dna(path: pathlib.Path) -> FranchiseDNA:
    """Load a FranchiseDNA from JSON file."""
    with path.open() as fh:
        data = json.load(fh)
    return FranchiseDNA(**data)


def _build_features_df(lots: list[dict]) -> pl.DataFrame:
    """Build a minimal features DataFrame from auction lot metadata.

    Missing feature values default to 0.5 (neutral) so the scorer can
    operate even without a full pre-computed feature matrix.
    """
    rows: list[dict] = []
    for lot in lots:
        row: dict = {"player_id": lot["player_id"]}
        row["player_name"] = lot.get("player_name", lot["player_id"])
        row["confidence_weight"] = float(lot.get("confidence_weight", 1.0))
        row["innings_count"] = int(lot.get("innings_count", 20))
        for feat in FEATURE_NAMES:
            row[feat] = float(lot.get(feat, 0.5))
        rows.append(row)
    return pl.DataFrame(rows)


def _build_archetypes_df(lots: list[dict]) -> pl.DataFrame:
    """Build a minimal archetypes DataFrame from auction lot metadata."""
    return pl.DataFrame(
        {
            "player_id": [lot["player_id"] for lot in lots],
            "archetype_code": [
                lot.get("archetype_code", "UNKNOWN") for lot in lots
            ],
            "archetype_label": [
                lot.get("archetype_label", "Unknown") for lot in lots
            ],
        }
    )


def main() -> None:
    """Run the auction simulation."""
    args = _parse_args()

    if args.verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(10)
        )

    # Load DNA
    dna_path = pathlib.Path(args.dna_json)
    if not dna_path.exists():
        log.error("DNA JSON not found", path=str(dna_path))
        sys.exit(1)
    dna = _load_dna(dna_path)
    log.info("Loaded franchise DNA", franchise=dna.franchise_name, mode=dna.dna_mode)

    # Load auction lots
    lots_path = pathlib.Path(args.auction_lots)
    if not lots_path.exists():
        log.error("Auction lots JSON not found", path=str(lots_path))
        sys.exit(1)
    with lots_path.open() as fh:
        lots: list[dict] = json.load(fh)
    log.info("Loaded auction lots", n_lots=len(lots))

    # Build DataFrames from lot metadata
    features_df = _build_features_df(lots)
    archetypes_df = _build_archetypes_df(lots)

    # Initialise components
    scorer = HomologyScorer()
    valuation = ValuationModel(
        base_value_t20i=settings.base_value_t20i,
        base_value_odi=settings.base_value_odi,
        base_value_test=settings.base_value_test,
    )
    manager = SquadManager(
        franchise_name=dna.franchise_name,
        budget_total=args.budget,
        dna=dna,
        archetypes=[],
        gap_alert_progress_pct=settings.gap_alert_auction_progress_pct,
    )

    overbid_threshold = (
        args.overbid_threshold
        if args.overbid_threshold is not None
        else settings.overbid_threshold
    )

    player_ids = [lot["player_id"] for lot in lots]
    scores = scorer.compute_scores(
        dna=dna,
        player_ids=player_ids,
        features_df=features_df,
        archetypes_df=archetypes_df,
    )

    lot_map = {lot["player_id"]: lot for lot in lots}

    # Enrich scores with valuation data
    enriched_scores: list[dict] = []
    overbid_alerts: list[OverbidAlert] = []

    for score in scores:
        lot = lot_map.get(score.player_id, {})
        market_price = float(lot.get("market_price", 1.0))
        age = int(lot.get("age", 28))

        try:
            fair_value = valuation.estimate_fair_value(
                player_id=score.player_id,
                homology_score=score.homology_score,
                player_features={"age": age},
                archetype_info={},
                auction_context={"format_type": args.format_type},
            )
            arb = valuation.compute_arbitrage(fair_value, max(market_price, 0.01))
        except Exception as exc:  # noqa: BLE001
            log.warning("Valuation failed", player_id=score.player_id, error=str(exc))
            fair_value = 0.0
            arb = {"arbitrage_gap": 0.0, "arbitrage_pct": 0.0, "recommendation": "NEUTRAL"}

        max_bid_ceiling = fair_value * overbid_threshold
        if market_price > max_bid_ceiling and max_bid_ceiling > 0:
            overpay = market_price - max_bid_ceiling
            overbid_alerts.append(
                OverbidAlert(
                    player_id=score.player_id,
                    current_bid=market_price,
                    max_bid_ceiling=max_bid_ceiling,
                    overpay_amount=overpay,
                    overpay_pct=(overpay / max_bid_ceiling) * 100,
                    severity="critical" if overpay / max_bid_ceiling > 0.3 else "warning",
                )
            )

        enriched_scores.append(
            {
                "player_id": score.player_id,
                "player_name": score.player_name,
                "archetype_code": score.archetype_code,
                "archetype_label": score.archetype_label,
                "homology_score": round(score.homology_score, 4),
                "archetype_bonus": score.archetype_bonus,
                "confidence_weight": score.confidence_weight,
                "fair_value": round(fair_value, 2),
                "market_price": round(market_price, 2),
                "arbitrage_gap": round(arb["arbitrage_gap"], 2),
                "arbitrage_pct": round(arb["arbitrage_pct"], 2),
                "recommendation": arb["recommendation"],
            }
        )

    # Simulate squad selection: auto-pick top BID/WAIT players within budget
    remaining_budget = args.budget
    selected: list[dict] = []
    for entry in enriched_scores:
        if entry["recommendation"] not in ("BID", "WAIT"):
            continue
        price = entry["market_price"]
        if price > remaining_budget:
            continue
        manager.add_player(
            player_id=entry["player_id"],
            price_paid=price,
            archetype_code=entry["archetype_code"],
            homology_score=entry["homology_score"],
        )
        remaining_budget -= price
        selected.append(entry)

    squad_state = manager.get_squad_state()

    # Gap alerts
    gap_alerts = manager.detect_gaps(
        upcoming_lots=max(0, len(lots) - len(selected)),
        total_lots=len(lots),
    )

    # Write outputs
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = dna.franchise_name.replace(" ", "_") or "franchise"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    def _save(name: str, data: object) -> pathlib.Path:
        path = output_dir / f"{name}_{safe_name}_{ts}.json"
        with path.open("w") as fh:
            json.dump(data, fh, indent=2, default=str)
        return path

    squad_path = _save("squad_report", squad_state.model_dump(mode="json"))
    scorecard_path = _save("scorecard", enriched_scores)
    overbid_path = _save(
        "overbid_alerts",
        [a.model_dump(mode="json") for a in overbid_alerts],
    )
    gap_path = _save(
        "gap_alerts",
        [a.model_dump(mode="json") for a in gap_alerts],
    )

    # Summary
    print("\n" + "=" * 60)
    print(f"  AUCTION SIMULATION — {dna.franchise_name}")
    print("=" * 60)
    print(f"  Format:           {args.format_type}")
    print(f"  Total budget:     ₹{args.budget:.1f} Cr")
    print(f"  Budget spent:     ₹{squad_state.budget_spent:.1f} Cr")
    print(f"  Budget remaining: ₹{args.budget - squad_state.budget_spent:.1f} Cr")
    print(f"  Players selected: {len(squad_state.players_locked_in)}")
    print(f"  Squad DNA score:  {squad_state.squad_dna_score:.4f}")
    print(f"  Overbid alerts:   {len(overbid_alerts)}")
    print(f"  Gap alerts:       {len(gap_alerts)}")
    print("\n  Archetype balance:")
    for code, count in squad_state.archetype_balance.items():
        print(f"    {code}: {count}")
    print(f"\n  Reports saved to: {output_dir}/")
    print(f"    {squad_path.name}")
    print(f"    {scorecard_path.name}")
    print(f"    {overbid_path.name}")
    print(f"    {gap_path.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
