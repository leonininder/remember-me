"""Adversarial redact tests for RECONCILE_STATE / ESCALATION_SNAPSHOT allowlists."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from remember_me.tfl.ledger import FactLedger
from remember_me.tfl.quarantine import QuarantineQueue
from remember_me.tfl.reconcile import FakeJevReconcileGate, ReconcileEngine
from remember_me.tfl.redact import (
    ESCALATION_SNAPSHOT_ALLOWLIST,
    RECONCILE_STATE_ALLOWLIST,
    assert_reconcile_outbound_safe,
    build_escalation_snapshot,
    build_reconcile_state,
    clip_value_struct,
    fact_version_to_reconcile_dict,
)
from remember_me.tfl.types import CandidateFact, FactVersion

FAKE_KEY = "sk-ANTAGONIST_TFL_KEY_9f3a2b"
FAKE_EMAIL = "victim@evil.example.com"
DIARY = f"Dear diary PASSWORD=hunter2 {FAKE_KEY} {FAKE_EMAIL} " + ("X" * 500)


def test_allowlists_named_in_plan():
    assert "fact_key" in RECONCILE_STATE_ALLOWLIST
    assert "value_struct" in RECONCILE_STATE_ALLOWLIST
    assert "stub_hash" in RECONCILE_STATE_ALLOWLIST
    assert "conflict_keys" in RECONCILE_STATE_ALLOWLIST
    for extra in ("source_event_id", "extract_method", "quarantine_reason"):
        assert extra in ESCALATION_SNAPSHOT_ALLOWLIST
    # Forbidden by default
    for banned in ("email", "phone", "diary", "content", "body"):
        assert banned not in RECONCILE_STATE_ALLOWLIST
        assert banned not in ESCALATION_SNAPSHOT_ALLOWLIST


def test_clip_drops_diary_and_secret_keys():
    clipped = clip_value_struct(
        {"condition": "sunny", "diary": DIARY, "email": FAKE_EMAIL, "secret": FAKE_KEY}
    )
    assert "diary" not in clipped
    assert "email" not in clipped
    assert "secret" not in clipped
    assert clipped.get("condition") == "sunny"


def test_build_reconcile_state_strips_extras():
    state = build_reconcile_state(
        new_fact={
            "fact_key": "user.weather.local",
            "value_struct": {"condition": "rainy", "diary": DIARY},
            "email": FAKE_EMAIL,
            "content": DIARY,
            "confidence": 0.9,
            "stub_hash": "abc",
            "salience_tier": "ephemeral",
            "valid_from": None,
            "receive_ts": None,
            "conflict_keys": [],
        },
        incumbents=[
            {
                "fact_key": "user.weather.local",
                "value_struct": {"condition": "sunny"},
                "secret": FAKE_KEY,
                "confidence": 0.8,
                "stub_hash": "def",
                "salience_tier": "ephemeral",
                "valid_from": "2026-09-21T10:00:00+08:00",
                "receive_ts": "2026-09-21T10:00:01+08:00",
                "conflict_keys": [],
            }
        ],
    )
    assert_reconcile_outbound_safe(state)
    blob = str(state)
    assert FAKE_KEY not in blob
    assert FAKE_EMAIL not in blob
    assert "Dear diary" not in blob
    assert "content" not in state["new"]
    assert "email" not in state["new"]
    assert "secret" not in state["incumbents"][0]


def test_escalation_snapshot_allowlist_drops_diary():
    snap = build_escalation_snapshot(
        {
            "fact_key": "user.home.city",
            "value_struct": {"city": "Taipei"},
            "source_event_id": "e1",
            "extract_method": "deterministic",
            "quarantine_reason": "needs_human",
            "diary": DIARY,
            "email": FAKE_EMAIL,
            "api_key": FAKE_KEY,
        }
    )
    assert "diary" not in snap
    assert "email" not in snap
    assert "api_key" not in snap
    assert snap["fact_key"] == "user.home.city"
    assert snap["quarantine_reason"] == "needs_human"


def test_assert_rejects_secret_in_string_value():
    with pytest.raises(AssertionError):
        assert_reconcile_outbound_safe(
            {
                "new": {
                    "fact_key": "user.pref.theme",
                    "value_struct": {"theme": "dark"},
                    "confidence": 0.9,
                    "stub_hash": FAKE_KEY,  # secret-like
                    "salience_tier": "routine",
                    "valid_from": None,
                    "receive_ts": None,
                    "conflict_keys": [],
                },
                "incumbents": [],
            }
        )


def test_fake_gate_outbound_clean_with_poisoned_incumbent(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.sqlite")
    # Plant incumbent via ledger (clean value), then poison projection manually
    fv = ledger.upsert(
        "user.weather.local",
        {"condition": "sunny"},
        source_event_id="d1",
        salience_tier="ephemeral",
    )
    poisoned = fact_version_to_reconcile_dict(fv)
    poisoned["email"] = FAKE_EMAIL
    poisoned["value_struct"] = {"condition": "sunny", "notes": DIARY}
    state = build_reconcile_state(
        new_fact={
            "fact_key": "user.weather.local",
            "value_struct": {"condition": "rainy", "body": DIARY},
            "confidence": 0.9,
            "stub_hash": "x",
            "salience_tier": "ephemeral",
            "valid_from": None,
            "receive_ts": None,
            "conflict_keys": [],
            "secret": FAKE_KEY,
        },
        incumbents=[poisoned],
    )
    gate = FakeJevReconcileGate(
        answers={
            "relation": "supersedes",
            "should_forget_incumbent": True,
            "needs_human": False,
        }
    )
    gate.reconcile(state)
    assert_reconcile_outbound_safe(gate.last_outbound)
    blob = str(gate.last_outbound)
    assert FAKE_KEY not in blob
    assert FAKE_EMAIL not in blob
    assert "Dear diary" not in blob


def test_engine_never_egresses_diary_fields(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.jsonl")
    q = QuarantineQueue(bound_n=8, spill_dir=tmp_path / "spill")
    gate = FakeJevReconcileGate(
        answers={
            "relation": "supersedes",
            "should_forget_incumbent": True,
            "needs_human": False,
            "salience_tier": "ephemeral",
        }
    )
    eng = ReconcileEngine(ledger, gate, quarantine=q)
    cand = CandidateFact(
        entity="user",
        attribute="weather",
        qualifier="local",
        value_struct={"condition": "rainy"},
        observed_at=datetime(2026, 9, 22, tzinfo=UTC),
        source_event_id="evt",
        extract_method="deterministic",
    )
    eng.reconcile_candidate(cand)
    assert gate.last_outbound is not None
    assert_reconcile_outbound_safe(gate.last_outbound)


def test_fact_version_projection_only_allowlisted():
    fv = FactVersion(
        fact_key="user.pref.theme",
        value_struct={"theme": "dark"},
        valid_from=datetime.now(UTC),
        source_event_id="should-not-be-in-reconcile-core",
    )
    d = fact_version_to_reconcile_dict(fv)
    assert set(d.keys()) <= RECONCILE_STATE_ALLOWLIST
    assert "source_event_id" not in d
