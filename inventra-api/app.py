"""Local-first prototype for receipt-based grocery planning in Manaus."""

from __future__ import annotations

import os
import re
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from secrets import token_hex
from statistics import median
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from flask import Flask, g, jsonify, request
import psycopg
from psycopg.rows import dict_row

from migrate import DEFAULT_URL, migrate
from receipt_parser import ReceiptParseError, parse_receipt

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-only")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", DEFAULT_URL)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000
app.config["QR_DEBUG_DIR"] = os.environ.get(
    "QR_DEBUG_DIR", str(Path(__file__).resolve().parent / "instance" / "qr-debug")
)
SEFAZ_HOST = "sistemas.sefaz.am.gov.br"
PRICE_MAX_AGE_DAYS = 30  # Pilot default; validate with Manaus shoppers.


def db():
    if "db" not in g:
        g.db = psycopg.connect(app.config["DATABASE_URL"], row_factory=dict_row)
    return g.db


@app.teardown_appcontext
def close_db(_error):
    connection = g.pop("db", None)
    if connection:
        connection.close()


def product_key(name: str, unit: str) -> str:
    return re.sub(r"\s+", " ", name.upper()).strip() + " | " + unit.upper()


def setting():
    return (
        db()
        .execute("SELECT share_mode FROM settings WHERE id = 1")
        .fetchone()["share_mode"]
    )


def fetch_qr_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != SEFAZ_HOST
        or parsed.port not in (None, 443)
        or parsed.path != "/nfceweb/consultarNFCe.jsp"
        or "p" not in parse_qs(parsed.query)
    ):
        raise ReceiptParseError(
            "Use a SEFAZ-AM NFC-e QR link, or upload its saved HTML page."
        )
    # Older printed QR codes use HTTP. Upgrade locally before sending the access token.
    secure_url = parsed._replace(scheme="https").geturl()
    req = Request(
        secure_url, headers={"User-Agent": "Mozilla/5.0 receipt-consumer-prototype"}
    )
    with urlopen(req, timeout=12) as response:
        if urlparse(response.url).hostname != SEFAZ_HOST:
            raise ReceiptParseError("The receipt link redirected outside SEFAZ-AM.")
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ReceiptParseError("The receipt page is too large.")
    return raw.decode("utf-8", errors="replace")


def optimize_trip(selected: list[dict], limit: int):
    """Exact search over store combinations; unpriced products remain unresolved."""
    from itertools import combinations

    wanted = {row["product_key"]: row for row in selected}
    if not wanted:
        return None
    cutoff = (date.today() - timedelta(days=PRICE_MAX_AGE_DAYS)).isoformat()
    observations = (
        db()
        .execute(
            """SELECT i.product_key, i.amount, i.quantity,
        r.store, r.issued_at
        FROM items i JOIN receipts r ON r.id = i.receipt_id
        WHERE r.issued_at >= %s
        ORDER BY r.issued_at DESC, r.id DESC, i.id DESC""",
            (cutoff,),
        )
        .fetchall()
    )
    latest = {}
    for obs in observations:
        key = (obs["product_key"], obs["store"])
        if key not in latest:
            latest[key] = obs
    stores = sorted({store for key, store in latest if key in wanted})
    if not stores:
        return None
    best = None
    for count in range(1, min(limit, len(stores)) + 1):
        for combination in combinations(stores, count):
            assigned = defaultdict(list)
            missing = []
            total = Decimal(0)
            for key, item in wanted.items():
                options = [
                    (
                        Decimal(latest[(key, store)]["amount"])
                        / Decimal(latest[(key, store)]["quantity"]),
                        store,
                        latest[(key, store)]["issued_at"],
                    )
                    for store in combination
                    if (key, store) in latest
                ]
                if not options:
                    missing.append(item["name"])
                    continue
                unit_price, store, observed_at = min(options)
                amount = unit_price * Decimal(item["quantity"])
                total += amount
                assigned[store].append(
                    {
                        "name": item["name"],
                        "quantity": item["quantity"],
                        "amount": amount,
                        "observed_at": observed_at,
                    }
                )
            rank = (len(missing), total, len(assigned))
            candidate = {
                "rank": rank,
                "stores": dict(assigned),
                "missing": missing,
                "total": total,
                "coverage": len(wanted) - len(missing),
                "count": len(wanted),
            }
            if best is None or rank < best["rank"]:
                best = candidate
    return best


