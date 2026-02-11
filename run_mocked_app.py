import unittest.mock
from mockfirestore import MockFirestore
import os

# Set up mocks before importing the app
mock_db = MockFirestore()

# Patch firebase_admin
import firebase_admin
from firebase_admin import firestore
firebase_admin.initialize_app = unittest.mock.MagicMock()
firestore.client = unittest.mock.MagicMock(return_value=mock_db)
firebase_admin.auth = unittest.mock.MagicMock()

# Now import the app
from app import app

if __name__ == "__main__":
    # Disable CSRF for easier testing
    app.config["WTF_CSRF_ENABLED"] = False
    app.run(debug=False, host="0.0.0.0", port=27272)
