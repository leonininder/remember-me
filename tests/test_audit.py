"""Persistent GateAuditRecord store — write + read + redaction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from remember_me.audit import (
    GateAuditRecord,
    GateAuditStore,
    record_from_emit,
    record_from_escalation,
    record_from_hydrate,
    record_from_writeback,
)
from remember_me.gates import EmitEgressGate, MemoryGate, WritebackGate
from remember_me.jev_client import FakeJev
from remember_me.types import (
    Candidate,
    EmitAction,
    EmitDecision,
    EscalationRecord,
    GateDecision,
    HydrateAction,
    NodeKind,
    WritebackAction,
    WritebackDecision,
)

FAKE_KEY = "sk-AUDIT_SHOULD_NOT_PERSIST"
FAKE_EMAIL = "audit-leak@example.com"


def test_audit_jsonl_write_read(tmp_path: Path):
    store = GateAuditStore(tmp_path / "gate_audit.jsonl")
    r = GateAuditRecord(
        source_gate="hydrate",
        node_id="n1",
        action="skip",
        confidence=0.0,
        fail_closed=True,
        reason="fail_closed:http_403",
        redacted_snapshot={"local_score": 0.8, "tags": ["preference"]},
    )
    store.append(r)
    store.append(
        GateAuditRecord(
            source_gate="emit",
            action="deny_emit",
            confidence=0.0,
            fail_closed=True,
            sink_or_target="audit_log",
            reason="fail_closed:timeout",
        )
    )
    rows = store.read_all()
    assert len(rows) == 2
    assert rows[0].node_id == "n1"
    assert rows[0].fail_closed is True
    assert rows[1].source_gate == "emit"
    assert rows[0].redacted_snapshot["local_score"] == 0.8


def test_audit_sqlite_write_read(tmp_path: Path):
    store = GateAuditStore(tmp_path / "gate_audit.sqlite")
    store.append(
        GateAuditRecord(
            source_gate="writeback",
            node_id="w1",
            action="deny_writeback",
            fail_closed=True,
            sink_or_target="wiki_stage",
        )
    )
    rows = store.read_all()
    assert len(rows) == 1
    assert rows[0].node_id == "w1"
    assert rows[0].source_gate == "writeback"


def test_audit_redacts_secret_keys_from_snapshot(tmp_path: Path):
    store = GateAuditStore(tmp_path / "a.jsonl")
    store.append(
        GateAuditRecord(
            source_gate="hydrate",
            node_id="n",
            action="escalate_human",
            redacted_snapshot={
                "local_score": 0.6,
                "content": "BODY",
                "secret": FAKE_KEY,
                "api_key": FAKE_KEY,
                "email": FAKE_EMAIL,
                "body": "xxx",
                "tags": ["ok"],
            },
        )
    )
    row = store.read_all()[0]
    snap = row.redacted_snapshot
    assert "content" not in snap
    assert "secret" not in snap
    assert "api_key" not in snap
    assert "email" not in snap
    assert "body" not in snap
    assert snap.get("tags") == ["ok"]
    raw = (tmp_path / "a.jsonl").read_text()
    assert FAKE_KEY not in raw
    assert FAKE_EMAIL not in raw
    assert "BODY" not in raw


def test_audit_drops_secret_like_string_values(tmp_path: Path):
    store = GateAuditStore(tmp_path / "b.jsonl")
    store.append(
        GateAuditRecord(
            source_gate="emit",
            action="deny_emit",
            redacted_snapshot={
                "note": f"see {FAKE_KEY}",
                "contact": FAKE_EMAIL,
                "kind": "fact",
                "tags": ["preference", FAKE_EMAIL],
            },
        )
    )
    snap = store.read_all()[0].redacted_snapshot
    assert "note" not in snap
    assert "contact" not in snap
    assert snap["kind"] == "fact"
    # email-like tag values stripped; clean tags kept
    assert FAKE_EMAIL not in str(snap.get("tags"))
    assert "preference" in snap.get("tags", [])
    assert FAKE_KEY not in (tmp_path / "b.jsonl").read_text()


def test_audit_append_rejects_secret_in_reason(tmp_path: Path):
    store = GateAuditStore(tmp_path / "c.jsonl")
    with pytest.raises(AssertionError):
        store.append(
            GateAuditRecord(
                source_gate="hydrate",
                action="skip",
                reason=f"debug {FAKE_KEY}",
            )
        )


def test_record_from_gate_decisions(tmp_path: Path):
    store = GateAuditStore(tmp_path / "d.jsonl")
    h = GateDecision(
        node_id="n1",
        action=HydrateAction.SKIP,
        confidence=0.0,
        fail_closed=True,
        reason="fail_closed:timeout",
        local_score=0.7,
    )
    e = EmitDecision(
        sink="agent_channel",
        action=EmitAction.DENY_EMIT,
        confidence=0.0,
        fail_closed=True,
        reason="fail_closed:http_401",
    )
    w = WritebackDecision(
        target="wiki_stage",
        node_id="n2",
        action=WritebackAction.DENY_WRITEBACK,
        confidence=0.0,
        fail_closed=True,
        reason="fail_closed:malformed",
    )
    esc = EscalationRecord(
        node_id="n3",
        source_gate="hydrate",
        band="mid",
        confidence=0.7,
        proposed_action="hydrate_full",
        reason="mid-band",
        redacted_snapshot={"tags": ["t"], "content": "NOPE", "secret": FAKE_KEY},
    )
    store.append(record_from_hydrate(h))
    store.append(record_from_emit(e))
    store.append(record_from_writeback(w))
    store.append(record_from_escalation(esc))
    rows = store.read_all()
    assert len(rows) == 4
    assert rows[0].source_gate == "hydrate" and rows[0].fail_closed
    assert rows[1].source_gate == "emit" and rows[1].sink_or_target == "agent_channel"
    assert rows[2].source_gate == "writeback"
    assert rows[3].source_gate == "escalate"
    assert "content" not in rows[3].redacted_snapshot
    assert "secret" not in rows[3].redacted_snapshot
    assert FAKE_KEY not in (tmp_path / "d.jsonl").read_text()


def test_audit_from_live_gates(tmp_path: Path):
    """End-to-end: FakeJev force_timeout → fail-closed decisions → audit store."""
    store = GateAuditStore(tmp_path / "e.jsonl")
    client = FakeJev(force_timeout=True)
    cand = Candidate(
        node_id="n1",
        kind=NodeKind.FACT,
        tags=["preference"],
        degree=0,
        last_touch=datetime.now(UTC),
        local_score=0.9,
        tokens_est=5,
        content=f"secret body {FAKE_KEY}",
    )
    for d in MemoryGate(client=client).evaluate("q", [cand]):
        store.append(record_from_hydrate(d))
    store.append(
        record_from_emit(
            EmitEgressGate(client=FakeJev(force_deny=True)).evaluate(
                "audit_log", {"proposed_summary": "hi"}
            )
        )
    )
    store.append(
        record_from_writeback(
            WritebackGate(client=FakeJev(force_malformed=True)).evaluate(
                "wiki_stage",
                {"node_id": "n1", "kind": "fact", "tags": ["t"], "salience": 0.5},
            )
        )
    )
    rows = store.read_all()
    assert all(r.fail_closed for r in rows)
    blob = (tmp_path / "e.jsonl").read_text()
    assert FAKE_KEY not in blob
    assert "secret body" not in blob
