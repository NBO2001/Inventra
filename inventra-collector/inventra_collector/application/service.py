import asyncio
import logging
from datetime import UTC, datetime
from time import monotonic as time_monotonic

from inventra_collector.application.collect_page_and_publish import (
    collect_page_and_publish,
)
from inventra_collector.infrastructure import (
    CollectorConfig,
    KafkaMessage,
    RetryMetadata,
)

LOGGER = logging.getLogger(__name__)


class AsyncRateLimiter:
    def __init__(
        self,
        requests_per_second: float,
        sleep=asyncio.sleep,
        monotonic=None,
    ) -> None:
        self._min_interval = 1 / requests_per_second
        self._sleep = sleep
        self._monotonic = monotonic if monotonic is not None else time_monotonic
        self._next_slot = 0.0

    async def acquire(self) -> None:
        now = self._monotonic()
        if now < self._next_slot:
            await self._sleep(self._next_slot - now)
            now = self._monotonic()
        self._next_slot = now + self._min_interval


class CollectorService:
    def __init__(
        self,
        config: CollectorConfig,
        publisher,
        fetcher=None,
        rate_limiter=None,
        now_provider=None,
        logger=None,
    ) -> None:
        self._config = config
        self._publisher = publisher
        self._fetcher = fetcher
        self._rate_limiter = rate_limiter or AsyncRateLimiter(
            config.rate_limit.requests_per_second
        )
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._logger = logger or LOGGER

    async def consume_messages(self, consumer) -> None:
        await consumer.subscribe(self._config.topic_collector_ids)
        self._logger.info(
            "Collector subscribed to topic=%s", self._config.topic_collector_ids
        )
        async for message in consumer:
            await self.process_message(message)

    async def process_message(self, message: KafkaMessage) -> bool:
        key_access = message.key.decode("utf-8")
        retry_metadata = RetryMetadata.from_message(message.value)
        now = self._now_provider()

        self._logger.info(
            "Received message for key_access=%s attempt=%s",
            key_access,
            retry_metadata.attempt,
        )

        if not retry_metadata.should_process(now):
            self._logger.info(
                "Deferred retry for key_access=%s attempt=%s next_try=%s",
                key_access,
                retry_metadata.attempt,
                retry_metadata.next_try,
            )
            return False

        try:
            processed = await collect_page_and_publish(
                key_access=key_access,
                config=self._config,
                publisher=self._publisher,
                fetcher=self._fetcher,
                now=now,
                rate_limiter=self._rate_limiter,
            )
        except Exception:
            self._logger.exception(
                "Processing failed for key_access=%s attempt=%s",
                key_access,
                retry_metadata.attempt,
            )
            await self._handle_failure(key_access, retry_metadata)
            return False

        if processed:
            self._logger.info(
                "Published processed payload for key_access=%s attempt=%s",
                key_access,
                retry_metadata.attempt,
            )
            return True

        self._logger.warning(
            "Collector returned no parsed payload for key_access=%s attempt=%s",
            key_access,
            retry_metadata.attempt,
        )
        await self._handle_failure(key_access, retry_metadata)
        return False

    async def _handle_failure(
        self,
        key_access: str,
        retry_metadata: RetryMetadata,
        next_attempt: int | None = None,
        next_try: datetime | None = None,
    ) -> None:
        next_attempt = next_attempt or retry_metadata.attempt + 1
        if next_attempt > self._config.retry_policy.max_attempts:
            self._logger.error(
                "Retry limit exhausted for key_access=%s at attempt=%s",
                key_access,
                retry_metadata.attempt,
            )
            return

        next_try = next_try or (
            self._now_provider() + self._config.retry_policy.next_delay(next_attempt)
        )
        scheduled_retry = RetryMetadata(attempt=next_attempt, next_try=next_try)
        await self._publisher.publish(
            self._config.topic_collector_ids,
            key_access.encode("utf-8"),
            scheduled_retry.to_message(),
        )
        self._logger.info(
            "Republished retry for key_access=%s attempt=%s next_try=%s",
            key_access,
            next_attempt,
            next_try,
        )
