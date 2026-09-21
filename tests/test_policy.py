"""Policy thresholds, escalate_human, emit/writeback, fail-closed."""

from __future__ import annotations

from datetime import UTC, datetime

from remember_me.policy import (
    T_ACCEPT,
    T_ESCALATE,
    assert_no_rerank,
    escalate_human,
    map_emit_action,
    map_hydrate_action,
    map_writeback_action,
)
from remember_me.types import (
    Q_EMIT_ACTION,
    Q_HYDRATE_ACTION,
    Q_LEAK_RISK,
    Q_ON_TOPIC,
    Q_STILL_MATTERS,
    Q_WRITEBACK_ACTION,
    Q_WRITEBACK_STILL_SAFE,
    Candidate,
    EmitAction,
    HydrateAction,
    JevBatchResponse,
    JevQuestionResult,
    NodeKind,
    WritebackAction,
)


def _cand(score: float = 0.9, node_id: str = "c1") -> Candidate:
    return Candidate(
        node_id=node_id,
        kind=NodeKind.FACT,
        tags=[],
        degree=0,
        last_touch=datetime.now(UTC),
        local_score=score,
        tokens_est=10,
    )


def _resp(conf: float, action: str = "hydrate_full", still: bool = True) -> JevBatchResponse:
    return JevBatchResponse(
        node_id="c1",
        results={
            Q_HYDRATE_ACTION: JevQuestionResult(
                question_id=Q_HYDRATE_ACTION, value=action, confidence=conf
            ),
            Q_STILL_MATTERS: JevQuestionResult(
                question_id=Q_STILL_MATTERS, value=still, confidence=conf
            ),
        },
    )


def test_thresholds_constants():
    assert T_ACCEPT == 0.85
    assert T_ESCALATE == 0.55


def test_accept_hydrates():
    d = map_hydrate_action(_resp(0.9), _cand())
    assert d.action == HydrateAction.HYDRATE_FULL
    assert not d.fail_closed


def test_mid_band_stubs():
    """Mid-band with raw hydrate_full → first-class escalate_human (+ EscalationRecord)."""
    d = map_hydrate_action(_resp(0.7, action="hydrate_full"), _cand())
    assert d.action == HydrateAction.ESCALATE_HUMAN
    assert d.escalation is not None
    assert d.escalation.source_gate == "hydrate"
    assert d.escalation.band == "mid"
    assert "content" not in d.escalation.redacted_snapshot


def test_mid_band_hydrate_attaches_escalation_and_stubs():
    """Explicit raw stub_only mid-band keeps stub + attaches escalation."""
    d = map_hydrate_action(_resp(0.7, action="stub_only"), _cand())
    assert d.action == HydrateAction.STUB_ONLY
    assert d.escalation is not None


def test_low_conf_skips():
    d = map_hydrate_action(_resp(0.4), _cand())
    assert d.action == HydrateAction.SKIP


def test_still_matters_false_downgrades():
    """Conflict: high-conf full hydrate + still_matters=false → escalate_human."""
    d = map_hydrate_action(_resp(0.95, still=False), _cand())
    assert d.action == HydrateAction.ESCALATE_HUMAN
    assert d.escalation is not None
    assert d.escalation.band == "conflict"


def test_fail_closed_timeout():
    resp = JevBatchResponse(node_id="c1", timed_out=True, error="timeout")
    d = map_hydrate_action(resp, _cand())
    assert d.fail_closed
    assert d.action == HydrateAction.SKIP


def test_fail_closed_deny():
    resp = JevBatchResponse(node_id="c1", denied=True, error="denied")
    d = map_hydrate_action(resp, _cand())
    assert d.fail_closed
    assert d.action == HydrateAction.SKIP


def test_fail_closed_malformed():
    resp = JevBatchResponse(node_id="c1", malformed=True, error="malformed")
    d = map_hydrate_action(resp, _cand())
    assert d.fail_closed


def test_fail_closed_local_stub_fallback():
    resp = JevBatchResponse(node_id="c1", timed_out=True, error="timeout")
    d = map_hydrate_action(
        resp,
        _cand(),
        fail_closed_top_k_fallback=True,
        fail_closed_rank=0,
        fail_closed_k=2,
    )
    assert d.fail_closed
    assert d.action == HydrateAction.STUB_ONLY


def test_escalate_human_builds_redacted_record():
    rec = escalate_human(
        node_id="n1",
        source_gate="hydrate",
        confidence=0.7,
        proposed_action="hydrate_full",
        reason="mid",
        redacted_snapshot={"node_id": "n1", "content": "SECRET", "tags": ["t"]},
    )
    assert rec.node_id == "n1"
    assert "content" not in rec.redacted_snapshot
    assert rec.redacted_snapshot.get("tags") == ["t"]


def _emit_resp(conf: float, action: str = "allow_emit", leak=False, on_topic=True):
    return JevBatchResponse(
        node_id="egress",
        results={
            Q_EMIT_ACTION: JevQuestionResult(
                question_id=Q_EMIT_ACTION, value=action, confidence=conf
            ),
            Q_LEAK_RISK: JevQuestionResult(
                question_id=Q_LEAK_RISK, value=leak, confidence=conf
            ),
            Q_ON_TOPIC: JevQuestionResult(
                question_id=Q_ON_TOPIC, value=on_topic, confidence=conf
            ),
        },
    )


def test_map_emit_action_fail_closed_denies():
    resp = JevBatchResponse(node_id="e", timed_out=True, error="timeout")
    d = map_emit_action(resp)
    assert d.fail_closed
    assert d.action == EmitAction.DENY_EMIT


def test_map_emit_action_accept_allows():
    d = map_emit_action(_emit_resp(0.9))
    assert d.action == EmitAction.ALLOW_EMIT
    assert not d.fail_closed


def test_map_emit_action_mid_band_escalates():
    d = map_emit_action(_emit_resp(0.7))
    assert d.action == EmitAction.ESCALATE_HUMAN
    assert d.escalation is not None


def test_map_emit_action_block_synonym():
    d = map_emit_action(_emit_resp(0.9, action="block"))
    assert d.action == EmitAction.DENY_EMIT


def _wb_resp(conf: float, action: str = "allow_writeback", still_safe: bool = True):
    return JevBatchResponse(
        node_id="n1",
        results={
            Q_WRITEBACK_ACTION: JevQuestionResult(
                question_id=Q_WRITEBACK_ACTION, value=action, confidence=conf
            ),
            Q_WRITEBACK_STILL_SAFE: JevQuestionResult(
                question_id=Q_WRITEBACK_STILL_SAFE, value=still_safe, confidence=conf
            ),
        },
    )


def test_map_writeback_mid_band_escalates_human():
    d = map_writeback_action(_wb_resp(0.7), node_id="n1")
    assert d.action == WritebackAction.ESCALATE_HUMAN
    assert d.escalation is not None


def test_map_writeback_high_conf_allows():
    d = map_writeback_action(_wb_resp(0.9), node_id="n1")
    assert d.action == WritebackAction.ALLOW_WRITEBACK


def test_map_writeback_still_safe_false_denies():
    d = map_writeback_action(_wb_resp(0.95, still_safe=False), node_id="n1")
    assert d.action == WritebackAction.DENY_WRITEBACK


def test_assert_no_rerank_ok():
    a = [_cand(0.9, "a"), _cand(0.5, "b")]
    assert_no_rerank(a, list(a))


def test_assert_no_rerank_detects_score_mutation():
    import pytest

    before = [_cand(0.9, "a")]
    after = [_cand(0.1, "a")]
    with pytest.raises(AssertionError, match="local_score"):
        assert_no_rerank(before, after)
