# JustinSun PLAN score — TEMPORAL_FACT_LEDGER_PLAN.md

**When:** 2026-09-22 ~23:28 CST (Asia/Taipei)  
**Role:** JustinSun characterization + VC red-team (not the real Justin Sun; not financial advice)  
**Artifact:** `/workspace/remember-me/docs/plans/TEMPORAL_FACT_LEDGER_PLAN.md` @ tip `53a4d17` (221 lines)  
**Scope:** **PLAN merit only** — not a shipping / product ≥9.5 claim.  
**Context noted:** remember-me PREVIEW/AWC ~8.6 + Leon sign-off 2026-09-22; independent redact review still open.

---

## Verdict

| Gate | Call |
|------|------|
| Direction / working draft | **APPROVE_WITH_CONDITIONS** (worth iterating) |
| PLAN ≥9.5 / lock Phase A | **REJECT** until must-fixes land |
| PRODUCT / acceleration / SaaS cosplay | **REJECT** (out of scope; plan correctly refuses hydrate-speed myth) |

Does **not** trip plan §8 auto-REJECT list (no hydrate acceleration claim; forget present; fail-closed write; eval bars; ledger SoT is structured apply, not free-text LLM rewrite). Still **short of ≥9.5** on implementability + verification sharpness.

---

## Scores (Leon weights — PLAN rubric)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **8.5** | Live remember-me lesson cited; falsifier table real; gold suite size / judge baseline / joint quality+latency still soft |
| Goal fit | 20% | **9.0** | Belief-update engine + correct Jev role + concrete “protocol not slogan”; extractor/ontology holes blunt 9.5 |
| Runtime | 15% | **8.0** | Sketch fits remember-me stack; FactKey, extract, merge, cost underbuilt |
| Verification | 15% | **8.5** | Pre-reg metrics good; missing suite N, splits, CI job map, co-bars |
| Safety | 10% | **8.5** | Fail-closed write + redact + escalate; extract injection / poisoned incumbents / clock skew absent |
| License | 10% | **9.0** | MIT + open protocol intent |
| Maintainability | 10% | **8.0** | Phases A–F clear; md→ledger migration + protocol stub thin |
| **Weighted** | 100% | **~8.5** | 0.20×8.5+0.20×9.0+0.15×8.0+0.15×8.5+0.10×8.5+0.10×9.0+0.10×8.0 = **8.525 ≈ 8.5** |

Bridge metaphor: the destination (forget well) is right; the blueprints still leave the on-ramp (extract + keys) and the speed trap (latency-vs-judge) half-drawn.

---

## What already clears the honesty bar

1. Problem = missing belief-update engine, not bigger window.  
2. Jev = reconcile/forget/upsert gate on structured pairs — not chat dump, not hydrate accelerator.  
3. Fail-closed on **write**; redaction-first; forget as success metric.  
4. Pre-registered falsifiers + explicit non-metric (hydrate speed).  
5. Humanity contribution = open protocol + fixtures, not star theater.  
6. PLAN score ≠ PRODUCT score; non-goals listed.

---

## Must-fixes for PLAN ≥9.5 (ordered)

1. **Specify `CandidateFact` + FactKey minting** — JSON schema fields; deterministic key rules (`entity.attribute[.qualifier]`); who may invent keys; ban silent LLM free-text as ledger SoT even at extract (LLM may propose struct; code validates enum/schema or quarantine).  
2. **Cross-key contradiction policy** — when embedding-neighbor / same-day weather keys conflict; single normative example beyond same-FactKey supersede.  
3. **Complete question pack ↔ actions** — map `relation` (+ any new salience question) → `upsert|supersede|merge|expire|tombstone|escalate`; either define `merge` or drop it from APPLY list; add salience/childhood→adult path (insects example currently invents `salience_shift` without a question).  
4. **Joint latency+quality bar** — name LLM-as-judge baseline (model, prompt hash, n pairs, hardware class); require **both** p95 beat **and** wrong-supersession ≤2% (or plan fails); forbid “slow judge makes Jev look fast.”  
5. **Eval suite contract** — min labeled pairs per class; train/held-out if any threshold tune; publish fixture layout in-plan (`memorybench_tfl/` stub tree).  
6. **Proactive profile metric** — one pass/fail for session-start inject (precision@k or “stale FactKey in profile = 0”).  
7. **Cost / token budget** — reconcile-per-event usage cap or batching rule (cite remember-me ~155k-in/50q as warning).  
8. **Threat notes (short)** — prompt-injected CandidateFact; poisoned incumbent; clock skew on `valid_from`; fail-closed behavior for each.  
9. **Migration non-goal or path** — one subsection: import `MEMORY.md` → CandidateFacts (manual / scripted) **or** explicit v0 non-goal.  
10. **Protocol stub in-plan** — minimal normative JSON for one weather supersession + question ids (Phase F can expand; ≥9.5 needs a seed, not only a future filename).  
11. **CI wiring** — which jobs gate Phase B property tests / Phase D harness on main (even if “planned jobs,” name them).

After these land in-file, request re-score. Do **not** start large Phase B–F code under a <9.5 PLAN unless Leon waives in writing (plan §6.A).

---

## Non-blockers (nice later)

- Video IDs as citations are fine; no need for full transcripts.  
- Pin `jev-1.13.0` already correct.  
- Independent redact human review (remember-me leftover) stays open and applies to TFL state design too — not a PLAN≥9.5 substitute.

