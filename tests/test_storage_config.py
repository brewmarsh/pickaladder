"""Test to verify Firebase Storage configuration."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class TestStorageConfig(unittest.TestCase):
    """Test case for storage configuration."""

    def setUp(self) -> None:
        self.mock_initialize_app = patch("firebase_admin.initialize_app").start()
        # Mock credentials to avoid actual Firebase initialization
        self.mock_cred = patch("firebase_admin.credentials.Certificate").start()
        self.mock_get_creds = patch("pickaladder._get_firebase_credentials").start()
        self.mock_get_creds.return_value = (MagicMock(), "test-project")

        # Patch os.environ to control environment variables
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

        self.addCleanup(patch.stopall)

    def test_default_storage_bucket(self) -> None:
        """Test that the storage bucket defaults to pickaladder.firebasestorage.app."""
        # Ensure env var is NOT set
        if "FIREBASE_STORAGE_BUCKET" in os.environ:
            del os.environ["FIREBASE_STORAGE_BUCKET"]

        app = create_app(
            {"TESTING": False}
        )  # TESTING=False to trigger _initialize_firebase

        # Verify initialize_app was called with the expected storage bucket
        self.mock_initialize_app.assert_called_once()
        args, kwargs = self.mock_initialize_app.call_args
        options = args[1] if len(args) > 1 else kwargs.get("options", {})

        self.assertEqual(
            options.get("storageBucket"), "pickaladder.firebasestorage.app"
        )
        self.assertEqual(
            app.config.get("FIREBASE_STORAGE_BUCKET"), "pickaladder.firebasestorage.app"
        )

    def test_override_storage_bucket_via_env(self) -> None:
        """Test that the storage bucket can be overridden via environment variable."""
        os.environ["FIREBASE_STORAGE_BUCKET"] = "custom-bucket.appspot.com"

        app = create_app({"TESTING": False})

        self.mock_initialize_app.assert_called_once()
        args, kwargs = self.mock_initialize_app.call_args
        options = args[1] if len(args) > 1 else kwargs.get("options", {})

        self.assertEqual(options.get("storageBucket"), "custom-bucket.appspot.com")
        self.assertEqual(
            app.config.get("FIREBASE_STORAGE_BUCKET"), "custom-bucket.appspot.com"
        )


if __name__ == "__main__":
    unittest.main()
