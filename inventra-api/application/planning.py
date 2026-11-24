"""Inventra API application module."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from infrastructure.database import db

PRICE_MAX_AGE_DAYS = 30


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


def replenishment_suggestions() -> list[dict]:
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
    return suggestions[:30]
