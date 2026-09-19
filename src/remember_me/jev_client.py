"""Jev client protocol: FakeJev (deterministic, CI) + HttpJev (optional cloud).

Pin: jev-1.13.0. Failures surface as timed_out / denied / malformed — callers
MUST fail-closed (see policy.map_hydrate_action).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol, runtime_checkable

from remember_me.redact import assert_no_secrets, redact_to_dicts
from remember_me.types import (
    JEV_MODEL_PIN,
    Q_ADMIT,
    Q_HYDRATE_ACTION,
    Q_NEED_FOR_NEXT_TURN,
    Q_NETWORK_ROUTE,
    Q_NODE_KIND,
    Q_STILL_MATTERS,
    Q_TRIGGER_REFLECT,
    AdmitDecision,
    Candidate,
    HydrateAction,
    JevBatchResponse,
    JevQuestionResult,
    NodeKind,
    RedactedCandidate,
)


@runtime_checkable
class JevClient(Protocol):
    """Protocol for calibrated Jev decision calls."""

    model_pin: str

    def decide_hydrate(
        self,
        query: str,
        candidates: list[Candidate] | list[RedactedCandidate],
        *,
        optional_network: bool = False,
        optional_reflect: bool = False,
    ) -> list[JevBatchResponse]:
        """Batch hydrate decisions for redacted candidates."""
        ...

    def decide_admit(
        self,
        proposed: dict[str, Any],
    ) -> JevBatchResponse:
        """Admit + node-kind Choice for a proposed marker (redacted fields only)."""
        ...


def _stable_unit(seed: str) -> float:
    """Deterministic [0, 1) from seed string."""
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class FakeJev:
    """Deterministic offline Jev for tests and bake-offs. No network."""

    def __init__(
        self,
        *,
        model_pin: str = JEV_MODEL_PIN,
        force_timeout: bool = False,
        force_deny: bool = False,
        force_malformed: bool = False,
        confidence_override: float | None = None,
        action_override: HydrateAction | None = None,
    ) -> None:
        self.model_pin = model_pin
        self.force_timeout = force_timeout
        self.force_deny = force_deny
        self.force_malformed = force_malformed
        self.confidence_override = confidence_override
        self.action_override = action_override
        self.call_count = 0
        self.last_outbound: list[dict[str, Any]] = []

    def decide_hydrate(
        self,
        query: str,
        candidates: list[Candidate] | list[RedactedCandidate],
        *,
        optional_network: bool = False,
        optional_reflect: bool = False,
    ) -> list[JevBatchResponse]:
        self.call_count += 1
        # Always redact if raw Candidates slipped through.
        if candidates and isinstance(candidates[0], Candidate):
            outbound = redact_to_dicts(candidates)  # type: ignore[arg-type]
        else:
            outbound = [c.model_dump(mode="json") for c in candidates]  # type: ignore[union-attr]
        assert_no_secrets(outbound)
        self.last_outbound = outbound

        if self.force_timeout:
            return [
                JevBatchResponse(node_id=o["node_id"], timed_out=True, error="timeout")
                for o in outbound
            ]
        if self.force_deny:
            return [
                JevBatchResponse(node_id=o["node_id"], denied=True, error="denied")
                for o in outbound
            ]
        if self.force_malformed:
            return [
                JevBatchResponse(node_id=o["node_id"], malformed=True, error="malformed")
                for o in outbound
            ]

        results: list[JevBatchResponse] = []
        for o in outbound:
            nid = o["node_id"]
            local_score = float(o.get("local_score", 0.5))
            unit = _stable_unit(f"{query}|{nid}|{self.model_pin}")
            conf = (
                self.confidence_override
                if self.confidence_override is not None
                else min(0.99, 0.45 + 0.5 * local_score + 0.05 * unit)
            )
            if self.action_override is not None:
                action = self.action_override
            elif conf >= 0.85:
                action = HydrateAction.HYDRATE_FULL
            elif conf >= 0.55:
                action = HydrateAction.STUB_ONLY
            else:
                action = HydrateAction.SKIP

            need = 1 + int(4 * min(1.0, local_score + unit * 0.2))
            still = conf >= 0.5 and local_score > 0.15

            batch: dict[str, JevQuestionResult] = {
                Q_HYDRATE_ACTION: JevQuestionResult(
                    question_id=Q_HYDRATE_ACTION,
                    value=action.value,
                    confidence=round(conf, 4),
                ),
                Q_NEED_FOR_NEXT_TURN: JevQuestionResult(
                    question_id=Q_NEED_FOR_NEXT_TURN,
                    value=need,
                    confidence=round(min(0.99, conf + 0.02), 4),
                ),
                Q_STILL_MATTERS: JevQuestionResult(
                    question_id=Q_STILL_MATTERS,
                    value=still,
                    confidence=round(min(0.99, conf), 4),
                ),
            }
            if optional_network:
                routes = ["world", "experience", "observation", "opinion", "skip"]
                batch[Q_NETWORK_ROUTE] = JevQuestionResult(
                    question_id=Q_NETWORK_ROUTE,
                    value=routes[int(unit * len(routes)) % len(routes)],
                    confidence=round(conf * 0.9, 4),
                )
            if optional_reflect:
                batch[Q_TRIGGER_REFLECT] = JevQuestionResult(
                    question_id=Q_TRIGGER_REFLECT,
                    value=unit > 0.85,
                    confidence=round(conf * 0.8, 4),
                )
            results.append(JevBatchResponse(node_id=nid, results=batch))
        return results

    def decide_admit(self, proposed: dict[str, Any]) -> JevBatchResponse:
        self.call_count += 1
        safe = {k: v for k, v in proposed.items() if k in {"node_id", "kind", "tags", "salience"}}
        assert_no_secrets(safe)
        self.last_outbound = [safe]
        nid = str(proposed.get("node_id", "unknown"))
        if self.force_timeout:
            return JevBatchResponse(node_id=nid, timed_out=True, error="timeout")
        if self.force_deny:
            return JevBatchResponse(node_id=nid, denied=True, error="denied")
        if self.force_malformed:
            return JevBatchResponse(node_id=nid, malformed=True, error="malformed")

        unit = _stable_unit(f"admit|{nid}|{self.model_pin}")
        conf = (
            self.confidence_override
            if self.confidence_override is not None
            else 0.7 + 0.25 * unit
        )
        kind_raw = proposed.get("kind", NodeKind.FACT.value)
        try:
            kind = NodeKind(str(kind_raw))
        except ValueError:
            kind = NodeKind.FACT
        decision = AdmitDecision.ADMIT if conf >= 0.55 else AdmitDecision.REJECT
        return JevBatchResponse(
            node_id=nid,
            results={
                Q_ADMIT: JevQuestionResult(
                    question_id=Q_ADMIT, value=decision.value, confidence=round(conf, 4)
                ),
                Q_NODE_KIND: JevQuestionResult(
                    question_id=Q_NODE_KIND, value=kind.value, confidence=round(conf, 4)
                ),
            },
        )


class HttpJev:
    """Optional HTTP client for TypeSafe Jev. Requires TYPESAFE_API_KEY.

    Not used in CI. Failures set timed_out / denied / malformed for fail-closed.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.typesafe.ai/v1/jev",
        model_pin: str = JEV_MODEL_PIN,
        timeout_s: float = 5.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model_pin = model_pin
        self.timeout_s = timeout_s
        self.call_count = 0
        self.last_outbound: list[dict[str, Any]] = []

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY not set; use FakeJev for offline")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Jev-Model": self.model_pin,
        }

    def decide_hydrate(
        self,
        query: str,
        candidates: list[Candidate] | list[RedactedCandidate],
        *,
        optional_network: bool = False,
        optional_reflect: bool = False,
    ) -> list[JevBatchResponse]:
        self.call_count += 1
        if candidates and isinstance(candidates[0], Candidate):
            outbound = redact_to_dicts(candidates)  # type: ignore[arg-type]
        else:
            outbound = [c.model_dump(mode="json") for c in candidates]  # type: ignore[union-attr]
        assert_no_secrets(outbound)
        self.last_outbound = outbound

        questions = [Q_HYDRATE_ACTION, Q_NEED_FOR_NEXT_TURN, Q_STILL_MATTERS]
        if optional_network:
            questions.append(Q_NETWORK_ROUTE)
        if optional_reflect:
            questions.append(Q_TRIGGER_REFLECT)

        payload = {
            "model": self.model_pin,
            "query": query,
            "candidates": outbound,
            "questions": questions,
        }
        return self._post_batch(payload, node_ids=[o["node_id"] for o in outbound])

    def decide_admit(self, proposed: dict[str, Any]) -> JevBatchResponse:
        self.call_count += 1
        safe = {k: v for k, v in proposed.items() if k in {"node_id", "kind", "tags", "salience"}}
        assert_no_secrets(safe)
        self.last_outbound = [safe]
        payload = {
            "model": self.model_pin,
            "proposed": safe,
            "questions": [Q_ADMIT, Q_NODE_KIND],
        }
        results = self._post_batch(payload, node_ids=[str(proposed.get("node_id", "unknown"))])
        return results[0] if results else JevBatchResponse(
            node_id=str(proposed.get("node_id", "unknown")),
            error="empty_response",
            malformed=True,
        )

    def _post_batch(self, payload: dict[str, Any], node_ids: list[str]) -> list[JevBatchResponse]:
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return [
                JevBatchResponse(node_id=nid, error="httpx_missing", malformed=True)
                for nid in node_ids
            ]
        try:
            headers = self._headers()
        except RuntimeError as exc:
            return [
                JevBatchResponse(node_id=nid, denied=True, error=str(exc)) for nid in node_ids
            ]
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(self.base_url, json=payload, headers=headers)
        except Exception as exc:  # network / timeout
            return [
                JevBatchResponse(node_id=nid, timed_out=True, error=str(exc)) for nid in node_ids
            ]

        if resp.status_code in (401, 403):
            return [
                JevBatchResponse(node_id=nid, denied=True, error=f"http_{resp.status_code}")
                for nid in node_ids
            ]
        if resp.status_code >= 400:
            return [
                JevBatchResponse(node_id=nid, error=f"http_{resp.status_code}", malformed=True)
                for nid in node_ids
            ]
        try:
            data = resp.json()
        except Exception:
            return [
                JevBatchResponse(node_id=nid, malformed=True, error="invalid_json")
                for nid in node_ids
            ]

        # Expected shape: {"decisions": [{node_id, results: {qid: {value, confidence}}}]}
        decisions = data.get("decisions")
        if not isinstance(decisions, list):
            return [
                JevBatchResponse(node_id=nid, malformed=True, error="missing_decisions")
                for nid in node_ids
            ]
        by_id = {d.get("node_id"): d for d in decisions if isinstance(d, dict)}
        out: list[JevBatchResponse] = []
        for nid in node_ids:
            d = by_id.get(nid)
            if not d:
                out.append(JevBatchResponse(node_id=nid, malformed=True, error="missing_node"))
                continue
            results: dict[str, JevQuestionResult] = {}
            raw_results = d.get("results") or {}
            if not isinstance(raw_results, dict):
                out.append(JevBatchResponse(node_id=nid, malformed=True, error="bad_results"))
                continue
            for qid, rr in raw_results.items():
                if not isinstance(rr, dict) or "value" not in rr or "confidence" not in rr:
                    out.append(JevBatchResponse(node_id=nid, malformed=True, error=f"bad_{qid}"))
                    break
                results[qid] = JevQuestionResult(
                    question_id=qid,
                    value=rr["value"],
                    confidence=float(rr["confidence"]),
                    raw=rr,
                )
            else:
                out.append(JevBatchResponse(node_id=nid, results=results))
                continue
        return out
