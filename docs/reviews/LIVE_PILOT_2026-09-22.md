# LIVE TypeSafe pilot — 2026-09-22 (Asia/Taipei)

**Label:** LIVE HttpJev evidence (not FakeJev)  
**Model pin:** `jev-1.13.0`  
**Endpoint:** `POST https://api.typesafe.ai/v1/systemone`  
**Artifacts:** `LIVE_SMOKE_2026-09-22.json`, `LIVE_HYDRATE_LOG_2026-09-22.json`, `bakeoff_metrics_live.json`

---

## Contract fix (why prior 422)

Live diagnosis showed hydrate/admit/emit/writeback questions used the wrong criteria shapes:

| Type | Broken (HTTP 422) | Fixed (HTTP 200) |
|------|-------------------|------------------|
| Choice | `criteria: ["hydrate_full", …]` (list of strings) | `criteria: {option_key: description}` (dict) |
| Score | `criteria: [1,2,3,4,5]` (ints) | `criteria: ["not needed…", … "critical…"]` (2–10 ordered strings) |
| Noul | OK | unchanged |

Smoke after fix: **malformed=False, denied=False**, non-empty answers for candidates; optional emit also succeeded.

---

## Smoke (1–2 hydrate + emit)

From `LIVE_SMOKE_2026-09-22.json` (batched hydrate, 2 candidates):

| Field | Value |
|-------|------:|
| latency_ms | ~465 |
| response_model | `jev-1.13.0` |
| usage | input≈511, output≈108 |
| hydrate failed? | no (both candidates) |
| emit failed? | no |

**Score indexing (live):** `need_for_next_turn.score` is a **continuous** value on ≈`[0, n_levels)` with a `legend` mapping integer levels → criteria strings (not FakeJev’s discrete 1…5 ints). Policy stores `float(need)`; gating still uses Choice confidence bands.

---

## Bake-off B vs C (`bakeoff_metrics_live.json`)

Arms: **B** `local_topk_stub` vs **C** `jev_gated_live` (n=50, k=5, `batch_candidates=True`).

| Metric | B local_topk_stub | C jev_gated_live | Δ (C−B) |
|--------|------------------:|-----------------:|--------:|
| precision@k | ~0.387 | **0.0** | **−0.387** |
| recall@k | 0.98 | **0.0** | −0.98 |
| overshare_rate | 0.04 | 0.0 | −0.04 |
| p50 latency (ms) | ~0.16 | ~422 | +422 |
| p95 latency (ms) | ~0.22 | ~509 | +509 |
| fail_closed_rate | 0.0 | **0.0** | 0 |
| jev_calls | 0 | 49 | — |
| jev_model | — | `jev-1.13.0` | — |
| usage tokens | — | in≈99.3k / out≈22.9k | — |
| mean_hydrated | 3.6 | ~0.02 | — |

No HTTP 429 during this run.

---

## Pass/fail vs `BAKEOFF_PLAN` thresholds (honest)

| Metric | Tentative bar | Result | Verdict |
|--------|---------------|--------|---------|
| precision@k (C−B) | ≥ +0.05 | **−0.387** | **FAIL** (quality claim falsified) |
| overshare_rate (C−B) | ≤ 0 | −0.04 | PASS (but via near-total skip) |
| latency_p95 (C−B) | report only | +~509 ms | Expected RTT; **do not claim faster** |
| fail_closed_rate | ≤ 0.05 healthy | 0.0 | PASS (HTTP health) |
| “Jev accelerates memory” | net benefit under RTT | quality↓ + latency↑ | **FAIL / falsified** |
| “HttpJev works” | 2xx + parse | smoke + 49 live calls | **PASS** (contract) |

### Why precision collapsed (not an HTTP bug)

Under default egress policy (`query_hash` only; no body; no `query_preview`), live Choice **confidence** lands ~0.2–0.5 with relatively flat `probabilities`. Policy reject band is `< 0.55` → almost all decisions map to **`skip`**. That is fail-*soft* via thresholds, not `fail_closed` via transport errors.

Sample (5 queries): 21/21 `skip`, conf≈0.32–0.49. Raw Choice often picks `stub_only` / `hydrate_full` / `skip` with max-prob ≈0.3–0.4 — still below accept (0.85) and usually below escalate (0.55).

---

## What this does / does not prove

**Proves**

- Live System One contract + criteria shapes work for hydrate/emit.
- Pin `jev-1.13.0` echoed in responses; usage tokens available.
- Offline FakeJev bake-off must not be cited as live proof (live Δ reverses Fake Δ).

**Does not prove**

- Acceleration, token win, or beat-Hindsight.
- That current 0.85/0.55 thresholds are calibrated for live System One on redacted hash-only state.
- Remote CI green on `main` (not claimed here).

---

## Remaining blockers toward honest ≥9.5

1. Recalibrate policy bands and/or enrich allowed state (`include_raw_query` opt-in, better instructions) so live decisions are useful without oversharing.  
2. Re-run live bake-off until precision/recall/overshare meet pre-registered bars **without** inventing wins.  
3. Remote Actions green on `main` with proof.  
4. Leon formal sign-off.

---

## Follow-up: enrichment recal (same day)

See [`LIVE_PILOT_RECAL_2026-09-22.md`](LIVE_PILOT_RECAL_2026-09-22.md). Structured allowlist enrichment (`intent_class`, `length_bucket`, `stub_tags`) + clearer criteria; thresholds **unchanged** (0.85/0.55). Live C precision_at_k recovered **0.0 → ~0.174** but still fails pre-registered bar vs B; **NON_PROMOTE**; no acceleration claim.

