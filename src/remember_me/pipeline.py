"""End-to-end pipeline: observe → retrieve → redact → jev → hydrate (+ optional egress).

Orphan hydrations forbidden. Jev never re-ranks candidates.
Local candidates first. Jev never ranks. Jev only admits.
"""

from __future__ import annotations

from typing import Any

from remember_me.fanout import FANOUT_DEFAULTS, FanOutDefaults
from remember_me.gates import EmitEgressGate, MemoryGate, RetainAdmitGate, WritebackGate
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev, JevClient
from remember_me.policy import assert_no_rerank
from remember_me.redact import redact_state
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import (
    AdmitDecision,
    DualGateResult,
    EgressResult,
    EscalationRecord,
    Horizon,
    HydrateAction,
    HydratedNode,
    Marker,
    NodeKind,
    PipelineResult,
    WritebackAction,
)


class MemoryPipeline:
    """Topology memory pipeline with Jev on the hydrate critical path."""

    def __init__(
        self,
        graph: TopologyGraph | None = None,
        client: JevClient | None = None,
        *,
        top_k: int = 8,
        optional_network: bool | None = None,
        optional_reflect: bool | None = None,
        fail_closed_top_k: int = 0,
        fanout: FanOutDefaults | None = None,
        emit_gate: EmitEgressGate | None = None,
        writeback_gate: WritebackGate | None = None,
    ) -> None:
        self.fanout = fanout or FANOUT_DEFAULTS
        self.graph = graph or TopologyGraph()
        self.client = client or FakeJev()
        self.retriever = LocalCandidateRetriever(self.graph, top_k=top_k)
        self.gate = MemoryGate(
            self.client,
            optional_network=optional_network,
            optional_reflect=optional_reflect,
            fail_closed_top_k=fail_closed_top_k,
            fanout=self.fanout,
        )
        self.admit_gate = RetainAdmitGate(self.client)
        self.emit_gate = emit_gate
        self.writeback_gate = writeback_gate

    def observe(
        self,
        *,
        node_id: str,
        content: str,
        kind: NodeKind = NodeKind.FACT,
        horizon: Horizon = Horizon.WORKING,
        tags: list[str] | None = None,
        salience: float = 0.5,
        require_admit: bool = False,
        require_writeback: bool = False,
    ) -> Marker:
        """Write a marker; optionally run retain/admit and/or writeback gates first."""
        if require_admit:
            admit = self.admit_gate.evaluate(
                node_id=node_id, kind=kind, tags=tags, salience=salience
            )
            if admit.decision != AdmitDecision.ADMIT:
                raise PermissionError(f"admit rejected: {admit.decision} ({admit.reason})")
            kind = admit.kind
        if require_writeback:
            wb_gate = self.writeback_gate or WritebackGate(self.client)
            wb = wb_gate.evaluate(
                "graph_durable",
                {
                    "node_id": node_id,
                    "kind": kind.value if isinstance(kind, NodeKind) else str(kind),
                    "tags": list(tags or []),
                    "salience": salience,
                    "horizon": horizon.value,
                },
            )
            if wb.action not in (
                WritebackAction.ALLOW_WRITEBACK,
                WritebackAction.STAGE_ONLY,
            ):
                raise PermissionError(
                    f"writeback rejected: {wb.action} ({wb.reason})"
                )
        return self.graph.observe(
            node_id=node_id,
            content=content,
            kind=kind,
            horizon=horizon,
            tags=tags,
            salience=salience,
        )

    def run(self, query: str, *, top_k: int | None = None) -> PipelineResult:
        """retrieve → redact → jev → hydrate. Candidate order / local_score immutable."""
        candidates = self.retriever.retrieve(query, top_k=top_k)
        order_snapshot = list(candidates)
        redacted = redact_state(candidates)
        if not candidates:
            return PipelineResult(
                query=query,
                candidates=[],
                redacted=[],
                decisions=[],
                hydrated=[],
                jev_called=False,
                fail_closed_count=0,
                escalate_human_count=0,
                escalations=[],
            )

        decisions = self.gate.evaluate(query, candidates)
        # No-rerank invariant: gate must not permute candidates or mutate local_score.
        assert_no_rerank(order_snapshot, candidates)
        jev_called = self.gate.jev_call_count > 0
        allowed_ids = {c.node_id for c in candidates}
        by_cand = {c.node_id: c for c in candidates}
        hydrated: list[HydratedNode] = []
        fail_closed = 0
        escalations: list[EscalationRecord] = []
        escalate_count = 0
        for d in decisions:
            if d.fail_closed:
                fail_closed += 1
            if d.escalation is not None:
                escalations.append(d.escalation)
            if d.action == HydrateAction.ESCALATE_HUMAN:
                escalate_count += 1
            if d.node_id not in allowed_ids:
                continue
            if d.action in (HydrateAction.SKIP, HydrateAction.ESCALATE_HUMAN):
                # escalate_human: surface on decisions/escalations; do not auto-hydrate full.
                continue
            marker = self.graph.get(d.node_id)
            c = by_cand[d.node_id]
            body = (marker.content if marker else None) or c.content or ""
            if d.action == HydrateAction.STUB_ONLY:
                stub_text = f"[stub:{d.node_id}|{c.kind.value}|score={c.local_score:.3f}]"
                hydrated.append(
                    HydratedNode(
                        node_id=d.node_id,
                        kind=c.kind,
                        content=stub_text,
                        content_ref=c.content_ref,
                        action=d.action,
                        confidence=d.confidence,
                        stub=True,
                    )
                )
            elif d.action in (HydrateAction.HYDRATE_FULL, HydrateAction.PROMOTE_DURABLE):
                hydrated.append(
                    HydratedNode(
                        node_id=d.node_id,
                        kind=c.kind,
                        content=body,
                        content_ref=c.content_ref,
                        action=d.action,
                        confidence=d.confidence,
                        stub=False,
                    )
                )
                if d.action == HydrateAction.PROMOTE_DURABLE and marker:
                    self.graph.promote(d.node_id, Horizon.DURABLE)

        # Survivors keep candidate relative order (no Jev-driven reorder).
        return PipelineResult(
            query=query,
            candidates=candidates,
            redacted=redacted,
            decisions=decisions,
            hydrated=hydrated,
            jev_called=jev_called,
            fail_closed_count=fail_closed,
            escalate_human_count=escalate_count,
            escalations=escalations,
        )

    def run_egress(
        self,
        proposed_text: str,
        context: dict[str, Any] | None = None,
        *,
        sink: str = "agent_channel",
    ) -> EgressResult:
        """Egress gate for a redacted proposed summary (demo / dual-gate)."""
        gate = self.emit_gate or EmitEgressGate(self.client)
        decision = gate.decide_emit(proposed_text, context, sink=sink)
        summary = (proposed_text or "").strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return EgressResult(
            proposed_text_redacted=summary,
            context=dict(context or {}),
            decision=decision,
            jev_called=gate.jev_call_count > 0,
        )

    def run_dual(
        self,
        query: str,
        *,
        top_k: int | None = None,
        egress_summary: str | None = None,
        egress_sink: str = "agent_channel",
    ) -> DualGateResult:
        """Ingress hydrate then optional egress emit (demo helper)."""
        ingress = self.run(query, top_k=top_k)
        egress = None
        if egress_summary is not None:
            egress = self.run_egress(
                egress_summary,
                {
                    "query_hash_hint": query[:32],
                    "hydrated_ids": [h.node_id for h in ingress.hydrated],
                },
                sink=egress_sink,
            )
        return DualGateResult(ingress=ingress, egress=egress)


class DualGatePipeline(MemoryPipeline):
    """MemoryPipeline with emit + writeback gates enabled by default."""

    def __init__(
        self,
        graph: TopologyGraph | None = None,
        client: JevClient | None = None,
        **kwargs: Any,
    ) -> None:
        client = client or FakeJev()
        kwargs.setdefault("emit_gate", EmitEgressGate(client))
        kwargs.setdefault("writeback_gate", WritebackGate(client))
        super().__init__(graph, client, **kwargs)
