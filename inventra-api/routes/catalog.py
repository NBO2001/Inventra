"""Inventra API routes module."""

import re
from decimal import Decimal
from hashlib import sha256

from flask import Blueprint, jsonify, request

from infrastructure.database import db

bp = Blueprint("catalog", __name__)


@bp.route("/api/prices")
def api_prices():
    query = request.args.get("q", "").strip()[:80]
    rows = (
        db()
        .execute(
            """SELECT i.name, i.product_key, i.unit, i.unit_price,
        r.store, r.issued_at FROM items i JOIN receipts r ON r.id = i.receipt_id
        WHERE r.shared = 1 AND i.name LIKE %s
        ORDER BY r.issued_at DESC, i.name LIMIT 200""",
            ("%" + query + "%",),
        )
        .fetchall()
    )
    return jsonify(observations=[dict(row) for row in rows])


@bp.route("/api/public/products")
def api_public_products():
    query = request.args.get("q", "").strip()[:80]
    rows = (
        db()
        .execute(
            """SELECT i.product_key, MAX(i.name) AS name, MAX(i.unit) AS unit,
        COUNT(*) AS observation_count, COUNT(DISTINCT r.id) AS receipt_count,
        COUNT(DISTINCT r.store) AS store_count,
        MAX(r.issued_at) AS last_seen
        FROM items i JOIN receipts r ON r.id = i.receipt_id
        WHERE r.shared = 1 AND i.name LIKE %s
        GROUP BY i.product_key
        ORDER BY last_seen DESC, observation_count DESC LIMIT 150""",
            ("%" + query + "%",),
        )
        .fetchall()
    )
    return jsonify(
        products=[
            {**dict(row), "slug": sha256(row["product_key"].encode()).hexdigest()[:20]}
            for row in rows
        ]
    )


@bp.route("/api/public/products/<slug>")
def api_public_product(slug):
    if not re.fullmatch(r"[0-9a-f]{20}", slug):
        return jsonify(error="Product not found."), 404
    rows = db().execute("""SELECT i.product_key, i.name, i.unit, i.quantity,
        i.amount, r.id AS receipt_id, r.store, r.issued_at
        FROM items i JOIN receipts r ON r.id = i.receipt_id
        WHERE r.shared = 1 ORDER BY r.issued_at DESC LIMIT 5000""").fetchall()
    matches = [
        row
        for row in rows
        if sha256(row["product_key"].encode()).hexdigest()[:20] == slug
    ]
    if not matches:
        return jsonify(error="Product not found."), 404
    observations = [
        {
            "store": row["store"],
            "issued_at": row["issued_at"],
            "unit_price": str(Decimal(row["amount"]) / Decimal(row["quantity"])),
        }
        for row in matches
    ]
    return jsonify(
        product={
            "name": matches[0]["name"],
            "unit": matches[0]["unit"],
            "observation_count": len(observations),
            "receipt_count": len({row["receipt_id"] for row in matches}),
            "store_count": len({row["store"] for row in matches}),
            "observations": observations,
        }
    )


@bp.route("/api/products")
def api_products():
    rows = db().execute("""SELECT * FROM (
        SELECT DISTINCT ON (i.product_key) i.product_key, i.name, i.unit, i.quantity,
        r.issued_at AS last_seen FROM items i
        JOIN receipts r ON r.id = i.receipt_id
        ORDER BY i.product_key, r.issued_at DESC, r.id DESC, i.id DESC
        ) latest ORDER BY last_seen DESC, name LIMIT 250""").fetchall()
    return jsonify(products=[dict(row) for row in rows])
