"""Policy thresholds and fail-closed decision mapping.

Defaults:
  T_accept >= 0.85 → hydrate_full / allow_emit / allow_writeback
  0.55–0.85       → escalate_human (first-class; structured EscalationRecord)
  < 0.55          → skip / deny_emit / deny_writeback
  Jev errors      → FAIL-CLOSED (never silent allow)
"""

from __future__ import annotations

from typing import Any

from remember_me.types import (
    Q_EMIT_ACTION,
    Q_HYDRATE_ACTION,
    Q_LEAK_RISK,
    Q_NEED_FOR_NEXT_TURN,
    Q_NETWORK_ROUTE,
    Q_ON_TOPIC,
    Q_STILL_MATTERS,
    Q_TRIGGER_REFLECT,
    Q_WRITEBACK_ACTION,
    Q_WRITEBACK_NEED,
    Q_WRITEBACK_STILL_SAFE,
    Candidate,
    EmitAction,
    EmitDecision,
    EscalationRecord,
    GateDecision,
    HydrateAction,
    JevBatchResponse,
    NetworkRoute,
    WritebackAction,
    WritebackDecision,
)

T_ACCEPT = 0.85
T_ESCALATE = 0.55


def escalate_human(
    *,
    node_id: str,
    source_gate: str,
    confidence: float,
    proposed_action: str,
    reason: str,
    redacted_snapshot: dict[str, Any],
    band: str = "mid",
) -> EscalationRecord:
    """Build a structured human/policy handoff (positive ALLOWLIST snapshot only).

    David correction: denylist is a reproducible leak surface (e.g. ``email``,
    ``proposed_summary``). Free text is forbidden — use ``proposed_chars`` /
    ``proposed_summary_sha256`` only when a summary fingerprint is required.
    """
    from remember_me.redact import ESCALATION_SNAPSHOT_ALLOWLIST, allowlist_snapshot

    safe = allowlist_snapshot(redacted_snapshot, allowed=ESCALATION_SNAPSHOT_ALLOWLIST)
    for banned in ("proposed_summary", "summary", "query", "query_preview", "raw_query"):
        safe.pop(banned, None)
    return EscalationRecord(
        node_id=node_id,
        source_gate=source_gate,
        band=band,
        confidence=confidence,
        proposed_action=proposed_action,
        reason=reason,
        redacted_snapshot=safe,
    )


