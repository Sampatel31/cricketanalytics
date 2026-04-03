"""Fit HDBSCAN on UMAP-reduced player coordinates and discover archetypes.

Reads the 10D UMAP coordinate pickle produced by ``train_umap.py``, fits
HDBSCAN, runs bootstrap stability validation, and writes cluster labels +
archetype definitions.  Optionally stores results in the ``hdbscan_clusters``
DB table.

Usage::

    python scripts/train_hdbscan.py --format T20I --umap-model data/models/umap_coords_T20I.pkl
    python scripts/train_hdbscan.py --format T20I --umap-model data/models/umap_coords_T20I.pkl --bootstrap-runs 1000
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import pickle
import sys
import time

# Ensure the project root is on the Python path when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import numpy as np


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fit HDBSCAN on UMAP 10D coordinates to discover player archetypes. "
            "Includes bootstrap stability validation."
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
        "--umap-model",
        required=True,
        help=(
            "Path to the UMAP coordinates pickle (.pkl) produced by train_umap.py, "
            "OR path to the Parquet feature matrix to use directly."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Directory to save HDBSCAN models and cluster labels (default: data/models)",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=15,
        help="HDBSCAN min_cluster_size (default: 15)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=15,
        help="HDBSCAN min_samples (default: 15)",
    )
    parser.add_argument(
        "--ari-threshold",
        type=float,
        default=0.85,
        help="Minimum mean ARI for stable clustering (default: 0.85)",
    )
    parser.add_argument(
        "--bootstrap-runs",
        type=int,
        default=1000,
        help="Number of bootstrap validation runs (default: 1000)",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip bootstrap stability validation",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Store cluster labels + centroids in the hdbscan_clusters DB table",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _load_coords(umap_model_path: pathlib.Path) -> tuple[np.ndarray, list]:
    """Load 10D UMAP coordinates from a pickle file.

    Returns:
        Tuple of (coords_10d ndarray, player_ids list).
    """
    with umap_model_path.open("rb") as fh:
        data = pickle.load(fh)
    if isinstance(data, dict):
        coords_10d = data.get("coords_10d", data.get("coords"))
        player_ids = data.get("player_ids", list(range(len(coords_10d))))
    else:
        # Raw ndarray
        coords_10d = np.asarray(data)
        player_ids = list(range(len(coords_10d)))
    return coords_10d, player_ids


def _save_to_db(
    format_type: str,
    labels: np.ndarray,
    centroids: np.ndarray,
) -> None:
    """Upsert cluster labels + centroids into the ``hdbscan_clusters`` table."""
    import sqlalchemy as sa

    from sovereign.config.settings import get_settings

    settings = get_settings()
    engine = sa.create_engine(settings.database_url)
    centroids_json = json.dumps(centroids.tolist())
    # Store labels as JSON-encoded bytes (not pickle) to avoid unsafe deserialisation.
    labels_bytes = json.dumps(labels.tolist()).encode("utf-8")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO hdbscan_clusters (format_type, labels, centroids, fitted_at)
                VALUES (:fmt, :labels, cast(:centroids AS jsonb), now())
                ON CONFLICT (format_type)
                DO UPDATE SET labels    = EXCLUDED.labels,
                              centroids = EXCLUDED.centroids,
                              fitted_at = EXCLUDED.fitted_at
                """
            ),
            {"fmt": format_type, "labels": labels_bytes, "centroids": centroids_json},
        )


