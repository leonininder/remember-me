"""Phase C stubs — Fake only; HttpJev reconcile not implemented in Phase B."""

from __future__ import annotations

from typing import Any


class FakeJevReconcileGate:
    """Deterministic stub so Phase B imports do not pull HttpJev reconcile.

    Phase C will replace with real FakeJev + HttpJev reconcile wiring.
    """

    def __init__(self, *, answers: dict[str, Any] | None = None) -> None:
        self.answers = dict(answers or {})
        self.calls: list[dict[str, Any]] = []

    def reconcile(
        self, state: dict[str, Any], questions: list[str] | None = None
    ) -> dict[str, Any]:
        self.calls.append({"state": state, "questions": list(questions or [])})
        # Fail-closed default: escalate_human until Phase C implements policy.
        out = {
            "relation": self.answers.get("relation", "other"),
            "should_forget_incumbent": self.answers.get("should_forget_incumbent", False),
            "needs_human": self.answers.get("needs_human", True),
            "salience_tier": self.answers.get("salience_tier", "routine"),
            "ttl_urgency": self.answers.get("ttl_urgency", "permanent"),
            "profile_worthiness": self.answers.get("profile_worthiness", False),
        }
        out.update({k: v for k, v in self.answers.items() if k not in out})
        return out


class HttpJevReconcileGate:  # pragma: no cover - Phase C
    """Placeholder — not implemented in Phase B."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "HttpJevReconcileGate is Phase C; use FakeJevReconcileGate in Phase B"
        )
