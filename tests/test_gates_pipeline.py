"""Integration: FakeJev on hydrate path; orphan hydrations forbidden; admit gate."""

from __future__ import annotations

from remember_me.gates import MemoryGate, RetainAdmitGate
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev
from remember_me.pipeline import MemoryPipeline
from remember_me.types import AdmitDecision, Horizon, HydrateAction, NodeKind


def test_memory_gate_calls_jev():
    g = TopologyGraph()
    g.observe(node_id="theme", content="dark theme", tags=["ui", "theme"], salience=0.9)
    client = FakeJev()
    gate = MemoryGate(client)
    from remember_me.retrieve import LocalCandidateRetriever

    cands = LocalCandidateRetriever(g).retrieve("theme preference")
    assert cands
    decisions = gate.evaluate("theme preference", cands)
    assert client.call_count == 1
    assert gate.jev_call_count == 1
    assert decisions
    # Prove secrets not outbound
    assert all("content" not in r.model_dump() for r in gate.last_redacted)


def test_pipeline_jev_called_on_hydrate_path():
    g = TopologyGraph()
    g.observe(
        node_id="lang",
        content="Traditional Chinese UI",
        tags=["locale", "language"],
        salience=0.95,
    )
    g.observe(node_id="noise", content="cricket trivia", tags=["sports"], salience=0.1)
    client = FakeJev()
    pipe = MemoryPipeline(g, client, top_k=5)
    result = pipe.run("UI language preference")
    assert result.jev_called is True
    assert client.call_count >= 1
    assert len(result.redacted) == len(result.candidates)
    # No orphan hydrations
    cand_ids = {c.node_id for c in result.candidates}
    for h in result.hydrated:
        assert h.node_id in cand_ids


def test_pipeline_empty_query_no_false_jev_when_no_candidates():
    pipe = MemoryPipeline(TopologyGraph(), FakeJev())
    result = pipe.run("nothing matches this zzqqxx")
    # empty graph → no candidates → jev not called
    assert result.candidates == []
    assert result.jev_called is False


def test_fail_closed_chaos_timeout():
    g = TopologyGraph()
    g.observe(node_id="a", content="preference theme dark", tags=["theme"], salience=0.9)
    client = FakeJev(force_timeout=True)
    pipe = MemoryPipeline(g, client, top_k=3)
    result = pipe.run("theme preference")
    assert result.jev_called
    assert result.fail_closed_count >= 1
    assert all(d.fail_closed for d in result.decisions)
    # Fail-closed default: skip → nothing full-hydrated
    assert all(h.stub or h.action != HydrateAction.HYDRATE_FULL for h in result.hydrated)


def test_orphan_hydration_forbidden():
    """Even if a decision somehow references unknown id, pipeline skips it."""
    g = TopologyGraph()
    g.observe(node_id="real", content="real preference", tags=["preference"], salience=0.9)
    client = FakeJev(confidence_override=0.99, action_override=HydrateAction.HYDRATE_FULL)
    pipe = MemoryPipeline(g, client)
    result = pipe.run("preference")
    for h in result.hydrated:
        assert h.node_id in {c.node_id for c in result.candidates}


def test_admit_gate_success_and_fail_closed():
    ok = RetainAdmitGate(FakeJev(confidence_override=0.9)).evaluate(
        node_id="n1", kind=NodeKind.FACT, tags=["preference"]
    )
    assert ok.decision in (AdmitDecision.ADMIT, AdmitDecision.REJECT, AdmitDecision.DEFER)
    assert not ok.fail_closed

    bad = RetainAdmitGate(FakeJev(force_deny=True)).evaluate(node_id="n2")
    assert bad.fail_closed
    assert bad.decision == AdmitDecision.DEFER


def test_observe_require_admit():
    client = FakeJev(confidence_override=0.95)
    pipe = MemoryPipeline(TopologyGraph(), client)
    m = pipe.observe(
        node_id="admitted",
        content="body",
        kind=NodeKind.FACT,
        tags=["preference"],
        require_admit=True,
    )
    assert m.node_id == "admitted"


def test_promote_durable_action():
    g = TopologyGraph()
    g.observe(node_id="p", content="important preference", tags=["preference"], salience=0.99)
    client = FakeJev(
        confidence_override=0.99, action_override=HydrateAction.PROMOTE_DURABLE
    )
    pipe = MemoryPipeline(g, client)
    result = pipe.run("important preference")
    assert any(h.action == HydrateAction.PROMOTE_DURABLE for h in result.hydrated)
    assert g.get("p").horizon == Horizon.DURABLE


