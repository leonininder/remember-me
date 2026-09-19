"""End-to-end pipeline: observe → retrieve → redact → jev → hydrate.

Orphan hydrations (nodes not in candidate set) are forbidden.
"""

from __future__ import annotations

from remember_me.gates import MemoryGate, RetainAdmitGate
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev, JevClient
from remember_me.redact import redact_state
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import (
    AdmitDecision,
    Horizon,
    HydrateAction,
    HydratedNode,
    Marker,
    NodeKind,
    PipelineResult,
)


class MemoryPipeline:
    """Topology memory pipeline with Jev on the hydrate critical path."""

    def __init__(
        self,
        graph: TopologyGraph | None = None,
        client: JevClient | None = None,
        *,
        top_k: int = 8,
        optional_network: bool = False,
        optional_reflect: bool = False,
        fail_closed_top_k: int = 0,
    ) -> None:
        self.graph = graph or TopologyGraph()
        self.client = client or FakeJev()
        self.retriever = LocalCandidateRetriever(self.graph, top_k=top_k)
        self.gate = MemoryGate(
            self.client,
            optional_network=optional_network,
            optional_reflect=optional_reflect,
            fail_closed_top_k=fail_closed_top_k,
        )
        self.admit_gate = RetainAdmitGate(self.client)

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
    ) -> Marker:
        """Write a marker; optionally run retain/admit gate first."""
        if require_admit:
            admit = self.admit_gate.evaluate(
                node_id=node_id, kind=kind, tags=tags, salience=salience
            )
            if admit.decision != AdmitDecision.ADMIT:
                raise PermissionError(f"admit rejected: {admit.decision} ({admit.reason})")
            kind = admit.kind
        return self.graph.observe(
            node_id=node_id,
            content=content,
            kind=kind,
            horizon=horizon,
            tags=tags,
            salience=salience,
        )

    def run(self, query: str, *, top_k: int | None = None) -> PipelineResult:
        """retrieve → redact → jev → hydrate. Jev is always called when candidates exist."""
        candidates = self.retriever.retrieve(query, top_k=top_k)
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
            )

        decisions = self.gate.evaluate(query, candidates)
        # MemoryGate always invokes Jev when candidates are non-empty.
        jev_called = self.gate.jev_call_count > 0
        allowed_ids = {c.node_id for c in candidates}
        by_cand = {c.node_id: c for c in candidates}
        hydrated: list[HydratedNode] = []
        fail_closed = 0
        for d in decisions:
            if d.fail_closed:
                fail_closed += 1
            if d.node_id not in allowed_ids:
                # Orphan hydration forbidden.
                continue
            if d.action == HydrateAction.SKIP:
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

        return PipelineResult(
            query=query,
            candidates=candidates,
            redacted=redacted,
            decisions=decisions,
            hydrated=hydrated,
            jev_called=jev_called,
            fail_closed_count=fail_closed,
        )
