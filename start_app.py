import sys
import os
import logging
sys.path.insert(0, '/app')

from flask import Flask, g
from unittest.mock import patch, MagicMock

# Mock Firebase
patch("pickaladder.__init__.firebase_admin.initialize_app").start()
patch("pickaladder.__init__.firestore.client").start()

from pickaladder import create_app

app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "CACHE_TYPE": "NullCache", "SERVER_NAME": "localhost:3000"})

@app.before_request
def mock_auth():
    g.user = None # We want to test login, so g.user must be None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=3000, debug=False)
