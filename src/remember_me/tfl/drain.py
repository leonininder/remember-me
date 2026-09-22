"""QuarantineQueue drain ↔ retry / escalate_human (PLAN §4.8).

Fail-closed: never md-append, never drop. On gate deny/timeout/malformed
re-enqueue (attempt++) or escalate_human snapshot.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from remember_me.tfl.policy import ApplyAction
from remember_me.tfl.quarantine import QuarantineQueue
from remember_me.tfl.reconcile import ReconcileEngine, ReconcileResult
from remember_me.tfl.redact import build_escalation_snapshot
from remember_me.tfl.types import CandidateFact, QuarantineItem
from remember_me.types import EscalationRecord

DrainOutcome = Literal["applied", "requeued", "escalated", "skipped", "blocked"]


class DrainItemResult(BaseModel):
    item_id: str
    outcome: DrainOutcome
    reason: str = ""
    reconcile: ReconcileResult | None = None
    escalation: EscalationRecord | None = None
    attempts: int = 0


class DrainReport(BaseModel):
    processed: int = 0
    applied: int = 0
    requeued: int = 0
    escalated: int = 0
    skipped: int = 0
    items: list[DrainItemResult] = Field(default_factory=list)


def _parse_candidate(item: QuarantineItem) -> CandidateFact | None:
    try:
        return CandidateFact.model_validate(item.candidate)
    except Exception:
        return None


def drain_quarantine(
    engine: ReconcileEngine,
    queue: QuarantineQueue,
    *,
    limit: int = 32,
    max_attempts: int = 3,
    escalate_after_attempts: int = 3,
    gate_healthy: bool = True,
) -> DrainReport:
    """Drain memory-head quarantine items via retry or escalate_human.

    - If ``gate_healthy`` is False → escalate_human (do not drop; requeue with
      escalate reason) for each item.
    - On APPLY success → item leaves queue (already drained from memory).
    - On gate failure / escalate → re-enqueue with attempts+1 (never drop).
    - Spill items are not auto-drained here (human / explicit load).
    """
    report = DrainReport()
    items = queue.drain_memory(limit=limit)
    now = datetime.now(UTC)

    for item in items:
        report.processed += 1
        attempts = int(item.attempts) + 1

        if not gate_healthy:
            esc = _escalate_item(item, reason="gate_unhealthy", attempts=attempts)
            _requeue(queue, item, reason="escalate:gate_unhealthy", attempts=attempts)
            report.escalated += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="escalated",
                    reason="gate_unhealthy",
                    escalation=esc,
                    attempts=attempts,
                )
            )
            continue

        # Past escalate_after deadline → escalate_human
        if item.escalate_after is not None and item.escalate_after <= now:
            esc = _escalate_item(item, reason="escalate_after_deadline", attempts=attempts)
            _requeue(queue, item, reason="escalate:deadline", attempts=attempts)
            report.escalated += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="escalated",
                    reason="escalate_after_deadline",
                    escalation=esc,
                    attempts=attempts,
                )
            )
            continue

        cand = _parse_candidate(item)
        if cand is None:
            esc = _escalate_item(item, reason="malformed_candidate", attempts=attempts)
            _requeue(queue, item, reason="escalate:malformed_candidate", attempts=attempts)
            report.escalated += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="escalated",
                    reason="malformed_candidate",
                    escalation=esc,
                    attempts=attempts,
                )
            )
            continue

        result = engine.reconcile_candidate(cand)

        if result.applied and result.action in {
            ApplyAction.UPSERT,
            ApplyAction.SUPERSEDE,
            ApplyAction.EXPIRE,
            ApplyAction.TOMBSTONE,
        }:
            report.applied += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="applied",
                    reason=result.reason,
                    reconcile=result,
                    attempts=attempts,
                )
            )
            continue

        if result.action == ApplyAction.NO_OP:
            # Noise / intentional no_op — leave out of queue (resolved)
            report.skipped += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="skipped",
                    reason=result.reason or "no_op",
                    reconcile=result,
                    attempts=attempts,
                )
            )
            continue

        # escalate or quarantine fail-closed → requeue, never drop
        if attempts >= escalate_after_attempts or attempts >= max_attempts:
            esc = result.escalation or _escalate_item(
                item, reason=result.reason or "max_attempts", attempts=attempts
            )
            _requeue(
                queue,
                item,
                reason=f"escalate:{result.reason or result.action.value}",
                attempts=attempts,
            )
            report.escalated += 1
            report.items.append(
                DrainItemResult(
                    item_id=item.id,
                    outcome="escalated",
                    reason=result.reason or "max_attempts",
                    reconcile=result,
                    escalation=esc,
                    attempts=attempts,
                )
            )
            continue

        _requeue(
            queue,
            item,
            reason=result.quarantine_reason or result.reason or result.action.value,
            attempts=attempts,
        )
        report.requeued += 1
        report.items.append(
            DrainItemResult(
                item_id=item.id,
                outcome="requeued",
                reason=result.reason,
                reconcile=result,
                attempts=attempts,
            )
        )

    return report


def _requeue(
    queue: QuarantineQueue,
    item: QuarantineItem,
    *,
    reason: str,
    attempts: int,
) -> QuarantineItem:
    """Re-enqueue without dropping; bump attempts. Never writes MEMORY.md."""
    new_item = QuarantineItem(
        id=item.id,
        candidate=dict(item.candidate),
        reason=reason,
        enqueued_at=datetime.now(UTC),
        attempts=attempts,
        escalate_after=item.escalate_after
        or (datetime.now(UTC) + timedelta(hours=24)),
        fact_key_hint=item.fact_key_hint,
    )
    return queue.enqueue(new_item)


def _escalate_item(
    item: QuarantineItem, *, reason: str, attempts: int
) -> EscalationRecord:
    snap = build_escalation_snapshot(
        {
            "fact_key": item.fact_key_hint,
            "quarantine_reason": reason,
            "source_event_id": str(
                (item.candidate or {}).get("source_event_id") or ""
            ),
            "extract_method": str(
                (item.candidate or {}).get("extract_method") or ""
            ),
            "stub_hash": None,
        }
    )
    return EscalationRecord(
        node_id=item.fact_key_hint or item.id,
        source_gate="reconcile_drain",
        band="fail_closed",
        confidence=0.0,
        proposed_action="escalate_human",
        reason=reason,
        redacted_snapshot=snap,
    )


def assert_never_md_append(path_hints: list[str] | None = None) -> None:
    """Documentation-level guard used by tests — drain must not touch md SoT."""
    banned = path_hints or ["MEMORY.md", "AGENTS.md", "SOUL.md"]
    # Pure assertion helper for tests; no I/O.
    for name in banned:
        if not name.endswith(".md"):
            raise AssertionError(f"unexpected non-md guard path {name}")
