import json
import math
from asyncio import run
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from inventra_collector.application.collect_page_and_publish import (
    collect_page_and_publish,
    parse_items_page,
)
from inventra_collector.domain import Item
from inventra_collector.infrastructure import (
    CollectorConfig,
    RateLimitConfig,
    RetryPolicy,
)


def _build_config() -> CollectorConfig:
    return CollectorConfig(
        kafka_bootstrap_servers="localhost:9092",
        topic_collector_ids="collector-ids",
        topic_processed_data="processed-data",
        sefaz_api_url="https://www.example.com/example-endpoint",
        retry_policy=RetryPolicy(
            max_attempts=5,
            initial_delay_minutes=15,
            backoff_multiplier=2,
        ),
        rate_limit=RateLimitConfig(requests_per_second=10),
    )


def _read_mock_page(name: str) -> str:
    return Path(f"mock-pages/{name}").read_text(encoding="utf-8")


def test_parse_items_page_with_valid_page_should_return_items():
    result = parse_items_page(
        page_html=_read_mock_page("page-mock.html"),
        key_access="00000000000000000000000000000000000000000000",
        collection_started_at=datetime(2023, 9, 1, 12, 0, 0, tzinfo=UTC),
    )

    assert result is not None
    assert len(result.itens) == 7
    assert (
        Item(
            description="ling tipo calab perdigao kg",
            value_unit=47.48,
            quantity=1,
            value_total=47.48,
            unit="kg",
            key_access="00000000000000000000000000000000000000000000",
            hash="00000000000000000000000000000000000000000000:2023-09-01T12:00:00",
        )
        in result.itens
    )
    assert math.isclose(
        sum(item.value_total for item in result.itens), 113.52, rel_tol=1e-2
    )
    assert all(
        item.hash == "00000000000000000000000000000000000000000000:2023-09-01T12:00:00"
        for item in result.itens
    )


def test_parse_items_page_with_invalid_page_should_return_none():
    result = parse_items_page(
        page_html=_read_mock_page("page-mock-invalid.html"),
        key_access="0000000000000000000",
        collection_started_at=datetime(2023, 9, 1, 12, 0, 0, tzinfo=UTC),
    )

    assert result is None


def test_collect_page_and_publish_with_valid_page_should_publish_json_payload():
    publisher = AsyncMock()
    fetcher = AsyncMock(return_value=_read_mock_page("page-mock.html"))

    result = run(
        collect_page_and_publish(
            key_access="00000000000000000000000000000000000000000000",
            config=_build_config(),
            publisher=publisher,
            fetcher=fetcher,
            now=datetime(2023, 9, 1, 12, 0, 0, tzinfo=UTC),
        )
    )

    assert result is True
    publisher.publish.assert_awaited_once()
    topic, key, value = publisher.publish.await_args.args
    assert topic == "processed-data"
    assert key == b"00000000000000000000000000000000000000000000"
    payload = json.loads(value.decode("utf-8"))
    assert payload["collection_started_at"] == "2023-09-01T12:00:00"
    assert len(payload["itens"]) == 7


def test_collect_page_and_publish_with_invalid_page_should_not_publish():
    publisher = AsyncMock()
    fetcher = AsyncMock(return_value=_read_mock_page("page-mock-invalid.html"))

    result = run(
        collect_page_and_publish(
            key_access="0000000000000000000",
            config=_build_config(),
            publisher=publisher,
            fetcher=fetcher,
            now=datetime(2023, 9, 1, 12, 0, 0, tzinfo=UTC),
        )
    )

    assert result is False
    publisher.publish.assert_not_awaited()
