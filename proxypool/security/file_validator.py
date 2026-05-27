"""
Path Traversal Protection Module - Validates file path safety.

This module provides:
- Path normalization and validation
- Directory whitelist enforcement
- Symlink detection
- Safe file reading with size limits
"""
from __future__ import annotations

from pathlib import Path


class PathTraversalError(Exception):
    """Path traversal attack detected."""
    pass


class PathValidationError(Exception):
    """Path validation error."""
    pass


def validate_file_path(
    path: str | Path,
    allowed_directories: list[Path] | None = None,
    allow_symlinks: bool = False,
) -> Path:
    """
    Validate file path safety to prevent path traversal attacks.

    Args:
        path: Path to validate
        allowed_directories: Whitelist of allowed directories (default: project dirs)
        allow_symlinks: Allow symbolic links (default: False)

    Returns:
        Resolved absolute path

    Raises:
        PathTraversalError: Path traversal attack detected
        PathValidationError: Path validation failed
    """
    if allowed_directories is None:
        # Default to project directories only
        project_root = Path(__file__).resolve().parents[2]
        allowed_directories = [
            project_root / "data",
            project_root / "output",
            project_root / "configs",
        ]

    path = Path(path)

    # 1. Convert to absolute path (handle relative paths)
    try:
        abs_path = path.resolve()
    except (OSError, ValueError) as e:
        raise PathValidationError(f"Cannot resolve path: {e}")

    # 2. Detect path traversal characters
    path_str = str(path)
    traversal_patterns = ["..", "~", "$", "`"]
    for pattern in traversal_patterns:
        if pattern in path_str:
            raise PathTraversalError(
                f"Path contains traversal character '{pattern}': {path_str}"
            )

    # 3. Validate path is within allowed directories (skip if empty list = no restriction)
    if allowed_directories:
        is_allowed = False
        for allowed_dir in allowed_directories:
            try:
                allowed_resolved = allowed_dir.resolve()
                if abs_path.is_relative_to(allowed_resolved):
                    is_allowed = True
                    break
            except (OSError, ValueError):
                continue

        if not is_allowed:
            raise PathTraversalError(
                f"Path '{abs_path}' is not within allowed directories: "
                f"{[str(d) for d in allowed_directories]}"
            )

    # 4. Check for symbolic links
    if not allow_symlinks and abs_path.exists():
        if abs_path.is_symlink():
            raise PathTraversalError(f"Path '{abs_path}' is a symlink (forbidden)")

    return abs_path


def safe_read_file(
    path: str | Path,
    allowed_directories: list[Path] | None = None,
    max_size_bytes: int = 10 * 1024 * 1024,  # 10MB default
) -> str:
    """
    Safely read file content with path validation.

    Args:
        path: File path to read
        allowed_directories: Whitelist of allowed directories
        max_size_bytes: Maximum file size in bytes (default: 10MB)

    Returns:
        File content as string

    Raises:
        PathTraversalError: Path traversal attack detected
        PathValidationError: Path validation failed
        FileNotFoundError: File not found
        ValueError: File too large or not a file
    """
    abs_path = validate_file_path(path, allowed_directories)

    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {abs_path}")

    if not abs_path.is_file():
        raise ValueError(f"Path is not a file: {abs_path}")

    # Check file size
    file_size = abs_path.stat().st_size
    if file_size > max_size_bytes:
        raise ValueError(
            f"File too large: {file_size} bytes (max: {max_size_bytes})"
        )

    return abs_path.read_text(encoding="utf-8", errors="ignore")


def safe_list_directory(
    path: str | Path,
    allowed_directories: list[Path] | None = None,
    pattern: str = "*",
) -> list[Path]:
    """
    Safely list directory contents with path validation.

    Args:
        path: Directory path to list
        allowed_directories: Whitelist of allowed directories
        pattern: File matching pattern (default: *)

    Returns:
        List of matching file paths

    Raises:
        PathTraversalError: Path traversal attack detected
        PathValidationError: Path validation failed
        ValueError: Path is not a directory
    """
    dir_path = validate_file_path(path, allowed_directories)

    if not dir_path.exists():
        return []

    if not dir_path.is_dir():
        raise ValueError(f"Path is not a directory: {dir_path}")

    return sorted(dir_path.glob(pattern))
