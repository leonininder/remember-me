"""FakeJevReconcileGate + ReconcileEngine C1 path (unit)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from remember_me.tfl.drain import assert_never_md_append, drain_quarantine
from remember_me.tfl.ledger import FactLedger
from remember_me.tfl.policy import ApplyAction
from remember_me.tfl.quarantine import QuarantineQueue
from remember_me.tfl.questions import RECONCILE_QUESTION_IDS, build_reconcile_questions
from remember_me.tfl.reconcile import FakeJevReconcileGate, ReconcileEngine
from remember_me.tfl.types import CandidateFact
from remember_me.types import JEV_MODEL_PIN


def _cand(**kwargs) -> CandidateFact:
    base = dict(
        entity="user",
        attribute="weather",
        qualifier="local",
        value_struct={"condition": "rainy"},
        observed_at=datetime(2026, 9, 22, 9, 0, tzinfo=UTC),
        source_event_id="evt_1",
        extract_method="deterministic",
        salience_hint="ephemeral",
    )
    base.update(kwargs)
    return CandidateFact(**base)


def test_question_pack_choice_criteria_are_dicts():
    qs = build_reconcile_questions()
    assert set(qs.keys()) == set(RECONCILE_QUESTION_IDS)
    assert isinstance(qs["relation"]["criteria"], dict)
    assert "supersedes" in qs["relation"]["criteria"]
    assert isinstance(qs["ttl_urgency"]["criteria"], list)
    assert qs["ttl_urgency"]["criteria"][0] == "permanent"
    assert qs["salience_tier"]["type"] == "choice"


def test_fake_gate_pins_jev_1_13_0():
    g = FakeJevReconcileGate()
    assert g.model_pin == JEV_MODEL_PIN == "jev-1.13.0"


def test_weather_supersede_sunny_to_rainy(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.sqlite")
    ledger.upsert(
        "user.weather.local",
        {"condition": "sunny"},
        source_event_id="d1",
        salience_tier="ephemeral",
    )
    gate = FakeJevReconcileGate(
        answers={
            "relation": "supersedes",
            "should_forget_incumbent": True,
            "needs_human": False,
            "salience_tier": "ephemeral",
            "ttl_urgency": "hours",
        }
    )
    q = QuarantineQueue(bound_n=16, spill_dir=tmp_path / "spill")
    eng = ReconcileEngine(ledger, gate, quarantine=q)
    result = eng.reconcile_candidate(_cand())
    assert result.applied
    assert result.action == ApplyAction.SUPERSEDE
    active = ledger.get_active("user.weather.local")
    assert active is not None
    assert active.value_struct == {"condition": "rainy"}
    ledger.assert_no_dual_active()
    assert q.total_count() == 0


def test_gate_timeout_quarantines_never_applies(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.jsonl")
    gate = FakeJevReconcileGate(force_timeout=True)
    q = QuarantineQueue(bound_n=8, spill_dir=tmp_path / "spill")
    eng = ReconcileEngine(ledger, gate, quarantine=q)
    result = eng.reconcile_candidate(_cand())
    assert not result.applied
    assert result.action == ApplyAction.QUARANTINE
    assert result.fail_closed
    assert q.total_count() == 1
    assert ledger.get_active("user.weather.local") is None


def test_contradicts_no_forget_escalates_and_quarantines(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.sqlite")
    ledger.upsert("user.weather.local", {"condition": "sunny"}, source_event_id="d1")
    gate = FakeJevReconcileGate(
        answers={
            "relation": "contradicts",
            "should_forget_incumbent": False,
            "needs_human": False,
        }
    )
    q = QuarantineQueue(bound_n=8, spill_dir=tmp_path / "spill")
    eng = ReconcileEngine(ledger, gate, quarantine=q)
    result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.ESCALATE_HUMAN
    assert not result.applied
    assert q.total_count() == 1
    # incumbent untouched
    assert ledger.get_active("user.weather.local").value_struct == {"condition": "sunny"}


def test_drain_retry_applies_then_clears(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.sqlite")
    q = QuarantineQueue(bound_n=16, spill_dir=tmp_path / "spill")
    # First: timeout → quarantine
    bad = FakeJevReconcileGate(force_timeout=True)
    eng = ReconcileEngine(ledger, bad, quarantine=q)
    eng.reconcile_candidate(_cand())
    assert q.total_count() == 1

    # Swap to healthy gate and drain
    good = FakeJevReconcileGate(
        answers={
            "relation": "supersedes",
            "should_forget_incumbent": True,
            "needs_human": False,
            "salience_tier": "ephemeral",
        }
    )
    eng.gate = good
    report = drain_quarantine(eng, q, limit=10)
    assert report.applied == 1
    assert ledger.get_active("user.weather.local").value_struct["condition"] == "rainy"
    assert_never_md_append()


def test_drain_gate_unhealthy_escalates_requeues(tmp_path: Path):
    ledger = FactLedger(tmp_path / "l.sqlite")
    q = QuarantineQueue(bound_n=16, spill_dir=tmp_path / "spill")
    q.enqueue(
        _cand().model_dump(mode="json"),
        reason="prior",
        fact_key_hint="user.weather.local",
    )
    eng = ReconcileEngine(ledger, FakeJevReconcileGate(), quarantine=q)
    report = drain_quarantine(eng, q, gate_healthy=False)
    assert report.escalated == 1
    assert q.total_count() == 1  # requeued, not dropped
