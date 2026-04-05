import asyncio

from aiokafka.structs import ConsumerRecord
from inventra_collector.application.consumer import run_consumer
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


def make_message(key: bytes | str) -> ConsumerRecord:
    if isinstance(key, str):
        key = key.encode()

    return ConsumerRecord(
        topic="collector_ids",
        partition=0,
        offset=0,
        timestamp=0,
        timestamp_type=0,
        key=key,
        value=b'{"next_try": null, "attempt": 1}',
        checksum=None,
        serialized_key_size=len(key),
        serialized_value_size=0,
        headers=[],
    )


def test_run_consumer_subscribes_to_topic_and_uses_message_key_for_processing():
    Config.Kafka.topic_collector_ids = "collector_ids"
    consumer = FakeConsumer(
        [make_message(b"00000000000000000000000000000000000000000000")]
    )
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
    assert processed == [
        (
            "00000000000000000000000000000000000000000000",
            b"00000000000000000000000000000000000000000000",
        )
    ]
