"""Tests for proxypool.__init__ module.

Verifies version string and package-level imports.
"""

from __future__ import annotations

import importlib
import sys


class TestVersion:
    """Test the __version__ export."""

    def test_version_is_string(self):
        from proxypool import __version__

        assert isinstance(__version__, str)

    def test_version_is_nonempty(self):
        from proxypool import __version__

        assert len(__version__) > 0

    def test_version_defined_at_package_level(self):
        import proxypool

        assert hasattr(proxypool, "__version__")
        assert isinstance(proxypool.__version__, str)


class TestPackageImport:
    """Test that the package can be imported cleanly."""

    def test_package_is_importable(self):
        assert "proxypool" in sys.modules or importlib.import_module("proxypool") is not None

    def test_package_has_docstring(self):
        import proxypool

        assert proxypool.__doc__ is not None
        assert "ProxyPool" in proxypool.__doc__


class TestFallbackVersion:
    """Test the fallback version path when PackageNotFoundError is raised."""

    def test_fallback_version_value(self):
        """When the package metadata is unavailable, __version__ defaults to '0.2.0'."""
        import importlib.metadata

        original_version = importlib.metadata.version

        def _raise_not_found(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        try:
            importlib.metadata.version = _raise_not_found  # type: ignore[assignment]
            # Force re-execution of the module-level code
            mod = importlib.import_module("proxypool")
            importlib.reload(mod)
            assert mod.__version__ == "0.2.0"
        finally:
            importlib.metadata.version = original_version
            importlib.reload(mod)
