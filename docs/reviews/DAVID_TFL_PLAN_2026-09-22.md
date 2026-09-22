# David — TFL PLAN score (2026-09-22 ~23:28 CST)

**Doc:** `docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` (main + local)  
**Scope:** **PLAN quality only** — not product ≥9.5; not remember-me AWC re-open.  
**Context FYI:** Leon PREVIEW/AWC sign-off `3a5d6b1` noted; independent redact still open on product track.

---

## Auto-REJECT checklist (hard)

| Forbidden | Present in PLAN? | Result |
|-----------|------------------|--------|
| Jev accelerates hydrate | Explicitly rejected; cites enrich v2 falsify | PASS |
| Unbounded md as SoT | Problem + non-goal; ledger replaces dump | PASS |
| LLM free-text as ledger SoT | Intent OK; **extractor underspec** → soft risk | PASS (with must-fix) |
| Omits forget | TTL / tombstone / should_forget | PASS |
| Omits fail-closed write | Stated | PASS |
| Omits eval bars | §5 table | PASS |

→ **No hard auto-REJECT.** Soft gaps still block PLAN ≥9.5.

---

## Verdict

**REJECT PLAN ≥9.5** until must-fix below land in the PLAN text.  
**PLAN overall ≈8.7** — strong direction; not lock-ready.

Do **not** start Phase B–F as if PLAN locked.

---

## Leon 10-pt (PLAN)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **8.5** | Good remember-me falsify cite; video “synthesis” thin; bars lack N/SHA/label protocol |
| Goal fit | 20% | **9.0** | Right problem + Jev-as-reconcile; FactKey/`merge`/extractor still fuzzy |
| Runtime | 15% | **8.5** | Stack-fit OK; embeddings + offline quarantine + cost bounds missing |
| Verification | 15% | **8.5** | Bars exist; need freeze-id, holdout, CI job stub, reconcile chaos |
| Safety | 10% | **8.5** | Fail-closed + redact + escalate; need reconcile allowlist, K-cap, human-redact as Phase C gate |
| License | 10% | **9.0** | MIT + open protocol intent |
| Maintainability | 10% | **8.5** | Non-goals good; need MVP cut, schema_version, md-import one-shot |
| **Weighted** | 100% | **≈8.7** | |

```text
0.20×8.5 + 0.20×9.0 + 0.15×8.5 + 0.15×8.5 + 0.10×8.5 + 0.10×9.0 + 0.10×8.5
= 1.70 + 1.80 + 1.275 + 1.275 + 0.85 + 0.90 + 0.85
= 8.65 ≈ **8.7**
```

---

## Must-fix (concrete PLAN edits)

1. **CandidateFactExtractor contract** — Define `CandidateFact` schema (closed fields/enums). Rule in PLAN: LLM may *propose* only; **validator + allowlist** before gate; **never** persist free-text diary as `value_struct`; reject unknown keys.

2. **FactKey specification** — Canonicalization (entity/attribute/normalize), collision policy, multi-value attributes, namespace/ownership, max active keys per entity.

3. **Align APPLY ↔ Jev Choice** — Either add `merge` to `relation` Choice or remove `merge` from APPLY. Define `side_thread` → new FactKey vs no-op. Define `same_fact` → bump salience/TTL only (no dual row).

4. **Eval freeze block** — Add `freeze-id`, fixture SHA, N, labeling guide for “wrong supersession,” contradiction denominator definition, 30/20-style calibrate/holdout, pass/fail owners.

5. **Incumbent bounds + redact allowlist** — Max K incumbents to Jev (local rank only); field/token caps; `ESCALATION_SNAPSHOT_ALLOWLIST` / reconcile outbound allowlist named in PLAN.

6. **QuarantineQueue (fail-closed offline)** — When Jev deny/timeout/malformed/unavailable: enqueue bound-size quarantine; **no** md-append fallback; drain rules + escalate_human.

7. **MVP cut line** — Phase B+C must alone falsify §5 size + dual-active + fail-closed before ProfileCompiler/blog. Defer `embedding-neighbor` or pin local embed model + non-goal until C2.

8. **Safety phase gate** — Independent human redact of reconcile allowlist = **Phase C exit**; not only §9 reminder.

9. **Schema version + md import** — `ledger_schema_version`; optional Phase B0 one-shot md→facts import; after import, md is **not** write SoT.

10. **Cost / rate policy** — Max reconciles per event/turn; batching; budget abort → escalate/quarantine, never silent drop-or-append.

11. **`needs_human` closed taxonomy** — Enum (medical/legal/identity/financial/minors/…) → deny_write vs escalate map in PLAN.

12. **Demote video section** — Move YouTube IDs to appendix; keep lesson bullets tied to remember-me evidence as primary Evidence.

---

## What already earns credit (do not regress)

- Explicit anti-acceleration stance.  
- Forget / TTL / tombstone as success.  
- Fail-closed writes vs chat fail-open.  
- Jev mutation class + code apply.  
- Open protocol as contribution (concrete).  
- Separate PLAN score from product score.

---

## After must-fix

Revise PLAN in place → re-ping David (+ Justin). Only then Phase A lock → Phase B.
