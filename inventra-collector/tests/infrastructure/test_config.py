from pathlib import Path

import pytest

from inventra_collector.infrastructure.config import Config


def test_config_loads_required_values_from_dotenv(tmp_path: Path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "KAFKA_BOOTSTRAP_SERVERS=localhost:9092",
                "TOPIC_COLLECTOR_IDS=collector_ids",
                "TOPIC_PROCESSED_DATA=processed_items",
                "SEFAZ_API_URL=https://example.com/consulta",
                "RATE_LIMIT_REQUESTS_PER_SECOND=10",
            ]
        )
    )

    Config.load(dotenv_path)

    assert Config.Kafka.bootstrap_servers == "localhost:9092"
    assert Config.Kafka.topic_collector_ids == "collector_ids"
    assert Config.Kafka.topic_processed_data == "processed_items"
    assert Config.SefazApi.url == "https://example.com/consulta"
    assert Config.RateLimit.requests_per_second == 10.0


def test_config_validate_fails_when_required_values_missing():
    Config.Kafka.bootstrap_servers = ""
    Config.Kafka.topic_collector_ids = ""
    Config.Kafka.topic_processed_data = ""
    Config.SefazApi.url = ""

    with pytest.raises(ValueError):
        Config.validate()
