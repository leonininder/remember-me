"""Memory hydrate, emit egress, writeback, and retain/admit gates — Jev on the path."""

from __future__ import annotations

from typing import Any

from remember_me.fanout import FANOUT_DEFAULTS, FanOutDefaults
from remember_me.jev_client import FakeJev, JevClient
from remember_me.policy import (
    T_ACCEPT,
    T_ESCALATE,
    map_emit_action,
    map_hydrate_action,
    map_writeback_action,
)
from remember_me.redact import assert_no_secrets, redact_state
from remember_me.types import (
    Q_ADMIT,
    Q_NODE_KIND,
    AdmitDecision,
    AdmitResult,
    Candidate,
    EmitDecision,
    GateDecision,
    NodeKind,
    RedactedCandidate,
    WritebackDecision,
)


class MemoryGate:
    """Post-recall hydrate gate. Mid-band / conflicts → escalate_human + EscalationRecord."""

    def __init__(
        self,
        client: JevClient | None = None,
        *,
        t_accept: float = T_ACCEPT,
        t_escalate: float = T_ESCALATE,
        optional_network: bool | None = None,
        optional_reflect: bool | None = None,
        fail_closed_top_k: int = 0,
        fanout: FanOutDefaults | None = None,
    ) -> None:
        self.fanout = fanout or FANOUT_DEFAULTS
        self.client = client or FakeJev()
        self.t_accept = t_accept
        self.t_escalate = t_escalate
        self.optional_network = (
            self.fanout.optional_network if optional_network is None else optional_network
        )
        self.optional_reflect = (
            self.fanout.optional_reflect if optional_reflect is None else optional_reflect
        )
        self.fail_closed_top_k = fail_closed_top_k
        self.last_redacted: list[RedactedCandidate] = []
        self.jev_call_count = 0

    def evaluate(self, query: str, candidates: list[Candidate]) -> list[GateDecision]:
        """Redact → one Jev batch (fan-out) → policy. Order preserved (no rerank)."""
        redacted = redact_state(candidates)
        self.last_redacted = redacted
        # Pass raw Candidates so HttpJev can derive salience_bucket; client redacts.
        responses = self.client.decide_hydrate(
            query,
            candidates,
            optional_network=self.optional_network,
            optional_reflect=self.optional_reflect,
        )
        self.jev_call_count += 1
        by_id = {r.node_id: r for r in responses}
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


class EmitEgressGate:
    """Egress gate: may this redacted payload leave the local boundary?"""

    def __init__(
        self,
        client: JevClient | None = None,
        *,
        t_accept: float = T_ACCEPT,
        t_escalate: float = T_ESCALATE,
    ) -> None:
        self.client = client or FakeJev()
        self.t_accept = t_accept
        self.t_escalate = t_escalate
        self.jev_call_count = 0
        self.last_outbound: dict[str, Any] = {}

    def evaluate(
        self,
        sink: str,
        payload_meta: dict[str, Any],
    ) -> EmitDecision:
        """Fail-closed → deny_emit (never silent allow).

        Positive allowlist only: free-text ``proposed_summary`` is never egressed —
        replaced with ``proposed_chars`` + ``proposed_summary_sha256``.
        """
        from remember_me.redact import (
            EMIT_META_ALLOWLIST,
            allowlist_snapshot,
            summary_fingerprint,
        )

        raw = dict(payload_meta or {})
        # Fingerprint any free-text summary before allowlisting (never send body text).
        summary = str(raw.pop("proposed_summary", "") or raw.pop("summary", "") or "")
        safe = allowlist_snapshot(raw, allowed=EMIT_META_ALLOWLIST)
        if summary:
            safe.update(summary_fingerprint(summary))
        elif "proposed_chars" in raw and "proposed_chars" not in safe:
            # already allowlisted if key present; nothing extra
            pass
        assert_no_secrets(safe)
        self.last_outbound = {"sink": sink, **safe}
        resp = self.client.decide_emit(sink=sink, payload_meta=safe)
        self.jev_call_count += 1
        chars = int(safe.get("proposed_chars") or 0)
        return map_emit_action(
            resp,
            sink=sink,
            proposed_chars=chars,
            t_accept=self.t_accept,
            t_escalate=self.t_escalate,
            redacted_snapshot=safe,
        )

    def decide_emit(
        self,
        proposed_text: str,
        context: dict[str, Any] | None = None,
        *,
        sink: str = "agent_channel",
    ) -> EmitDecision:
        """Convenience: fingerprint summary + allowlisted context → EmitDecision."""
        from remember_me.redact import summary_fingerprint

        summary = (proposed_text or "").strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        ctx = dict(context or {})
        # Never put free text into payload_meta — hash + length only.
        payload = {**summary_fingerprint(summary), **ctx}
        return self.evaluate(sink, payload)


# Alias for dual-gate docs / original prompt naming.
EmitGate = EmitEgressGate


class WritebackGate:
    """Durable writeback gate: may this marker hit LTM / wiki / bank?"""

    def __init__(
        self,
        client: JevClient | None = None,
        *,
        t_accept: float = T_ACCEPT,
        t_escalate: float = T_ESCALATE,
    ) -> None:
        self.client = client or FakeJev()
        self.t_accept = t_accept
        self.t_escalate = t_escalate
        self.jev_call_count = 0
        self.last_outbound: dict[str, Any] = {}

    def evaluate(
        self,
        target: str,
        proposed: dict[str, Any],
    ) -> WritebackDecision:
        safe = {
            k: v
            for k, v in proposed.items()
            if k
            in {
                "node_id",
                "kind",
                "tags",
                "salience",
                "horizon",
                "tokens_est",
                "degree",
            }
        }
        assert_no_secrets(safe)
        self.last_outbound = {"target": target, **safe}
        resp = self.client.decide_writeback(target=target, proposed=safe)
        self.jev_call_count += 1
        return map_writeback_action(
            resp,
            target=target,
            node_id=str(safe.get("node_id") or ""),
            t_accept=self.t_accept,
            t_escalate=self.t_escalate,
            redacted_snapshot=safe,
        )


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
