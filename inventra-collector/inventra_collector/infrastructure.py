import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing."""


def _parse_dotenv(dotenv_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not dotenv_path.exists():
        return values

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def _get_required_env(
    key: str,
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> str:
    source = env if env is not None else os.environ
    value = source.get(key)
    if value:
        return value

    dotenv_values = _parse_dotenv(dotenv_path) if dotenv_path else {}
    value = dotenv_values.get(key)
    if value:
        return value

    raise ConfigError(f"Missing required environment variable: {key}")


def _get_int_env(
    key: str,
    default: int,
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> int:
    source = env if env is not None else os.environ
    value = source.get(key)
    if value is None and dotenv_path:
        value = _parse_dotenv(dotenv_path).get(key)
    return int(value or default)


def _get_float_env(
    key: str,
    default: float,
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> float:
    source = env if env is not None else os.environ
    value = source.get(key)
    if value is None and dotenv_path:
        value = _parse_dotenv(dotenv_path).get(key)
    return float(value or default)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    initial_delay_minutes: int
    backoff_multiplier: float

    def next_delay(self, next_attempt: int) -> timedelta:
        exponent = max(next_attempt - 1, 0)
        minutes = self.initial_delay_minutes * (self.backoff_multiplier**exponent)
        return timedelta(minutes=minutes)


@dataclass(frozen=True)
class RateLimitConfig:
    requests_per_second: float

    @property
    def min_interval_seconds(self) -> float:
        if self.requests_per_second <= 0:
            raise ConfigError("RATE_LIMIT_REQUESTS_PER_SECOND must be greater than 0")
        return 1 / self.requests_per_second


@dataclass(frozen=True)
class CollectorConfig:
    kafka_bootstrap_servers: str
    topic_collector_ids: str
    topic_processed_data: str
    sefaz_api_url: str
    retry_policy: RetryPolicy
    rate_limit: RateLimitConfig

    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        dotenv_path: Path | None = None,
    ) -> "CollectorConfig":
        resolved_dotenv = (
            dotenv_path
            if dotenv_path is not None
            else Path(__file__).resolve().parent.parent / ".env"
        )

        return cls(
            kafka_bootstrap_servers=_get_required_env(
                "KAFKA_BOOTSTRAP_SERVERS", env=env, dotenv_path=resolved_dotenv
            ),
            topic_collector_ids=_get_required_env(
                "TOPIC_COLLECTOR_IDS", env=env, dotenv_path=resolved_dotenv
            ),
            topic_processed_data=_get_required_env(
                "TOPIC_PROCESSED_DATA", env=env, dotenv_path=resolved_dotenv
            ),
            sefaz_api_url=_get_required_env(
                "SEFAZ_API_URL", env=env, dotenv_path=resolved_dotenv
            ),
            retry_policy=RetryPolicy(
                max_attempts=_get_int_env(
                    "RETRY_MAX_ATTEMPTS",
                    default=5,
                    env=env,
                    dotenv_path=resolved_dotenv,
                ),
                initial_delay_minutes=_get_int_env(
                    "RETRY_INITIAL_DELAY_MINUTES",
                    default=15,
                    env=env,
                    dotenv_path=resolved_dotenv,
                ),
                backoff_multiplier=_get_float_env(
                    "RETRY_BACKOFF_MULTIPLIER",
                    default=2,
                    env=env,
                    dotenv_path=resolved_dotenv,
                ),
            ),
            rate_limit=RateLimitConfig(
                requests_per_second=_get_float_env(
                    "RATE_LIMIT_REQUESTS_PER_SECOND",
                    default=10,
                    env=env,
                    dotenv_path=resolved_dotenv,
                )
            ),
        )

    def to_legacy_config(self) -> "Config":
        return Config.from_collector_config(self)


class Config:
    Kafka = SimpleNamespace()
    SefazApi = SimpleNamespace()
    Retry = SimpleNamespace()
    RateLimit = SimpleNamespace()

    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        dotenv_path: Path | None = None,
    ) -> "Config":
        return cls.from_collector_config(
            CollectorConfig.from_env(env=env, dotenv_path=dotenv_path)
        )

    @classmethod
    def from_collector_config(cls, collector_config: CollectorConfig) -> "Config":
        cls.Kafka = SimpleNamespace(
            bootstrap_servers=collector_config.kafka_bootstrap_servers,
            topic_collector_ids=collector_config.topic_collector_ids,
            topic_processed_data=collector_config.topic_processed_data,
        )
        cls.SefazApi = SimpleNamespace(url=collector_config.sefaz_api_url)
        cls.Retry = SimpleNamespace(
            max_attempts=collector_config.retry_policy.max_attempts,
            initial_delay_minutes=collector_config.retry_policy.initial_delay_minutes,
            backoff_multiplier=collector_config.retry_policy.backoff_multiplier,
        )
        cls.RateLimit = SimpleNamespace(
            requests_per_second=collector_config.rate_limit.requests_per_second
        )
        return cls


@dataclass(frozen=True)
class KafkaMessage:
    key: bytes
    value: bytes | None = None


@dataclass(frozen=True)
class RetryMetadata:
    attempt: int
    next_try: datetime | None = None

    @classmethod
    def from_message(cls, value: bytes | None) -> "RetryMetadata":
        if value in (None, b"", ""):
            return cls(1, None)

        parsed = json.loads(
            value.decode("utf-8") if isinstance(value, bytes) else value
        )
        raw_next_try = parsed.get("next_try")
        next_try = None
        if raw_next_try:
            normalized = raw_next_try.replace("Z", "+00:00")
            next_try = datetime.fromisoformat(normalized)
            if next_try.tzinfo is None:
                next_try = next_try.replace(tzinfo=UTC)

        return cls(int(parsed.get("attempt", 1)), next_try=next_try)

    def should_process(self, now: datetime) -> bool:
        if self.next_try is None:
            return True

        reference = now if now.tzinfo else now.replace(tzinfo=UTC)
        return self.next_try <= reference

    def to_message(self) -> bytes:
        payload = {
            "attempt": self.attempt,
            "next_try": (
                self.next_try.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if self.next_try is not None
                else None
            ),
        }
        return json.dumps(payload).encode("utf-8")
