# inventra-collector Notes

- Run formatting, lint, and tests from `/workspace/inventra-collector` so the local `.flake8` and package-relative imports are applied correctly.
- Treat the Kafka message key as the authoritative collector id. The Kafka message value is only retry metadata JSON with `attempt` and `next_try`.
- Keep orchestration testable by injecting collaborators into `collect_page_and_publish` and `process_message` instead of hardwiring HTTP clients, clocks, or publishers.
- Parser tests use the HTML fixtures in `mock-pages/` and prefer lightweight stub clients over live HTTP or Kafka dependencies.
