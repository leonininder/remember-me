"""Policy thresholds and fail-closed behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from remember_me.policy import T_ACCEPT, T_ESCALATE, map_hydrate_action
from remember_me.types import (
    Q_HYDRATE_ACTION,
    Q_STILL_MATTERS,
    Candidate,
    HydrateAction,
    JevBatchResponse,
    JevQuestionResult,
    NodeKind,
)


def _cand(score: float = 0.9) -> Candidate:
    return Candidate(
        node_id="c1",
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
    d = map_hydrate_action(_resp(0.7, action="hydrate_full"), _cand())
    assert d.action == HydrateAction.STUB_ONLY


def test_low_conf_skips():
    d = map_hydrate_action(_resp(0.4), _cand())
    assert d.action == HydrateAction.SKIP


def test_still_matters_false_downgrades():
    d = map_hydrate_action(_resp(0.95, still=False), _cand())
    assert d.action == HydrateAction.STUB_ONLY


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
