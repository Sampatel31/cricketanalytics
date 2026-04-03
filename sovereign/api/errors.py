"""Custom exception classes and HTTP exception handlers for the API."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Custom exception classes
# ---------------------------------------------------------------------------


class APIError(Exception):
    """Base API error with HTTP status code and structured payload."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Return JSON-serialisable representation."""
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


class SessionNotFoundError(APIError):
    """Raised when an auction session cannot be found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            code="SESSION_NOT_FOUND",
            message=f"Auction session '{session_id}' not found.",
            status_code=404,
            details={"session_id": session_id},
        )


class InvalidDNAError(APIError):
    """Raised when a franchise DNA profile is invalid or not found."""

    def __init__(self, dna_id: str) -> None:
        super().__init__(
            code="INVALID_DNA",
            message=f"Franchise DNA '{dna_id}' not found or invalid.",
            status_code=404,
            details={"dna_id": dna_id},
        )


class InvalidPlayerError(APIError):
    """Raised when a player ID cannot be resolved."""

    def __init__(self, player_id: str) -> None:
        super().__init__(
            code="INVALID_PLAYER",
            message=f"Player '{player_id}' not found.",
            status_code=404,
            details={"player_id": player_id},
        )


class BudgetExceededError(APIError):
    """Raised when a pick would exceed the franchise budget."""

    def __init__(self, required: float, remaining: float) -> None:
        super().__init__(
            code="BUDGET_EXCEEDED",
            message=(
                f"Pick price {required:.2f} Cr exceeds remaining budget "
                f"{remaining:.2f} Cr."
            ),
            status_code=422,
            details={"required_crores": required, "remaining_crores": remaining},
        )


class RequestValidationFailedError(APIError):
    """Raised when incoming request data fails validation."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            code="VALIDATION_FAILED",
            message=f"Validation failed for field '{field}': {reason}",
            status_code=422,
            details={"field": field, "reason": reason},
        )


# ---------------------------------------------------------------------------
# Exception handlers (registered in main.py)
# ---------------------------------------------------------------------------


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Convert ``APIError`` subclasses to structured JSON responses."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        },
    )
