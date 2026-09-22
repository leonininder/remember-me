**Phase C exit:** CLOSED 2026-09-22 (David redact PASS).

# TFL Phase C — JevReconcileGate (implementation notes)

**Date:** 2026-09-22 (Asia/Taipei)  
**Scope:** PLAN §6 Phase C / §4.6–§4.8 — **not** a PRODUCT ≥9.5 claim; **not** an acceleration claim.  
**Parent tip before this work:** `a9d59f9` (Phase B ledger MVP).

## What landed

| Piece | Location |
|-------|----------|
| `RECONCILE_STATE_ALLOWLIST` + TFL `ESCALATION_SNAPSHOT_ALLOWLIST` | `src/remember_me/tfl/redact.py` |
| Question pack (Choice=dict criteria; Score=string levels; pin `jev-1.13.0`) | `src/remember_me/tfl/questions.py` |
| APPLY policy table (no merge; C1 same-FactKey; contradicts×¬forget → escalate) | `src/remember_me/tfl/policy.py` |
| `FakeJevReconcileGate` + `HttpJevReconcileGate` + `ReconcileEngine` | `src/remember_me/tfl/reconcile.py` |
| Quarantine drain ↔ retry / escalate_human (never md-append, never drop) | `src/remember_me/tfl/drain.py` |
| CI job `tfl-reconcile-unit` | `.github/workflows/tfl.yml` (enabled) |

## Thresholds

- `T_accept` / `T_escal` = **0.85 / 0.55** (`T_ACCEPT_RECONCILE` / `T_ESCALATE_RECONCILE`) unless held-out evidence later.
- `should_forget_incumbent` treated true only at Noul ≥ T_accept.
- `needs_human` treated true at Noul ≥ T_escal → always escalate_human.

## C1 vs C2

- **C1 (this phase):** same-FactKey incumbents only (K≤5 still honored for shape).
- **C2 deferred:** ontology/embedding neighbors — not implemented; cross-key auto-apply is non-goal until embed model pinned.

## Fail-closed

Gate deny / timeout / malformed / unavailable → `ApplyAction.QUARANTINE` + enqueue.  
Never silent ledger APPLY. Never MEMORY.md / AGENTS.md append fallback.

## Exit criterion (human — not automated)

Phase C **does not close** until independent **human redact review** of the two allowlists passes.  
See checklist: `docs/reviews/PHASE_C_HUMAN_REDACT_CHECKLIST.md`.  
Do **not** fake Leon (or any reviewer) sign-off in-repo.

## Non-claims

- No PRODUCT ≥9.5.
- No “Jev accelerates memory retrieval / hydrate.”
- Joint latency+quality bakeoff remains Phase D.
