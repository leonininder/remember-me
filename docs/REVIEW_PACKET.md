# Review packet — Dual-gate Phase 9.5 (David + Justin Sun)

**For:** David · Justin Sun  
**From:** Leon (remember-me Pre-Skill)  
**Date:** 2026-09-21 (CST / Asia/Taipei)  
**Package:** `/workspace/remember-me` v0.1.0 · card `PS-REMEMBER-ME-2026-09-19`  
**Plan:** [PHASE_9_5_PLAN.md](PHASE_9_5_PLAN.md) · [DUAL_GATE.md](DUAL_GATE.md)

---

## One-liner

**Local candidates first. Jev never ranks. Jev only admits.**

---

## What landed (offline-verifiable)

1. **Dual-gate egress** — `decide_emit` + `decide_writeback` on `JevClient` / FakeJev / HttpJev; `EmitEgressGate` + `WritebackGate`; `MemoryPipeline.run_egress` / `run_dual` / `DualGatePipeline`.
2. **First-class `escalate_human`** — on ingress mid-band + conflicts; `EscalationRecord` + `escalate_human()` helper; `PipelineResult.escalations`.
3. **Fan-out defaults** — `FANOUT_DEFAULTS` frozen; batch multi-candidate × multi-question in one call.
4. **No-rerank proofs** — `assert_no_rerank` + `tests/test_no_rerank.py`.
5. **CLI** — `remember-me demo` / `demo-dual` print ingress actions + egress decision.
6. **CI** — `.github/workflows/ci.yml` (pytest + ruff on 3.11–3.13).
7. **pyproject URLs** — `leonininder/remember-me`.

**Pytest:** green offline suite (see SCORECARD for count at freeze). FakeJev only — **not** live TypeSafe proof.

---

## Leon 10-pt dimensions (honest PREVIEW)

| # | Dimension | Score | Notes for reviewers |
|---|-----------|------:|---------------------|
| 1 | Evidence | **7.5** | David correction: FakeJev bake-off NON-EVIDENCE (conf∝local_score); no live logs |
| 2 | Goal fit | **9.0→~9.2 intent** | Dual egress + escalate_human + no-rerank now coded; keep advertised Goal fit **≤9.0** until live |
| 3 | Runtime | **8.0→~8.5 intent** | CLI dual demo + fan-out defaults; HttpJev still unproven live |
| 4 | Verification | **8.5** | Real HttpJev HTTP chaos offline; remote CI on main not claimed (David) |
| 5 | Safety | **9.0** | Allowlist EscalationRecord + GateAuditRecord store + adversarial redact (David) |
| 6 | License | **9.0** | MIT unchanged |
| 7 | Maintainability | **7.5→~8.5 intent** | **CI added**; docs DUAL_GATE + REVIEW_PACKET |

**Weighted overall (honest freeze):** still **~8.4–8.6 PREVIEW**. **Do not score ≥9.5** without live pilot + Leon sign-off. SCORECARD remains ≤8.5 advertised until Evidence moves.

---

## What to verify (checklist)

### David

- [ ] Emit/writeback never silent-allow on timeout/403/malformed  
- [ ] `EscalationRecord` is allowlisted (no `content` / secrets) — partial answer to P1 gate-audit  
- [ ] Default hydrate path unchanged when egress gates off  
- [ ] No dead CI badge / Homepage wrong-owner  
- [ ] SCORECARD not inflated past PREVIEW ceiling  

### Justin Sun

- [ ] No theater: `jev_called` still asserted; FakeJev ≠ product proof labeled  
- [ ] Fail-closed red lines intact (redaction, orphan hydrate forbidden)  
- [ ] No accelerate / beat-Hindsight language in new docs  
- [ ] Library + CLI only — not a drop-in Claude/Codex/Hermes plugin claim  
- [ ] No-rerank tests green; Jev is not a similarity ranker  

### Shared 10 success criteria (PHASE_9_5_PLAN §5)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Dual-gate egress fail-closed | **PASS** offline |
| 2 | No silent durable write | **PASS** (`require_writeback` + mid-band escalate) |
| 3 | Structured escalate_human | **PASS** |
| 4 | Fan-out defaults frozen | **PASS** |
| 5 | No-rerank proven | **PASS** |
| 6 | Redaction extended | **PASS** offline |
| 7 | Hydrate path not theater | **PASS** |
| 8 | Honesty / no acceleration | **PASS** (SCORECARD PREVIEW) |
| 9 | FakeJev labeled | **PASS** |
| 10 | Review packet | **THIS FILE** |

---

## Remaining blockers to honest ≥9.5

**Offline closes (2026-09-21):** see [REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md](REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md) —
HTTP 401/403/429 chaos, GateAuditRecord store, EscalationRecord positive allowlist,
adversarial redaction, FakeJev bake-off labeled NON-EVIDENCE. David overall **≈8.2**.

Still open:

1. Live TypeSafe hydrate/emit call logs (pin `jev-1.13.0`) on personal-prefs only  
2. Remote CI green on `main` (workflow file present; do not claim until remote green)  
3. Dual-track bake-off under live RTT budget (FakeJev bake-off is non-evidence)  
4. Leon formal sign-off  

---

## Suggested verdict language

`APPROVE_WITH_CONDITIONS` — Phase 9.5 **API + offline proofs** land; keep PREVIEW / Pre-Skill; **REJECT** any ≥9.5 or acceleration narrative until live Evidence closes.

---

*Packet generated for priority re-review. Source tree: `/workspace/remember-me`.*
