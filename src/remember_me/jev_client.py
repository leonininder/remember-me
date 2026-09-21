"""Jev client protocol: FakeJev (deterministic, CI) + HttpJev (System One).

Pin: jev-1.13.0 via ``JEV_MODEL_PIN``. HttpJev posts to
``POST /v1/systemone`` with ``state`` + typed ``questions`` and maps
``answers`` (not a fictional ``/v1/jev`` or ``{decisions}`` shape).

Failures surface as timed_out / denied / malformed — callers MUST
fail-closed (see policy.map_hydrate_action).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol, runtime_checkable

from remember_me.redact import assert_no_secrets, redact_to_dicts
from remember_me.types import (
    JEV_MODEL_PIN,
    Q_ADMIT,
    Q_EMIT_ACTION,
    Q_HYDRATE_ACTION,
    Q_LEAK_RISK,
    Q_NEED_FOR_NEXT_TURN,
    Q_NETWORK_ROUTE,
    Q_NODE_KIND,
    Q_ON_TOPIC,
    Q_STILL_MATTERS,
    Q_TRIGGER_REFLECT,
    Q_WRITEBACK_ACTION,
    Q_WRITEBACK_NEED,
    Q_WRITEBACK_STILL_SAFE,
    AdmitDecision,
    Candidate,
    EmitAction,
    HydrateAction,
    JevBatchResponse,
    JevQuestionResult,
    NetworkRoute,
    NodeKind,
    RedactedCandidate,
    WritebackAction,
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

    def decide_emit(
        self,
        *,
        sink: str,
        payload_meta: dict[str, Any],
    ) -> JevBatchResponse:
        """Egress emit Choice for a redacted payload leaving the local boundary."""
        ...

    def decide_writeback(
        self,
        *,
        target: str,
        proposed: dict[str, Any],
    ) -> JevBatchResponse:
        """Writeback Choice for durable LTM / wiki / bank (redacted fields only)."""
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
                action = HydrateAction.ESCALATE_HUMAN
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


    def decide_emit(
        self,
        *,
        sink: str,
        payload_meta: dict[str, Any],
    ) -> JevBatchResponse:
        """One decide call: emit_action (+ leak_risk / on_topic). Fail-closed on force_*."""
        self.call_count += 1
        from remember_me.redact import EMIT_META_ALLOWLIST, allowlist_snapshot

        safe = allowlist_snapshot(payload_meta, allowed=EMIT_META_ALLOWLIST)
        outbound = {"sink": sink, **safe}
        assert_no_secrets(outbound)
        self.last_outbound = [outbound]
        nid = str(safe.get("node_id") or safe.get("egress_id") or "egress")
        if self.force_timeout:
            return JevBatchResponse(node_id=nid, timed_out=True, error="timeout")
        if self.force_deny:
            return JevBatchResponse(node_id=nid, denied=True, error="denied")
        if self.force_malformed:
            return JevBatchResponse(node_id=nid, malformed=True, error="malformed")

        unit = _stable_unit(f"emit|{sink}|{nid}|{self.model_pin}")
        conf = (
            self.confidence_override
            if self.confidence_override is not None
            else 0.6 + 0.35 * unit
        )
        if conf >= 0.85:
            action = EmitAction.ALLOW_EMIT
        elif conf >= 0.55:
            action = EmitAction.ESCALATE_HUMAN
        else:
            action = EmitAction.DENY_EMIT
        leak = unit < 0.15
        on_topic = unit > 0.25
        return JevBatchResponse(
            node_id=nid,
            results={
                Q_EMIT_ACTION: JevQuestionResult(
                    question_id=Q_EMIT_ACTION,
                    value=action.value,
                    confidence=round(conf, 4),
                ),
                Q_LEAK_RISK: JevQuestionResult(
                    question_id=Q_LEAK_RISK,
                    value=leak,
                    confidence=round(min(0.99, conf), 4),
                ),
                Q_ON_TOPIC: JevQuestionResult(
                    question_id=Q_ON_TOPIC,
                    value=on_topic,
                    confidence=round(min(0.99, conf), 4),
                ),
            },
        )

    def decide_writeback(
        self,
        *,
        target: str,
        proposed: dict[str, Any],
    ) -> JevBatchResponse:
        """One decide call: writeback_action (+ optional need / still_safe)."""
        self.call_count += 1
        safe = {
            k: v
            for k, v in proposed.items()
            if k in {"node_id", "kind", "tags", "salience", "horizon", "tokens_est", "degree"}
        }
        outbound = {"target": target, **safe}
        assert_no_secrets(outbound)
        self.last_outbound = [outbound]
        nid = str(safe.get("node_id") or "unknown")
        if self.force_timeout:
            return JevBatchResponse(node_id=nid, timed_out=True, error="timeout")
        if self.force_deny:
            return JevBatchResponse(node_id=nid, denied=True, error="denied")
        if self.force_malformed:
            return JevBatchResponse(node_id=nid, malformed=True, error="malformed")

        unit = _stable_unit(f"writeback|{target}|{nid}|{self.model_pin}")
        conf = (
            self.confidence_override
            if self.confidence_override is not None
            else 0.55 + 0.4 * unit
        )
        if conf >= 0.85:
            action = WritebackAction.ALLOW_WRITEBACK
        elif conf >= 0.55:
            action = WritebackAction.ESCALATE_HUMAN
        else:
            action = WritebackAction.DENY_WRITEBACK
        still_safe = conf >= 0.5
        need = 1 + int(4 * min(1.0, conf))
        return JevBatchResponse(
            node_id=nid,
            results={
                Q_WRITEBACK_ACTION: JevQuestionResult(
                    question_id=Q_WRITEBACK_ACTION,
                    value=action.value,
                    confidence=round(conf, 4),
                ),
                Q_WRITEBACK_NEED: JevQuestionResult(
                    question_id=Q_WRITEBACK_NEED,
                    value=need,
                    confidence=round(min(0.99, conf + 0.02), 4),
                ),
                Q_WRITEBACK_STILL_SAFE: JevQuestionResult(
                    question_id=Q_WRITEBACK_STILL_SAFE,
                    value=still_safe,
                    confidence=round(min(0.99, conf), 4),
                ),
            },
        )


class HttpJev:
    """HTTP client for TypeSafe System One (`POST /v1/systemone`).

    Requires ``TYPESAFE_API_KEY``. Not used in CI. Failures set
    ``timed_out`` / ``denied`` / ``malformed`` for fail-closed policy.

    Egress (David P1): by default does **not** send the raw ``query`` string.
    Always includes ``query_hash`` (sha256 hex of utf-8 query) in ``state``.
    Set ``include_raw_query=True`` to also send ``query_preview`` (full query).

    Hydrate batching (default ``batch_candidates=True``): one ``POST`` with
    ``state.candidates`` + questions keyed ``{node_id}__{question_id}``.
    Set ``batch_candidates=False`` to fall back to per-node calls for debugging.

    Answer mapping → ``JevQuestionResult``:
    - Choice → value=choice str, confidence=confidence
    - Score → value=score number, confidence=confidence
    - Noul → value=bool(noul >= 0.5), confidence=noul (yes-probability)
    """

    DEFAULT_BASE_URL = "https://api.typesafe.ai/v1/systemone"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model_pin: str = JEV_MODEL_PIN,
        timeout_s: float = 5.0,
        include_raw_query: bool = False,
        batch_candidates: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model_pin = model_pin
        self.timeout_s = timeout_s
        self.include_raw_query = include_raw_query
        self.batch_candidates = batch_candidates
        self.call_count = 0
        self.last_outbound: list[dict[str, Any]] = []
        self.last_usage: dict[str, Any] | None = None
        self.last_response_model: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY not set; use FakeJev for offline")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _query_hash(query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def _build_state(self, query: str, extra: dict[str, Any]) -> dict[str, Any]:
        state: dict[str, Any] = {"query_hash": self._query_hash(query), **extra}
        if self.include_raw_query:
            state["query_preview"] = query
        return state

    def decide_hydrate(
        self,
        query: str,
        candidates: list[Candidate] | list[RedactedCandidate],
        *,
        optional_network: bool = False,
        optional_reflect: bool = False,
        batch_candidates: bool | None = None,
    ) -> list[JevBatchResponse]:
        self.call_count += 1
        if candidates and isinstance(candidates[0], Candidate):
            outbound = redact_to_dicts(candidates)  # type: ignore[arg-type]
        else:
            outbound = [c.model_dump(mode="json") for c in candidates]  # type: ignore[union-attr]
        assert_no_secrets(outbound)
        self.last_outbound = outbound

        if not outbound:
            return []

        use_batch = self.batch_candidates if batch_candidates is None else batch_candidates
        if use_batch:
            return self._decide_hydrate_batched(
                query,
                outbound,
                optional_network=optional_network,
                optional_reflect=optional_reflect,
            )

        # Debug fallback: one System One POST per candidate (legacy shape).
        questions = _hydrate_questions(
            optional_network=optional_network, optional_reflect=optional_reflect
        )
        results: list[JevBatchResponse] = []
        for cand in outbound:
            nid = str(cand["node_id"])
            state = self._build_state(query, {"candidate": cand})
            payload = {
                "model": self.model_pin,
                "state": state,
                "questions": questions,
            }
            results.append(self._post_system_one(payload, node_id=nid))
        return results

    def _decide_hydrate_batched(
        self,
        query: str,
        outbound: list[dict[str, Any]],
        *,
        optional_network: bool,
        optional_reflect: bool,
    ) -> list[JevBatchResponse]:
        """ONE ``POST /v1/systemone`` for N redacted candidates.

        Questions are keyed ``{node_id}__{question_id}``. Fail-closed: whole HTTP
        failure → every node gets the same timed_out/denied/malformed; a missing
        per-node answer slice → that node malformed, others OK.
        """
        node_ids = [str(c["node_id"]) for c in outbound]
        questions = _hydrate_questions_batched(
            node_ids,
            optional_network=optional_network,
            optional_reflect=optional_reflect,
        )
        state = self._build_state(query, {"candidates": outbound})
        payload = {
            "model": self.model_pin,
            "state": state,
            "questions": questions,
        }
        return self._post_system_one_batch(payload, node_ids=node_ids)

    def decide_admit(self, proposed: dict[str, Any]) -> JevBatchResponse:
        self.call_count += 1
        safe = {k: v for k, v in proposed.items() if k in {"node_id", "kind", "tags", "salience"}}
        assert_no_secrets(safe)
        self.last_outbound = [safe]
        nid = str(proposed.get("node_id", "unknown"))
        # state = proposed safe fields only (no user query / no raw content).
        payload = {
            "model": self.model_pin,
            "state": safe,
            "questions": _admit_questions(),
        }
        return self._post_system_one(payload, node_id=nid)

    def _post_system_one(self, payload: dict[str, Any], *, node_id: str) -> JevBatchResponse:
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return JevBatchResponse(node_id=node_id, error="httpx_missing", malformed=True)
        try:
            headers = self._headers()
        except RuntimeError as exc:
            return JevBatchResponse(node_id=node_id, denied=True, error=str(exc))
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(self.base_url, json=payload, headers=headers)
        except Exception as exc:  # network / timeout
            return JevBatchResponse(node_id=node_id, timed_out=True, error=str(exc))

        if resp.status_code in (401, 403):
            return JevBatchResponse(node_id=node_id, denied=True, error=f"http_{resp.status_code}")
        if resp.status_code == 429:
            retry_after = ""
            try:
                h = resp.headers
                retry_after = str(h.get("Retry-After") or h.get("retry-after") or "")
            except Exception:
                retry_after = ""
            err = "http_429"
            if retry_after:
                err = f"http_429:retry_after={retry_after}"
            # Rate-limit → fail-closed (treat as timed_out so policy never allows).
            return JevBatchResponse(node_id=node_id, timed_out=True, error=err)
        if resp.status_code >= 400:
            return JevBatchResponse(
                node_id=node_id, error=f"http_{resp.status_code}", malformed=True
            )
        try:
            data = resp.json()
        except Exception:
            return JevBatchResponse(node_id=node_id, malformed=True, error="invalid_json")

        if not isinstance(data, dict):
            return JevBatchResponse(node_id=node_id, malformed=True, error="non_object_body")

        # Bake-off telemetry (last successful HTTP parse path).
        usage = data.get("usage")
        if isinstance(usage, dict):
            self.last_usage = usage
        model = data.get("model")
        if isinstance(model, str):
            self.last_response_model = model

        answers = data.get("answers")
        if not isinstance(answers, dict):
            return JevBatchResponse(node_id=node_id, malformed=True, error="missing_answers")

        mapped = _map_system_one_answers(answers)
        if mapped is None:
            return JevBatchResponse(node_id=node_id, malformed=True, error="bad_answers")
        return JevBatchResponse(node_id=node_id, results=mapped)

    def _post_system_one_batch(
        self, payload: dict[str, Any], *, node_ids: list[str]
    ) -> list[JevBatchResponse]:
        """POST once; fan out answers to per-node ``JevBatchResponse``."""

        def _all(failed: JevBatchResponse) -> list[JevBatchResponse]:
            return [
                JevBatchResponse(
                    node_id=nid,
                    error=failed.error,
                    denied=failed.denied,
                    malformed=failed.malformed,
                    timed_out=failed.timed_out,
                )
                for nid in node_ids
            ]

        try:
            import httpx
        except ImportError:  # pragma: no cover
            return _all(
                JevBatchResponse(node_id="*", error="httpx_missing", malformed=True)
            )
        try:
            headers = self._headers()
        except RuntimeError as exc:
            return _all(JevBatchResponse(node_id="*", denied=True, error=str(exc)))
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(self.base_url, json=payload, headers=headers)
        except Exception as exc:  # network / timeout
            return _all(JevBatchResponse(node_id="*", timed_out=True, error=str(exc)))

        if resp.status_code in (401, 403):
            return _all(
                JevBatchResponse(node_id="*", denied=True, error=f"http_{resp.status_code}")
            )
        if resp.status_code == 429:
            retry_after = ""
            try:
                h = resp.headers
                retry_after = str(h.get("Retry-After") or h.get("retry-after") or "")
            except Exception:
                retry_after = ""
            err = "http_429"
            if retry_after:
                err = f"http_429:retry_after={retry_after}"
            return _all(JevBatchResponse(node_id="*", timed_out=True, error=err))
        if resp.status_code >= 400:
            return _all(
                JevBatchResponse(
                    node_id="*", error=f"http_{resp.status_code}", malformed=True
                )
            )
        try:
            data = resp.json()
        except Exception:
            return _all(JevBatchResponse(node_id="*", malformed=True, error="invalid_json"))

        if not isinstance(data, dict):
            return _all(
                JevBatchResponse(node_id="*", malformed=True, error="non_object_body")
            )

        usage = data.get("usage")
        if isinstance(usage, dict):
            self.last_usage = usage
        model = data.get("model")
        if isinstance(model, str):
            self.last_response_model = model

        answers = data.get("answers")
        if not isinstance(answers, dict):
            return _all(
                JevBatchResponse(node_id="*", malformed=True, error="missing_answers")
            )

        return _split_batched_answers(answers, node_ids=node_ids)


    def decide_emit(
        self,
        *,
        sink: str,
        payload_meta: dict[str, Any],
    ) -> JevBatchResponse:
        """Egress: one System One POST with emit_action + leak_risk + on_topic."""
        self.call_count += 1
        from remember_me.redact import EMIT_META_ALLOWLIST, allowlist_snapshot

        safe = allowlist_snapshot(payload_meta, allowed=EMIT_META_ALLOWLIST)
        state = {"sink": sink, **safe}
        assert_no_secrets(state)
        self.last_outbound = [state]
        nid = str(safe.get("node_id") or safe.get("egress_id") or "egress")
        payload = {
            "model": self.model_pin,
            "state": state,
            "questions": _emit_questions(),
        }
        return self._post_system_one(payload, node_id=nid)

    def decide_writeback(
        self,
        *,
        target: str,
        proposed: dict[str, Any],
    ) -> JevBatchResponse:
        """Writeback: one System One POST with writeback_action (+ need / still_safe)."""
        self.call_count += 1
        safe = {
            k: v
            for k, v in proposed.items()
            if k in {"node_id", "kind", "tags", "salience", "horizon", "tokens_est", "degree"}
        }
        state = {"target": target, **safe}
        assert_no_secrets(state)
        self.last_outbound = [state]
        nid = str(safe.get("node_id") or "unknown")
        payload = {
            "model": self.model_pin,
            "state": state,
            "questions": _writeback_questions(),
        }
        return self._post_system_one(payload, node_id=nid)



def _hydrate_questions(
    *, optional_network: bool, optional_reflect: bool
) -> dict[str, dict[str, Any]]:
    actions = [a.value for a in HydrateAction]
    questions: dict[str, dict[str, Any]] = {
        Q_HYDRATE_ACTION: {
            "type": "choice",
            "instructions": (
                "Choose the hydrate action for this redacted memory candidate "
                "relative to the latest user ask (query_hash only unless preview present)."
            ),
            "criteria": actions,
        },
        Q_NEED_FOR_NEXT_TURN: {
            "type": "score",
            "instructions": (
                "How needed is this candidate for answering the latest ask on the next turn?"
            ),
            "criteria": [1, 2, 3, 4, 5],
        },
        Q_STILL_MATTERS: {
            "type": "noul",
            "instructions": (
                "Does this candidate still matter for the latest ask "
                "(yes ≈ hydrate consideration; no ≈ safe to skip)?"
            ),
        },
    }
    if optional_network:
        questions[Q_NETWORK_ROUTE] = {
            "type": "choice",
            "instructions": "Optional memory-network route for this candidate.",
            "criteria": [r.value for r in NetworkRoute],
        }
    if optional_reflect:
        questions[Q_TRIGGER_REFLECT] = {
            "type": "noul",
            "instructions": (
                "Should the agent trigger a reflect/compaction pass "
                "for this candidate?"
            ),
        }
    return questions


def _hydrate_questions_batched(
    node_ids: list[str],
    *,
    optional_network: bool,
    optional_reflect: bool,
) -> dict[str, dict[str, Any]]:
    """Prefix each hydrate question with ``{node_id}__`` for a multi-candidate POST."""
    base = _hydrate_questions(
        optional_network=optional_network, optional_reflect=optional_reflect
    )
    out: dict[str, dict[str, Any]] = {}
    for nid in node_ids:
        for qid, spec in base.items():
            keyed = dict(spec)
            # Keep criteria/instructions; annotate which candidate in instructions.
            instr = str(keyed.get("instructions", ""))
            keyed["instructions"] = f"[candidate {nid}] {instr}"
            out[f"{nid}__{qid}"] = keyed
    return out


def _split_batched_answers(
    answers: dict[str, Any], *, node_ids: list[str]
) -> list[JevBatchResponse]:
    """Split ``{node_id}__{qid}`` answer keys into per-node ``JevBatchResponse``."""
    by_node: dict[str, dict[str, Any]] = {nid: {} for nid in node_ids}
    for key, ans in answers.items():
        if "__" not in str(key):
            continue
        nid, _, qid = str(key).partition("__")
        if nid not in by_node or not qid:
            continue
        by_node[nid][qid] = ans

    results: list[JevBatchResponse] = []
    for nid in node_ids:
        node_answers = by_node.get(nid) or {}
        if not node_answers:
            results.append(
                JevBatchResponse(node_id=nid, malformed=True, error="missing_node_answers")
            )
            continue
        mapped = _map_system_one_answers(node_answers)
        if mapped is None:
            results.append(
                JevBatchResponse(node_id=nid, malformed=True, error="bad_answers")
            )
            continue
        results.append(JevBatchResponse(node_id=nid, results=mapped))
    return results


def _admit_questions() -> dict[str, dict[str, Any]]:
    return {
        Q_ADMIT: {
            "type": "choice",
            "instructions": "Should this proposed marker be admitted into the topology store?",
            "criteria": [d.value for d in AdmitDecision],
        },
        Q_NODE_KIND: {
            "type": "choice",
            "instructions": "Classify the proposed marker kind.",
            "criteria": [k.value for k in NodeKind],
        },
    }


def _emit_questions() -> dict[str, dict[str, Any]]:
    return {
        Q_EMIT_ACTION: {
            "type": "choice",
            "instructions": (
                "Choose the egress/writeback emit action for this redacted payload. "
                "allow_emit only when safe and on-topic; otherwise deny_emit, "
                "redact_further, or escalate_human."
            ),
            "criteria": [a.value for a in EmitAction],
        },
        Q_LEAK_RISK: {
            "type": "noul",
            "instructions": (
                "Does this proposed summary risk leaking secrets, PII, or credentials?"
            ),
        },
        Q_ON_TOPIC: {
            "type": "noul",
            "instructions": (
                "Is this proposed summary on-topic for the intended emit / egress channel?"
            ),
        },
    }


def _writeback_questions() -> dict[str, dict[str, Any]]:
    return {
        Q_WRITEBACK_ACTION: {
            "type": "choice",
            "instructions": (
                "Choose the durable writeback action for this redacted proposed marker. "
                "allow_writeback only when safe; mid uncertainty → escalate_human."
            ),
            "criteria": [a.value for a in WritebackAction],
        },
        Q_WRITEBACK_NEED: {
            "type": "score",
            "instructions": "How needed is this durable write for long-term memory quality?",
            "criteria": [1, 2, 3, 4, 5],
        },
        Q_WRITEBACK_STILL_SAFE: {
            "type": "noul",
            "instructions": (
                "Is it still safe to write this marker to durable LTM / wiki / bank?"
            ),
        },
    }



def _map_system_one_answers(
    answers: dict[str, Any],
) -> dict[str, JevQuestionResult] | None:
    """Map System One ``answers`` dict → JevQuestionResult.

    Noul confidence uses the raw yes-probability ``noul`` (not abs-scaled).
    """
    results: dict[str, JevQuestionResult] = {}
    for qid, ans in answers.items():
        if not isinstance(ans, dict):
            return None
        atype = ans.get("type")
        try:
            if atype == "choice":
                if "choice" not in ans or "confidence" not in ans:
                    return None
                value: Any = ans["choice"]
                confidence = float(ans["confidence"])
            elif atype == "score":
                if "score" not in ans or "confidence" not in ans:
                    return None
                value = ans["score"]
                confidence = float(ans["confidence"])
            elif atype == "noul":
                if "noul" not in ans:
                    return None
                noul = float(ans["noul"])
                value = noul >= 0.5
                # Prefer confidence=noul (yes-probability) for policy thresholds.
                confidence = noul
            else:
                return None
            # Clamp confidence into [0, 1] for pydantic; malformed if out of range badly.
            if confidence < 0.0 or confidence > 1.0:
                # Allow slight float noise; hard reject otherwise.
                if confidence < -0.01 or confidence > 1.01:
                    return None
                confidence = max(0.0, min(1.0, confidence))
            results[qid] = JevQuestionResult(
                question_id=qid,
                value=value,
                confidence=confidence,
                raw=ans,
            )
        except (TypeError, ValueError):
            return None
    return results
