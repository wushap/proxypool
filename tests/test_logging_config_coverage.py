"""
Tests for proxypool.logging_config module.

Covers JSONFormatter, HumanReadableFormatter, setup_logging, and get_logger.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from proxypool.logging_config import (
    JSONFormatter,
    HumanReadableFormatter,
    get_logger,
    setup_logging,
)


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """Tests for JSONFormatter.format."""

    def setup_method(self) -> None:
        self.formatter = JSONFormatter()

    def _make_record(
        self,
        level: int = logging.INFO,
        msg: str = "hello",
        name: str = "test.logger",
        exc_info: object = None,
        extra_data: dict | None = None,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )
        if extra_data is not None:
            record.extra_data = extra_data  # type: ignore[attr-defined]
        return record

    def test_basic_format_returns_valid_json(self) -> None:
        record = self._make_record(level=logging.INFO, msg="test message", name="mylogger")
        output = self.formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "mylogger"
        assert data["message"] == "test message"
        assert "timestamp" in data

    def test_extra_data_merged_into_output(self) -> None:
        record = self._make_record(extra_data={"request_id": "abc123", "user_id": 42})
        data = json.loads(self.formatter.format(record))
        assert data["request_id"] == "abc123"
        assert data["user_id"] == 42

    def test_extra_data_ignored_when_not_dict(self) -> None:
        record = self._make_record()
        record.extra_data = "not a dict"  # type: ignore[attr-defined]
        data = json.loads(self.formatter.format(record))
        assert "extra_data" not in data

    def test_no_extra_data_attribute(self) -> None:
        record = self._make_record()
        # Ensure attribute doesn't exist
        if hasattr(record, "extra_data"):
            delattr(record, "extra_data")
        data = json.loads(self.formatter.format(record))
        assert "timestamp" in data

    def test_exception_info_included(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys as _sys

            exc_info = _sys.exc_info()

        record = self._make_record(exc_info=exc_info)
        data = json.loads(self.formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "boom" in data["exception"]

    def test_exc_info_none_does_not_add_exception_key(self) -> None:
        record = self._make_record(exc_info=None)
        data = json.loads(self.formatter.format(record))
        assert "exception" not in data

    def test_debug_level_adds_file_and_line(self) -> None:
        record = self._make_record(level=logging.DEBUG)
        record.filename = "test.py"
        record.lineno = 42
        data = json.loads(self.formatter.format(record))
        assert data["file"] == "test.py"
        assert data["line"] == 42

    def test_non_debug_level_omits_file_and_line(self) -> None:
        record = self._make_record(level=logging.WARNING)
        record.filename = "test.py"
        record.lineno = 42
        data = json.loads(self.formatter.format(record))
        assert "file" not in data
        assert "line" not in data

    def test_exc_info_first_element_none_not_added(self) -> None:
        """exc_info=(None, None, None) should not add exception key."""
        record = self._make_record(exc_info=(None, None, None))
        data = json.loads(self.formatter.format(record))
        assert "exception" not in data

    def test_message_with_args(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="count=%d",
            args=(5,),
            exc_info=None,
        )
        data = json.loads(self.formatter.format(record))
        assert data["message"] == "count=5"


# ---------------------------------------------------------------------------
# HumanReadableFormatter
# ---------------------------------------------------------------------------


class TestHumanReadableFormatter:
    """Tests for HumanReadableFormatter.format."""

    def _make_record(
        self,
        level: int = logging.INFO,
        msg: str = "hello",
        name: str = "test.logger",
        exc_info: object = None,
    ) -> logging.LogRecord:
        return logging.LogRecord(
            name=name,
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )

    def test_basic_format_with_colors(self) -> None:
        formatter = HumanReadableFormatter(use_colors=True)
        record = self._make_record(level=logging.INFO, name="myapp.sub")
        output = formatter.format(record)
        assert "INFO" in output
        assert "[sub]" in output  # short name (last component)
        assert "hello" in output
        # Should contain ANSI color codes
        assert "\033[32m" in output  # Green for INFO

    def test_basic_format_without_colors(self) -> None:
        formatter = HumanReadableFormatter(use_colors=False)
        record = self._make_record(level=logging.WARNING, name="myapp.module")
        output = formatter.format(record)
        assert "WARNING" in output
        assert "[module]" in output
        assert "\033[" not in output  # No ANSI codes

    def test_exception_info_appended(self) -> None:
        formatter = HumanReadableFormatter(use_colors=False)
        try:
            raise RuntimeError("test error")
        except RuntimeError:
            import sys as _sys

            exc_info = _sys.exc_info()

        record = self._make_record(exc_info=exc_info)
        output = formatter.format(record)
        assert "RuntimeError" in output
        assert "test error" in output

    def test_exc_info_none_no_exception(self) -> None:
        formatter = HumanReadableFormatter(use_colors=False)
        record = self._make_record(exc_info=None)
        output = formatter.format(record)
        assert "hello" in output
        # Should just be the single line
        assert "\n" not in output

    def test_exc_info_first_element_none(self) -> None:
        formatter = HumanReadableFormatter(use_colors=False)
        record = self._make_record(exc_info=(None, None, None))
        output = formatter.format(record)
        assert "\n" not in output

    def test_all_log_level_colors(self) -> None:
        formatter = HumanReadableFormatter(use_colors=True)
        for level, expected_color in HumanReadableFormatter.COLORS.items():
            record = self._make_record(level=level)
            output = formatter.format(record)
            assert expected_color in output

    def test_default_use_colors_true(self) -> None:
        formatter = HumanReadableFormatter()
        assert formatter.use_colors is True

    def test_unknown_level_no_color(self) -> None:
        formatter = HumanReadableFormatter(use_colors=True)
        record = self._make_record(level=999)  # Unknown level
        output = formatter.format(record)
        # Unknown level: COLORS.get(999, "") returns "", so only the RESET code
        # is present (no foreground color). The level string is still formatted.
        assert "Level 999" in output
        assert "\033[0m" in output  # RESET is always added when use_colors=True
        assert "\033[3" not in output  # No foreground color code for unknown level
        assert "hello" in output


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self) -> None:
        # Reset root logger after each test
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_default_setup(self) -> None:
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) >= 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_json_output_uses_json_formatter(self) -> None:
        setup_logging(json_output=True)
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_human_readable_output(self) -> None:
        setup_logging(json_output=False)
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, HumanReadableFormatter)

    def test_custom_log_level(self) -> None:
        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert root.handlers[0].level == logging.DEBUG

    def test_clears_existing_handlers(self) -> None:
        root = logging.getLogger()
        # Add a dummy handler first
        dummy = logging.StreamHandler(io.StringIO())
        root.addHandler(dummy)
        assert len(root.handlers) >= 1

        setup_logging()
        # The dummy handler should be gone (unless it was re-added)
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1

    def test_log_file_creates_rotating_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            setup_logging(log_file=log_path)
            root = logging.getLogger()
            # Should have 2 handlers: console + file
            assert len(root.handlers) == 2
            # Second handler should be a RotatingFileHandler
            from logging.handlers import RotatingFileHandler

            assert isinstance(root.handlers[1], RotatingFileHandler)

    def test_log_file_handler_uses_json_formatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            setup_logging(log_file=log_path)
            file_handler = logging.getLogger().handlers[1]
            assert isinstance(file_handler.formatter, JSONFormatter)

    def test_log_file_custom_rotation_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            setup_logging(
                log_file=log_path,
                log_max_bytes=1024,
                log_backup_count=3,
            )
            from logging.handlers import RotatingFileHandler

            file_handler = logging.getLogger().handlers[1]
            assert isinstance(file_handler, RotatingFileHandler)
            assert file_handler.maxBytes == 1024
            assert file_handler.backupCount == 3

    def test_console_handler_writes_to_stdout(self) -> None:
        setup_logging()
        root = logging.getLogger()
        console = root.handlers[0]
        assert isinstance(console, logging.StreamHandler)
        assert console.stream is sys.stdout

    def test_verify_log_output_json(self) -> None:
        setup_logging(json_output=True)
        logger = logging.getLogger("test.verify")
        stream = io.StringIO()
        # Replace the console handler's stream
        root = logging.getLogger()
        root.handlers[0].stream = stream  # type: ignore[assignment]

        logger.info("verify message")
        output = stream.getvalue()
        data = json.loads(output.strip())
        assert data["message"] == "verify message"
        assert data["level"] == "INFO"

    def test_verify_log_output_human(self) -> None:
        setup_logging(json_output=False)
        logger = logging.getLogger("test.verify")
        stream = io.StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream  # type: ignore[assignment]

        logger.info("verify message")
        output = stream.getvalue()
        assert "verify message" in output


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_with_correct_name(self) -> None:
        logger = get_logger("my.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "my.module"

    def test_returns_same_logger_for_same_name(self) -> None:
        logger1 = get_logger("same.name")
        logger2 = get_logger("same.name")
        assert logger1 is logger2

    def test_different_names_return_different_loggers(self) -> None:
        logger_a = get_logger("name.a")
        logger_b = get_logger("name.b")
        assert logger_a is not logger_b
