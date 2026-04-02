"""Ingestion pipeline orchestrating parse → classify → validate → enrich → write.

Usage::

    from pathlib import Path
    from sovereign.ingestion.pipeline import IngestPipeline

    pipeline = IngestPipeline()
    stats = pipeline.run(Path("data/cricsheet"))
    print(stats)
"""

from __future__ import annotations

import signal
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import structlog

from sovereign.config.settings import settings
from sovereign.enrichment.context import ContextBuilder
from sovereign.enrichment.spi import SPICalculator
from sovereign.ingestion.classifier import MatchClassifier
from sovereign.ingestion.models import IngestStats, ParsedMatch
from sovereign.ingestion.parser import MatchParseError, MatchParser
from sovereign.ingestion.validator import DuplicateDetector, MatchValidator

log = structlog.get_logger(__name__)


def _process_file(path_str: str) -> dict:
    """Worker function: parse + classify + validate a single file.

    Returns a dict with keys:
        status: 'accepted' | 'rejected' | 'failed'
        reason: str (for rejected/failed)
        delivery_count: int
        player_ids: list[str]
    """
    from pathlib import Path as _Path

    path = _Path(path_str)
    parser = MatchParser()
    validator = MatchValidator()

    try:
        match = parser.parse(path)
        if match is None:
            return {"status": "rejected", "reason": "franchise", "delivery_count": 0, "player_ids": []}

        is_valid, errors = validator.validate_match(match)
        if not is_valid:
            return {
                "status": "failed",
                "reason": f"validation: {errors[0]}",
                "delivery_count": 0,
                "player_ids": [],
            }

        player_ids = list(
            {d.batter_id for d in match.deliveries}
            | {d.bowler_id for d in match.deliveries}
        )
        return {
            "status": "accepted",
            "reason": "",
            "delivery_count": len(match.deliveries),
            "player_ids": player_ids,
            "match": match,
        }
    except MatchParseError as exc:
        return {"status": "failed", "reason": str(exc), "delivery_count": 0, "player_ids": []}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "reason": str(exc), "delivery_count": 0, "player_ids": []}


class IngestPipeline:
    """Full ingestion pipeline with parallel file processing.

    Parameters
    ----------
    n_workers:
        Number of parallel workers (defaults to ``settings.ingest_workers``).
    batch_size:
        Files per batch (defaults to ``settings.ingest_batch_size``).
    """

    def __init__(
        self,
        n_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self._n_workers = n_workers or settings.ingest_workers
        self._batch_size = batch_size or settings.ingest_batch_size
        self._shutdown = False

    def run(
        self, cricsheet_dir: Path, sample_mode: Optional[bool] = None
    ) -> IngestStats:
        """Run the full ingestion from *cricsheet_dir*.

        Parameters
        ----------
        cricsheet_dir:
            Directory containing Cricsheet YAML/JSON files.
        sample_mode:
            Override ``settings.ingest_sample_mode``.  When ``True``,
            only the first 500 files are processed.
        """
        start_time = time.time()
        use_sample = sample_mode if sample_mode is not None else settings.ingest_sample_mode

        stats = IngestStats()
        duplicate_detector = DuplicateDetector()
        all_player_ids: set[str] = set()

        # Register graceful shutdown handler
        original_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigint(sig: int, frame: object) -> None:
            log.warning("pipeline_shutdown_requested")
            self._shutdown = True

        signal.signal(signal.SIGINT, _handle_sigint)

        try:
            # Collect files
            paths = self._collect_files(cricsheet_dir)
            if use_sample:
                paths = paths[:500]

            stats.total_files = len(paths)
            log.info("pipeline_start", total_files=stats.total_files, sample_mode=use_sample)

            # Process in batches
            for batch_idx, batch in enumerate(self._batches(paths)):
                if self._shutdown:
                    log.info("pipeline_early_stop", batch=batch_idx)
                    break

                batch_start = time.time()
                self._process_batch(batch, stats, all_player_ids, duplicate_detector)
                elapsed = time.time() - batch_start

                log.info(
                    "batch_complete",
                    batch=batch_idx + 1,
                    files_in_batch=len(batch),
                    accepted=stats.accepted_files,
                    rejected=stats.rejected_franchise,
                    failed=stats.failed_files,
                    deliveries=stats.total_deliveries,
                    batch_seconds=round(elapsed, 2),
                )

        finally:
            signal.signal(signal.SIGINT, original_sigint)

        stats.total_players_unique = len(all_player_ids)
        stats.elapsed_seconds = time.time() - start_time
        log.info(
            "pipeline_complete",
            total_files=stats.total_files,
            accepted=stats.accepted_files,
            rejected=stats.rejected_franchise,
            failed=stats.failed_files,
            deliveries=stats.total_deliveries,
            players=stats.total_players_unique,
            elapsed=round(stats.elapsed_seconds, 2),
        )
        return stats

    def _collect_files(self, directory: Path) -> list[Path]:
        """Recursively collect all YAML/JSON files from *directory*."""
        if not directory.exists():
            log.warning("cricsheet_dir_missing", path=str(directory))
            return []
        files: list[Path] = []
        for ext in ("*.yaml", "*.yml", "*.json"):
            files.extend(directory.rglob(ext))
        files.sort()
        return files

    def _batches(self, paths: list[Path]):
        """Yield successive batches of size *self._batch_size*."""
        for i in range(0, len(paths), self._batch_size):
            yield paths[i : i + self._batch_size]

    def _process_batch(
        self,
        batch: list[Path],
        stats: IngestStats,
        all_player_ids: set[str],
        duplicate_detector: DuplicateDetector,
    ) -> None:
        """Process one batch of files, updating *stats* in place."""
        # Filter duplicates before processing
        unique_batch = [p for p in batch if not duplicate_detector.is_duplicate(p)]

        if not unique_batch:
            return

        # Use process pool for parallel parsing
        results: list[dict] = []
        if self._n_workers > 1:
            with ProcessPoolExecutor(max_workers=self._n_workers) as executor:
                futures = {
                    executor.submit(_process_file, str(p)): p
                    for p in unique_batch
                }
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as exc:  # noqa: BLE001
                        log.error("worker_error", error=str(exc))
                        stats.failed_files += 1
        else:
            # Single-process mode (useful for testing)
            for p in unique_batch:
                results.append(_process_file(str(p)))

        for result in results:
            status = result["status"]
            if status == "accepted":
                stats.accepted_files += 1
                stats.total_deliveries += result["delivery_count"]
                all_player_ids.update(result["player_ids"])
            elif status == "rejected":
                stats.rejected_franchise += 1
            else:
                stats.failed_files += 1
