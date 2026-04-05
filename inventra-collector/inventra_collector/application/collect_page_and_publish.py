from __future__ import annotations

import logging
from datetime import datetime, timezone

from inventra_collector.infrastructure.config import Config
from inventra_collector.infrastructure.http import fetch_page, parse_items
from inventra_collector.infrastructure.rate_limit import RateLimiter


async def collect_page_and_publish(
    key_access: str,
    *,
    publisher,
    rate_limiter: RateLimiter | None = None,
    now_fn=None,
    client_factory=None,
    logger: logging.Logger | None = None,
) -> bool:
    logger = logger or logging.getLogger(__name__)
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    limiter = rate_limiter or RateLimiter(Config.RateLimit.requests_per_second)

    await limiter.acquire()
    html = await fetch_page(
        key_access,
        base_url=Config.SefazApi.url,
        client_factory=client_factory,
    )
    itens = parse_items(
        html,
        key_access=key_access,
        collection_started_at=now_fn(),
    )
    await publisher.publish(itens.to_dict(), key=key_access)
    logger.info("published parsed payload", extra={"key_access": key_access})
    return True
