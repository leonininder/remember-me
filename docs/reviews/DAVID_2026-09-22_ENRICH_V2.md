# David 重評 — LIVE enrich v2 (2026-09-22)

**Date:** 2026-09-22 07:28 CST (Asia/Taipei)  
**Tree:** `/workspace/remember-me` @ `b8749f4` (local, unpushed)  
**Against:** `LIVE_PILOT_ENRICH_V2_PREREG_2026-09-22.md`, `LIVE_PILOT_ENRICH_V2_2026-09-22.md`, `bakeoff_metrics_live.json`, `enrich.py`  
**Method:** Read pre-reg + pilot; verify metrics JSON; spot `intent_topic_fit` (ontology, no gold label); confirm `include_raw_query=False` / T 0.85/0.55; pytest offline green.

---

## Verdict

**`APPROVE_WITH_CONDITIONS`** — keep PREVIEW / Pre-Skill.  
**`PROMOTE_CANDIDATE` for pre-registered quality bars: CONCUR** (scope: this fixture pack + these bars only).  
**`REJECT` ≥9.5** / formal skill / acceleration narrative.

**Weighted overall: ~8.6**

---

## Leon 10-pt

| Dimension | Weight | Prior | Now | Notes |
|-----------|-------:|------:|----:|-------|
| Evidence | 20% | 8.0 | **8.5** | Live C precision **0.727** clears B−0.05 and beats B (+0.34); single fixture pack caps |
| Goal fit | 20% | 8.5 | **9.0** | Useful gate under redacted enrich now shown (mean_hydrated 1.66, recall 0.95) |
| Runtime | 15% | 8.5 | **8.5** | Pin `jev-1.13.0`; RTT ~420/498 ms |
| Verification | 15% | 8.5 | **8.5** | Live 200s; remote Actions still unproven |
| Safety | 10% | 9.0 | **9.0** | No raw query; T held; allowlist expanded — still needs **human** redact review |
| License | 10% | 9.0 | **9.0** | unchanged |
| Maintainability | 10% | 8.0 | **7.5** | SCORECARD lower sections still claim C=0.0 / NON_PROMOTE; push blocked |
| **Weighted** | 100% | ~8.5 | **~8.6** | |

```text
0.20×8.5 + 0.20×9.0 + 0.15×8.5 + 0.15×8.5 + 0.10×9.0 + 0.10×9.0 + 0.10×7.5
= 1.70 + 1.80 + 1.275 + 1.275 + 0.90 + 0.90 + 0.75
= 8.60
```

---

## Bars check (David)

| Bar | Pre-reg | Observed | David |
|-----|---------|----------|-------|
| Precision C ≥ B−0.05 | ≈0.337 | **0.727** | **PASS** (also beats B; soft floor acknowledged) |
| Overshare ≤0.02 and ≤B | — | **0.0** | **PASS** |
| Fail-closed ≤0.05 | — | **0.0** | **PASS** |
| Escalate report | — | **0.028** | noted |
| No T-into-noise | hold 0.85/0.55 | held | **PASS** |
| No raw query | — | False | **PASS** |
| Acceleration | forbid | p95~498 | **not claimed** ✓ |

`intent_topic_fit` / `topic_family` / overlap are ontology + tag intersection — **no gold label in enrich path** (gold only in comments).

---

## Challenges (must track)

1. **Soft pre-reg precision floor** (B−0.05) was a recovery bar; do not reframe as beat-Hindsight / ≥9.5 evidence. Actual +0.34 vs B is the stronger claim — keep scoped to `personal_prefs`.
2. **P@k couples to selective hydrate** (`prec = hits/len(hydrated[:k])`); mean_hydrated 1.66 naturally lifts P. Mitigated by recall **0.95** + overshare 0 — say selective precision, not magic.
3. **Fixture-tuned needles / ontology** — transfer to other domains unproven.
4. **SCORECARD hygiene** — top table ~8.6 but lower LIVE snapshot still shows C=0.0 / NON_PROMOTE; fix before promote language in README.
5. Remaining ≥9.5 blockers: remote CI green, independent human redact, Leon sign-off; plus generalization if Evidence ≥9 wanted.

---

## Next gate

Fix SCORECARD stale sections → remote Actions green → independent redact review of expanded allowlist → Leon sign-off.  
Do **not** lower T_*; do **not** default raw query; do **not** claim ≥9.5.
