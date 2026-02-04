"""Tests for ProxyFix middleware configuration."""

from __future__ import annotations

import unittest

from flask import request

from pickaladder import create_app


class TestProxyFix(unittest.TestCase):
    """Test case for ProxyFix middleware."""

    def setUp(self) -> None:
        """Set up the test client."""
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_https_scheme_with_proxy_headers(self) -> None:
        """Test that X-Forwarded-Proto header is respected."""

        @self.app.route("/test_scheme")
        def test_scheme() -> str:
            """Test route to check request scheme."""
            return request.scheme

        response = self.client.get(
            "/test_scheme", headers={"X-Forwarded-Proto": "https"}
        )
        self.assertEqual(response.data.decode(), "https")
