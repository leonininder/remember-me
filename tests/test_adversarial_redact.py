"""Adversarial redaction — fake keys, emails, long bodies, tag/node_id side-channels.

Justin ranked fix #3: independent redaction adversarial (tag/node_id side channels).
Secrets must never appear in outbound state for hydrate AND emit/writeback.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from remember_me.gates import EmitEgressGate, MemoryGate, WritebackGate
from remember_me.jev_client import FakeJev, HttpJev
from remember_me.redact import assert_no_secrets, redact_state, redact_to_dicts
from remember_me.types import Candidate, NodeKind

FAKE_KEY = "sk-ANTAGONIST_LIVE_KEY_9f3a2b1c0d"
FAKE_EMAIL = "victim@evil.example.com"
LONG_BODY = ("PASSWORD=hunter2 " + "X" * 4000 + f" Bearer {FAKE_KEY} {FAKE_EMAIL}")


def _poisoned(**kwargs) -> Candidate:
    base = dict(
        node_id="n_clean",
        kind=NodeKind.FACT,
        tags=["preference"],
        degree=2,
        last_touch=datetime.now(UTC),
        local_score=0.9,
        tokens_est=99,
        content=LONG_BODY,
        secret=FAKE_KEY,
    )
    base.update(kwargs)
    return Candidate(**base)


def _assert_clean(blob: object) -> None:
    s = str(blob)
    assert FAKE_KEY not in s
    assert "sk-ANTAGONIST" not in s
    assert FAKE_EMAIL not in s
    assert "hunter2" not in s
    assert "PASSWORD=" not in s.upper() or "PASSWORD=" not in s
    assert LONG_BODY[:80] not in s


def test_adversarial_hydrate_redact_drops_body_and_key():
    c = _poisoned()
    red = redact_state([c])
    d = red[0].model_dump(mode="json")
    _assert_clean(d)
    assert_no_secrets(d)
    assert "content" not in d
    assert "secret" not in d


def test_adversarial_fakejev_hydrate_outbound_clean():
    client = FakeJev()
    client.decide_hydrate("q", [_poisoned()])
    _assert_clean(client.last_outbound)
    assert_no_secrets(client.last_outbound)


def test_adversarial_httpjev_hydrate_outbound_clean_no_network():
    """HttpJev redacts before POST; missing key → denied, outbound still clean."""
    client = HttpJev(api_key="")  # triggers denied before network
    # decide_hydrate still builds outbound via redact before _post
    # Empty api_key: _headers raises → denied; but last_outbound set first.
    out = client.decide_hydrate("q", [_poisoned()])
    assert out[0].failed
    _assert_clean(client.last_outbound)
    assert_no_secrets(client.last_outbound)


def test_adversarial_tag_side_channel_blocked_by_assert():
    """Tags carrying secret-like substrings must fail assert_no_secrets preflight."""
    c = _poisoned(tags=[f"exfil:{FAKE_KEY}", FAKE_EMAIL])
    payload = redact_to_dicts([c])
    # redact keeps tags as-is (allowlisted field) — assert_no_secrets must catch values
    with pytest.raises(AssertionError):
        assert_no_secrets(payload)


def test_adversarial_node_id_side_channel_blocked():
    c = _poisoned(node_id=f"id_with_{FAKE_KEY}")
    payload = redact_to_dicts([c])
    with pytest.raises(AssertionError):
        assert_no_secrets(payload)


def test_adversarial_memory_gate_never_egress_body():
    client = FakeJev(confidence_override=0.99)
    gate = MemoryGate(client=client)
    gate.evaluate("prefs", [_poisoned()])
    _assert_clean(client.last_outbound)
    _assert_clean(gate.last_redacted)


def test_adversarial_emit_strips_secret_keys_and_body():
    """Allowlist drops email/content/api_key; summary becomes hash+chars only."""
    client = FakeJev(confidence_override=0.99)
    gate = EmitEgressGate(client=client)
    gate.evaluate(
        "agent_channel",
        {
            "proposed_summary": "safe summary",
            "content": LONG_BODY,
            "body": LONG_BODY,
            "api_key": FAKE_KEY,
            "secret": FAKE_KEY,
            "email": FAKE_EMAIL,
            "node_id": "e1",
        },
    )
    _assert_clean(gate.last_outbound)
    _assert_clean(client.last_outbound)
    for bad in ("content", "body", "api_key", "secret", "email", "proposed_summary"):
        assert bad not in gate.last_outbound
    assert gate.last_outbound.get("node_id") == "e1"
    assert "proposed_summary_sha256" in gate.last_outbound
    assert gate.last_outbound.get("proposed_chars") == len("safe summary")


def test_adversarial_emit_summary_with_key_never_egressed():
    """Secret-bearing free-text summary must not appear outbound (hash only)."""
    client = FakeJev()
    gate = EmitEgressGate(client=client)
    gate.evaluate(
        "agent_channel",
        {"proposed_summary": f"leak {FAKE_KEY} {FAKE_EMAIL}", "node_id": "e1"},
    )
    blob = str(gate.last_outbound) + str(client.last_outbound)
    assert FAKE_KEY not in blob
    assert FAKE_EMAIL not in blob
    assert "proposed_summary" not in gate.last_outbound
    assert "proposed_summary_sha256" in gate.last_outbound


def test_adversarial_writeback_rejects_body_fields():
    client = FakeJev(confidence_override=0.99)
    gate = WritebackGate(client=client)
    d = gate.evaluate(
        "wiki_stage",
        {
            "node_id": "n1",
            "kind": "fact",
            "tags": ["ok"],
            "salience": 0.5,
            "content": LONG_BODY,
            "body": LONG_BODY,
            "secret": FAKE_KEY,
            "email": FAKE_EMAIL,
            "api_key": FAKE_KEY,
        },
    )
    assert d is not None
    _assert_clean(gate.last_outbound)
    _assert_clean(client.last_outbound)
    for bad in ("content", "body", "secret", "email", "api_key"):
        assert bad not in gate.last_outbound


def test_adversarial_writeback_tag_side_channel_caught():
    client = FakeJev()
    gate = WritebackGate(client=client)
    with pytest.raises(AssertionError):
        gate.evaluate(
            "graph_durable",
            {
                "node_id": "n1",
                "kind": "fact",
                "tags": [FAKE_EMAIL, f"k={FAKE_KEY}"],
                "salience": 0.5,
            },
        )


def test_adversarial_long_body_never_in_redacted_dicts():
    payload = redact_to_dicts([_poisoned()])
    joined = str(payload)
    assert len(joined) < 2000  # no 4k body
    _assert_clean(payload)


def test_escalation_allowlist_drops_proposed_summary_and_email():
    """David: EscalationRecord uses positive allowlist — free text / email never kept."""
    from remember_me.policy import escalate_human

    rec = escalate_human(
        node_id="n1",
        source_gate="emit",
        confidence=0.7,
        proposed_action="allow_emit",
        reason="mid-band",
        redacted_snapshot={
            "node_id": "n1",
            "local_score": 0.7,
            "tags": ["preference"],
            "proposed_summary": f"user email {FAKE_EMAIL} key={FAKE_KEY}",
            "email": FAKE_EMAIL,
            "content": LONG_BODY,
            "api_key": FAKE_KEY,
            "proposed_chars": 12,
            "proposed_summary_sha256": "abc123",
        },
    )
    snap = rec.redacted_snapshot
    assert "proposed_summary" not in snap
    assert "email" not in snap
    assert "content" not in snap
    assert "api_key" not in snap
    assert snap.get("node_id") == "n1"
    assert snap.get("local_score") == 0.7
    assert snap.get("proposed_chars") == 12
    assert snap.get("proposed_summary_sha256") == "abc123"
    assert FAKE_KEY not in str(snap)
    assert FAKE_EMAIL not in str(snap)


def test_escalation_allowlist_rejects_novel_free_text_keys():
    from remember_me.policy import escalate_human

    rec = escalate_human(
        node_id="n2",
        source_gate="hydrate",
        confidence=0.6,
        proposed_action="hydrate_full",
        reason="mid",
        redacted_snapshot={
            "note": "should not survive",
            "summary": f"leak {FAKE_KEY}",
            "query_preview": "raw ask",
            "kind": "fact",
        },
    )
    snap = rec.redacted_snapshot
    assert "note" not in snap
    assert "summary" not in snap
    assert "query_preview" not in snap
    assert snap.get("kind") == "fact"
