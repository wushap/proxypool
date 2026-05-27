"""
Security Helper Functions for API Routes.

This module provides helper functions for integrating security checks
into FastAPI route handlers.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from proxypool.security.file_validator import PathTraversalError, validate_file_path
from proxypool.security.url_validator import (
    SSRFProtectionError,
    is_safe_url,
)


def validate_url_or_raise(url: str, field_name: str = "url") -> None:
    """
    Validate URL and raise HTTPException if unsafe.

    Args:
        url: URL to validate
        field_name: Name of the field for error message

    Raises:
        HTTPException: 400 Bad Request if URL is unsafe
    """
    if not url:
        return

    is_safe, error = is_safe_url(url)
    if not is_safe:
        raise HTTPException(
            status_code=400,
            detail=f"URL validation failed for {field_name}: {error}",
        )


def validate_file_path_or_raise(
    path: str | Path,
    allowed_directories: list[Path] | None = None,
) -> Path:
    """
    Validate file path and raise HTTPException if unsafe.

    Args:
        path: Path to validate
        allowed_directories: Whitelist of allowed directories

    Returns:
        Validated absolute path

    Raises:
        HTTPException: 400 Bad Request if path is unsafe
    """
    try:
        return validate_file_path(path, allowed_directories)
    except PathTraversalError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Path validation failed: {e}",
        )


def validate_urls_list_or_raise(urls: list[str], field_name: str = "urls") -> None:
    """
    Validate list of URLs and raise HTTPException if any are unsafe.

    Args:
        urls: List of URLs to validate
        field_name: Name of the field for error message

    Raises:
        HTTPException: 400 Bad Request if any URL is unsafe
    """
    for i, url in enumerate(urls):
        is_safe, error = is_safe_url(url)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"URL validation failed for {field_name}[{i}]: {error}",
            )


def validate_sources_list_or_raise(sources: list[str]) -> None:
    """
    Validate list of sources (URLs or file paths) and raise HTTPException if unsafe.

    Args:
        sources: List of sources to validate

    Raises:
        HTTPException: 400 Bad Request if any source is unsafe
    """
    for i, source in enumerate(sources):
        # Sources can be URLs or file paths
        if source.startswith(("http://", "https://")):
            is_safe, error = is_safe_url(source)
            if not is_safe:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source URL validation failed for sources[{i}]: {error}",
                )
        # File paths are validated at the route level with allowed directories
