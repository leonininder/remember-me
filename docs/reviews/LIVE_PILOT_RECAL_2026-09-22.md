# LIVE pilot recalibration — enrichment-first (2026-09-22, Asia/Taipei)

**Status:** `NON_PROMOTE` (bars_clear=False)  
**Constraints honored:** David — no threshold lowering into conf≈0.2–0.5; JustinSun — `include_raw_query=False`, ALLOWED_OUTBOUND_KEYS enrichment only; skip→admit alone ≠ ≥9.5.

---

## Policy bands (unchanged)

| Band | Confidence | Hydrate policy |
|------|------------|----------------|
| **Accept** | ≥ **0.85** (`T_ACCEPT`) | Accept Choice |
| **Escalate** | **0.55–0.85** (`T_ESCALATE`) | `escalate_human` (+ record); raw `stub_only` may stub |
| **Reject** | **< 0.55** | `skip` |
| **Fail-closed** | transport / deny / malformed | `skip` |

**Hard NO:** lowering floors to match pre-enrichment noise.

---

## Enrichment shipped (allowlist only)

| Key | Where | Notes |
|-----|-------|-------|
| `intent_class` | state | Closed enum |
| `length_bucket` | state | short/medium/long |
| `stub_tags` | candidate | ≤8 capped tags |
| core fields | candidate | node_id, kind, tags, degree, last_touch, local_score, tokens_est |

`include_raw_query=False`. Clearer Choice/Score instructions reference enrichment fields.

---

## Pre-registered bars (before live re-run) → outcome

| Bar | Pass condition | Result |
|-----|----------------|--------|
| Precision | C ≥ B − 0.05 (target beat B) | **FAIL** — C=0.174 vs B−0.05=0.337 (B=0.387) |
| Overshare | C ≤ B | **PASS** — C=0.000 ≤ B=0.040 |
| Fail-closed | C ≤ 0.05 | **PASS** — 0.000 |
| Escalate | report | **0.022** |
| Promotion | NON_PROMOTE until bars clear | **NON_PROMOTE** |
| ≥9.5 / acceleration | not claimed | **not claimed** |

---

## LIVE smoke (enrichment sanity)

Artifact: `docs/reviews/LIVE_SMOKE_RECAL_2026-09-22.json`

- Calls: 3; fail_closed on smoke path: 0
- Confidence summary: {'n': 9, 'min': 0.4, 'max': 0.82, 'mean': 0.588} (prior pilot ~0.2–0.5; enrichment raised mean/max without floor changes)
- Some `stub_only` admits observed under held 0.85/0.55 bands

---

## LIVE bake-off metrics (n=50, k=5, pin `jev-1.13.0`)

| Metric | B local_topk_stub | C jev_gated_live | Δ |
|--------|------------------:|-----------------:|--:|
| precision_at_k | 0.3867 | **0.1740** | -0.2127 |
| recall_at_k | 0.9800 | 0.3000 | -0.6800 |
| overshare_rate | 0.0400 | 0.0000 | -0.0400 |
| p50 latency ms | 0.17 | 427.38 | 427.20 |
| p95 latency ms | 0.29 | 584.04 | 583.76 |
| fail_closed_rate | 0.0000 | 0.0000 | 0.0000 |
| escalate_rate | 0.0000 | 0.0222 | 0.0222 |
| mean_hydrated | 3.60 | 1.70 | — |
| jev_calls | 0 | 49 | — |

Usage (C): in≈130831, out≈22869.

**Vs prior live pilot (precision C=0.0):** enrichment-first path is a **material quality recovery** (0.0 → 0.174) while staying fail-closed-healthy and not raising overshare. **Still fails** the pre-registered precision bar vs B.

---

## Honest verdict

- Contract + enrichment path: **working**
- Pre-registered quality bars: **not cleared** → remain **NON_PROMOTE**
- Acceleration / “Jev speeds memory”: **not supported** (latency ↑, precision still < B)
- SCORECARD / ≥9.5: **do not promote**
- Next: held-out conf calibration **only if** enrichment keeps mass ≥0.55; else more structured signal (still no raw query) or accept gate utility gap

FakeJev bake-off remains **NON-EVIDENCE**.
