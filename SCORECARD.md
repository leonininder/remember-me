# SCORECARD — remember-me

**Status:** PREVIEW ONLY — NOT A FORMAL SKILL  
**Card / freeze:** PS-REMEMBER-ME-2026-09-19 / freeze-2026-09-19-v1  
**Scored:** 2026-09-19 (CST / Asia/Taipei); Phase 9.5 dual-gate refresh 2026-09-21; David adversarial 2026-09-21; **LIVE pilot + enrich v2 2026-09-22**  
**Package:** `/workspace/remember-me` v0.1.0 (`remember_me`)  
**Evidence basis:** Offline FakeJev + pytest (offline green) + **LIVE HttpJev smoke/bake-off logs** (see `docs/reviews/LIVE_PILOT_2026-09-22.md`). FakeJev bake-off remains **NON-EVIDENCE** (conf ∝ local_score).

---

## Leon dimensions (1–10)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **8.5** | Live enrich v2 `bakeoff_metrics_live.json`: C precision **0.727** clears B−0.05; still **not ≥9.5**; no acceleration |
| Goal fit | 20% | **9.0** | Dual egress + escalate_human + no-rerank; Jev ≠ store ≠ ranker |
| Runtime | 15% | **8.5** | Live System One hydrate/emit succeed on pin `jev-1.13.0`; CLI `bakeoff --live` |
| Verification | 15% | **8.5** | HTTP chaos (offline mock) + live 200s; remote CI on main **not claimed** |
| Safety | 10% | **9.0** | ALLOWLIST EscalationRecord + GateAuditRecord + adversarial redact |
| License | 10% | **9.0** | MIT; pydantic/httpx clean |
| Maintainability | 10% | **8.0** | Stale LIVE C=0.0/NON_PROMOTE section fixed 2026-09-22 post-David; CI workflow present — **do not claim remote green** |
| **Weighted overall** | 100% | **~8.6** | Enrich v2 quality bars clear; **not ≥9.5**; acceleration still **not** supported (latency) |

### Weighted calculation

```text
0.20×8.5 + 0.20×9.0 + 0.15×8.5 + 0.15×8.5 + 0.10×9.0 + 0.10×9.0 + 0.10×8.0
= 1.70 + 1.80 + 1.275 + 1.275 + 0.90 + 0.90 + 0.80
= 8.65 ≈ **~8.6**
```

Honesty note: Evidence rises above 7.5 **only** because real live logs are committed. Enrich v2 clears precision/overshare/fail_closed bars under redacted egress; latency still ↑ vs B → **do not** claim acceleration. **Do not advertise ≥9.5.**

---

## Bake-off snapshot (offline FakeJev) — NON-EVIDENCE

From `bakeoff_metrics.json` (k=5, n=50):

| Mode | precision@k | recall@k | overshare_rate | p95 latency (ms) | jev_calls |
|------|------------:|---------:|---------------:|-----------------:|----------:|
| local_topk_stub | ~0.387 | 0.98 | 0.04 | ~0.22 | 0 |
| jev_gated | ~0.472 | 0.97 | 0.04 | ~0.35 | 49 |

**NON-EVIDENCE:** FakeJev conf ∝ `local_score`.

---

## Bake-off snapshot (LIVE HttpJev) — EVIDENCE (enrich v2 @ `b8749f4`)

From `bakeoff_metrics_live.json` after allowlisted enrich v2 (2026-09-22, pin `jev-1.13.0`, `include_raw_query=False`, T_ACCEPT/T_ESCALATE **0.85/0.55** held):

| Mode | precision@k | recall@k | overshare_rate | p50 / p95 (ms) | fail_closed_rate | escalate_rate | jev_calls |
|------|------------:|---------:|---------------:|---------------:|-----------------:|--------------:|----------:|
| local_topk_stub (B) | ~0.387 | 0.98 | 0.04 | ~0.2 / ~0.3 | 0.0 | 0 | 0 |
| jev_gated_live (C) | **0.727** | (see pilot) | **0.00** | ~420 / ~498 | **0.0** | ~0.028 | 49 |

**Pre-registered quality bars:** precision ≥ B−0.05 ≈0.337 → **PASS**; overshare ≤0.02 → **PASS**; fail_closed ≤0.05 → **PASS**.  
**Label:** `PROMOTE_CANDIDATE` for those bars on `personal_prefs` only — **not** a ≥9.5 claim. Latency still ≫ B → **no acceleration**.

Earlier same-day pilots (hash-only C=0.0; enrich v1 C≈0.174) are historical — see `LIVE_PILOT_2026-09-22.md` / `LIVE_PILOT_RECAL_2026-09-22.md`. Current evidence: `docs/reviews/LIVE_PILOT_ENRICH_V2_2026-09-22.md`.

Usage (C enrich v2): see live metrics JSON (~155k in / ~23k out class).

---

## Remaining blockers to honest ≥9.5

1. Remote CI green on `main` (push blocked until PAT has **workflow** scope; not claimed)  
2. Independent human redact / allowlist review  
3. David/Justin formal ≥9.5 (still REJECT on current packet)  
4. Leon formal sign-off  
5. Do **not** treat recovery-floor precision bar as ≥9.5 evidence; ontology may be fixture-tilted

---

## Verdict

**Keep as Pre-Skill / PREVIEW.** Overall **~8.6** after enrich v2 live bake-off.  
**PROMOTE_CANDIDATE** for pre-registered quality bars only (`personal_prefs`).  
Live **contract works**; quality bars **cleared** under redacted enrich; acceleration / ≥9.5 narratives still **REJECTED**.

See [docs/reviews/LIVE_PILOT_ENRICH_V2_2026-09-22.md](docs/reviews/LIVE_PILOT_ENRICH_V2_2026-09-22.md) + [docs/reviews/DAVID_2026-09-22_ENRICH_V2.md](docs/reviews/DAVID_2026-09-22_ENRICH_V2.md) + [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md).
