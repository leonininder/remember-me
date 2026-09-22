"""JevReconcileGate — FakeJev + HttpJev reconcile (Phase C, PLAN §4.6).

Choice criteria = dict; Score = ordered string levels; pin jev-1.13.0.
C1 MVP: same-FactKey incumbents only. Fail-closed on deny/timeout/malformed.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from remember_me.tfl.ledger import FactLedger
from remember_me.tfl.ontology import Ontology, mint_fact_key
from remember_me.tfl.policy import (
    T_ACCEPT_RECONCILE,
    T_ESCALATE_RECONCILE,
    ApplyAction,
    ApplyDecision,
    answers_from_override,
    map_gate_failure,
    map_reconcile_policy,
    normalize_answers,
)
from remember_me.tfl.quarantine import QuarantineQueue
from remember_me.tfl.questions import RECONCILE_QUESTION_IDS, build_reconcile_questions
from remember_me.tfl.redact import (
    assert_reconcile_outbound_safe,
    build_escalation_snapshot,
    build_reconcile_state,
    candidate_to_reconcile_dict,
    fact_version_to_reconcile_dict,
)
from remember_me.tfl.types import CandidateFact, FactVersion
from remember_me.tfl.validate import validate_candidate
from remember_me.types import JEV_MODEL_PIN, JevBatchResponse, JevQuestionResult


@runtime_checkable
class JevReconcileGate(Protocol):
    model_pin: str

    def reconcile(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]] | None = None,
    ) -> JevBatchResponse:
        """Run reconcile questions on redacted state."""
        ...


class FakeJevReconcileGate:
    """Deterministic offline reconcile gate (CI / unit). No network."""

    def __init__(
        self,
        *,
        model_pin: str = JEV_MODEL_PIN,
        answers: dict[str, Any] | None = None,
        force_timeout: bool = False,
        force_deny: bool = False,
        force_malformed: bool = False,
    ) -> None:
        self.model_pin = model_pin
        self.answers = dict(answers or {})
        self.force_timeout = force_timeout
        self.force_deny = force_deny
        self.force_malformed = force_malformed
        self.call_count = 0
        self.last_outbound: dict[str, Any] | None = None
        self.calls: list[dict[str, Any]] = []

    def reconcile(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]] | None = None,
    ) -> JevBatchResponse:
        self.call_count += 1
        assert_reconcile_outbound_safe(state)
        self.last_outbound = state
        self.calls.append(
            {"state": state, "questions": list((questions or {}).keys())}
        )
        nid = str((state.get("new") or {}).get("fact_key") or "reconcile")

        if self.force_timeout:
            return JevBatchResponse(node_id=nid, timed_out=True, error="timeout")
        if self.force_deny:
            return JevBatchResponse(node_id=nid, denied=True, error="denied")
        if self.force_malformed:
            return JevBatchResponse(node_id=nid, malformed=True, error="malformed")

        flat = answers_from_override(self.answers)
        results: dict[str, JevQuestionResult] = {
            "relation": JevQuestionResult(
                question_id="relation",
                value=flat.relation,
                confidence=flat.relation_confidence,
            ),
            "should_forget_incumbent": JevQuestionResult(
                question_id="should_forget_incumbent",
                value=flat.should_forget_incumbent,
                confidence=(
                    flat.should_forget_confidence
                    if flat.should_forget_confidence
                    else (0.95 if flat.should_forget_incumbent else 0.05)
                ),
            ),
            "ttl_urgency": JevQuestionResult(
                question_id="ttl_urgency",
                value=flat.ttl_urgency or "permanent",
                confidence=0.9,
            ),
            "profile_worthiness": JevQuestionResult(
                question_id="profile_worthiness",
                value=flat.profile_worthiness,
                confidence=0.9 if flat.profile_worthiness else 0.1,
            ),
            "needs_human": JevQuestionResult(
                question_id="needs_human",
                value=flat.needs_human,
                confidence=(
                    flat.needs_human_confidence
                    if flat.needs_human_confidence
                    else (0.95 if flat.needs_human else 0.05)
                ),
            ),
            "salience_tier": JevQuestionResult(
                question_id="salience_tier",
                value=flat.salience_tier or "routine",
                confidence=0.9,
            ),
        }
        return JevBatchResponse(node_id=nid, results=results)


class HttpJevReconcileGate:
    """HTTP System One reconcile gate. Failures → denied/timed_out/malformed."""

    DEFAULT_BASE_URL = "https://api.typesafe.ai/v1/systemone"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model_pin: str = JEV_MODEL_PIN,
        timeout_s: float = 5.0,
    ) -> None:
        if api_key is None:
            self.api_key = os.environ.get("TYPESAFE_API_KEY", "")
        else:
            self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_pin = model_pin
        self.timeout_s = timeout_s
        self.call_count = 0
        self.last_outbound: dict[str, Any] | None = None
        self.last_usage: dict[str, Any] | None = None
        self.last_response_model: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY not set; use FakeJevReconcileGate")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def reconcile(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]] | None = None,
    ) -> JevBatchResponse:
        self.call_count += 1
        assert_reconcile_outbound_safe(state)
        self.last_outbound = state
        nid = str((state.get("new") or {}).get("fact_key") or "reconcile")
        q = questions or build_reconcile_questions()
        payload = {
            "model": self.model_pin,
            "state": state,
            "questions": q,
        }
        return self._post_system_one(payload, node_id=nid)

    def _post_system_one(self, payload: dict[str, Any], *, node_id: str) -> JevBatchResponse:
        # Reuse mapping from jev_client
        from remember_me.jev_client import _map_system_one_answers

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
        except Exception as exc:
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
        # Require core reconcile question ids
        missing = [qid for qid in ("relation",) if qid not in mapped]
        if missing:
            return JevBatchResponse(
                node_id=node_id,
                malformed=True,
                error=f"missing_questions:{','.join(missing)}",
            )
        return JevBatchResponse(node_id=node_id, results=mapped)



def _as_reconcile_result(
    decision: ApplyDecision,
    *,
    fact_key: str | None = None,
    fact_version: FactVersion | None = None,
    quarantine_id: str | None = None,
    applied: bool = False,
) -> ReconcileResult:
    return ReconcileResult(
        action=decision.action,
        answers=decision.answers,
        reason=decision.reason,
        fail_closed=decision.fail_closed,
        demote_profile=decision.demote_profile,
        prefer_expire=decision.prefer_expire,
        escalation=decision.escalation,
        quarantine_reason=decision.quarantine_reason,
        fact_version=fact_version,
        quarantine_id=quarantine_id,
        fact_key=fact_key,
        applied=applied,
    )


class ReconcileResult(ApplyDecision):
    """ApplyDecision plus optional resulting FactVersion / quarantine id."""

    fact_version: FactVersion | None = None
    quarantine_id: str | None = None
    fact_key: str | None = None
    applied: bool = False


class ReconcileEngine:
    """Validate → same-FactKey lookup → JevReconcileGate → APPLY or quarantine.

    C1: same-FactKey only. Never md-append. Never drop on gate failure.
    """

    def __init__(
        self,
        ledger: FactLedger,
        gate: JevReconcileGate,
        *,
        quarantine: QuarantineQueue | None = None,
        ontology: Ontology | None = None,
        t_accept: float = T_ACCEPT_RECONCILE,
        t_escalate: float = T_ESCALATE_RECONCILE,
        max_incumbents: int = 5,
    ) -> None:
        self.ledger = ledger
        self.gate = gate
        self.quarantine = quarantine
        self.ontology = ontology or Ontology.load()
        self.t_accept = t_accept
        self.t_escalate = t_escalate
        self.max_incumbents = max_incumbents
        self.last_decision: ReconcileResult | None = None

    def _enqueue_quarantine(
        self,
        candidate: CandidateFact | dict[str, Any],
        *,
        reason: str,
        fact_key_hint: str | None = None,
    ) -> str | None:
        if self.quarantine is None:
            return None
        payload = (
            candidate.model_dump(mode="json")
            if isinstance(candidate, CandidateFact)
            else dict(candidate)
        )
        item = self.quarantine.enqueue(
            payload, reason=reason, fact_key_hint=fact_key_hint
        )
        return item.id

    def reconcile_candidate(self, candidate: CandidateFact | dict[str, Any]) -> ReconcileResult:
        """Run full C1 reconcile path for one CandidateFact."""
        # Schema validate
        if isinstance(candidate, dict):
            try:
                cand = CandidateFact.model_validate(candidate)
            except Exception as exc:
                qid = self._enqueue_quarantine(
                    candidate if isinstance(candidate, dict) else {},
                    reason=f"schema:{exc}",
                )
                out = ReconcileResult(
                    action=ApplyAction.QUARANTINE,
                    reason=f"schema:{exc}",
                    fail_closed=True,
                    quarantine_reason=f"schema:{exc}",
                    quarantine_id=qid,
                    applied=False,
                )
                self.last_decision = out
                return out
        else:
            cand = candidate

        vres = validate_candidate(cand, ontology=self.ontology)
        if not vres.ok or not vres.fact_key:
            reason = vres.reason or "validate_failed"
            qid = self._enqueue_quarantine(
                cand, reason=reason, fact_key_hint=vres.fact_key
            )
            out = ReconcileResult(
                action=ApplyAction.QUARANTINE,
                reason=reason,
                fail_closed=True,
                quarantine_reason=reason,
                quarantine_id=qid,
                fact_key=vres.fact_key,
                applied=False,
            )
            self.last_decision = out
            return out

        fact_key = vres.fact_key
        # C1: same-FactKey incumbent only
        incumbent = self.ledger.get_active(fact_key)
        incumbents = [fact_version_to_reconcile_dict(incumbent)] if incumbent else []
        new_dict = candidate_to_reconcile_dict(
            fact_key=fact_key,
            value_struct=cand.value_struct,
            salience_tier=cand.salience_hint,
        )
        state = build_reconcile_state(
            new_fact=new_dict,
            incumbents=incumbents,
            max_incumbents=self.max_incumbents,
        )
        assert_reconcile_outbound_safe(state)

        questions = build_reconcile_questions()
        # Ensure question pack ids match protocol seed
        assert set(questions.keys()) >= set(RECONCILE_QUESTION_IDS)

        response = self.gate.reconcile(state, questions)

        snap_base = {
            **new_dict,
            "source_event_id": cand.source_event_id,
            "extract_method": cand.extract_method,
            "candidate_entity": cand.entity,
            "candidate_attribute": cand.attribute,
            "candidate_qualifier": cand.qualifier,
            "incumbent_version_id": incumbent.version_id if incumbent else None,
        }

        if response.failed:
            decision = map_gate_failure(response, snapshot=snap_base)
            qid = self._enqueue_quarantine(
                cand, reason=decision.quarantine_reason or decision.reason, fact_key_hint=fact_key
            )
            out = _as_reconcile_result(
                decision, fact_key=fact_key, quarantine_id=qid, applied=False
            )
            self.last_decision = out
            return out

        answers = normalize_answers(
            response.results,
            t_accept=self.t_accept,
            t_escalate=self.t_escalate,
        )
        decision = map_reconcile_policy(
            answers,
            has_incumbent=incumbent is not None,
            new_value_struct=cand.value_struct,
            incumbent_value_struct=incumbent.value_struct if incumbent else None,
            incumbent_salience=incumbent.salience_tier if incumbent else None,
            snapshot=snap_base,
            t_accept=self.t_accept,
        )

        if decision.action == ApplyAction.QUARANTINE:
            qid = self._enqueue_quarantine(
                cand, reason=decision.quarantine_reason or decision.reason, fact_key_hint=fact_key
            )
            out = _as_reconcile_result(
                decision, fact_key=fact_key, quarantine_id=qid, applied=False
            )
            self.last_decision = out
            return out

        if decision.action == ApplyAction.ESCALATE_HUMAN:
            qid = self._enqueue_quarantine(
                cand,
                reason=f"escalate_human:{decision.reason}",
                fact_key_hint=fact_key,
            )
            out = _as_reconcile_result(
                decision, fact_key=fact_key, quarantine_id=qid, applied=False
            )
            self.last_decision = out
            return out

        if decision.action == ApplyAction.NO_OP:
            out = _as_reconcile_result(
                decision, fact_key=fact_key, applied=False
            )
            self.last_decision = out
            return out

        # APPLY mutations
        sal = answers.salience_tier
        ttl = answers.ttl_urgency
        conf = answers.relation_confidence
        fv: FactVersion | None = None

        if decision.action == ApplyAction.SUPERSEDE:
            fv = self.ledger.supersede(
                fact_key,
                cand.value_struct,
                observed_at=cand.observed_at,
                source_event_id=cand.source_event_id,
                confidence=conf,
                salience_tier=sal,
                ttl_hint=ttl,
                should_forget_incumbent_applied=answers.should_forget_incumbent,
            )
        elif decision.action == ApplyAction.UPSERT:
            fv = self.ledger.upsert(
                fact_key,
                cand.value_struct,
                observed_at=cand.observed_at,
                source_event_id=cand.source_event_id,
                confidence=conf,
                salience_tier=sal,
                ttl_hint=ttl,
            )
        elif decision.action == ApplyAction.EXPIRE:
            if incumbent:
                self.ledger.expire(fact_key)
            fv = self.ledger.upsert(
                fact_key,
                cand.value_struct,
                observed_at=cand.observed_at,
                source_event_id=cand.source_event_id,
                confidence=conf,
                salience_tier=sal,
                ttl_hint=ttl,
            )
        elif decision.action == ApplyAction.TOMBSTONE:
            if incumbent:
                self.ledger.tombstone(fact_key)
            out = _as_reconcile_result(
                decision, fact_key=fact_key, applied=True
            )
            self.last_decision = out
            return out
        else:
            # Unknown action — fail-closed quarantine
            qid = self._enqueue_quarantine(
                cand, reason=f"unknown_action:{decision.action}", fact_key_hint=fact_key
            )
            out = ReconcileResult(
                action=ApplyAction.QUARANTINE,
                answers=answers,
                reason=f"unknown_action:{decision.action}",
                fail_closed=True,
                quarantine_reason=f"unknown_action:{decision.action}",
                quarantine_id=qid,
                fact_key=fact_key,
                applied=False,
            )
            self.last_decision = out
            return out

        self.ledger.assert_no_dual_active()
        out = _as_reconcile_result(
            decision, fact_key=fact_key, fact_version=fv, applied=True
        )
        # Attach escalation snapshot allowlist check
        if out.escalation is not None:
            out.escalation.redacted_snapshot = build_escalation_snapshot(
                out.escalation.redacted_snapshot
            )
        self.last_decision = out
        return out


def mint_key_for_candidate(
    candidate: CandidateFact, ontology: Ontology | None = None
) -> str:
    """Helper: mint FactKey via ontology (user.* only for domain examples)."""
    ont = ontology or Ontology.load()
    return mint_fact_key(
        candidate.entity,
        candidate.attribute,
        candidate.qualifier,
        ontology=ont,
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
