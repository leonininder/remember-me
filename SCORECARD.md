# SCORECARD — remember-me

**Status:** PREVIEW ONLY — NOT A FORMAL SKILL  
**Card / freeze:** PS-REMEMBER-ME-2026-09-19 / freeze-2026-09-19-v1  
**Scored:** 2026-09-19 (CST / Asia/Taipei); Phase 9.5 dual-gate refresh 2026-09-21; David adversarial 2026-09-21; **LIVE pilot 2026-09-22**  
**Package:** `/workspace/remember-me` v0.1.0 (`remember_me`)  
**Evidence basis:** Offline FakeJev + pytest (**140 passed**) + **LIVE HttpJev smoke/bake-off logs** (see `docs/reviews/LIVE_PILOT_2026-09-22.md`). FakeJev bake-off remains **NON-EVIDENCE** (conf ∝ local_score).

---

## Leon dimensions (1–10)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **8.0** | Live smoke + `bakeoff_metrics_live.json` committed; quality claim **fails** (precision Δ negative) |
| Goal fit | 20% | **9.0** | Dual egress + escalate_human + no-rerank; Jev ≠ store ≠ ranker |
| Runtime | 15% | **8.5** | Live System One hydrate/emit succeed on pin `jev-1.13.0`; CLI `bakeoff --live` |
| Verification | 15% | **8.5** | HTTP chaos (offline mock) + live 200s; remote CI on main **not claimed** |
| Safety | 10% | **9.0** | ALLOWLIST EscalationRecord + GateAuditRecord + adversarial redact |
| License | 10% | **9.0** | MIT; pydantic/httpx clean |
| Maintainability | 10% | **8.0** | src layout + docs + CI workflow present; **do not claim CI green on main until remote green** |
| **Weighted overall** | 100% | **~8.5** | Live contract works; **not ≥9.5**; acceleration **falsified** on this pilot |

### Weighted calculation

```text
0.20×8.0 + 0.20×9.0 + 0.15×8.5 + 0.15×8.5 + 0.10×9.0 + 0.10×9.0 + 0.10×8.0
= 1.60 + 1.80 + 1.275 + 1.275 + 0.90 + 0.90 + 0.80
= 8.55 ≈ **~8.5**
```

Honesty note: Evidence rises above 7.5 **only** because real live logs are committed. Live bake-off **does not** support “Jev accelerates memory” (latency↑, precision↓ under current thresholds + hash-only state). **Do not advertise ≥9.5.**

---

## Bake-off snapshot (offline FakeJev) — NON-EVIDENCE

From `bakeoff_metrics.json` (k=5, n=50):

| Mode | precision@k | recall@k | overshare_rate | p95 latency (ms) | jev_calls |
|------|------------:|---------:|---------------:|-----------------:|----------:|
| local_topk_stub | ~0.387 | 0.98 | 0.04 | ~0.22 | 0 |
| jev_gated | ~0.472 | 0.97 | 0.04 | ~0.35 | 49 |

**NON-EVIDENCE:** FakeJev conf ∝ `local_score`.

---

## Bake-off snapshot (LIVE HttpJev) — EVIDENCE (quality claim fails)

From `bakeoff_metrics_live.json` (2026-09-22, pin `jev-1.13.0`):

| Mode | precision@k | recall@k | overshare_rate | p50 / p95 (ms) | fail_closed_rate | jev_calls |
|------|------------:|---------:|---------------:|---------------:|-----------------:|----------:|
| local_topk_stub (B) | ~0.387 | 0.98 | 0.04 | ~0.16 / ~0.22 | 0.0 | 0 |
| jev_gated_live (C) | **0.0** | **0.0** | 0.0 | ~422 / ~509 | **0.0** | 49 |

Usage (C): ~99k input / ~23k output tokens. Details: `docs/reviews/LIVE_PILOT_2026-09-22.md`.

---

## Remaining blockers to honest ≥9.5

1. Enrichment-first recal shipped (intent/length/stub_tags); live C precision ~0.174 still below pre-registered bar vs B — held-out calibration next, **without** lowering floors into noise  
2. Live bake-off meeting pre-registered quality bars (today: **fails**)  
3. Remote CI green on main (proof required; not claimed)  
4. Leon formal sign-off  

---

## Verdict

**Keep as Pre-Skill / PREVIEW.** Overall **~8.5** after live pilot; enrichment recal **NON_PROMOTE** (precision recovered but bars uncleared — see LIVE_PILOT_RECAL_2026-09-22).  
Live **contract works**; acceleration / ≥9.5 narratives **REJECTED** on this evidence.

See [docs/reviews/LIVE_PILOT_2026-09-22.md](docs/reviews/LIVE_PILOT_2026-09-22.md) + [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md).
