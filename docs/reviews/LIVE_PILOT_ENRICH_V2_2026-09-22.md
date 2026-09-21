# LIVE pilot enrich v2 — 2026-09-22 (Asia/Taipei)

**Status:** quality bars **CLEAR** → `PROMOTE_CANDIDATE` (precision/overshare/fail_closed)  
**Not claimed:** ≥9.5 SCORECARD; acceleration / “Jev speeds memory” (latency still ≫ B)  
**Constraints honored:** `include_raw_query=False`; ALLOWED_OUTBOUND_KEYS only; thresholds **held** at 0.85/0.55

**Pre-reg doc (before run):** [`LIVE_PILOT_ENRICH_V2_PREREG_2026-09-22.md`](LIVE_PILOT_ENRICH_V2_PREREG_2026-09-22.md)  
**Artifacts:** `bakeoff_metrics_live.json`, `LIVE_SMOKE_ENRICH_V2_2026-09-22.json`

---

## Analysis: why v1 precision was ~0.174

| Observation | Implication |
|-------------|-------------|
| Smoke: gold `pref_theme_dark` **skip@0.40**; off-gold UI stubs **stub_only@0.6–0.8** | Jev admitted wrong mid-band stubs |
| “What UI language…?” → `preference_ui` | Coarse intent (needle `ui`) misrouted locale asks |
| Conf mean≈0.59 / max≈0.82 | Almost no accept-band; enrichment raised floor but not discrimination |
| `stub_tags` + `intent_class` only | Too coarse to separate theme vs font vs editor |

---

## Enrich v2 (structured allowlist)

**State:** `intent_class`, `intent_focus`, `length_bucket`  
**Candidate:** `stub_tags`, `topic_family`, `overlap_tag_count`, `intent_topic_fit`, `candidate_rank_in_topk`, `salience_bucket`, `stub_token_bucket`

Intent routing fixes: locale before bare `ui`; soft-negate “without health”; beverage/testing/workflow needles; new `preference_safety`.

Choice/Score criteria updated to reference `intent_topic_fit` + rank + focus (still dict criteria).

---

## Held-out threshold decision

- Split: queries **0:30** calibrate / **30:50** holdout (offline signal check).
- Offline: gold mostly `strong_match`; mean gold rank ≈1.0–1.3.
- Live smoke (3 queries): conf **min0.33 max1.0 mean≈0.85**; gold **hydrate_full@1.0**.
- **No T_* change** — accept-band mass for gold is separable above 0.55; lowering into 0.2–0.5 would violate David.

---

## Pre-registered bars → outcome

| Bar | Pass condition | Result |
|-----|----------------|--------|
| Precision | C ≥ B − 0.05 (≈0.337) | **PASS** — C=**0.7267** (B=0.3867) |
| Overshare | C ≤ 0.02 and ≤ B | **PASS** — 0.000 |
| Fail-closed | C ≤ 0.05 | **PASS** — 0.000 |
| Escalate | report | **0.0278** |
| ≥9.5 / acceleration | not claimed | **not claimed** (p95 ≈498 ms) |

---

## LIVE bake-off metrics (n=50, k=5, pin `jev-1.13.0`)

| Metric | B local_topk_stub | C jev_gated_live | Δ |
|--------|------------------:|-----------------:|--:|
| precision_at_k | 0.3867 | **0.7267** | **+0.3400** |
| recall_at_k | 0.9800 | 0.9500 | −0.0300 |
| overshare_rate | 0.0400 | 0.0000 | −0.0400 |
| p50 latency ms | ~0.17 | ~419.6 | +419 |
| p95 latency ms | ~0.23 | ~498.0 | +498 |
| fail_closed_rate | 0.0000 | 0.0000 | 0 |
| escalate_rate | 0.0000 | 0.0278 | +0.0278 |
| mean_hydrated | 3.60 | 1.66 | — |
| jev_calls | 0 | 49 | — |

**Usage (C):** input_tokens≈**154958**, output_tokens≈**22882** (plus smoke ≈6.5k in / ~1.1k out estimate).

---

## Honest verdict

- Enrich v2 cleared the **pre-registered precision bar** without raw query or threshold-into-noise.
- Selective hydrate (mean_hydrated 1.66 vs B 3.6) with **higher** precision — gate utility, not “faster memory.”
- Latency remains RTT-dominated → **do not** claim acceleration.
- SCORECARD / ≥9.5: **still do not claim**; remote CI / Leon sign-off / human redact review remain separate blockers.
- FakeJev bake-off remains **NON-EVIDENCE**.

