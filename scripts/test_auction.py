"""Simulate a full auction session with WebSocket client.

Usage::

    python scripts/test_auction.py \
        --franchise "Mumbai Indians" \
        --budget 100 \
        --format T20I \
        --lots 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a live cricket auction")
    parser.add_argument("--franchise", default="Mumbai Indians", help="Franchise name")
    parser.add_argument("--budget", type=float, default=100.0, help="Budget in crores")
    parser.add_argument("--format", default="T20I", dest="format_type", help="Cricket format")
    parser.add_argument("--lots", type=int, default=5, help="Number of auction lots to simulate")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    return parser.parse_args()


async def simulate_auction(args: argparse.Namespace) -> None:
    """Run a full auction simulation."""
    try:
        import httpx
        import websockets
    except ImportError:
        print("httpx and websockets are required. Install: pip install httpx websockets")
        sys.exit(1)

    base_url = f"http://{args.host}:{args.port}"
    ws_base = f"ws://{args.host}:{args.port}"

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Build DNA
        print(f"Building DNA for {args.franchise}...")
        dna_resp = await client.post(
            "/api/v1/dna/slider",
            json={
                "franchise_name": args.franchise,
                "feature_weights": {"sr_spi_low": 80.0, "sr_spi_medium": 60.0},
                "target_archetypes": [],
            },
        )
        dna_resp.raise_for_status()
        dna_id = dna_resp.json()["dna_id"]
        print(f"  DNA ID: {dna_id}")

        # Create session
        print(f"Creating auction session ({args.budget} Cr)...")
        sess_resp = await client.post(
            "/api/v1/auction/session",
            json={
                "franchise_name": args.franchise,
                "budget_crores": args.budget,
                "dna_id": dna_id,
                "format_type": args.format_type,
            },
        )
        sess_resp.raise_for_status()
        session_id = sess_resp.json()["session_id"]
        print(f"  Session ID: {session_id}")

    # Connect WebSocket and simulate lots
    print(f"Connecting WebSocket for {args.lots} lots...")
    uri = f"{ws_base}/ws/{session_id}"
    try:
        async with websockets.connect(uri) as ws:
            connected_msg = json.loads(await ws.recv())
            print(f"  Connected: {connected_msg}")

            player_ids = [f"p{i:03d}" for i in range(1, args.lots + 1)]
            for pid in player_ids:
                await ws.send(json.dumps({"type": "lot_called", "player_id": pid}))
                msg = json.loads(await ws.recv())
                print(f"  Lot {pid}: {msg.get('type')} - {msg.get('recommendation', '')}")

    except Exception as exc:
        print(f"WebSocket simulation skipped (server not running): {exc}")

    print("Auction simulation complete.")


def main() -> None:
    args = parse_args()
    asyncio.run(simulate_auction(args))


if __name__ == "__main__":
    main()
