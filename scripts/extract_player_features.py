"""Extract 54-dimensional player feature vectors from raw delivery data.

Usage::

    python scripts/extract_player_features.py --format T20I --season 2024 --output-dir data/models
    python scripts/extract_player_features.py --format ODI --season 2024 --input-parquet data/deliveries.parquet
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import time

# Ensure the project root is on the Python path when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import polars as pl

from sovereign.features.builder import FeatureBuilder


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract 54-dimensional player feature vectors from raw delivery data. "
            "Aggregates by player × format × season and outputs Parquet files."
        )
    )
    parser.add_argument(
        "--format",
        dest="format_type",
        default="T20I",
        choices=["T20I", "ODI", "TEST"],
        help="Cricket format to extract features for (default: T20I)",
    )
    parser.add_argument(
        "--season",
        default="2024",
        help="Season identifier, e.g. 2024 (default: 2024)",
    )
    parser.add_argument(
        "--input-parquet",
        default=None,
        help=(
            "Path to enriched deliveries Parquet file. "
            "If omitted, a synthetic demo dataset is used."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Directory to write Parquet feature matrix (default: data/models)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers for feature computation (default: 4)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of players processed per batch (default: 100)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _make_demo_deliveries(
    n_players: int = 20,
    deliveries_per_player: int = 120,
) -> pl.DataFrame:
    """Build a small synthetic deliveries DataFrame for smoke-testing."""
    import random

    random.seed(42)
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


def main(argv: list[str] | None = None) -> int:
    """Entry point for feature extraction."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("extract_player_features")

    t_start = time.perf_counter()

    # ------------------------------------------------------------------ #
    # Load deliveries                                                      #
    # ------------------------------------------------------------------ #
    if args.input_parquet:
        log.info("Loading deliveries from %s", args.input_parquet)
        deliveries_df = pl.read_parquet(args.input_parquet)
    else:
        log.info("No --input-parquet provided; using synthetic demo data.")
        deliveries_df = _make_demo_deliveries()

    player_col = "batter_id" if "batter_id" in deliveries_df.columns else "player_id"
    player_ids = deliveries_df[player_col].unique().to_list()
    log.info(
        "Loaded %d deliveries for %d unique players.",
        len(deliveries_df),
        len(player_ids),
    )

    # ------------------------------------------------------------------ #
    # Build feature matrix                                                 #
    # ------------------------------------------------------------------ #
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    builder = FeatureBuilder(n_workers=args.workers, batch_size=args.batch_size)
    feature_df = builder.build_all(
        player_ids=player_ids,
        deliveries_df=deliveries_df,
        format_type=args.format_type,
        season=args.season,
        output_dir=str(output_dir),
    )

    n_players, n_cols = feature_df.shape
    n_feature_cols = n_cols - 5  # subtract metadata columns
    log.info(
        "Feature matrix: %d players × %d feature columns",
        n_players,
        n_feature_cols,
    )

    # ------------------------------------------------------------------ #
    # Save Parquet                                                         #
    # ------------------------------------------------------------------ #
    out_name = f"features_{args.format_type}_{args.season}.parquet"
    out_path = output_dir / out_name
    feature_df.write_parquet(str(out_path))
    log.info("Saved feature matrix to %s", out_path)

    elapsed = time.perf_counter() - t_start
    print(
        f"\n✓ Feature extraction complete in {elapsed:.1f}s\n"
        f"  Format : {args.format_type}\n"
        f"  Season : {args.season}\n"
        f"  Players: {n_players}\n"
        f"  Columns: {n_cols} ({n_feature_cols} features + metadata)\n"
        f"  Output : {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