def map_hydrate_action(
    response: JevBatchResponse,
    candidate: Candidate,
    *,
    t_accept: float = T_ACCEPT,
    t_escalate: float = T_ESCALATE,
    fail_closed_top_k_fallback: bool = False,
    fail_closed_rank: int = 0,
    fail_closed_k: int = 0,
) -> GateDecision:
    """Map a Jev batch response + confidence to a local GateDecision.

    Mid-band / conflicts → first-class ``escalate_human`` + EscalationRecord.
    Fail-closed → skip (or optional local top-k stub-only fallback).
    """
    snap = {
        "node_id": candidate.node_id,
        "kind": candidate.kind.value,
        "tags": list(candidate.tags),
        "local_score": candidate.local_score,
        "tokens_est": candidate.tokens_est,
    }

    if response.failed:
        if fail_closed_top_k_fallback and fail_closed_rank < fail_closed_k:
            return GateDecision(
                node_id=candidate.node_id,
                action=HydrateAction.STUB_ONLY,
                confidence=0.0,
                fail_closed=True,
                reason=f"fail_closed:{_failure_reason(response)}; local stub fallback",
                local_score=candidate.local_score,
            )
        return GateDecision(
            node_id=candidate.node_id,
            action=HydrateAction.SKIP,
            confidence=0.0,
            fail_closed=True,
            reason=f"fail_closed:{_failure_reason(response)}",
            local_score=candidate.local_score,
        )

    hydrate_res = response.results.get(Q_HYDRATE_ACTION)
    need_res = response.results.get(Q_NEED_FOR_NEXT_TURN)
    matters_res = response.results.get(Q_STILL_MATTERS)
    route_res = response.results.get(Q_NETWORK_ROUTE)
    reflect_res = response.results.get(Q_TRIGGER_REFLECT)

    conf = float(hydrate_res.confidence) if hydrate_res else 0.0
    raw_action = _parse_action(hydrate_res.value if hydrate_res else None)
    need = float(need_res.value) if need_res and need_res.value is not None else None
    still = bool(matters_res.value) if matters_res and matters_res.value is not None else None
    route = _parse_route(route_res.value if route_res else None)
    reflect = bool(reflect_res.value) if reflect_res and reflect_res.value is not None else None

    escalation: EscalationRecord | None = None

    if conf >= t_accept:
        if raw_action == HydrateAction.ESCALATE_HUMAN:
            action = HydrateAction.ESCALATE_HUMAN
            reason = f"accept conf={conf:.3f}; raw escalate_human"
        elif raw_action == HydrateAction.OTHER:
            action = HydrateAction.HYDRATE_FULL
            reason = f"accept conf={conf:.3f}"
        else:
            action = raw_action
            reason = f"accept conf={conf:.3f}"
    elif conf >= t_escalate:
        # Mid band: first-class escalate_human (never auto hydrate_full).
        if raw_action == HydrateAction.SKIP:
            action = HydrateAction.SKIP
            reason = f"escalate-band conf={conf:.3f}; raw skip"
        elif raw_action == HydrateAction.STUB_ONLY:
            action = HydrateAction.STUB_ONLY
            reason = f"escalate-band conf={conf:.3f}; raw stub_only"
            escalation = escalate_human(
                node_id=candidate.node_id,
                source_gate="hydrate",
                confidence=conf,
                proposed_action=raw_action.value,
                reason=reason,
                redacted_snapshot=snap,
                band="mid",
            )
        else:
            action = HydrateAction.ESCALATE_HUMAN
            reason = f"escalate_human conf={conf:.3f}"
            escalation = escalate_human(
                node_id=candidate.node_id,
                source_gate="hydrate",
                confidence=conf,
                proposed_action=raw_action.value,
                reason=reason,
                redacted_snapshot=snap,
                band="mid",
            )
    else:
        action = HydrateAction.SKIP
        reason = f"reject conf={conf:.3f}"

    # Conflicts: still_matters=false with full hydrate → escalate_human.
    if still is False and action == HydrateAction.HYDRATE_FULL:
        action = HydrateAction.ESCALATE_HUMAN
        reason += "; still_matters=false→escalate_human"
        escalation = escalate_human(
            node_id=candidate.node_id,
            source_gate="hydrate",
            confidence=conf,
            proposed_action=HydrateAction.HYDRATE_FULL.value,
            reason=reason,
            redacted_snapshot=snap,
            band="conflict",
        )

    if raw_action == HydrateAction.ESCALATE_HUMAN and conf >= t_escalate:
        action = HydrateAction.ESCALATE_HUMAN
        if "escalate_human" not in reason:
            reason += "; raw escalate_human"
        if escalation is None:
            escalation = escalate_human(
                node_id=candidate.node_id,
                source_gate="hydrate",
                confidence=conf,
                proposed_action=raw_action.value,
                reason=reason,
                redacted_snapshot=snap,
                band="mid",
            )

    return GateDecision(
        node_id=candidate.node_id,
        action=action,
        confidence=conf,
        need_score=need,
        still_matters=still,
        network_route=route,
        trigger_reflect=reflect,
        fail_closed=False,
        reason=reason,
        local_score=candidate.local_score,
        escalation=escalation,
    )