def receipt_from_request():
    uploaded = request.files.get("receipt_html")
    if uploaded and uploaded.filename:
        html = uploaded.read().decode("utf-8", errors="replace")
    elif request.form.get("qr_url", "").strip():
        html = fetch_qr_url(request.form["qr_url"])
    else:
        raise ReceiptParseError("Provide a SEFAZ-AM QR link or saved HTML page.")
    parsed = parse_receipt(html)
    typed_key = re.sub(r"\D", "", request.form.get("access_key", ""))
    if typed_key and typed_key != parsed["access_key"]:
        raise ReceiptParseError("The access key does not match the receipt page.")
    return parsed


def public_receipt(parsed):
    return {
        key: value
        for key, value in parsed.items()
        if key not in {"access_key", "store_cnpj"}
    }


@app.before_request
def qr_debug_upload_limit():
    if request.path == "/api/qr-debug":
        request.max_content_length = 20_000_000


@app.errorhandler(413)
def too_large(_error):
    if request.path == "/api/qr-debug":
        return jsonify(error="The debug photo exceeds the 20 MB limit."), 413
    return jsonify(error="The receipt page exceeds the 1 MB limit."), 413


@app.route("/api/qr-debug", methods=["POST"])
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
    if image.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif image.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        suffix = ".webp"
    elif image[4:8] == b"ftyp" and image[8:12] in {b"heic", b"heix", b"mif1"}:
        suffix = ".heic"
    else:
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
            or set(attempt) != {"width", "height", "found"}
            or type(attempt["width"]) is not int
            or type(attempt["height"]) is not int
            or type(attempt["found"]) is not bool
            or not 0 < attempt["width"] <= 10000
            or not 0 < attempt["height"] <= 10000
            for attempt in attempts
        )
    ):
        return jsonify(error="Invalid QR debug attempts."), 400
    directory = Path(app.config["QR_DEBUG_DIR"])
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
    app.logger.warning(
        "QR capture failed: id=%s reason=%s attempts=%s image=%s",
        report_id,
        reason,
        attempts,
        image_path,
    )
    return jsonify(id=report_id), 201


@app.route("/api/dashboard")
def api_dashboard():
    receipts = db().execute("""SELECT id, store, issued_at, total, approx_tax, shared,
        (SELECT COUNT(*) FROM items WHERE receipt_id = receipts.id) AS item_count
        FROM receipts ORDER BY issued_at DESC, id DESC""").fetchall()
    monthly = defaultdict(
        lambda: {"spend": Decimal(0), "tax": Decimal(0), "count": 0, "tax_count": 0}
    )
    for receipt in receipts:
        bucket = monthly[receipt["issued_at"][:7]]
        bucket["spend"] += Decimal(receipt["total"])
        bucket["count"] += 1
        if receipt["approx_tax"] is not None:
            bucket["tax"] += Decimal(receipt["approx_tax"])
            bucket["tax_count"] += 1
    months = [
        {
            "month": month,
            **{k: str(v) if isinstance(v, Decimal) else v for k, v in data.items()},
        }
        for month, data in sorted(monthly.items(), reverse=True)
    ]
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


@app.route("/api/receipts/preview", methods=["POST"])
def api_preview():
    try:
        return jsonify(receipt=public_receipt(receipt_from_request()))
    except (ReceiptParseError, OSError, ValueError) as exc:
        app.logger.warning(
            "Receipt preview failed: source=%s error_type=%s",
            "qr_url" if request.form.get("qr_url") else "html",
            type(exc).__name__,
        )
        return jsonify(error=str(exc)), 400


