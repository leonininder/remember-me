# David — TFL PLAN re-score R3 (2026-09-22 ~23:33 CST)

**Doc:** `docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ `e51caa3`  
**Scope:** PLAN quality only — not product ≥9.5.

---

## R2 remaining six → status

| # | Must-fix | Status |
|---|-----------|--------|
| 1 | Close `value_struct` (ontology schemas / caps / forbid prose keys) | **DONE** (§4.2 rules + §4.2.1 schemas `additionalProperties: false`) |
| 2 | Seed ontology path + inline | **DONE** (`ontology_v0.json` stub) |
| 3 | Examples under `user.*` | **DONE** (bare `weather.*` illegal) |
| 4 | Quarantine forbid drop; spill; block+escalate | **DONE** (§4.8) |
| 5 | `salience_tier` Choice only | **DONE** |
| 6 | MVP contradicts×¬forget → escalate; §4.5 = C2 | **DONE** |

Hard auto-REJECT list: **PASS**.

---

## Verdict

**PASS — PLAN ≥9.5 (David).** Overall **9.5**.  
Phase A lock **from David**.  

**Still required for full PLAN lock per §6.A:** Justin ≥9.5 (or Leon written waive).  
**Before first Phase B code commit:** land editorial fix below (one-liner; no full re-score cycle if that is the only delta).

Do **not** treat this as product ≥9.5. Implementation evidence is a separate loop.

---

## Leon 10-pt (PLAN)

| Dimension | R2 | R3 | Notes |
|-----------|---:|---:|-------|
| Evidence | 9.5 | **9.5** | Live lessons + freeze + joint bar |
| Goal fit | 9.0 | **9.5** | Ontology + `user.*` ownership aligned |
| Runtime | 9.0 | **9.5** | Choice-only salience; quarantine closed |
| Verification | 9.5 | **9.5** | Suite/CI commitments intact |
| Safety | 9.0 | **9.5** | No drop; MVP dual-belief escalate |
| License | 9.5 | **9.5** | MIT + protocol seed |
| Maintainability | 9.5 | **9.5** | MVP B+C; schema_version |
| **Weighted** | ≈9.3 | **9.5** | |

```text
0.20×9.5 + 0.20×9.5 + 0.15×9.5 + 0.15×9.5 + 0.10×9.5 + 0.10×9.5 + 0.10×9.5
= 9.50
```

---

## Pre-Phase-B editorial (must land; not a new scoring round)

§10 protocol seed `candidate` currently has **duplicate keys**:

```json
"qualifier": "local",
"qualifier": null,
```

**Fix:** keep a single `"qualifier": "local"` (delete the null line). Normative JSON must parse.

Optional hygiene: add `schema/ontology_v0.json` to §5.3 fixture tree listing; bump review-trail header to cite R2/R3 notes.

---

## After dual PLAN lock

1. Issues for Phase B–F (MVP = B+C).  
2. Feature-flag Phase B; `tfl.yml` stubs.  
3. Re-score **implementation** separately.  
4. Independent human redact = Phase C exit (unchanged).
