"""Jev reconcile question pack — Choice criteria dicts; Score string levels.

Pin: jev-1.13.0 (PLAN §4.6).
"""

from __future__ import annotations

from typing import Any

# Question ids (normative)
Q_RELATION = "relation"
Q_SHOULD_FORGET = "should_forget_incumbent"
Q_TTL_URGENCY = "ttl_urgency"
Q_PROFILE_WORTHINESS = "profile_worthiness"
Q_NEEDS_HUMAN = "needs_human"
Q_SALIENCE_TIER = "salience_tier"

RECONCILE_QUESTION_IDS = (
    Q_RELATION,
    Q_SHOULD_FORGET,
    Q_TTL_URGENCY,
    Q_PROFILE_WORTHINESS,
    Q_NEEDS_HUMAN,
    Q_SALIENCE_TIER,
)

RELATION_CRITERIA: dict[str, str] = {
    "same_fact": (
        "New candidate is the same belief as the incumbent (same FactKey meaning); "
        "update salience/TTL/confidence only unless value_struct materially changed."
    ),
    "supersedes": (
        "New candidate replaces the incumbent belief on the same FactKey "
        "(e.g. weather sunny → rainy)."
    ),
    "contradicts": (
        "New candidate contradicts the incumbent belief; may require forget "
        "or human escalation."
    ),
    "side_thread": (
        "Related but distinct belief — should live on a different FactKey; "
        "do not mutate the incumbent."
    ),
    "noise": "Not a useful belief update; ignore / no_op.",
    "other": "None of the closed relations clearly apply.",
}

SALIENCE_TIER_CRITERIA: dict[str, str] = {
    "childhood_play": "Childhood / play-oriented belief (may be demoted by adult_safety).",
    "adult_safety": "Adult safety / caution belief (wins over childhood_play on conflict).",
    "routine": "Routine ongoing preference or state.",
    "ephemeral": "Short-lived observation (weather, temporary state).",
}

# Score criteria: ordered string levels low → high urgency / short TTL
TTL_URGENCY_LEVELS: list[str] = [
    "permanent",
    "years",
    "months",
    "weeks",
    "days",
    "hours",
]


def _choice_criteria(descriptions: dict[str, str]) -> dict[str, str | None]:
    """System One Choice criteria: ``{option_key: description}`` (not a list)."""
    return dict(descriptions)


def build_reconcile_questions() -> dict[str, dict[str, Any]]:
    """Typed questions for JevReconcileGate (PLAN §4.6)."""
    return {
        Q_RELATION: {
            "type": "choice",
            "instructions": (
                "Classify the relation between state.new and state.incumbents[0] "
                "(same-FactKey C1). Prefer supersedes for material value changes on "
                "the same key; contradicts when beliefs conflict; same_fact when only "
                "metadata should update; noise when irrelevant."
            ),
            "criteria": _choice_criteria(RELATION_CRITERIA),
        },
        Q_SHOULD_FORGET: {
            "type": "noul",
            "instructions": (
                "Should the incumbent leave the active set (forget / demote) if the "
                "new candidate is admitted? High yes when supersedes/contradicts with "
                "a clear winner."
            ),
        },
        Q_TTL_URGENCY: {
            "type": "score",
            "instructions": (
                "How urgent is TTL / expiry for this belief? Levels ordered "
                "permanent → hours (low urgency → high urgency / short life)."
            ),
            "criteria": list(TTL_URGENCY_LEVELS),
        },
        Q_PROFILE_WORTHINESS: {
            "type": "noul",
            "instructions": (
                "Should this belief belong in static/dynamic profile inject?"
            ),
        },
        Q_NEEDS_HUMAN: {
            "type": "noul",
            "instructions": (
                "Is this sensitive (identity/medical/legal/financial/minors/"
                "precise location/other) and must escalate to a human before write?"
            ),
        },
        Q_SALIENCE_TIER: {
            "type": "choice",
            "instructions": (
                "Choose the salience tier for the new candidate (Choice only, not Score)."
            ),
            "criteria": _choice_criteria(SALIENCE_TIER_CRITERIA),
        },
    }
