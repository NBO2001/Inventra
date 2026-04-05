import asyncio
from datetime import datetime, timezone
from pathlib import Path

from inventra_collector.application.collect_page_and_publish import (
    collect_page_and_publish,
)
from inventra_collector.infrastructure.config import Config


class StubLimiter:
    def __init__(self) -> None:
        self.calls = 0

    async def acquire(self) -> None:
        self.calls += 1


class StubPublisher:
    def __init__(self) -> None:
        self.payloads = []

    async def publish(self, payload, *, key=None) -> None:
        self.payloads.append((payload, key))


class StubResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class StubClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.requested_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str) -> StubResponse:
        self.requested_urls.append(url)
        return StubResponse(self._text)


def fixture_path(name: str) -> Path:
    return Path("/workspace/inventra-collector/mock-pages") / name


def test_collect_page_html_and_publish_to_items_with_valid_page_should_return_items():
    Config.SefazApi.url = "https://www.example.com/example-endpoint"
    publisher = StubPublisher()
    limiter = StubLimiter()
    page_html = fixture_path("page-mock.html").read_text()
    client = StubClient(page_html)
    collected_at = datetime(2026, 2, 3, 18, 56, 21, tzinfo=timezone.utc)
    expected_hash = (
        "00000000000000000000000000000000000000000000" f":{collected_at.isoformat()}"
    )

    result = asyncio.run(
        collect_page_and_publish(
            key_access="00000000000000000000000000000000000000000000",
            publisher=publisher,
            rate_limiter=limiter,
            now_fn=lambda: collected_at,
            client_factory=lambda: client,
        )
    )

    assert result is True
    assert limiter.calls == 1
    assert client.requested_urls == [
        (
            "https://www.example.com/example-endpoint"
            "?p=00000000000000000000000000000000000000000000"
        )
    ]
    assert len(publisher.payloads) == 1

    published_data, key = publisher.payloads[0]
    assert key == "00000000000000000000000000000000000000000000"
    assert len(published_data["itens"]) == 7
    assert {
        "description": "ling tipo calab perdigao kg",
        "value_unit": 47.48,
        "quantity": 1.0,
        "value_total": 47.48,
        "unit": "kg",
        "key_access": "00000000000000000000000000000000000000000000",
        "hash": expected_hash,
    } in published_data["itens"]
    assert {item["hash"] for item in published_data["itens"]} == {expected_hash}


def test_collect_page_html_and_publish_to_items_with_invalid_page_should_not_publish():
    Config.SefazApi.url = "https://www.example.com/example-endpoint"
    publisher = StubPublisher()
    limiter = StubLimiter()
    page_html = fixture_path("page-mock-invalid.html").read_text()

    import pytest

    with pytest.raises(ValueError):
        asyncio.run(
            collect_page_and_publish(
                key_access="0000000000000000000",
                publisher=publisher,
                rate_limiter=limiter,
                client_factory=lambda: StubClient(page_html),
            )
        )

    assert limiter.calls == 1
    assert publisher.payloads == []
