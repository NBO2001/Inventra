"""Inventra API infrastructure module."""

import json
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex

from flask import current_app, request


def qr_image_suffix(image):
    if image.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return ".webp"
    if image[4:8] == b"ftyp" and image[8:12] in {b"heic", b"heix", b"mif1"}:
        return ".heic"
    return None


def save_qr_failure(image, suffix, reason, attempts):
    directory = Path(current_app.config["QR_DEBUG_DIR"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + token_hex(6)
    image_path = directory / f"{report_id}{suffix}"
    metadata = {
        "reason": reason,
        "attempts": attempts,
        "image_bytes": len(image),
        "image_format": suffix,
        "user_agent": request.user_agent.string[:300],
    }
    image_path.write_bytes(image)
    image_path.chmod(0o600)
    report_path = directory / f"{report_id}.json"
    report_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    report_path.chmod(0o600)
    current_app.logger.warning(
        "QR capture failed: id=%s reason=%s attempts=%s image=%s",
        report_id,
        reason,
        attempts,
        image_path,
    )
    return report_id
