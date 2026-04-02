"""Tests for IngestPipeline (sovereign/ingestion/pipeline.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sovereign.ingestion.pipeline import IngestPipeline, _process_file

SAMPLE_DIR = Path(__file__).parent / "sample_data"


def test_process_file_accepted():
    """_process_file returns 'accepted' for a valid non-franchise file."""
    result = _process_file(str(SAMPLE_DIR / "t20i_v2.yaml"))
    assert result["status"] == "accepted"
    assert result["delivery_count"] > 0
    assert len(result["player_ids"]) > 0


def test_process_file_franchise():
    """_process_file returns 'rejected' for a franchise file."""
    result = _process_file(str(SAMPLE_DIR / "ipl_franchise.yaml"))
    assert result["status"] == "rejected"
    assert result["reason"] == "franchise"


def test_process_file_missing():
    """_process_file returns 'failed' for a nonexistent file."""
    result = _process_file("/tmp/does_not_exist_xyz.yaml")
    assert result["status"] == "failed"


def test_sample_mode_limits_files(tmp_path: Path):
    """Sample mode limits processing to at most 500 files."""
    # Copy sample files into a temp dir
    import shutil

    for f in SAMPLE_DIR.glob("*.yaml"):
        shutil.copy(f, tmp_path / f.name)

    pipeline = IngestPipeline(n_workers=1, batch_size=500)
    stats = pipeline.run(tmp_path, sample_mode=True)
    # sample_mode=True, so at most 500 files processed
    assert stats.total_files <= 500


def test_franchise_files_counted(tmp_path: Path):
    """Franchise files are counted in rejected_franchise."""
    import shutil

    shutil.copy(SAMPLE_DIR / "ipl_franchise.yaml", tmp_path / "ipl_franchise.yaml")
    shutil.copy(SAMPLE_DIR / "t20i_v2.yaml", tmp_path / "t20i_v2.yaml")

    pipeline = IngestPipeline(n_workers=1, batch_size=500)
    stats = pipeline.run(tmp_path)

    assert stats.rejected_franchise >= 1
    assert stats.accepted_files >= 1


def test_ingest_stats_populated(tmp_path: Path):
    """IngestStats has correct field types after a run."""
    import shutil

    shutil.copy(SAMPLE_DIR / "t20i_v2.yaml", tmp_path / "t20i_v2.yaml")
    shutil.copy(SAMPLE_DIR / "odi_final_v2.yaml", tmp_path / "odi_final_v2.yaml")

    pipeline = IngestPipeline(n_workers=1, batch_size=500)
    stats = pipeline.run(tmp_path)

    assert stats.total_files == 2
    assert stats.total_deliveries > 0
    assert stats.total_players_unique > 0
    assert stats.elapsed_seconds >= 0.0


def test_duplicate_files_skipped(tmp_path: Path):
    """The same file processed twice is only counted once."""
    import shutil

    src = SAMPLE_DIR / "t20i_v2.yaml"
    shutil.copy(src, tmp_path / "t20i_v2.yaml")
    # Copy the same file with a different name to test the hash-based dedup
    # (same content = same hash)
    shutil.copy(src, tmp_path / "t20i_v2_copy.yaml")

    pipeline = IngestPipeline(n_workers=1, batch_size=500)
    stats = pipeline.run(tmp_path)

    # Only one of the two identical files should be accepted
    assert stats.accepted_files == 1


def test_missing_directory():
    """Running on a missing directory returns empty stats."""
    pipeline = IngestPipeline(n_workers=1, batch_size=500)
    stats = pipeline.run(Path("/tmp/nonexistent_dir_xyz"))
    assert stats.total_files == 0
    assert stats.accepted_files == 0
