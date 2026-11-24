"""Inventra API routes module."""

import json
from flask import Blueprint, current_app, jsonify, request

from infrastructure.qr_decoder import QrDecodeError, decode_qr_image
from infrastructure.qr_debug import qr_image_suffix, save_qr_failure

bp = Blueprint("qr", __name__)


@bp.before_request
def qr_debug_upload_limit():
    if request.path in {"/api/qr-debug", "/api/qr/decode"}:
        request.max_content_length = 20_000_000


@bp.errorhandler(413)
def too_large(_error):
    if request.path in {"/api/qr-debug", "/api/qr/decode"}:
        return jsonify(error="A foto excede o limite de 20 MB."), 413
    return jsonify(error="The receipt page exceeds the 1 MB limit."), 413


@bp.route("/api/qr/decode", methods=["POST"])
def api_decode_qr():
    uploaded = request.files.get("image")
    if not uploaded:
        return jsonify(error="Envie uma foto do QR code."), 400
    image = uploaded.read(19_000_001)
    if len(image) > 19_000_000:
        return jsonify(error="A foto excede o limite de 19 MB."), 413
    suffix = qr_image_suffix(image)
    if not suffix:
        return jsonify(error="Formato de imagem não compatível."), 400
    try:
        url, attempts = decode_qr_image(image)
    except QrDecodeError as exc:
        report_id = save_qr_failure(image, suffix, exc.reason, exc.attempts)
        return jsonify(error=str(exc), reason=exc.reason, id=report_id), 422
    current_app.logger.info(
        "QR decoded: image_bytes=%s attempts=%s", len(image), attempts
    )
    return jsonify(url=url)


@bp.route("/api/qr-debug", methods=["POST"])
def api_qr_debug():
    uploaded = request.files.get("image")
    reason = request.form.get("reason", "")
    if not uploaded or reason not in {
        "image_load_failed",
        "canvas_unavailable",
        "qr_not_found",
        "invalid_url",
        "unsupported_qr_url",
        "unexpected_error",
    }:
        return jsonify(error="Invalid QR debug report."), 400
    image = uploaded.read(19_000_001)
    if len(image) > 19_000_000:
        return jsonify(error="The debug photo exceeds the 19 MB image limit."), 413
    suffix = qr_image_suffix(image)
    if not suffix:
        return jsonify(error="Unsupported debug image format."), 400
    try:
        attempts = json.loads(request.form.get("attempts", "[]"))
    except json.JSONDecodeError:
        return jsonify(error="Invalid QR debug attempts."), 400
    if (
        not isinstance(attempts, list)
        or len(attempts) > 5
        or any(
            not isinstance(attempt, dict)
            or not {"width", "height", "found"} <= set(attempt)
            or not set(attempt) <= {"width", "height", "found", "rotation"}
            or type(attempt["width"]) is not int
            or type(attempt["height"]) is not int
            or type(attempt["found"]) is not bool
            or attempt.get("rotation", "none")
            not in {"none", "clockwise", "counterclockwise"}
            or not 0 < attempt["width"] <= 10000
            or not 0 < attempt["height"] <= 10000
            for attempt in attempts
        )
    ):
        return jsonify(error="Invalid QR debug attempts."), 400
    report_id = save_qr_failure(image, suffix, reason, attempts)
    return jsonify(id=report_id), 201
