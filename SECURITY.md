# Security — remember-me

## Data boundary

The default hydrate request omits memory `content` and `content_ref`, and sends a query hash plus structured intent fields. Core candidate fields are:

```text
node_id, kind, tags, degree, last_touch, local_score, tokens_est
```

Enrichment also sends `stub_tags`, `topic_family`, `overlap_tag_count`, `intent_topic_fit`, `candidate_rank_in_topk`, `salience_bucket`, and `stub_token_bucket`. Query-derived fields include `intent_class`, `intent_focus`, and `length_bucket`. See `redact.py`, `enrich.py`, and `HttpJev._build_state` for the current schema.

This is field projection, not general anonymization. IDs and tags are caller-controlled strings; they can contain identifying information. Secret-pattern checks reject common token-like strings but cannot recognize all PII or secrets. Use synthetic or non-sensitive IDs/tags, and inspect your payload before enabling a remote client. Hashes can still disclose equality and permit guessing of low-entropy text.

`include_raw_query=True` explicitly adds the raw query to outbound state. Keep the default `False` for metadata-only use. Do not send customer data, credentials, unpublished vulnerabilities, or personal information to TypeSafe.

## Returned memory and application responsibilities

A `hydrate_full` or `promote_durable` result contains the selected local memory body. The caller decides whether to send that body to an LLM or another service. Admission is not a content sanitizer or authorization check. An application must enforce its own access control and disclosure policy.

Optional emit gates use a summary fingerprint and allowlisted metadata; they do not inspect all content in a proposed message. Treat their decision as a policy signal, not DLP certification. `escalate_human` records a decision; the application must route and resolve it.

## Failure behavior

Default policy skips on client timeout, denial, or malformed responses. An explicitly configured local-stub fallback can return markers without full bodies. Candidate-set checks exclude unknown IDs. Offline tests exercise these behaviors with test doubles and mocked HTTP; they do not certify a production deployment.

Writeback gates are opt-in. `observe(require_writeback=True)` writes only on `ALLOW_WRITEBACK`. A `STAGE_ONLY` response raises `PermissionError` and leaves the graph unchanged; the caller must handle staging separately. Do not interpret a confidence value alone as authority to update a Wiki or compliance record.

## Credentials and fixtures

- Keep API credentials out of source control and diagnostic logs.
- `HttpJev` can read `TYPESAFE_API_KEY`; offline demos use `FakeJev`.
- Repository fixtures are synthetic. Use synthetic cases in public issues.

## Reporting

Use the repository's private vulnerability reporting channel if available, or arrange private contact with the maintainer before sharing sensitive details. Public issues should contain only a sanitized reproducer. See [GitHub security](https://github.com/leonininder/remember-me/security).
