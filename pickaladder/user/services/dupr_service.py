import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

class DUPRService:
    """Service for interacting with the DUPR API."""

    @staticmethod
    def fetch_rating(dupr_id: str) -> float | None:
        """
        Fetch the DUPR rating for a given DUPR ID.

        Args:
            dupr_id: The DUPR ID to fetch the rating for.

        Returns:
            The DUPR rating as a float, or None if the request failed.
        """
        api_key = current_app.config.get("DUPR_API_KEY")
        base_url = current_app.config.get("DUPR_BASE_URL", "https://api.mydupr.com")

        if not api_key:
            logger.warning("DUPR_API_KEY is not configured. Skipping API call.")
            return None

        if not dupr_id:
            logger.warning("No dupr_id provided for rating fetch.")
            return None

        try:
            # We assume a standard REST API structure for DUPR
            # The exact endpoint and header might need adjustment based on real DUPR docs
            url = f"{base_url}/v1/player/{dupr_id}"
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers, timeout=10)
            success_code = 200

            if response.status_code == success_code:
                data = response.json()
                # Typical response might have multiple ratings (doubles, singles)
                # We'll default to doubles or a general rating field
                return float(data.get("rating") or data.get("doubles_rating") or 0.0)

            logger.error(f"DUPR API returned error {response.status_code}: {response.text}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch DUPR rating for ID {dupr_id}: {e}")
            return None
