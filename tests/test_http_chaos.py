"""Real HttpJev HTTP chaos via httpx mock — not FakeJev force_*.

Justin #3 / David Verification: 401, 403, 429(+Retry-After), timeout,
malformed JSON → fail-closed deny/escalate; never silent allow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from remember_me.gates import EmitEgressGate, MemoryGate, WritebackGate
from remember_me.jev_client import HttpJev
from remember_me.policy import map_emit_action, map_hydrate_action, map_writeback_action
from remember_me.redact import redact_state
from remember_me.types import (
    Candidate,
    EmitAction,
    HydrateAction,
    NodeKind,
    WritebackAction,
)


def _cand(nid: str = "n1") -> Candidate:
    return Candidate(
        node_id=nid,
        kind=NodeKind.FACT,
        tags=["preference"],
        degree=1,
        last_touch=datetime.now(UTC),
        local_score=0.95,
        tokens_est=10,
        content="BODY-SHOULD-NEVER-EGRESS sk-LIVEKEY123",
    )


def _mock_client(resp: MagicMock | None = None, *, side_effect=None) -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    if side_effect is not None:
        mock_client.post.side_effect = side_effect
    else:
        mock_client.post.return_value = resp
    return mock_client


def _resp(status: int, *, headers: dict | None = None, json_body=None, json_exc=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.headers = headers or {}
    if json_exc is not None:
        mock_resp.json.side_effect = json_exc
    elif json_body is not None:
        mock_resp.json.return_value = json_body
    else:
        mock_resp.json.return_value = {}
    return mock_resp


# --- HttpJev surface flags ---


@pytest.mark.parametrize("code", [401, 403])
def test_http_chaos_auth_denied(code: int):
    client = HttpJev(api_key="bad-key")
    mock_client = _mock_client(_resp(code))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert len(out) == 1
    assert out[0].denied
    assert out[0].failed
    assert f"http_{code}" in (out[0].error or "")
    assert not out[0].results  # never a silent allow payload


def test_http_chaos_429_retry_after_timed_out():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(_resp(429, headers={"Retry-After": "12"}))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert out[0].timed_out
    assert out[0].failed
    assert "http_429" in (out[0].error or "")
    assert "retry_after=12" in (out[0].error or "")


def test_http_chaos_429_without_retry_after():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(_resp(429, headers={}))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert out[0].timed_out and out[0].failed
    assert out[0].error == "http_429"


def test_http_chaos_timeout_exception():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(side_effect=httpx.TimeoutException("slow"))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert out[0].timed_out and out[0].failed


def test_http_chaos_malformed_json():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(_resp(200, json_exc=ValueError("not json")))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert out[0].malformed and out[0].failed
    assert out[0].error == "invalid_json"


def test_http_chaos_non_object_body_malformed():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(_resp(200, json_body=["not", "an", "object"]))
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state([_cand()]))
    assert out[0].malformed and out[0].failed


# --- Policy / gate fail-closed: never hydrate_full / allow_emit / allow_writeback ---


@pytest.mark.parametrize(
    "status,expect_flag",
    [
        (401, "denied"),
        (403, "denied"),
        (429, "timed_out"),
    ],
)
def test_http_chaos_hydrate_gate_fail_closed(status: int, expect_flag: str):
    headers = {"Retry-After": "5"} if status == 429 else {}
    client = HttpJev(api_key="k")
    gate = MemoryGate(client=client)
    mock_client = _mock_client(_resp(status, headers=headers))
    with patch("httpx.Client", return_value=mock_client):
        decisions = gate.evaluate("prefs?", [_cand()])
    d = decisions[0]
    assert d.fail_closed is True
    assert d.action in (HydrateAction.SKIP, HydrateAction.STUB_ONLY)
    assert d.action != HydrateAction.HYDRATE_FULL
    assert "fail_closed" in d.reason
    raw = client.last_outbound
    assert "BODY-SHOULD-NEVER-EGRESS" not in str(raw)
    assert "sk-LIVEKEY123" not in str(raw)


def test_http_chaos_hydrate_timeout_fail_closed():
    client = HttpJev(api_key="k")
    gate = MemoryGate(client=client)
    mock_client = _mock_client(side_effect=TimeoutError("rtt"))
    with patch("httpx.Client", return_value=mock_client):
        decisions = gate.evaluate("q", [_cand()])
    assert decisions[0].fail_closed
    assert decisions[0].action != HydrateAction.HYDRATE_FULL


def test_http_chaos_hydrate_malformed_fail_closed():
    client = HttpJev(api_key="k")
    gate = MemoryGate(client=client)
    mock_client = _mock_client(_resp(200, json_body={"answers": "bogus"}))
    with patch("httpx.Client", return_value=mock_client):
        decisions = gate.evaluate("q", [_cand()])
    assert decisions[0].fail_closed
    assert decisions[0].action != HydrateAction.HYDRATE_FULL


@pytest.mark.parametrize("status", [401, 403, 429])
def test_http_chaos_emit_gate_deny(status: int):
    headers = {"Retry-After": "3"} if status == 429 else {}
    client = HttpJev(api_key="k")
    gate = EmitEgressGate(client=client)
    mock_client = _mock_client(_resp(status, headers=headers))
    with patch("httpx.Client", return_value=mock_client):
        d = gate.evaluate("audit_log", {"proposed_summary": "hi", "node_id": "e1"})
    assert d.fail_closed is True
    assert d.action == EmitAction.DENY_EMIT
    assert d.action != EmitAction.ALLOW_EMIT


@pytest.mark.parametrize("status", [401, 403, 429])
def test_http_chaos_writeback_gate_deny(status: int):
    headers = {"Retry-After": "7"} if status == 429 else {}
    client = HttpJev(api_key="k")
    gate = WritebackGate(client=client)
    mock_client = _mock_client(_resp(status, headers=headers))
    with patch("httpx.Client", return_value=mock_client):
        d = gate.evaluate(
            "wiki_stage",
            {"node_id": "n1", "kind": "fact", "tags": ["t"], "salience": 0.5},
        )
    assert d.fail_closed is True
    assert d.action == WritebackAction.DENY_WRITEBACK
    assert d.action != WritebackAction.ALLOW_WRITEBACK


def test_http_chaos_emit_timeout_and_malformed_deny():
    client = HttpJev(api_key="k")
    gate = EmitEgressGate(client=client)

    mock_client = _mock_client(side_effect=httpx.TimeoutException("x"))
    with patch("httpx.Client", return_value=mock_client):
        d1 = gate.evaluate("agent_channel", {"proposed_summary": "x"})
    assert d1.fail_closed and d1.action == EmitAction.DENY_EMIT

    mock_client2 = _mock_client(_resp(200, json_exc=ValueError("bad")))
    with patch("httpx.Client", return_value=mock_client2):
        d2 = gate.evaluate("agent_channel", {"proposed_summary": "x"})
    assert d2.fail_closed and d2.action == EmitAction.DENY_EMIT


def test_http_chaos_writeback_malformed_deny():
    client = HttpJev(api_key="k")
    gate = WritebackGate(client=client)
    mock_client = _mock_client(_resp(200, json_body={"nope": True}))
    with patch("httpx.Client", return_value=mock_client):
        d = gate.evaluate("graph_durable", {"node_id": "n", "kind": "fact", "tags": []})
    assert d.fail_closed and d.action == WritebackAction.DENY_WRITEBACK


def test_http_chaos_batch_429_all_nodes_fail_closed():
    cands = [_cand("a"), _cand("b")]
    client = HttpJev(api_key="k")
    mock_client = _mock_client(_resp(429, headers={"Retry-After": "30"}))
    with patch("httpx.Client", return_value=mock_client):
        outs = client.decide_hydrate("q", redact_state(cands))
    assert len(outs) == 2
    assert all(o.timed_out and o.failed for o in outs)
    for o in outs:
        mapped = map_hydrate_action(o, cands[0] if o.node_id == "a" else cands[1])
        assert mapped.fail_closed
        assert mapped.action != HydrateAction.HYDRATE_FULL


def test_http_chaos_policy_helpers_never_allow_on_failed_response():
    """Direct map_* on failed HttpJev-shaped responses — belt and suspenders."""
    from remember_me.types import JevBatchResponse

    failed = [
        JevBatchResponse(node_id="n", denied=True, error="http_401"),
        JevBatchResponse(node_id="n", denied=True, error="http_403"),
        JevBatchResponse(node_id="n", timed_out=True, error="http_429:retry_after=1"),
        JevBatchResponse(node_id="n", timed_out=True, error="timeout"),
        JevBatchResponse(node_id="n", malformed=True, error="invalid_json"),
    ]
    c = _cand()
    for resp in failed:
        h = map_hydrate_action(resp, c)
        assert h.fail_closed and h.action != HydrateAction.HYDRATE_FULL
        e = map_emit_action(resp, sink="x", proposed_chars=0)
        assert e.fail_closed and e.action == EmitAction.DENY_EMIT
        w = map_writeback_action(resp, target="t", node_id="n")
        assert w.fail_closed and w.action == WritebackAction.DENY_WRITEBACK
