from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from typing import Any, Callable

from inventra_collector.domain.item import Item, Itens


def _collapse_spaces(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def _parse_decimal(value: str) -> float:
    normalized = value.replace(".", "").replace(",", ".").strip()
    return float(normalized)


def _extract(pattern: str, content: str) -> str | None:
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return _collapse_spaces(match.group(1))


def parse_items(
    html: str,
    *,
    key_access: str,
    collection_started_at: datetime,
) -> Itens:
    row_pattern = re.compile(
        r"<tr id=\"Item \+ \d+\">(.*?)</tr>",
        re.DOTALL | re.IGNORECASE,
    )
    items = []
    document_hash = f"{key_access}:{collection_started_at.isoformat()}"
    for row in row_pattern.findall(html):
        description = _extract(r'<span class="txtTit">(.*?)</span>', row)
        quantity = _extract(
            r'<span class="Rqtd"><strong>Qtde\.:<\/strong>(.*?)</span>', row
        )
        unit = _extract(
            r'<span class="RUN"><strong>UN: <\/strong>(.*?)</span>',
            row,
        )
        value_unit = _extract(
            (
                r'<span class="RvlUnit"><strong>Vl\. Unit\.:<\/strong>'
                r"\s*&nbsp;\s*(.*?)</span>"
            ),
            row,
        )
        value_total = _extract(r'<span class="valor">(.*?)</span>', row)
        if not all([description, quantity, unit, value_unit, value_total]):
            continue

        items.append(
            Item(
                description=description.lower(),
                value_unit=_parse_decimal(value_unit),
                quantity=_parse_decimal(quantity),
                value_total=_parse_decimal(value_total),
                unit=unit.lower(),
                key_access=key_access,
                hash=document_hash,
            )
        )

    if not items:
        raise ValueError("No items found in collected page")

    return Itens(itens=items)


async def fetch_page(
    key_access: str,
    *,
    base_url: str,
    client_factory: Callable[[], Any] | None = None,
) -> str:
    if client_factory is None:
        import httpx

        factory = httpx.AsyncClient
    else:
        factory = client_factory

    async with factory() as client:
        response = await client.get(f"{base_url}?p={key_access}")
        response.raise_for_status()
        return response.text
