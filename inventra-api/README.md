# inventra-api

Flask API for the local Inventra prototype. Run from this directory with `uv sync` and `uv run python app.py`; the API listens on `127.0.0.1:5000` and stores data in `instance/receipts.sqlite3`.

The API parses SEFAZ-AM NFC-e QR pages or uploaded saved HTML. It stores a hash of the access key for duplicate detection, not the raw key or HTML. Sharing is off by default and can be changed per receipt. `/api/public/products` and `/api/public/products/<slug>` only return observations from shared receipts.

Run `uv run pytest -q` to test parsing and import against the repository's anonymized collector mock page, plus dashboard totals, list comparison, and sharing withdrawal.
