"""Tests for ProxyFix middleware configuration."""

import unittest

from pickaladder import create_app


class TestProxyFix(unittest.TestCase):
    """Test case for ProxyFix middleware."""

    def setUp(self):
        """Set up the test client."""
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_https_scheme_with_proxy_headers(self):
        """Test that X-Forwarded-Proto header is respected."""

        @self.app.route("/test_scheme")
        def test_scheme():
            from flask import request

            return request.scheme

        response = self.client.get(
            "/test_scheme", headers={"X-Forwarded-Proto": "https"}
        )
        self.assertEqual(response.data.decode(), "https")
