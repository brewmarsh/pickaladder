from unittest.mock import patch, MagicMock
import mockfirestore
from mockfirestore import MockFirestore, CollectionReference, Query
import firebase_admin
from flask import session, redirect, url_for

# Patch FieldFilter and where to be compatible
class MockFieldFilter:
    def __init__(self, field, op, value):
        self.field = field
        self.op = op
        self.value = value

orig_where = Query.where
def patched_where(self, *args, **kwargs):
    if "filter" in kwargs:
        f = kwargs["filter"]
        return orig_where(self, f.field, f.op, f.value)
    return orig_where(self, *args, **kwargs)

Query.where = patched_where
CollectionReference.where = patched_where

# Mock Firestore before importing anything
mock_db = MockFirestore()

# Setup some mock data
mock_db.collection("users").document("testuser_id").set({
    "username": "testuser",
    "email": "test@example.com",
    "name": "Test User",
    "avatar_url": "",
    "uid": "testuser_id"
})

# Mock firestore module
mock_firestore_module = MagicMock()
mock_firestore_module.client.return_value = mock_db
mock_firestore_module.FieldFilter = MockFieldFilter
mock_firestore_module.SERVER_TIMESTAMP = "mock_timestamp"
mock_firestore_module.ArrayUnion = lambda x: x
mock_firestore_module.ArrayRemove = lambda x: x

# Globally patch firebase_admin.firestore.client
firebase_admin.firestore.client = MagicMock(return_value=mock_db)

# We also need to handle the case where it's already imported
import pickaladder
with patch("firebase_admin.credentials.Certificate"), \
     patch("firebase_admin.initialize_app"), \
     patch("pickaladder.user.routes.firestore", mock_firestore_module), \
     patch("pickaladder.tournament.routes.firestore", mock_firestore_module), \
     patch("pickaladder.group.routes.firestore", mock_firestore_module), \
     patch("pickaladder.match.routes.firestore", mock_firestore_module), \
     patch("pickaladder.teams.routes.firestore", mock_firestore_module), \
     patch("pickaladder.user.utils.firestore", mock_firestore_module), \
     patch("pickaladder.group.utils.firestore", mock_firestore_module), \
     patch("pickaladder.firestore", mock_firestore_module):

    from pickaladder import create_app
    app = create_app()

    @app.route("/debug_login")
    def debug_login():
        session["user_id"] = "testuser_id"
        return redirect(url_for("user.dashboard"))

    if __name__ == "__main__":
        app.run(debug=True, host="0.0.0.0", port=27272)
