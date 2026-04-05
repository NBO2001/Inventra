from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


class Config:
    class Kafka:
        bootstrap_servers = ""
        topic_collector_ids = ""
        topic_processed_data = ""
        consumer_group_id = "inventra-collector"
        auto_offset_reset = "earliest"

    class SefazApi:
        url = ""

    class Retry:
        max_attempts = 5
        initial_delay_minutes = 15
        backoff_multiplier = 2

    class RateLimit:
        requests_per_second = 10.0

    @classmethod
    def load(cls, dotenv_path: str | Path | None = None) -> "Config":
        base_path = Path(dotenv_path) if dotenv_path else Path(".env")
        _load_dotenv(base_path)

        cls.Kafka.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
        cls.Kafka.topic_collector_ids = os.getenv("TOPIC_COLLECTOR_IDS", "")
        cls.Kafka.topic_processed_data = os.getenv("TOPIC_PROCESSED_DATA", "")
        cls.Kafka.consumer_group_id = os.getenv(
            "KAFKA_CONSUMER_GROUP_ID", "inventra-collector"
        )
        cls.Kafka.auto_offset_reset = os.getenv(
            "KAFKA_AUTO_OFFSET_RESET", "earliest"
        )
        cls.SefazApi.url = os.getenv("SEFAZ_API_URL", "")
        cls.Retry.max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS", "5"))
        cls.Retry.initial_delay_minutes = int(
            os.getenv("RETRY_INITIAL_DELAY_MINUTES", "15")
        )
        cls.Retry.backoff_multiplier = int(os.getenv("RETRY_BACKOFF_MULTIPLIER", "2"))
        cls.RateLimit.requests_per_second = float(
            os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND", "10")
        )
        return cls

    @classmethod
    def validate(cls) -> None:
        missing = []
        required = {
            "KAFKA_BOOTSTRAP_SERVERS": cls.Kafka.bootstrap_servers,
            "TOPIC_COLLECTOR_IDS": cls.Kafka.topic_collector_ids,
            "TOPIC_PROCESSED_DATA": cls.Kafka.topic_processed_data,
            "SEFAZ_API_URL": cls.SefazApi.url,
        }
        for key, value in required.items():
            if not value:
                missing.append(key)

        if missing:
            raise ValueError(
                "Missing required configuration: " + ", ".join(sorted(missing))
            )

        if cls.Retry.max_attempts < 1:
            raise ValueError("RETRY_MAX_ATTEMPTS must be greater than zero")
        if cls.Retry.initial_delay_minutes < 1:
            raise ValueError("RETRY_INITIAL_DELAY_MINUTES must be greater than zero")
        if cls.RateLimit.requests_per_second <= 0:
            raise ValueError("RATE_LIMIT_REQUESTS_PER_SECOND must be greater than zero")
        if not cls.Kafka.consumer_group_id:
            raise ValueError("KAFKA_CONSUMER_GROUP_ID must not be empty")
        if cls.Kafka.auto_offset_reset not in {"earliest", "latest", "none"}:
            raise ValueError(
                "KAFKA_AUTO_OFFSET_RESET must be one of: earliest, latest, none"
            )
