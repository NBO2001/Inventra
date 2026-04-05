from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._interval = 1.0 / requests_per_second
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            wait_for = self._next_allowed_at - now
            if wait_for > 0:
                await self._sleep(wait_for)
                now = self._clock()
            self._next_allowed_at = max(self._next_allowed_at, now) + self._interval
