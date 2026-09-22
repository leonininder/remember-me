# JustinSun PLAN re-score — TEMPORAL_FACT_LEDGER_PLAN.md @ 9aaf9ae

**When:** 2026-09-22 ~23:31 CST (Asia/Taipei)  
**Role:** JustinSun characterization + VC red-team (not the real Justin Sun; not financial advice)  
**Artifact:** `/workspace/remember-me/docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ **`9aaf9ae`** (553 lines)  
**Prior:** ~8.5 REJECT (≥9.5) with must-fixes 1–11  
**Scope:** PLAN merit only — not product shipping.

---

## Verdict

| Gate | Call |
|------|------|
| Direction / revised draft | **APPROVE_WITH_CONDITIONS** (strong iterate — almost lockable) |
| PLAN ≥9.5 / Phase A lock | **REJECT** — remaining gaps below (short list) |
| PRODUCT / hydrate acceleration | **REJECT** (plan correctly refuses) |

Prior must-fixes **1–11: ADDRESSED** in-file. Auto-REJECT §11 triggers: **none**. Still **~9.3**, not ≥9.5, because namespace/ontology consistency and a few sharpness holes remain.

---

## Checklist vs prior Justin 1–11

| # | Item | Status |
|---|------|--------|
| 1 | CandidateFact + FactKey minting; ban prose SoT | **ADDRESSED** (§4.2–4.3) |
| 2 | Cross-key policy + worked example | **ADDRESSED** (§4.5) — see remaining #R2 on MVP label |
| 3 | APPLY map + salience; drop merge | **ADDRESSED** (§4.6; merge non-goal) |
| 4 | Joint latency+quality vs named judge | **ADDRESSED** (§5.2: `openai/gpt-4o-mini`, n≥200, both bars) |
| 5 | Suite N / splits / fixture stub | **ADDRESSED** (§5.3: ≥250, 20% holdout, tree) |
| 6 | Profile inject metric | **ADDRESSED** (§5.4: stale=0; ≤1500 p50) |
| 7 | Token/cost budget | **ADDRESSED** (§4.7: ≤3k; K=5; ≤3/turn) |
| 8 | Threat notes | **ADDRESSED** (§4.9) |
| 9 | md migration / non-goal | **ADDRESSED** (§7; B0 → quarantine) |
| 10 | Protocol seed JSON | **ADDRESSED** (§10) — see remaining #R1 |
| 11 | CI job names | **ADDRESSED** (§8: `tfl.yml` jobs) |

David-oriented extras (QuarantineQueue, MVP B+C, redact exit, taxonomy): present and helpful.

---

## Scores (Leon weights)

| Dimension | Was | Now | Notes |
|-----------|----:|----:|-------|
| Evidence | 8.5 | **9.2** | Live lessons primary; joint bars; suite freeze contract |
| Goal fit | 9.0 | **9.3** | APPLY/FactKey complete; seed↔namespace clash blocks 9.5 |
| Runtime | 8.0 | **9.0** | Implementable; starter ontology enum still missing |
| Verification | 8.5 | **9.5** | Metrics + freeze + CI names + ≥250 |
| Safety | 8.5 | **9.5** | Named allowlists + taxonomy + threats + Phase C human-redact exit |
| License | 9.0 | **9.5** | MIT + protocol seed |
| Maintainability | 8.0 | **9.2** | MVP cut + schema_version; “materially changed” soft |
| **Weighted** | ~8.5 | **~9.3** | 0.20×9.2+0.20×9.3+0.15×9.0+0.15×9.5+0.10×9.5+0.10×9.5+0.10×9.2 = **9.295 ≈ 9.3** |

Almost at the toll booth. One tight revise should clear — do not pretend you already paid.

---

## Remaining must-fixes for PLAN ≥9.5 (short)

1. **R1 — Namespace ↔ seed alignment.** §4.3 limits entity prefixes to `user|home|agent|quarantine`, but §10 seed uses `"entity": "weather"`. Either extend allowlisted entities to include domain nouns (`weather`, `insects`, …) **or** rewrite all examples/seeds to `home.weather.local` / `user.insects.play`. Same rule everywhere.

2. **R2 — Label §4.5 worked example as Phase C2+.** MVP C1 is same-FactKey only; the sunny/rainy *different keys* example needs an explicit “C2+ only” banner so implementers do not build neighbor TopicIndex in MVP.

3. **R3 — Starter ontology freeze.** Add `ontology_v0` closed enum (or commit path `fixtures/.../ontology.yaml` + freeze-id) covering at least weather / insects / address / preference attributes used in examples. “Allowlist” without a list is still fog.

4. **R4 — Define “materially changed”.** For `same_fact` → supersedes when `value_struct` changes: pin rule (e.g. canonical JSON deep-equal after key sort; ignore pure confidence/TTL fields).

5. **R5 — Cap `value_struct`.** `additionalProperties: true` still allows fat blobs. Add max depth + max bytes (e.g. depth ≤4, ≤2 KiB) and restate ban on diary-only shapes.

After R1–R5 land in-file, request re-score. Expect clear path to **≥9.5** if no new scope creep.

---

## Explicit non-issues (do not churn)

- Pin `jev-1.13.0` + judge model name: good.  
- Videos demoted to Appendix A: good.  
- PRODUCT ≠ PLAN: good.  
- No hydrate acceleration claim: good.
