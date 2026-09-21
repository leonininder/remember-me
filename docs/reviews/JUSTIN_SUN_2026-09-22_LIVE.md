# JustinSun LIVE re-score — remember-me @ d8a7548

**When:** 2026-09-22 ~07:17 CST (Asia/Taipei)  
**Role:** JustinSun characterization + VC red-team (not the real Justin Sun; not financial advice)  
**Tree:** `/workspace/remember-me` HEAD `d8a75485e43e4be5c27201c752e06bbfbf29e54d`  
**Process:** Independent re-check of `bakeoff_metrics_live.json`, `docs/reviews/LIVE_PILOT_2026-09-22.md`, smoke/hydrate logs; `.venv/bin/ruff check src tests` (exit 0); `.venv/bin/pytest` → **140 passed** in 0.36s (07:16 CST). `gh` Actions **401** — remote green not claimed.

---

## Verdict

| Gate | Call |
|------|------|
| Internal Pre-Skill / PREVIEW (contract harness) | **APPROVE_WITH_CONDITIONS** |
| ≥9.5 / formal skill / “Jev accelerates memory” / beat-Hindsight marketing | **REJECT** |

Hard deal-breakers still open: acceleration claims; FakeJev as promotion evidence; remote CI green unproven; Leon sign-off absent.

---

## Scores (Leon weights)

| Dimension | Weight | Prior (ruff recheck) | LIVE now | Notes |
|-----------|-------:|---------------------:|---------:|-------|
| Evidence | 20% | 7.5 | **8.0** | Real HttpJev logs + live bake-off committed; quality claim **fails** — honesty raises Evidence |
| Goal fit | 20% | 8.8 | **8.0** | Architecture (admit≠rank) intact; live utility for hydrate **falsified** this pilot |
| Runtime | 15% | 8.0 | **8.0** | `jev-1.13.0` contract PASS; effective precision@k **0.0** (near-total skip) |
| Verification | 15% | 8.5 | **8.5** | Offline 140 + ruff green; live 200s; **no** remote Actions green |
| Safety | 10% | 8.8 | **9.0** | Hash-only default + redacted outbound confirmed in live logs |
| License | 10% | 9.0 | **9.0** | unchanged |
| Maintainability | 10% | 8.0 | **8.0** | Criteria fix + CLI live path; CI file present, green unproven |
| **Weighted** | 100% | 8.3 | **~8.3** | 0.20×8.0+0.20×8.0+0.15×8.0+0.15×8.5+0.10×9.0+0.10×9.0+0.10×8.0 = **8.275 ≈ 8.3** |

Disagree with SCORECARD Goal fit **9.0** after product FAIL — cut to **8.0**. Agree Evidence **8.0** and overall stay **&lt;9.5**.

---

## What the numbers say (exact)

From `bakeoff_metrics_live.json` (k=5, n=50, pin `jev-1.13.0`):

- B `local_topk_stub` precision@k **0.3866…** ≈ 0.39; p95 ~**0.22** ms  
- C `jev_gated_live` precision@k **0.0**; p95 ~**509.30** ms; `jev_calls` **49**; `fail_closed_rate` **0.0**  
- Δ precision **−0.3866…** → pre-registered “accelerates memory” bar **FAIL**

Contract PASS ≠ product PASS. Bridge is open; cars are not crossing.

---

## Stub / tag enrichment without `query_preview`

**Accept for next pilot, with conditions:**

1. Keep default `include_raw_query=False` (no free-text query egress).  
2. Enrich only within `ALLOWED_OUTBOUND_KEYS` (tags / kind / scores / topology) — already the privacy bargain.  
3. Pre-register quality bars before the run; label results NON-PROMOTE until bars clear.  
4. Do **not** treat a better skip→admit ratio alone as ≥9.5 evidence without precision/latency/overshare bars.

---

## Remaining blockers to honest ≥9.5

1. Calibrated live quality bars (precision Δ, latency, overshare) under redacted egress  
2. Workflow-scoped push + Actions green on main (proof)  
3. Leon formal sign-off  
