# David — TFL PLAN re-score R2 (2026-09-22 ~23:31 CST)

**Doc:** `docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ `9aaf9ae`  
**Scope:** PLAN quality only.

---

## Checklist vs David must-fix 1–12

| # | Item | Status |
|---|------|--------|
| 1 | CandidateFact + LLM propose-only | **Mostly** — schema present; `value_struct.additionalProperties: true` still open |
| 2 | FactKey caps / normalize | **Done** |
| 3 | APPLY ↔ Choice (no merge) | **Done** |
| 4 | Eval freeze / SHA / N / holdout | **Done** |
| 5 | K-cap + allowlists named | **Done** |
| 6 | QuarantineQueue (no md-append) | **Mostly** — overflow allows drop-with-audit |
| 7 | MVP = B+C | **Done** |
| 8 | Human redact = Phase C exit | **Done** |
| 9 | ledger_schema_version + md import | **Done** |
| 10 | Per-turn cost | **Done** |
| 11 | needs_human taxonomy | **Done** |
| 12 | Videos → Appendix A | **Done** |

Hard auto-REJECT list: still **PASS**.

---

## Verdict

**REJECT PLAN ≥9.5** — close, not locked.  
**Overall ≈9.3** (prior ≈8.7).

Do **not** open Phase B until remaining must-fixes land (or Leon waives in writing).

---

## Leon 10-pt (PLAN)

| Dimension | Prior | Now | Notes |
|-----------|------:|----:|-------|
| Evidence | 8.5 | **9.5** | Live lessons primary; freeze + joint bar |
| Goal fit | 9.0 | **9.0** | Ontology seed + entity ownership vs `weather.*` still fuzzy |
| Runtime | 8.5 | **9.0** | salience Choice-or-Score; value_struct hole |
| Verification | 8.5 | **9.5** | Suite N, freeze-id, tfl.yml jobs, joint bar |
| Safety | 8.5 | **9.0** | Quarantine drop; dual-belief edge on contradicts×¬forget |
| License | 9.0 | **9.5** | MIT + protocol seed |
| Maintainability | 8.5 | **9.5** | MVP cut + schema_version + non-goals |
| **Weighted** | ≈8.7 | **≈9.3** | |

```text
0.20×9.5 + 0.20×9.0 + 0.15×9.0 + 0.15×9.5 + 0.10×9.0 + 0.10×9.5 + 0.10×9.5
= 1.90 + 1.80 + 1.35 + 1.425 + 0.90 + 0.95 + 0.95
= 9.275 ≈ **9.3**
```

---

## Remaining must-fixes (short)

1. **Close `value_struct`** — Prefer per-attribute value schemas (seed weather/insects) with `additionalProperties: false`, **or** hard caps: max_depth≤3, max_string≤128, forbid sole `text`/`body`/`prose`/`diary` keys for admit. Schema must enforce what prose rules claim.

2. **Seed ontology in-PLAN** — Path `fixtures/memorybench_tfl/schema/ontology_v0.json` (or inline enum) listing v0 entities/attributes used in examples (`weather.local`, `insects.play`, `insects.safety`, …). “Allowlisted” must not be vapor.

3. **Entity ownership vs examples** — Extend ownership prefixes to domain entities (`weather.*`, `insects.*`) **or** rewrite all examples/protocol seed under `user.weather.local` / `user.insects.*`.

4. **Quarantine overflow** — **Forbid drop**. Spill-to-disk only; when full → block new auto-admits + escalate_human (audit). Never discard CandidateFacts silently.

5. **Pin `salience_tier` = Choice only** for v0 (drop “or Score”).

6. **MVP dual-belief edge** — Mark §4.5 neighbor worked example as **C2 illustrative**. For C1/MVP: `contradicts` × `should_forget=false` → **always escalate_human** (delete “keep both active if different keys…” row for v0).

---

## Credit (do not regress)

Anti-acceleration; forget-as-success; fail-closed + quarantine; propose-only LLM; joint latency+quality; Phase C human-redact exit; protocol seed; tfl.yml named jobs.
