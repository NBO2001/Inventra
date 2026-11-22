.PHONY: help db-up db-stop migrate setup api web test test-api test-collector build-web import-sqlite

help:
	@echo "make setup          Start PostgreSQL, install API dependencies, and migrate"
	@echo "make api            Run the Flask API"
	@echo "make web            Run the Next.js development server"
	@echo "make test           Run API and collector tests, then build the web app"
	@echo "make import-sqlite  Transfer an existing SQLite database into PostgreSQL"
	@echo "make db-stop        Stop the PostgreSQL container"

db-up:
	docker compose up -d --wait postgres

db-stop:
	docker compose stop postgres

migrate:
	cd inventra-api && uv run python migrate.py

setup: db-up
	cd inventra-api && uv sync
	$(MAKE) migrate

api:
	cd inventra-api && uv run python app.py

web:
	cd inventra-web && npm run dev

test-api: db-up
	cd inventra-api && uv run pytest -q

test-collector:
	cd inventra-collector && uv run pytest -q

build-web:
	cd inventra-web && npm run build

test: test-api test-collector build-web

SQLITE_FILE ?= inventra-api/instance/receipts.sqlite3
import-sqlite:
	cd inventra-api && uv run python import_sqlite.py "$(abspath $(SQLITE_FILE))"
