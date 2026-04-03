"""FastAPI application setup with lifespan, middleware, and routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sovereign.api.errors import APIError, api_error_handler, generic_error_handler
from sovereign.api.middleware import RequestLoggingMiddleware
from sovereign.api.routes import auction, dna, health, players, squad, ws
from sovereign.config.settings import settings

logger = structlog.get_logger(__name__)

_API_VERSION = "1.0"
_API_TITLE = "Sovereign Archetyping - Cricket Auction Intelligence"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    logger.info(
        "api_startup",
        version=_API_VERSION,
        host=settings.api_host,
        port=settings.api_port,
    )
    yield
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=_API_TITLE,
        version=_API_VERSION,
        description=(
            "Production-grade FastAPI backend for Sovereign Cricket Auction Intelligence. "
            "Exposes player data, franchise DNA building, real-time auction management, "
            "and WebSocket live auction support."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------ #
    # CORS                                                                 #
    # ------------------------------------------------------------------ #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # ------------------------------------------------------------------ #
    # Custom middleware                                                    #
    # ------------------------------------------------------------------ #
    app.add_middleware(RequestLoggingMiddleware)

    # ------------------------------------------------------------------ #
    # Exception handlers                                                   #
    # ------------------------------------------------------------------ #
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # ------------------------------------------------------------------ #
    # Routes                                                               #
    # ------------------------------------------------------------------ #
    app.include_router(health.router)
    app.include_router(players.router)
    app.include_router(dna.router)
    app.include_router(auction.router)
    app.include_router(squad.router)
    app.include_router(ws.router)

    # Version header on every response
    @app.middleware("http")
    async def add_version_header(request, call_next):
        response = await call_next(request)
        response.headers["API-Version"] = _API_VERSION
        return response

    return app


app = create_app()
