"""Policy thresholds and fail-closed decision mapping.

Defaults (calibrate later):
  T_accept >= 0.85 → hydrate_full
  0.55–0.85       → escalate / stub
  < 0.55          → skip
  Jev errors      → FAIL-CLOSED (never open more secrets to cloud)
"""

from __future__ import annotations

from remember_me.types import (
    Q_HYDRATE_ACTION,
    Q_NEED_FOR_NEXT_TURN,
    Q_NETWORK_ROUTE,
    Q_STILL_MATTERS,
    Q_TRIGGER_REFLECT,
    Candidate,
    GateDecision,
    HydrateAction,
    JevBatchResponse,
    NetworkRoute,
)

T_ACCEPT = 0.85
T_ESCALATE = 0.55


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

    Fail-closed: on timeout/deny/malformed/error → skip (or optional local top-k
    stub-only fallback without sending more data to cloud).
    """
    if response.failed:
        # Fail-closed: do not hydrate full content into cloud-influenced path.
        # Optional: allow top-k by local TEMPR score as stub_only (local-only).
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

    # Confidence gates override raw action when below thresholds.
    if conf >= t_accept:
        action = raw_action if raw_action != HydrateAction.OTHER else HydrateAction.HYDRATE_FULL
        reason = f"accept conf={conf:.3f}"
    elif conf >= t_escalate:
        # Mid band: escalate / stub — never auto hydrate_full
        action = (
            HydrateAction.SKIP
            if raw_action == HydrateAction.SKIP
            else HydrateAction.STUB_ONLY
        )
        reason = f"escalate conf={conf:.3f}"
    else:
        action = HydrateAction.SKIP
        reason = f"reject conf={conf:.3f}"

    # Noul still_matters can force skip even at high conf.
    if still is False and action == HydrateAction.HYDRATE_FULL:
        action = HydrateAction.STUB_ONLY
        reason += "; still_matters=false→stub"

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


def _parse_route(value: object) -> NetworkRoute | None:
    if value is None:
        return None
    if isinstance(value, NetworkRoute):
        return value
    try:
        return NetworkRoute(str(value).strip().lower())
    except ValueError:
        return None
