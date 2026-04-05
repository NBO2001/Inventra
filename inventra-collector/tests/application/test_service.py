import json
from asyncio import run
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

from inventra_collector.application.service import AsyncRateLimiter, CollectorService
from inventra_collector.infrastructure import (
    CollectorConfig,
    KafkaMessage,
    RateLimitConfig,
    RetryMetadata,
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


def test_process_message_defers_retry_until_next_try():
    publisher = AsyncMock()
    logger = Mock()
    now = datetime(2026, 4, 4, 17, 0, 0, tzinfo=UTC)

    service = CollectorService(
        config=_build_config(),
        publisher=publisher,
        fetcher=AsyncMock(),
        rate_limiter=AsyncMock(),
        now_provider=lambda: now,
        logger=logger,
    )

    deferred = RetryMetadata(attempt=2, next_try=now + timedelta(minutes=1))
    message = KafkaMessage(
        key=b"abc",
        value=deferred.to_message(),
    )

    result = run(service.process_message(message))

    assert result is False
    publisher.publish.assert_not_awaited()
    logger.info.assert_any_call(
        "Deferred retry for key_access=%s attempt=%s next_try=%s",
        "abc",
        2,
        deferred.next_try,
    )


def test_process_message_republishes_failed_message_with_retry_metadata():
    publisher = AsyncMock()
    now = datetime(2026, 4, 4, 17, 0, 0, tzinfo=UTC)
    logger = Mock()

    service = CollectorService(
        config=_build_config(),
        publisher=publisher,
        fetcher=AsyncMock(return_value="<html>Nota não encontrada</html>"),
        rate_limiter=AsyncMock(),
        now_provider=lambda: now,
        logger=logger,
    )

    result = run(service.process_message(KafkaMessage(key=b"abc", value=None)))

    assert result is False
    publisher.publish.assert_awaited_once()
    topic, key, value = publisher.publish.await_args.args
    payload = json.loads(value.decode("utf-8"))
    assert topic == "collector-ids"
    assert key == b"abc"
    assert payload["attempt"] == 2
    assert payload["next_try"] == "2026-04-04T17:30:00Z"
    logger.info.assert_any_call(
        "Republished retry for key_access=%s attempt=%s next_try=%s",
        "abc",
        2,
        now + timedelta(minutes=30),
    )


def test_process_message_stops_retrying_after_max_attempts():
    publisher = AsyncMock()
    logger = Mock()
    now = datetime(2026, 4, 4, 17, 0, 0, tzinfo=UTC)

    service = CollectorService(
        config=_build_config(),
        publisher=publisher,
        fetcher=AsyncMock(return_value="<html>Nota não encontrada</html>"),
        rate_limiter=AsyncMock(),
        now_provider=lambda: now,
        logger=logger,
    )

    retry_metadata = RetryMetadata(attempt=5, next_try=None)
    result = run(
        service.process_message(
            KafkaMessage(key=b"abc", value=retry_metadata.to_message())
        )
    )

    assert result is False
    publisher.publish.assert_not_awaited()
    logger.error.assert_called_once_with(
        "Retry limit exhausted for key_access=%s at attempt=%s",
        "abc",
        5,
    )


def test_async_rate_limiter_waits_for_next_slot():
    slept = []
    times = iter([0.0, 0.0, 0.05, 0.1])

    async def fake_sleep(delay):
        slept.append(delay)

    limiter = AsyncRateLimiter(
        requests_per_second=10,
        sleep=fake_sleep,
        monotonic=lambda: next(times),
    )

    run(limiter.acquire())
    run(limiter.acquire())

    assert slept == [0.1]
