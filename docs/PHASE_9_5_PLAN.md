# Phase 9.5 implementation plan — remember-me

**Status:** PLAN ONLY — do not implement in this freeze turn  
**Written:** 2026-09-21 (CST / Asia/Taipei)  
**Package freeze:** `/workspace/remember-me` v0.1.0 · card `PS-REMEMBER-ME-2026-09-19` / `freeze-2026-09-19-v1`  
**Baseline evidence:** offline FakeJev + pytest (see §0)  
**Review target:** David + Justin Sun 10-pt re-review after implementation

---

## 0. Baseline freeze (do not regress)

| Item | Value at plan write |
|------|---------------------|
| Weighted SCORECARD | **8.4** (Evidence 8.0 · Goal fit 9.0 · Runtime 8.0 · Verification 8.5 · Safety 8.5 · License 9.0 · Maintainability 7.5) |
| Promotion ceiling | PREVIEW / Pre-Skill; **do not claim ≥9.5 proven** until live evidence + Leon sign-off |
| Bake-off (FakeJev) | precision@k Δ ≈ +0.085; overshare Δ 0; p95 ~0.35 ms **local CPU** (`bakeoff_metrics.json`) |
| HttpJev contract | System One `POST /v1/systemone` + batch hydrate; **live still unproven** |
| Existing gates | `MemoryGate.evaluate` (hydrate) · `RetainAdmitGate.evaluate` (admit) · `policy.map_hydrate_action` |
| Pytest at plan start | **66 passed** (`pytest -q`, ~22:28 CST 2026-09-21) |
| Pytest at plan finalize | **64 passed, 2 failed** — concurrent shared-box edits already began landing `HydrateAction.ESCALATE_HUMAN` in `policy.py`/`types.py` before this plan-only turn finished; `test_mid_band_stubs` + `test_still_matters_false_downgrades` expect `stub_only`. **Plan-only executor did not author those src edits.** Reconcile tests vs API in the implementation turn. |

**Non-negotiables retained:** redaction allowlist; fail-closed; Jev ≠ store ≠ ranker; no accelerate/Hindsight marketing; synthetic fixtures only.

---

## 1. Current scores vs 9.5 gaps

Phase gate language in `SCORECARD.md` / Pre-Skill plan uses **≥9.5 as an exit target after listed evidence**, not a present score. Gap = what blocks an honest step toward that gate (and what David/Justin still condition on).

| Dimension | Now | 9.5-gate intent | Concrete gap for Phase 9.5 |
|-----------|----:|-----------------|----------------------------|
| Evidence | 8.0 | Live hydrate logs + dual-track bake-off | No live TypeSafe call log; FakeJev-only metrics |
| Goal fit | 9.0 | Dual egress gates + explicit human escalate + no-rerank proof | Hydrate/admit only; mid-band silently → `stub_only`; no emit/writeback API; no dedicated no-rerank test |
| Runtime | 8.0 | Installable + documented fan-out defaults | Fan-out flags exist (`optional_network` / `optional_reflect`) but **not** a frozen public defaults object / registry |
| Verification | 8.5 | Chaos beyond `force_*`; egress deny; no-rerank | Missing tests named below |
| Safety | 8.5 | Dual-gate egress fail-closed; DLP on writeback | No `decide_emit` / `decide_writeback`; no persistent GateAuditRecord (David P1) |
| License | 9.0 | Keep MIT + clean deps | No API work required |
| Maintainability | 7.5 | CI on main + question-ID registry completeness | Still **no `.github/` CI**; new Q IDs must land in `types.py` registry |

**Top 5 gaps (priority for this phase):**

1. **Dual-gate egress missing** — only hydrate (LLM inbound) + admit (store inbound); no first-class **emit** (outbound leave-local) / **writeback** (durable LTM/wiki) decisions.  
2. **`escalate_human` not first-class** — mid-band (0.55–0.85) collapses to `stub_only` without a structured human/policy handoff record.  
3. **Fan-out defaults not API-frozen** — batch `{node_id}__{qid}` works; default question set / optional toggles not exported as a single defaults contract.  
4. **No dedicated no-rerank regression** — architecture claims “Jev never ranks”; tests prove call/redact/fail-closed, **not** order/`local_score` invariance.  
5. **Live Evidence / CI still open** — blocks honest ≥9.0 advertising (David/Justin); Phase 9.5 ships the **API + offline proofs** first; live pilot remains a scored follow-on, not theater.

---

## 2. Exact APIs to add

### 2.1 Dual-gate egress — `decide_emit` + `decide_writeback`

**Product rule:** Hydrate answers “what may enter the LLM context?” Admit answers “what may enter the local graph?” Phase 9.5 adds the **egress** pair:

