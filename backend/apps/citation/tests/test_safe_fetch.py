"""Tests for the SSRF-safe fetch utility."""

from __future__ import annotations

import socket
from ipaddress import IPv4Address
from unittest.mock import MagicMock, patch

import pytest

from apps.citation.safe_fetch import (
    FetchResponse,
    SSRFBlockedError,
    _is_blocked,
    _resolve_and_validate,
    safe_fetch,
)

# ---------------------------------------------------------------------------
# IP validation (TDD — these define the security boundary)
# ---------------------------------------------------------------------------


class TestIsBlocked:
    """Exhaustive checks — blocked means ``not is_global``."""

    def test_loopback_ipv4(self):
        assert _is_blocked("127.0.0.1") is True

    def test_loopback_ipv6(self):
        assert _is_blocked("::1") is True

    def test_private_10(self):
        assert _is_blocked("10.0.0.1") is True

    def test_private_172(self):
        assert _is_blocked("172.16.0.1") is True

    def test_private_192(self):
        assert _is_blocked("192.168.1.1") is True

    def test_link_local_ipv4(self):
        assert _is_blocked("169.254.1.1") is True

    def test_link_local_ipv6(self):
        assert _is_blocked("fe80::1") is True

    def test_multicast_ipv4(self):
        assert _is_blocked("224.0.0.1") is True

    def test_multicast_ipv6(self):
        assert _is_blocked("ff02::1") is True

    def test_reserved_ipv4(self):
        # The unspecified address (all zeros) is reserved.
        assert _is_blocked(str(IPv4Address(0))) is True

    def test_ipv4_mapped_ipv6_loopback(self):
        assert _is_blocked("::ffff:127.0.0.1") is True

    def test_ipv4_mapped_ipv6_private(self):
        assert _is_blocked("::ffff:10.0.0.1") is True

    def test_cgnat_range(self):
        # 100.64.0.0/10 — Shared Address Space (RFC 6598)
        assert _is_blocked("100.64.0.1") is True

    def test_documentation_range(self):
        # 192.0.2.0/24 — TEST-NET-1 (RFC 5737)
        assert _is_blocked("192.0.2.1") is True

    def test_public_ipv4_allowed(self):
        assert _is_blocked("8.8.8.8") is False

    def test_public_ipv6_allowed(self):
        assert _is_blocked("2607:f8b0:4004:800::200e") is False


class TestResolveAndValidate:
    """DNS resolution + IP validation."""

    @patch("apps.citation.safe_fetch.socket.getaddrinfo")
    def test_blocks_when_all_ips_private(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80)),
        ]
        with pytest.raises(SSRFBlockedError) as exc_info:
            _resolve_and_validate("evil.example.com", 80)
        assert "127.0.0.1" in str(exc_info.value)

    @patch("apps.citation.safe_fetch.socket.getaddrinfo")
    def test_returns_first_public_ip(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        ]
        assert _resolve_and_validate("example.com", 80) == "93.184.216.34"

    @patch("apps.citation.safe_fetch.socket.getaddrinfo")
    def test_dns_failure_raises_oserror(self, mock_dns):
        mock_dns.side_effect = OSError("Name resolution failed")
        with pytest.raises(OSError, match="Name resolution"):
            _resolve_and_validate("nonexistent.invalid", 80)

    @patch("apps.citation.safe_fetch.socket.getaddrinfo")
    def test_empty_dns_result_raises(self, mock_dns):
        mock_dns.return_value = []
        with pytest.raises(OSError, match="no results"):
            _resolve_and_validate("empty.example.com", 80)


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------


class TestSchemeValidation:
    @patch("apps.citation.safe_fetch._resolve_and_validate")
    def test_rejects_ftp_scheme(self, mock_resolve):
        with pytest.raises(SSRFBlockedError, match="invalid-scheme"):
            safe_fetch("ftp://example.com/file", timeout=5)
        mock_resolve.assert_not_called()

    @patch("apps.citation.safe_fetch._resolve_and_validate")
    def test_rejects_file_scheme(self, mock_resolve):
        with pytest.raises(SSRFBlockedError, match="invalid-scheme"):
            safe_fetch("file:///etc/passwd", timeout=5)
        mock_resolve.assert_not_called()

    @patch("apps.citation.safe_fetch._resolve_and_validate")
    def test_rejects_javascript_scheme(self, mock_resolve):
        with pytest.raises(SSRFBlockedError, match="invalid-scheme"):
            safe_fetch("javascript:alert(1)", timeout=5)
        mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Connection behavior (mock http.client)
