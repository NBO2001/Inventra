# inventra-collector

## Kafka message contract

When running the collector on the host alongside this repo's `docker-compose.yml`, use `KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:29092`. The `kafka:9092` listener is only resolvable from other containers on the Compose network.

The consumer uses the `KAFKA_CONSUMER_GROUP_ID` group and defaults `KAFKA_AUTO_OFFSET_RESET=earliest`, so a fresh group will consume backlog that already exists in `TOPIC_COLLECTOR_IDS`.

The collector input topic is configured through `TOPIC_COLLECTOR_IDS`.

- The Kafka message key is the authoritative collector id (`key_access`) and must be set on every input message.
- The Kafka message value is reserved for retry metadata JSON, for example `{"attempt": 1, "next_try": null}`.
- The consumer stays alive when the topic is idle and keeps polling until a new message arrives.
