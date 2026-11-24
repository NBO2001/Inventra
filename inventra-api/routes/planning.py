"""Inventra API routes module."""

from flask import Blueprint, jsonify, request

from application.planning import (
    PRICE_MAX_AGE_DAYS,
    _select_plan_items,
    optimize_trip,
    replenishment_suggestions,
)
from infrastructure.database import db

bp = Blueprint("planning", __name__)


@bp.route("/api/replenishment")
def api_replenishment():
    return jsonify(suggestions=replenishment_suggestions())


@bp.route("/api/replenishment/dismiss", methods=["POST"])
def api_dismiss_replenishment():
    payload = request.get_json(silent=True) or {}
    key = payload.get("product_key")
    if not isinstance(key, str) or not key or len(key) > 250:
        return jsonify(error="Invalid product."), 400
    row = (
        db()
        .execute(
            """SELECT MAX(r.issued_at) AS last_bought
        FROM items i JOIN receipts r ON r.id = i.receipt_id WHERE i.product_key = %s""",
            (key,),
        )
        .fetchone()
    )
    if not row["last_bought"]:
        return jsonify(error="Product not found."), 404
    db().execute(
        """INSERT INTO dismissed_suggestions (product_key, last_bought) VALUES (%s, %s)
        ON CONFLICT(product_key) DO UPDATE SET last_bought = excluded.last_bought""",
        (key, row["last_bought"]),
    )
    db().commit()
    return jsonify(dismissed=True)


@bp.route("/api/plan", methods=["POST"])
def api_plan():
    payload = request.get_json(silent=True) or {}
    keys = payload.get("products", [])
    if (
        not isinstance(keys, list)
        or not all(isinstance(key, str) for key in keys)
        or len(keys) > 250
    ):
        return jsonify(error="Select a valid product list."), 400
    try:
        limit = int(payload.get("max_stores", 1))
    except (TypeError, ValueError):
        return jsonify(error="Invalid supermarket limit."), 400
    if not 1 <= limit <= 20:
        return jsonify(error="Choose between 1 and 20 supermarkets."), 400
    overrides = payload.get("quantities", {})
    if not isinstance(overrides, dict):
        return jsonify(error="Invalid quantities."), 400
    try:
        selected = _select_plan_items(keys, overrides)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    result = optimize_trip(selected, limit)
    single = optimize_trip(selected, 1) if limit > 1 else result
    if result:
        result["single_store_total"] = (
            str(single["total"])
            if single and single["coverage"] == result["coverage"]
            else None
        )
        result.pop("rank")
        result["total"] = str(result["total"])
        result["stores"] = {
            store: [{**item, "amount": str(item["amount"])} for item in items]
            for store, items in result["stores"].items()
        }
    return jsonify(plan=result, price_max_age_days=PRICE_MAX_AGE_DAYS)
