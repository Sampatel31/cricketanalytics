#!/usr/bin/env python3
"""Download the latest Cricsheet data archive.

Usage::

    python scripts/download_cricsheet.py \
        --output-dir data/cricsheet
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# Ensure the repository root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

# Cricsheet bulk downloads
_ALL_MATCHES_URL = "https://cricsheet.org/downloads/all_json.zip"
_YAML_URL = "https://cricsheet.org/downloads/all.zip"

log = structlog.get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Cricsheet data files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/cricsheet"),
        help="Directory to save downloaded files",
    )
    parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Download YAML or JSON archives",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        default=False,
        help="Keep the zip archive after extracting",
    )
    return parser


def _progress_hook(count: int, block_size: int, total_size: int) -> None:
    if total_size > 0:
        pct = min(100, count * block_size * 100 // total_size)
        sys.stdout.write(f"\rDownloading... {pct}%")
        sys.stdout.flush()


def main() -> int:
    args = _build_parser().parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    url = _YAML_URL if args.format == "yaml" else _ALL_MATCHES_URL
    zip_path = output_dir / f"cricsheet_{args.format}.zip"

    log.info("download_start", url=url, dest=str(zip_path))
    print(f"Downloading from {url} …")

    try:
        urlretrieve(url, zip_path, reporthook=_progress_hook)
        print()  # newline after progress
    except Exception as exc:
        log.error("download_failed", url=url, error=str(exc))
        print(f"\nERROR: Download failed: {exc}", file=sys.stderr)
        return 1

    # Extract
    print(f"Extracting to {output_dir} …")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)
    except zipfile.BadZipFile as exc:
        log.error("extract_failed", path=str(zip_path), error=str(exc))
        print(f"ERROR: Extraction failed: {exc}", file=sys.stderr)
        return 1

    if not args.keep_zip:
        zip_path.unlink(missing_ok=True)

    # Count downloaded files
    ext = "*.yaml" if args.format == "yaml" else "*.json"
    count = len(list(output_dir.rglob(ext)))
    print(f"Done. {count:,} {args.format.upper()} files available in {output_dir}")
    log.info("download_complete", files=count, output_dir=str(output_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
