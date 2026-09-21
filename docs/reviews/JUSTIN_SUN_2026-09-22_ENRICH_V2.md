# JustinSun LIVE enrich v2 re-score — remember-me @ b8749f4

**When:** 2026-09-22 ~07:28–07:30 CST (Asia/Taipei)  
**Role:** JustinSun characterization + VC red-team (not the real Justin Sun; not financial advice)  
**Tree:** `/workspace/remember-me` HEAD `b8749f458ff67848a9e0e9ff9b2e6b49b9feaff9`  
**Process:** Re-check `bakeoff_metrics_live.json`, `docs/reviews/LIVE_PILOT_ENRICH_V2_2026-09-22.md`, `policy.py` thresholds, egress allowlist; `.venv/bin/ruff check src tests` exit 0; `.venv/bin/pytest -q` → **149 passed** (~07:28–07:29 CST). `gh` Actions **401** — remote green not claimed.

---

## Verdict

| Gate | Call |
|------|------|
| Pre-registered live quality bars (this pilot) | **PROMOTE_CANDIDATE** (bars_clear confirmed) |
| Internal Pre-Skill / PREVIEW harness | **APPROVE_WITH_CONDITIONS** |
| ≥9.5 / formal skill / “accelerates memory” marketing | **REJECT** |

Hard deal-breakers still open: remote CI green unproven; Leon sign-off; any ≥9.5 or latency-as-speed narrative.

---

## Scores (Leon weights)

| Dimension | Weight | Prior LIVE (d8a7548) | enrich v2 now | Notes |
|-----------|-------:|---------------------:|--------------:|-------|
| Evidence | 20% | 8.0 | **8.5** | C p@k **0.7267** vs B **0.3867**; path 0.0→0.174→0.727 documented; FakeJev still NON-EVIDENCE |
| Goal fit | 20% | 8.0 | **8.5** | Redacted enrich clears pre-reg bars; not “acceleration”; thresholds held |
| Runtime | 15% | 8.0 | **8.2** | Selective hydrate (mean 1.66); p50/p95 ~**420/498** ms — RTT tax remains |
| Verification | 15% | 8.5 | **8.5** | 149 pytest + ruff; live pin `jev-1.13.0`; remote CI **unverified** |
| Safety | 10% | 9.0 | **9.0** | `include_raw_query=False`; enrich ⊆ ALLOWED_OUTBOUND_KEYS; no query_preview |
| License | 10% | 9.0 | **9.0** | unchanged |
| Maintainability | 10% | 8.0 | **7.5** | **SCORECARD.md split-brain**: top ~8.6 / PROMOTE_CANDIDATE; bottom still C=0.0 / NON_PROMOTE |
| **Weighted** | 100% | ~8.3 | **~8.5** | 0.20×8.5+0.20×8.5+0.15×8.2+0.15×8.5+0.10×9.0+0.10×9.0+0.10×7.5 = **8.455 ≈ 8.5** |

Disagree with any SCORECARD Goal fit that reads like product-done. Agree **not ≥9.5**. Fix SCORECARD bottom before using the card as a ship artifact.

---

## Exact numbers trusted

From `/workspace/remember-me/bakeoff_metrics_live.json` (k=5, n=50, pin `jev-1.13.0`, `include_raw_query=false`):

| Arm | precision@k | overshare | fail_closed | p95 ms | jev_calls |
|-----|------------:|----------:|------------:|-------:|----------:|
| B local_topk_stub | 0.3867 | 0.04 | 0.0 | ~0.23 | 0 |
| C jev_gated_live | **0.7267** | **0.0** | **0.0** | **~498** | 49 |

`pre_registered_bars.bars_clear`: **true**. Prior C: 0.0 → 0.174 (NON_PROMOTE) → 0.727 (PROMOTE_CANDIDATE).

Bridge now has traffic. Still not a highway speed claim.

---

## Conditions to keep

1. Do not market acceleration while p95 ≈ 500 ms vs local ~0.2 ms.  
2. Sync SCORECARD LIVE table / blockers / verdict with enrich v2 JSON.  
3. Workflow-scoped push + Actions green on main (proof).  
4. Leon formal sign-off before any formal skill / showcase language.  
5. skip→admit alone still ≠ ≥9.5; need sustained bars + remote CI + sign-off.

