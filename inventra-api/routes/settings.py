"""Inventra API routes module."""

from flask import Blueprint, jsonify, request

from application.settings import setting
from infrastructure.database import db

bp = Blueprint("settings", __name__)


@bp.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        mode = payload.get("share_mode")
        if mode not in {"ask", "always", "never"}:
            return jsonify(error="Invalid sharing preference."), 400
        db().execute("UPDATE settings SET share_mode = %s WHERE id = 1", (mode,))
        db().commit()
    return jsonify(share_mode=setting())
