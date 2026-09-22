# David — Phase C independent human redact review

**Date:** 2026-09-22 23:53 CST (Asia/Taipei)  
**Reviewer:** David (Leon’s standards / security gatekeeper lens)  
**Tree:** `/workspace/remember-me` @ `5fab570`  
**Scope:** Phase C **exit** — `RECONCILE_STATE_ALLOWLIST` + `ESCALATION_SNAPSHOT_ALLOWLIST` only.  
**Not in scope:** PRODUCT ≥9.5; hydrate acceleration; Phase D bake-off.

**Evidence read:** `src/remember_me/tfl/redact.py`, `drain.py`, `quarantine.py`, `reconcile.py` (assert-before-POST), `tests/tfl/test_reconcile_redact.py`, `test_reconcile_chaos.py`, `docs/PHASE_C_NOTES.md`, `docs/reviews/PHASE_C_LIVE_SMOKE_2026-09-22.json`, checklist.  
**Tests run:** `.venv/bin/pytest -q tests/tfl/test_reconcile_redact.py tests/tfl/test_reconcile_chaos.py` → green.

---

## Checklist 1–7

| # | Item | Verdict |
|---|------|---------|
| 1 | Reconcile outbound ⊆ named allowlist | **PASS** |
| 2 | Escalation = reconcile + documented extras only | **PASS** |
| 3 | No diary/body/prose/notes/email/phone/street as outbound key / active belief path | **PASS** (see residual A) |
| 4 | `clip_value_struct` + caps fail closed → stub_hash under adversarial | **PASS** |
| 5 | HttpJev chaos never APPLY on 401/403/429/timeout/malformed | **PASS** |
| 6 | Quarantine drain never md-appends; never drops on escalate | **PASS** |
| 7 | Residual risks recorded | **PASS** |

**Overall Phase C redact exit: PASS**

---

## Findings (evidence)

1. **Positive allowlist SoT:** `RECONCILE_STATE_ALLOWLIST` matches PLAN §4.7 exactly; envelope is only `new` + `incumbents`. `allowlist_snapshot` strips extras (`email`, `content`, `secret`, …) before gate.
2. **Escalation extras** are explicit in frozenset (`source_event_id`, `extract_method`, `quarantine_reason`, `relation`, `apply_action`, `gate_error`, `incumbent_version_id`, `candidate_*`) — documented; not an open denylist.
3. **`clip_value_struct`:** drops `_FORBIDDEN_VALUE_KEYS`; truncates long strings; on cap fail returns `{_clipped, stub_hash}` (verified nested depth → stub_hash).
4. **Outbound assert:** `FakeJevReconcileGate`, `HttpJevReconcileGate`, and `ReconcileEngine` call `assert_reconcile_outbound_safe` before use/POST.
5. **Chaos:** 401/403/429/timeout/invalid_json/missing_answers → `ApplyAction.QUARANTINE`, `applied=False`, ledger active count 0.
6. **Drain / quarantine:** spill-only overflow; block+escalate when spill exhausted; `_requeue` never writes MEMORY/AGENTS; drain requeues on escalate (never drop).

Live smoke (`PHASE_C_LIVE_SMOKE_2026-09-22.json`): outbound keys ⊆ allowlist shape (`new`/`incumbents` + allowlisted fields).

---

## Residual risks (track; not Phase C blockers)

| ID | Risk | Severity | Suggested follow-up |
|----|------|----------|---------------------|
| A | Value-key posture is **denylist** (`_FORBIDDEN_VALUE_KEYS`). Keys like `message` / `transcript` / `summary` still clip through if caps OK. Ontology admit path mitigates for seeded attrs; quarantine / future attrs less so. | Med | Prefer per-attribute value-key allowlist from ontology on outbound; expand forbidden list short-term (`message`, `transcript`, `summary`, `raw`, `query`). |
| B | Secret-like substrings inside **allowed** string values (`sk-…` in `condition`/`stance`) are caught by `assert_reconcile_outbound_safe` as **AssertionError**, not mapped to quarantine. Fail-closed intent is quarantine, not crash. | Low–Med | Catch `AssertionError` in engine → `QUARANTINE` + audit reason `outbound_unsafe`. |
| C | Spill items are not auto-drained (by design) — human/explicit load required; ops must not “clean” spill by deleting files. | Low | Document ops runbook in Phase C notes / drain CLI. |
| D | Email heuristic (`@` + `.`) may false-positive; secret marker list is incomplete (`AKIA`, `ghp_`, etc.). | Low | Expand markers; keep fail-closed bias. |

---

## Sign-off

| Role | Name | Date (Asia/Taipei) | Verdict |
|------|------|--------------------|---------|
| Independent redact reviewer | **David** | **2026-09-22** | **PASS** |

Phase C exit criterion (PLAN §6): **satisfied** on redact allowlists.  
**Do not** treat this as PRODUCT ≥9.5. Phase D / product loops remain separate.
