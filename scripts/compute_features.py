"""CLI script to compute 54-dimensional player feature matrices.

Usage::

    python scripts/compute_features.py \\
      --format-type T20I \\
      --season 2024 \\
      --workers 4 \\
      --batch-size 100 \\
      --output-dir data/models \\
      --verbose
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

# Ensure the project root is on the Python path when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import polars as pl

from sovereign.features.builder import FeatureBuilder


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute 54-dimensional player behavioral fingerprints."
    )
    parser.add_argument(
        "--format-type",
        default="T20I",
        choices=["T20I", "ODI", "TEST"],
        help="Cricket format (default: T20I)",
    )
    parser.add_argument(
        "--season",
        default="2024",
        help="Season identifier (default: 2024)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers (default: 4)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Players per batch (default: 100)",
    )
    parser.add_argument(
        "--input-parquet",
        default=None,
        help="Path to enriched deliveries Parquet file.  "
             "If omitted, a synthetic demo dataset is used.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Directory to write the feature matrix Parquet (default: data/models)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _make_demo_df(n_players: int = 5, deliveries_per_player: int = 60) -> pl.DataFrame:
    """Generate a small synthetic deliveries DataFrame for demonstration."""
    import random

    rows = []
    for p_idx in range(n_players):
        pid = f"player_{p_idx:04d}"
        for d_idx in range(deliveries_per_player):
            runs = random.choices([0, 1, 2, 4, 6], weights=[40, 30, 15, 10, 5])[0]
            over_no = d_idx // 6 + 1
            rows.append(
                {
                    "batter_id": pid,
                    "match_id": f"m_{p_idx:03d}_{d_idx // 30:02d}",
                    "innings_number": 1,
                    "over_number": over_no,
                    "ball_in_innings": d_idx + 1,
                    "runs_batter": runs,
                    "runs_total": runs,
                    "is_legal_ball": True,
                    "wicket": False,
                    "spi_total": random.uniform(0, 10),
                    "is_boundary": runs >= 4,
                    "is_home": d_idx % 2 == 0,
                    "target": None,
                    "opposition_elo": random.choice(
                        [1350.0, 1450.0, 1550.0, 1650.0, 1700.0]
                    ),
                }
            )
    return pl.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger(__name__)

    # Load or generate deliveries
    if args.input_parquet:
        log.info("Loading deliveries from %s", args.input_parquet)
        deliveries_df = pl.read_parquet(args.input_parquet)
    else:
        log.info("No --input-parquet provided; using synthetic demo data.")
        deliveries_df = _make_demo_df()

    # Detect player IDs
    player_col = "batter_id" if "batter_id" in deliveries_df.columns else "player_id"
    player_ids = deliveries_df[player_col].unique().to_list()
    log.info(
        "Found %d unique players in deliveries DataFrame.", len(player_ids)
    )

    builder = FeatureBuilder(n_workers=args.workers, batch_size=args.batch_size)

    feature_df = builder.build_all(
        player_ids=player_ids,
        deliveries_df=deliveries_df,
        format_type=args.format_type,
        season=args.season,
        output_dir=args.output_dir,
    )

    log.info(
        "Feature matrix shape: %d players × %d columns",
        len(feature_df),
        len(feature_df.columns),
    )
    if args.verbose:
        print(feature_df.head())


if __name__ == "__main__":
    main()
