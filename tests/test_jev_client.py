"""FakeJev deterministic behavior + HttpJev fail paths without network success."""

from __future__ import annotations

from datetime import UTC, datetime

from remember_me.jev_client import FakeJev, HttpJev
from remember_me.redact import redact_state
from remember_me.types import JEV_MODEL_PIN, Candidate, HydrateAction, NodeKind


def _cands():
    return [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["preference"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.9,
            tokens_est=10,
            content="SECRET should not appear",
        )
    ]


def test_fake_jev_redacts_and_decides():
    client = FakeJev()
    red = redact_state(_cands())
    out = client.decide_hydrate("theme?", red)
    assert client.call_count == 1
    assert out[0].node_id == "a"
    assert not out[0].failed
    payload = client.last_outbound
    assert "content" not in payload[0]
    assert "SECRET" not in str(payload)


def test_fake_jev_accepts_raw_candidates_but_redacts():
    client = FakeJev()
    client.decide_hydrate("q", _cands())
    assert "content" not in client.last_outbound[0]


def test_fake_jev_force_timeout_deny_malformed():
    for kw in ({"force_timeout": True}, {"force_deny": True}, {"force_malformed": True}):
        client = FakeJev(**kw)
        resp = client.decide_hydrate("q", redact_state(_cands()))
        assert resp[0].failed


def test_fake_jev_action_override():
    client = FakeJev(action_override=HydrateAction.SKIP, confidence_override=0.99)
    resp = client.decide_hydrate("q", redact_state(_cands()))
    assert resp[0].results["hydrate_action"].value == HydrateAction.SKIP.value


def test_fake_jev_admit():
    client = FakeJev()
    resp = client.decide_admit({"node_id": "n", "kind": "fact", "tags": [], "salience": 0.5})
    assert not resp.failed
    assert "admit" in resp.results


def test_fake_jev_model_pin():
    assert FakeJev().model_pin == JEV_MODEL_PIN


def test_http_jev_missing_key_fail_closed():
    client = HttpJev(api_key="")
    resp = client.decide_hydrate("q", redact_state(_cands()))
    assert resp[0].failed
    assert resp[0].denied or resp[0].error


def test_http_jev_admit_missing_key():
    client = HttpJev(api_key="")
    resp = client.decide_admit({"node_id": "n", "kind": "fact", "tags": [], "salience": 0.4})
    assert resp.failed


def test_fake_jev_decide_emit():
    client = FakeJev(confidence_override=0.9)
    resp = client.decide_emit(
        sink="agent_channel",
        payload_meta={"proposed_summary": "ok", "node_id": "e1", "content": "NO"},
    )
    assert not resp.failed
    assert "emit_action" in resp.results
    assert "content" not in client.last_outbound[0]


def test_fake_jev_decide_writeback():
    client = FakeJev(confidence_override=0.9)
    resp = client.decide_writeback(
        target="graph_durable",
        proposed={"node_id": "n1", "kind": "fact", "tags": ["t"], "salience": 0.5, "body": "NO"},
    )
    assert not resp.failed
    assert "writeback_action" in resp.results
    assert "body" not in client.last_outbound[0]


def test_fake_jev_fanout_one_call_multi_candidate():
    """Multi-candidate × multi-question = one decide_hydrate call (fan-out default)."""
    from datetime import UTC, datetime

    cands = [
        Candidate(
            node_id=nid,
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=s,
            tokens_est=4,
            content="secret",
        )
        for nid, s in (("a", 0.9), ("b", 0.5), ("c", 0.3))
    ]
    client = FakeJev()
    out = client.decide_hydrate("q", redact_state(cands))
    assert client.call_count == 1
    assert len(out) == 3
    for r in out:
        assert "hydrate_action" in r.results
        assert "need_for_next_turn" in r.results
        assert "still_matters_for_latest_ask" in r.results


def test_hydrate_questions_live_criteria_shape():
    """System One: Choice criteria=dict; Score criteria=list[str] (not ints)."""
    from remember_me.jev_client import (
        NEED_FOR_NEXT_TURN_LEVELS,
        _admit_questions,
        _emit_questions,
        _hydrate_questions,
        _writeback_questions,
    )

    hq = _hydrate_questions(optional_network=True, optional_reflect=True)
    assert isinstance(hq["hydrate_action"]["criteria"], dict)
    assert "hydrate_full" in hq["hydrate_action"]["criteria"]
    assert isinstance(hq["need_for_next_turn"]["criteria"], list)
    assert hq["need_for_next_turn"]["criteria"] == list(NEED_FOR_NEXT_TURN_LEVELS)
    assert all(isinstance(x, str) for x in hq["need_for_next_turn"]["criteria"])
    assert isinstance(hq["memory_network"]["criteria"], dict)

    aq = _admit_questions()
    assert isinstance(aq["admit"]["criteria"], dict)
    assert isinstance(aq["node_kind"]["criteria"], dict)

    eq = _emit_questions()
    assert isinstance(eq["emit_action"]["criteria"], dict)

    wq = _writeback_questions()
    assert isinstance(wq["writeback_action"]["criteria"], dict)
    assert all(isinstance(x, str) for x in wq["writeback_need"]["criteria"])
