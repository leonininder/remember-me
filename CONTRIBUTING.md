# Contributing

Thanks for interest in **remember-me** (`remember_me` Python package).

## Principles

1. **Jev ≠ store ≠ similarity ranker.** Local retrieval first; Jev only gates hydrate/admit.
2. **Fail-closed** on Jev timeout / deny / malformed. Never fail-open into cloud influence.
3. **Redact outbound state.** Bodies, secrets, and PII must never appear in Jev payloads.
4. **Offline CI.** FakeJev and real localhost HTTP contract tests require no live API key. A hosted TypeSafe call separately requires `TYPESAFE_API_KEY`.
5. **Synthetic fixtures only.** No customer data in `fixtures/`.

## Dev setup

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
remember-me demo
```

## Tests

- Unit: schema, redact, TTL, policy thresholds, fail-closed
- Integration: FakeJev hydrate, actual local context assembly, and real localhost HTTP including malformed answers and node-ID round trips
- Negative: secrets never in outbound; orphan hydrations forbidden
- Bake-off: 50 queries offline → metrics JSON

## Pull requests

- Keep PRs small; conventional commits preferred
- Add/adjust tests with behavior changes
- Do not commit real API keys or PII

## GitHub topics

Historical topic list; recheck online settings before treating these as applied. Current candidate settings are in the launch checklist:

```text
python
memory-gate
typesafe
jev
system-one
agent-memory
redaction
fail-closed
decision-gate
llm-agents
```

Launch shell pattern: [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md).

