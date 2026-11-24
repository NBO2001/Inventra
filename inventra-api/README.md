# inventra-api

Flask API for the local Inventra prototype. Start PostgreSQL from the repository root with `docker compose up -d postgres`. Then run `uv sync`, `uv run python migrate.py`, and `uv run python app.py` from this directory. The API listens on `127.0.0.1:5000`. Set `DATABASE_URL` to override the default local PostgreSQL connection. Migrations run in filename order, are tracked in `schema_migrations`, and can be rerun safely. The server also applies pending migrations on direct startup.

The API is organized by responsibility: `domain/` contains receipt parsing and pure receipt rules; `application/` contains planning and settings use cases; `routes/` contains Flask blueprints grouped by feature; and `infrastructure/` contains PostgreSQL access, SEFAZ requests, QR image decoding, and local diagnostic storage. `app.py` configures Flask and registers the routes. `migrate.py` and `import_sqlite.py` are command-line entrypoints.

The API parses SEFAZ-AM NFC-e QR pages or uploaded saved HTML. It stores a hash of the access key for duplicate detection, not the raw key or HTML. Sharing is off by default and can be changed per receipt. `/api/public/products` and `/api/public/products/<slug>` only return observations from shared receipts.

`POST /api/qr/decode` accepts a camera photo, reads QR codes in the backend, and returns a validated SEFAZ-AM URL. Failed photos and diagnostic reports are kept locally under `instance/qr-debug/`; successful photos are not retained. Tests generate synthetic QR images in memory.

To transfer data from the previous SQLite prototype, run `uv run python import_sqlite.py instance/receipts.sqlite3` after starting PostgreSQL. The import is repeatable and keeps the SQLite file intact. Use `--database-url` if your target differs from the local default.

Run `uv run pytest -q` with PostgreSQL running to test parsing and import against the repository's anonymized collector mock page, plus migrations, dashboard totals, list comparison, and sharing withdrawal. Tests use isolated PostgreSQL schemas. Set `TEST_DATABASE_URL` if your test server differs from the default.