# ---------------------------------------------------------------------------


def _mock_response(status=200, headers=None, body=b"<html></html>", location=None):
    """Build a mock http.client.HTTPResponse."""
    resp = MagicMock()
    resp.status = status
    all_headers = list((headers or {}).items())
    if location:
        all_headers.append(("Location", location))
    resp.getheaders.return_value = all_headers
    resp.read.return_value = body
    return resp


class TestSafeFetchConnection:
    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_connects_to_resolved_ip_not_hostname(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("http://example.com/page", timeout=5)

        # Connection should be to the resolved IP, not the hostname
        mock_conn_cls.assert_called_once()
        args = mock_conn_cls.call_args
        assert args[0][0] == "93.184.216.34"
        assert args[0][1] == 80

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_sets_host_header_to_original_hostname(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("http://example.com/page", timeout=5)

        request_call = mock_conn.request.call_args
        headers = (
            request_call[1].get("headers") or request_call[0][2]
            if len(request_call[0]) > 2
            else request_call[1]["headers"]
        )
        assert headers["Host"] == "example.com"

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_sends_accept_encoding_identity(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("http://example.com/page", timeout=5)

        request_call = mock_conn.request.call_args
        headers = (
            request_call[1].get("headers") or request_call[0][2]
            if len(request_call[0]) > 2
            else request_call[1]["headers"]
        )
        assert headers["Accept-Encoding"] == "identity"

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_returns_fetch_response(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response(
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=b"<html><title>Hello</title></html>",
        )

        result = safe_fetch("http://example.com/", timeout=5)

        assert isinstance(result, FetchResponse)
        assert result.status == 200
        assert result.headers["content-type"] == "text/html; charset=utf-8"
        assert b"<title>Hello</title>" in result.body

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_preserves_path_and_query(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("http://example.com/path/to/page?foo=bar", timeout=5)

        request_call = mock_conn.request.call_args
        assert request_call[0][0] == "GET"
        assert request_call[0][1] == "/path/to/page?foo=bar"

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_non_2xx_returned_not_raised(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response(
            status=404, body=b"Not Found"
        )

        result = safe_fetch("http://example.com/missing", timeout=5)
        assert result.status == 404

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_custom_port(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("http://example.com:8080/page", timeout=5)

        args = mock_conn_cls.call_args
        assert args[0][1] == 8080
        mock_resolve.assert_called_with("example.com", 8080)


# ---------------------------------------------------------------------------
# HTTPS / TLS
# ---------------------------------------------------------------------------


class TestSafeFetchTLS:
    @patch("apps.citation.safe_fetch.ssl.create_default_context")
    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_https_wraps_socket_with_server_hostname(
        self, mock_conn_cls, mock_resolve, mock_ssl_ctx
    ):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_wrapped = MagicMock()
        mock_ssl_ctx.return_value.wrap_socket.return_value = mock_wrapped
        mock_conn.getresponse.return_value = _mock_response()

        safe_fetch("https://example.com/page", timeout=5)

        # Should wrap the socket with server_hostname for SNI
        wrap_call = mock_ssl_ctx.return_value.wrap_socket.call_args
        assert wrap_call[1]["server_hostname"] == "example.com"


# ---------------------------------------------------------------------------
# Redirects
# ---------------------------------------------------------------------------


class TestSafeFetchRedirects:
    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_follows_redirect(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn

        # First response: 301 redirect
        # Second response: 200
        mock_conn.getresponse.side_effect = [
            _mock_response(status=301, location="http://example.com/new-page"),
            _mock_response(status=200, body=b"final"),
        ]

        result = safe_fetch("http://example.com/old-page", timeout=5)
        assert result.status == 200
        assert result.body == b"final"

    @patch("apps.citation.safe_fetch._resolve_and_validate")
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_redirect_revalidates_ip(self, mock_conn_cls, mock_resolve):
        """Redirect to a private IP must be blocked."""
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.getresponse.return_value = _mock_response(
            status=301, location="http://internal.example.com/secret"
        )

        # First resolve: public, second resolve: private → blocked
        mock_resolve.side_effect = [
            "93.184.216.34",
            SSRFBlockedError("http://internal.example.com/secret", "10.0.0.1"),
        ]

        with pytest.raises(SSRFBlockedError):
            safe_fetch("http://example.com/redirect", timeout=5)

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_relative_redirect(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn

        mock_conn.getresponse.side_effect = [
            _mock_response(status=302, location="/new-path"),
            _mock_response(status=200, body=b"done"),
        ]

        result = safe_fetch("http://example.com/old", timeout=5)
        assert result.status == 200

    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    def test_max_redirects_returns_last_response(self, mock_conn_cls, mock_resolve):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn

        # 6 redirects (exceeds _MAX_REDIRECTS=5)
        mock_conn.getresponse.return_value = _mock_response(
            status=301, location="http://example.com/loop"
        )

        result = safe_fetch("http://example.com/start", timeout=10)
        # After exhausting redirects, returns the last redirect response
        assert result.status == 301


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TestSafeFetchTimeout:
    @patch("apps.citation.safe_fetch.time.monotonic")
    @patch(
        "apps.citation.safe_fetch._resolve_and_validate", return_value="93.184.216.34"
    )
    def test_wall_clock_deadline_exceeded(self, mock_resolve, mock_time):
        # Simulate: start=0, after resolve=6 (past 5s deadline)
        mock_time.side_effect = [0.0, 6.0]

        with pytest.raises(socket.timeout, match="wall-clock deadline"):
            safe_fetch("http://example.com/slow", timeout=5)


# ---------------------------------------------------------------------------
# Empty / missing hostname
# ---------------------------------------------------------------------------


class TestEmptyHostname:
    def test_rejects_missing_hostname(self):
        with pytest.raises(SSRFBlockedError, match="empty-hostname"):
            safe_fetch("http:///etc/passwd", timeout=5)

    def test_rejects_empty_authority(self):
        with pytest.raises(SSRFBlockedError, match="empty-hostname"):
            safe_fetch("http://", timeout=5)


# ---------------------------------------------------------------------------
# Cross-scheme redirect
# ---------------------------------------------------------------------------


class TestCrossSchemeRedirect:
    @patch("apps.citation.safe_fetch._resolve_and_validate")
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    @patch("apps.citation.safe_fetch.ssl.create_default_context")
    def test_https_to_http_redirect_revalidates(
        self, mock_ssl_ctx, mock_conn_cls, mock_resolve
    ):
        """Redirect from HTTPS to HTTP still validates the new target's IP."""
        mock_resolve.return_value = "93.184.216.34"
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_ssl_ctx.return_value.wrap_socket.return_value = MagicMock()

        mock_conn.getresponse.side_effect = [
            _mock_response(status=301, location="http://example.com/plain"),
            _mock_response(status=200, body=b"done"),
        ]

        result = safe_fetch("https://example.com/secure", timeout=5)
        assert result.status == 200

        # resolve_and_validate called twice — once per hop
        assert mock_resolve.call_count == 2

    @patch("apps.citation.safe_fetch._resolve_and_validate")
    @patch("apps.citation.safe_fetch.http.client.HTTPConnection")
    @patch("apps.citation.safe_fetch.ssl.create_default_context")
    def test_https_redirect_to_private_http_blocked(
        self, mock_ssl_ctx, mock_conn_cls, mock_resolve
    ):
        """HTTPS → HTTP redirect to a private IP is blocked."""
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_ssl_ctx.return_value.wrap_socket.return_value = MagicMock()

        mock_conn.getresponse.return_value = _mock_response(
            status=301, location="http://169.254.169.254/metadata"
        )

        mock_resolve.side_effect = [
            "93.184.216.34",
            SSRFBlockedError("http://169.254.169.254/metadata", "169.254.169.254"),
        ]

        with pytest.raises(SSRFBlockedError):
            safe_fetch("https://example.com/evil-redirect", timeout=5)


# ---------------------------------------------------------------------------
# Integration — real DNS, no mocks
# ---------------------------------------------------------------------------


class TestSSRFIntegration:
    """Exercises _resolve_and_validate with real DNS resolution.

    These tests verify the full chain: real hostname → real getaddrinfo →
    real IP → _is_blocked.  The unit tests above mock getaddrinfo, so they
    only prove the logic is correct *if the mocked inputs are realistic*.
    These tests prove the assumption holds on the actual platform.
    """

    def test_localhost_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _resolve_and_validate("localhost", 80)

    def test_127_0_0_1_blocked(self):
        """Numeric localhost — getaddrinfo returns it directly."""
        with pytest.raises(SSRFBlockedError):
            _resolve_and_validate("127.0.0.1", 80)
