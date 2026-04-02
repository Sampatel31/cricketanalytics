#!/usr/bin/env python3
"""CLI script for archetype discovery.

Usage::

    python scripts/discover_archetypes.py \\
        --features-parquet data/models/features_matrix_T20I_2024.parquet \\
        --format-type T20I \\
        --season 2024 \\
        --min-cluster-size 15 \\
        --bootstrap-runs 100 \\
        --output-dir data/models \\
        --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover player archetypes via UMAP + HDBSCAN"
    )
    parser.add_argument(
        "--features-parquet",
        required=True,
        help="Path to feature matrix Parquet file",
    )
    parser.add_argument("--format-type", default="T20I", help="Cricket format")
    parser.add_argument("--season", default="2024", help="Season identifier")
    parser.add_argument(
        "--min-cluster-size", type=int, default=15, help="HDBSCAN min cluster size"
    )
    parser.add_argument(
        "--bootstrap-runs", type=int, default=100, help="Bootstrap validation runs"
    )
    parser.add_argument(
        "--output-dir", default="data/models", help="Output directory"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip bootstrap stability validation",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("discover_archetypes")

    import polars as pl

    from sovereign.intelligence.archetype import ArchetypeDiscoverer
    from sovereign.intelligence.clusterer import ArchetypeClusterer
    from sovereign.intelligence.reducer import DimensionalityReducer

    parquet_path = pathlib.Path(args.features_parquet)
    if not parquet_path.exists():
        logger.error("Features Parquet not found: %s", parquet_path)
        return 1

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading features from %s", parquet_path)
    features_df = pl.read_parquet(str(parquet_path))
    logger.info("Loaded %d players", len(features_df))

    # Step 1: dimensionality reduction
    reducer = DimensionalityReducer(models_dir=output_dir)
    reducer.fit(features_df, force=True)

    coords_cluster = reducer.transform_clustering(features_df)
    logger.info("Reduced to %s for clustering", coords_cluster.shape)

    # Step 2: clustering
    clusterer = ArchetypeClusterer(
        min_cluster_size=args.min_cluster_size, ari_threshold=0.0
    )
    clusterer.fit(coords_cluster)
    labels = clusterer.get_labels()
    centroids = clusterer.get_centroids()
    stats = clusterer.get_stats()
    if stats:
        logger.info(
            "Found %d clusters, %d noise points, silhouette=%.3f",
            stats.n_clusters,
            stats.n_noise_points,
            stats.silhouette_score,
        )

    # Step 3: bootstrap (optional)
    stability_ari = 0.0
    if not args.skip_bootstrap and args.bootstrap_runs > 0:
        logger.info("Running %d bootstrap validation runs…", args.bootstrap_runs)
        try:
            boot = clusterer.bootstrap_validate(
                coords_cluster,
                n_runs=args.bootstrap_runs,
                subsample_ratio=0.8,
            )
            stability_ari = boot["mean_ari"]
            logger.info(
                "Bootstrap ARI: mean=%.3f std=%.3f",
                boot["mean_ari"],
                boot["std_ari"],
            )
        except Exception as exc:
            logger.warning("Bootstrap validation warning: %s", exc)

    # Step 4: archetype discovery
    discoverer = ArchetypeDiscoverer()
    archetypes = discoverer.discover(
        coords_cluster,
        features_df,
        labels,
        centroids,
        stability_ari=stability_ari,
    )
    logger.info("Discovered %d archetypes", len(archetypes))

    # Save archetypes as JSON
    out_name = f"archetypes_{args.format_type}_{args.season}.json"
    out_path = output_dir / out_name
    arc_dicts = [a.model_dump(mode="json") for a in archetypes]
    with out_path.open("w") as fh:
        json.dump(arc_dicts, fh, indent=2, default=str)
    logger.info("Archetypes saved to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
