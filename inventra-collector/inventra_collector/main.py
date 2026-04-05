import asyncio
import logging

from inventra_collector.application.service import CollectorService
from inventra_collector.infrastructure import CollectorConfig


async def main() -> CollectorService:
    logging.basicConfig(level=logging.INFO)
    config = CollectorConfig.from_env()
    service = CollectorService(config=config, publisher=None)
    logging.getLogger(__name__).info(
        "Collector configuration loaded for topic=%s",
        config.topic_collector_ids,
    )
    return service


if __name__ == "__main__":
    asyncio.run(main())
