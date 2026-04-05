from __future__ import annotations

import asyncio
import logging

from inventra_collector.application.consumer import process_message, run_consumer
from inventra_collector.infrastructure.config import Config
from inventra_collector.infrastructure.kafka import KafkaPublisher

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except ImportError:  # pragma: no cover
    AIOKafkaConsumer = None
    AIOKafkaProducer = None


async def _main_async() -> None:
    Config.load()
    Config.validate()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    if AIOKafkaConsumer is None or AIOKafkaProducer is None:
        raise RuntimeError("aiokafka must be installed to run the collector")

    consumer = AIOKafkaConsumer(
        bootstrap_servers=Config.Kafka.bootstrap_servers,
        key_deserializer=lambda value: value,
        value_deserializer=lambda value: value,
    )
    producer = AIOKafkaProducer(bootstrap_servers=Config.Kafka.bootstrap_servers)
    output_publisher = KafkaPublisher(
        producer,
        Config.Kafka.topic_processed_data,
    )
    retry_publisher = KafkaPublisher(
        producer,
        Config.Kafka.topic_collector_ids,
    )

    await producer.start()
    await consumer.start()
    logger.info("collector startup complete")

    try:
        await run_consumer(
            consumer=consumer,
            processor=lambda _key_access, message: process_message(
                message,
                publisher=output_publisher,
                retry_publisher=retry_publisher,
                logger=logger,
            ),
            logger=logger,
        )
    finally:
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
