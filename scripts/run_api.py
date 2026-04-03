"""CLI runner for the Sovereign API server.

Usage::

    python scripts/run_api.py --host 0.0.0.0 --port 8000 --workers 4 --reload
"""

from __future__ import annotations

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Sovereign Cricket Analytics API server"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--workers", type=int, default=4, help="Uvicorn worker count (default: 4)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument("--log-level", default="info", help="Log level (default: info)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required. Install it with: pip install uvicorn[standard]")
        sys.exit(1)

    print(f"Starting Sovereign API at http://{args.host}:{args.port}")
    uvicorn.run(
        "sovereign.api.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers if not args.reload else 1,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
