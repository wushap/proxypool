"""
Security Integration Tests - Validates security checks in API schemas and routes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from proxypool.api.schemas import (
    AutoTaskConfigRequest,
    HttpGatewayTestRequest,
    ImportSourcesRequest,
    ImportUrlsRequest,
    SpeedTestRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
)


class TestSSRFProtectionInSchemas:
    """Test SSRF protection integrated into Pydantic schemas."""

    # ---- ImportUrlsRequest Tests ----

    def test_import_urls_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            ImportUrlsRequest(urls=["http://127.0.0.1/secret"])

    def test_import_urls_rejects_localhost(self):
        with pytest.raises(ValidationError, match="private"):
            ImportUrlsRequest(urls=["http://localhost/admin"])

    def test_import_urls_rejects_metadata_endpoint(self):
        with pytest.raises(ValidationError, match="metadata"):
            ImportUrlsRequest(urls=["http://169.254.169.254/"])

    def test_import_urls_rejects_dangerous_port(self):
        with pytest.raises(ValidationError, match="forbidden"):
            ImportUrlsRequest(urls=["http://example.com:22/"])

    def test_import_urls_allows_public_url(self):
        req = ImportUrlsRequest(urls=["https://example.com/proxies.txt"])
        assert len(req.urls) == 1

    def test_import_urls_multiple_mixed(self):
        with pytest.raises(ValidationError):
            ImportUrlsRequest(
                urls=[
                    "https://example.com/good.txt",
                    "http://127.0.0.1/evil",
                ]
            )

    # ---- ImportSourcesRequest Tests ----

    def test_import_sources_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            ImportSourcesRequest(sources=["http://192.168.1.1/proxies"])

    def test_import_sources_allows_file_path(self):
        req = ImportSourcesRequest(sources=["/path/to/sources.txt"])
        assert len(req.sources) == 1

    def test_import_sources_allows_public_url(self):
        req = ImportSourcesRequest(sources=["https://example.com/sources"])
        assert len(req.sources) == 1

    # ---- SpeedTestRequest Tests ----

    def test_speed_test_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            SpeedTestRequest(url="http://10.0.0.1/test")

    def test_speed_test_rejects_metadata(self):
        with pytest.raises(ValidationError, match="metadata"):
            SpeedTestRequest(url="http://metadata.google.internal/")

    def test_speed_test_allows_public_url(self):
        req = SpeedTestRequest(url="https://speed.cloudflare.com/__down?bytes=100")
        assert req.url == "https://speed.cloudflare.com/__down?bytes=100"

    # ---- HttpGatewayTestRequest Tests ----

    def test_gateway_test_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            HttpGatewayTestRequest(target_url="http://172.16.0.1/secret")

    def test_gateway_test_rejects_aws_metadata(self):
        with pytest.raises(ValidationError, match="metadata"):
            HttpGatewayTestRequest(target_url="http://169.254.169.254/latest/")

    def test_gateway_test_allows_public_url(self):
        req = HttpGatewayTestRequest(target_url="https://example.com")
        assert req.target_url == "https://example.com"

    # ---- SubscriptionCreateRequest Tests ----

    def test_subscription_create_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            SubscriptionCreateRequest(
                name="test",
                url="http://127.0.0.1/subscription",
            )

    def test_subscription_create_rejects_loopback(self):
        with pytest.raises(ValidationError, match="private"):
            SubscriptionCreateRequest(
                name="test",
                url="http://localhost:8080/proxies",
            )

    def test_subscription_create_allows_public_url(self):
        req = SubscriptionCreateRequest(
            name="test",
            url="https://example.com/subscription",
        )
        assert req.url == "https://example.com/subscription"

    # ---- SubscriptionUpdateRequest Tests ----

    def test_subscription_update_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            SubscriptionUpdateRequest(url="http://192.168.0.1/evil")

    def test_subscription_update_allows_none(self):
        req = SubscriptionUpdateRequest(url=None)
        assert req.url is None

    def test_subscription_update_allows_public_url(self):
        req = SubscriptionUpdateRequest(url="https://example.com/new")
        assert req.url == "https://example.com/new"

    # ---- AutoTaskConfigRequest Tests ----

    def test_auto_task_config_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="private"):
            AutoTaskConfigRequest(speed_test_url="http://10.0.0.1/test")

    def test_auto_task_config_rejects_dangerous_port(self):
        with pytest.raises(ValidationError, match="forbidden"):
            AutoTaskConfigRequest(speed_test_url="http://example.com:6379/")

    def test_auto_task_config_allows_public_url(self):
        req = AutoTaskConfigRequest(speed_test_url="https://speed.cloudflare.com/__down?bytes=1000")
        assert "cloudflare" in req.speed_test_url


class TestPathTraversalInSchemas:
    """Test path traversal protection in schemas."""

    def test_import_files_accepts_valid_paths(self):
        from proxypool.api.schemas import ImportFilesRequest

        req = ImportFilesRequest(paths=["/data/proxies.txt", "configs/sources.txt"])
        assert len(req.paths) == 2

    # Note: Path validation happens in the route handler, not in schema
    # This test verifies the schema accepts paths (validation is in app.py)