def test_memory_gate_optional_network_reflect():
    g = TopologyGraph()
    g.observe(node_id="x", content="preference locale timezone", tags=["locale"], salience=0.9)
    client = FakeJev()
    gate = MemoryGate(client, optional_network=True, optional_reflect=True)
    from remember_me.retrieve import LocalCandidateRetriever

    cands = LocalCandidateRetriever(g).retrieve("locale timezone")
    decisions = gate.evaluate("locale timezone", cands)
    assert decisions
    assert any(d.network_route is not None or d.trigger_reflect is not None for d in decisions)


def test_observe_admit_reject_raises():
    import pytest

    pipe = MemoryPipeline(TopologyGraph(), FakeJev(force_deny=True))
    with pytest.raises(PermissionError):
        pipe.observe(node_id="nope", content="x", require_admit=True)


def test_emit_egress_gate_calls_jev_and_redacts():
    from remember_me.gates import EmitEgressGate

    client = FakeJev(confidence_override=0.9)
    gate = EmitEgressGate(client)
    d = gate.evaluate(
        "audit_log",
        {"proposed_summary": "prefs only", "node_id": "e1", "content": "SHOULD_STRIP"},
    )
    assert client.call_count == 1
    assert gate.jev_call_count == 1
    assert "content" not in gate.last_outbound
    assert d.action.value in ("allow_emit", "deny_emit", "escalate_human", "redact_further")


def test_writeback_gate_fail_closed_on_timeout():
    from remember_me.gates import WritebackGate
    from remember_me.types import WritebackAction

    gate = WritebackGate(FakeJev(force_timeout=True))
    d = gate.evaluate(
        "graph_durable",
        {"node_id": "n1", "kind": "fact", "tags": ["preference"], "salience": 0.8},
    )
    assert d.fail_closed
    assert d.action == WritebackAction.DENY_WRITEBACK


def test_observe_require_writeback_blocks_silent_durable():
    import pytest

    from remember_me.gates import WritebackGate

    client = FakeJev(force_deny=True)
    pipe = MemoryPipeline(
        TopologyGraph(), client, writeback_gate=WritebackGate(client)
    )
    with pytest.raises(PermissionError, match="writeback"):
        pipe.observe(
            node_id="blocked",
            content="x",
            require_writeback=True,
        )


def test_pipeline_collects_escalations_list():
    g = TopologyGraph()
    g.observe(
        node_id="m",
        content="preference theme",
        tags=["preference", "theme"],
        salience=0.6,
    )
    # Mid-band confidence → escalate_human + EscalationRecord
    client = FakeJev(confidence_override=0.7, action_override=HydrateAction.HYDRATE_FULL)
    pipe = MemoryPipeline(g, client)
    result = pipe.run("theme preference")
    assert result.escalate_human_count >= 1
    assert result.escalations
    assert all(e.source_gate == "hydrate" for e in result.escalations)


def test_pipeline_default_path_unchanged_without_egress_gates():
    g = TopologyGraph()
    g.observe(node_id="p", content="preference locale", tags=["locale"], salience=0.95)
    client = FakeJev(confidence_override=0.99)
    pipe = MemoryPipeline(g, client)
    assert pipe.emit_gate is None
    assert pipe.writeback_gate is None
    result = pipe.run("locale preference")
    assert result.jev_called is True


def test_run_egress_and_dual_gate_pipeline():
    from remember_me.pipeline import DualGatePipeline
    from remember_me.types import EmitAction

    g = TopologyGraph()
    g.observe(node_id="p", content="preference ui", tags=["ui"], salience=0.9)
    pipe = DualGatePipeline(g, FakeJev(confidence_override=0.95), top_k=3)
    dual = pipe.run_dual(
        "ui preference",
        egress_summary="Redacted UI preference summary for channel.",
    )
    assert dual.ingress.jev_called
    assert dual.egress is not None
    assert dual.egress.jev_called
    assert dual.egress.decision.action in (
        EmitAction.ALLOW_EMIT,
        EmitAction.DENY_EMIT,
        EmitAction.ESCALATE_HUMAN,
        EmitAction.REDACT_FURTHER,
    )
