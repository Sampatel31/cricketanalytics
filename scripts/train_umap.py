"""Train a UMAP dimensionality reducer on a player feature matrix.

Reduces 54-dimensional behavioral fingerprints to 10D (for HDBSCAN clustering)
and 2D (for galaxy-view visualisation).  Saves pickled models to
``data/models/`` and optionally stores them in the ``umap_models`` DB table.

Usage::

    python scripts/train_umap.py --format T20I --features-file data/models/features_T20I_2024.parquet
    python scripts/train_umap.py --format ODI  --features-file data/models/features_ODI_2024.parquet --output-dir data/models
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import pickle
import sys
import time

# Ensure the project root is on the Python path when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import polars as pl

from sovereign.intelligence.reducer import DimensionalityReducer


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train UMAP dimensionality reduction models on a 54D player feature "
            "matrix.  Produces 10D coordinates for clustering and 2D for "
            "visualisation."
        )
    )
    parser.add_argument(
        "--format",
        dest="format_type",
        default="T20I",
        choices=["T20I", "ODI", "TEST"],
        help="Cricket format (default: T20I)",
    )
    parser.add_argument(
        "--features-file",
        required=True,
        help="Path to the Parquet feature matrix produced by extract_player_features.py",
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Directory to save pickled UMAP models (default: data/models)",
    )
    parser.add_argument(
        "--n-components-cluster",
        type=int,
        default=10,
        help="UMAP output dimensions for clustering (default: 10)",
    )
    parser.add_argument(
        "--n-components-viz",
        type=int,
        default=2,
        help="UMAP output dimensions for visualisation (default: 2)",
    )
    parser.add_argument(
        "--n-neighbors",
        type=int,
        default=15,
        help="UMAP n_neighbors hyperparameter (default: 15)",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=0.1,
        help="UMAP min_dist hyperparameter (default: 0.1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refit even if cached models exist",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Store serialised model in the umap_models DB table (requires DB)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _save_to_db(format_type: str, model_blob: bytes) -> None:
    """Upsert a serialised UMAP reducer into the ``umap_models`` table."""
    import sqlalchemy as sa

    from sovereign.config.settings import get_settings

    settings = get_settings()
    engine = sa.create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO umap_models (format_type, model_data, fitted_at)
                VALUES (:fmt, :data, now())
                ON CONFLICT (format_type)
                DO UPDATE SET model_data = EXCLUDED.model_data,
                              fitted_at  = EXCLUDED.fitted_at
                """
            ),
            {"fmt": format_type, "data": model_blob},
        )


def main(argv: list[str] | None = None) -> int:
    """Entry point for UMAP training."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("train_umap")

    features_path = pathlib.Path(args.features_file)
    if not features_path.exists():
        log.error("Features file not found: %s", features_path)
        return 1

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Load features                                                        #
    # ------------------------------------------------------------------ #
    log.info("Loading features from %s", features_path)
    features_df = pl.read_parquet(str(features_path))
    log.info(
        "Loaded feature matrix: %d players × %d columns",
        len(features_df),
        len(features_df.columns),
    )

    # ------------------------------------------------------------------ #
    # Train UMAP                                                           #
    # ------------------------------------------------------------------ #
    # Use per-format model paths so multiple formats can coexist.
    reducer = DimensionalityReducer(
        models_dir=output_dir,
        random_state=42,
    )
    # Override the default path names to be format-specific.
    reducer._SCALER_PATH = f"umap_scaler_{args.format_type}.joblib"
    reducer._UMAP_CLUSTER_PATH = f"umap_10d_{args.format_type}.joblib"
    reducer._UMAP_VIZ_PATH = f"umap_2d_{args.format_type}.joblib"

    t_start = time.perf_counter()
    log.info(
        "Training UMAP (n_neighbors=%d, min_dist=%.2f, cluster_dim=%d, viz_dim=%d)",
        args.n_neighbors,
        args.min_dist,
        args.n_components_cluster,
        args.n_components_viz,
    )

    reducer.fit(
        features_df,
        n_components_cluster=args.n_components_cluster,
        n_components_viz=args.n_components_viz,
        force=args.force,
    )

    elapsed = time.perf_counter() - t_start
    log.info("UMAP training completed in %.1fs", elapsed)

    # ------------------------------------------------------------------ #
    # Produce and save transformed coordinates                             #
    # ------------------------------------------------------------------ #
    coords_10d = reducer.transform_clustering(features_df)
    coords_2d = reducer.transform_viz(features_df)
    log.info("Cluster coords shape  : %s", coords_10d.shape)
    log.info("Viz coords shape      : %s", coords_2d.shape)

    coords_path = output_dir / f"umap_coords_{args.format_type}.pkl"
    with coords_path.open("wb") as fh:
        pickle.dump(
            {
                "format_type": args.format_type,
                "coords_10d": coords_10d,
                "coords_2d": coords_2d,
                "player_ids": (
                    features_df["player_id"].to_list()
                    if "player_id" in features_df.columns
                    else list(range(len(features_df)))
                ),
            },
            fh,
        )
    log.info("Saved UMAP coordinates to %s", coords_path)

    # ------------------------------------------------------------------ #
    # Optionally persist model to DB                                       #
    # ------------------------------------------------------------------ #
    if args.save_db:
        log.info("Saving UMAP model to DB (umap_models table)…")
        try:
            import joblib
            import io

            buf = io.BytesIO()
            joblib.dump(reducer, buf)
            _save_to_db(args.format_type, buf.getvalue())
            log.info("UMAP model stored in DB for format %s", args.format_type)
        except Exception as exc:
            log.warning("Could not save UMAP model to DB: %s", exc)

    print(
        f"\n✓ UMAP training complete in {elapsed:.1f}s\n"
        f"  Format          : {args.format_type}\n"
        f"  Players         : {len(features_df)}\n"
        f"  Input dims      : {features_df.shape[1]} columns\n"
        f"  Cluster dims    : {args.n_components_cluster}D\n"
        f"  Viz dims        : {args.n_components_viz}D\n"
        f"  Coords output   : {coords_path}\n"
        f"  Models saved to : {output_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