def map_emit_action(
    response: JevBatchResponse,
    *,
    sink: str = "agent_channel",
    proposed_chars: int = 0,
    t_accept: float = T_ACCEPT,
    t_escalate: float = T_ESCALATE,
    redacted_snapshot: dict[str, Any] | None = None,
) -> EmitDecision:
    """Map egress Jev response → allow_emit | deny/block | escalate_human.

    Fail-closed: never silent allow_emit on error → deny_emit/block.
    """
    snap = dict(redacted_snapshot or {})
    if response.failed:
        return EmitDecision(
            sink=sink,
            action=EmitAction.DENY_EMIT,
            confidence=0.0,
            fail_closed=True,
            reason=f"fail_closed:{_failure_reason(response)}→deny_emit",
            proposed_chars=proposed_chars,
        )

    emit_res = response.results.get(Q_EMIT_ACTION)
    leak_res = response.results.get(Q_LEAK_RISK)
    topic_res = response.results.get(Q_ON_TOPIC)

    conf = float(emit_res.confidence) if emit_res else 0.0
    raw = _parse_emit(emit_res.value if emit_res else None)
    leak = bool(leak_res.value) if leak_res and leak_res.value is not None else None
    on_topic = bool(topic_res.value) if topic_res and topic_res.value is not None else None

    escalation: EscalationRecord | None = None

    if conf >= t_accept:
        action = raw if raw is not None else EmitAction.ALLOW_EMIT
        if action == EmitAction.OTHER:
            action = EmitAction.ALLOW_EMIT
        reason = f"accept conf={conf:.3f}"
    elif conf >= t_escalate:
        if raw in (EmitAction.DENY_EMIT, EmitAction.BLOCK):
            action = EmitAction.DENY_EMIT
            reason = f"escalate-band conf={conf:.3f}; raw deny"
        else:
            action = EmitAction.ESCALATE_HUMAN
            reason = f"escalate_human conf={conf:.3f}"
            escalation = escalate_human(
                node_id=str(snap.get("node_id") or "egress"),
                source_gate="emit",
                confidence=conf,
                proposed_action=(raw.value if raw else "allow_emit"),
                reason=reason,
                redacted_snapshot=snap,
                band="mid",
            )
    else:
        action = EmitAction.DENY_EMIT
        reason = f"reject conf={conf:.3f}→deny_emit"

    if leak is True and action == EmitAction.ALLOW_EMIT:
        action = EmitAction.ESCALATE_HUMAN
        reason += "; leak_risk=true→escalate_human"
        escalation = escalate_human(
            node_id=str(snap.get("node_id") or "egress"),
            source_gate="emit",
            confidence=conf,
            proposed_action=EmitAction.ALLOW_EMIT.value,
            reason=reason,
            redacted_snapshot=snap,
            band="conflict",
        )

    if on_topic is False and action == EmitAction.ALLOW_EMIT:
        action = EmitAction.DENY_EMIT
        reason += "; on_topic=false→deny_emit"

    # Normalize block → deny_emit for policy outcomes.
    if action == EmitAction.BLOCK:
        action = EmitAction.DENY_EMIT

    return EmitDecision(
        sink=sink,
        action=action,
        confidence=conf,
        leak_risk=leak,
        on_topic=on_topic,
        fail_closed=False,
        reason=reason,
        proposed_chars=proposed_chars,
        escalation=escalation,
    )


