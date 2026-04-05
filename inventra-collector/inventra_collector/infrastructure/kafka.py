from __future__ import annotations

import json
from typing import Any


class KafkaPublisher:
    def __init__(self, producer: Any, topic: str) -> None:
        self._producer = producer
        self._topic = topic

    async def publish(self, payload: Any, *, key: str | None = None) -> None:
        value = payload
        if not isinstance(payload, (bytes, bytearray)):
            value = json.dumps(payload).encode("utf-8")

        key_bytes = key.encode("utf-8") if key is not None else None
        await self._producer.send_and_wait(
            self._topic,
            value=value,
            key=key_bytes,
        )