def main(argv: list[str] | None = None) -> int:
    """Entry point for HDBSCAN training."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("train_hdbscan")

    umap_path = pathlib.Path(args.umap_model)
    if not umap_path.exists():
        log.error("UMAP model/coords file not found: %s", umap_path)
        return 1

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Load UMAP coordinates                                                #
    # ------------------------------------------------------------------ #
    log.info("Loading UMAP 10D coordinates from %s", umap_path)
    coords_10d, player_ids = _load_coords(umap_path)
    log.info("Loaded %d player coordinate vectors (%dD)", *coords_10d.shape)

    # ------------------------------------------------------------------ #
    # Fit HDBSCAN                                                          #
    # ------------------------------------------------------------------ #
    from sovereign.intelligence.clusterer import ArchetypeClusterer
    from sovereign.intelligence.models import UnstableClusteringError

    clusterer = ArchetypeClusterer(
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
        ari_threshold=args.ari_threshold,
    )

    t_start = time.perf_counter()
    log.info(
        "Fitting HDBSCAN (min_cluster_size=%d, min_samples=%d)",
        args.min_cluster_size,
        args.min_samples,
    )
    clusterer.fit(coords_10d)
    t_fit = time.perf_counter() - t_start

    labels = clusterer.get_labels()
    centroids = clusterer.get_centroids()
    stats = clusterer.get_stats()

    n_clusters = stats.n_clusters if stats else len(np.unique(labels))
    n_noise = stats.n_noise_points if stats else 0
    silhouette = stats.silhouette_score if stats else 0.0
    dbi = stats.davies_bouldin_index if stats else 0.0

    log.info(
        "HDBSCAN fit in %.1fs → %d clusters, %d noise points, "
        "silhouette=%.3f, DBI=%.3f",
        t_fit,
        n_clusters,
        n_noise,
        silhouette,
        dbi,
    )

    # ------------------------------------------------------------------ #
    # Bootstrap validation                                                 #
    # ------------------------------------------------------------------ #
    mean_ari = 0.0
    std_ari = 0.0
    if not args.skip_bootstrap and args.bootstrap_runs > 0:
        log.info("Running %d bootstrap validation runs…", args.bootstrap_runs)
        t_boot = time.perf_counter()
        try:
            boot_result = clusterer.bootstrap_validate(
                coords_10d,
                n_runs=args.bootstrap_runs,
                subsample_ratio=0.8,
            )
            mean_ari = boot_result["mean_ari"]
            std_ari = boot_result["std_ari"]
            log.info(
                "Bootstrap ARI: mean=%.3f ± %.3f (threshold=%.2f) [%.1fs]",
                mean_ari,
                std_ari,
                args.ari_threshold,
                time.perf_counter() - t_boot,
            )
        except UnstableClusteringError as exc:
            log.warning(
                "Clustering stability warning: %s  "
                "(continuing with best result)",
                exc,
            )
            mean_ari = exc.mean_ari
        except Exception as exc:
            log.warning("Bootstrap validation error: %s", exc)
    else:
        log.info("Bootstrap validation skipped.")

    # ------------------------------------------------------------------ #
    # Save models and cluster labels                                       #
    # ------------------------------------------------------------------ #
    # Pickled HDBSCAN object
    hdbscan_pkl = output_dir / f"hdbscan_{args.format_type}.pkl"
    with hdbscan_pkl.open("wb") as fh:
        pickle.dump(clusterer, fh)
    log.info("Saved HDBSCAN model to %s", hdbscan_pkl)

    # Labels + centroids + player mapping
    labels_path = output_dir / f"cluster_labels_{args.format_type}.pkl"
    with labels_path.open("wb") as fh:
        pickle.dump(
            {
                "format_type": args.format_type,
                "labels": labels,
                "centroids": centroids,
                "player_ids": player_ids,
                "n_clusters": n_clusters,
                "silhouette": silhouette,
                "mean_ari": mean_ari,
            },
            fh,
        )
    log.info("Saved cluster labels to %s", labels_path)

    # Human-readable archetype summary
    summary_path = output_dir / f"cluster_summary_{args.format_type}.json"
    unique_labels = sorted(np.unique(labels).tolist())
    archetype_dist = {
        f"ARC_{int(lbl):03d}": int((labels == lbl).sum())
        for lbl in unique_labels
    }
    summary = {
        "format_type": args.format_type,
        "n_clusters": n_clusters,
        "n_noise_points": n_noise,
        "silhouette_score": round(silhouette, 4),
        "davies_bouldin_index": round(dbi, 4),
        "stability_ari_mean": round(mean_ari, 4),
        "stability_ari_std": round(std_ari, 4),
        "archetype_distribution": archetype_dist,
    }
    with summary_path.open("w") as fh:
        json.dump(summary, fh, indent=2)
    log.info("Saved cluster summary to %s", summary_path)

    # ------------------------------------------------------------------ #
    # Optionally persist to DB                                             #
    # ------------------------------------------------------------------ #
    if args.save_db:
        log.info("Saving cluster results to DB (hdbscan_clusters table)…")
        try:
            _save_to_db(args.format_type, labels, centroids)
            log.info("Cluster results stored in DB for format %s", args.format_type)
        except Exception as exc:
            log.warning(
                "Could not save cluster results to DB (format=%s): %s",
                args.format_type,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------ #
    # Summary output                                                       #
    # ------------------------------------------------------------------ #
    elapsed = time.perf_counter() - t_start
    print(
        f"\n✓ HDBSCAN training complete in {elapsed:.1f}s\n"
        f"  Format            : {args.format_type}\n"
        f"  Players           : {len(labels)}\n"
        f"  Clusters found    : {n_clusters}\n"
        f"  Noise points      : {n_noise}\n"
        f"  Silhouette score  : {silhouette:.4f}\n"
        f"  Davies-Bouldin    : {dbi:.4f}\n"
        f"  Stability ARI     : {mean_ari:.4f} ± {std_ari:.4f}\n"
        f"  Models saved to   : {output_dir}"
    )
    print("\n  Archetype distribution:")
    for arc_code, count in archetype_dist.items():
        pct = 100.0 * count / max(len(labels), 1)
        print(f"    {arc_code}: {count:4d} players ({pct:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
