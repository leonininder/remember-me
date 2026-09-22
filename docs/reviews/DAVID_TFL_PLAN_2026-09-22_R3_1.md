# David — TFL PLAN re-score R3.1 (2026-09-22 ~23:34 CST)

**Doc:** `docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ `07e0fb1`  
**Scope:** PLAN quality only.

---

## What R3.1 adds (vs David R3 @ `e51caa3`)

| Item | Status |
|------|--------|
| Justin R4 — canonical deep-equal “materially changed” | **DONE** (§4.6: UTF-8, sorted keys, whitespace stripped; compare `value_struct` only) |
| Justin R5 — `value_struct` ≤2 KiB canonical | **DONE** (§4.2 rules) |
| David R2 six (from R3) | Still **DONE** |
| David R3 editorial — §10 duplicate `qualifier` | **STILL OPEN** |

Hard auto-REJECT list: **PASS**.

---

## Verdict

**PASS — PLAN ≥9.5 (David).** Overall **9.5** (reaffirm; R3.1 does not regress).  

Phase A lock **from David** stands. Full dual lock still needs **Justin ≥9.5** (or Leon written waive) per §6.A.

**Phase B still blocked** until §10 protocol seed is valid JSON (editorial below). That is not a new scoring dimension — it is the same pre-B landing gate from R3, **not landed in R3.1**.

Not a product ≥9.5.

---

## Leon 10-pt (PLAN)

| Dimension | R3 | R3.1 | Notes |
|-----------|---:|-----:|-------|
| Evidence | 9.5 | **9.5** | unchanged |
| Goal fit | 9.5 | **9.5** | deep-equal closes same_fact→supersedes ambiguity |
| Runtime | 9.5 | **9.5** | 2 KiB + deep-equal sharpen implementability |
| Verification | 9.5 | **9.5** | unchanged |
| Safety | 9.5 | **9.5** | size cap helps blob / diary pressure |
| License | 9.5 | **9.5** | unchanged |
| Maintainability | 9.5 | **9.5** | §10 typo still open for Phase B hygiene |
| **Weighted** | 9.5 | **9.5** | |

---

## Pre-Phase-B gate (unchanged; still red)

§10 `candidate` still contains:

```json
"qualifier": "local",
"qualifier": null,
```

**Fix:** keep only `"qualifier": "local"`.  
Land this one-liner on main before any Phase B code. No new David re-score needed if that is the only delta.

Optional: add `schema/ontology_v0.json` to §5.3 fixture tree; update review-trail header to cite R3 / R3.1 notes.

---

## Addendum (same day ~23:34 CST)

- Verified on `f955505` (R3.2): §10 candidate keeps only `"qualifier": "local"` — **pre-Phase-B editorial CLOSED**.
- FYI: Justin also PASS ≥9.5 → **full Phase A dual lock**. Phase B may open.
- Still **not** product ≥9.5; implementation evidence remains a separate loop; Phase C human-redact exit unchanged.
