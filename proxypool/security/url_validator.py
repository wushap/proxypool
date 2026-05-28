"""
SSRF Protection Module - Validates URL safety to prevent Server-Side Request Forgery.

This module provides:
- Private IP detection (10.x, 172.16.x, 192.168.x, localhost)
- Cloud metadata endpoint blocking (AWS, GCP, Azure)
- Dangerous port detection (SSH, Redis, MongoDB, etc.)
- URL format validation
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private IP address ranges
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),  # Class A private
    ipaddress.ip_network("172.16.0.0/12"),  # Class B private
    ipaddress.ip_network("192.168.0.0/16"),  # Class C private
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local (AWS/GCP metadata)
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
]

# Cloud metadata endpoints
METADATA_ENDPOINTS = {
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "metadata.google.internal",  # GCP metadata
    "169.254.170.2",  # AWS ECS container metadata
}

# Dangerous ports (well-known services that should not be accessed)
DANGEROUS_PORTS = {22, 23, 445, 3389, 5900, 6379, 11211, 27017}


class SSRFProtectionError(Exception):
    """Base exception for SSRF protection errors."""

    pass


class PrivateIPError(SSRFProtectionError):
    """Attempted access to private/internal IP address."""

    pass


class MetadataEndpointError(SSRFProtectionError):
    """Attempted access to cloud metadata endpoint."""

    pass


class DangerousPortError(SSRFProtectionError):
    """Attempted access to dangerous port."""

    pass


class URLValidationError(SSRFProtectionError):
    """URL format validation error."""

    pass


def validate_url(
    url: str,
    allow_private_ips: bool = False,
    allow_metadata: bool = False,
    allowed_schemes: frozenset[str] = frozenset({"http", "https"}),
) -> urlparse:
    """
    Validate URL safety for SSRF protection.

    Args:
        url: URL to validate
        allow_private_ips: Allow private IP addresses (default: False)
        allow_metadata: Allow cloud metadata endpoints (default: False)
        allowed_schemes: Allowed URL schemes (default: http, https)

    Returns:
        Parsed URL object

    Raises:
        URLValidationError: Invalid URL format
        PrivateIPError: Attempted access to private IP
        MetadataEndpointError: Attempted access to metadata endpoint
        DangerousPortError: Attempted access to dangerous port
    """
    # 1. Basic format validation
    if not url or not isinstance(url, str):
        raise URLValidationError("URL is empty or invalid")

    url = url.strip()
    if len(url) > 2048:
        raise URLValidationError("URL exceeds maximum length (2048)")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}")

    # 2. Scheme validation
    if parsed.scheme not in allowed_schemes:
        raise URLValidationError(
            f"Scheme '{parsed.scheme}' not allowed. Must be one of: {allowed_schemes}"
        )

    # 3. Hostname validation
    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL has no hostname")

    # 4. DNS resolution + IP validation
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)

        # Check metadata endpoints (before private IP check)
        if not allow_metadata and hostname in METADATA_ENDPOINTS:
            raise MetadataEndpointError(f"Access to metadata endpoint '{hostname}' is forbidden")

        # Check private IP ranges
        if not allow_private_ips:
            for network in PRIVATE_IP_RANGES:
                if ip_obj in network:
                    raise PrivateIPError(f"IP {ip} ({hostname}) is in private network {network}")
    except (socket.gaierror, socket.herror) as e:
        raise URLValidationError(f"DNS resolution failed for '{hostname}': {e}")
    except (PrivateIPError, MetadataEndpointError):
        raise  # Re-raise known exceptions
    except Exception:
        pass  # DNS resolution failure is not fatal, continue checking

    # 5. Port validation
    port = parsed.port
    if port and port in DANGEROUS_PORTS:
        raise DangerousPortError(f"Port {port} is forbidden (dangerous service)")

    return parsed


def is_safe_url(url: str) -> tuple[bool, str | None]:
    """
    Check if URL is safe (non-throwing version).

    Args:
        url: URL to check

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        validate_url(url)
        return True, None
    except SSRFProtectionError as e:
        return False, str(e)


def sanitize_url_for_logging(url: str) -> str:
    """
    Sanitize URL for logging (hide sensitive information).

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL safe for logging
    """
    try:
        parsed = urlparse(url)
        # Hide password
        if parsed.password:
            return url.replace(f":{parsed.password}@", ":***@")
        return url
    except Exception:
        return "[invalid url]"
