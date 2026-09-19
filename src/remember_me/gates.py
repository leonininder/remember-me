"""Memory hydrate gate and retain/admit gate — Jev on the critical path."""

from __future__ import annotations

from typing import Any

from remember_me.jev_client import FakeJev, JevClient
from remember_me.policy import T_ACCEPT, T_ESCALATE, map_hydrate_action
from remember_me.redact import redact_state
from remember_me.types import (
    Q_ADMIT,
    Q_NODE_KIND,
    AdmitDecision,
    AdmitResult,
    Candidate,
    GateDecision,
    NodeKind,
    RedactedCandidate,
)


class MemoryGate:
    """Post-recall hydrate gate: Choice hydrate_action + Score need + Noul still_matters.

    Always redacts before calling Jev. Fail-closed via policy.
    """

    def __init__(
        self,
        client: JevClient | None = None,
        *,
        t_accept: float = T_ACCEPT,
        t_escalate: float = T_ESCALATE,
        optional_network: bool = False,
        optional_reflect: bool = False,
        fail_closed_top_k: int = 0,
    ) -> None:
        self.client = client or FakeJev()
        self.t_accept = t_accept
        self.t_escalate = t_escalate
        self.optional_network = optional_network
        self.optional_reflect = optional_reflect
        self.fail_closed_top_k = fail_closed_top_k
        self.last_redacted: list[RedactedCandidate] = []
        self.jev_call_count = 0

    def evaluate(self, query: str, candidates: list[Candidate]) -> list[GateDecision]:
        """Redact → Jev batch → policy map. Proves Jev is on the hydrate path."""
        redacted = redact_state(candidates)
        self.last_redacted = redacted
        responses = self.client.decide_hydrate(
            query,
            redacted,
            optional_network=self.optional_network,
            optional_reflect=self.optional_reflect,
        )
        self.jev_call_count += 1
        by_id = {r.node_id: r for r in responses}
        # Rank by local_score for optional fail-closed stub fallback.
        ranked = sorted(candidates, key=lambda c: c.local_score, reverse=True)
        rank_of = {c.node_id: i for i, c in enumerate(ranked)}

        decisions: list[GateDecision] = []
        for c in candidates:
            resp = by_id.get(c.node_id)
            if resp is None:
                from remember_me.types import JevBatchResponse

                resp = JevBatchResponse(
                    node_id=c.node_id, malformed=True, error="missing_response"
                )
            decisions.append(
                map_hydrate_action(
                    resp,
                    c,
                    t_accept=self.t_accept,
                    t_escalate=self.t_escalate,
                    fail_closed_top_k_fallback=self.fail_closed_top_k > 0,
                    fail_closed_rank=rank_of.get(c.node_id, 999),
                    fail_closed_k=self.fail_closed_top_k,
                )
            )
        return decisions


class RetainAdmitGate:
    """Retain/admit gate: Choice admit + closed node-kind taxonomy."""

    def __init__(self, client: JevClient | None = None) -> None:
        self.client = client or FakeJev()
        self.jev_call_count = 0
        self.last_outbound: dict[str, Any] = {}

    def evaluate(
        self,
        *,
        node_id: str,
        kind: NodeKind | str = NodeKind.FACT,
        tags: list[str] | None = None,
        salience: float = 0.5,
    ) -> AdmitResult:
        kind_enum = kind if isinstance(kind, NodeKind) else NodeKind(str(kind))
        proposed = {
            "node_id": node_id,
            "kind": kind_enum.value,
            "tags": list(tags or []),
            "salience": salience,
        }
        self.last_outbound = proposed
        resp = self.client.decide_admit(proposed)
        self.jev_call_count += 1

        if resp.failed:
            return AdmitResult(
                node_id=node_id,
                decision=AdmitDecision.DEFER,
                kind=kind_enum,
                confidence=0.0,
                fail_closed=True,
                reason=f"fail_closed:{resp.error or 'error'}",
            )

        admit_res = resp.results.get(Q_ADMIT)
        kind_res = resp.results.get(Q_NODE_KIND)
        conf = float(admit_res.confidence) if admit_res else 0.0
        decision = AdmitDecision.DEFER
        if admit_res and admit_res.value is not None:
            try:
                decision = AdmitDecision(str(admit_res.value).lower())
            except ValueError:
                decision = AdmitDecision.DEFER
        out_kind = kind_enum
        if kind_res and kind_res.value is not None:
            try:
                out_kind = NodeKind(str(kind_res.value).lower())
            except ValueError:
                out_kind = kind_enum
        return AdmitResult(
            node_id=node_id,
            decision=decision,
            kind=out_kind,
            confidence=conf,
            fail_closed=False,
            reason="ok",
        )
