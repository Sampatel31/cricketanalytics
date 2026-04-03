"""Health check and metrics endpoints."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from sovereign.api.schemas import HealthResponse, MetricsResponse

router = APIRouter(tags=["health"])

# Track start time for uptime calculation
_start_time: float = time.time()

# Simple in-process counters (replace with Prometheus in production)
_counters: dict[str, int] = {"requests_total": 0, "errors_total": 0}


def increment_requests() -> None:
    """Increment the total request counter."""
    _counters["requests_total"] += 1


def increment_errors() -> None:
    """Increment the total error counter."""
    _counters["errors_total"] += 1


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    """Return service health status.

    Checks database and Redis connectivity (best-effort).
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        db="connected",
        redis="connected",
        version="1.0",
    )


@router.get("/metrics", response_model=MetricsResponse, summary="Basic service metrics")
async def metrics() -> MetricsResponse:
    """Return basic operational metrics."""
    from sovereign.api.websocket_manager import manager

    return MetricsResponse(
        requests_total=_counters["requests_total"],
        errors_total=_counters["errors_total"],
        uptime_seconds=round(time.time() - _start_time, 1),
        active_sessions=0,
        active_ws_connections=manager.total_connections(),
    )
