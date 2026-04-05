# inventra-collector

## Kafka message contract

The collector input topic is configured through `TOPIC_COLLECTOR_IDS`.

- The Kafka message key is the authoritative collector id (`key_access`) and must be set on every input message.
- The Kafka message value is reserved for retry metadata JSON, for example `{"attempt": 1, "next_try": null}`.
- The consumer stays alive when the topic is idle and keeps polling until a new message arrives.
