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
