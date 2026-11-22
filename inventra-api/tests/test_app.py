from datetime import date
from io import BytesIO
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql

from app import app, db
from import_sqlite import import_sqlite
from migrate import DEFAULT_URL, migrate
from receipt_parser import parse_receipt

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "inventra-collector"
    / "mock-pages"
    / "page-mock.html"
)


@pytest.fixture
def database_url():
    base_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_URL)
    try:
        admin = psycopg.connect(base_url)
    except psycopg.OperationalError:
        pytest.skip(
            "PostgreSQL is unavailable; start it with docker compose up -d postgres"
        )
    schema = "test_" + uuid4().hex
    with admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    test_url = psycopg.conninfo.make_conninfo(
        base_url, options=f"-c search_path={schema}"
    )
    try:
        migrate(test_url)
        yield test_url
    finally:
        with psycopg.connect(base_url) as cleanup:
            cleanup.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.fixture
def client(database_url):
    previous = dict(app.config)
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    try:
        yield app.test_client()
    finally:
        app.config.update(previous)


def test_migrations_are_idempotent(database_url):
    migrate(database_url)
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert conn.execute("SELECT share_mode FROM settings").fetchone()[0] == "ask"


def test_sqlite_import_preserves_receipts_and_is_repeatable(database_url, tmp_path):
    source = tmp_path / "receipts.sqlite3"
    with sqlite3.connect(source) as old:
        old.executescript("""
            CREATE TABLE settings (id INTEGER, share_mode TEXT);
            INSERT INTO settings VALUES (1, 'always');
            CREATE TABLE receipts (id INTEGER, key_hash TEXT, store TEXT,
                store_cnpj TEXT, issued_at TEXT, total TEXT, discount TEXT,
                approx_tax TEXT, shared INTEGER, created_at TEXT);
            INSERT INTO receipts VALUES (7, 'hash', 'Market', NULL, '2026-01-01',
                '10.00', '0', '1.00', 1, '2026-01-01 12:00:00');
            CREATE TABLE items (id INTEGER, receipt_id INTEGER, name TEXT,
                product_key TEXT, code TEXT, quantity TEXT, unit TEXT,
                unit_price TEXT, amount TEXT);
            INSERT INTO items VALUES (3, 7, 'Rice', 'RICE | UN', NULL,
                '1', 'UN', '10.00', '10.00');
            CREATE TABLE dismissed_suggestions (product_key TEXT, last_bought TEXT);
            INSERT INTO dismissed_suggestions VALUES ('RICE | UN', '2026-01-01');
        """)
    assert import_sqlite(source, database_url) == 1
    assert import_sqlite(source, database_url) == 0
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
        assert conn.execute("SELECT share_mode FROM settings").fetchone()[0] == "always"
        assert (
            conn.execute("SELECT last_bought FROM dismissed_suggestions").fetchone()[0]
            == "2026-01-01"
        )


def upload(client, share="no"):
    return client.post(
        "/api/receipts",
        data={
            "receipt_html": (BytesIO(SAMPLE.read_bytes()), "receipt.html"),
            "share": share,
        },
    )


def test_parser_reads_sample_without_raw_private_data():
    receipt = parse_receipt(SAMPLE.read_text())
    assert len(receipt["items"]) == 7
    assert len(receipt["access_key"]) == 44
    assert receipt["approx_tax"] is not None
    assert receipt["total"] is not None


def test_import_dashboard_duplicate_and_withdrawal(client):
    preview = client.post(
        "/api/receipts/preview",
        data={"receipt_html": (BytesIO(SAMPLE.read_bytes()), "receipt.html")},
    )
    assert preview.status_code == 200
    assert "access_key" not in preview.json["receipt"]
    assert "store_cnpj" not in preview.json["receipt"]

    created = upload(client, "yes")
    assert created.status_code == 201
    assert created.json["item_count"] == 7
    assert upload(client).status_code == 409

    dashboard = client.get("/api/dashboard").json
    assert len(dashboard["months"]) == 1
    assert dashboard["months"][0]["count"] == 1
    assert dashboard["months"][0]["tax_count"] == 1
    assert len(client.get("/api/prices").json["observations"]) == 7

    receipt_id = created.json["id"]
    assert (
        client.post(
            f"/api/receipts/{receipt_id}/sharing", json={"shared": False}
        ).status_code
        == 200
    )
    assert client.get("/api/prices").json["observations"] == []
    assert client.get("/api/dashboard").json["months"][0]["count"] == 1


def test_trip_split_respects_store_limit_and_quantities(client):
    first = upload(client, "yes")
    assert first.status_code == 201
    products = client.get("/api/products").json["products"][:2]
    assert len(products) == 2
    keys = [row["product_key"] for row in products]

    with app.app_context():
        connection = db()
        for store, prices in (
            ("Mercado A", ("1.00", "100.00")),
            ("Mercado B", ("100.00", "1.00")),
        ):
            cursor = connection.execute(
                """INSERT INTO receipts
                (key_hash, store, issued_at, total, discount, shared)
                VALUES (%s, %s, %s, '101', '0', 0) RETURNING id""",
                (f"synthetic-{store}", store, date.today().isoformat()),
            )
            receipt_id = cursor.fetchone()["id"]
            for row, price in zip(products, prices):
                connection.execute(
                    """INSERT INTO items
                    (receipt_id, name, product_key, quantity, unit, unit_price, amount)
                    VALUES (%s, %s, %s, '1', %s, %s, %s)""",
                    (
                        receipt_id,
                        row["name"],
                        row["product_key"],
                        row["unit"],
                        price,
                        price,
                    ),
                )
        connection.commit()

    one = client.post("/api/plan", json={"products": keys, "max_stores": 1}).json[
        "plan"
    ]
    two = client.post("/api/plan", json={"products": keys, "max_stores": 2}).json[
        "plan"
    ]
    assert one["coverage"] == 2
    assert two["coverage"] == 2
    assert len(two["stores"]) == 2
    assert float(two["total"]) < float(one["total"])
    doubled = client.post(
        "/api/plan",
        json={"products": keys, "max_stores": 2, "quantities": {keys[0]: "2"}},
    ).json["plan"]
    assert float(doubled["total"]) > float(two["total"])
    assert (
        client.post(
            "/api/plan",
            json={"products": keys, "max_stores": 2, "quantities": {keys[0]: "0"}},
        ).status_code
        == 400
    )


def test_public_product_pages_follow_sharing_choice(client):
    created = upload(client, "yes")
    products = client.get("/api/public/products").json["products"]
    assert products
    slug = products[0]["slug"]
    detail = client.get(f"/api/public/products/{slug}")
    assert detail.status_code == 200
    assert detail.json["product"]["observations"]
    assert "receipt_id" not in str(detail.json)
    assert "access_key" not in str(detail.json)

    client.post(f"/api/receipts/{created.json['id']}/sharing", json={"shared": False})
    assert client.get(f"/api/public/products/{slug}").status_code == 404