| API | Meaning | Fail-closed default |
|-----|---------|---------------------|
| `decide_emit(...)` | May this **redacted** payload leave the local boundary toward an external sink (TypeSafe already gated elsewhere; logs; agent channel; export)? | `deny_emit` |
| `decide_writeback(...)` | May this marker / promote / note be written to **durable** LTM / wiki / bank? | `deny_writeback` (aligns with “no silent LTM writes”) |

**Protocol extension** (`JevClient`):

```python
def decide_emit(
    self,
    *,
    sink: str,                          # e.g. "typesafe_systemone" | "audit_log" | "agent_channel"
    payload_meta: dict[str, Any],       # redacted metadata only
) -> JevBatchResponse: ...

def decide_writeback(
    self,
    *,
    target: str,                        # e.g. "graph_durable" | "wiki_stage" | "hindsight_bank"
    proposed: dict[str, Any],           # redacted: node_id, kind, tags, salience, horizon — NEVER body
) -> JevBatchResponse: ...
```

**New question IDs** (`types.py` registry):

| ID | Type | Closed criteria |
|----|------|-----------------|
| `emit_action` | Choice | `allow_emit` \| `deny_emit` \| `redact_further` \| `other` |
| `writeback_action` | Choice | `allow_writeback` \| `deny_writeback` \| `stage_only` \| `escalate_human` \| `other` |
| `writeback_need` (optional Score 1–5) | Score | same pattern as need_for_next_turn |
| `writeback_still_safe` (optional Noul) | Noul | yes ≈ durable write consideration |

**Gate classes** (`gates.py`):

- `EmitEgressGate.evaluate(sink, payload_meta) -> EgressDecision`
- `WritebackGate.evaluate(target, proposed) -> WritebackDecision`

Both: redact/assert_no_secrets → client call → policy map → `fail_closed=True` on timeout/deny/malformed.

**Policy helpers** (`policy.py`):

- `map_emit_action(response, *, t_accept=T_ACCEPT, t_escalate=T_ESCALATE) -> EgressDecision`
- `map_writeback_action(...) -> WritebackDecision`  
  Mid-band writeback → **`escalate_human`** (not silent allow). High-conf `allow_writeback` only when conf ≥ `T_ACCEPT` **and** optional Noul still_safe ≠ false.

**Pipeline hooks** (`pipeline.py`) — opt-in flags, default **off** so hydrate path stays unchanged:

- `MemoryPipeline(..., emit_gate: EmitEgressGate | None = None, writeback_gate: WritebackGate | None = None)`
- `observe(..., require_writeback: bool = False)` — if True, `WritebackGate` must `allow_writeback` (or stage_only) before `graph.observe` / `promote`
- `run` does **not** call emit/writeback unless explicitly configured (keeps hydrate critical path lean)

**Types** (`types.py`):

```python
class EmitAction(StrEnum): ...
class WritebackAction(StrEnum): ...  # includes ESCALATE_HUMAN

class EgressDecision(BaseModel):
    sink: str
    action: EmitAction
    confidence: float
    fail_closed: bool = False
    reason: str = ""

class WritebackDecision(BaseModel):
    target: str
    node_id: str
    action: WritebackAction
    confidence: float
    fail_closed: bool = False
    reason: str = ""
    escalation: EscalationRecord | None = None
```

---

### 2.2 `escalate_human`

**Problem today:** `map_hydrate_action` mid-band → `HydrateAction.STUB_ONLY` with reason `escalate conf=…` but **no structured handoff**.

**Add:**

```python
class EscalationRecord(BaseModel):
    node_id: str
    source_gate: str          # "hydrate" | "emit" | "writeback" | "admit"
    band: str                 # "mid" | "fail_closed" | "policy"
    confidence: float
    proposed_action: str      # raw / constrained action before human
    reason: str
    redacted_snapshot: dict[str, Any]  # allowlisted fields only

def escalate_human(
    *,
    node_id: str,
    source_gate: str,
    confidence: float,
    proposed_action: str,
    reason: str,
    redacted_snapshot: dict[str, Any],
    band: str = "mid",
) -> EscalationRecord: ...
```

**Wire-in:**

1. `policy.map_hydrate_action` — when `T_ESCALATE ≤ conf < T_ACCEPT`, still return `STUB_ONLY` for hydrate safety **and** attach `escalation: EscalationRecord` on `GateDecision` (new optional field).  
2. `map_writeback_action` — mid-band **primary** action = `WritebackAction.ESCALATE_HUMAN` (deny durable write until human/policy).  
3. `MemoryPipeline.run` — collect `result.escalations: list[EscalationRecord]` (new field on `PipelineResult`, default `[]`).  
4. FakeJev — no network; escalation is **local policy**, not a new cloud call (unless a future optional Choice is added; **out of scope** for 9.5).

