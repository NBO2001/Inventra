# inventra-collector Notes

- Run formatting, lint, and tests from the `inventra-collector/` service directory so the local `.flake8` and package-relative imports are applied correctly.
- Treat the Kafka message key as the authoritative collector id. The Kafka message value is only retry metadata JSON with `attempt` and `next_try`.
- Keep orchestration testable by injecting collaborators into `collect_page_and_publish` and `process_message` instead of hardwiring HTTP clients, clocks, or publishers.
- Parser tests use the HTML fixtures in `mock-pages/` and prefer lightweight stub clients over live HTTP or Kafka dependencies.
- Host-based processes should connect to Kafka at `127.0.0.1:29092`; `kafka:9092` is reserved for other containers on the Compose network.
- `Config.load(dotenv_path)` is expected to make the provided dotenv file authoritative, so tests and local overrides should rely on it overwriting existing environment variables.
- The collector consumer should always run with an explicit Kafka `group_id`; keep `KAFKA_AUTO_OFFSET_RESET=earliest` for fresh groups when you need backlog from `collector_ids`.
