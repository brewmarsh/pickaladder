"""Utility functions for the Pick-a-Ladder application."""

import os


def get_storage_bucket_name():
    """Determine the Firebase Storage bucket name.

    It checks for an environment variable first, then falls back to deriving
    the name from the Google Cloud project ID.

    Returns:
        str: The name of the storage bucket, or None if it cannot be determined.
    """
    # First, check for the environment variable
    storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        return storage_bucket

    # If not found, try to derive it from the project ID
    project_id = None
    try:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        _, project_id = google.auth.default()
    except (ImportError, DefaultCredentialsError):
        # This can happen in local development if gcloud SDK is not configured.
        # We can try to get it from the credentials file if it exists.
        cred_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "firebase_credentials.json"
        )
        if os.path.exists(cred_path):
            import json

            try:
                with open(cred_path, "r") as f:
                    cred_info = json.load(f)
                project_id = cred_info.get("project_id")
            except (ValueError, json.JSONDecodeError):
                project_id = None

    if project_id:
        return f"{project_id}.appspot.com"

    return None


def send_email(to, subject, template, **context):
    """A placeholder for sending an email."""
    # This is a placeholder. In a real application, you would implement this
    # using Flask-Mail or a similar extension.
    pass