---

### 2.3 Fan-out defaults

**Freeze a public defaults object** (single source of truth for System One question fan-out):

```python
# types.py or new fanout.py
@dataclass(frozen=True)
class FanOutDefaults:
    batch_candidates: bool = True
    include_raw_query: bool = False      # query_hash only
    optional_network: bool = False
    optional_reflect: bool = False
    core_hydrate_questions: tuple[str, ...] = (
        Q_HYDRATE_ACTION,
        Q_NEED_FOR_NEXT_TURN,
        Q_STILL_MATTERS,
    )
    core_admit_questions: tuple[str, ...] = (Q_ADMIT, Q_NODE_KIND)
    core_emit_questions: tuple[str, ...] = (Q_EMIT_ACTION,)
    core_writeback_questions: tuple[str, ...] = (Q_WRITEBACK_ACTION,)

FANOUT_DEFAULTS = FanOutDefaults()
```

**Wire-in:**

- `HttpJev` / `FakeJev` / `MemoryGate` / `MemoryPipeline` accept `fanout: FanOutDefaults | None = None` → default `FANOUT_DEFAULTS`.  
- `_hydrate_questions*` builds **only** core set + optionals when flags true.  
- Export `FANOUT_DEFAULTS` from `remember_me.__init__`.  
- Docs: one paragraph in `ARCHITECTURE.md` + cookbook pointing at `FANOUT_DEFAULTS`.

---

### 2.4 No-rerank contract (API + test)

**Invariant (code comment + test):**

> After local retrieve, candidate **order** and each candidate’s **`local_score`** are immutable through redact → Jev → policy. Jev may only emit per-node actions/confidences; it must not reorder, rescore, or drop-from-ranking the candidate list used for orphan checks.

**Helper** (optional, for clarity):

```python
def assert_no_rerank(
    before: list[Candidate],
    after_candidates: list[Candidate],
) -> None:
    """Raise AssertionError if node_id order or local_score changed."""
```

Used by tests (and optionally debug asserts behind env flag — **default off** in production path).

---

## 3. File-by-file edit list

| File | Change |
|------|--------|
| `src/remember_me/types.py` | Add `EmitAction`, `WritebackAction`, `EgressDecision`, `WritebackDecision`, `EscalationRecord`; extend `GateDecision.escalation`, `PipelineResult.escalations`; register `Q_EMIT_ACTION`, `Q_WRITEBACK_ACTION`, (+ optional score/noul IDs) |
| `src/remember_me/fanout.py` | **New** — `FanOutDefaults`, `FANOUT_DEFAULTS` |
| `src/remember_me/policy.py` | Add `escalate_human`, `map_emit_action`, `map_writeback_action`; mid-band hydrate attaches escalation |
| `src/remember_me/gates.py` | Add `EmitEgressGate`, `WritebackGate`; plumb `fanout` into `MemoryGate` |
| `src/remember_me/jev_client.py` | Extend `JevClient` Protocol + `FakeJev` + `HttpJev` with `decide_emit` / `decide_writeback`; honor `FANOUT_DEFAULTS` |
| `src/remember_me/pipeline.py` | Opt-in emit/writeback gates; `require_writeback` on observe; populate `escalations`; keep hydrate path default behavior identical |
| `src/remember_me/redact.py` | Allowlist helper for emit/writeback proposed dicts (reuse `assert_no_secrets`) |
| `src/remember_me/__init__.py` | Export new public symbols |
| `tests/test_policy.py` | Escalation + emit/writeback mapping cases |
| `tests/test_gates_pipeline.py` | Emit/writeback gates; escalations on pipeline; require_writeback |
| `tests/test_jev_client.py` | FakeJev `decide_emit` / `decide_writeback` + redaction |
| `tests/test_http_jev_mocked.py` | Mocked System One payloads for emit/writeback question shapes |
| `tests/test_no_rerank.py` | **New** — dedicated no-rerank suite |
| `tests/test_fanout_defaults.py` | **New** — defaults frozen + optional flags expand questions |
| `ARCHITECTURE.md` | Dual-gate egress diagram + fan-out defaults + escalate_human |
| `SECURITY.md` | Emit/writeback fail-closed + no body on writeback proposed |
| `docs/COOKBOOK.md` | Short egress / escalate examples (no live claims) |
| `SCORECARD.md` | After impl: note Phase 9.5 API landed; **keep ≤8.5** until live pilot (honesty) |
| `docs/PHASE_9_5_PLAN.md` | This file (plan); mark sections done only in a later turn |

