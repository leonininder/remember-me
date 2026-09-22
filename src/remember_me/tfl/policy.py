"""APPLY policy table for TFL reconcile (PLAN §4.6).

No merge. MVP/C1: same-FactKey only; contradicts×¬forget → escalate_human.
T_accept=0.85 / T_escal=0.55 unless held-out evidence says otherwise.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from remember_me.policy import T_ACCEPT, T_ESCALATE
from remember_me.tfl.canonical import value_struct_equal
from remember_me.tfl.questions import (
    Q_NEEDS_HUMAN,
    Q_RELATION,
    Q_SALIENCE_TIER,
    Q_SHOULD_FORGET,
    Q_TTL_URGENCY,
    TTL_URGENCY_LEVELS,
)
from remember_me.tfl.redact import build_escalation_snapshot
from remember_me.types import EscalationRecord, JevBatchResponse, JevQuestionResult

# Re-export pin thresholds for TFL callers
T_ACCEPT_RECONCILE = T_ACCEPT  # 0.85
T_ESCALATE_RECONCILE = T_ESCALATE  # 0.55

RELATION_VALUES = frozenset(
    {"same_fact", "supersedes", "contradicts", "side_thread", "noise", "other"}
)
SALIENCE_VALUES = frozenset(
    {"childhood_play", "adult_safety", "routine", "ephemeral"}
)


class ApplyAction(StrEnum):
    UPSERT = "upsert"
    SUPERSEDE = "supersede"
    EXPIRE = "expire"
    TOMBSTONE = "tombstone"
    ESCALATE_HUMAN = "escalate_human"
    NO_OP = "no_op"
    QUARANTINE = "quarantine"  # gate unavailable — not an APPLY mutation


class ReconcileAnswers(BaseModel):
    """Normalized answers after mapping System One / FakeJev results."""

    relation: str = "other"
    relation_confidence: float = 0.0
    should_forget_incumbent: bool = False
    should_forget_confidence: float = 0.0
    needs_human: bool = False
    needs_human_confidence: float = 0.0
    salience_tier: str | None = "routine"
    ttl_urgency: str | None = "permanent"
    profile_worthiness: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class ApplyDecision(BaseModel):
    """Outcome of policy map — never silent md-append."""

    action: ApplyAction
    answers: ReconcileAnswers | None = None
    reason: str = ""
    fail_closed: bool = False
    demote_profile: bool = False  # adult_safety vs childhood_play
    prefer_expire: bool = False
    escalation: EscalationRecord | None = None
    quarantine_reason: str | None = None


def _noul_true(res: JevQuestionResult | None, *, threshold: float) -> tuple[bool, float]:
    """Interpret Noul: value bool + confidence (yes-probability)."""
    if res is None:
        return False, 0.0
    conf = float(res.confidence)
    # Prefer confidence threshold; also honor explicit True with conf>=threshold
    if conf >= threshold:
        return True, conf
    if bool(res.value) and conf >= threshold:
        return True, conf
    return False, conf


def _ttl_label(res: JevQuestionResult | None) -> str | None:
    if res is None or res.value is None:
        return None
    val = res.value
    if isinstance(val, str) and val in TTL_URGENCY_LEVELS:
        return val
    try:
        idx = int(val)
    except (TypeError, ValueError):
        return str(val) if val is not None else None
    # API may be 0- or 1-based; clamp into levels
    if 0 <= idx < len(TTL_URGENCY_LEVELS):
        return TTL_URGENCY_LEVELS[idx]
    if 1 <= idx <= len(TTL_URGENCY_LEVELS):
        return TTL_URGENCY_LEVELS[idx - 1]
    return None


def normalize_answers(
    results: dict[str, JevQuestionResult],
    *,
    t_accept: float = T_ACCEPT_RECONCILE,
    t_escalate: float = T_ESCALATE_RECONCILE,
) -> ReconcileAnswers:
    rel = results.get(Q_RELATION)
    forget = results.get(Q_SHOULD_FORGET)
    needs = results.get(Q_NEEDS_HUMAN)
    sal = results.get(Q_SALIENCE_TIER)
    ttl = results.get(Q_TTL_URGENCY)
    prof = results.get("profile_worthiness")

    relation = str(rel.value) if rel and rel.value is not None else "other"
    if relation not in RELATION_VALUES:
        relation = "other"
    rel_conf = float(rel.confidence) if rel else 0.0

    # PLAN: should_forget Noul high / above T_accept
    forget_bool, forget_conf = _noul_true(forget, threshold=t_accept)
    # needs_human true at escalate band
    needs_bool, needs_conf = _noul_true(needs, threshold=t_escalate)

    sal_val = str(sal.value) if sal and sal.value is not None else "routine"
    if sal_val not in SALIENCE_VALUES:
        sal_val = "routine"

    prof_bool = bool(prof.value) if prof and prof.value is not None else False

    return ReconcileAnswers(
        relation=relation,
        relation_confidence=rel_conf,
        should_forget_incumbent=forget_bool,
        should_forget_confidence=forget_conf,
        needs_human=needs_bool,
        needs_human_confidence=needs_conf,
        salience_tier=sal_val,
        ttl_urgency=_ttl_label(ttl) or "permanent",
        profile_worthiness=prof_bool,
        raw={k: v.model_dump(mode="json") for k, v in results.items()},
    )


def answers_from_override(override: dict[str, Any]) -> ReconcileAnswers:
    """Build answers from FakeJev-style flat dict (tests / drain retries)."""
    relation = str(override.get("relation", "other"))
    if relation not in RELATION_VALUES:
        relation = "other"
    sal = override.get("salience_tier", "routine")
    if sal not in SALIENCE_VALUES:
        sal = "routine"
    return ReconcileAnswers(
        relation=relation,
        relation_confidence=float(override.get("relation_confidence", 0.99)),
        should_forget_incumbent=bool(override.get("should_forget_incumbent", False)),
        should_forget_confidence=float(
            override.get("should_forget_confidence", 0.99)
            if override.get("should_forget_incumbent")
            else override.get("should_forget_confidence", 0.0)
        ),
        needs_human=bool(override.get("needs_human", False)),
        needs_human_confidence=float(
            override.get("needs_human_confidence", 0.99)
            if override.get("needs_human")
            else override.get("needs_human_confidence", 0.0)
        ),
        salience_tier=str(sal) if sal else "routine",
        ttl_urgency=str(override.get("ttl_urgency", "permanent")),
        profile_worthiness=bool(override.get("profile_worthiness", False)),
        raw=dict(override),
    )


def map_reconcile_policy(
    answers: ReconcileAnswers,
    *,
    has_incumbent: bool,
    new_value_struct: dict[str, Any] | None = None,
    incumbent_value_struct: dict[str, Any] | None = None,
    incumbent_salience: str | None = None,
    snapshot: dict[str, Any] | None = None,
    t_accept: float = T_ACCEPT_RECONCILE,
) -> ApplyDecision:
    """Map relation × should_forget × needs_human → APPLY (no merge)."""
    snap = build_escalation_snapshot(snapshot)

    def _escal(
        reason: str, *, band: str = "policy", proposed: str = "escalate_human"
    ) -> ApplyDecision:
        return ApplyDecision(
            action=ApplyAction.ESCALATE_HUMAN,
            answers=answers,
            reason=reason,
            fail_closed=True,
            escalation=EscalationRecord(
                node_id=str((snapshot or {}).get("fact_key") or "reconcile"),
                source_gate="reconcile",
                band=band,
                confidence=answers.relation_confidence,
                proposed_action=proposed,
                reason=reason,
                redacted_snapshot=snap,
            ),
        )

    # Any needs_human → escalate
    if answers.needs_human:
        return _escal(
            f"needs_human conf={answers.needs_human_confidence:.3f}",
            band="sensitive",
        )

    # Uncertain relation → escalate (fail-closed write)
    if answers.relation_confidence < t_accept and answers.relation != "noise":
        return _escal(
            f"relation conf={answers.relation_confidence:.3f} < T_accept={t_accept}",
            band="mid",
        )

    rel = answers.relation
    forget = answers.should_forget_incumbent
    ttl = answers.ttl_urgency or "permanent"
    prefer_expire = ttl in {"hours", "days"}

    if rel == "noise":
        return ApplyDecision(
            action=ApplyAction.NO_OP,
            answers=answers,
            reason="relation=noise",
        )

    if rel == "other":
        return _escal("relation=other", band="policy")

    if rel == "side_thread":
        # C1: cannot auto-mint distinct FactKey from same-key lookup → escalate
        return _escal(
            "side_thread on C1 same-FactKey path; needs new FactKey mint / human",
            band="policy",
            proposed="side_thread",
        )

    if not has_incumbent:
        # First belief for this key
        if rel in {"same_fact", "supersedes", "contradicts"}:
            return ApplyDecision(
                action=ApplyAction.UPSERT,
                answers=answers,
                reason=f"no incumbent; treat as upsert ({rel})",
            )
        return _escal(f"no incumbent; unsupported relation={rel}")

    # Material change under same_fact → treat as supersedes (Justin R4)
    effective = rel
    if (
        rel == "same_fact"
        and new_value_struct is not None
        and incumbent_value_struct is not None
        and not value_struct_equal(new_value_struct, incumbent_value_struct)
    ):
        effective = "supersedes"

    if effective == "same_fact":
        return ApplyDecision(
            action=ApplyAction.UPSERT,
            answers=answers,
            reason="same_fact metadata upsert; value_struct unchanged",
        )

    if effective == "supersedes":
        if forget:
            return ApplyDecision(
                action=ApplyAction.SUPERSEDE,
                answers=answers,
                reason="supersedes + should_forget",
                prefer_expire=False,
            )
        # supersedes × ¬forget → upsert new; prefer expire if ttl high
        if prefer_expire:
            return ApplyDecision(
                action=ApplyAction.SUPERSEDE,
                answers=answers,
                reason="supersedes ¬forget but ttl_urgency high → supersede/expire path",
                prefer_expire=True,
            )
        return ApplyDecision(
            action=ApplyAction.UPSERT,
            answers=answers,
            reason="supersedes ¬forget → upsert new version",
            prefer_expire=prefer_expire,
        )

    if effective == "contradicts":
        if forget:
            demote = (
                answers.salience_tier == "adult_safety"
                and incumbent_salience == "childhood_play"
            )
            return ApplyDecision(
                action=ApplyAction.SUPERSEDE,
                answers=answers,
                reason="contradicts + should_forget"
                + ("; demote childhood_play from profile" if demote else ""),
                demote_profile=demote,
            )
        # MVP/C1: always escalate (David R2 #6) — never dual-active
        return _escal(
            "contradicts × ¬forget → escalate_human (MVP/C1; no dual-active)",
            band="conflict",
        )

    return _escal(f"unhandled relation={effective}")


def map_gate_failure(
    response: JevBatchResponse,
    *,
    snapshot: dict[str, Any] | None = None,
) -> ApplyDecision:
    """Deny / timeout / malformed → quarantine (never apply, never md-append)."""
    if response.denied:
        reason = f"gate_denied:{response.error or 'denied'}"
    elif response.timed_out:
        reason = f"gate_timeout:{response.error or 'timeout'}"
    elif response.malformed:
        reason = f"gate_malformed:{response.error or 'malformed'}"
    else:
        reason = f"gate_failed:{response.error or 'unknown'}"
    snap = build_escalation_snapshot(
        {**(snapshot or {}), "gate_error": reason, "quarantine_reason": reason}
    )
    return ApplyDecision(
        action=ApplyAction.QUARANTINE,
        reason=reason,
        fail_closed=True,
        quarantine_reason=reason,
        escalation=EscalationRecord(
            node_id=str((snapshot or {}).get("fact_key") or "reconcile"),
            source_gate="reconcile",
            band="fail_closed",
            confidence=0.0,
            proposed_action="quarantine",
            reason=reason,
            redacted_snapshot=snap,
        ),
    )
