"""Orchestrate the full ML training pipeline: features → UMAP → HDBSCAN.

Runs all three phases end-to-end for one or more cricket formats and a given
season.  Each phase is timed individually and a summary is printed at the end.

Usage::

    # Single format
    python scripts/train_all_models.py --format T20I --season 2024

    # Multiple formats
    python scripts/train_all_models.py --format T20I,ODI,TEST --season 2024

    # With custom deliveries Parquet
    python scripts/train_all_models.py --format T20I --season 2024 \\
        --input-parquet data/deliveries.parquet

    # Skip bootstrap for faster runs
    python scripts/train_all_models.py --format T20I --season 2024 --skip-bootstrap
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import time

# Ensure the project root is on the Python path when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

_SCRIPTS_DIR = pathlib.Path(__file__).parent


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end ML training pipeline: "
            "Phase 1 (feature extraction) → Phase 2 (UMAP) → Phase 3 (HDBSCAN)."
        )
    )
    parser.add_argument(
        "--format",
        dest="formats",
        default="T20I",
        help=(
            "Comma-separated list of formats to train (e.g. T20I,ODI,TEST). "
            "Default: T20I"
        ),
    )
    parser.add_argument(
        "--season",
        default="2024",
        help="Season identifier (default: 2024)",
    )
    parser.add_argument(
        "--input-parquet",
        default=None,
        help=(
            "Path to enriched deliveries Parquet file. "
            "If omitted, synthetic demo data is used for each format."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="data/models",
        help="Root directory for all model and feature artefacts (default: data/models)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers for feature computation (default: 4)",
    )
    parser.add_argument(
        "--bootstrap-runs",
        type=int,
        default=1000,
        help="Bootstrap validation runs for HDBSCAN (default: 1000)",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip bootstrap stability validation (faster, less reliable)",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Persist model artefacts to the PostgreSQL database",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _run_phase(
    phase_name: str,
    module_main,
    argv: list[str],
    log: logging.Logger,
) -> tuple[bool, float]:
    """Run one pipeline phase by calling its ``main()`` function.

    Returns:
        Tuple of (success: bool, elapsed_seconds: float).
    """
    t0 = time.perf_counter()
    log.info("▶ %s  args=%s", phase_name, " ".join(argv))
    try:
        rc = module_main(argv)
        elapsed = time.perf_counter() - t0
        if rc != 0:
            log.error("✗ %s failed (rc=%d)", phase_name, rc)
            return False, elapsed
        log.info("✓ %s completed in %.1fs", phase_name, elapsed)
        return True, elapsed
    except SystemExit as exc:
        elapsed = time.perf_counter() - t0
        if exc.code == 0:
            return True, elapsed
        log.error("✗ %s exited with code %s", phase_name, exc.code)
        return False, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        log.exception("✗ %s raised an exception: %s", phase_name, exc)
        return False, elapsed


def _train_format(
    fmt: str,
    season: str,
    output_dir: pathlib.Path,
    args: argparse.Namespace,
    log: logging.Logger,
) -> dict:
    """Run all three pipeline phases for a single *fmt* / *season* combination.

    Returns:
        A summary dict with timing and success flags for each phase.
    """
    # Lazy imports so each phase module can also be run standalone.
    import importlib.util

    def _load_module(script_name: str):
        spec = importlib.util.spec_from_file_location(
            script_name.replace(".py", ""),
            str(_SCRIPTS_DIR / script_name),
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    summary: dict = {"format": fmt, "season": season, "phases": {}}

    # ------------------------------------------------------------------
    # Phase 1: Feature Extraction
    # ------------------------------------------------------------------
    features_parquet = output_dir / f"features_{fmt}_{season}.parquet"
    phase1_argv = [
        "--format", fmt,
        "--season", season,
        "--output-dir", str(output_dir),
        "--workers", str(args.workers),
    ]
    if args.input_parquet:
        phase1_argv += ["--input-parquet", args.input_parquet]
    if args.verbose:
        phase1_argv.append("--verbose")

    extract_mod = _load_module("extract_player_features.py")
    ok1, t1 = _run_phase("Phase 1 – Feature Extraction", extract_mod.main, phase1_argv, log)
    summary["phases"]["feature_extraction"] = {"ok": ok1, "elapsed_s": round(t1, 2)}

    if not ok1:
        log.error("Aborting pipeline for format %s due to Phase 1 failure.", fmt)
        return summary

    # ------------------------------------------------------------------
    # Phase 2: UMAP Training
    # ------------------------------------------------------------------
    phase2_argv = [
        "--format", fmt,
        "--features-file", str(features_parquet),
        "--output-dir", str(output_dir),
        "--force",
    ]
    if args.save_db:
        phase2_argv.append("--save-db")
    if args.verbose:
        phase2_argv.append("--verbose")

    umap_mod = _load_module("train_umap.py")
    ok2, t2 = _run_phase("Phase 2 – UMAP Training", umap_mod.main, phase2_argv, log)
    summary["phases"]["umap_training"] = {"ok": ok2, "elapsed_s": round(t2, 2)}

    if not ok2:
        log.error("Aborting pipeline for format %s due to Phase 2 failure.", fmt)
        return summary

    # ------------------------------------------------------------------
    # Phase 3: HDBSCAN Training
    # ------------------------------------------------------------------
    umap_coords = output_dir / f"umap_coords_{fmt}.pkl"
    phase3_argv = [
        "--format", fmt,
        "--umap-model", str(umap_coords),
        "--output-dir", str(output_dir),
        "--bootstrap-runs", str(args.bootstrap_runs),
    ]
    if args.skip_bootstrap:
        phase3_argv.append("--skip-bootstrap")
    if args.save_db:
        phase3_argv.append("--save-db")
    if args.verbose:
        phase3_argv.append("--verbose")

    hdbscan_mod = _load_module("train_hdbscan.py")
    ok3, t3 = _run_phase("Phase 3 – HDBSCAN Training", hdbscan_mod.main, phase3_argv, log)
    summary["phases"]["hdbscan_training"] = {"ok": ok3, "elapsed_s": round(t3, 2)}

    return summary


def main(argv: list[str] | None = None) -> int:
    """Entry point for the combined training orchestrator."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("train_all_models")

    formats = [f.strip().upper() for f in args.formats.split(",") if f.strip()]
    valid = {"T20I", "ODI", "TEST"}
    invalid = [f for f in formats if f not in valid]
    if invalid:
        log.error("Unknown format(s): %s (valid: %s)", invalid, sorted(valid))
        return 1

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_wall = time.perf_counter()
    all_summaries = []

    for fmt in formats:
        log.info("=" * 60)
        log.info("Training pipeline for format: %s  season: %s", fmt, args.season)
        log.info("=" * 60)
        summary = _train_format(fmt, args.season, output_dir, args, log)
        all_summaries.append(summary)

    elapsed_total = time.perf_counter() - t_wall

    # ------------------------------------------------------------------ #
    # Print summary table                                                  #
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("TRAINING PIPELINE SUMMARY")
    print("=" * 60)
    print(f"{'Format':<8} {'Phase':<30} {'Status':<8} {'Time':>8}")
    print("-" * 60)

    all_ok = True
    for s in all_summaries:
        fmt = s["format"]
        for phase_key, phase_info in s["phases"].items():
            status = "✓ OK" if phase_info["ok"] else "✗ FAIL"
            t = phase_info["elapsed_s"]
            if not phase_info["ok"]:
                all_ok = False
            label = phase_key.replace("_", " ").title()
            print(f"{fmt:<8} {label:<30} {status:<8} {t:>6.1f}s")

    print("-" * 60)
    print(f"{'Total':<38} {elapsed_total:>6.1f}s")
    print("=" * 60)

    if all_ok:
        print(f"\n✓ All formats completed successfully.  Output: {output_dir}")
        return 0
    else:
        print("\n✗ One or more phases failed.  Check logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
