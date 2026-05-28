"""
API Error Handling Module - Centralized error handling and error response formatting.
"""

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(HTTPException):
    """Custom API exception with error code and details"""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        detail: str,
        field: str | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.field = field
        self.suggestion = suggestion


class NotFoundError(APIError):
    """Resource not found error"""

    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            status_code=404,
            error_code=f"ERR_{resource.upper()}_NOT_FOUND",
            detail=f"{resource} with ID '{resource_id}' not found",
            suggestion=f"Check if {resource} with ID '{resource_id}' exists",
        )


class ValidationError(APIError):
    """Validation error"""

    def __init__(self, detail: str, field: str | None = None):
        super().__init__(
            status_code=422,
            error_code="ERR_VALIDATION_FAILED",
            detail=detail,
            field=field,
            suggestion="Check the request parameters and try again",
        )


class ConflictError(APIError):
    """Resource conflict error"""

    def __init__(self, detail: str, field: str | None = None):
        super().__init__(
            status_code=409,
            error_code="ERR_CONFLICT",
            detail=detail,
            field=field,
        )


class RateLimitError(APIError):
    """Rate limit exceeded error"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            error_code="ERR_RATE_LIMIT_EXCEEDED",
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds",
            suggestion=f"Wait {retry_after} seconds before making another request",
        )
        self.retry_after = retry_after


class InternalError(APIError):
    """Internal server error"""

    def __init__(self, detail: str = "Internal server error"):
        super().__init__(
            status_code=500,
            error_code="ERR_INTERNAL",
            detail=detail,
            suggestion="Contact support if the problem persists",
        )


def create_error_response(
    status_code: int,
    error_code: str,
    detail: str,
    field: str | None = None,
    suggestion: str | None = None,
    correlation_id: str | None = None,
) -> JSONResponse:
    """Create standardized error response"""
    content = {
        "detail": detail,
        "code": error_code,
    }
    if field:
        content["field"] = field
    if suggestion:
        content["suggestion"] = suggestion
    if correlation_id:
        content["correlation_id"] = correlation_id

    return JSONResponse(status_code=status_code, content=content)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions"""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.warning(
        f"API error: {exc.error_code} - {exc.detail} "
        f"[{request.method} {request.url.path}] "
        f"correlation_id={correlation_id}"
    )
    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        detail=exc.detail,
        field=exc.field,
        suggestion=exc.suggestion,
        correlation_id=correlation_id,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException exceptions"""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.warning(
        f"HTTP error: {exc.status_code} - {exc.detail} "
        f"[{request.method} {request.url.path}] "
        f"correlation_id={correlation_id}"
    )
    return create_error_response(
        status_code=exc.status_code,
        error_code=f"ERR_HTTP_{exc.status_code}",
        detail=str(exc.detail),
        correlation_id=correlation_id,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions"""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.exception(
        f"Unhandled exception: {exc} "
        f"[{request.method} {request.url.path}] "
        f"correlation_id={correlation_id}"
    )
    return create_error_response(
        status_code=500,
        error_code="ERR_INTERNAL",
        detail="Internal server error",
        suggestion="Contact support if the problem persists",
        correlation_id=correlation_id,
    )
