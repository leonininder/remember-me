"""No-rerank hard contract: Jev never reorders or rescores local candidates.

After gates, relative order of surviving candidates must not be a Jev-driven
reorder by local_score / confidence. Local TEMPR order + local_score are
immutable through redact → Jev → policy.
"""

from __future__ import annotations

from remember_me.gates import MemoryGate
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev
from remember_me.pipeline import MemoryPipeline
from remember_me.policy import assert_no_rerank
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import Horizon, HydrateAction, NodeKind


def _seed() -> TopologyGraph:
    g = TopologyGraph()
    for nid, tags, sal in [
        ("high", ["preference", "ui"], 0.95),
        ("mid", ["preference", "locale"], 0.7),
        ("low", ["noise"], 0.2),
        ("also", ["preference"], 0.85),
    ]:
        g.observe(
            node_id=nid,
            content=f"body-{nid}",
            kind=NodeKind.FACT,
            horizon=Horizon.SESSION,
            tags=tags,
            salience=sal,
        )
    return g


def test_pipeline_preserves_candidate_order_and_local_scores():
    g = _seed()
    client = FakeJev()
    pipe = MemoryPipeline(g, client, top_k=4)
    # Capture pre-gate retrieval order.
    before = LocalCandidateRetriever(g, top_k=4).retrieve("preference ui locale")
    result = pipe.run("preference ui locale")
    assert_no_rerank(before, result.candidates)
    # Decisions follow candidate order (not Jev-confidence sort).
    assert [d.node_id for d in result.decisions] == [c.node_id for c in result.candidates]


def test_gate_does_not_permute_candidate_ids():
    g = _seed()
    cands = LocalCandidateRetriever(g, top_k=4).retrieve("preference")
    ids_before = [c.node_id for c in cands]
    scores_before = [c.local_score for c in cands]
    gate = MemoryGate(FakeJev())
    decisions = gate.evaluate("preference", cands)
    assert [c.node_id for c in cands] == ids_before
    assert [c.local_score for c in cands] == scores_before
    assert [d.node_id for d in decisions] == ids_before


def test_assert_no_rerank_detects_score_mutation():
    from datetime import UTC, datetime

    import pytest

    from remember_me.types import Candidate

    b = Candidate(
        node_id="a",
        kind=NodeKind.FACT,
        tags=[],
        degree=0,
        last_touch=datetime.now(UTC),
        local_score=0.9,
        tokens_est=1,
    )
    a = b.model_copy(update={"local_score": 0.2})
    with pytest.raises(AssertionError):
        assert_no_rerank([b], [a])


def test_jev_actions_do_not_act_as_similarity_ranker():
    """Survivors keep relative local_score order from retrieval — not Jev conf sort."""
    g = _seed()
    # Force mixed actions via default FakeJev; survivors = non-skip/non-escalate.
    pipe = MemoryPipeline(g, FakeJev(confidence_override=0.99), top_k=4)
    result = pipe.run("preference ui")
    # Hydrated list must follow candidate encounter order among survivors.
    cand_order = [c.node_id for c in result.candidates]
    hyd_ids = [h.node_id for h in result.hydrated]
    # Relative order: indices in cand_order must be strictly increasing.
    idxs = [cand_order.index(i) for i in hyd_ids]
    assert idxs == sorted(idxs), "hydrated order must follow candidate order (no Jev reorder)"
    # Explicit: sorting hydrated by Jev confidence must NOT be required for correctness;
    # document that we did NOT sort by confidence.
    conf_order = sorted(result.hydrated, key=lambda h: h.confidence, reverse=True)
    # If conf order differs, that is fine — we assert we kept local order instead.
    _ = conf_order
    assert all(h.action != HydrateAction.ESCALATE_HUMAN for h in result.hydrated)
