import asyncio
import inspect
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlencode
from urllib.request import urlopen

from inventra_collector.domain import Item, Itens
from inventra_collector.infrastructure import CollectorConfig, Config


def _normalize_space(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def _parse_decimal(value: str) -> float:
    normalized = _normalize_space(value).replace(".", "").replace(",", ".")
    return float(normalized)


def _extract_first(pattern: str, content: str) -> str:
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Pattern not found: {pattern}")
    return _normalize_space(match.group(1))


def parse_items_page(
    *,
    page_html: str,
    key_access: str,
    collection_started_at: datetime,
) -> Itens | None:
    lowered = page_html.lower()
    if "nota n" in lowered and "encontrada" in lowered:
        return None

    timestamp = collection_started_at.astimezone(UTC).isoformat()
    if timestamp.endswith("+00:00"):
        timestamp = timestamp.split("+")[0]

    item_rows = re.findall(r'<tr id="Item \+ .*?</tr>', page_html, re.DOTALL)
    if not item_rows:
        return None

    document_hash = f"{key_access}:{timestamp}"
    itens: list[Item] = []
    for raw_row in item_rows:
        description = _extract_first(r'class="txtTit">(.*?)</span>', raw_row).lower()
        quantity = _parse_decimal(
            _extract_first(
                r'class="Rqtd"><strong>Qtde\.\:</strong>(.*?)</span>', raw_row
            )
        )
        unit = _extract_first(
            r'class="RUN"><strong>UN: </strong>(.*?)</span>', raw_row
        ).lower()
        value_unit = _parse_decimal(
            _extract_first(
                r'class="RvlUnit"><strong>Vl\. Unit\.\:</strong>\s*&nbsp;\s*(.*?)</span>',
                raw_row,
            )
        )
        value_total = _parse_decimal(
            _extract_first(r'<span class="valor">(.*?)</span>', raw_row)
        )

        itens.append(
            Item(
                description=description,
                value_unit=value_unit,
                quantity=quantity,
                value_total=value_total,
                unit=unit,
                key_access=key_access,
                hash=document_hash,
            )
        )

    return Itens(itens=itens, collection_started_at=timestamp)


async def fetch_page_html(
    *,
    key_access: str,
    sefaz_api_url: str,
    fetcher=None,
) -> str:
    if fetcher is not None:
        result = fetcher(key_access=key_access, sefaz_api_url=sefaz_api_url)
        return await result if inspect.isawaitable(result) else result

    def _fetch() -> str:
        with urlopen(
            f"{sefaz_api_url}?{urlencode({'p': key_access})}", timeout=30
        ) as response:
            return response.read().decode("utf-8")

    return await asyncio.to_thread(_fetch)


async def collect_page_and_publish(
    *,
    key_access: str,
    config: CollectorConfig | None = None,
    publisher=None,
    fetcher=None,
    now: datetime | None = None,
    rate_limiter=None,
) -> bool:
    active_config = config or CollectorConfig.from_env()
    Config.from_collector_config(active_config)

    if rate_limiter is not None:
        await rate_limiter.acquire()

    collection_started_at = now or datetime.now(UTC)
    page_html = await fetch_page_html(
        key_access=key_access,
        sefaz_api_url=active_config.sefaz_api_url,
        fetcher=fetcher,
    )
    parsed = parse_items_page(
        page_html=page_html,
        key_access=key_access,
        collection_started_at=collection_started_at,
    )
    if parsed is None:
        return False

    if publisher is not None:
        await publisher.publish(
            active_config.topic_processed_data,
            key_access.encode("utf-8"),
            json.dumps(asdict(parsed)).encode("utf-8"),
        )

    return True
