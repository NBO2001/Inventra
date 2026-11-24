"""Flask entrypoint for the Inventra API."""

import os
from pathlib import Path

from flask import Flask

from infrastructure.database import close_db, db as db
from migrate import DEFAULT_URL, migrate
from routes import register_routes

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-only")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", DEFAULT_URL)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000
app.config["QR_DEBUG_DIR"] = os.environ.get(
    "QR_DEBUG_DIR", str(Path(__file__).resolve().parent / "instance" / "qr-debug")
)
app.teardown_appcontext(close_db)
register_routes(app)

__all__ = ["app", "db"]


if __name__ == "__main__":
    migrate(app.config["DATABASE_URL"])
    app.run(debug=True, host="127.0.0.1", port=5000)
