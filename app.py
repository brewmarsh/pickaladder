"""Main entry point for the application."""

from typing import Response, Union

from pickaladder import create_app

app = create_app()


@app.route("/health")
def health_check() -> Union[str, Response]:
    """Perform a simple health check."""
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=27272)  # nosec
