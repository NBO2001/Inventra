import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from inventra_collector.application.consumer import (
    compute_retry_delay_minutes,
    process_message,
    run_consumer,
)
from inventra_collector.infrastructure.config import Config


class FakeConsumer:
    def __init__(self, messages):
        self.messages = list(messages)
        self.subscriptions = []
        self.poll_calls = 0

    def subscribe(self, topics):
        self.subscriptions.append(topics)

    async def getone(self, *partitions):
        self.poll_calls += 1
        await asyncio.sleep(0)
        if self.messages:
            return self.messages.pop(0)
        return None


class FakePublisher:
    def __init__(self):
        self.calls = []

    async def publish(self, payload, *, key=None):
        self.calls.append((payload, key))


@dataclass
class ConsumerRecord:
    topic: str
    partition: int
    offset: int
    timestamp: int
    timestamp_type: int
    key: bytes
    value: bytes | None
    checksum: None
    serialized_key_size: int
    serialized_value_size: int
    headers: list


def make_message(key: bytes | str, value: bytes | None = None) -> ConsumerRecord:
    default_value = b'{"next_try": null, "attempt": 1}'

    if isinstance(key, str):
        key = key.encode()

    return ConsumerRecord(
        topic="collector_ids",
        partition=0,
        offset=0,
        timestamp=0,
        timestamp_type=0,
        key=key,
        value=value if value is not None else default_value,
        checksum=None,
        serialized_key_size=len(key),
        serialized_value_size=0,
        headers=[],
    )


def test_run_consumer_subscribes_to_topic_and_uses_message_key_for_processing():
    Config.Kafka.topic_collector_ids = "collector_ids"
    consumer = FakeConsumer([make_message(b"0" * 44)])
    processed = []

    async def processor(key_access, message):
        processed.append((key_access, message.key))

    handled_count = asyncio.run(
        run_consumer(
            consumer=consumer,
            processor=processor,
            stop_after_messages=1,
            poll_interval_seconds=0.01,
        )
    )

    assert consumer.subscriptions == [["collector_ids"]]
    assert handled_count == 1
    assert processed == [("0" * 44, b"0" * 44)]


def test_compute_retry_delay_minutes_uses_initial_delay_then_square_growth():
    assert compute_retry_delay_minutes(2, initial_delay_minutes=15) == 15
    assert compute_retry_delay_minutes(3, initial_delay_minutes=15) == 225
    assert compute_retry_delay_minutes(4, initial_delay_minutes=15) == 50625


def test_process_message_defers_retry_until_next_try(caplog):
    now = datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc)
    message = make_message(
        "abc",
        b'{"attempt": 2, "next_try": "2026-04-04T12:15:00+00:00"}',
    )
    publisher = FakePublisher()
    retry_publisher = FakePublisher()

    with caplog.at_level(logging.INFO):
        result = asyncio.run(
            process_message(
                message,
                publisher=publisher,
                retry_publisher=retry_publisher,
                now_fn=lambda: now,
                collector=None,
            )
        )

    assert result == "deferred"
    assert publisher.calls == []
    assert retry_publisher.calls == []
    assert "retry deferred" in caplog.text


def test_process_message_republishes_failed_messages_with_retry_metadata():
    Config.Retry.max_attempts = 5
    Config.Retry.initial_delay_minutes = 15
    now = datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc)
    message = make_message("abc", b'{"attempt": 1, "next_try": null}')
    publisher = FakePublisher()
    retry_publisher = FakePublisher()

    async def failing_collector(*args, **kwargs):
        raise RuntimeError("boom")

    result = asyncio.run(
        process_message(
            message,
            publisher=publisher,
            retry_publisher=retry_publisher,
            now_fn=lambda: now,
            collector=failing_collector,
        )
    )

    assert result == "retried"
    assert publisher.calls == []
    assert retry_publisher.calls == [
        ({"attempt": 2, "next_try": "2026-04-04T12:15:00+00:00"}, "abc")
    ]


def test_process_message_stops_after_max_attempts(caplog):
    Config.Retry.max_attempts = 5
    now = datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc)
    message = make_message("abc", b'{"attempt": 5, "next_try": null}')
    publisher = FakePublisher()
    retry_publisher = FakePublisher()

    async def failing_collector(*args, **kwargs):
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(
            process_message(
                message,
                publisher=publisher,
                retry_publisher=retry_publisher,
                now_fn=lambda: now,
                collector=failing_collector,
            )
        )

    assert result == "exhausted"
    assert retry_publisher.calls == []
    assert "retry attempts exhausted" in caplog.text
