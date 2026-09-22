"""APPLY policy table — PLAN §4.6 (no merge; contradicts×¬forget → escalate)."""

from __future__ import annotations

from remember_me.tfl.policy import (
    ApplyAction,
    answers_from_override,
    map_reconcile_policy,
)


def _ans(**kwargs):
    base = {
        "relation": "same_fact",
        "relation_confidence": 0.99,
        "should_forget_incumbent": False,
        "needs_human": False,
        "salience_tier": "routine",
        "ttl_urgency": "permanent",
    }
    base.update(kwargs)
    return answers_from_override(base)


def test_same_fact_metadata_upsert():
    d = map_reconcile_policy(
        _ans(relation="same_fact"),
        has_incumbent=True,
        new_value_struct={"condition": "sunny"},
        incumbent_value_struct={"condition": "sunny"},
    )
    assert d.action == ApplyAction.UPSERT


def test_same_fact_material_change_becomes_supersedes():
    d = map_reconcile_policy(
        _ans(relation="same_fact", should_forget_incumbent=True),
        has_incumbent=True,
        new_value_struct={"condition": "rainy"},
        incumbent_value_struct={"condition": "sunny"},
    )
    assert d.action == ApplyAction.SUPERSEDE


def test_supersedes_forget():
    d = map_reconcile_policy(
        _ans(relation="supersedes", should_forget_incumbent=True),
        has_incumbent=True,
        new_value_struct={"condition": "rainy"},
        incumbent_value_struct={"condition": "sunny"},
    )
    assert d.action == ApplyAction.SUPERSEDE


def test_supersedes_no_forget_upsert():
    d = map_reconcile_policy(
        _ans(relation="supersedes", should_forget_incumbent=False, ttl_urgency="permanent"),
        has_incumbent=True,
        new_value_struct={"condition": "rainy"},
        incumbent_value_struct={"condition": "sunny"},
    )
    assert d.action == ApplyAction.UPSERT


def test_contradicts_no_forget_escalates_mvp():
    d = map_reconcile_policy(
        _ans(relation="contradicts", should_forget_incumbent=False),
        has_incumbent=True,
        new_value_struct={"stance": "caution"},
        incumbent_value_struct={"stance": "play"},
    )
    assert d.action == ApplyAction.ESCALATE_HUMAN
    assert "contradicts" in d.reason


def test_contradicts_forget_supersede_adult_safety_demote():
    d = map_reconcile_policy(
        _ans(
            relation="contradicts",
            should_forget_incumbent=True,
            salience_tier="adult_safety",
        ),
        has_incumbent=True,
        new_value_struct={"stance": "caution_toxic"},
        incumbent_value_struct={"stance": "fun"},
        incumbent_salience="childhood_play",
    )
    assert d.action == ApplyAction.SUPERSEDE
    assert d.demote_profile is True


def test_needs_human_always_escalates():
    d = map_reconcile_policy(
        _ans(relation="supersedes", should_forget_incumbent=True, needs_human=True),
        has_incumbent=True,
        new_value_struct={"a": 1},
        incumbent_value_struct={"a": 0},
    )
    assert d.action == ApplyAction.ESCALATE_HUMAN


def test_noise_no_op():
    d = map_reconcile_policy(_ans(relation="noise"), has_incumbent=True)
    assert d.action == ApplyAction.NO_OP


def test_other_escalates():
    d = map_reconcile_policy(_ans(relation="other"), has_incumbent=True)
    assert d.action == ApplyAction.ESCALATE_HUMAN


def test_side_thread_c1_escalates():
    d = map_reconcile_policy(_ans(relation="side_thread"), has_incumbent=True)
    assert d.action == ApplyAction.ESCALATE_HUMAN


def test_low_relation_confidence_escalates():
    d = map_reconcile_policy(
        _ans(relation="supersedes", relation_confidence=0.6, should_forget_incumbent=True),
        has_incumbent=True,
        new_value_struct={"condition": "rainy"},
        incumbent_value_struct={"condition": "sunny"},
    )
    assert d.action == ApplyAction.ESCALATE_HUMAN
    assert "T_accept" in d.reason


def test_no_merge_action_exists_not_in_enum_values_for_apply_list():
    # PLAN: merge DROPPED
    assert "merge" not in {a.value for a in ApplyAction}
