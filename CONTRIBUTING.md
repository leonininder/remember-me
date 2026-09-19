# Contributing

Thanks for interest in **remember-me** (`remember_me` Python package).

## Principles

1. **Jev ≠ store ≠ similarity ranker.** Local retrieval first; Jev only gates hydrate/admit.
2. **Fail-closed** on Jev timeout / deny / malformed. Never fail-open into cloud influence.
3. **Redact outbound state.** Bodies, secrets, and PII must never appear in Jev payloads.
4. **FakeJev for CI.** `HttpJev` is optional and requires `TYPESAFE_API_KEY`.
5. **Synthetic fixtures only.** No customer data in `fixtures/`.

## Dev setup

```bash
python -m pip install -e ".[dev]"
make test
make lint
remember-me demo
```

## Tests

- Unit: schema, redact, TTL, policy thresholds, fail-closed
- Integration: FakeJev end-to-end hydrate path (assert Jev is called)
- Negative: secrets never in outbound; orphan hydrations forbidden
- Bake-off: 50 queries offline → metrics JSON

## Pull requests

- Keep PRs small; conventional commits preferred
- Add/adjust tests with behavior changes
- Do not commit real API keys or PII