def map_writeback_action(
    response: JevBatchResponse,
    *,
    target: str = "graph_durable",
    node_id: str = "",
    t_accept: float = T_ACCEPT,
    t_escalate: float = T_ESCALATE,
    redacted_snapshot: dict[str, Any] | None = None,
) -> WritebackDecision:
    """Map writeback Jev response. Mid-band → escalate_human (no silent durable write)."""
    snap = dict(redacted_snapshot or {})
    nid = node_id or str(snap.get("node_id") or "unknown")

    if response.failed:
        return WritebackDecision(
            target=target,
            node_id=nid,
            action=WritebackAction.DENY_WRITEBACK,
            confidence=0.0,
            fail_closed=True,
            reason=f"fail_closed:{_failure_reason(response)}→deny_writeback",
        )

    wb_res = response.results.get(Q_WRITEBACK_ACTION)
    need_res = response.results.get(Q_WRITEBACK_NEED)
    safe_res = response.results.get(Q_WRITEBACK_STILL_SAFE)

    conf = float(wb_res.confidence) if wb_res else 0.0
    raw = _parse_writeback(wb_res.value if wb_res else None)
    still_safe = bool(safe_res.value) if safe_res and safe_res.value is not None else None
    _ = need_res  # optional Score retained for telemetry

    escalation: EscalationRecord | None = None

    if conf >= t_accept:
        action = raw if raw is not None else WritebackAction.ALLOW_WRITEBACK
        if action == WritebackAction.OTHER:
            action = WritebackAction.ALLOW_WRITEBACK
        reason = f"accept conf={conf:.3f}"
    elif conf >= t_escalate:
        if raw == WritebackAction.DENY_WRITEBACK:
            action = WritebackAction.DENY_WRITEBACK
            reason = f"escalate-band conf={conf:.3f}; raw deny"
        elif raw == WritebackAction.STAGE_ONLY:
            action = WritebackAction.STAGE_ONLY
            reason = f"escalate-band conf={conf:.3f}; stage_only"
        else:
            action = WritebackAction.ESCALATE_HUMAN
            reason = f"escalate_human conf={conf:.3f}"
            escalation = escalate_human(
                node_id=nid,
                source_gate="writeback",
                confidence=conf,
                proposed_action=(raw.value if raw else "allow_writeback"),
                reason=reason,
                redacted_snapshot=snap,
                band="mid",
            )
    else:
        action = WritebackAction.DENY_WRITEBACK
        reason = f"reject conf={conf:.3f}→deny_writeback"

    if still_safe is False and action == WritebackAction.ALLOW_WRITEBACK:
        action = WritebackAction.DENY_WRITEBACK
        reason += "; still_safe=false→deny_writeback"

    return WritebackDecision(
        target=target,
        node_id=nid,
        action=action,
        confidence=conf,
        still_safe=still_safe,
        fail_closed=False,
        reason=reason,
        escalation=escalation,
    )


def assert_no_rerank(
    before: list[Candidate],
    after_candidates: list[Candidate],
) -> None:
    """Raise AssertionError if node_id order or local_score changed (Jev must not rank)."""
    if len(before) != len(after_candidates):
        raise AssertionError(
            f"candidate count changed: {len(before)} → {len(after_candidates)}"
        )
    for b, a in zip(before, after_candidates, strict=True):
        if b.node_id != a.node_id:
            raise AssertionError(f"order mutated: {b.node_id} → {a.node_id}")
        if b.local_score != a.local_score:
            raise AssertionError(
                f"local_score mutated for {b.node_id}: {b.local_score} → {a.local_score}"
            )


def _failure_reason(response: JevBatchResponse) -> str:
    if response.timed_out:
        return "timeout"
    if response.denied:
        return "denied"
    if response.malformed:
        return "malformed"
    return response.error or "error"


def _parse_action(value: object) -> HydrateAction:
    if value is None:
        return HydrateAction.OTHER
    if isinstance(value, HydrateAction):
        return value
    s = str(value).strip().lower()
    try:
        return HydrateAction(s)
    except ValueError:
        return HydrateAction.OTHER


def _parse_emit(value: object) -> EmitAction | None:
    if value is None:
        return None
    if isinstance(value, EmitAction):
        return value
    s = str(value).strip().lower()
    if s == "block":
        return EmitAction.DENY_EMIT
    try:
        return EmitAction(s)
    except ValueError:
        return None


def _parse_writeback(value: object) -> WritebackAction | None:
    if value is None:
        return None
    if isinstance(value, WritebackAction):
        return value
    try:
        return WritebackAction(str(value).strip().lower())
    except ValueError:
        return None


def _parse_route(value: object) -> NetworkRoute | None:
    if value is None:
        return None
    if isinstance(value, NetworkRoute):
        return value
    try:
        return NetworkRoute(str(value).strip().lower())
    except ValueError:
        return None
