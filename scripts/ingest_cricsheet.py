#!/usr/bin/env python3
"""CLI script to run the Cricsheet data ingestion pipeline.

Usage::

    python scripts/ingest_cricsheet.py \
        --cricsheet-dir data/cricsheet \
        --sample-mode \
        --batch-size 500 \
        --verbose
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the repository root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from sovereign.config.settings import settings
from sovereign.ingestion.pipeline import IngestPipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest Cricsheet data files into PostgreSQL",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--cricsheet-dir",
        type=Path,
        default=Path("data/cricsheet"),
        help="Directory containing Cricsheet YAML/JSON files",
    )
    parser.add_argument(
        "--sample-mode",
        action="store_true",
        default=False,
        help="Only process the first 500 files",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.ingest_batch_size,
        help="Number of files per processing batch",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=settings.ingest_workers,
        help="Number of parallel worker processes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug-level logging",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    # Configure logging
    import logging

    log_level = "DEBUG" if args.verbose else "INFO"
    logging.basicConfig(level=getattr(logging, log_level))
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
    )

    log = structlog.get_logger(__name__)
    log.info(
        "ingest_start",
        cricsheet_dir=str(args.cricsheet_dir),
        sample_mode=args.sample_mode,
        batch_size=args.batch_size,
        workers=args.workers,
    )

    pipeline = IngestPipeline(
        n_workers=args.workers,
        batch_size=args.batch_size,
    )

    stats = pipeline.run(args.cricsheet_dir, sample_mode=args.sample_mode)

    # Print summary
    print("\n=== Ingestion Complete ===")
    print(f"  Total files:         {stats.total_files:,}")
    print(f"  Accepted:            {stats.accepted_files:,}")
    print(f"  Rejected (franchise): {stats.rejected_franchise:,}")
    print(f"  Failed:              {stats.failed_files:,}")
    print(f"  Total deliveries:    {stats.total_deliveries:,}")
    print(f"  Unique players:      {stats.total_players_unique:,}")
    print(f"  Elapsed:             {stats.elapsed_seconds:.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
