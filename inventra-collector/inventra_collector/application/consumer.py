from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from inventra_collector.application.collect_page_and_publish import (
    collect_page_and_publish,
)
from inventra_collector.infrastructure.config import Config


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_retry_metadata(raw_value: bytes | str | None) -> dict:
    if raw_value in (None, b"", ""):
        return {"attempt": 1, "next_try": None}

    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")

    payload = json.loads(raw_value)
    return {
        "attempt": int(payload.get("attempt", 1)),
        "next_try": payload.get("next_try"),
    }


def compute_retry_delay_minutes(
    next_attempt: int,
    *,
    initial_delay_minutes: int,
) -> int:
    delay = initial_delay_minutes
    for _ in range(2, next_attempt):
        delay = delay**2
    return delay


def schedule_retry_metadata(
    *,
    current_attempt: int,
    now: datetime,
) -> dict:
    next_attempt = current_attempt + 1
    delay_minutes = compute_retry_delay_minutes(
        next_attempt,
        initial_delay_minutes=Config.Retry.initial_delay_minutes,
    )
    next_try = now + timedelta(minutes=delay_minutes)
    return {"attempt": next_attempt, "next_try": next_try.isoformat()}


async def process_message(
    message,
    *,
    publisher,
    retry_publisher,
    logger: logging.Logger | None = None,
    now_fn=None,
    collector=collect_page_and_publish,
) -> str:
    logger = logger or logging.getLogger(__name__)
    now_fn = now_fn or _utc_now

    key_access = (
        message.key.decode("utf-8") if isinstance(message.key, bytes) else message.key
    )
    metadata = parse_retry_metadata(getattr(message, "value", None))
    attempt = metadata["attempt"]
    next_try_raw = metadata["next_try"]

    logger.info(
        "received collector message",
        extra={"key_access": key_access, "attempt": attempt},
    )

    if next_try_raw:
        next_try = datetime.fromisoformat(next_try_raw)
        if now_fn() < next_try:
            logger.info(
                "retry deferred",
                extra={
                    "key_access": key_access,
                    "attempt": attempt,
                    "next_try": next_try_raw,
                },
            )
            return "deferred"

    try:
        published = await collector(
            key_access,
            publisher=publisher,
            now_fn=now_fn,
            logger=logger,
        )
        if published:
            logger.info(
                "collector message processed successfully",
                extra={
                    "key_access": key_access,
                    "attempt": attempt,
                },
            )
            return "processed"
    except Exception:
        logger.exception(
            "collector processing failed",
            extra={"key_access": key_access, "attempt": attempt},
        )

    if attempt >= Config.Retry.max_attempts:
        logger.error(
            "retry attempts exhausted",
            extra={"key_access": key_access, "attempt": attempt},
        )
        return "exhausted"

    retry_metadata = schedule_retry_metadata(
        current_attempt=attempt,
        now=now_fn(),
    )
    await retry_publisher.publish(retry_metadata, key=key_access)
    logger.info(
        "retry republished",
        extra={
            "key_access": key_access,
            "attempt": retry_metadata["attempt"],
            "next_try": retry_metadata["next_try"],
        },
    )
    return "retried"


async def run_consumer(
    *,
    consumer,
    processor,
    stop_after_messages: int | None = None,
    poll_interval_seconds: float = 1.0,
    logger: logging.Logger | None = None,
) -> int:
    logger = logger or logging.getLogger(__name__)
    handled_count = 0

    consumer.subscribe([Config.Kafka.topic_collector_ids])
    logger.info(
        "collector consumer subscribed",
        extra={"topic": Config.Kafka.topic_collector_ids},
    )

    while True:
        message = await consumer.getone()
        if message is None:
            await asyncio.sleep(poll_interval_seconds)
            if stop_after_messages is not None and handled_count >= stop_after_messages:
                break
            continue

        key_access = (
            message.key.decode("utf-8")
            if isinstance(message.key, bytes)
            else message.key
        )
        await processor(key_access, message)
        handled_count += 1

        if stop_after_messages is not None and handled_count >= stop_after_messages:
            break

    return handled_count