**Explicitly out of scope for Phase 9.5 implementation turn:** live TypeSafe pilot, GitHub Actions CI, commercial Hindsight wiring, wiki sync script integration, SCORECARD bump above PREVIEW ceiling.

---

## 4. Test names to add

### Policy / escalate

- `test_escalate_human_builds_redacted_record`
- `test_mid_band_hydrate_attaches_escalation_and_stubs`
- `test_map_emit_action_fail_closed_denies`
- `test_map_emit_action_accept_allows`
- `test_map_writeback_mid_band_escalates_human`
- `test_map_writeback_high_conf_allows`
- `test_map_writeback_still_safe_false_denies`

### Gates / pipeline

- `test_emit_egress_gate_calls_jev_and_redacts`
- `test_writeback_gate_fail_closed_on_timeout`
- `test_observe_require_writeback_blocks_silent_durable`
- `test_pipeline_collects_escalations_list`
- `test_pipeline_default_path_unchanged_without_egress_gates`

### Client

- `test_fake_jev_decide_emit`
- `test_fake_jev_decide_writeback`
- `test_http_jev_decide_emit_payload_shape_mocked`
- `test_http_jev_decide_writeback_payload_shape_mocked`

### Fan-out defaults

- `test_fanout_defaults_frozen_values`
- `test_fanout_optional_network_adds_question`
- `test_fanout_core_hydrate_question_ids_stable`

### No-rerank (required)

- `test_pipeline_preserves_candidate_order_and_local_scores`
- `test_gate_does_not_permute_candidate_ids`
- `test_assert_no_rerank_detects_score_mutation`
- `test_jev_actions_do_not_act_as_similarity_ranker`

### Redaction / safety

- `test_emit_payload_rejects_content_keys`
- `test_writeback_proposed_rejects_body_secret_fields`

---

## 5. Success criteria — David / Justin Sun 10-pt review

Reviewers score **implementation honesty**, not marketing. Target for Phase 9.5 exit packet: each bullet **must** be demonstrable offline; live items marked N/A or blocked.

| # | Criterion | Pass evidence |
|---|-----------|---------------|
| 1 | Dual-gate egress exists and is fail-closed | `decide_emit` / `decide_writeback` on Protocol + FakeJev; chaos timeout → deny |
| 2 | No silent durable write | `require_writeback` / WritebackGate mid-band → `escalate_human` or deny; test proves block |
| 3 | `escalate_human` is structured | `EscalationRecord` on mid-band hydrate + writeback; pipeline exposes `escalations` |
| 4 | Fan-out defaults frozen | `FANOUT_DEFAULTS` imported; tests lock core Q IDs and `include_raw_query=False` |
| 5 | No-rerank proven | New tests green; order + `local_score` invariant documented in ARCHITECTURE |
| 6 | Redaction unchanged / extended | Emit+writeback payloads never carry `content` / secrets; existing redact tests still pass |
| 7 | Hydrate critical path not theater | Existing `jev_called` / call_count tests still pass; default `pipeline.run` behavior unchanged when egress gates off |
| 8 | Honesty / no acceleration claim | README + SCORECARD still PREVIEW ≤8.5; no new “beats Hindsight / accelerates” language |
| 9 | FakeJev ≠ product proof labeled | Any new bake-off mention still cites FakeJev; live pilot listed as open gap |
| 10 | Review packet | This plan + pytest green + short `docs/reviews/` note linking David P1 (egress/audit) + Justin ranked fixes (no theater, fail-closed) |

**David-specific:** addresses P1 “optional gate audit” direction via `EscalationRecord` + egress decisions (full persistent `GateAuditRecord` store can be Phase 9.6).  
**Justin-specific:** strengthens fail-closed / no-theater / library-not-plugin posture; does **not** pretend live bake-off is done.

**Hard fail (auto REJECT narrative):** fail-open emit/writeback; body egress on writeback proposed; tests that “pass” by skipping Jev on hydrate; SCORECARD bumped to ≥9.0 without live logs.

---

## 6. Suggested implementation order (next executor)

1. Types + `fanout.py` + `escalate_human` + policy mappers  
2. FakeJev protocol methods + unit tests  
3. Gates + pipeline opt-in wires  
4. No-rerank + fan-out default tests  
5. HttpJev mocked shapes  
6. Docs + SCORECARD honesty note (no score inflation)

---

## 7. Open items deferred past 9.5

- Live personal-prefs HttpJev pilot log (`bakeoff_metrics_live.json`)  
- Real HTTP 401/403/429 chaos (not only `force_*`)  
- Independent redaction adversarial review  
- GitHub Actions CI on main  
- Persistent GateAuditRecord store  
- Hermes/Claude skill packaging (explicit non-goal unless Leon pivots)

---

*End of plan. Implementation is a separate turn.*
