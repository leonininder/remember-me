# Security — remember-me

## Red lines

1. **No customer / PII / secrets / unpublished vulns to TypeSafe.**
2. **Fail-closed** on Jev errors — never fail-open into cloud-influenced hydrate.
3. **No theater** — hydrate path must call Jev when candidates exist (proven in tests).
4. **No auto-wiki / compliance evidence** from Jev confidence alone.
5. Synthetic fixtures only under `fixtures/`.

## Redaction contract

Outbound candidate fields are exactly:

```text
node_id, kind, tags, degree, last_touch, local_score, tokens_est
```

`redact.assert_no_secrets` rejects secret-like keys and obvious token material (`sk-`, `bearer `, `password=`, …). `FakeJev` / `HttpJev` call this before recording `last_outbound`.

## Secrets handling

- Do not commit `.env` or API keys
- `TYPESAFE_API_KEY` is read only by `HttpJev`
- CI sets an empty key and uses `FakeJev`

## Reporting

If you discover a redaction bypass or fail-open path in **remember-me**, open a private security advisory / email the maintainer. Prefer a failing regression test with the PR.

## Threat notes (v0.1)

| Threat | Mitigation |
|--------|------------|
| Body/PII egress to Jev | Redaction + unit/property tests |
| Cloud outage opens hydrate | Fail-closed skip / local stub only |
| Orphan node injection | Candidate-set allowlist in pipeline |
| Theater skill (never calls Jev) | Integration assert `jev_called` / `call_count` |
