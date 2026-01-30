"""Tests for ProxyFix middleware configuration."""

import unittest

from pickaladder import create_app


class TestProxyFix(unittest.TestCase):
    """Test case for ProxyFix middleware."""

    # TODO: Add type hints for Agent clarity
    def setUp(self):
        """Set up the test client."""
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    # TODO: Add type hints for Agent clarity
    def test_https_scheme_with_proxy_headers(self):
        """Test that X-Forwarded-Proto header is respected."""

        # TODO: Add type hints for Agent clarity
        @self.app.route("/test_scheme")
        def test_scheme():
            """TODO: Add docstring for AI context."""
            from flask import request

            return request.scheme

        response = self.client.get(
            "/test_scheme", headers={"X-Forwarded-Proto": "https"}
        )
        self.assertEqual(response.data.decode(), "https")
