from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from app import app, db
from receipt_parser import parse_receipt

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "inventra-collector"
    / "mock-pages"
    / "page-mock.html"
)


@pytest.fixture
def client(tmp_path):
    app.config.update(TESTING=True, DATABASE=str(tmp_path / "test.sqlite3"))
    return app.test_client()


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
                VALUES (?, ?, ?, '101', '0', 0)""",
                (f"synthetic-{store}", store, date.today().isoformat()),
            )
            for row, price in zip(products, prices):
                connection.execute(
                    """INSERT INTO items
                    (receipt_id, name, product_key, quantity, unit, unit_price, amount)
                    VALUES (?, ?, ?, '1', ?, ?, ?)""",
                    (
                        cursor.lastrowid,
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