@app.route("/api/receipts", methods=["POST"])
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


@app.route("/api/receipts/<int:receipt_id>", methods=["GET"])
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


@app.route("/api/receipts/<int:receipt_id>/sharing", methods=["POST"])
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


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        mode = payload.get("share_mode")
        if mode not in {"ask", "always", "never"}:
            return jsonify(error="Invalid sharing preference."), 400
        db().execute("UPDATE settings SET share_mode = %s WHERE id = 1", (mode,))
        db().commit()
    return jsonify(share_mode=setting())


@app.route("/api/prices")
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


@app.route("/api/public/products")
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


@app.route("/api/public/products/<slug>")
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


@app.route("/api/products")
def api_products():
    rows = db().execute("""SELECT * FROM (
        SELECT DISTINCT ON (i.product_key) i.product_key, i.name, i.unit, i.quantity,
        r.issued_at AS last_seen FROM items i
        JOIN receipts r ON r.id = i.receipt_id
        ORDER BY i.product_key, r.issued_at DESC, r.id DESC, i.id DESC
        ) latest ORDER BY last_seen DESC, name LIMIT 250""").fetchall()
    return jsonify(products=[dict(row) for row in rows])


@app.route("/api/replenishment")
def api_replenishment():
    rows = db().execute("""SELECT i.product_key, i.name, r.issued_at
        FROM items i JOIN receipts r ON r.id = i.receipt_id
        ORDER BY i.product_key, r.issued_at""").fetchall()
    history = defaultdict(lambda: {"name": "", "dates": set()})
    for row in rows:
        history[row["product_key"]]["name"] = row["name"]
        history[row["product_key"]]["dates"].add(row["issued_at"])
    today = date.today()
    dismissed = {
        row["product_key"]: row["last_bought"]
        for row in db().execute(
            "SELECT product_key, last_bought FROM dismissed_suggestions"
        )
    }
    suggestions = []
    for key, group in history.items():
        dates = sorted(date.fromisoformat(value) for value in group["dates"])
        if len(dates) < 3:
            continue
        gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
        typical_days = median(gaps)
        if (
            typical_days <= 0
            or (today - dates[-1]).days < typical_days
            or dismissed.get(key) == dates[-1].isoformat()
        ):
            continue
        suggestions.append(
            {
                "product_key": key,
                "name": group["name"],
                "last_bought": dates[-1].isoformat(),
                "typical_days": typical_days,
                "estimated_next": (
                    dates[-1] + timedelta(days=typical_days)
                ).isoformat(),
            }
        )
    suggestions.sort(key=lambda row: row["estimated_next"])
    return jsonify(suggestions=suggestions[:30])


@app.route("/api/replenishment/dismiss", methods=["POST"])
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


def _select_plan_items(keys: list[str], overrides: dict) -> list[dict]:
    rows = db().execute("""SELECT * FROM (
        SELECT DISTINCT ON (i.product_key) i.product_key, i.name, i.unit, i.quantity,
        r.issued_at AS last_seen FROM items i
        JOIN receipts r ON r.id = i.receipt_id
        ORDER BY i.product_key, r.issued_at DESC, r.id DESC, i.id DESC
        ) latest ORDER BY last_seen DESC""").fetchall()
    selected = []
    for row in rows:
        if row["product_key"] not in keys:
            continue
        entry = dict(row)
        try:
            quantity = Decimal(str(overrides.get(row["product_key"], row["quantity"])))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Invalid item quantity.") from exc
        if not Decimal("0") < quantity <= Decimal("1000"):
            raise ValueError("Item quantity must be above zero and at most 1000.")
        entry["quantity"] = str(quantity)
        selected.append(entry)
    return selected


@app.route("/api/plan", methods=["POST"])
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


if __name__ == "__main__":
    migrate(app.config["DATABASE_URL"])
    app.run(debug=True, host="127.0.0.1", port=5000)
