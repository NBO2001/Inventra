"""Inventra API domain module."""

import re
from collections import defaultdict
from decimal import Decimal


def product_key(name: str, unit: str) -> str:
    return re.sub(r"\s+", " ", name.upper()).strip() + " | " + unit.upper()


def public_receipt(parsed):
    return {
        key: value
        for key, value in parsed.items()
        if key not in {"access_key", "store_cnpj"}
    }


def summarize_months(receipts) -> list[dict]:
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
    return [
        {
            "month": month,
            **{k: str(v) if isinstance(v, Decimal) else v for k, v in data.items()},
        }
        for month, data in sorted(monthly.items(), reverse=True)
    ]
