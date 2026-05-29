"""Main entry point for the application."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pickaladder import create_app

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

app = create_app()


@app.route("/health")
def health_check() -> str | Response | tuple[str, int]:
    """Perform a simple health check."""
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=27272)  # nosec
