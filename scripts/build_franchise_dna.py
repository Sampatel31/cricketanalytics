"""CLI script: Build franchise DNA in slider, exemplar, or historical mode.

Usage
-----
Slider mode::

    python scripts/build_franchise_dna.py \\
        --mode slider \\
        --features-parquet data/models/features_matrix_T20I_2024.parquet \\
        --franchise-name "Mumbai Indians" \\
        --slider-file dna_sliders.json \\
        --output-dir data/models \\
        --verbose

Exemplar mode::

    python scripts/build_franchise_dna.py \\
        --mode exemplar \\
        --features-parquet data/models/features_matrix_T20I_2024.parquet \\
        --franchise-name "CSK" \\
        --player-ids rohit-123 virat-456 sky-789 \\
        --output-dir data/models

Historical mode::

    python scripts/build_franchise_dna.py \\
        --mode historical \\
        --features-parquet data/models/features_matrix_T20I_2024.parquet \\
        --franchise-name "RCB" \\
        --player-ids player-aaa player-bbb \\
        --output-dir data/models
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import polars as pl

# Allow running directly from repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import structlog

from sovereign.matching.dna import FranchiseDNABuilder

log = structlog.get_logger()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build franchise DNA from slider weights, exemplar players, "
        "or historical picks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["slider", "exemplar", "historical"],
        required=True,
        help="DNA build mode",
    )
    parser.add_argument(
        "--features-parquet",
        required=True,
        help="Path to player × 54-feature Parquet file",
    )
    parser.add_argument(
        "--franchise-name",
        default="",
        help="Franchise name (e.g. 'Mumbai Indians')",
    )
    parser.add_argument(
        "--slider-file",
        help="[slider mode] Path to JSON file with feature→weight (0-100) mapping",
    )
    parser.add_argument(
        "--player-ids",
        nargs="+",
        metavar="PLAYER_ID",
        help="[exemplar / historical mode] Player IDs to include",
    )
    parser.add_argument(
        "--target-archetypes",
        nargs="*",
        metavar="ARC_CODE",
        default=[],
        help="Optional preferred archetype codes (e.g. ARC_001 ARC_003)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Directory where the DNA JSON will be saved",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = _parse_args()

    if args.verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(10)
        )

    # Load features
    feat_path = pathlib.Path(args.features_parquet)
    if not feat_path.exists():
        log.error("features_parquet not found", path=str(feat_path))
        sys.exit(1)

    log.info("Loading features", path=str(feat_path))
    features_df = pl.read_parquet(feat_path)
    log.info("Features loaded", rows=len(features_df), cols=len(features_df.columns))

    builder = FranchiseDNABuilder()

    if args.mode == "slider":
        if not args.slider_file:
            log.error("--slider-file is required for slider mode")
            sys.exit(1)
        slider_path = pathlib.Path(args.slider_file)
        if not slider_path.exists():
            log.error("slider_file not found", path=str(slider_path))
            sys.exit(1)
        with slider_path.open() as fh:
            feature_weights: dict[str, float] = json.load(fh)
        log.info(
            "Building slider DNA",
            active_features=sum(1 for v in feature_weights.values() if v > 0),
        )
        dna = builder.build_slider(
            feature_weights=feature_weights,
            franchise_name=args.franchise_name,
            target_archetypes=args.target_archetypes,
        )

    elif args.mode == "exemplar":
        if not args.player_ids:
            log.error("--player-ids is required for exemplar mode")
            sys.exit(1)
        log.info("Building exemplar DNA", n_players=len(args.player_ids))
        dna = builder.build_exemplar(
            player_ids=args.player_ids,
            features_df=features_df,
            franchise_name=args.franchise_name,
            target_archetypes=args.target_archetypes,
        )

    else:  # historical
        if not args.player_ids:
            log.error("--player-ids is required for historical mode")
            sys.exit(1)
        log.info("Building historical DNA", n_picks=len(args.player_ids))
        dna = builder.build_historical(
            player_ids=args.player_ids,
            features_df=features_df,
            franchise_name=args.franchise_name,
            target_archetypes=args.target_archetypes,
        )

    # Save output
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = args.franchise_name.replace(" ", "_") or "franchise"
    out_path = output_dir / f"franchise_dna_{safe_name}.json"

    with out_path.open("w") as fh:
        json.dump(dna.model_dump(mode="json"), fh, indent=2, default=str)

    log.info(
        "Franchise DNA saved",
        path=str(out_path),
        mode=dna.dna_mode,
        franchise=dna.franchise_name,
        description=dna.description,
    )
    print(f"\n✅ DNA saved: {out_path}")
    print(f"   Mode:      {dna.dna_mode}")
    print(f"   Franchise: {dna.franchise_name}")
    print(f"   DNA ID:    {dna.dna_id}")
    print(f"   Note:      {dna.description}")


if __name__ == "__main__":
    main()
