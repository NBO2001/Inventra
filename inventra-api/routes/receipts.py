"""Inventra API routes module."""

from hashlib import sha256

from flask import Blueprint, current_app, jsonify, request

from application.receipt_import import parse_receipt_source
from domain.receipt_helpers import product_key, public_receipt, summarize_months
from domain.receipt_parser import ReceiptParseError
from infrastructure.database import db

bp = Blueprint("receipts", __name__)


def receipt_from_request():
    uploaded = request.files.get("receipt_html")
    return parse_receipt_source(
        uploaded.read() if uploaded and uploaded.filename else None,
        request.form.get("qr_url", ""),
        request.form.get("access_key", ""),
    )


@bp.route("/api/dashboard")
def api_dashboard():
    receipts = db().execute("""SELECT id, store, issued_at, total, approx_tax, shared,
        (SELECT COUNT(*) FROM items WHERE receipt_id = receipts.id) AS item_count
        FROM receipts ORDER BY issued_at DESC, id DESC""").fetchall()
    months = summarize_months(receipts)
    available_store_count = (
        db()
        .execute("SELECT COUNT(DISTINCT store) AS count FROM receipts")
        .fetchone()["count"]
    )
    return jsonify(
        receipts=[dict(row) for row in receipts],
        months=months,
        available_store_count=available_store_count,
    )


@bp.route("/api/receipts/preview", methods=["POST"])
def api_preview():
    try:
        return jsonify(receipt=public_receipt(receipt_from_request()))
    except (ReceiptParseError, OSError, ValueError) as exc:
        current_app.logger.warning(
            "Receipt preview failed: source=%s error_type=%s",
            "qr_url" if request.form.get("qr_url") else "html",
            type(exc).__name__,
        )
        return jsonify(error=str(exc)), 400


@bp.route("/api/receipts", methods=["POST"])
def api_create_receipt():
    try:
        parsed = receipt_from_request()
        fingerprint = sha256(parsed["access_key"].encode()).hexdigest()
        existing = (
            db()
            .execute("SELECT id FROM receipts WHERE key_hash = %s", (fingerprint,))
            .fetchone()
        )
        if existing:
            return (
                jsonify(
                    error="This receipt is already in your history.", id=existing["id"]
                ),
                409,
            )
        share_value = request.form.get("share")
        if share_value not in {"yes", "no"}:
            return jsonify(error="Choose whether to share this receipt."), 400
        cursor = db().execute(
            """INSERT INTO receipts
            (key_hash, store, store_cnpj, issued_at, total, discount, approx_tax, shared)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                fingerprint,
                parsed["store"],
                parsed["store_cnpj"],
                parsed["issued_at"],
                parsed["total"],
                parsed["discount"],
                parsed["approx_tax"],
                int(share_value == "yes"),
            ),
        )
        receipt_id = cursor.fetchone()["id"]
        db().cursor().executemany(
            """INSERT INTO items
            (receipt_id, name, product_key, code, quantity, unit, unit_price, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    receipt_id,
                    item["name"],
                    product_key(item["name"], item["unit"]),
                    item["code"],
                    item["quantity"],
                    item["unit"],
                    item["unit_price"],
                    item["amount"],
                )
                for item in parsed["items"]
            ],
        )
        db().commit()
        return jsonify(id=receipt_id, item_count=len(parsed["items"])), 201
    except (ReceiptParseError, OSError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@bp.route("/api/receipts/<int:receipt_id>", methods=["GET"])
def api_receipt_detail(receipt_id):
    receipt = (
        db()
        .execute(
            """SELECT id, store, issued_at, total, discount, approx_tax, shared
        FROM receipts WHERE id = %s""",
            (receipt_id,),
        )
        .fetchone()
    )
    if not receipt:
        return jsonify(error="Receipt not found."), 404
    items = (
        db()
        .execute(
            """SELECT id, name, quantity, unit, unit_price, amount
        FROM items WHERE receipt_id = %s ORDER BY id""",
            (receipt_id,),
        )
        .fetchall()
    )
    return jsonify(receipt=dict(receipt), items=[dict(row) for row in items])


@bp.route("/api/receipts/<int:receipt_id>/sharing", methods=["POST"])
def api_receipt_sharing(receipt_id):
    payload = request.get_json(silent=True) or {}
    if type(payload.get("shared")) is not bool:
        return jsonify(error="Provide shared as true or false."), 400
    result = db().execute(
        "UPDATE receipts SET shared = %s WHERE id = %s",
        (int(payload["shared"]), receipt_id),
    )
    if not result.rowcount:
        return jsonify(error="Receipt not found."), 404
    db().commit()
    return jsonify(shared=payload["shared"])
