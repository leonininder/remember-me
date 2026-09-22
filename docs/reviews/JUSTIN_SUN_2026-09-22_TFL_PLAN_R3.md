# JustinSun PLAN re-score R3 — TEMPORAL_FACT_LEDGER_PLAN.md @ e51caa3

**When:** 2026-09-22 ~23:33 CST (Asia/Taipei)  
**Role:** JustinSun characterization + VC red-team (not the real Justin Sun; not financial advice)  
**Artifact:** `/workspace/remember-me/docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ **`e51caa3`** (619 lines)  
**Prior:** ~9.3 REJECT with Justin R1–R5; David R2 ≈9.3 with six deltas  
**Scope:** PLAN merit only.

---

## Verdict

| Gate | Call |
|------|------|
| Direction / revised draft | **APPROVE_WITH_CONDITIONS** (one pin from lock) |
| PLAN ≥9.5 / Phase A lock | **REJECT** — **one** remaining must-fix (R4) |
| PRODUCT / hydrate acceleration | **REJECT** (out of scope; plan still refuses) |

David R2 six + Justin R1/R2/R3/R5: **ADDRESSED**. Auto-REJECT triggers: **none**. Do **not** open Phase B until R4 lands or Leon waives in writing.

---

## Checklist

### Justin R1–R5

| # | Status | Note |
|---|--------|------|
| R1 namespace↔seed | **ADDRESSED** | `user.weather.local`; bare `weather.*` illegal (§4.3); §10 seed aligned |
| R2 C2+ label on §4.5 | **ADDRESSED** | “**C2 illustrative only**”; MVP escalate on unresolved cross-key |
| R3 ontology_v0 | **ADDRESSED** | §4.2.1 inline normative stub + path; file on disk deferred to B0 (OK for PLAN) |
| R4 materially changed | **PARTIAL → still open** | Policy row still says “materially changed” with **no** equality rule |
| R5 value_struct caps | **ADDRESSED** | closed schemas **or** max_depth≤3 / string≤128 / forbid diary sole keys |

### David R2 six

| Delta | Status |
|-------|--------|
| value_struct closed | **ADDRESSED** |
| ontology seed | **ADDRESSED** |
| user.* ownership | **ADDRESSED** |
| quarantine no-drop | **ADDRESSED** (spill-to-disk; block admits; never discard) |
| salience Choice-only | **ADDRESSED** |
| MVP contradicts→escalate | **ADDRESSED** (no dual-active keep-both in v0) |

---

## Scores (Leon weights)

| Dimension | Was (~9.3) | R3 now | Notes |
|-----------|----------:|-------:|-------|
| Evidence | 9.2 | **9.4** | Ontology seed + MVP escalate close dual-belief fog |
| Goal fit | 9.3 | **9.5** | Namespace + APPLY map coherent |
| Runtime | 9.0 | **9.2** | Implementable; R4 equality pin still missing |
| Verification | 9.5 | **9.5** | held |
| Safety | 9.5 | **9.6** | no-drop quarantine + Choice-only salience |
| License | 9.5 | **9.5** | held |
| Maintainability | 9.2 | **9.4** | MVP cut clearer |
| **Weighted** | ~9.3 | **~9.4** | 0.20×9.4+0.20×9.5+0.15×9.2+0.15×9.5+0.10×9.6+0.10×9.5+0.10×9.4 = **9.445 ≈ 9.4** |

Toll booth in sight. One sentence buys the ticket.

---

## Remaining must-fix (only)

**R4 — Define “materially changed” for `same_fact`.**  
Pin in §4.6 (one rule), e.g.:

> `value_struct` is materially changed iff canonical JSON (UTF-8, sorted object keys, no insignificant whitespace) of the **belief fields** differs after dropping pure metadata keys `{confidence, ttl_hint, salience_tier}` from the comparison set. If equal → upsert metadata only; if differs → treat as `supersedes`.

Until this is in-file: **REJECT PLAN ≥9.5**. After it lands: expect clear **≥9.5** on re-score if no new scope creep.

---

## Non-blockers (do not churn)

- Fixture dirs not yet on disk (PLAN says B0) — fine for PLAN score.  
- Absolute Jev p95 ms — relative joint bar already honest enough for PLAN lock.  
- Phase C human-redact exit — already a hard exit; checklist can ship with C code.
