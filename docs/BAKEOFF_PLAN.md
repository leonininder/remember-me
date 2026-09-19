# Minimal live bake-off plan — falsify “Jev accelerates memory”

**Written:** 2026-09-20 (CST / Asia/Taipei)  
**Rule:** Offline FakeJev alone is **insufficient**. This plan must be able to **falsify** the acceleration claim.

---

## Claim under test (precise)

> After local TEMPR-style retrieval, calling live TypeSafe Jev (`jev-1.13.0`) as a hydrate gate improves **decision quality** and/or **hydrate token efficiency** enough to justify its **added latency**, versus a no-Jev baseline.

Acceleration is **not** “FakeJev is 0.3 ms.” Acceleration means: *net workflow benefit under live RTT + token accounting*.

---

## Preconditions (blockers)

1. Fix `HttpJev` to System One (`POST …/v1/systemone`, `state` + typed `questions`) — see `RUNTIME_HOWTO.md`.
2. `TYPESAFE_API_KEY` available locally — **never commit**.
3. Fixtures remain synthetic (`fixtures/personal_prefs/`) — no PII egress.
4. Redaction assertions still pass on live outbound state.
5. Separate output file: `bakeoff_metrics_live.json` (do not overwrite FakeJev JSON without renaming).

If (1) fails, **stop** — do not publish partial live numbers.

---

## Arms (minimum three)

| Arm ID | Description | Jev? |
|--------|-------------|------|
| A `dump_topk` | Hydrate full bodies for local top-k | No |
| B `local_topk_stub` | Local top-k stubs only (current offline baseline) | No |
| C `jev_gated_live` | retrieve → redact → **HttpJev** → policy | Yes, live |
| D (optional) `jev_gated_fake` | Same path with FakeJev for A/B sanity | Fake only |

Primary contrast for the claim: **B vs C** (same retrieve, gate vs no-gate).  
Optional: **A vs C** for overshare / token blow-up.

---

## Metrics (required)

| Metric | Definition | Falsification hint |
|--------|------------|--------------------|
| **latency_p50_ms / latency_p95_ms** | Wall time of full `pipeline.run` per query | If C p95 ≫ B and quality Δ ≤ 0 → acceleration claim fails |
| **hydrate_token_count** | Sum of estimated tokens in hydrated contents (use `tokens_est` or tiktoken) | If C does not reduce tokens vs A (or worsens vs B without quality gain) → efficiency claim fails |
| **decision quality** | On labeled keep/drop: precision@k, recall@k, macro-F1 of {hydrate_full, stub_only, skip} vs gold | If C ≤ B within CI → quality claim fails |
| **overshare_rate** | Fraction of queries hydrating any `overshare_ids` | Must not rise materially |
| **fail_closed_rate** | `fail_closed_count / decisions` and queries with any fail-closed | High rates → reliability claim fails; report separately |
| **jev_calls / jev_input_tokens** | From client + API `usage` | Cost accounting |
| **jev_model** | Echo response model pin | Detect alias drift |

Do **not** average Fake and live latencies into one table without labeling.

---

## Labeled keep/drop protocol

Existing fixtures already have `relevant_ids` / `overshare_ids`. Extend lightly:

1. Keep n≥50 synthetic queries (current set OK for v0).
2. For each candidate in top-k, gold label ∈ {`hydrate_full`, `stub_only`, `skip`} — start from relevant/overshare maps:
   - in `relevant_ids` → prefer `hydrate_full`
   - in `overshare_ids` → `skip`
   - else → `stub_only` or `skip` (document rule)
3. Freeze labels **before** looking at live Jev outputs (no peeking).
4. Report confusion matrix for C vs gold; B maps all retrieved → stub hydrate for quality proxy as today.

---

## Procedure (minimal)

```text
1. Fix HttpJev contract; smoke one curl/system_one call with redacted toy state.
2. Add CLI flag or script: remember-me bakeoff --live --out bakeoff_metrics_live.json
   - Refuse to run if TYPESAFE_API_KEY missing.
   - Pin model jev-1.13.0 (not only jev-latest).
3. Run arms B and C on the same fixtures, same machine, same wall clock window.
4. Chaos subset (optional but strong): force 1–2 queries with invalid key / 1s timeout → expect fail-closed, not dump-all.
5. Write JSON + short prose: pass/fail per metric against pre-registered thresholds.
6. Commit metrics only after dual approval; never claim GitHub “acceleration” on FakeJev alone.
```

### Pre-registered pass thresholds (draft — adjust before run)

| Metric | Tentative “interesting” bar | Falsify if |
|--------|----------------------------|------------|
| precision@k (C − B) | ≥ +0.05 | < 0 (or within noise) |
| overshare_rate (C − B) | ≤ 0 | > +0.02 |
| hydrate_token_count mean (C / A) | ≤ 0.7 | ≥ 1.0 with no quality gain |
| latency_p95 (C − B) | **report only** | Claiming “faster” when C − B > 0 |
| fail_closed_rate | ≤ 0.05 under healthy API | > 0.2 without documented outage |

**Important:** If C is **slower** (expected: +70–500 ms class RTT) but **better quality / fewer tokens**, the honest claim is “better gate, not faster,” not “accelerates.”

---

## What this plan can falsify

| Slogan | How falsified |
|--------|----------------|
| “Jev accelerates memory” | C latency ≥ B and no token/quality win |
| “Live Jev matches FakeJev bake-off” | Live precision Δ ≪ Fake Δ (+0.085) or reverses |
| “Fail-closed is theater” | Live errors hydrate full bodies |
| “HttpJev works” | Non-2xx / malformed on every call after contract fix attempt |

---

## Out of scope (v0 live)

- Production Hindsight SaaS A/B
- Multi-user PII corpora
- Claude/Codex/Hermes hook E2E (separate integration tests)
- Claiming vendor headline “193× faster” numbers

---

## Deliverables

| Artifact | Path |
|----------|------|
| Live metrics | `bakeoff_metrics_live.json` (new) |
| Call log (redacted) | `docs/evidence/live_jev_calls_YYYYMMDD.jsonl` (optional) |
| Verdict paragraph | Append to SCORECARD only after dual approval |

---

## Status

**Plan only.** No live bake-off executed in this research pass. Offline FakeJev metrics remain the only numbers on disk.
