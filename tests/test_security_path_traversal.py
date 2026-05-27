"""
Path Traversal Security Tests - Validates path traversal protection.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from proxypool.security.file_validator import (
    PathTraversalError,
    PathValidationError,
    safe_list_directory,
    safe_read_file,
    validate_file_path,
)


class TestPathTraversalProtection:
    """Path traversal protection test suite."""

    def test_block_double_dots(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            validate_file_path("../../../etc/passwd", [tmp_path])

    def test_block_tilde_expansion(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            validate_file_path("~/secret.txt", [tmp_path])

    def test_block_dollar_expansion(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            validate_file_path("$HOME/.ssh/id_rsa", [tmp_path])

    def test_block_backtick_injection(self, tmp_path: Path):
        with pytest.raises(PathTraversalError):
            validate_file_path("`whoami`.txt", [tmp_path])

    def test_allow_valid_relative_path(self, tmp_path: Path):
        allowed = [tmp_path / "data"]
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "test.txt").write_text("content")

        result = validate_file_path(tmp_path / "data" / "test.txt", allowed)
        assert result.exists()

    def test_block_symlink(self, tmp_path: Path):
        allowed = [tmp_path / "allowed"]
        (tmp_path / "allowed").mkdir(exist_ok=True)
        (tmp_path / "secret").write_text("secret")
        (tmp_path / "allowed" / "link").symlink_to(tmp_path / "secret")

        with pytest.raises(PathTraversalError, match="symlink"):
            validate_file_path(
                tmp_path / "allowed" / "link", allowed, allow_symlinks=False
            )

    def test_safe_read_file_within_allowed(self, tmp_path: Path):
        allowed = [tmp_path / "data"]
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "config.txt").write_text("config content")

        content = safe_read_file(tmp_path / "data" / "config.txt", allowed)
        assert content == "config content"

    def test_safe_read_file_blocks_traversal(self, tmp_path: Path):
        allowed = [tmp_path / "data"]
        with pytest.raises(PathTraversalError):
            safe_read_file("../../../etc/passwd", allowed)

    def test_safe_read_file_blocks_large_file(self, tmp_path: Path):
        allowed = [tmp_path / "data"]
        (tmp_path / "data").mkdir(exist_ok=True)
        large_file = tmp_path / "data" / "large.txt"
        large_file.write_text("x" * 20 * 1024 * 1024)  # 20MB

        with pytest.raises(ValueError, match="too large"):
            safe_read_file(large_file, allowed, max_size_bytes=10 * 1024 * 1024)

    def test_safe_list_directory(self, tmp_path: Path):
        allowed = [tmp_path / "data"]
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "a.txt").write_text("")
        (tmp_path / "data" / "b.txt").write_text("")

        files = safe_list_directory(tmp_path / "data", allowed)
        assert len(files) == 2
